/*
 * Thinko ESP32 Interactive Buddy Firmware (Wi-Fi WebSocket Version)
 *
 * Hardware:
 *   - ESP32 Dev Module
 *   - 0.96" or 1.3" I2C OLED Display (SSD1306 128x64)
 *       - VCC -> 3.3V
 *       - GND -> GND
 *       - SCL -> GPIO 22 (Default ESP32 I2C SCL)
 *       - SDA -> GPIO 21 (Default ESP32 I2C SDA)
 *   - Pushbutton ("Done Speaking" / Trigger AI reasoning button):
 *       - One pin -> GPIO 0 (On-board BOOT button) or GPIO 4 (External button)
 *       - Other pin -> GND (Uses internal INPUT_PULLUP)
 *
 * Features:
 *   - Expressive animated faces on OLED (Idle, Listening, Thinking, Speaking, Paused)
 *   - Connects to your home/mobile hotspot Wi-Fi
 *   - Connects to Thinko WebSocket server on your laptop (ws://<laptop_ip>:8765)
 *   - Pressing the button sends {"type": "done_speaking"} to trigger instant AI reasoning!
 */

#include <WiFi.h>
#include <WebSocketsClient.h>
#include <Wire.h>
#include <Adafruit_GFX.h>
#include <Adafruit_SSD1306.h>
#include <ArduinoJson.h>

// -------------------------------------------------------------
// 1. Wi-Fi & Laptop WebSocket Configuration
// -------------------------------------------------------------
const char* WIFI_SSID     = "YOUR_WIFI_NAME";
const char* WIFI_PASSWORD = "YOUR_WIFI_PASSWORD";

// Your laptop's local IP address (e.g., 192.168.29.114)
const char* LAPTOP_IP     = "192.168.29.114";
const uint16_t WS_PORT    = 8765;

// -------------------------------------------------------------
// 2. Hardware Configuration
// -------------------------------------------------------------
#define SCREEN_WIDTH 128
#define SCREEN_HEIGHT 64
#define OLED_RESET    -1
#define SCREEN_ADDRESS 0x3C

// Button Pin:
// GPIO 0 is the on-board BOOT button on virtually all ESP32 boards.
// If you connect an external pushbutton, change this to GPIO 4, 18, etc.
#define BUTTON_PIN 0

// State constants matching Thinko
enum BuddyState {
  STATE_IDLE,
  STATE_LISTENING,
  STATE_THINKING,
  STATE_SPEAKING,
  STATE_PAUSED
};

Adafruit_SSD1306 display(SCREEN_WIDTH, SCREEN_HEIGHT, &Wire, OLED_RESET);
WebSocketsClient webSocket;

BuddyState currentState = STATE_IDLE;
bool wsConnected = false;
unsigned long lastAnimUpdate = 0;
int animFrame = 0;

bool lastButtonReading = HIGH;
bool debouncedButtonState = HIGH;
unsigned long lastDebounceTime = 0;
const unsigned long debounceDelay = 40;

// -------------------------------------------------------------
// Face Renderers for 128x64 OLED
// -------------------------------------------------------------
void drawEye(int x, int y, int w, int h, int pupilOffsetX, int pupilOffsetY, bool blink) {
  if (blink) {
    display.fillRoundRect(x - w / 2, y - 2, w, 4, 2, SSD1306_WHITE);
  } else {
    display.fillRoundRect(x - w / 2, y - h / 2, w, h, 6, SSD1306_WHITE);
    int pw = w / 2;
    int ph = h / 2;
    display.fillRoundRect(x + pupilOffsetX - pw / 2, y + pupilOffsetY - ph / 2, pw, ph, 3, SSD1306_BLACK);
    display.fillCircle(x + pupilOffsetX - pw / 4, y + pupilOffsetY - ph / 4, 2, SSD1306_WHITE);
  }
}

