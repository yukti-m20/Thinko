"""Utterance gate — only release text once the student has finished speaking.

Prevents the agent from jumping on interim STT, filler noise, or mid-sentence cuts.
"""

from __future__ import annotations

import re
import time
from dataclasses import dataclass, field
from enum import Enum


class GateDecision(str, Enum):
    WAIT = "wait"  # still listening / incomplete
    READY = "ready"  # finished utterance — agent may reply
    IGNORE = "ignore"  # noise/filler — do not reply, keep listening


@dataclass
class GateResult:
    decision: GateDecision
    text: str = ""
    reason: str = ""


# Pure fillers / hesitation — never trigger an agent reply on their own.
_FILLER_ONLY = re.compile(
    r"^(um+|uh+|erm+|hmm+|hm+|ah+|oh+|mm+|mmm+|like|so|and|the|yeah|yep|ok|okay|right)?[.!?]*$",
    re.I,
)

# Trailing words that usually mean the thought is not finished yet.
_TRAILING_INCOMPLETE = re.compile(
    r"\b(and|or|but|so|because|then|like|with|to|for|of|the|a|an|if|when|while|that|which)\s*$",
    re.I,
)


@dataclass
class UtteranceGate:
    """Buffer STT chunks and open only when speech has truly ended.

    Typical RealtimeSTT / Deepgram wiring:
      - feed interim/stabilized text with speech_ended=False
      - feed final text with speech_ended=True (after silence)
    """

    # How long text must stay unchanged after a final before we commit (seconds).
    settle_seconds: float = 0.45
    # Minimum silence / end-of-speech confirmation already handled by STT;
    # this is an extra settle after the final arrives.
    min_chars: int = 2
    min_words: int = 1
    # Reject unfinished clauses unless the pause was long (handled by STT finals).
    reject_trailing_incomplete: bool = True
    # Allow short voice-UX commands through even if terse ("wait", "pause").
    allow_short_commands: bool = True

    _buffer: str = ""
    _last_change_at: float = 0.0
    _speech_ended: bool = False
    _released_text: str = ""
    _command_re: re.Pattern[str] = field(
        default_factory=lambda: re.compile(
            r"\b("
            r"wait|hold\s*on|pause|resume|continue|"
            r"repeat|slower|bookmark|quiz\s*mode|teach\s*back|"
            r"thinko|lilvro"
            r")\b",
            re.I,
        )
    )

    def reset(self) -> None:
        self._buffer = ""
        self._last_change_at = 0.0
        self._speech_ended = False
        self._released_text = ""

    def feed(
        self,
        text: str,
        *,
        speech_ended: bool = False,
        is_interim: bool = False,
        now: float | None = None,
    ) -> GateResult:
        """Ingest one STT update. Returns WAIT until a finished utterance is ready."""
        now = time.monotonic() if now is None else now
        cleaned = " ".join((text or "").strip().split())

        if is_interim and not speech_ended:
            # Show/listen only — never reply on interim audio.
            if cleaned and cleaned != self._buffer:
                self._buffer = cleaned
                self._last_change_at = now
            self._speech_ended = False
            return GateResult(GateDecision.WAIT, self._buffer, "interim")

        if not cleaned:
            if speech_ended:
                self.reset()
                return GateResult(GateDecision.IGNORE, "", "empty")
            return GateResult(GateDecision.WAIT, "", "empty_partial")

        if cleaned != self._buffer:
            self._buffer = cleaned
            self._last_change_at = now

        if speech_ended:
            self._speech_ended = True
        else:
            self._speech_ended = False
            return GateResult(GateDecision.WAIT, self._buffer, "awaiting_end")

        # Speech ended — still wait a brief settle so late corrections can land.
        if now - self._last_change_at < self.settle_seconds:
            return GateResult(GateDecision.WAIT, self._buffer, "settling")

        return self._evaluate(self._buffer)

    def force_evaluate(self, text: str | None = None, *, accept_incomplete: bool = False) -> GateResult:
        """Evaluate current buffer (or provided text) as a finished utterance."""
        candidate = " ".join(((text if text is not None else self._buffer) or "").strip().split())
        if accept_incomplete:
            prev = self.reject_trailing_incomplete
            self.reject_trailing_incomplete = False
            try:
                return self._evaluate(candidate)
            finally:
                self.reject_trailing_incomplete = prev
        return self._evaluate(candidate)
    def _evaluate(self, text: str) -> GateResult:
        if not text:
            self.reset()
            return GateResult(GateDecision.IGNORE, "", "empty")

        # Don't double-fire the same finished line.
        if text == self._released_text:
            return GateResult(GateDecision.IGNORE, text, "duplicate")

        if _FILLER_ONLY.match(text):
            self.reset()
            return GateResult(GateDecision.IGNORE, text, "filler")

        words = [w for w in re.split(r"\s+", text) if w]
        is_command = bool(self._command_re.search(text)) if self.allow_short_commands else False

        if not is_command:
            if len(text) < self.min_chars:
                self.reset()
                return GateResult(GateDecision.IGNORE, text, "too_short")
            if len(words) < self.min_words:
                self.reset()
                return GateResult(GateDecision.IGNORE, text, "too_few_words")
            if self.reject_trailing_incomplete and _TRAILING_INCOMPLETE.search(text):
                # Treat as not finished — keep listening instead of answering.
                self._speech_ended = False
                return GateResult(GateDecision.WAIT, text, "trailing_incomplete")

        self._released_text = text
        # Clear buffer so the next utterance starts fresh, but keep released_text
        # for duplicate suppression until a new distinct utterance arrives.
        self._buffer = ""
        self._speech_ended = False
        self._last_change_at = 0.0
        return GateResult(GateDecision.READY, text, "complete")


def is_ready_utterance(text: str, *, allow_commands: bool = True) -> bool:
    """Stateless helper for one-shot finals (e.g. recorder.text callbacks)."""
    gate = UtteranceGate(allow_short_commands=allow_commands, settle_seconds=0.0)
    result = gate.force_evaluate(text)
    return result.decision == GateDecision.READY
