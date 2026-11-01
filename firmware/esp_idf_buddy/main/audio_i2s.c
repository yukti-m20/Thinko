/**
 * @file audio_i2s.c
 * @brief I2S Audio Driver Implementation for INMP441 (Rx) and MAX98357A (Tx).
 */

#include "audio_i2s.h"
#include <string.h>
#include "esp_log.h"
#include "driver/i2s_std.h"

static const char *TAG = "thinko_audio_i2s";

static i2s_chan_handle_t s_rx_handle = NULL;
static i2s_chan_handle_t s_tx_handle = NULL;

// Temporary 32-bit slot buffer for INMP441 conversion
static int32_t s_raw_mic_buffer[MIC_CHUNK_SAMPLES];

esp_err_t audio_i2s_init(void)
{
    esp_err_t ret = ESP_OK;

    // -------------------------------------------------------------------------
    // 1. INMP441 Microphone (I2S0 - RX, Master, 16 kHz Mono)
    // -------------------------------------------------------------------------
    ESP_LOGI(TAG, "Initializing INMP441 Mic (16 kHz, I2S0, SCK=%d, WS=%d, SD=%d)...",
             PIN_I2S_MIC_SCK, PIN_I2S_MIC_WS, PIN_I2S_MIC_SD);

    i2s_chan_config_t rx_chan_cfg = I2S_CHANNEL_DEFAULT_CONFIG(I2S_NUM_0, I2S_ROLE_MASTER);
    rx_chan_cfg.dma_desc_num = 6;
    rx_chan_cfg.dma_frame_num = MIC_CHUNK_SAMPLES;

    ret = i2s_new_channel(&rx_chan_cfg, NULL, &s_rx_handle);
    if (ret != ESP_OK) {
        ESP_LOGE(TAG, "Failed to create I2S Rx channel: %s", esp_err_to_name(ret));
        return ret;
    }

    // INMP441 sends 24-bit audio in 32-bit slot
    i2s_std_config_t rx_std_cfg = {
        .clk_cfg = I2S_STD_CLK_DEFAULT_CONFIG(MIC_SAMPLE_RATE_HZ),
        .slot_cfg = I2S_STD_PHILIPS_SLOT_DEFAULT_CONFIG(I2S_DATA_BIT_WIDTH_32BIT, I2S_SLOT_MODE_MONO),
        .gpio_cfg = {
            .mclk = I2S_GPIO_UNUSED,
            .bclk = PIN_I2S_MIC_SCK,
            .ws   = PIN_I2S_MIC_WS,
            .dout = I2S_GPIO_UNUSED,
            .din  = PIN_I2S_MIC_SD,
            .invert_flags = {
                .mclk_inv = false,
                .bclk_inv = false,
                .ws_inv   = false,
            },
        },
    };
    rx_std_cfg.slot_cfg.slot_mask = I2S_STD_SLOT_LEFT;

    ret = i2s_channel_init_std_mode(s_rx_handle, &rx_std_cfg);
    if (ret != ESP_OK) {
        ESP_LOGE(TAG, "Failed to init I2S Rx std mode: %s", esp_err_to_name(ret));
        return ret;
    }

    ret = i2s_channel_enable(s_rx_handle);
    if (ret != ESP_OK) {
        ESP_LOGE(TAG, "Failed to enable I2S Rx channel: %s", esp_err_to_name(ret));
        return ret;
    }

    // -------------------------------------------------------------------------
    // 2. MAX98357A Speaker Amp (I2S1 - TX, Master, 24 kHz Mono)
    // -------------------------------------------------------------------------
    ESP_LOGI(TAG, "Initializing MAX98357A Speaker (24 kHz, I2S1, BCLK=%d, LRC=%d, DIN=%d)...",
             PIN_I2S_SPK_BCLK, PIN_I2S_SPK_LRC, PIN_I2S_SPK_DIN);

    i2s_chan_config_t tx_chan_cfg = I2S_CHANNEL_DEFAULT_CONFIG(I2S_NUM_1, I2S_ROLE_MASTER);
    tx_chan_cfg.dma_desc_num = SPK_DMA_BUFFER_COUNT;
    tx_chan_cfg.dma_frame_num = SPK_DMA_BUFFER_LEN;

    ret = i2s_new_channel(&tx_chan_cfg, &s_tx_handle, NULL);
    if (ret != ESP_OK) {
        ESP_LOGE(TAG, "Failed to create I2S Tx channel: %s", esp_err_to_name(ret));
        return ret;
    }

    i2s_std_config_t tx_std_cfg = {
        .clk_cfg = I2S_STD_CLK_DEFAULT_CONFIG(SPK_SAMPLE_RATE_HZ),
        .slot_cfg = I2S_STD_PHILIPS_SLOT_DEFAULT_CONFIG(I2S_DATA_BIT_WIDTH_16BIT, I2S_SLOT_MODE_MONO),
        .gpio_cfg = {
            .mclk = I2S_GPIO_UNUSED,
            .bclk = PIN_I2S_SPK_BCLK,
            .ws   = PIN_I2S_SPK_LRC,
            .dout = PIN_I2S_SPK_DIN,
            .din  = I2S_GPIO_UNUSED,
            .invert_flags = {
                .mclk_inv = false,
                .bclk_inv = false,
                .ws_inv   = false,
            },
        },
    };
    tx_std_cfg.slot_cfg.slot_mask = I2S_STD_SLOT_LEFT;

    ret = i2s_channel_init_std_mode(s_tx_handle, &tx_std_cfg);
    if (ret != ESP_OK) {
        ESP_LOGE(TAG, "Failed to init I2S Tx std mode: %s", esp_err_to_name(ret));
        return ret;
    }

    ret = i2s_channel_enable(s_tx_handle);
    if (ret != ESP_OK) {
        ESP_LOGE(TAG, "Failed to enable I2S Tx channel: %s", esp_err_to_name(ret));
        return ret;
    }

    ESP_LOGI(TAG, "Dual I2S Audio System Initialized Successfully!");
    return ESP_OK;
}

