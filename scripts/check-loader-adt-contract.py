#!/usr/bin/env python3
"""Check a boot image for the DarwinBoot <-> ADT property contract.

The image's firmware volume must carry the DarwinBoot loader and the payload's
ADT must use the same property names. Run it on a green image to see it PASS and
on the pong-era image (e9b615bf...) to see it FAIL; a checker that cannot fail on
the old image proves nothing.

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

LZMA_GUID = uuid.UUID("EE4E5898-3914-4259-9D6E-DC7BD79403CF")
OLD = (b"pong-allocatable-ram", b"pong-audio-dma", b"pong_ram_banks")
NEW = (b"diting-allocatable-ram", b"diting-audio-dma", b"diting_ram_banks")
OFFICIAL = (b"GpuAddon", b"RootPolicies", b"darwinboot-memory-size",
            b"RAMDisk", b"PackedRAMDisk", b"TrustCache")


def align(value):
    return (value + 4095) // 4096 * 4096


def load_image(path):
    data = Path(path).read_bytes()
    if data[:8] != b"ANDROID!":
        raise SystemExit(f"{path}: not an Android boot image")
    kernel_size, ramdisk_size = struct.unpack_from("<2I", data, 8)
    header_size, = struct.unpack_from("<I", data, 20)
    kstart = align(header_size)
    kernel = data[kstart:kstart + kernel_size]
    rstart = align(header_size) + align(kernel_size)
    ramdisk = data[rstart:rstart + ramdisk_size]
    kernel = zlib.decompress(kernel, 16 + zlib.MAX_WBITS)
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


def check_gpu_addon(fat, failures):
    """DarwinBoot fails with EFI_COMPROMISED_DATA when the GpuAddon slot and the
    kernel.macho.gpuaddon file disagree (DarwinBoot.c AddonOffset checks)."""
    addon = payload_member(fat, '/EFI/UniXNU/Payloads/kernel.macho.gpuaddon')
    adt = payload_member(fat, '/EFI/UniXNU/Payloads/kernel.macho.adt')
    slot = None
    if adt:
        try:
            slot = parse_adt(adt).get('/chosen/memory-map', {}).get('GpuAddon')
        except ValueError as error:
            failures.append(f'payload ADT is unreadable: {error}')
    if addon is not None:
        if slot is None:
            failures.append('payload carries kernel.macho.gpuaddon but the ADT lacks /chosen/memory-map/GpuAddon')
        elif len(slot) != 16 or any(slot):
            failures.append(f'ADT GpuAddon slot is {len(slot)} bytes, DarwinBoot requires 16 zero bytes')
        if len(addon) < 24 or addon[:8] != b'NGPUADD2':
            failures.append('gpuaddon does not start with the NGPUADD2 header')
        else:
            declared = int.from_bytes(addon[16:24], 'little')
            if declared != len(addon):
                failures.append(f'gpuaddon declares {declared} bytes but the file is {len(addon)}')
    elif slot is not None:
        failures.append('ADT reserves /chosen/memory-map/GpuAddon but the payload carries no kernel.macho.gpuaddon')


def check_image(path):
    kernel, ramdisk = load_image(path)
    failures = []
    files = walk_fv(kernel, [])
    loader = None
    for label, body in files:
        strings = body.upper()
        if b"DARWINBOOT" in strings:
            loader = body
            break
    if loader is None:
        failures.append("no DarwinBoot image found in the firmware volume")
    else:
        if "DarwinBoot".encode("utf-16-le") not in loader and b"DarwinBoot" not in loader:
            failures.append("loader UI name is not DarwinBoot")
        # The fork loader knows the diting-* ADT names; the official component uses
        # the documented DarwinBoot placeholder set instead.
        expected = NEW if b"DarwinBoot24" in loader else OFFICIAL
        for token in expected:
            if token not in loader:
                failures.append(f"loader lacks {token.decode()}")
        for token in OLD:
            if token in loader:
                failures.append(f"loader still carries {token.decode()}")
    # Payload envelope + ADT contract.
    if ramdisk[:8] != b"PONGFAT1":
        failures.append("payload is not a PONGFAT1 envelope")
        return failures
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
    check_gpu_addon(fat, failures)
    return failures


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("image", type=Path)
    args = parser.parse_args()
    failures = check_image(args.image)
    if failures:
        print(f"FAIL {args.image}")
        for item in failures:
            print("  -", item)
        return 1
    print(f"PASS {args.image}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
