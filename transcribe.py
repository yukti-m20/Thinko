"""
transcribe.py — Sam's module

Live mic -> RealtimeSTT (faster-whisper, open source) -> clean one-line transcript.
No interim partials — fires only on complete utterances detected by VAD (silero).

Install: pip install RealtimeSTT
"""

import os
import logging
import warnings

# Suppress HuggingFace and ctranslate2 noise
os.environ["HF_HUB_DISABLE_IMPLICIT_TOKEN"] = "1"
os.environ["CT2_VERBOSE"] = "0"
logging.getLogger("huggingface_hub").setLevel(logging.ERROR)
warnings.filterwarnings("ignore")

from RealtimeSTT import AudioToTextRecorder


def on_transcript(text: str):
    print(f"\r> {text}          ")


if __name__ == "__main__":
    print("Loading Whisper model (first run downloads ~150MB)...")

    recorder = AudioToTextRecorder(
        model="tiny.en",
        language="en",
        compute_type="float32",   # explicit — avoids ctranslate2 float16 warning on Mac
        silero_sensitivity=0.4,
        post_speech_silence_duration=1.0,
        on_realtime_transcription_stabilized=lambda t: print(f"\r  {t}          ", end="", flush=True),
    )

    print("Listening... speak into your microphone. Press Ctrl+C to stop.\n")

    try:
        while True:
            recorder.text(on_transcript)
    except KeyboardInterrupt:
        print("\nStopped.")
        recorder.stop()
