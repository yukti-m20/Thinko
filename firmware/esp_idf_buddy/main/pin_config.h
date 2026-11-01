/**
 * @file pin_config.h
 * @brief Hardware Pin Definitions for Lil-Vro ESP32-S3 Voice Buddy.
 */

#pragma once

#include "driver/gpio.h"

#ifdef __cplusplus
extern "C" {
#endif

// =========================================================================
// 1. INMP441 Digital Microphone (I2S0 Input)
// =========================================================================
#define PIN_I2S_MIC_SCK         GPIO_NUM_4   // Bit Clock (BCLK / SCK)
#define PIN_I2S_MIC_WS          GPIO_NUM_5   // Word Select (LRCL / WS)
#define PIN_I2S_MIC_SD          GPIO_NUM_6   // Serial Data In from Mic (SDOUT / SD)

// Sample rate & format
#define MIC_SAMPLE_RATE_HZ      16000        // 16 kHz for Gemini Live
#define MIC_CHUNK_SAMPLES       512          // 512 samples = 32 ms chunk (1024 bytes)

// =========================================================================
// 2. MAX98357A Audio Amplifier + Speaker (I2S1 Output)
// =========================================================================
#define PIN_I2S_SPK_BCLK        GPIO_NUM_15  // Bit Clock (BCLK)
#define PIN_I2S_SPK_LRC         GPIO_NUM_16  // Left/Right Word Clock (LRC / WS)
#define PIN_I2S_SPK_DIN         GPIO_NUM_7   // Serial Data Out to Amp (DIN)

// Sample rate & format
#define SPK_SAMPLE_RATE_HZ      24000        // 24 kHz Gemini Live output
#define SPK_DMA_BUFFER_COUNT    6
#define SPK_DMA_BUFFER_LEN      512

// =========================================================================
// 3. SSD1306 128x64 OLED Display (I2C)
// =========================================================================
#define PIN_I2C_SDA             GPIO_NUM_8   // I2C Data
#define PIN_I2C_SCL             GPIO_NUM_9   // I2C Clock
#define I2C_PORT_NUM            I2C_NUM_0    // I2C Port 0
#define I2C_FREQ_HZ             400000       // 400 kHz Fast Mode
#define OLED_I2C_ADDR           0x3C         // Standard 0x3C (or 0x3D)

#define OLED_SCREEN_WIDTH       128
#define OLED_SCREEN_HEIGHT      64

// =========================================================================
// 4. Pause / Resume Push Button
// =========================================================================
// GPIO 10 is a safe, non-strapping pin for the pause/resume push button.
// (Avoids GPIO 0 which is the boot strapping pin).
#define PIN_BUTTON_PAUSE        GPIO_NUM_10
#define BUTTON_DEBOUNCE_MS      50
#define BUTTON_LONG_PRESS_MS    1500

#ifdef __cplusplus
}
#endif
