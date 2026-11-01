/**
 * @file oled_ssd1306.c
 * @brief Universal 128x64 OLED Display Driver (SSD1306 & SH1106 compatible).
 */

#include "oled_ssd1306.h"
#include <string.h>
#include <stdio.h>
#include "esp_log.h"
#include "driver/i2c.h"

static const char *TAG = "LILVRO_OLED";

// Detected I2C address (default 0x3C, auto-probed in oled_init)
static uint8_t s_oled_addr = OLED_I2C_ADDR;
static bool s_oled_detected = false;

// Framebuffer: 128 cols * 64 rows / 8 bits = 1024 bytes
static uint8_t s_framebuffer[OLED_SCREEN_WIDTH * (OLED_SCREEN_HEIGHT / 8)];

// Compact 5x7 ASCII font (characters 32 to 126)
static const uint8_t font5x7[][5] = {
    {0x00, 0x00, 0x00, 0x00, 0x00}, // ' ' (32)
    {0x00, 0x00, 0x5F, 0x00, 0x00}, // '!'
    {0x00, 0x07, 0x00, 0x07, 0x00}, // '"'
    {0x14, 0x7F, 0x14, 0x7F, 0x14}, // '#'
    {0x24, 0x2A, 0x7F, 0x2A, 0x12}, // '$'
    {0x23, 0x13, 0x08, 0x64, 0x62}, // '%'
    {0x36, 0x49, 0x55, 0x22, 0x50}, // '&'
    {0x00, 0x05, 0x03, 0x00, 0x00}, // '''
    {0x00, 0x1C, 0x22, 0x41, 0x00}, // '('
    {0x00, 0x41, 0x22, 0x1C, 0x00}, // ')'
    {0x14, 0x08, 0x3E, 0x08, 0x14}, // '*'
    {0x08, 0x08, 0x3E, 0x08, 0x08}, // '+'
    {0x00, 0x50, 0x30, 0x00, 0x00}, // ','
    {0x08, 0x08, 0x08, 0x08, 0x08}, // '-'
    {0x00, 0x60, 0x60, 0x00, 0x00}, // '.'
    {0x20, 0x10, 0x08, 0x04, 0x02}, // '/'
    {0x3E, 0x51, 0x49, 0x45, 0x3E}, // '0'
    {0x00, 0x42, 0x7F, 0x40, 0x00}, // '1'
    {0x42, 0x61, 0x51, 0x49, 0x46}, // '2'
    {0x21, 0x41, 0x45, 0x4B, 0x31}, // '3'
    {0x18, 0x14, 0x12, 0x7F, 0x10}, // '4'
    {0x27, 0x45, 0x45, 0x45, 0x39}, // '5'
    {0x3C, 0x4A, 0x49, 0x49, 0x30}, // '6'
    {0x01, 0x71, 0x09, 0x05, 0x03}, // '7'
    {0x36, 0x49, 0x49, 0x49, 0x36}, // '8'
    {0x06, 0x49, 0x49, 0x29, 0x1E}, // '9'
    {0x00, 0x36, 0x36, 0x00, 0x00}, // ':'
    {0x00, 0x56, 0x36, 0x00, 0x00}, // ';'
    {0x08, 0x14, 0x22, 0x41, 0x00}, // '<'
    {0x14, 0x14, 0x14, 0x14, 0x14}, // '='
    {0x00, 0x41, 0x22, 0x14, 0x08}, // '>'
    {0x02, 0x01, 0x51, 0x09, 0x06}, // '?'
    {0x32, 0x49, 0x79, 0x41, 0x3E}, // '@'
    {0x7E, 0x11, 0x11, 0x11, 0x7E}, // 'A'
    {0x7F, 0x49, 0x49, 0x49, 0x36}, // 'B'
    {0x3E, 0x41, 0x41, 0x41, 0x22}, // 'C'
    {0x7F, 0x41, 0x41, 0x22, 0x1C}, // 'D'
    {0x7F, 0x49, 0x49, 0x49, 0x41}, // 'E'
    {0x7F, 0x09, 0x09, 0x09, 0x01}, // 'F'
    {0x3E, 0x41, 0x49, 0x49, 0x7A}, // 'G'
    {0x7F, 0x08, 0x08, 0x08, 0x7F}, // 'H'
    {0x00, 0x41, 0x7F, 0x41, 0x00}, // 'I'
    {0x20, 0x40, 0x41, 0x3F, 0x01}, // 'J'
    {0x7F, 0x08, 0x14, 0x22, 0x41}, // 'K'
    {0x7F, 0x40, 0x40, 0x40, 0x40}, // 'L'
    {0x7F, 0x02, 0x0C, 0x02, 0x7F}, // 'M'
    {0x7F, 0x04, 0x08, 0x10, 0x7F}, // 'N'
    {0x3E, 0x41, 0x41, 0x41, 0x3E}, // 'O'
    {0x7F, 0x09, 0x09, 0x09, 0x06}, // 'P'
    {0x3E, 0x41, 0x51, 0x21, 0x5E}, // 'Q'
    {0x7F, 0x09, 0x19, 0x29, 0x46}, // 'R'
    {0x46, 0x49, 0x49, 0x49, 0x31}, // 'S'
    {0x01, 0x01, 0x7F, 0x01, 0x01}, // 'T'
    {0x3F, 0x40, 0x40, 0x40, 0x3F}, // 'U'
    {0x1F, 0x20, 0x40, 0x20, 0x1F}, // 'V'
    {0x3F, 0x40, 0x38, 0x40, 0x3F}, // 'W'
    {0x63, 0x14, 0x08, 0x14, 0x63}, // 'X'
    {0x07, 0x08, 0x70, 0x08, 0x07}, // 'Y'
    {0x61, 0x51, 0x49, 0x45, 0x43}, // 'Z'
    {0x00, 0x7F, 0x41, 0x41, 0x00}, // '['
    {0x02, 0x04, 0x08, 0x10, 0x20}, // '\'
    {0x00, 0x41, 0x41, 0x7F, 0x00}, // ']'
    {0x04, 0x02, 0x01, 0x02, 0x04}, // '^'
    {0x40, 0x40, 0x40, 0x40, 0x40}, // '_'
    {0x00, 0x01, 0x02, 0x04, 0x00}, // '`'
    {0x20, 0x54, 0x54, 0x54, 0x78}, // 'a'
    {0x7F, 0x48, 0x44, 0x44, 0x38}, // 'b'
    {0x38, 0x44, 0x44, 0x44, 0x20}, // 'c'
    {0x38, 0x44, 0x44, 0x48, 0x7F}, // 'd'
    {0x38, 0x54, 0x54, 0x54, 0x18}, // 'e'
    {0x08, 0x7E, 0x09, 0x01, 0x02}, // 'f'
    {0x0C, 0x52, 0x52, 0x52, 0x3E}, // 'g'
    {0x7F, 0x08, 0x04, 0x04, 0x78}, // 'h'
    {0x00, 0x44, 0x7D, 0x40, 0x00}, // 'i'
    {0x20, 0x40, 0x44, 0x3D, 0x00}, // 'j'
    {0x7F, 0x10, 0x28, 0x44, 0x00}, // 'k'
    {0x00, 0x41, 0x7F, 0x40, 0x00}, // 'l'
    {0x7C, 0x04, 0x18, 0x04, 0x78}, // 'm'
    {0x7C, 0x08, 0x04, 0x04, 0x78}, // 'n'
    {0x38, 0x44, 0x44, 0x44, 0x38}, // 'o'
    {0x7C, 0x14, 0x14, 0x14, 0x08}, // 'p'
    {0x08, 0x14, 0x14, 0x18, 0x7C}, // 'q'
    {0x7C, 0x08, 0x04, 0x04, 0x08}, // 'r'
    {0x48, 0x54, 0x54, 0x54, 0x20}, // 's'
    {0x04, 0x3F, 0x44, 0x40, 0x20}, // 't'
    {0x3C, 0x40, 0x40, 0x20, 0x7C}, // 'u'
    {0x1C, 0x20, 0x40, 0x20, 0x1C}, // 'v'
    {0x3C, 0x40, 0x30, 0x40, 0x3C}, // 'w'
    {0x44, 0x28, 0x10, 0x28, 0x44}, // 'x'
    {0x0C, 0x50, 0x50, 0x50, 0x3C}, // 'y'
    {0x44, 0x64, 0x54, 0x4C, 0x44}, // 'z'
    {0x00, 0x08, 0x36, 0x41, 0x00}, // '{'
    {0x00, 0x00, 0x7F, 0x00, 0x00}, // '|'
    {0x00, 0x41, 0x36, 0x08, 0x00}, // '}'
    {0x08, 0x08, 0x2A, 0x1C, 0x08}, // '~'
};

