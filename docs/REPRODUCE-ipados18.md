# Diting iPadOS 18.7.10 复现记录

本阶段使用 UniXNU 核心 `0ce9779c2aa7c4f85fdc7f7610bcd0cfc2fde8e2`、`diting_ipados18_defconfig` 与 42_02_0a 面板。见 [实机状态](STATUS.md)。

## 输入与构建

1. 准备 iPad7,11 / J171AP 的 22H374 还原组件和原始内核缓存、Diting 实物对应的板级固件、平台种子与目标的卷布局。输入的版本和补丁顺序见 `feeds.toml`、`unixnu.lock`、`patches/xnu-ipados18/series`。实机卷 UUID 用 `scripts/read-ufs-window-apfs.py` 在 TWRP 中读取。现有系统与重建内核的 OS、SystemOS、Data UUID 必须匹配。
2. 用 [diting-userdata 工作流](../.github/workflows/diting-userdata.yml)，或按其中参数在 macOS 运行 `scripts/prepare-diting-userland-from-ipsw.py`，制备匹配的 OS 窗口。保留现有 Data 时只部署需要更新的窗口。
3. 用 [package 工作流](../.github/workflows/package.yml) 构建完整启动镜像，手动选 `ipados-18.7.10-22H374` 和 `diting_ipados18_defconfig`。流程记录了固件版本、板级输入、IOGPUFamily 预链接、八核 ADT、UFS 描述和自包含 Android boot v4 封装。核对工作流里的卷 UUID 是否匹配目标设备。

## WSL 内核及打包

使用同一核心 pin 和 `xnu-linux-toolchain`。设置 `DITING_KERNELCACHE`、`UNIXNU_KERNELCACHE`、`DITING_ADRENO_FIRMWARE`、`DITING_WIFI_SOURCE`、`DITING_WIFI_FIRMWARE`、`DITING_VOLUME_LAYOUT`。使用工作流的板级 DTB 配方和本机的 Wi‑Fi 及共享驱动输入，让 `diting_native_inputs` 解析依赖。

~~~sh
./unixnu defconfig diting_ipados18_defconfig -D "$device_repo" --out "$out"
# 在生成的 .config 中按实际布局填入 OWNER_ROOT、OWNER_CACHE 和 OWNER_DATA 卷 UUID。
./unixnu build kernel -D "$device_repo" --out "$out"
~~~

用 `scripts/build-release-image-linux.py` 中的 `prelink_release_kernel(..., iogpu=True)` 处理 `device-tree/build/xnu/ios-obj/DEVELOPMENT_ARM64_DITING/mach.development.diting`。根列表和 slide 从 `board.toml` 读取。正式显示镜像沿用已上机 v3 的 Android v4 头、固件槽和 PONGFAT1 尺寸。用 `mcopy -o` 只替换 FAT 内的 `/EFI/UniXNU/Payloads/kernel.macho`，更新 PONGFAT1 头偏移 24 的 32 位小端 CRC32（对 FAT 内容计算）。复核 FAT 成员集合及其余成员哈希一致。缺少参考封装时可用完整打包流程重建。

~~~sh
python3 scripts/precheck-workflow.py
python3 scripts/check-storage-bindings.py "$kernel"
python3 scripts/check-loader-adt-contract.py "$boot_image"
git diff --check
~~~

## 保留现有 Data 的扩容

1. 在 TWRP 确认 userdata 未挂载，回读当前 SHNGROOT 和整个 Data 外窗。校验备份及卷 UUID。
2. 在工作副本增大外层 GPT 磁盘，运行 `sgdisk -e` 移动备用表，同时保留旧 APFS 分区范围。到 macOS 或断网的本地 macOS Recovery，用 `diskutil apfs resizeContainer <store> 0` 扩原容器，再用 `diskutil verifyVolume <volume>` 校验，并核对 GPT、原 UUID 和重要用户文件。
3. 本次实机 userdata 240,092,426,240 B，Data 起点 `0x285000000`。尾部留 1 GiB 后，Data 外窗长 228,197,380,096 B，最后 4 MiB 继续供 `diting_data_reserve=4` 的 ramoops 使用。回写只涉及 Data 新增区间和差异块，读回后再写 SHNGROOT，扩容前后核对 OS 和 SystemOS 的全窗哈希。

保留正式启动镜像、一个 v3 回退镜像、恢复镜像、原 Data 备份和实机日志。XNU 对象、CI 解包树、统一日志解析全文、临时 APFS 副本与恢复虚拟机均可按配方重建。平台种子、私有固件、还原资产与实际用户数据留在本地。
