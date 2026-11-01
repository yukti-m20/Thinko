"""
websocket_bridge.py — WebSocket server bridging the ESP32-S3 and Gemini Live.

Handles:
  - Binary frames (ESP32 -> Python: 16 kHz PCM; Python -> ESP32: 24 kHz PCM)
  - JSON control messages (device_state, button events, status, captions, response_id)
  - Hardware pause/resume button handling:
      * Pause stops speaker output, preserves buffer, and gates mic.
      * Resume continues playback right where left off.
  - Interruption handling:
      * Sends {"type": "audio_cancel", "response_id": id} to tell ESP32 to drop DMA buffers.
"""

from __future__ import annotations

import asyncio
import audioop
import json
import logging
import time
from typing import Callable, Optional, Set

import websockets
from websockets.server import WebSocketServerProtocol

from live_audio_handler import LiveAudioHandler
from live_session_manager import LiveSessionManager
from stem_normalizer import normalize_stem

logger = logging.getLogger("thinko.bridge")


class WebSocketBridge:
    """
    WebSocket server for communication between ESP32-S3 buddy and Python Gemini Live engine.
    """

    def __init__(
        self,
        session_manager: LiveSessionManager,
        audio_handler: LiveAudioHandler,
        port: int = 8765,
        host: str = "0.0.0.0",
        on_mode_change: Optional[Callable[[str], None]] = None,
    ):
        self.session_manager = session_manager
        self.audio_handler = audio_handler
        self.port = port
        self.host = host
        self.on_mode_change = on_mode_change or (lambda m: None)

        self._connected_clients: Set[WebSocketServerProtocol] = set()
        self._server = None
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._current_state = "ready"

        # Volume control: scale output PCM to 35% so neither ESP32 nor laptop blasts
        self.speaker_volume: float = 0.35

        # Hardware VAD tracking with balanced sensitivity (in the middle between too sensitive and hard to trigger)
        self._is_speaking_turn = False
        self._speech_started_time = 0.0
        self._last_voice_time = 0.0
        self._ambient_samples: list[int] = []
        self._voice_start_threshold: int = 3100
        self._voice_stop_threshold: int = 2300
        self.silence_timeout_sec: float = 1.0
        self.min_speech_duration_sec: float = 0.5
        self.max_speech_duration_sec: float = 8.0
        self._watchdog_task: Optional[asyncio.Task] = None

        # Wire audio handler output to websocket broadcast
        self.audio_handler.on_send_output_chunk = self._on_audio_chunk_ready
        self.audio_handler.on_state_change = self.set_state

        # Wire session manager events
        self.session_manager.on_audio_chunk = self._on_gemini_audio
        self.session_manager.on_transcript = self._on_gemini_transcript
        self.session_manager.on_interrupted = self._on_gemini_interrupted
        self.session_manager.on_turn_complete = self._on_gemini_turn_complete

    def _start_thinking_watchdog(self) -> None:
        """Start watchdog to ensure we never get stuck in THINKING state."""
        if self._watchdog_task and not self._watchdog_task.done():
            self._watchdog_task.cancel()
        self._watchdog_task = asyncio.create_task(self._thinking_watchdog())

    async def _thinking_watchdog(self) -> None:
        """If Gemini doesn't produce audio within 5.5s, auto-recover to LISTENING."""
        try:
            await asyncio.sleep(5.5)
            if self._current_state == "thinking":
                logger.warning("⏳ [Thinking Watchdog (5.5s)] No audio from Gemini Live -> Auto-recovering to LISTENING")
                self._is_speaking_turn = False
                self.set_state("listening")
        except asyncio.CancelledError:
            pass

    def _on_gemini_audio(self, chunk: bytes, response_id: int) -> None:
        """Forward Gemini Live audio chunk to both the audio handler queue (ESP32) and laptop speakers."""
        if self._watchdog_task and not self._watchdog_task.done():
            self._watchdog_task.cancel()

        if chunk and self.speaker_volume != 1.0:
            try:
                chunk = audioop.mul(chunk, 2, self.speaker_volume)
            except Exception:
                pass
        self.audio_handler.handle_incoming_audio_chunk(chunk, response_id)

    def _on_gemini_transcript(self, text: str, final: bool) -> None:
        """Format transcript with STEM normalizer and send caption to ESP32."""
        norm = normalize_stem(text)
        caption_payload = {
            "type": "caption",
            "text": norm.raw,
            "stem_text": norm.oled,
            "has_stem": norm.has_stem,
        }
        self.broadcast_json(caption_payload)

    def _on_gemini_interrupted(self, old_response_id: int) -> None:
        """Handle server-side voice interruption."""
        if self._watchdog_task and not self._watchdog_task.done():
            self._watchdog_task.cancel()

        new_response_id = self.audio_handler.handle_voice_interruption(old_response_id)
        # Send audio_cancel to ESP32 so it instantly flushes its local I2S buffer
        cancel_msg = {
            "type": "audio_cancel",
            "response_id": old_response_id,
            "new_response_id": new_response_id,
        }
        self.broadcast_json(cancel_msg)
        self.set_state("listening")

    def _on_gemini_turn_complete(self, response_id: int) -> None:
        """Notify ESP32 that current audio stream generation has finished."""
        if self._watchdog_task and not self._watchdog_task.done():
            self._watchdog_task.cancel()

        self.broadcast_json({"type": "audio_end", "response_id": response_id})
        # If output audio queue is already empty, revert back to listening immediately
        if not self.audio_handler.is_playing:
            self.set_state("listening")

    def _on_audio_chunk_ready(self, chunk: bytes, response_id: int) -> None:
        """Send 24 kHz binary PCM chunk to ESP32."""
        if not self._connected_clients:
            return
        asyncio.create_task(self._broadcast_binary(chunk))

    def set_state(self, new_state: str) -> None:
        """Broadcast state updates to OLED and dashboard."""
        self._current_state = new_state
        self.broadcast_json({"type": "status", "state": new_state})

    def broadcast_json(self, data: dict) -> None:
        """Broadcast JSON message to all connected clients."""
        if not self._connected_clients:
            return
        msg = json.dumps(data)
        for client in list(self._connected_clients):
            asyncio.create_task(self._safe_send_text(client, msg))

    async def _broadcast_binary(self, data: bytes) -> None:
        """Broadcast binary audio chunk to all connected clients."""
        for client in list(self._connected_clients):
            await self._safe_send_binary(client, data)

    async def _safe_send_text(self, ws: WebSocketServerProtocol, msg: str) -> None:
        try:
            await ws.send(msg)
        except Exception:
            pass

    async def _safe_send_binary(self, ws: WebSocketServerProtocol, data: bytes) -> None:
        try:
            await ws.send(data)
        except Exception:
            pass

    async def _handle_connection(self, websocket: WebSocketServerProtocol) -> None:
        """Handle a single ESP32 or Dashboard connection."""
        self._connected_clients.add(websocket)
        logger.info(f"ESP32 Buddy connected: {websocket.remote_address}")

        # Reset connection state & ambient samples for clean turn tracking
        self._ambient_samples.clear()
        self._is_speaking_turn = False
        if self._watchdog_task and not self._watchdog_task.done():
            self._watchdog_task.cancel()
        self.set_state("listening")

        try:
            async for message in websocket:
                # 1. Binary frames: Audio chunk from INMP441 microphone (16 kHz PCM)
                if isinstance(message, bytes):
                    # Strict Half-Duplex: ONLY stream mic when speaker is not playing, not paused, and state is listening/ready
                    if not self.audio_handler.is_paused and not self.audio_handler.is_playing and self._current_state in ("listening", "ready"):
                        try:
                            rms = audioop.rms(message, 2)
                        except Exception:
                            rms = 0

                        # Dynamic calibration: measure initial 25 chunks (~0.8s) to determine baseline
                        if len(self._ambient_samples) < 25:
                            self._ambient_samples.append(rms)
                            if len(self._ambient_samples) == 25:
                                # Use 20th percentile to avoid skew if speech occurred during boot
                                sorted_samples = sorted(self._ambient_samples)
                                ambient = sorted_samples[5]
                                self._voice_start_threshold = max(3000, int(ambient * 1.50))
                                self._voice_stop_threshold = max(2300, int(ambient * 1.20))
                                logger.info(
                                    f"🎤 [Mic Calibrated] Ambient: {ambient} RMS | "
                                    f"Start Threshold: {self._voice_start_threshold} RMS | "
                                    f"Stop Threshold: {self._voice_stop_threshold} RMS"
                                )
                            await self.session_manager.send_audio_chunk(message)
                            continue

                        await self.session_manager.send_audio_chunk(message)

                        now = time.monotonic()
                        if rms >= self._voice_start_threshold:
                            if not self._is_speaking_turn:
                                self._is_speaking_turn = True
                                self._speech_started_time = now
                                logger.info(f"🎙 Student started speaking (RMS: {rms})")
                            self._last_voice_time = now
                        elif self._is_speaking_turn:
                            total_speech_so_far = now - self._speech_started_time

                            # Hysteresis: keep speaking alive if voice is above stop_threshold and under max cap
                            if rms >= self._voice_stop_threshold and total_speech_so_far < self.max_speech_duration_sec:
                                self._last_voice_time = now
                            else:
                                silence_dur = now - self._last_voice_time
                                speech_dur = self._last_voice_time - self._speech_started_time

                                # Natural silence detected (1.0s) or hit max speech duration cap (8.0s)
                                if (silence_dur >= self.silence_timeout_sec and speech_dur >= self.min_speech_duration_sec) or total_speech_so_far >= self.max_speech_duration_sec:
                                    self._is_speaking_turn = False
                                    logger.info(
                                        f"⏳ Silence detected ({silence_dur:.1f}s after {speech_dur:.1f}s speech) "
                                        "-> Sending to Gemini Live (Thinking...)"
                                    )
                                    self.set_state("thinking")
                                    await self.session_manager.end_audio_stream()
                                    self._start_thinking_watchdog()
                    continue

                # 2. Text / JSON messages: Control events
                try:
                    payload = json.loads(message)
                except json.JSONDecodeError:
                    continue

                msg_type = payload.get("type")

                # Pause button events from ESP32
                if msg_type == "button":
                    action = payload.get("action")
                    if action == "pause":
                        self.audio_handler.pause_playback()
                        self.set_state("paused")
                    elif action == "resume":
                        self.audio_handler.resume_playback()
                        self.set_state("listening")
                    elif action == "ready":
                        self.audio_handler.resume_playback()
                        self.set_state("ready")

                elif msg_type == "pause_toggle":
                    if self.audio_handler.is_paused:
                        self.audio_handler.resume_playback()
                        self.set_state("listening")
                    else:
                        self.audio_handler.pause_playback()
                        self.set_state("paused")

                elif msg_type == "mode_change":
                    new_mode = payload.get("mode")
                    if new_mode:
                        self.session_manager.set_mode(new_mode)
                        self.on_mode_change(new_mode)
                        self.broadcast_json({"type": "mode", "value": new_mode})
                        logger.info(f"Switched learning mode to: {new_mode}")

                elif msg_type == "device_state":
                    logger.info(f"ESP32 reported state: {payload.get('state')}")

        except websockets.exceptions.ConnectionClosed:
            pass
        finally:
            self._connected_clients.discard(websocket)
            logger.info("ESP32 Buddy disconnected.")

    async def start(self) -> None:
        """Start the WebSocket server."""
        self._loop = asyncio.get_running_loop()
        self.audio_handler.start()
        self._server = await websockets.serve(self._handle_connection, self.host, self.port)
        logger.info(f"Thinko ESP32 WebSocket bridge listening on ws://{self.host}:{self.port}")

    async def stop(self) -> None:
        """Stop the WebSocket server."""
        self.audio_handler.stop()
        if self._server:
            self._server.close()
            await self._server.wait_closed()
