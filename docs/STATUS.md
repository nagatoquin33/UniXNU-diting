# Diting 当前状态（2026-11-16）

- 设备：Redmi K50 至尊版 `diting`，Qualcomm SM8475，bootloader 已解锁
- 目标系统：iPadOS 18.7.10 / 22H374 / Darwin 24.6.0（XNU 11417.140.69）
- 本文件只写已在 Diting 真机上观察到的结果与已知阻塞；逐条原始记录在 [`AGENTS.md`](../AGENTS.md)。
  继承自 Pong 的记录不算 Diting 证据，来源规则见 [`PROVENANCE.md`](PROVENANCE.md)。

## 当前设备与镜像

| 项 | 值 |
| --- | --- |
| 启动镜像 | `boot_a` = `diting-addon18.img`（进桌面、Metal 已测） |
| core 钉版 | `121ea7f`（**条件性 bump**：核心 fork `dev` @ `121ea7f` = merge upstream `9931232`/PR #272；diting-ci `dev` `2d6d0c2` 上 kernel exit 0、kernel `0c1a2c1f…` 73,781,248 B、26 entries 含 IOGPU、construct `fd7bbfa9…21320094`、storage/porting PASS；**仅 build-verified**，addon30 重建/设备启动与 `main` `f853d0d` 复验待完成；上一 pin `fd2f4d1` 仍在历史中，见 `core-provenance.json`） |
| OS | Diting 布局：`/sbin/launchd` = `/diting/init` sha256 `95cb7341…`；`libditing-ui18.dylib` 174,976 B，含 `/dev/diting-touch`；卷 UUID `B07DF049…` |
| userdata | 整盘 sparse 恢复：`userdata-osditing-1109.sparse.img`（19,411,252,824 B，OS 窗口来自 `artifacts/ci-42987806310/diting-ipados18-system.cdr`，6,845,104,128 B sha256 `27c507c8972275c9170806bb975b03d762ebbb9379945b890d5665a154e8102d`） |
| 待上机候选 | `D:\ai\diting\build-work\diting-addon24-diag.img`（`54ed270b…`）、`diting-addon26-diag.img`（`ee7278b2…`）、`diting-addon27-diag.img`（`d0b0e1e1…`）、`diting-addon28-diag.img`（`8cdd951d…`）、`diting-addon29-diag.img`（`4fadc124…`）、`diting-addon30-diag.img`（`a2158d7a…`，合并 core `121ea7f`/PR #272 + Turnip BO lock fix；kernel marker audit `119a6740…`：DitingWifi 19 / ath11k 846 / MHI 34 / QMI 6 / PCIe 62 / wcn6855 38 / mhi_ring 17 / `cmd written tcs` 1 / Diting touch 11 / goodix 44 / IOGPUFamily 7 / SCANOUT 1 / diting_ramoops 12 / Diting pwrkey 4 / PSCI SYSTEM_OFF 1，设备轮按这些字符串匹配），静态检查 PASS，`hardware_tested=false`；`diting-addon31-rails.img`（`73767046933f825d0a93d939e5ce42c65bcc6c9e6091d75be2969d7c2247fb1e`，WiFi `diting_wifi=2`）、`diting-addon31-link.img`（`cb291a2d353995dfec3efe34741737b54e6c51bcf493bfe7d00e83876693cdef`，`diting_wifi=4`）、`diting-addon31-full.img`（`67208eeb8ef67fbe295956ed3607011fe9aa778ca90c3da5e40c78474d490d81`，full） |
| ADT 官方路径候选 | `image-candidate-release-v4-cpus1.img`（`9bf5ea50…`；ADT `4ac18849…` 15,352 B，CRC `0xda0f09a9`）与旧 ADT 对照 `image-candidate-oldadt-release-v4-cpus1.img`（`47e6b744…`；ADT `cdc7b8cc…`，CRC `0x2f129509`）；两者 args/manifest/kernel `ddccc812…`/addon `8ea462a3…`/layout 一致，仅 ADT 与 payload FAT/CRC 不同；gates contract/storage/single-core PASS；**未合并为默认**，binary-patch 路径仍是默认 |
| 分支状态 | diting-ci `main` @ `f853d0d` + `dev` @ `2d6d0c2`；核心 fork `main` @ `377f0ff` + `dev` @ `121ea7f`（= `fd2f4d1` + `feat/adt-arm-io` + upstream `9931232`）；旧 `sync/*` 与 feature 分支已归档/删除；`dev` 未合入 `main` |
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
- ADT 官方路径候选/A-B：`build-work/evidence-20261116-adt-gen/README.md` §14–15、`ab-compare.json`、`merge-checklist.md`（合并门槛与回滚）
- 仓库记录：`AGENTS.md` 的 2026-11-15/16 各条

