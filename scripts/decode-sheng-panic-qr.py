#!/usr/bin/env python3
"""Decode the SHENG panic QR from a screen photo or screenshot.

The panic hook draws `SHENG-PANIC-1` (or `SHENG-PANIC-*`) as a QR beside the
panic text; the payload carries the panic registers, the UUID, the image base
and a truncated reason string. This turns a photo into the structured record
without retyping the screen.

Usage:
    decode-sheng-panic-qr.py PHOTO [--json]
    decode-sheng-panic-qr.py PHOTO --out record.txt

Requires the `zxing-cpp` module (pip install --user --break-system-packages
zxing-cpp); Pillow is used for image loading when available.
"""
import argparse
import json
import re
import sys

FIELDS = ('UUID', 'CALLER', 'SP', 'ELR', 'ESR', 'FAR', 'PHYS', 'IMAGE',
          'TOTAL', 'DROPPED', 'REGS', 'REASON', 'TRUNCATED')


def load_image(path):
    try:
        from PIL import Image
    except ImportError:
        return None
    return Image.open(path).convert('L')


def decode(path):
    try:
        import zxingcpp
    except ImportError:
        sys.exit('zxingcpp is missing: python3 -m pip install --user --break-system-packages zxing-cpp')
    image = load_image(path)
    if image is None:
        sys.exit('Pillow is missing: python3 -m pip install --user --break-system-packages pillow')
    found = zxingcpp.read_barcodes(image)
    texts = [r.text for r in found if r.text]
    if not texts:
        sys.exit('no QR/barcode found in ' + path)
    records = []
    for text in texts:
        if not text.startswith('SHENG-PANIC'):
            records.append({'raw': text})
            continue
        record = {'header': text.splitlines()[0]}
        for line in text.splitlines()[1:]:
            key, _, value = line.partition('=')
            record[key.strip()] = value.strip()
        # The reason string is deliberately truncated in the QR; keep it whole.
        if 'REASON' in record:
            record.setdefault('reason_truncated', 'TRUNCATED' not in record or record.get('TRUNCATED') == '1')
        records.append(record)
    return records


def main():
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('photo')
    parser.add_argument('--json', action='store_true', help='print JSON instead of key=value lines')
    parser.add_argument('--out', help='write the decoded records to this file')
    args = parser.parse_args()

    records = decode(args.photo)
    if args.json:
        text = json.dumps(records, indent=2)
    else:
        lines = []
        for record in records:
            lines.append('---- record ----')
            for key, value in record.items():
                lines.append(f'{key}={value}')
            lines.append('---- end ----')
        text = '\n'.join(lines)
    print(text)
    if args.out:
        with open(args.out, 'w', encoding='utf-8') as handle:
            handle.write(text + '\n')


if __name__ == '__main__':
    main()
