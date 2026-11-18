# Diting 当前状态（2026-11-18）

- 设备：Redmi K50 至尊版 `diting`（串号 `9e0c2b55`），Qualcomm SM8475，bootloader 已解锁，无 EDL/firehose 救砖文件
- 目标系统：iPadOS 18.7.10 / 22H374 / Darwin 24.6.0（XNU 11417.140.69）
- 本文件只写已在 Diting 真机上观察到的结果与已知阻塞；逐条原始记录在 [`AGENTS.md`](../AGENTS.md)，详细交接与复制矩阵见 `D:\ai\diting\交接-2026-11-18-真机进展与接续.md` 与 `D:\ai\diting\build-work\evidence-20261117-copy-plan\PLAN.md`。
  继承自 Pong 的记录不算 Diting 证据，来源规则见 [`PROVENANCE.md`](PROVENANCE.md)。

## 当前设备与镜像

| 项 | 值 |
| --- | --- |
| 启动镜像 | `boot_a` = `diting-release-20261117.img`（`0d938372…`，只换 9 组件 library-only 预链接内核 `6aae196e…`，保留 addon18 的 loader/ADT/args/7 文件插件，**已真机进桌面**）；`boot_b` = `diting-recovery-boot.img`（TWRP `67cf2dc9…`，恢复与 ramoops 回读用）；active slot=`a` |
| core 钉版 | `nagatoquin33/UniXNU` 单分支 `main`（含 `121ea7f` 与 CI 钉版 `0ce9779`） |
| 设备现役 OS / userdata | Diting 布局（`ci-42987806310` `diting-ipados18-system.cdr` `27c507c8…`）：卷 UUID `B07DF049…`；SystemOS `4A77BA00…`；Data 窗口 8 GiB（UUID `337CF716…`） |
| 待刷入的新 OS 窗口 | CI `diting-userdata` run `44203238062`（`bd5d0f1`）产出 `D:\ai\diting\artifacts\ci-44203238062\diting-ipados18-system.cdr`（6,845,104,128 B，sha256 `f07fb252…`，离线 APFS 校验含 `cameracaptured` `JetsamProperties=192`/`ThrottleInterval=30` 与 `libditing-ui18.dylib` `12b5a2c3…` `UIKit.InProcessAnimationManager` 动画钩子；**尚未刷入真机**） |
| 分支状态 | `nagatoquin33/UniXNU-diting` 与 `nagatoquin33/UniXNU` 均已统一收敛为**单分支 `main`**（保留完整提交历史与 GitHub Secrets） |

## 已实机证实（截至 `ramoops-release-20261118.bin` `20628c4b…`）

| 项目 | 结果 |
| --- | --- |
| 桌面与内核稳定性 | `diting-release-20261117.img`（新内核 `6aae196e…`）正常启动进入 iPadOS 18.7.10 桌面，无 panic |
| 触摸 | Goodix GT9916 驱动栈工作正常：`Diting touch latency: reports=1280 irq=1280 spurious=0 polls=10298 read_mean_us=156`，触摸点击与滑动可用 |
| GPU / Metal / Scanout | `DITING ADRENO`（CP_ME_INIT / PAS13 ZAP / CP ready）全部 `result=0`；`IOAcceleratorES` + `NativeAdreno` + `real Vulkan-backed device created status=0x0`；`DITING SCANOUT: GPU frame completed` / `actual GPU scanout copy completed status=0x0`；`[gpu cache] submits=8192 completed=8191` 持续硬件提交 |
| Wi-Fi 扫描 | QCA6490（`DitingWifi`）在真机完成扫描：`scans=5 BSS=44 frames=158`（42 信道扫出 44 个网络），`Preferences` 经 `wifid` 收到扫描结果；日志尚无关联/DHCP（`en0 address none, in/out dhcp 0`） |
| 证据通道 | ramoops（userdata 尾部 4 MiB，TWRP `dd` 回读）；Advanced Logger 菜单镜像；panic 屏 QR 解码器（`scripts/decode-sheng-panic-qr.py`） |

## 当前阻塞与待验项（真机日志定位）

| 项目 | 现象 | 当前状态与下一步 |
| --- | --- | --- |
| 系统卡顿 / 相机服务风暴 | `ramoops-release-20261118.bin` 中 `cameracaptured` 每 5 秒建 128 MiB GPU VA 租约后触及 27 MB 上限被 jetsam 杀掉（共 126 次 `EXC_RESOURCE`）；设备仍装旧 OS 窗口，缺 SpringBoard 动画高刷钩子 | **主机与 CI 产物已就绪**（`bd5d0f1` 接入 `metal_services18.configure`，CI `44203238062` 新 OS 窗口 `f07fb252…` 已离线验过 `JetsamProperties=192`/`ThrottleInterval=30` 与 `InProcessAnimationManager` 钩子）；**待授权写入设备 OS 窗口后真机复测** |
| Wi-Fi 关联 / DHCP | 扫描已通（44 BSS），日志无 `assoc`/`link up`/DHCP | 刷入新 OS 窗口复测设置内输入密码连接与 DHCP；若仍只扫描不关联，按 `UniXNU-zizhan` 关联/DHCP 阶梯单变量排查，不动已进桌面内核 |
| 电池 / ADSP | 用户观察充电图标正常，但 `ramoops` 无 `ADSP` / `AppleSmartBattery` 发布行 | 待真机核对 Settings 电量/健康度并补 `DITING ADSP` / GLINK 阶段日志 |
| CI 内核打包配方 | `package.yml`（run `44084373013`）已绿，但内核仍走旧 5 根 `XnuPrelink` | 后续将 CI 内核步骤对齐至本地已进桌面的 9 组件 library-only 预链接配方 |
| 音频 / 蓝牙 / 相机 / Data 容量 | 均未接入；Data 窗口仍为 8 GiB | 排在 Wi-Fi 联网、桌面流畅度与电池读数真机闭环之后 |

**未达成、不得声称真机已完成**：Wi-Fi 关联/DHCP/联网、电池容量/健康度发布、新 OS 窗口下的桌面高帧率与 `cameracaptured` 止血、音频、蓝牙、相机、休眠唤醒。

## 维护规则

- 严格遵守 `AGENTS.md` 中的 **社区优先与移植铁律（能抄就抄）** 与 **工作方法**。
- 自有仓只维护唯一分支 `main`，可直接 `push` 跑 CI，禁止向上游 `UniXNU/UniXNU` 推送或提 PR。
- 新结论先写 `AGENTS.md`（输入/命令/观察/结论/下一步），再同步本文件；`host-build` 与 `device` 证据分开记。
- 原厂固件、Apple 资产、unique-chip-id 等只留本地或私有加密凭据，不进公开源码树。
