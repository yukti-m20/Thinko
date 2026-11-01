"""Fast local tools the agent can recognize and switch between in real time.

Routing is pure keyword / pattern matching — no extra LLM call — so tool
selection stays under a millisecond on each voice turn.
"""

from __future__ import annotations

import re
from typing import Iterable

from contracts import Mode, SessionState, Tool, TurnDecision, TurnSignals

# Re-export contracts so existing `from tools import Tool, Mode, ...` keeps working.
__all__ = [
    "Mode",
    "SessionState",
    "Tool",
    "TurnDecision",
    "TurnSignals",
    "apply_decision",
    "build_instructions",
    "collect_signals",
    "extract_topic",
    "route_turn",
]

# Precompiled once at import — keep voice turns cheap.
_FRUSTRATION = re.compile(
    r"("
    r"i\s*(don'?t|do not)\s*(get|understand)|"
    r"this\s*(is\s*)?(stupid|impossible|too\s*hard|so\s*hard)|"
    r"i\s*(give\s*up|hate\s*this)|"
    r"i\s*can'?t\s*(do|figure|solve)|"
    r"\bugh+\b|\bargh+\b|\bwhatever\b|"
    r"i'?m\s*(so\s*)?(lost|stuck|confused)|"
    r"none of this makes sense"
    r")",
    re.I,
)
_DISTRESS = re.compile(
    r"("
    r"i\s*(want\s*to\s*die|hate\s*myself)|"
    r"kill\s*myself|hurt\s*myself|"
    r"no\s*one\s*(cares|loves\s*me)|"
    r"i'?m\s*(scared|anxious|panicking|overwhelmed)|"
    r"i\s*(can'?t\s*breathe|feel\s*hopeless)|"
    r"i\s*want\s*to\s*disappear"
    r")",
    re.I,
)
_MOTIVATION = re.compile(
    r"("
    r"encourage\s*me|motivate\s*me|"
    r"i\s*(need|want)\s*(a\s*)?(pep\s*talk|boost)|"
    r"i'?m\s*(tired|bored|done)|"
    r"why\s*(bother|try)|"
    r"this\s*(is\s*)?pointless|"
    r"\bstreak\b|keep\s*(going|me\s*going)|"
    r"i\s*feel\s*dumb"
    r")",
    re.I,
)
_ADVISING = re.compile(
    r"("
    r"how\s*(should|do)\s*i\s*(study|prepare|approach)|"
    r"study\s*tips?|"
    r"what\s*(should|do)\s*i\s*(learn|do)\s*next|"
    r"\badvice\b|advise\s*me|"
    r"plan\s*(my\s*)?(study|session)|"
    r"how\s*do\s*i\s*get\s*better\s*at|"
    r"what\s*should\s*i\s*practice"
    r")",
    re.I,
)
_TEACHBACK = re.compile(
    r"("
    r"let\s*me\s*teach(\s*you)?|"
    r"i'?ll\s*explain|i\s*will\s*explain|"
    r"teach[\s-]*back|"
    r"can\s*i\s*explain|"
    r"i\s*want\s*to\s*teach|"
    r"listen\s*to\s*(my\s*)?explanation|"
    r"i'?ll\s*teach\s*you"
    r")",
    re.I,
)
_MISTAKE = re.compile(
    r"("
    r"mistake\s*mode|"
    r"quiz\s*me|"
    r"catch\s*(my|the)\s*mistake|"
    r"find\s*the\s*(error|mistake)|"
    r"trick\s*me|"
    r"spot\s*the\s*(bug|error|mistake)|"
    r"make\s*a\s*mistake\s*(for|and)\s*me"
    r")",
    re.I,
)
_EXIT = re.compile(
    r"("
    r"stop\s*(teach[\s-]*back|mistake|quiz)|"
    r"normal\s*mode|"
    r"back\s*to\s*(teaching|studying|problems?)|"
    r"enough(\s*of\s*that)?|"
    r"exit\s*mode|"
    r"let'?s\s*just\s*study"
    r")",
    re.I,
)
_ENGAGED = re.compile(
    r"("
    r"got\s*it|i\s*see|that\s*helps|"
    r"makes\s*sense|oh\s*okay|"
    r"i\s*understand|cool|nice|"
    r"ohh+|aha|that\s*clicked"
    r")",
    re.I,
)
_DISENGAGED = re.compile(
    r"("
    r"idk|i\s*don'?t\s*know|"
    r"\bmeh\b|\bnah\b|"
    r"can\s*we\s*(do|talk\s*about)\s*something\s*else|"
    r"this\s*is\s*boring|i'?m\s*bored|"
    r"whatever|"
    r"i\s*don'?t\s*care"
    r")",
    re.I,
)
_OFF_TOPIC = re.compile(
    r"("
    r"tiktok|instagram|snapchat|youtube|"
    r"video\s*game|fortnite|minecraft|"
    r"girlfriend|boyfriend|dating|"
    r"how\s*to\s*(hack|cheat)|"
    r"tell\s*me\s*a\s*(scary|ghost)\s*story"
    r")",
    re.I,
)
_ANOTHER = re.compile(
    r"("
    r"another(\s*one)?|again|"
    r"one\s*more|next\s*(round|one)|"
    r"keep\s*going"
    r")",
    re.I,
)
_TEACHING = re.compile(
    r"("
    r"help\s*(me\s*)?(with|solve|understand)|"
    r"walk\s*(me\s*)?through|"
    r"\bexplain\b|"
    r"what\s*is|how\s*(do|does|to)|"
    r"integral|derivative|equation|solve|simplify|"
    r"fraction|matrix|limit|molecule|atom|force|gravity"
    r")",
    re.I,
)
_TOPIC = re.compile(
    r"(?:about|on|with|for)\s+([a-z0-9π√∫^=+\-*/\s]{2,40})"
    r"(?:\s+(?:please|mode|now|okay|ok))?$",
    re.I,
)
_TOPIC_FALLBACK = re.compile(
    r"\b(fractions?|derivatives?|integrals?|algebra|geometry|"
    r"photosynthesis|gravity|matrices|limits?|exponents?|"
    r"chemical\s+equations?|atoms?|molecules?)\b",
    re.I,
)


