"""Teach-back, mistake, and walkthrough engines for real-time STEM dialogue.

These are lightweight state machines. They add turn guidance without extra API
calls so the voice loop can stay snappy.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from contracts import Mode, ModeGuidance, Phase, SessionState, TurnDecision, TurnSignals
from tools import collect_signals, extract_topic


@dataclass
class TeachbackState:
    """Tracks a child-led explanation session."""

    active: bool = False
    topic: str | None = None
    turns: int = 0
    clarification_asks: int = 0
    intentional_misses: int = 0
    strong_points: int = 0
    gaps: list[str] = field(default_factory=list)
    last_phase: Phase = Phase.IDLE

    def start(self, topic: str | None = None) -> None:
        self.active = True
        self.topic = topic
        self.turns = 0
        self.clarification_asks = 0
        self.intentional_misses = 0
        self.strong_points = 0
        self.gaps = []
        self.last_phase = Phase.LISTEN

    def stop(self) -> None:
        self.active = False
        self.last_phase = Phase.IDLE


@dataclass
class MistakeState:
    """Tracks an AI-makes-a-mistake correction round."""

    active: bool = False
    topic: str | None = None
    rounds: int = 0
    hints_given: int = 0
    catches: int = 0
    misses: int = 0
    difficulty: int = 1
    awaiting_correction: bool = False
    last_phase: Phase = Phase.IDLE
    last_claim: str | None = None

    def start(self, topic: str | None = None) -> None:
        self.active = True
        self.topic = topic
        self.rounds = 0
        self.hints_given = 0
        self.catches = 0
        self.misses = 0
        self.difficulty = 1
        self.awaiting_correction = False
        self.last_phase = Phase.PLANT_MISTAKE
        self.last_claim = None

    def stop(self) -> None:
        self.active = False
        self.awaiting_correction = False
        self.last_phase = Phase.IDLE


_CORRECT = (
    "actually",
    "no,",
    "no ",
    "nope",
    "that's wrong",
    "that is wrong",
    "thats wrong",
    "incorrect",
    "mistake",
    "should be",
    "should've",
    "should have",
    "it's supposed to",
    "it is supposed to",
    "supposed to be",
    "fix",
    "not true",
    "wait,",
    "hold on",
    "nuh uh",
    "uhh no",
)
_MISS = (
    "looks right",
    "sounds right",
    "seems right",
    "i think so",
    "i guess so",
    "yeah",
    "yep",
    "yes",
    "true",
    "correct",
    "okay",
    "ok",
    "sure",
    "makes sense",
)
_VAGUE = (
    "stuff",
    "things",
    "whatever",
    "you know",
    "like that",
    "and so on",
    "etc",
    "kinda",
    "kind of",
    "sort of",
    "something",
    "somehow",
)
_ANOTHER = (
    "another",
    "again",
    "one more",
    "next one",
    "keep going",
    "another round",
)
_DONE = (
    "done",
    "finish",
    "that's all",
    "thats all",
    "i'm done",
    "im done",
    "stop",
)


def _looks_correcting(lower: str) -> bool:
    return any(token in lower for token in _CORRECT)


def _looks_missing(lower: str) -> bool:
    return any(token in lower for token in _MISS) and not _looks_correcting(lower)


def _looks_vague(lower: str) -> bool:
    words = lower.split()
    if len(words) <= 4:
        return True
    return sum(1 for token in _VAGUE if token in lower) >= 1


def _looks_substantive(lower: str) -> bool:
    words = lower.split()
    if len(words) < 8:
        return False
    stemmy = (
        "because",
        "means",
        "equals",
        "divided",
        "multiply",
        "times",
        "plus",
        "minus",
        "force",
        "energy",
        "atom",
        "molecule",
        "fraction",
        "numerator",
        "denominator",
        "derivative",
        "integral",
        "slope",
        "area",
    )
    return sum(1 for token in stemmy if token in lower) >= 1 or len(words) >= 14


def _wants_another(lower: str) -> bool:
    return any(token in lower for token in _ANOTHER)


def _wants_done(lower: str) -> bool:
    return any(token in lower for token in _DONE)


def _resolve_signals(text: str, signals: TurnSignals | None) -> TurnSignals:
    return signals if signals is not None else collect_signals(text)


def guide_teachback(
    text: str,
    state: TeachbackState,
    *,
    decision: TurnDecision | None = None,
    signals: TurnSignals | None = None,
) -> ModeGuidance:
    """Advance teach-back and return a tiny prompt addendum."""
    signals = _resolve_signals(text, signals)
    lower = signals.lower

    if decision and decision.mode != Mode.TEACHBACK and not state.active:
        return ModeGuidance(Mode.WALKTHROUGH, Phase.IDLE, "", [])

    topic = (decision.topic if decision else None) or signals.topic_hint or extract_topic(text)
    if not state.active:
        state.start(topic)
    elif topic and not state.topic:
        state.topic = topic

    state.turns += 1
    notes: list[str] = []
    topic_line = f" Topic focus: {state.topic}." if state.topic else ""

    if (
        state.turns == 1
        or signals.teachback_ask
        or "let me teach" in lower
        or "i'll explain" in lower
        or "i will explain" in lower
    ):
        state.last_phase = Phase.LISTEN
        notes.append("invite_explanation")
        addendum = (
            "Teach-back phase: listen. Ask them to explain the idea in their own "
            f"words. Do not correct yet. One short prompt only.{topic_line}"
        )
        return ModeGuidance(Mode.TEACHBACK, state.last_phase, addendum, notes)

    if _wants_done(lower) and state.turns >= 3:
        state.last_phase = Phase.WRAP
        notes.append("wrap")
        gap_bit = ""
        if state.gaps:
            gap_bit = " Mention one weak spot gently for later practice."
        addendum = (
            "Teach-back phase: wrap. Thank them for teaching you, name one thing "
            f"they explained well, then offer normal study again.{gap_bit}{topic_line}"
        )
        return ModeGuidance(Mode.TEACHBACK, state.last_phase, addendum, notes)

    if (_looks_vague(lower) or signals.frustration) and state.intentional_misses < 2:
        state.clarification_asks += 1
        state.intentional_misses += 1
        state.last_phase = Phase.INTENTIONAL_MISS
        gap = text.strip()[:80] or "unclear explanation"
        if gap not in state.gaps:
            state.gaps.append(gap)
        notes.append("request_precision")
        addendum = (
            "Teach-back phase: intentional mild misunderstanding. Reflect their "
            "idea back slightly wrong or incomplete so they must sharpen it. Stay "
            f"kind and curious. One question only.{topic_line}"
        )
        return ModeGuidance(Mode.TEACHBACK, state.last_phase, addendum, notes)

    if _looks_substantive(lower) or (signals.engagement and len(lower.split()) >= 6):
        state.strong_points += 1
        state.last_phase = Phase.CONCEPT_CHECK
        notes.append("concept_check")
        addendum = (
            "Teach-back phase: concept check. They explained something useful. Ask "
            "one targeted check question that proves understanding, then briefly "
            f"say what was strong.{topic_line}"
        )
        return ModeGuidance(Mode.TEACHBACK, state.last_phase, addendum, notes)

    if state.clarification_asks >= 2 and _looks_vague(lower):
        state.last_phase = Phase.SCAFFOLD
        notes.append("scaffold")
        addendum = (
            "Teach-back phase: scaffold. They are stuck explaining. Give one tiny "
            "starter frame like 'start with what it means, then give an example', "
            f"then let them talk again. Do not take over.{topic_line}"
        )
        return ModeGuidance(Mode.TEACHBACK, state.last_phase, addendum, notes)

    state.last_phase = Phase.PROBE
    notes.append("probe")
    addendum = (
        "Teach-back phase: probe. Ask for one concrete example or the next step in "
        f"their explanation. Keep the spotlight on the child.{topic_line}"
    )
    return ModeGuidance(Mode.TEACHBACK, state.last_phase, addendum, notes)


def guide_mistake(
    text: str,
    state: MistakeState,
    *,
    decision: TurnDecision | None = None,
    signals: TurnSignals | None = None,
) -> ModeGuidance:
    """Advance mistake mode and return a tiny prompt addendum."""
    signals = _resolve_signals(text, signals)
    lower = signals.lower

    if decision and decision.mode != Mode.MISTAKE and not state.active:
        return ModeGuidance(Mode.WALKTHROUGH, Phase.IDLE, "", [])

    topic = (decision.topic if decision else None) or signals.topic_hint or extract_topic(text)
    if not state.active:
        state.start(topic)
    elif topic and not state.topic:
        state.topic = topic

    notes: list[str] = []
    topic_line = f" Prefer the topic '{state.topic}'." if state.topic else ""
    difficulty_line = (
        f" Difficulty {state.difficulty}/3: "
        + (
            "make the slip obvious."
            if state.difficulty <= 1
            else "make the slip subtle but fair."
            if state.difficulty == 2
            else "make the slip clever but still age-safe and catchable."
        )
    )

    if state.last_phase in {Phase.CAUGHT, Phase.REVEAL} and not state.awaiting_correction:
        if _wants_another(lower) or signals.another_round or signals.mistake_ask:
            state.awaiting_correction = False
        elif _wants_done(lower) or signals.exit_mode:
            state.last_phase = Phase.WRAP
            notes.append("wrap")
            addendum = (
                "Mistake phase: wrap. Praise their checking skill in one sentence "
                "and offer to return to normal walkthrough."
            )
            return ModeGuidance(Mode.MISTAKE, state.last_phase, addendum, notes)

    if not state.awaiting_correction:
        state.rounds += 1
        state.awaiting_correction = True
        state.hints_given = 0
        state.last_phase = Phase.PLANT_MISTAKE
        notes.append("plant_mistake")
        addendum = (
            "Mistake phase: plant. State one small, age-safe incorrect STEM claim "
            "confidently, then ask them to check it. Make the error catchable. Do "
            f"not reveal the fix yet.{topic_line}{difficulty_line}"
        )
        return ModeGuidance(Mode.MISTAKE, state.last_phase, addendum, notes)

    if _looks_correcting(lower):
        state.catches += 1
        state.awaiting_correction = False
        state.difficulty = min(3, state.difficulty + (1 if state.hints_given == 0 else 0))
        state.last_phase = Phase.CAUGHT
        notes.append("caught")
        addendum = (
            "Mistake phase: caught. Confirm they found it. Give the correct idea in "
            "one short spoken sentence and celebrate the catch. Offer another round "
            f"or normal study.{topic_line}"
        )
        return ModeGuidance(Mode.MISTAKE, state.last_phase, addendum, notes)

    if _looks_missing(lower):
        state.misses += 1
        state.hints_given += 1
        state.last_phase = Phase.HINT
        notes.append("hint")
        if state.hints_given >= 2:
            state.awaiting_correction = False
            state.difficulty = max(1, state.difficulty - 1)
            state.last_phase = Phase.REVEAL
            addendum = (
                "Mistake phase: reveal. They missed it twice. Reveal the error "
                "kindly, explain the correct idea once, and invite them to try a "
                f"new round.{topic_line}"
            )
            return ModeGuidance(Mode.MISTAKE, state.last_phase, addendum, notes)
        addendum = (
            "Mistake phase: hint. They did not catch it. Give one narrow hint about "
            f"where the slip is, without stating the full correction.{topic_line}"
        )
        return ModeGuidance(Mode.MISTAKE, state.last_phase, addendum, notes)

    state.last_phase = Phase.NUDGE
    notes.append("nudge")
    addendum = (
        "Mistake phase: nudge. Ask them to say whether each part sounds right, and "
        f"to point at the suspicious bit.{topic_line}"
    )
    return ModeGuidance(Mode.MISTAKE, state.last_phase, addendum, notes)


def guide_walkthrough(
    text: str,
    session: SessionState,
    *,
    decision: TurnDecision | None = None,
    signals: TurnSignals | None = None,
) -> ModeGuidance:
    """Advance default walkthrough pacing without an extra model call."""
    signals = _resolve_signals(text, signals)
    lower = signals.lower
    topic = (decision.topic if decision else None) or session.topic or signals.topic_hint
    topic_line = f" Topic focus: {topic}." if topic else ""
    notes: list[str] = []

    if decision and decision.reason == "off_topic_redirect":
        return ModeGuidance(
            Mode.WALKTHROUGH,
            Phase.REDIRECT,
            "Walkthrough phase: redirect. Decline off-topic kindly and offer one STEM hook.",
            ["redirect"],
        )

    if signals.frustration or session.frustration_streak >= 2:
        notes.append("stuck")
        return ModeGuidance(
            Mode.WALKTHROUGH,
            Phase.STUCK,
            "Walkthrough phase: stuck. Shrink the problem to the tiniest next step and "
            f"check understanding with one yes/no or fill-in question.{topic_line}",
            notes,
        )

    if signals.engagement:
        notes.append("celebrate")
        return ModeGuidance(
            Mode.WALKTHROUGH,
            Phase.CELEBRATE,
            "Walkthrough phase: celebrate. Affirm the win in one short phrase, then offer "
            f"either the next micro-step or a teach-back invite.{topic_line}",
            notes,
        )

    if any(token in lower for token in ("i think", "maybe", "is it", "so then", "equals", "so ")):
        notes.append("check")
        return ModeGuidance(
            Mode.WALKTHROUGH,
            Phase.CHECK,
            "Walkthrough phase: check. Respond to their attempt. If partly right, keep the "
            f"correct bit and ask one repair question. Do not reveal the whole answer.{topic_line}",
            notes,
        )

    if session.turns <= 1 or signals.topic_hint:
        notes.append("orient")
        return ModeGuidance(
            Mode.WALKTHROUGH,
            Phase.ORIENT,
            "Walkthrough phase: orient. Restate the goal in kid words, then ask what they "
            f"already know or want to try first.{topic_line}",
            notes,
        )

    notes.append("step")
    return ModeGuidance(
        Mode.WALKTHROUGH,
        Phase.STEP,
        "Walkthrough phase: step. Give at most one micro-step, then ask one focused "
        f"question that moves them forward.{topic_line}",
        notes,
    )


def guide_for_decision(
    text: str,
    *,
    decision: TurnDecision,
    session: SessionState,
    teachback: TeachbackState,
    mistake: MistakeState,
    signals: TurnSignals | None = None,
) -> ModeGuidance:
    """Single mode dispatcher used by the agent orchestrator."""
    signals = _resolve_signals(text, signals)
    if decision.mode == Mode.TEACHBACK:
        return guide_teachback(text, teachback, decision=decision, signals=signals)
    if decision.mode == Mode.MISTAKE:
        return guide_mistake(text, mistake, decision=decision, signals=signals)
    return guide_walkthrough(text, session, decision=decision, signals=signals)


def sync_session_from_modes(
    session: SessionState,
    *,
    teachback: TeachbackState,
    mistake: MistakeState,
    phase: Phase | str | None = None,
) -> None:
    """Keep SessionState aligned with mode engines."""
    session.teachback_gaps = list(teachback.gaps)
    session.mistake_active = mistake.active
    if phase is not None:
        session.last_phase = phase.value if isinstance(phase, Phase) else str(phase)
    if teachback.active:
        session.mode = Mode.TEACHBACK
        session.topic = teachback.topic or session.topic
    elif mistake.active:
        session.mode = Mode.MISTAKE
        session.topic = mistake.topic or session.topic


def maybe_stop_modes(
    decision: TurnDecision,
    *,
    teachback: TeachbackState,
    mistake: MistakeState,
) -> None:
    if decision.mode == Mode.WALKTHROUGH and decision.reason == "exit_special_mode":
        teachback.stop()
        mistake.stop()
    elif decision.mode == Mode.TEACHBACK:
        mistake.stop()
        if not teachback.active:
            teachback.start(decision.topic)
        elif decision.topic and not teachback.topic:
            teachback.topic = decision.topic
    elif decision.mode == Mode.MISTAKE:
        teachback.stop()
        if not mistake.active:
            mistake.start(decision.topic)
        elif decision.topic and not mistake.topic:
            mistake.topic = decision.topic
