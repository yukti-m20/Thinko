"""
main.py — Full voice conversation loop

Pipeline:
    Mic -> RealtimeSTT -> utterance_gate -> speech_normalizer -> agent
      -> math_renderer -> Deepgram TTS -> Speaker

The agent only replies after the student has finished a real utterance —
not on interim text, fillers, or mid-sentence cuts.
"""

import os
import sys
import select
import asyncio
import json
import threading
import warnings
import logging
import tempfile
import wave
import subprocess
import time
import requests
from dotenv import load_dotenv

if os.name == "nt":
    import msvcrt
else:
    import termios
    import tty

# Suppress model loading noise and OpenMP duplicate runtime conflicts in Anaconda
os.environ["KMP_DUPLICATE_LIB_OK"] = "TRUE"
os.environ["HF_HUB_DISABLE_IMPLICIT_TOKEN"] = "1"
os.environ["CT2_VERBOSE"] = "0"
logging.getLogger("huggingface_hub").setLevel(logging.ERROR)
try:
    from RealtimeSTT import AudioToTextRecorder
except ModuleNotFoundError:
    print("\n" + "=" * 65)
    print("  Notice: 'RealtimeSTT' is not installed in this environment.")
    print("  Launching Lil-Vro Gemini Live Voice Tutor (main_live.py)...")
    print("=" * 65 + "\n")
    import main_live
    asyncio.run(main_live.main())
    sys.exit(0)
from speech_normalizer import normalize
from math_renderer import render_math
from agent import respond, detect_mode
from utterance_gate import GateDecision, UtteranceGate
from speech_styler import style_speech
from session_store import SessionStore
from chem_normalizer import normalize as chem_normalize, render as chem_render
from content_filter import filter_response
from mood_tracker import SessionStats
from problem_counter import ProblemCounter

load_dotenv()

# ------------------------------------------------------------------ #
#  Config
# ------------------------------------------------------------------ #

WS_PORT = int(os.getenv("WS_PORT", "8765"))  # WebSocket bridge port for child UI

DEEPGRAM_API_KEY = os.getenv("DEEPGRAM_API_KEY")
DEEPGRAM_VOICE = os.getenv("DEEPGRAM_VOICE", "aura-2-thalia-en")
TTS_URL = f"https://api.deepgram.com/v1/speak?model={DEEPGRAM_VOICE}&encoding=linear16&sample_rate=24000&channels=1"

# How long after speech stops before we treat the utterance as finished.
POST_SPEECH_SILENCE = 0.6

# Optional parent-dashboard persistence (no-op if env unset).
store = SessionStore()

# ------------------------------------------------------------------ #
#  Feature flags — flip these to enable/disable optional features
# ------------------------------------------------------------------ #

# Noise filter: WebRTC VAD-based noise gate on mic input (0 = off, 1-3 = aggressive)
NOISE_FILTER = True
NOISE_FILTER_LEVEL = 3  # 1 = mild, 2 = moderate, 3 = aggressive

# Echo cancellation: ignore transcripts that arrive while/just after TTS is playing
# so the agent never hears and responds to its own voice.
ECHO_CANCEL = True
ECHO_CANCEL_COOLDOWN = 1.5  # seconds to ignore mic input after TTS finishes

# ------------------------------------------------------------------ #
#  State
# ------------------------------------------------------------------ #

history = []
mode = "walkthrough"
_paused = False
stats = SessionStats()
counter = ProblemCounter()
gate = UtteranceGate(
    settle_seconds=0.1,
    min_chars=2,
    min_words=1,
    reject_trailing_incomplete=False,
)
_busy = False  # True while agent/TTS is running — ignore new triggers
_last_spoken_user = ""
_speaking = False      # True while TTS audio is actively playing
_speak_end_time = 0.0  # monotonic timestamp when last TTS finished
_exiting = False       # Set to True by _end_session() to trigger clean shutdown

# Reference to the active recorder instance for button-triggered early stop
_recorder_instance = None

# WebSocket bridge — child UI connects here for blob animation + emergency stop
_ws_loop: asyncio.AbstractEventLoop | None = None
_ws_clients: set = set()
_ws_transcript: list[dict] = []  # running transcript [{role, content}]


# ------------------------------------------------------------------ #
#  Pause / resume — press P in terminal or say "pause" / "resume"
# ------------------------------------------------------------------ #

# ------------------------------------------------------------------ #
#  WebSocket bridge — state signals for child blob UI
# ------------------------------------------------------------------ #

