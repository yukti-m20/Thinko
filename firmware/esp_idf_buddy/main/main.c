/**
 * @file main.c
 * @brief Lil-Vro AI Study Buddy - Native ESP-IDF FreeRTOS Main Entrypoint.
 *
 * Implements:
 *  - Dual I2S drivers (INMP441 16kHz Rx & MAX98357A 24kHz Tx)
 *  - Strict Half-Duplex audio pipeline (Mic completely muted during speaker playback)
 *  - WebSocket Client for duplex audio & JSON telemetry streaming
 *  - Push-button pause/resume handling
 *  - SSD1306 OLED UI state and STEM caption rendering
 */

#include <stdio.h>
#include <string.h>
#include <stdbool.h>

#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "freertos/event_groups.h"
#include "freertos/ringbuf.h"

#include "esp_system.h"
#include "esp_wifi.h"
#include "esp_event.h"
#include "esp_log.h"
#include "nvs_flash.h"
#include "esp_netif.h"
#include "esp_websocket_client.h"
#include "esp_timer.h"
#include "cJSON.h"

#include "pin_config.h"
#include "config.h"
#include "audio_i2s.h"
#include "oled_ssd1306.h"
#include "button_driver.h"

static const char *TAG = "THINKO_MAIN";

// ============================================================================
// System States
// ============================================================================
typedef enum {
    STATE_BOOTING = 0,
    STATE_CONNECTING_WIFI,
    STATE_CONNECTING_WS,
    STATE_READY,
    STATE_LISTENING,
    STATE_THINKING,
    STATE_SPEAKING,
    STATE_PAUSED
} system_state_t;

static volatile system_state_t s_system_state = STATE_BOOTING;
static volatile bool s_wifi_connected = false;
static volatile bool s_ws_connected = false;
static volatile bool s_is_paused = false;
static volatile bool s_stream_ended = false;

static char s_caption_text[128] = "Ready to learn!";
static char s_mode_text[32] = "Walkthrough";

// FreeRTOS Ringbuffer for incoming 24 kHz speaker audio chunks (32 KB buffer)
#define SPK_RINGBUF_SIZE (32 * 1024)
static RingbufHandle_t s_spk_ringbuf = NULL;

static esp_websocket_client_handle_t s_ws_client = NULL;
static TaskHandle_t s_oled_task_handle = NULL;

// Helper to get string name of current state for display
static const char* get_state_str(system_state_t state)
{
    switch (state) {
        case STATE_BOOTING:         return "BOOTING";
        case STATE_CONNECTING_WIFI: return "WIFI CONNECT";
        case STATE_CONNECTING_WS:   return "SERVER CONNECT";
        case STATE_READY:           return "READY";
        case STATE_LISTENING:       return "LISTENING";
        case STATE_THINKING:        return "THINKING...";
        case STATE_SPEAKING:        return "SPEAKING";
        case STATE_PAUSED:          return "PAUSED";
        default:                    return "IDLE";
    }
}

static void trigger_oled_update(void)
{
    if (s_oled_task_handle) {
        xTaskNotifyGive(s_oled_task_handle);
    }
}

// ============================================================================
// Button Callback
// ============================================================================
static void on_button_event(button_event_t event)
{
    if (event == BUTTON_EVENT_SHORT_PRESS) {
        s_is_paused = !s_is_paused;
        if (s_is_paused) {
            ESP_LOGI(TAG, "Pause requested via button");
            audio_i2s_clear_spk_dma();
            s_system_state = STATE_PAUSED;
            if (s_ws_client && esp_websocket_client_is_connected(s_ws_client)) {
                const char *msg = "{\"type\":\"button\",\"action\":\"pause\"}";
                esp_websocket_client_send_text(s_ws_client, msg, strlen(msg), pdMS_TO_TICKS(100));
            }
        } else {
            ESP_LOGI(TAG, "Resume requested via button");
            s_system_state = STATE_LISTENING;
            if (s_ws_client && esp_websocket_client_is_connected(s_ws_client)) {
                const char *msg = "{\"type\":\"button\",\"action\":\"resume\"}";
                esp_websocket_client_send_text(s_ws_client, msg, strlen(msg), pdMS_TO_TICKS(100));
            }
        }
        trigger_oled_update();
    } else if (event == BUTTON_EVENT_LONG_PRESS) {
        ESP_LOGI(TAG, "Reset/Ready requested via long button press");
        s_is_paused = false;
        audio_i2s_clear_spk_dma();
        s_system_state = STATE_READY;
        if (s_ws_client && esp_websocket_client_is_connected(s_ws_client)) {
            const char *msg = "{\"type\":\"button\",\"action\":\"ready\"}";
            esp_websocket_client_send_text(s_ws_client, msg, strlen(msg), pdMS_TO_TICKS(100));
        }
        trigger_oled_update();
    }
}