static esp_err_t oled_send_cmd(uint8_t cmd)
{
    uint8_t buf[2] = {0x00, cmd};
    return i2c_master_write_to_device(I2C_PORT_NUM, s_oled_addr, buf, 2, pdMS_TO_TICKS(50));
}

esp_err_t oled_init(void)
{
    ESP_LOGI(TAG, "Initializing I2C Port %d (SDA=GPIO%d, SCL=GPIO%d)...", I2C_PORT_NUM, PIN_I2C_SDA, PIN_I2C_SCL);

    i2c_config_t conf = {
        .mode = I2C_MODE_MASTER,
        .sda_io_num = PIN_I2C_SDA,
        .sda_pullup_en = GPIO_PULLUP_ENABLE,
        .scl_io_num = PIN_I2C_SCL,
        .scl_pullup_en = GPIO_PULLUP_ENABLE,
        .master.clk_speed = I2C_FREQ_HZ,
    };
    i2c_param_config(I2C_PORT_NUM, &conf);
    esp_err_t ret = i2c_driver_install(I2C_PORT_NUM, conf.mode, 0, 0, 0);
    if (ret != ESP_OK && ret != ESP_ERR_INVALID_STATE) {
        ESP_LOGE(TAG, "I2C driver install failed: %s", esp_err_to_name(ret));
        return ret;
    }

    // Auto-probe I2C address (0x3C first, then 0x3D)
    uint8_t test_byte = 0x00;
    if (i2c_master_write_to_device(I2C_PORT_NUM, 0x3C, &test_byte, 1, pdMS_TO_TICKS(50)) == ESP_OK) {
        s_oled_addr = 0x3C;
        s_oled_detected = true;
        ESP_LOGI(TAG, "Found OLED display at I2C address 0x3C!");
    } else if (i2c_master_write_to_device(I2C_PORT_NUM, 0x3D, &test_byte, 1, pdMS_TO_TICKS(50)) == ESP_OK) {
        s_oled_addr = 0x3D;
        s_oled_detected = true;
        ESP_LOGI(TAG, "Found OLED display at I2C address 0x3D!");
    } else {
        ESP_LOGW(TAG, "Warning: No ACK at 0x3C or 0x3D! Attempting with default 0x3C. Please check SDA(GPIO%d)/SCL(GPIO%d) wiring.", PIN_I2C_SDA, PIN_I2C_SCL);
        s_oled_addr = OLED_I2C_ADDR;
    }

    // Universal OLED Init sequence (Compatible with SSD1306 and SH1106)
    const uint8_t init_cmds[] = {
        0xAE,       // Display OFF
        0xD5, 0x80, // Set Display Clock Divide Ratio
        0xA8, 0x3F, // Set Multiplex Ratio (64 lines)
        0xD3, 0x00, // Set Display Offset (0)
        0x40,       // Set Display Start Line (0)
        0x8D, 0x14, // Charge Pump Setting (Internal VCC for SSD1306)
        0xAD, 0x8B, // DC-DC control (Internal VCC for SH1106)
        0x32,       // Pump voltage 8.0V (SH1106)
        0xA1,       // Segment Re-map: column 127 mapped to SEG0
        0xC8,       // COM Output Scan Direction: remapped mode
        0xDA, 0x12, // COM Pins Hardware Config: Alternative
        0x81, 0xCF, // Set Contrast Control
        0xD9, 0xF1, // Set Pre-charge Period
        0xDB, 0x40, // Set VCOMH Deselect Level
        0xA4,       // Entire Display ON: Resume to RAM content
        0xA6,       // Set Normal Display (non-inverted)
        0xAF        // Display ON
    };

    for (size_t i = 0; i < sizeof(init_cmds); i++) {
        oled_send_cmd(init_cmds[i]);
    }

    // Cleanly clear memory and paint boot screen
    oled_clear();
    oled_render_screen("BOOTING...", "Walkthrough", "Lil-Vro Starting...", false);
    ESP_LOGI(TAG, "OLED Initialized and Cleared Successfully!");
    return ESP_OK;
}

