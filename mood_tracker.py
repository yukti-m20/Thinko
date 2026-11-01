"""
mood_tracker.py — Detect student mood from utterances and track session statistics.

    classify_mood(text) → "frustrated" | "confused" | "confident" | "disengaged" | "neutral"

SessionStats tracks mood history and engagement across a session.
The current_mood property feeds directly into agent.py's respond() mood parameter.
"""

from __future__ import annotations

import re
import time
from collections import Counter
from dataclasses import dataclass, field
from typing import Literal

Mood = Literal["frustrated", "confused", "confident", "disengaged", "neutral"]

# Patterns per mood — longer/more specific phrases listed first so they win ties.
_PATTERNS: list[tuple[Mood, list[str]]] = [
    ("frustrated", [
        "i give up", "i can't do this", "this is stupid", "this is too hard",
        "i hate this", "i don't get it at all", "this makes no sense",
        "why is this so hard", "i'm bad at this", "forget it",
        "ugh", "argh", "this is annoying", "i quit", "i don't get it",
        "i still don't understand", "nothing makes sense",
    ]),
    ("confused", [
        "i don't understand", "i'm confused", "what do you mean",
        "i'm lost", "i have no idea", "i don't know what",
        "can you explain", "how does that work", "i'm not sure what",
        "i don't follow", "i'm not sure", "what?", "huh?",
    ]),
    ("confident", [
        "i know this", "i got it", "that makes sense", "i figured it out",
        "makes sense now", "i see", "i understand", "i think i know",
        "easy", "obviously", "got it", "that's right",
    ]),
    ("disengaged", [
        "yeah yeah", "whatever", "i guess", "sure", "fine", "okay okay",
    ]),
]

# Compile to regex patterns, longest phrase first within each mood
_COMPILED: list[tuple[Mood, re.Pattern]] = []
for _mood, _phrases in _PATTERNS:
    for _phrase in sorted(_phrases, key=len, reverse=True):
        _COMPILED.append((_mood, re.compile(rf"\b{re.escape(_phrase)}\b", re.IGNORECASE)))


def classify_mood(text: str) -> Mood:
    """
    Classify the mood signal in a single utterance.
    Returns the first (most-specific) match, or "neutral".
    """
    for mood, pattern in _COMPILED:
        if pattern.search(text):
            return mood
    # Very short single-word replies with no positive signal → disengaged
    words = text.strip().split()
    if len(words) == 1 and words[0].lower() in {"ok", "okay", "mhm", "yeah", "yep", "nope", "no"}:
        return "disengaged"
    return "neutral"


@dataclass
class SessionStats:
    """
    Tracks mood and engagement statistics for one session.

    Usage:
        stats = SessionStats()
        mood = stats.update(student_utterance)   # call each turn
        respond(..., mood=stats.current_mood)     # feed into agent
        print(stats.summary())                   # at session end
    """

    start_time: float = field(default_factory=time.monotonic)
    utterance_count: int = 0
    mood_history: list[Mood] = field(default_factory=list)
    mood_counts: Counter = field(default_factory=Counter)
    _window: int = 5  # rolling window size for current_mood

    def update(self, text: str) -> Mood:
        """Feed a student utterance. Returns the mood detected for this turn."""
        mood = classify_mood(text)
        self.utterance_count += 1
        self.mood_history.append(mood)
        self.mood_counts[mood] += 1
        return mood

    @property
    def current_mood(self) -> Mood:
        """
        Mood trend over the last _window utterances.
        Returns the most common non-neutral mood, or "neutral" if none.
        """
        recent = self.mood_history[-self._window:]
        counts = Counter(recent)
        counts.pop("neutral", None)
        if not counts:
            return "neutral"
        return counts.most_common(1)[0][0]

    @property
    def elapsed_seconds(self) -> float:
        return time.monotonic() - self.start_time

    def summary(self) -> dict:
        dominant = self.mood_counts.most_common(1)[0][0] if self.mood_counts else "neutral"
        return {
            "utterances": self.utterance_count,
            "elapsed_min": round(self.elapsed_seconds / 60, 1),
            "mood_counts": dict(self.mood_counts),
            "current_mood": self.current_mood,
            "dominant_mood": dominant,
        }


if __name__ == "__main__":
    cases = [
        ("I give up, this makes no sense", "frustrated"),
        ("I don't understand what you mean", "confused"),
        ("Oh I got it! That makes sense now", "confident"),
        ("ok", "disengaged"),
        ("What is the derivative of x squared?", "neutral"),
        ("ugh this is so annoying", "frustrated"),
        ("I figured it out!", "confident"),
    ]
    print("=== classify_mood tests ===")
    for text, expected in cases:
        result = classify_mood(text)
        status = "PASS" if result == expected else "FAIL"
        print(f"  [{status}] {text!r} → {result!r}  (expected {expected!r})")

    print("\n=== SessionStats rolling mood ===")
    stats = SessionStats()
    utterances = [
        "What is this?",
        "I don't understand",
        "I'm confused",
        "ugh I give up",
        "I got it!",
    ]
    for u in utterances:
        mood = stats.update(u)
        print(f"  turn mood={mood!r}  current={stats.current_mood!r}")
    print("\n  Summary:", stats.summary())
