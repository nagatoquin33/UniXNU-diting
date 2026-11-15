# Diting 当前状态（2026-11-15 晚）

- 设备：Redmi K50 至尊版 `diting`，Qualcomm SM8475，bootloader 已解锁
- 目标系统：iPadOS 18.7.10 / 22H374 / Darwin 24.6.0（XNU 11417.140.69）
- 本文件只写**已在 Diting 真机上观察到的结果**与**已知阻塞**；逐条原始记录在 [`AGENTS.md`](../AGENTS.md)。
  继承自 Pong 的记录不算 Diting 证据，来源规则见 [`PROVENANCE.md`](PROVENANCE.md)。

## 当前设备与镜像

| 项 | 状态 |
| --- | --- |
| 设备 | TWRP recovery（RAM-only，ADB 可用）；`boot_a` 未被改动 |
| 当前装置 OS | 11-11 userdata 重刷装入的是 **Pong 时代布局**：`/pong/init` `a80747bb…` = `/sbin/launchd`，`/pong/libpong-ui18.dylib` 174,960 B `28d133d0…`，`/diting` 不存在 —— 这是触摸 UI 收不到事件的直接原因 |
| 恢复基线 | `D:\ai\diting\build-work\diting-addon18.img`（进桌面、Metal 已测）；已验证退路 `diting-addon16-full.img` |
| 下一版候选 | OS：`artifacts/ci-42987806310/diting-ipados18-system.cdr`（Diting 布局，6,845,104,128 B `27c507c8…`）；userdata：`out/userdata/userdata-root.img`（11-09 干净原件，19,411,238,912 B）；内核/诊断见阻塞表 |
| 交接文档 | `D:\ai\diting\交接-2026-11-15-addon18-八核-Metal-WiFi-电量.md` |
| 代码备份 | `/home/nagatoquin/unixnu/backups/diting-ci-before-rpmh-slot-20261115` |

## 已实机证实

| 项目 | 结果 |
| --- | --- |
| 桌面 | addon16（cpus=1、Wi-Fi 关闭）进入 iPadOS 桌面并稳定运行；addon16-full / addon17（cpus=8）同样进入桌面；addon18c 正常重启后仍到桌面 |
| 八核 | addon16-full 的 CPU0–7 均报 `first boot completed`；SpringBoard / backboardd 正常运行 |
| Metal / GPU | addon16-full：真实 Vulkan-backed 设备、3 条实际 `GPU scanout copy completed status=0`、10240 submits / 10239 completed；addon17：9216 / 9215。**逐应用兼容性与帧率未验收** |
| 触摸（内核侧） | addon18c ramoops：`Diting touch: DT ok`、`BERLIN`/`9916`、GENI-DMA 6.4 MHz、IRQ240 GPIO21、`finger 0 at 5084, 23812` ×4，无 touch failure —— **驱动→内核链路正常** |
| 触摸（UI 侧） | 当前 Pong 布局 OS 的 `libpong-ui18` 只有 IOHID 路径且 9 类入口全部 `unavailable … SKIP`，**UI 收不到触摸事件**；11-14 报告的“可用但卡顿”是重刷前状态，不能拿来代表当前装置 |
| 插件 / 持久化 | 六/七件 GPU+ADSP addon 分块同步写入、Data 同步后重命名并挂载；Recovery 回读 `written=0 same=6/7 failed=0`，Extensions stage/status = 5/0；`/ngpu/firmware/adsp.mbn` 23,380,392 B 在盘 |
| launchd | PID 1 `exec /sbin/launchd` 的 EFAULT 已由独立 scratch 页修复，addon16 起不再复现 |
| 存储 | UFS 的 SHNGROOT v1 三窗口（OS/SystemOS/Data）在 Diting 上完成 launchd 与用户态启动；addon16+ 进桌面 |

## 证据路径

