"""Lightweight per-topic mastery tracking for real-time sessions."""

from __future__ import annotations

from dataclasses import dataclass, field

from contracts import ModeGuidance, Phase


@dataclass
class MasteryBook:
    """Topic confidence scores in [0, 1], updated locally each turn."""

    scores: dict[str, float] = field(default_factory=dict)
    events: list[str] = field(default_factory=list)

    def get(self, topic: str | None) -> float:
        if not topic:
            return 0.0
        return self.scores.get(topic.lower(), 0.0)

    def bump(self, topic: str | None, delta: float, *, event: str) -> float:
        if not topic:
            return 0.0
        key = topic.lower()
        current = self.scores.get(key, 0.35)
        updated = max(0.0, min(1.0, current + delta))
        self.scores[key] = updated
        self.events.append(f"{event}:{key}:{updated:.2f}")
        if len(self.events) > 40:
            self.events = self.events[-40:]
        return updated

    def note_turn(
        self,
        *,
        topic: str | None,
        engagement: bool = False,
        frustration: bool = False,
        teachback_strong: bool = False,
        teachback_gap: bool = False,
        mistake_catch: bool = False,
        mistake_miss: bool = False,
    ) -> float:
        if engagement:
            return self.bump(topic, 0.06, event="engagement")
        if teachback_strong:
            return self.bump(topic, 0.10, event="teachback_strong")
        if teachback_gap:
            return self.bump(topic, -0.05, event="teachback_gap")
        if mistake_catch:
            return self.bump(topic, 0.12, event="mistake_catch")
        if mistake_miss:
            return self.bump(topic, -0.04, event="mistake_miss")
        if frustration:
            return self.bump(topic, -0.07, event="frustration")
        return self.get(topic)

    def note_from_guidance(
        self,
        *,
        topic: str | None,
        guidance: ModeGuidance,
        frustration: bool = False,
        engagement: bool = False,
    ) -> float:
        """Map shared phase contracts onto mastery deltas."""
        phase = guidance.phase
        return self.note_turn(
            topic=topic,
            engagement=engagement or phase == Phase.CELEBRATE,
            frustration=frustration,
            teachback_strong=phase == Phase.CONCEPT_CHECK,
            teachback_gap=phase in {Phase.INTENTIONAL_MISS, Phase.SCAFFOLD},
            mistake_catch=phase == Phase.CAUGHT,
            mistake_miss=phase in {Phase.HINT, Phase.REVEAL},
        )

    def snapshot(self) -> dict[str, object]:
        return {
            "scores": dict(self.scores),
            "top": sorted(self.scores.items(), key=lambda item: item[1], reverse=True)[:5],
            "recent_events": list(self.events[-8:]),
        }

    def coaching_line(self, topic: str | None) -> str:
        score = self.get(topic)
        if not topic:
            return ""
        if score < 0.35:
            return f"Mastery on {topic} is still forming — keep steps tiny."
        if score < 0.7:
            return f"Mastery on {topic} is growing — stretch with one check question."
        return f"Mastery on {topic} looks strong — invite teach-back or a harder twist."
