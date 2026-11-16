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
- 工作内核钉版：**`121ea7f11afc3bbeb5d56336ab1550fba3ddf228`**（核心 fork `dev`，merge upstream `9931232fd68b8ae1db0abd957ecba417f1996e52`/PR #272；在 diting-ci `dev` `2d6d0c2` 上 kernel exit 0、kernel `0c1a2c1f…` 73,781,248 B、26 entries 含 IOGPU、construct bytes `fd7bbfa9…21320094`、storage/porting PASS）。**条件**：仅 build-verified；addon30 重建与设备启动、以及 diting-ci `main`（`f853d0d`）在该 core 上的复验仍待完成；上一 pin `fd2f4d1` 是 `dev` 的祖先，回滚只需改 pin。核心 fork 只保留 `main` `377f0ff` 与 `dev` `121ea7f`；首次干净构建前需清理 diting-ci 的 4 个过期 refer 软链（见 [`core-provenance.json`](../core-provenance.json) 的 `prerequisite_refer_cleanup`）。
- 同步原则：先 fetch 阅读上游变更（文档、契约、组件），再决定是否 bump 钉版；不向上游推送。

## 6. 分支策略（2026-11-16 起）

单人维护的仓库只保留两条长期分支，功能分支短命、合并后立即删除；远端只有 `main` 与 `dev`。

| 分支 | 角色 | 规则 |
| --- | --- | --- |
| `main` | 稳定/已验证 | 只接受已通过对应验证（构建、离线门禁、真机或 CI 证据）的变更；文档与证据随代码一起提交；不直接在其上开发长任务 |
| `dev` | 集成分支 | 功能/移植分支先合入 `dev`，完成单变量验证后再合入 `main`；合并消息记录来源分支与验证结论 |

工作方式：

1. 功能分支从 `dev`（或紧急修复从 `main`）切出，命名短描述（`fix/…`、`port/…`、`ci/…`），寿命以一次验证为限。
2. 合并进 `dev` 后删除本地与远端功能分支；`dev` 仅保留未验证或未上机的集成内容。
3. 通过验证后把 `dev` 合入 `main`（或把已验证提交 cherry-pick 到 `main`），并在 `AGENTS.md`/`docs/STATUS.md` 记录证据。
4. 不进 `main` 的内容（如未上机的 ADT 官方路径、experimental GPU 变体）在 `dev` 中保持可复现，并在文档中标注“未合并/待验证”。
5. 不建长期 personal/backup 分支；回退点用 commit/tag 记录，已合并或已废弃的分支删除。

当前状态（2026-11-16 整理后）：

- diting-ci：`main` @ `1b83f44`（稳定）、`dev` @ `03cb8b7`（集成；= main + `fix/adt-gen` + 分支策略文档）。
- 核心 fork（`nagatoquin33/UniXNU`）：`main` @ `377f0ff`、`dev` @ `97e6c92`（= `fd2f4d1` + `feat/adt-arm-io` `8968f72`）；旧 `sync/*` 与 feature 分支已归档/删除，验证 pin 仍为 `fd2f4d1`（`dev` 的祖先）。
- `dev` 已包含 `fix/adt-gen`（`ed18043`，含 `port/official-prelink` `5b4df48`）与官方 ADT 路径改动；核心 `feat/adt-arm-io` 已合入核心 `dev`，尚待设备 A/B 后再按 `merge-checklist.md` 并入 diting-ci `main`。
- 已删除的远端分支：`fix/adt-gen`、`port/official-prelink`、`no-stall`（`12a8596`，未包含在 dev）、`ci/systemos-union`（`9628bd4`，未包含在 dev）、`ci/eacces-applog-fix`（`be630b9e`，已在 dev 历史中）。删除前 heads 记录于 `AGENTS.md`。
- `dev` 未合入 `main`；`main` 的默认 ADT 路径仍是旧 binary-patch，直到设备 A/B 验证通过。
