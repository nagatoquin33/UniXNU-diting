# 与官方文档的差距审计（2026-11-16）

对照上游 `UniXNU/docs/zh/`（origin/main `03129b6`）逐项检查本项目实现：哪些是官方已有能力、哪些是必要适配、哪些属于自造轮子或弯路。结论：**多数自研点有明确原因，但至少 6 处重复造轮子，4 条弯路**；后续应优先回到官方接口。

## 1. 重复造轮子

| 领域 | 官方能力（文档） | 我们的实现 | 判断与建议 |
| --- | --- | --- | --- |
| GPU 帧诊断 | `gpu-trace=1 gpu-perf=1 diag-export=240`、`log-gpu=1`；板级 `[gpu jobs]/[gpu long]/[gpu slow]/[gpu kick]/[gpu pool views]`、`frames.trace`、`read-sheng-log.py`（`porting/gpu-diagnostics.md`） | 自建 `Diting GPU` 跟踪 ABI、`frameEvent` id、遥测表；靠 TWRP 回读 ramoops | **自造**。官方工具已覆盖"提交前延迟/编码/完成/显示空档"。建议下一轮直接开 `gpu-trace=1 gpu-perf=1 diag-export=240 log-gpu=1` 并接 `read-sheng-log.py`，我们的日志保留为补充 |
| 预链接 | `kits/XnuPrelink/emit_prelink.py` + `[kernel.prelink] roots`（组件及其导入接口）；`concepts/prelink.md` | 自写 NativePrelink emit、手动 IOGPU library-only、改 kit、绕 `__PRELINK_INFO` 位置 | **部分自造**。IOGPU 零填充问题本质是 roots/library-only 契约没走通。建议把 IOGPUFamily + 依赖正式写进 `kernel.prelink.roots`，不再手工注入 |
| payload/启动镜像 | `unixnu payload`/`bootimg`；FAT 布局 `EFI/UniXNU/unixnu.toml`；ADT 由 profile 生成（`concepts/payload.md`） | 自建 PONGFAT1 打包、`build-bootimg` 脚本、对已验证 ADT 做二进制补丁 | **部分自造**。二进制补丁 ADT 是为绕过生成器 bug 的临时手段；应修 profile/DT 输入让 ADT 生成正确，恢复官方打包 |
| userdata | `unixnu build userdata`：SHNGROOT 生成；Linux 端 `scripts/unixnu/udif.py` 解 UDIF（`concepts/userdata.md`） | 自写 SHNGROOT 组装、sparse 编码、dd/fastboot 刷写工具 | **自造**。官方已有 Linux UDIF 解码，"userdata 必须 macOS"的早期判断是错的；建议改用官方 userdata 步骤，sparse 只作为刷写工具保留 |
| 打包脚本 | `scripts/package.sh` 为固定模板，板级只改 `board.toml`（`porting/packaging.md`） | 自建 `build-release-image-linux.py`、`--diagnostics`/`gpu-addon` 注入、`pack-diting-stage.py` | **自造且偏离模板**。建议把差异收敛到 `board.toml`（`[payload.runtime]`/`[payload.install]`），脚本回归模板 |
| GPU addon 输入 | `[payload.runtime] gpu_addon`（`configuration.md`） | 自建 `.gpuaddon` 容器、payload 后 mtools 注入、durability 补丁 | **自造传输层**。传输应交给 `payload.runtime.gpu_addon`；durability 问题属内核挂载逻辑，可单独保留 |
| 日志抓取 | AdvancedLogDxe 导出器 + 内存缓冲 + Linux/recovery reader（`porting/log-capture.md`） | TWRP 尾部 dd + 自制 ramoops 解析 + USB CDC 尝试 | **部分自造**。Advanced Logger 通道已具备，ramoops 仅作补充；CDC 尝试无果应放弃 |
| 触控 | `QcomGeniSpi` + `ShengNovatekTouch` + `ShengHidInput`；板级 `TouchBoard/TouchProbe`（`porting/input.md`） | 自写 goodix 内核驱动 + THP 主机触点 + `/dev/diting-touch` → 用户态 HID 注入 | **自造协议栈**。芯片不同可以自研，但 HID 报告层应参照 `ShengHidInput`（`IOHIDDevice` 报告描述符、同帧快照）；当前 devfs 注入桥在 Pong 布局 OS 上失配，正是自造层带来的耦合 |