void oled_clear(void)
{
    memset(s_framebuffer, 0x00, sizeof(s_framebuffer));
}

void oled_draw_char(int x, int y, char c, bool invert)
{
    if (c < 32 || c > 126) c = ' ';
    const uint8_t *glyph = font5x7[c - 32];

    for (int col = 0; col < 5; col++) {
        int px = x + col;
        if (px >= OLED_SCREEN_WIDTH) break;

        uint8_t line = glyph[col];
        for (int row = 0; row < 7; row++) {
            int py = y + row;
            if (py >= OLED_SCREEN_HEIGHT) break;

            bool pixel_on = (line >> row) & 0x01;
            if (invert) pixel_on = !pixel_on;

            int page = py / 8;
            int bit = py % 8;
            int idx = page * OLED_SCREEN_WIDTH + px;

            if (pixel_on) {
                s_framebuffer[idx] |= (1 << bit);
            } else {
                s_framebuffer[idx] &= ~(1 << bit);
            }
        }
    }
}

void oled_draw_string(int x, int y, const char *str, bool invert)
{
    if (!str) return;
    int cur_x = x;
    while (*str) {
        if (*str == '\n') {
            cur_x = x;
            y += 9;
            str++;
            continue;
        }
        if (cur_x + 6 > OLED_SCREEN_WIDTH) {
            cur_x = x;
            y += 9;
        }
        if (y + 8 > OLED_SCREEN_HEIGHT) break;

        oled_draw_char(cur_x, y, *str, invert);
        cur_x += 6;
        str++;
    }
}

