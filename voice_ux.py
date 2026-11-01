"""Voice / conversation UX for Thinko.

Handles barge-in, repeat/rephrase, wake phrases, bookmarks, STT confidence,
speaking-distance profiles, noise robustness knobs, hardware turn-taking cues,
pickable peer personas, bilingual hooks, and soft thinking fillers.

Designed to run *before* STEM tool routing so kids can control the conversation
instantly without an extra LLM call.
"""

from __future__ import annotations

import random
import re
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


# --------------------------------------------------------------------------- #
#  Enums & contracts
# --------------------------------------------------------------------------- #


class VoiceIntent(str, Enum):
    NONE = "none"
    BARGE_IN = "barge_in"  # wait / hold on
    GO_BACK = "go_back"  # previous turn / bookmark
    REPEAT = "repeat"
    REPEAT_SLOWER = "repeat_slower"
    SAY_ANOTHER_WAY = "say_another_way"
    PAUSE = "pause"
    RESUME = "resume"
    BOOKMARK = "bookmark"
    RECALL_BOOKMARK = "recall_bookmark"
    SWITCH_PERSONA = "switch_persona"
    SWITCH_LANGUAGE = "switch_language"
    SET_DISTANCE = "set_distance"
    UNCERTAIN_REASK = "uncertain_reask"


class SpeakDistance(str, Enum):
    """Mic gain / VAD profile for how close the kid is to the device."""

    WHISPER = "whisper"  # close, quiet
    NORMAL = "normal"
    ROOM = "room"  # farther / group


class LanguageCode(str, Enum):
    EN = "en"
    ES = "es"  # Spanish/STEM bilingual path
    BILINGUAL = "bilingual"  # mix: teach STEM terms in both


class HardwareCue(str, Enum):
    LISTENING = "listening"
    THINKING = "thinking"
    SPEAKING = "speaking"
    BARGE_IN = "barge_in"
    PAUSED = "paused"
    BOOKMARK = "bookmark"
    ERROR = "error"
    CELEBRATE = "celebrate"


class PeerVoice(str, Enum):
    """Pickable peer personas — still classmates, never creepy adults."""

    SPARK = "spark"  # curious, upbeat
    CALM = "calm"  # steady, gentle
    WITTY = "witty"  # playful science jokes, light
    COACH = "coach"  # hype-but-kind teammate


# --------------------------------------------------------------------------- #
#  Profiles: Whisper / STT / noise / distance
# --------------------------------------------------------------------------- #


