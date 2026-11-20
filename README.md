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


## iPadOS 阶段收尾（2026-11-20）

本阶段保留已上机的 **iPadOS 18.7.10 / 22H374** 基线。后续计划评估 iOS 或 macOS 基线。选型和移植结果待定。

| 已实机观察 | 结果 |
| --- | --- |
| 启动和触摸 | 进入桌面，八核已启动，常规点击与滑动可用 |
| Adreno 730 / 显示 | Metal 提交和零拷贝扫描输出已跑通。每个 TE 自动刷新一次后，面板实测 121.2–121.6 Hz，显示锁存平均约 4.0–4.5 ms。主屏明显更流畅，应用合成最高采到 110 fps |
| Wi‑Fi | 已实测可用。设置里的密码输入仍有问题 |
| 存储 | 原 32 GiB Data 在实机扩到 212.53 GiB。保留卷 UUID 和用户数据，OS 与 SystemOS 的全窗哈希一致，尾部保留 1 GiB，最后 4 MiB 继续用于 ramoops |

仍有键盘裁切、Wi‑Fi 密码输入与数字键面切换、残影、音量调节、视频解码和蓝牙问题。原生 USB 缺少固件 DMA 交接和系统 usb-mux 桥接，当前关闭。应用持续 120 fps 及休眠唤醒尚未验收。

详见 [实机状态与证据](docs/STATUS.md) 和 [构建复现](docs/REPRODUCE-ipados18.md)。

## 组件与来源

`drivers/` 是社区 SM8475 实现（A730 / QCA6490 / SM8475 UFS 等）的 vendored 副本，源自
Chengdong-Yu 的 `pong-*` 仓库（曾以 submodule 引用，现为仓内普通目录，无 `.gitmodules`），本设备复用其板级代码。组件 ID 保持 `DitingPlatform24` 以保留来源、ABI 与验证记录；不要把它标成上游 A740/WCN7850 实现。

**来源纪律**：`porting.toml` 与 `migration/ipados18/` 中的部分记录继承自 Pong（Nothing Phone 2，同 SM8475）真机历史，例如 TFA9873 音频、铃声与部分 Wi-Fi/存储结论。它们可以作为实现参照，**不是 Diting 的验证证据**；Diting 的当前结论以 `AGENTS.md` 的实机条目和 `docs/STATUS.md` 为准。详见 [docs/PROVENANCE.md](docs/PROVENANCE.md)。


## 构建

内核可在 Linux / WSL 使用 `xnu-linux-toolchain` 构建。macOS 用于准备 Apple OS 窗口和原生 APFS 操作。CI 将 [OS 窗口准备](.github/workflows/diting-userdata.yml) 与 [固件和启动镜像](.github/workflows/package.yml) 分开，由手动运行触发。

构建需要与 22H374 匹配的还原输入、板级固件和实机卷布局。OS、SystemOS 和 Data 的 UUID 必须与内核配置匹配。构建、验证命令及镜像和中间文件的保留范围见 [复现文档](docs/REPRODUCE-ipados18.md)。

## 源码边界

仓库只包含板级源码、补丁、配置和脚本。IPSW、Apple 私有二进制、固件、认证数据、userdata 和构建产物不进入仓库，由脚本在本机获取或生成。原厂 ADSP/固件只保留本地，不提交、不推送。设备级代码采用 BSD-2-Clause-Patent；导入组件保留原始许可证及 SPDX 标记，见 [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md)。

## 免责声明与商标

- 本项目是非官方、独立的硬件适配研究，与 Apple Inc.、小米、高通无隶属、授权或背书关系；相关商标归各自所有者。
- 操作涉及 userdata 分区 LBA 划窗、自建 UEFI 引导与内核替换，可能造成数据丢失或设备无法启动；请先备份，风险由使用者自行承担。
- 仓库不包含、也不分发 Apple 还原镜像、厂商固件或提取后的二进制；这些内容由使用者在自有设备或本地环境获取。