/**
 * @brief Push the full 1024-byte framebuffer to OLED display using universal Page Addressing.
 * Works reliably on BOTH SSD1306 and SH1106 displays, eliminating static snow!
 */
esp_err_t oled_update(void)
{
    uint8_t chunk[129];
    chunk[0] = 0x40; // Co=0, D/C#=1 -> Data stream

    for (uint8_t page = 0; page < 8; page++) {
        // 1. Set Page address (0xB0 to 0xB7)
        oled_send_cmd(0xB0 + page);

        // 2. Set Column address (SH1106 has 132 columns, display is centered with +2 offset)
        oled_send_cmd(0x02); // Lower column address (column 2)
        oled_send_cmd(0x10); // Higher column address (column 0)

        // 3. Send 128 bytes of page data
        memcpy(&chunk[1], &s_framebuffer[page * OLED_SCREEN_WIDTH], OLED_SCREEN_WIDTH);
        i2c_master_write_to_device(I2C_PORT_NUM, s_oled_addr, chunk, 129, pdMS_TO_TICKS(50));
    }

    return ESP_OK;
}

void oled_draw_pixel(int x, int y, bool on)
{
    if (x < 0 || x >= OLED_SCREEN_WIDTH || y < 0 || y >= OLED_SCREEN_HEIGHT) return;
    int idx = (y / 8) * OLED_SCREEN_WIDTH + x;
    int bit = y % 8;
    if (on) {
        s_framebuffer[idx] |= (1 << bit);
    } else {
        s_framebuffer[idx] &= ~(1 << bit);
    }
}

void oled_draw_line(int x0, int y0, int x1, int y1, bool on)
{
    int dx = (x1 > x0) ? (x1 - x0) : (x0 - x1);
    int sx = (x0 < x1) ? 1 : -1;
    int dy = (y1 > y0) ? (y0 - y1) : (y1 - y0); // dy is negative
    int sy = (y0 < y1) ? 1 : -1;
    int err = dx + dy, e2;

    while (1) {
        oled_draw_pixel(x0, y0, on);
        if (x0 == x1 && y0 == y1) break;
        e2 = 2 * err;
        if (e2 >= dy) { err += dy; x0 += sx; }
        if (e2 <= dx) { err += dx; y0 += sy; }
    }
}

void oled_draw_rect(int x, int y, int w, int h, bool on)
{
    for (int i = 0; i < w; i++) {
        oled_draw_pixel(x + i, y, on);
        oled_draw_pixel(x + i, y + h - 1, on);
    }
    for (int j = 0; j < h; j++) {
        oled_draw_pixel(x, y + j, on);
        oled_draw_pixel(x + w - 1, y + j, on);
    }
}

