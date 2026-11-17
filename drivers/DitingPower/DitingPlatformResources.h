/* SPDX-License-Identifier: BSD-2-Clause-Patent */
#ifndef DITING_PLATFORM_RESOURCES_H
#define DITING_PLATFORM_RESOURCES_H
#include <stdbool.h>
#include <stdint.h>
/* Diting 原厂设备树 live DT: rsc@17a00000 qcom,tcs-config declares ACTIVE_TCS
 * command slots 0–2 and SLEEP_TCS slots 3–4 (sleep). Slot map:
 *   TCS0 = touch (Goodix IOVDD via diting_rpmh_vote)
 *   TCS1 = Wi-Fi + ADSP shared votes
 *   TCS2 = GPU ARC parent votes
 * TCS3/TCS4 are sleep slots and must not carry active client votes. */
enum {
    DITING_RPMH_TOUCH_TCS  = 0,
    DITING_RPMH_SHARED_TCS = 1,
    DITING_RPMH_GPU_TCS    = 2,
};
#ifdef __cplusplus
extern "C" {
#endif
void diting_rpmh_init(void);
bool diting_scm_call_lock(void);
void diting_scm_call_unlock(void);
bool diting_rpmh_vote(uint32_t address, uint32_t value);
bool diting_smmu_lease_lock(void);
void diting_smmu_lease_unlock(void);
#ifdef __cplusplus
}
#endif
#endif