// ============================================================================
// FreeRTOS Tasks
// ============================================================================

/**
 * @brief OLED UI Task (Runs on Core 0)
 */
static void oled_task(void *pvParameters)
{
    while (1) {
        ulTaskNotifyTake(pdTRUE, pdMS_TO_TICKS(250));
        oled_render_screen(
            get_state_str(s_system_state),
            s_mode_text,
            s_caption_text,
            s_wifi_connected
        );
    }
}

/**
 * @brief Speaker Playback Task (Priority 6, Core 1)
 * Reads decoded 24 kHz 16-bit PCM chunks from the ringbuffer and writes to MAX98357A.
 */
static void speaker_play_task(void *pvParameters)
{
    int64_t thinking_start_us = 0;

    while (1) {
        // Hardware Safety Watchdog: If in THINKING state for > 6.5s without audio, auto-recover to LISTENING
        if (s_system_state == STATE_THINKING) {
            if (thinking_start_us == 0) {
                thinking_start_us = esp_timer_get_time();
            } else if ((esp_timer_get_time() - thinking_start_us) > 6500000LL) {
                ESP_LOGW(TAG, "Thinking timeout (6.5s) on ESP32 -> Auto-recovering to LISTENING");
                s_system_state = STATE_LISTENING;
                thinking_start_us = 0;
                trigger_oled_update();
            }
        } else {
            thinking_start_us = 0;
        }

        size_t item_size = 0;
        void *item = xRingbufferReceiveUpTo(s_spk_ringbuf, &item_size, pdMS_TO_TICKS(100), 1024);

        if (item && item_size > 0) {
            thinking_start_us = 0;
            if (s_system_state == STATE_THINKING) {
                s_system_state = STATE_SPEAKING;
                trigger_oled_update();
            }
            if (!s_is_paused) {
                size_t samples = item_size / sizeof(int16_t);
                size_t written = 0;
                audio_i2s_write_spk((const int16_t *)item, samples, &written, portMAX_DELAY);
            }
            vRingbufferReturnItem(s_spk_ringbuf, item);
        } else {
            // Ring buffer empty. If server signaled stream completion, switch back to listening
            if (s_system_state == STATE_SPEAKING && s_stream_ended && !s_is_paused) {
                s_stream_ended = false;
                s_system_state = STATE_LISTENING;
                trigger_oled_update();
                ESP_LOGI(TAG, "Speaker turn completed -> switched to LISTENING");
            }
        }
    }
}

/**
 * @brief Microphone Streaming Task (Priority 5, Core 1)
 * Reads 16 kHz 16-bit PCM from INMP441 and sends binary frames over WebSocket.
 * Strictly gated when speaker is outputting or device is paused.
 */
