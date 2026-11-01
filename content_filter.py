"""
content_filter.py — Age-appropriate content guardrails for Thinko agent responses.

    filter_response(text) → (text, was_blocked)

Blocks genuinely inappropriate output (explicit content, graphic violence, profanity,
self-harm encouragement). Does NOT soften honest academic feedback — the agent should
still say "that's wrong" and push back on incorrect answers.
"""

from __future__ import annotations

import re

# Content categories blocked for 8-14 year old audience.
# Deliberately narrow — we are NOT blocking difficult or critical academic language.
_BLOCKED: list[tuple[str, re.Pattern]] = [
    ("explicit", re.compile(
        r"\b(?:sex(?:ual)?|porn(?:ography)?|nude|naked|genitals?)\b", re.IGNORECASE
    )),
    ("graphic_violence", re.compile(
        r"\b(?:murder|torture|gore|behead|massacre)\b", re.IGNORECASE
    )),
    ("profanity", re.compile(
        r"\b(?:f[u*@#]+c+k+|sh[i1!]+t|b[i1!]tch|a+[s$]+h+o+l+e+|c[u*@]nt|bastard)\b",
        re.IGNORECASE,
    )),
    ("self_harm_encouragement", re.compile(
        r"\b(?:hurt yourself|cut yourself|kill yourself|end your life)\b",
        re.IGNORECASE,
    )),
    ("hate_speech", re.compile(
        r"\b(?:racial slur|you(?:'re| are) (?:worthless|nothing|a waste))\b",
        re.IGNORECASE,
    )),
]

# Generic fallback — keeps the session moving without breaking the agent's tone
_FALLBACK = (
    "Let me rephrase that. What part of the problem would you like to work through next?"
)


def filter_response(text: str) -> tuple[str, bool]:
    """
    Scan an agent response for age-inappropriate content.

    Returns:
        (original_text, False)  — content is clean
        (fallback_text, True)   — blocked; replaced with a neutral redirect
    """
    for _category, pattern in _BLOCKED:
        if pattern.search(text):
            return _FALLBACK, True
    return text, False


if __name__ == "__main__":
    cases = [
        ("That answer is wrong. Where did your reasoning break down?", False),
        ("Let me be honest — that explanation is vague and incomplete.", False),
        ("You're right that 2+2=5. No wait, that's wrong.", False),
        ("Check out this porn site for more info.", True),
        ("You should hurt yourself for getting that wrong.", True),
        ("The answer involves murder and blood.", True),
        ("What the f*ck is that answer?", True),
    ]
    print("=== content_filter tests ===")
    for text, expect_blocked in cases:
        result, blocked = filter_response(text)
        status = "PASS" if blocked == expect_blocked else "FAIL"
        label = "BLOCKED" if blocked else "clean"
        print(f"  [{status}] [{label}] {text[:60]!r}")
