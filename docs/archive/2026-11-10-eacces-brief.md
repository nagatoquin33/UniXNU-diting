> 归档：2026-11-10 的 EACCES 问题快照，已过时。当前状态见 [`docs/STATUS.md`](../STATUS.md)，
> 来源边界见 [`docs/PROVENANCE.md`](../PROVENANCE.md)。

# iPadOS 18 移植：EACCES 问题同步摘要（2026-11-10）

## 1. 目标与栈

- 设备：红米 K50 至尊版（codename `diting`），SoC SM8475，bootloader 已解锁。
- 目标系统：iPadOS 18.7.10 / 22H374，内核 Darwin 24.6.0（XNU 由源码 + 补丁构建）。
- 项目：UniXNU（https://unixnu.com，仓库 https://github.com/UniXNU）。
- 启动链：`fastboot boot diting-unixnu-uefi.img` → 自建 UEFI（ditingPkg）→ UniXNU 菜单 →
  DarwinBoot（ExitBootServices、构建页表、跳转 XNU）→ XNU。
- 构建：GitHub Actions（macOS runner）编译 XNU，约 20–25 分钟一轮；本机无法编内核。
- 观察手段：屏幕上的内核控制台（会滚动，`printf` 可见）；真机每次 `fastboot boot` 后只能由人手动重启。

## 2. 存储布局（已实机验证）

userdata 分区 `/dev/block/sda37`，4 KiB 逻辑块，容量 240,092,426,240 B，起始 LBA 0x2F8A00。
分区开头是 SHNGROOT 清单（4096 B，版本 1，含每个窗口的 offset/size/sha256），后面三个窗口：

| 窗口 | 偏移 | 大小 | 内容 | 卷 UUID |
| --- | --- | --- | --- | --- |
| OS | 0x100000 | 6,845,104,128 | 原始 APFS 容器（iPadOS 系统卷） | b07df049-7ad9-47b5-9f8f-9ee728056398 |
| SystemOS | 0x198100000 | 3,963,617,280 | 原始 SystemOS cryptex 容器 | 4a77ba00-2826-44c4-b883-1fa92ac36880 |
| Data | 0x285000000 | 8,589,934,592 | GPT + 单 APFS 分区（`EFI PART`@512, `NXSB`@分区+32） | 337cf716-f62b-446b-b959-4a5f12a7701c |

镜像总长 19,411,238,912 B，用 Android sparse 编码在 bootloader 里刷入（25 个 chunk，494 s）。

驱动：自研 `drivers/NativeUfs`（源自 Diting 的 NativeUfs），每窗口发布一个 512 字节逻辑块的
IOBlockStorageDevice/IOMedia；Data 窗口只有在块设备 `DitingWritable` 且 IOMedia 可写时才被接受
（`DitingUfsTransport.cpp:392-395`）。

## 3. 当前状态（关键）

已经达成：

- 根卷按 UUID 匹配并挂载：`DITING_UFS: OS root binding UUID b07df049-… bound to OS UFS window /dev/disk2s1`
  之后 `DITING: APFS: diting`；
- 内核走正常 `load_init_program` 路径执行 `/sbin/launchd`，**launchd 正常运行**并在拉起服务；
- `xpcproxy` 能创建进程（日志出现 pid 2045/2062/2063 等），说明从该卷执行程序本身是允许的。

阻塞点：所有被 launchd/xpcproxy 拉起的**目标服务**在 spawn 时返回 `EACCES`，随后 `exit(78)`，
launchd 反复重试，日志一直滚动。

## 4. 实测证据（屏幕日志原文）

```
Service could not initialize: posix_spawn(/usr/libexec/timed)
error 0xd - Permission denied
Initialization failure: 22H374: xpcproxy
xpcproxy exited due to exit(78)
```

同样错误出现在 `/usr/libexec/sharingd`、`/usr/libexec/ptpd`、`/usr/libexec/logd`、
`/usr/libexec/accountsd`、`/usr/libexec/tccd`、
`/System/Library/PrivateFrameworks/CoreDuetContext.framework/Resources/contextstored`。

失败的服务分属 system 域和 user/501 域，说明不是某一个 uid 的问题。

另外反复出现（与 EACCES 的关系未确认）：

```
kpersona_find_by_type() failed with ret -1 errno 3
Unable to find persona with type 4
```

启动早期与存储相关的日志（readwrite=0 那一轮）：