## 当前阻塞（真机日志定位，非推断）

| 阻塞 | 现象 | 已确认 / 待确认 |
| --- | --- | --- |
| Wi-Fi | 首笔 smpe2 RPMh 投票 `0x40508=7` 在 PCIe 训练前超时，未扫描 | 阶段分析（`evidence-20261116-wifi-stage/README.md` `065f12fd…`）：addon18c（旧内核）止于 W1——「RPMh response timeout; transaction retained」→「rail vote hi failed」→ 优雅停止。轨表 = `DitingWifiInputs.h` `kDitingWifiRails` 九项：smpe2 1012mV/`0x49e`、smpb11 966/`0x1b9`、smpb10 1800/`0x1b6`、smpc1 1900/`0x29b`、smpb12 1350/`0x1bc`、ldoe7 2800/PPID 0、smpe3 2200/`0x4a1`、ldoc10 1200/PPID 0、ldob5 880/PPID 0。addon19（TCS1 镜像 `102fd293…`）所有投票 `committed`，按顺序 **六条轨** smpe2/smpb11/smpb10/smpc1/smpb12/ldoe7 到 `physical ready`（smpe2 PPID `0x49e` 1012mV status=0x8f；smpb10 status=0x9f、smpc1 0x9f、smpb12 0x97），ldoc10/ldob5 无 PPID 按设计跳过；随后 smpe3 电压 `43400=2200` committed、enable `43404=1` 停在「triggered, polling」（日志结束，无 PCIe0）→ **六条已过、第七个（smpe3）是 stall 点**；`rpmh-tcs0` patch（`TCS(reg)=rsc+0xd00+reg`，替代 TCS4 sleep slot）已在当前 series 与 addon26+ 内核，首次 addon26/30 启动即测试 |
| ADSP / 电量 | ADSP 到 stage 6，stage 7 `0x30030=7` 超时（-60） | 未到 PAS 加载与电池服务发布 |
| UI 帧率 | 桌面可用但帧间隔不稳、卡顿 | Metal pipeline 编译未摊销（插件已内嵌 `__DATA,__primelist`）+ shader cache 不落盘；addon27 起 telemetry 增加 `V cache h/m/w/q/rf/wf/ev` 与 `V drv l/h/m/s/tr/mm/un`，并可开 `log-gpu=1` 的 `Diting Metal pass` 有界行；addon28 进一步用上游 Turnip 0016（shader-share）/0017（retired-BO sweep）重建，并新增 `diting_gpu_cache_dir` 与 `C cache dir=… shared=… writable=…` 行；addon30 在合并 core `121ea7f`（PR #272）上重建，Turnip `6001cadb…` 含 BO free under-lock fix（预期减少 address-0 提交与尾抖动），待上机与 addon29 对照 T/PR/H/ctc/V/C；**primelist 已修正**：原 10 行构建主机列表有 6 条路径在 OS 卷不存在（`UIKitCore`/`CoreMaterial`/`CorePDF`/`CoreChartSwift`/`MetalPerformanceShaders`/`MetalPerformanceShadersGraph` 的 `default.metallib`），真实 OS 卷 167 个 `.metallib`；addon31 起改用 `scripts/gen-diting-prime-list.py` 从镜像生成（167 路径/13,172 B/`0ca614ac…`，plugin `f8cb839b…`，`--verify` 逐条 stat 通过） |
| 关机 | 长按电源不能关机 | 内核无 poweroff 路径；下一候选内核含 PSCI SYSTEM_OFF 长按补丁（`Diting pwrkey … SYSTEM_OFF`） |

**未达成、不得声称可用**：Wi-Fi 扫描/关联/DHCP、电量与充电状态、Metal 逐应用兼容性与稳定帧率、
音频（live DT 为双 CS35L41，未接入）、休眠唤醒、按键关机。

## 下一轮验收

按顺序只记录第一个失败阶段，不跳步、不猜测。

