"""
chem_normalizer.py — Chai's module

Two-direction chemistry text processor, driven by chem_symbols.json.

  normalize(text) — spoken chemistry → canonical notation  (STT → LLM)
  render(text)    — canonical notation → speakable English  (LLM → TTS)

Usage:
    from chem_normalizer import normalize, render

    normalize("water reacts with carbon dioxide")  → "H₂O + CO₂"
    normalize("hydrogen gas yields water")         → "H₂ → H₂O"
    render("H₂O")                                  → "water"
    render("2H₂ + O₂ → 2H₂O")                    → "2 H 2 plus O 2 yields 2 H 2 O"
    render("Ca²⁺ + 2Cl⁻")                         → "calcium 2 plus ion plus 2 chloride ion"
    render("CaCO₃ ⇌ CaO + CO₂")                  → "calcium carbonate is in equilibrium with Ca O plus carbon dioxide"
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

# --------------------------------------------------------------------------- #
#  Load lexicon
# --------------------------------------------------------------------------- #

_LEXICON_PATH = Path(__file__).parent / "chem_symbols.json"
_LEXICON: dict[str, Any] = json.loads(_LEXICON_PATH.read_text(encoding="utf-8"))

_ELEMENTS:     dict[str, Any] = _LEXICON["elements"]
_COMPOUNDS:    dict[str, Any] = _LEXICON["compounds"]
_RXNSYMBOLS:   dict[str, Any] = _LEXICON["reaction_symbols"]
_STATES:       dict[str, Any] = _LEXICON["states"]
_IONS:         dict[str, Any] = _LEXICON["ions"]
_SUBSCRIPTS:   dict[str, str] = _LEXICON["subscripts"]
_SUPERSCRIPTS: dict[str, str] = _LEXICON["superscripts"]
_ENERGY:       dict[str, Any] = _LEXICON["energy_terms"]
_CONC_UNITS:   dict[str, Any] = _LEXICON["concentration_units"]

# Subscript/superscript translation tables
_SUB_TABLE  = str.maketrans(_SUBSCRIPTS)
_SUPER_TABLE = str.maketrans({k: v for k, v in _SUPERSCRIPTS.items() if k not in ("⁺", "⁻")})


# --------------------------------------------------------------------------- #
#  Build alias lookup tables  (normalize direction: spoken → formula)
# --------------------------------------------------------------------------- #

# Compound aliases: "water" → "H₂O",  sorted longest first
_SPOKEN_TO_COMPOUND: list[tuple[str, str]] = []
for formula, entry in _COMPOUNDS.items():
    for alias in entry.get("aliases", []):
        _SPOKEN_TO_COMPOUND.append((alias.lower(), formula))
_SPOKEN_TO_COMPOUND.sort(key=lambda x: len(x[0]), reverse=True)

# Ion aliases: "hydroxide" → "OH⁻"
_SPOKEN_TO_ION: list[tuple[str, str]] = []
for ion, entry in _IONS.items():
    for alias in entry.get("aliases", []):
        _SPOKEN_TO_ION.append((alias.lower(), ion))
_SPOKEN_TO_ION.sort(key=lambda x: len(x[0]), reverse=True)

# Element name → symbol: "hydrogen" → "H"
_ELEMENT_NAME_TO_SYM: dict[str, str] = {
    entry["name"].lower(): sym for sym, entry in _ELEMENTS.items()
}

# Reaction symbol aliases: "yields" → "→"
_SPOKEN_TO_RXNSYM: list[tuple[str, str]] = []
for sym, entry in _RXNSYMBOLS.items():
    if sym == "+":   # keep "plus" as-is; avoid clobbering arithmetic
        continue
    for alias in entry.get("aliases", []):
        _SPOKEN_TO_RXNSYM.append((alias.lower(), sym))
_SPOKEN_TO_RXNSYM.sort(key=lambda x: len(x[0]), reverse=True)

# State aliases: "dissolved" → "(aq)"
_SPOKEN_TO_STATE: list[tuple[str, str]] = []
for state, entry in _STATES.items():
    for alias in entry.get("aliases", []):
        _SPOKEN_TO_STATE.append((alias.lower(), state))
_SPOKEN_TO_STATE.sort(key=lambda x: len(x[0]), reverse=True)


# --------------------------------------------------------------------------- #
#  Helpers shared by both directions
# --------------------------------------------------------------------------- #

def _strip_subscripts(text: str) -> str:
    """Replace Unicode subscript digits with plain digits."""
    return text.translate(_SUB_TABLE)


def _strip_superscript_digits(text: str) -> str:
    """Replace Unicode superscript digits (not ⁺/⁻) with plain digits."""
    return text.translate(_SUPER_TABLE)


def _is_chemical_context(text: str) -> bool:
    """Heuristic: does this text likely contain chemistry?"""
    lower = text.lower()
    chem_keywords = {
        "react", "yield", "product", "reagent", "mole", "acid", "base",
        "salt", "ion", "oxide", "compound", "element", "formula", "equation",
        "aqueous", "precipitate", "catalyst", "equilibrium", "enthalpy",
        "dissolved", "solution", "concentration",
    }
    # Also true if any element symbol appears (2+ chars prevents false hits on I/C)
    has_element = bool(re.search(r"\b(?:H₂O|CO₂|NaCl|NH₃|CH₄|H₂SO₄|HCl|NaOH)\b", text))
    return has_element or any(kw in lower for kw in chem_keywords)


# --------------------------------------------------------------------------- #
#  normalize — spoken text → canonical chemistry notation  (STT → LLM)
# --------------------------------------------------------------------------- #

def normalize(text: str) -> str:
    """
    Convert spoken chemistry phrases to canonical notation for the LLM.

    "water plus carbon dioxide"      → "H₂O + CO₂"
    "sodium chloride dissolves"      → "NaCl (aq)"
    "calcium carbonate yields"       → "CaCO₃ →"
    "H 2 plus O 2 yields H 2 O"     → "H₂ + O₂ → H₂O"

    Leaves non-chemistry text unchanged.
    """
    t = text.strip()

    # 1. Reaction symbol phrases ("yields", "in equilibrium with", etc.)
    for alias, sym in _SPOKEN_TO_RXNSYM:
        t = re.sub(rf"\b{re.escape(alias)}\b", f" {sym} ", t, flags=re.IGNORECASE)

    # 2. Known compound names → formulas (longest first)
    for alias, formula in _SPOKEN_TO_COMPOUND:
        t = re.sub(rf"\b{re.escape(alias)}\b", formula, t, flags=re.IGNORECASE)

    # 3. Ion names → notation
    for alias, ion in _SPOKEN_TO_ION:
        t = re.sub(rf"\b{re.escape(alias)}\b", ion, t, flags=re.IGNORECASE)

    # 4. State labels: "aqueous" → (aq), "solid" → (s), etc.
    for alias, state in _SPOKEN_TO_STATE:
        t = re.sub(rf"\b{re.escape(alias)}\b", f" {state} ", t, flags=re.IGNORECASE)

    # 5. Spoken formula letters: "H 2 O" → "H₂O"
    #    Pattern: uppercase letter(s) followed by a digit word
    def _glue_spoken_formula(m: re.Match) -> str:
        elem = m.group(1)
        num  = m.group(2)
        sub  = "₀₁₂₃₄₅₆₇₈₉"[int(num)]
        return f"{elem}{sub}"

    t = re.sub(r"\b([A-Z][a-z]?)\s+([2-9])\b", _glue_spoken_formula, t)

    # 6. Element names → symbols (only when isolated, not inside a larger word)
    for name, sym in sorted(_ELEMENT_NAME_TO_SYM.items(), key=lambda x: len(x[0]), reverse=True):
        t = re.sub(rf"\b{re.escape(name)}\b", sym, t, flags=re.IGNORECASE)

    # 7. Energy / equilibrium spoken terms
    for sym, entry in _ENERGY.items():
        for alias in entry.get("aliases", []):
            t = re.sub(rf"\b{re.escape(alias)}\b", sym, t, flags=re.IGNORECASE)

    # 8. Convert "plus" between chemical tokens to "+"
    t = re.sub(r"(?<=[A-Za-z₀-₉⁰-⁹\d\)])\s+plus\s+(?=[A-Z\d])", " + ", t)

    # Clean up extra whitespace
    t = re.sub(r" {2,}", " ", t).strip()
    return t


# --------------------------------------------------------------------------- #
#  render — canonical notation → speakable English  (LLM → TTS)
# --------------------------------------------------------------------------- #

def _render_formula_token(token: str, mode: str = "normal") -> str:
    """
    Render a single chemical formula or ion to spoken English.

    H₂O   → "water"       (compound lookup)
    Ca²⁺  → "calcium 2 plus ion"
    SO₄²⁻ → "S O 4 2 minus ion"
    Fe₂O₃ → "Fe 2 O 3"
    """
    # Ion lookup (try exact match first, including superscripts)
    if token in _IONS:
        return _IONS[token]["tts"][mode] if mode in _IONS[token].get("tts", {}) else _IONS[token]["tts"]["normal"]

    # Compound lookup
    if token in _COMPOUNDS:
        entry = _COMPOUNDS[token]
        tts_key = mode if mode in entry.get("tts", {}) else "normal"
        return entry["tts"][tts_key]

    # Generic formula parse: convert subscript/superscript then split into tokens
    plain = _strip_subscripts(token)

    # Handle charge notation: ²⁺ → "2 plus", ⁻ → "minus", ²⁻ → "2 minus"
    charge_match = re.search(r"([⁰¹²³⁴⁵⁶⁷⁸⁹]*)([⁺⁻])$", token)
    charge_spoken = ""
    if charge_match:
        charge_digits = charge_match.group(1).translate(_SUPER_TABLE)
        charge_sign   = "plus" if charge_match.group(2) == "⁺" else "minus"
        charge_spoken = f" {charge_digits} {charge_sign}" if charge_digits else f" {charge_sign}"
        plain = _strip_subscripts(token[:charge_match.start()])

    # Tokenize: element symbols and their counts
    parts = re.findall(r"[A-Z][a-z]?|\d+", plain)
    spoken_parts = []
    for part in parts:
        if part.isdigit():
            spoken_parts.append(part)
        elif part in _ELEMENTS:
            spoken_parts.append(part)  # keep symbol as-is; TTS reads it letter by letter
        else:
            spoken_parts.append(part)

    return (" ".join(spoken_parts) + charge_spoken + (" ion" if charge_spoken else "")).strip()


def render(text: str, mode: str = "normal") -> str:
    """
    Convert chemical notation in text to speakable English for TTS.

    "H₂O"                → "water"
    "Ca²⁺"               → "calcium 2 plus ion"
    "2H₂ + O₂ → 2H₂O"   → "2 H 2 plus O 2 yields 2 H 2 O"
    "CaCO₃ ⇌ CaO + CO₂" → "calcium carbonate is in equilibrium with Ca O plus carbon dioxide"
    "ΔH = -286 kJ/mol"   → "delta H equals negative 286 kilojoules per mole"
    """
    t = text

    # 1. State symbols: (aq) → "aqueous" etc.
    for state, entry in _STATES.items():
        tts = entry["tts"][mode] if mode in entry.get("tts", {}) else entry["tts"]["normal"]
        t = t.replace(state, f" {tts} ")

    # 2. Reaction symbols
    for sym, entry in _RXNSYMBOLS.items():
        if sym == "+":
            continue
        tts = entry["tts"][mode] if mode in entry.get("tts", {}) else entry["tts"]["normal"]
        t = t.replace(sym, f" {tts} ")

    # 3. Energy / equilibrium terms (ΔH, Kc, pH …)
    for sym, entry in _ENERGY.items():
        tts = entry["tts"][mode] if mode in entry.get("tts", {}) else entry["tts"]["normal"]
        t = re.sub(re.escape(sym), f" {tts} ", t)

    # 4. Concentration units
    for unit, entry in _CONC_UNITS.items():
        t = re.sub(re.escape(unit), f" {entry['tts']} ", t)

    # 5. Replace known ions (longest first, before compound parse strips chars)
    for ion in sorted(_IONS, key=len, reverse=True):
        if ion in t:
            spoken = _render_formula_token(ion, mode)
            t = t.replace(ion, f" {spoken} ")

    # 6. Replace known compound formulas (longest first)
    # Prefer "casual" (common name) for speech output — "water" not "H 2 O"
    for formula in sorted(_COMPOUNDS, key=len, reverse=True):
        if formula in t:
            entry = _COMPOUNDS[formula]
            tts = entry.get("tts", {})
            spoken = tts.get("casual") or tts.get(mode) or tts.get("normal", formula)
            t = t.replace(formula, f" {spoken} ")

    # 7. Remaining formula tokens: optional coefficient + element sequence with subscripts
    #    e.g. "2H₂" → "2 H 2",  "Fe₂O₃" → "Fe 2 O 3"
    def _render_remaining(m: re.Match) -> str:
        coeff  = m.group(1) or ""
        body   = m.group(2)
        spoken = _render_formula_token(body, mode)
        return f" {coeff} {spoken} ".strip() if coeff else f" {spoken} "

    # Only match tokens that contain at least one subscript/superscript Unicode character.
    # This prevents mangling normal English words like "Let", "First", "What"
    # which are capitalized but are NOT chemical formulas.
    t = re.sub(
        r"(\d*)"                                         # optional leading coefficient
        r"([A-Z][a-zA-Z]*[₀-₉⁰-⁹⁺⁻][a-zA-Z₀-₉⁰-⁹⁺⁻]*)",  # must contain sub/superscript
        _render_remaining,
        t,
    )

    # 8. Replace lone "+" between chemical species with "plus"
    t = re.sub(r"(?<=\w)\s*\+\s*(?=\w)", " plus ", t)

    # 9. Clean whitespace and punctuation
    t = re.sub(r" {2,}", " ", t).strip()
    return t


# --------------------------------------------------------------------------- #
#  Quick self-test
# --------------------------------------------------------------------------- #

if __name__ == "__main__":
    normalize_cases = [
        ("water",                             "H₂O"),
        ("carbon dioxide",                    "CO₂"),
        ("hydrogen gas yields water",         "H₂ → H₂O"),
        ("sodium chloride",                   "NaCl"),
        ("sulfuric acid",                     "H₂SO₄"),
        ("calcium carbonate in equilibrium",  "CaCO₃ ⇌"),
        ("H 2 plus O 2",                      "H₂ + O₂"),
    ]

    render_cases = [
        ("H₂O",                  "water"),
        ("CO₂",                  "carbon dioxide"),
        ("NaCl",                 "sodium chloride"),
        ("Ca²⁺",                 "calcium 2 plus ion"),
        ("H₂SO₄",                "sulfuric acid"),
        ("2H₂ + O₂ → 2H₂O",     "2 H 2 plus O 2 yields 2 water"),
        ("CaCO₃ ⇌ CaO + CO₂",   "calcium carbonate is in equilibrium with calcium oxide plus carbon dioxide"),
        ("Fe₂O₃",                "iron oxide"),
    ]

    print("=== normalize (spoken → notation) ===")
    for spoken, expected in normalize_cases:
        result = normalize(spoken)
        status = "PASS" if expected in result else "INFO"
        print(f"  [{status}] {spoken!r}")
        if status != "PASS":
            print(f"          expected: {expected!r}")
            print(f"          got:      {result!r}")

    print("\n=== render (notation → spoken) ===")
    for formula, expected in render_cases:
        result = render(formula)
        status = "PASS" if expected.lower() in result.lower() else "INFO"
        print(f"  [{status}] {formula!r} → {result!r}")
        if status != "PASS":
            print(f"          expected: {expected!r}")
