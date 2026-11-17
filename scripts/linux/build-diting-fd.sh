#!/usr/bin/env bash
#
# Build the Diting firmware volume (SILICIUM_UEFI.fd) on Linux.
#
# Same steps as .github/workflows/package.yml "build the diting volume", with one
# deliberate difference: the loader is the official drivers/DarwinBoot component (pin 3c75734),
# copied over Platforms/Xiaomi/DarwinBootPkg without source edits. darwin-boot-diting.patch is NOT
# applied: it only renames pong-* tokens in the vendored loader and leaves the
# package split across two sources.
#
#   scripts/linux/build-diting-fd.sh --uefi-dir ~/unixnu/uefi-b1-tree \
#       --device <device repo> --out build-work/b1-fd
#
# Runs without root. Two host gaps CI does not have are covered here:
#   * Ubuntu keeps ensurepip in python3.14-venv, so `python3 -m venv` cannot seed
#     pip without apt; the venv is created with --without-pip and seeded from the
#     distro pip wheel unpacked under --out.
#   * edk2toolext fetches the mu_nasm nuget dependency through mono; without
#     mono-complete the same pinned package is fetched from the same feed and
#     laid out where the ext_dep descriptor expects it.
#
set -euo pipefail

UEVI=""
DEVICE=$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)
OUT=$(pwd)/build-work/b1-fd
VENV=""
while [ $# -gt 0 ]; do
  case "$1" in
    --uefi-dir) UEVI=$2; shift 2;;
    --device) DEVICE=$2; shift 2;;
    --out) OUT=$2; shift 2;;
    --venv) VENV=$2; shift 2;;
    *) echo "unknown argument: $1" >&2; exit 2;;
  esac
done
[ -n "$UEVI" ] || { echo "--uefi-dir is required" >&2; exit 2; }
UEVI=$(cd "$UEVI" && pwd)
DEVICE=$(cd "$DEVICE" && pwd)
mkdir -p "$OUT"
# The build changes directory into the UEFI tree; resolve a relative --out
# against the invocation directory before that happens.
OUT=$(cd "$OUT" && pwd)

log() { printf '== %s\n' "$*"; }

# Fetch a submodule with retries: a transient clone failure must not be taken for
# a build defect.
init_submodule() {
  local repo=$1 path=$2 attempt
  for attempt in 1 2 3; do
    if git -C "$repo" submodule update --init --depth 1 "$path"; then
      return 0
    fi
    echo "submodule $path attempt $attempt failed; retrying" >&2
    sleep 10
  done
  return 1
}

# Put a working pip inside the venv at $1 without root.
#
# Ubuntu keeps ensurepip in the python3.14-venv package, so on a host without it
# (and without sudo) `python3 -m venv` cannot seed pip. Unpack the distro pip
# wheel out of python3-pip-whl into the venv instead of installing anything
# system-wide; fall back to bootstrap.pypa.io only when that wheel is missing.
seed_venv_pip() {
  local venv=$1 py=$1/bin/python cache=$OUT/python-bootstrap
  local wheel="" deb tmp site
  "$py" -m pip --version >/dev/null 2>&1 && return 0
  mkdir -p "$cache"
  wheel=$(ls "$cache"/pip-*.whl 2>/dev/null | head -1 || true)
  if [ -z "$wheel" ]; then
    log "unpack python3-pip-whl into $cache (no root)"
    ( cd "$cache" && apt-get download python3-pip-whl ) >"$cache/apt-get-download.log" 2>&1 || true
    deb=$(ls "$cache"/python3-pip-whl_*.deb 2>/dev/null | head -1 || true)
    if [ -n "$deb" ]; then
      tmp=$(mktemp -d)
      if dpkg -x "$deb" "$tmp"; then
        wheel=$(ls "$tmp"/usr/share/python-wheels/pip-*.whl 2>/dev/null | head -1 || true)
        if [ -n "$wheel" ]; then
          cp -a "$wheel" "$cache/"
          wheel=$cache/$(basename "$wheel")
        fi
      fi
      rm -rf "$tmp"
    fi
  fi
  if [ -n "$wheel" ]; then
    site=$("$py" -c 'import sysconfig; print(sysconfig.get_paths()["purelib"])')
    "$py" - "$wheel" "$site" <<'PY'
import sys, zipfile
with zipfile.ZipFile(sys.argv[1]) as wheel:
    wheel.extractall(sys.argv[2])
print("unpacked", sys.argv[1])
PY
  fi
  "$py" -m pip --version >/dev/null 2>&1 && return 0
  log "no distro pip wheel; bootstrapping pip with get-pip.py"
  curl -fsSL https://bootstrap.pypa.io/get-pip.py -o "$cache/get-pip.py"
  "$py" "$cache/get-pip.py"
  "$py" -m pip --version >/dev/null 2>&1
}

