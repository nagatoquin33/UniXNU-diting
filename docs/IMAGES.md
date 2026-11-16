# 镜像与本地产物清单

`build-work/` 与 `out/` 为 gitignored 本地目录；镜像本身不入库，本文件记录保留策略、哈希与重建入口。位置：Windows `D:\ai\diting\build-work\`；WSL `/home/nagatoquin/unixnu/diting-ci/out/`。

## 1. 保留基线

| 产物 | 用途 | 大小 | sha256 |
| --- | --- | --- | --- |
| `diting-addon18.img` | `boot_a` 当前镜像；Diting OS 桌面/触摸基线 | 101,187,584 | `6c026c4960f8fa93762dbdacacdc2cc64b928b816dea32a8d3189aa75be9c515` |
| `diting-addon16-full.img` | 八核 + Metal scanout 已验证回退 | 101,187,584 | `b93fd086e87d4145d4a6955e4ca3d5c8c230373dcff54f0ae3cdc427f10fea8c` |
| `diting-addon19.img` | RPMh TCS1 供电证据（ramoops-addon19） | 101,187,584 | `102fd293e45b9d3d542fdb2900f8eb1730c3a0a0f7251eb8370f6aec51766ab3` |
| `diting-addon22.img` | USB CDC 诊断变体（未观察到 console） | 101,187,584 | `9463932459e525b856badd41b3f78a9717092d78696b009d4d3a4109d60120df` |
| `diting-addon23-diag.img` | 诊断默认 + 7 文件 addon（未取得 ramoops） | 101,187,584 | `f5bb6e72a63bd348522a9d7f932c91dbb266a220b17cc07931632e0bea517966` |
| `diting-addon24-diag.img` | primelist 插件 + `e991983d` 内核 | 101,187,584 | `54ed270b31aa223e46b5603c0a25481de58bf93424e8d01a0b698a6968fcf9f4` |
| `diting-addon26-diag.img` | pwrkey/PSCI + TCS1 + latency + primelist | 101,187,584 | `ee7278b260ffa0f3c2cb8fcb28ee0263f26d30edd31123eaccc18937dfe15edc` |
| `diting-addon27-diag.img` | GPU 上游诊断移植 + 完整 shader-cache 计数 + primelist 插件（内核沿用 addon26 `20834d3c…`） | 101,187,584 | `d0b0e1e13e9a5e4c155d8aeb0a6c6626a06038c244d5cd008163681f26ead710` |
| `diting-addon28-diag.img` | Turnip 0016/0017 重建 + `diting_gpu_cache_dir`/`C cache dir` 遥测（kernel `7ed899e5…`） | 101,187,584 | `8cdd951dfee38a196a754d8f4956e6b88e5656488c9433741c2cf253e6a8ebc5` |
| `diting-addon29-diag.img` | addon28 的 args-only 追踪变体：`diting_gpu_trace=1 diting_gpu_pixels=1`（52 args/999 B，内核/插件/bridge/turnip/addon 与 addon28 逐字节相同） | 101,187,584 | `4fadc1241b0b8dc9877f4ffd9fb219edbd862f4b58a3ecd43414902446ef1408` |
| `diting-addon30-diag.img` | 合并 core dev `121ea7f`（upstream `9931232`/PR #272）：kernel `0c1a2c1f…`（26 IOGPU）+ Turnip `6001cadb…`（BO free under-lock fix）+ bridge `2a4ef86d…`（语义同 addon29）+ plugin `f624a7d5…` | 101,187,584 | `a2158d7a025ff04f08d0a84eae9444b4d6bfdd76d0144603580a1c0f776f99e3` |
| `image-candidate-release-v4-cpus1.img` | ADT 官方路径候选（`evidence-20261116-adt-gen`，**尚未合并为默认**）：ADT `4ac18849…` 15,352 B，CRC `0xda0f09a9`，contract/storage/single-core PASS | 101,187,584 | `9bf5ea504c1b445df662dad266e039fb5900ff7589f5abbe79e5eafecdcfca75` |
| `image-candidate-oldadt-release-v4-cpus1.img` | 同候选的旧 binary-patch ADT 对照（args/manifest/kernel/addon/layout 逐项相同，仅 ADT 与 payload FAT/CRC 不同）：ADT `cdc7b8cc…` 14,112 B，CRC `0x2f129509` | 101,187,584 | `47e6b744b495a9671f636d6507d9ebe687bb8e58487238b808c175bad1bbb287` |
| `diting-recovery-boot.img` | TWRP RAM Recovery（ramoops/APFS 回读） | 127,148,032 | `67cf2dc9d247815bc5be8c33f4c717b5833f13ca93a4d371ce796bfa0c3c2d6a` |
| `b1-darwinboot24/diting-unixnu-uefi-darwinboot24.img` | B1 DarwinBoot24 bring-up 基线 | 101,187,584 | `285e6afa1f4291f10839619fbc06d09ce08842ac14d7143be20756d4c8f106fa` |
| `greenI2-log-menu.img` | Advanced Logger 菜单镜像（回读通道） | 101,187,584 | `32c1a7c72ea61a5f0f4aae1cf744a1c060fb7d6b57930cfabd4462f89fe1d680` |
| `artifacts/ci-42987806310/` | Diting OS 窗口 cdr 源（userdata 重写用） | 约 6.4 GiB | 见 AGENTS.md；恢复步骤见 `docs/RECOVERY.md` |

## 2. userdata 与系统窗口

> 回退资产（`ipados18-source/`、`windows/Data.img`、`prepared-420734-os.img`）已从 D: `build-work` 移到 WSL `/home/nagatoquin/unixnu/rollback-assets/`；D: `build-work` 现约 23 GB（2026-11-16 清理旧变体/旧 CI 产物后），`userdata-osditing-1109.sparse.img` 仍在 D:；救砖步骤见 `docs/RECOVERY.md`。

| 产物 | 用途 | 大小 | 说明 |
| --- | --- | --- | --- |
| `userdata-osditing-1109.sparse.img` | 当前可用恢复镜像：11-09 raw + Diting OS 窗口（`27c507c8…`） | 19,411,252,824 | sha256 `6c455decba368a736426aa5cbd8d3246eb52aa93c1e067f95eddfb9bb81d136e` |
| `out/userdata/userdata-osditing-1109.img` | 上者的 raw 源 | 19,411,238,912 | 保留，可重建 sparse |
| `out/userdata/userdata-root.img` | 11-09 基础 raw（Pong 布局 OS，仅作容器/回退素材） | 19,411,238,912 | sha256 `a30ed367…` |
| `/home/nagatoquin/unixnu/rollback-assets/prepared-420734-os.img` | OS 窗口回退镜像（11-09 原始内容） | 6,845,104,128 | sha256 `45b6344f8a23f9943ff8660ecfcc929f38bd1c87cf14d8fdaa8d7dd289f23fda` |
| `/home/nagatoquin/unixnu/rollback-assets/windows/Data.img` | Data 窗口回退（UUID 337CF716） | 8,589,934,592 | sha256 `1378adfe62916cf2cc01dfdca23ab847f489636a4790809024a3ab219b7f4095` |
| `/home/nagatoquin/unixnu/rollback-assets/ipados18-source/{OS,SystemOS,AppOS}.dmg` | 一次制备用还原源 | 约 11 GiB | 只读资产，保留 |

## 3. 重建入口

- release v4 镜像（当前生产路径）：`scripts/build-release-image-linux.py`（默认 `--diagnostics`，需要 `--gpu-addon`）。
- 官方打包路径（`scripts/package.sh` 与上游模板逐字节相同）：`scripts/package.sh --check --no-deps` 已验证（28 patches + defconfig）；
  完整 `--no-deps` 目前在 kernel 步停止于设备配方的 macOS 默认 `volume-layout` 路径，需本地输入 `DITING_VOLUME_LAYOUT`；
  对齐细节与迁移表见 `docs/GAP-ANALYSIS.md §5`（证据 `build-work/evidence-20261116-package-align/`）。
- bring-up / addon 镜像：`build-work/evidence-*/build-*.sh` 与 addon 打包脚本；发布前用 `scripts/check-loader-adt-contract.py`、`check-storage-bindings.py` 校验。
- userdata sparse：`python3 scripts/make-sparse-image.py <raw> <out.sparse> --chunk-mib 16`。
- 全窗写入：`scripts/flash-userdata-image.py --image <raw> --sparse <sparse> --product diting`。
- ramoops 回读：`scripts/extract-ramoops-ufs.py --reserve-mib 4` 或 `adb exec-out dd ... skip=58615291 count=1024`。

## 4. 保留策略

- 保留：`boot_a` 镜像、最近一个已验证桌面回退、当前候选镜像、Recovery、B1、userdata 当前可用 sparse 与 raw、OS/Data 回退镜像、还原源 DMG。
- 可重建删除：中间 addon 镜像（编号小于当前基线且无对应证据链）、重复 sparse（由 raw 重建约 20 s）、临时 clone 与旧备份（保留最近一套全量）。
- ramoops 证据（每个 4 MiB）全部保留；哈希在 `AGENTS.md` 与 `docs/STATUS.md`。