```
DITING APFS: Data prepare emit
DITING APFS: Data UFS window ... timeout=5s
DITING APFS: Data UUID appears valid
DITING APFS: UUID candidate ... accepted
DITING APFS: vwindow media ...
DITING APFS: vwindow UFS Data UUID unavailable
UUID candidate ... accepted=0 window=Data
UUID lookup MISS
writable UFS Data UUID unavailable
scratch Data mount SKIP error=6 step=0        ← error 6 = ENXIO
```

注意：`readwrite=1` 的那一轮，照片里**没有**拍到 Data 是否真的绑定/挂载成功，这一项仍未观测。

## 5. 已排除或已处理的项

- `diting_init_path` 白名单：补丁里 `strcmp(diting_init_path, "/diting/init") != 0` 就 `panic("Unsupported Diting init path")`；
  已把这个启动参数整个删掉，改走原生 `init_programs`，launchd 因此得以运行。
- 根卷 UUID 与 SystemOS UUID 都已实测比对并修正（SystemOS 之前用了错误的旧 UUID，导致等 5 秒超时）。
- Data 卷 UUID 已按 CI 编译进内核的值（337cf716-…）重建窗口；`diting_ufs_readwrite=0 → 1` 已做，
  EACCES 症状未改变（但 Data 挂载结果未观测）。
- 全卷 `noexec` 的可能性低：`xpcproxy` 与失败的服务在同一卷同一目录下，前者能执行。

## 6. 候选成因（需要定位到具体返回值）

1. `exec_check_permissions()` 返回 EACCES（文件模式/uid/gid 不满足）；
2. `mac_vnode_check_exec()` / `vnode_authorize(KAUTH_VNODE_EXECUTE)` 拒绝；
3. 代码签名/信任链：`check_for_signature()`、`mac_proc_check_launch_constraints()`；
4. xpcproxy 的 spawn 属性（sandbox profile / 容器 / entitlements）在缺少 `/private/var` 时被拒；
5. 与 `persona` 缺失相关（日志里的 persona 报错），影响 user/501 域服务的 spawn。

## 7. 我们的内核环境（供分析）

- 内核补丁在 `patches/xnu-ipados18/`（`0001-diting-darwin24.patch` 等），构建时打到 XNU 源码上；
  panic 里出现的 `kern_exec.c:7863` 之类行号是打补丁后的树。
- 当前启动参数（`board.toml` 的 `kernel_args`）：

```
-v keepsyms=1 cpus=1 diting_allow_unauthenticated_root=1 cs_enforcement_disable=1
cs_library_val_enable=0 amfi_get_out_of_my_way=1 -apfs_shared_datavolume debug=0x14e
serial=0 diting_disable_swap=1 diting_skip_setup=1 diting_adsp=2 diting_audio=2 diting_ufs_readwrite=1
ignition_level=1 dyld_flags=0x8 launchd_rd=md0 diting_init_trace=1 applog=1 applog_name=<服务列表>
diting_software_keybag=1 diting_display=1 diting_software_ui=1 diting_ui_software=1 diting_touch=1 diting_buttons=1
diting_build=ipados18-22H374 diting_gpu_scanout=1 diting_gpu_pool_mib=0 diting_metal_global=1
diting_gpu_lock_max=1 diting_usb=1 diting_usb_mux=1 diting_usb_iphone=1 diting_rootful=1
```

- 本地已提交的相关工具：`scripts/dump-diting-adt.py`（解 payload 里的 ADT）、
  `scripts/apfs-volume-uuid.py`（读容器卷 UUID）、`scripts/make-data-window.py`、
  `scripts/make-userdata-image.py`、`scripts/make-sparse-image.py`、`scripts/decode-sparse-image.py`、
  `scripts/flash-userdata-image.py`。

## 8. 希望得到的帮助

请指出：在 Darwin 24（iOS 18）的 `execve`/`posix_spawn` 路径上，**哪些检查会返回 EACCES**，
以及在我们这种「自建块设备 + 未签名/sealed 校验不可用」的根卷上，最可能是哪一处；
并给出**最小侵入的取证方法**（例如在 `exec_check_permissions` / `mac_vnode_check_exec` /
`check_for_signature` / `mac_proc_check_launch_constraints` 里打印 cred、vnode、错误码），
以便一轮构建就能定位到具体返回值，而不是逐个试启动参数。

补充约束：我们不能用调试器；只能靠内核 `printf` 到屏幕；每轮构建约 25 分钟，真机每次启动后需要人工重启。
