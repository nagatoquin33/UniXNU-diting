import argparse
from pathlib import Path
import subprocess
import tempfile

parser = argparse.ArgumentParser()
parser.add_argument('--xnu-source', type=Path, required=True)
args = parser.parse_args()
repo = Path(__file__).resolve().parents[1]
with tempfile.TemporaryDirectory(prefix='pong-data-tmp-test-') as d:
    root = Path(d)
    source = root / 'bsd/kern/kern_exec.c'
    source.parent.mkdir(parents=True)
    source.write_bytes((args.xnu_source / 'bsd/kern/kern_exec.c').read_bytes())
    for name in ('0001-pong-darwin24.patch', 'zzzzzzzzz-pong-exec-diagnostic.patch',
                 'zzzzzzzzzz-pong-data-tmp.patch'):
        subprocess.run(['git', 'apply', '--include=bsd/kern/kern_exec.c',
                        str(repo / 'patches/xnu-ipados18' / name)], cwd=root,
                       capture_output=True, check=True)
    text = source.read_text()
    start = text.index('\tif (!error) {\n\t\tnative_owner_data_stage = 4;')
    end = text.index('\ndone:\n\tif (data_root)', start)
    block = text[start:end]
    c = r"""
#include <stdio.h>
#include <stdint.h>
#include <string.h>
#include <errno.h>
typedef unsigned long user_addr_t;
struct mkdir_args { user_addr_t path; int mode; };
struct chmod_args { user_addr_t path; int mode; };
static int state, mkdir_calls, chmod_calls;
static int copyout(const char *s, user_addr_t p, unsigned long n) {
    (void)p; return strcmp(s, "/private/var/tmp") || n != sizeof("/private/var/tmp") ? EINVAL : 0;
}
static int mkdir(void *p, struct mkdir_args *a, int *r) {
    (void)p; (void)r; mkdir_calls++; if (a->mode != 01777) return EINVAL;
    return state == 1 ? EEXIST : state == 2 ? EROFS : 0;
}
static int chmod(void *p, struct chmod_args *a, int *r) {
    (void)p; (void)r; chmod_calls++; return a->mode == 01777 ? 0 : EINVAL;
}
static int run(int error) {
    int native_owner_data_stage = 0, result = 0; void *p = 0; user_addr_t scratch = 100;
""" + block + r"""
    return native_owner_data_stage;
}
int main(void) {
    if (run(1) || mkdir_calls || chmod_calls) return 1;
    state=0; if (run(0)!=4 || mkdir_calls!=1 || chmod_calls!=1) return 2;
    state=1; if (run(0)!=4 || mkdir_calls!=2 || chmod_calls!=1) return 3;
    state=2; if (run(0)!=4 || mkdir_calls!=3 || chmod_calls!=1) return 4;
    return 0;
}
"""
    test = root / 'check.c'
    test.write_text(c)
    subprocess.run(['clang', '-std=gnu11', '-Wall', '-Wextra', '-Werror', str(test), '-o', str(root / 'check')], check=True)
    subprocess.run([str(root / 'check')], check=True)
    print('XNU patch applies; tmp mode, existing directory and mount failure paths verified')