@dataclass(slots=True)
class SttProfile:
    """Settings consumed by Whisper / Deepgram / device audio front-ends."""

    language: LanguageCode = LanguageCode.EN
    distance: SpeakDistance = SpeakDistance.NORMAL
    kid_speech: bool = True
    noise_robust: bool = True
    sample_rate: int = 16000
    channels: int = 1
    # Confidence below this triggers a polite re-ask.
    min_confidence: float = 0.55
    # Interim results help barge-in feel instant.
    interim_results: bool = True

    def whisper_options(self) -> dict[str, Any]:
        """Options aimed at faster-whisper / whisper.cpp style front-ends."""
        # Kid speech: slightly more aggressive VAD, beam for clarity.
        beam = 5 if self.kid_speech else 3
        # Whisper distance → energy threshold / initial prompt hints.
        vad_threshold = {
            SpeakDistance.WHISPER: 0.35,
            SpeakDistance.NORMAL: 0.5,
            SpeakDistance.ROOM: 0.65,
        }[self.distance]
        initial_prompt = (
            "A child is studying math and science out loud. "
            "Expect words like fraction, derivative, molecule, equals, squared."
        )
        if self.language in {LanguageCode.ES, LanguageCode.BILINGUAL}:
            initial_prompt += (
                " The child may mix English and Spanish STEM words."
            )
        return {
            "language": "es" if self.language == LanguageCode.ES else "en",
            "beam_size": beam,
            "vad_filter": True,
            "vad_threshold": vad_threshold,
            "condition_on_previous_text": True,
            "initial_prompt": initial_prompt,
            "temperature": 0.0,
            "word_timestamps": False,
        }

    def deepgram_options(self) -> dict[str, Any]:
        """Options for streaming STT (Deepgram-style)."""
        model = "nova-3"
        language = {
            LanguageCode.EN: "en-US",
            LanguageCode.ES: "es",
            LanguageCode.BILINGUAL: "en-US",  # primary; bilingual handled in UX
        }[self.language]
        # Closer speech → lower endpointing delay feels better for barge-in.
        endpointing_ms = {
            SpeakDistance.WHISPER: 200,
            SpeakDistance.NORMAL: 300,
            SpeakDistance.ROOM: 450,
        }[self.distance]
        opts: dict[str, Any] = {
            "model": model,
            "language": language,
            "encoding": "linear16",
            "sample_rate": self.sample_rate,
            "channels": self.channels,
            "interim_results": self.interim_results,
            "punctuate": True,
            "smart_format": True,
            "endpointing": endpointing_ms,
        }
        if self.noise_robust:
            opts["filler_words"] = False
            opts["utterance_end_ms"] = 1000 if self.distance != SpeakDistance.ROOM else 1400
        if self.kid_speech:
            # Bias keywords help kid STEM speech; providers that support keyterms
            # can consume this list.
            opts["keywords"] = [
                "fraction",
                "denominator",
                "numerator",
                "derivative",
                "integral",
                "molecule",
                "equals",
                "squared",
                "thinko",
            ]
        return opts

    def input_gain(self) -> float:
        """Suggested digital gain multiplier for the capture path."""
        return {
            SpeakDistance.WHISPER: 2.2,
            SpeakDistance.NORMAL: 1.0,
            SpeakDistance.ROOM: 1.6,
        }[self.distance]


# --------------------------------------------------------------------------- #
#  Hardware turn-taking cues (phone / ESP32)
# --------------------------------------------------------------------------- #


@dataclass(slots=True)
class HardwareSignal:
    cue: HardwareCue
    led_rgb: tuple[int, int, int]
    beep_hz: int | None
    beep_ms: int
    note: str


_HARDWARE: dict[HardwareCue, HardwareSignal] = {
    HardwareCue.LISTENING: HardwareSignal(
        HardwareCue.LISTENING, (40, 180, 255), 880, 40, "soft ready chirp"
    ),
    HardwareCue.THINKING: HardwareSignal(
        HardwareCue.THINKING, (180, 120, 255), None, 0, "pulse while planning"
    ),
    HardwareCue.SPEAKING: HardwareSignal(
        HardwareCue.SPEAKING, (80, 220, 120), None, 0, "steady speak light"
    ),
    HardwareCue.BARGE_IN: HardwareSignal(
        HardwareCue.BARGE_IN, (255, 200, 40), 660, 60, "ack interruption"
    ),
    HardwareCue.PAUSED: HardwareSignal(
        HardwareCue.PAUSED, (120, 120, 120), 440, 80, "pause"
    ),
    HardwareCue.BOOKMARK: HardwareSignal(
        HardwareCue.BOOKMARK, (255, 160, 60), 990, 50, "bookmark saved"
    ),
    HardwareCue.ERROR: HardwareSignal(
        HardwareCue.ERROR, (255, 60, 60), 220, 120, "error"
    ),
    HardwareCue.CELEBRATE: HardwareSignal(
        HardwareCue.CELEBRATE, (255, 215, 0), 1320, 70, "tiny win"
    ),
}


def hardware_signal(cue: HardwareCue) -> HardwareSignal:
    return _HARDWARE[cue]