void oled_fill_rect(int x, int y, int w, int h, bool on)
{
    for (int i = 0; i < w; i++) {
        for (int j = 0; j < h; j++) {
            oled_draw_pixel(x + i, y + j, on);
        }
    }
}

void oled_draw_circle(int xc, int yc, int r, bool on)
{
    int x = 0, y = r;
    int d = 3 - 2 * r;
    while (y >= x) {
        oled_draw_pixel(xc + x, yc + y, on);
        oled_draw_pixel(xc - x, yc + y, on);
        oled_draw_pixel(xc + x, yc - y, on);
        oled_draw_pixel(xc - x, yc - y, on);
        oled_draw_pixel(xc + y, yc + x, on);
        oled_draw_pixel(xc - y, yc + x, on);
        oled_draw_pixel(xc + y, yc - x, on);
        oled_draw_pixel(xc - y, yc - x, on);
        x++;
        if (d > 0) { y--; d = d + 4 * (x - y) + 10; }
        else d = d + 4 * x + 6;
    }
}

void oled_fill_circle(int xc, int yc, int r, bool on)
{
    for (int y = -r; y <= r; y++) {
        for (int x = -r; x <= r; x++) {
            if (x * x + y * y <= r * r) {
                oled_draw_pixel(xc + x, yc + y, on);
            }
        }
    }
}

void oled_fill_round_rect(int x, int y, int w, int h, int r, bool on)
{
    if (r <= 0) {
        oled_fill_rect(x, y, w, h, on);
        return;
    }
    if (r * 2 > w) r = w / 2;
    if (r * 2 > h) r = h / 2;

    oled_fill_rect(x + r, y, w - 2 * r, h, on);
    oled_fill_rect(x, y + r, r, h - 2 * r, on);
    oled_fill_rect(x + w - r, y + r, r, h - 2 * r, on);
    oled_fill_circle(x + r, y + r, r, on);
    oled_fill_circle(x + w - r - 1, y + r, r, on);
    oled_fill_circle(x + r, y + h - r - 1, r, on);
    oled_fill_circle(x + w - r - 1, y + h - r - 1, r, on);
}

// ----------------------------------------------------------------------------
// Expressive Eyes & Face Rendering (Minimalist Two Eyes + Lower Mode Text)
// ----------------------------------------------------------------------------

static void draw_face_listening(void)
{
    // Alert, curious wide-open rounded eyes with dark pupil and shiny glints
    oled_fill_round_rect(24, 10, 30, 32, 9, true);
    oled_fill_circle(39, 26, 8, false); // black pupil
    oled_fill_circle(36, 23, 2, true);  // glint

    oled_fill_round_rect(74, 10, 30, 32, 9, true);
    oled_fill_circle(89, 26, 8, false); // black pupil
    oled_fill_circle(86, 23, 2, true);  // glint

    // Raised attentive eyebrows
    oled_draw_line(26, 5, 52, 5, true);
    oled_draw_line(76, 5, 102, 5, true);
}

static void draw_face_thinking(void)
{
    // Puzzled, looking up-and-right towards thought bubbles
    // Left eye looking up-right
    oled_fill_round_rect(24, 11, 30, 31, 9, true);
    oled_fill_circle(44, 21, 7, false); // pupil looking top-right
    oled_fill_circle(43, 19, 2, true);

    // Right eye slightly squinted / inquisitive
    oled_fill_round_rect(74, 15, 30, 27, 8, true);
    oled_fill_circle(94, 23, 6, false); // pupil looking top-right
    oled_fill_circle(93, 21, 2, true);

    // Inquisitive tilted left eyebrow
    oled_draw_line(24, 5, 54, 8, true);

    // Thought bubbles floating above right eye
    oled_draw_circle(108, 17, 2, true);
    oled_draw_circle(115, 11, 3, true);
    oled_draw_circle(122, 4, 4, true);
}

static void draw_face_speaking(void)
{
    // Joyful, smiling animated arched eyes (^  ^) + talking mouth + soundwaves
    for (int dx = 0; dx <= 26; dx++) {
        int dy = - (dx * (26 - dx)) / 14;
        oled_draw_line(26 + dx, 30 + dy, 26 + dx, 34 + dy, true);
        oled_draw_line(76 + dx, 30 + dy, 76 + dx, 34 + dy, true);
    }

    // Soundwave ripples on sides
    oled_draw_line(16, 20, 16, 32, true);
    oled_draw_line(11, 16, 11, 36, true);
    oled_draw_line(112, 20, 112, 32, true);
    oled_draw_line(117, 16, 117, 36, true);

    // Small cheerful talking mouth
    oled_draw_line(58, 33, 70, 33, true);
    oled_draw_line(60, 35, 68, 35, true);
}

