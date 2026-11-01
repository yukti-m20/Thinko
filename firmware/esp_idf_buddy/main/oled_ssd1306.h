/**
 * @file oled_ssd1306.h
 * @brief SSD1306 128x64 OLED Display Driver for ESP-IDF.
 */

#pragma once

#include <stdint.h>
#include <stdbool.h>
#include "esp_err.h"
#include "pin_config.h"

#ifdef __cplusplus
extern "C" {
#endif

/**
 * @brief Initialize I2C bus and SSD1306 display.
 */
esp_err_t oled_init(void);

/**
 * @brief Clear framebuffer.
 */
void oled_clear(void);

/**
 * @brief Draw a string onto the framebuffer at (x, y).
 */
void oled_draw_pixel(int x, int y, bool on);
void oled_draw_line(int x0, int y0, int x1, int y1, bool on);
void oled_draw_rect(int x, int y, int w, int h, bool on);
void oled_fill_rect(int x, int y, int w, int h, bool on);
void oled_draw_circle(int xc, int yc, int r, bool on);
void oled_fill_circle(int xc, int yc, int r, bool on);
void oled_fill_round_rect(int x, int y, int w, int h, int r, bool on);

/**
 * @brief Push the full 1024-byte framebuffer to the SSD1306 display over I2C.
 */
esp_err_t oled_update(void);

/**
 * @brief Render the expressive Lil-Vro screen with animated eyes, faces, and captions.
 * @param state Current state (e.g., "WIFI CONNECT", "SERVER CONNECT", "READY", "LISTENING", "THINKING...", "SPEAKING", "PAUSED")
 * @param mode Active learning mode ("Walkthrough", "Teach-back", "Quiz")
 * @param caption Spoken caption text (with STEM notation)
 * @param wifi_ok True if connected to Wi-Fi
 */
void oled_render_screen(const char *state, const char *mode, const char *caption, bool wifi_ok);

#ifdef __cplusplus
}
#endif
