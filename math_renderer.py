"""Turn common mathematical notation in an LLM response into speech text."""

from __future__ import annotations

import re
import json
from pathlib import Path
from typing import Any


_SYMBOLS_PATH = Path(__file__).with_name("symbols.json")


def _load_symbols() -> dict[str, dict[str, Any]]:
	with _SYMBOLS_PATH.open(encoding="utf-8") as symbols_file:
		return json.load(symbols_file)


_SYMBOLS = _load_symbols()
_LATEX_TO_SPOKEN = {
	entry["latex"]: entry["tts"]["normal"]
	for entry in _SYMBOLS.values()
	if entry.get("latex") and entry.get("tts", {}).get("normal")
}


def _strip_math_delimiters(text: str) -> str:
	text = re.sub(r"\\\[(.*?)\\\]", r"\1", text, flags=re.DOTALL)
	text = re.sub(r"\\\((.*?)\\\)", r"\1", text, flags=re.DOTALL)
	text = re.sub(r"\$\$(.*?)\$\$", r"\1", text, flags=re.DOTALL)
	return re.sub(r"\$(.*?)\$", r"\1", text, flags=re.DOTALL)


def _replace_latex_commands(text: str) -> str:
	text = re.sub(r"\\frac\s*\{([^{}]+)\}\s*\{([^{}]+)\}", r"the fraction \1 over \2", text)
	text = re.sub(r"\\sqrt\s*\[([^]]+)\]\s*\{([^{}]+)\}", r"the \1 root of \2", text)
	text = re.sub(r"\\sqrt\s*\{([^{}]+)\}", r"the square root of \1", text)
	text = re.sub(r"\\cbrt\s*\{([^{}]+)\}", r"the cube root of \1", text)
	text = re.sub(r"\\int\s*_\{?([^_{}^ ]+)\}?\s*\^\{?([^{} ]+)\}?", r"the integral from \1 to \2 of", text)
	text = re.sub(r"\\lim\s*_\{?([^{}]+)\}?", r"the limit as \1", text)
	text = re.sub(
		r"\\([A-Za-z]+)",
		lambda match: _LATEX_TO_SPOKEN.get("\\" + match.group(1), match.group(1)),
		text,
	)
	return text


def _replace_symbols(text: str) -> str:
	for symbol, entry in sorted(_SYMBOLS.items(), key=lambda item: len(item[0]), reverse=True):
		spoken = entry.get("tts", {}).get("normal")
		if spoken:
			if symbol == "!":
				text = re.sub(r"(?<=[0-9)\]])!", f" {spoken} ", text)
			else:
				text = text.replace(symbol, f" {spoken} ")
	return text


def _replace_ascii_operators(text: str) -> str:
	text = re.sub(r"(?<=\d)\s*\*\s*(?=[A-Za-z0-9(])", " times ", text)
	text = re.sub(r"(?<=\w)\s+\*\s+(?=\w)", " times ", text)
	text = re.sub(r"(?<=\d)\s*/\s*(?=[A-Za-z0-9(])", " divided by ", text)
	text = re.sub(r"(?<=\w)\s+/\s+(?=\w)", " divided by ", text)
	return text


_SUPERSCRIPT_MAP = str.maketrans("⁰¹²³⁴⁵⁶⁷⁸⁹", "0123456789")

def _normalize_superscripts(text: str) -> str:
	"""Convert Unicode superscript digits (e.g. 5²) to caret notation (5^2)."""
	result = []
	i = 0
	while i < len(text):
		ch = text[i]
		if ch in "⁰¹²³⁴⁵⁶⁷⁸⁹":
			# Collect consecutive superscript digits
			sup = ""
			while i < len(text) and text[i] in "⁰¹²³⁴⁵⁶⁷⁸⁹":
				sup += text[i].translate(_SUPERSCRIPT_MAP)
				i += 1
			result.append(f"^{sup}")
		else:
			result.append(ch)
			i += 1
	return "".join(result)


def _replace_structured_notation(text: str) -> str:
	# Space between coefficient and variable: 2x → 2 x, 3y² → 3 y², etc.
	# Exclude scientific notation: 3.14e10 stays intact.
	text = re.sub(r"(?<=[0-9])(?=[A-DF-Za-df-z]|[Ee](?![0-9+-]))", " ", text)
	text = re.sub(
		r"d\^\s*2\s*([A-Za-z])\s*/\s*d([A-Za-z])\^\s*2",
		r"the second derivative of \1 with respect to \2",
		text,
		flags=re.IGNORECASE,
	)
	text = re.sub(
		r"d([A-Za-z])\s*/\s*d([A-Za-z])",
		r"the derivative of \1 with respect to \2",
		text,
		flags=re.IGNORECASE,
	)
	text = re.sub(r"\b(?:int|∫)_?([^\s^]+)\^([^\s]+)", r"the integral from \1 to \2 of", text)
	text = re.sub(r"\blim\s*\(?([A-Za-z])\s*(?:->|→)\s*([^),]+)\)?", r"the limit as \1 approaches \2", text)
	text = re.sub(r"\bsqrt\s*\(([^()]+)\)", r"the square root of \1", text, flags=re.IGNORECASE)
	text = re.sub(r"\bcbrt\s*\(([^()]+)\)", r"the cube root of \1", text, flags=re.IGNORECASE)
	text = re.sub(r"\^\s*2\b", " squared", text)
	text = re.sub(r"\^\s*3\b", " cubed", text)
	text = re.sub(r"\^\s*([A-Za-z0-9]+)", r" to the power of \1", text)
	text = re.sub(r"(?<![A-Za-z])([0-9]+(?:\.[0-9]+)?)e([+-]?[0-9]+)\b", r"\1 times 10 to the \2", text, flags=re.IGNORECASE)
	text = text.replace("->", " approaches ").replace("→", " approaches ")
	return text


def _replace_matrices(text: str) -> str:
	def speak_matrix(match: re.Match[str]) -> str:
		rows = [row.strip() for row in match.group(1).split("],")]
		rows = [row.strip(" []") for row in rows]
		row_words = [" and ".join(value.strip() for value in row.split(",")) for row in rows]
		dimensions = f"{len(rows)} by {len(row_words[0].split(' and '))}" if row_words else "matrix"
		return f"a {dimensions} matrix, " + ", ".join(f"row {index + 1}: {values}" for index, values in enumerate(row_words))

	return re.sub(r"\[\[(.*?)\]\]", speak_matrix, text)


def _clean_for_speech(text: str) -> str:
	text = re.sub(r"[*_`#]", "", text)
	text = re.sub(r"\s+", " ", text)
	text = re.sub(r"\s+([,.;:?!])", r"\1", text)
	return text.strip()


def render_math(text: str) -> str:
	"""Render math notation inside Codex prose as natural English for TTS."""
	if not isinstance(text, str):
		raise TypeError("text must be a string")

	rendered = _strip_math_delimiters(text)
	rendered = _replace_latex_commands(rendered)
	rendered = _replace_ascii_operators(rendered)
	rendered = _replace_symbols(rendered)
	rendered = _replace_matrices(rendered)
	rendered = _normalize_superscripts(rendered)
	rendered = _replace_structured_notation(rendered)
	return _clean_for_speech(rendered)


math_to_speech = render_math


if __name__ == "__main__":
	print("Loaded", len(_SYMBOLS), "symbols from", _SYMBOLS_PATH.name)
	print(render_math(r"The set $A \subseteq B$ means every element of A is in B."))
	print(render_math(r"The value of $\pi$ is approximately 3.14."))
	print(render_math(r"The derivative of $x^2$ is $2x$."))
