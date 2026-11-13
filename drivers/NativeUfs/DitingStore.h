// SPDX-License-Identifier: BSD-2-Clause-Patent
#pragma once
// ---- Persistent Data store window (diting_data_persist) ---------------------------------------
// The RAM block driver's overlay (drivers/NativeRamBlock PersistOverlay.h) asks once for a window
// of the given size at the END of the userdata partition. diting_data_persist=1 opens it read-only:
// the window and an earlier overlay's header are proved but nothing is written back. Mode 2
// additionally accepts writes, which go through the shared FUA write path and therefore need the
// same diting_ufs_readwrite permission as every other write. A window is refused unless it lies
// inside the partition and clear of the flashed root image plus a 4 MiB guard. All exports are
// consumed through weak imports: a build or boot without this driver keeps a volatile disk.
//
// Include at file scope, after the transport's anonymous namespace: this header needs gHost and
// the command helpers it declares (hostRead4k, hostWrite4kLocked, hostSyncCache, kDataMax), the
// layout helpers (le32, rootCrc32), transportFailure, PE_parse_boot_argn, IOLog, IOLock and the
// C memory primitives. The exports must stay outside that namespace so their linkage is global.
namespace {
struct StoreGeometry {
  bool valid;
  uint64_t first, last, imageBytes, entriesLba;
  uint32_t headerCrc, entriesCrc, entryCount;
};
StoreGeometry gStoreGeometry;
uint64_t gStoreRegionFirst, gStoreRegionBlocks;

// Boot arguments are parsed once and cached: an overlay written by an earlier boot is found again
// only when the placement rule is identical on every boot.
static unsigned storeMode (void)
{
  static int cached = -1;
  if (cached < 0) {
    uint32_t value = 0;
    if (!PE_parse_boot_argn ("diting_data_persist", &value, sizeof (value)) || value > 2) value = 0;
    cached = static_cast<int> (value);
  }
  return static_cast<unsigned> (cached);
}

// 4096-byte blocks held back at the very end of userdata, below the store (diting_data_reserve,
// in MiB, default 0). Diting has no diagnostic-log window down there; the reserve exists only so
// a future consumer of the partition tail does not silently move the store.
static uint64_t storeReserveBlocks (void)
{
  static int64_t cached = -1;
  if (cached < 0) {
    uint32_t mib = 0;
    if (!PE_parse_boot_argn ("diting_data_reserve", &mib, sizeof (mib)) || mib > 16384) mib = 0;
    cached = static_cast<int64_t> (mib) * 256;   // 4096-byte blocks
  }
  return static_cast<uint64_t> (cached);
}
}

extern "C" unsigned native_ufs_store_mode (void) { return storeMode (); }

// Returns 1 and the first absolute 4096-byte LBA of the window, 0 on refusal (reason in *why).
extern "C" int native_ufs_store_open (uint64_t blocks, uint64_t *firstLba, const char **why)
{
  const char *reason = "";
  int ok = 0;
  if (!storeMode ()) reason = "off";
  else if (!gStoreGeometry.valid || !gHost.ready) reason = "no root layout";
  else if (gStoreRegionBlocks) reason = "already open";
  else {
    uint64_t partition = gStoreGeometry.last - gStoreGeometry.first + 1;
    uint64_t imageBlocks = (gStoreGeometry.imageBytes + 4095) / 4096;
    const uint64_t reserve = storeReserveBlocks ();
    if (!blocks || reserve >= partition || blocks > partition - reserve) reason = "size";
    // Every window the SHNGROOT manifest declares ends inside imageBytes, so a window starting
    // above the image plus a 4 MiB guard is also clear of all published media.
    else if (partition - blocks - reserve < imageBlocks + 1024) reason = "overlaps the root image";
    else if (storeMode () == 2 && !gHost.writable) reason = "storage writes disabled";
    else {
      gStoreRegionFirst = gStoreGeometry.last + 1 - reserve - blocks;
      gStoreRegionBlocks = blocks;
      if (firstLba) *firstLba = gStoreRegionFirst;
      ok = 1;
    }
  }
  if (why) *why = reason;
  if (!ok && storeMode ()) IOLog ("DITING_UFS: persistent store window refused: %s\n", reason);
  return ok;
}

