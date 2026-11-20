/* SPDX-License-Identifier: BSD-2-Clause-Patent */
/* Diting display scanout: zero-copy DPU page-flipping over loader-reserved
 * low-RAM panel-pool canvas slots + HS-mode 120 Hz DCS timing switch for
 * Xiaomi 42-02-0a (default) and 36-02-0b panels, while preserving the v2
 * userspace presenter fallback ABI (DitingScanoutWire.h) untouched. */
#include "DitingAdrenoScanout.h"
#include "../DitingPower/DitingDsiLease.h"
#define NATIVE_GPU_TRACE_OPTIONAL
#include "submit/NativeGpuTrace.h"
#include <IOKit/IOLib.h>
#include <IOKit/IOMapper.h>
#include <IOKit/IOSubMemoryDescriptor.h>
#include <IOKit/IORegistryEntry.h>
#include <IOKit/IODeviceTreeSupport.h>
#include <libkern/c++/OSData.h>
#include <libkern/OSAtomic.h>
#include <kern/clock.h>
#include <kern/task.h>
#include <pexpert/pexpert.h>

extern "C" void diting_ramoops_diagnostic_write(const char *,int);
extern "C" vm_offset_t ml_io_map_unmappable(vm_offset_t phys_addr,vm_size_t size,uint32_t flags);
extern "C" int diting_gpu_fences(uint32_t *submitted,uint32_t *retired);

