"""Shared andy-agent contracts used by tools, modes, persona, mastery, and agent.

One source of truth for enums and turn/session shapes keeps the voice loop cohesive.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class Tool(str, Enum):
    MENTAL_HEALTH = "mental_health"
    MOTIVATION = "motivation"
    TEACHING = "teaching"
    ADVISING = "advising"
    ENTERTAINMENT = "entertainment"


class Mode(str, Enum):
    WALKTHROUGH = "walkthrough"
    TEACHBACK = "teachback"
    MISTAKE = "mistake"


class Phase(str, Enum):
    IDLE = "idle"
    # Walkthrough
    ORIENT = "orient"
    STEP = "step"
    CHECK = "check"
    STUCK = "stuck"
    CELEBRATE = "celebrate"
    REDIRECT = "redirect"
    # Teach-back
    LISTEN = "listen"
    PROBE = "probe"
    INTENTIONAL_MISS = "intentional_miss"
    CONCEPT_CHECK = "concept_check"
    SCAFFOLD = "scaffold"
    WRAP = "wrap"
    # Mistake
    PLANT_MISTAKE = "plant_mistake"
    NUDGE = "nudge"
    HINT = "hint"
    REVEAL = "reveal"
    CAUGHT = "caught"


@dataclass(slots=True)
class TurnSignals:
    """Compressed signals from one student utterance."""

    text: str
    lower: str
    word_count: int = 0
    frustration: int = 0
    distress: int = 0
    motivation_need: int = 0
    advise_ask: int = 0
    teachback_ask: int = 0
    mistake_ask: int = 0
    exit_mode: int = 0
    engagement: int = 0
    disengaged: int = 0
    off_topic: int = 0
    another_round: int = 0
    topic_hint: str | None = None

    @property
    def is_frustrated(self) -> bool:
        return self.frustration > 0 or self.distress > 0

    @property
    def is_engaged(self) -> bool:
        return self.engagement > 0


@dataclass(slots=True)
class TurnDecision:
    """What the agent should do for this turn."""

    primary_tool: Tool
    support_tool: Tool | None
    mode: Mode
    reason: str
    adjust: bool = False
    confidence: float = 1.0
    invite_mode: Mode | None = None
    topic: str | None = None


@dataclass(slots=True)
class ModeGuidance:
    """Extra spoken-instruction hints injected into the model prompt."""

    mode: Mode
    phase: Phase
    prompt_addendum: str
    notes: list[str] = field(default_factory=list)

    @property
    def phase_value(self) -> str:
        return self.phase.value


@dataclass
class SessionState:
    """Sticky real-time session memory across turns."""

    tool: Tool = Tool.TEACHING
    mode: Mode = Mode.WALKTHROUGH
    support_tool: Tool | None = None
    turns: int = 0
    frustration_streak: int = 0
    success_streak: int = 0
    short_reply_streak: int = 0
    disengage_streak: int = 0
    topic: str | None = None
    teachback_gaps: list[str] = field(default_factory=list)
    mistake_active: bool = False
    last_reason: str = "start"
    last_phase: str = Phase.IDLE.value
    invite_teachback_soon: bool = False

    def snapshot(self) -> dict[str, object]:
        return {
            "tool": self.tool.value,
            "support_tool": self.support_tool.value if self.support_tool else None,
            "mode": self.mode.value,
            "turns": self.turns,
            "frustration_streak": self.frustration_streak,
            "success_streak": self.success_streak,
            "short_reply_streak": self.short_reply_streak,
            "disengage_streak": self.disengage_streak,
            "topic": self.topic,
            "teachback_gaps": list(self.teachback_gaps),
            "mistake_active": self.mistake_active,
            "last_reason": self.last_reason,
            "last_phase": self.last_phase,
            "invite_teachback_soon": self.invite_teachback_soon,
        }
