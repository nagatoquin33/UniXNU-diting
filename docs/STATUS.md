# Diting 当前状态（2026-11-15）

- 设备：Redmi K50 至尊版 `diting`，Qualcomm SM8475，bootloader 已解锁
- 目标系统：iPadOS 18.7.10 / 22H374 / Darwin 24.6.0（XNU 11417.140.69）
- 本文件只写**已在 Diting 真机上观察到的结果**与**已知阻塞**；逐条原始记录在 [`AGENTS.md`](../AGENTS.md)。
  继承自 Pong 的记录不算 Diting 证据，来源规则见 [`PROVENANCE.md`](PROVENANCE.md)。

## 当前设备与镜像

| 项 | 状态 |
| --- | --- |
| 设备 | 停在临时 Recovery（ADB 可用）；上一轮已回读 addon17 日志与 APFS |
| 下一版镜像 | `D:\ai\diting\build-work\diting-addon18.img`（已构建、预链接、打包，并从最终镜像回读确认含 TCS1 修复内核、七文件 GPU/ADSP addon、cpus=8、`diting_wifi=1`、`diting_metal=1`、`diting_adsp=2`；**未上机**） |
| 已验证退路 | `D:\ai\diting\build-work\diting-addon16-full.img`（八核进桌面；Wi-Fi/电池仍有已知阻塞） |
| 交接文档 | `D:\ai\diting\交接-2026-11-15-addon18-八核-Metal-WiFi-电量.md` |
| 代码备份 | `/home/nagatoquin/unixnu/backups/diting-ci-before-rpmh-slot-20261115` |

## 已实机证实

| 项目 | 结果 |
| --- | --- |
| 桌面 | addon16（cpus=1、Wi-Fi 关闭）进入 iPadOS 桌面并稳定运行；addon16-full / addon17（cpus=8）同样进入桌面 |
| 八核 | addon16-full 的 CPU0–7 均报 `first boot completed`；SpringBoard 正常运行 |
| Metal / GPU | addon16-full：真实 Vulkan-backed 设备、3 条实际 `GPU scanout copy completed status=0`、10240 submits / 10239 completed；addon17：9216 / 9215。**逐应用兼容性与帧率未验收** |
| 触摸 | Goodix GT9916（Berlin-D，SPI `0x990000`）已通电、握手并产生 digitizer 事件；**可用但异常卡顿**（2026-11-14），THP 主机触点处理仍在调优 |
| 插件 / 持久化 | 六件 GPU addon 分块同步写入、Data 同步后重命名并挂载；重启后 Recovery 回读 `written=0 same=6 failed=0`，Extensions stage/status = 5/0 |
| launchd | PID 1 `exec /sbin/launchd` 的 EFAULT 已由独立 scratch 页修复，addon16 起不再复现 |
| 存储 | UFS 的 SHNGROOT v1 三窗口（OS/SystemOS/Data）在 Diting 上完成 launchd 与用户态启动；addon16+ 进桌面 |

## 证据路径

- ramoops 原始日志（Diting 真机，Recovery 只读回读）：
  - `D:\ai\diting\build-work\ramoops-addon16.bin`（单核桌面、六文件落盘、ADSP 缺件）
  - `D:\ai\diting\build-work\ramoops-addon16-full.bin`（八核 + Metal + 首次 Wi-Fi RPMh 超时）
  - `D:\ai\diting\build-work\ramoops-addon17.bin`（ADSP 由缺件推进到供电请求阶段；Wi-Fi 同样超时）
- 交接：`D:\ai\diting\交接-2026-11-15-addon18-八核-Metal-WiFi-电量.md`
- 仓库记录：`AGENTS.md` 的 2026-11-15 各条（addon13–addon18、GPU addon 安装、launchd EFAULT、RPMh 活动槽修复）
- 相关补丁：`patches/xnu-ipados18/zzzzzzzzzzzzzzzzzzzz-diting-gpu-addon-durability.patch`、
  `...z-diting-launchd-scratch.patch`、触摸系列 `...diting-touch-*.patch`；驱动侧 `drivers/DitingPower/`、`drivers/DitingWifi/`、`drivers/DitingAdreno/`

## 当前阻塞（真机日志定位，非推断）

| 阻塞 | 现象 | 已确认 / 待确认 |
| --- | --- | --- |
| Wi-Fi | addon16-full / addon17 在 PCIe 训练前，第一笔 smpe2 高位设置 `0x40508=7` 报 RPMh response timeout，未进入扫描 | 原厂 DT 的活动 TCS 为 TCS0–2，TCS4 是休眠槽；addon18 已将共享请求改为 TCS1（寄存器偏移 `0xfa0`、IRQ bit `0x2`），**已构建、未上机** |
| ADSP / 电量 | addon17 写入原厂签名 ADSP 后，ADSP 走到 stage 6，stage 7 的共享 RPMh `0x30030=7` 超时（-60） | 尚未到 PAS 加载与电池服务发布；驱动已改用本机 carveout `0x9fd00000 + 0x03100000` 并保留 PAS 验签 |
| 触摸卡顿 | 可用但异常卡顿 | THP 主机触点处理/中断配置仍在调优；四类验收（静止不滚动、按中图标、连续拖动、正确抬起）未做 |

**未达成、不得声称可用**：Wi-Fi 扫描/关联/DHCP、电量与充电状态、Metal 逐应用兼容性与性能、音频
（live DT 为双 CS35L41，尚未接入）、休眠唤醒。

## addon18 验收阶梯

按顺序只记录第一个失败阶段，不跳步、不猜测。

1. **Wi-Fi**（从 smpe2 开始）：RPMh committed → 物理电源跟随 → PCIe 链路 → SMMU/MSI → MHI/QMI →
   station/真实 MAC → 系统设置扫描 → 关联 → DHCP 与网络。
   若仍超时：比较 TCS1 的触发控制、命令状态、idle 与 `IRQ_STATUS`，并对照已实测工作的 Goodix TCS0 路径；
   若已过供电：只沿第一个失败阶段查。
2. **电量 / ADSP**：ADSP 越过 stage 7 → PAS 导入 → DSP ready → GLINK → `PMIC_RTR_ADSP_APPS` →
   `DitingBattery: physical battery power source published` → 桌面状态栏与插拔充电跟随实际状态。
   若到 GLINK 仍无电量：按原厂 DT 的 charger protection domain（`tms/servreg`、`msm/adsp/charger_pd`）结合日志查服务。
3. **Metal 回归**：GPU CP/fence → 用户态 Vulkan 设备 → 实际 scanout → 提交完成。
   失败时区分：未走 GPU、已走 GPU 但 retirement 慢、上层服务（相机等）反复退出；保留 addon16-full / addon17 已测结果作为基线。

上机约束：只 `fastboot boot`（RAM-only），不写分区；用户在场；镜像用 Windows `D:\ai\diting\build-work` 最终版，
不要直接启动构建目录里的同名中间镜像；启动前从最终镜像回读内核并逐字节比对。

## 维护规则

- 新结论先写 `AGENTS.md`（输入/命令/观察/结论/下一步），再同步本文件；`host-build` 与 `device` 证据分开记。
- 继承自 Pong 的 `porting.toml` / `migration/ipados18/` 记录只作实现参照，见 [`PROVENANCE.md`](PROVENANCE.md)。
- 原厂固件、Apple 资产、unique-chip-id 等只留本地，不进仓库。
