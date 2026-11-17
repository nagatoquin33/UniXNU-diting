#!/usr/bin/env python3
"""Check a boot image for the DarwinBoot <-> ADT property contract.

The image's firmware volume must carry the DarwinBoot loader and the payload's
ADT must use the same property names. Run it on a green image to see it PASS and
on the pong-era image (e9b615bf...) to see it FAIL; a checker that cannot fail on
the old image proves nothing.

Every clause below mirrors the refusal path in
drivers/DarwinBoot/DarwinBootPkg/Driver/DarwinBoot.c (official) or the fork
drivers/DarwinBoot24 copy (RAMDisk/PackedRAMDisk, TrustCache, GpuAddon and
RootPolicies file<->slot pairing, the zeroed placeholder tables, the fork RAM
wire tables, and the 1023-byte ASCII boot-args bound).

    scripts/check-loader-adt-contract.py <image>
"""
import argparse
import hashlib
import lzma
import os
import subprocess
import tempfile
import struct
import sys
import uuid
import zlib
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from diting_adt_contract import parse_adt

try:
    import tomllib
except ImportError:
    tomllib = None

LZMA_GUID = uuid.UUID("EE4E5898-3914-4259-9D6E-DC7BD79403CF")
OLD = (b"pong-allocatable-ram", b"pong-audio-dma", b"pong_ram_banks")
NEW = (b"diting-allocatable-ram", b"diting-audio-dma", b"diting_ram_banks")
OFFICIAL = (b"GpuAddon", b"RootPolicies", b"darwinboot-memory-size",
            b"RAMDisk", b"PackedRAMDisk", b"TrustCache")

# The four /chosen/memory-map file slots of the official loader (the fork knows
# every one except RootPolicies).
SLOTS = ("RAMDisk", "PackedRAMDisk", "TrustCache", "GpuAddon", "RootPolicies")
# DITING_RAM_MAX in the fork loader: the RAM wire is 32 + 64*16 bytes.
RAM_BANK_LIMIT = 64
RAM_WIRE_SIZE = 32 + RAM_BANK_LIMIT * 16
# BootArgs.h: CHAR8 CommandLine[1024] including the terminator.
BOOT_ARGS_LIMIT = 1023
# DarwinWindowSizeValid: 256 MiB .. 8 GiB, 2 MiB aligned.
WINDOW_SIZE_MIN = 0x10000000
WINDOW_SIZE_MAX = 0x200000000
WINDOW_SIZE_ALIGN = 0x200000


def align(value):
    return (value + 4095) // 4096 * 4096


def load_image(path):
    data = Path(path).read_bytes()
    if data[:8] != b"ANDROID!":
        raise ValueError("not an Android boot image")
    kernel_size, ramdisk_size = struct.unpack_from("<2I", data, 8)
    header_size, = struct.unpack_from("<I", data, 20)
    kstart = align(header_size)
    kernel = data[kstart:kstart + kernel_size]
    rstart = align(header_size) + align(kernel_size)
    ramdisk = data[rstart:rstart + ramdisk_size]
    try:
        kernel = zlib.decompress(kernel, 16 + zlib.MAX_WBITS)
    except zlib.error as exc:
        raise ValueError(f"kernel slot is not a gzip stream: {exc}") from exc
    return kernel, ramdisk


def walk_fv(data, files):
    """Collect (name, sections) for every FFS file, following nested/LZMA FVs."""
    i = 0
    while True:
        j = data.find(b"_FVH", i)
        if j < 40:
            break
        base = j - 40
        fv_len, = struct.unpack_from("<Q", data, base + 32)
        hdr_len, = struct.unpack_from("<H", data, base + 48)
        if fv_len < hdr_len or base + fv_len > len(data):
            i = j + 4
            continue
        fv = data[base:base + fv_len]
        off = hdr_len
        ext, = struct.unpack_from("<H", fv, 52)
        if ext:
            off = max(off, ext + struct.unpack_from("<I", fv, ext + 16)[0])
        off = (off + 7) & ~7
        while off + 24 <= len(fv):
            ffs_name = fv[off:off + 16]
            if ffs_name == b"\xff" * 16:
                break
            size = int.from_bytes(fv[off + 20:off + 23], "little")
            ftype = fv[off + 18]
            hdr = 24
            if size == 0xFFFFFF:
                size, = struct.unpack_from("<Q", fv, off + 24)
                hdr = 32
            if size < hdr:
                break
            body = fv[off + hdr:off + size]
            if ftype not in (0xF0,):
                walk_sections(body, files, str(uuid.UUID(bytes_le=ffs_name)))
            off = (off + size + 7) & ~7
        i = base + fv_len
    return files


