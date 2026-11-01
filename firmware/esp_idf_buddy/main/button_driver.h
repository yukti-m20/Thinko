/**
 * @file button_driver.h
 * @brief Push Button Driver with Debounce for Lil-Vro Buddy.
 */

#pragma once

#include <stdbool.h>
#include "esp_err.h"

#ifdef __cplusplus
extern "C" {
#endif

typedef enum {
    BUTTON_EVENT_SHORT_PRESS = 0,   // Toggle Pause / Resume
    BUTTON_EVENT_LONG_PRESS         // Reset / Interrupt session
} button_event_t;

typedef void (*button_callback_t)(button_event_t event);

/**
 * @brief Initialize the button GPIO and start the FreeRTOS debounce task.
 * @param cb Callback function invoked upon short or long press.
 */
esp_err_t button_init(button_callback_t cb);

#ifdef __cplusplus
}
#endif
