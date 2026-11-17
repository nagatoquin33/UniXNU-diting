#!/usr/bin/env python3
"""Prepare the complete, pinned A730/22H374 Mesa source in a new directory.

The patch includes the public Darwin backend and Diting's accumulated fixes.
Existing source checkouts are read only; no firmware or system images are used.
"""
import argparse
import io
import json
from pathlib import Path
import subprocess
import tarfile

ROOT = Path(__file__).resolve().parents[1]
PIN = '85fda3b36405bcaea8bffc64aa4f2651dc90770d'
PATCH = 'patches/mesa/parity167/diting-darwin22h374.patch'
# Turnip shader-share (upstream c34f018) and retired-BO sweep-on-miss (2bbb39d),
# applied in order after the parity167 backend patch.
EXTRA_PATCHES = [
    'patches/mesa/0016-diting-turnip-shaders-shared-across-pipeline-caches.patch',
    'patches/mesa/0017-diting-turnip-sweep-retired-on-cache-miss.patch',
]


def apply_patch(destination, patch):
    # patch(1) is repo-agnostic: `git apply` run inside an enclosing work tree
    # resolves the diff against that repo's index, not the extracted files.
    path = ROOT / patch
    data = path.read_bytes()

    def dry_run(*args):
        return subprocess.run(['patch', '--dry-run', '-p1', *args],
                              cwd=destination, input=data,
                              stdout=subprocess.DEVNULL,
                              stderr=subprocess.DEVNULL).returncode == 0

    if dry_run('-R'):
        return False
    if dry_run('-N'):
        subprocess.run(['patch', '-p1', '-N', '--batch'], cwd=destination,
                       input=data, check=True,
                       stdout=subprocess.DEVNULL)
        return True
    raise SystemExit('Patch does not apply and is not already applied: ' + patch)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repository', required=True, type=Path)
    parser.add_argument('--out', required=True, type=Path)
    args = parser.parse_args()
    destination = args.out.resolve()
    if destination.exists():
        parser.error('output already exists; preserve it or choose a new path')
    source = subprocess.check_output(['git', 'archive', PIN], cwd=args.repository)
    destination.mkdir(parents=True)
    with tarfile.open(fileobj=io.BytesIO(source)) as archive:
        archive.extractall(destination, filter='data')
    apply_patch(destination, PATCH)
    applied = []
    for patch in EXTRA_PATCHES:
        if apply_patch(destination, patch):
            applied.append(patch)
        else:
            print(patch + ': already applied, skipping')
    (destination / '.diting-mesa.json').write_text(json.dumps({
        'schema': 1, 'mesa': PIN, 'guest': '22H374', 'native_abi': 1,
        'patch': PATCH, 'extra_patches': EXTRA_PATCHES, 'snapshot': 'services167',
    }, indent=2) + '\n')
    print(destination)


if __name__ == '__main__':
    main()