esp_err_t audio_i2s_read_mic(int16_t *pcm_out, size_t max_samples, size_t *samples_read, TickType_t timeout)
{
    if (!s_rx_handle || !pcm_out || max_samples == 0) {
        return ESP_ERR_INVALID_ARG;
    }

    size_t to_read_samples = max_samples < MIC_CHUNK_SAMPLES ? max_samples : MIC_CHUNK_SAMPLES;
    size_t bytes_to_read = to_read_samples * sizeof(int32_t);
    size_t bytes_read = 0;

    esp_err_t ret = i2s_channel_read(s_rx_handle, s_raw_mic_buffer, bytes_to_read, &bytes_read, timeout);
    if (ret == ESP_OK && bytes_read > 0) {
        size_t count = bytes_read / sizeof(int32_t);
        // Convert 24-bit data in 32-bit slot to clean 16-bit PCM for Gemini Live with DC-blocking
        // Shift by 13 for balanced sensitivity (middle ground between >> 14 baseline and >> 12 high sensitivity)
        static int32_t s_dc_filter = 0;
        for (size_t i = 0; i < count; i++) {
            int32_t sample = s_raw_mic_buffer[i] >> 13;
            s_dc_filter += (sample - (s_dc_filter >> 8));
            int32_t filtered = sample - (s_dc_filter >> 8);
            if (filtered > 32767) filtered = 32767;
            if (filtered < -32768) filtered = -32768;
            pcm_out[i] = (int16_t)filtered;
        }
        if (samples_read) {
            *samples_read = count;
        }
    } else {
        if (samples_read) {
            *samples_read = 0;
        }
    }

    return ret;
}

esp_err_t audio_i2s_write_spk(const int16_t *pcm_in, size_t samples_count, size_t *samples_written, TickType_t timeout)
{
    if (!s_tx_handle || !pcm_in || samples_count == 0) {
        return ESP_ERR_INVALID_ARG;
    }

    // Audio volume is digitally scaled by coordinator; stream directly to I2S DMA
    size_t bytes_to_write = samples_count * sizeof(int16_t);
    size_t bytes_written = 0;

    esp_err_t ret = i2s_channel_write(s_tx_handle, pcm_in, bytes_to_write, &bytes_written, timeout);
    if (samples_written) {
        *samples_written = bytes_written / sizeof(int16_t);
    }

    return ret;
}

void audio_i2s_clear_spk_dma(void)
{
    if (!s_tx_handle) return;
    // Quickly disable and re-enable to drop in-flight DMA hardware buffers
    i2s_channel_disable(s_tx_handle);
    i2s_channel_enable(s_tx_handle);
}