def walk_sections(data, files, label, depth=0):
    off = 0
    while off + 4 <= len(data):
        size = int.from_bytes(data[off:off + 3], "little")
        stype = data[off + 3]
        hdr = 4
        if size == 0xFFFFFF:
            size, = struct.unpack_from("<I", data, off + 4)
            hdr = 8
        if size < hdr or off + size > len(data):
            break
        body = data[off + hdr:off + size]
        if stype == 0x17 and depth < 2:
            walk_fv(body, files)
        elif stype == 0x02 and depth < 2:
            try:
                guid = uuid.UUID(bytes_le=bytes(body[:16]))
            except ValueError:
                guid = None
            if guid == LZMA_GUID:
                inner = data[off + struct.unpack_from("<H", body, 16)[0]:off + size]
                try:
                    walk_sections(lzma.decompress(inner, format=lzma.FORMAT_ALONE),
                                  files, label, depth + 1)
                except lzma.LZMAError:
                    pass
        elif body[:2] == b"MZ" or b"DARWINBOOT" in body.upper():
            files.append((label, body))
        off = (off + size + 3) & ~3


def payload_member(fat, member):
    """Read one payload file through mtools (the build hosts carry mtools)."""
    with tempfile.TemporaryDirectory() as scratch_dir:
        scratch = Path(scratch_dir) / 'payload.img'
        scratch.write_bytes(fat)
        env = dict(os.environ, MTOOLS_SKIP_CHECK='1', TZ='UTC')
        probe = subprocess.run(['mtype', '-i', str(scratch), f'::{member}'],
                               env=env, capture_output=True)
        return probe.stdout if probe.returncode == 0 else None


def payload_entries(toml):
    """The xnu boot entries of unixnu.toml (id, kernel path, args, initrd)."""
    if toml is None or tomllib is None:
        return []
    try:
        config = tomllib.loads(toml.decode('utf-8', 'replace'))
    except Exception:
        return []
    return [entry for entry in config.get('entry', [])
            if entry.get('type') == 'xnu']


def fat_member(name):
    """A payload-relative name such as Payloads/scratch-data.img -> FAT member."""
    return '/EFI/UniXNU/' + str(name).replace('\\', '/').lstrip('/')


def load_tree(fat, kernel_name, failures):
    """kernel.macho.adt parsed once; None with a recorded failure on problems."""
    adt = payload_member(fat, fat_member(kernel_name + '.adt'))
    if adt is None:
        failures.append(f'payload lacks {kernel_name}.adt; DarwinBoot cannot boot')
        return None
    try:
        return parse_adt(adt)
    except ValueError as error:
        failures.append(f'payload ADT is unreadable: {error}')
        return None


def prop_places(nodes, name):
    """(node path, value) for every node carrying the ADT property name."""
    return [(path, props[name]) for path, props in nodes.items() if name in props]


