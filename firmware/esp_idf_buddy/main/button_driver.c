/**
 * @file button_driver.c
 * @brief Push Button Driver with Debounce for Lil-Vro Buddy.
 */

#include "button_driver.h"
#include "pin_config.h"
#include "driver/gpio.h"
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "esp_log.h"

static const char *TAG = "BUTTON";

static button_callback_t s_btn_callback = NULL;

static void button_scan_task(void *pvParameters)
{
    int pressed_ms = 0;
    bool long_press_fired = false;

    while (1) {
        int level = gpio_get_level(PIN_BUTTON_PAUSE);

        if (level == 0) { // Active LOW (pressed)
            pressed_ms += 10;
            if (pressed_ms >= BUTTON_LONG_PRESS_MS && !long_press_fired) {
                ESP_LOGI(TAG, "Long press detected!");
                long_press_fired = true;
                if (s_btn_callback) {
                    s_btn_callback(BUTTON_EVENT_LONG_PRESS);
                }
            }
        } else { // Released (HIGH)
            if (pressed_ms >= BUTTON_DEBOUNCE_MS && !long_press_fired) {
                ESP_LOGI(TAG, "Short press detected!");
                if (s_btn_callback) {
                    s_btn_callback(BUTTON_EVENT_SHORT_PRESS);
                }
            }
            pressed_ms = 0;
            long_press_fired = false;
        }

        vTaskDelay(pdMS_TO_TICKS(10));
    }
}

esp_err_t button_init(button_callback_t cb)
{
    s_btn_callback = cb;

    gpio_config_t io_conf = {
        .pin_bit_mask = (1ULL << PIN_BUTTON_PAUSE),
        .mode = GPIO_MODE_INPUT,
        .pull_up_en = GPIO_PULLUP_ENABLE,
        .pull_down_en = GPIO_PULLDOWN_DISABLE,
        .intr_type = GPIO_INTR_DISABLE
    };

    esp_err_t err = gpio_config(&io_conf);
    if (err != ESP_OK) {
        ESP_LOGE(TAG, "Failed to configure button GPIO %d: %s", PIN_BUTTON_PAUSE, esp_err_to_name(err));
        return err;
    }

    BaseType_t ret = xTaskCreate(button_scan_task, "btn_scan", 2048, NULL, 3, NULL);
    if (ret != pdPASS) {
        ESP_LOGE(TAG, "Failed to create button task");
        return ESP_FAIL;
    }

    ESP_LOGI(TAG, "Button initialized on GPIO %d (active LOW)", PIN_BUTTON_PAUSE);
    return ESP_OK;
}