def hardware_payload(cue: HardwareCue) -> dict[str, Any]:
    """JSON-serializable cue for ESP32 / phone bridges."""
    signal = hardware_signal(cue)
    return {
        "cue": signal.cue.value,
        "led_rgb": list(signal.led_rgb),
        "beep_hz": signal.beep_hz,
        "beep_ms": signal.beep_ms,
        "note": signal.note,
    }


# --------------------------------------------------------------------------- #
#  Peer voice personas
# --------------------------------------------------------------------------- #


@dataclass(slots=True)
class VoicePersona:
    voice: PeerVoice
    display_name: str
    vibe: str
    prompt_flavor: str
    tts_style_hint: str  # for Aura / ElevenLabs style tags later


_PERSONAS: dict[PeerVoice, VoicePersona] = {
    PeerVoice.SPARK: VoicePersona(
        PeerVoice.SPARK,
        "Spark",
        "curious and upbeat classmate",
        "Sound curious and a little excited about STEM ideas. Keep it peer-like.",
        "bright, mid tempo",
    ),
    PeerVoice.CALM: VoicePersona(
        PeerVoice.CALM,
        "Calm",
        "steady gentle study buddy",
        "Sound calm, patient, and steady. Never rush the kid.",
        "soft, slower tempo",
    ),
    PeerVoice.WITTY: VoicePersona(
        PeerVoice.WITTY,
        "Witty",
        "playful science-loving peer",
        "Light playful energy and tiny science wordplay are OK if short. Never mean.",
        "lively, clear",
    ),
    PeerVoice.COACH: VoicePersona(
        PeerVoice.COACH,
        "Coach",
        "kind hype teammate",
        "Sound like a supportive teammate. Celebrate effort, then the next tiny step.",
        "warm, energetic",
    ),
}


def list_personas() -> list[VoicePersona]:
    return list(_PERSONAS.values())


def get_persona(voice: PeerVoice | str) -> VoicePersona:
    if isinstance(voice, str):
        voice = PeerVoice(voice.lower())
    return _PERSONAS[voice]


# --------------------------------------------------------------------------- #
#  Bookmarks
# --------------------------------------------------------------------------- #


@dataclass
class Bookmark:
    label: str
    text: str
    topic: str | None = None
    created_at: float = field(default_factory=time.time)

    def snapshot(self) -> dict[str, object]:
        return {
            "label": self.label,
            "text": self.text,
            "topic": self.topic,
            "created_at": self.created_at,
        }


@dataclass
class BookmarkStore:
    items: list[Bookmark] = field(default_factory=list)

    def add(self, label: str, text: str, topic: str | None = None) -> Bookmark:
        label = _clean_label(label) or _auto_label(text, topic)
        mark = Bookmark(label=label, text=text.strip(), topic=topic)
        # Replace same label.
        self.items = [item for item in self.items if item.label != mark.label]
        self.items.append(mark)
        if len(self.items) > 20:
            self.items = self.items[-20:]
        return mark

    def find(self, query: str) -> Bookmark | None:
        q = query.lower().strip()
        if not q:
            return self.items[-1] if self.items else None
        for item in reversed(self.items):
            if q in item.label.lower() or (item.topic and q in item.topic.lower()):
                return item
            if q in item.text.lower():
                return item
        # Fuzzy token overlap
        tokens = [token for token in re.split(r"\W+", q) if token]
        best: Bookmark | None = None
        best_score = 0
        for item in self.items:
            hay = f"{item.label} {item.topic or ''} {item.text}".lower()
            score = sum(1 for token in tokens if token in hay)
            if score > best_score:
                best, best_score = item, score
        return best if best_score else None

    def snapshot(self) -> list[dict[str, object]]:
        return [item.snapshot() for item in self.items]


def _clean_label(label: str) -> str:
    return re.sub(r"\s+", " ", label.strip().lower())[:40]


def _auto_label(text: str, topic: str | None) -> str:
    if topic:
        return topic.lower()[:40]
    words = [word for word in re.split(r"\W+", text.lower()) if len(word) > 3]
    return " ".join(words[:3]) or "moment"


