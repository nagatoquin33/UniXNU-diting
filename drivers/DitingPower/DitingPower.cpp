/* SPDX-License-Identifier: BSD-2-Clause-Patent */
#include <IOKit/IOService.h>
#include <IOKit/IOLib.h>
#include <libkern/OSKextLib.h>
#include <mach/kmod.h>
#include <pexpert/pexpert.h>
#include "DitingPlatformResources.h"
extern kmod_info_t g_kernel_kmod_info;
#include "../DitingBootCapture/DitingBootCapture.h"
#include "../DitingUsb/DitingUsbDevice.h"
extern "C" {
void DitingAudioServiceStaticInit(void);
bool diting_audio_service_classes_ready(void) {
 static uint32_t state;
 uint32_t expected=0;
 if(__atomic_compare_exchange_n(&state,&expected,1,false,__ATOMIC_ACQ_REL,__ATOMIC_ACQUIRE)) {
  void *h=OSMetaClass::preModLoad(g_kernel_kmod_info.name);
  if(!h){__atomic_store_n(&state,3,__ATOMIC_RELEASE);return false;}
  DitingAudioServiceStaticInit();
  __atomic_store_n(&state,OSMetaClass::postModLoad(h)==0?2u:3u,__ATOMIC_RELEASE);
 }
 // Never repeat partially failed C++ meta-class constructors or wait on
 // another optional caller. Actual endpoint publication stays independent.
 return __atomic_load_n(&state,__ATOMIC_ACQUIRE)==2;
}
void sheng_adsp_probe(void);
void sheng_audio_probe(void);
void sheng_battery_start(void);
void DitingBatteryStaticInit(void);
volatile int32_t native_battery_stats[16];
void diting_power_start_optional(void) {
 diting_rpmh_init();
 // Register the transport classes independently of ADSP readiness. Actual
 // USB/audio services still publish only after their own hardware succeeds.
 // Audio registration covers the board's (currently retired) speaker path;
 // it is reported for diagnostics but must never gate the USB transport.
 const bool audioClasses=diting_audio_service_classes_ready();
 IOLog("DitingPower: audio transport classes %s; USB starts regardless\n",audioClasses?"registered":"unavailable");
 DitingUsb::start();
 unsigned enabled=0;PE_parse_boot_argn("diting_adsp",&enabled,sizeof(enabled));
 if(enabled!=2)return;
 static uint32_t started;
 if(__atomic_exchange_n(&started,1,__ATOMIC_ACQ_REL))return;
 sheng_adsp_probe();
 // DSP channel registration is ready synchronously; remote opens follow
 // only after firmware and PAS prerequisites complete on its worker.
 void *h=OSMetaClass::preModLoad(g_kernel_kmod_info.name);
 if(h){DitingBatteryStaticInit();if(!OSMetaClass::postModLoad(h))sheng_battery_start();}
 sheng_audio_probe();
}
}
