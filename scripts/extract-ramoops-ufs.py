#!/usr/bin/env python3
"""Extract the ramoops mirror from the userdata-tail reserve via adb.

Kernel side contract (diting_ramoops_ufs=1 + diting_data_reserve=<MiB>):
zone layout in the last reserve MiB of the userdata partition's LUN LBA space:
  rel block 0   : console ring  (12-byte header + wrapped data, 2 MiB)
  rel block 512 : diagnostic    (12-byte header + append data, 2 MiB)
Header: <III sig=0x43474244 start size

Usage:
  python3 scripts/extract-ramoops-ufs.py [--reserve-mib 4] [--out ramoops.txt]
Runs `adb shell su -c dd ...` on a device in recovery/root adb.
"""
import argparse, subprocess, struct, sys

MAGIC = 0x43474244
ZONE_BYTES = 0x200000
HDR = 12

def sh(cmd):
    r = subprocess.run(cmd, capture_output=True)
    return r

def main():
    p = argparse.ArgumentParser()
    p.add_argument('--reserve-mib', type=int, default=4)
    p.add_argument('--userdata-last', type=lambda s: int(s, 0), default=0x3adf3fa,
                   help='absolute LUN LBA of the last userdata block (ADT/geometry)')
    p.add_argument('--dev', default='/dev/block/sda', help='block device spanning the LUN')
    p.add_argument('--out', default='ramoops-ring.txt')
    a = p.parse_args()

    blocks = a.reserve_mib * 256
    base = a.userdata_last + 1 - blocks
    total_bytes = blocks * 4096
    print(f'reserve zone: LBA {base:#x} .. {a.userdata_last:#x} ({total_bytes} bytes)')

    # dd in 4K blocks; adb exec-out keeps the bytes raw
    cmd = ['adb', 'exec-out', 'su', '-c',
           f'dd if={a.dev} bs=4096 skip={base} count={blocks} 2>/dev/null']
    r = sh(cmd)
    data = r.stdout
    if r.returncode != 0 or len(data) < ZONE_BYTES:
        sys.exit(f'dd failed rc={r.returncode} bytes={len(data)}: {r.stderr[:200]!r}')
    print(f'read {len(data)} bytes')

    for zone, name in [(0, 'console-ring'), (1, 'diagnostic')]:
        off = zone * ZONE_BYTES
        sig, start, size = struct.unpack_from('<III', data, off)
        if sig != MAGIC:
            print(f'[{name}] no magic ({sig:#010x}) — zone not written (mirror off? not flushed?)')
            continue
        zone_data = data[off + HDR: off + ZONE_BYTES]
        if zone == 0:
            # wrapped ring: bytes [start, start+size) modulo capacity
            cap = ZONE_BYTES - HDR
            out = bytes(zone_data[(start + i) % cap] for i in range(size))
        else:
            out = bytes(zone_data[:size])
        text = out.decode('utf-8', errors='replace')
        path = a.out.replace('.txt', f'-{name}.txt') if '.txt' in a.out else f'{a.out}-{name}.txt'
        open(path, 'w').write(text)
        print(f'[{name}] size={size} -> {path}')
        # show tail so the last lines are visible immediately
        tail = text.rstrip().split('\n')[-40:]
        print('---- tail ----')
        print('\n'.join(tail))
        print('--------------')

if __name__ == '__main__':
    main()