# --------------------------------------------------------------------------- #
#  Thinking fillers
# --------------------------------------------------------------------------- #


_FILLERS_EN = (
    "Okay, one sec…",
    "Hmm, let me think…",
    "Alright, working on it…",
    "Got it — thinking…",
    "Okay okay…",
)

_FILLERS_ES = (
    "Okay, un segundo…",
    "Hmm, déjame pensar…",
    "Va, lo estoy pensando…",
    "Ya — pensando…",
)


def thinking_filler(language: LanguageCode = LanguageCode.EN) -> str:
    if language == LanguageCode.ES:
        return random.choice(_FILLERS_ES)
    if language == LanguageCode.BILINGUAL:
        return random.choice(_FILLERS_EN + _FILLERS_ES)
    return random.choice(_FILLERS_EN)


# --------------------------------------------------------------------------- #
#  Delivery transforms: slower / another way
# --------------------------------------------------------------------------- #


def speak_slower(text: str) -> str:
    """Insert gentle pacing for TTS without sounding robotic."""
    text = text.strip()
    if not text:
        return text
    # Split into short clauses; TTS engines pause on ellipses / commas.
    parts = re.split(r"(?<=[.!?])\s+", text)
    paced: list[str] = []
    for part in parts:
        part = part.strip()
        if not part:
            continue
        # Add a soft beat after commas already present; otherwise lightly chunk.
        if "," in part or len(part.split()) <= 8:
            paced.append(part)
        else:
            words = part.split()
            chunks = [" ".join(words[i : i + 6]) for i in range(0, len(words), 6)]
            paced.append("… ".join(chunks))
    joined = " … ".join(paced)
    return f"Okay — slower this time. {joined}"


def say_another_way(text: str) -> str:
    """Local rephrase scaffold when we can't afford another model call."""
    text = text.strip()
    if not text:
        return text
    simplified = text
    replacements = (
        (r"\btherefore\b", "so"),
        (r"\bhowever\b", "but"),
        (r"\bapproximately\b", "about"),
        (r"\butilize\b", "use"),
        (r"\bdemonstrate\b", "show"),
        (r"\bcalculate\b", "figure out"),
        (r"\bconsequently\b", "so then"),
    )
    for pattern, repl in replacements:
        simplified = re.sub(pattern, repl, simplified, flags=re.I)
    return f"Another way to say it: {simplified}"


# --------------------------------------------------------------------------- #
#  Intent detection (wake phrases + conversation controls)
# --------------------------------------------------------------------------- #


