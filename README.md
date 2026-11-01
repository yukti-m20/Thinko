# Thinko  🤖💡
### *The Open-Source, Screen-Free AI STEM Study Buddy & Voice Tutor*

[![License](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](LICENSE)
[![Python Version](https://img.shields.io/badge/Python-3.10%2B-blue.svg)](https://python.org)
[![Next.js](https://img.shields.io/badge/Next.js-15-black.svg)](https://nextjs.org)
[![Hardware](https://img.shields.io/badge/Hardware-ESP32--S3-red.svg)](https://www.espressif.com/)
[![Gemini Live](https://img.shields.io/badge/Gemini-Live%20API-orange.svg)](https://ai.google.dev/)

---

## 🌟 Overview

**Thinko** (featuring the **Desk Buddy** persona) is a screen-free, voice-first physical study buddy and conversational STEM tutor built for students aged **8 to 14** (Grades 5–7).

Unlike traditional chat apps that encourage passive screen addiction or simply hand out homework answers, Thinko operates as an interactive physical companion powered by an **ESP32-S3**. It guides students through math, science, and reasoning problems using **Socratic dialogue**, encouraging active discovery, resilience, and genuine conceptual mastery.

Thinko supports natural, conversational **Hinglish** (fluid blend of Hindi and English written in Latin script) as well as standard English, keeping all core STEM terms internationally standardized.
![BreatheSafe Device](Thinko%20image.jpeg)

---

## ✨ Key Features

- 🎙️ **Real-Time Full-Duplex Voice**:
  - Direct integration with Google's **Gemini Live API** (`gemini-2.5-flash-native-audio-latest`) for ultra-low latency, natural voice interruptions, and 24 kHz studio-quality conversational audio.
  - Optional offline/hybrid pipeline powered by **RealtimeSTT (Faster-Whisper)**, local utterance gating, and **Deepgram Aura TTS**.
- 📟 **Screen-Free Physical Companion**:
  - Runs on an **ESP32-S3** microcontroller with an I2S digital microphone (**INMP441**), I2S DAC class-D amplifier (**MAX98357A**), tactile push button, and an OLED mini-display (**SSD1306 / SH1106**) for live formula rendering.
- 📐 **STEM Formula & Symbol Normalization**:
  - Real-time normalization of complex mathematical notation and chemical equations (`chem_normalizer.py`, `math_renderer.py`, `stem_normalizer.py`), translating formulas into clean speech-friendly phonetics and crisp OLED screen lines.
- 🧠 **Socratic Learning Modes**:
  - **Walkthrough Mode**: Breaks down multi-step problems step-by-step without spoiling answers.
  - **Teach-Back Mode**: Prompts the student to explain the concept back in their own words to verify mastery.
  - **Quiz Mode**: Rapid concept checks and interactive practice problems.
- 🛡️ **Child Safety & Local Distress Guardrails**:
  - Built-in local safety filter (`agent.py`, `content_filter.py`) that intercepts distress or crisis keywords locally before sending any audio to external cloud LLMs, providing immediate empathetic reassurance and encouraging guidance towards trusted adults.
- 📊 **Parent & Educator Dashboard**:
  - Full-stack web dashboard built with **Next.js 15**, **Tailwind CSS**, and **Supabase**, allowing parents to review session duration, concepts mastered, mood trends, and areas needing support.

---

## 🏗️ System Architecture

```
                 +-------------------------------------------------+
                 |                ESP32-S3 BUDDY                   |
                 |                                                 |
                 |   [INMP441 Mic]              [MAX98357A Speaker]|
                 |      (16 kHz)                     (24 kHz)      |
                 |            \                     /              |
                 |         [OLED Screen]     [Tactile Button]      |
                 +-------------------+-----------------------------+
                                     |  Wi-Fi (WebSockets / LAN)
                                     v  ws://<HOST_IP>:8765
                 +-------------------------------------------------+
                 |            THINKO PYTHON COORDINATOR            |
                 |                                                 |
                 |  +-------------------------------------------+  |
                 |  | WebSocket Bridge (websocket_bridge.py)    |  |
                 |  +---------------------+---------------------+  |
                 |                        |                        |
                 |  +---------------------v---------------------+  |
                 |  | Live Session Coordinator (main_live.py)   |  |
                 |  +----+------------------+-------------------+  |
                 |       |                  |                      |
                 |  +----v----+        +----v----+   +----------+  |
                 |  | Safety  |        |  STEM   |   | Mastery  |  |
                 |  | Filter  |        | Normal- |   | & Mood   |  |
                 |  | & Guard |        | izers   |   | Tracker  |  |
                 |  +----+----+        +----+----+   +----+-----+  |
                 +-------|------------------|-------------|--------+
                         |                  |             |
           +-------------v------+           |        +----v----+
           |  Gemini Live API   |           |        | Supabase|
           | (Bidirectional PCM)|           |        | (Session|
           +--------------------+           |        |  Store) |
                                            |        +----+----+
                                            |             |
                                            |        +----v----+
                                            +------->| Parent  |
                                                     | Dash-   |
                                                     | board   |
                                                     +---------+
```

---

## 🔌 Hardware Setup (ESP32-S3)

### Bill of Materials (BOM)

| Component | Description | Interface |
|---|---|---|
| **ESP32-S3** | ESP32-S3-WROOM-1 / DevKitC-1 with PSRAM | Microcontroller |
| **INMP441** | Omnidirectional Digital Microphone | I2S RX (16 kHz, 16-bit) |
| **MAX98357A** | Mono Class-D Audio Amplifier Module | I2S TX (24 kHz, 16-bit) |
| **SSD1306 / SH1106** | 128x64 Monochrome OLED Display | I2C (Wire) |
| **Push Button** | Tactile Switch (Pause / Mode Switch) | GPIO (Pull-up) |
| **Speaker** | 4Ω 3W or 8Ω 2W Mini Speaker | Analog Audio |

### Pinout Mapping

```
ESP32-S3 Pin          Component & Function
------------------------------------------------------
GPIO 4                INMP441 SCK  (I2S Serial Clock)
GPIO 5                INMP441 WS   (I2S Word Select)
GPIO 6                INMP441 SD   (I2S Serial Data In)
GPIO 7                MAX98357A BCLK (I2S Bit Clock)
GPIO 8                MAX98357A LRC  (I2S Word Select)
GPIO 9                MAX98357A DIN  (I2S Data Out)
GPIO 1                I2C SDA (OLED Display)
GPIO 2                I2C SCL (OLED Display)
GPIO 0                Tactile Push Button (Pause/Reset)
3.3V / GND            Power Rails
```

---

## 📁 Repository Structure

```
thinko/
├── agent.py                 # Core conversational logic, prompt engineering & safety
├── content_filter.py        # Student safety & content moderation rules
├── contracts.py             # Data models and interfaces
├── main.py                  # Standalone PC audio pipeline (STT -> LLM -> TTS)
├── main_live.py             # Real-time Gemini Live & ESP32-S3 coordinator
├── live_audio_handler.py    # Bidirectional PCM audio stream management
├── live_session_manager.py  # Session lifecycle & event dispatching
├── websocket_bridge.py      # Low-latency WebSocket server for hardware client
├── stem_normalizer.py       # LaTeX & technical notation spoken converter
├── chem_normalizer.py       # Chemical formula phonetic generator
├── math_renderer.py         # Visual & phonetic formatting for mathematical terms
├── mood_tracker.py          # Session sentiment and frustration tracking
├── mastery.py               # Topic proficiency and curriculum progression
├── session_store.py         # Supabase database integration
├── run_thinko.bat           # One-click Windows launch script
├── requirements.txt         # Python dependencies
├── .env.example             # Template for API keys and configuration
│
├── firmware/                # ESP32-S3 Hardware Client
│   ├── platformio.ini       # PlatformIO build configuration
│   ├── src/main.cpp         # ESP-IDF / Arduino C++ firmware
│   ├── thinko_buddy_s3.ino  # Arduino IDE sketch
│   └── README.md            # Hardware flashing instructions
│
├── dashboard/               # Parent & Educator Web Application
│   ├── src/                 # Next.js 15 application source code
│   ├── package.json         # Dashboard dependencies
│   ├── .env.local.example   # Dashboard environment template
│   └── README.md            # Dashboard deployment guide
│
└── supabase/                # Database Migrations & Schemas
    ├── config.toml          # Local Supabase CLI configuration
    ├── seed.sql             # Demo seed data
    └── migrations/          # PostgreSQL schema migrations
```

---

## 🚀 Quick Start Guide

### 1. Prerequisites

- **Python**: 3.10 or higher
- **Node.js**: v18.0+ & npm (for Parent Dashboard)
- **C++ / PlatformIO or Arduino IDE** (if building physical hardware)
- **API Keys**:
  - [Google Gemini API Key](https://aistudio.google.com/) (Required for Gemini Live)
  - [Deepgram API Key](https://console.deepgram.com/) (Optional: for standalone `main.py`)
  - [OpenAI API Key](https://platform.openai.com/) (Optional: fallback LLM)

---

### 2. Python Coordinator Setup

1. **Clone the repository**:
   ```bash
   git clone https://github.com/your-username/thinko.git
   cd thinko
   ```

2. **Create and activate a virtual environment**:
   ```bash
   python -m venv .venv
   # Windows:
   .venv\Scripts\activate
   # macOS/Linux:
   source .venv/bin/activate
   ```

3. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

4. **Configure environment variables**:
   ```bash
   cp .env.example .env
   ```
   Open `.env` in your editor and provide your keys:
   ```ini
   # Required for Gemini Live
   GEMINI_API_KEY=your_gemini_api_key_here
   GEMINI_LIVE_MODEL=gemini-2.5-flash-native-audio-latest

   # Optional: For traditional pipeline
   DEEPGRAM_API_KEY=your_deepgram_api_key_here
   DEEPGRAM_VOICE=aura-2-thalia-en
   OPENAI_API_KEY=your_openai_api_key_here

   # Optional: Supabase persistence
   # SUPABASE_URL=http://127.0.0.1:54321
   # SUPABASE_SERVICE_ROLE_KEY=your_supabase_key
   ```

5. **Start the Coordinator**:
   - On Windows: double-click `run_thinko.bat` or run:
     ```bash
     python main_live.py
     ```
   - For standalone PC microphone/speaker testing (without hardware):
     ```bash
     python main.py
     ```

---

### 3. ESP32-S3 Firmware Setup

1. Open `firmware/` in **PlatformIO** (VS Code) or open `thinko_buddy_s3.ino` in **Arduino IDE**.
2. Update your Wi-Fi credentials and your host machine's local IP address:
   ```cpp
   const char* WIFI_SSID     = "Your_WiFi_SSID";
   const char* WIFI_PASSWORD = "Your_WiFi_Password";
   const char* WS_HOST       = "192.168.1.100"; // IP address of Python host
   const int   WS_PORT       = 8765;
   ```
3. Connect your ESP32-S3 board via USB.
4. Build and upload the firmware. The OLED display will show `Connecting to WiFi...` and switch to `READY` when connected to your Python coordinator.

---

### 4. Parent Dashboard Setup

1. Navigate to the dashboard directory:
   ```bash
   cd dashboard
   npm install
   ```
2. Set up environment variables:
   ```bash
   cp .env.local.example .env.local
   ```
3. Start the local development server:
   ```bash
   npm run dev
   ```
4. Open [http://localhost:3000](http://localhost:3000) in your browser.
   - Demo Credentials: `parent@thinko.local` / `password123`

---

## 🛡️ Safety & Privacy Guardrails

Thinko is engineered with strict child safety principles:
- **No Autonomous Problem Spoiling**: Guides students towards the solution without completing assignments on their behalf.
- **Local Crisis Interceptor**: Mentions of self-harm or severe distress trigger an immediate compassionate pause with guidance to consult trusted adults.
- **Privacy-Conscious Data Handling**: Audio streams are processed in memory and not retained permanently on edge devices.
- **Parental Visibility**: The dashboard offers parents transparent insight into topics explored and emotional sentiment during study sessions.

---

## 🤝 Contributing

Contributions to Thinko are warmly welcomed! Whether you want to improve prompt engineering, add new STEM curriculum modules, enhance ESP32 hardware capabilities, or polish the parent dashboard:

1. Fork the Project.
2. Create your Feature Branch (`git checkout -b feature/AmazingFeature`).
3. Commit your Changes (`git commit -m 'Add some AmazingFeature'`).
4. Push to the Branch (`git push origin feature/AmazingFeature`).
5. Open a Pull Request.

---

## 📄 License

This project is licensed under the **Apache License 2.0**. See the [LICENSE](LICENSE) file for complete terms and copyright notices.

```
Copyright 2026 Thinko Contributors

Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at

    http://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.
```
