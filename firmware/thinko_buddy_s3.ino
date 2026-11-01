/*
 * Thinko ESP32-S3 Voice Tutor Firmware (Gemini Live Edition)
 *
 * Hardware Components:
 *   1. ESP32-S3 (or ESP32) Microcontroller
 *   2. INMP441 I2S Digital Microphone (16 kHz 16-bit PCM capture)
 *   3. MAX98357A I2S Audio Amplifier + Speaker (24 kHz 16-bit PCM playback)
 *   4. 1.3" or 0.96" I2C OLED Display (SSD1306 / SH1106, 128x64)
 *   5. Physical Pause/Resume Button (GPIO 0 BOOT or external push button)
 *
 * Architecture:
 *   - Connects to home Wi-Fi
 *   - Connects to Thinko Python Coordinator over WebSocket (ws://<LAPTOP_IP>:8765)
 *   - Full-duplex: streams INMP441 mic frames (binary) -> Python -> Gemini Live
 *   - Receives 24 kHz audio chunks (binary) <- Python <- Gemini Live -> plays via MAX98357A
 *   - Interruption: when audio_cancel is received, instantly mutes & flushes I2S DMA buffer
 *   - Pause: stops speaker output, preserves buffer, sends pause/resume events
 */

#include <WiFi.h>
#include <WebSocketsClient.h>
#include <Wire.h>
#include <Adafruit_GFX.h>
#include <Adafruit_SSD1306.h>
#include <ArduinoJson.h>
#include <driver/i2s.h>

// =========================================================================
// 1. Wi-Fi & Laptop Gateway Configuration
// =========================================================================
const char* WIFI_SSID     = "YOUR_WIFI_NAME";
const char* WIFI_PASSWORD = "YOUR_WIFI_PASSWORD";

// IP address of the laptop running `python main_live.py`
const char* LAPTOP_IP     = "192.168.29.114";
const uint16_t WS_PORT    = 8765;

// =========================================================================
// 2. Hardware Pinout (Configurable for ESP32-S3 or standard ESP32)
// =========================================================================
#define SCREEN_WIDTH 128
#define SCREEN_HEIGHT 64
#define OLED_RESET    -1
#define SCREEN_ADDRESS 0x3C

// OLED I2C Pins (Default ESP32: SDA=21, SCL=22. ESP32-S3: often 8/9 or 21/22)
#define I2C_SDA 21
#define I2C_SCL 22

// Pause Button (BOOT button is GPIO 0 on almost all ESP32/S3 boards)
#define PAUSE_BUTTON_PIN 0

// INMP441 Microphone (I2S Port 0 - Input)
#define I2S_MIC_PORT I2S_NUM_0
#define I2S_MIC_SCK  14   // Serial Clock (BCLK)
#define I2S_MIC_WS   15   // Word Select (LRCL)
#define I2S_MIC_SD   32   // Serial Data In (SDOUT from mic)

// MAX98357A Amplifier (I2S Port 1 - Output)
#define I2S_SPK_PORT I2S_NUM_1
#define I2S_SPK_BCLK 26   // Bit Clock (BCLK)
#define I2S_SPK_LRC  25   // Left/Right Clock (LRC)
#define I2S_SPK_DIN  27   // Data In (DIN to amp)

// Audio Buffer Sizes
#define MIC_CHUNK_SAMPLES 512   // 512 samples @ 16 kHz = 32 ms chunk
#define SPK_BUFFER_SIZE   4096

// =========================================================================
// 3. States & Global Variables
// =========================================================================
enum BuddyState {
  STATE_CONNECTING,
  STATE_READY,
  STATE_LISTENING,
  STATE_THINKING,
  STATE_SPEAKING,
  STATE_PAUSED,
  STATE_ERROR
};

BuddyState currentState = STATE_CONNECTING;
String currentMode = "Walkthrough";
String lastCaption = "";
bool isHardwarePaused = false;
bool wsConnected = false;

Adafruit_SSD1306 display(SCREEN_WIDTH, SCREEN_HEIGHT, &Wire, OLED_RESET);
WebSocketsClient webSocket;

// Button debounce
bool lastBtnState = HIGH;
unsigned long lastDebounceTime = 0;
const unsigned long debounceDelay = 50;
unsigned long btnPressStartTime = 0;
bool isLongPress = false;

