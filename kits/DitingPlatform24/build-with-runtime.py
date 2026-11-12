#!/usr/bin/env python3
"""Use current driver recipes without replacing the device's packaging scripts.

The original build-kernel.py and scripts/ remain the remote packaging baseline.
Build-only copies of the recipes that accompany the runtime are selected in an
explicit overlay; all other source directories refer to this checkout.
"""
import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tomllib

HERE = Path(__file__).resolve().parent

# The two XnuPrelink layout fixes CI installs before its kernel build
# (.github/workflows/package.yml runs scripts/install-unixnu-inputs.py, whose
# fix_prelink_info_extent and fix_apple_cpu_match carry exactly these texts).
# A bare `unixnu build kernel` does not run that installer, and both the pinned
# CI kit (XnuPrelink b74ed7c) and the newer local kit (440589b) still lack the
# fixes, so the emitted kernel puts __PRELINK_INFO before the appended kext
# segments and keeps AppleARMPlatform's AppleARMCPU personality that competes
# with the native ArmCpu driver. Keep these strings identical to the installer.
PRELINK_INFO_OLD = (
    "    info_va = align(max(s['va'] + s['size'] for s in native['segments'] if s['size']))")
PRELINK_INFO_NEW = (
    "    info_va = align(max(s['va'] + s['size'] for s in [*native['segments'], *new_segments] if s['size']))")
APPLE_CPU_ANCHOR = "        entry = copy.deepcopy(entries[identifier])\n"
APPLE_CPU_ADDITION = (
    "        if identifier == 'com.apple.driver.AppleARMPlatform':\n"
    "            personalities = entry.get('IOKitPersonalities', {})\n"
    "            cpu = personalities.get('AppleARMCPU')\n"
    "            if not isinstance(cpu, dict) or cpu.get('IOClass') != 'AppleARMCPU':\n"
    "                raise ValueError('AppleARMCPU personality changed; review device matching')\n"
    "            del personalities['AppleARMCPU']\n"
)
APPLE_CPU_MARKER = APPLE_CPU_ADDITION.split('\n', 1)[0]
STAGED_KIT = Path('.cache/diting-prelink-kit')


def _forwarded_option(forwarded, name):
    for index, item in enumerate(forwarded):
        if item == name and index + 1 < len(forwarded):
            return forwarded[index + 1]
        if item.startswith(name + '='):
            return item.split('=', 1)[1]
    return None


def stage_prelink_tool(tree, device):
    """Give the kernel step a prelinker that carries CI's two layout fixes.

    `unixnu build kernel` runs the tool named by [kernel.prelink].tool from the
    shared tree, where kits/ are links to the core checkouts. The kit revision
    pinned by the core predates the two fixes, so a local build without CI's
    install-unixnu-inputs.py step emits a kernel whose static address upper
    bound (__PRELINK_INFO) cuts through the appended component segments. Patch a
    copy of the kit inside the tree and point only that link at it, so the core
    checkout stays clean and the prelink step sees the CI-equivalent tool.
    """
    board = tomllib.loads((device / 'board.toml').read_text())
    tool = Path(board['kernel']['prelink']['tool'])
    link = tree / tool.parent
    source = (tree / tool).resolve()
    if not source.is_file():
        raise SystemExit(f'{tool} missing: [kernel.prelink].tool names it')
    body = source.read_text()
    if PRELINK_INFO_NEW in body and APPLE_CPU_MARKER in body:
        return None  # CI's installer already patched the kit in place.
    staged = tree / STAGED_KIT
    if staged.exists():
        shutil.rmtree(staged)
    shutil.copytree(source.parent, staged)
    patched = staged / tool.name
    body = patched.read_text()
    if body.count(PRELINK_INFO_OLD) != 1:
        raise SystemExit(
            f'XnuPrelink layout changed in {source}: review the __PRELINK_INFO bound '
            'before staging a prelink tool')
    body = body.replace(PRELINK_INFO_OLD, PRELINK_INFO_NEW, 1)
    if body.count(APPLE_CPU_ANCHOR) != 1:
        raise SystemExit(
            f'XnuPrelink metadata handling changed in {source}: review the '
            'AppleARMCPU personality before staging a prelink tool')
    body = body.replace(APPLE_CPU_ANCHOR, APPLE_CPU_ANCHOR + APPLE_CPU_ADDITION, 1)
    patched.write_text(body)
    if link.is_symlink():
        link.unlink()
    elif link.exists():
        raise SystemExit(f'{link} is not a tree link; the build tree layout changed')
    link.symlink_to(staged)
    print(json.dumps({'prelink_kit': {'source': str(source), 'staged': str(staged),
                                      'layout_patches': ['prelink_info_extent',
                                                         'apple_arm_cpu_match']}}), flush=True)
    return patched


