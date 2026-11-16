#!/usr/bin/env python3
"""Generate the Diting GPU primelist from the actual OS volume.

The shipped 10-line primelist was derived on the build host and six of its ten
paths do not exist in the iPadOS 18.7.10 OS volume. This script enumerates the
.metallib files that really exist in the OS window image instead, so the plugin
primelist always matches the userland that boots.

Reads only: tools/apfs/apfs.py walks the APFS container (raw partition or .dmg).
The output is deterministic: absolute paths, sorted, unique, LF, trailing newline.

Usage:
    scripts/gen-diting-prime-list.py --image prepared-os.img --out primelist
    scripts/gen-diting-prime-list.py --image prepared-os.img --out primelist --verify
    scripts/gen-diting-prime-list.py --image os.dmg --volume CrystalUpdate22H374.J171J172OS \
        --out primelist --verify --drop-missing

--verify stats every emitted path with the same APFS reader; by default it
refuses (exit 1) and lists paths that do not resolve. --drop-missing keeps only
the paths that do resolve (the count and the dropped list are printed).
"""
import argparse
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_TOOL = ROOT / 'tools/apfs/apfs.py'


def apfs(tool, args):
    return subprocess.run([sys.executable, str(tool), *args], text=True,
                          stdout=subprocess.PIPE, stderr=subprocess.PIPE)


def list_metallibs(tool, image, volume):
    command = ['tree', str(image), '/System']
    if volume:
        command += ['-v', volume]
    completed = apfs(tool, command)
    if completed.returncode != 0:
        raise SystemExit(f'apfs.py tree failed: {completed.stderr.strip()}')
    paths = set()
    for line in completed.stdout.splitlines():
        line = line.strip()
        if not line or line.endswith('/') or not line.lower().endswith('.metallib'):
            continue
        paths.add(line if line.startswith('/') else '/' + line)
    return sorted(paths)


def verify_paths(tool, image, paths, volume):
    missing = []
    for path in paths:
        command = ['stat', str(image), path]
        if volume:
            command += ['-v', volume]
        completed = apfs(tool, command)
        if completed.returncode != 0 or 'no such path' in completed.stdout + completed.stderr:
            missing.append(path)
    return missing


def main():
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--image', required=True, type=Path,
                        help='OS window image or DMG (read-only)')
    parser.add_argument('--out', required=True, type=Path, help='primelist file to write')
    parser.add_argument('--volume', default=None,
                        help='APFS volume name/index for apfs.py -v (default: first volume)')
    parser.add_argument('--tool', type=Path, default=DEFAULT_TOOL,
                        help=f'APFS reader (default: {DEFAULT_TOOL})')
    parser.add_argument('--verify', action='store_true',
                        help='stat every path and refuse (exit 1) on unresolvable ones')
    parser.add_argument('--drop-missing', action='store_true',
                        help='with --verify, drop unresolvable paths instead of failing')
    args = parser.parse_args()

    if not args.image.is_file():
        raise SystemExit(f'image not found: {args.image}')
    if not args.tool.is_file():
        raise SystemExit(f'APFS reader not found: {args.tool}')

    paths = list_metallibs(args.tool, args.image, args.volume)
    if not paths:
        raise SystemExit(f'no .metallib paths under /System in {args.image}')

    if args.verify:
        missing = verify_paths(args.tool, args.image, paths, args.volume)
        if missing:
            if not args.drop_missing:
                print(f'FAIL {len(missing)} of {len(paths)} paths do not resolve:', file=sys.stderr)
                for path in missing:
                    print('  ' + path, file=sys.stderr)
                raise SystemExit(1)
            print(f'dropped {len(missing)} unresolvable path(s):', file=sys.stderr)
            for path in missing:
                print('  ' + path, file=sys.stderr)
            paths = [path for path in paths if path not in set(missing)]

    text = '\n'.join(paths) + '\n'
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(text)
    import hashlib
    digest = hashlib.sha256(text.encode()).hexdigest()
    print(f'{len(paths)} paths -> {args.out} ({len(text.encode())} bytes, sha256 {digest})')
    if args.verify:
        print('verify: every emitted path resolves')


if __name__ == '__main__':
    main()