# Place the mu_nasm nuget dependency where Mu_Basecore/BaseTools/Bin/
# nasm_ext_dep.yaml expects it, without NuGet.exe (which needs mono).
#
# edk2toolext's NugetDependency would install mu_nasm@20016.1.1 from the projectmu
# Basetools-Binary feed into Mu_Basecore/BaseTools/Bin/mu_nasm_extdep and write
# extdep_state.yaml with the version; the package is a plain zip, so the same
# bytes can be fetched and unpacked here. The pinned sha256 makes a changed feed
# payload a hard failure instead of a silent difference from CI.
seed_mu_nasm() {
  local extdep=$1 cache=$2
  python3 - "$extdep" "$cache" <<'PY'
import hashlib
import io
import json
import os
import shutil
import sys
import urllib.request
import zipfile
from pathlib import Path

FEED_INDEX = "https://pkgs.dev.azure.com/projectmu/mu/_packaging/Basetools-Binary/nuget/v3/index.json"
NAME = "mu_nasm"
VERSION = "20016.1.1"
SHA256 = "534b21331f70f13c14c03e08bc29968fbe4c5b1219bbcf4b777c4ff158b9e584"

extdep = Path(sys.argv[1])
cache = Path(sys.argv[2])
state = extdep / "extdep_state.yaml"
published = extdep / "Linux-x86-64" / "nasm"
if state.is_file() and published.is_file() and VERSION in state.read_text():
    print(f"mu_nasm {VERSION} already seeded at {extdep}")
    raise SystemExit(0)

cache.mkdir(parents=True, exist_ok=True)
nupkg = cache / f"{NAME}.{VERSION}.nupkg"


def download(url: str) -> bytes:
    print("GET", url)
    with urllib.request.urlopen(url, timeout=120) as response:
        return response.read()


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


if nupkg.is_file() and digest(nupkg.read_bytes()) == SHA256:
    data = nupkg.read_bytes()
elif nupkg.is_file():
    print(f"cached {nupkg} does not match the pinned sha256; downloading again")
    data = b""
else:
    data = b""

if not data:
    index = json.loads(download(FEED_INDEX))
    base = next(res["@id"].rstrip("/") for res in index["resources"]
                if res["@type"].startswith("PackageBaseAddress"))
    url = f"{base}/{NAME.lower()}/{VERSION.lower()}/{NAME.lower()}.{VERSION.lower()}.nupkg"
    data = download(url)
    nupkg.write_bytes(data)

got = digest(data)
if got != SHA256:
    raise SystemExit(f"{NAME} {VERSION} sha256 {got} != pinned {SHA256}")

with zipfile.ZipFile(io.BytesIO(data)) as archive:
    payload = [name for name in archive.namelist() if name.startswith(NAME + "/")]
    if not payload:
        raise SystemExit(f"{nupkg} has no {NAME}/ payload")
    scratch = cache / f"{NAME}-{VERSION}-unpack"
    if scratch.is_dir():
        shutil.rmtree(scratch)
    archive.extractall(scratch)
    if extdep.is_dir():
        shutil.rmtree(extdep)
    shutil.copytree(scratch / NAME, extdep)
    shutil.rmtree(scratch)

# The zip carries no POSIX modes; the ext_dep is put on PATH and executed.
for platform in extdep.iterdir():
    if platform.is_dir():
        for binary in platform.iterdir():
            if binary.is_file():
                os.chmod(binary, 0o755)
state.write_text(f"version: {VERSION}\n")
if not published.is_file():
    raise SystemExit(f"seeded {extdep} but {published} is missing")
print(f"seeded mu_nasm {VERSION} at {extdep} (sha256 {SHA256})")
PY
}