_BARGE = re.compile(
    r"\b("
    r"wait|hold\s*on|hang\s*on|stop\s*talking|pause\s*for\s*a\s*sec|"
    r"one\s*sec|one\s*second|shh+|quiet"
    r")\b",
    re.I,
)
_GO_BACK = re.compile(
    r"\b("
    r"go\s*back|previous|the\s*last\s*(one|part|step)|"
    r"what\s*did\s*you\s*(just\s*)?say|say\s*that\s*again\s*from\s*before|"
    r"back\s*up"
    r")\b",
    re.I,
)
_REPEAT_SLOWER = re.compile(
    r"\b("
    r"repeat\s*that\s*slower|say\s*that\s*slower|slower\s*please|"
    r"slow\s*down|too\s*fast"
    r")\b",
    re.I,
)
_REPEAT = re.compile(
    r"\b("
    r"repeat\s*that|say\s*that\s*again|one\s*more\s*time|come\s*again"
    r")\b",
    re.I,
)
_ANOTHER_WAY = re.compile(
    r"\b("
    r"say\s*it\s*another\s*way|another\s*way|rephrase|"
    r"explain\s*(it\s*)?differently|in\s*simpler\s*words|"
    r"i\s*didn'?t\s*get\s*(that|what\s*you\s*meant)"
    r")\b",
    re.I,
)
_PAUSE = re.compile(
    r"\b("
    r"(thinko|lilvro)\s*,?\s*pause|pause(\s*please)?|take\s*a\s*break|"
    r"mute|be\s*quiet\s*for\s*a\s*(minute|sec|second)"
    r")\b",
    re.I,
)
_RESUME = re.compile(
    r"\b("
    r"(thinko|lilvro)\s*,?\s*(resume|continue|unpause)|"
    r"i'?m\s*back|continue|keep\s*going|resume"
    r")\b",
    re.I,
)
_BOOKMARK = re.compile(
    r"\b("
    r"(bookmark|save|pin)\s*(this|that|here)?|"
    r"remember\s*this\s*part|"
    r"(thinko|lilvro)\s*,?\s*bookmark"
    r")\b",
    re.I,
)
_RECALL = re.compile(
    r"\b("
    r"go\s*back\s*to\s+(?P<label>.+)$|"
    r"jump\s*to\s+(?P<label2>.+)$|"
    r"what\s*about\s+the\s+(?P<label3>.+?)\s+part$|"
    r"bookmark\s+(?P<label4>.+)$"
    r")",
    re.I,
)
_PERSONA = re.compile(
    r"\b("
    r"(be|switch\s*to|use)\s*(spark|calm|witty|coach)|"
    r"persona\s*(spark|calm|witty|coach)|"
    r"talk\s*like\s*(spark|calm|witty|coach)"
    r")\b",
    re.I,
)
_LANGUAGE = re.compile(
    r"\b("
    r"(speak|talk)\s*(in\s*)?spanish|en\s*espa[nñ]ol|"
    r"(speak|talk)\s*(in\s*)?english|"
    r"bilingual(\s*mode)?|mix\s*(english|spanish)"
    r")\b",
    re.I,
)
_DISTANCE = re.compile(
    r"\b("
    r"i'?m\s*whispering|whisper\s*mode|"
    r"normal\s*(mic|distance|mode)|"
    r"i'?m\s*farther|room\s*mode|louder\s*mic"
    r")\b",
    re.I,
)


@dataclass(slots=True)
class DetectedIntent:
    intent: VoiceIntent
    label: str | None = None
    persona: PeerVoice | None = None
    language: LanguageCode | None = None
    distance: SpeakDistance | None = None
    confidence: float = 1.0


def detect_voice_intent(text: str) -> DetectedIntent:
    lower = text.strip().lower()
    if not lower:
        return DetectedIntent(VoiceIntent.NONE)

    if _PAUSE.search(lower) and not _RESUME.search(lower):
        return DetectedIntent(VoiceIntent.PAUSE, confidence=0.95)
    if _RESUME.search(lower):
        return DetectedIntent(VoiceIntent.RESUME, confidence=0.95)

    persona_match = _PERSONA.search(lower)
    if persona_match:
        raw = persona_match.group(0)
        for name in PeerVoice:
            if name.value in raw:
                return DetectedIntent(
                    VoiceIntent.SWITCH_PERSONA, persona=name, confidence=0.95
                )

    if _LANGUAGE.search(lower):
        if "spanish" in lower or "español" in lower or "espanol" in lower:
            lang = LanguageCode.ES
        elif "bilingual" in lower or "mix" in lower:
            lang = LanguageCode.BILINGUAL
        else:
            lang = LanguageCode.EN
        return DetectedIntent(VoiceIntent.SWITCH_LANGUAGE, language=lang, confidence=0.9)

    if _DISTANCE.search(lower):
        if "whisper" in lower:
            dist = SpeakDistance.WHISPER
        elif "room" in lower or "farther" in lower or "louder" in lower:
            dist = SpeakDistance.ROOM
        else:
            dist = SpeakDistance.NORMAL
        return DetectedIntent(VoiceIntent.SET_DISTANCE, distance=dist, confidence=0.9)

    recall = _RECALL.search(lower)
    if recall and ("go back to" in lower or "jump to" in lower or "what about the" in lower):
        label = (
            recall.groupdict().get("label")
            or recall.groupdict().get("label2")
            or recall.groupdict().get("label3")
            or recall.groupdict().get("label4")
            or ""
        )
        label = label.strip(" ?.!")
        # Avoid stealing plain "go back"
        if label and label not in {"that", "it", "this"}:
            return DetectedIntent(VoiceIntent.RECALL_BOOKMARK, label=label, confidence=0.9)

    if _BOOKMARK.search(lower):
        return DetectedIntent(VoiceIntent.BOOKMARK, confidence=0.9)

    if _REPEAT_SLOWER.search(lower):
        return DetectedIntent(VoiceIntent.REPEAT_SLOWER, confidence=0.95)
    if _ANOTHER_WAY.search(lower):
        return DetectedIntent(VoiceIntent.SAY_ANOTHER_WAY, confidence=0.95)
    if _GO_BACK.search(lower):
        return DetectedIntent(VoiceIntent.GO_BACK, confidence=0.9)
    if _BARGE.search(lower):
        return DetectedIntent(VoiceIntent.BARGE_IN, confidence=0.9)
    if _REPEAT.search(lower):
        return DetectedIntent(VoiceIntent.REPEAT, confidence=0.9)

    return DetectedIntent(VoiceIntent.NONE)