def trigger_done_speaking():
    """Triggered by spacebar, Enter, or ESP32 Wi-Fi button: finalize speaking immediately."""
    global _recorder_instance
    if _recorder_instance and not _busy and not _speaking:
        print("\n  [>>> Button pressed: finalizing speech & starting reasoning...]")
        try:
            _recorder_instance.stop()
        except Exception as e:
            pass

async def _ws_handler(websocket):
    """Handle a single child browser or ESP32 Wi-Fi connection."""
    _ws_clients.add(websocket)
    print("  [WebSocket] Client connected (ESP32 / Web UI)")
    # Send current state so late-joining client catches up
    try:
        await websocket.send(json.dumps({"type": "state", "value": "idle"}))
        async for raw in websocket:
            try:
                msg = json.loads(raw)
            except json.JSONDecodeError:
                continue
            msg_type = msg.get("type")
            if msg_type == "emergency_stop":
                transcript_text = "\n".join(
                    f"{t['role'].upper()}: {t['content']}" for t in _ws_transcript
                )
                store.record_emergency_stop(transcript_text)
                print("\n  [EMERGENCY STOP triggered from interface]")
            elif msg_type in ("done_speaking", "button_press"):
                trigger_done_speaking()
            elif msg_type == "pause_toggle":
                _toggle_pause()
    except Exception:
        pass
    finally:
        _ws_clients.discard(websocket)


async def _ws_broadcast(msg: dict):
    if _ws_clients:
        data = json.dumps(msg)
        await asyncio.gather(*[c.send(data) for c in set(_ws_clients)], return_exceptions=True)


def ws_broadcast(msg: dict):
    """Thread-safe broadcast from sync code (main voice loop)."""
    if _ws_loop and not _ws_loop.is_closed():
        asyncio.run_coroutine_threadsafe(_ws_broadcast(msg), _ws_loop)


def _start_ws_server():
    """Run the WebSocket server in its own thread + event loop."""
    global _ws_loop
    try:
        import websockets
    except ImportError:
        print("  [WebSocket bridge disabled — pip install websockets to enable]")
        return

    async def _serve():
        global _ws_loop
        _ws_loop = asyncio.get_running_loop()
        async with websockets.serve(_ws_handler, "0.0.0.0", WS_PORT):
            await asyncio.Future()  # run forever

    asyncio.run(_serve())


_BYE_PHRASES = [
    "bye", "goodbye", "good bye", "see you", "see ya", "later",
    "i have to go", "i gotta go", "i got to go", "i need to go",
    "i'm done", "i am done", "that's all", "that is all",
    "i'm leaving", "i am leaving", "got to go now", "gotta go now",
    "talk later", "talk to you later", "ttyl", "have to go now",
    "i'm finished", "i am finished", "end session", "stop session",
]


def _end_session():
    """Say goodbye, print stats, and trigger clean shutdown."""
    global _exiting
    _exiting = True
    psummary = counter.summary()
    msummary = stats.summary()
    subjects_str = (
        "  ".join(f"{s}:{n}" for s, n in psummary["by_subject"].items())
        if psummary["by_subject"] else "none"
    )
    print(
        f"\n  [session ended — {msummary['utterances']} turns, "
        f"{msummary['elapsed_min']} min | "
        f"solved: {psummary['total_solved']} ({subjects_str}) | "
        f"mood: {msummary['dominant_mood']}]"
    )
    farewell = (
        "See you next time! You did good work today."
        if psummary["total_solved"] > 0
        else "See you next time! Keep practising."
    )
    ding()
    speak(farewell)
    store.record_session_stats(
        mood_counts=dict(stats.mood_counts),
        problems_solved=counter.total,
        subjects=counter.by_subject,
        topics_needing_help=[
            s for s, n in counter.by_subject.items() if n == 0
        ],
    )
    store.end_session()
    raise SystemExit(0)


def _toggle_pause():
    global _paused
    _paused = not _paused
    status = "PAUSED  (press p or say 'resume' to continue)" if _paused else "RESUMED"
    print(f"\n  [{status}]          ")
    ws_broadcast({"type": "state", "value": "paused" if _paused else "idle"})


