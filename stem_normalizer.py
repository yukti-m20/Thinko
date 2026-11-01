"""
stem_normalizer.py — High-precision, deterministic STEM display formatter.

Translates spoken math, chemistry, and physical units into clean representations
for the 1.3" OLED display (Unicode) and the Parent Web Dashboard (LaTeX).

Crucial rule:
Always keeps the original transcript. Only applies substitutions when patterns
are explicit and unambiguous, avoiding accidental replacement in casual speech.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

# Unicode exponent mappings
_EXPONENTS: dict[str, str] = {
    "0": "⁰", "1": "¹", "2": "²", "3": "³", "4": "⁴",
    "5": "⁵", "6": "⁶", "7": "⁷", "8": "⁸", "9": "⁹",
    "+": "⁺", "-": "⁻", "n": "ⁿ", "x": "ˣ",
}

# Unicode subscript mappings
_SUBSCRIPTS: dict[str, str] = {
    "0": "₀", "1": "₁", "2": "₂", "3": "₃", "4": "₄",
    "5": "₅", "6": "₆", "7": "₇", "8": "₈", "9": "₉",
    "+": "₊", "-": "₋",
}

# High-confidence chemical expressions (spoken -> OLED Unicode)
_EXPLICIT_CHEM_SPOKEN: list[tuple[re.Pattern, str, str]] = [
    # (regex pattern, OLED unicode, LaTeX)
    (re.compile(r"\b(?:H\s*two\s*O|h\s*2\s*o)\b", re.I), "H₂O", r"\text{H}_2\text{O}"),
    (re.compile(r"\b(?:C\s*O\s*two|c\s*o\s*2)\b", re.I), "CO₂", r"\text{CO}_2"),
    (re.compile(r"\b(?:O\s*two|o\s*2)\b", re.I), "O₂", r"\text{O}_2"),
    (re.compile(r"\b(?:H\s*two|h\s*2)\b", re.I), "H₂", r"\text{H}_2"),
    (re.compile(r"\b(?:N\s*two|n\s*2)\b", re.I), "N₂", r"\text{N}_2"),
    (re.compile(r"\b(?:N\s*a\s*C\s*l|sodium\s+chloride)\b", re.I), "NaCl", r"\text{NaCl}"),
    (re.compile(r"\b(?:C\s*H\s*four|methane)\b", re.I), "CH₄", r"\text{CH}_4"),
    (re.compile(r"\b(?:H\s*two\s*S\s*O\s*four|sulfuric\s+acid)\b", re.I), "H₂SO₄", r"\text{H}_2\text{SO}_4"),
    (re.compile(r"\b(?:H\s*C\s*l|hydrochloric\s+acid)\b", re.I), "HCl", r"\text{HCl}"),
]

# Physical units
_EXPLICIT_UNITS: list[tuple[re.Pattern, str, str]] = [
    (re.compile(r"\bmeters?\s+per\s+second\s+squared\b", re.I), "m/s²", r"\text{m/s}^2"),
    (re.compile(r"\bmeters?\s+per\s+second\b", re.I), "m/s", r"\text{m/s}"),
    (re.compile(r"\bkilometers?\s+per\s+hour\b", re.I), "km/h", r"\text{km/h}"),
    (re.compile(r"\b(?:degrees?\s+celsius|degree\s+c)\b", re.I), "°C", r"^\circ\text{C}"),
    (re.compile(r"\b(?:degrees?\s+fahrenheit|degree\s+f)\b", re.I), "°F", r"^\circ\text{F}"),
    (re.compile(r"\bcentimeters?\s+cubed\b", re.I), "cm³", r"\text{cm}^3"),
    (re.compile(r"\bcentimeters?\s+squared\b", re.I), "cm²", r"\text{cm}^2"),
]


_WORD_TO_DIGIT: dict[str, str] = {
    "zero": "0", "one": "1", "two": "2", "three": "3", "four": "4",
    "five": "5", "six": "6", "seven": "7", "eight": "8", "nine": "9", "ten": "10",
}


@dataclass(slots=True)
class STEMDisplay:
    raw: str
    oled: str
    latex: str
    has_stem: bool = False


def normalize_stem(text: str) -> STEMDisplay:
    """
    Format spoken transcript for OLED and Dashboard.
    Always maintains original raw text and only modifies when clear patterns match.
    """
    if not text:
        return STEMDisplay(raw="", oled="", latex="", has_stem=False)

    oled = text
    latex = text
    found_stem = False

    # 1. Chemical formulas
    for pattern, oled_sub, latex_sub in _EXPLICIT_CHEM_SPOKEN:
        if pattern.search(oled):
            found_stem = True
            oled = pattern.sub(oled_sub, oled)
            # Use lambda to prevent re.sub from treating \t as an escape code
            latex = pattern.sub(lambda _: latex_sub, latex)

    # 2. Units
    for pattern, oled_sub, latex_sub in _EXPLICIT_UNITS:
        if pattern.search(oled):
            found_stem = True
            oled = pattern.sub(oled_sub, oled)
            latex = pattern.sub(lambda _: latex_sub, latex)

    # 3. Powers: e.g. "x squared", "3 cubed", "y to the power of 4"
    power_sq = re.compile(r"\b([a-zA-Z0-9]+)\s+squared\b", re.I)
    if power_sq.search(oled):
        found_stem = True
        oled = power_sq.sub(r"\1²", oled)
        latex = power_sq.sub(r"\1^2", latex)

    power_cb = re.compile(r"\b([a-zA-Z0-9]+)\s+cubed\b", re.I)
    if power_cb.search(oled):
        found_stem = True
        oled = power_cb.sub(r"\1³", oled)
        latex = power_cb.sub(r"\1^3", latex)

    power_n = re.compile(r"\b([a-zA-Z0-9]+)\s+to\s+the\s+power\s+of\s+([a-zA-Z0-9]+)\b", re.I)
    def _sub_pow_oled(m):
        base, exp = m.group(1), m.group(2).lower()
        base = _WORD_TO_DIGIT.get(base.lower(), base)
        exp = _WORD_TO_DIGIT.get(exp, exp)
        exp_unicode = "".join(_EXPONENTS.get(c, c) for c in exp)
        return f"{base}{exp_unicode}"

    def _sub_pow_latex(m):
        base, exp = m.group(1), m.group(2).lower()
        base = _WORD_TO_DIGIT.get(base.lower(), base)
        exp = _WORD_TO_DIGIT.get(exp, exp)
        return f"{base}^{{{exp}}}"

    if power_n.search(oled):
        found_stem = True
        oled = power_n.sub(_sub_pow_oled, oled)
        latex = power_n.sub(_sub_pow_latex, latex)

    # 4. Roots: "square root of x" -> "√x"
    sqrt_pat = re.compile(r"\b(?:the\s+)?square\s+root\s+of\s+([a-zA-Z0-9]+)\b", re.I)
    if sqrt_pat.search(oled):
        found_stem = True
        oled = sqrt_pat.sub(r"√\1", oled)
        latex = sqrt_pat.sub(r"\\sqrt{\1}", latex)

    # 5. Pi symbol: "pi r squared" -> "πr²"
    pi_pat = re.compile(r"\bpi\s+r\s+squared\b", re.I)
    if pi_pat.search(oled):
        found_stem = True
        oled = pi_pat.sub("πr²", oled)
        latex = pi_pat.sub(r"\pi r^2", latex)

    # 6. Basic arithmetic symbols when spoken in equations
    eq_pat = re.compile(r"\bplus\b", re.I)
    # Only replace "plus", "minus", "equals" if surrounded by digits or variables
    oled = re.sub(r"(?<=[a-zA-Z0-9])\s+plus\s+(?=[a-zA-Z0-9])", " + ", oled)
    oled = re.sub(r"(?<=[a-zA-Z0-9])\s+minus\s+(?=[a-zA-Z0-9])", " - ", oled)
    oled = re.sub(r"(?<=[a-zA-Z0-9])\s+equals\s+(?=[a-zA-Z0-9])", " = ", oled)
    oled = re.sub(r"(?<=[a-zA-Z0-9])\s+times\s+(?=[a-zA-Z0-9])", " × ", oled)

    # Clean double spaces
    oled = re.sub(r"\s{2,}", " ", oled).strip()
    latex = re.sub(r"\s{2,}", " ", latex).strip()

    return STEMDisplay(raw=text, oled=oled, latex=latex, has_stem=found_stem)