static void draw_face_paused(void)
{
    // Peaceful sleeping eyes (-  -) with floating Zzz
    oled_draw_line(24, 27, 54, 27, true);
    oled_draw_line(25, 28, 53, 28, true);
    oled_draw_line(27, 29, 51, 29, true);

    oled_draw_line(74, 27, 104, 27, true);
    oled_draw_line(75, 28, 103, 28, true);
    oled_draw_line(77, 29, 101, 29, true);

    // Floating Zzz
    oled_draw_string(106, 17, "Z", false);
    oled_draw_string(114, 10, "z", false);
    oled_draw_string(120, 4, "z", false);
}

static void draw_face_happy_connected(void)
{
    // Beaming joyful eyes (^  ^) + wide happy smile + rosy cheeks
    for (int dx = 0; dx <= 26; dx++) {
        int dy = - (dx * (26 - dx)) / 12;
        oled_draw_line(26 + dx, 26 + dy, 26 + dx, 30 + dy, true);
        oled_draw_line(76 + dx, 26 + dy, 76 + dx, 30 + dy, true);
    }

    // Rosy blush cheek dots
    oled_fill_circle(18, 31, 2, true);
    oled_fill_circle(110, 31, 2, true);

    // Big happy open smile
    oled_draw_line(56, 31, 72, 31, true);
    oled_draw_line(57, 33, 71, 33, true);
    oled_draw_line(59, 35, 69, 35, true);
}

void oled_render_screen(const char *state, const char *mode, const char *caption, bool wifi_ok)
{
    oled_clear();

    // 1. STARTUP CONNECTING SCREENS (Clean minimal text)
    if (state && (strcmp(state, "BOOTING") == 0 || strcmp(state, "WIFI CONNECT") == 0)) {
        oled_draw_string(46, 12, "Thinko", true);
        oled_draw_string(8, 28, "Connecting Wi-Fi...", false);
        oled_draw_string(34, 44, "[ . . . . ]", false);
        oled_update();
        return;
    }

    if (state && strcmp(state, "SERVER CONNECT") == 0) {
        oled_draw_string(46, 12, "Thinko", true);
        oled_draw_string(6, 28, "Connecting Server...", false);
        oled_draw_string(34, 44, "[ . . . . ]", false);
        oled_update();
        return;
    }

    // 2. CONNECTED HAPPY FACE
    if (state && strcmp(state, "READY") == 0) {
        draw_face_happy_connected();
        oled_draw_string(16, 54, "Thinko is Ready!", false);
        oled_update();
        return;
    }

    // 3. MAIN RUNNING SCREENS (Two Expressive Eyes + Lower Mode Text)
    // Draw the two eyes based on state
    if (state && strcmp(state, "THINKING...") == 0) {
        draw_face_thinking();
    } else if (state && strcmp(state, "SPEAKING") == 0) {
        draw_face_speaking();
    } else if (state && strcmp(state, "PAUSED") == 0) {
        draw_face_paused();
    } else {
        // Default: LISTENING eyes!
        draw_face_listening();
    }

    // Lower side text: "Thinko • <Mode>" or caption
    char lower_text[48];
    if (state && strcmp(state, "PAUSED") == 0) {
        snprintf(lower_text, sizeof(lower_text), "Thinko * Paused");
    } else if (state && strcmp(state, "SPEAKING") == 0 && caption && strlen(caption) > 0) {
        snprintf(lower_text, sizeof(lower_text), "%s", caption);
    } else {
        const char *m = (mode && strlen(mode) > 0) ? mode : "Walkthrough";
        snprintf(lower_text, sizeof(lower_text), "Thinko * %s", m);
    }

    // Center lower text at y=54
    int text_len = strlen(lower_text);
    int text_x = (OLED_SCREEN_WIDTH - (text_len * 6)) / 2;
    if (text_x < 0) text_x = 0;
    oled_draw_string(text_x, 54, lower_text, false);

    oled_update();
}
