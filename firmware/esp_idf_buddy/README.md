# Lil-Vro AI Study Buddy - ESP-IDF Firmware

This is the native **ESP-IDF** firmware for the Lil-Vro AI Study Buddy running on an **ESP32-S3** microcontroller. It implements:
- Dual I2S audio architecture (16 kHz microphone input + 24 kHz speaker output)
- Strict half-duplex communication (Mic is muted whenever speaker is active to eliminate acoustic echo feedback)
- Real-time bidirectional WebSocket streaming to the Python coordinator
- 128x64 SSD1306 OLED UI showing connection status, learning mode, and STEM captions
- Push button handling for instant pause / resume

---

## 1. Hardware Pinout & Wiring Connections

### A. ESP32-S3 Pin Allocation Summary

| Component | Pin Function | ESP32-S3 Pin | Notes |
| :--- | :--- | :--- | :--- |
| **INMP441 (Mic)** | SCK (BCLK) | **GPIO 4** | I2S0 Bit Clock |
| | WS (LRC) | **GPIO 5** | I2S0 Word Select |
| | SD (Data Out) | **GPIO 6** | I2S0 Serial Data In |
| | L/R | **GND** | Left channel select |
| | VDD | **3.3V** | Power (Do NOT connect to 5V) |
| | GND | **GND** | Common Ground |
| **MAX98357A (Amp)** | BCLK | **GPIO 15** | I2S1 Bit Clock |
| | LRC (WS) | **GPIO 16** | I2S1 Left/Right Clock |
| | DIN | **GPIO 7** | I2S1 Serial Data Out |
| | GAIN | **GND** | 9 dB Gain (clean sound) |
| | SD_MODE | **Open or 3.3V** | Auto left/right mix |
| | VIN | **5V (or VBUS)** | 5V delivers optimal volume |
| | GND | **GND** | Common Ground |
| **SSD1306 OLED (I2C)**| SDA | **GPIO 8** | I2C Data |
| | SCL | **GPIO 9** | I2C Clock |
| | VCC | **3.3V** | Power |
| | GND | **GND** | Common Ground |
| **Pause Button** | Button Pin | **GPIO 10** | Safe non-strapping pin (internal pull-up enabled, active LOW) |
| | Other Terminal | **GND** | Common Ground |

> [!IMPORTANT]
> **Do not connect any external button to GPIO 0!** GPIO 0 is a strapping pin that forces the ESP32-S3 into ROM Bootloader / Download mode (`boot:0x0 waiting for download`) if held LOW at startup. Connect your push button between **GPIO 10** and **GND**.

---

## 2. Configuration Setup

Before compiling, configure your local Wi-Fi credentials and laptop IP in [main/config.h](file:///home/pranjal/thinko/firmware/esp_idf_buddy/main/config.h):

```c
// Wi-Fi Network Credentials
#define CONFIG_WIFI_SSID            "YOUR_WIFI_SSID"
#define CONFIG_WIFI_PASSWORD        "YOUR_WIFI_PASSWORD"

// Python WebSocket Coordinator Server (Your Laptop's IP on local Wi-Fi)
#define CONFIG_LAPTOP_IP            "192.168.1.100"
#define CONFIG_WS_PORT              8765
```

> [!NOTE]
> Make sure both your laptop and your ESP32-S3 are connected to the same 2.4 GHz Wi-Fi router or mobile hotspot. To find your laptop's IP address on Linux, run `hostname -I`.

---

## 3. How to Build & Flash with ESP-IDF

### Step 1: Export ESP-IDF Environment
Open your terminal and activate the ESP-IDF environment:
```bash
. /home/pranjal/.espressif/v6.1/esp-idf/export.sh
```

### Step 2: Navigate to Firmware Directory
```bash
cd /home/pranjal/thinko/firmware/esp_idf_buddy
```

### Step 3: Set Target (One-Time)
```bash
idf.py set-target esp32s3
```

### Step 4: Build Firmware
```bash
idf.py build
```

### Step 5: Flash and Monitor
Connect your ESP32-S3 to your laptop via USB, find the serial port (typically `/dev/ttyACM0` or `/dev/ttyUSB0`), and run:
```bash
idf.py -p /dev/ttyACM0 flash monitor
```
*(To exit the serial monitor, press `Ctrl + ]`)*

---

## 4. Running the Laptop Coordinator

Start the Python backend coordinator on your laptop:
```bash
cd /home/pranjal/thinko
python main_live.py
```

Once running:
1. The ESP32-S3 boots and displays **WIFI CONNECT** on the OLED.
2. It connects to your Wi-Fi and shows **SERVER CONNECT**.
3. It connects to the laptop WebSocket on port `8765` and enters **READY** mode.
4. Speak your question or math/chemistry problem. Lil-Vro will guide you with Socratic questions in Roman-script Hinglish!
5. Press the button once at any time to **PAUSE** Lil-Vro, and press again to **RESUME**.