def check_slot_shape(nodes, failures):
    """RAMDisk/PackedRAMDisk/TrustCache/GpuAddon/RootPolicies placement, count,
    16-byte zero value, and the at-most-one-ramdisk rule the loader enforces."""
    packed = 0
    memory_map = nodes.get('/chosen/memory-map', {})
    for name in SLOTS:
        places = prop_places(nodes, name)
        if name == 'PackedRAMDisk':
            packed = len(places)
        if not places:
            continue
        # A slot property anywhere but on /chosen/memory-map is invisible to
        # the loader (RootPolicies there is a hard AdtNode refusal); the
        # file<->slot pairing checks then fail on the missing slot anyway.
        for path, value in places:
            if path != '/chosen/memory-map':
                failures.append(f'{name} is a property of {path}, the loader only reads /chosen/memory-map/{name}')
        slot = memory_map.get(name)
        if slot is None:
            continue
        if len(slot) != 16:
            failures.append(f'/chosen/memory-map/{name} is {len(slot)} bytes, DarwinBoot requires 16 zero bytes')
        elif any(slot):
            failures.append(f'/chosen/memory-map/{name} is not the 16-byte zero placeholder DarwinBoot fills')
    if packed > 1:
        failures.append(f'{packed} PackedRAMDisk properties; the loader accepts at most one')
    if 'RAMDisk' in memory_map and 'PackedRAMDisk' in memory_map:
        failures.append('/chosen/memory-map carries both RAMDisk and PackedRAMDisk; the loader accepts at most one ramdisk slot')


def check_initrd_slot(fat, nodes, initrd_names, failures, notes):
    """unixnu.toml initrd files and the /chosen/memory-map ramdisk slot must
    agree with the loader's PackedRamdisk.h + AdtNode contract."""
    slot = None
    packed_slot = False
    if nodes is not None:
        memory_map = nodes.get('/chosen/memory-map', {})
        packed_slot = 'PackedRAMDisk' in memory_map
        slot = memory_map.get('PackedRAMDisk', memory_map.get('RAMDisk'))
    initrds = {}
    for name in initrd_names:
        member = fat_member(name)
        if member not in initrds:
            initrds[member] = payload_member(fat, member)
        if initrds[member] is None:
            failures.append(f'unixnu.toml declares initrd {name} but the payload carries no {member}')
            continue
        notes.append(f'initrd {name} = {len(initrds[member])} bytes')
    present = [blob for blob in initrds.values() if blob is not None]
    if initrd_names and slot is None:
        failures.append('unixnu.toml carries an initrd but the ADT lacks /chosen/memory-map/RAMDisk')
    if slot is not None and not initrd_names:
        failures.append('ADT reserves a RAMDisk slot but unixnu.toml has no initrd')
    for blob in present:
        if len(blob) > 256 * 1024 * 1024:
            failures.append(f'initrd is {len(blob)} bytes; PackedRamdisk.h rejects anything over 256 MiB')
            continue
        if blob[:8] == b'DBRDISK1':
            problem = packed_ramdisk_layout(blob)
            if problem:
                failures.append(f'packed initrd layout rejected: {problem}')
    if packed_slot and present and not all(blob[:8] == b'DBRDISK1' for blob in present):
        failures.append('ADT uses the PackedRAMDisk slot but the initrd does not start with DBRDISK1')