## 2. 弯路

1. **以为 Linux 不能做完整链路**：早期结论是 userdata/OS 窗口必须 macOS/CI；官方文档明确 Linux `udif.py` 可解 UDIF，后续本地整链已跑通。
2. **OS 布局错配**：整盘 userdata 写入的 11-09 镜像实际是 Pong 布局（无 `/diting`），导致桌面黑屏/更新页；Diting 布局 OS 才有 `/dev/diting-touch`。
3. **重新生成 ADT**：破坏内存拓扑触发 `AppleARMCPU` panic；官方 ADT 由 profile 生成，正确做法是修输入而不是二进制补丁。
4. **帧率问题顺序反了**：先自定义遥测、primelist、cache 计数和上游 patch，之后才读官方 `gpu-diagnostics`；官方现成的 `gpu-trace`/`[gpu slow]` 能更早定位。
5. **电源/关机**：没有走平台 power 路径，先后用 boot_b TWRP、Settings 关机，最后才补 PSCI SYSTEM_OFF 长按。

## 3. 必要适配（不是轮子）

- **Linux 内核构建/链接垫片**（`xcrun` 包装、`HOST_COMPAT`、clang/flags）：官方以 macOS 为主，Linux 支持有限；这部分属于真实增量。
- **Diting 板级值**（SoC 资源、GPIO、PMIC 轨、ADT token、卷 UUID）：官方只有 SM8550 参考，必须自研。
- **Goodix GT9916 协议与 THP 触点**：官方只有 Novatek 参考，芯片协议差异属必要实现；HID 层仍建议对齐 `ShengHidInput`。
- **addon 持久化/launchd scratch 页**：OS 用户态与内核 ABI 约束下的修复，属板级缺陷修复。

## 4. 建议顺序

1. 用官方 `gpu-trace`/`read-sheng-log.py` 重做一次帧率基线，替换/补充自建遥测。
2. 把 IOGPUFamily 与 payload addon 输入收敛到 `kernel.prelink.roots` / `payload.runtime.gpu_addon`。
3. 修 ADT/DT 输入使 `unixnu payload` 可生成正确 ADT，移除二进制补丁路径。
4. 用户态/触控 HID 层对齐 `ShengHidInput` 模式，去掉 devfs 注入与 OS 布局的耦合。
5. 打包脚本回归 `scripts/package.sh` 模板，板级差异只放 `board.toml`。

> 说明：本文是工程审计，不改变已验证镜像；任何迁移都按单变量上机验证。

## 5. 打包对齐进度（2026-11-16）

- `scripts/package.sh` 与上游模板逐字节相同：sha256 `f7b8e3ea043058b9c61d5b45c32b8e7669a85737c89d55d404957c3b43ec4aab`（`UniXNU/templates/package.sh`）。板级只应改 `board.toml`。
- 官方 `--check` 通过（合并 core `fd2f4d1`，`--no-deps`）：`== step deps / preflight / patches`，28 个补丁顺序解析、defconfig `diting_ipados18_defconfig`、OS `ipados-18.7.10-22H374`（证据 `build-work/evidence-20261116-package-align/check-nodeps.log`）。
- 官方 `--no-deps` 首次失败在 **kernel 步**（不是 package.sh）：设备配方 `kits/DitingPlatform24/build-ipados18-diting-macos.py:121` 默认读取 macOS 机器路径
  `/Volumes/DitingDev/build/Diting-iPadOS18-inputs/volume-layout.json`，本机不存在 → `FileNotFoundError`；应在本地输入层提供（`DITING_VOLUME_LAYOUT` / `unixnu.local.toml`），不属 `package.sh` 改动。日志 `release-nodeps*.log`。

### board.toml 对照官方 schema

