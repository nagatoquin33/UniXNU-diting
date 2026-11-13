# NativeUfs

SM8475 UFS 主控制器传输层与 SMMU takeover：只发只读存储命令，为 XNU 提供根卷传输。

## 适配硬件

- SM8475 UFS host：`0x01d84000`、长度 `0x3000`，GCC UFS 页 `0x187000`
- SMMU stream ID `0xe0`，UFS 中断 SPI 265
- 根布局只接受 SHNGROOT v1，强制 OS / SystemOS / Data 三个窗口，块大小 512、flags 1
- UFS 设备树节点可通过 `unixnu,userdata-first-lba` 和 `unixnu,userdata-last-lba` 提供 4 KiB 扇区范围；两项必须同时提供并与实际 GPT 一致。未提供时使用 Diting 原有范围。

## 仓库关系

Diting 专属实现，上游没有对应组件（`UniXNU/ShengUfs` 是 SM8550 的另一套）。

## 说明

- `RootLayout.h` 决定只读根卷布局；`SmmuTakeover.h` 与 `DitingPower`、`DitingUsb`、`DitingWifi` 共用。
- `NativeUfs.cpp`、`DitingUfsTransport.cpp` include `../DitingProbe.h`，该头由 UniXNU-diting 的 `drivers/` 提供，独立 clone 时缺失。

构建、接口与组件目录见 [UniXNU 组件目录](https://unixnu.com/reference/components)，板级输入与编译入口在 [UniXNU-diting](https://github.com/Chengdong-Yu/UniXNU-pong)。

## 实现细节

### 文件

- `NativeUfs.cpp`：`IOService` 前端。映射 GCC UFS 页与 host 寄存器窗口，取得 SMMU stream ID `0xe0`，注册 UFS 中断，然后交给传输层。
- `DitingUfsTransport.cpp`：`diting_ufs_transport_start` 的板级实现，负责时钟、PHY 与设备初始化序列。
- `RootLayout.h`：userdata 里 SHNGROOT v1 的解析器，包含 LUN 0 GPT 与根镜像清单，强制 OS / SystemOS / Data 三窗口。
- `RootQueue.h`、`RootCommands.h`、`TransferPoll.h`、`RootTransportLayout.h`：队列接管、命令路径、单槽完成策略与 UCD/PRDT/DMA 布局；宿主故障注入工装复用同一份代码，只替换 MMIO 与同步原语。
- `RootDiagnostics.h`：被动快照格式化，不做任何信任或发布判断。
- `SmmuTakeover.h`：从 UEFI 接过 SMMU 的上下文编程，DitingPower、DitingUsb、DitingWifi 共用。
- `DitingStore.h`：持久化 store 窗口。`diting_data_persist` boot-arg 为 0（默认）时关闭；1 表示只读恢复，2 表示读写持久化（同时需要 `diting_ufs_readwrite=1`）。窗口取 userdata 分区末尾、`diting_data_reserve`（MiB，默认 0）保留区之下，且不得与 SHNGROOT 镜像及其 4 MiB 保护区重叠。对外导出 `native_ufs_store_mode/open/read/write/sync/gpt_check`（`extern "C"`，供 NativeRamBlock 弱引用）；写路径复用 WRITE(10) FUA。

## 许可

`LICENSE` 为 BSD-2-Clause-Patent。每个源文件的 SPDX 声明为准。