# --------------------------------------------------------------------------- #
#  STT confidence gate
# --------------------------------------------------------------------------- #


@dataclass(slots=True)
class TranscriptEvent:
    text: str
    confidence: float = 1.0
    is_final: bool = True
    is_interim: bool = False


def confidence_should_reask(event: TranscriptEvent, profile: SttProfile) -> bool:
    if not event.is_final:
        return False
    if not event.text.strip():
        return True
    return event.confidence < profile.min_confidence


def reask_prompt(language: LanguageCode = LanguageCode.EN) -> str:
    if language == LanguageCode.ES:
        return "No te escuché bien — ¿lo puedes decir otra vez un poquito más claro?"
    if language == LanguageCode.BILINGUAL:
        return "I didn't catch that — ¿lo puedes repetir a bit clearer?"
    return "I didn't quite catch that — can you say it one more time a little clearer?"


# --------------------------------------------------------------------------- #
#  Session UX state + action handler
# --------------------------------------------------------------------------- #


@dataclass(slots=True)
class VoiceUxAction:
    """Result of handling a conversation-control turn."""

    intent: VoiceIntent
    handled: bool
    speak: str | None = None
    stop_tts: bool = False
    resume_agent: bool = True
    hardware: HardwareCue | None = None
    thinking_filler: str | None = None
    updated: dict[str, object] = field(default_factory=dict)


@dataclass
class VoiceUxState:
    """Sticky voice UX memory for a session."""

    stt: SttProfile = field(default_factory=SttProfile)
    persona: PeerVoice = PeerVoice.SPARK
    paused: bool = False
    bookmarks: BookmarkStore = field(default_factory=BookmarkStore)
    last_agent_text: str | None = None
    previous_agent_text: str | None = None
    last_user_text: str | None = None
    recent_agent: list[str] = field(default_factory=list)

    def remember_agent(self, text: str) -> None:
        text = text.strip()
        if not text:
            return
        self.previous_agent_text = self.last_agent_text
        self.last_agent_text = text
        self.recent_agent.append(text)
        if len(self.recent_agent) > 12:
            self.recent_agent = self.recent_agent[-12:]

    def remember_user(self, text: str) -> None:
        self.last_user_text = text.strip()

    def persona_flavor(self) -> str:
        return get_persona(self.persona).prompt_flavor

    def snapshot(self) -> dict[str, object]:
        return {
            "persona": self.persona.value,
            "language": self.stt.language.value,
            "distance": self.stt.distance.value,
            "paused": self.paused,
            "bookmarks": self.bookmarks.snapshot(),
            "kid_speech": self.stt.kid_speech,
            "noise_robust": self.stt.noise_robust,
            "min_confidence": self.stt.min_confidence,
        }