def _keyboard_watcher():
    """Background thread: press 'space' or 'Enter' to finish speaking immediately, 'p' to pause."""
    if os.name == "nt":
        while True:
            ch = msvcrt.getwch()
            if ch in (" ", "\r", "\n", "d"):
                trigger_done_speaking()
            elif ch.lower() == "p":
                _toggle_pause()
            elif ch.lower() == "b":
                _end_session()
            elif ch == "\x03":
                return

    # Open /dev/tty directly so we don't compete with RealtimeSTT's stdin handling.
    try:
        tty_fd = open("/dev/tty", "rb", buffering=0)
    except OSError:
        return  # no controlling terminal — skip keyboard watcher silently

    old = termios.tcgetattr(tty_fd)
    try:
        tty.setcbreak(tty_fd)
        while True:
            # Non-blocking poll — returns immediately if no key pressed
            ready, _, _ = select.select([tty_fd], [], [], 0.05)
            if ready:
                ch = tty_fd.read(1).decode("utf-8", errors="ignore")
                if ch in (" ", "\r", "\n", "d"):
                    trigger_done_speaking()
                elif ch.lower() == "p":
                    _toggle_pause()
                elif ch.lower() == "b":
                    _end_session()
                elif ch == "\x03":
                    raise KeyboardInterrupt
    except Exception:
        pass
    finally:
        termios.tcsetattr(tty_fd, termios.TCSADRAIN, old)
        tty_fd.close()


#  TTS — Deepgram Aura
# ------------------------------------------------------------------ #

_SOUNDS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "sounds")
_DING_WAV = os.path.join(_SOUNDS_DIR, "ding.wav")
_DING_MP3 = os.path.join(_SOUNDS_DIR, "ding.mp3")
_DING = _DING_WAV if (sys.platform == "win32" and os.path.exists(_DING_WAV)) else _DING_MP3

def ding():
    """Play a short chime to signal Thinko is about to speak."""
    try:
        if sys.platform == "win32":
            import winsound
            if os.path.exists(_DING_WAV):
                winsound.PlaySound(_DING_WAV, winsound.SND_FILENAME)
            else:
                winsound.MessageBeep(winsound.MB_ICONASTERISK)
        elif sys.platform == "darwin":
            subprocess.run(["afplay", _DING], check=False)
        else:
            subprocess.run(["aplay", _DING], check=False)
    except Exception:
        pass


def speak(text: str):
    """Send text to Deepgram Aura TTS and play audio through speaker.

    Only called with a complete agent reply — never with partials.
    Sets _speaking while audio plays so the echo-cancel guard can ignore
    any mic transcripts that capture our own output.
    """
    global _speaking, _speak_end_time
    _speaking = True
    ws_broadcast({"type": "state", "value": "agent_speaking"})
    openai_key = os.getenv("OPENAI_API_KEY")
    audio_played = False
    printed_text = False

    def _play_and_display(audio_file):
        nonlocal printed_text
        if not printed_text:
            print(f"\r< {text}          ")
            ws_broadcast({"type": "transcript", "role": "assistant", "content": text})
            _ws_transcript.append({"role": "assistant", "content": text})
            printed_text = True
        if sys.platform == "win32":
            import winsound
            winsound.PlaySound(audio_file, winsound.SND_FILENAME)
        elif sys.platform == "darwin":
            subprocess.run(["afplay", audio_file], check=True)
        else:
            subprocess.run(["aplay", audio_file], check=True)

    try:
        # 1. Try Deepgram Aura TTS if key is configured
        if DEEPGRAM_API_KEY and not DEEPGRAM_API_KEY.startswith("your_"):
            try:
                response = requests.post(
                    TTS_URL,
                    headers={
                        "Authorization": f"Token {DEEPGRAM_API_KEY}",
                        "Content-Type": "application/json",
                    },
                    json={"text": text},
                    timeout=10,
                )
                response.raise_for_status()
                with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
                    tmp = f.name
                    with wave.open(tmp, "wb") as wf:
                        wf.setnchannels(1)
                        wf.setsampwidth(2)
                        wf.setframerate(24000)
                        wf.writeframes(response.content)
                _play_and_display(tmp)
                audio_played = True
            except Exception as e:
                print(f"  [Deepgram TTS error: {e}]")

        # 2. Fallback to OpenAI TTS if Deepgram is unavailable or failed
        if not audio_played and openai_key and not openai_key.startswith("your_"):
            try:
                response = requests.post(
                    "https://api.openai.com/v1/audio/speech",
                    headers={
                        "Authorization": f"Bearer {openai_key}",
                        "Content-Type": "application/json",
                    },
                    json={
                        "model": "tts-1",
                        "input": text,
                        "voice": "nova",
                        "response_format": "wav",
                    },
                    timeout=12,
                )
                response.raise_for_status()
                with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
                    tmp = f.name
                    f.write(response.content)
                _play_and_display(tmp)
                audio_played = True
            except Exception as e:
                print(f"  [OpenAI TTS fallback error: {e}]")

        # 3. Local Windows SAPI fallback if offline/no cloud TTS
        if not audio_played and sys.platform == "win32":
            try:
                if not printed_text:
                    print(f"\r< {text}          ")
                    ws_broadcast({"type": "transcript", "role": "assistant", "content": text})
                    _ws_transcript.append({"role": "assistant", "content": text})
                    printed_text = True
                safe_text = text.replace('"', '""').replace("'", "''")
                cmd = f"Add-Type -AssemblyName System.Speech; (New-Object System.Speech.Synthesis.SpeechSynthesizer).Speak('{safe_text}')"
                subprocess.run(["powershell", "-NoProfile", "-Command", cmd], check=False)
                audio_played = True
            except Exception:
                pass

        if not printed_text:
            print(f"\r< {text}          ")
            ws_broadcast({"type": "transcript", "role": "assistant", "content": text})
            _ws_transcript.append({"role": "assistant", "content": text})
    finally:
        if "tmp" in locals():
            try:
                os.unlink(tmp)
            except OSError:
                pass
        _speaking = False
        _speak_end_time = time.monotonic()
        ws_broadcast({"type": "state", "value": "idle"})