// Audio buffers
int32_t micRawBuffer[MIC_CHUNK_SAMPLES];
int16_t micPcmBuffer[MIC_CHUNK_SAMPLES];

// Display animation
unsigned long lastDisplayUpdate = 0;
int animFrame = 0;

// =========================================================================
// 4. I2S Initialization
// =========================================================================
void setupI2SMicrophone() {
  i2s_config_t i2s_config = {
    .mode = (i2s_mode_t)(I2S_MODE_MASTER | I2S_MODE_RX),
    .sample_rate = 16000,
    .bits_per_sample = I2S_BITS_PER_SAMPLE_32BIT, // INMP441 sends 24-bit in 32-bit slot
    .channel_format = I2S_CHANNEL_FMT_ONLY_LEFT,
    .communication_format = I2S_COMM_FORMAT_STAND_I2S,
    .intr_alloc_flags = ESP_INTR_FLAG_LEVEL1,
    .dma_buf_count = 4,
    .dma_buf_len = MIC_CHUNK_SAMPLES,
    .use_apll = false,
    .tx_desc_auto_clear = false,
    .fixed_mclk = 0
  };

  i2s_pin_config_t pin_config = {
    .bck_io_num = I2S_MIC_SCK,
    .ws_io_num = I2S_MIC_WS,
    .data_out_num = I2S_PIN_NO_CHANGE,
    .data_in_num = I2S_MIC_SD
  };

  i2s_driver_install(I2S_MIC_PORT, &i2s_config, 0, NULL);
  i2s_set_pin(I2S_MIC_PORT, &pin_config);
  i2s_zero_dma_buffer(I2S_MIC_PORT);
  Serial.println("[I2S] INMP441 Microphone initialized (16 kHz, 16-bit mono).");
}

void setupI2SSpeaker() {
  i2s_config_t i2s_config = {
    .mode = (i2s_mode_t)(I2S_MODE_MASTER | I2S_MODE_TX),
    .sample_rate = 24000, // Gemini Live output rate
    .bits_per_sample = I2S_BITS_PER_SAMPLE_16BIT,
    .channel_format = I2S_CHANNEL_FMT_ONLY_LEFT,
    .communication_format = I2S_COMM_FORMAT_STAND_I2S,
    .intr_alloc_flags = ESP_INTR_FLAG_LEVEL1,
    .dma_buf_count = 8,
    .dma_buf_len = 512,
    .use_apll = false,
    .tx_desc_auto_clear = true,
    .fixed_mclk = 0
  };

  i2s_pin_config_t pin_config = {
    .bck_io_num = I2S_SPK_BCLK,
    .ws_io_num = I2S_SPK_LRC,
    .data_out_num = I2S_SPK_DIN,
    .data_in_num = I2S_PIN_NO_CHANGE
  };

  i2s_driver_install(I2S_SPK_PORT, &i2s_config, 0, NULL);
  i2s_set_pin(I2S_SPK_PORT, &pin_config);
  i2s_zero_dma_buffer(I2S_SPK_PORT);
  Serial.println("[I2S] MAX98357A Speaker initialized (24 kHz, 16-bit mono).");
}

// =========================================================================
// 5. OLED Display Rendering
// =========================================================================
void updateDisplay() {
  display.clearDisplay();
  display.setTextColor(SSD1306_WHITE);

  // Top header: Thinko + Wi-Fi status
  display.setTextSize(1);
  display.setCursor(0, 0);
  display.print("LIL-VRO");

  display.setCursor(75, 0);
  if (wsConnected) {
    display.print("WiFi: OK");
  } else {
    display.print("WiFi: ..");
  }
  display.drawFastHLine(0, 10, 128, SSD1306_WHITE);

  // Mode line
  display.setCursor(0, 14);
  display.print("Mode: ");
  display.print(currentMode);

  // Status icon / text
  display.setCursor(0, 26);
  display.setTextSize(1);
  switch (currentState) {
    case STATE_CONNECTING:
      display.print("[CONNECTING...]");
      break;
    case STATE_READY:
      display.print("[READY] Speak now");
      break;
    case STATE_LISTENING:
      display.print("[LISTENING...]");
      break;
    case STATE_THINKING:
      display.print("[THINKING...]");
      break;
    case STATE_SPEAKING:
      display.print("[SPEAKING...]");
      break;
    case STATE_PAUSED:
      display.print("[PAUSED]");
      break;
    case STATE_ERROR:
      display.print("[ERROR]");
      break;
  }

  // Short caption or STEM notation snippet
  display.setCursor(0, 40);
  display.setTextSize(1);
  if (lastCaption.length() > 0) {
    String snippet = lastCaption.substring(0, 42);
    display.println(snippet);
  } else if (currentState == STATE_SPEAKING) {
    display.println("Explaining concept...");
  } else if (currentState == STATE_PAUSED) {
    display.println("Press button to resume");
  } else {
    display.println("Ask your STEM question!");
  }

  // Bottom action bar
  display.drawFastHLine(0, 54, 128, SSD1306_WHITE);
  display.setCursor(0, 56);
  if (currentState == STATE_SPEAKING) {
    display.print("[Button]: Pause");
  } else if (currentState == STATE_PAUSED) {
    display.print("[Button]: Resume");
  } else {
    display.print("[Button]: Listen / Pause");
  }

  display.display();
}