| 区块/字段 | 当前 | 官方契约 | 处理 |
| --- | --- | --- | --- |
| `[package] unixnu` / `[package.defconfig]` | 有 | `release` 读 checkout 与各 OS defconfig | 保留 |
| `[payload] kernel_args` | 有（39 项 / 805 字符） | 官方 payload 直接读；上限 1000 字节 | 保留；诊断/GPU 参数迁移见下表 |
| `[payload] loader` | 缺（默认 `firmware`） | `firmware` 或驱动加载 | 显式写 `firmware` |
| `[payload.adt] tool` | 缺 | 官方 payload 调 `<tool> --output --dram-size` | 未启用：Diting 生成器 CLI 不同，见下表 |
| `[payload.runtime]` | 缺 | 构建前准备 trust/addon/Data 种子 | 先加 `enabled = false`（与缺省等价），迁移见下表 |
| `[bootimg] dtb` | 有 | 固件 preflight 生成的 DTB | 保留 |
| `[firmware] config/dsc/fd/preflight/patches/submodules/packages` | 有 | 固件构建契约 | 保留（含 `{tree}/drivers/DarwinBoot24`） |
| `os_overrides` | 无 | 多 OS 配置的板级覆盖 | 单 OS 不需要；新增目标时再加 |

### 迁移表（keep / replace / retire）

| 项 | 现状 | 目标 | 决定 | 风险/前置 |
| --- | --- | --- | --- | --- |
| `scripts/package.sh` | 与模板逐字节相同 | 固定模板 | **keep** | 无 |
| `board.toml` 板级输入 | `[package]`/`[bootimg]`/`[firmware]`/`[payload]` | 官方契约 | **keep**（本次显式 `loader`、加入 disabled runtime 钩子） | 无行为变化 |
| `scripts/build-release-image-linux.py` 的诊断/`gpu-addon` 注入 | `--diagnostics` 默认追加 6 个参数并 mtools 注入 addon | `[payload] kernel_args`（诊断）/`[payload.runtime] gpu_addon`（addon） | **replace**（分两步） | 参数从 805→约 950 字符，仍 <1000；改后需单变量上机确认，未验证前保留脚本 |
| `.gpuaddon` 容器 + mtools 注入 + durability 补丁 | 自定义传输层 | `[payload.runtime] gpu_addon = true` + 上游 runtime builder | **replace**（依赖 runtime 工具支持 Diting 用户态/信任模块） | 无 Diting runtime tool 前不可切 |
| `scripts/finalize-diting-adt.py` | 生成 ADT/manifest 并写 v4 容器 | 官方 `[payload.adt] tool` + `[bootimg]` pack | **replace**（先对齐 CLI；v4 容器仍需 core 支持） | 官方 pack 只写 v0–v2 头；v4 由固件要求，需 core/脚本变更 → 报告后再动 |
| `scripts/pack-diting-stage.py` / addon 打包脚本 | 自定义 staging | 官方 build/pack 步骤 | **retire**（与 finalize/runtime 迁移同步） | 排序依赖，放在最后 |
| `patches/xnu-ipados18` + `drivers/Diting*` | 板级必要适配 | 保留 | **keep** | 与打包无关 |

### 需要先报告的 functional 变更（本次不编辑 scripts）

1. `kits/DitingPlatform24/build-ipados18-diting-macos.py` 的 `--volume-layout` 默认是 macOS 机器路径，应改为本地输入（env/`unixnu.local.toml`）而不是脚本默认。
2. `[payload.adt] tool` 的 CLI 与官方 `--output/--dram-size` 不一致；切换官方 payload 步前需要生成器适配，且 v4 boot 容器需要 core 的 bootimg 支持（官方模板只写 v0–v2）。
3. `[payload.runtime]` 需要 Diting 的 runtime tool 才能替换自定义 addon/trust 路径。

> 结论：`package.sh` 与板级 principal 输入已对齐；真正的差异集中在**设备配方默认值**、**ADT 生成器 CLI**、**v4 容器**和**runtime/addon 生成器**四处，全部需要功能性改动，先报告再实施。本轮只记录对齐结果，不改变已验证镜像。
