#!/usr/bin/env python3
"""DEPRECATED — 从现有启动镜像生成仅调整 AppleARMCPU 匹配项的诊断镜像。

Nothing in the build chain calls this script. The AppleARMCPU personality fix
it produced by hand is now applied to the prelink metadata itself:
scripts/install-unixnu-inputs.py fix_apple_cpu_match patches the core
XnuPrelink emit_prelink.py before the release prelink (the same patch
kits/DitingPlatform24/build-with-runtime.py stages for local builds), so the
emitted image no longer carries the competing AppleARMCPU match. Retained as a
reference for the retired diagnostic path; it still imports kits/NativePrelink
helpers.
"""
import argparse
import json
import os
from pathlib import Path
import shutil
import struct
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET
import zlib

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'kits/NativePrelink'))
from native_prelink import macho, unserialize_xml


def pairs(element):
    items = list(element)
    if element.tag != 'dict' or len(items) % 2:
        raise ValueError('预链接信息字典格式无效')
    return {items[i].text: (items[i], items[i + 1]) for i in range(0, len(items), 2)
            if items[i].tag == 'key'}


def remove_apple_cpu(data):
    image = macho(data)
    segments = [s for s in image['segments'] if s['name'] == '__PRELINK_INFO']
    if len(segments) != 1:
        raise ValueError('预链接信息段不唯一')
    segment = segments[0]
    begin, size = segment['fileoff'], segment['filesize']
    if begin + size > len(data):
        raise ValueError('预链接信息超出内核文件')
    old = data[begin:begin + size].split(b'\0', 1)[0]
    original = unserialize_xml(old)
    root = ET.fromstring(old)
    entries = pairs(root)['_PrelinkInfoDictionary'][1]
    matching = []
    for item in entries:
        fields = pairs(item)
        identifier = fields.get('CFBundleIdentifier')
        if identifier is not None and identifier[1].text == 'com.apple.driver.AppleARMPlatform':
            matching.append(fields)
    if len(matching) != 1:
        raise ValueError('AppleARMPlatform 预链接项不唯一')
    personalities = matching[0]['IOKitPersonalities'][1]
    key, value = pairs(personalities)['AppleARMCPU']
    if pairs(value).get('IOClass', (None, None))[1].text != 'AppleARMCPU':
        raise ValueError('AppleARMCPU 匹配项与预期不同')
    if any(element.get('ID') for element in value.iter()):
        raise ValueError('目标匹配项包含共享 XML 对象，不能安全移除')
    personalities.remove(key)
    personalities.remove(value)
    updated = ET.tostring(root, encoding='utf-8').replace(b' />', b'/>') + b'\0'
    if len(updated) > size:
        raise ValueError('修改后的预链接信息超出原有空间')
    expected = original
    expected_entry = next(e for e in expected['_PrelinkInfoDictionary']
                          if e.get('CFBundleIdentifier') == 'com.apple.driver.AppleARMPlatform')
    del expected_entry['IOKitPersonalities']['AppleARMCPU']
    if unserialize_xml(updated) != expected:
        raise ValueError('预链接信息发生了其他变化')
    return data[:begin] + updated + bytes(size - len(updated)) + data[begin + size:]


def mtool(command, image, offset, *args):
    return subprocess.check_output([command, '-i', f'{image}@@{offset}', *args],
                                   env={**os.environ, 'MTOOLS_SKIP_CHECK': '1'})


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input', required=True, type=Path)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    source, output = args.input.resolve(), args.output.resolve()
    if source == output or output.exists():
        raise SystemExit('输出必须是不存在的新文件')
    with source.open('rb') as stream:
        header = stream.read(4096)
        if header[:8] != b'ANDROID!' or struct.unpack_from('<I', header, 40)[0] != 4:
            raise ValueError('仅支持 Android v4 启动镜像')
        kernel_size, ramdisk_size = struct.unpack_from('<II', header, 8)
        ramdisk = 4096 + ((kernel_size + 4095) // 4096) * 4096
        stream.seek(ramdisk)
        envelope = stream.read(4096)
    magic, version, envelope_size, fat_size, _, _ = struct.unpack_from('<8sIIQII', envelope)
    if magic != b'PONGFAT1' or version != 1 or envelope_size != 4096 or ramdisk_size != envelope_size + fat_size:
        raise ValueError('不支持的 PONGFAT1 布局')
    fat = ramdisk + envelope_size
    manifest = json.loads(mtool('mtype', source, fat, '::/EFI/UniXNU/Payloads/pong-boot-manifest.json'))
    if manifest.get('kernel_sha384') is not None:
        raise ValueError('清单绑定了内核摘要，不能直接修改')
    member = '::/EFI/UniXNU/Payloads/kernel.macho'
    patched = remove_apple_cpu(mtool('mtype', source, fat, member))
    output.parent.mkdir(parents=True, exist_ok=True)
    try:
        with source.open('rb') as incoming, output.open('xb') as outgoing:
            shutil.copyfileobj(incoming, outgoing)
        with tempfile.TemporaryDirectory(prefix='diting-cpu-') as directory:
            temporary = Path(directory) / 'kernel.macho'
            temporary.write_bytes(patched)
            mtool('mcopy', output, fat, '-o', str(temporary), member)
        crc = 0
        with output.open('rb') as stream:
            stream.seek(fat)
            remaining = fat_size
            while remaining:
                chunk = stream.read(min(1024 * 1024, remaining))
                if not chunk:
                    raise ValueError('payload 截断')
                crc = zlib.crc32(chunk, crc)
                remaining -= len(chunk)
        with output.open('r+b') as stream:
            stream.seek(ramdisk + 24)
            stream.write(struct.pack('<I', crc & 0xffffffff))
    except Exception:
        output.unlink(missing_ok=True)
        raise
    print(f'已生成诊断镜像 {output}；尚未真机验证。')


if __name__ == '__main__':
    main()