// =========================================================================
// 6. WebSocket Event Handling
// =========================================================================
void webSocketEvent(WStype_t type, uint8_t * payload, size_t length) {
  switch (type) {
    case WStype_DISCONNECTED:
      Serial.println("[WS] Disconnected from Thinko server.");
      wsConnected = false;
      currentState = STATE_CONNECTING;
      break;

    case WStype_CONNECTED:
      Serial.println("[WS] Connected to Thinko server!");
      wsConnected = true;
      currentState = STATE_READY;
      webSocket.sendTXT("{\"type\":\"device_state\",\"state\":\"ready\"}");
      break;

    case WStype_TEXT: {
      StaticJsonDocument<512> doc;
      DeserializationError err = deserializeJson(doc, payload);
      if (err) return;

      const char* msgType = doc["type"];
      if (strcmp(msgType, "status") == 0) {
        const char* st = doc["state"];
        if (strcmp(st, "listening") == 0) currentState = STATE_LISTENING;
        else if (strcmp(st, "thinking") == 0) currentState = STATE_THINKING;
        else if (strcmp(st, "speaking") == 0) currentState = STATE_SPEAKING;
        else if (strcmp(st, "paused") == 0) {
          currentState = STATE_PAUSED;
          isHardwarePaused = true;
        } else if (strcmp(st, "ready") == 0) {
          currentState = STATE_READY;
          isHardwarePaused = false;
        }
      }
      else if (strcmp(msgType, "caption") == 0) {
        const char* stem = doc["stem_text"];
        const char* raw = doc["text"];
        lastCaption = stem ? String(stem) : String(raw);
      }
      else if (strcmp(msgType, "mode") == 0) {
        const char* m = doc["value"];
        if (m) currentMode = String(m);
      }
      // Instant Interruption: flush I2S speaker buffer immediately!
      else if (strcmp(msgType, "audio_cancel") == 0) {
        Serial.println("[Audio] Cancel received! Flushing I2S output buffer.");
        i2s_zero_dma_buffer(I2S_SPK_PORT);
        currentState = STATE_LISTENING;
      }
      // Audio End: Model finished generating audio
      else if (strcmp(msgType, "audio_end") == 0) {
        Serial.println("[Audio] Turn audio finished -> Switching to Listening.");
        currentState = STATE_LISTENING;
      }
      break;
    }

    // Binary audio frame from Python/Gemini Live (24 kHz PCM)
    case WStype_BIN:
      if (!isHardwarePaused && length > 0) {
        currentState = STATE_SPEAKING;
        size_t bytesWritten = 0;
        i2s_write(I2S_SPK_PORT, payload, length, &bytesWritten, portMAX_DELAY);
      }
      break;

    default:
      break;
  }
}

