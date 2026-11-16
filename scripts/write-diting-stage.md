# Writing a DITSTG1 archive to the device reserve zone

Geometry (same math as `native_ufs_debug_read`):

- userdata partition: first LBA `0x2F8A00`, last LBA `0x3ADF3FA` (4 KiB blocks)
- reserve: `diting_data_reserve` MiB held back at partition tail
- reserve base (absolute LBA) = `last + 1 - reserve_blocks`
- archive target = `reserve_base + diting_stage_off`

For `diting_data_reserve=48` (12288 blocks) and `diting_stage_off=1024`:

- reserve base = 0x3ADF3FA + 1 - 12288 = 61604859 - 12288 = 61592571 (0x3ACD7FB)
- archive LBA  = 61592571 + 1024 = 61593595 (0x3ACDB7B)

From a booted recovery (TWRP / diting-recovery with adb shell, root):

```
# copy archive.bin to /tmp on device first (adb push), then:
dd if=/tmp/archive.bin of=/dev/block/sda37 bs=4096 seek=61593595
```

`sda37` is userdata. Verify with `dd if=/dev/block/sda37 bs=4096 skip=61593595 count=1 | xxd | head` — first 8 bytes must be `DITSTG1\0`.

Boot args for the image: `diting_data_reserve=48;diting_stage_off=1024`
(alongside the usual `diting_ramoops_ufs=1`; the reserve holds ramoops zone0/1
at offsets 0/512, the archive sits at 1024+ — no overlap).