# ------------------------------------------------------------------ #
#  Live partials — display only, never reply
# ------------------------------------------------------------------ #

def _is_self_echo() -> bool:
    """Return True if we should ignore this transcript — agent is speaking or just finished."""
    if not ECHO_CANCEL:
        return False
    if _speaking or _busy:
        return True
    return time.monotonic() - _speak_end_time < ECHO_CANCEL_COOLDOWN


def on_partial(text: str):
    """Realtime stabilized text: show what we heard, do not answer yet."""
    text = (text or "").strip()
    if not text or _busy or _paused or _is_self_echo():
        return
    gate.feed(text, speech_ended=False, is_interim=True)
    print(f"\r  … {text}          ", end="", flush=True)


# ------------------------------------------------------------------ #
#  Finished utterance callback
# ------------------------------------------------------------------ #

def on_transcript(text: str):
    """Called when STT thinks speech ended. Gate may still WAIT/IGNORE."""
    global history, mode, _busy, _last_spoken_user, _paused

    if _busy or _is_self_echo():
        return

    text = (text or "").strip()
    if not text:
        return

    # Voice-activated pause / resume
    lower = text.lower()
    if any(p in lower for p in ["pause learning", "stop listening", "go to sleep"]):
        if not _paused:
            _toggle_pause()
        return
    if any(p in lower for p in ["resume", "wake up", "start listening"]):
        if _paused:
            _toggle_pause()
        return

    # Voice-triggered goodbye
    if any(p in lower for p in _BYE_PHRASES):
        _end_session()
        return

    if _paused:
        print(f"\r  [paused — press p or say 'resume']          ", end="", flush=True)
        return

    result = gate.feed(text, speech_ended=True, is_interim=False)

    # If still settling / trailing-incomplete, poll briefly then re-check.
    if result.decision == GateDecision.WAIT and result.reason in {"settling", "trailing_incomplete"}:
        deadline = time.monotonic() + max(gate.settle_seconds, 0.6)
        while time.monotonic() < deadline:
            time.sleep(0.1)
            result = gate.feed(text, speech_ended=True, is_interim=False)
            if result.decision != GateDecision.WAIT:
                break
        # After wait, if still trailing-incomplete, accept as finished anyway
        # so long pauses don't deadlock the loop.
        if result.decision == GateDecision.WAIT and result.reason == "trailing_incomplete":
            result = gate.force_evaluate(text, accept_incomplete=True)

    if result.decision == GateDecision.IGNORE:
        print(f"\r  (listening)          ", end="", flush=True)
        return

    if result.decision != GateDecision.READY:
        print(f"\r  … {result.text}          ", end="", flush=True)
        return

    final_text = result.text
    if final_text == _last_spoken_user:
        return

    _busy = True
    _last_spoken_user = final_text
    try:
        print(f"\r> {final_text}          ")
        ws_broadcast({"type": "state", "value": "child_speaking"})
        ws_broadcast({"type": "transcript", "role": "user", "content": final_text})
        _ws_transcript.append({"role": "user", "content": final_text})

        new_mode = detect_mode(final_text, mode)
        if new_mode != mode:
            mode = new_mode
            print(f"  [switched to {mode} mode]")

        # Update mood tracker — feeds into agent's teaching tone
        turn_mood = stats.update(final_text)
        current_mood = stats.current_mood
        if turn_mood != "neutral":
            print(f"  [mood: {turn_mood} | session: {current_mood}]")

        # Normalize: spoken math + spoken chemistry → canonical notation for LLM
        normalized = chem_normalize(normalize(final_text))

        # Think quietly — do not speak until the full reply exists.
        print("  (thinking)", end="", flush=True)
        ws_broadcast({"type": "state", "value": "agent_thinking"})
        try:
            response_text, history = respond(normalized, history, mode=mode, mood=current_mood)
        except Exception as e:
            print(f"\r  [agent error: {e}]")
            return

        if not (response_text or "").strip():
            print("\r  [empty agent reply — staying quiet]")
            return

        # Content guardrails — block age-inappropriate output before it reaches TTS
        response_text, was_blocked = filter_response(response_text)
        if was_blocked:
            print("  [content filter triggered]")

        # Render: math notation + chemistry notation → speakable English
        speakable = style_speech(chem_render(render_math(response_text))).strip()
        if not speakable:
            print("\r  [nothing to speak]")
            return

        # Problem counter — check if agent just confirmed a correct answer
        solved_subject = counter.check_and_record(final_text, response_text)

        store.record_turn(role="user", content=final_text, mode=mode)
        store.record_turn(role="assistant", content=speakable, mode=mode)
        ding()
        speak(speakable)
        if solved_subject:
            summary = counter.by_subject
            subjects_str = "  ".join(f"{s}:{n}" for s, n in summary.items())
            print(f"  [solved #{counter.total} — {solved_subject} | session: {subjects_str}]")
    finally:
        _busy = False
        gate.reset()


