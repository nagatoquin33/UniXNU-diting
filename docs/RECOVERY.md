# 救砖与恢复手册

设备：Redmi K50 至尊版（diting，SM8475，串号 9e0c2b55）。所有刷写操作先核对目标分区与哈希；**写分区前必须获得明确授权**。本文只列已有资产与可验证步骤，未在本轮真机验证的项已标注。

## 1. 可用恢复资产

| 资产 | 位置 | sha256 | 用途 |
| --- | --- | --- | --- |
| `diting-addon18.img` | D: `build-work/` | `6c026c49…c515` | `boot_a` 当前镜像；Diting OS 桌面/触摸基线（RAM-only `fastboot boot` 亦可） |
| `diting-recovery-boot.img` | D: `build-work/` | `67cf2dc9…2d6a` | TWRP RAM Recovery：ramoops/APFS 回读、`reboot bootloader` |
| 已刷入的 TWRP（`boot_b`） | 设备 `boot_b` | 同上 | 电源尝试期间刷入；如 `boot_a` 不可用可临时从 `boot_b` 进 TWRP |
| `userdata-osditing-1109.sparse.img` | D: `build-work/` | `6c455dec…136e` | 当前可用 userdata 恢复（11-09 raw + Diting OS 窗口 `27c507c8…`） |
| `userdata-root.img` | WSL `diting-ci/out/userdata/` | `a30ed367…` | raw 容器（Pong 布局 OS，仅作容器/回退素材） |
| `prepared-420734-os.img` | WSL `rollback-assets/` | `45b6344f…3fda` | OS 窗口内容回退 |
| `windows/Data.img` | WSL `rollback-assets/` | `1378adfe…4095` | Data 窗口回退（UUID 337CF716） |
| `ipados18-source/` | WSL `rollback-assets/` | — | OS/SystemOS/AppOS 还原源（只读资产） |
| `diting-unixnu-uefi-darwinboot24.img` | D: `build-work/b1-darwinboot24/` | `285e6afa…06fa` | B1 DarwinBoot24 bring-up 基线 |
| `greenI2-log-menu.img` | D: `build-work/` | `32c1a7c7…d680` | Advanced Logger 菜单镜像（固件日志导出通道） |
| ADT 候选 A/B | `build-work/evidence-20261116-adt-gen/` | `9bf5ea50…` / `47e6b744…` | 官方-ADT 验证对照 |
| OS 窗口 cdr | D: `artifacts/ci-42987806310/` | 见 AGENTS.md | Diting OS 窗口重写源（6.4 GB） |

`boot_a` 当前为 addon18；`boot_b` 曾刷入 TWRP 用于关机尝试，设备可能仍停在 Mi logo、active slot 为 `b`。

## 2. 常见场景与步骤

### A. 设备正常进入 FASTBOOT

```sh
fastboot devices
fastboot set_active a
fastboot reboot
```

预期：回 iOS 桌面；触摸可用（Diting OS 窗口）。若桌面黑屏/卡更新页，见场景 D/E。

### B. 卡 Mi logo / 黑屏，adb 不可见

1. 长按 **音量下 + 电源** 10–15 秒，松开后应进入 FASTBOOT（本轮多次需要用户手动按键，属已知边界）；
2. `fastboot devices` 出现设备后先 `set_active a`，再 `fastboot boot build-work/diting-addon18.img` 或直接 `fastboot reboot`；
3. 若仍停在 logo：尝试 **音量上 + 电源** 进 recovery（`boot_b` 的 TWRP），`adb devices` 应出现 recovery；在 TWRP 内可 `fastboot` 不可用，但可 `adb shell reboot bootloader` 回 FASTBOOT。

### C. FASTBOOT / recovery 都不可见

这是硬砖边界：本机**没有** EDL/firehose loader（`rom-os3-fastboot/` 为空），不能本地走 9008 恢复。此时不要盲试写分区；记录现象并等待具备 Firehose 工具/授权后再处理。

### D. userdata 损坏或 OS 窗口异常

