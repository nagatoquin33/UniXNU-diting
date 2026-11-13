#!/usr/bin/env python3
"""DEPRECATED — Build the Diting RELEASE Android-boot-v4 image on Linux, without macOS hdiutil.

Nothing in the build chain calls this script. The release image path it wraps
now lives in .github/workflows/package.yml: `unixnu release` prelinks through
the core XnuPrelink kit (board.toml [kernel.prelink]), then
scripts/finalize-diting-adt.py and scripts/build-bootimg.py assemble the v4
container. Its --prelink-kernel option still imports the retained
kits/NativePrelink because the library-only component policy
(emit(library_only_components=...), plan(verify_images=False)) never moved
upstream; keep it only as a reference for that retired path.

Why this script exists
----------------------
`scripts/package.sh` is a 17-line wrapper: it reads `board.toml [package].unixnu`
and runs `unixnu release -D <device>`. The release chain in
`UniXNU/scripts/unixnu/cli.py:294-331` is deps -> preflight -> patches -> build
(`STEPS = ('kernel', 'package', 'firmware', 'payload')`, `cli.py:12`) -> pack ->
verify. The only hdiutil call inside that chain is
`UniXNU/scripts/unixnu/payload.py:91` in `skip_setup_seed()`, reached only with
`--skip-setup` and a `--data-ramdisk`; Diting's release uses neither. The OS /
Data / userdata stages that genuinely need hdiutil (prepare-ipados18-os-delta.py,
prepare-diting-userland-from-ipsw.py, make-macos-data-seed.py, ...) are not part
of release: `userdata` and `runtime` are OPTIONAL_STEPS (`cli.py:13`).

So the boot image is separable. This script runs exactly that boot-only subset
and nothing else:

  1. `unixnu build payload` (mtools FAT volume, Linux) with the already-built
     release kernel, the C5/C6/C7 arguments and the platform seed read at
     runtime from a B1 image's payload ADT (`/chosen unique-chip-id`); the seed
     is passed by argument/env only and is never written to a repository file.
  2. `scripts/finalize-diting-adt.py` regenerates the board ADT with the local
     generator, writes `Payloads/kernel.macho.adt` + `pong-boot-manifest.json`
     back into payload.img (mtools) and emits the release-spec boot image.
  3. The payload is wrapped in the PONGFAT1 envelope and packed with
     `scripts/build-bootimg.py` (pure Python + gzip + Mu-Silicium mkbootimg.py)
     around the B1 firmware volume, BootShim and the plan 3B device tree.

Verification is built in, because the point of this image is a device boot:
   * PONGFAT1 header/CRC32 over the FAT volume,
   * `pong-boot-manifest.json` SHA-384 == ADT `/chosen boot-manifest-hash`
     (`diting_adt_contract.audit_adt`),
   * `scripts/check-loader-adt-contract.py` PASS (DarwinBoot24/ADT contract),
   * `scripts/check-storage-bindings.py` PASS on the release kernel,
   * structural comparison of the kernel slot / DTB against the B1 image.

The script never writes the platform seed to disk. Its logs and summaries are
redacted; the finalize record (which names the seed) is not copied.

Every device input (B1 image, firmware volume, BootShim, mkbootimg, firmware
config, volume layout) is an explicit flag or a DITING_* environment variable:
this file names no workstation paths and no artifact-directory defaults. Only the
UniXNU checkout and the release kernel derive from board.toml, and the artifact
directory defaults to <cwd>/release-image.
"""
import argparse
import hashlib
import json
import os
import shutil
import struct
import subprocess
import sys
import tempfile
import tomllib
import zlib
from pathlib import Path

DEVICE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(DEVICE / 'scripts'))
from diting_adt_contract import audit_adt, parse_adt  # noqa: E402

MAGIC = b'PONGFAT1'
ENVELOPE_HEADER = 4096
DEFAULT_ARGS = ('diting_usb=0', 'diting_wifi=1', 'diting_adreno_start=1',
                'diting_metal=1', 'diting_ui_software=0', 'diting_software_ui=0')
