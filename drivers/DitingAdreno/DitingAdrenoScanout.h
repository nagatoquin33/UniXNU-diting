/* SPDX-License-Identifier: BSD-2-Clause-Patent */
#pragma once
#include <IOKit/IOMemoryDescriptor.h>
#include "DitingScanoutWire.h"
extern "C" {
void diting_scanout_initialize(uint64_t,size_t,uint32_t,uint32_t,uint32_t);
int diting_scanout_frame(IOMemoryDescriptor *,size_t,uint32_t,uint32_t,uint32_t);
bool diting_scanout_quarantined(void);
void diting_scanout_idle(void);
void diting_scanout_cpu_frame(void);
void diting_scanout_set_tag(uint32_t);
uint32_t diting_scanout_latch_poll(void);
int diting_panel_slot_take(uint32_t width,uint32_t height,uint32_t bytesPerRow,uint32_t bytes,uint64_t *phys);
void diting_panel_slot_give(uint64_t phys);
IOMemoryDescriptor *diting_panel_slot_memory(uint64_t phys,uint32_t bytes);
bool diting_panel_slot_range(uint64_t phys,uint64_t bytes);
uint64_t diting_panel_slot_address(uint64_t phys);
IOReturn diting_scanout_connect(task_t);
void diting_scanout_disconnect(task_t);
IOReturn diting_scanout_call(task_t,unsigned,const void *,size_t,void *,size_t);
IOMemoryDescriptor *diting_scanout_memory(task_t);
}
