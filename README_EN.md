# UniXNU-diting

[简体中文](README.md) | **English**

Format 2 device support for the Redmi K50 Ultra (`diting`), Qualcomm **SM8475**. Main targets **iPadOS 18.7.10 (22H374)** from iPad7,11 / J171AP, Darwin 24.6.0 / XNU 11417.140.69. Most driver sources descend from the Pong (Nothing Phone 2, same SM8475) port and are marked `provenance = "pong"` in [porting.toml](porting.toml) until re-verified on this device.

- [UniXNU tools](https://github.com/UniXNU/UniXNU); UEFI package in-tree at `platform-firmware/ditingPkg` ([uefi-pong](https://github.com/Chengdong-Yu/uefi-pong) is the external SM8475 reference)
- Official [migration](https://unixnu.com/en/porting/migration) and [device repository](https://unixnu.com/en/porting/device-repository) guides
- [Format 2 integration](migration/format2/README.zh.md), [OS migration](migration/ipados18/README.zh.md), [porting record](porting.toml),
  [status](docs/STATUS.md), [provenance](docs/PROVENANCE.md)

## Status (2026-11-16)

**Observed on Diting hardware** (each item traced in [`AGENTS.md`](AGENTS.md) and
[`docs/STATUS.md`](docs/STATUS.md)):

- **Desktop and touch**: with the Diting-layout OS (`/sbin/launchd` = `/diting/init`, sha256 `95cb7341...`;
  `libditing-ui18.dylib` 174,976 B consuming events through `/dev/diting-touch`) restored through the
  whole-userdata sparse path, addon18 boots to the iPadOS 18.7.10 desktop and the Goodix GT9916 touch
  works (tap, swipe, drag). The Pong-era layout (`/pong`, `libpong-ui18`) is not compatible with this
  device's touch bridge.
- **GPU / Metal hardware path**: the device log shows `DITING ADRENO: CP ready`, both `DITING METAL`
  lines, `DITING SCANOUT ... status=0` and GPU submits; the UI is still not smooth (see blockers).
- **Also verified**: CPU0-7 all report `first boot completed`; the six/seven GPU/ADSP addon files persist
  after chunked sync writes (`written=0 same=6/7`, Extensions stage/status 5/0); the PID 1
  `exec /sbin/launchd` EFAULT is fixed.

**Current blockers** (located in device logs, not inferred):

- **Wi-Fi**: the first smpe2 RPMh vote (`0x40508=7`) times out before PCIe training; no scan is reached.
- **Battery / ADSP**: ADSP reaches stage 6 and stage 7 times out on `0x30030=7` (-60); battery service
  is not published.
- **UI frame rate**: Metal pipeline compilation is not amortized (the plugin now embeds a primelist) and
  the shader cache is not persisted, which limits smoothness; this is the next GPU work item.
- **Power-off**: the kernel has no poweroff path, so holding the power button cannot power the device
  off; the next candidate kernel carries a PSCI SYSTEM_OFF long-press patch.

**Ready but not device-tested** (static checks PASS, `hardware_tested=false`): `diting-addon24-diag.img`
(`54ed270b...`, `e991983d` kernel + primelist plugin) and `diting-addon26-diag.img` (`ee7278b2...`,
fresh release kernel with pwrkey/PSCI SYSTEM_OFF, TCS1, touch-latency, primelist and the 7-file addon).

**Not achieved - do not claim usable**: Wi-Fi scan/association/DHCP, battery and charging, per-app Metal
compatibility and stable frame rate, audio (the live DT has dual CS35L41, not integrated), suspend/resume,
power-key shutdown.

## Driver repositories

Every board driver under `drivers/` is a vendored copy derived from the Chengdong-Yu `pong-*` community repositories (formerly referenced as submodules; the trees are now plain directories in this repository). Path names are unchanged so the build scripts and the drivers' relative `#include`s keep working.

| Path | Repository | Hardware |
| --- | --- | --- |
| `drivers/ArmCpu` | [pong-arm-cpu](https://github.com/Chengdong-Yu/pong-arm-cpu) | SM8475 GICv3 + ARM generic timer, PSCI secondaries; Diting variant of upstream [ArmCpu](https://github.com/UniXNU/ArmCpu) |
| `drivers/ArmDTPlatform` | [pong-arm-dt-platform](https://github.com/Chengdong-Yu/pong-arm-dt-platform) | Apple-format DT platform expert (`/chosen`/`/cpus`/`/arm-io`); Diting variant of upstream [ArmDTPlatform](https://github.com/UniXNU/ArmDTPlatform) |
| `drivers/NativeRamBlock` | [pong-ram-block](https://github.com/Chengdong-Yu/pong-ram-block) | RAM-backed Data volume (sparse seed + persistent overlay); Diting variant of upstream [RamBlock](https://github.com/UniXNU/RamBlock) |
| `drivers/DarwinBoot24` | [pong-darwin-boot24](https://github.com/Chengdong-Yu/pong-darwin-boot24) | Darwin 24 UEFI XNU loader + PONGFAT1; Darwin 24 variant of upstream [DarwinBoot](https://github.com/UniXNU/DarwinBoot) |
| `drivers/AdrenoMetal` | [pong-adreno-metal](https://github.com/Chengdong-Yu/pong-adreno-metal) | Adreno Metal frontend pinned at `c6d29ca`; upstream [AdrenoMetal](https://github.com/UniXNU/AdrenoMetal) |
| `drivers/NativeUfs` | [pong-ufs](https://github.com/Chengdong-Yu/pong-ufs) | SM8475 UFS host (`0x01d84000`), SID `0xe0`, SPI 265; SHNGROOT v1 three-window layout |
| `drivers/DitingAdreno` | [pong-adreno](https://github.com/Chengdong-Yu/pong-adreno) | Adreno 730 GMU/CP/HFI/ZAP/SMMU/scanout (Cape GPUCC) |
| `drivers/DitingMetal` | [pong-metal](https://github.com/Chengdong-Yu/pong-metal) | A730 Metal frontend for 22H374 with GOP scanout |
| `drivers/DitingPower` | [pong-power](https://github.com/Chengdong-Yu/pong-power) | ADSP PAS1, CS35L41 amps, NT37705 DCS backlight, battery |
| `drivers/DitingUsb` | [pong-usb](https://github.com/Chengdong-Yu/pong-usb) | SM8475 DWC3/eUSB2 + NXP repeater, 32 KiB DMA / SID0 |
| `drivers/DitingWifi` | [pong-wifi](https://github.com/Chengdong-Yu/pong-wifi) | QCA6490 over PCIe0 + MHI + ath11k, SID `0x1c01` |
| `drivers/DitingBootCapture` | [pong-boot-capture](https://github.com/Chengdong-Yu/pong-boot-capture) | Bounded diagnostic restart via PMK8350 SID0 SDAM7100 |

The shared header `drivers/DitingProbe.h` stays in this repository. No submodules are required; the `drivers/` trees are complete in this checkout.

## Build

Requires Python 3.12, dtc, selected Apple open source dependencies, matching 22H374 restore/ABI inputs and firmware obtained from Diting. The kernel and boot image build on Linux via `scripts/linux/` plus `xnu-linux-toolchain` (ld64 is the hard dependency; xcodebuild/iPhoneOS SDK is not). Xcode is only needed for the one-time OS-window content preparation. Source revisions are pinned in feeds, lock and migration records.

```sh
git clone https://github.com/UniXNU/UniXNU ../UniXNU-upstream
git -C ../UniXNU-upstream checkout 0fc0fc1f9ddd0fbd4787738afef38667df5e0a95
cp local.toml.example local.toml
# Set local build, Xcode and volume-layout paths in local.toml.
python3.12 scripts/migrate-diting-format2.py --unixnu ../UniXNU-upstream
python3.12 scripts/build-diting-format2.py --unixnu ../UniXNU-upstream --out ../diting-build --jobs 4
```

The entry point resolves ARM64, SM8475, OS and board layers, compiles the hardware DTS and invokes the Darwin24 builder. Outputs reside in `../diting-build/diting/ipados-18.7.10-22H374/diting_ipados18/`. See the OS migration guide for restore download, userland and userdata preparation; these require matching local binary inputs.

Image hashing, whole-image validation and device image readback are skipped by default. The protocol's SHNGROOT header checksum is retained.

## Packaging with GitHub Actions

When there is no local Xcode, Apple open-source dependency tree or private firmware to hand, let a GitHub-hosted macOS runner do the packaging. The workflow is `.github/workflows/package.yml` (name **package**), it runs on `macos-15-intel` and drives `scripts/package.sh` the way UniXNU's packaging document (`docs/porting/packaging.md`) describes, plus the userdata image that document does not cover.

### Two jobs

| job | what it does | artifacts |
| --- | --- | --- |
| **userdata image** | builds the prepared userland, the SHNGROOT directory and the whole userdata image from the IPSW at `ipsw_url` | `diting-userdata` (30 days), `volume-layout` (1 day) |
| **boot image, payload and kernel** | `scripts/package.sh --os …` runs deps / preflight / patches / build / pack / verify, then adds the two things the spec does not describe but the local flow does | `diting-package` (14 days) |

The jobs are split by disk, not by CPU: the userdata chain peaks near 37 GiB, the packaging job's XNU objects and EDK II output near 25 GiB, and a hosted runner has 14 GiB of RAM and 80–180 GiB of disk. The packaging job takes only a 2 KB `ci-volume-layout.json` from the other, so a failed or skipped `userdata` never blocks it.

### Running it by hand

1. Open the repository's **Actions** tab and pick **package** on the left.
2. Press **Run workflow** and choose the branch.
3. The OS profile is fixed to `ipados-18.7.10-22H374` (the only choice).
4. For a userdata image as well, put the restore download URL for Apple's iPadOS 18.7.10 (22H374) into `ipsw_url`. Leaving it empty skips that job, and the packaging job then compiles the kernel against uuid5 placeholder UUIDs, so that run's output cannot be booted on hardware.
5. To use the stock 22H374 kernelcache as a prelink base, tick `prelink`. It is off by default and the run uses the natively built kernel.
6. When the run finishes, download `diting-package` from **Artifacts** at the bottom of the run page, plus `diting-userdata` when that job ran.

The `package` job needs a repository secret named `UNIXNU_UNIQUE_CHIP_ID`: the device's 8-digit hexadecimal platform seed. Without it the payload step refuses to run, because the seed is compiled into the image and differs per chip.

The concurrency group is `package-${{ github.ref }}` with `cancel-in-progress: true`, so starting another run on the same branch cancels the one still going. Only `workflow_dispatch` triggers the workflow; pushing does not start a run.

### What the packaging job does

`scripts/package.sh` is byte-identical to UniXNU's `templates/package.sh`. It follows `board.toml [package] unixnu` to the UniXNU checkout and runs `unixnu release`. Output lands in `UniXNU/out/diting/<os>/<config>/`: `boot/boot.img`, `payload/payload.img`, `kernel/kernel.macho`, `package.manifest.json`.

Three things differ from the repository defaults on the runner, none of them incidental:

- **defconfig**: `release` always uses the `[package.defconfig]` mapping and there is no command-line override, so the runner repoints that mapping to `diting_ipados18_ci_defconfig`. The shipping configuration's Wi-Fi, backlight and Adreno stages need private firmware that the public repository does not carry, so CI cannot build it. The repository keeps the shipping mapping.
- **Build tree**: the shared kernel step's tree already has real `drivers/`, `kits/` and `patches/` directories, so the device kernel builder uses a separate tree and copies `mach.development.diting` back to the shared tree's `[kernel.prelink] kernel` path.
- **Volume UUIDs**: the kernel bakes the OS, SystemOS and Data UUIDs in as constants. A run that produced userdata uses that layout; otherwise fixed-namespace uuid5 placeholders keep the object tree reusable, at the cost of an output that only proves it compiles.

### Matching the local artifacts

`docs/porting/packaging.md` stops at `boot/boot.img`, while the local flow does two more things. CI performs them with `scripts/finalize-diting-adt.py` under the same parameters, so a CI image has the same shape as a local one:

- **ADT from the local generator**: the shared `devicetree.generate()` writes only root, chosen and the nodes configured under `[adt]`. The `diting,ufs-*` properties, touch and button resources and PMIC metadata that the kernel reads on `/arm-io` are not among them. This step calls `scripts/make-diting-adt-ipados18.py` with the local parameters: `--dram-size 0x300000000` (12 GiB), `--window-size 0x100000000` (4 GiB), `--cpus 1`, `--chip-id 0x8010`, `--development-debug`, `--skip-image-verification`, and stores the SHA-384 of `pong-boot-manifest.json` in `/chosen/boot-manifest-hash`. The result replaces `EFI/UniXNU/Payloads/kernel.macho.adt` inside `payload.img`, and a copy of `pong-boot-manifest.json` sits beside it.
- **Boot image in the flashable shape**: the firmware (`DitingBootMemoryDxe`) only accepts an initrd carrying the `PONGFAT1` envelope, while `release` puts `payload.img` into the ramdisk slot unwrapped. This step rewrites `boot/diting-xnu-initial.img` in the local container's shape: Android boot v4 header, empty kernel slot (this machine boots firmware from its own partition), ramdisk is the envelope plus `payload.img`, and 4096 zero bytes of empty signature area at the end. `boot/boot.img` remains the spec artifact that `release` wrote.

Inside that `PONGFAT1` envelope `payload.img` must be 96 MiB, because `DitingBootMemoryDxe` rejects an initrd over 128 MiB and the local `--fat-mib` is 96 as well. That is why `board.toml [payload] size_mib` is 96.

### The userdata image

There is one input: the download URL of Apple's iPadOS 18.7.10 / 22H374 restore (IPSW), in `ipsw_url`. Unpacking, decryption, mounting and assembly all happen on the runner.

The link must be https and end in `.ipsw`. A non-empty `ipsw_sha256` is checked against the whole IPSW after download, and a mismatch fails before a single byte is unpacked.

On the runner (`scripts/prepare-diting-userland-from-ipsw.py` chains the steps):

1. Download the IPSW (`scripts/download-ipados18-restore.py`, chunked and resumable), check its size and the sha256 when given.
2. Take the components with `scripts/prepare-ipados18-components.py --ipsw`, after confirming it really is 18.7.10 / 22H374 for an iPad7,11 or 7,12.
3. Decrypt the OS and SystemOS `.dmg.aea` files (`scripts/decrypt-ipados18-aea.py`, AEA profile 1).
4. Expand OS into a raw disk and mount it as `--os-root`, with the same raw disk as `--os-image`.
5. Create a fresh 5 GiB plain APFS volume, copy the stock SystemOS files with `userland/build-systemos18.py`, and emit `diting-ipados18-systemos.cdr`.
6. Create a fresh empty 8 GiB APFS volume, convert it to a raw disk, and use it as the Data starting point.
7. Run `userland/build-ipados18.py prepare` / `apply` / `finish`.
8. Check the five files, the build in `result.json`, image alignment and the three volume UUIDs with the validators in `scripts/stage-diting-userdata.py`.

Then it writes `ci-volume-layout.json`, generates the SHNGROOT directory (`scripts/prepare-ipados18-ufs-layout.py`, which reads about 19 GiB and is the slow part), and finally assembles the whole image from that directory (`scripts/build-diting-userdata-image.py`).

The three UUIDs are read from the APFS volume headers of the image, baked into the kernel's `XNU_OWNER_*_VOLUME_UUID` and written into the ADT's root-match value. **The kernel from a run and that run's userland belong together**: the UUIDs are kernel constants, so a different userland means rebuilding the kernel.

This step needs macOS with passwordless `sudo`: `apply` and `build-systemos18.py` must be root to write the stock files' uid/gid correctly. A failing `sudo -n true` fails the step rather than skipping a root step and pretending it worked.

The image is uploaded as four parts of `diting-userdata`, named `<name>.part00` … `.part03` (two-digit numbering, at most 8 GiB each for a ~19.4 GiB image, kept 30 days). Join them in order:

```sh
cat diting-ipados18-userdata.img.part00 diting-ipados18-userdata.img.part01 \
    diting-ipados18-userdata.img.part02 diting-ipados18-userdata.img.part03 > diting-ipados18-userdata.img
```

The image stops at the end of the last window rather than spanning the whole 454 GiB partition. Writing it to a phone is still `scripts/install-ipados18-ufs.py`, one window at a time with a final commit of the SHNGROOT directory; CI never pushes to a device.

Without `ipsw_url` the userdata job reports `staged=false` and stops. That is not a failure.

### Artifacts

`diting-package` (14 days):

| file | contents |
| --- | --- |
| `diting-xnu-initial.img` | the boot image in the local shape: Android boot v4, empty kernel slot, ramdisk is the `PONGFAT1` envelope plus `payload.img`, empty signature area; `diting-boot.json` records the parameters and the ADT and manifest digests |
| `boot.img` / `payload.img` | the spec artifacts `release` wrote; the ramdisk in `boot.img` is the unwrapped `payload.img` |
| `kernel/kernel.macho` | the kernel this run built (or prelinked) |
| `package.manifest.json` | the `release` manifest, with digests updated for the rewritten files |
| `pong-boot-manifest.json` | the same unsigned development boot description the local image carries |
| `ci-volume-layout.json` / `local.toml` | the volume layout this run used and the board-level local inputs written on the runner |

`diting-userdata` (30 days) is `.part00` … `.part03` plus `userdata-image.json` and `ci-volume-layout.json`. `volume-layout` (1 day) only passes the layout between the two jobs.

### What it does not do

- It does not flash a device or touch hardware; a run only produces files.
- It has no degraded mode: any failing step (download, component check, AEA decryption, `sudo`, `apply`, the five checks, packaging, the ADT and container checks) fails that step.
- The ADT and boot image are generated with the local parameters, and `--skip-image-verification` matches the local flow, so no hash audit beyond `image_sha256` happens; the container structure is still checked.
- No artifact has been on real hardware. CI validates container structure and packaged contents, not booting.
- The prelink slide is not yet expressed for this board, so the `prelink` path uses the local fixed base; that path has not been verified on a runner.

## Source boundaries and license

Only source, configuration, patches and scripts are published. IPSWs, Apple private binaries, firmware, credentials and generated userdata remain local and ignored. Machine paths belong in local configuration.

`DitingPlatform24` identifies the community A730/QCA6490 implementation (derived from the Diting work), independently of the upstream A740/WCN7850 driver. The versioned SM8475 seed is kept under `migration/format2/soc-seed`.

Board code uses BSD-2-Clause-Patent. Imported components retain their licenses and SPDX identifiers; see [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).

## Disclaimer and trademarks

- This is an unofficial, independent hardware porting effort. It is not affiliated with, endorsed by, or sponsored by Apple Inc., Xiaomi Inc., or Qualcomm Incorporated; trademarks belong to their respective owners.
- The work rewrites userdata LBA windows and boots a self-built UEFI chain; it can cause data loss or an unbootable device. Back up first; you use it at your own risk.
- The repository does not contain or redistribute Apple restore images, vendor firmware, or extracted binaries; obtain those on your own hardware or local environment.