def _hits(pattern: re.Pattern[str], text: str) -> int:
    return len(pattern.findall(text))


def extract_topic(text: str) -> str | None:
    """Pull a lightweight topic hint without NLP."""
    lower = text.strip().lower()
    match = _TOPIC.search(lower)
    if match:
        topic = re.sub(r"\s+", " ", match.group(1)).strip(" .,!?")
        if topic and topic not in {"it", "this", "that", "you", "me"}:
            return topic[:60]
    match = _TOPIC_FALLBACK.search(lower)
    if match:
        return match.group(1).lower()
    return None


def collect_signals(text: str) -> TurnSignals:
    cleaned = text.strip()
    lower = cleaned.lower()
    words = lower.split()
    return TurnSignals(
        text=cleaned,
        lower=lower,
        word_count=len(words),
        frustration=_hits(_FRUSTRATION, lower),
        distress=_hits(_DISTRESS, lower),
        motivation_need=_hits(_MOTIVATION, lower),
        advise_ask=_hits(_ADVISING, lower),
        teachback_ask=_hits(_TEACHBACK, lower),
        mistake_ask=_hits(_MISTAKE, lower),
        exit_mode=_hits(_EXIT, lower),
        engagement=_hits(_ENGAGED, lower),
        disengaged=_hits(_DISENGAGED, lower),
        off_topic=_hits(_OFF_TOPIC, lower),
        another_round=_hits(_ANOTHER, lower),
        topic_hint=extract_topic(cleaned),
    )


