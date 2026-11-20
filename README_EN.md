# UniXNU-diting

[简体中文](README.md) | **English**

Format 2 device support for the Redmi K50 Ultra (`diting`), Qualcomm **SM8475**. Main targets **iPadOS 18.7.10 (22H374)** from iPad7,11 / J171AP, Darwin 24.6.0 / XNU 11417.140.69. Most driver sources descend from the Pong (Nothing Phone 2, same SM8475) port and are marked `provenance = "pong"` in [porting.toml](porting.toml) until re-verified on this device.

- [UniXNU tools](https://github.com/UniXNU/UniXNU); UEFI package in-tree at `platform-firmware/ditingPkg` ([uefi-pong](https://github.com/Chengdong-Yu/uefi-pong) is the external SM8475 reference)
- Official [migration](https://unixnu.com/en/porting/migration) and [device repository](https://unixnu.com/en/porting/device-repository) guides
- [Format 2 integration](migration/format2/README.zh.md), [OS migration](migration/ipados18/README.zh.md), [porting record](porting.toml),
  [status](docs/STATUS.md), [provenance](docs/PROVENANCE.md)


## iPadOS milestone (2026-11-20)

This checkout preserves the hardware-tested **iPadOS 18.7.10 / 22H374** baseline. The next phase will consider iOS or macOS as the base OS. The choice and bring-up are pending.

| Observed on Diting | Result |
| --- | --- |
| Boot and touch | Desktop boot, all eight cores online, and ordinary taps and swipes |
| Adreno 730 / display | Metal submissions and zero-copy scanout work. One auto-refresh per TE produced 121.2–121.6 Hz panel scanout and an average display latch wait of about 4.0–4.5 ms. Home-screen animation is smoother, with application composition sampled up to 110 fps |
| Wi‑Fi | Wi‑Fi worked in device use. Password entry in Settings remains incomplete |
| Storage | The existing 32 GiB Data window grew to 212.53 GiB on-device. The volume UUID and user data were preserved, the full OS and SystemOS hashes matched, and the last 4 MiB of a 1 GiB tail reserve remain available for ramoops |

Open issues include clipped keyboard controls, number-layer switching, Wi‑Fi password input, display ghosting, volume adjustment, video decoding and Bluetooth. Native USB remains off pending the firmware DMA handoff and userland usb-mux bridge. Sustained 120 fps application rendering and suspend/resume remain unverified.

See the [hardware status](docs/STATUS.md) and [reproduction guide](docs/REPRODUCE-ipados18.md).

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


## Build and packaging

The kernel builds on Linux or WSL with `xnu-linux-toolchain`. macOS provides the tools for preparing the Apple OS window and performing native APFS operations. CI runs [OS-window preparation](.github/workflows/diting-userdata.yml) and [firmware and boot packaging](.github/workflows/package.yml) as separate, manually dispatched workflows.

Use the matching 22H374 restore assets, board firmware and installed volume layout. The OS, SystemOS and Data UUIDs must match the kernel configuration. The [reproduction guide](docs/REPRODUCE-ipados18.md) records the build steps, checks and artifacts to retain.

## Source boundaries and license

Only source, configuration, patches and scripts are published. IPSWs, Apple private binaries, firmware, credentials and generated userdata remain local and ignored. Machine paths belong in local configuration.

`DitingPlatform24` identifies the community A730/QCA6490 implementation (derived from the Diting work), independently of the upstream A740/WCN7850 driver. The versioned SM8475 seed is kept under `migration/format2/soc-seed`.

Board code uses BSD-2-Clause-Patent. Imported components retain their licenses and SPDX identifiers; see [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).

## Disclaimer and trademarks

- This is an unofficial, independent hardware porting effort. It is not affiliated with, endorsed by, or sponsored by Apple Inc., Xiaomi Inc., or Qualcomm Incorporated; trademarks belong to their respective owners.
- The work rewrites userdata LBA windows and boots a self-built UEFI chain; it can cause data loss or an unbootable device. Back up first; you use it at your own risk.
- The repository does not contain or redistribute Apple restore images, vendor firmware, or extracted binaries; obtain those on your own hardware or local environment.
