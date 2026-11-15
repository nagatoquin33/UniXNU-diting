# UniXNU-diting

Redmi K50 至尊版（`diting` / Qualcomm SM8475）的 UniXNU 格式 2 设备仓库。目标系统为
**iPadOS 18.7.10（22H374）/ Darwin 24.6.0**，系统输入为 iPad7,11 / J171AP。

- 核心构建工具：[UniXNU](https://github.com/UniXNU/UniXNU)
- 固件：仓库内 `platform-firmware/ditingPkg` 的 FDF 内嵌 `sm8475-xiaomi-diting.dtb`；外部 `uefi-diting` 开发树只作参考
- 官方说明：[仓库迁移](https://unixnu.com/zh/porting/migration)、[设备仓库](https://unixnu.com/zh/porting/device-repository)、
  [驱动适配](https://unixnu.com/zh/porting/drivers)、[启动验证顺序](https://unixnu.com/zh/porting/bring-up)、
  [日志抓取](https://unixnu.com/zh/porting/log-capture)
- 本设备：[格式 2 配置](migration/format2/README.zh.md)、[系统迁移](migration/ipados18/README.zh.md)、
  [结构化移植记录](porting.toml)、[AGENTS.md](AGENTS.md)、[当前状态](docs/STATUS.md)、[来源说明](docs/PROVENANCE.md)

## 当前状态（2026-11-15）

**已在 Diting 真机观察到的结果**（逐条见 `AGENTS.md` 与 `docs/STATUS.md`）：

- **桌面**：addon16（cpus=1、Wi-Fi 关闭）进入 iPadOS 桌面并稳定运行；addon16-full / addon17（cpus=8）同样进入桌面。
- **Metal / GPU**：addon16-full 有 Vulkan-backed 设备、3 条实际 `GPU scanout copy completed status=0`、10240 submits / 10239 completed；addon17 为 9216 / 9215。逐应用兼容性与帧率未验收。
- **触摸**：Goodix GT9916（Berlin-D，SPI 0x990000）已通电、握手并产生 digitizer 事件，**可用但异常卡顿**（2026-11-14），THP 主机触点处理仍在调优。
- **插件与持久化**：六件 GPU addon 分块同步写入、Data 同步后重命名并挂载；重启后 Recovery 回读 `written=0 same=6 failed=0`，Extensions stage/status=5/0。
- **启动参数**：PID 1 `exec /sbin/launchd` 的 EFAULT 已由独立 scratch 页修复，addon16 起不再复现。

**当前阻塞**（真机日志定位，非推断）：

- **Wi-Fi**：addon16-full / addon17 在 PCIe 训练前，第一笔 smpe2 高位设置 `0x40508=7` 报 RPMh response timeout，未进入扫描。原厂 DT 的活动 TCS 为 TCS0–2，TCS4 是休眠槽；addon18 已将共享请求改为 TCS1，**已构建、未上机**。
- **电量 / ADSP**：addon17 写入原厂签名 ADSP 后，ADSP 走到 stage 6，stage 7 的共享 RPMh `0x30030=7` 同样超时（-60），尚未到 PAS 加载或电池服务发布。
- 当前设备停在临时 Recovery；下一版为 `D:\ai\diting\build-work\diting-addon18.img`，退路为已验证的 `diting-addon16-full.img`。

**未达成、不得声称可用**：Wi-Fi 扫描/关联/DHCP、电量与充电状态、Metal 逐应用兼容性与性能、音频（live DT 为双 CS35L41，尚未接入）、休眠唤醒。

## 组件与来源

`drivers/` 是社区 SM8475 实现（A730 / QCA6490 / SM8475 UFS 等）的 vendored 副本，源自
Chengdong-Yu 的 `pong-*` 仓库（曾以 submodule 引用，现为仓内普通目录，无 `.gitmodules`），本设备复用其板级代码。组件 ID 保持 `DitingPlatform24` 以保留来源、ABI 与验证记录；不要把它标成上游 A740/WCN7850 实现。

**来源纪律**：`porting.toml` 与 `migration/ipados18/` 中的部分记录继承自 Pong（Nothing Phone 2，同 SM8475）真机历史，例如 TFA9873 音频、铃声与部分 Wi-Fi/存储结论。它们可以作为实现参照，**不是 Diting 的验证证据**；Diting 的当前结论以 `AGENTS.md` 的实机条目和 `docs/STATUS.md` 为准。详见 [docs/PROVENANCE.md](docs/PROVENANCE.md)。

## 构建

需要 Python 3.12、dtc、匹配的 22H374 restore/ABI 输入和板级私有固件。源版本由 `feeds.toml`、`unixnu.lock` 和迁移记录固定。

- **内核与启动镜像**：Linux 上用 `scripts/linux/` + `xnu-linux-toolchain` 构建（ld64 为硬依赖，xcodebuild/iPhoneOS SDK 不是）；Xcode 仅 OS 窗口内容一次性制备需要。
- **ADT**：只对已验证 ADT 做二进制补丁（注入 goodix 配置/坐标等），**不要重新生成 ADT**；重新生成会破坏内存拓扑并触发 AppleARMCPU panic。
- **预链接**：必须使用 `kits/NativePrelink/emit_prelink.py` 的 `emit()`（`__PRELINK_INFO` 在组件区之上），并保证 `IOGPUFamily` 等 Metal 依赖以 library-only 入库；否则会在 Metal 发布时跳到零填充地址。
- **最终镜像**：以 Windows `D:\ai\diting\build-work\diting-addon*.img` 为准；不要直接启动构建目录里的同名中间镜像，启动前从最终镜像回读内核并逐字节比对。
- **CI**：`.github/workflows/package.yml`（仅 `workflow_dispatch`）在 macOS runner 上做可选打包；本地 Linux 链路不需要它。

三个卷 UUID 是内核常量，换 userdata 必须重编内核；占位 UUID 的构建只能用于编译验证，不能上机。

## 源码边界

仓库只包含板级源码、补丁、配置和脚本。IPSW、Apple 私有二进制、固件、认证数据、userdata 和构建产物不进入仓库，由脚本在本机获取或生成。原厂 ADSP/固件只保留本地，不提交、不推送。设备级代码采用 BSD-2-Clause-Patent；导入组件保留原始许可证及 SPDX 标记，见 [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md)。

## 免责声明与商标

- 本项目是非官方、独立的硬件适配研究，与 Apple Inc.、小米、高通无隶属、授权或背书关系；相关商标归各自所有者。
- 操作涉及 userdata 分区 LBA 划窗、自建 UEFI 引导与内核替换，可能造成数据丢失或设备无法启动；请先备份，风险由使用者自行承担。
- 仓库不包含、也不分发 Apple 还原镜像、厂商固件或提取后的二进制；这些内容由使用者在自有设备或本地环境获取。
