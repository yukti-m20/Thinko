"""
main_live.py — Real-time Gemini Live & ESP32-S3 Voice Tutor Coordinator

Orchestrates:
  - Gemini Live bidirectional voice session (24 kHz out / 16 kHz in)
  - ESP32-S3 WebSocket bridge for INMP441 mic, MAX98357A speaker, OLED, and pause button
  - Socratic STEM guidance for Classes 5–7
  - Learning mode selection (walkthrough, teach_back, quiz)
  - Supabase persistence (optional)
"""

from __future__ import annotations

import asyncio
import logging
import os
import signal
import sys
import time
from dotenv import load_dotenv

from live_audio_handler import LiveAudioHandler
from live_session_manager import LiveSessionManager
from session_store import SessionStore
from websocket_bridge import WebSocketBridge

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("thinko.main")

WS_PORT = int(os.getenv("WS_PORT", "8765"))
store = SessionStore()


async def main():
    print("=" * 65)
    print("  Thinko — Gemini Live & ESP32-S3 Real-Time STEM Tutor")
    print("  Screen-free physical companion for Classes 5 to 7")
    print("=" * 65)

    mode = "walkthrough"
    print(f"Default Mode: {mode.upper()} (Socratic step-by-step guidance)")
    print(f"ESP32 Wi-Fi Gateway: ws://0.0.0.0:{WS_PORT}")
    if store.enabled:
        print(f"Parent Dashboard: Enabled (Child: {store.child_id[:8]}…)")
    else:
        print("Parent Dashboard: Off (Set SUPABASE_URL to persist sessions)")
    print("-" * 65)

    audio_handler = LiveAudioHandler()

    def on_transcript(text: str, final: bool):
        # Print transcript token stream in real time
        print(text, end="", flush=True)

    session_mgr = LiveSessionManager(
        mode=mode,
        on_transcript=on_transcript,
    )

    bridge = WebSocketBridge(
        session_manager=session_mgr,
        audio_handler=audio_handler,
        port=WS_PORT,
    )

    print("Connecting to Gemini Live API...")
    try:
        active_model = await session_mgr.connect()
        print(f"Connected to Gemini Live engine ({active_model})!")
    except Exception as e:
        logger.error(f"Failed to connect to Gemini Live: {e}")
        print("\nPlease verify your GEMINI_API_KEY in .env and check internet connectivity.")
        return

    await bridge.start()
    bridge.set_state("ready")

    print("\nThinko is READY!")
    print(" - Turn on your ESP32-S3 Buddy to start speaking.")
    print(" - Press 'p' + Enter in terminal to toggle pause.")
    print(" - Press 'm' + Enter to switch mode (walkthrough / teach_back / quiz).")
    print(" - Press Ctrl+C to stop.\n")

    loop = asyncio.get_running_loop()
    stop_event = asyncio.Event()

    def handle_signal():
        stop_event.set()

    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, handle_signal)
        except NotImplementedError:
            pass

    async def console_listener():
        reader = asyncio.StreamReader()
        protocol = asyncio.StreamReaderProtocol(reader)
        await loop.connect_read_pipe(lambda: protocol, sys.stdin)
        while not stop_event.is_set():
            line = await reader.readline()
            if not line:
                break
            cmd = line.decode().strip().lower()
            if cmd == "p":
                if audio_handler.is_paused:
                    audio_handler.resume_playback()
                    bridge.set_state("ready")
                    print("\n[RESUMED]")
                else:
                    audio_handler.pause_playback()
                    bridge.set_state("paused")
                    print("\n[PAUSED — press p to resume]")
            elif cmd == "m":
                nonlocal mode
                modes = ["walkthrough", "teach_back", "quiz"]
                cur_idx = modes.index(mode) if mode in modes else 0
                mode = modes[(cur_idx + 1) % len(modes)]
                session_mgr.set_mode(mode)
                bridge.broadcast_json({"type": "mode", "value": mode})
                print(f"\n[Switched to {mode.upper()} mode]")
            elif cmd in ("q", "quit", "exit"):
                stop_event.set()
                break

    console_task = asyncio.create_task(console_listener())

    try:
        await stop_event.wait()
    except asyncio.CancelledError:
        pass
    finally:
        print("\nShutting down Lil-Vro...")
        console_task.cancel()
        bridge.set_state("paused")
        await bridge.stop()
        await session_mgr.close()
        if store.enabled:
            store.end_session()
        print("Goodbye!")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        pass