namespace {
IOLock *scanout_gate;
IOMemoryDescriptor *scanout;
task_t client;
DitingScanoutModeInfo mode{};
bool waiting=false,workerReady=false,poisoned=false,idleNotify=false;
uint64_t sequence=0,completed=0,sourceUse=0;
uint32_t nextSource=1;

struct Source {IOMemoryDescriptor *owner=nullptr,*memory=nullptr;IOMemoryMap *map=nullptr;
    size_t offset=0,bytes=0;uint32_t generation=0;uint64_t used=0;} sources[3];
bool releaseSource(Source &source) {
    if(!source.memory)return true;
    if(source.map){source.map->release();source.map=nullptr;}
    const IOReturn status=source.memory->complete();
    if(status){poisoned=true;return false;}
    source.memory->release();source.owner->release();source={};return true;
}
void releaseSources() {for(auto &source:sources)if(!releaseSource(source))break;}

struct Pending {bool offered=false,delivered=false,done=false;uint64_t id=0;
    uint32_t status=0;IOMemoryDescriptor *memory=nullptr;IOMemoryMap *map=nullptr;
    uint32_t stride=0;Source *source=nullptr;} pending;

uint64_t us(uint64_t a){uint64_t n=0;absolutetime_to_nanoseconds(a,&n);return n/1000;}
uint64_t deadline(unsigned ms){uint64_t d=0;clock_interval_to_deadline(ms,kMillisecondScale,&d);return d;}
void dpuLine(const char *text,int n){if(n>0){IOLog("%s",text);diting_ramoops_diagnostic_write(text,n);}}
void note(const char *phase,uint64_t id,unsigned status)
{
    char text[180];int n=snprintf(text,sizeof(text),"DITING SCANOUT: %s sequence=%llu status=0x%x\n",phase,id,status);
    dpuLine(text,n);
}

/* SM8475 DPU 8.1 / GCC / DISPCC register map (verified against diting-live.dts
 * qcom,mdss_mdp@ae00000: sde-sspp-off 0x5000..0x2b000, sde-ctl-off 0x16000..0x1b000,
 * sde-intf-off 0x35000..0x38000). */
enum : uint32_t {GccPa=0x00130000u,GccLen=0x10000,GccDispAhb=0x7004};
enum : uint32_t {DispccPa=0x0af00000u,DispccLen=0x10000,DcMdssAhb=0x80a4,DcGdsc=0x9000};
enum : uint32_t {MdssPa=0x0ae00000u,MdssLen=0x84000,SsppSrcSize=0x00,SsppSrc0Addr=0x14,
    SsppYstride0=0x24,CtlFlush=0x18,CtlIntfActive=0xf4,CtlFetchActive=0xfc};
static const uint32_t sspp[8]={0x5000,0x7000,0x9000,0xb000,0x25000,0x27000,0x29000,0x2b000};
static const uint32_t ctl[6]={0x16000,0x17000,0x18000,0x19000,0x1a000,0x1b000};
static const char *const ssppNames[8]={"VIG0","VIG1","VIG2","VIG3","DMA0","DMA1","DMA2","DMA3"};
static const uint32_t ssppFlushBit[8]={0,1,2,18,11,12,24,25},ssppFetchBit[8]={16,17,18,19,0,1,2,3};
constexpr uint32_t CtlFlushCtl=1u<<17;

vm_offset_t gccMap,dispccMap,dpuMap;
uint64_t dpuConsolePhys;

uint32_t dpuRd(vm_offset_t at){return *reinterpret_cast<volatile uint32_t *>(at);}
void dpuWr(vm_offset_t at,uint32_t v){*reinterpret_cast<volatile uint32_t *>(at)=v;__asm__ volatile("dsb sy":::"memory");}
bool dpuBranchOn(vm_offset_t cbcr){return !(dpuRd(cbcr)&0x80000000u);}
bool dpuBranchEnable(vm_offset_t cbcr)
{
    dpuWr(cbcr,dpuRd(cbcr)|1u);
    for(unsigned i=0;i<2000 && !dpuBranchOn(cbcr);++i)IODelay(1);
    return dpuBranchOn(cbcr);
}

bool dpuBus(const char *when)
{
    char text[220];
    if(!gccMap)gccMap=ml_io_map_unmappable(GccPa,GccLen,0x7 /* VM_WIMG_IO */);
    if(!gccMap){dpuLine(text,snprintf(text,sizeof text,"DITING DPU %s: no mapping of GCC\n",when));return false;}
    if(!dpuBranchOn(gccMap+GccDispAhb) && !dpuBranchEnable(gccMap+GccDispAhb)) {
        dpuLine(text,snprintf(text,sizeof text,"DITING DPU %s: GCC_DISP_AHB_CLK stayed off\n",when));return false;
    }
    if(!dispccMap)dispccMap=ml_io_map_unmappable(DispccPa,DispccLen,0x7);
    if(!dispccMap){dpuLine(text,snprintf(text,sizeof text,"DITING DPU %s: no mapping of DISPCC\n",when));return false;}
    if(!(dpuRd(dispccMap+DcGdsc)&0x80000000u)) {
        dpuLine(text,snprintf(text,sizeof text,"DITING DPU %s: MDSS GDSC not powered\n",when));return false;
    }
    if(!dpuBranchOn(dispccMap+DcMdssAhb) && !dpuBranchEnable(dispccMap+DcMdssAhb)) {
        dpuLine(text,snprintf(text,sizeof text,"DITING DPU %s: DISP_CC_MDSS_AHB_CLK stayed off\n",when));return false;
    }
    if(!dpuMap)dpuMap=ml_io_map_unmappable(MdssPa,MdssLen,0x7);
    if(!dpuMap){dpuLine(text,snprintf(text,sizeof text,"DITING DPU %s: no mapping of MDSS\n",when));return false;}
    return true;
}

/* INTF tearcheck / DPU frame-rate observation (MDSS-relative). */
enum : uint32_t {IntfFrameCount=0xac,IntfTearSyncVsync=0x288,IntfTearAutorefresh=0x2b4};
static const uint32_t intfOff[4]={0x35000,0x36000,0x37000,0x38000};
constexpr uint32_t AutorefreshEnable=1u<<31,AutorefreshFrameMask=0xffffu;
unsigned teIntf=1;uint32_t intfFrames0;uint64_t intfAt0;

/* Panel-pool slots + zero-copy flip state.
 * db[0] is the firmware console framebuffer (CPU frames + fallback presenter).
 * db[1..slotCount] are loader-reserved low-RAM panel-pool slots (< 4 GiB) for
 * backboardd's panel-sized BGRA canvases (1220x2712 @ 5120 B/row = 13.24 MiB). */
constexpr unsigned SlotMax=8;
constexpr unsigned DbMax=10;
constexpr uint64_t SlotStride=0x0E00000ull; /* 14 MiB per slot */

struct DbBuf {uint64_t phys;uint32_t stride;};
DbBuf db[DbMax];
unsigned dbN=0,dbMode=0;
bool dbOn=false;
int dbShown=0,dbFlipped=-1;
uint64_t dbFlipAt=0;
uint32_t dbCurStride=0;
struct {uint32_t pipes[8];unsigned count;uint32_t ctl,flush;} dbPipes;
uint64_t dbFlips=0,dbTaken=0,dbLatchMaxUs=0,dbCpuFlips=0;
unsigned dbLogged=0;

uint64_t slotPhys[SlotMax];
bool slotUsed[SlotMax];
int slotDb[SlotMax];
IOMemoryDescriptor *slotMemory[SlotMax];
IOMemoryMap *slotMapping[SlotMax];
unsigned slotCount=0,slotTaken=0,slotRefused=0;
uint32_t slotBytes=0,zc=0,zcAsync=0,slotPreMap=1;
IOSimpleLock *slotLock=nullptr;

uint64_t zcFrames=0,zcInPlace=0,zcFenceUs=0,zcFenceMaxUs=0,zcFenceTimeouts=0;
uint64_t zcLatchUs=0,zcLatchMaxUs=0,zcLatchTimeouts=0;
uint64_t zcWindowStart=0,zcLastAt=0,zcMovingUs=0;
unsigned zcWindowFrames=0,zcMovingFrames=0;

uint32_t zcTag=0;
extern "C" {volatile uint32_t diting_zc_flipped_tag,diting_zc_latched_tag;}

bool dbFindPipes(void)
{
    char text[240];uint32_t fetch=0;dbPipes.count=0;dbPipes.flush=0;
    for(unsigned p=0;p<8;++p) {
        if(dpuRd(dpuMap+sspp[p]+SsppSrc0Addr)!=(uint32_t)dpuConsolePhys)continue;
        dbPipes.pipes[dbPipes.count++]=p;dbPipes.flush|=1u<<ssppFlushBit[p];fetch|=1u<<ssppFetchBit[p];
    }
    if(!dbPipes.count) {
        dpuLine(text,snprintf(text,sizeof text,"DITING DBUF: off: no SSPP fetches console 0x%llx\n",(unsigned long long)dpuConsolePhys));
        return false;
    }
    int found=-1;
    for(unsigned c=0;c<6;++c)if((dpuRd(dpuMap+ctl[c]+CtlFetchActive)&fetch)==fetch){found=int(c);break;}
    if(found<0) {
        dpuLine(text,snprintf(text,sizeof text,"DITING DBUF: off: no CTL fetches pipes 0x%x\n",fetch));
        return false;
    }
    dbPipes.ctl=ctl[found];
    dbPipes.flush|=CtlFlushCtl;
    const uint32_t active=dpuRd(dpuMap+dbPipes.ctl+CtlIntfActive);
    for(unsigned i=1;i<4;++i)if(active&(1u<<i)){teIntf=i;break;}
    const vm_offset_t ib=dpuMap+intfOff[teIntf];
    intfFrames0=dpuRd(ib+IntfFrameCount);intfAt0=mach_absolute_time();
    dpuLine(text,snprintf(text,sizeof text,"DITING DBUF: pipes %s %s on CTL%d (INTF_%u active=0x%x autorefresh=0x%x vsync_count=%u), flush=0x%x\n",
        ssppNames[dbPipes.pipes[0]],dbPipes.count>1?ssppNames[dbPipes.pipes[1]]:"",found,teIntf,active,
        dpuRd(ib+IntfTearAutorefresh),dpuRd(ib+IntfTearSyncVsync)&0x7ffff,dbPipes.flush));
    return true;
}

void intfRate(const char *when)
{
    if(!intfAt0 || !dpuMap)return;
    const vm_offset_t b=dpuMap+intfOff[teIntf];
    const uint32_t frames=dpuRd(b+IntfFrameCount);
    const uint64_t now=mach_absolute_time(),elapsed=us(now-intfAt0);
    if(elapsed<200000)return;
    const uint64_t rate=uint64_t(frames-intfFrames0)*10000000ull/elapsed;
    char text[200];
    dpuLine(text,snprintf(text,sizeof text,"DITING DPU %s: INTF_%u frames %llu.%llu/s over %llu ms (autorefresh 0x%x, vsync_count %u)\n",
        when,teIntf,rate/10,rate%10,elapsed/1000,dpuRd(b+IntfTearAutorefresh),dpuRd(b+IntfTearSyncVsync)&0x7ffff));
    intfFrames0=frames;intfAt0=now;
}

bool dbLatched(void){return (dpuRd(dpuMap+dbPipes.ctl+CtlFlush)&dbPipes.flush)==0;}
void dbSettle(void)
{
    if(dbFlipped<0 || !dbLatched())return;
    const uint64_t t=us(mach_absolute_time()-dbFlipAt);
    if(t>dbLatchMaxUs)dbLatchMaxUs=t;
    ++dbTaken;dbShown=dbFlipped;dbFlipped=-1;
}
void dbFlip(int i)
{
    __asm__ volatile("dsb sy":::"memory");
    const uint32_t st=db[i].stride?db[i].stride:uint32_t(mode.stride);
    if(st!=dbCurStride) {
        for(unsigned k=0;k<dbPipes.count;++k) {
            const vm_offset_t r=dpuMap+sspp[dbPipes.pipes[k]]+SsppYstride0;
            dpuWr(r,(dpuRd(r)&0xffff0000u)|(st&0xffffu));
        }
        dbCurStride=st;
    }
    for(unsigned k=0;k<dbPipes.count;++k)dpuWr(dpuMap+sspp[dbPipes.pipes[k]]+SsppSrc0Addr,(uint32_t)db[i].phys);
    dpuWr(dpuMap+dbPipes.ctl+CtlFlush,dbPipes.flush);
    dbFlipped=i;dbFlipAt=mach_absolute_time();++dbFlips;
    if(dbLogged<4) {
        ++dbLogged;
        for(unsigned k=0;k<80 && !dbLatched();++k)IODelay(250);
        char text[220];
        dpuLine(text,snprintf(text,sizeof text,"DITING DBUF: flip %llu: buf %d at 0x%llx stride %u %s after %llu us (CTL_FLUSH 0x%x)\n",
            (unsigned long long)dbFlips,i,(unsigned long long)db[i].phys,st,dbLatched()?"taken":"pending",
            (unsigned long long)us(mach_absolute_time()-dbFlipAt),dpuRd(dpuMap+dbPipes.ctl+CtlFlush)));
    }
}

/* Panel HS-mode DCS refresh-rate switch sets, verbatim from
 * platform-firmware/diting-live.dts (42_02_0a default; 36_02_0b via
 * diting_panel=36). Both share geometry, DSC, porches and 1.1 GHz DSI clock. */
enum : uint32_t {DsiPa=0x0ae94000u,DsiLen=0x400,DsiHwVersion=0x000,DsiCtrl=0x004,DsiStatus=0x008,
    DsiCmdDmaCtrl=0x03c,DsiDmaCmdLength=0x04c,DsiTrigCtrl=0x084,DsiCmdDmaSwTrigger=0x090,
    DsiIntCtrl=0x110,DsiTpgCtrl=0x15c,DsiTpgCmdDmaInitVal=0x17c,DsiTpgDmaFifoReset=0x1ec};
constexpr uint32_t DsiDmaBusy=1u<<1,DsiMdpBusy=1u<<2,DsiIntDmaDone=1u<<0,
    DsiIntEnableBits=0xaaaaaaaau,DsiTpgFifoOn=(3u<<16)|(1u<<2)|(1u<<1),DsiTrigSw=4u,DsiMaxPayload=60;

vm_offset_t dsiMap;
unsigned panelHzWant=120,panelHzNow=60,panelId=42,dsiFailures=0,dsiMdpWaits=0;
bool panelDone=false;

static const uint8_t panel42Switch120[]={
    0x15,0,0,0x00,0,0,2, 0x2f,0x03,
    0x39,0,0,0x40,0,0,6, 0xf0,0x55,0xaa,0x52,0x08,0x00,
    0x15,0,0,0x40,0,0,2, 0x6f,0x0a,
    0x15,0,0,0x40,0,0,2, 0xc0,0x20,
    0x39,0,0,0x40,0,0,6, 0xf0,0x55,0xaa,0x52,0x08,0x02,
    0x15,0,0,0x40,0,0,2, 0xcc,0x30,
    0x15,0,0,0x00,10,0,2, 0xce,0x01,
    0x15,0,0,0x00,0,0,2, 0xcc,0x00
};
static const uint8_t panel42Switch60[]={
    0x15,0,0,0x00,0,0,2, 0x2f,0x02,
    0x39,0,0,0x40,0,0,6, 0xf0,0x55,0xaa,0x52,0x08,0x00,
    0x15,0,0,0x40,0,0,2, 0x6f,0x09,
    0x15,0,0,0x40,0,0,2, 0xc0,0x00,
    0x39,0,0,0x40,0,0,6, 0xf0,0x55,0xaa,0x52,0x08,0x02,
    0x15,0,0,0x40,0,0,2, 0xcc,0x30,
    0x15,0,0,0x00,20,0,2, 0xce,0x01,
    0x15,0,0,0x00,0,0,2, 0xcc,0x00
};
static const uint8_t panel36Switch120[]={
    0x15,0,0,0x00,0,0,2, 0x2f,0x02,
    0x39,0,0,0x40,0,0,6, 0xf0,0x55,0xaa,0x52,0x08,0x08,
    0x15,0,0,0x40,0,0,2, 0xe0,0x01,
    0x39,0,0,0x40,0,0,5, 0xe2,0xd6,0x4e,0x84,0x88,
    0x15,0,0,0x40,0,0,2, 0x6f,0x12,
    0x39,0,0,0x40,0,0,3, 0xe2,0xfd,0x03,
    0x39,0,0,0x40,0,0,9, 0xea,0x02,0x00,0xe0,0x00,0xe0,0x80,0x00,0x80,
    0x15,0,0,0x40,0,0,2, 0x6f,0x17,
    0x39,0,0,0x00,0,0,4, 0xea,0x38,0x00,0x38
};
static const uint8_t panel36Switch60[]={
    0x15,0,0,0x00,0,0,2, 0x2f,0x00,
    0x39,0,0,0x40,0,0,6, 0xf0,0x55,0xaa,0x52,0x08,0x08,
    0x15,0,0,0x40,0,0,2, 0xe0,0x01,
    0x39,0,0,0x40,0,0,5, 0xe2,0x88,0xe0,0xcc,0x0c,
    0x15,0,0,0x40,0,0,2, 0x6f,0x12,
    0x39,0,0,0x40,0,0,3, 0xe2,0x86,0x01,
    0x39,0,0,0x40,0,0,9, 0xea,0x02,0x00,0xe0,0x00,0xe0,0x70,0x00,0x70,
    0x15,0,0,0x40,0,0,2, 0x6f,0x17,
    0x39,0,0,0x00,0,0,4, 0xea,0x80,0x00,0x80
};

uint32_t dsiRd(uint32_t off){return dpuRd(dsiMap+off);}
void dsiWr(uint32_t off,uint32_t v){dpuWr(dsiMap+off,v);}

bool dsiInit(void)
{
    char text[220];
    if(!dsiMap)dsiMap=ml_io_map_unmappable(DsiPa,DsiLen,0x7);
    if(!dsiMap){dpuLine(text,snprintf(text,sizeof text,"DITING PANEL: no mapping of DSI0\n"));return false;}
    const uint32_t ver=dsiRd(DsiHwVersion),ctrl=dsiRd(DsiCtrl);
    dpuLine(text,snprintf(text,sizeof text,"DITING PANEL: DSI0 ver 0x%08x ctrl 0x%08x status 0x%08x dma 0x%08x trig 0x%08x\n",
        ver,ctrl,dsiRd(DsiStatus),dsiRd(DsiCmdDmaCtrl),dsiRd(DsiTrigCtrl)));
    if((ver>>28)!=2 || (ctrl&5u)!=5u) {
        dpuLine(text,snprintf(text,sizeof text,"DITING PANEL: DSI0 is not a running command-mode DSI 2.x controller\n"));
        return false;
    }
    return true;
}

int dsiDcs(const uint8_t *buf,uint32_t len,bool lp)
{
    uint32_t words[2+(DsiMaxPayload+3)/4];uint32_t n=0,i=0;
    if(!dsiMap || !len || len>DsiMaxPayload || dsiFailures>=3)return -1;
    if(len<=2)words[n++]=(1u<<31)|((len==1?0x05u:0x15u)<<16)|(len==2?uint32_t(buf[1])<<8:0u)|buf[0];
    else {
        words[n++]=(1u<<31)|(1u<<30)|(0x39u<<16)|len;
        for(i=0;i<len;i+=4){uint32_t w=0;for(uint32_t b=0;b<4 && i+b<len;++b)w|=uint32_t(buf[i+b])<<(8*b);words[n++]=w;}
    }
    const uint32_t bytes=n*4;
    if(n&1u)words[n++]=0;
    int rc=0;
    for(i=0;i<250 && (dsiRd(DsiStatus)&DsiDmaBusy);++i)IODelay(20);
    if(dsiRd(DsiStatus)&DsiDmaBusy)rc=-2;
    else {
        for(i=0;i<1000 && (dsiRd(DsiStatus)&DsiMdpBusy);++i)IODelay(20);
        if(i==1000)++dsiMdpWaits;
        const uint32_t tpg=dsiRd(DsiTpgCtrl),dma=dsiRd(DsiCmdDmaCtrl),trig=dsiRd(DsiTrigCtrl);
        if((trig&0xfu)!=DsiTrigSw)dsiWr(DsiTrigCtrl,(trig&~0xfu)|DsiTrigSw);
        dsiWr(DsiIntCtrl,(dsiRd(DsiIntCtrl)&DsiIntEnableBits)|DsiIntDmaDone);
        dsiWr(DsiTpgCtrl,DsiTpgFifoOn);
        for(uint32_t w=0;w<n;++w)dsiWr(DsiTpgCmdDmaInitVal,words[w]);
        dsiWr(DsiCmdDmaCtrl,(dma&~((1u<<31)|(1u<<30)|(1u<<26)))|(1u<<28)|(lp?(1u<<26):0u));
        dsiWr(DsiDmaCmdLength,bytes);
        dsiWr(DsiCmdDmaSwTrigger,1);
        bool done=false;
        for(i=0;i<1250 && !done;++i){done=(dsiRd(DsiIntCtrl)&DsiIntDmaDone)!=0;if(!done)IODelay(20);}
        if(!(dsiRd(DsiStatus)&DsiDmaBusy)) {
            dsiWr(DsiIntCtrl,(dsiRd(DsiIntCtrl)&DsiIntEnableBits)|DsiIntDmaDone);
            dsiWr(DsiTpgCtrl,0);dsiWr(DsiTpgDmaFifoReset,1);IODelay(1);dsiWr(DsiTpgDmaFifoReset,0);
            dsiWr(DsiTpgCtrl,tpg);dsiWr(DsiCmdDmaCtrl,dma);
            if((trig&0xfu)!=DsiTrigSw)dsiWr(DsiTrigCtrl,trig);
        }
        if(!done)rc=-3;
    }
    if(rc) {
        ++dsiFailures;char text[200];
        dpuLine(text,snprintf(text,sizeof text,"DITING PANEL: DCS 0x%02x (%u B) failed rc=%d status=0x%x int=0x%x\n",
            buf[0],len,rc,dsiRd(DsiStatus),dsiRd(DsiIntCtrl)));
    }
    return rc;
}

int dsiSet(const uint8_t *set,uint32_t len,bool lp,unsigned *sent)
{
    uint32_t i=0;int rc=0;*sent=0;
    while(i+7<=len && !rc) {
        const uint32_t plen=(uint32_t(set[i+5])<<8)|set[i+6];
        if(!plen || i+7+plen>len){rc=-4;break;}
        if(set[i]!=0x05 && set[i]!=0x15 && set[i]!=0x39){rc=-5;break;}
        rc=dsiDcs(set+i+7,plen,lp);
        if(!rc){++*sent;if(set[i+4])IODelay(1000u*set[i+4]);}
        i+=7+plen;
    }
    return rc;
}

void usePerTeAutorefresh()
{
    if(!(dpuRd(dpuMap+dbPipes.ctl+CtlIntfActive)&(1u<<teIntf)))return;
    const vm_offset_t reg=dpuMap+intfOff[teIntf]+IntfTearAutorefresh;
    const uint32_t inherited=dpuRd(reg);
    if(!(inherited&AutorefreshEnable) || (inherited&AutorefreshFrameMask)==1)return;

    // 固件为静态开机画面每 60 个 TE 送一帧。接管后每个 TE 都允许锁存新画面。
    // 保留自动刷新使能和其他字段，沿用命令模式的 CTL_FLUSH 路径。
    intfRate("before autorefresh update");
    dpuWr(reg,(inherited&~AutorefreshFrameMask)|1u);
    char text[160];
    dpuLine(text,snprintf(text,sizeof text,"DITING PANEL: INTF_%u autorefresh 0x%x -> 0x%x\n",
        teIntf,inherited,dpuRd(reg)));
}

void panelHz(void)
{
    char text[220];
    panelHzWant=120;(void)PE_parse_boot_argn("diting_panel_hz",&panelHzWant,sizeof panelHzWant);
    panelId=42;(void)PE_parse_boot_argn("diting_panel",&panelId,sizeof panelId);
    if(panelHzWant!=120){usePerTeAutorefresh();panelDone=true;return;}
    if(!diting_dsi_try_acquire(DitingDsiTiming))return; /* retry next frame if backlight holds DSI0 */
    panelDone=true;
    if(!dsiInit()){(void)diting_dsi_release(DitingDsiTiming);return;}
    intfRate("before switch");
    const uint64_t t0=mach_absolute_time();unsigned sent=0;
    const uint8_t *prog=panelId==36
        ?(panelHzWant==120?panel36Switch120:panel36Switch60)
        :(panelHzWant==120?panel42Switch120:panel42Switch60);
    const uint32_t bytes=panelId==36
        ?(panelHzWant==120?sizeof(panel36Switch120):sizeof(panel36Switch60))
        :(panelHzWant==120?sizeof(panel42Switch120):sizeof(panel42Switch60));
    const int rc=dsiSet(prog,bytes,false,&sent);
    if(!(dsiRd(DsiStatus)&DsiDmaBusy))(void)diting_dsi_release(DitingDsiTiming);
    dpuLine(text,snprintf(text,sizeof text,"DITING PANEL: switch panel %u to %u Hz: %u packets rc=%d in %llu us (MDP waits %u)\n",
        panelId,panelHzWant,sent,rc,(unsigned long long)us(mach_absolute_time()-t0),dsiMdpWaits));
    if(rc)return;
    panelHzNow=panelHzWant;
    uint32_t tc=0;(void)PE_parse_boot_argn("diting_panel_tc",&tc,sizeof tc);
    if(tc && dpuMap) {
        const vm_offset_t b=dpuMap+intfOff[teIntf];
        const uint32_t cfg=dpuRd(b+IntfTearSyncVsync);
        const uint32_t count=19200000u/(2756u*panelHzNow);
        dpuWr(b+IntfTearSyncVsync,(cfg&~0x7ffffu)|count);
        dpuLine(text,snprintf(text,sizeof text,"DITING PANEL: INTF_%u vsync_count %u -> %u\n",teIntf,cfg&0x7ffff,count));
    }
    usePerTeAutorefresh();
    for(unsigned k=0;k<250;++k)IODelay(1000);
    intfRate("after switch");
}

void dbInit(uint64_t physical,size_t rounded,uint32_t stride,uint32_t height)
{
    char text[280];
    if(!dpuBus("flip")){dpuLine(text,snprintf(text,sizeof text,"DITING DBUF: off: MDSS unreachable\n"));return;}
    if(!dbFindPipes())return;
    db[0]={physical,stride};dbN=1;dbShown=0;dbFlipped=-1;

    uint32_t usePool=1;(void)PE_parse_boot_argn("diting_panel_pool",&usePool,sizeof usePool);
    uint64_t lease[2]={};
    if(usePool) {
        IORegistryEntry *chosen=IORegistryEntry::fromPath("/chosen",gIODTPlane);
        OSData *data=chosen?OSDynamicCast(OSData,chosen->getProperty("diting-panel-pool")):nullptr;
        if(data && data->getLength()==16)memcpy(lease,data->getBytesNoCopy(),16);
        if(chosen)chosen->release();
    }
    const uint64_t slotStride=rounded>SlotStride?uint64_t(rounded):SlotStride;
    if(lease[0] && !(lease[0]&4095) && lease[1]>=slotStride && lease[0]+lease[1]<=0x100000000ull) {
        zc=2;(void)PE_parse_boot_argn("diting_zc",&zc,sizeof zc);
        zcAsync=0;(void)PE_parse_boot_argn("diting_zc_async",&zcAsync,sizeof zcAsync);
        (void)PE_parse_boot_argn("diting_slot_premap",&slotPreMap,sizeof slotPreMap);
        if(!slotLock)slotLock=IOSimpleLockAlloc();
        const unsigned total=unsigned(lease[1]/slotStride);
        for(unsigned i=0;i<total && slotCount<SlotMax && dbN<DbMax;++i) {
            const uint64_t phys=lease[0]+uint64_t(i)*slotStride;
            IOMemoryDescriptor *memory=nullptr;IOMemoryMap *mapping=nullptr;
            if(slotPreMap) {
                memory=IOMemoryDescriptor::withPhysicalAddress(phys,slotStride,kIODirectionInOut);
                const IOReturn held=memory?memory->prepare():kIOReturnNoMemory;
                if(held==kIOReturnSuccess)mapping=memory->createMappingInTask(kernel_task,0,kIOMapAnywhere|kIOMapCopybackCache);
                if(!mapping) {
                    dpuLine(text,snprintf(text,sizeof text,"DITING DBUF: slot premap FAILED phys=0x%llx bytes=%llu err=0x%x\n",
                        (unsigned long long)phys,(unsigned long long)slotStride,held));
                    if(memory){if(held==kIOReturnSuccess)memory->complete();memory->release();}
                    continue;
                }
            }
            slotPhys[slotCount]=phys;slotDb[slotCount]=int(dbN);
            slotMemory[slotCount]=memory;slotMapping[slotCount]=mapping;
            db[dbN]={phys,0};++dbN;++slotCount;
        }
        slotBytes=uint32_t(slotStride);
        if(slotCount>0)dbOn=true;
        dpuLine(text,snprintf(text,sizeof text,"DITING DBUF: panel pool 0x%llx (%llu MiB): %u/%u canvas slots (%u MiB each), zc=%u async=%u, %ux%u\n",
            (unsigned long long)lease[0],(unsigned long long)(lease[1]>>20),slotCount,total,unsigned(slotStride>>20),zc,zcAsync,unsigned(mode.width),height));
    } else if(usePool) {
        dpuLine(text,snprintf(text,sizeof text,"DITING DBUF: no panel pool lease (0x%llx + 0x%llx); fallback copy mode\n",
            (unsigned long long)lease[0],(unsigned long long)lease[1]));
    }
}

static void zcLatchedTo(uint32_t t)
{
    for(;;) {
        const uint32_t o=diting_zc_latched_tag;
        if(int32_t(t-o)<=0)return;
        if(OSCompareAndSwap(o,t,&diting_zc_latched_tag))return;
    }
}

/* Zero-copy flip (gate held; releases gate before returning).
 * Returns 3 (flipped, async latch pending) or 1 (latched). */
static int zcFlip(int zi,uint32_t stride)
{
    ++zcFrames;
    dbSettle();
    if(zi==dbShown)++zcInPlace;

    uint32_t submitted=0,retired=0;
    const uint64_t f0=mach_absolute_time();
    if(diting_gpu_fences(&submitted,&retired)) {
        unsigned k=0;
        while(int32_t(submitted-retired)>0 && k<500) {
            IODelay(100);++k;
            if(!diting_gpu_fences(&submitted,&retired))break;
        }
        if(int32_t(submitted-retired)>0)++zcFenceTimeouts;
    }
    const uint64_t fw=us(mach_absolute_time()-f0);
    zcFenceUs+=fw;if(fw>zcFenceMaxUs)zcFenceMaxUs=fw;

    uint64_t lw=0;
    if(zi!=dbFlipped && zi!=dbShown) {
        if(dbFlipped>=0) {
            const uint64_t o0=mach_absolute_time();
            for(unsigned k=0;k<200 && !dbLatched();++k)IODelay(100);
            if(dbLatched())zcLatchedTo(diting_zc_flipped_tag);
            dbSettle();
            if(zcAsync)lw=us(mach_absolute_time()-o0);
        }
        db[zi].stride=stride;
        dbFlip(zi);
    }
    diting_zc_flipped_tag=zcTag;
    if(!zcAsync) {
        const uint64_t l0=mach_absolute_time();
        for(unsigned k=0;k<200 && !dbLatched();++k)IODelay(100);
        lw=us(mach_absolute_time()-l0);
        if(!dbLatched())++zcLatchTimeouts;
        else zcLatchedTo(zcTag);
        dbSettle();
    }
    zcLatchUs+=lw;if(lw>zcLatchMaxUs)zcLatchMaxUs=lw;

    if(zcFrames<=4) {
        char text[220];
        dpuLine(text,snprintf(text,sizeof text,"DITING ZC: frame %llu: buf %d 0x%llx stride %u, fence %u/%u (%llu us), %s (%llu us)\n",
            (unsigned long long)zcFrames,zi,(unsigned long long)db[zi].phys,stride,submitted,retired,(unsigned long long)fw,
            dbShown==zi?"shown":zcAsync?"flipped(async)":"pending",(unsigned long long)lw));
    }

    const uint64_t now=mach_absolute_time();
    if(!zcWindowFrames)zcWindowStart=now;
    if(zcLastAt) {
        const uint64_t gap=us(now-zcLastAt);
        if(gap<90000){zcMovingUs+=gap;++zcMovingFrames;}
    }
    zcLastAt=now;
    if(++zcWindowFrames==128) {
        const uint64_t span=us(now-zcWindowStart);
        char text[240];
        dpuLine(text,snprintf(text,sizeof text,"DITING ZC TIMING: 128 frames in %llu ms (moving %u at %llu fps) fence avg %llu max %llu us, latch avg %llu max %llu us, in-place %llu\n",
            (unsigned long long)(span/1000),zcMovingFrames,zcMovingUs?(unsigned long long)(uint64_t(zcMovingFrames)*1000000ull/zcMovingUs):0ull,
            (unsigned long long)(zcFenceUs/zcFrames),(unsigned long long)zcFenceMaxUs,
            (unsigned long long)(zcLatchUs/zcFrames),(unsigned long long)zcLatchMaxUs,(unsigned long long)zcInPlace));
        intfRate("zc");
        zcWindowFrames=0;zcMovingFrames=0;zcMovingUs=0;
    }

    const int ret=zcAsync?3:1;
    IOLockUnlock(scanout_gate);
    return ret;
}
}

