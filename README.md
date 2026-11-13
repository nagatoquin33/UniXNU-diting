# UniXNU-diting

Redmi K50 至尊版（`diting` / Qualcomm SM8475）的 UniXNU 格式 2 设备仓库。目标系统为
**iPadOS 18.7.10（22H374）/ Darwin 24.6.0**，系统输入为 iPad7,11 / J171AP。

- 核心构建工具：[UniXNU](https://github.com/UniXNU/UniXNU)
- 固件：仓库内 `platform-firmware/ditingPkg` 的 FDF 内嵌 `sm8475-xiaomi-diting.dtb`；外部 `uefi-diting` 开发树只作参考，其旧 FDF 可能仍内嵌 Nothing Phone (2) 的 DTB
- 官方说明：[仓库迁移](https://unixnu.com/zh/porting/migration)、[设备仓库](https://unixnu.com/zh/porting/device-repository)、
  [驱动适配](https://unixnu.com/zh/porting/drivers)、[启动验证顺序](https://unixnu.com/zh/porting/bring-up)、
  [日志抓取](https://unixnu.com/zh/porting/log-capture)
- 本设备：[格式 2 配置](migration/format2/README.zh.md)、[系统迁移](migration/ipados18/README.zh.md)、
  [结构化移植记录](porting.toml)、[AGENTS.md](AGENTS.md)

## 当前状态（2026-11-13）

- bring-up 第 6 阶段已过：UFS 三窗口（OS / SystemOS / Data）已发布，根卷按 UUID 匹配并挂载，
  `launchd` 已实机启动。
- C1 bring-up 镜像（cpus=1、最小驱动）2026-11-12 实机到达 iOS 主屏（用户读屏确认）；C4 再达主屏
  但触摸未归因。全开镜像仍有确定性内存损坏 panic，按执行计划单变量分轮排查（见 AGENTS.md）。
- 已验证的设备布局（userdata `0x2F8A00..0x3ADF3FA`，4 KiB LBA）：
  OS `0x100000`、SystemOS `0x198100000`、Data `0x285000000`，SHNGROOT v1 清单；
  三个卷 UUID 与内核内嵌的 `XNU_OWNER_*_VOLUME_UUID` 一致。
- 当前停点：准备用户态的 `launchd_cache_loader` 在 restore 模式下以
  `Failed to verify code directory` 退出。按 `migration/ipados18/services.md`（services9）的既有结论，
  启动参数需要 `launchd_unsecure_cache=1`；该参数已写入 `board.toml` 的 `kernel_args`。
- 日志不使用拍屏：固件每次启动读取 `0xA7000000` 的 ramoops 环（`RAMOOPS|`），下一轮启动用
  Advanced Logger 的二维码导出上一轮 XNU console。

## 组件与来源

`drivers/` 是社区 SM8475 实现（A730 / QCA6490 / SM8475 UFS 等）的 vendored 副本，源自
Chengdong-Yu 的 `pong-*` 仓库（曾以 submodule 引用，现为仓内普通目录），本设备复用其板级代码。组件 ID 保持 `DitingPlatform24` 以保留来源、ABI 与验证记录；不要把它标成上游
A740/WCN7850 实现。Diting 的板级配置在 `board.toml`、`dts/diting.dts` 和 `drivers/`。

## 构建

需要 Python 3.12、dtc、匹配的 22H374 restore/ABI 输入和板级私有
固件。源版本由 `feeds.toml`、`unixnu.lock` 和迁移记录固定。内核与启动镜像可用本仓
`scripts/linux/` 工具链 + `xnu-linux-toolchain` 在 Linux 构建（ld64 为硬依赖，xcodebuild/iPhoneOS SDK 不是）；
Xcode 仅 OS 窗口内容一次性制备需要。

CI 使用 `.github/workflows/package.yml`（仅 `workflow_dispatch`），在 macOS runner 上构建
kernel / payload / boot image，产物为 `diting-package` artifact。三个卷 UUID 是内核常量，换 userdata
必须重编内核；占位 UUID 的构建只能用于编译验证，不能上机。

## 源码边界

仓库只包含板级源码、补丁、配置和脚本。IPSW、Apple 私有二进制、固件、认证数据、userdata 和构建
产物不进入仓库，由脚本在本机获取或生成。设备级代码采用 BSD-2-Clause-Patent；导入组件保留原始
许可证及 SPDX 标记，见 [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md)。

## 免责声明与商标

- 本项目是非官方、独立的硬件适配研究，与 Apple Inc.、小米、高通无隶属、授权或背书关系；相关商标归各自所有者。
- 操作涉及 userdata 分区 LBA 划窗、自建 UEFI 引导与内核替换，可能造成数据丢失或设备无法启动；请先备份，风险由使用者自行承担。
- 仓库不包含、也不分发 Apple 还原镜像、厂商固件或提取后的二进制；这些内容由使用者在自有设备或本地环境获取。