def route_turn(text: str, session: SessionState | None = None) -> TurnDecision:
    """Pick primary tool, optional support tool, and interaction mode.

    Priority (fast path):
    1. Distress / mental health overrides
    2. Off-topic redirect via advising
    3. Explicit mode wake / exit phrases
    4. Sticky active mode (teachback / mistake)
    5. Motivation / entertainment / advising / teaching cues
    6. Soft adjust overlays when frustration or disengagement rises
    """
    session = session or SessionState()
    signals = collect_signals(text)
    topic = signals.topic_hint or session.topic

    # 1) Safety / mental health always wins.
    if signals.distress:
        return TurnDecision(
            primary_tool=Tool.MENTAL_HEALTH,
            support_tool=None,
            mode=Mode.WALKTHROUGH,
            reason="distress_signal",
            adjust=True,
            confidence=1.0,
            topic=topic,
        )

    # 2) Off-topic: redirect kindly without abandoning the session.
    if signals.off_topic:
        return TurnDecision(
            primary_tool=Tool.ADVISING,
            support_tool=Tool.MOTIVATION,
            mode=Mode.WALKTHROUGH,
            reason="off_topic_redirect",
            adjust=True,
            confidence=0.95,
            topic=topic,
        )

    # 3) Explicit exit from special modes.
    if signals.exit_mode and session.mode in (Mode.TEACHBACK, Mode.MISTAKE):
        return TurnDecision(
            primary_tool=Tool.TEACHING,
            support_tool=Tool.MOTIVATION if signals.frustration else None,
            mode=Mode.WALKTHROUGH,
            reason="exit_special_mode",
            adjust=True,
            confidence=0.95,
            topic=topic,
        )

    # 4) Explicit mode entry.
    if signals.teachback_ask:
        return TurnDecision(
            primary_tool=Tool.TEACHING,
            support_tool=None,
            mode=Mode.TEACHBACK,
            reason="wake_teachback",
            confidence=0.98,
            topic=topic,
        )
    if signals.mistake_ask:
        return TurnDecision(
            primary_tool=Tool.TEACHING,
            support_tool=None,
            mode=Mode.MISTAKE,
            reason="wake_mistake",
            confidence=0.98,
            topic=topic,
        )

    # 5) Sticky special modes until exit.
    if session.mode == Mode.TEACHBACK:
        support = None
        if signals.frustration >= 2 or session.frustration_streak >= 2:
            support = Tool.MENTAL_HEALTH
        elif signals.frustration or signals.disengaged:
            support = Tool.MOTIVATION
        return TurnDecision(
            primary_tool=Tool.TEACHING,
            support_tool=support,
            mode=Mode.TEACHBACK,
            reason="sticky_teachback",
            adjust=support is not None,
            confidence=0.92,
            topic=topic,
        )
    if session.mode == Mode.MISTAKE or session.mistake_active:
        support = Tool.MOTIVATION if signals.frustration or signals.disengaged else None
        return TurnDecision(
            primary_tool=Tool.TEACHING,
            support_tool=support,
            mode=Mode.MISTAKE,
            reason="sticky_mistake",
            adjust=support is not None,
            confidence=0.92,
            topic=topic,
        )

    # 6) Soft mental-health / entertainment adjust while staying on task.
    if signals.frustration >= 2 or session.frustration_streak >= 2:
        teachingish = bool(_hits(_TEACHING, signals.lower) or session.tool == Tool.TEACHING)
        return TurnDecision(
            primary_tool=Tool.TEACHING if teachingish else Tool.MENTAL_HEALTH,
            support_tool=Tool.MENTAL_HEALTH,
            mode=Mode.WALKTHROUGH,
            reason="frustration_adjust",
            adjust=True,
            confidence=0.88,
            topic=topic,
        )

    if signals.disengaged or session.disengage_streak >= 2 or session.short_reply_streak >= 3:
        return TurnDecision(
            primary_tool=Tool.ENTERTAINMENT,
            support_tool=Tool.TEACHING,
            mode=Mode.WALKTHROUGH,
            reason="disengage_reframe",
            adjust=True,
            confidence=0.86,
            topic=topic,
        )

    if signals.motivation_need:
        return TurnDecision(
            primary_tool=Tool.MOTIVATION,
            support_tool=Tool.TEACHING if _hits(_TEACHING, signals.lower) else None,
            mode=Mode.WALKTHROUGH,
            reason="motivation_cue",
            confidence=0.9,
            topic=topic,
        )

    if signals.advise_ask:
        return TurnDecision(
            primary_tool=Tool.ADVISING,
            support_tool=None,
            mode=Mode.WALKTHROUGH,
            reason="advising_cue",
            confidence=0.9,
            topic=topic,
        )

    if signals.frustration == 1:
        return TurnDecision(
            primary_tool=Tool.TEACHING,
            support_tool=Tool.MOTIVATION,
            mode=Mode.WALKTHROUGH,
            reason="light_frustration_boost",
            adjust=True,
            confidence=0.82,
            topic=topic,
        )

    invite = None
    if (
        session.invite_teachback_soon
        or session.success_streak >= 2
        or (session.success_streak >= 1 and signals.engagement)
    ):
        invite = Mode.TEACHBACK

    if _hits(_TEACHING, signals.lower) or session.tool in {Tool.TEACHING, Tool.ENTERTAINMENT}:
        return TurnDecision(
            primary_tool=Tool.TEACHING,
            support_tool=None,
            mode=Mode.WALKTHROUGH,
            reason="teaching_default",
            confidence=0.78,
            invite_mode=invite,
            topic=topic,
        )

    return TurnDecision(
        primary_tool=session.tool,
        support_tool=session.support_tool,
        mode=session.mode,
        reason="sticky_session",
        confidence=0.65,
        invite_mode=invite,
        topic=topic,
    )