extern "C" void diting_scanout_set_tag(uint32_t tag){zcTag=tag;}
extern "C" uint32_t diting_scanout_latch_poll(void)
{
    const uint32_t t=diting_zc_flipped_tag;
    __asm__ volatile("dmb ish":::"memory");
    if(t!=diting_zc_latched_tag && dbOn && dbN && dbLatched())zcLatchedTo(t);
    return diting_zc_latched_tag;
}
extern "C" void diting_scanout_cpu_frame(void)
{
    if(!scanout_gate || !dbOn)return;
    IOLockLock(scanout_gate);
    if(dbOn) {
        dbSettle();
        if(dbShown!=0 || dbFlipped>0) {
            if(dbFlipped>=0){for(unsigned k=0;k<200 && !dbLatched();++k)IODelay(100);dbSettle();}
            dbFlip(0);++dbCpuFlips;
            for(unsigned k=0;k<80 && !dbLatched();++k)IODelay(250);
            dbSettle();
        }
    }
    IOLockUnlock(scanout_gate);
}
extern "C" int diting_panel_slot_take(uint32_t width,uint32_t height,uint32_t bytesPerRow,uint32_t bytes,uint64_t *phys)
{
    *phys=0;
    if(!zc || !slotCount || !slotLock)return 0;
    if(width!=mode.width || height!=mode.height || bytesPerRow<width*4 || (bytesPerRow&63) ||
       bytesPerRow>0xffff || bytes>slotBytes || uint64_t(bytesPerRow)*height>slotBytes) {
        if(slotRefused++<4)IOLog("DITING DBUF: canvas %ux%u bpr %u (%u B) does not fit slot (%ux%u, %u B)\n",
            width,height,bytesPerRow,bytes,unsigned(mode.width),unsigned(mode.height),slotBytes);
        return 0;
    }
    unsigned active=0;
    IOSimpleLockLock(slotLock);
    for(unsigned i=0;i<slotCount;++i) {
        if(slotUsed[i]){++active;continue;}
        if(*phys)continue;
        slotUsed[i]=true;db[slotDb[i]].stride=bytesPerRow;*phys=slotPhys[i];++active;++slotTaken;
    }
    IOSimpleLockUnlock(slotLock);
    IOLog("DITING DBUF: canvas slot %s 0x%llx (active %u/%u, %u taken)\n",
        *phys?"given":"NONE FREE for",(unsigned long long)*phys,active,slotCount,slotTaken);
    return *phys?1:0;
}
extern "C" void diting_panel_slot_give(uint64_t phys)
{
    if(!slotLock)return;
    unsigned active=0;
    IOSimpleLockLock(slotLock);
    for(unsigned i=0;i<slotCount;++i) {
        if(slotPhys[i]==phys)slotUsed[i]=false;
        if(slotUsed[i])++active;
    }
    IOSimpleLockUnlock(slotLock);
    IOLog("DITING DBUF: canvas slot 0x%llx returned (active %u/%u)\n",(unsigned long long)phys,active,slotCount);
}
extern "C" IOMemoryDescriptor *diting_panel_slot_memory(uint64_t phys,uint32_t bytes)
{
    if(!bytes || bytes>slotBytes || !slotLock)return nullptr;
    IOMemoryDescriptor *parent=nullptr;bool leased=false;
    IOSimpleLockLock(slotLock);
    for(unsigned i=0;i<slotCount;++i)if(slotPhys[i]==phys && slotUsed[i]) {
        leased=true;parent=slotMemory[i];if(parent)parent->retain();break;
    }
    IOSimpleLockUnlock(slotLock);
    if(!leased)return nullptr;
    if(!slotPreMap)return IOMemoryDescriptor::withPhysicalAddress(phys,bytes,kIODirectionInOut);
    if(!parent)return nullptr;
    IOMemoryDescriptor *memory=IOSubMemoryDescriptor::withSubRange(parent,0,bytes,kIODirectionInOut);
    parent->release();return memory;
}
extern "C" bool diting_panel_slot_range(uint64_t phys,uint64_t bytes)
{
    if(!bytes || bytes>slotBytes)return false;
    for(unsigned i=0;i<slotCount;++i)if(phys>=slotPhys[i] && phys-slotPhys[i]<=slotBytes-bytes)return true;
    return false;
}
extern "C" uint64_t diting_panel_slot_address(uint64_t phys)
{
    for(unsigned i=0;i<slotCount;++i)if(slotPhys[i]==phys && slotMapping[i])return slotMapping[i]->getVirtualAddress();
    return 0;
}