# The reference checkout may have empty submodule directories; the volume build
# needs the Mu base tree and the logging library it links.
if [ ! -f "$UEVI/Mu_Basecore/MdeModulePkg/Core/Dxe/DxeMain.inf" ]; then
  log "initialize uefi-mondrian submodules"
  for path in Binaries Common/Mu Common/Mu_OEM_Sample Mu_Basecore Silicium-ACPI; do
    init_submodule "$UEVI" "$path"
  done
  git -C "$UEVI/Mu_Basecore" submodule update --init --depth 1 --recursive
fi
# diting.dsc links OpenSSL through Silicon/Silicium/OpensslPkg. CI checks the tree
# out with submodules: recursive; initializing only the five top paths above leaves
# this one empty, so fetch it here as stuart setup would.
if [ ! -f "$UEVI/Silicon/Silicium/OpensslPkg/Library/OpensslLib/openssl/Configure" ]; then
  log "initialize the openssl submodule"
  init_submodule "$UEVI" Silicon/Silicium/OpensslPkg/Library/OpensslLib/openssl
fi

# 1. AdvancedLoggerLib in the DXE core: Mu's DxeMain never consumes it.
log "insert AdvancedLoggerLib into DxeMain.inf"
python3 - "$UEVI" <<'PY'
import sys
from pathlib import Path
uefi = Path(sys.argv[1])
path = uefi / "Mu_Basecore/MdeModulePkg/Core/Dxe/DxeMain.inf"
data = path.read_bytes()
if b"AdvancedLoggerLib" in data:
    print("already present")
else:
    nl = b"\r\n" if b"\r\n" in data else b"\n"
    marker = b"[Guids]" + nl
    if marker not in data:
        raise SystemExit("DxeMain.inf has no [Guids] section")
    add = b"  AdvancedLoggerLib         ## UniXNU: create the DXE Advanced Logger buffer" + nl
    path.write_bytes(data.replace(marker, add + nl + marker, 1))
    print("inserted")
PY

# 2. Device firmware package and resources.
log "copy platform-firmware"
rm -rf "$UEVI/Platforms/Xiaomi/ditingPkg"
cp -a "$DEVICE/platform-firmware/ditingPkg" "$UEVI/Platforms/Xiaomi/ditingPkg"
mkdir -p "$UEVI/Resources/DTBs"
cp -a "$DEVICE/platform-firmware/ditingPkg/FdtBlob/sm8475-xiaomi-diting.dtb" "$UEVI/Resources/DTBs/diting.dtb"
: > "$UEVI/Resources/ramdisk"
cp -a "$DEVICE/platform-firmware/diting.toml" "$UEVI/Resources/Configs/diting.toml"

# 3. Single loader source: replace the vendored package with DarwinBoot24.
log "replace DarwinBootPkg with official drivers/DarwinBoot"
rm -rf "$UEVI/Platforms/Xiaomi/DarwinBootPkg"
cp -a "$DEVICE/drivers/DarwinBoot/DarwinBootPkg" "$UEVI/Platforms/Xiaomi/DarwinBootPkg"

# 4. AdvancedLogger: retry LocateProtocol until the protocol exists.
log "patch AdvancedLoggerLib locate latch"
python3 - "$UEVI" <<'PY'
import sys
from pathlib import Path
uefi = Path(sys.argv[1])
path = uefi / "Common/Mu/AdvLoggerPkg/Library/AdvancedLoggerLib/Dxe/AdvancedLoggerLib.c"
data = path.read_bytes()
nl = b"\r\n" if b"\r\n" in data else b"\n"
old = b"  if (!mInitialized) {" + nl + b"    mInitialized = TRUE;" + nl
if old not in data:
    done = b"} else {" + nl + b"        mInitialized = TRUE;"
    if done in data:
        print("already retried")
    else:
        raise SystemExit("AdvancedLoggerLib.c latch site not found")
