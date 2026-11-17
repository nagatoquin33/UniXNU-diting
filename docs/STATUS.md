# Diting 当前状态（2026-11-17）

- 设备：Redmi K50 至尊版 `diting`（串号 `9e0c2b55`），Qualcomm SM8475，bootloader 已解锁，无 EDL/firehose 救砖文件
- 目标系统：iPadOS 18.7.10 / 22H374 / Darwin 24.6.0（XNU 11417.140.69）
- 本文件只写已在 Diting 真机上观察到的结果与已知阻塞；逐条原始记录在 [`AGENTS.md`](../AGENTS.md)，详细交接与复制矩阵见 `D:\ai\diting\交接-2026-11-17-状态与下一步.md` 与 `D:\ai\diting\build-work\evidence-20261117-copy-plan\PLAN.md`。
  继承自 Pong 的记录不算 Diting 证据，来源规则见 [`PROVENANCE.md`](PROVENANCE.md)。

## 当前设备与镜像

| 项 | 值 |
| --- | --- |
| 启动镜像 | `boot_a` = `diting-addon18.img`（`6c026c49…`，**目前唯一真机验证能进桌面的基线**）；`boot_b` = `diting-recovery-boot.img`（TWRP `67cf2dc9…`，当前 active slot=`b`）；日常实验仅用 RAM-only `fastboot boot` |
| core 钉版 | `121ea7f`（条件性 build-verified；`xnu-ci-core` 仍保留 `0ce9779`） |
| OS / userdata | Diting 布局：`/sbin/launchd` = `/diting/init` sha256 `95cb7341…`；`libditing-ui18.dylib` 174,976 B，含 `/dev/diting-touch`；卷 UUID `B07DF049…`；Data 窗口 8 GiB（UUID `337CF716…`）；sparse 恢复 `userdata-osditing-1109.sparse.img`（19,411,252,824 B） |
| 历史候选（11-16/17 实测结论） | `addon18`（`6c026c49…`）能进桌面；`addon19`（`102fd293…`，不可复现脏树构建）到 smpe3 投票；`addon35`–`48` 均未过启动：缺失 `GpuAddon` 槽（`addon26`–`35`）或 `initrd`/`RAMDisk` 槽不匹配（`addon45`–`47`）在 loader 报 `Compromised Data`，`addon39`/`40` 符号化落点 `_cfil_data_filter+0x13c` 早崩，`addon42`/`44` 早崩，`addon48` 无 ramoops |
| 分支状态 | `diting-ci`：`dev`（含 6 个 host-verified 提交 `890532b`/`18870af`/`0bd067f`/`00daa2a`/`c46603f`/`48c6b80`，merge `7144282`；feature branch 已删除；未合入 `main`）；`main`（稳定，仅文档与已验证配置）、`dev`（集成，含 `e8e82d6`..`91dbe4f` 共 6 项 `device-unverified` 改动）。核心 fork：`main` @ `377f0ff`、`dev` @ `121ea7f` |
| 设备可见性 | **手机未连接**；关机/重启需先确认设备连接与在场，恢复见 [`RECOVERY.md`](RECOVERY.md) |
| 代码备份 | `/home/nagatoquin/unixnu/backups/diting-ci-before-rpmh-slot-20261115` |

## 已实机证实

| 项目 | 结果 |
| --- | --- |
| 桌面 | addon18 + Diting 布局 OS 启动到 iPadOS 18.7.10 桌面并稳定运行 |
| 触摸 | Goodix GT9916（Berlin-D，SPI `0x990000`，GENI-DMA 6.4 MHz，IRQ240/GPIO21）驱动栈就绪，UI 经 `/dev/diting-touch` 收到事件；点击、滑动、拖动可用 |
| OS 布局 | Diting 布局（`/diting`、`launchd` = `/diting/init` `95cb7341…`、`libditing-ui18` 174,976 B）；Pong 布局（`/pong`、`libpong-ui18` `28d133d0…`）与触摸桥不兼容 |
| GPU / Metal 路径 | `DITING ADRENO: CP ready`、`DITING METAL: real IOAcceleratorES provider published`、`… status=0x0`、`DITING SCANOUT … status=0x0`，GPU submits 有记录 |
| 八核 | CPU0–7 均 `first boot completed`；SpringBoard / backboardd 正常运行 |
| 插件 / 持久化 | 六/七件 GPU+ADSP addon 分片同步写入后持久化：`written=0 same=6/7 failed=0`，Extensions stage/status 5/0；`/ngpu/firmware/adsp.mbn` 23,380,392 B 在盘 |
| 证据通道 | ramoops（userdata 尾部 4 MiB，TWRP `dd` 回读，见场景 E）；Advanced Logger 菜单镜像（`greenI2-log-menu.img`，固件日志导出）；panic 屏 QR（`SHENG-PANIC-1`：寄存器 + 截断 reason，`scripts/decode-sheng-panic-qr.py`，见 `evidence-20261116-panic-qr/README.md`）；USB CDC console 多次尝试未取得（不作为通道） |
| ADSP //ngpu 链路（静态） | addon 写入链 → 加载链已按源码逐点核对：`zzzzzzzzzzzzzzzzzz-diting-gpu-addon.patch` 先 `mkdir` 缺失父目录（含 `/private/var/ngpu` 本身，`:194-201`），再对每个 addon 成员 `snprintf("/private/var/ngpu/%s", name)`（`:292`），故 `firmware/adsp.mbn` 落在 `/private/var/ngpu/firmware/adsp.mbn`；`DitingFirmware.c:11-12` 白名单恰好接受 `/diting/firmware/adsp.mbn` 与 `/private/var/ngpu/firmware/adsp.mbn`；`DitingAdsp.cpp` `openFirmware()` 用 `snprintf("%s/adsp.mbn", base)`（`:495`，base 缺省 `/diting/firmware`），`start()` 从 `diting_adsp-fw` 解析 base（`:512`，我们的 args = `/private/var/ngpu/firmware`），读不到时按 ENOENT/ENXIO/EIO 重试 90×1 s。7 文件 addon（如 `735fbc6d…`）确含 `firmware/adsp.mbn` sha `d299d413…`；静态链路自洽，剩余设备侧未知只有「启动时 addon 拷贝成功」与「ADSP 加载到 ready」 |
| launchd | PID 1 `exec /sbin/launchd` 的 EFAULT 已修复 |