前提：FASTBOOT 可用且已授权。

1. 校验 sparse：`sha256sum` 应等于 `6c455dec…136e`；
2. `scripts/flash-userdata-image.py --image <raw> --sparse <sparse> --product diting`（或 Windows 侧等价流程）——整窗写入会清空 `/ngpu`，随后用带 7 文件 addon 的镜像启动重建；
3. 或只恢复 OS 窗口：`prepared-420734-os.img` / `27c507c8…` 窗口内容（优先保留 Data）。

### E. 启动后服务/桌面异常的取证

1. 用 `diting-recovery-boot.img` 进 TWRP，回读 ramoops：

```sh
adb exec-out dd if=/dev/block/sda37 bs=4096 skip=58615291 count=1024 of=ramoops.bin
```

2. 或使用 `scripts/extract-ramoops-ufs.py --reserve-mib 4`；
3. 固件日志：启动菜单 Tools → Advanced Logger（greenI2 菜单镜像）导出二维码/文件；
4. 记录到 `build-work/device-runs/<日期>/`，不拍屏。

### F. 关机 / 强制重启

- 正常：长按电源 ≥ `diting_pwrkey_long`（默认 5000 ms），addon26+ 内核走 PSCI SYSTEM_OFF；
- 异常：长按电源 10–15 秒硬断电；不要反复刷 boot 分区。

### F. panic 屏（SHENG-PANIC-1 QR）

panic hook 在 panic 文本旁画 QR（头 `SHENG-PANIC-1`），载荷含寄存器、UUID、镜像基址与被截断的 reason。
流程：**拍照 → 离线解码 → 断电重进 fastboot**（不要在 panic 后反复重启）：

```sh
python3 -m pip install --user --break-system-packages zxing-cpp pillow   # 一次性
python3 scripts/decode-sheng-panic-qr.py panic-photo.jpg --json          # 或 --out record.txt
```

- QR 只含寄存器与被截断的 reason（`TRUNCATED=1`）；完整 console 仍需 ramoops（场景 E）。
- **外部样本**（2026-11-16 群聊屏拍，非 Diting 设备；仅用于验证解码器与 RootLayout 解读，**不是** Diting panic，
  也不能当作我们 userdata/slot 的证据）：UUID `218FDCCE-86F6-326F-9BC1-536380109D02`、ELR `FFFFFE00075C3220`、
  FAR `FFFFFECF9BD00000`、REASON `UFS ROOT FAILURE: no userdata partition …`；解码记录見 `build-work/evidence-20261116-panic-qr/`。
- `no userdata partition` 来自 `drivers/NativeUfs/RootLayout.h`（GPT 解析段 `:139-142`）：GPT 头/表 CRC 已通过，
  只是没有名为 `userdata` 的 GPT 分区（或首尾 LBA 非法）⇒ **userdata 布局/内核预期不匹配**，不是读 UFS 失败；
  先核对镜像 sha、slot 与 kernel 几何（`manifest=`/`stage=` 诊断），再决定是否走场景 D/E。
- 取证后重新进 fastboot：长按 **音量下 + 电源** 10–15 秒（见场景 B）。

## 3. 安全规则

- 任何 `fastboot flash` / 窗口写入前必须获得明确授权，并先 `sha256sum` 校验镜像；
- 保留 `boot_a` 为已验证基线，不要用未验证镜像覆盖；
- 覆盖 `boot_b` 的 TWRP 前确认 `boot_a` 可用；
- 整盘 userdata 写入会清 `/ngpu`，恢复后用带 addon 的镜像启动；
- 所有恢复动作记录时间、命令、哈希与观察结果到 AGENTS.md/evidence。

## 4. 未验证项

- `set_active a` 后的 iOS 桌面恢复：本轮设备未回到 FASTBOOT，未验证。
- EDL/9008 恢复路径：本机无 loader，未验证。
- TWRP 退出到 FASTBOOT 的按键序列：仅按常见 TWRP 行为记录，未在本轮验证。