void drawMouth(int cx, int cy, BuddyState state, int frame) {
  if (state == STATE_SPEAKING) {
    int openHeight = 3 + (frame % 4) * 3;
    display.fillRoundRect(cx - 16, cy - openHeight / 2, 32, openHeight, 4, SSD1306_WHITE);
  } else if (state == STATE_PAUSED) {
    display.drawFastHLine(cx - 8, cy, 16, SSD1306_WHITE);
  } else {
    display.drawPixel(cx - 10, cy - 2, SSD1306_WHITE);
    display.drawLine(cx - 8, cy, cx + 8, cy, SSD1306_WHITE);
    display.drawPixel(cx + 10, cy - 2, SSD1306_WHITE);
  }
}

void renderFace() {
  display.clearDisplay();

  int leftEyeX = 40;
  int rightEyeX = 88;
  int eyeY = 26;
  int mouthY = 52;
  const char* statusText = "BUDDY: READY";

  switch (currentState) {
    case STATE_IDLE: {
      statusText = wsConnected ? "READY (PRESS BTN)" : "CONNECTING WI-FI...";
      bool blink = (animFrame % 45 == 0 || animFrame % 45 == 1);
      int lookX = 0;
      if (animFrame % 60 > 45) lookX = -3;
      else if (animFrame % 60 > 30) lookX = 3;
      
      drawEye(leftEyeX, eyeY, 26, 32, lookX, 0, blink);
      drawEye(rightEyeX, eyeY, 26, 32, lookX, 0, blink);
      drawMouth(64, mouthY, currentState, animFrame);
      break;
    }

    case STATE_LISTENING: {
      statusText = "LISTENING... (BTN=DONE)";
      drawEye(leftEyeX, eyeY, 30, 36, 0, 0, false);
      drawEye(rightEyeX, eyeY, 30, 36, 0, 0, false);
      drawMouth(64, mouthY, currentState, animFrame);

      int wave = (animFrame % 4) * 3;
      display.drawCircle(8, 26, 4 + wave, SSD1306_WHITE);
      display.drawCircle(120, 26, 4 + wave, SSD1306_WHITE);
      break;
    }

    case STATE_THINKING: {
      statusText = "THINKING...";
      drawEye(leftEyeX, eyeY, 26, 30, 0, -6, false);
      drawEye(rightEyeX, eyeY, 26, 30, 0, -6, false);
      drawMouth(64, mouthY, currentState, animFrame);

      int step = animFrame % 3;
      for (int i = 0; i < 3; i++) {
        if (i == step) {
          display.fillCircle(54 + i * 10, 8, 3, SSD1306_WHITE);
        } else {
          display.drawCircle(54 + i * 10, 8, 2, SSD1306_WHITE);
        }
      }
      break;
    }

    case STATE_SPEAKING: {
      statusText = "SPEAKING";
      drawEye(leftEyeX, eyeY, 28, 32, 0, 0, false);
      drawEye(rightEyeX, eyeY, 28, 32, 0, 0, false);
      drawMouth(64, mouthY, currentState, animFrame);
      break;
    }

    case STATE_PAUSED: {
      statusText = "PAUSED (ZZZ)";
      drawEye(leftEyeX, eyeY, 24, 28, 0, 0, true);
      drawEye(rightEyeX, eyeY, 24, 28, 0, 0, true);
      drawMouth(64, mouthY, currentState, animFrame);

      int zOffset = (animFrame % 10);
      display.setTextSize(1);
      display.setTextColor(SSD1306_WHITE);
      display.setCursor(98 + zOffset / 2, 14 - zOffset);
      display.print("z");
      display.setCursor(108 + zOffset / 2, 8 - zOffset);
      display.print("Z");
      break;
    }
  }

  // Draw bottom status bar
  display.setTextSize(1);
  display.setTextColor(SSD1306_WHITE);
  display.setCursor(2, 56);
  display.print(statusText);

  // Wi-Fi connected icon indicator (top-right dot)
  if (wsConnected) {
    display.drawPixel(124, 2, SSD1306_WHITE);
    display.drawPixel(125, 2, SSD1306_WHITE);
    display.drawPixel(124, 3, SSD1306_WHITE);
  }

  display.display();
}

