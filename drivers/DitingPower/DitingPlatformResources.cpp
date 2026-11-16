/* SPDX-License-Identifier: BSD-2-Clause-Patent */
/* Diting APSS 的共享资源。Wi-Fi 和 ADSP 共用供电请求槽，GPU 管理自己的槽。 */
#include <IOKit/IOLib.h>
#include <IOKit/IODeviceMemory.h>
#include <kern/clock.h>
#include "DitingPlatformResources.h"

namespace {
IOLock *powerLock, *smmuLeaseLock, *scmCallLock;
IOMemoryMap *rscMap;
volatile uint8_t *rsc;
extern "C" int native_ufs_debug_write(uint64_t, uint32_t, const void *) __attribute__((weak_import));
extern "C" vm_offset_t diting_ramoops_mapped_base(void);
extern "C" uint32_t diting_ramoops_zone_size(unsigned);
void voteFlush() {
    if (!native_ufs_debug_write) return;
    vm_offset_t base = diting_ramoops_mapped_base();
    if (!base) return;
    uint32_t blocks = (diting_ramoops_zone_size(0) + 16 + 4095) / 4096;
    if (blocks > 512) blocks = 512;
    if (blocks) native_ufs_debug_write(0, blocks, reinterpret_cast<const void *>(base));
    volatile uint64_t *sig = reinterpret_cast<volatile uint64_t *>(base + 0x1f0000);
    if ((*sig >> 32) == 0x454c3158)
        native_ufs_debug_write(0x1f0, 2, reinterpret_cast<const void *>(base + 0x1f0000));
}

void initLock(IOLock **slot) {
    if (__atomic_load_n(slot, __ATOMIC_ACQUIRE)) return;
    IOLock *lock = IOLockAlloc(), *empty = nullptr;
    if (lock && !__atomic_compare_exchange_n(slot, &empty, lock, false,
                                            __ATOMIC_ACQ_REL, __ATOMIC_ACQUIRE)) IOLockFree(lock);
}
uint64_t now() {
    uint64_t ns = 0;
    absolutetime_to_nanoseconds(mach_absolute_time(), &ns);
    return ns / 1000000;
}
uint32_t rd(unsigned off) {
    uint32_t value = *reinterpret_cast<volatile uint32_t *>(rsc + off);
    __asm__ volatile("dmb oshld" ::: "memory");
    return value;
}
void wr(unsigned off, uint32_t value) {
    *reinterpret_cast<volatile uint32_t *>(rsc + off) = value;
    __asm__ volatile("dsb oshst" ::: "memory");
}
bool mapped() {
    if (rsc) return true;
    auto memory = IODeviceMemory::withRange(0x17a20000, 0x10000);
    if (!memory) return false;
    rscMap = memory->map(kIOMapAnywhere | kIOMapInhibitCache);
    memory->release();
    if (rscMap) rsc = reinterpret_cast<volatile uint8_t *>(rscMap->getVirtualAddress());
    return rsc != nullptr;
}
bool fail(const char *message) {
    IOLog("Diting resources: %s\n", message);
    return false;
}
bool rawVote(uint32_t addr, uint32_t value) {
    IOLog("Diting resources: vote %x=%u pre\n", addr, value);
    voteFlush();
    constexpr unsigned other = 0xd00 + 3 * 0x2a0;
    unsigned caps = rd(0xc), count = (caps >> 12) & 63, ncpt = (caps >> 27) & 31;
    IOLog("Diting resources: vote %x caps=%x\n", addr, caps);
    voteFlush();
    if (((rd(0) >> 16) & 255) >= 3 || count < 8 || ncpt < 1)
        return fail("RPMh controller unavailable");
    unsigned tcs = DITING_RPMH_SHARED_TCS;
    if (rd(0xd00 + tcs * 0x2a0 + 0x1c) || !rd(0xd00 + tcs * 0x2a0 + 0x18)) {
        static const unsigned kOrder[] = {2u, 0u};
        tcs = 3;
        for (unsigned cand : kOrder)
            if (!rd(0xd00 + cand * 0x2a0 + 0x1c) && rd(0xd00 + cand * 0x2a0 + 0x18)) { tcs = cand; break; }
        if (tcs >= 3) return fail("no idle active TCS");
        IOLog("Diting resources: shared slot busy, using TCS%u\n", tcs);
        voteFlush();
    }
    const unsigned b = 0xd00 + tcs * 0x2a0, irq = 1u << tcs;
    if (unsigned armed = rd(b + 0x1c))
        IOLog("Diting resources: TCS%u pre-armed mask=%x addr0=%x\n", tcs, armed, rd(b + 0x34));
    if (!rd(other + 0x18)) {
        unsigned mask = rd(other + 0x1c);
        for (unsigned i = 0; i < ncpt && i < 16; i++)
            if ((mask & (1u << i)) && rd(other + 0x34 + 20 * i) == addr)
                return fail("conflicting RPMh transaction");
    }
    wr(b + 0x14, rd(b + 0x14) & ~(1u << 24));
    wr(b + 0x14, rd(b + 0x14) & ~(1u << 16));
    wr(b + 0x1c, 0); wr(0xd08, irq);
    wr(b + 0x30, 0x10108); wr(b + 0x34, addr); wr(b + 0x38, value);
    IOLog("Diting resources: vote %x cmd written tcs=%u\n", addr, tcs);
    voteFlush();
    wr(b + 0x10, 1); wr(b + 0x1c, 1);
    wr(0xd00, rd(0xd00) | irq);
    wr(b + 0x14, 1u << 16);
    wr(b + 0x14, (1u << 16) | (1u << 24));
    IOLog("Diting resources: vote %x triggered, polling\n", addr);
    voteFlush();
    const char *via = nullptr;
    bool done = false;
    uint64_t end = now() + 200;
    do {
        if (rd(0xd04) & irq) { done = true; via = "irq"; break; }
        // Vendor completion: CMD_STATUS bit8 ISSUED | bit16 COMPL (rpmh-rsc.c).
        // The command may complete without the TCS IRQ and without the idle
        // readback, which is the failure both ADSP stage 7 and WiFi smpe3 show;
        // accept the status register as an extra proof, never as a replacement.
        unsigned st = rd(b + 0x3c);
        if ((st & 0x10100) == 0x10100) { done = true; via = "status"; break; }
        if ((st & 0x10000) && rd(b + 0x18)) { done = true; via = "status"; break; }
        IODelay(10);
    } while (now() < end);
    wr(b + 0x14, rd(b + 0x14) & ~(1u << 24));
    wr(b + 0x14, rd(b + 0x14) & ~(1u << 16));
    wr(b + 0x1c, 0); wr(b + 0x10, 0); wr(0xd08, irq);
    if (!done) {
        IOLog("Diting resources: timeout tcs=%u st=%x idle=%x irq=%x ctrl=%x en=%x msgid=%x caddr=%x cdata=%x\n",
              tcs, rd(b + 0x3c), rd(b + 0x18), rd(0xd04), rd(b + 0x14), rd(b + 0x1c),
              rd(b + 0x30), rd(b + 0x34), rd(b + 0x38));
        voteFlush();
        return fail("RPMh response timeout");
    }
    IOLog("Diting resources: vote %x=%u committed via=%s\n", addr, value, via);
    voteFlush();
    return true;
}
}

extern "C" void diting_rpmh_init(void) {
    initLock(&powerLock); initLock(&smmuLeaseLock);
}
extern "C" bool diting_rpmh_vote(uint32_t address, uint32_t value) {
    diting_rpmh_init();
    if (!powerLock) return false;
    IOLockLock(powerLock);
    bool ok = mapped() && rawVote(address, value);
    IOLockUnlock(powerLock);
    return ok;
}
extern "C" bool diting_smmu_lease_lock(void) {
    diting_rpmh_init();
    if (!smmuLeaseLock) return false;
    IOLockLock(smmuLeaseLock);
    return true;
}
extern "C" void diting_smmu_lease_unlock(void) {
    if (smmuLeaseLock) IOLockUnlock(smmuLeaseLock);
}

/* A suspended/interrupted secure transaction owns its session across
 * resumes. Serialize the complete GPU/ADSP call, never individual SMCs. */
extern "C" bool diting_scm_call_lock(void) {
    initLock(&scmCallLock);if(!scmCallLock)return false;
    IOLockLock(scmCallLock);return true;
}
extern "C" void diting_scm_call_unlock(void) {
    if(scmCallLock)IOLockUnlock(scmCallLock);
}
