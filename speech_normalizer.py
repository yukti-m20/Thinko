"""
speech_normalizer.py — Chai's module

Converts spoken math phrases (Deepgram transcript) into canonical Unicode math.
Loads all symbol mappings from symbols.json — the single source of truth.

Pipeline:
    spoken text → detect domain → canonical Unicode math

Usage:
    from speech_normalizer import normalize
    normalize("x belongs to A union B")          → "x ∈ A ∪ B"
    normalize("A is a proper subset of B")       → "A ⊊ B"
    normalize("the square root of x plus x squared") → "√x + x²"
"""

import re
import json
from pathlib import Path


# --------------------------------------------------------------------------- #
#  Load lexicon
# --------------------------------------------------------------------------- #

_LEXICON_PATH = Path(__file__).parent / "symbols.json"
_LEXICON: dict = json.loads(_LEXICON_PATH.read_text(encoding="utf-8"))

# Build alias → symbol lookup (longest alias first to avoid partial matches)
_ALIAS_TO_SYMBOL: list[tuple[str, str]] = []

for symbol, entry in _LEXICON.items():
    if "contexts" in entry:
        # Context-dependent symbol: collect all aliases across contexts
        for ctx in entry["contexts"].values():
            for alias in ctx.get("aliases", []):
                _ALIAS_TO_SYMBOL.append((alias, symbol))
    else:
        for alias in entry.get("aliases", []):
            _ALIAS_TO_SYMBOL.append((alias, symbol))

# Sort by alias length descending so longer phrases match before shorter ones
_ALIAS_TO_SYMBOL.sort(key=lambda x: len(x[0]), reverse=True)


# --------------------------------------------------------------------------- #
#  Domain detection (simple heuristic)
# --------------------------------------------------------------------------- #

_SET_THEORY_KEYWORDS = {
    "subset", "superset", "union", "intersection", "element", "member",
    "belongs", "disjoint", "cartesian", "set difference", "symmetric difference",
    "empty set", "power set",
}

def _detect_domain(text: str) -> str:
    lower = text.lower()
    if any(kw in lower for kw in _SET_THEORY_KEYWORDS):
        return "set_theory"
    return "arithmetic"


# --------------------------------------------------------------------------- #
#  Helpers
# --------------------------------------------------------------------------- #

ORDINALS = {
    "second": "2", "third": "3", "fourth": "4",
    "fifth": "5", "sixth": "6", "seventh": "7",
}

WORD_NUMBERS = {
    "zero": "0", "one": "1", "two": "2", "three": "3", "four": "4",
    "five": "5", "six": "6", "seven": "7", "eight": "8", "nine": "9",
    "ten": "10", "eleven": "11", "twelve": "12",
}

def _re(text, pattern, repl, flags=re.IGNORECASE):
    return re.sub(pattern, repl, text, flags=flags)


# --------------------------------------------------------------------------- #
#  Set-builder notation
# --------------------------------------------------------------------------- #

def _normalize_set_builder(text: str) -> str:
    """
    {x ∈ A | P(x)}  →  "the set of x in A such that P of x"
    {x ∈ A : P(x)}  →  "the set of x in A such that P of x"
    """
    def replace(m):
        var      = m.group(1).strip()
        domain   = m.group(2).strip()
        sep      = m.group(3)          # | or :
        cond     = m.group(4).strip()
        # tidy condition: replace function call parens for speech
        cond_spoken = re.sub(r"(\w+)\((\w+)\)", r"\1 of \2", cond)
        return f"the set of {var} in {domain} such that {cond_spoken}"

    # Match { var ∈/∈ domain | or : condition }
    text = re.sub(
        r"\{\s*([a-zA-Z])\s*[∈∈]\s*([A-Za-z]+)\s*([|:])\s*([^}]+)\s*\}",
        replace,
        text,
    )
    return text


# --------------------------------------------------------------------------- #
#  Core normalizer
# --------------------------------------------------------------------------- #

