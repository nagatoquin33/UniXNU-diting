# 仓库与产物架构

本文说明 Diting 工程的分层：哪些是源码、哪些是记录、哪些是镜像与证据，以及上游/自有仓库的边界。实时状态见 [STATUS.md](STATUS.md)，来源规则见 [PROVENANCE.md](PROVENANCE.md)。

## 1. 仓库边界

| 仓库 | 归属 | 允许操作 |
| --- | --- | --- |
| `nagatoquin33/UniXNU-diting`（本仓） | 自有 | 提交、推送、发布 |
| UniXNU 主仓（`UniXNU/UniXNU`） | 上游 | 只读同步（fetch/检出参照）；不推送、不提 PR |
| Chengdong-Yu `pong-*` 驱动仓 | 上游社区 | 只读；以 vendored 副本进入 `drivers/`，不向上游提交 |
| Apple 开源 / IPSW 资产 | 第三方 | 只读；按许可证使用，不重新分发 |

规则：未经完全验证的实现只留在自有仓库，不向上游输出。

## 2. 设备仓分层

| 路径 | 角色 | 说明 |
| --- | --- | --- |
| `board.toml` `feeds.toml` `unixnu.lock` `porting.toml` | 设备声明 | 板级配置、源码钉版、结构化移植记录 |
| `configs/` `dts/` | 板级配置与设备树 | defconfig、DTS |
| `drivers/` | 板级驱动（vendored） | `ArmCpu`、`ArmDTPlatform`、`NativeUfs`、`DitingPower`、`DitingAdreno`、`DitingMetal`、`DitingWifi`、`DitingUsb`、`DarwinBoot24` 等 |
| `patches/xnu*/` | 内核补丁 | `series` 顺序 + `zz…` 增量补丁；touch、RPMh、launchd、GPU addon、pwrkey 等 |
| `kits/` | 构建组件 | `DitingPlatform24`（板内 kit）、`NativePrelink`/`XnuPrelink` 预链接 |
| `scripts/` | 构建与打包 | Linux 工具链、release v4 镜像、addon 打包、ADT 合约检查 |
| `userland/` | 用户态适配 | init/launchd 包装、touch/按钮 HID、UI 兼容层 |
| `migration/` | 历史记录 | format2 迁移与 ipados18 各轮记录（含 Pong 谱系） |
| `docs/` | 当前文档 | STATUS、ARCHITECTURE、PROVENANCE、IMAGES、USB 日志方案 |
| `AGENTS.md` | 工程日志/规则 | 时间序证据、哈希、阻塞、工作方法 |
| `build-work/`（gitignored） | 本地工作区 | 镜像、ramoops 证据、验证脚本；不进入仓库 |
| `out/`（gitignored） | 构建输出 | 内核、payload、boot、userdata 产物 |

## 3. 镜像与启动链

启动镜像为 Android v4 boot 容器：

- kernel 槽：`gzip(BootShim + UEFI FD) + DTB`；
- ramdisk：PONGFAT1 负载，内含 ADT（`/chosen` 的 manifest 哈希、内存区间、diting token）、manifest、内核与用户态输入；
- 参数：`[payload].kernel_args`（≤1000 B 由 core 检查，含 NUL ≤1023 B），`diting_*` 前缀为本设备开关。

运行镜像分三类：

1. **bring-up / release 内核镜像**（`diting-addon*.img`）：fastboot boot 使用；
2. **Recovery**（`diting-recovery-boot.img`）：只读回读 userdata 尾部 ramoops、APFS 检查；
3. **userdata 整窗镜像**（`userdata-*.sparse.img`）：从 bootloader 写入 `sda37`，含 SHNGROOT + OS/SystemOS/Data 窗口。

镜像清单、哈希与保留策略见 [IMAGES.md](IMAGES.md)。

## 4. 证据与状态

- `AGENTS.md`：按时间追加的实机/构建证据（命令、哈希、日志片段、阻塞与条件）。
- `docs/STATUS.md`：当前已验证状态、证据路径、阻塞、下一步验收阶梯。
- `porting.toml`：结构化移植记录，官方 `porting-record.py check` 校验；`device-verified` 区域必须带 `kind="device"` 证据。
- ramoops：内核 console/诊断环，位于 userdata 尾部 4 MiB；回读脚本 `scripts/extract-ramoops-ufs.py`、`read-ufs-window-apfs.py`。

## 5. 上游同步

- 参照检出：`/home/nagatoquin/unixnu/UniXNU-upstream`（detached，`origin/main`），只读；
- 工作内核钉版：core `0ce9779`（`core-provenance.json`），升级需单独验证；
- 同步原则：先 fetch 阅读上游变更（文档、契约、组件），再决定是否 bump 钉版；不向上游推送。