# The library-only policy scripts/build-ipados18-prelinked-boot.py:36-45 uses for
# this board: base library components, plus the IOGPU closure when Adreno runs.
BASE_LIBRARY = {'com.apple.driver.AppleARMWatchdogTimer', 'com.apple.driver.AppleARMPlatform',
                'com.apple.driver.ApplePMGR', 'com.apple.driver.AppleEffaceableStorage',
                'com.apple.driver.AppleMobileFileIntegrity'}
GPU_LIBRARY = {'com.apple.iokit.IOGPUFamily', 'com.apple.iokit.IOSurface',
               'com.apple.iokit.IOReportFamily', 'com.apple.iokit.IOSlowAdaptiveClockingFamily'}


def prelink_release_kernel(native, kernelcache, roots, slide, out_dir, iogpu):
    """Re-prelink the existing release XNU aggregate with the board's kext closure.

    The shared kernel step prelinks only board.toml [kernel.prelink].roots, and
    the pinned kit has no library-only policy, so the release kernel carried no
    com.apple.iokit.IOGPUFamily code. With diting_metal=1 the generated
    DitingIOAcceleratorMetaConstruct binding lands on that component's
    __TEXT_EXEC bytes, which were therefore zero-fill (C5 panic: instr=0 at
    pc=0xfffffff00be106c8). This repeats scripts/build-ipados18-prelinked-boot.py's
    qualified recipe on the current Linux path: when Adreno is enabled, add
    IOGPUFamily to the roots and prelink IOGPUFamily + its closure library-only.
    """
    sys.path.insert(0, str(DEVICE / 'kits/NativePrelink'))
    from emit_prelink import emit           # noqa: E402  (device kit, has library_only)
    from native_prelink import arm64_image, plan  # noqa: E402
    native_data = Path(native).read_bytes()
    original_data = arm64_image(Path(kernelcache).read_bytes())
    roots = list(roots)
    library = set(BASE_LIBRARY)
    if iogpu:
        roots.append('com.apple.iokit.IOGPUFamily')
        library |= GPU_LIBRARY
    closure = plan(native_data, original_data, roots, slide, verify_images=False)
    library &= set(closure['components'])
    candidate, selection = emit(native_data, original_data, roots, slide,
                                verify_images=False, library_only_components=library)
    out_dir.mkdir(parents=True, exist_ok=True)
    target = out_dir / ('kernel-iogpu.macho' if iogpu else 'kernel-release.macho')
    target.write_bytes(candidate)
    (out_dir / (target.stem + '.selection.json')).write_text(
        json.dumps(selection, indent=2, sort_keys=True) + '\n')
    report = {'native': str(native), 'native_sha256': hashlib.sha256(native_data).hexdigest(),
              'kernelcache': str(kernelcache), 'slide': hex(slide), 'iogpu': iogpu,
              'roots': roots, 'components': selection['components'],
              'library_only_components': selection['library_only_components'],
              'codeless_components': selection['codeless_components'],
              'kernel_interfaces': selection['kernel_interfaces'],
              'candidate': str(target), 'candidate_bytes': len(candidate),
              'candidate_sha256': hashlib.sha256(candidate).hexdigest()}
    return target, report


def merge_overrides(cpus, extra):
    """Combine the per-variant CPU count, the release defaults and --arg overrides.

    A later value for the same NAME replaces the earlier one while keeping its
    position, so `--arg diting_wifi=0` really turns the default wifi=1 off
    instead of emitting a duplicate key (PE_parse_boot_argn selects the first
    duplicate, so a duplicate would silently win).
    """
    merged = {}
    for item in (f'cpus={cpus}', *DEFAULT_ARGS, *extra):
        key, separator, _value = item.partition('=')
        if not separator or not key:
            raise SystemExit(f'boot argument must be NAME=VALUE: {item}')
        merged[key] = item
    return list(merged.values())


def sha256_file(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1 << 20), b''):
            digest.update(block)
    return digest.hexdigest()