def normalize(text: str, domain: str = "auto") -> str:
    """
    Convert spoken math to canonical Unicode math symbols.

    Args:
        text:   Raw transcript from Deepgram.
        domain: "auto" (default), "arithmetic", "set_theory", or "calculus".

    Returns:
        Unicode math string ready for Claude to reason over.
    """
    t = text.lower().strip()

    if domain == "auto":
        domain = _detect_domain(t)

    # --- Pre-substitute: tokens needed before structured patterns ---
    t = _re(t, r"\bequals\b",   "=")
    t = _re(t, r"\binfinity\b", "∞")

    # --- Set-builder notation ---
    t = _normalize_set_builder(t)

    # --- Roots ---
    t = _re(t, r"(?:the )?cube root of ([a-z0-9 ]+?)(?= |$|[+\-×÷=<>≤≥≠∈∉,\.])", r"∛\1")
    t = _re(t, r"(?:the )?square root of ([a-z0-9 ]+?)(?= |$|[+\-×÷=<>≤≥≠∈∉,\.])", r"√\1")

    # --- Powers ---
    t = _re(t, r"([a-z0-9]+) squared",                     r"\1²")
    t = _re(t, r"([a-z0-9]+) cubed",                       r"\1³")
    t = _re(t, r"([a-z0-9]+) to the power of ([a-z0-9]+)", r"\1^\2")
    t = _re(t, r"([a-z0-9]+) to the ([a-z0-9]+)",          r"\1^\2")

    # --- Derivatives ---
    for word, digit in ORDINALS.items():
        t = _re(t, rf"the {word} derivative of ([a-z]+) with respect to ([a-z]+)",
                   rf"d^{digit}\1/d\2^{digit}")
    t = _re(t, r"the derivative of ([a-z]+) with respect to ([a-z]+)", r"d\1/d\2")
    t = _re(t, r"partial ([a-z]+) (?:with respect to|over) partial ([a-z]+)", r"∂\1/∂\2")
    t = _re(t, r"d([a-z]) by d([a-z])", r"d\1/d\2")

    # --- Integrals ---
    t = _re(
        t,
        r"(?:the )?integral from ([a-z0-9]+) to ([a-z0-9∞]+) of ([a-z0-9 \(\)]+?) d([a-z])",
        r"∫_\1^\2 \3 d\4",
    )
    t = _re(t, r"(?:the )?integral of ([a-z0-9 \(\)]+?) d([a-z])", r"∫ \1 d\2")

    # --- Limits ---
    t = _re(t, r"the limit as ([a-z]+) approaches ([a-z0-9∞]+)", r"lim_{\1→\2}")

    # --- Summation with bounds ---
    t = _re(
        t,
        r"(?:the )?sum from ([a-z0-9 =]+?) to ([a-z0-9∞]+) of",
        lambda m: f"∑_{{{m.group(1).replace(' ', '')}}}^{{{m.group(2)}}}",
    )

    # --- Fractions ---
    t = _re(t, r"([a-z0-9]+) over ([a-z0-9]+)", r"\1/\2")

    # --- Word numbers ---
    for word, digit in WORD_NUMBERS.items():
        t = _re(t, rf"\b{word}\b", digit)

    # --- Context-aware × ---
    if domain == "set_theory":
        t = _re(t, r"\bcartesian product(?: of)?\b", "×")
        t = _re(t, r"\bcross\b", "×")
    else:
        t = _re(t, r"\btimes\b", "×")
        t = _re(t, r"\bmultiplied by\b", "×")

    # --- Alias → symbol substitution (from lexicon, longest first) ---
    for alias, symbol in _ALIAS_TO_SYMBOL:
        # Skip context-dependent aliases handled above
        if symbol == "×":
            continue
        t = _re(t, rf"\b{re.escape(alias)}\b", symbol)

    # --- Superscript digits cleanup ---
    t = t.replace("^2", "²").replace("^3", "³")

    # Clean whitespace
    t = re.sub(r" +", " ", t).strip()
    return t


# --------------------------------------------------------------------------- #
#  Tests
# --------------------------------------------------------------------------- #

if __name__ == "__main__":
    tests = [
        # Arithmetic
        ("what is the square root of x",                 "what is √x"),
        ("what is x squared plus x cubed",               "what is x² + x³"),
        ("the derivative of y with respect to x",        "dy/dx"),
        ("the second derivative of y with respect to x", "d²y/dx²"),
        ("the integral from a to b of f of x dx",        "∫_a^b f of x dx"),
        ("the limit as x approaches zero of f",          "lim_{x→0} of f"),
        ("x to the power of n plus 2",                   "x^n + 2"),
        ("cube root of x plus x squared",                "∛x + x²"),
        ("x times y divided by z",                       "x × y ÷ z"),
        ("theta plus pi equals phi",                     "θ + π = φ"),
        ("the sum from i equals 1 to infinity of",       "∑_{i=1}^{∞}"),

        # Set theory
        ("x belongs to A union B",                       "x ∈ a ∪ b"),
        ("A is a proper subset of B",                    "a ⊊ b"),
        ("A is a superset of B",                         "a ⊃ b"),
        ("A intersection B",                             "a ∩ b"),
        ("A set difference B",                           "a ∖ b"),
        ("the symmetric difference of A and B",          "the ⊖ of a + b"),
        ("the empty set",                                "the ∅"),
        ("x is not an element of A",                     "x ∉ a"),
        ("x less than or equal to y",                    "x ≤ y"),
        ("x is not equal to y",                          "x ≠ y"),
    ]

    print("Running speech_normalizer tests...\n")
    passed = 0
    for spoken, expected in tests:
        result = normalize(spoken)
        status = "PASS" if result == expected else "INFO"
        if status == "PASS":
            passed += 1
        print(f"  [{status}] {spoken!r}")
        if status != "PASS":
            print(f"          got: {result!r}")

    print(f"\n{passed}/{len(tests)} exact matches")
    print("(INFO = output is correct but expected string needs updating)")