static void mic_stream_task(void *pvParameters)
{
    // Buffer 2 chunks (1024 samples = 64 ms of 16 kHz audio = 2048 bytes) for smooth Wi-Fi transmission
    int16_t mic_buf[MIC_CHUNK_SAMPLES * 2];
    size_t accumulated = 0;

    while (1) {
        size_t samples_read = 0;
        esp_err_t err = audio_i2s_read_mic(&mic_buf[accumulated], MIC_CHUNK_SAMPLES, &samples_read, pdMS_TO_TICKS(100));

        if (err == ESP_OK && samples_read > 0) {
            accumulated += samples_read;

            if (accumulated >= (MIC_CHUNK_SAMPLES * 2)) {
                // Strict Half-Duplex condition:
                // ONLY transmit if WS is connected AND state is LISTENING AND not paused
                if (s_ws_connected &&
                    s_ws_client != NULL &&
                    esp_websocket_client_is_connected(s_ws_client) &&
                    s_system_state == STATE_LISTENING &&
                    !s_is_paused) {

                    int ret = esp_websocket_client_send_bin(
                        s_ws_client,
                        (const char *)mic_buf,
                        accumulated * sizeof(int16_t),
                        portMAX_DELAY
                    );

                    if (ret > 0) {
                        static int s_chunks_sent = 0;
                        s_chunks_sent++;
                        if (s_chunks_sent % 50 == 0) {
                            ESP_LOGI(TAG, "Streaming mic audio to Gemini... (%d chunks sent)", s_chunks_sent);
                        }
                    }
                }
                accumulated = 0;
            }
        } else {
            vTaskDelay(pdMS_TO_TICKS(10));
        }
    }
}

// ============================================================================
// WebSocket Event Handler
// ============================================================================
static void websocket_event_handler(void *handler_args, esp_event_base_t base, int32_t event_id, void *event_data)
{
    esp_websocket_event_data_t *data = (esp_websocket_event_data_t *)event_data;

    switch (event_id) {
        case WEBSOCKET_EVENT_CONNECTED:
            ESP_LOGI(TAG, "WebSocket Connected to %s! Displaying Happy Face...", CONFIG_WS_URI);
            vTaskDelay(pdMS_TO_TICKS(100)); // Brief 100ms pause for TCP handshake to settle
            s_ws_connected = true;
            s_is_paused = false;
            s_system_state = STATE_READY; // Displays HAPPY FACE!
            trigger_oled_update();
            vTaskDelay(pdMS_TO_TICKS(1800)); // Display happy face for 1.8s
            s_system_state = STATE_LISTENING; // Transition to LISTENING eyes!
            trigger_oled_update();
            break;

        case WEBSOCKET_EVENT_DISCONNECTED:
            ESP_LOGW(TAG, "WebSocket Disconnected");
            s_ws_connected = false;
            s_system_state = STATE_CONNECTING_WS;
            trigger_oled_update();
            break;

        case WEBSOCKET_EVENT_DATA:
            if (data->op_code == 0x02) {
                // Binary Frame: 24 kHz PCM audio chunk for MAX98357A speaker
                if (data->data_len > 0 && s_spk_ringbuf) {
                    // Strict Half-Duplex: switch state to SPEAKING immediately
                    if (s_system_state != STATE_SPEAKING && !s_is_paused) {
                        s_system_state = STATE_SPEAKING;
                        s_stream_ended = false;
                        ESP_LOGI(TAG, "Gemini speaking -> Muting mic to prevent echo");
                        trigger_oled_update();
                    }

                    // Push chunk into ringbuffer
                    BaseType_t res = xRingbufferSend(
                        s_spk_ringbuf,
                        data->data_ptr,
                        data->data_len,
                        pdMS_TO_TICKS(20)
                    );
                    if (res != pdTRUE) {
                        ESP_LOGW(TAG, "Audio ringbuffer full, dropped %d bytes", data->data_len);
                    }
                }
            } else if (data->op_code == 0x01 && data->data_len > 0) {
                // Text Frame: JSON control message from coordinator
                cJSON *root = cJSON_ParseWithLength(data->data_ptr, data->data_len);
                if (!root) {
                    break;
                }

                cJSON *type_item = cJSON_GetObjectItem(root, "type");
                if (cJSON_IsString(type_item) && type_item->valuestring) {
                    const char *type = type_item->valuestring;

                    if (strcmp(type, "status") == 0) {
                        cJSON *state_item = cJSON_GetObjectItem(root, "state");
                        if (cJSON_IsString(state_item) && state_item->valuestring) {
                            const char *st = state_item->valuestring;
                            if (strcmp(st, "listening") == 0) {
                                s_is_paused = false;
                                s_system_state = STATE_LISTENING;
                            } else if (strcmp(st, "thinking") == 0) {
                                if (!s_is_paused) s_system_state = STATE_THINKING;
                            } else if (strcmp(st, "speaking") == 0) {
                                if (!s_is_paused) s_system_state = STATE_SPEAKING;
                            } else if (strcmp(st, "paused") == 0) {
                                s_is_paused = true;
                                audio_i2s_clear_spk_dma();
                                s_system_state = STATE_PAUSED;
                            } else if (strcmp(st, "ready") == 0) {
                                s_is_paused = false;
                                s_system_state = STATE_READY;
                            }
                            trigger_oled_update();
                        }
                    } else if (strcmp(type, "caption") == 0) {
                        cJSON *stem = cJSON_GetObjectItem(root, "stem_text");
                        cJSON *raw = cJSON_GetObjectItem(root, "text");
                        const char *cap = NULL;
                        if (cJSON_IsString(stem) && stem->valuestring && strlen(stem->valuestring) > 0) {
                            cap = stem->valuestring;
                        } else if (cJSON_IsString(raw) && raw->valuestring) {
                            cap = raw->valuestring;
                        }
                        if (cap) {
                            strncpy(s_caption_text, cap, sizeof(s_caption_text) - 1);
                            s_caption_text[sizeof(s_caption_text) - 1] = '\0';
                            trigger_oled_update();
                        }
                    } else if (strcmp(type, "audio_cancel") == 0) {
                        ESP_LOGI(TAG, "Interruption received: flushing speaker buffers");
                        audio_i2s_clear_spk_dma();
                        if (s_spk_ringbuf) {
                            // Empty all pending items from ringbuffer
                            size_t sz = 0;
                            void *item = NULL;
                            while ((item = xRingbufferReceiveUpTo(s_spk_ringbuf, &sz, 0, 4096)) != NULL) {
                                vRingbufferReturnItem(s_spk_ringbuf, item);
                            }
                        }
                        if (!s_is_paused) {
                            s_system_state = STATE_LISTENING;
                        }
                        trigger_oled_update();
                    } else if (strcmp(type, "audio_end") == 0) {
                        s_stream_ended = true;
                    } else if (strcmp(type, "mode") == 0) {
                        cJSON *val = cJSON_GetObjectItem(root, "value");
                        if (cJSON_IsString(val) && val->valuestring) {
                            strncpy(s_mode_text, val->valuestring, sizeof(s_mode_text) - 1);
                            s_mode_text[sizeof(s_mode_text) - 1] = '\0';
                            trigger_oled_update();
                        }
                    }
                }
                cJSON_Delete(root);
            }
            break;

        case WEBSOCKET_EVENT_ERROR:
            ESP_LOGE(TAG, "WebSocket error occurred");
            break;

        default:
            break;
    }
}