def handle_transcript_confidence(
    state: VoiceUxState, event: TranscriptEvent
) -> VoiceUxAction | None:
    if confidence_should_reask(event, state.stt):
        return VoiceUxAction(
            intent=VoiceIntent.UNCERTAIN_REASK,
            handled=True,
            speak=reask_prompt(state.stt.language),
            resume_agent=False,
            hardware=HardwareCue.ERROR,
        )
    return None


def handle_voice_ux(
    text: str,
    state: VoiceUxState,
    *,
    topic: str | None = None,
) -> VoiceUxAction:
    """Interpret conversation-control speech. Fast, local, no LLM."""
    detected = detect_voice_intent(text)
    intent = detected.intent

    if state.paused and intent not in {VoiceIntent.RESUME, VoiceIntent.PAUSE}:
        return VoiceUxAction(
            intent=VoiceIntent.PAUSE,
            handled=True,
            speak="We're still on pause. Say 'thinko, continue' when you're ready.",
            resume_agent=False,
            hardware=HardwareCue.PAUSED,
        )

    if intent == VoiceIntent.NONE:
        return VoiceUxAction(intent=VoiceIntent.NONE, handled=False, resume_agent=True)

    if intent == VoiceIntent.BARGE_IN:
        return VoiceUxAction(
            intent=intent,
            handled=True,
            speak="Yep — I'm listening.",
            stop_tts=True,
            resume_agent=False,
            hardware=HardwareCue.BARGE_IN,
        )

    if intent == VoiceIntent.PAUSE:
        state.paused = True
        return VoiceUxAction(
            intent=intent,
            handled=True,
            speak="Paused. Say 'thinko, continue' whenever you want.",
            stop_tts=True,
            resume_agent=False,
            hardware=HardwareCue.PAUSED,
            updated={"paused": True},
        )

    if intent == VoiceIntent.RESUME:
        state.paused = False
        return VoiceUxAction(
            intent=intent,
            handled=True,
            speak="Welcome back. Where were we?",
            resume_agent=False,
            hardware=HardwareCue.LISTENING,
            updated={"paused": False},
        )

    if intent == VoiceIntent.REPEAT_SLOWER:
        source = state.last_agent_text or "I don't have something to repeat yet."
        return VoiceUxAction(
            intent=intent,
            handled=True,
            speak=speak_slower(source) if state.last_agent_text else source,
            resume_agent=False,
            hardware=HardwareCue.SPEAKING,
        )

    if intent == VoiceIntent.SAY_ANOTHER_WAY:
        source = state.last_agent_text or "I don't have something to rephrase yet."
        return VoiceUxAction(
            intent=intent,
            handled=True,
            speak=say_another_way(source) if state.last_agent_text else source,
            resume_agent=False,
            hardware=HardwareCue.SPEAKING,
        )

    if intent == VoiceIntent.REPEAT:
        source = state.last_agent_text or "I don't have something to repeat yet."
        return VoiceUxAction(
            intent=intent,
            handled=True,
            speak=source,
            resume_agent=False,
            hardware=HardwareCue.SPEAKING,
        )

    if intent == VoiceIntent.GO_BACK:
        source = state.previous_agent_text or state.last_agent_text
        if not source:
            speak = "We don't have an earlier part saved yet."
        else:
            speak = f"Going back. {source}"
        return VoiceUxAction(
            intent=intent,
            handled=True,
            speak=speak,
            resume_agent=False,
            hardware=HardwareCue.SPEAKING,
        )

    if intent == VoiceIntent.BOOKMARK:
        source = state.last_agent_text or text
        mark = state.bookmarks.add(detected.label or "", source, topic=topic)
        return VoiceUxAction(
            intent=intent,
            handled=True,
            speak=f"Bookmarked as {mark.label}.",
            resume_agent=False,
            hardware=HardwareCue.BOOKMARK,
            updated={"bookmark": mark.snapshot()},
        )

    if intent == VoiceIntent.RECALL_BOOKMARK:
        mark = state.bookmarks.find(detected.label or "")
        if not mark:
            speak = "I couldn't find that bookmark. Try 'bookmark this' first."
        else:
            speak = f"Back to {mark.label}. {mark.text}"
        return VoiceUxAction(
            intent=intent,
            handled=True,
            speak=speak,
            resume_agent=False,
            hardware=HardwareCue.SPEAKING,
        )

    if intent == VoiceIntent.SWITCH_PERSONA and detected.persona:
        state.persona = detected.persona
        persona = get_persona(detected.persona)
        return VoiceUxAction(
            intent=intent,
            handled=True,
            speak=f"Okay — I'll talk more like {persona.display_name}, your {persona.vibe}.",
            resume_agent=False,
            hardware=HardwareCue.CELEBRATE,
            updated={"persona": persona.voice.value},
        )

    if intent == VoiceIntent.SWITCH_LANGUAGE and detected.language:
        state.stt.language = detected.language
        labels = {
            LanguageCode.EN: "English",
            LanguageCode.ES: "Spanish",
            LanguageCode.BILINGUAL: "bilingual English and Spanish",
        }
        return VoiceUxAction(
            intent=intent,
            handled=True,
            speak=f"Got it — switching to {labels[detected.language]}.",
            resume_agent=False,
            hardware=HardwareCue.LISTENING,
            updated={"language": detected.language.value},
        )

    if intent == VoiceIntent.SET_DISTANCE and detected.distance:
        state.stt.distance = detected.distance
        labels = {
            SpeakDistance.WHISPER: "whisper distance",
            SpeakDistance.NORMAL: "normal distance",
            SpeakDistance.ROOM: "room distance",
        }
        return VoiceUxAction(
            intent=intent,
            handled=True,
            speak=f"Mic set to {labels[detected.distance]}.",
            resume_agent=False,
            hardware=HardwareCue.LISTENING,
            updated={
                "distance": detected.distance.value,
                "stt": state.stt.deepgram_options(),
                "gain": state.stt.input_gain(),
            },
        )

    return VoiceUxAction(intent=intent, handled=False, resume_agent=True)