extern "C" int native_ufs_store_read (uint64_t rel, uint32_t blocks, void *dst)
{
  if (!gStoreRegionBlocks || !gHost.lock || !dst || !blocks || rel >= gStoreRegionBlocks ||
      blocks > gStoreRegionBlocks - rel) return 0;
  while (blocks) {
    uint32_t chunk = blocks > kDataMax / 4096 ? static_cast<uint32_t> (kDataMax / 4096) : blocks;
    if (hostRead4k (0, gStoreRegionFirst + rel, chunk, dst) != kIOReturnSuccess) {
      transportFailure ("persistent store read");
      return 0;
    }
    dst = static_cast<uint8_t *> (dst) + chunk * 4096ULL;
    rel += chunk;
    blocks -= chunk;
  }
  return 1;
}

extern "C" int native_ufs_store_write (uint64_t rel, uint32_t blocks, const void *src)
{
  if (storeMode () != 2 || !gStoreRegionBlocks || !gHost.writable || !gHost.lock || !src || !blocks ||
      rel >= gStoreRegionBlocks || blocks > gStoreRegionBlocks - rel) return 0;
  while (blocks) {
    uint32_t chunk = blocks > kDataMax / 4096 ? static_cast<uint32_t> (kDataMax / 4096) : blocks;
    // Stage the payload into the shared DMA area, then the shared FUA write: the block is on the
    // medium when the command completes, so the overlay needs no separate cache flush. The rel
    // bounds above are the write's window check; the absolute range can never leave the open window.
    IOLockLock (gHost.lock);
    IOReturn status;
    if (!gHost.ready || gHost.poisoned) {
      status = kIOReturnNotReady;
    } else {
      memcpy (gHost.virt + kDataOffset, src, chunk * 4096ULL);
      status = hostWrite4kLocked (0, gStoreRegionFirst + rel, chunk);
    }
    IOLockUnlock (gHost.lock);
    if (status != kIOReturnSuccess) {
      transportFailure ("persistent store write");
      return 0;
    }
    src = static_cast<const uint8_t *> (src) + chunk * 4096ULL;
    rel += chunk;
    blocks -= chunk;
  }
  return 1;
}

extern "C" int native_ufs_store_sync (void)
{
  // Every write already used FUA; the SYNCHRONIZE CACHE(10) is still issued so a caller asking for
  // a flush gets a real LUN-wide one.
  return storeMode () == 2 && gStoreRegionBlocks && hostSyncCache () == kIOReturnSuccess;
}

// Re-read the GPT header and entry array and compare their CRCs with what was recorded at root
// start. 0 = unchanged; any other value names the stage that disagreed.
extern "C" unsigned native_ufs_store_gpt_check (void)
{
  if (!gStoreGeometry.valid || !gHost.ready) return 1;
  static uint8_t block[4096];
  if (hostRead4k (0, 1, 1, block) != kIOReturnSuccess) return 2;
  uint32_t headerBytes = le32 (block + 12);
  if (headerBytes < 92 || headerBytes > 4096 || rootCrc32 (block, headerBytes, true) != le32 (block + 16) ||
      le32 (block + 16) != gStoreGeometry.headerCrc) return 3;
  uint32_t blocks = (gStoreGeometry.entryCount * 128 + 4095) / 4096;
  static uint8_t entries[4096 * 4];
  if (blocks > 4 || hostRead4k (0, gStoreGeometry.entriesLba, blocks, entries) != kIOReturnSuccess) return 4;
  return rootCrc32 (entries, gStoreGeometry.entryCount * 128) == gStoreGeometry.entriesCrc ? 0 : 5;
}
