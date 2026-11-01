# Lil-Vro ESP32-S3 Interactive Voice Tutor (Gemini Live Edition)

Transform your **ESP32-S3** into a physical, screen-free STEM study buddy with full-duplex conversational voice using Google's **Gemini Live API**!

```
     ┌──────────────────────────────────────────────┐
     │           LIL-VRO ESP32-S3 BUDDY             │
     │   ┌──────────────────────────────────────┐   │
     │   │ LIL-VRO                     WiFi: OK │   │  <-- 1.3" OLED Display
     │   │ Mode: Walkthrough                    │   │      (SSD1306 / SH1106)
     │   │ [SPEAKING...]                        │   │
     │   │ H₂O breaks down into H₂ + O₂         │   │
     │   │ [Button]: Pause                      │   │
     │   └──────────────────────────────────────┘   │
     │                                              │
     │     [🎤 INMP441]           [🔊 MAX98357A]    │  <-- Full-duplex I2S Audio
     │   Digital Mic (16kHz)     Amplifier (24kHz)  │
     │                                              │
     │                 [ PAUSE ]                    │  <-- Physical Button (GPIO 0)
     │            (Short: Pause/Resume)             │      (Long: Reset to Ready)
     └──────────────────────┬───────────────────────┘
                            │
                     Wi-Fi WebSockets
                     ws://<LAPTOP_IP>:8765
                            │
                            ▼
              [ Lil-Vro Python Coordinator ]
                            │
                     Gemini Live API
```

---

## 1. Hardware Wiring (ESP32-S3)

All pin assignments align directly with [`esp_idf_buddy/main/pin_config.h`](esp_idf_buddy/main/pin_config.h):

### A. INMP441 Digital Microphone (I2S0 Input):
| INMP441 Pin | ESP32-S3 Pin | Description |
|:---|:---|:---|
| **SCK** | **GPIO 4** | I2S0 Bit Clock (BCLK) |
| **WS** | **GPIO 5** | Word Select (LRCL / WS) |
| **SD** | **GPIO 6** | Serial Data Out (SD) |
| **L/R** | **GND** | Selects Left Channel |
| **VDD** | **3.3V** | Power (⚠️ 3.3V only) |
| **GND** | **GND** | Common Ground |

### B. MAX98357A Audio Amplifier + Speaker (I2S1 Output):
| MAX98357A Pin | ESP32-S3 Pin | Description |
|:---|:---|:---|
| **BCLK** | **GPIO 15** | I2S1 Bit Clock |
| **LRC** | **GPIO 16** | I2S1 Left/Right Word Clock (WS) |
| **DIN** | **GPIO 7** | Serial Data In (DIN) |
| **GAIN** | **GND** | 9 dB clean default gain |
| **SD_MODE** | **Leave open** or 3.3V | Left/Right auto-mix |
| **VIN** | **5V** (or VBUS) | 5V delivers optimal volume |
| **GND** | **GND** | Common Ground |

### C. 1.3" or 0.96" SSD1306 OLED Display (I2C):
| OLED Pin | ESP32-S3 Pin | Description |
|:---|:---|:---|
| **SDA** | **GPIO 8** | I2C Data |
| **SCL** | **GPIO 9** | I2C Clock |
| **VCC** | **3.3V** | Power |
| **GND** | **GND** | Common Ground |

### D. Pause/Resume Push Button:
| Button Pin | ESP32-S3 Pin | Description |
|:---|:---|:---|
| **Pin 1** | **GPIO 10** | Safe non-strapping pin (internal pull-up enabled, active LOW) |
| **Pin 2** | **GND** | Common Ground |

---

## 2. Firmware Options

### Recommended: Native ESP-IDF FreeRTOS Firmware
Go to [`firmware/esp_idf_buddy`](esp_idf_buddy/) for the native ESP-IDF implementation:
```bash
. /home/pranjal/.espressif/v6.1/esp-idf/export.sh
cd firmware/esp_idf_buddy
idf.py set-target esp32s3
idf.py build
idf.py -p /dev/ttyACM0 flash monitor
```

### Alternative: Arduino IDE
1. Open [`firmware/thinko_buddy_s3.ino`](thinko_buddy_s3.ino).
2. Configure Wi-Fi SSID and Laptop IP in lines 30–36.
3. Select board **ESP32-S3 Dev Module** and click **Upload**.

---

## 3. Running Lil-Vro

1. Make sure your laptop and ESP32 are on the same Wi-Fi network.
2. Ensure `GEMINI_API_KEY` is set in your `.env`.
3. Start the coordinator on your laptop:
   ```bash
   python main_live.py
   ```
4. Power on your ESP32-S3. The OLED will show `[READY]`.
5. Speak your question. Lil-Vro will guide you with Socratic questions!
6. Short press the button anytime while speaking to pause, and press again to resume.
7. **Strict Half-Duplex Operation**: When Lil-Vro is speaking, the microphone is automatically muted to prevent acoustic feedback within the enclosure. Automatic 0.8s silence detection ends the student's turn cleanly without manual cuts.

