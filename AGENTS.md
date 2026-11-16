# Diting probe policy

> 当前状态以 `D:\ai\diting\交接-2026-11-11-准备用户态.md` 为准，执行步骤见 `D:\ai\diting\DeepSeek执行计划-进系统与Diting整理-20261111.md`。下方带日期的段落是历史实机与构建记录。

- Optional probes must record PASS, FAIL, SKIP or RUNNING and return to the normal boot path. Never terminate boot with panic, halt or an unbounded loop to display a probe result.
- On failed prerequisites, log the reason and skip dependent MMIO/DMA work. Do not fabricate successful services, media or hardware resources to keep boot moving.
- Save bounded result snapshots through DitingProbeRecord. The early panic hook must print completed snapshots before the real panic message, without allocating, taking registry locks or accessing hardware.
- Preserve real kernel panic handling and functional invariants. A failed optional probe does not authorize suppressing a genuine fatal kernel error.
- Keep Diting DT/hardware constants specific to SM8475. Refer to Sheng for implementation structure and adapt its SM8550 values before use.
- Prefer temporary fastboot boot for device trials. The user has also authorized entering Android to read partitions and clearing userdata/other required partitions for this port. Use that authorization when a concrete installation step needs it; verify target geometry and keep required boot/firmware backups before destructive writes.
- After completing a build and installing any matching runtime update, temporary fastboot boot is the default authorized next step. A later explicit request to hold a particular image takes precedence. Leave the device running after boot for the user's observations.

# Local build preference

- The user explicitly requested skipping image hashes, image audits and device image readback verification. Use `--skip-image-verification` for kernel/boot builds and the default non-verifying Diting userland workflow. Do not run verification or benchmarks unless the user asks.
- Keep generated candidates and runtime artifacts under `/Volumes/DitingDev/build/servicesNN`, logs/install receipts under `/Volumes/DitingDev/logs/diting/servicesNN`, and temporary task scripts under `/Volumes/DitingDev/tmp/servicesNN`. Never write these into the user's Downloads directory.
- The user requested deleting superseded temporary candidates and logs. Retain current deployment metadata and required compiler/firmware inputs; retire the previous candidate after the replacement is deployed. Keep original project sources and user scripts.
- For system updates, the user requests changed parts only. Refresh the unmounted guest OS with `scripts/sync-diting-os-for-update.py` before local edits, then use begin/stage/finish and install changed bands. Keep REC quiescent until the update is installed so guest filesystem changes are preserved. Do not blindly overlay old host APFS metadata after a guest boot.
- DarwinBoot24 and the selected XNU boot_args ABI have a 1024-byte command-line array, including the NUL terminator. Keep the assembled ASCII boot command at most 1023 bytes. Shorten optional log filters instead of changing the ABI or silently truncating functional boot arguments.

# Repository layout

- This is the Diting SM8475 format 2 device repository, targeting iPadOS 18.7.10 / 22H374 / Darwin24. Follow https://unixnu.com/zh/porting/migration and https://unixnu.com/zh/porting/device-repository.
- Keep the ARM64, SM8475, OS profile and board layers separate. The versioned SM8475 seed is under migration/format2/soc-seed; local overrides belong in ignored local.toml.
- Preserve community component identity DitingPlatform24. Do not label the A730/QCA6490 implementation as the upstream A740/WCN7850 driver.
- Publish source/configuration/porting records only. Apple restore binaries, generated ABI dumps, firmware, userdata, credentials and build artifacts stay local.
- Record host build results separately from device results in porting.toml. A successful build or Fastboot command is not evidence of working Wi-Fi, PCM audio or buttons.
- Keep XNU_DITING_POWER independent of Wi-Fi. Shared RPMh/SMMU locks belong to DitingPlatformResources, and Darwin24 links native4K helpers once through libDitingSmmu4K.a.
- Native public prerequisites are pinned in configs/diting-native-sources.toml. Use scripts/fetch-diting-native-sources.py and ignored local.toml paths; do not reintroduce host volume paths into recipes.

# Diting packaging status (2026-11-06)

- Keep scripts/package.sh identical to the UniXNU template and use device driver submodules. The workflow pins the previously used UniXNU revision and installs the device OS profile and component catalog before packaging.
- The pinned upstream core receives a temporary generic kernel-component patch; board.toml selects DitingPlatform24. The workflow uses the CI configuration, native-only kernel staging and the volume-layout artifact from the specified run. This integration has only local tests, not a successful macOS run. The layout must match the userdata image retained from that run. Do not treat the output as device-tested.
- Diting firmware is a reference, not validated Diting firmware. Record host builds and hardware results separately.
- The Diting firmware FDF separately embeds `Platforms/Nothing/ditingPkg/FdtBlob/sm8475-nothing-diting.dtb`; it identifies Nothing Phone (2), regardless of the Diting DTB generated for the boot image. Do not claim that the firmware itself carries a Diting tree.
- Diting's firmware region at 0xA7100000–0xA7400000 overlaps the Diting ramoops reservation at 0xA7000000–0xA7400000. Diting firmware is not a Diting boot candidate, even if it compiles; derive and validate a Diting memory map before device testing.
- `uefi-mondrian-reference` is an independent Xiaomi SM8475 firmware reference, not a Diting port. Its documented UEFI menu result does not establish XNU boot; its DarwinBoot targets Darwin 22, while this project targets Darwin 24.
- The reconstructed Diting DTS retains incomplete board resources and an unverified RAM declaration. `dtc` success is not evidence that the original DTBO, UEFI tree, memory map or peripherals are correctly adapted.

# Diting Wi-Fi 构建进展（2026-11-07）

- Actions 运行 42350648631 的内层日志显示，所用 Sheng main 引入了与设备清单不同的 Ath12kWifi，31 个编译单元因此找不到 `linux/kconfig.h`；Linux 稀疏检出还缺少 MHI 和 QMI 源码。
- `scripts/prepare-ci-wifi.py` 根据 `configs/diting-native-sources.toml` 固定 Linux、Sheng 和 Ath12kWifi，检查 ath11k、MHI、QMI、shim 及头文件。工作流先独立编译 Wi-Fi，再进入较耗时的内核构建；检查日志会随失败产物上传。
- 使用清单中的 Linux 和 Ath12kWifi 固定版本，本机 Linux 交叉编译已生成 arm64 Mach-O 对象及 `libDitingAth11k.a`。macOS/Xcode、内核最终链接、固件加载和 Diting 真机 Wi-Fi 仍需分别验证。
- 这是本地未提交修改；在 33 授权提交推送前，远端 Actions 不会使用这些改动。请勿把编译归档或占位卷布局当成设备功能证据。

# Diting 实机 panic 与构建检查（2026-11-08）

- 33 的照片显示 XNU 已进入 IOKit。greenA 内核 PC 0xfffffff00793ef74 对应 OSMetaClass::postModLoad，访问的 FAR 为 0xfffffff00da591e0，恰好等于 IOBlockStorageDevice::gMetaClass 符号 0xfffffff00da591d0 加 0x10；该地址不属于 greenA Mach-O 的任何映射段。
- 存储绑定由 prepare-ipados18-storage.py 根据 22H374 内核和固定 prelink 基址 0xfffffff00b000000 生成，board.toml 当前 slide 为 -0x1000000；greenA 实际 __PRELINK_TEXT 为 0xfffffff004130000。检查原始输入和 bindings 之前不要盲改 slide，也不要继续把 greenA 用于真机。
- 新增 scripts/check-storage-bindings.py，工作流在 v4 镜像组装前检查最终内核的 IOBlockStorageDevice 绝对符号是否落在映射段，方法地址另检查可执行权限。greenA 实测报 9 个不匹配，内存中模拟已映射符号的正向检查通过；这只是静态范围检查，不证明类结构、映射或启动成功。尚未提交或运行 CI。
- 另需修复 greenA 内核内 Diting ramoops 的 0x85200000 地址和 Diting 实机 0xa7000000 保留区不一致，并核对与固件区间的冲突及 pstore 格式。未经核实不要将保留区改成任意地址。
- 2026-11-08：根据 greenA 已映射段和旧配置反推的 22H374 起始地址，候选 slide 设为 0x5ed0000，使预链接基址对齐存储绑定的 0xfffffff00b000000；Diting 两份配置暂时关闭 Diting 固定物理地址的 ramoops；实际 payload 启用 -v，manifest 从 payload 配置读取相同参数。提交 43e14aa 已推送并启动 Actions 42404848268；CI、生成映射和真机启动均待验证。
- Action 42404848268 在内核链接失败：关闭 ramoops 后 kern_exit.o 仍引用 diting_ramoops_diagnostic_write。提交 92b3ef7 将诊断入口和调用按同一构建开关编译，并把宏传入 kern_exit.o；两种开关状态的预处理检查通过。新 Action 42407447526 已启动，尚未通过 CI 或上机。
- Action 42407447526（92b3ef7）成功：内核以 0x5ed0000 预链接，9 个存储绝对绑定落入映射段，实际 boot args 含 -v；Wi-Fi 仅通过预编译。尚未在 Diting 测试该镜像。后续提交 7fa0fb9 只处理 ramoops 开关切换后的增量对象失效，未被本轮 CI 覆盖。
- 33 要求刷入后，Action 42407447526 的镜像已写入 Diting 的 boot_b（Fastboot 写入 OKAY）；当前活动槽仍为 a。随后同一镜像经 fastboot boot 临时启动，命令返回 OKAY；OS 实际状态未确认，暂未发现 ADB 或串口。未通过 Fastboot 写入 boot_a 或 userdata。
- 33 随后提供的实机画面显示 corecrypto/pthread 的入口范围校验失败，接着 `IOPlatformExpertDevice::generatePlatformUUID` 调用 `sha1_init`，空指针访问 0x28 导致 panic。对 CI 42407447526 内核分析发现组件 Mach-O 的入口落在组件代码段，但父内核的 `__PRELINK_INFO` 结束地址低于这些组件；Darwin 24 将其用作静态地址上界，`ml_static_slide` 可能将高地址段清零，解释范围校验失败，需用下一轮实机验证。不要通过跳过 OSKext 检查掩盖。
- 手机重启回 Android 后，ADB root 直接检查 `/sys/fs/pstore`，目录为空；Android 实际 ramoops 参数为基址 0xa7000000、总长 0x400000、console 与 pmsg 各 0x200000、ECC 和 record_size 均为 0。该轮 XNU 因先前禁用写入器不能回读其日志。当前修改正使用设备配置为 Diting 传递该基址，并修复预链接信息位置；构建和设备日志回读尚待验证。
- Action 42411722700（6d1299b）通过并已临时启动，33 报告出现内核文字或 panic；随后 Android pstore 为空。内核反汇编确认日志地址 0xa7000000。向 Android `/dev/pmsg0` 写入短标记并正常重启后，pstore 仍为空；Android dropbox 未找到记录，原因未确认，不能把持久日志回读标为成功。该轮没有覆盖 boot_b。
- 33 明确允许清空 userdata 安装；但必须等匹配的 22H374 OS、SystemOS、Data 完整就绪、恢复写入环境可用、Diting UFS 和实际几何经过核对后才执行，不能提前擦除。当前 Android `/data` 为 F2FS，实测 userdata 4K 首 LBA 0x2f8a00、末 LBA 0x3adf3fa。
- CPU 诊断镜像越过 AppleARMCPU，现停在 Failed to mount root device。其 ADT 缺少 ufshc；当前 Diting UFS 固定使用另一机型的 userdata 几何，且设备尚未安装 SHNGROOT/APFS。Diting UFS 几何适配在独立 fork 准备中，OS、SystemOS、Data 不在当前 CI 成品中。
- 557e4f8 的 CPU 匹配修正在 Action 42416561746 通过；同等本地诊断镜像已真机越过 AppleARMCPU，停在根设备挂载。Diting UFS 分区范围适配已在独立仓库 nagatoquin33/diting-ufs 提交 4fe0173（unixnu topic），主仓库 c67bc72 接入该子模块、发布 UFS 节点和实测边界；安装准备期间保留只读。Action 42419087356 验证中，尚未声明 UFS 实机工作。

# Diting bring-up state (2026-11-08)

## Target
- Device: Redmi K50 Ultra `diting`, SM8475 (Cape family), Android 16, bootloader **unlocked**
  (`fastboot getvar unlocked` = yes; the `ro.boot.flash.locked=1` property is spoofed), active slot `_a`.
- Target OS: iPadOS 18.7.10 / 22H374 / Darwin 24, built as `DEVELOPMENT_ARM64_DITING` (MACHINE_CONFIGS=DITING).

## What is proven
- CI `package` runs green end to end: kernel links (`mach.development.diting` ~17.8 MB), payload, three containers.
- Diting's own UEFI (`ditingPkg`, RELEASE, 3,145,728 B `SILICIUM_UEFI.fd`) builds in a Linux job and is packed
  into `boot/diting-unixnu-uefi.img` (kernel slot = gzip(112 B BootShim + FD) + DTB, ramdisk = PONGFAT1 envelope).
- On hardware, `fastboot boot` of that image reaches the UniXNU menu, renders at 1220x2712, finds block IO
  (`blockio=1 volumes=1`) and DarwinBoot returns `HANDOFF EXIT RETURN 0`. The kernel then dies silently.

## Open blockers
1. Kernel death after handoff: no screen output even with `-v debug=0x144`, `/sys/fs/pstore` is empty.
   Next: firmware log via `Tools -> Advanced Logger` (QR, OneSend) and/or a real UART.
2. Wi-Fi: sources compile locally (`libDitingAth11k.a`, 2,981 symbols) but CI stops in
   `build-diting-wifi-native.py` because the build reads `device-tree/build/diting/hardware.dtb`, not
   `DITING_HARDWARE_DTB`. The live tree (`/sys/firmware/fdt`) plus `platform-firmware/dtb-fixups/apply.py`
   provides PCIe/PHY/GPIO; the refgen clock is at `freq[10]` with `clock_names[8]` = `pcie_phy_refgen_clk`.
3. Wi-Fi firmware is checked in under `platform-firmware/wifi/` (amss.bin 5,470,128, amss20.bin 5,296,128,
   m3.bin 266,684, regdb.bin 24,278), pulled from `/vendor/firmware_mnt/image/qca6490` on the device.
   更正（2026-11-13d）：这些 `.bin` 从未提交入仓——`.gitignore:9 *.bin` 一直将其挡在仓外，
   文件只存在于本地磁盘；后续已迁至私有仓 `nagatoquin33/diting-firmware` release fw-20261111（见下）。"checked in" 应读作 "checked into the local workspace"。

## CI notes
- `.github/workflows/package.yml` has two jobs: `firmware` (ubuntu, builds the Diting FD and uploads
  SILICIUM_UEFI.fd + BootShim.bin + mkbootimg.py + diting.toml) and `package` (macos-15-intel, needs firmware).
- Before pushing, run `scripts/precheck-workflow.py` (bash -n on every run block, duplicate env keys,
  and every `--flag` against the script it targets). Both mistakes that broke earlier runs would be caught.
- `DITING_HARDWARE_DTB` is only meaningful for the Wi-Fi step; the kernel still uses the device-tree component's
  `hardware.dtb`.

## Artifacts
- `D:\ai\diting\artifacts\ci-20261107-diting-firmware\diting-unixnu-uefi.img` (first hardware boot, sha ac5aa923).
- `D:\ai\diting\build-work\greenB\...\diting-unixnu-uefi.img` (Tools menu enabled, sha FB2867EE).

- Apple 22H374 的 OS、SystemOS、AppOS 已在 WSL 本地提取/解密并只读挂载，未上传。用户态 helper Action 42458543571 成功，输出在 `D:\ai\diting\build-work\runtime-42458543571`。用户态 APFS 写入仅通过小样文件、属主与权限的独立读取；完整卷及设备均未验证，尚无可刷入的 userdata 成品。

## 2026-11-08 17:2x — Advanced Logger / firmware CDN

- On hardware the menu works, `Tools` is present (payload entry), but `Tools -> Advanced Logger`
  shows `Advanced Logger: no log`.
- Cause: the plugin reads through `AdvancedLoggerAccessLibGetNextFormattedLine`, which does
  `LocateProtocol(gAdvancedLoggerProtocolGuid)`. That protocol is installed by the DXE_CORE
  instance of `AdvancedLoggerLib`, and Mu's stock `Mu_Basecore/MdeModulePkg/Core/Dxe/DxeMain.inf`
  never consumes `AdvancedLoggerLib`, so the buffer is never created.
- Fix in the firmware job: insert `AdvancedLoggerLib` into `[LibraryClasses]` of `DxeMain.inf`
  before `[Guids]`, idempotently, in place (a patch failed because CI checks out Mu_Basecore
  3c9c7b2e, not the workstation revision, and the patch file lost its CRLF).
- Current blocker: the firmware job cannot fetch its external dependencies. Both
  `basetools-v2026080000.0.1.tar.gz` and `OneCrypto-Accelerated.zip` return **HTTP 504** from the
  GitHub release CDN, also from this workstation with curl, so it is an upstream outage, not our
  configuration. Retries (3x) and longer backoff do not help; the build resumes when GitHub serves
  the assets again.



## 2026-11-08 19:1x — ext deps vendored

- Run 42474456806 still died in stuart update with HTTP 504 for the same two assets. From this
  workstation the same URLs returned the real gzip and zip.
- platform-firmware/vendor/ now carries those two upstream archives. seed-ext-deps.py checks the
  sha256 values from Mu ext_dep descriptors and unpacks them into Mu-Basetools_extdep and
  onecrypto-bin_extdep with extdep_state.yaml, so stuart update does not download them.
- The DxeCore AdvancedLoggerLib link has still not been compiled.


## 2026-11-08 19:5x — nested Mu submodules

- Run 42477512954 seeded the ext deps, then Build.py failed: MdePkg.dec include
  Library/MipiSysTLib/mipisyst/library/include is not in the workspace.
- stuart setup skips a dirty submodule. Inserting AdvancedLoggerLib dirties Mu_Basecore
  before setup, so the recursive checkout of mipisyst never runs. The firmware job now
  initializes Mu_Basecore submodules before that edit.

## 2026-11-08 20:3x — logger firmware packaged

- Run 42478126479 on 4570412 is green. The firmware job checked out mipisyst
  370b5944, seeded the vendored ext deps, and linked DxeCore with
  DxeCoreAdvancedLoggerLib. SILICIUM_UEFI.fd is 3145728 bytes, sha256
  b6782ca101d0fd52d55a6e9e40c072ad4af240ac8ae69bbefcddc9b62a9359cb.
- Package artifact images-ipados-18.7.10-22H374. The fastboot candidate
  boot/diting-unixnu-uefi.img is 101109760 bytes, sha256
  e0a4bd1f1d026dadc78346ef8f2fa4467675a11bdedebdaba3bed8d565e6bbe2;
  its fd_sha256 matches that volume. hardware_tested is false.
- check-storage-bindings.py reported 9 storage bindings inside mapped
  segments, with prelink info after the components. Runtime behavior is
  still unchecked.
- No partition was written. Tools -> Advanced Logger is still a device
  observation; this build only creates the DXE logger buffer.

## 2026-11-08 20:4x — temporary boot of the logger image

- fastboot boot of the run 42478126479 image
  diting-unixnu-uefi.img, 101109760 bytes, built from 4570412.
  Host copy:
  D:\ai\diting\artifacts\ci-42478126479\...\boot\diting-unixnu-uefi.img.
- Device 9e0c2b55, product diting, model 22081212C, unlocked yes,
  current slot a. Sending and Booting both returned OKAY.
  No partition was written and the slot was not changed.
- Fifteen seconds later the phone was not in fastboot and not in
  Android adb. The host did not observe the screen. Tools ->
  Advanced Logger is still unread.

## 2026-11-08 20:5x — Advanced Logger was empty

- Temporary boots of run 42478126479 still showed Advanced Logger: no log.
  The menu reads only the Advanced Logger buffer. RELEASE builds pass
  -D MDEPKG_NDEBUG, and DebugLib.h turns DEBUG() into if(FALSE), so the
  buffer stays empty. On-screen DARWINBOOT lines are Print(), which never
  enters that buffer.
- The firmware build now undefines MDEPKG_NDEBUG, keeps DEBUG_ERROR as the
  runtime filter, retries a missed logger LocateProtocol, installs AdvLogDxe
  before DarwinBoot, and mirrors the boot-refused / inputs-validated Prints
  into DEBUG_ERROR.

## 2026-11-08 21:3x — logger fix booted

- Run 42482636331 on 585b305 is green. The firmware log shows the locate
  retry and the DarwinBoot DEBUG_ERROR mirrors, and DarwinBoot.c was
  compiled with -U MDEPKG_NDEBUG after -D MDEPKG_NDEBUG.
- SILICIUM_UEFI.fd sha256
  91554cbc12a1f40d313a52f0c04b6bb17616709f73918780cc5f61a43ffdb9a7,
  3145728 bytes. diting-unixnu-uefi.img is 101191680 bytes, sha256
  d49888c27b41235db026de8beee25844bee2ed00bb785900a309e479635e321e.
- fastboot boot on 9e0c2b55, product diting, unlocked yes, slot a.
  Sending and Booting returned OKAY. No partition was written.
  The Advanced Logger screen for this image was not read from the host.


## 2026-11-09 — the storage path is the wrong driver (documentation audit)

`unixnu.com/zh/porting/ufs`, `/zh/reference/components` and `/drivers/sheng-ufs` state the supported
storage implementation and its integration; the device repository does not follow it yet:

| requirement | documentation | this repository |
| --- | --- | --- |
| driver source | `UniXNU/ShengUfs` vendored at `drivers/ShengUfs` (catalog id `ShengUfs`, revision e2b32cc) | `drivers/NativeUfs`, imported by hand from UniXNU-diting |
| publication module | `RootPublication.h`, `RootWindowRead.h`, `GccUfs.h` | absent |
| boot argument | `native-ufs-root=1` | not used anywhere in the repository |
| component selection | `[components] include` contains `ShengUfs`, kernel links `component:ShengUfs` | `include = ["DitingPlatform24", "XnuPrelink"]` |
| compatible | `qcom,sm8550-ufshc` (board constant to adapt) | Diting constants `diting,ufs-*` |

Bring-up stage list (`/zh/porting/bring-up`) puts us at **stage 6**: the kernel reaches the platform
expert and IOKit, then panics `Failed to mount root device`. Stage 6 requires the block driver to
print link speed and the command queue, publish `OS` and `SystemOS`, and match
`root_match_volume_uuid`. The imported Diting probe driver never publishes root media, so the current
driver cannot pass stage 6 regardless of tuning.

Next: vendor `drivers/ShengUfs` at e2b32cc, add `ShengUfs` to `[components] include`, link its
archive (catalog aliases `build/native-ufs/libNativeUfs.a` to `build/sheng-ufs/libShengUfs.a`), add
`native-ufs-root=1`, and adapt the board constants (diting: controller 0x01d84000, SMMU 0x15000000,
stream 0xe0, SPI 265, UFS compatible `qcom,sm8475-ufshc` — verify against the live FDT).


## 2026-11-09 02:30 — storage experiments (what is actually true now)

- The imported `drivers/NativeUfs` is already adapted for diting: `kGccUfsPage = 0x00187000`,
  `kUfsHost = 0x01d84000`, `kUfsStreamId = 0xe0`, ADT properties `diting,smmu-base = 0x15000000`,
  `diting,smmu-size = 0x100000`, `diting,smmu-context-banks = 78`, `diting,smmu-match-groups = 120`,
  `diting,ufs-spi = 265`. The ADT generator writes the ufshc node with
  `compatible = qcom,sm8475-ufshc\0qcom,sm8450-ufshc\0` (make-diting-adt-ipados18.py:244), which is
  exactly what the driver's `compatible()` accepts, so matching is not the blocker.
- Swapping in the supported ShengUfs component is **not** a board.toml edit: `[kernel]
  builder_component = DitingPlatform24` makes the core skip `build_archives()` entirely, the kit recipe
  rebuilds `drivers/NativeUfs` unconditionally from `DITING_NATIVE_DRIVER_SOURCE` and unlinks any alias,
  and the archive the kernel links is hard-coded at three sites in the **merged** copy
  `kits/DitingPlatform24/build-support/merged-scripts/build-xnu-ipados18.sh` (the repo copy is not what
  runs). A real switch needs a `UFS_DRIVER`/`UFS_ARCHIVE` parameter, a `--driver` option in
  `build-diting-ufs-ipados18-macos.py`, VerifiedRoot/VirtioMmioBlock include paths, and the
  bindings.json producer to keep writing `mac-build/native-ufs/bindings.json` (Adreno platform reads
  it). Until that is done, tune the imported driver.
- `native-ufs-root=1` must **not** be set while the imported driver is used: the core rejects the
  payload with `native UFS root boot needs exactly one sheng-pmgr=2`, and that PMGR personality is
  not part of this board.
- Current experiment (build 1c04458): `diting_ufs_stall=1` in `kernel_args`. On a UFS failure the
  driver logs the `formatUfsRootDiagnostics` block and then holds the CPU (`IOSleep` loop), so the
  last console lines stay on the panel for a photograph. `panic()` cannot be used: it is a macro in
  this SDK and the symbol is not linkable from the archive.

## 2026-11-09 03:20 — device state and what to look for