def packed_ramdisk_layout(blob):
    """PackedRamdisk.h RamdiskLayout for an initrd that begins with DBRDISK1."""
    if len(blob) < 32:
        return 'DBRDISK1 header truncated'
    version, page_size = struct.unpack_from('<II', blob, 8)
    logical, count = struct.unpack_from('<QQ', blob, 16)
    if version != 1 or page_size != 4096:
        return f'version {version} page {page_size}; expected version 1 page 4096'
    if (logical == 0 or logical > (1 << 40) or logical & 4095 or
            count > 65536 or count > (len(blob) - 32) // 16):
        return 'bad logical size or extent count'
    cursor, end = 32 + count * 16, 0
    for index in range(count):
        offset, length = struct.unpack_from('<QQ', blob, 32 + index * 16)
        if (not length or (offset | length) & 4095 or offset < end or
                offset > logical or length > logical - offset or
                length > len(blob) - cursor):
            return f'extent {index} out of bounds'
        end = offset + length
        cursor += length
    if cursor != len(blob):
        return f'{len(blob) - cursor} trailing bytes after the extents'
    return None


def valid_trust_caches(blob):
    """DarwinBoot.c ValidTrustCaches: 1..128 version-2 trust cache blobs of
    sorted 20-byte hashes (type 1..4). Returns a problem or None."""
    if len(blob) < 8:
        return 'trust cache file is shorter than its count field'
    count, = struct.unpack_from('<I', blob, 0)
    if not 1 <= count <= 128 or count > (len(blob) - 4) // 4:
        return f'trust cache count {count} out of range'
    for index in range(count):
        start, = struct.unpack_from('<I', blob, 4 + index * 4)
        end = struct.unpack_from('<I', blob, 8 + index * 4)[0] if index + 1 < count else len(blob)
        if (start < 4 + count * 4 or start & 3 or end > len(blob) or
                end < start or end - start < 24):
            return f'trust cache {index} extent 0x{start:x}..0x{end:x} out of bounds'
        if struct.unpack_from('<I', blob, start)[0] != 2:
            return f'trust cache {index} is not a version-2 blob'
        entries, = struct.unpack_from('<I', blob, start + 20)
        if entries > (end - start - 24) // 24 or end - start != 24 + entries * 24:
            return f'trust cache {index} declares {entries} entries for {end - start} bytes'
        for entry in range(entries):
            head = blob[start + 24 + entry * 24:start + 48 + entry * 24]
            if not 1 <= head[20] <= 4:
                return f'cache {index} entry {entry} hash type {head[20]} out of range'
            if entry and head[:20] <= blob[start + entry * 24:start + 24 + entry * 24]:
                return f'cache {index} entry {entry} hash not strictly sorted'
    return None


def check_file_slot(fat, nodes, kernel_name, member_suffix, slot_name, validate,
                    failures):
    """The shared pattern of DarwinBoot.c: a payload file named
    kernel.macho.<suffix> requires a zeroed /chosen/memory-map slot, and a slot
    without the file is refused."""
    member = payload_member(fat, fat_member(kernel_name + member_suffix))
    slot = nodes.get('/chosen/memory-map', {}).get(slot_name) if nodes is not None else None
    if member is not None:
        if slot is None:
            failures.append(f'payload carries {kernel_name}{member_suffix} but the ADT lacks /chosen/memory-map/{slot_name}')
        validate(member, failures)
    elif slot is not None:
        failures.append(f'ADT reserves /chosen/memory-map/{slot_name} but the payload carries no {kernel_name}{member_suffix}')


def check_gpu_addon(fat, nodes, kernel_name, failures):
    """DarwinBoot fails with EFI_COMPROMISED_DATA when the GpuAddon slot and the
    kernel.macho.gpuaddon file disagree (DarwinBoot.c AddonOffset checks)."""
    def validate(addon, problems):
        if len(addon) < 24 or addon[:8] != b'NGPUADD2':
            problems.append('gpuaddon does not start with the NGPUADD2 header')
        else:
            declared = int.from_bytes(addon[16:24], 'little')
            if declared != len(addon):
                problems.append(f'gpuaddon declares {declared} bytes but the file is {len(addon)}')
    check_file_slot(fat, nodes, kernel_name, '.gpuaddon', 'GpuAddon', validate, failures)


def check_trust_cache(fat, nodes, kernel_name, failures):
    """kernel.macho.trustcache file<->slot pairing and the ValidTrustCaches
    structure the loader requires (DarwinBoot.c TrustCacheOffset checks)."""
    def validate(caches, problems):
        problem = valid_trust_caches(caches)
        if problem:
            problems.append(problem)
    check_file_slot(fat, nodes, kernel_name, '.trustcache', 'TrustCache', validate, failures)


def check_root_policies(fat, nodes, kernel_name, official, failures):
    """kernel.macho.vroot file<->slot pairing and the VROOTB01 envelope the
    official loader requires (the fork does not read it)."""
    if not official:
        return
    def validate(policies, problems):
        if (len(policies) < 32 or policies[:8] != b'VROOTB01' or
                int.from_bytes(policies[8:16], 'little') != 1):
            problems.append('vroot does not start with the VROOTB01 version-1 header')
            return
        count = int.from_bytes(policies[16:24], 'little')
        declared = int.from_bytes(policies[24:32], 'little')
        if not 1 <= count <= 16:
            problems.append(f'vroot declares {count} policies; the loader accepts 1..16')
        if declared != len(policies):
            problems.append(f'vroot declares {declared} bytes but the file is {len(policies)}')
    check_file_slot(fat, nodes, kernel_name, '.vroot', 'RootPolicies', validate, failures)


def check_loader_tables(nodes, official, failures):
    """The /chosen placeholder tables and the memory window size that
    AdtNode validates before it touches any file."""
    sizes = prop_places(nodes, 'darwinboot-memory-size')
    for path, value in sizes:
        if path != '/chosen':
            failures.append(f'darwinboot-memory-size is a property of {path}; the loader only reads /chosen')
            continue
        if len(value) != 8:
            failures.append(f'/chosen/darwinboot-memory-size is {len(value)} bytes; DarwinBoot requires 8')
            continue
        size, = struct.unpack('<Q', value)
        if not (WINDOW_SIZE_MIN <= size <= WINDOW_SIZE_MAX and size % WINDOW_SIZE_ALIGN == 0):
            failures.append(f'/chosen/darwinboot-memory-size 0x{size:x} is outside the 0x{WINDOW_SIZE_MIN:x}..0x{WINDOW_SIZE_MAX:x} 2 MiB-aligned window range')
    ranges = prop_places(nodes, 'darwinboot-memory-ranges')
    allocatable = prop_places(nodes, 'diting-allocatable-ram')
    for path, value in ranges:
        if path != '/chosen':
            failures.append(f'darwinboot-memory-ranges is a property of {path}; the fork loader only reads /chosen')
        if len(value) != RAM_WIRE_SIZE:
            failures.append(f'{path} darwinboot-memory-ranges is {len(value)} bytes; the fork wire table is {RAM_WIRE_SIZE}')
    for path, value in allocatable:
        banks = len(value) // 16
        if path != '/chosen':
            failures.append(f'diting-allocatable-ram is a property of {path}; the fork loader only reads /chosen')
        if not value or len(value) % 16:
            failures.append(f'{path} diting-allocatable-ram is {len(value)} bytes; it must be non-empty (base, size) pairs')
        elif banks > RAM_BANK_LIMIT:
            failures.append(f'{path} diting-allocatable-ram carries {banks} banks; the fork wire holds at most {RAM_BANK_LIMIT}')
    if bool(ranges) != bool(allocatable):
        failures.append('darwinboot-memory-ranges and diting-allocatable-ram must appear together')
    for path, value in prop_places(nodes, 'diting-audio-dma'):
        if path != '/chosen':
            failures.append(f'diting-audio-dma is a property of {path}; the fork loader only reads /chosen')
        if len(value) != 16:
            failures.append(f'{path} diting-audio-dma is {len(value)} bytes; the fork loader requires 16')
    if not official:
        return
    for path, value in prop_places(nodes, 'darwinboot-memory-excluded'):
        if path != '/chosen':
            failures.append(f'darwinboot-memory-excluded is a property of {path}; the loader only reads /chosen')
        if len(value) < 16 or len(value) % 16:
            failures.append(f'{path} darwinboot-memory-excluded is {len(value)} bytes; the table is one or more 16-byte pairs')
        elif any(value):
            failures.append(f'{path} darwinboot-memory-excluded must be empty pairs the loader fills, not real ranges')
    for path, value in prop_places(nodes, 'darwinboot-loader-inputs'):
        if path != '/chosen':
            failures.append(f'darwinboot-loader-inputs is a property of {path}; the loader only reads /chosen')
        if len(value) != 64:
            failures.append(f'{path} darwinboot-loader-inputs is {len(value)} bytes; the table is two 32-byte records')
        elif any(value):
            failures.append(f'{path} darwinboot-loader-inputs must be empty records the loader fills')
    for path, value in prop_places(nodes, 'darwinboot-memory-outside'):
        if len(value) < 16 or len(value) % 16:
            failures.append(f'{path} darwinboot-memory-outside is {len(value)} bytes; the table is one or more 16-byte pairs')
        elif any(value):
            failures.append(f'{path} darwinboot-memory-outside must be empty pairs the loader fills')


def check_boot_args(entries, failures, notes):
    """DarwinBoot copies the entry args into CHAR8 CommandLine[1024]; anything
    longer than 1023 bytes or non-ASCII is EFI_BAD_BUFFER_SIZE."""
    for entry in entries:
        args = entry.get('args')
        if not isinstance(args, str):
            continue
        label = entry.get('id', 'xnu')
        notes.append(f'boot args[{label}] = {len(args)} bytes')
        if len(args) > BOOT_ARGS_LIMIT:
            failures.append(f'entry {label} boot args are {len(args)} bytes; DarwinBoot allows {BOOT_ARGS_LIMIT}')
        bad = next((ch for ch in args if ord(ch) > 0x7f), None)
        if bad is not None:
            failures.append(f'entry {label} boot args carry non-ASCII U+{ord(bad):04x}')


def check_image(path):
    kernel, ramdisk = load_image(path)
    failures = []
    notes = []
    files = walk_fv(kernel, [])
    loader = None
    for label, body in files:
        strings = body.upper()
        if b"DARWINBOOT" in strings:
            loader = body
            break
    official = True
    if loader is None:
        failures.append("no DarwinBoot image found in the firmware volume")
    else:
        official = b"DarwinBoot24" not in loader
        if "DarwinBoot".encode("utf-16-le") not in loader and b"DarwinBoot" not in loader:
            failures.append("loader UI name is not DarwinBoot")
        # The fork loader knows the diting-* ADT names; the official component uses
        # the documented DarwinBoot placeholder set instead.
        expected = OFFICIAL if official else NEW
        for token in expected:
            if token not in loader:
                failures.append(f"loader lacks {token.decode()}")
        for token in OLD:
            if token in loader:
                failures.append(f"loader still carries {token.decode()}")
    # Payload envelope + ADT contract.
    if ramdisk[:8] != b"PONGFAT1":
        failures.append("payload is not a PONGFAT1 envelope")
        return failures, notes
    tag, version, head_len, fat_len, crc, flags = struct.unpack_from("<8sIIQII", ramdisk, 0)
    fat = ramdisk[head_len:head_len + fat_len]
    if zlib.crc32(fat) != crc:
        failures.append("PONGFAT1 CRC does not match the FAT")
    for token in (b"darwinboot-memory-ranges", b"diting-allocatable-ram"):
        if token not in fat:
            failures.append(f"payload ADT lacks {token.decode()}")
    for token in OLD:
        if token in fat:
            failures.append(f"payload ADT still carries {token.decode()}")
    toml = payload_member(fat, '/EFI/UniXNU/unixnu.toml')
    if toml is None:
        failures.append('payload lacks /EFI/UniXNU/unixnu.toml')
    entries = payload_entries(toml)
    kernel_name = entries[0].get('path', 'Payloads/kernel.macho') if entries else 'Payloads/kernel.macho'
    initrd_names = [entry['initrd'] for entry in entries
                    if isinstance(entry.get('initrd'), str)]
    nodes = load_tree(fat, kernel_name, failures)
    if nodes is not None:
        check_slot_shape(nodes, failures)
        check_loader_tables(nodes, official, failures)
    check_initrd_slot(fat, nodes, initrd_names, failures, notes)
    check_trust_cache(fat, nodes, kernel_name, failures)
    check_gpu_addon(fat, nodes, kernel_name, failures)
    check_root_policies(fat, nodes, kernel_name, official, failures)
    check_boot_args(entries, failures, notes)
    return failures, notes


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("image", type=Path)
    args = parser.parse_args()
    try:
        failures, notes = check_image(args.image)
    except Exception as exc:
        print(f"ERROR {args.image}: {exc}", file=sys.stderr)
        return 2
    if failures:
        print(f"FAIL {args.image}")
        for item in failures:
            print("  -", item)
        return 1
    print(f"PASS {args.image}")
    for item in notes:
        print("  =", item)
    return 0


if __name__ == "__main__":
    sys.exit(main())