def begin_turn_cues(state: VoiceUxState) -> dict[str, Any]:
    """What the device should do at the start of agent thinking."""
    return {
        "hardware": hardware_payload(HardwareCue.THINKING),
        "filler": thinking_filler(state.stt.language),
        "stop_tts_on_barge_in": True,
    }


def listening_cues(state: VoiceUxState) -> dict[str, Any]:
    return {
        "hardware": hardware_payload(HardwareCue.LISTENING),
        "stt": state.stt.deepgram_options(),
        "whisper": state.stt.whisper_options(),
        "gain": state.stt.input_gain(),
    }


def bilingual_stem_hint(term_en: str, term_es: str) -> str:
    """Tiny helper for later bilingual STEM explanations."""
    return f"{term_en} — in Spanish, {term_es}"


# Common STEM glossary seeds for bilingual mode (expand later).
STEM_GLOSSARY_EN_ES: dict[str, str] = {
    "fraction": "fracción",
    "derivative": "derivada",
    "integral": "integral",
    "molecule": "molécula",
    "force": "fuerza",
    "equals": "igual",
    "squared": "al cuadrado",
    "equation": "ecuación",
}


def enrich_bilingual(text: str, language: LanguageCode) -> str:
    if language != LanguageCode.BILINGUAL:
        return text
    lower = text.lower()
    extras = [
        bilingual_stem_hint(en, es)
        for en, es in STEM_GLOSSARY_EN_ES.items()
        if en in lower
    ]
    if not extras:
        return text
    # Keep it light — at most one gloss tag.
    return f"{text} ({extras[0]})"