def align(value):
    return (value + 4095) // 4096 * 4096


def parse_boot_image(data):
    """Return the Android boot image fields this script needs (v0 or v4)."""
    if data[:8] != b'ANDROID!':
        raise SystemExit('not an Android boot image')
    kernel_size, ramdisk_size, _, header_size = struct.unpack_from('<4I', data, 8)
    version = struct.unpack_from('<I', data, 40)[0]
    kernel_at = (header_size + 4095) // 4096 * 4096
    ramdisk_at = kernel_at + ((kernel_size + 4095) // 4096 * 4096)
    return {'version': version, 'header_size': header_size, 'kernel_size': kernel_size,
            'ramdisk_size': ramdisk_size,
            'kernel': data[kernel_at:kernel_at + kernel_size],
            'ramdisk': data[ramdisk_at:ramdisk_at + ramdisk_size],
            'bytes': len(data)}


def b1_inputs(image):
    """Extract the platform seed, appended DTB, ADT and manifest from a B1 image."""
    parsed = parse_boot_image(image.read_bytes())
    if parsed['version'] != 4:
        raise SystemExit(f'{image} is not an Android boot v4 image')
    ramdisk = parsed['ramdisk']
    if ramdisk[:8] != MAGIC:
        raise SystemExit(f'{image}: ramdisk is not PONGFAT1')
    _, version, head_len, fat_len, crc, _flags = struct.unpack_from('<8sIIQII', ramdisk, 0)
    fat = ramdisk[head_len:head_len + fat_len]
    if zlib.crc32(fat) != crc:
        raise SystemExit(f'{image}: PONGFAT1 CRC mismatch')
    with tempfile.TemporaryDirectory(prefix='diting-b1-payload-') as scratch_dir:
        scratch = Path(scratch_dir) / 'payload.img'
        scratch.write_bytes(fat)
        env = dict(os.environ, MTOOLS_SKIP_CHECK='1', TZ='UTC')
        adt = subprocess.run(['mtype', '-i', str(scratch), '::/EFI/UniXNU/Payloads/kernel.macho.adt'],
                             check=True, capture_output=True, env=env).stdout
        manifest = subprocess.run(['mtype', '-i', str(scratch), '::/EFI/UniXNU/Payloads/pong-boot-manifest.json'],
                                  check=True, capture_output=True, env=env).stdout
    stream = zlib.decompressobj(16 + zlib.MAX_WBITS)
    stream.decompress(parsed['kernel'])
    dtb = stream.unused_data
    if not stream.eof or dtb[:4] != b'\xd0\x0d\xfe\xed':
        raise SystemExit(f'{image}: kernel slot has no appended DTB')
    chosen = parse_adt(adt)['/chosen']
    seed = int.from_bytes(chosen['unique-chip-id'], 'little')
    audit_adt(adt, boot_manifest=manifest)  # the B1 ADT must be self-consistent
    return {'seed': seed, 'dtb': dtb, 'adt': adt, 'manifest': manifest,
            'kernel_slot': parsed['kernel'], 'image': parsed}


def redact(text, seed):
    for spelling in ('%016x' % seed, '%016X' % seed, '%x' % seed, '%X' % seed, str(seed)):
        text = text.replace(spelling, '<seed>')
    return text


def run_logged(command, cwd, env, log):
    log.parent.mkdir(parents=True, exist_ok=True)
    completed = subprocess.run(command, cwd=cwd, env=env, text=True,
                               stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    log.write_text(completed.stdout)
    return completed


def verify_manifest(adt, manifest, cpus):
    """Manifest SHA-384 must equal the ADT boot-manifest-hash.

    `diting_adt_contract.audit_adt` is the single-core bring-up auditor and
    rejects any CPU layout but /cpus/cpu0 (diting_adt_contract.py:158-179); the
    multi-core variants are checked here for the loader contract itself.
    """
    chosen = parse_adt(adt)['/chosen']
    if chosen.get('boot-manifest-hash') != hashlib.sha384(manifest).digest():
        raise SystemExit('ADT boot-manifest-hash does not match the staged manifest')
    seed = chosen.get('unique-chip-id')
    if seed is None or len(seed) != 8:
        raise SystemExit('ADT /chosen unique-chip-id is missing or not 8 bytes')
    nodes = parse_adt(adt)
    cpu_paths = [path for path in nodes
                 if path.rsplit('/', 1)[0] == '/cpus'
                 and path.rsplit('/', 1)[1].startswith('cpu')
                 and path.rsplit('/', 1)[1] != 'cpu-map']
    if len(cpu_paths) != cpus:
        raise SystemExit(f'ADT exposes {len(cpu_paths)} CPUs, the variant requested {cpus}')
    return {'manifest_sha384_matches': True, 'cpu_nodes': len(cpu_paths),
            'unique_chip_id_bytes': len(seed)}


def envelope(fat):
    if len(fat) % 512 or fat[510:512] != b'\x55\xaa' or struct.unpack_from('<H', fat, 11)[0] != 512:
        raise SystemExit('payload volume is not a FAT volume with 512-byte sectors')
    sectors16 = struct.unpack_from('<H', fat, 19)[0]
    sectors = sectors16 or struct.unpack_from('<I', fat, 32)[0]
    if sectors != len(fat) // 512:
        raise SystemExit(f'payload volume declares {sectors} sectors, holds {len(fat) // 512}')
    header = bytearray(ENVELOPE_HEADER)
    struct.pack_into('<8sIIQII', header, 0, MAGIC, 1, ENVELOPE_HEADER,
                     len(fat), zlib.crc32(fat) & 0xffffffff, 0)
    return bytes(header) + fat


def payload_member(payload, member):
    env = dict(os.environ, MTOOLS_SKIP_CHECK='1', TZ='UTC')
    probe = subprocess.run(['mtype', '-i', str(payload), f'::{member}'], env=env, capture_output=True)
    return probe.stdout if probe.returncode == 0 else None


def main():
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--device', type=Path, default=DEVICE)
    parser.add_argument('--core', type=Path,
                        help='UniXNU checkout (default: board.toml [package].unixnu)')
    parser.add_argument('--kernel', type=Path,
                        help='release kernel.macho (default: <core>/out/diting/<os>/<config>/kernel/kernel.macho)')
    parser.add_argument('--prelink-kernel', action='store_true',
                        help='re-prelink the existing release XNU aggregate with the board kext '
                             'closure: when Adreno is enabled, add com.apple.iokit.IOGPUFamily to '
                             'the roots and prelink IOGPUFamily + its closure library-only '
                             '(scripts/build-ipados18-prelinked-boot.py:36-45). Reuses the built '
                             'aggregate; XNU is not relinked from scratch')
    parser.add_argument('--native-kernel', type=Path,
                        help='native XNU aggregate for --prelink-kernel (default: <work>/tree/build/'
                             'xnu/ios-obj/DEVELOPMENT_ARM64_<machine>/mach.development.diting)')
    parser.add_argument('--kernelcache', type=Path,
                        help='original decompressed kernelcache for --prelink-kernel '
                             '(or DITING_KERNELCACHE / UNIXNU_KERNELCACHE)')
    parser.add_argument('--b1-image', type=Path,
                        help='B1 image carrying the B1 ADT (seed) and the plan 3B DTB '
                             '(or DITING_B1_IMAGE)')
    parser.add_argument('--fd', type=Path, help='firmware volume (or DITING_FD)')
    parser.add_argument('--shim', type=Path, help='BootShim.bin (or DITING_BOOTSHIM)')
    parser.add_argument('--mkbootimg', type=Path,
                        help='Mu-Silicium mkbootimg.py (or DITING_MKBOOTIMG)')
    parser.add_argument('--firmware-config', type=Path,
                        help='firmware config TOML (or DITING_FIRMWARE_CONFIG)')
    parser.add_argument('--volume-layout', type=Path,
                        help='volume layout JSON the kernel was configured with '
                             '(or DITING_VOLUME_LAYOUT)')
    parser.add_argument('--output-dir', type=Path, default=Path.cwd() / 'release-image',
                        help='artifact directory (default: <cwd>/release-image)')
    parser.add_argument('--cpus', default='8,1', help='comma separated CPU counts to build')
    parser.add_argument('--arg', action='append', default=[], metavar='NAME=VALUE',
                        help='extra/replacement boot argument for every variant')
    args = parser.parse_args()

    def required(flag, value, env_name):
        """Resolve a device input from the flag or its DITING_* environment variable."""
        if value is not None:
            return value.resolve()
        from_env = os.environ.get(env_name)
        if from_env:
            return Path(from_env).expanduser().resolve()
        parser.error(f'{flag} is required: pass the flag or set {env_name}')

    args.b1_image = required('--b1-image', args.b1_image, 'DITING_B1_IMAGE')
    args.fd = required('--fd', args.fd, 'DITING_FD')
    args.shim = required('--shim', args.shim, 'DITING_BOOTSHIM')
    args.mkbootimg = required('--mkbootimg', args.mkbootimg, 'DITING_MKBOOTIMG')
    args.firmware_config = required('--firmware-config', args.firmware_config,
                                    'DITING_FIRMWARE_CONFIG')
    args.volume_layout = required('--volume-layout', args.volume_layout,
                                  'DITING_VOLUME_LAYOUT')
    args.output_dir = args.output_dir.expanduser().resolve()
    for flag, path in (('--b1-image', args.b1_image), ('--fd', args.fd), ('--shim', args.shim),
                       ('--mkbootimg', args.mkbootimg),
                       ('--firmware-config', args.firmware_config),
                       ('--volume-layout', args.volume_layout)):
        if not path.is_file():
            parser.error(f'{flag}: {path} is not a file')

    device = args.device.resolve()
    board = tomllib.loads((device / 'board.toml').read_text())
    core = (args.core or (device / board['package']['unixnu'])).resolve()
    os_profile = board['board']['os_profile']
    config_name = board['package']['defconfig'][os_profile]
    work_name = config_name[:-len('_defconfig')] if config_name.endswith('_defconfig') else config_name
    work = core / 'out' / board['board']['name'] / os_profile / work_name
    kernel = (args.kernel or work / 'kernel/kernel.macho').resolve()
    if not kernel.is_file():
        raise SystemExit(f'release kernel not found: {kernel}')
    out = args.output_dir.resolve()
    images = out / 'images'
    logs = out / 'logs'
    images.mkdir(parents=True, exist_ok=True)
    logs.mkdir(parents=True, exist_ok=True)

    cpus_list = [int(value) for value in args.cpus.split(',') if value.strip()]
    overrides_by_cpus = {cpus: merge_overrides(cpus, args.arg) for cpus in cpus_list}

    # The payload step's work directory is the core's *current* configuration
    # (out/<device>/<os>/<configuration>). Make the release configuration
    # explicit here instead of inheriting whichever config the core last ran,
    # or payload.img is read from a stale directory.
    completed = run_logged([sys.executable, str(core / 'unixnu'), 'defconfig', config_name,
                            '-D', str(device)], core, dict(os.environ),
                           logs / 'defconfig.log')
    if completed.returncode != 0:
        print(completed.stdout[-4000:])
        raise SystemExit(f'defconfig {config_name} failed')
    print(f'== configuration {config_name} selected (work dir {work})')

    prelink = None
    if args.prelink_kernel:
        machine = board.get('kernel', {}).get('machine_config', 'DITING')
        native = args.native_kernel or (
            work / 'tree' / 'build/xnu/ios-obj' / f'DEVELOPMENT_ARM64_{machine}'
            / 'mach.development.diting')
        if not native.is_file():
            fallback = work / 'kernel' / 'mach.development.diting'
            native = fallback if fallback.is_file() else native
        if not native.is_file():
            parser.error(f'--native-kernel: {native} is not a file')
        kernelcache = (args.kernelcache or os.environ.get('DITING_KERNELCACHE')
                       or os.environ.get('UNIXNU_KERNELCACHE'))
        if not kernelcache:
            parser.error('--prelink-kernel needs --kernelcache or DITING_KERNELCACHE/UNIXNU_KERNELCACHE')
        kernelcache = Path(kernelcache).expanduser().resolve()
        if not kernelcache.is_file():
            parser.error(f'--kernelcache: {kernelcache} is not a file')
        iogpu = any('diting_adreno_start=1' in overrides
                    for overrides in overrides_by_cpus.values())
        kernel, prelink = prelink_release_kernel(
            native.resolve(), kernelcache, board['kernel']['prelink']['roots'],
            int(board['kernel']['prelink']['slide'], 0), out / 'kernel', iogpu)
        kernel = kernel.resolve()
        print(json.dumps({'prelink': {'kernel': str(kernel),
                                      'sha256': prelink['candidate_sha256'],
                                      'iogpu': iogpu,
                                      'components': len(prelink['components']),
                                      'library_only_components':
                                          len(prelink['library_only_components'])}}, indent=2))

    stock = b1_inputs(args.b1_image.resolve())
    seed = stock['seed']
    seed_hex = '%016x' % seed
    env = dict(os.environ)
    env['UNIXNU_UNIQUE_CHIP_ID'] = seed_hex
    dtb = stock['dtb']
    dtb_path = out / 'plan3b-diting.dtb'
    dtb_path.write_bytes(dtb)

    summary = {'device': str(device), 'core': str(core), 'work_dir': str(work),
               'kernel': {'path': str(kernel), 'bytes': kernel.stat().st_size, 'sha256': sha256_file(kernel)},
               'prelink': prelink,
               'b1_image': {'path': str(args.b1_image.resolve()), 'sha256': sha256_file(args.b1_image.resolve())},
               'fd': {'path': str(args.fd.resolve()), 'sha256': sha256_file(args.fd.resolve())},
               'shim': {'path': str(args.shim.resolve()), 'sha256': sha256_file(args.shim.resolve())},
               'dtb': {'path': str(dtb_path), 'bytes': len(dtb), 'sha256': hashlib.sha256(dtb).hexdigest()},
               'seed_source': 'B1 payload ADT /chosen unique-chip-id (value not recorded)',
               'hdiutil_used': False, 'variants': {}}

    for cpus in cpus_list:
        variant = f'release-v4-cpus{cpus}'
        overrides = overrides_by_cpus[cpus]
        print(f'== {variant}: payload step')
        command = [sys.executable, str(core / 'unixnu'), 'build', 'payload',
                   '-D', str(device), '--kernel', str(kernel)]
        for value in overrides:
            command += ['--kernel-arg', value]
        completed = run_logged(command, core, env, logs / f'payload-{variant}.log')
        if completed.returncode != 0:
            print(completed.stdout[-4000:])
            raise SystemExit(f'payload step failed for {variant}')
        payload = work / 'payload/payload.img'
        if not payload.is_file():
            raise SystemExit(f'{payload} missing after the payload step')

        print(f'== {variant}: finalize ADT')
        finalize = [sys.executable, str(device / 'scripts/finalize-diting-adt.py'),
                    '--work-dir', str(work), '--unique-chip-id', seed_hex,
                    '--cpus', str(cpus), '--hardware-dtb', str(dtb_path),
                    '--volume-layout', str(args.volume_layout), '--ufs-probe']
        completed = run_logged(finalize, device, env, logs / f'finalize-{variant}.log')
        # finalize prints its record (it names the seed): keep a redacted copy.
        (logs / f'finalize-{variant}.log').write_text(redact(completed.stdout, seed))
        if completed.returncode != 0:
            print(redact(completed.stdout[-4000:], seed))
            raise SystemExit(f'finalize failed for {variant}')

        adt = payload_member(payload, '/EFI/UniXNU/Payloads/kernel.macho.adt')
        manifest = payload_member(payload, '/EFI/UniXNU/Payloads/pong-boot-manifest.json')
        if not adt or not manifest:
            raise SystemExit(f'{payload}: finalize did not write the ADT/manifest')
        loader_checks = verify_manifest(adt, manifest, cpus)
        if cpus == 1:
            # The stricter single-core loader audit, unchanged from the B1 path.
            loader_checks['single_core_audit'] = audit_adt(adt, boot_manifest=manifest)['status']
        config = payload_member(payload, '/EFI/UniXNU/unixnu.toml')
        entries = [line for line in config.decode().splitlines() if line.startswith('args = ')]
        if len(entries) != 1 or f'cpus={cpus}' not in entries[0]:
            raise SystemExit(f'{payload}: kernel arguments do not carry cpus={cpus}')

        ramdisk = envelope(payload.read_bytes())
        ramdisk_path = out / f'{variant}-pongfat1.img'
        ramdisk_path.write_bytes(ramdisk)
        print(f'== {variant}: pack the v4 image')
        variant_dir = out / 'images' / variant
        command = [sys.executable, str(device / 'scripts/build-bootimg.py'),
                   '--shim', str(args.shim), '--mkbootimg', str(args.mkbootimg),
                   '--config', str(args.firmware_config), '--fd', str(args.fd),
                   '--dtb', str(dtb_path), '--ramdisk', str(ramdisk_path),
                   '--output-dir', str(variant_dir)]
        completed = run_logged(command, device, env, logs / f'bootimg-{variant}.log')
        if completed.returncode != 0:
            print(completed.stdout[-4000:])
            raise SystemExit(f'boot image packing failed for {variant}')
        image = variant_dir / 'diting-unixnu-uefi.img'
        final = images / f'{variant}.img'
        shutil.copyfile(image, final)

        print(f'== {variant}: verify')
        packed = parse_boot_image(final.read_bytes())
        if packed['ramdisk'] != ramdisk:
            raise SystemExit(f'{variant}: ramdisk does not equal the PONGFAT1 envelope')
        if packed['kernel'] != stock['kernel_slot']:
            raise SystemExit(f'{variant}: kernel slot differs from the B1 shim+FD+DTB slot')
        checks = {}
        for label, script, target in (
                ('loader_adt_contract', 'check-loader-adt-contract.py', final),
                ('storage_bindings', 'check-storage-bindings.py', kernel)):
            completed = subprocess.run([sys.executable, str(device / 'scripts' / script), str(target)],
                                       cwd=device, env=env, text=True,
                                       stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
            checks[label] = {'exit': completed.returncode, 'output': completed.stdout.strip()}
            if completed.returncode != 0:
                raise SystemExit(f'{variant}: {label} checker failed:\n{completed.stdout}')
        summary['variants'][variant] = {
            'cpus': cpus, 'boot_args_overrides': overrides,
            'payload': {'bytes': payload.stat().st_size, 'sha256': sha256_file(payload)},
            'adt': {'bytes': len(adt), 'sha256': hashlib.sha256(adt).hexdigest()},
            'boot_manifest': {'bytes': len(manifest), 'sha256': hashlib.sha256(manifest).hexdigest()},
            'pongfat1': {'bytes': len(ramdisk), 'crc32': '%#010x' % zlib.crc32(payload.read_bytes())},
            'loader': loader_checks,
            'image': {'path': str(final), 'bytes': final.stat().st_size, 'sha256': sha256_file(final)},
            'checks': checks,
            'structure_matches_b1_kernel_slot': True,
        }
        print(json.dumps(summary['variants'][variant], indent=2))

    (out / 'summary.json').write_text(json.dumps(summary, indent=2, sort_keys=True) + '\n')
    print(json.dumps({'summary': str(out / 'summary.json'),
                      'images': {name: info['image'] for name, info in summary['variants'].items()}},
                     indent=2))


if __name__ == '__main__':
    main()