else:
    data = data.replace(old, b"  if (!mInitialized) {" + nl, 1)
    needle = (
        b"        Status = EFI_NOT_FOUND;" + nl
        + b"      }" + nl
        + b"    }" + nl
    )
    insert = (
        b"        Status = EFI_NOT_FOUND;" + nl
        + b"      } else {" + nl
        + b"        mInitialized = TRUE;" + nl
        + b"      }" + nl
        + b"    }" + nl
    )
    if needle not in data:
        raise SystemExit("AdvancedLoggerLib.c signature check not found")
    path.write_bytes(data.replace(needle, insert, 1))
    print("retries until the protocol exists")
PY

# 5. (removed) the official DarwinBoot source is used unmodified.

# 6. Python environment for stuart/build_uefi.py.
#
# CI installs python3-venv, so `python3 -m venv` seeds pip there. Locally there is
# no root and Ubuntu keeps ensurepip in python3.14-venv: create the venv without
# pip and seed it from the distro wheel (see seed_venv_pip). Either path leaves pip
# inside $VENV, so build_uefi.py imports the requirements from that interpreter.
# An interrupted earlier run leaves a venv whose python exists but has no pip, so
# the pip probe, not the python probe, decides whether to (re)create it.
VENV=${VENV:-$OUT/uefi-venv}
if [ ! -x "$VENV/bin/python" ] || ! "$VENV/bin/python" -m pip --version >/dev/null 2>&1; then
  log "create venv $VENV"
  rm -rf "$VENV"
  if ! python3 -m venv "$VENV" 2>"$OUT/venv-create.log"; then
    log "python3 -m venv cannot seed pip (no ensurepip/python3.14-venv); creating $VENV without pip"
    rm -rf "$VENV"
    python3 -m venv --without-pip "$VENV"
    seed_venv_pip "$VENV"
  fi
fi
# shellcheck disable=SC1091
. "$VENV/bin/activate"
python3 -m pip --version
python3 -m pip install --quiet --upgrade pip
python3 -m pip install --quiet -r "$UEVI/pip-requirements.txt"

# 7. Seed the two ext deps that GitHub releases answer with 504.
log "seed ext deps"
python3 "$DEVICE/platform-firmware/seed-ext-deps.py" "$DEVICE/platform-firmware/vendor" "$UEVI"

# 7b. mu_nasm normally arrives through NuGet.exe under mono (mono-complete in CI).
if ! command -v mono >/dev/null 2>&1; then
  log "mono is absent; seeding the mu_nasm nuget dependency from the same pinned feed"
  seed_mu_nasm "$UEVI/Mu_Basecore/BaseTools/Bin/mu_nasm_extdep" "$OUT/nuget-cache"
fi

# 8. Build.
log "build_uefi.py -d diting"
cd "$UEVI"
for attempt in 1 2 3; do
  if python3 build_uefi.py -d diting; then
    break
  fi
  echo "firmware build attempt $attempt failed; retrying" >&2
  sleep 10
done
FD="$UEVI/Build/ditingPkg/RELEASE_CLANGPDB/FV/SILICIUM_UEFI.fd"
[ -f "$FD" ] || { echo "missing firmware volume: $FD" >&2; exit 1; }
sha256sum "$FD"
mkdir -p "$OUT"
cp -a "$FD" "$OUT/SILICIUM_UEFI.fd"
cp -a "$UEVI/BootShim/BootShim.bin" "$OUT/BootShim.bin"
cp -a "$UEVI/Resources/Scripts/mkbootimg.py" "$OUT/mkbootimg.py"
cp -a "$UEVI/Resources/Configs/diting.toml" "$OUT/diting.toml"
log "done: $OUT"