def apply_decision(session: SessionState, decision: TurnDecision, signals: TurnSignals | None = None) -> SessionState:
    """Mutate session in place for the next real-time turn."""
    signals = signals or TurnSignals(text="", lower="", word_count=0)
    session.turns += 1
    session.tool = decision.primary_tool
    session.support_tool = decision.support_tool
    session.mode = decision.mode
    session.last_reason = decision.reason
    session.mistake_active = decision.mode == Mode.MISTAKE
    if decision.topic:
        session.topic = decision.topic

    if signals.word_count and signals.word_count <= 2 and not signals.engagement:
        session.short_reply_streak += 1
    else:
        session.short_reply_streak = 0

    if signals.disengaged:
        session.disengage_streak += 1
    elif signals.engagement or signals.word_count >= 6:
        session.disengage_streak = max(0, session.disengage_streak - 1)

    if signals.frustration or signals.distress:
        session.frustration_streak += 1
        session.success_streak = 0
        session.invite_teachback_soon = False
    elif signals.engagement:
        session.success_streak += 1
        session.frustration_streak = max(0, session.frustration_streak - 1)
        if session.success_streak >= 2 and session.mode == Mode.WALKTHROUGH:
            session.invite_teachback_soon = True
    else:
        session.frustration_streak = max(0, session.frustration_streak - 1)

    if decision.invite_mode == Mode.TEACHBACK:
        session.invite_teachback_soon = True
    if decision.mode == Mode.TEACHBACK:
        session.invite_teachback_soon = False

    return session


TOOL_OVERLAYS: dict[Tool, str] = {
    Tool.MENTAL_HEALTH: (
        "TOOL: mental_health. Prioritize emotional safety. Validate feelings, "
        "slow down, offer a short break or easier step. Never diagnose. If distress "
        "sounds serious, calmly tell them to talk to a trusted adult right away. "
        "Do not ask for personal details. Keep STEM optional this turn."
    ),
    Tool.MOTIVATION: (
        "TOOL: motivation. Give a short, specific pep moment. Celebrate effort, "
        "name one tiny next win, keep energy warm and peer-like. Then return to the "
        "learning goal in one sentence."
    ),
    Tool.TEACHING: (
        "TOOL: teaching. Stay Socratic. One step, one question. Do not dump the "
        "final answer. Use spoken math."
    ),
    Tool.ADVISING: (
        "TOOL: advising. Give practical study guidance: how to approach the topic, "
        "what to practice next, or a tiny study plan. If they went off-topic, kindly "
        "steer back to STEM without shaming. Keep it concrete and short."
    ),
    Tool.ENTERTAINMENT: (
        "TOOL: entertainment. Re-engage with one vivid STEM analogy, mini wonder, "
        "or surprising angle about the current topic, then invite them back into "
        "the problem with one easy question."
    ),
}


MODE_OVERLAYS: dict[Mode, str] = {
    Mode.WALKTHROUGH: (
        "MODE: walkthrough. Guide the student through their problem step by step."
    ),
    Mode.TEACHBACK: (
        "MODE: teachback. The child teaches YOU. Listen first. Ask one precise "
        "concept-check question. If their explanation is vague or wrong, gently "
        "misunderstand on purpose so they must clarify. Track weak spots in plain "
        "speech. Do not lecture over them."
    ),
    Mode.MISTAKE: (
        "MODE: mistake. YOU state one small incorrect STEM claim on purpose. Ask "
        "the child to catch and fix it. If they miss it, give one hint. If they "
        "catch it, confirm and explain why in one short spoken sentence. Then offer "
        "another round or an exit."
    ),
}


def build_instructions(
    decision: TurnDecision,
    *,
    base_prompt: str,
    extra: Iterable[str] = (),
    session: SessionState | None = None,
) -> str:
    """Compose a compact instruction block for low-latency model calls."""
    parts = [base_prompt.strip(), TOOL_OVERLAYS[decision.primary_tool]]
    if decision.support_tool and decision.support_tool != decision.primary_tool:
        parts.append("SUPPORT " + TOOL_OVERLAYS[decision.support_tool])
    parts.append(MODE_OVERLAYS[decision.mode])

    if decision.topic:
        parts.append(f"CURRENT TOPIC: {decision.topic}")
    elif session and session.topic:
        parts.append(f"CURRENT TOPIC: {session.topic}")

    if session and session.teachback_gaps:
        gaps = "; ".join(session.teachback_gaps[-3:])
        parts.append(f"KNOWN WEAK SPOTS: {gaps}")

    if decision.adjust:
        parts.append(
            "ADJUST NOW: soften tone, reduce cognitive load, and keep the reply "
            "under three short spoken sentences."
        )
    if decision.invite_mode == Mode.TEACHBACK:
        parts.append(
            "OPTIONAL INVITE: if they seem confident, briefly offer teach-back: "
            "ask if they want to teach you the idea in their own words."
        )
    if decision.reason == "off_topic_redirect":
        parts.append(
            "REDIRECT: they asked something off-limits for this STEM buddy. "
            "Decline briefly and offer a STEM alternative."
        )
    if decision.reason == "distress_signal":
        parts.append(
            "SAFETY: lead with care. Encourage talking to a trusted adult. "
            "Do not dig for details of self-harm."
        )

    parts.extend(item.strip() for item in extra if item and item.strip())
    return "\n\n".join(parts)
