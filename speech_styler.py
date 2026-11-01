"""
speech_styler.py — Post-process TTS text for a more human, natural voice.

Two independent feature flags at the top of this file:

    NATURAL_PAUSES   — adds strategic commas/ellipses so Deepgram breathes
                        naturally at clause boundaries and before questions.

    UX_WARMTH        — varies sentence openers, softens corrections, adds
                        light encouragement without touching the math content.

Usage:
    from speech_styler import style_speech
    speakable = style_speech(render_math(llm_reply))

To disable either feature, set the flag to False below.
"""

from __future__ import annotations
import re
import random
NATURAL_PAUSES = True   # breathing-room punctuation for Deepgram TTS
UX_WARMTH      = True   # varied openers, softer corrections, light encouragement


# ------------------------------------------------------------------ #
#  Natural pauses
# ------------------------------------------------------------------ #

# Words that sound better with a comma pause after them when they open a sentence
_PAUSE_STARTERS = [
    "So", "Well", "Now", "Okay", "Right", "Alright",
    "Hmm", "Actually", "Remember", "Notice", "Think about it",
]

# Math result words — a tiny pause after these helps the student absorb the number
_MATH_RESULT_WORDS = [
    "squared", "cubed", "equals", "is", "gives", "yields",
    "plus", "minus", "divided by", "times",
]


def _add_natural_pauses(text: str) -> str:
    """
    Insert commas and ellipses at natural breathing points.

    - "So what..." → "So, what..."
    - "x squared equals 9 what..." → "x squared equals 9... what..."
    - Long sentence before a question → add comma before the question word
    """
    t = text

    # 1. Comma after sentence-opening single words (only if not already punctuated)
    for word in _PAUSE_STARTERS:
        # Match only at the very start of the text or after a sentence-ending punctuation
        t = re.sub(
            rf"(^|(?<=[.!?] ))({re.escape(word)})(?!\s*,)(\s+)",
            r"\1\2,\3",
            t,
            flags=re.IGNORECASE,
        )

    # 2. Ellipsis before an inline question word in a long clause
    #    "x squared equals 9 what is x" → "x squared equals 9... what is x?"
    t = re.sub(
        r"(\b(?:equals|is|gives)\b\s+[^\.\?!,]{4,20})\s+(what|how|which|why|can you)",
        r"\1... \2",
        t,
        flags=re.IGNORECASE,
    )

    # 3. Short pause after a math result before a follow-up question
    #    "That gives 4. What does that tell you?" → already fine with period
    #    "That gives 4 so what..." → "That gives 4, so what..."
    t = re.sub(
        r"(\d)\s+(so|and)\s+(what|how|why|which)",
        r"\1, \2 \3",
        t,
        flags=re.IGNORECASE,
    )

    # 4. Comma before "but" in two-clause sentences (sounds more conversational)
    t = re.sub(r"(?<!\,)\s+but\s+", ", but ", t, flags=re.IGNORECASE)

    # 5. Ellipsis at end of a Socratic question to imply waiting
    #    "What do you get?" stays. "What do you think?" → "What do you think...?"
    t = re.sub(
        r"(what do you think|what would you say|what comes next|have a guess)\??",
        r"\1...?",
        t,
        flags=re.IGNORECASE,
    )

    return t


# ------------------------------------------------------------------ #
#  UX warmth — varied language, softer corrections
# ------------------------------------------------------------------ #

# Alternative openers to cycle through so every reply doesn't start the same way
_OPENER_VARIANTS: dict[str, list[str]] = {
    r"^Let'?s think about":    ["Let's work through", "Think about", "Consider"],
    r"^Let'?s try":            ["How about we try", "Let's explore", "Let's see"],
    r"^Let'?s start":          ["We can start", "A good place to start is", "Begin by thinking about"],
    r"^Good question":         ["Nice one", "That's a great place to start", "Interesting question"],
    r"^That'?s right":         ["Exactly right", "Yes, that's it", "Spot on"],
    r"^That'?s correct":       ["That's exactly it", "You got it", "Correct"],
}

# Correction softeners — make wrong-answer redirects feel kinder
_CORRECTION_VARIANTS: list[tuple[str, list[str]]] = [
    (
        r"Hmm,? not quite[,.]?",
        [
            "Not quite,",
            "Almost, but not quite —",
            "Hmm, let me push back on that —",
        ],
    ),
    (
        r"Close[!.]?\s+[Ll]et'?s double.?check that step[^\.\!]*[\.!]?",
        [
            "Almost! Let's look at that step again.",
            "Getting warm — let's retrace that step.",
            "Nearly there. Can we check that part?",
        ],
    ),
    (
        r"[Ll]et'?s double.?check that together",
        [
            "Let's retrace that together",
            "let's look at that again",
            "let's slow down on that part",
        ],
    ),
]


def _add_warmth(text: str) -> str:
    """Vary openers and soften correction phrases."""
    t = text

    # Randomise opener variants (seeded on content so same input = same output)
    seed = sum(ord(c) for c in t[:40])
    rng = random.Random(seed)

    for pattern, options in _OPENER_VARIANTS.items():
        def _replace_opener(m: re.Match, opts: list[str] = options, r: random.Random = rng) -> str:
            chosen = r.choice(opts)
            # preserve capitalisation of the rest of the match
            rest = m.group(0)[len(m.group(0).split()[0]):]
            return chosen

        t = re.sub(pattern, _replace_opener, t, count=1, flags=re.IGNORECASE)

    # Randomise correction phrases
    for pattern, options in _CORRECTION_VARIANTS:
        if re.search(pattern, t, re.IGNORECASE):
            replacement = rng.choice(options)
            t = re.sub(pattern, replacement, t, count=1, flags=re.IGNORECASE)

    return t


# ------------------------------------------------------------------ #
#  Public entry point
# ------------------------------------------------------------------ #

def style_speech(text: str) -> str:
    """
    Apply enabled speech styling to TTS-ready text.

    Args:
        text: Output of render_math() / render() — clean speakable text.

    Returns:
        Styled text ready to send to Deepgram TTS.
    """
    if not isinstance(text, str) or not text.strip():
        return text

    t = text

    if NATURAL_PAUSES:
        t = _add_natural_pauses(t)

    if UX_WARMTH:
        t = _add_warmth(t)

    # Final whitespace cleanup
    t = re.sub(r" {2,}", " ", t).strip()
    return t


# ------------------------------------------------------------------ #
#  Quick demo
# ------------------------------------------------------------------ #

if __name__ == "__main__":
    samples = [
        "So what happens when you multiply both sides by 2?",
        "Well let's think about what division means here.",
        "Hmm not quite. Let's double check that step.",
        "That gives 4 so what does that tell you about x?",
        "Let's think about the square root of 9. What do you think?",
        "That's right! Now what would the next step be?",
        "Close! Let's double-check that step together.",
        "Actually remember that a squared number is always positive.",
    ]

    print(f"NATURAL_PAUSES={NATURAL_PAUSES}  UX_WARMTH={UX_WARMTH}\n")
    for s in samples:
        out = style_speech(s)
        changed = " *" if out != s else ""
        print(f"  IN : {s}")
        print(f"  OUT: {out}{changed}")
        print()
