"""
live_session_manager.py — Gemini Live API Session Manager for Thinko

Handles bidirectional streaming connection to the Gemini Multimodal Live API.
Configures Class 5–7 STEM tutor persona and learning modes.
Provides callbacks for:
  - Audio output chunks (24 kHz 16-bit PCM)
  - Spoken text transcripts
  - Voice interruption (barge-in) events
  - Turn completion
"""

from __future__ import annotations

import asyncio
import logging
import os
import time
from typing import AsyncGenerator, Callable, Optional

from dotenv import load_dotenv
from google import genai
from google.genai import types

from tutor_prompt_builder import build_tutor_prompt

load_dotenv()
logger = logging.getLogger("thinko.live")

# Confirmed working models in priority order
DEFAULT_MODELS = [
    os.getenv("GEMINI_LIVE_MODEL", "gemini-2.5-flash-native-audio-latest"),
    "gemini-2.5-flash-native-audio-latest",
    "gemini-3.8-live",
    "gemini-3.1-flash-live-preview",
]


class LiveSessionManager:
    """
    Manages a stateful Gemini Live session over WebSockets.
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        mode: str = "walkthrough",
        model: Optional[str] = None,
        voice_name: str = "Puck",
        on_audio_chunk: Optional[Callable[[bytes, int], None]] = None,
        on_transcript: Optional[Callable[[str, bool], None]] = None,
        on_interrupted: Optional[Callable[[int], None]] = None,
        on_turn_complete: Optional[Callable[[int], None]] = None,
    ):
        self.api_key = api_key or os.getenv("GEMINI_API_KEY")
        if not self.api_key:
            raise ValueError("GEMINI_API_KEY is required to start a Live session.")

        self.mode = mode
        self.preferred_model = model or DEFAULT_MODELS[0]
        self.voice_name = voice_name
        self.active_model: Optional[str] = None

        # Callbacks
        self.on_audio_chunk = on_audio_chunk or (lambda chunk, r_id: None)
        self.on_transcript = on_transcript or (lambda text, final: None)
        self.on_interrupted = on_interrupted or (lambda r_id: None)
        self.on_turn_complete = on_turn_complete or (lambda r_id: None)

        self.client = genai.Client(api_key=self.api_key)
        self._session = None
        self._receive_task: Optional[asyncio.Task] = None
        self._running = False
        self._current_response_id = 1

        # Latency metrics
        self._turn_start_time: float = 0.0
        self._first_audio_received: bool = False
        self.time_to_first_audio: Optional[float] = None

    @property
    def is_connected(self) -> bool:
        return self._session is not None and self._running

    @property
    def current_response_id(self) -> int:
        return self._current_response_id

    def set_mode(self, new_mode: str) -> None:
        """Update active mode (walkthrough, teach_back, quiz)."""
        self.mode = new_mode

    async def connect(self) -> str:
        """
        Establish the Gemini Live session using the confirmed working model.
        """
        system_instruction = build_tutor_prompt(self.mode)
        config = types.LiveConnectConfig(
            response_modalities=["AUDIO"],
            speech_config=types.SpeechConfig(
                voice_config=types.VoiceConfig(
                    prebuilt_voice_config=types.PrebuiltVoiceConfig(voice_name=self.voice_name)
                )
            ),
            thinking_config=types.ThinkingConfig(thinking_budget=0),
            system_instruction=types.Content(
                parts=[types.Part.from_text(text=system_instruction)]
            ),
            output_audio_transcription=types.AudioTranscriptionConfig(),
        )

        candidates = [self.preferred_model] + [m for m in DEFAULT_MODELS if m != self.preferred_model]
        last_error = None

        for model_id in candidates:
            try:
                logger.info(f"Connecting to Gemini Live with model: {model_id}...")
                session_cm = self.client.aio.live.connect(model=model_id, config=config)
                self._session = await session_cm.__aenter__()
                self._session_cm = session_cm
                self.active_model = model_id
                self._running = True
                logger.info(f"Successfully connected to Gemini Live ({model_id})!")

                # Start the background receive loop
                self._receive_task = asyncio.create_task(self._receive_loop())
                return model_id
            except Exception as e:
                logger.warning(f"Connection attempt for {model_id} failed: {e}")
                last_error = e

        raise RuntimeError(f"Failed to connect to any Gemini Live model: {last_error}")

    async def send_audio_chunk(self, pcm_bytes: bytes) -> None:
        """
        Send a raw 16 kHz 16-bit mono PCM chunk to Gemini.
        """
        if not self.is_connected or not self._session:
            return
        if self._turn_start_time == 0.0:
            self._turn_start_time = time.monotonic()
            self._first_audio_received = False

        blob = types.Blob(data=pcm_bytes, mime_type="audio/pcm;rate=16000")
        try:
            await self._session.send_realtime_input(audio=blob)
        except Exception as e:
            logger.error(f"Error sending audio chunk: {e}")

    async def end_audio_stream(self) -> None:
        """
        Signals that user finished speaking by sending silence padding.
        Prompts Gemini's server-side VAD without closing or killing the live audio channel.
        """
        if not self.is_connected or not self._session:
            return
        # 200 ms of clean silence PCM (16 kHz 16-bit mono)
        silent_pcm = b"\x00\x00" * 3200
        blob = types.Blob(data=silent_pcm, mime_type="audio/pcm;rate=16000")
        try:
            await self._session.send_realtime_input(audio=blob)
        except Exception as e:
            logger.error(f"Error sending silence boundary: {e}")

    async def send_text_prompt(self, text: str) -> None:
        """
        Send a text turn to Gemini Live via the realtime channel.
        """
        if not self.is_connected or not self._session:
            return
        self._turn_start_time = time.monotonic()
        self._first_audio_received = False
        try:
            await self._session.send_realtime_input(text=text)
        except Exception:
            content = types.Content(
                role="user",
                parts=[types.Part.from_text(text=text)],
            )
            await self._session.send_client_content(turns=[content], turn_complete=True)

    async def _receive_loop(self) -> None:
        """
        Continuous loop listening for incoming audio chunks, transcripts,
        interruption notices, and turn completions from Gemini across ALL turns.
        """
        try:
            while self._running and self._session:
                async for response in self._session.receive():
                    if not self._running:
                        break

                    server_content = response.server_content
                    if server_content is None:
                        continue

                    # 1. Voice Interruption Detection (Student spoke over Thinko)
                    if server_content.interrupted:
                        logger.info(f"Server signaled interruption for response #{self._current_response_id}")
                        old_id = self._current_response_id
                        self._current_response_id += 1
                        self.on_interrupted(old_id)
                        continue

                    # 2. Spoken Text Transcript (from output_transcription)
                    out_trans = getattr(server_content, "output_transcription", None)
                    if out_trans and getattr(out_trans, "text", None):
                        self.on_transcript(out_trans.text, False)

                    # 3. Model Turn (Audio chunks)
                    model_turn = getattr(server_content, "model_turn", None)
                    if model_turn is not None:
                        for part in model_turn.parts:
                            # Fallback for plain text if output_transcription is absent
                            if not out_trans and part.text and not getattr(part, "thought", False):
                                self.on_transcript(part.text, False)

                            # Output audio chunk (24 kHz 16-bit mono PCM)
                            if part.inline_data and part.inline_data.data:
                                if not self._first_audio_received:
                                    self._first_audio_received = True
                                    if self._turn_start_time > 0.0:
                                        self.time_to_first_audio = time.monotonic() - self._turn_start_time
                                        logger.info(f"Time to first audio: {self.time_to_first_audio * 1000:.1f} ms")

                                self.on_audio_chunk(part.inline_data.data, self._current_response_id)

                    # 4. Turn Complete
                    if getattr(server_content, "turn_complete", False):
                        self.on_turn_complete(self._current_response_id)
                        self._turn_start_time = 0.0
                        self._current_response_id += 1

        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.error(f"Error in Gemini Live receive loop: {e}")
        finally:
            self._running = False

    async def close(self) -> None:
        """Cleanly close the session."""
        self._running = False
        if self._receive_task:
            self._receive_task.cancel()
            try:
                await self._receive_task
            except asyncio.CancelledError:
                pass
        if hasattr(self, "_session_cm") and self._session_cm:
            try:
                await self._session_cm.__aexit__(None, None, None)
            except Exception:
                pass
        self._session = None