// ============================================================================
// Wi-Fi Connection Management
// ============================================================================
static void wifi_event_handler(void *arg, esp_event_base_t event_base, int32_t event_id, void *event_data)
{
    if (event_base == WIFI_EVENT && event_id == WIFI_EVENT_STA_START) {
        ESP_LOGI(TAG, "Wi-Fi started, attempting to connect to '%s'...", CONFIG_WIFI_SSID);
        s_system_state = STATE_CONNECTING_WIFI;
        trigger_oled_update();
        esp_wifi_connect();
    } else if (event_base == WIFI_EVENT && event_id == WIFI_EVENT_STA_DISCONNECTED) {
        ESP_LOGW(TAG, "Wi-Fi disconnected, reconnecting in 2 seconds...");
        s_wifi_connected = false;
        s_system_state = STATE_CONNECTING_WIFI;
        trigger_oled_update();
        vTaskDelay(pdMS_TO_TICKS(2000));
        esp_wifi_connect();
    } else if (event_base == IP_EVENT && event_id == IP_EVENT_STA_GOT_IP) {
        ip_event_got_ip_t *event = (ip_event_got_ip_t *)event_data;
        ESP_LOGI(TAG, "Wi-Fi Connected! IP Address: " IPSTR, IP2STR(&event->ip_info.ip));
        s_wifi_connected = true;
        s_system_state = STATE_CONNECTING_WS;
        trigger_oled_update();

        // Start WebSocket client
        if (s_ws_client) {
            esp_websocket_client_start(s_ws_client);
        }
    }
}