- The phone was written with `build-work/userdata/userdata-root.img` (SHNGROOT + OS + SystemOS,
  manifest sha f237878b…) over adb (`dd` to `/dev/block/sda37`), verified by reading back the first
  eight bytes. Android's fastboot cannot do this write on this host: the 32-bit fastboot aborts with
  `std::bad_alloc` on a 10 GiB image, and `-S 256M` does not help.
- The image booted is `diting-unixnu-uefi.img` from run 42509554099 (sha256 F2EDDF7F…, 101,191,680 B),
  built from 1c04458. It contains `diting_ufs_stall=1`.
- Expected panel states and what each means:
  * a `DITING_UFS ...` report with gdsc/axi/ahb/cap/ver/hcs/hce lines and the boot stops → the driver
    matched but the transport or the power/clocks gate failed; the values name the failing gate;
  * `DITING_UFS PROBE FAILED: <property> ...` → a board property check failed, the name is the answer;
  * no stall and the root-mount panic returns → the transport succeeded and the failure moved to the
    root volume (UUID or manifest), which is a different problem;
  * the menu again → the payload never handed off.
- The stall build is deliberately sticky: the phone stays as it is until someone reboots it.

## 2026-11-09 03:40 — the ADT the driver receives is correct

Added the reusable `scripts/dump-diting-adt.py` (parses the Apple device tree out of any payload
image without knowing the FAT layout; `--all` lists blobs, `--index` selects one).

`payload.img` from run 42509554099 carries **two** device-tree blobs:

```
[0] 0xc3800   13732 bytes  7 top-level nodes   (arm-io/ufshc has only reg/compatible/interrupts)
[1] 0x3227800 14684 bytes  7 top-level nodes   (the one with the board properties)
```

Blob 1, `/device-tree/arm-io/ufshc`, carries exactly what `drivers/NativeUfs` validates:

```
compatible                qcom,sm8475-ufshc qcom,sm8450-ufshc
diting,ufs-hc-base          0x1d84000
diting,ufs-hc-size          0x3000
diting,gcc-ufs-page         0x187000
diting,smmu-stream-id       0xe0
diting,smmu-base            0x15000000
diting,smmu-size            0x100000
diting,smmu-context-banks   0x4e
diting,smmu-match-groups    0x78
diting,ufs-spi              0x109
unixnu,userdata-first-lba 0x2f8a00
unixnu,userdata-last-lba  0x3adf3fa
```

So matching and every board-property check pass; the remaining suspects are the GCC power/clock gate
(`0x187004` bit 31 and the AXI/AHB/aggregate enable bits) and the transport itself. Both are reported
by the stall build now on the phone.

## 2026-11-09 03:55 — the persistent log channel already exists

The firmware reads a ramoops ring at `0xA7000000` on every boot and dumps its tail as `RAMOOPS|`
lines through `DEBUG()` (`Platforms/Xiaomi/UniXNUPkg/Driver/UniXNURamDiskDxe/UniXNURamDiskDxe.c`,
`DumpRamoops`), which is exactly what the Advanced Logger plugin exports.

Header layout, shared by both sides:

```
uint32 sig   = 0x43474244   ('DBGC')
uint32 start
uint32 size
// then capacity = 0x200000 - 12 bytes of ring, written by the kernel
```

The kernel side is `osfmk/arm64/diting_ramoops_console.h` from `patches/xnu-ipados18`:
`diting_ramoops_console_init()` maps `CONFIG_XNU_DITING_RAMOOPS_BASE` (0xa7000000 in both diting
defconfigs) plus 4 MiB, writes the magic and a `DITING DIAGNOSTIC v92` line, and every later console
write is mirrored into the ring.

Consequence: the console of a hung boot — including every `DITING_UFS` line — should survive in DRAM
and be readable from the firmware on the **next** boot, without a screen and without a QR scan of the
panic screen. The one observation so far (`RAMOOPS: sig=0x1400382E size=0x0`) predates any kernel run
that had the mirror enabled, so the channel is untested rather than broken.

Next device session, in this order:
1. reboot the stalled phone,
2. `fastboot boot` the same image again (the firmware dumps the previous ring at startup),
3. `Tools -> Advanced Logger`, scan with OneSend, send the `.log`.

That file should contain the kernel console tail of the stalled run.

## 2026-11-09 03:45 — root UUID verified against the shipped images

Added `scripts/apfs-volume-uuid.py` (lists every APFS volume superblock of a raw container with its
UUID and name; offsets from apfsprogs `include/apfs/raw.h`: magic 32, uuid 0xF0, name 0x2C0).

Measured on the images this port actually ships:

```
OS.dmg        volume b07df049-7ad9-47b5-9f8f-9ee728056398  name CrystalUpdate22H374.J171J172OS
SystemOS.dmg  volume 4a77ba00-2826-44c4-b883-1fa92ac36880  name CrystalUpdate22H374.J171J172SystemCryptex
AppOS.dmg     volume 78e7965a-108b-4dc9-a7a4-7ed503838e4f  name AppCryptex
```

The OS volume UUID equals `profile.toml os_volume_uuid` and the payload's `root_match_volume_uuid`
(`b07df049-7ad9-47b5-9f8f-9ee728056398`), so a published OS window is mountable by UUID.

**Discrepancy to fix:** `profile.toml systemos_volume_uuid` records
`D44F8E57-4171-4C6B-B21A-1808F6EF2E20`, which is the UUID of a *prepared* SystemOS volume made by the
macOS prepare step; the window we flash is the raw `SystemOS.dmg` whose volume is
`4a77ba00-2826-44c4-b883-1fa92ac36880`. Nothing consumes the SystemOS UUID for the root mount, but
the record is wrong for the image we ship and must be corrected before the SystemOS volume is
resolved by UUID.

`profile.toml systemos_volume_uuid` corrected in the same commit: `check-ci-volume-layout.py`
compares the layout's measured UUIDs against the profile, and the window this port flashes is the raw
`SystemOS.dmg`, whose volume is `4a77ba00-2826-44c4-b883-1fa92ac36880`, not the UUID of a macOS-prepared
copy.

## 2026-11-09 04:30 — reading the UFS report (ready-made mapping)

The stall build prints `formatUfsRootDiagnostics` before it freezes; this is what each field means
and what to do next. Line names come from `drivers/NativeUfs/RootDiagnostics.h`.