extern "C" void diting_scanout_initialize(uint64_t address,size_t bytes,uint32_t stride,uint32_t width,uint32_t height)
{
    unsigned enabled=0;
    if(scanout_gate || !PE_parse_boot_argn("diting_gpu_scanout",&enabled,sizeof(enabled)) || enabled!=1)return;
    if(!address || (address&4095) || !width || !height || stride<uint64_t(width)*4 ||
       bytes!=uint64_t(stride)*height || bytes>SIZE_MAX-4095)return;
    const size_t rounded=(bytes+4095)&~size_t(4095);
    if(address>UINT64_MAX-rounded)return;
    PE_Video video{};
    if(PE_current_console(&video) || !video.v_baseAddr || (video.v_baseAddr>>63) ||
       video.v_width!=width || video.v_height!=height || video.v_rowBytes!=stride ||
       video.v_depth!=32 || video.v_rotate ||
       (video.v_length && (video.v_offset>video.v_length || rounded>video.v_length-video.v_offset)))return;
    const uint64_t base=video.v_baseAddr&~UINT64_C(3);
    if(video.v_offset>UINT64_MAX-base)return;
    const uint64_t physical=base+video.v_offset;
    if(!physical || (physical&4095) || physical>UINT64_MAX-rounded)return;
    scanout=IOMemoryDescriptor::withPhysicalAddress(physical,rounded,kIODirectionInOut);
    if(!scanout)return;
    scanout_gate=IOLockAlloc();if(!scanout_gate){scanout->release();scanout=nullptr;return;}
    mode={DitingScanoutVersion,DitingScanoutBgra,width,height,stride,rounded};
    dpuConsolePhys=physical;
    dbMode=1;(void)PE_parse_boot_argn("diting_dpu_flip",&dbMode,sizeof(dbMode));
    if(dbMode)dbInit(physical,rounded,stride,height);
    note("actual framebuffer handoff available",0,0);
}
extern "C" IOReturn diting_scanout_connect(task_t owner)
{
    if(!scanout_gate || !owner)return kIOReturnNotReady;
    IOLockLock(scanout_gate);IOReturn result=kIOReturnBusy;
    if(!client && !poisoned){task_reference(owner);client=owner;result=kIOReturnSuccess;}
    IOLockUnlock(scanout_gate);return result;
}
extern "C" void diting_scanout_disconnect(task_t owner)
{
    if(!scanout_gate)return;
    IOLockLock(scanout_gate);
    if(client==owner) {
        waiting=false;workerReady=false;
        if(pending.offered && pending.delivered && !pending.done) {
            poisoned=true;
            note("client closed with outstanding GPU copy; retain pages",pending.id,kIOReturnAborted);
        } else if(pending.offered && !pending.delivered) {
            pending.done=true;pending.status=kIOReturnAborted;
        }
        client=nullptr;task_deallocate(owner);
        if(!poisoned && !pending.offered)releaseSources();
        IOLockWakeup(scanout_gate,&pending,false);
    }
    IOLockUnlock(scanout_gate);
}
extern "C" IOMemoryDescriptor *diting_scanout_memory(task_t owner)
{
    if(!scanout_gate)return nullptr;
    IOLockLock(scanout_gate);auto *memory=client==owner && !poisoned?scanout:nullptr;
    if(memory)memory->retain();IOLockUnlock(scanout_gate);return memory;
}
extern "C" bool diting_scanout_quarantined(void)
{
    if(!scanout_gate)return false;
    IOLockLock(scanout_gate);bool blocked=poisoned;IOLockUnlock(scanout_gate);return blocked;
}
extern "C" void diting_scanout_idle(void)
{
    if(!scanout_gate)return;
    IOLockLock(scanout_gate);
    if(client && !poisoned && !pending.offered) {
        workerReady=false;idleNotify=true;
        IOLockWakeup(scanout_gate,&pending,false);
    }
    IOLockUnlock(scanout_gate);
}
extern "C" IOReturn diting_scanout_call(task_t owner,unsigned op,const void *in,size_t inBytes,void *out,size_t outBytes)
{
    if(!scanout_gate)return kIOReturnNotReady;
    IOLockLock(scanout_gate);
    if(client!=owner || poisoned){IOLockUnlock(scanout_gate);return kIOReturnNotReady;}
    if(op==DitingScanoutResetSources && !inBytes && !outBytes) {
        workerReady=false;
        if(pending.offered){IOLockUnlock(scanout_gate);return kIOReturnBusy;}
        releaseSources();bool ok=!poisoned;
        IOLockUnlock(scanout_gate);return ok?kIOReturnSuccess:kIOReturnNotReady;
    }
    if(op==DitingScanoutMode && !inBytes && out && outBytes==sizeof(mode)) {
        memcpy(out,&mode,sizeof(mode));IOLockUnlock(scanout_gate);return kIOReturnSuccess;
    }
    if(op==DitingScanoutComplete && in && inBytes==sizeof(DitingScanoutDone) && !outBytes) {
        const auto &q=*static_cast<const DitingScanoutDone *>(in);
        if(q.reserved || !pending.offered || !pending.delivered || pending.done || q.sequence!=pending.id) {
            IOLockUnlock(scanout_gate);return kIOReturnBadArgument;
        }
        gpuTraceEvent(GpuTraceDisplayFence,0,q.sequence,q.status?2:1,q.sequence,q.sequence,q.status?0:q.sequence,0,0,0,q.status);
        pending.status=q.status;pending.done=true;
        if(q.status==DitingScanoutNotSubmitted)workerReady=false;
        if(q.status && q.status!=DitingScanoutNotSubmitted)poisoned=true;
        IOLockWakeup(scanout_gate,&pending,false);IOLockUnlock(scanout_gate);return kIOReturnSuccess;
    }
    if(op!=DitingScanoutWait || !in || inBytes!=sizeof(DitingScanoutWaitInfo) || !out || outBytes!=sizeof(DitingScanoutFrame)) {
        IOLockUnlock(scanout_gate);return kIOReturnBadArgument;
    }
    if(waiting){IOLockUnlock(scanout_gate);return kIOReturnBusy;}
    uint64_t ms=static_cast<const DitingScanoutWaitInfo *>(in)->timeout_ms;
    const uint64_t until=deadline(unsigned(ms>1000?1000:ms));waiting=true;workerReady=true;
    while(client==owner && !poisoned && !idleNotify && (!pending.offered || pending.delivered)) {
        if(IOLockSleepDeadline(scanout_gate,&pending,until,THREAD_ABORTSAFE)!=THREAD_AWAKENED) {
            waiting=false;IOLockUnlock(scanout_gate);return kIOReturnTimeout;
        }
    }
    waiting=false;
    if(client!=owner || poisoned){IOLockUnlock(scanout_gate);return kIOReturnNotReady;}
    if(idleNotify){idleNotify=false;workerReady=false;IOLockUnlock(scanout_gate);return kIOReturnAborted;}
    Source *source=pending.source;
    if(!source || !source->memory){IOLockUnlock(scanout_gate);return kIOReturnNotReady;}
    if(!source->map)source->map=source->memory->createMappingInTask(owner,0,kIOMapAnywhere);
    IOMemoryMap *map=source->map;
    if(!map || !map->getVirtualAddress()) {
        if(map){map->release();source->map=nullptr;}
        workerReady=false;pending.done=true;pending.status=kIOReturnNoMemory;
        IOLockWakeup(scanout_gate,&pending,false);IOLockUnlock(scanout_gate);return kIOReturnNoMemory;
    }
    pending.map=map;pending.delivered=true;
    *static_cast<DitingScanoutFrame *>(out)={pending.id,map->getVirtualAddress(),map->getLength(),pending.stride,
        uint32_t(mode.width),uint32_t(mode.height),mode.format,source->generation};
    IOLockUnlock(scanout_gate);return kIOReturnSuccess;
}
/* 0: caller keeps CPU path. 1: completed GPU copy/sync flip. 2: DMA uncertain (quarantined).
 * 3: zero-copy flip written, latch pending (SwapWait polls diting_scanout_latch_poll). */
