# UniXNU-diting

Redmi K50 至尊版（`diting` / Qualcomm SM8475）的 UniXNU 格式 2 设备仓库。目标系统为
**iPadOS 18.7.10（22H374）/ Darwin 24.6.0**，系统输入为 iPad7,11 / J171AP。

- 核心构建工具：[UniXNU](https://github.com/UniXNU/UniXNU)
- 固件：仓库内 `platform-firmware/ditingPkg` 的 FDF 内嵌 `sm8475-xiaomi-diting.dtb`；外部 `uefi-diting` 开发树只作参考
- 官方说明：[仓库迁移](https://unixnu.com/zh/porting/migration)、[设备仓库](https://unixnu.com/zh/porting/device-repository)、
  [驱动适配](https://unixnu.com/zh/porting/drivers)、[启动验证顺序](https://unixnu.com/zh/porting/bring-up)、
  [日志抓取](https://unixnu.com/zh/porting/log-capture)
- 本设备：[格式 2 配置](migration/format2/README.zh.md)、[系统迁移](migration/ipados18/README.zh.md)、
  [结构化移植记录](porting.toml)、[AGENTS.md](AGENTS.md)、[当前状态](docs/STATUS.md)、[来源说明](docs/PROVENANCE.md)、[架构](docs/ARCHITECTURE.md)、[镜像清单](docs/IMAGES.md)

## 当前状态（2026-11-16）

**已在 Diting 真机观察到的结果**（逐条见 `AGENTS.md` 与 `docs/STATUS.md`）：

- **桌面与触摸**：Diting 布局 OS（`/sbin/launchd` = `/diting/init`，sha256 `95cb7341…`；`libditing-ui18.dylib`
  174,976 B 通过 `/dev/diting-touch` 消费事件）经整盘 userdata sparse 恢复后，addon18 启动到
  iPadOS 18.7.10 桌面，Goodix GT9916 触摸可用（点击、滑动、拖动）。Pong 时代布局（`/pong`、
  `libpong-ui18`）与本机触摸桥不兼容。
- **GPU / Metal 硬件路径**：真机已出现 `DITING ADRENO: CP ready`、两条 `DITING METAL` 行、
  `DITING SCANOUT ... status=0` 与 GPU submits 记录；UI 帧率仍不平滑（见阻塞）。
- **其余已测**：八核 CPU0–7 均 `first boot completed`；六/七件 GPU/ADSP addon 分片同步写入后持久化
  （`written=0 same=6/7`，Extensions stage/status 5/0）；PID 1 `exec /sbin/launchd` 的 EFAULT 已修复。

**当前阻塞**（真机日志定位，非推断）：

- **Wi-Fi**：首笔 smpe2 RPMh 投票 `0x40508=7` 在 PCIe 训练前超时，未进入扫描。
- **电量 / ADSP**：ADSP 到达 stage 6，stage 7 的 `0x30030=7` 超时（-60），尚未发布电池服务。
- **UI 帧率**：Metal pipeline 编译未摊销（插件已改为内嵌 primelist）、shader cache 不落盘，导致卡顿；
  这是下一步 GPU 工作项。
- **关机**：内核当前没有 poweroff 路径，长按电源不能关机；下一候选内核包含 PSCI SYSTEM_OFF 长按补丁。

**待验证镜像**（静态检查 PASS，`hardware_tested=false`）：`diting-addon24-diag.img`
（`54ed270b…`，`e991983d` 内核 + primelist 插件）与 `diting-addon26-diag.img`
（`ee7278b2…`，重建 release 内核含 pwrkey/PSCI SYSTEM_OFF、TCS1、touch-latency、primelist 与 7 文件 addon）。

**未达成、不得声称可用**：Wi-Fi 扫描/关联/DHCP、电量与充电、Metal 逐应用兼容性与稳定帧率、
音频（live DT 为双 CS35L41，尚未接入）、休眠唤醒、按键关机。

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