## 证据路径

- ramoops（Diting 真机，Recovery 只读回读）：`ramoops-addon16.bin`、`ramoops-addon16-full.bin`、
  `ramoops-addon17.bin`、`ramoops-addon18c.bin`（桌面/触摸/GPU/ADSP 状态）；均在 `D:\ai\diting\build-work\`
- OS 窗口：`artifacts/ci-42987806310/diting-ipados18-system.cdr`（6,845,104,128 B `27c507c8…`）；
  sparse：`D:\ai\diting\build-work\userdata-osditing-1109.sparse.img`
- GPU：`build-work/evidence-20261115-gpu-framerate/README.md`、`evidence-20261115-gpu-prime/`；
  触摸延迟：`build-work/evidence-20261115-touch-lag/README.md`
- 候选镜像：`build-work/evidence-20261116-addon26/README.md`（addon26）、`evidence-20261115-gpu-prime/verify-addon24.py`
  （addon24）；pwrkey/PSCI：`build-work/evidence-20261116-pwrkey/README.md`
- GPU 上游诊断移植：`build-work/evidence-20261116-gpu-upstream/README.md`、`addon27-report.json`、`verification.json`
- Turnip 重建 / addon28：`build-work/evidence-20261116-turnip/README.md`、`addon28-report.json`、`verification.json`
- addon29 追踪变体：`build-work/evidence-20261116-gpu-official/verification-addon29.json`、`build-image-addon29.log`（产物逐字节与 addon28 相同，仅 args 不同）
- ADT 官方路径候选/A-B：`build-work/evidence-20261116-adt-gen/README.md` §14–15、`ab-compare.json`、`merge-checklist.md`（合并门槛与回滚）
- panic QR 通道（解码器）；解码记录来自**外部群聊样本**（仅验证解码器与 RootLayout 解读，不是 Diting panic）：
  `build-work/evidence-20261116-panic-qr/README.md`、`record.json`、`synthetic-decode.json`
- 仓库记录：`AGENTS.md` 的 2026-11-15/16 各条

## 当前阻塞（真机日志定位与社区对照，非推断）

| 阻塞 | 现象 | 根因与社区解法 |
| --- | --- | --- |
| 重编内核早崩 | `addon19` 之后重编内核（`addon35`/`39`/`40`/`42`/`44`）均早崩；`addon39`/`40` 符号化落点 `_cfil_data_filter+0x13c` | **主机端已对齐**（`dev` merge `7144282`，`890532b`）：`build-xnu-ipados18.sh` 恢复 `patch --forward` 并剥离 `0001` 以外编号补丁；`build-release-image-linux.py` 默认 `--prelink-kernel`（un-prelinked 输入、9 个 library-only 组件）；`CONFIG_XNU_PRELINKED_IOSURFACE=n`；kernel sha `6553048f…`、prelink 候选 `c3dfa0f5…`。真机待验 |
| Loader `Compromised Data` | `addon45`–`48` 在菜单被拒 | **主机端已扩检**（`18870af`）：`check-loader-adt-contract.py` 扩为完整 DarwinBoot 契约（TrustCache/RootPolicies、16-byte 零槽、packed ramdisk、official/fork `/chosen`、boot-arg 长度/ASCII）。199 镜像扫描：116 PASS / 75 FAIL / 8 ERROR；`addon23`–`36` 因早于 `e8e82d6` 的 GpuAddon 槽预留而 FAIL，`addon45`–`47` 因 initrd 无 RAMDisk 槽 FAIL；`addon18`/`addon48`/B1 PASS |
| Wi-Fi | `addon18c` 首笔 `smpe2` 超时；`addon19` 六轨 `physical ready` 后 `smpe3` 停在 `triggered, polling` | **主机端已回灌**（`0bd067f`/`00daa2a`）：整包对齐 `UniXNU-zizhan @ 034a0b0` `PongWifi`，恢复 `wait_event_timeout_once`/`adapt_dispatcher_timers`/重连与 basic-rate/`nw_wifi_rssi_limits`/`scan_result24`/`bdwlang` BDF 前缀/锁外通知队列，撤掉 `station_identity`、6 GHz 跳过、staged/forceFlush、合成 MAC。live-DT TCS 映射：触控 TCS0、Wi-Fi/ADSP 共享 TCS1、GPU TCS2；Goodix `io_supply_on()` 经 `diting_rpmh_vote()`。`diting_wifi_ipa` 缺省 `0` 并推迟 `smpe3` 轨。kernel sha `bd69c8b7…`，ath11k 独立编译净。真机待验 |
| ADSP / 电量 | ADSP stage 7 `0x30030=7` 超时（-60）；`DitingBattery` 缺 `AppleSmartBattery` | **主机端已对齐**（`c46603f`）：发布 `AppleSmartBattery`（含 `MaximumCapacityPercent`/`Serial`/`BatteryData`），Xiaomi 属性 ID 在 12 后 +1 偏移，去掉 `*10` 温度缩放。kernel sha `8d057e5c…`。真机待验；健康度转圈在 `zizhan` 亦未闭环，不伪造状态 |
| UI 帧率 | `addon18` 桌面掉帧严重 | **主机端已对齐**（`48c6b80`）：`ui_compat18.c` CADisplayLink swizzle 同时覆盖 `UIViewInProcessAnimationManager` 与 `UIKit.InProcessAnimationManager`（仅 SpringBoard 安装）；`prepare-diting-mesa.py` 幂等应用 `patches/mesa/0016`/`0017`；Turnip dylib 重建 17,882,280 B sha `ccc122f6…`。userland dylib 仅 macOS（`xcrun --sdk iphoneos`）可构建，主机未验证。真机待验 |
| 音频 / 蓝牙 / 相机 | 均未接入；Data 窗口仅 8 GiB | 音频：live DT 为双 `CS35L41 @ 0x40/0x42`（`TFA9873` 不存在），参照 `UniXNU-sheng` AudioReach + `gts7xlwifi` `T970Audio.cpp`；蓝牙：参照 `UniXNU/QcaBluetooth` + `gts7xlwifi` `bluetoothd` 补丁；相机暂无 iOS 原生 H9 ISP 方案 |

**未达成、不得声称可用**：Wi-Fi 扫描/关联/DHCP、电量与充电状态、Metal 逐应用兼容性与稳定帧率、音频、蓝牙、相机、休眠唤醒、按键关机。

## 下一轮工作重点（社区优先，主机验证后再上机）

1. **构建候选镜像（手机未连接时可完成）**：
   - 在 `dev` 分支用现有配方产出一张候选 boot 镜像（kernel `bd69c8b7…`/`8d057e5c…` 叠加后的新基线 + addon18 args + library-only prelink `c3dfa0f5…`），先跑 `check-loader-adt-contract.py`、`check-storage-bindings.py` 与 `porting-record.py check` 三张主机门禁。
2. **单变量上机验收（需设备连接与用户在场；host-only 改动一律先验证再上机）**：
   - 每轮只改一个变量、只做 RAM-only `fastboot boot`，逐段取 `ramoops` 与 `Advanced Logger` 原文；写分区前必须单独授权。建议顺序：
     - TCS0–TCS4 探针：确认活动槽 0–2、共享 TCS1、GPU TCS2 的实际投票与 `via=` 判据；
     - 6 条 WLAN 轨 + `diting_wifi_ipa=1`（恢复 `smpe3`）：看 `physical ready` 与 PCIe/MHI/QMI 推进；
     - 电池/GLINK：`AppleSmartBattery` 发布、读数与插拔，ADSP stage 7→8+；
     - GPU：桌面 fps 与 Metal 兼容性回归。

上机约束：只 `fastboot boot`（RAM-only），不写分区；使用 `D:\ai\diting\build-work` 最终镜像，启动前核对 sha256 与载荷一致。

## 维护规则

- 严格遵守 `AGENTS.md` 中的 **社区优先与移植铁律（能抄就抄）** 与 **工作方法**。
- 新结论先写 `AGENTS.md`（输入/命令/观察/结论/下一步），再同步本文件；`host-build` 与 `device` 证据分开记。
- 继承自 Pong 的 `porting.toml` / `migration/ipados18/` 记录只作实现参照，见 [`PROVENANCE.md`](PROVENANCE.md)。
- 原厂固件、Apple 资产、unique-chip-id 等只留本地，不进仓库。