// =========================================================================
// 7. Button Handling (Short press: Pause/Resume; Long press: Reset)
// =========================================================================
void checkButton() {
  bool reading = digitalRead(PAUSE_BUTTON_PIN);

  if (reading != lastBtnState) {
    lastDebounceTime = millis();
  }

  if ((millis() - lastDebounceTime) > debounceDelay) {
    // Button just pressed (LOW because of INPUT_PULLUP)
    if (reading == LOW && btnPressStartTime == 0) {
      btnPressStartTime = millis();
      isLongPress = false;
    }
    // Button held long (> 1.5 seconds)
    else if (reading == LOW && (millis() - btnPressStartTime > 1500) && !isLongPress) {
      isLongPress = true;
      Serial.println("[Button] Long press detected -> Reset to Ready.");
      webSocket.sendTXT("{\"type\":\"button\",\"action\":\"ready\"}");
      i2s_zero_dma_buffer(I2S_SPK_PORT);
      currentState = STATE_READY;
      isHardwarePaused = false;
    }
    // Button released
    else if (reading == HIGH && btnPressStartTime > 0) {
      if (!isLongPress) {
        // Short press
        if (currentState == STATE_SPEAKING) {
          Serial.println("[Button] Short press -> PAUSE.");
          isHardwarePaused = true;
          currentState = STATE_PAUSED;
          webSocket.sendTXT("{\"type\":\"button\",\"action\":\"pause\"}");
        } else if (currentState == STATE_PAUSED) {
          Serial.println("[Button] Short press -> RESUME.");
          isHardwarePaused = false;
          currentState = STATE_SPEAKING;
          webSocket.sendTXT("{\"type\":\"button\",\"action\":\"resume\"}");
        } else {
          Serial.println("[Button] Short press -> Start Listening.");
          currentState = STATE_LISTENING;
          webSocket.sendTXT("{\"type\":\"button\",\"action\":\"listen\"}");
        }
      }
      btnPressStartTime = 0;
    }
  }

  lastBtnState = reading;
}

// =========================================================================
// 8. Microphone Streaming Loop
// =========================================================================
void streamMicrophone() {
  // STRICT HALF-DUPLEX:
  // When speaker is ON (or state is not STATE_LISTENING), microphone is completely OFF!
  // This physically prevents acoustic feedback between MAX98357A speaker and INMP441 mic in same case.
  if (isHardwarePaused || !wsConnected || currentState != STATE_LISTENING) {
    return;
  }

  size_t bytesRead = 0;
  esp_err_t result = i2s_read(I2S_MIC_PORT, micRawBuffer, sizeof(micRawBuffer), &bytesRead, 10);

  if (result == ESP_OK && bytesRead > 0) {
    int samplesRead = bytesRead / sizeof(int32_t);
    // Convert 24-bit in 32-bit slot to 16-bit PCM for Gemini Live
    for (int i = 0; i < samplesRead; i++) {
      micPcmBuffer[i] = (int16_t)(micRawBuffer[i] >> 14);
    }
    // Stream binary PCM chunk over WebSocket
    webSocket.sendBIN((uint8_t*)micPcmBuffer, samplesRead * sizeof(int16_t));
  }
}

// =========================================================================
// 9. Setup & Main Loop
// =========================================================================
void setup() {
  Serial.begin(115200);
  delay(500);
  Serial.println("\n--- Thinko ESP32-S3 Voice Buddy ---");

  pinMode(PAUSE_BUTTON_PIN, INPUT_PULLUP);

  Wire.begin(I2C_SDA, I2C_SCL);
  if (!display.begin(SSD1306_SWITCHCAPVCC, SCREEN_ADDRESS)) {
    Serial.println("[OLED] Warning: SSD1306 allocation failed (check SDA/SCL wiring).");
  } else {
    display.clearDisplay();
    display.display();
  }

  setupI2SMicrophone();
  setupI2SSpeaker();

  // Connect to Wi-Fi
  Serial.printf("[Wi-Fi] Connecting to %s...\n", WIFI_SSID);
  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);
  int retries = 0;
  while (WiFi.status() != WL_CONNECTED && retries < 20) {
    delay(500);
    Serial.print(".");
    retries++;
  }

  if (WiFi.status() == WL_CONNECTED) {
    Serial.printf("\n[Wi-Fi] Connected! IP: %s\n", WiFi.localIP().toString().c_str());
  } else {
    Serial.println("\n[Wi-Fi] Connection failed, will retry in background.");
  }

  // Connect to WebSocket Server on Laptop
  webSocket.begin(LAPTOP_IP, WS_PORT, "/");
  webSocket.onEvent(webSocketEvent);
  webSocket.setReconnectInterval(2000);
}

void loop() {
  webSocket.loop();
  checkButton();
  streamMicrophone();

  // Refresh OLED at ~10 Hz
  if (millis() - lastDisplayUpdate > 100) {
    lastDisplayUpdate = millis();
    updateDisplay();
  }
}
