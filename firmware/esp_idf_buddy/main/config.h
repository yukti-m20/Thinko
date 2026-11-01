/**
 * @file config.h
 * @brief Wi-Fi and WebSocket Server Configuration for Lil-Vro Buddy.
 */

#pragma once

#ifdef __cplusplus
extern "C" {
#endif

// =========================================================================
// Wi-Fi Network Credentials
// =========================================================================
#define CONFIG_WIFI_SSID            "esp"
#define CONFIG_WIFI_PASSWORD        "12345678"

// =========================================================================
// Python WebSocket Coordinator Server (Laptop)
// =========================================================================
#define CONFIG_LAPTOP_IP            "10.30.183.62"
#define CONFIG_WS_PORT              8765

// WebSocket URL format: ws://<IP>:<PORT>/
#define CONFIG_WS_URI               "ws://" CONFIG_LAPTOP_IP ":8765"

#ifdef __cplusplus
}
#endif