- ramoops（Diting 真机，Recovery 只读回读）：`ramoops-addon16.bin`、`ramoops-addon16-full.bin`、
  `ramoops-addon17.bin`、**`ramoops-addon18c.bin`**（触摸内核事件 + update 页）、`ramoops-addon23.bin`
  （与 addon18c 逐字节相同，sha256 `e93d1fa1…`）；均在 `D:\ai\diting\build-work\`
- 崩溃：`build-work/crash-softwareupdated-latest.ips`；OS UI 库：`build-work/os1111-libpong-ui18.dylib`
- 设备轮次：`build-work/device-runs/2026-11-15-addon22/`（addon18c 分析、addon23 运行、Data/OS 只读检查、OS 兼容性矩阵）
- GPU：`build-work/evidence-20261115-gpu-framerate/README.md`；触摸延迟：`build-work/evidence-20261115-touch-lag/README.md`
- 仓库记录：`AGENTS.md` 的 2026-11-15 各条；交接文档 `D:\ai\diting\交接-2026-11-15-addon18-八核-Metal-WiFi-电量.md`

## 当前阻塞（真机日志定位，非推断）

| 阻塞 | 现象 | 已确认 / 待确认 |
| --- | --- | --- |
| 触摸 UI | 内核有 finger 事件，UI 收不到 | **OS 布局不匹配**：当前是 Pong OS（IOHID 全 SKIP）；候选 Diting OS cdr 有 `/dev/diting-touch`。写 6.8 GB OS 窗口需用户对那一次明确授权 |
| 更新完成页 | 屏幕停在“软件更新已完成”，点 Continue 不前进 | `softwareupdated` 反复 SIGSEGV（`EXC_BAD_ACCESS` at 0x20，main+1612，`consecutiveCrashCount=2`）；状态文件 `softwareupdateservicesd.state` 15,204 B。换 Diting OS 后是否仍出现未观察 |
| Wi-Fi | addon16-full / addon17 在 PCIe 训练前 `0x40508=7` RPMh timeout，未扫描 | 活动 TCS 为 TCS0–2、TCS4 是休眠槽；addon18 改 TCS1 已构建未上机 |
| ADSP / 电量 | addon17 写入原厂签名 ADSP 后 stage 6 ok、stage 7 `0x30030=7` 超时（-60） | 未到 PAS 加载与电池服务发布 |
| GPU 流畅度 | 120 Hz 下掉帧、卡顿 | plugin 无 `--prime-list`、cache `wr0`、`default.metallib InvalidFile`；修复顺序：primelist → cache 持久化 → encode/GPU |
| 诊断通道 | addon22/23 的 CDC console 均为阴性；addon23 ramoops 未更新 | `9b8e4c6b` 内核不写 UFS ramoops；后续诊断镜像改用 `03b90020`/`e991983d` 系内核或先修 CDC |

**未达成、不得声称可用**：触摸 UI 事件消费（OS 布局）、更新完成页（softwareupdated 崩溃）、Wi-Fi 扫描/关联/DHCP、
电量与充电状态、Metal 逐应用兼容性与性能、GPU 流畅度（primelist）、音频（live DT 为双 CS35L41，未接入）、
休眠唤醒、USB CDC console。

## addon18 验收阶梯

按顺序只记录第一个失败阶段，不跳步、不猜测。

1. **OS / 触摸**：把 OS 窗口换成 Diting 布局（`ci-42987806310/diting-ipados18-system.cdr`，或 11-09 干净
   `userdata-root.img`）→ 回读确认 `/diting` 存在、`/pong` 缺失、`libditing-ui18.dylib` 174,976 B →
   上机确认 `display-integrated digitizer opened` 与 UI 触摸；更新完成页是否还出现同样观察。
2. **Wi-Fi**（从 smpe2 开始）：RPMh committed → 物理电源 → PCIe → SMMU/MSI → MHI/QMI → station/MAC →
   系统设置扫描 → 关联 → DHCP。仍超时时比较 TCS1 的触发控制、命令状态、idle 与 IRQ_STATUS。
3. **电量 / ADSP**：ADSP 越过 stage 7 → PAS → DSP ready → GLINK → `PMIC_RTR_ADSP_APPS` →
   `DitingBattery: physical battery power source published` → 桌面状态栏与插拔跟随。
4. **Metal 回归**：GPU CP/fence → Vulkan 设备 → 实际 scanout → 提交完成；随后按 GPU memo 修 primelist
   （`build-diting-metal-plugin.py --prime-list`、bundle 含 `.primelist`、`PR functions resumed>0`）与 cache 持久化。
5. **诊断**：每次启动默认带诊断参数（`diting_usb=1`/`ufslog`/`ramoops_ufs`），但只有 `03b90020`/`e991983d`
   系内核会写 UFS ramoops；若仍无 CDC，用 Recovery 只读回读 4 MiB 尾部并确认与上一轮不同。

上机约束：只 `fastboot boot`（RAM-only），不写分区；用户在场；镜像用 Windows `D:\ai\diting\build-work` 最终版，
启动前从最终镜像回读内核并逐字节比对；任何 OS/userdata 写入都要用户对那一次明确授权。

## 维护规则

- 新结论先写 `AGENTS.md`（输入/命令/观察/结论/下一步），再同步本文件；`host-build` 与 `device` 证据分开记。
- 继承自 Pong 的 `porting.toml` / `migration/ipados18/` 记录只作实现参照，见 [`PROVENANCE.md`](PROVENANCE.md)。
- 当前装置 OS 是 Pong 布局这一事实，属于设备状态而非来源记录；改用 Diting 布局后要同步更新本节与 `AGENTS.md`。
- 原厂固件、Apple 资产、unique-chip-id 等只留本地，不进仓库。
