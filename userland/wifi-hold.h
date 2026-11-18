/* Ported from UniXNU-zizhan userland/wifi-hold.h @ 034a0b0 */
/* SPDX-License-Identifier: BSD-2-Clause-Patent */
#ifndef DITING_WIFI_HOLD_H
#define DITING_WIFI_HOLD_H
#include <stdbool.h>

enum diting_wifi_hold_action {
    DitingWifiHoldWait,
    DitingWifiHoldProbe,
    DitingWifiHoldStopped,
    DitingWifiHoldLinkLost,
    DitingWifiHoldStartupTimeout,
    DitingWifiHoldInvalidClock
};

struct diting_wifi_hold {
    double began, first_success, last_success, next_probe;
    unsigned attempts, successes, failures, link_losses;
    bool stopped;
};

static inline enum diting_wifi_hold_action
diting_wifi_hold_poll(struct diting_wifi_hold *state, double now, bool link, bool ipv4,
    bool reported, bool probe_running)
{
    if (state->stopped) return DitingWifiHoldStopped;
    if (!(now >= state->began)) {
        state->stopped = true;
        return DitingWifiHoldInvalidClock;
    }
    if (state->successes && (!link || !ipv4)) {
        state->stopped = true;
        ++state->link_losses;
        return DitingWifiHoldLinkLost;
    }
    if (!state->successes && now - state->began >= 330) {
        state->stopped = true;
        return DitingWifiHoldStartupTimeout;
    }
    if (link && ipv4 && reported && !probe_running && now >= state->next_probe)
        return DitingWifiHoldProbe;
    return DitingWifiHoldWait;
}

static inline void
diting_wifi_hold_result(struct diting_wifi_hold *state, double now, bool success)
{
    if (state->stopped) return;
    ++state->attempts;
    if (success) {
        if (!state->successes) state->first_success = now;
        ++state->successes;
        state->last_success = now;
        state->next_probe = now + 60;
        if (state->successes >= 64) state->stopped = true;
    } else {
        ++state->failures;
        state->next_probe = now + 8;
        if (state->successes || state->failures >= 4) state->stopped = true;
    }
}
#endif
