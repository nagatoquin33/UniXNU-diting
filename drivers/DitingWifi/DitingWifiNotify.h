/* Ported from UniXNU-zizhan PongWifi @ 034a0b0 */
/* SPDX-License-Identifier: BSD-2-Clause-Patent */
#ifndef DITING_WIFI_NOTIFY_H
#define DITING_WIFI_NOTIFY_H
#include <stdint.h>
#include <stdbool.h>

/* Protected by the network driver's lock. Producers never deliver socket
 * or ifnet events from the cooperative firmware dispatcher. */
struct diting_wifi_notification {
    uint32_t kind;
    int32_t result, rssi;
    uint32_t keyed;
};
#define DITING_WIFI_NOTIFY_CAPACITY 32
struct diting_wifi_notification_queue {
    struct diting_wifi_notification entries[DITING_WIFI_NOTIFY_CAPACITY];
    unsigned first, count;
};
static inline bool diting_wifi_notification_push(struct diting_wifi_notification_queue *q,
                                              struct diting_wifi_notification event)
{
    if (q->count == DITING_WIFI_NOTIFY_CAPACITY) return false;
    q->entries[(q->first + q->count) % DITING_WIFI_NOTIFY_CAPACITY] = event;
    ++q->count;
    return true;
}
static inline bool diting_wifi_notification_pop(struct diting_wifi_notification_queue *q,
                                             struct diting_wifi_notification *event)
{
    if (!q->count) return false;
    *event = q->entries[q->first];
    q->first = (q->first + 1) % DITING_WIFI_NOTIFY_CAPACITY;
    --q->count;
    return true;
}
static inline void diting_wifi_notification_reset(struct diting_wifi_notification_queue *q)
{
    q->first = q->count = 0;
}
#endif
