/**
 * @file audio_i2s.h
 * @brief I2S Audio Driver Header for INMP441 (Rx) and MAX98357A (Tx) on ESP32-S3.
 */

#pragma once

#include <stdint.h>
#include <stddef.h>
#include "esp_err.h"
#include "freertos/FreeRTOS.h"
#include "pin_config.h"

#ifdef __cplusplus
extern "C" {
#endif

/**
 * @brief Initialize both INMP441 (I2S0 Rx @ 16kHz) and MAX98357A (I2S1 Tx @ 24kHz).
 */
esp_err_t audio_i2s_init(void);

/**
 * @brief Read 16 kHz 16-bit mono PCM samples from INMP441 microphone.
 * Converts 24-bit/32-bit slot audio to 16-bit PCM for Gemini Live.
 */
esp_err_t audio_i2s_read_mic(int16_t *pcm_out, size_t max_samples, size_t *samples_read, TickType_t timeout);

/**
 * @brief Write 24 kHz 16-bit PCM audio chunks to MAX98357A speaker amp.
 */
esp_err_t audio_i2s_write_spk(const int16_t *pcm_in, size_t samples_count, size_t *samples_written, TickType_t timeout);

/**
 * @brief Immediately silence and zero the speaker DMA buffer (used on interruption).
 */
void audio_i2s_clear_spk_dma(void);

#ifdef __cplusplus
}
#endif