def overlay(device, destination):
    device, destination = device.resolve(), destination.resolve()
    if destination == device or device in destination.parents:
        raise SystemExit('The recipe overlay must be outside the source checkout')
    destination.mkdir(parents=True, exist_ok=True)
    # Keep even local input configuration as a reference, never in a manifest.
    # No firmware or restore image is copied into this source-only overlay.
    for source in device.iterdir():
        if source.name in ('scripts', 'build', 'out', '.cache', '__pycache__'):
            continue
        target = destination / source.name
        if target.is_symlink():
            if target.resolve() != source.resolve():
                raise SystemExit(f'Unexpected overlay link: {target}')
        elif target.exists():
            raise SystemExit(f'Unexpected overlay source: {target}')
        else:
            target.symlink_to(source, target_is_directory=source.is_dir())
    scripts = destination / 'scripts'
    scripts.mkdir(exist_ok=True)
    selected = {}
    duplicates = HERE / 'build-support/merged-scripts'
    if duplicates.is_dir() and any(duplicates.iterdir()):
        raise SystemExit(
            'Build recipes must live in scripts/: '
            f'{duplicates} still carries shadow copies')
    for source in (device / 'scripts').rglob('*'):
        if not source.is_file() or source.name.endswith('.pyc'):
            continue
        relative = source.relative_to(device / 'scripts')
        target = scripts / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
        selected[str(relative)] = 'scripts/' + str(relative)
    (destination / 'DITING_RECIPE_OVERLAY.json').write_text(json.dumps({
        'device': str(device), 'scripts': selected,
        'source_scripts_modified': False, 'workflow_modified': False,
    }, indent=2) + '\n')
    return destination


def main():
    parser = argparse.ArgumentParser(description=__doc__, add_help=False)
    parser.add_argument('--overlay-only', action='store_true')
    parser.add_argument('--overlay-dir', type=Path)
    parser.add_argument('--artifact-dir', type=Path)
    args, forwarded = parser.parse_known_args()
    device = Path(os.environ.get('UNIXNU_DEVICE', HERE.parents[1])).resolve()
    if not args.overlay_dir and not args.artifact_dir:
        raise SystemExit('--artifact-dir or --overlay-dir is required')
    if not args.overlay_only and not args.artifact_dir:
        raise SystemExit('--artifact-dir is required when building the kernel')
    target = args.overlay_dir or args.artifact_dir.resolve().parent / 'diting-runtime-source'
    target = overlay(device, target)
    if args.overlay_only:
        print(target)
        return
    env = dict(os.environ, UNIXNU_DEVICE=str(target))
    subprocess.run([sys.executable, str(HERE / 'build-kernel.py'),
                    '--artifact-dir', str(args.artifact_dir.resolve()), *forwarded],
                   cwd=target, env=env, check=True)
    # The prelink runs after this recipe and reads the tool from the build tree;
    # stage the CI layout fixes there so the plain build command passes the
    # storage-bindings check without the CI-only install step.
    tree = _forwarded_option(forwarded, '--tree')
    if tree:
        stage_prelink_tool(Path(tree).resolve(), device)


if __name__ == '__main__':
    main()
