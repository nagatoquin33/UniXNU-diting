#!/usr/bin/env python3
"""Pack a file set into the DITSTG1 staged-install archive.

The kernel-side installer (zzzzzzzzzzzzzzzzzz-diting-stage-install.patch)
reads this archive from the userdata reserve zone at reserve-relative block
`diting_stage_off` and plants each record on the rw root volume under
/System/Library/Extensions.

Layout (4096-byte blocks):
  block 0: hdr { magic 'DITSTG1\\0' u64, count u32, flags u32, blocks u64 }
  record:  meta block { type u32, mode u32, uid u32, gid u32, size u64,
                        blocks u64, pathLen u32, crc u32, path[4040] }
           then `blocks` data blocks of file content (zero-padded).

Usage: pack-diting-stage.py --out archive.bin --file SRC=DEST ... --dir DEST ...
"""
import argparse, os, struct, zlib, stat

MAGIC = 0x3147535453544944  # 'DITSTG1\0' little-endian
BLK = 4096


def meta_block(type_, mode, uid, gid, size, blocks, path, crc=0):
    p = path.encode()
    assert 0 < len(p) < 4040
    return struct.pack('<IIIIQQII', type_, mode, uid, gid, size, blocks,
                       len(p), crc) + p


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--out', required=True)
    ap.add_argument('--file', action='append', default=[],
                    help='SRC=DEST local file to absolute guest path')
    ap.add_argument('--dir', action='append', default=[],
                    help='SRC_DIR=DEST_PREFIX recursive add of a directory')
    ap.add_argument('--mkdir', action='append', default=[],
                    help='absolute guest directory to create')
    args = ap.parse_args()

    records = []  # (type, mode, uid, gid, data_bytes, guest_path)

    for d in args.mkdir:
        records.append((2, 0o755, 0, 0, b'', d))
    for spec in args.dir:
        src, dest = spec.split('=', 1)
        src = os.path.abspath(src)
        for root, dirs, files in os.walk(src):
            rel = os.path.relpath(root, src)
            gdir = dest if rel == '.' else dest + '/' + rel.replace(os.sep, '/')
            records.append((2, 0o755, 0, 0, b'', gdir))
            for name in files:
                fsrc = os.path.join(root, name)
                mode = 0o755 if os.access(fsrc, os.X_OK) else 0o644
                with open(fsrc, 'rb') as f:
                    records.append((1, mode, 0, 0, f.read(), gdir + '/' + name))
    for spec in args.file:
        src, dest = spec.split('=', 1)
        mode = 0o755 if os.access(src, os.X_OK) else 0o644
        with open(src, 'rb') as f:
            records.append((1, mode, 0, 0, f.read(), dest))

    for r in records:
        assert r[5].startswith('/System/Library/Extensions/'), \
            f'record outside Extensions scope: {r[5]}'

    blob = bytearray()
    pos_meta = []
    for type_, mode, uid, gid, data, path in records:
        blocks = (len(data) + BLK - 1) // BLK if type_ == 1 else 0
        crc = zlib.crc32(data) & 0xffffffff if data else 0
        meta = meta_block(type_, mode, uid, gid, len(data), blocks, path, crc)
        meta += b'\0' * (BLK - len(meta))
        blob += meta + data + b'\0' * (blocks * BLK - len(data))
        pos_meta.append(path)

    total = (len(blob) + BLK - 1) // BLK + 1
    hdr = struct.pack('<QIIQ', MAGIC, len(records), 0, total)
    hdr += b'\0' * (BLK - len(hdr))
    image = hdr + bytes(blob)
    with open(args.out, 'wb') as f:
        f.write(image)

    print(f'{args.out}: {len(image)} bytes = {len(image)//BLK} blocks, '
          f'{len(records)} records')
    for p in pos_meta:
        print(f'  {p}')


if __name__ == '__main__':
    main()