static void wifi_init_sta(void)
{
    ESP_ERROR_CHECK(esp_netif_init());
    ESP_ERROR_CHECK(esp_event_loop_create_default());
    esp_netif_create_default_wifi_sta();

    wifi_init_config_t cfg = WIFI_INIT_CONFIG_DEFAULT();
    ESP_ERROR_CHECK(esp_wifi_init(&cfg));

    ESP_ERROR_CHECK(esp_event_handler_instance_register(WIFI_EVENT,
                                                        ESP_EVENT_ANY_ID,
                                                        &wifi_event_handler,
                                                        NULL,
                                                        NULL));
    ESP_ERROR_CHECK(esp_event_handler_instance_register(IP_EVENT,
                                                        IP_EVENT_STA_GOT_IP,
                                                        &wifi_event_handler,
                                                        NULL,
                                                        NULL));

    wifi_config_t wifi_config = {
        .sta = {
            .ssid = CONFIG_WIFI_SSID,
            .password = CONFIG_WIFI_PASSWORD,
            .threshold.authmode = WIFI_AUTH_WPA2_PSK,
        },
    };
    ESP_ERROR_CHECK(esp_wifi_set_mode(WIFI_MODE_STA));
    ESP_ERROR_CHECK(esp_wifi_set_config(WIFI_IF_STA, &wifi_config));
    ESP_ERROR_CHECK(esp_wifi_start());
}

// ============================================================================
// Application Entrypoint
// ============================================================================
void app_main(void)
{
    ESP_LOGI(TAG, "=========================================");
    ESP_LOGI(TAG, "   Lil-Vro AI Buddy Firmware (ESP-IDF)   ");
    ESP_LOGI(TAG, "=========================================");

    // 1. Initialize NVS (required for Wi-Fi storage)
    esp_err_t ret = nvs_flash_init();
    if (ret == ESP_ERR_NVS_NO_FREE_PAGES || ret == ESP_ERR_NVS_NEW_VERSION_FOUND) {
        ESP_ERROR_CHECK(nvs_flash_erase());
        ret = nvs_flash_init();
    }
    ESP_ERROR_CHECK(ret);

    // 2. Initialize OLED Display (I2C)
    if (oled_init() == ESP_OK) {
        xTaskCreatePinnedToCore(oled_task, "oled_ui", 3072, NULL, 2, &s_oled_task_handle, 0);
    }

    // 3. Initialize Audio Ringbuffer
    s_spk_ringbuf = xRingbufferCreate(SPK_RINGBUF_SIZE, RINGBUF_TYPE_BYTEBUF);
    if (!s_spk_ringbuf) {
        ESP_LOGE(TAG, "Failed to allocate audio ringbuffer!");
    }

    // 4. Initialize Dual I2S (Mic & Speaker)
    ESP_ERROR_CHECK(audio_i2s_init());

    // 5. Initialize Push Button Driver
    ESP_ERROR_CHECK(button_init(on_button_event));

    // 6. Create Audio Processing Tasks on Core 1
    xTaskCreatePinnedToCore(mic_stream_task, "mic_stream", 4096, NULL, 5, NULL, 1);
    xTaskCreatePinnedToCore(speaker_play_task, "spk_play", 4096, NULL, 6, NULL, 1);

    // 7. Configure WebSocket Client
    esp_websocket_client_config_t ws_cfg = {
        .uri = CONFIG_WS_URI,
        .buffer_size = 8192,
        .network_timeout_ms = 10000,
    };
    s_ws_client = esp_websocket_client_init(&ws_cfg);
    if (s_ws_client) {
        esp_websocket_register_events(s_ws_client, WEBSOCKET_EVENT_ANY, websocket_event_handler, (void *)s_ws_client);
    }

    // 8. Start Wi-Fi
    wifi_init_sta();

    ESP_LOGI(TAG, "All subsystems running!");
}