// -------------------------------------------------------------
// WebSocket Event Handler
// -------------------------------------------------------------
void webSocketEvent(WStype_t type, uint8_t * payload, size_t length) {
  switch(type) {
    case WStype_DISCONNECTED:
      wsConnected = false;
      Serial.println("[WS] Disconnected from laptop!");
      break;
    case WStype_CONNECTED:
      wsConnected = true;
      Serial.println("[WS] Connected to Thinko server on laptop!");
      break;
    case WStype_TEXT: {
      // Parse JSON payload from laptop
      JsonDocument doc;
      DeserializationError err = deserializeJson(doc, payload, length);
      if (!err) {
        const char* msgType = doc["type"];
        if (msgType && strcmp(msgType, "state") == 0) {
          const char* val = doc["value"];
          if (strcmp(val, "idle") == 0) {
            currentState = STATE_IDLE;
          } else if (strcmp(val, "child_speaking") == 0) {
            currentState = STATE_LISTENING;
          } else if (strcmp(val, "agent_thinking") == 0 || strcmp(val, "thinking") == 0) {
            currentState = STATE_THINKING;
          } else if (strcmp(val, "agent_speaking") == 0 || strcmp(val, "speaking") == 0) {
            currentState = STATE_SPEAKING;
          } else if (strcmp(val, "paused") == 0) {
            currentState = STATE_PAUSED;
          }
          animFrame = 0;
        }
      }
      break;
    }
    default:
      break;
  }
}

// -------------------------------------------------------------
// Button Action
// -------------------------------------------------------------
void sendDoneSpeakingEvent() {
  Serial.println("[BUTTON] Done speaking pressed! Sending to Thinko...");
  if (wsConnected) {
    webSocket.sendTXT("{\"type\":\"done_speaking\"}");
  }
}

// -------------------------------------------------------------
// Setup & Loop
// -------------------------------------------------------------
void setup() {
  Serial.begin(115200);
  Serial.println("\n[Thinko ESP32 Wi-Fi Buddy Starting...]");

  pinMode(BUTTON_PIN, INPUT_PULLUP);

  Wire.begin();
  if (!display.begin(SSD1306_SWITCHCAPVCC, SCREEN_ADDRESS)) {
    Serial.println("[OLED] SSD1306 allocation failed. Check wiring (SDA=21, SCL=22).");
  } else {
    display.clearDisplay();
    display.setTextSize(1);
    display.setTextColor(SSD1306_WHITE);
    display.setCursor(15, 20);
    display.println("Thinko Buddy");
    display.setCursor(15, 35);
    display.println("Connecting Wi-Fi...");
    display.display();
  }

  // Connect to Wi-Fi
  Serial.printf("[Wi-Fi] Connecting to %s...\n", WIFI_SSID);
  WiFi.mode(WIFI_STA);
  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);

  while (WiFi.status() != WL_CONNECTED) {
    delay(500);
    Serial.print(".");
  }
  Serial.println("\n[Wi-Fi] Connected! IP: " + WiFi.localIP().toString());

  // Connect to WebSocket server on laptop
  webSocket.begin(LAPTOP_IP, WS_PORT, "/");
  webSocket.onEvent(webSocketEvent);
  webSocket.setReconnectInterval(2000);
}

void loop() {
  webSocket.loop();

  // Read and debounce button
  int reading = digitalRead(BUTTON_PIN);
  if (reading != lastButtonReading) {
    lastDebounceTime = millis();
  }

  if ((millis() - lastDebounceTime) > debounceDelay) {
    if (reading != debouncedButtonState) {
      debouncedButtonState = reading;
      if (debouncedButtonState == LOW) {
        // Button pressed down (active low)
        sendDoneSpeakingEvent();
      }
    }
  }
  lastButtonReading = reading;

  // Update Face Animation (~15 FPS)
  unsigned long now = millis();
  if (now - lastAnimUpdate > 65) {
    lastAnimUpdate = now;
    animFrame++;
    renderFace();
  }
}