extern "C" int diting_scanout_frame(IOMemoryDescriptor *source,size_t offset,uint32_t stride,uint32_t width,uint32_t height)
{
    if(!scanout_gate || !source || stride<uint64_t(width)*4 || width!=mode.width || height!=mode.height || (offset&4095))return 0;
    IOLockLock(scanout_gate);
    if(poisoned){IOLockUnlock(scanout_gate);return 2;}
    size_t bytes=(size_t(stride)*height+4095)&~size_t(4095);
    if(offset>source->getLength() || bytes>source->getLength()-offset){IOLockUnlock(scanout_gate);return 0;}
    if(dbN && !panelDone)panelHz();
    /* Zero-copy fast path: CoreAnimation canvas lives in a loader panel-pool slot.
     * No userspace presenter copy is needed; flip the DPU pipes directly to it. */
    if(zc>=2 && dbOn && offset==0 && slotCount && !pending.offered) {
        IOByteCount seg=0;
        const addr64_t p=source->getPhysicalSegment(0,&seg,kIOMemoryMapperNone);
        for(unsigned i=0;i<slotCount;++i) {
            if(slotPhys[i]==p && seg>=bytes)return zcFlip(slotDb[i],stride);
        }
    }
    if(!client || !workerReady || pending.offered){IOLockUnlock(scanout_gate);return 0;}
    Source *slot=nullptr;
    for(auto &entry:sources) {
        if(entry.owner==source && entry.offset==offset && entry.bytes==bytes){slot=&entry;break;}
        if(!slot || !entry.owner || (slot->owner && entry.used<slot->used))slot=&entry;
    }
    if(slot->owner!=source || slot->offset!=offset || slot->bytes!=bytes) {
        if(!nextSource || !releaseSource(*slot)){IOLockUnlock(scanout_gate);return poisoned?2:0;}
        auto *memory=IOSubMemoryDescriptor::withSubRange(source,offset,bytes,kIODirectionInOut);
        if(!memory){IOLockUnlock(scanout_gate);return 0;}
        if(memory->prepare()!=kIOReturnSuccess){memory->release();IOLockUnlock(scanout_gate);return 0;}
        source->retain();*slot={source,memory,nullptr,offset,bytes,nextSource++,++sourceUse};
    } else slot->used=++sourceUse;
    pending={true,false,false,++sequence,0,slot->memory,slot->map,stride,slot};
    gpuTraceEvent(GpuTraceDisplay,0,pending.id,7,uint64_t(uintptr_t(source)),0,0,slot->generation,0,0,1);
    gpuTraceEvent(GpuTraceDisplaySurface,0,pending.id,0,width,height,stride,mode.format,bytes,slot->memory->getLength());
    IOLockWakeup(scanout_gate,&pending,false);const uint64_t until=deadline(2000);
    while(!pending.done && !poisoned)
        if(IOLockSleepDeadline(scanout_gate,&pending,until,THREAD_UNINT)!=THREAD_AWAKENED)break;
    if(pending.delivered && (!pending.done || (pending.status && pending.status!=DitingScanoutNotSubmitted))) {
        poisoned=true;note("GPU copy not retired; retain pages and previous frame",pending.id,pending.status?:kIOReturnTimeout);
        IOLockUnlock(scanout_gate);return 2;
    }
    if(!pending.delivered)workerReady=false;
    bool ok=pending.done && !pending.status;
    if(ok && dbOn) {
        dbSettle();
        if(dbShown!=0 || dbFlipped>0) {
            if(dbFlipped>=0){for(unsigned k=0;k<200 && !dbLatched();++k)IODelay(100);dbSettle();}
            dbFlip(0);
            for(unsigned k=0;k<80 && !dbLatched();++k)IODelay(250);
            dbSettle();
        }
    }
    gpuTraceEvent(GpuTraceDisplayLatch,0,pending.id,pending.status,0,ok?slot->generation:0,0);
    if(ok && completed++<3)note("GPU frame completed",pending.id,0);
    pending={};
    if(!client)releaseSources();
    IOLockUnlock(scanout_gate);return ok?1:0;
}