1. **addon31 三阶段（rails → link → full；addon30 fallback）**：RAM-only 依次启动同一 addon31 的三个 args 变体（kernel `0c1a2c1f…`、
   bridge `2a4ef86d…`、turnip `6001cadb…`、plugin `f8cb839b…` 含 167 路径 primelist、addon `735fbc6d…` 均相同，只有 `diting_wifi` 不同）：
   - `diting-addon31-rails.img`（`73767046…`，`diting_wifi=2`）：只到 WLAN rails 投票/物理就绪、无 GCC/PCIe 写；看 `WiFi worker armed stage=2`、
     六条 PPID 轨 + `smpe3` 的 `rail … physical ready`、`staged stop at 2:`——直接回答 W1 的 smpe3 stall 是否消失。
   - `diting-addon31-link.img`（`cb291a2d…`，`diting_wifi=4`）：轨 + PCIe0 link trained（pre-ATU/endpoint）；看 `DitingWifi: PCIe0 ELBI=… link=… PHY=… LTSSM=…`、
     `training attempt=… target=Gen…`、`staged stop at 4:`。
   - `diting-addon31-full.img`（`67208eeb…`，`diting_wifi=1`）：完整路径；看 SMMU `program status=…`、MHI/QMI、`ath11k start failed=0`、扫描/关联；
     同时采集 addon30 的 GPU 观测项（`[gpu slow]`、`T pipeline`、`PR resumed`、`H frame-enc`、`ctc`、`V cache`、`V drv`、`C cache dir`）。
   任一步异常/桌面回归时回 addon30（`a2158d7a…`，kernel `0c1a2c1f…`）作同 kernel 对照；addon26 继续用于 pwrkey/PSCI SYSTEM_OFF。
2. **ADT 官方路径 A/B（未合并前不设默认）**：RAM-only 先启 `image-candidate-release-v4-cpus1.img`（`9bf5ea50…`，ADT `4ac18849…`），
   再启 `image-candidate-oldadt-release-v4-cpus1.img`（`47e6b744…`，ADT `cdc7b8cc…`）作对照；两镜像除 ADT/payload CRC 外逐项相同。
   记录：无 AppleARMCPU panic/IOKit 匹配回归、桌面/触摸、`/cpus`（单 CPU、无 `/psci`、cpu0 `cluster-type`）、`/chosen/memory-map` 的 `GpuAddon` 区间、
   ufshc 的 `reg/reg-names/interrupts` 是否被 NativeUfs 误用。通过后才按 `merge-checklist.md` 先 core `feat/adt-arm-io` → diting-ci `fix/adt-gen` → 切默认并删 binary-patch 路径。
3. **Wi-Fi**：W1 判据 = 五条轨（smpb10/smpc1/smpb12/ldoe7/smpe3）全部 `cmd written tcs=1` → `committed` → `physical ready`；
   任一 `RPMh response timeout`/`rail vote hi failed` 或 poll 无 `physical ready` 即停在 W1，保留最后 40 行与 `triggered, polling` 状态。
   之后：PCIe0 `ELBI/link/PHY/LTSSM` → `training attempt=… target=Gen…` → SMMU/MSI → MHI/QMI → ath11k → station/MAC →
   系统设置扫描 → 关联 → DHCP。仍超时时比较 TCS1 的触发控制、命令状态、idle 与 IRQ_STATUS。
4. **电量 / ADSP**：越过 stage 7 → PAS → DSP ready → GLINK → `PMIC_RTR_ADSP_APPS` →
   `DitingBattery: physical battery power source published` → 桌面状态栏与插拔跟随。
5. **GPU 流畅度**：primelist 已内嵌且改为从真实 OS 镜像生成（167 路径，`0ca614ac…`）；下一步补 shader-cache 持久化并回归 CP/fence、Vulkan 设备、
   实际 scanout 与提交完成；用帧间隔/`frame-enc`/`ctc` 统计判断改善。
6. **触摸延迟**：release 内核纳入 touch-latency instrumentation，采集 THP 帧间隔与 IRQ 唤醒率后再调优。

上机约束：只 `fastboot boot`（RAM-only），不写分区；使用 `D:\ai\diting\build-work` 最终镜像，启动前
从最终镜像回读内核并逐字节比对。

## 维护规则

- 新结论先写 `AGENTS.md`（输入/命令/观察/结论/下一步），再同步本文件；`host-build` 与 `device` 证据分开记。
- 继承自 Pong 的 `porting.toml` / `migration/ipados18/` 记录只作实现参照，见 [`PROVENANCE.md`](PROVENANCE.md)。
- 原厂固件、Apple 资产、unique-chip-id 等只留本地，不进仓库。