# ------------------------------------------------------------------ #
#  Entry point
# ------------------------------------------------------------------ #

if __name__ == "__main__":
    print("Thinko — voice STEM agent")
    print("Mode: walkthrough  |  Say 'quiz mode' / 'teach back' / 'help me' to switch")
    print("Pause: press p  or say 'pause learning' / 'resume'")
    print("End:   press b  or say 'bye' / 'I have to go'")
    print("I only answer after you finish speaking.")
    if store.enabled:
        print(f"Session store: on (child {store.child_id[:8]}…)")
    else:
        print("Session store: off (set SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY, CHILD_ID)")
    print("Press Ctrl+C to quit\n")
    print("Push-to-Talk / Fast-trigger: press Spacebar or Enter when done speaking\n")

    threading.Thread(target=_keyboard_watcher, daemon=True).start()
    threading.Thread(target=_start_ws_server, daemon=True, name="ws-bridge").start()
    print(f"ESP32 Wi-Fi / Child UI server: ws://0.0.0.0:{WS_PORT}")

    recorder = AudioToTextRecorder(
        model="tiny.en",
        language="en",
        compute_type="float32",
        silero_sensitivity=0.4,
        silero_deactivity_detection=True,
        early_transcription_on_silence=0.2,
        webrtc_sensitivity=NOISE_FILTER_LEVEL if NOISE_FILTER else 0,
        post_speech_silence_duration=POST_SPEECH_SILENCE,
        # Partials for the UI only — never trigger the agent.
        on_realtime_transcription_stabilized=on_partial,
    )
    _recorder_instance = recorder

    try:
        while True:
            # recorder.text blocks until a silence-delimited utterance.
            recorder.text(on_transcript)
    except (KeyboardInterrupt, SystemExit):
        if not _exiting:  # Ctrl+C path — _end_session() already handles the other path
            summary = stats.summary()
            psummary = counter.summary()
            subjects_str = (
                "  ".join(f"{s}:{n}" for s, n in psummary["by_subject"].items())
                if psummary["by_subject"] else "none"
            )
            print(f"\nGoodbye!  Session: {summary['utterances']} turns, "
                  f"{summary['elapsed_min']} min, "
                  f"dominant mood: {summary['dominant_mood']} | "
                  f"problems solved: {psummary['total_solved']} ({subjects_str})")
            store.record_session_stats(
                mood_counts=dict(stats.mood_counts),
                problems_solved=counter.total,
                subjects=counter.by_subject,
                topics_needing_help=[
                    s for s, n in counter.by_subject.items() if n == 0
                ],
            )
            store.end_session()
        recorder.stop()