| field | meaning | next action |
| --- | --- | --- |
| `powered=0` (GDSC bit 31 clear at `0x187004`) | the firmware handed off with the UFS PHY power domain down | enable `gcc_ufs_phy_gdsc` (0x187004) and the PHY branches before reading the host, or make the payload keep it up |
| `buses=0` (AXI 0x187018 / AHB 0x187020 / AGGRE 0x1870d4 enable bits clear) | the clock branches are gated | enable the three branch bits, then re-read; `hwcg` may still report CLK_OFF on an idle branch, so judge by the enable bit only |
| `cap=0`/`cap=ffffffff` or `ver` out of range | the host block is not clocked (or not mapped) | same as above; do not trust any other field until `ver` is sane |
| `hcs` bit0 clear | the device is not present on the link | link/firmware handoff problem, not a driver bug |
| `hcs[3:0] != 0xf`, `db != 0`, or `is != 0` | the controller still owns commands from the previous owner | the request list is not ours to take; find who left it running (the bootloader's UFS driver) |
| `stage=` | exact step in `hostBringUp`/`RootQueue`/`RootCommands` | read the matching source line |
| `manifest=` | `RootLayout` status: 0 ok, 1 no magic, 2 version/count, 3 hash, 4 bounds, 5 names, 6 overlap, 7 attributes | the flashed image's SHNGROOT block; we verified ours, so a non-zero here means the partition was overwritten |
| `GPT/read lba=… userdata=…` | the GPT entry the driver resolved | must equal 0x2F8A00..0x3ADF3FA |

Two variants are built for the next session:

- `main` (2e6fc90): `diting_ufs_stall=1`, freezes on a UFS failure so the panel keeps the report.
- `no-stall` (12a8596): identical but without the stall, so the boot continues to the root-mount panic.

Both are otherwise the same kernel; the stall only decides whether the failure is frozen on screen.

Both next-session images are built and downloaded:

| variant | run | path | sha256 (first 16) | boot arg |
| --- | --- | --- | --- | --- |
| stall | 42509554099 | `build-work/greenD/.../boot/diting-unixnu-uefi.img` | `F2EDDF7F1B7B0466` | `diting_ufs_stall=1` |
| no-stall | 42519844089 | `build-work/greenE/.../boot/diting-unixnu-uefi.img` | `589710228B605371` | — |

The `no-stall` branch (12a8596) holds the variant; main keeps the stall build. The branch was rebuilt
after the first attempt accidentally committed `git commit -a` gitlink deletions for the drivers that
are not checked out locally (`drivers/ArmDTPlatform`, `DarwinBoot24`, `NativeRamBlock`, `DitingAdreno`,
`DitingBootCapture`, `DitingMetal`, `DitingPower`), which made that CI checkout fail with a missing source
file. Only `board.toml` is in the branch commit now.

## 2026-11-09 08:10 — why the manifest failed, and the fix

The panel from the stall run reported:

```
GPT/read lba=2f8a00 userdata=2f8a00..3adf3fa magic=474e4853 544f4f52 manifest=3
WINDOWS found=0 prepared=0 published=0 bytes=0 policies=0 verify=ffffffff
DITING_UFS: no media published; continue boot
```

So the UFS path itself works: GPT parsed, the first userdata block was read, and its `SHNGROOT` magic
matched. `manifest=3` is `RootLayout`'s header-SHA failure, and the local image still hashes exactly
(`ae82e3ea…` stored and computed) — the block on the phone was changed after the write.

Cause: the image was written with `dd` from a running Android and then `adb reboot bootloader`. That
is an orderly reboot, so Android unmounts `/data` and f2fs writes its superblock at offset 1024 of the
partition, which sits inside the SHNGROOT block — the magic survives, the hash does not.

Fix: write the partition **from the bootloader**, with Android out of the picture. 32-bit fastboot
cannot take the 10 GiB raw image, so `scripts/make-sparse-image.py` encodes it with the Android sparse
format (645 chunks, 10,809,777,752 bytes) and `scripts/flash-userdata-image.py` checks the product and
unlock state, flashes that, and can boot the payload in the same step.

Fallback if the sparse flash is refused: `dd` the raw image, then set the bootloader control block to
`boot-fastboot` in `/dev/block/by-name/misc` and force an immediate reboot (`echo b >
/proc/sysrq-trigger`), so Android never unmounts `/data`. Not used yet.

## 2026-11-09 21:15 — userdata written from the bootloader (sparse)

`fastboot flash userdata userdata-root.sparse.img` with the phone in the bootloader succeeded where
the raw image failed: 14 sparse chunks, every `Sending`/`Writing` line OKAY, total 276 s. Android never
ran, so nothing could rewrite the SHNGROOT block.

Pre-flight facts checked before the write: `fastboot devices` -> 9e0c2b55, `product=diting`,
`unlocked=yes`, `partition-size:userdata = 0x37E69FB000` (240,092,426,240 bytes = the 223.6 GiB the
board records), sparse encoding round-trip verified against the raw image on the host.

Then `fastboot boot diting-unixnu-uefi.img` (stall variant, F2EDDF7F) was sent: `Sending ... OKAY`,
`Booting OKAY`. The panel is the only remaining witness; the phone dropped off adb, which is what a
running payload looks like.

## 2026-11-09 22:20 — **root volume mounted** (stage 6 reached)

Three-window userdata image (OS 6,845,104,128 at 0x100000; SystemOS 3,963,617,280 at 0x198100000;
Data 8 GiB GPT+APFS at 0x285000000; image 19,411,238,912 bytes) written from the bootloader with
`fastboot flash userdata` on the sparse encoding (25 chunks, 492 s), then `fastboot boot`.

Panel evidence:

```
DITING_UFS: OS root binding UUID b07df049-7ad9-47b5-9f8f-9ee728056398 bound to OS UFS window /dev/disk2s1
DITING: APFS: diting
DITING_UFS: wait for SystemOS UUID D44F8E57-4171-4C6B-B21A-1808F6EF2E20, timeout=5s
DITING_UFS: SystemOS UUID wait timed out
DITING_UFS: SystemOS media identity published on /dev/disk2s1
DITING DEVELOPMENT: scratch Data mount SKIP error=-6 stage=0
Diting init: Loading helper /diting/init
Diting init: helper exec result=2
panic: Diting init helper exec failed, errno 2 @kern_exec.c:7067
```

What each line establishes:

- the OS window is published, the APFS root volume is mounted, and the kernel resolves it by UUID;
- the SystemOS wait used the **stale** `D44F8E57…` value (the profile entry corrected in 2e6fc90 has
  not been in a build yet); the media that appears is `4a77ba00-2826-44c4-b883-1fa92ac36880`;
- the Data window is accepted by the manifest/GPT and its mount is skipped, not fatal;
- `load_init_program` runs and execs the configured init, so the failure is only that `/diting/init` is
  not part of the stock Apple OS volume.

Next experiment (this commit): `diting_init_path=/sbin/launchd`, so the stock launchd is the init and the
boot no longer depends on our userland helper being installed. Only the payload changes, so the flash
is not needed again; a `fastboot boot` of the new image is enough.

## 2026-11-09 23:20 — Data window matches, launchd is the init now

- The CI workflow hard-codes the Data volume UUID it compiles in
  (`.github/workflows/package.yml`, volume layout step: `'data': {'uuid': '337CF716-F62B-446B-B959-4A5F12A7701C'}`),
  and `build-ipados18-diting-macos.py` passes `layout['data']['uuid']` as `XNU_OWNER_DATA_VOLUME_UUID`.
  Our first Data window was created with a random mkapfs UUID, so the kernel skipped the mount
  (`scratch Data mount SKIP error=-6`).
- `scripts/make-data-window.py` now takes `--uuid` and passes it to mkapfs **-u** (the volume UUID;
  `-U` sets the container UUID). Rebuilt with `337cf716-f62b-446b-b959-4a5f12a7701c` and verified with
  `scripts/apfs-volume-uuid.py`.
- The SystemOS UUID also comes from `profile.toml` through the same layout step, so the 2e6fc90
  correction (`4A77BA00-2826-44C4-B883-1FA92AC36880`) took effect in the 42634647682 build.
- Rebuilt userdata (19,411,238,912 bytes), sparse (1157 chunks), flashed from the bootloader in 494 s,
  then `fastboot boot` of the build with `diting_init_path=/sbin/launchd` (sha A135720C).

Panel: the OS root binds by UUID, APFS mounts, the SystemOS wait now uses 4a77ba00, the Data mount no
longer reports the UUID mismatch, the kernel then tries to exec `/sbin/launchd` and panics in
`kern_exec`. The exact errno needs a legible photo of the last lines before concluding whether the
root tree really lacks the file or the exec is rejected for another reason.

## 2026-11-09 23:55 — the init path whitelist, and the Data mount is SKIP not panic

`patches/xnu-ipados18/0001-diting-darwin24.patch` (load_init_program):

```c
if (PE_parse_boot_argn("diting_init_path", diting_init_path, sizeof(diting_init_path))) {
    if (strcmp(diting_init_path, "/diting/init") != 0)
        panic("Unsupported Diting init path");
    ... exec /diting/init ...
}
// only reached when diting_init_path is absent:
for (i = 0; i < init_programs...) load_init_program_at_path(...);
```

So `diting_init_path=/sbin/launchd` was itself the panic. The argument is removed; with it absent the
kernel walks its normal `init_programs` list and `/sbin/launchd` is tried as the stock init.

The Data lines before the panic are not fatal and are separate:
`UUID candidate ... accepted=0 window=Data` → `UUID lookup MISS` → `writable UFS Data UUID
unavailable` → `scratch Data mount SKIP error=6 step=0` (ENXIO). The driver publishes every window
read-only while `diting_ufs_readwrite=0`, so the kernel finds no *writable* Data device and skips the
mount instead of panicking. Making only the Data window writable while OS/SystemOS stay read-only is
a driver change to do after launchd is seen running.

## 2026-11-10 00:35 — stock init path enabled

`diting_init_path` removed from `kernel_args` (commit 865ff27), build 42650203427 green, image sha
F354D89C, booted on the phone. With the argument absent the kernel leaves the Diting branch and walks its
normal `init_programs` list, so `/sbin/launchd` is attempted as the stock init. No userdata change, so
no reflash was needed.

## 2026-11-10 00:50 — launchd runs; services die on EACCES

With `diting_init_path` absent the kernel walks its normal init list, `/sbin/launchd` executes, and the
console scrolls: launchd is managing services. Every service then fails the same way:

```
Service could not initialize: posix_spawn(/usr/libexec/timed)
error 0xd - Permission denied
Initialization failure: 22H374: xpcproxy
xpcproxy exited due to exit(78)
```

and the same for `/usr/libexec/sharingd`, `/usr/libexec/ptpd`,
`/System/Library/PrivateFrameworks/CoreDuetContext.framework/Resources/contextstored`.

`xpcproxy` itself starts, i.e. execution from the mounted OS volume works; the denial happens when
xpcproxy spawns the service. The kernel skipped the Data mount just before
(`scratch Data mount SKIP error=6 step=0`, ENXIO) because the driver publishes every window read-only
while `diting_ufs_readwrite=0`, so `writable UFS Data UUID unavailable` even though the UUID candidate is
accepted. A missing `/private/var` is the most plausible cause of the EACCES storm.

Experiment: `diting_ufs_readwrite=1`. The root volume is mounted read-only by APFS policy regardless of
the block device's write flag, so this mainly lets the Data window be published writable; if the
services stop failing, the hypothesis is confirmed and the driver can later be restricted to publish
only the Data window writable.

## 2026-11-10 01:35 — writable window build booted

`diting_ufs_readwrite=1` (commit e8aafae), build 42658401487 green, image sha 5AA052E2, booted.
`native_diting_ufs_data_volume_device` -> `native_diting_ufs_volume_device(uuid, 2, ...)` accepts a Data
window only when the block reports `DitingWritable` **and** the IOMedia reports writable, so this flag is
exactly the gate that produced `writable UFS Data UUID unavailable` with the read-only build.

Watching for: `DITING APFS: UUID ... bound to Data UFS window`, `scratch Data mount` no longer SKIP, and
whether the `posix_spawn(...) error 0xd - Permission denied` loop stops.

## 2026-11-10：服务启动权限诊断

- 22H374 原生 launchd 与 xpcproxy 已实机运行，多个目标服务的 `posix_spawn` 返回 EACCES；Data 在只读轮次未挂载，写入轮次尚未观察到其最终状态。
- `applog=1` 现有逻辑会把 spawn 文件操作中输出到 `/dev/null` 的路径重定向到 `/dev/console`；这是一条待验证的失败路径，不能认定为实际原因。
- `diting_exec_diag=1` 启用有次数上限的 xpcproxy spawn 诊断，区分文件操作、路径查找、执行权限、镜像激活、persona、签名约束及 Data 状态；诊断不修改原错误或权限行为。实际根因必须以该镜像的设备日志为准。

## 2026-11-10：applog 读写重定向修正

- 22H374 的 xpcproxy 以 `O_RDWR | O_NOCTTY` 打开输出的 `/dev/null`；console 默认权限为 `root:wheel 0622`，非 root 读写打开可能触发 EACCES。
- `e331648` 保留读写打开的 `/dev/null`，仍将只写打开的标准输出或标准错误按 `applog` 设置重定向到 console。本地源码级验证通过，设备上是否消除 EACCES 仍需确认。
- greenH 对照镜像仅将 `applog=1` 改为 `applog=0`，已通过 `fastboot boot` 临时启动；观察结果尚未收到。Action 42698962449 构建的是此前的诊断提交 `835b22a`，不含本次修正。
- greenH 的 `applog=0` 对照启动进入了 `watchdogd[186]` 退出引起的 panic，退出原因 namespace 2、code 5 对应 SIGTRAP；此前 EACCES 是否全部消失仍待完整日志。现有用户异常抓取名单已加入 watchdogd，下一镜像可打印异常 PC、LR、共享缓存 slide 和部分用户栈，供定位退出位置。
- Action 42727444462（aa093e2）已成功，构建日志确认编译 `diting_ui_exception.o`。其镜像追加 `panic_on_crash_disabled=1` 后离线生成 `D:\ai\diting\build-work\watchdog-trace-no-panic.img`，尚未实机启动；该开关只抑制非 launchd 进程退出触发的 panic，不能消除进程崩溃或其他 panic。
- 2026-11-10 实机日志：SpringBoard、accountsd 等已 spawn，但以 `couldn't dlopen libobjc-trampolines.dylib` 退出；本地 OS 卷缺少该库，匹配的 SystemOS 卷中有该库。当前非 union 模式将 SystemOS 挂在 `/private/preboot`，标准 `/usr/lib` 路径不可见；不能仅凭此确认所有崩溃的根因。
- 独立实验分支 `ci/systemos-union`（1ec3b7b）启用已有 SystemOS 根目录联合挂载，Action 42817934102 构建中；不要将实验构建当作实机通过。
- Union 实机日志出现 `Unable to set current working directory /tmp` / ENOENT；OS 中 `/tmp -> private/var/tmp`，本地 8 GiB Data 种子 APFS 为空。实验提交 9628bd4 在核验 Data 可写后创建缺失 tmp，已测试、构建 Action 42829451753 尚未完成；完整 Data 种子仍需按现有 userland/init 方案处理。
- 2026-11-10 文档复核：新图显示 `mobile.usermanagerd` SIGABRT，描述 `Daemon failed to load persona manifest`。原始 OS 的 launchd `Boot.usermanagerd` 和 `Boot.launchd_cache_loader` 均没有 `PerformInRestore`；`userland/build-ipados18.py:adapt_launchd18` 与 `migration/ipados18/services.md` 已记录相应准备步骤。是否为此次失败的直接原因仍须核对实际启动模式。
- 空 Data 卷不是完整 Data seed；现有 tmp 补丁只是局部实验。当前 package 工作流没有 userdata job 或 ipsw_url 输入，README 已修正。继续按匹配 Data 种子、OS 用户态准备和可回读日志的路径排查，勿直接套用 Sheng 镜像或覆盖手机数据。

## 2026-11-10 23:45 — Data skeleton generated from the matching OS volume

The OS restore volume already carries the complete `/private/var` skeleton with the right owners and
modes (mounted read-only at `/home/nagatoquin/unixnu/diagnostics/mounts/diting-os/root`). That removes
the need for a macOS-prepared Data image for the directory layout: `scripts/gen-var-skeleton.py` reads
the mounted volume and emits `patches/xnu-ipados18/zzzzzzzzzzz-diting-data-skeleton.patch`, which creates
every missing directory (mode, uid, gid) right after the Data volume is mounted at `/private/var` and
leaves existing entries untouched. 87 directories at depth 2, app bundles excluded; metadata only, no
Apple file contents.

The patch follows the pattern the Data tmp experiment established (`mkdir`/`chmod` syscall wrappers
called from `native_owner_data_prepare`), and adds `chown` for the recorded owner.

## 2026-11-11 01:30 — Data skeleton builds (patched into the base XNU patch)

The first attempt shipped the skeleton as its own follow-up patch
(`zzzzzzzzzzz-diting-data-skeleton.patch`), and the CI rejected it with
`Patch does not apply cleanly`: a follow-up hunk cannot be anchored reliably because every earlier
patch shifts the line numbers, and `git apply` only searches a short distance from the hint. A second
attempt anchored at line 1 failed the same way.

Fix: `scripts/gen-var-skeleton.py --insert-into patches/xnu-ipados18/0001-diting-darwin24.patch` inserts the
generated table and loop into the base patch itself, where the context is guaranteed to match, and
`scripts/recount-patch.py` recomputes every hunk header from its body afterwards. Build 42859003034
(4147d47) is green, so the kernel compiles with the new code.

The code creates the 87 directories at depth 2 (app bundles excluded) right after the Data volume is
mounted at `/private/var`, using the `mkdir`/`chmod`/`chown` syscall wrappers already proven by the Data
tmp experiment, and prints `DITING APFS: var skeleton created=%d failed=%d`.

## 2026-11-11 02:15 — skeleton build booted (verification pending)

Build 42859003034 (4147d47) produced image sha C5D58F80; `fastboot boot` OKAY on 9e0c2b55 and the phone
left adb/fastboot, i.e. the payload is running. The panel is the only witness so far: the expected line
is `DITING APFS: var skeleton created=87 failed=0`, and the next questions are whether the `/tmp` ENOENT
and the persona/usermanagerd failures changed.

## 2026-11-11 02:20 — launchd boot task inspected (read-only)

The mounted OS volume's `/sbin/launchd` (560,752 bytes) embeds its boot-task plist. The `usermanagerd`
task is:

```
<key>usermanagerd</key>
<dict>
    <key>PerformAfterUserspaceReboot</key><true/>
    <key>ProgramArguments</key><array>
        <string>/usr/libexec/usermanagerd</string><string>--init</string>
    </array>
    <key>AllowCrash</key><true/>
</dict>
```

so it carries `PerformAfterUserspaceReboot` but **no `PerformInRestore`**, which matches the handover's
claim. `PerformInRestore` appears on other tasks (`restore-datapartition`, `exclaves-boot`), so the key
is understood by this launchd build. Whether the current boot counts as restore mode decides if the
persona initialisation runs; that is the next thing to establish from the panel, not to guess.

## 2026-11-11：合并已构建的 Data 骨架与 SystemOS 路径

- 4147d47 的 Data 目录骨架和 ci/systemos-union 的只读根卷合并此前位于不同分支；本次把后者的 CI 配置接入包含骨架的 main，避免新构建回到仅依靠 Cryptex 备用路径的配置。之前照片未完整证明 trampoline 已解决；合并后的挂载、Data 骨架、用户态与界面均待实机验证。

## 2026-11-11：二维码日志实机复核

- 33 使用 `greenI2-log-menu.img` 的 Tools → Advanced Logger 成功通过二维码导出日志到 `C:\Users\nagatoquin\Downloads\Redmi K50 Ultra-20190100-000250(1).log`。二维码导出与固件日志已实机成功，不应再表述成该功能不存在。
- 导出内容包含 `RAMOOPS: sig=0x1400382E size=0x0 (no xnu log)`；本次未取到上轮 XNU 日志。原因尚待核对复位类型、内存保留和内核写入，不能只凭这一份日志判断所有重启场景。该日志是固件输出，不代表已实现独立落盘日志。
- 6ec0b96 将已构建的 Data 骨架与已有 SystemOS union CI 配置合并；Action 42877431747 已根据 33 的反馈取消，合并版尚未编译或启动。不要因目录存在而重写 Data 或假称系统可用。

## 2026-11-11 03:55 — prepared userland installed; both window writes verified by sampling

The previous session finished writing the prepared 22H374 OS and Data into their userdata windows
before it hit the usage limit, and left the phone in the temporary TWRP (`diting-recovery-boot.img`,
root adb, no dd/gzip process). This round did **no boot and no write**: the user is away and a failed
`fastboot boot` cannot be power-cycled back to fastboot without them.

Read-only verification (`scripts/verify-ufs-window.py`, added here):

- SHNGROOT v1 at userdata offset 0: 3 windows, `imageBytes=19,411,238,912`, directory checksum ok.
  OS `0x100000` (6,845,104,128), SystemOS `0x198100000` (3,963,617,280), Data `0x285000000`
  (8,589,934,592).
- OS window equals `prepared-420734-os.img` at 7/7 sampled 64 KiB regions from 0 to 6.375 GiB,
  including the final 64 KiB of the window: the sequential dd reached the end.
- Data window equals `build-work/windows/Data.img` at 7/7 samples; the 4 KiB block holding
  `Diting development Data seed for 18.7.10 / 22H374` (image offset 0x184e000) is byte-identical on the
  device.
- SystemOS was not rewritten; its first 4 KiB still starts with an APFS `NXSB` object, so the OS
  stream did not overrun 0x198100000.

The directory still records the previous OS/Data sha256 (`be43bec0…`, `e5bced3f…`); the installed
content hashes to `45b6344f…` and `1378adfe…`. `RootLayout.h` checks only the 4064-byte directory
checksum and bounds/names/flags, and `DitingUfsTransport.cpp` never compares the per-window digests, so
the stale record does not block publication — but it must not be quoted as the installed digests.

`scripts/inspect-diting-userland.py` (added here) passes on the installed triple: OS UUID B07DF049,
`/diting/init` 755, `/diting/etc/var.skel`, `/diting/var-seed`; `/sbin/launchd` is byte-identical to
`/diting/init` (the Diting static init wrapper) while `/sbin/launchd.ios` is Apple's 560,752-byte launchd
and carries `PerformInRestore` for `usermanagerd` and `launchd_cache_loader`; Data UUID 337CF716 with
the seed marker, `keybags 0700`, `mobile 0711`, `db`, `containers`, `preferences`, `tmp 01777`.

Pairing for the next boot: build 42859003034 (4147d47) image `C5D58F80`,
`build-work/greenI2/.../boot/diting-unixnu-uefi.img`. Its payload args have no `diting_init_path` and do
carry `diting_ufs_readwrite=1 diting_ufs_stall=1 diting_exec_diag=1 applog=1`; the ADT has B07DF049 /
4A77BA00 and mounts SystemOS at `/private/preboot`. The DITING init list starts at `/sbin/launchd`,
which this userland replaces with the wrapper, so the native path runs the Diting init and execs
`launchd.ios`. No `diting_init_path` and no SystemOS union (6ec0b96) needed — that merged build is still
unbuilt/unproven and must not be conflated with this pairing.

Still unobserved, therefore not acceptance: kernel-side re-publication of the windows, root binding,
Data mount at `/private/var` and launchd services with the prepared userland. Those need the next
manual boot; see `D:\ai\diting\交接-2026-11-11-准备用户态.md` for the exact commands and screen
criteria.

## 2026-11-11 04:20 — live window UUIDs read from the device

`scripts/read-ufs-window-apfs.py` (added here) reads only the APFS metadata blocks a container needs
and follows the GPT for the Data window, so the UUID match can be checked while the phone still sits
in recovery (48–64 device blocks, 192–256 KiB per window, no full-image readback):

- OS `0x100000`: volume `CrystalUpdate22H374.J171J172OS` UUID B07DF049-7AD9-47B5-9F8F-9EE728056398,
  role 0x1, sealed=False, container xid 442. Matches XNU_OWNER_ROOT_VOLUME_UUID.
- SystemOS `0x198100000`: volume `CrystalUpdate22H374.J171J172SystemCryptex` UUID
  4A77BA00-2826-44C4-B883-1FA92AC36880, sealed=True. Matches XNU_OWNER_CACHE_VOLUME_UUID.
- Data `0x285000000`: GPT with the APFS partition at 0x100000; volume `Data` UUID
  337CF716-F62B-446B-B959-4A5F12A7701C. Matches XNU_OWNER_DATA_VOLUME_UUID.

The built payload embeds those three strings (plus `/private/preboot` and the DYLD_* environment), and
the `DITING APFS: writable UFS Data UUID unavailable` literal proves the UFS Data branch is compiled,
not the md0/RAM fallback. `native_owner_data_prepare` mounts "apfs" at "/private/var" with flags 0
and then rejects the mount if it is MNT_RDONLY, so `diting_ufs_readwrite=1` is required and present.
That code does not consult the APFS volume role or volume group; both the OS and Data images carry a
zero volume group id, so the Data UUID rewrite did not create a group mismatch.

## 2026-11-11 04:30 — file-level identity of the installed windows

`read-ufs-window-apfs.py` grew `--stat/--hash` and `--image`, so the same report runs on the device
and on the local window source. Against the live windows:

- OS: `/sbin/launchd` is the wrapper (71,392 B, sha256 `a80747bb…`, identical to `/diting/init`),
  `/sbin/launchd.ios` is Apple's launchd (560,752 B, sha256 `81cefc45…`), `/diting/etc/var.skel`
  31,219 B. Both file hashes equal the `prepared-420734-os.img` values, and the container UUID/xid
  (`afc0f9bd…`, 442) match, so the installed OS window carries the prepared image at the file level,
  not just at the sampled offsets.
- Data: `/.diting-data-22H374` (48 B, sha256 `defb18e6…`) and
  `/mobile/Library/Preferences/com.apple.purplebuddy.plist` (146 B, 501:501) match
  `windows/Data.img`; container `3475eb93…`, xid 2.
- SystemOS: container `975fa298…`, xid 13, volume 4A77BA00… sealed. The local `SystemOS.dmg` has the
  same container UUID/xid, but block 926542 is zero in both source and device and the sealed live
  root tree resolves through it, so the in-tree apfs reader cannot list files on that volume. This is
  a reader limitation, not a device fault (apfs-fuse listed the same volume earlier); file-level
  evidence for SystemOS still comes from that mount, not from this reader.

## 2026-11-11 04:40 — boot preflight gate passes end to end

`scripts/preflight-diting-boot.py` (added here) is the single gate before a one-way `fastboot boot`.
It checks the device is in recovery and reports `diting`, the boot image sha256 (C5D58F80), the
embedded args (must keep `diting_ufs_readwrite=1`, must not set `diting_init_path`), samples both windows
against their source images, and reads the three APFS volume UUIDs from the live windows. It writes
nothing and does not boot. Run today against `9e0c2b55` with the C5D58F80 image and the installed
windows: all checks passed (window sampling plus the three UUID reads), so the remaining acceptance
work is the boot itself, not the inputs.

## 2026-11-11 08:15 — C5D58F80 booted again with the prepared userland

- `fastboot getvar`: product=diting, unlocked=yes, current-slot=a. Boot image sha256 checked in full
  (`C5D58F8088900F6BAB15B177B52FD3A080A94E9CBE6E6ABE4185D13CDB98F833`), then `fastboot boot` reported
  `Sending 'boot.img' (98820 KB) OKAY` and `Booting OKAY`.
- 60 s after boot neither adb nor fastboot had a device on USB, so the panel is the only witness.
  Phase 6 scoring waits for the user's photo; do not treat OKAY as a hardware pass.
- A screen-line table for that photo now sits in `D:\ai\diting\交接-2026-11-11-准备用户态.md`
  (strings quoted from `drivers/NativeUfs` and `patches/xnu-ipados18/0001-diting-darwin24.patch`).

## 2026-11-11 09:50 — the cache loader panic; fix was already recorded

- The panel from the 08:15 boot showed `panic: launchd_cache_loader(1) exited -- exit_reason
  namespace 7 subcode 0x1 description: Failed to verify code directory`. The prepared wrapper did
  exec `/sbin/launchd.ios`, so this is the restore-mode cache loader, not a storage failure.
- `migration/ipados18/services.md` already records the fix (services9): the loader supports
  `launchd_unsecure_cache=1`, which lets the stock loader load the locally adapted cache instead of
  pairing a modified plist with Apple's old signature. The C5D58F80 payload did not carry it;
  `board.toml [payload] kernel_args` now does (assembled args line 757 bytes, under the 1023 limit).
- Logs no longer need a photo: the firmware dumps the `0xA7000000` ramoops ring through
  Tools -> Advanced Logger on the next boot (see 2026-11-09 03:55 above). The 02:45 export showed
  `size=0` because it predates a mirror-enabled run; the next export must be checked before claiming
  the channel works.
- Repo identity: README.md was still the Diting / Nothing Phone (2) page. Rewritten for Diting with the
  current stage and the ramoops/QR log note. The AGENTS line "This is the Diting SM8475 ..." was
  corrected to Diting. Component identity DitingPlatform24 stays: the drivers are the community Diting
  SM8475 implementations, not the upstream A740/WCN7850 source.
- No device access this round (phone disconnected); nothing was written or booted.

## 2026-11-11：DeepSeek 执行计划

- 33 将任务改为编写接手计划，不继续试验。计划位于 `D:\ai\diting\DeepSeek执行计划-进系统与Diting整理-20261111.md`；优先把现有准备用户态所需的 `launchd_unsecure_cache=1` 放入实际 payload，然后推进系统界面。Diting 命名迁移列出 board/kit/firmware/组件/机器配置/脚本/产物的完整调用链，全部在 main 完成。
- 原 OS 窗口写入后台任务已确认完整结束；本轮写计划时没有新增设备写入或启动。较新的准备用户态与 cache loader 状态见 `交接-2026-11-11-准备用户态.md` 及上方 09:50 记录，不能再以旧空 Data 状态继续。

## 2026-11-11 09:55 — launchd_unsecure_cache=1 is in an actual boot image

- `scripts/patch-boot-payload-args.py` (commit b995b82) rewrites the xnu args in
  `EFI/UniXNU/unixnu.toml`, the development boot manifest, the ADT's `boot-manifest-hash` (SHA-384) and
  the PONGFAT1 CRC, leaving the kernel, ADT tree and firmware untouched.
- Output: `D:\ai\diting\build-work\diting-boot-launchd-unsecure.img`, 101,191,680 bytes, sha256
  `cb56ac9de5b4573c8ddcbbfc24215b38742a4dfe5b194251145492ffb31a412b`. Verified: same size, kernel
  slot byte-identical, only the ramdisk region changed; TOML and manifest `boot_args` both contain
  `launchd_unsecure_cache=1`; the ADT digest equals the manifest SHA-384; the envelope CRC is valid.
- Action 42941361215 was cancelled: it used the SystemOS-union CI defconfig, not the pairing of the
  installed prepared userland.
- Next device step: `fastboot boot` this image after the product/slot checks, then read the previous
  XNU console through the ramoops/Advanced Logger QR export on the next boot. No screen photo.

# Diting 全量改名（2026-11-11）

- 机器配置改为 DITING：`config/MASTER.arm64.diting`、`pexpert/arm64/DITING.h`、`-DARM64_BOARD_CONFIG_DITING`、对象目录 `DEVELOPMENT_ARM64_DITING`、产物 `mach.development.diting`；补丁系列与文件同步改名。
- 驱动已收编进仓库（12 个 submodule 转普通目录，保留来源与许可证）；`Diting*` 目录、文件、类名、启动参数、DT 属性、日志前缀统一改为 Diting；打包产物与配置改为 `diting-*`。
- 固件入口改为 `Platforms/Xiaomi/ditingPkg`；CI 的 package job 从固定的 `Emilelu/uefi-mondrian` 加 `platform-firmware/ditingPkg` 准备固件树，release 用 `--fd` 接收 Linux 固件 job 构建的 FD（核心分支 `diting-release-fd`，commit `0ce9779`）。
- 保留的外部接口（不可单独改名）：`PONGFAT1` 信封、`Binaries/diting/RawFiles` 固件二进制、`pong-boot-manifest` 文件名/格式、上游 Diting 仓库 URL 与版权声明、以及**已安装 prepared OS 的 `/diting` 运行时约定**。
- 重要：新内核要求 Diting 用户态（`/diting/init`、`/dev/diting-*`、`dev.unixnu.diting.*`）。当前已安装 prepared OS 仍是 `/diting`，只与改名前内核配对；验证界面用 `D:i\ditinguild-work\diting-boot-launchd-unsecure.img`，重装 Diting userdata 前不要用新内核启动。
- 构建状态：本次改名后尚未完成 CI 构建。

# Diting 构建通过（2026-11-11）

- CI run 42963886855：`firmware` 与 `package` 两个 job 全绿，改用 `--fd` 让 package job 消费 Linux 固件 job 的卷。
- 产物：`diting-unixnu-uefi.img` 101,191,680 B sha256 `a96a33339489ef3c8b6579db8bc3f33d8509f623579559f832f381f8008e0cd1`；`diting-xnu-initial.img` sha256 `1d7c151accad4b40d813ffd8a34a0da7da02e61bd6e44902cc93460a41df6bbc`；`kernel.macho` 51,793,920 B sha256 `c096ca2aee97ff29ab8991805ae8b4507e82a78894561b7347737739ae23c2d6`。
- 该内核的运行时命名空间已是 Diting（`/diting/init`、`/dev/diting-*`、`dev.unixnu.diting.*`、`diting_*` 启动参数）；当前已安装 prepared OS 仍是 `/pong`，**不能直接引导新内核**。设备界面验证继续用旧内核镜像 `D:\ai\diting\build-work\diting-boot-launchd-unsecure.img`（sha256 `cb56ac9d…`）；要上机新内核必须先重编并重装 Diting userdata。
- 保留的外部接口：`PONGFAT1` 信封、`Binaries/pong/RawFiles` 固件二进制、`pong-boot-manifest` 格式/文件名、上游 Pong 仓库 URL 与版权声明。

# 2026-11-11 上游对齐与驱动审计

- Sheng 上游对齐结论：保持 22H374；只借其打包/运行时/固件层（`[payload.runtime]`、`make-data-seed.py`、`runtime.py`、固件预检链、CI seed 缓存）；不搬 WiFi/BT/Metal/基带驱动。详见 `D:\ai\diting\Sheng上游对齐-结论与待办-20261111.md`。
- 驱动真实状态：WiFi/GPU/Metal 代码在，但刚绿的 CI（42963886855）用 `diting_ipados18_ci_defconfig`（`WIFI=n`、`ADRENO=n`、`BACKLIGHT=n`、无 `POWER`），三个驱动树都没编进内核；该产物只做编译验证，不能配 prepared OS 进界面。
- 基带：无驱动、无 `QcomBaseband`、目标 IPSW 是 Wi-Fi iPad（`iPad7,11`，无基带固件/消费者）；移出目标，只在文档记录原因。
- userdata 写入器几何已修（`73f73c8`）：`scripts/` 里的 `sda13`、`0x413248/0x75a40ea`、8 GiB 偏移改为 `sda37`、`0x2F8A00/0x3ADF3FA`、`0x285000000`；写入前仍须 recovery 现场核对 start/size/logical。
- Wi-Fi：老谱系有用户确认连接记录（`porting.toml` services107/108/112），当前构建未启用；阻塞是 CI 无 WiFi 固件 secret、`WIFI=n`、缺 `diting_wifi=1`。不要搬 Sheng 的 WLAN ADT 节点，Diting 已用剥离 `_LimitLoadToDeviceTree` 的方式解决 wifid。
- Metal：老谱系有设备证据（services124/135/155/167）；当前缺 `diting_adreno_start=1`/`diting_metal=1`，CI 不构建 Metal bundle；`drivers/AdrenoMetal` 是未使用的重复副本。
- 许可证：`THIRD_PARTY_NOTICES.md` 未列 GPL-2.0（ath11k/MHI/QMI）、metal2vulkan、Mesa/Turnip；公开产物前补。
- 当前真正卡点仍是 `launchd_cache_loader` 的 code directory 校验；WiFi/Metal/基带都不在进入界面的关键路径。

# Sheng 答复要点（2026-11-11）

- Sheng 未改 OS 镜像：OS/SystemOS 原样；驱动在内核；Metal 插件走 payload gpu-addon 写到 Data；owner trust 合入 trust cache；无 /sheng 包装器、无 launchd cache 改动。
- Sheng 的 RootLayout 是 v1 两窗口（OS/SystemOS）+ payload Data seed；Diting 的 v1 三窗口是 fork 自己的选择。
- Data seed 是 packed_ramdisk DBRDISK1（APFS NXSB），960 GiB 逻辑容量打包后仅 1.28 MB；在 macos-15 runner 上用 seed-data-grow.py 生成。
- userdata 在 WSL Linux 上用 unixnu build userdata 生成；21H461 无 AEA，udif.py 可直接解码；18.7.10 的 AEA 才需要 macOS。
- 对 Diting：A 路线（v1 两窗口 + seed、不改 OS）可完全 Linux 化，但需替代 /diting 包装器与 launchd 补丁；B 路线（保留 prepared OS，只重建 6.8 GB OS 窗口）峰值约 14 GB，仍需一台 Mac。先走 B，A 作为目标。

# 2026-11-11 Claude 结论与重建路线

- 选 B：保留 prepared OS，只重建 OS 窗口；SystemOS 与 Data 第一次不动。纯 A（OS 原样、用户态全进内核）需要重写 Diting 的 mini-AMFI + restore launchd + kern.exec_inject 适配，不做。
- 更正：托管 `macos-15-intel` 可以跑完整 userdata 链（run 42073458178 / job 127407532963，34 分钟，reclaim disk 到 80 GiB，峰值约 37 GiB）。旧 userdata job 在 `425c309` 被删，已恢复为 `.github/workflows/diting-userdata.yml`，只上传 OS 窗口与报告。
- 新增 `configs/diting_ipados18_bringup_defconfig`：`CONFIG_XNU_OWNER_CRYPTEX_FILES=y`、`CONFIG_XNU_OWNER_UNION_SYSTEMOS=n`；WiFi/Adreno/backlight 保持关。`package.yml` 增加 `defconfig` 输入。
- 顺序：舞台 1（旧镜像 `cb56ac9d…`）→ userdata job 出 OS 窗口 → bring-up 内核 → TWRP 写 OS 窗口（`sda37`，`seek=1`）→ `fastboot boot` 新镜像 → 逐步开驱动。
- 写 OS 窗口前核对 `sda37` start=24924160、size=468930520；回退用 `prepared-420734-os.img`。
- provenance 修正：`porting.toml` 里继承的 “Pong live Android DT” 等历史输入不再改成 Diting。

# 2026-11-11 阶段 2a/2b 完成

- userdata job `42987806310` 绿：新 OS 窗口 `diting-ipados18-system.cdr` 6,845,104,128 B，sha256 `27c507c8972275c9170806bb975b03d762ebbb9379945b890d5665a154e8102d`；根卷 UUID `B07DF049…`，`/sbin/launchd` == `/diting/init`（71,392 B，sha256 `95cb7341…`），`launchd.ios` 含 `PerformInRestore`，`/diting/libditing-ui18.dylib` 174,976 B，`/pong` 不存在。已下载到 `D:\ai\diting\artifacts\ci-42987806310`。
- 该 job 的 `volume-layout.json` 里 SystemOS/Data 是新建容器 UUID（`771CEF3F…`/`1C04B790…`），**不要**用于设备或内核；设备继续用 `4A77BA00…`/`337CF716…`。
- bring-up 内核 run `42994674560` 绿（`diting_ipados18_bringup_defconfig`）：`diting-unixnu-uefi.img` 101,191,680 B sha256 `e9b615bf9ae0143cbe6195f9625105b92cbbc877c5e35e97ec7b6d6130b0d35d`；`kernel.macho` 51,793,920 B sha256 `6399f2ca5dbde521a3aaf352028da2a22f704803272e2c8665a56491d995ff76`；配置 `diting_ipados18_bringup_defconfig`。
- 镜像参数已逐个核对：`launchd_unsecure_cache=1`、`diting_ufs_readwrite=1`、`diting_exec_diag=1` 均在；无 `diting_init_path`、无 `pong_`；manifest 与 TOML 一致，ADT 的 `boot-manifest-hash` 等于 manifest SHA-384，PONGFAT1 CRC 有效；内核里三个 UUID 字符串都在。
- CI 修正：`5863dd7`（按所选 defconfig 走打包路径）、`31e710c`（断言 `[package.defconfig]` 与输入一致）。
- 写入 runbook：`D:\ai\diting\OS窗口写入与回退-安全版-20261111.md`；路线图 §2c 已改为 `shell -T` + `count=6528` + `pipefail` + receipt，并用 `ANDROID_ADB_SERVER_PORT=5038` 适配只读校验脚本。
- 下一步：手机可用时先舞台 1（`diting-boot-launchd-unsecure.img`，`cb56ac9d…`）取日志；再按 runbook 写 OS 窗口、`fastboot boot` bring-up 镜像、Advanced Logger 取日志。

# 2026-11-12 全开配对（private firmware + live DTB）

- run `43057086317`（`23d3a92`，`diting_ipados18_defconfig` + `firmware_tag=fw-20261111`）在 package 步骤失败：Wi-Fi native 构建 `prepare-diting-wifi.py:54` `KeyError: 'qcom,phy-sequence'`。原因：`scripts/build-ipados18-diting-macos.py:46` 把 `DITING_HARDWARE_DTB` 覆盖成内核 `hardware.dtb`（format-2 精简树），Wi-Fi 的 PHY 参数来自 live 树。修复 `2e406ef`：新增 `DITING_LIVE_DTB`，`build-diting-wifi-native.py` 优先读它；workflow package env 指向 `$RUNNER_TEMP/diting-live.dtb`。
- 音频可缺省：`prepare-diting-audio.py` 在 `tfa98xx.cnt` 缺失时写哨兵 profile 并跳过；手机 `/vendor` 确实没有 TFA 容器（DTB 音频是 Qualcomm WSA），`POWER` 仍能编译出电量/背光。
- 私有固件：QCA6490 的 222 个文件（`amss/amss20/m3/regdb/bdwlan*`，解包 25.7 MB，压缩 7.2 MB）放在私有仓库 `nagatoquin33/diting-firmware` 的 release `fw-20261111`；公共仓库用 `FIRMWARE_TOKEN` secret 拉取，固件不进公共仓库。`stage-diting-firmware.py` 允许只带部分分组（wifi）。
- 全开配置：`diting_ipados18_defconfig` 进入 CI 选项；`board.toml` 的 `cpus=1` 改为 `cpus=8`，并加 `diting_wifi=1`、`diting_adreno_start=1`、`diting_metal=1`。
- 新 run `43068678253`（`2e406ef`）验证以上修复。

# 工作方法（长期有效，不可省略）

以下方法不因阶段或目标改写而失效；每次改 objective/交接时必须保留。

1. 先读 unixnu.com 官方文档与 Sheng/UniXNU 上游实现，按文档契约修改；不靠猜测，不用“关掉功能/哨兵”绕过阻塞。
2. 本地能验证的先本地验证（静态检查、离线校验、DTB/固件/配置比对），再走 CI。
3. 每次失败先读日志定位根因；同一批问题一次改完，只派发一次；禁止重跑碰运气，网络性失败在步骤内重试。
4. 证据、哈希、阻塞与具体条件写入本文件；未在真机观察确认，不声称成功。
5. 用 Advanced Logger/ramoops 等日志取证，不拍屏；分区写入/刷机前必须得到明确授权。
6. 保留 Pong 来源说明与许可证合规；不把厂商 blob 提交或发布到公共仓库。
7. 以 Sheng 上游为参照消除重复劳动，对比架构与工具链；不为“看起来完成”而删减范围。

# 2026-11-12 上游同步、本地工具链与固件对照

- 上游同步：`UniXNU-sheng` 从 08cde20 fast-forward 到 upstream `e893717`（429 个提交）；`UniXNU` 核心 `diting-release-fd` 与 `origin/main` 合并（252 个上游提交 + 5 个 fork 提交），冲突 `scripts/build-xnu-4k-baseline.sh` 已解决（保留 MACHINE_CONFIG 变量 + 上游 APP_VOLUME_UUID）。
- 本地 XNU 工具链：`xnu-linux-toolchain` bootstrap 成功（mig/cctools/ld64/libtool/tcsh/lzfse/iig/plutil/xcrun shim）；依赖装在 `~/.local/xnu-linux-deps`（autoconf/automake/BlocksRuntime，libdispatch 源码编）。本地 `defconfig/status` 已跑通。
- 本地构建卡点（工具链 known gap）：`linux-host-tools.patch` 需要 `$(HOST_SDKROOT)/usr/include/compat/hostcompat.h` 和 `usr/lib/libhostcompat*`、`libuuid*`，来自 Xcode macOS SDK。该卡点在 2026-11-12 下午的本地构建中已越过（见下方 16:15 A3 证据条）；越过它的具体环境条件（`HOST_COMPAT_*` 变量与本地工具链）未逐项复核，机制标"未观察"。
- 固件对照（2026-11-12 16:15 核实）：内核槽 = `gzip(112 B BootShim + 3,145,728 B FD)` + 追加 DTB。旧镜像（greenI2 / 舞台 1）内核槽 514,459 B sha `6fd3463a…`；CI bring-up 内核槽 514,470 B sha `af179bf8…`。**CI 与 CI 的两份 FD 都是 3,145,728 B，解包 99 个 FFS 文件后只有 `SmBiosTableDxe` 不同**；`DarwinBoot` PE（30,720 B，sha `04bd7879e854…`）、`UniXNU`、`UniXNUDxe`、`UniXNURamDiskDxe` 字节相同（`build-work/evidence-20261112-darwinboot/fv-diff.txt`，本机 `fvwalk.py` 复跑）。11 B 的槽长差全部来自 DTB（49,913 vs 49,947 B），与固件无关。
- 固件对照的判据更正（2026-11-12 16:36，B1；同时更正计划 §1.1 的表述）："只有 `SmBiosTableDxe` 不同"只在 **CI 与 CI** 之间成立；跨工具链不成立——本机 clang 21.1.8 与 CI 的 ubuntu-24.04 clang 18（都开 `-flto`）使同一份源码的 99 个 FFS 文件里 52 个不同。判断 loader 改动必须用**同工具链对照**：vendored loader + `darwin-boot-diting.patch` 的控制卷（`dcbba1d2…`）vs B1 卷只差 **1 个文件**（`DarwinBoot` PE 29,696 → 32,256 B）。完成标准是结构对照（同工具链 FFS 差集 + checker + 段表/kext 列表/UUID），**不是**与 CI 字节一致。
- payload 的 `kernel.macho` **并不相同**：三份大小都是 51,793,920 B（固定填充），sha256 greenI2/舞台 1 `00768ed6…`（`DEVELOPMENT_ARM64_PONG`）、CI bring-up `6399f2ca…`（`DEVELOPMENT_ARM64_DITING`），Mach-O 32 B 头相同、内容不同（2026-11-12 16:15 从两份 payload FAT 取出重算）。
- "菜单选 iOS 失败"的根因不是"CI 新固件"本身：两份 FD 里的旧 DarwinBoot 都仍用 `pong-allocatable-ram`/`pong-audio-dma`/`pong_ram_banks`，与 payload ADT 的 `darwinboot-memory-ranges`/`diting-allocatable-ram`/`diting-audio-dma` 不一致，`PARSE ADT` 拒绝（计划 §1.1；屏幕原文尚未取到，标"未观察"）。对照卷（vendored loader + `darwin-boot-diting.patch`）的 PE 里这三个 `pong-*` token 仍在、`diting-*` 全无（`build-work/evidence-20261112-b1/loader-token-scan.txt`），所以"给旧 loader 打 patch"不可行，必须整体替换 package——B1 已按此做。
- 混合镜像 `D:\ai\diting\build-work\diting-hybrid-oldfw-newpayload.img`，sha256 `B2E270DE…`（旧固件 `6fd3463a…` + 新 payload `cfeb7e83…`，`timeout=0`）：内核槽与 stage-1 镜像字节相同，DarwinBoot 也与 CI bring-up 字节相同，会以同样方式失败。**取消该对照，不再为它占用一次真机启动**（计划 §1.2）。
- 卡点：设备不在 fastboot。真机下一步只排 C1（B1 修正镜像）一轮；Mac SDK 文件不再是首选路径。

# 2026-11-12 16:15 — 配方单一来源、Linux 工具链适配、本地 bring-up 内核与 loader/ADT 检查

## A1 — 15 个构建配方收归 `scripts/`
- 输入：设备仓 `/home/nagatoquin/unixnu/diting-ci`（HEAD `62ff5ba`，工作区未提交）；15 对配方 `scripts/<name>` 与 `kits/DitingPlatform24/build-support/merged-scripts/<name>`。逐对差异：`D:\ai\diting\build-work\evidence-20261112-scripts\diffs\<name>.diff`；清单 `pair-list.txt`、汇总 `summary.txt`。
- 命令：`diff -u scripts/<name> kits/DitingPlatform24/build-support/merged-scripts/<name>`（15 对）；`kits/DitingPlatform24/build-with-runtime.py` 改为 `(device/'scripts').rglob('*')` 递归拷贝，且 `build-support/merged-scripts/` 只要还有文件就 `SystemExit`；`git rm -r kits/DitingPlatform24/build-support/merged-scripts`（本地已删空）。
- 观察：15 对同名脚本全部不同，差异合计 +379/−113 行（`summary.txt`）；合并后 `scripts/` 保留两边的实质改动（`62ff5ba` 的 Adreno 固件 fail-fast、`local.toml` refer 覆盖、`patches/xnu` + `patches/xnu-ipados18` 双目录补丁、SMMU4K 归档与链接、power/wifi 依赖 fail-fast）。`porting.toml` 的 `paths` 原列 `kits/DitingPlatform24/build-support/merged-scripts/**`，lead 已在 2026-11-12 16:2x 删除；`/build-work/` 也同时加入 `.gitignore`，C1 无需再补这两处。本记录取代 2026-11-09 02:30 条中"实际运行的是 merged 副本"的路径描述。同一文件现在还包含 A4 的 `stage_prelink_tool()`（A 主题），提交拆分时 `build-with-runtime.py` 要按 hunk 拆到 C1 与 C5。
- 结论：配方单一来源在本地成立，kit 在仍有重复副本时拒绝构建；未跑一次完整 kit 打包，属局部验证。
- 下一步：integration 按 `review.md` 的主题拆分提交；A 在 `0ce9779` 上继续收敛。

## A2 — Linux 主机工具链适配（Mac-only 配方可在 Linux 执行）
- 输入：`scripts/linux/TargetConditionals.h`（4,095 B，sha256 `2dbd9a68…`，与核心 `UniXNU/scripts/linux/TargetConditionals.h` 相同）；工具链 `~/.local/xnu-linux`（`xnu-linux-toolchain/env.sh`，`HOST_CC=/opt/unixnu-linux/CommandLineTools/usr/bin/xnu-host-cc`）。
- 命令：`source ~/unixnu/xnu-linux-toolchain/env.sh`；`./unixnu defconfig diting_ipados18_bringup_defconfig -D ../diting-ci`；`./unixnu build kernel -D ../diting-ci`（环境：`DITING_KERNELCACHE=$HOME/unixnu/UniXNU/out/ipsw/22H374/kernelcache.decompressed`、`DITING_VOLUME_LAYOUT=$HOME/unixnu/volume-layout.json`）。
- 观察：`build-diting-armcpu-macos.py`、`build-diting-platform-macos.py`、`build-diting-ufs-ipados18-macos.py`、`build-diting-ram-block-macos.py` 的主机守卫改为 `platform.system() != 'Darwin' and != 'Linux'`；`build-diting-platform-macos.py` 与 `build-ipados18-diting-macos.py` 把 `TargetConditionals.h` 装进 fakeroot/构建树；`build-ipados18-diting-macos.py` 在 kit 过滤环境变量时保留 `UNIXNU_SHIM`/`UNIXNU_HOST_CCTOOLS_INCLUDE`/`UNIXNU_SDKROOT` 和 `XNU_LINUX_*`；`build-xnu-ipados18.sh` 在 Linux 上导出 `UNIXNU_SDKROOT=$KERNEL_SDKROOT`（fakeroot）并安装同一头文件。构建成功（见 A3）。
- 结论：Linux 侧夹具可用；Mac CI 路径未在 macOS 上重跑，标"未观察"。
- 下一步：Linux 与 macOS 产物只做结构对比，不要求字节一致。

## A3 — 本地 bring-up 内核能编过，但当前不能作为启动候选
- 输入：本地核心 `/home/nagatoquin/unixnu/UniXNU` @ `fa71574`（`sync/upstream-20261112`，未推送）；CI 同版核心 `/home/nagatoquin/unixnu/xnu-ci-core`（worktree，detached `0ce9779`）；`DITING_KERNELCACHE` 48,562,176 B sha256 `aa65c36c486a8b5cb1d7a2d565d1d6b3cc228b3c172f8c69c5da664ee19832cf`；`volume-layout.json` 253 B sha256 `dfbe996c…`；配置 `diting_ipados18_bringup_defconfig`。
- 命令：`./unixnu build kernel -D ../diting-ci`；`python3 scripts/check-storage-bindings.py kernel/kernel.macho`；`otool -l`。
- 观察：`fa71574` 产物 `mach.development.diting` 16,955,064 B sha256 `f1b923dc5e5eb52293340776cc88e26c44ea42513422933f60ec7cff209c69f4`、`kernel.macho` 50,896,896 B sha256 `700e8e37f9c2c484eaea81c0200d5e0f880aef626744dc006232c49b61340871`；`check-storage-bindings.py` FAIL 2 项（`__PRELINK_INFO` 不在所有预链接段之后；`AppleARMCPU` 仍与 ArmCpu 争用 CPU 节点）。`0ce9779` 产物 `kernel.macho` 50,896,896 B sha256 `fcf4205f51858cb488620a1bb1255a17931bd72e448ec9d6832177563e807347`，同样 FAIL 2 项。CI bring-up 内核 51,793,920 B sha `6399f2ca…` 通过；`otool -l` 的 `__TEXT` vmsize 0x178000 / `__TEXT_EXEC` 0x8a8000，本地 0x174000 / 0x864000，文件小 897,024 B。版本串 `DEVELOPMENT_ARM64_DITING` 与三个卷 UUID 字符串都在。
- 结论：两项失败与核心 SHA 无关；根因不是 Linux 预链接器语义，而是本地构建没执行 CI 的 `scripts/install-unixnu-inputs.py`，`kits/XnuPrelink` 缺两处补丁（见 A4）；修复后两个核心的检查器都 PASS。未在真机启动（未观察）；C1 仍用 CI bring-up payload + B1 修正 FD。
- 下一步：见 A4；本地内核不作为 C1 候选。

## A4 — `check-storage-bindings.py` 两项失败的根因与修复（task-2，2026-11-12 16:35）
- 输入：设备仓 `62ff5ba`；核心 `UniXNU` @ `fa71574` 与 `xnu-ci-core` @ `0ce9779`；`DITING_KERNELCACHE` sha256 `aa65c36c…`；证据 `D:\ai\diting\build-work\evidence-20261112-prelink\README.md`（`exp1/`、`rebuild-ci-core.log`、`rebuild-unixnu.log`、`size-decomposition.py`、`compare-kexts.py`）。
- 命令：`./unixnu build kernel -D ../diting-ci`（环境同 A2，另加 `LD_LIBRARY_PATH=~/.local/xnu-linux-deps/lib:…`、`HOST_COMPAT_CFLAGS=`/`HOST_COMPAT_LIBS=`、`HOST_CSH=tcsh`、`HOST_FLEX=flex`、`BISON=/usr/bin/bison` 等）；`python3 scripts/check-storage-bindings.py kernel/kernel.macho`；`git -C <core> status kits/XnuPrelink`。
- 观察：CI 的 macOS 内核用**同一个** Python 预链接器，能通过检查只是因为 workflow 在构建前跑了 `scripts/install-unixnu-inputs.py`（`fix_prelink_info_extent` :70-90、`fix_apple_cpu_match` :93-113）；核心钉住的 XnuPrelink（UniXNU `440589b` / CI `b74ed7c`）都缺这两处。修复在 `kits/DitingPlatform24/build-with-runtime.py` 新增 `stage_prelink_tool()`：把 kit 复制到 `<tree>/.cache/diting-prelink-kit`，施加与安装脚本**逐字相同**的两处文本补丁，再把构建树里的 `kits/XnuPrelink` 链接指向副本；核心 checkout 不动（`git status` 干净），CI 若已打过补丁则幂等返回。重建结果：`0ce9779` 最终态 `kernel.macho` 50,896,896 B sha256 `cc4ce8e2813eab4071c004ec142df67d984203925f1188f7597d8e39423a08b7`、`mach.development.diting` 16,955,064 B sha256 `ee37f7230037114a057d4aedb5e5f038512ea08dd1a089ded2d6046091c7a004`，检查器 PASS；`fa71574` `kernel.macho` sha256 `180f3e222810dd8aace87d7397c3b1813fbf3ebd5178f78401febe585423bf1e`，PASS。同核心、同输入、同配置的两次成功构建 `kernel.macho` sha 不同（`3206ee90…` / `cc4ce8e2…`），该链路不是逐字节可复现；预链接 kext 列表与 CI 多重集相同（34 条 / 22 个 bundle id），`__PRELINK_INFO` 与最后一个预链接段结束地址同为 `0xfffffff00dbb0000`。
- 结论：两项失败不是 Linux 替代 `prelink` 的结构问题；验收判据是检查器 + 结构对照（段表、kext 列表、三个卷 UUID、`DEVELOPMENT_ARM64_DITING`），不能与 CI 或上一次构建比哈希。
- 下一步：task-4 **已修复并验证**（拆分里是 C6）——`scripts/build-xnu-ipados18.sh` 在 forward `git apply --check` 与 fuzz 回退之间新增 `git -C .cache/xnu-work apply --reverse --check -C0` 分支，命中即打印 `Already applied: <patch>`；文件 sha256 `574063fc94ad111c3a09129b378cb7ac75309f5a545bf91217b5f2875bc7a25e`。验证：全新树（`rm -rf .cache/xnu-work`）构建 exit 0、紧接着第二次构建 exit 0，日志 `build-20261112T084641Z.log` 第 6 行 `Already applied: 0000-linux-link-shims.patch`，无反向应用、无 `___cxa_atexit`/`___llvm_profile_*` 未定义符号，`check-storage-bindings.py` PASS；两次 `kernel.macho` 都是 `cd3147a8f31d2a64a4cee5bd6b23eba36e82b85e1928a6c6caa20964f01bc514`，但验收判据仍是 checker + 结构对照，不是哈希相等。剩余已知限制是本地原生链接不是逐字节可复现（A4 里同输入两次成功构建 `3206ee90…`/`cc4ce8e2…`），所以证据一律用结构。

## B1 — DarwinBoot24 修正 FD 与镜像离线产出；合约检查对新镜像 PASS（2026-11-12 16:36）
- 输入：`~/unixnu/uefi-b1-tree`（uefi-mondrian `e06211d`，submodules 已初始化）；loader 源 `drivers/DarwinBoot24/DarwinBootPkg`（FFS UI 名 `DarwinBoot24`）；旧 CI bring-up 镜像 `artifacts/ci-42994674560/…/boot/diting-unixnu-uefi.img` 101,191,680 B sha256 `e9b615bf…`（FD `1e443d09…`，payload PONGFAT1 `cfeb7e83…` CRC `0x4da7f1ab`，DTB `ef77a551…` 49,947 B）；证据目录 `build-work/evidence-20261112-b1/`。
- 命令：`bash scripts/linux/build-diting-fd.sh --uefi-dir ~/unixnu/uefi-b1-tree --device <repo> --out build-work/b1-fd`；`python3 scripts/build-bootimg.py --shim … --mkbootimg … --config … --fd build-work/b1-fd/SILICIUM_UEFI.fd --dtb <e9b615bf 的 DTB> --ramdisk <e9b615bf 的 PONGFAT1> --output-dir build-work/b1-darwinboot24`；`python3 scripts/patch-boot-payload-args.py --image …/diting-unixnu-uefi.img --output …/diting-unixnu-uefi-darwinboot24.img --set diting_usb=0`；`python3 scripts/check-loader-adt-contract.py <old>` 与 `<new>`；`rebuild-verify.sh`（`rm -rf Build` 后重跑 `build_uefi.py`）。
- 观察：FD 3,145,728 B sha256 `c6b6c43c47d591526ba84a2802fd7104302bd0084a237b08e678e0251456487d`，清空 `Build/` 同源码重建得到同一 sha → 本地可复现。BootShim 112 B sha256 `9fad1c8c5d009b71cdc5165a9991c8ad93135ef04bdcc77cbf876fd270172018`。最终镜像 `build-work/b1-darwinboot24/diting-unixnu-uefi-darwinboot24.img` 101,187,584 B sha256 `285e6afa1f4291f10839619fbc06d09ce08842ac14d7143be20756d4c8f106fa`；与未改 args 版本（`62a353d5…`）相比只有 `diting_usb=1`→`0` 一个 token（39 个 token 位置不变），PONGFAT1 CRC `0xc9b35b22` 计算一致，manifest SHA-384 `0c5f242c97…` 与 ADT `boot-manifest-hash` 一致。检查器：旧 `e9b615bf` rc=1 FAIL 7 条（loader 名不是 `DarwinBoot24`、缺 3 个 `diting-*`、仍带 3 个 `pong-*`；payload 侧通过）；新镜像 rc=0 PASS。同工具链控制卷（vendored loader + `darwin-boot-diting.patch`，`dcbba1d2…`）vs B1 卷：99 个 FFS 只有 `DarwinBoot` 一个文件不同（PE 29,696 → 32,256 B）；CI 卷 vs 本地控制卷 52/99 不同，纯粹是 clang 21.1.8 vs ubuntu-24.04 clang 18（都 `-flto`）。loader 身份：旧 CI PE 30,720 B `04bd7879…`、控制卷 29,696 B `a82d2e84…`（`pong-*` 三 token 全在、`diting-*` 全无）、B1 卷 32,256 B `7b65f1d5…`（`pong-*` 全无、`diting-*` 全在）。注意 checker 的 "loader UI name" 只是 PE 内字符串判据；FFS UI 名 `DarwinBoot24` 由 `dump-ffs-ui.py` 单独验证。`scripts/linux/build-diting-fd.sh` 现有 13,657 B 版本（新增无 root 的 venv/pip 引导与 mu_nasm 预置）。
- 结论：修正 FD 与修正镜像已离线产出并通过合约检查；`darwin-boot-diting.patch` 不会把 ADT 契约 token 从 `pong-*` 改成 `diting-*`，给旧 loader 打补丁不可行，整体替换 package 是正确路线。真机屏幕（`DARWINBOOT24 REQUEST` / G2）**未观察**——C1 尚未执行。
- 下一步：C1 用 `build-work/b1-darwinboot24/diting-unixnu-uefi-darwinboot24.img`（`285e6afa…`）按 runbook `fastboot boot`，期望先出 `DARWINBOOT24 REQUEST`；`diting_usb=0` 首轮只验证合约，USB 交接（C2）另开一轮。CI `firmware` job 仍内联流程；把 CI 切到 `scripts/linux/build-diting-fd.sh` 是单独一次变更。

## 2026-11-12 16:3x — 补丁副本状态（lead 已裁定）
- 输入：`xnu-linux-toolchain/patches/xnu/*.patch`（工具链侧的通用版）；本仓 `patches/xnu/*.patch`（按 XNU 11417 与 Linux tcsh 工具链改写的移植版）与 `patches/xnu-ipados18/0000-*.patch`（同一批文件的 `0000-` 前缀副本）。
- 命令：`cmp` 逐个比较；`grep -c 'DOCONF_EXCLAVES'` 与 `grep -c 'HOST_CSH'` 对比两版；`grep` 查看 `scripts/build-xnu-ipados18.sh` 的补丁应用循环。
- 观察：本仓 `patches/xnu/linux-host-tools.patch` 里 `DOCONF_EXCLAVES`/`DOCONF_SPTM`/`DOCONF_KERNEL_TAG` 共出现 16 次，工具链源为 0 次（`HOST_CSH` 两版各 9 次）——本仓拷贝是**更新的移植版**，不是过期副本；其余 4 个与工具链源相同。`build-xnu-ipados18.sh` 的 `PATCHES=("$ROOT"/patches/xnu/*.patch "$ROOT"/patches/xnu-ipados18/*.patch)` 会同时拿到两套同名补丁，靠 `git apply --reverse --check` 的 "Already applied" 分支跳过第二次；`patches/xnu-ipados18/0000-*` 不在 `series` 里，只由 glob 应用。
- 结论：`patches/xnu/*` 以本仓移植版为准，**不得**用 `xnu-linux-toolchain/scripts/sync-patches.sh` 覆盖（会破坏 XNU 11417 本地构建）。C4 只提交 `patches/xnu/*` 5 个文件；`patches/xnu-ipados18/0000-*` 继续留本地，因为 macOS CI 会把它们当板级系列一起应用，`link-shims` 的 `__llvm_profile_*`/`__cxa_atexit` 是否与 macOS 链接冲突未验证（未观察）。
- 下一步：`build-xnu-ipados18.sh` 加 `uname -s` 守卫、只对 Linux 应用 `0000-linux-*` 是后续单独一轮，完成后再考虑是否把 `0000-*` 入库。

# 2026-11-12 17:4x — D1：release 配置本地链接通过，`_diting_adreno_start_optional` 已解析

- 输入：核心 `/home/nagatoquin/unixnu/xnu-ci-core` @ `0ce9779`（worktree）；设备仓 `/home/nagatoquin/unixnu/diting-ci` @ `46898d1`（`62ff5ba` 是祖先）；配置 `configs/diting_ipados18_defconfig`（POWER/BACKLIGHT/WIFI/ADRENO/ARMCPU/ARM_DT/NATIVE_UFS=y）；kernelcache sha256 `aa65c36c486a8b5cb1d7a2d565d1d6b3cc228b3c172f8c69c5da664ee19832cf`；`volume-layout.json` sha256 `dfbe996c…`（`ci_placeholder: true`）；原始 live DTB `b137505a…`、`dtb-fixups/apply.py` + `dtc` 之后 `cca8bd62ae8ae41078329bf72ff8150886a05418edb75c55ef5a859db06d1977`；Adreno 固件 5 个输入与 staged Wi-Fi 固件的 sha256 见 `build-work/evidence-20261112-adreno/inputs-hashes.txt`；证据目录 `build-work/evidence-20261112-adreno/`（README、link-evidence.txt、kernel-hashes.txt、check-storage-bindings.txt、logs/ 5 次运行）。
- 命令：环境按 `build-release5.sh`（`source ~/unixnu/xnu-linux-toolchain/env.sh`、`LD_LIBRARY_PATH=~/.local/xnu-linux-deps/...`、`HOST_CC=/opt/unixnu-linux/CommandLineTools/usr/bin/xnu-host-cc`、`HOST_COMPAT_CFLAGS=`/`HOST_COMPAT_LIBS=`/`HOST_OS_VERSION=1.0`、`HOST_CSH=tcsh`、`HOST_FLEX=flex`、`BISON=/usr/bin/bison`、`DSYMUTIL=/usr/bin/dsymutil`；`export DITING_KERNELCACHE=…; export UNIXNU_KERNELCACHE=$DITING_KERNELCACHE`；`DITING_LIVE_DTB`/`DITING_HARDWARE_DTB` 指向 fixup 后 DTB；`DITING_ADRENO_FIRMWARE`、`DITING_WIFI_FIRMWARE`、`DITING_WIFI_SOURCE`/`DITING_WIFI_SHARED`/`DITING_SHENG_ROOT`）；`./unixnu defconfig diting_ipados18_defconfig -D ../diting-ci`；`./unixnu build kernel -D ../diting-ci`；`python3 scripts/check-storage-bindings.py …/kernel/kernel.macho`。
- 观察：第 5 次运行（`logs/build5-20261112T093618Z.log`）exit 0；`_diting_adreno_start_optional` 由 `libDitingAdrenoPlatform.a(DitingAdrenoPlatform.o)` 定义（`nm`：`0000000000000000 T _diting_adreno_start_optional`），链接后的 unstripped 内核符号为 `fffffff008fdd428 S _diting_adreno_start_optional`，链接日志 `Undefined symbols` 出现 **0** 次，`nm -u` 聚合无 adreno 未定义符号；archive 每个成员都有 `-force_load` 的 ld warning 记录，证明归档确实进了链接。调用点本来就在 `#if XNU_DITING_ADRENO_PLATFORM`（`drivers/ArmDTPlatform/ArmDTPlatform.cpp:252-254`），`62ff5ba` 的 fail-fast 解析 + archive 构建/`-force_load`（`scripts/build-xnu-ipados18.sh:1037、:1081、:1151`）提供定义；`drivers/**` 未改动（`git status drivers` 干净）。产物：`kernel.macho` 73,666,560 B sha256 `339d276094d6dd72f365bb5f039d4a3c3a148d9249026b55057b6014d3b6131c`（本地 Linux prelink 输出，不是 CI 固定的 51,793,920 B），`mach.development.diting` 39,723,432 B sha256 `0477ce0a7bad1f7e83188a89fe7e6c461316a4c701d3ebcd93bd904fbdcb2be4`，`kernel.json` 6,693,634 B sha256 `8b3aab41…`；`check-storage-bindings.py` PASS（"9 个存储绑定位于映射段，预链接信息位于组件之后；仍需核对运行时行为。"）。run 1→4 的每个真实错误与修法见该 README 的 run matrix。
- 结论：计划 §3D1 的 release 链接前置已解决，且不需要改驱动：`ADRENO_PLATFORM=y` 时 archive 会被构建并 `-force_load`，缺固件在构建前 fail-fast，符号既没被静默禁用也没被丢掉。本地 `kernel.macho` 是 Linux prelink 产物，验收用结构门（段表/kext 列表/UUID/检查器），不与 CI 比字节。真机未观察（没有启动）。
- 下一步：下一道未执行的 package.yml 阶段是 v4 容器 `scripts/finalize-diting-adt.py`，需要 B1 的 `SILICIUM_UEFI.fd`（已有）、私有的 `UNIXNU_UNIQUE_CHIP_ID` 和非占位 volume layout，本轮未尝试。

## 2026-11-12 17:4x — 本地运行的输入契约（D1 实操记录）

- (a) `DITING_LIVE_DTB` 必须是 `platform-firmware/dtb-fixups/apply.py` + `dtc` 之后的 DTB（`cca8bd62…`）；直接用原始 `/mnt/d/ai/diting/fw/diting-live.dtb`（`b137505a…`）会在 `scripts/prepare-diting-wifi.py:54` 报 `KeyError: 'wlan-enable-gpios'`（缺 pci-msm fixup 的属性块）。
- (b) 核心 kit 的预链接读 `--kernelcache`/`UNIXNU_KERNELCACHE`，**不是** `DITING_KERNELCACHE`；只设后者时 prelink 回退到 `ipsw.Ipsw(ctx)` 走 HTTPS 并报 `urllib.error.URLError: SSL UNEXPECTED_EOF`。本地构建两个都导出。
- (c) 工具链 shim 现在支持 `xcrun -f clang`（lead 修了 `xnu-linux-toolchain/toolchain/xcrun` 与 `~/.local/xnu-linux/bin/xcrun`）。D1 run 1 的 `clang: error: no input files` 是旧 shim 只认 `-find/--find` 造成的；证据目录里临时 `bin/xcrun` 只用于复现早期迭代，现在不需要。

# 2026-11-12 18:2x — 纯 Linux 组装 RELEASE v4 启动镜像（无 hdiutil）

- 输入：设备仓 `/home/nagatoquin/unixnu/diting-ci` @ `3c9fd04`（工作区未提交）；核心 `/home/nagatoquin/unixnu/xnu-ci-core` @ `0ce9779`（release kernel `339d276094d6dd72f365bb5f039d4a3c3a148d9249026b55057b6014d3b6131c`，73,666,560 B）；B1 FD `c6b6c43c47d591526ba84a2802fd7104302bd0084a237b08e678e0251456487d`（3,145,728 B）、BootShim `9fad1c8c5d009b71cdc5165a9991c8ad93135ef04bdcc77cbf876fd270172018`（112 B）、plan §3B DTB `ef77a551…`（49,947 B）、B1 镜像 `285e6afa…`（运行期读 platform seed 与 DTB）；`volume-layout.json` `dfbe996c…`（`ci_placeholder: true`）；新脚本 `scripts/build-release-image-linux.py`（19,325 B，sha256 `9f6cf2ec0f3af57f5644be3e4ae755c196a8064f9e381facb876385580b7cbca`）；证据目录 `build-work/evidence-20261112-release-image/`（README、invocation.log、summary.json、verification.json、repro-compare.json、images/）。
- 命令：`python3 scripts/build-release-image-linux.py --core ~/unixnu/xnu-ci-core --kernel <core>/out/diting/ipados-18.7.10-22H374/diting_ipados18/kernel/kernel.macho --b1-image build-work/b1-darwinboot24/diting-unixnu-uefi-darwinboot24.img --fd build-work/b1-fd/SILICIUM_UEFI.fd --shim build-work/b1-fd/BootShim.bin --mkbootimg build-work/b1-fd/mkbootimg.py --firmware-config build-work/b1-fd/diting.toml --volume-layout ~/unixnu/volume-layout.json --output-dir build-work/evidence-20261112-release-image`（`logs/invocation.log` 是显式参数全文；脚本内所有设备输入都是必填 flag 或 `DITING_*` env —— `DITING_B1_IMAGE`/`DITING_FD`/`DITING_BOOTSHIM`/`DITING_MKBOOTIMG`/`DITING_FIRMWARE_CONFIG`/`DITING_VOLUME_LAYOUT`，`--output-dir` 默认 `<cwd>/release-image`，无机器绝对路径、无 build-work 默认值）。
- 观察：两个 v4 镜像均 101,187,584 B：cpus8 `36bdd2738e34d85807ae457eaf42c99a0fd3990128c8a9e3ccef0bd698869cd2`、cpus1 `4701c1e6688b99293ebb8572713e4abae61d1bc9bf7982dec76eae2ba5e81219`；`check-loader-adt-contract.py` 两个都 PASS，`check-storage-bindings.py` 对 release kernel `339d2760…` PASS；kernel 槽 509,684 B 与 B1 镜像逐字节相同（gzip(112 B BootShim + FD) + DTB）；PONGFAT1 CRC cpus8 `0x377d5c20`、cpus1 `0x7bd7d642`；manifest SHA-384 == ADT `boot-manifest-hash`；ADT 只有 diting token（无 `pong-*`）；boot args 856 字符，含 `cpus=8|1`、`diting_usb=0`、`diting_wifi=1`、`diting_adreno_start=1`、`diting_metal=1`、`diting_ui_software=0`、`diting_software_ui=0`。hdiutil 映射：release 链里唯一的 hdiutil 调用是 `UniXNU/scripts/unixnu/payload.py:91` 的 `skip_setup_seed()`（仅 `--skip-setup` + `--data-ramdisk` 时触发），OS/Data/userdata 那些 hdiutil 步骤属于 `userdata`/`runtime` 的 OPTIONAL_STEPS，release 不跑（`cli.py:12-13`）。platform seed 只在运行期从 B1 ADT `/chosen unique-chip-id` 读取，经 `--unique-chip-id`/`UNIXNU_UNIQUE_CHIP_ID` 传递，日志已 redact，未写入任何仓库文件或证据文件。
- 结论：纯 Linux（WSL Ubuntu-26.04）可以产出 boot-only RELEASE v4 镜像，全程没有调用 hdiutil，也不需要 macOS；合约检查、存储绑定检查、结构对照都通过。**镜像不是跨运行可复现的**：`scripts/make-diting-adt-ipados18.py:197` 的 `boot-epoch = int(time.time())`、`:175` 的 `BNCH = sha384(os.urandom(32))`、`:178` 的 `random-seed = os.urandom(64)` 让 ADT 每次不同；`repro-compare.json` 两次连续构建显示 kernel 槽、payload 内 kernel、`pong-boot-manifest.json`、`unixnu.toml` 完全相同，只有 `boot-epoch`/`random-seed`/`BNCH` 不同。验收判据是 manifest SHA-384 + 结构 + 两个 checker，不是镜像哈希跨运行相等。`hardware_tested=false`，真机未观察。
- 下一步：若需要可复现镜像，给 `make-diting-adt-ipados18.py` 增加固定的 `--boot-epoch`/`--random-seed` 入口（本轮不做，超出 C9 范围）；设备候选仍是 B1 族的 `285e6afa…`/`d416a29c…`/`9c0100bb…`，不是这些 release 镜像。

# 2026-11-12 18:44—22:42 — 首轮真机（C1/C0/C4/C5）与 IOGPUFamily 预链接修复（E1）

## C1 — B1 修正镜像首次真机启动：到达 iOS 主屏幕（Diting 首次），触摸未达成

- 输入：`build-work/b1-darwinboot24/diting-unixnu-uefi-darwinboot24.img` 101,187,584 B sha256 `285e6afa1f4291f10839619fbc06d09ce08842ac14d7143be20756d4c8f106fa`（FD `c6b6c43c…`、BootShim `9fad1c8c…`、DTB `ef77a551…`）；设备 `9e0c2b55`，product=diting、slot=a、unlocked=yes、battery 4032 mV；证据 `build-work/device-runs/2026-11-12-c1/`。
- 命令：`fastboot -s 9e0c2b55 boot <img>`（RAM-only；本轮没有 flash/dd/erase，没有写分区，没有拍屏）。
- 观察：`Sending 'boot.img' (98816 KB) OKAY` / `Booting OKAY` / total 2.714 s，exit 0；设备离开 fastboot 后持续运行（44 s、76 s、2/4.5/24/28 min 复查 adb/fastboot 均无设备，未自行重启回 fastboot）；在场者 19:07 报读滚动内核日志（XNU console 在滚），19:12 报读 `Denied attempt to escape CPU monitor (missing required entitlement)`（22H374 `lsd` 缺可选 entitlement，良性、非 panic），19:17 报读 **iOS 主屏幕与应用图标**；触摸无反应；没有看到 `BOOT FAILED`。`DARWINBOOT24 REQUEST` 横幅原文、`DITING_*` / cache loader / persona 原文、Advanced Logger 导出、电量/亮度数值均 **未观察**。
- 结论：G4（SpringBoard 渲染）首次在 Diting 上被用户直接观察；G2/G3 只能从"console 滚动 + 用户态 lsd 日志 + 主屏幕"推断通过，原文未观察；G5 未达成（触摸无反应）；本轮不能证明任何驱动（WiFi/GPU/Metal/多核/音频）工作。
- 下一步：C0 识别触摸 IC（已完成，见下），C4 按结论修驱动。

## C0 — TWRP 只读硬件识别：Goodix Berlin-D/GT9916 确认，功放未能识别

- 输入：TWRP `build-work/diting-recovery-boot.img` 127,148,032 B sha256 `67cf2dc9d247815bc5be8c33f4c717b5833f13ca93a4d371ce796bfa0c3c2d6a`；设备 `9e0c2b55`；只读，未 mount/backup/reboot/sideload，未写分区；证据 `build-work/device-runs/2026-11-12-c0/`。
- 命令：`fastboot -s 9e0c2b55 boot <TWRP>`；`adb shell cat /proc/bus/input/devices`；`adb shell dmesg`（设备侧带引号的 grep 被 TWRP 的 sh 分词破坏，改为主机侧过滤，等价且不写设备）；`cat /proc/asound/cards`；`getprop ro.product.device`。
- 观察：`goodix_ts` probe 成功；dmesg 原文 `ic type is BerlinD`、`rom_pid:BERLIN`、`pid:9916`、固件 `goodix_firmware_l12`（配置组 `goodix_cfg_group_l12`）、`config_id: 0x631B5025`、`panel_x/y: 1220/2712`、`panel_max_x/y: 12200/27120`、`IRQ:363`、`avdd-gpio[372]`/`reset-gpio[321]`/`irq-gpio[322]`（内核全局号；按 tlmm base 301 折算为 DT 的 71/20/21，base 301 是推断而非本轮直接读出）、SPI `0x990000`；`[ FTS ] TP is goodix` 明确排除 FTS；`/proc/asound/cards` = `--- no soundcards ---`，dmesg 没有 `cs35l41`/`wsa883`/`cirrus` 行。
- 结论：触摸 IC = **Goodix Berlin-D（GT9916）**，不需要写 FTS 驱动；现有 `bsd/dev/diting_goodix.c`（Goodix Berlin-D，Pong 移植）家族方向正确，C4 应按 GT9916/Berlin-D 的固件名、config_id、1220×2712 对齐。功放 **未能识别**（TWRP recovery 未加载音频 codec；`no soundcards` 不等于"没有功放"，CS35L41 vs WSA883x 仍未定）。设备当时仍在 TWRP，回 fastboot 需用户手动按键。
- 下一步：C4 触摸驱动按 C0 结论修；功放需 Android 侧或带 codec 的内核再确认。

## C4 — Goodix 电源/TCS4 修复镜像首轮：再次到主屏幕，触摸仍未恢复（未归因）

- 输入：`build-work/evidence-20261112-touch/image/diting-unixnu-uefi-c4-touch.img` 101,187,584 B sha256 `cd4e5bd47c8b16987beca49e3fb9bdf1cdc658eddb8484c444a5f794c191441e`（bring-up kernel + Goodix IOVDD ldoc2/GPIO71/TCS4/panel-max 修复；FD `c6b6c43c…`、DTB `ef77a551…`、PONGFAT1 CRC `0x8ba37e54`、args 39 token 含 `diting_touch=1`/`diting_buttons=1`，不含 wifi/adreno/metal）；设备 `9e0c2b55`，battery 4237 mV；证据 `build-work/device-runs/2026-11-12-c4/`。
- 命令：`fastboot -s 9e0c2b55 boot <c4 img>`（RAM-only；没有 flash/dd/erase）。
- 观察：`Sending 'boot.img' (98816 KB) OKAY` / `Booting OKAY`，exit 0；+43/64/94 s 复查 adb/fastboot 均无设备，未自行重启；用户 22:20 报读：handoff 正常、**到达 iOS 主屏幕（有图标）**、**触摸仍无反应**、未报告 panic 或 `BOOT FAILED`（按"未上报"记录，不等于没有发生）。`Diting touch:` / `goodix:` console 行、触摸失败的具体阶段（电源 / GENI / IC_INFO / kernel→backboardd bridge）**未观察**。
- 结论：C4 的驱动修复 **没有恢复触摸**（did not restore touch）；在拿到 touch console 行前不归因、不回退驱动改动。G4 再次由用户观察通过（C4 内核）；G5 仍未达成。
- 下一步：取 `Diting touch:` / `goodix:` 行（Advanced Logger 或下一轮屏幕报读），按 `evidence-20261112-touch/README.md` 的决策树定位。

## C5 — release 全开镜像首轮：panic `Undefined kernel instruction`（IOGPUFamily 未预链接）

- 输入：`build-work/evidence-20261112-release-image/images/release-v4-cpus8.img` 101,187,584 B sha256 `36bdd2738e34d85807ae457eaf42c99a0fd3990128c8a9e3ccef0bd698869cd2`（release kernel `339d2760…` 73,666,560 B；args 42 token：cpus=8、wifi=1、adreno=1、metal=1、usb=0、ui/software UI=0）；设备 `9e0c2b55`，battery 4177 mV；证据 `build-work/device-runs/2026-11-12-c5/`。
- 命令：`fastboot -s 9e0c2b55 boot <img>`（RAM-only）。本轮 **不是单变量**：内核、cpus=8、wifi、adreno、metal、UI 路径同时改变。
- 观察：bootloader OKAY；设备持续运行、未自行重启回 fastboot；屏幕 panic（用户照片经 lead 转录，hex 按近似）：`panic(cpu 7 caller 0xfffffff0089b72ab8): Undefined kernel instruction: pc=0xfffffff00be106c8 instr=0 @sleh.c:1215`；紧邻之前是 DITING ADRENO 序列，最后一条 `CP ready: authenticated nonsecure fence result=0 a=0x1 b=0x147de9`（各条 result 全为 0）。离线根因（用户指出、E1 复核）：旧 release kernel 在该 pc 的 `__PLK_TEXT_EXEC` 32 B 全零、`__PRELINK_INFO` 22 entries 没有 `IOGPUFamily`；原始 22H374 kernelcache 在 `pc-slide`（slide 0x5ed0000）是有效 ARM64 指令，owner = `com.apple.iokit.IOGPUFamily __TEXT_EXEC` → `diting_metal=1` 时 `DitingIOAcceleratorMetaConstruct` 落到零填充。
- 结论：panic 的直接原因是没有预链接 `IOGPUFamily` 的 kernel（`instr=0`），不是 8 核或 WiFi 本身；但本轮非单变量，WiFi/GPU 的其它问题不能排除。真机现象已观察；`slide=` / 符号化 caller 原文未取得，panic hex 按近似记录。
- 下一步：用 E1 的 `--prelink-kernel` 出 A（metal=1）/ B（metal=0）对照镜像再上机，单变量确认 panic 是否消失。

## E1 — release kernel 预链接 IOGPUFamily（C5 panic 修复；未上机）

- 输入：E1 前脚本 `9f6cf2ec…`；新脚本 `scripts/build-release-image-linux.py` sha256 `1e0234195faffb872c6887295c308d8246d657caf8d9a48692ab2c1d210ab0d6`（+127/−2）；核心 `xnu-ci-core` @ `0ce9779`；release native aggregate `0477ce0a…`（39,723,432 B，复用，不重链 XNU）；原始 kernelcache `aa65c36c…`（48,562,176 B）；证据 `build-work/evidence-20261112-prelink-iogpu/`。
- 命令：`python3 scripts/build-release-image-linux.py --prelink-kernel --core <core> --kernelcache <aa65c36c…> --cpus 8 …`（完整显式参数与 `--arg diting_metal=0` 的 B 变体见证据 `build-images.sh`）；随后沿用 payload/finalize/bootimg 流程出图。
- 观察：新 kernel `7434c82fb15c61ec0037bdb7b480a1c92fc708bfb759a91d9b3ca49e77b93d6d`（73,719,808 B）；`__PRELINK_INFO` 26 entries，含 `IOGPUFamily`（旧 kernel 22 entries 无）；`pc=0xfffffff00be106c8` 处 32 B = `fd7bbfa9fd030091219efff021940291427600d042ec47f90311805221320094`，与原始 22H374 cache 同地址**逐字节相同**；镜像 A metal=1 `db99450bb23b69f981617a246f4f231b0e20a0fc4b0fe3e95a759c02932b7679`、B metal=0 `414f6cb0406715b2fbaefa900cb1ddcec7d0618dd3d20f557195ea7fb30306d9`（均 101,187,584 B），contract PASS、storage PASS、CRC/manifest true；A 与旧 C5 在 config/manifest 层单变量：args value sha256 `154eca67…` 相同、manifest `bf6d864c…` 相同、kernel 槽相同，只有 payload kernel 变。脚本顺带修了一个确定性缺陷：payload work 目录取核心"当前配置"，配置漂移到 bring-up 时会读旧 payload；现在 payload 前显式 `unixnu defconfig diting_ipados18_defconfig`。镜像 `hardware_tested=false`；A/B 上机后是否还 panic、是否出现 `DITING METAL: real IOAcceleratorES provider published` **未观察**。
- 结论：E1 在离线层面复现并修复了 C5 的零填充地址（新 kernel 同地址 32 B 与原始组件逐字节相同），并给出 A/B 单变量镜像；这仍是离线证据，不等于 C5 已在真机修复。本 E1 就是随后的 C10 提交（脚本 + 本段）。
- 下一步：真机按 A（metal=1）→ B（metal=0）顺序 `fastboot boot`（RAM-only，需用户在场与授权），观察是否仍出现 `pc=0xfffffff00be106c8 instr=0 @sleh.c:1215` 以及是否出现 `DITING METAL: real IOAcceleratorES provider published`；镜像哈希跨运行不可复现，核对 manifest 与结构即可。

## E1a — E1 A 镜像真机首轮：Metal 修复证实，root 挂载 panic（ufs 节点缺失）

- 输入：E1 A（metal=1）`db99450bb23b69f981617a246f4f231b0e20a0fc4b0fe3e95a759c02932b7679`（101,187,584 B，内嵌 kernel `7434c82f…`）；设备 `9e0c2b55`，battery 4258 mV；证据 `build-work/device-runs/2026-11-12-e1a/`（含两张用户照片）。
- 命令：`fastboot -s 9e0c2b55 boot <e1a img>`（RAM-only；无 flash/erase/dd）。
- 观察：bootloader OKAY；+20 s 离开 fastboot 持续运行；屏幕（照片转录，右缘截断标 …）依次出现 `DITING METAL: real IOAcceleratorES provider published`、`DITING METAL: NativeAdreno complete runtime publication status…`、EPSS 八核变频行，随后 ~40× `rootvnode is not set` → `Still waiting for root device` → `panic(cpu 0): Failed to mount root device @IOKitBSDInit.cpp:996`。
- 结论：E1 修复在真机证实——`instr=0 @sleh.c:1215` 不再出现，Metal/IOAcceleratorES 发布成功；新阻塞在 root 挂载。归因（离线）：payload ADT blob 1 缺 `/device-tree/arm-io/ufshc`——`build-release-image-linux.py` 调 `finalize-diting-adt.py` 漏传 `--ufs-probe`（CI `package.yml:458` 必传，构建日志记 `ufs_probe:false`）→ NativeUfs 无 `diting,ufs-*` 可匹配 → 无 IOMedia。非硬件故障、非资源竞争。三个窗口 UUID 已排除（与真机一致）。屏幕证据以用户照片转录，右缘截断处未读全。
- 下一步：E2 修复镜像上机验证 `DITING_UFS: matched SM8475` → clocks/transport → APFS 根卷发布。

## E2 — release ADT 补 ufshc 节点：修复 root-mount 路径（未上机）

- 输入：E1a 根因链（见上）；`scripts/build-release-image-linux.py` finalize 调用追加 `--ufs-probe` 一行（与 CI 契约一致、无条件）；证据 `build-work/evidence-20261112-ufs-adt/`。
- 命令：与 E1 `build-images.sh` 相同参数重建两变体（`--prelink-kernel`、同 relink kernel `7434c82f…`、cpus=8、metal=1/0），输出到新目录。
- 观察（全离线）：`finalize-*.log` 记 `"ufs_probe": true`；blob 1 = 16,536 B，含 `/device-tree/arm-io/ufshc` 全套 Diting 属性（`ufs-hc-base 0x1d84000`、`gcc-ufs-page 0x187000`、`smmu-base 0x15000000`、`smmu-stream-id 0xe0`、`context-banks 0x4e`、`match-groups 0x78`、`ufs-spi 0x109`、userdata LBA `0x2f8a00-0x3adf3fa`）；`root-matching` UUID `B07DF049…`、`diting-touch`/`diting-buttons`/`boot-epoch` 不变；contract PASS、storage PASS、`structure_matches_b1_kernel_slot: true`。镜像：metal=1 `6b0f53c45e32d9263996e9388b715519aadc7cf9aad2b1ca53beabad67299c75`、metal=0 `cf007f172bcd43c1c87abc53da4e4447f2cacc9d4ac4d4aa947994cb9b318f7c`（均 101,187,584 B）。`hardware_tested=false`。
- 结论：离线层面 root-mount 缺件已补齐；是否恢复挂载仍需 E2a 真机确认，不预先声称。
- 下一步：设备回 fastboot、用户在场后 `fastboot boot` metal=1 镜像，用 Advanced Logger/ramoops 取证 `DITING_UFS:`/SHNGROOT/APFS 行；若根卷发布成功，再继续 Metal 结果验证与 WiFi/多核/触摸各单变量轮。

### E2 附记 — release kernel 未含 C4 触摸修复（一致性警告）

- 证据：E2 内嵌 kernel `7434c82f…` 源自 native aggregate `0477ce0a…`（E1 复用）；`strings` 中只有 `ldoc3`/`ldoc12` 旧路径，无 `ldoc2`/GPIO71/TCS4/`IC_INFO` 字符串 → kernel 构建早于 `0001` patch 的 C4 工作区编辑。
- 口径：E2a 上机后触摸若失败，记为 **pre-C4 行为**，不归因 C4 修复无效、不归因 ufs 修复；release kernel 带 C4 重建列为独立待办（需先决定 `0001` patch 的提交策略）。

## E2a/E2dbg — slot b 真机 panic（确定性，已符号化）：坏函数指针跳进 __DATA_CONST dispatchArray

- 输入：E2a（metal=1，`6b0f53c4…`）与 e2dbg-usb1（`c37e0a04…`，同 kernel `7434c82f…` + `diting_usb=1`）。设备 `9e0c2b55`，slot 切 b 后 `fastboot boot` 恢复可用（A 侧引导链状态曾致全部镜像 `Not Found`）。
- 观察：两次启动同屏同寄存器确定性 panic——`Kernel data abort. at pc 0xfffffff007907330, lr 0xfffffff0079f6734, far 0x928, esr 0x96080005`，pid 0 / tid 101；`Compressor Info: 0%`。
- 符号化（slide=-0xDF3A0C，由 caller `0x7ad6660`↔panic 调用点 `0x88ca06c` 数学钉死）：pc→`__DATA_CONST.__const`（`IOUserServer::externalMethod` dispatchArray，执行表数据）；lr→`_kalloc_type_get_heap+0x30`；backtrace：`thread_dispatch→…→c_current_seg_filled→vm_fault_*→zcache_alloc_one→kalloc_type_get_heap→mach_vm_map_wrapped`。即压缩器/页故障路径上一个 **blr 跳进方法分发表**（表项指针被当函数指针调用）。`check-storage-bindings.py` PASS（9 绑定在段内）→ 排除 `ml_static_slide` 先例类。
- 嫌疑（未定性）：未提交的 `0000-portable-kalloc-type-builtins.patch`（直接碰 kalloc_type）；`pmap_pong_pa_index` 物理页索引；压缩器 c_seg/codec ops 读错对象。e2dbg 未出 CDC 口——panic 早于 DitingUsb 枚举或 USB 路径未通。
- 文档勘误（同批）：`porting.toml` 33 个 area 全部是 **Pong（Nothing Phone 2）迁移线**记录（format2 README 即 pong 版换名；services70-167 全含 /pong 路径+TFA9873，零 diting 硬件标记；`UniXNU-diting` checkout 含原始记录）。已逐 area 加 `provenance="pong"`、summary 点名 Pong 来源、新增 `diting-cs35l41-audio`（status=planned，注明 live DT 双 cs35l41 enabled / WSA883x disabled、C1-C4-E2 均未编音频）；`porting-record.py check` 通过。上游 sync-devices 重渲染后生效。
- 下一步：定位 `_kalloc_type_get_heap`+0x2c 的 `blr` 目标来源（kalloc_type 表/描述符索引是否越界）；确认 panic 内核是否带了未提交 kalloc patch；再出新镜像。

# 2026-11-13 — slot b 恢复与 E2a panic 符号化、文档 provenance 修正

# 2026-11-13 — E2a panic 定性更新：嵌套 panic + 确定性内存损坏（非压缩器记账错）

- panic 顺序确认：屏幕 `Original panic string:` 标签 = 嵌套 panic。第一个 panic = `Kernel data abort`（caller 正确值 `0x7bc32a8` → `_sleh_synchronous+0xfe0` 的 panic 调用点；此前照片把 caller 读成 7ad56xx/7af56xx 是 OCR 误读）。第二个 panic = panic 处理中嵌套触发的 `assertf(c_segment_pages_compressed_incore_late_swapout >= 0)`（`_c_decompress_page+0xc10`；`x9=5438` 为源码行号）。
- panic#1 机制：`zcache_alloc_one(zid,flags,ops)` 的 `ops`（x2→x21）取 `ops->zc_op_alloc/zc_op_mark_valid`（`blr x8`）跳转——但保存的 `x21=0x7c21720` → `__TEXT_EXEC`（`_fasttrap_meta_create_probe+0x200`），即 ops 指向代码区。跳转经 `br/braa`（PAC 不改 lr）落 `__DATA_CONST` dispatchArray，执行表项字节解码出 `[NULL+0x928]` 访存 → far=0x928。
- panic#2 机制：`c_has_donated_pages` 在被释放的 c_seg 上为 1——此配置（无 swap、`memorystatus_swap_all_apps=false`、freezer 不跑）下该 flag 永远不可能合法置位 → c_seg 结构被野写。
- 三个独立损坏指纹同源：①坏函数指针跳转 ②c_seg flag 伪置位 ③栈帧链走进 `_diting_wifi_firmware` 数据区 → 大范围内存损坏，不是记账错。
- 更正（2026-11-13）：`0000-portable-kalloc-type-builtins.patch` **实际已被应用**——`PATCHES=(patches/xnu/*.patch patches/xnu-ipados18/*.patch)` 是 glob 不是 series 驱动；该 patch 把 `__builtin_xnu_type_signature→""`、`type_summary→DATA`、`types_compatible→1`，效果是全部类型标 `KT_DATA_ONLY`（签名本就对 data 类型为空）、堆选择仍按真实 sizeof —— 安全机制降级（类型混淆/释放检查失效）但**不是主动野写源**，E1a 能跑到 mountroot 也印证。原记录"不在 series 未应用"作废（series 文件此前缺失 0000-*/0002/0003，已重建为 glob 应用序）。`pmap_pong_pa_index` 只在 pong patch，diting patch 用的是 `pmap_diting_pa_index`（稠密多段索引，实现自洽）；page_shift 静态初始化无时序问题；ml_static_slide 类经 check-storage-bindings 排除。
- 物理内存拓扑：`diting-allocatable-ram` = 14 bank ~11.5GiB（含 4GiB 线以上 `0x840000000..0xa80000000` 9GiB），由 loader `ClaimDitingRam` 认领后写 `darwinboot-memory-ranges` wire（镜像里是零模板，运行时填充）。kernel `diting_ram_init` 对重叠 bank fail-safe 退化为单段线性 → bank 数据本身不是直接根因。
- 最强嫌疑：`--ufs-probe`（E1a↔E2a 唯一差异）。E1a（无 ufshc 节点 → NativeUfs 不起）同 kernel `7434c82f` 跑到 root-mount 超时 panic；E2a（NativeUfs 起：MMIO@0x01d84000 + SMMU takeover@0x15000000 把 stream 0xe0 配成 VA64 bypass 裸 PA DMA + DMA buffer）在更早阶段确定性崩。两条路径：(a) NativeUfs SMMU/DMA 描述符 PA 错→控制器乱写；(b) SMMU takeover 重编程了其他设备在用的 context bank/stream→旁设备 DMA 乱写。确定性（两次同屏同寄存器）偏向逻辑 bug 而非随机 DMA，但 takeover 每次 boot 状态一致→可确定性。
- 下一步（只取证）：对比 E1a/E2a 镜像 ADT `ufshc` 节点 + memory-map/reserved 差异（静态）；核对 0x15000000/0x01d84000 是否为 diting 真实 SMMU/UFHC MMIO（错地址=写 RAM）；若资源无误做"ufshc 节点在但 NativeUfs 不启动"对照镜像隔离 node-presence vs driver-start。

# 2026-11-13 — UFS 隔离实验一：`native-ufs=0` → mountroot（损坏 panic 消失）；上游/文档核查

- 设备 boot `e2dbg-ufs0.img`（e2dbg-usb1 `c37e0a04` + `native-ufs=0`，sha256 `dd7a0cdb`）：驱动在 start() 顶部拒绝 → 一路跑到 `Failed to mount root device @IOKitBSDInit.cpp:996`，与 E1a 同点；压缩器损坏 panic 未发生 → **`ufshc` ADT 节点存在本身无罪，`diting_ufs_transport_start` 运行时路径是损坏触发点**。二级变体 `e2dbg-ufs2.img`（`native-ufs-probe=2`，sha256 `f442b9aa`，只读寄存器不碰 DMA/SMMU/队列）已生成未 boot。
- e2dbg boot args（补丁工具读全）：`diting_ufs_readwrite=1` `diting_ufs_stall=1` `diting_disable_swap=1` `launchd_rd=md0` `cpus=8` `diting_usb=1` —— UFS 写路径开启。
- 上游参照 `UniXNU-sheng/drivers/ShengUfs`（SM8550，官方实现 `NativeUfs`）：diting 驱动是其移植后代。已核实 diting 常量对板正确：stream `0xe0`（live DT `iommus=<0x5b 0xe0 0x00>`）、apps_smmu `0x15000000`（`qcom,qsmmu-v500`，banks 78 / smr 120 = DT override 一致）、HC `0x01d84000`。`dma-coherent`。
- 上游移植契约（unixnu.com/porting/ufs）明确要求 "establish DMA reachability"；上游实测教训："kernel-allocated buffer at 0xf080f000 reset the system, nothing below 0xc8000000 is allocatable"——任意内核 buffer 对 UFS 控制器不一定可达；diting 直接分配新 IOBufferMemoryDescriptor，未收养固件 UTRL（上游 adopt 路径）。
- 已排除：`vm_page_find_contiguous` 用 `VM_PAGE_GET_PHYS_PAGE`（稠密索引→真实 PA），跨 bank 正确断 run；`getPhysicalSegment` 按真实 pnum 相邻性合段；pnum 语义保持真实 PA；四个共享 apps_smmu 的驱动（ufs 0xe0 / usb 0 / audio 0x1801 / wifi 0x1c01）均走 `diting_smmu_lease_lock` 串行 plan+configure，S2CR 全为 TRANSLATE 型互检有效；Adreno 用独立的 kgsl-smmu@0x3da0000。
- 次要发现（非本 panic 根因）：`configs/diting-memory-sm8475.json` 的 allocatable 与 live DT reserved 布局不一致（config 系 REC fdt 派生），与 live DT 保留区有 5 处表面重叠（adsp 42MB / qheebsp 6MB / hyp 1MB / global_sync 1MB / xbl_ramdump）——但认领路径是 `allocatable ∩ UEFI-free ∩ ≥4GiB`，UEFI 若标保留则不会认领。配置应修正对齐 live DT 以防依赖 UEFI 正确性。
- 损坏指纹重申（确定性、两次同屏同寄存器）：①`zcache_ops[zid]`→ops=__TEXT_EXEC 码址→`blr` 跳 __DATA_CONST dispatchArray 执行表数据 far=0x928；②`c_has_donated_pages` 伪置位（无 swap 不可能合法置位）→嵌套 assertf `lateswapout>=0`；③fp 链走进 `_diting_wifi_firmware` 数据区。主嫌疑：UFS 传输开始后控制器 DMA 经错误可达性/描述符拾取野写。
- 待办：boot `e2dbg-ufs2.img` 区分"寄存器阶段 vs 传输阶段"；若确认传输阶段，按上游契约改为收养固件 UTRL PA（UTRLBA 0x50/0x54 读出值）或把 DMA 约束进已证明可达的低区，再验证。

# 2026-11-13b — 仓库整理 + allocatable 保留区勘误

- `configs/diting-memory-sm8475.json`：allocatable 与本仓 `dts/diting.dts` reserved-memory 曾有 6 段自相矛盾的重叠（adsp region23 `0xa0400000-0xa2e00000` 42MB、region24 2.5MB、region26 1MB、ramoops `0xa7000000-0xa7400000` 4MB、region27 `0xe0000000-0xe0600000` 6MB、region29 1MB）。已按**本仓 dts reserved ∪ REC reserved 双集**切割，14→15 bank、边界对齐保留区、剩余重叠 0。注：这些 bank 全 <4GiB，而 `ClaimDitingRam` 每次认领 `MAX(base,desc,0x100000000)` 钳到 ≥4GiB——重叠是死配置不生效，修正属契约一致性/防回归；≥4GiB 三 bank 不受此切割影响。
- `patches/xnu-ipados18/series` 重建为真实应用序（5×0000 + 0001 + 0002 + 0003 + 7×zz*）。`0000-*` 与 `patches/xnu/` 同名文件逐字节相同，是 macOS 布局必需品（`build-ipados18-diting-macos.py` 将 xnu-ipados18 链接为 xnu），已纳入 git 跟踪。
- UniXNU-diting 检出（HEAD `6400a07`，落后 diting-ci 6 天）含 26 文件旧版未提交改动 + 独有 `diting_ipados18_validation_defconfig`、`platform-firmware/basecore-advanlogger.patch`——旧迭代残留，非当前线。

# 2026-11-13c — 文档重读后的事实更正（路线图/交接/执行计划三文档）

- **桌面已到过**：C1 bring-up 镜像 `285e6afa…`（cpus=1、POWER/BACKLIGHT、最小驱动）2026-11-12 真机进 iOS 主屏（G4 门槛已过）；C4 再进主屏但触摸未归因。"进不了桌面"的说法作废——进不去的是"全开"镜像。
- **UFS 单独无罪**：bring-up defconfig 里 NativeUfs=y，C1 带 UFS 在 cpus=1 上工作了全程（launchd 时代到 C1 桌面两次实证）。ufs0（cpus=8+无 UFS）mountroot 是**预期**（无根介质），不是"修复证据"；e2dbg 损坏 panic 的必要条件是 UFS transport，但充分条件疑似 **UFS × {cpus=8, 全开驱动, release-vs-bringup 差量}**。按执行计划 §5，正确单变量下一跳是 **C3 = C1 基线 + cpus=8**——多核是不是协因子一boot便知；e2dbg-ufs2（寄存器 vs 传输）仍有效但优先级降到 C3 之后。
- **userdata 全链可本地**（纠正"还需 macOS"）：OS 窗口内容一次制备需 macOS/CI（`prepare-diting-userland-from-ipsw.py` hdiutil；产物 `diting-ipados18-system.cdr` `27c507c8…` 已在 `D:/ai/diting/artifacts/ci-42987806310`），其余全部 Linux：`make-data-window.py`（sgdisk + `~/apfsprogs/mkapfs/mkapfs`，本机已装）、`make-userdata-image.py`/`build-diting-userdata-image.py`（SHNGROOT 纯 Python）、`make-sparse-image.py`/`flash-userdata-image.py`（Android sparse 刷写）。11-09 的 19GB userdata-root.img 即本地产物。
- **执行计划 §5 分轮表（每轮一变量，设备在场时按此走）**：C1 bring-up 基线（已过 G4/G5 桌面）→ C2 +diting_usb → C3 +cpus=8 → C4 触摸（已跑，未归因）→ C5 +wifi → C6 +adreno → C7 +metal → C8 音频。e2dbg 式全开镜像与该计划矛盾，AGENTS.md:961 已自记"不是单变量"。
- **硬件事实**（C0/TWRP）：触摸 = Goodix Berlin-D GT9916（firmware `goodix_firmware_l12`，1220x2712，IRQ363，GPIO reset20/irq21/avdd71，SPI 0x990000）；功放未定（live DT 双 cs35l41 enabled、wsa883x disabled，Pong TFA9873 不存在）；ramoops@a7000000 在 dts reserved 内。
- **回退资产清单**（阶段0，不得删）：`diting-boot-launchd-unsecure.img` `cb56ac9d…`、`greenI2-log-menu.img`、`prepared-420734-os.img`、`windows/Data.img`（337CF716）、`ipados18-source/{OS,SystemOS,AppOS}.dmg`、`diting-recovery-boot.img`。

# 2026-11-13d — 按官方契约与上游的全仓审视（4 路只读审计 + 可执行检查）

- 方法：对照 `UniXNU/docs/{porting,reference}/` 契约、`UniXNU-sheng` 参照仓、`UniXNU/drivers|kits`、soc-seed；报告全文在 `D:/ai/diting/audit-20261113-本地成果审视.md`。
- 执行验证 PASS：porting-record 检查 33 区、package.sh 与模板字节相同（f7b8e3ea…）、feeds 全 40-hex 钉版、unixnu defconfig 官方 CLI 解析成功、dtc 编译 EXIT=0、kernel_args 806B≤1023、仓内零违例二进制（wifi *.bin 被 .gitignore 正确挡住）、os-profile 与上游同字节、[device] 逐字匹配 board、13 必需区齐。
- FAIL（必修）：①porting.toml:355 `[[areas]]` 复数拼写使 safari-metal-residency159 被 checker/站点静默丢弃；②README_EN 硬件进度表把 Pong 实机结论（触摸/双TFA9873/WiFi/Data128GB）发布为 diting 现状；③README/porting.toml/workflow 的 submodule 叙述已随 vendored 失效（无 .gitmodules）；④DitingAudio 的 TFA9873@0x34/35+GENI 0xa94000 指向不存在硬件（live DT 双 cs35l41@40/42 on i2c@880000，0xa94000 是 disabled 的 ir-spi SE），会真机 NACK/误触；⑤diting-memory-sm8475.json reserved 陈旧（ramoops 写 0x85200000 vs dts 0xa7000000 等 5 处）。
- HIGH（疑似 bug/上游修复缺失）：①reportMediaState 绑 gHost.ready + transportFailure 清 ready → 任一 UFS 错误级联拆光全部介质（services17 同形，DitingUfsTransport.cpp:260/115/548）；②diting_smmu_lease_lock 对 UFS 是 weak_import——DitingPlatformResources 缺席时无串行编程 apps_smmu（:174-177），配合无 root 人格的启动时序构成与 E2a 乱写模型吻合的竞态入口 ★；③diting_ufs_stall=1 在默认 kernel_args，违反自有探针纪律（无界循环）；④ArmCpu 缺上游防御（unowned SPI panic vs 上游计数+屏蔽；drain 256 panic vs 上游 1M 阈值）；⑤DitingUsb 启动被音频类注册门控（DitingPower.cpp:34）；⑥缺 [ipsw.sha256]；⑦board.toml 声明 XnuPrelink 但 6 脚本实际用 kits/NativePrelink 两代并存。
- E2a 关联修正：B 路否定了"固件 UTRL 收养=缺失修复"——上游该路径仅是诊断探针，生产路径同样用内核分配缓冲；当前最高嫌疑改为 lease weak_import + 无 root 人格时序的 SMMU 并发编程入口。
- 修复批次：批1 文档合规（F1/F2/F3+LOW）、批2 配置对齐（F5/H6/H3/glob）、批3 代码修复（reportMediaState 解绑 / lease 硬依赖 / USB 解耦 / ArmCpu 回移 / 音频改 cs35l41 挂 C8 轮）。


## 2026-11-13e — 批2 配置 + UFS 修复（commit 78ff23d）

- `configs/diting-memory-sm8475.json`：`reserved` 按 `dts/diting.dts` reserved-memory 38 节点重建（旧值 REC 派生、ramoops `0x85200000` 陈旧），与 `allocatable` 交集 = 0；base+size 匹配的条目保留原可读名（30 个）。ADT 生成只消费 `allocatable`，此段为描述性数据。
- `board.toml`：新增 `[ipsw.sha256]`——DeviceTree `acf9c611…`、StaticTrustCache `61ce2dc9…`（本地成员实算）；kernelcache/OS 等解压产物不钉（`migration-state image_hashes_used=false` 延续）。`unixnu.lock` 删除 `DitingPlatform24` 条目（本地 kit，lock 只记 git 源）。
- `porting.toml`：paths 属主补 `platform-firmware/**`、`assets/**`、`kits/NativePrelink/**`、`tools/**`、`docs/**` 等；`metal2vulkan/0011` 重号修复——未被脚本引用的 `bounded-command-stage-summary` 改 `0014`。
- `drivers/NativeUfs/DitingUfsTransport.cpp` 三处：
  1. `reportMediaState` 解绑 `gHost.ready`（介质存在性是窗口属性；一次 IO 失败不再级联撤下全部已发布介质——services17 事故形态）
  2. `diting_smmu_lease_lock/unlock` 从"缺席则静默无锁编程"改为硬依赖：符号缺席则 transportFailure（共享 SMMU 写必须串行；无锁路径正是 E2a 乱写模型嫌疑）
  3. `diting_ufs_stall` 从 `for(;;)` 无界改 180s 有界窗口后继续启动（违 optional-probe "return to normal boot" 政策项修复）
- PAC patch 复核：`HAS_NATIVE_PAC` 双门控（`__arm64e__` && `XNU_DITING_NATIVE_PAC`），arm64 构建惰性；arch-darwin24.series 注释明确"设备聚合内携带已适配的 arch 变更"——分层是有意设计，不动。
- C3 镜像已备：`build-work/b1-darwinboot24/diting-unixnu-uefi-c3-cpus8.img` sha256 `e2d298a903606d4f977159dfac85d4f56857fe1dda403bcb41cbc03c366b3af8`（C1 `285e6afa` 仅 `cpus=1`→`cpus=8`，其余 39 token 不变）；`check-loader-adt-contract.py` PASS。设备在场时 `fastboot boot` 即可定多核协因子。
- `diting_disable_swap=1` 复核：patch 实现保内存压缩器、置 `swap_is_present/active/freezer_swap_is_active=FALSE`，与 CONFIG_FREEZE_SUSPENDED_MIN 阈值常量不冲突——配置自洽。
- 待办更新：Sheng `native_ufs_store_*` 持久化导出移植中（RamBlock PersistOverlay 弱引用目前全空、盘内状态易失）；ArmCpu/ArmDTPlatform/DitingPower/Wi-Fi 构建修复在途。

## 2026-11-13e — 批3 驱动/脚本修复全落地（A 方向：iPadOS 18.7.10 坚守）

策略已定：守 iPadOS 18.7.10（Pong 上游已转 iOS 18.6.2/22G100 native arm64e 赛道，userland 重写件留作移植参照）。批3 五路并行子代理交付：

- 8eb77f7 驱动：ArmDTPlatform 上游更新版回移（时钟/RTC/阶段诊断，+135/-5）、USB 启动与音频注册解耦、TFA9873 退役换 CS35L41/WSA（audio serving 保持 0，查询安全返回未就绪）、NativeUfs 新增 DitingStore.h 持久化 store（native_ufs_store_* 6 个 extern "C" 导出供 NativeRamBlock 弱引用；宿主机 fixture 六场景验证过，内核编译未验）。不伪造通道。
- 176bf22 脚本：Wi-Fi DTB 解析顺序 DITING_LIVE_DTB > DITING_HARDWARE_DTB > 编译回退（内核 recipe 会覆写 HARDWARE_DTB，LIVE 优先是刻意）；prelinker 统一到上游 kits/XnuPrelink（diting_paths.py:176-211 新增 unixnu_checkout/xnu_prelink，二进制 tomllib.load 修 Windows GBK）；5 个死脚本标 DEPRECATED。
- dab3157 Wi-Fi 收尾：选中 DTB 缺 12 个 live-tree Wi-Fi 属性时点名失败，不再静默发陈旧 baked 值。
- 40786fc ArmCpu 上游防御回移：unowned SPI 计数+ICENABLER 屏蔽（不再 panic）、排水>1M 仅在 armcpu-diagnostics=1 时 panic（计数无条件）、armcpu_smp_fail[8] 逐核失败码（1 MPIDR / 2 redist / 6 PSCI 拒绝）、CPU_ON 应答核 MPIDR 校验、signalCPU aff0<16 边界。
- 上游对比结论：diting 驱动层不落后 pong-* 拆分仓——UFS 三处修复（reportMediaState 解绑/lease 硬依赖/有界 stall）上游尚无；usb-sm8475.json 命名替换后逐字节相同；power 配置含上游全部新字段。真正差距在 userland 两代重写（BSD 许可、版本锁 22G100）——留作后期移植参照。
- C3 镜像已备：build-work/b1-darwinboot24/diting-unixnu-uefi-c3-cpus8.img sha256 e2d298a9（C1 基线仅 cpus=1->8），loader/ADT 合约 PASS。设备在场后 fastboot boot 定多核协因子；若 SMP 坐实死症再评 iOS 跳转。

- 2026-11-13f 批3 本地编译验证完成：按 AGENTS.md:915 全量环境（xnu-linux-toolchain env.sh + HOST_* + LD_LIBRARY_PATH）跑 `./unixnu build kernel -D ../diting-ci`，exit 0。产出 kernel.macho sha256 1faac405952643adda78308a879b8cf6df79dfb3a2561717bb1a655705f63b4f；check-storage-bindings PASS（9 绑定落映射段）。符号验证：_native_ufs_store_* 8 导出、_armcpu_smp_fail/_armcpu_spi_unhandled/_armcpu_spi_unhandled_id 均链入 mach.development.diting——DitingStore.h 与 ArmCpu 回移在真实工具链下编译+链接通过。踩坑记录：(1) .cache/xnu-work 陈旧补丁态（goodix 后加的 0001 导致部分应用、双向校验皆败）——解法 rm -rf device-tree/.cache/xnu-work 重建；(2) xcrun shim 把 bison/flex/gm4 解析到 /usr/sbin/（本机无此路径）——需显式 export HOST_BISON=/usr/bin/bison HOST_FLEX=/usr/bin/flex HOST_GM4=/usr/bin/m4，AGENTS.md:915 的 BISON 变量名对 MakeInc.cmd 无效（它读 HOST_BISON）。
- 后续提交 40786fc+dab3157+40786fc 后 ArmCpu 收尾两增量（smp_fail=4 注册码、stage5 非覆写守卫）已提交（见 git log）。批3 全部落地：文档/配置/UFS/ArmCpu/ArmDTPlatform/音频/USB/Wi-Fi/脚本/store 十面修复，工作树干净。

# Diting 触控突破与 panic 修复（2026-11-13/14）

## 真机已验证

- iPadOS 18.7.10/22H374 进桌面稳定运行（一次 ≥7 分钟），SpringBoard/backboardd 正常。
- Goodix GT9916 Berlin-D 通电+SPI+固件握手：RPMh 必须投 TCS0 活动槽（ldob12≈1.8V + GPIO71 AVDD 3.2V）；芯片自报 "BERLIN"/"9916" 00.80.02.51。
- 面板配置已在芯片内（config_id 0x631b5025），不需要上传；上传协议仍实现（0x0A/0x0B/0x0C + {csum,0x3e000,len,cfg} 写 fw_buffer_addr）供差异时调用。
- 厂商 DTS 权威报告空间 goodix,panel-max-x/y = 12200x27120；ADT max-x/max-y 已按此改。
- 内核→用户态：/dev/diting-touch 队列，backboardd 内 touch.c（Pong/redwood MIT）注入 display-integrated digitizer 事件，服务被事件服务器打开，TouchDetectionMode 正常流转。
- 触控能用但异常卡顿（2026-11-14，待调优）。

## THP 主机触点处理（本代关键）

- K70 经验包证实 GT9916 坐标计算留给主机 THP 栈：命令 0x90/0x82 请求 firmware-baselined 差分帧；0x90/0 回坐标模式。
- IC-info（0x10070）misc 块偏移：cmd_addr +0、fw_state +12、frame_data_addr +24、frame head/attr/log 长 +28/+30/+32（三者之和=frame_skip）、fw_buffer +18/max_len +22、touch_data +44、real axes +52/+54；tx=info[28]、rx=info[29]。
- 帧就绪：frame_data_addr 首字节 bit7；矩阵 = tx-major int16 LE，位于 frame_skip+8 起。
- 主机处理：top-5 |v|≥thr(默认200) 峰值 → 3x3 加权质心（半节点单位）→ 长轴=y（t_is_y=(T>=R)^map0）→ 按 max_x/max_y 缩放 → 300px@1440 比例半径最近槽跟踪 → DOWN/MOVE/UP。
- 新 boot args：diting-touch-thr（阈值）、diting-touch-map（bit0 长轴交换 bit1 x镜像 bit2 y镜像）、已有 touch_flip（归一后镜像）。
- 卡顿排查方向：轮询节奏（touch_wait 2-8ms）、帧实际到达率、THP 与坐标轮询并存占 SPI 带宽、map 轴序是否正确。日志行 'goodix: THP mode %u; matrix %ux%u frame %#x skip %u' 给出芯片实际矩阵尺寸。

## Panic 修复（三项，均为流水线错误非触控代码）

1. CPU config panic @AppleARMCPU:111 —— 重新生成的 ADT 内存拓扑错误；**禁止重生成 ADT，只能二进制补丁已验证 ADT**（patched.adt 注入 goodix,cfg-data + max-x/y 成功）。
2. AppleARMCPU 争用 cpu 节点 panic —— kernel.macho 里 IONameMatch cpu→xpu 等长重写（stage-kernel.py）。
3. far=0x28 sha1_init panic（generatePlatformUUID 调空指针）—— **kits/XnuPrelink/emit_prelink.py 把 __PRELINK_INFO 放在原生内核顶 0x8178000（组件区之下），ml_static_slide 清零全部预链接组件**；改用 kits/NativePrelink/emit_prelink.py emit()（info_va 含 new_segments → 0xdbb0000 在组件之上）+ 空 library 集 + diting_rootful_policy。脚本：build-work/native-prelink.py + stage-kernel.py。

## 证据通道（已打通，不再要照片）

- XNU ramoops 镜像写 userdata 尾部 4MiB；板级 LBA 兜底（不要求 SHNGROOT manifest）。
- userdata=/dev/block/sda37，4K 扇区；GPT 盘内 LBA 0x2F8A00-0x3ADF3FA；**dd skip 用分区内偏移**：最后 4MiB skip=58615291 bs=4096 count=1024。
- TWRP/stock-recovery adb root（uid=0）可拉取；MSYS 下远程路径写 //tmp/。
- slot A 刷 HyperOS 3.0.3.0（boot/vendor_boot/dtbo/vbmeta 全套同源），已救活 unbootable 槽；slot B=UniXNU。

## 构建/产物

- 内核构建：build-work/goodix-xref/rebuild.sh（env 全齐）；**xnu-work 已 git checkout+clean 复位，diting_goodix.c 由补丁创建属未跟踪文件——改动一律走 patches/xnu-ipados18/zz*.patch + series，禁手改**。
- 最新镜像：diting-unixnu-uefi-thp.img sha256 88b8a3833cac36b8（内核 4ac460a94fdd4033），临时 fastboot boot 方式验证。
- 补丁链：…→touch-config→touch-reportspace→**touch-thp**（16 个 z）。

## 未完成（不得声称可用）

- Wi-Fi：libDitingAth11k.a 仅编译；固件 amss/amss20/m3/regdb 未打包进镜像；CI 读错 DTB 路径已知。
- Metal/GPU：编译参数在，零硬件验证。
- WSA 音频：未实现。
- 多核：cpus=8 在 args，协因子未验证。
- 触控剩余：卡顿调优 + 四类验收（静止不滚动/按中图标/连续拖动/正确抬起）。

# GPU addon 安装 panic 调查（2026-11-15）

## 状态

- 采用上游 Pong 式 addon 架构：DarwinBoot24 读 `<kernel>.gpuaddon`（NGPUADD2 信封）→ 拷进内核窗口 → 写 `/chosen/memory-map/GpuAddon` ADT 项 → XNU 经 `native_ram_block_gpu_addon` 弱引用访问器读取 → `native_owner_data_prepare` 在 launchd exec 前把文件写入 Data 卷 `/private/var/ngpu/` → union mount 覆盖 Extensions/LaunchDaemons。
- 实机复现路径：文件 0-2 完整写入成功（含 25MB dylib 全流程 rdwr→setattr→fsync→close）；文件 3（libvulkan_freedreno.dylib 17.9MB）在 close/writeback 阶段必崩 `Entered recursive exception`。
- addon payload 全段可读性已验证（head=NGPUADD2 magic、tail 正常），访问器/解析/前三个文件安装链路无问题。

## 崩点定性（裸写 ramoops 探针实证）

- 探针：sleh sync/serror/invalid-stack 三入口无锁无 printf 裸写 16 字记录到 ramoops zone0 尾部（0x1f0000/0x1f0800/0x1f1000，每条 128B：tag/esr/far/pc/sp/lr/fp/x0-x3），随 console zone 被 UFS 镜像冲出。printf 探针在禁中断/嵌套上下文拿不到数据，裸写可以。
- addon12 捕获 10 条记录：tag=0x125（EL1 同步异常 class 0x25 Data Abort）、ESR=0x9600004f（**写权限 fault, level 3**）、FAR=0xfffffffa88758000 起按页步进至 0xfffffffa8875c000、同序列出现两遍、PC 交替 0xfffffff00908a6fc/0xfffffff00908a724、同 SP。
- PC 符号化：两个 PC 均落在 `_bzero`（0xfffffff00908a6e0）内部——`stp x1,x1,[x0]` 边界写 + `dc zva,x3` 整块清缓存的标准页清零循环。
- FAR 位于 physmap（DATA map 止于 0xfffffffa87ca2000、ipc_kernel_copy_map 止于 0xfffffffa884a2000 之后）。**页分配器把 physmap 只读映射的物理页发给 VM/APFS 写回，pagezero 逐页 fault**。
- 高置信度嫌疑：UEFI 内存表 PIL Reserved（0x85200000 起 ~477MB）等保留洞既进了空闲页链表、physmap 又不给写权限 → 空闲链表与 physmap 权限不一致。待 addon13 的 x0/x1/lr 记录（bzero 目标地址/长度/调用者）确认具体区域与调用方。
- 已排除：Wi-Fi 并发（diting_wifi=0 同点崩）、ramoops-UFS 镜像竞态（=0 同点崩）、diting_ufs_stall 持锁睡眠（=0 同点崩且无 TRANSPORT 报告）、fsync 本身（跳过 fsync 后崩在 close）、payload 映射。

## 工程教训/规则

- **补丁树幂等**：zz* 补丁若含"context 依赖前序补丁"的 hunk，`git apply --reverse --check` 零容差反不掉 → 0001 反装检测失败 → 构建卡死循环。reportspace 补丁 context 已改为含 config 插入行的真实布局；任何动 0001 创建文件的补丁必须保证 git 正反检测都能过。残留混态时用 GNU patch --fuzz 按 LIFO 反装恢复。
- `wsl -- bash -c 'A; B'` 的单引号在 Windows 命令行被吞，只有 A 进 -c、B 在外层 MSYS 跑——**跨 WSL 执行一律写脚本文件再 `wsl -- bash /path.sh`**；write 工具写 UNC 路径会落 CRLF，跑前 `tr -d '\r'`。
- `nohup ... &` 或 `bash -c '... &'` 的后台进程在 wsl 命令退出时整树被杀，后台构建必须前台跑（长 timeout）或 script 文件。
- `diting_ramoops_mapped_base ? f() : 0` 对导出普通函数恒为真（-Wpointer-bool-conversion 警告）；符号存在时无害，但写法待清理。
- unstripped 内核（mach.development.diting.unstripped）有完整 6.4 万符号表——`llvm-nm` 可直接符号化 PC；`physmap_base`/`physmap_end` 是 SECURITY_READ_ONLY_LATE 运行期赋值，镜像里为 0，physmap_base = phystokv(args->topOfKernelData)+slide。

## 下一步

1. 拉 addon13 ramoops → x0/x1（bzero 目标/长度）+ lr（调用者）定调用链：pagezero / APFS bounce / kalloc / 其他。
2. 若坐实保留洞进空闲链表：修设备内存声明（DTS/UEFI 内存表→ADT 传递），使空闲页链表与 physmap 权限一致。
3. 修通后恢复 fsync（当前为跳过的诊断态，非最终行为），再继续 Metal/加速路径。

## 未完成（不得声称可用，同上节之外新增）

- GPU addon：装机路径崩在文件 3 写回，未装完；bundle 未真正挂进系统。
- Metal/GPU 加速：内核侧 CP/ZAP/fence 初始化通过，用户态加速仍未接通。
- 持久 ramoops 异常记录探针属诊断设施，后续决定是否保留为开发开关。


## 2026-11-15 — addon13 实机回读

- 临时启动已验证的 Recovery，从 userdata 尾部只读回收 4 MiB，保存为 D:\ai\diting\build-work\ramoops-addon13.bin。确认 12 条记录通过 addon13 格式的 PC 反码与尾标校验。设备已回 bootloader fastboot，未刷写分区。
- LR 0xfffffff008e9fb98 对应 OSKext::updateLoadedKextSummaries() 内 0xfffffff008e9fb94 的 bl _bzero。首条记录停在 _bzero 的第一条 stp，x0=0xfffffffa05f37000、x2=0x5000（入口 x1 已转存到 x2，现场 x1=0）。ESR=0x9600004f，FAR 覆盖 0xfffffffa05f37000 至 0xfffffffa05f3b000 的五个页首。
- 更正上节判断：这组 fault 发生在 kernel_map 的 kext 摘要缓冲区清零路径。源码的 kmem_alloc(KMA_DATA) 新分配分支与对已有缓冲区 mach_vm_protect(..., VM_PROT_DEFAULT) 的复用分支汇合到同一条 bl，LR 单独无法判定分支。文件 3 的 close 尚未返回是日志时序，原先的 physmap/PIL Reserved 与 APFS 页清零推断缺少页表及调用栈证据。
- 下一轮先区分新分配与复用，记录缓冲区的 VM map 保护值、L3 PTE、上层调用帧和内核写权限故障的处理结果。vm_map_protect 对普通映射增加写权限时会先更新 map，留给后续写故障补 PTE；因此复用分支出现首个写 fault 可以符合预期，需要查后续恢复路径。此次只取证和维护记录，内核与设备内存声明未改。


## 2026-11-15 — addon14 摘要缓冲区修复

- 新增 Diting 专用补丁 zzzzzzzzzzzzzzzzzzz-diting-kext-summary-mapping.patch。每次在新分配的可写映射填好 kext 摘要，设置为只读后发布，再释放旧缓冲区。分配或权限设置失败时继续保留旧摘要。该修复针对复用只读缓冲区时依赖写权限 fault 恢复的路径。
- 源码全量备份在 WSL /home/nagatoquin/unixnu/backups/diting-ci-addon13-before-fix-20261115。新增补丁 LF 正反检测通过，完整内核编译链接成功，九个存储绑定落在映射段。反汇编确认 Diting 的 bzero 前进入新分配路径，摘要在发布前仍设置为只读。
- 以 D:\ai\diting\build-work\diting-addon13.img 为模板换内核，保留同一份启动参数、固件和 GPU addon。D:\ai\diting\build-work\diting-addon14.img 已获 Fastboot 临时启动 OKAY，未刷写。设备画面与运行时结果待确认。


## 2026-11-15 — addon14 实机结果

- 33 确认 addon14 仍到 panic 屏。临时 Recovery 回读 userdata 尾部到 D:\ai\diting\build-work\ramoops-addon14.bin，设备已回 bootloader fastboot。
- UFS 镜像中的有效 console 尾部仍在文件 3 的 rdwr、setattr 成功之后、vnode_close 返回之前。有效裸记录只有两条：skmem_sysctl_init 的 0x96000046 L2 翻译故障，以及 copyout 首字节写 0x1100 的 0x96000045 L1 翻译故障（寄存器与早期 copyout("apfs", scratch + 0x100, 5) 相符）。这两条均发生在系统继续启动到 addon 之前。镜像中没有最终 panic 现场，不能判断它是否仍在摘要清零。
- addon14 的摘要缓冲区改动还没有通过实机验收。需要 panic 屏最初报错和调用栈，或能跨重启保留最后一次异常的日志，再决定修复范围。
- 另用同一份 addon14 只将 cpus=8 改为 cpus=1。D:\ai\diting\build-work\diting-addon14-cpus1.img 临时启动已交接；观察至少 44 秒，电脑未再看到 fastboot 或 ADB，屏幕状态和单核日志待查。


## 2026-11-15 — addon14 单核对照

- 33 将机器切回 fastboot 后，只读回收 D:\ai\diting\build-work\ramoops-addon14-cpus1.bin。单核跑过文件 3 的 close，六文件全部写完（written=6 failed=0），Extensions mount/visible/owner 均返回 0，继续到尝试加载 /sbin/launchd。Daemons 与 wallpaper 日志为 1/2，不能记为挂载完成。
- 除八核也出现的两次早期翻译故障外，第三条 0x96000046 来自 exec_save_path 调用 bzero 时写 0xfffffff0008fc000（长度 0x410）。它是 L2 翻译故障，是否正常按需映射待核对，不能直接称为致命 panic。
- 同份日志明确显示 DitingWifi worker 启动并进入 PCIe coldLink。镜像同时带 diting_wifi=0 和末尾 diting_wifi=1，之前仅改第一个值的操作不能作为本轮 Wi-Fi 关闭证据。只将末尾值也设为 0 得到 D:\ai\diting\build-work\diting-addon14-cpus1-nowifi.img，已临时启动，待真机结果。


## 2026-11-15 — launchd EFAULT 与安装持久化

- 关 Wi-Fi 的单核回读确认六文件写完、Extensions 通过，系统进入尝试 exec /sbin/launchd。此时 Recovery 从 Data APFS checkpoint 10261 查不到六个文件，安装未跨重启持久化。
- 33 的本地 panic 原图写明 PID 1 exec /sbin/launchd failed, errno 14。源码确认旧代码把 SystemOS 的 envp 表放在临时页 +0x500，Extensions bindfs 参数也在同处拷入 /private/var/ngpu/addons，首指针被路径字节覆盖。Data 的 mkdir 还占用 +0x400，会覆盖 DYLD_SHARED_CACHE_DIR。用 4 KiB 和 16 KiB 页的布局复现了覆盖和修复。
- 新增 zzzzzzzzzzzzzzzzzzzz-diting-gpu-addon-durability.patch：分段同步写临时文件，同步并关闭后重命名，卷同步成功才挂载。宿主机复现通过短写、同步失败、关闭失败、重命名失败保留旧文件，以及成功写入后的同文件复用。另新增 zzzzzzzzzzzzzzzzzzzzz-diting-launchd-scratch.patch：Data 与 addon 使用单独的第二页，保留 SystemOS 和 launchd 的 argv/envp。
- 第一次名为 addon15 的 Windows 镜像由于临时打包脚本取错来源，仍是 addon14 内核。其 panic 照片与回读均不能作为持久化补丁实机结果。更正后显式传入新镜像、对照镜像与本轮构建 kernel.macho，取出包中内核逐字节比对并确认新日志标记。
- addon16 完整构建、补丁正反检查及预链接存储绑定检查通过，沿用单核、关闭 Wi-Fi 和原六件 GPU addon。Windows 产物 D:\ai\diting\build-work\diting-addon16.img 已 fastboot boot OKAY。待实机确认 launchd、插件持久化与 Metal 功能。


## 2026-11-15 — addon16 实机进入桌面

- 33 确认临时启动的 addon16 已进入 iPadOS 桌面。该镜像使用 cpus=1，Wi-Fi 关闭。这一组合已经越过上一轮 PID 1 exec 的 EFAULT，作为下一轮回归基线保留。当前把设备留在运行状态，Windows 侧未枚举出可用的 ADB 或 Apple USB 接口。
- 确认桌面不能用来确认硬件合成、八核或 Wi-Fi。下一次计划重启时先由 Recovery 只读检查 Data 卷内六件 addon 的持久化，再用同一镜像核对启动日志中 written=0/same=6、Extensions 挂载、Metal 用户态提交和 fence 完成。
- 当前代码全量备份位置为 /home/nagatoquin/unixnu/backups/diting-ci-before-launchd-scratch-20261115，已替换本任务较早的两份备份。


## 2026-11-15 — addon16 八核功能版

- D:\ai\diting\build-work\diting-addon16-full.img 基于已进桌面的 addon16，只把 cpus=1 改为 8、把两处 Wi-Fi 参数归并为唯一的 diting_wifi=1。内嵌内核和 GPU addon 逐字节一致，Metal、GPU scanout、diting_adsp=2 均保留。
- 电池驱动已链接，实机日志应出现 DitingBattery: physical battery power source published。驱动依赖 ADSP 固件与 PMIC GLINK，归档系统镜像 ci-42987806310 的 OS UUID 匹配且检查点为 442，里面未找到 /diting/firmware/adsp.mbn。下一次进 Recovery 直接查设备卷和 addon16 的电源日志，再按实际结果处理固件。
- 功能版尚未启动，电脑端暂未看到设备回 fastboot。当前已知桌面验证仍为单核、关 Wi-Fi 的 addon16。


## 2026-11-15 — 八核版与电源固件

- 回读单核 addon16：GPU addon 六文件同步成功，重启后 Recovery 在 Data checkpoint 10665 查到六个文件，大小和模式均匹配。内核日志显示 backboardd / SpringBoard 分配 Adreno VA、真实 Vulkan-backed 设备、GPU scanout copy completed status=0，运行中 8192 submits / 8191 completed。该证据属于单核版；33 报告八核版进桌面但 Wi-Fi、Metal、电量均未达成，尚待回读八核日志。
- 单核版日志显示 ADSP stage=3 error=2，Recovery 的 OS 卷也没有 /diting/firmware/adsp.mbn。只读读取本机当前槽 modem_a 的 26 个原厂签名 ADSP 分段（未刷分区），合成本地镜像。使用本项目实际 QcomMdt.c 验证 24 个 load 段都落在本机 carveout，5404 字节 PAS 元数据与原厂 MDT 逐字节一致。
- Diting 原厂 DT 以及平台表都明确 ADSP 保留区为 0x9fd00000 + 0x03100000。此前驱动的 0x85700000 + 0x02800000 属于 Nothing 参考并且小于本机固件需要。驱动已更正并改用 pmap_has_managed_page 检查全部非连续 RAM 段，允许把原厂签名固件通过 addon 写到固定 Data 路径，保留 PAS 验签。
- D:\ai\diting\build-work\diting-addon17.img 已构建，最终 payload 的新内核、七文件 addon、原厂 ADSP 字节和八核 / Wi-Fi / Metal / ADSP 参数均已核对。未临时启动；等待八核 addon16 设备回 fastboot，读出 Wi-Fi、Metal、ADSP 状态后再继续。


## 2026-11-15 — 八核实机回读与 RPMh 活动槽修复

- D:\ai\diting\build-work\ramoops-addon16-full.bin 确认 CPU0–7 均报 first boot completed，六文件全部复用（written=0 same=6 failed=0），Extensions stage/status=5/0。八核实机有 3 次实际 GPU scanout copy completed status=0 和累计 10240 submits / 10239 completed。桌面渲染性能及更多 Metal 应用仍需具体测试。
- Wi-Fi 在 smpe2 高位设置（RPMh 0x40508=7）报 timeout，未走到 PCIe 或扫描。原厂 DT qcom,tcs-config 的活动组先列、占 TCS0–2；TCS4 是休眠槽。对照 Linux rpmh-rsc 的按 DT 顺序编号逻辑，并结合已实机工作的 Goodix TCS0，Wi-Fi/ADSP 的共享请求改为 TCS1，统一调整寄存器和 IRQ 位，GPU 原有请求路径保留并检查新共享槽是否有冲突。
- D:\ai\diting\build-work\diting-addon17.img 已 fastboot 临时启动，固件与电量结果尚待回读。D:\ai\diting\build-work\diting-addon18.img 已构建并确认包内含 TCS1 修复的新内核、七文件 addon 和八核功能参数，尚未临时启动。


## 2026-11-15 — addon17 回读和最终交接

- 33 确认 addon17 进桌面仍无电量。Recovery 回读 D:\ai\diting\build-work\ramoops-addon17.bin：第七件原厂 ADSP 固件写入且 Data sync=0，ADSP 走到 stage 6，stage 7 发 0x30030=7 后共享 RPMh 超时（-60）；Wi-Fi 0x40508=7 同样超时。Metal 实际 scanout 成功，累计 9215 次完成。
- 33 要求停在交接。设备在 Recovery，addon18 未启动。完整实机状态和下一轮验收见 D:\ai\diting\交接-2026-11-15-addon18-八核-Metal-WiFi-电量.md。全量备份为 /home/nagatoquin/unixnu/backups/diting-ci-before-rpmh-slot-20261115。

## 2026-11-15 — docs refresh（README_EN / STATUS / PROVENANCE）

- README.md 已由 lead 按 addon18 现实重写；本次把同一组事实同步到 README_EN.md，并补齐仓库缺失的状态与来源文档。
- README_EN.md：替换 “Hardware and progress” 表与两段状态文字为 addon18 现实 —— addon16/16-full/17 进桌面、
  八核 CPU0–7 均 first boot completed、Metal 有 Vulkan-backed 设备与 scanout/submit 计数、触摸 Goodix GT9916
  可用但卡顿、六文件插件持久化、launchd EFAULT 已修；阻塞写 Wi-Fi RPMh `0x40508=7`（TCS4 为休眠槽，addon18 改 TCS1
  未上机）与 ADSP stage 7 `0x30030=7`（无 PAS/电量）；删除 “touch not responsive”“GPU/Wi-Fi not device-verified”
  “deterministic memory-corruption panic under investigation” 等过时表述。
- 新增 docs/STATUS.md（中文）：当前设备/镜像、已实机证实项、ramoops 证据路径、阻塞表、addon18 验收阶梯
  （Wi-Fi：RPMh committed→电源→PCIe→SMMU/MSI→MHI/QMI→station→扫描→关联→DHCP；ADSP：stage7→PAS→GLINK→
  battery publish；Metal 回归）与维护规则。
- 新增 docs/PROVENANCE.md（中文）：三层来源（上游/Pong 继承/Diting 实机）、Pong 记录清单（TFA9873 音频/铃声、
  部分 Wi-Fi/存储结论）、`porting.toml` 的 `kind`/`reported_kind` 解读规则，以及“新结论先写 AGENTS/STATUS”。
- 归档 docs-eacces-brief.md（2026-11-10 快照）到 docs/archive/2026-11-10-eacces-brief.md，加归档横幅；
  docs/USB-LOGGING-PLAN.zh.md 保留。
- 本次只改文档（README.md 为 lead 已改内容、README_EN.md、docs/STATUS.md、docs/PROVENANCE.md、
  docs/archive/2026-11-10-eacces-brief.md、AGENTS.md）；未改代码/构建，未上机，未 push/CI。

## 2026-11-15 evening — OS 布局导致触摸 UI 失效、更新页崩溃与 GPU 帧率限制

- **触摸根因 = OS 布局，不是驱动**：11-11 userdata 重刷装的是 Pong 时代 OS —— 设备只读回读 `/pong/init`
  sha256 `a80747bbcaf076861c29669b8b49ece28215e3a0861e86d2a67d76e3b2b7bfb8`（71,392 B，与 `/sbin/launchd` 相同）、
  `/sbin/launchd.ios` `81cefc45…`（560,752 B）、`/pong/libpong-ui18.dylib` 174,960 B sha256
  `28d133d00c870a6baec0578d03961b2f968b34a2fd2b36b6790141294aeba37c`，`/diting` 不存在；该库的 9 类触控入口全部打印
  `Pong touch HID: unavailable IOHID…; SKIP`。内核侧触摸正常：`D:\ai\diting\build-work\ramoops-addon18c.bin` 有
  `Diting touch: DT ok`、`BERLIN`/`9916`、GENI-DMA 6.4 MHz、`IRQ240` GPIO21、`finger 0 at 5084, 23812` ×4，
  没有任何 touch failure —— 但 Pong UI 库没有 `/dev/diting-touch` 直连路径，UI 永远收不到这些事件。
  离线兼容候选：`artifacts/ci-42987806310/diting-ipados18-system.cdr`（6,845,104,128 B sha256
  `27c507c8972275c9170806bb975b03d762ebbb9379945b890d5665a154e8102d`，卷 UUID B07DF049…、`/diting` 布局、
  `/sbin/launchd`=`/diting/init` sha `95cb7341…`、`libditing-ui18.dylib` 174,976 B 含 `/dev/diting-touch` 与
  `display-integrated digitizer opened`、`/pong` 缺失）；11-09 干净原件在
  `diting-ci/out/userdata/userdata-root.img`（19,411,238,912 B）。写 OS 窗口属 6.8 GB 级分区写入，必须用户对那一次明确授权。
- **“软件更新已完成”页 = softwareupdated 崩溃循环**：Data `/mobile/Library/Logs/CrashReporter` 有 9 份
  `softwareupdated-*.ips`（最新已取回 `build-work/crash-softwareupdated-latest.ips`）；异常是
  `EXC_BAD_ACCESS / SIGSEGV / KERN_INVALID_ADDRESS at 0x20`，main 线程
  `objc_release → AutoreleasePoolPage::releaseUntil → objc_autoreleasePoolPop → softwareupdated main+1612`，
  `consecutiveCrashCount=2`。状态文件 `/mobile/Library/SoftwareUpdateCore/softwareupdateservicesd.state`（15,204 B），
  `/mobile/Library/SoftwareUpdates*`、`/db/softwareupdated` 缺失。该页面属于 MobileSoftwareUpdate 路径，
  不是触摸驱动问题；换 Diting OS 后是否仍出现未观察。
- **诊断通道未打通（addon21/22/23 未观察）**：addon22（kernel `9b8e4c6bf936adb7a5ecac05a919224e01724f6ca5147b1ce7d322e417282d84`，
  镜像 `9463932459e525b856badd41b3f78a9717092d78696b009d4d3a4109d60120df`）与 addon23（镜像
  `f5bb6e72a63bd348522a9d7f932c91dbb266a220b17cc07931632e0bea517966`，kernel 同上，7 文件 addon 含
  `firmware/adsp.mbn` 23,380,392 B `d299d413…`）都带 `diting_usb=1`，但 Windows 5 分钟窗口内没有枚举任何
  COM/CDC（无 05AC/18D1/2717/05C6，也无 unknown 设备）；addon23 回读的 `ramoops-addon23.bin` 与
  `ramoops-addon18c.bin` **逐字节相同**（sha256 `e93d1fa10b0dda114a4f7bcb88e25466986b8938899e445a0bf6d7c98ec0a252`）
  ⇒ `9b8e4c6b` 内核不写 UFS ramoops，addon21/22/23 的 console 与功能结果都未观察、不得推断。后续诊断镜像必须用
  会写 ramoops 的 `03b90020`/`e991983d` 系内核（或先解决 CDC）。
- **GPU 流畅度限制器（task-24，memo `build-work/evidence-20261115-gpu-framerate/README.md`）**：固定 120 Hz、
  预算 8.33 ms；`T pipeline n=24 total=100ms max=11ms`、`T library 15ms`、`PR functions resumed=0`、
  `V cache hit27 miss23 wr0`、`P0 … QuartzCore.framework/default.metallib InvalidFile`；`H frame-enc` 4/16 帧
  ≥16 ms（含 1 帧 128–255 ms）；GPU `ctc` mean 5241 µs max 8077 µs、commit→complete mean 4643 µs max 16000 µs；
  帧间隔 8,8,8,8,12,13 ms（≈125/125/125/125/83/77 fps）。根因是 plugin 构建时没给 `--prime-list`
  （`scripts/build-diting-metal-plugin.py:21,48-54` 支持 `-Wl,-sectcreate,__DATA,__primelist,…`，但
  `build-work/metal-out/plugin/build-report.json` 无 `-sectcreate`、bundle 无 `.primelist`），运行期 cache 也从不写盘
  （`wr0`）。修复顺序：primelist 重建 → cache 持久化 → 再看 encode/GPU；`DitingMetalPlugin.mm:184-198` 的 primer
  代码本身存在，只是没有输入列表。
- **触摸延迟诊断补丁**：`patches/xnu-ipados18/zzzzzzzzzzzzzzzzzz-diting-touch-latency.patch`（88 行，sha256
  `7c22b77900eccaed6825b945a24aa121ed40e176b25774631ed3d28e2ca57fe3`）已加入 `series`；bring-up 构建验证通过
  （kernel `b02fe3c2…`），尚未进 release 镜像。touch-lag memo 结论：主机路径最坏约 11 ms，主要未知项是 THP 帧到达
  间隔（驱动目前没有帧间隔计数），先加 instrumentation 再改行为；11-14 的卡顿镜像还同时跑了 THP 与坐标轮询。
- **构建脚本默认值（task-23）**：`scripts/build-release-image-linux.py` 现在默认 `--diagnostics`（追加
  `diting_usb=1`、`diting_ufslog=1`、`diting_ramoops_ufs=1`、`diting_data_reserve=4`、
  `diting_adsp-fw=/private/var/ngpu/firmware`、`diting_ufs_stall=0`，`--arg` 仍可覆盖）并要求 `--gpu-addon`；
  addon23（`f5bb6e72…`，kernel `9b8e4c6b…`、7 文件 addon）已构建但未观察。
- 本轮只做只读回读与离线分析：没有 flash/dd/写分区、没有 CI、没有 push；设备回到 TWRP recovery。

## 2026-11-16 — 桌面与触摸里程碑

- 设备状态：`boot_a` = addon18；OS 为 Diting 布局（`/sbin/launchd` = `/diting/init` sha256 `95cb7341…`，
  `libditing-ui18.dylib` 174,976 B 含 `/dev/diting-touch`），经整盘 userdata sparse 恢复
  （`userdata-osditing-1109.sparse.img` 19,411,252,824 B；OS 窗口 = `artifacts/ci-42987806310/diting-ipados18-system.cdr`
  6,845,104,128 B sha256 `27c507c8972275c9170806bb975b03d762ebbb9379945b890d5665a154e8102d`）。
  上机结果：iPadOS 18.7.10 桌面，Goodix GT9916 触摸点击/滑动/拖动可用。Pong 时代布局
  （`/pong/init` `a80747bb…`、`libpong-ui18.dylib` `28d133d0…`）与本机触摸桥不兼容。
- GPU/Metal 硬件路径：真机日志有 `DITING ADRENO: CP ready`、`DITING METAL: real IOAcceleratorES provider published`、
  `… status=0x0`、`DITING SCANOUT … status=0x0`，GPU submits 有记录；UI 帧率仍受 Metal pipeline 编译未摊销
  （插件已内嵌 `__DATA,__primelist`）与 shader cache 不落盘限制，列为下一 GPU 工作项。
- 阻塞：Wi-Fi 首笔 smpe2 RPMh `0x40508=7` 在 PCIe 前超时；ADSP stage 6→7 `0x30030=7` 超时（-60），无电池发布；
  内核无 poweroff 路径，长按电源不能关机（PSCI SYSTEM_OFF 长按补丁在下一候选内核）。
- 待上机镜像（静态检查 PASS，`hardware_tested=false`）：`D:\ai\diting\build-work\diting-addon24-diag.img`
  （`54ed270b31aa223e46b5603c0a25481de58bf93424e8d01a0b698a6968fcf9f4`，`e991983d…` 内核 + primelist 插件）与
  `diting-addon26-diag.img`（`ee7278b260ffa0f3c2cb8fcb28ee0263f26d30edd31123eaccc18937dfe15edc`，重建 release 内核
  `20834d3c0770db2e6f2ad7238b3bcfd2cd1b4e2508dc01b766c08a0142a6b6e3`，含 pwrkey/PSCI SYSTEM_OFF、TCS1、
  touch-latency、primelist 与 7 文件 addon）。
- 证据：`build-work/ramoops-addon16*.bin`、`ramoops-addon17.bin`、`ramoops-addon18c.bin`；
  `build-work/evidence-20261115-gpu-framerate/`、`evidence-20261115-gpu-prime/`、`evidence-20261116-addon26/`、
  `evidence-20261116-pwrkey/`；`build-work/evidence-20261115-touch-lag/`。

## 2026-11-16 — GPU 上游诊断移植与 addon27

- 上游 `pong-adreno-metal` @ `418c550`（声称基线 `a0f0287`）与 `drivers/DitingMetal` 是分叉关系而非子集：
  `NativeBridgeMetalFrontend.mm` 70 hunks / 5,471 行、`bridge/NativeMetalObjects.rs` 35 hunks / 1,515 行；
  上游新诊断建立在 frames.trace（type 7/8/10/12）与 translator `0021…0024` 之上，fork 用自己的
  `NativeGpuTrace.h` ABI 与 `frameEvent` 覆盖同类信息。
- 已移植（`drivers/DitingMetal/**`，+36/−4）：`log-gpu=1` / `diting_gpu_log=1` → `SHENG_LOG_GPU=1`（否则 unset，`a0a34fa` 语义）；
  `logGpuOn()` + 每 commit 一条有界 pass note（`Diting Metal pass: pid/commit/passes/draws/blits/kpx/ctc/finish`，≤1/250 ms，
  `f46fc88` 概念）；`NmbShaderCacheStats.writes_queued`（bridge `.h`/`.rs`）；telemetry `V cache h/m/w/q/rf/wf/ev` 与新增
  `V drv l/h/m/s/tr/mm/un`（`de38c6f` 的 "full shader cache counts"），直接回答 11-15 的 `wr0` 问题
  （queued-but-unwritten vs write-failure；驱动记录层是否持久）。
- 未移植/出范围：translator `0021–0024`（room-keeper 线程、pass ring、sample ring）与 19 个有意丢弃的上游文件
  （HostMetalCommandServer/Offline*/Original*ABI/tools）；fork 已有等价的 per-pass 附件与 stage-summary 覆盖。
  本轮只改诊断，不改渲染策略与 guest ABI。
- 构建产物：`DitingMetalBridge.dylib` 25,078,768 B sha256 `3286ae6d73bea8b5ea8501525d7314c385167ea88bc441ffb4deb5abfd3c7921`；
  `DitingAdrenoMetal` 116,824 B sha256 `3c38d92ec5bb5c83c0024975ca9701717d128694ca84622d481d9b9df8c59b62`，
  `__DATA,__primelist` 728 B / 10 行（嵌入字节 == `diting-ui-metallibs.primelist`，build report 含 `-sectcreate`）；
  `addon27.gpuaddon` 24,370,920 B sha256 `8ea462a30d7ebcb0070dbb401d2f23c4244db8018cf7b5f7bbd64fb4153a04a2`（7 文件，含 `adsp.mbn`）。
- 镜像：`D:\ai\diting\build-work\diting-addon27-diag.img` 101,187,584 B sha256
  `d0b0e1e13e9a5e4c155d8aeb0a6c6626a06038c244d5cd008163681f26ead710`；v4 布局 PASS，kernel = addon26 的
  `20834d3c0770db2e6f2ad7238b3bcfd2cd1b4e2508dc01b766c08a0142a6b6e3`（73,773,056 B，`__PRELINK_INFO` 26 条含
  `com.apple.iokit.IOGPUFamily`）不变（本轮只动 plugin/bridge）；args 50 token / 968 字符，含 `log-gpu=1` 与
  `diting_pwrkey_log=1 diting_pwrkey_long=5000`，`manifest == args`、`ADT == SHA-384(manifest)`、contract PASS、storage PASS；
  `hardware_tested=false`。
- 证据：`build-work/evidence-20261116-gpu-upstream/README.md`、`addon27-report.json`、`verification.json`、`logs/bridge-build.log`、
  `logs/plugin-build.log`。本轮未上机、未派 CI。

## 2026-11-16 — merged core verified, pin fd2f4d1

- 内核 core：`sync/upstream-20261116` merge commit `fd2f4d17833fb8439a801cd8bad85beef7b363f4`
  （upstream `origin/main` `03129b6d33395a0a57715b1673e7e5ce3b516e10` + 本地保留提交
  `00b841547946103eb5035a2bf974ddde03ba73a5`；merge base `0e2fb2b`）。
- 验证：diting-ci `59c88c87ae8d7d210b1a15302ae546e400adb425`、fresh `xnu-work`，
  `./unixnu build kernel -D ../diting-ci` **exit 0**（`kernel-build-20261116T025028Z.log`）；
  `./unixnu status` / `defconfig` / `scripts/porting-record.py check`（34 areas）均 PASS。
  **前置条件**：先清理 diting-ci 中 4 个未跟踪的过期 refer 软链（指向 `xnu-ci-core/out/feeds`，属生成物）：
  `AvailabilityVersions-143.7`、`IOStorageFamily-323`、`libdispatch-1521.140.2`、`libplatform-349.140.6`。
- 产物：core 预链接 `kernel.macho` 73,719,808 B sha256
  `67b5199e445a7825c29e43960aea2ed1e7cbd85c1ec40493c23bc4ec013dd914`（22 个 `__PRELINK_INFO` entries，无 IOGPU）；
  IOGPU library-only `kernel-merged-core-iogpu.macho` 73,773,056 B sha256
  `7ed899e5d0f3c812e26f0df52fa02f129a1f4542fef858806ab33fc9011a07f8`（26 entries 含 `com.apple.iokit.IOGPUFamily`，
  19 components / 9 library-only），`check-storage-bindings.py` PASS（9 绑定，prelink info 在组件后）。
- markers 全部存在：`Diting touch latency`/`Diting touch THP latency`、`cmd written tcs=`/`timeout tcs=`、
  `Diting pwrkey`×4、`PSCI SYSTEM_OFF`、`diting_pwrkey_long`/`diting_pwrkey_log`、`ramoops`/`ramoops_ufs`/
  `diting_ramoops_ufs`。
- pin：由 `0ce9779` 更新为 `fd2f4d1`；落盘 `core-provenance.json`（含 artifacts、verification、
  `prerequisite_refer_cleanup`、`previous_pin`、`evidence_path`），`docs/ARCHITECTURE.md §5` 与 `docs/STATUS.md` 同步。
- 证据：`build-work/evidence-20261116-core-sync/README.md`、`merged-core-kernel.json`、`verify-merged-kernel.py`。
  本轮只更新文档与 provenance 记录，未上机、未派 CI；上游仓库仍只读、未推送。

## 2026-11-16 — Turnip 重建（shared-shader / retired-BO）+ addon28

- `patches/mesa/0016-diting-turnip-shaders-shared-across-pipeline-caches.patch`（2,002 B sha256
  `54b2438548f90ee0f9a187725d4d58c31988f24b150f1020d1a9472284f0acee`，上游 `c34f018`：同 stage 跨
  `VkPipelineCache` 复用 device shader）；`patches/mesa/0017-diting-turnip-sweep-retired-on-cache-miss.patch`
  （3,835 B sha256 `acf17b799ee6954609d370a4a79a9758d82d331ecb1e10704ac658ed4d1c0872`，上游 `2bbb39d`：
  retired BO 只在 cache miss 时 sweep，不再等他人 fence）。两补丁 LF-only，应用到 Mesa 快照副本
  （`diting-mesa` @ `85fda3b…`）后 `patch -p1 -R --dry-run` 通过；共享 mesa 树未改。
- Turnip rebuild：`scripts/build-diting-turnip.py --guest-build 22H374` 产出 `libvulkan_freedreno.dylib`
  **17,882,280 B** sha256 `eab147a893c194c3778ececa3c6f3539963e92f55a917521c67ce55b97fea89b`（旧 17,883,400 B
  `4b77d1ae…`）；`tu_pipeline.cc.o` 185,888→187,752 B、`tu_knl_darwin.cc.o` 41,704→42,728 B，新对象导入
  `_pthread_mutex_trylock`。工具链注意：`--tools-directory` 必须用 target-clang 包装目录
  `~/.local/xnu-linux/bin`（否则 meson 记录 host clang 并报 `unrecognisable emulation mode: llvm`）。
- 缓存目录/金属流：fork 已有 `SharedShaderCache.h sharedShaderCacheDirectory()`（`NATIVE_METAL_SHARED_CACHE_DIR`、
  同 UID/非 group+world 可写、mkstemp 探针）；`DitingMetalPlugin.mm` 新增 boot arg
  `diting_gpu_cache_dir=<path>` 在候选列表构建前设置该 env、启动 NSLog 打印 chosen dir/shared/writable/metal-flow
  与 bit-4 状态；`NativeBridgeMetalFrontend.mm` 把 chosen dir 交给 telemetry，新增
  `C cache dir=… shared=… writable=…`（≤90 字符）。`metal-flow` 本 fork 未实现（iPadOS 默认 `7` = bits 0/1/2，
  bit 4 early warming 未启用；warming 仍走 `PrimeShaders`/`diting_gpu_prime`）。
- 产物：plugin `DitingAdrenoMetal` 116,960 B sha256 `f624a7d53b6425f84d173f80aaafbebd3438dce7d8666c8cd56245e91ab00d9d`
  （`__DATA,__primelist` 728 B/10 行 == `diting-ui-metallibs.primelist`，bundle 内 turnip = `eab147a8…`）；
  bridge 25,074,944 B sha256 `582cca9159dad0e709196ffb91e898b964ddbc8291b91c466676324c1dcb76cd`；
  `addon28.gpuaddon` 24,371,768 B sha256 `5007f1fbeed5b5e0d23ef2a9ec3c2536e7040b94d19f40fb2677990486322005`
  （7 文件，含 `firmware/adsp.mbn` `d299d413…`）。
- 镜像：`D:\ai\diting\build-work\diting-addon28-diag.img` 101,187,584 B sha256
  `8cdd951dfee38a196a754d8f4956e6b88e5656488c9433741c2cf253e6a8ebc5`；kernel = merged-core IOGPU
  `7ed899e5…`（73,773,056 B，26 entries 含 IOGPU）；args 50 tokens/968 chars（`log-gpu=1`、
  `diting_pwrkey_log=1`/`diting_pwrkey_long=5000`、`diting_gpu_cache_dir` 支持），contract/storage PASS、
  v4 布局/CRC/ADT==SHA-384(manifest) 均通过；`hardware_tested=false`。
- 预期（code-level，待真机确认）：shader-share 减少冷编译停顿（`T pipeline total/max` 与 `H frame-enc` 16–63 ms 分箱下降）；
  retired-BO sweep 降低 encode/submit 抖动（`frame-enc`/`ctc` 尾部与 `E age` 离群值下降）；`C cache dir` + `V cache`/`V drv`
  可判定写入是否落盘、跨启动是否持久。真机测试（RAM-only）：冷滚 30 s → 热滚 30 s → 重启再冷滚 30 s，逐项对比
  `T pipeline`、`PR resumed`、`H frame-enc`、`ctc`、`V cache`、`V drv`、`C cache dir`；异常回 addon27（旧 Turnip）同内核对照。
- 证据：`build-work/evidence-20261116-turnip/README.md`、`addon28-report.json`、`verification.json`、`logs/turnip-build.log`。
  本轮只提交补丁/驱动与文档，未上机、未派 CI；上游仓库只读。

## 2026-11-16 — addon29：args-only GPU trace/pixel 追踪变体

- 来源：committed main `05e9e48` 的 release 镜像重用，仅改 args；产物与 addon28 逐字节相同：kernel `7ed899e5…`
  （73,773,056 B，26 IOGPU entries）、plugin `f624a7d5…`、bridge `582cca91…`、turnip `eab147a8…`、
  `addon28.gpuaddon` `5007f1fb…`（7 文件，adsp `d299d413…`）。
- args：52 tokens / 999 chars（`within_1000`），在 addon28 基础上新增 `diting_gpu_trace=1 diting_gpu_pixels=1`，
  保留 `log-gpu=1`、`diting_pwrkey_log=1`、`diting_pwrkey_long=5000`；`applog_name=backboardd,SpringBoard` 以让总长度回到 1000 B 以内。
  两个 UI 开关 `diting_ui_software=0`/`diting_software_ui=0` 来自 `scripts/build-release-image-linux.py` 的 builder 默认值（不在 board.toml），
  留作后续与 `[payload] kernel_args` 统一时的跟进项。
- 验证（`verification-addon29.json`，全部 PASS）：v4 layout、kernel slot = intended `7ed899e5…` 首 4 MiB、PONGFAT1 CRC `0x209d9609`、
  `manifest boot_args == args`、`ADT == SHA-384(manifest)`、`loader/adt contract` PASS、`storage bindings` PASS（9 绑定）、
  plugin/bridge/turnip/addon 均 `same_as_28`；`bytes=101,187,584`。
- 镜像：`D:\ai\diting\build-work\diting-addon29-diag.img` sha256
  `4fadc1241b0b8dc9877f4ffd9fb219edbd862f4b58a3ecd43414902446ef1408`；`hardware_tested=false`。
- 预期：`diting_gpu_trace=1` 输出 per-frame GPU trace（提交/pass/fence 事件），`diting_gpu_pixels=1` 打开 pixel capture（`frameEvent(40)`），
  与 `log-gpu=1` 的 `Diting Metal pass` 行一起把 `T pipeline`/`H frame-enc`/`ctc` 尾部归因到具体 pass/draw/pixel 集；
  真机测试仍按冷滚 30 s → 热滚 30 s → 重启冷滚 30 s，异常回 addon28/addon27 对照。
- 证据：`build-work/evidence-20261116-gpu-official/verification-addon29.json`、`build-image-addon29.log`、`verify-addon29.py`。
  本轮只改 args 并记录，未上机、未派 CI。

## 2026-11-16 — 官方 ADT 候选与 A/B 对照（未合并）

- 分支：diting-ci **`fix/adt-gen` @ `ed18043`**（已推 fork；含 `5b4df48` official-prelink + `7dc1e7f`/`1186469` dts/静态 `[adt.*]` 输入、
  `d42b068` `[adt.arm-io]` 节点/UFS 属性、`ed18043` finalize `--official-adt` + release 透传 + contract 接受 64/256 seed）；
  UniXNU fork **`feat/adt-arm-io` @ `8968f72`**（base `fd2f4d1`，`scripts/unixnu/devicetree.py` 29 行 `[adt.arm-io]`，仅 fork、无 upstream PR）；
  共享 core checkout 已切回 `sync/upstream-20261116`（`fd2f4d1`）；`port/official-prelink` @ `5b4df48` 保留为 pre-ADT baseline。
- A/B 对（同日/同 kernel/同 addon/同 cpus=1 与 args）：official-ADT 候选 `image-candidate-release-v4-cpus1.img`
  101,187,584 B sha256 `9bf5ea504c1b445df662dad266e039fb5900ff7589f5abbe79e5eafecdcfca75`（ADT 15,352 B `4ac18849…`，
  CRC `0xda0f09a9`）；旧 binary-patch 对照 `image-candidate-oldadt-release-v4-cpus1.img` 101,187,584 B sha256
  `47e6b744b495a9671f636d6507d9ebe687bb8e58487238b808c175bad1bbb287`（ADT 14,112 B `cdc7b8cc…`，CRC `0x2f129509`）。
  manifest 1,345 B `7695a248…`、kernel `ddccc812…`（prelink 26）、addon `8ea462a3…`（7 文件）、layout 在两者间一致；
  gates contract/storage/single_core/layout PASS。两镜像仅 ADT 及其决定的 payload FAT/CRC 不同。
- 接受的结构性差异（首轮设备测试前不改 generator）：root compatible 追加 DTS 串；intc 带 phandle/`#interrupt-cells`/base-relative reg；
  ufshc 额外 reg/reg-names/interrupts（NativeUfs 仍读 diting,*）；`/cpus` 缺 `#address-cells`、cpu0 `cluster-type='E'`、无 `/psci`；
  `/chosen/memory-map` 含 `GpuAddon`；allocatable-ram 240B（config 15 bank）；random-seed 256B（xnu-12377 需 4×64，旧内核读首 64；
  contract 已接受 64/256）；`BNCH`/`boot-epoch`/`boot-manifest-hash`/`root-matching` 为每启动动态值（finalize 负责）。
- 风险/门槛：default 仍是旧 binary-patch ADT；合并需候选镜像真机启动且无 AppleARMCPU/IOKit 匹配回归。
  `build-work/evidence-20261116-adt-gen/merge-checklist.md` 记录合并顺序（先 core `feat/adt-arm-io` → diting-ci `fix/adt-gen` → 验证后切默认）、
  post-merge 重建验证清单与回滚方案；`ab-compare.json` 保存 A/B 差异。
- 证据：`build-work/evidence-20261116-adt-gen/README.md` §14–15、`ab-compare.json`、`merge-checklist.md`、`adt-final-result.json`。
  本轮只记录，未上机、未合并、未派 CI；upstream 仓库只读、未推送。

## 2026-11-16 — 分支策略：main + dev

- 仓库（`nagatoquin33/UniXNU-diting`）只保留两条长期分支：`main` 稳定/已验证，`dev` 集成；功能分支短命，合并后删除。
  完整规则见 `docs/ARCHITECTURE.md §6`。
- 本次整理：
  - `dev` 从 `main` `77904cf` 创建，合入 `fix/adt-gen` `ed18043`（其已含 `port/official-prelink` `5b4df48`）→ merge commit
    `00bb154`；无冲突。`board.toml` 合并后同时保留 main 的打包字段（`[payload] loader`、`[payload.runtime] enabled=false`、
    `[payload.adt] tool` 注释）与分支的 `[kernel.prelink] roots`（含 `com.apple.iokit.IOGPUFamily`）及 `[adt.arm-io]`
    （`diting-touch`/`diting-buttons`/`ufshc`）；`finalize-diting-adt.py`/`build-release-image-linux.py`/`diting_adt_contract.py`/`dts/diting.dts`
    取分支版本。`git diff main..dev` 仅上述 5 个文件（+213/−3）。
  - 离线门禁：`py_compile` PASS；`porting-record.py check --device .` → “diting: 34 structured areas checked” PASS；
    `diting_adt_contract.py --help` PASS；`tomllib` 解析 PASS。未上机、未派 CI（内核/镜像门禁沿用 `evidence-20261116-adt-gen` 记录）。
  - 已推 `dev` → `00bb154b134e774e142bd8889d50562bcb72257f`；随后删除远端 `fix/adt-gen`（`ed18043`）、
    `port/official-prelink`（`5b4df48`）、`no-stall`（`12a8596`）、`ci/systemos-union`（`9628bd4`）、
    `ci/eacces-applog-fix`（`be630b9e`）；删除本地同名分支与 `port/official-prelink-rebased`（`5b4df48`，其 worktree
    `/home/nagatoquin/unixnu/diting-rebase` 一并移除）。整理后远端/本地仅 `main` 与 `dev`，worktree 仅主检出。
- 边界：`dev` 未合入 `main`；`main` 的 ADT 默认仍是旧 binary-patch 路径，`feat/adt-arm-io`（核心 fork `8968f72`）待设备
  A/B 后再按 `build-work/evidence-20261116-adt-gen/merge-checklist.md` 合入。
