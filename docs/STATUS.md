# Diting 当前状态（2026-11-16）

- 设备：Redmi K50 至尊版 `diting`，Qualcomm SM8475，bootloader 已解锁
- 目标系统：iPadOS 18.7.10 / 22H374 / Darwin 24.6.0（XNU 11417.140.69）
- 本文件只写已在 Diting 真机上观察到的结果与已知阻塞；逐条原始记录在 [`AGENTS.md`](../AGENTS.md)。
  继承自 Pong 的记录不算 Diting 证据，来源规则见 [`PROVENANCE.md`](PROVENANCE.md)。

## 当前设备与镜像

| 项 | 值 |
| --- | --- |
| 启动镜像 | `boot_a` = `diting-addon18.img`（进桌面、Metal 已测） |
| core 钉版 | `fd2f4d1`（`sync/upstream-20261116`；upstream `03129b6` + 本地 `00b8415`，device `59c88c8` 验证：kernel exit 0、storage/porting PASS；见根目录 `core-provenance.json`） |
| OS | Diting 布局：`/sbin/launchd` = `/diting/init` sha256 `95cb7341…`；`libditing-ui18.dylib` 174,976 B，含 `/dev/diting-touch`；卷 UUID `B07DF049…` |
| userdata | 整盘 sparse 恢复：`userdata-osditing-1109.sparse.img`（19,411,252,824 B，OS 窗口来自 `artifacts/ci-42987806310/diting-ipados18-system.cdr`，6,845,104,128 B sha256 `27c507c8972275c9170806bb975b03d762ebbb9379945b890d5665a154e8102d`） |
| 待上机候选 | `D:\ai\diting\build-work\diting-addon24-diag.img`（`54ed270b…`）、`diting-addon26-diag.img`（`ee7278b2…`）、`diting-addon27-diag.img`（`d0b0e1e1…`）、`diting-addon28-diag.img`（`8cdd951d…`）、`diting-addon29-diag.img`（`4fadc124…`，addon28 的 GPU trace/pixel 变体），静态检查 PASS，`hardware_tested=false` |
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
- 仓库记录：`AGENTS.md` 的 2026-11-15/16 各条

## 当前阻塞（真机日志定位，非推断）

| 阻塞 | 现象 | 已确认 / 待确认 |
| --- | --- | --- |
| Wi-Fi | 首笔 smpe2 RPMh 投票 `0x40508=7` 在 PCIe 训练前超时，未扫描 | 活动 TCS 为 TCS0–2；下一候选内核改用 TCS1（`cmd written tcs=` 已编入），待上机确认 committed → PCIe |
| ADSP / 电量 | ADSP 到 stage 6，stage 7 `0x30030=7` 超时（-60） | 未到 PAS 加载与电池服务发布 |
| UI 帧率 | 桌面可用但帧间隔不稳、卡顿 | Metal pipeline 编译未摊销（插件已内嵌 `__DATA,__primelist`）+ shader cache 不落盘；addon27 起 telemetry 增加 `V cache h/m/w/q/rf/wf/ev` 与 `V drv l/h/m/s/tr/mm/un`，并可开 `log-gpu=1` 的 `Diting Metal pass` 有界行；addon28 进一步用上游 Turnip 0016（shader-share）/0017（retired-BO sweep）重建，并新增 `diting_gpu_cache_dir` 与 `C cache dir=… shared=… writable=…` 行，预期降低冷编译与 fence 尾延迟（待上机对比 T/PR/H/ctc/V/C） |
| 关机 | 长按电源不能关机 | 内核无 poweroff 路径；下一候选内核含 PSCI SYSTEM_OFF 长按补丁（`Diting pwrkey … SYSTEM_OFF`） |

**未达成、不得声称可用**：Wi-Fi 扫描/关联/DHCP、电量与充电状态、Metal 逐应用兼容性与稳定帧率、
音频（live DT 为双 CS35L41，未接入）、休眠唤醒、按键关机。

## 下一轮验收

按顺序只记录第一个失败阶段，不跳步、不猜测。

1. **addon29-diag**（`4fadc124…`，kernel `7ed899e5…`，52 args/999 B；内核/插件/bridge/turnip/addon 与 addon28 逐字节相同）：
   在 addon28 基础上加 `diting_gpu_trace=1 diting_gpu_pixels=1`——前者打开 fork 的 per-frame GPU trace（提交/pass/fence 事件行），
   后者打开 pixel capture（`frameEvent(40)`，用于把 `H frame-enc`/`ctc` 尾部对应到具体 pass/pixel 集）；保留 `log-gpu=1`、
   `diting_pwrkey_log=1`/`diting_pwrkey_long=5000`，`applog_name` 收窄为 `backboardd,SpringBoard` 以放进 1000 B。
   确认桌面/触摸保持；滚动 Settings/Home 30 s 冷态读 +20/+60 s 块：`T pipeline n/total/max`、`PR resumed`、`H frame-enc` 分箱、`ctc`、
   `V cache h/m/w/q/rf/wf/ev`、`V drv l/h/m/s/tr/mm/un`、`C cache dir=… shared=… writable=…`，并用新增 trace 行归因 pass/draw/pixel 集；
   再滚 30 s 热态对比 `T`/`frame-enc`/`ctc`/`E age`；重启后再冷滚一次，看 shader-cache `h` 是否上升、`T` 是否下降；
   异常时回 addon28（无 trace，同内核/同 artifacts）或 addon27（旧 Turnip）对照。addon26 继续用于 pwrkey/PSCI SYSTEM_OFF 与 `PR functions resumed`。
   > 跟进项：args 里 `diting_ui_software=0`、`diting_software_ui=0` 来自 `scripts/build-release-image-linux.py` 的 builder 默认值，
   > 不在 board.toml；它们占用约 45 B 预算，后续应与 `[payload] kernel_args` 统一后再动。
2. **Wi-Fi**：RPMh committed → 物理电源 → PCIe → SMMU/MSI → MHI/QMI → station/MAC → 系统设置扫描 →
   关联 → DHCP。仍超时时比较 TCS1 的触发控制、命令状态、idle 与 IRQ_STATUS。
3. **电量 / ADSP**：越过 stage 7 → PAS → DSP ready → GLINK → `PMIC_RTR_ADSP_APPS` →
   `DitingBattery: physical battery power source published` → 桌面状态栏与插拔跟随。
4. **GPU 流畅度**：primelist 已内嵌；下一步补 shader-cache 持久化并回归 CP/fence、Vulkan 设备、
   实际 scanout 与提交完成；用帧间隔/`frame-enc`/`ctc` 统计判断改善。
5. **触摸延迟**：release 内核纳入 touch-latency instrumentation，采集 THP 帧间隔与 IRQ 唤醒率后再调优。

上机约束：只 `fastboot boot`（RAM-only），不写分区；使用 `D:\ai\diting\build-work` 最终镜像，启动前
从最终镜像回读内核并逐字节比对。

## 维护规则

- 新结论先写 `AGENTS.md`（输入/命令/观察/结论/下一步），再同步本文件；`host-build` 与 `device` 证据分开记。
- 继承自 Pong 的 `porting.toml` / `migration/ipados18/` 记录只作实现参照，见 [`PROVENANCE.md`](PROVENANCE.md)。
- 原厂固件、Apple 资产、unique-chip-id 等只留本地，不进仓库。
