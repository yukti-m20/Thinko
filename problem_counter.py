"""
problem_counter.py — Track problems solved per session and classify their subject.

    counter = ProblemCounter()
    counter.check_and_record(user_text, agent_reply)   # call after every turn
    counter.summary()   # → {"total": 3, "by_subject": {"algebra": 2, "chemistry": 1}}

Subject classification uses keyword matching first (free, instant).
If nothing matches, an optional LLM call classifies the subject from the
conversation snippet (uses OPENAI_API_KEY — only fires on ambiguous turns).
"""

from __future__ import annotations

import os
import re
from collections import Counter
from dataclasses import dataclass, field
from typing import Optional

import requests
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), ".env"), override=True)

# --------------------------------------------------------------------------- #
#  Solved detection — look for explicit confirmation phrases in agent reply
# --------------------------------------------------------------------------- #

_SOLVED_PATTERNS = re.compile(
    r"\b(?:"
    r"that(?:'s| is) (?:correct|right|exactly|spot.?on|it)"
    r"|yes[,!]? (?:that'?s?|exactly|correct|right)"
    r"|correct[!. ]"
    r"|exactly[!. ]"
    r"|you(?:'ve| have) got it"
    r"|well done"
    r"|nice(?: work| one)?"
    r"|perfect[!. ]"
    r"|nailed it"
    r"|right[!.] (?:so|now|let)"
    r")(?:\b|(?=[^a-zA-Z]))",
    re.IGNORECASE,
)


def detect_solved(agent_reply: str) -> bool:
    """
    Return True if the agent reply explicitly confirms a correct answer.
    Only fires on clear confirmation phrases — not on mid-problem encouragement.
    """
    return bool(_SOLVED_PATTERNS.search(agent_reply))


# --------------------------------------------------------------------------- #
#  Subject classification — keyword matching with LLM fallback
# --------------------------------------------------------------------------- #

_SUBJECT_KEYWORDS: list[tuple[str, list[str]]] = [
    ("algebra",    ["equation", "solve for", "factor", "quadratic", "polynomial",
                    "variable", "linear", "inequality", "expression", "simplify"]),
    ("geometry",   ["angle", "triangle", "circle", "area", "perimeter", "volume",
                    "rectangle", "polygon", "parallel", "perpendicular", "radius",
                    "diameter", "hypotenuse", "congruent", "similar"]),
    ("calculus",   ["derivative", "integral", "limit", "differentiate", "integrate",
                    "rate of change", "tangent", "slope of", "anti-derivative"]),
    ("chemistry",  ["reaction", "element", "compound", "molecule", "atom", "bond",
                    "acid", "base", "mole", "periodic", "ion", "equation",
                    "H2O", "CO2", "NaCl", "yields", "equilibrium", "aqueous"]),
    ("physics",    ["force", "velocity", "acceleration", "gravity", "mass", "energy",
                    "momentum", "friction", "newton", "weight", "kinetic", "potential",
                    "wave", "frequency", "voltage", "current", "resistance"]),
    ("biology",    ["cell", "dna", "photosynthesis", "organism", "evolution",
                    "chromosome", "gene", "mitosis", "meiosis", "protein",
                    "enzyme", "membrane", "nucleus", "ecosystem"]),
    ("arithmetic", ["fraction", "decimal", "percentage", "multiply", "divide",
                    "addition", "subtraction", "remainder", "prime", "factor",
                    "greatest common", "least common", "ratio", "proportion"]),
    ("statistics", ["mean", "median", "mode", "probability", "standard deviation",
                    "variance", "sample", "distribution", "histogram", "average"]),
]

# Pre-compile keyword patterns (word boundary, case-insensitive)
_COMPILED_SUBJECTS: list[tuple[str, list[re.Pattern]]] = [
    (subject, [re.compile(rf"\b{re.escape(kw)}\b", re.IGNORECASE) for kw in keywords])
    for subject, keywords in _SUBJECT_KEYWORDS
]


def _classify_by_keywords(text: str) -> Optional[str]:
    """Return the subject with the most keyword hits, or None if nothing matches."""
    scores: Counter = Counter()
    for subject, patterns in _COMPILED_SUBJECTS:
        for pat in patterns:
            if pat.search(text):
                scores[subject] += 1
    if not scores:
        return None
    best, count = scores.most_common(1)[0]
    return best if count >= 1 else None


def _classify_by_llm(text: str) -> str:
    """
    Fallback: ask gpt-4o-mini to classify the subject in one word.
    Returns 'general_math' on any failure to avoid blocking.
    """
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        return "general_math"
    try:
        resp = requests.post(
            "https://api.openai.com/v1/chat/completions",
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json={
                "model": "gpt-4o-mini",
                "messages": [
                    {
                        "role": "system",
                        "content": (
                            "You classify STEM problems into one subject. "
                            "Reply with exactly one word from: "
                            "algebra, geometry, calculus, chemistry, physics, "
                            "biology, arithmetic, statistics, general_math. "
                            "No explanation."
                        ),
                    },
                    {"role": "user", "content": text[:400]},
                ],
                "max_tokens": 5,
            },
            timeout=8,
        )
        resp.raise_for_status()
        word = resp.json()["choices"][0]["message"]["content"].strip().lower()
        valid = {s for s, _ in _SUBJECT_KEYWORDS} | {"general_math"}
        return word if word in valid else "general_math"
    except Exception:
        return "general_math"


def classify_subject(user_text: str, agent_reply: str = "") -> str:
    """
    Classify the STEM subject of the current problem.

    Tries keyword matching first (free). Falls back to LLM only if
    nothing matches — avoids unnecessary API calls.
    """
    combined = f"{user_text} {agent_reply}"
    result = _classify_by_keywords(combined)
    if result:
        return result
    # LLM fallback for ambiguous turns
    return _classify_by_llm(combined)


# --------------------------------------------------------------------------- #
#  ProblemCounter
# --------------------------------------------------------------------------- #

@dataclass
class Problem:
    subject: str
    user_text: str


@dataclass
class ProblemCounter:
    """
    Tracks the number of problems a student solves in a session,
    broken down by subject.

    Usage:
        counter = ProblemCounter()
        # After every agent turn:
        counter.check_and_record(user_text, agent_reply)
        # On session end:
        print(counter.summary())
    """

    problems: list[Problem] = field(default_factory=list)

    def check_and_record(self, user_text: str, agent_reply: str) -> Optional[str]:
        """
        Check if the agent just confirmed a correct answer.
        If so, classify the subject, record it, and return the subject string.
        Returns None if no problem was solved this turn.
        """
        if not detect_solved(agent_reply):
            return None
        subject = classify_subject(user_text, agent_reply)
        self.problems.append(Problem(subject=subject, user_text=user_text[:120]))
        return subject

    @property
    def total(self) -> int:
        return len(self.problems)

    @property
    def by_subject(self) -> dict[str, int]:
        counts: Counter = Counter(p.subject for p in self.problems)
        return dict(counts.most_common())

    def summary(self) -> dict:
        return {
            "total_solved": self.total,
            "by_subject": self.by_subject,
        }


# --------------------------------------------------------------------------- #
#  Self-test
# --------------------------------------------------------------------------- #

if __name__ == "__main__":
    solved_cases = [
        ("That's correct! Now let's move on.", True),
        ("You've got it — good work.", True),
        ("Not quite. Where do you think the error is?", False),
        ("Exactly. The derivative of x² is 2x.", True),
        ("Hmm, let me check that.", False),
        ("Yes, that's right! Now try the next one.", True),
        ("Nice work! So the area is π r squared.", True),
    ]
    print("=== detect_solved ===")
    for reply, expected in solved_cases:
        result = detect_solved(reply)
        status = "PASS" if result == expected else "FAIL"
        print(f"  [{status}] {reply[:55]!r} → {result}")

    subject_cases = [
        ("how do I solve 2x plus 4 equals 10", "algebra"),
        ("what is the area of a circle with radius 5", "geometry"),
        ("water reacts with carbon dioxide", "chemistry"),
        ("what is the derivative of x squared", "calculus"),
        ("what is force equal to in Newton's law", "physics"),
        ("what is the mean of 3 4 5 6 7", "statistics"),
    ]
    print("\n=== classify_subject (keyword path) ===")
    for text, expected in subject_cases:
        result = classify_subject(text)
        status = "PASS" if result == expected else f"FAIL (got {result!r})"
        print(f"  [{status}] {text!r}")

    print("\n=== ProblemCounter ===")
    counter = ProblemCounter()
    turns = [
        ("solve 2x plus 3 equals 11", "Not quite — what's your first step?"),
        ("x equals 4", "That's correct! x equals 4. Nice."),
        ("what is H2O", "That's correct — H2O is water."),
        ("what is the area of a triangle", "Hmm, think about the base and height."),
        ("half base times height", "Exactly. Area equals half base times height."),
    ]
    for user, agent in turns:
        subject = counter.check_and_record(user, agent)
        if subject:
            print(f"  solved: {subject!r}  ← {user!r}")
    print("  Summary:", counter.summary())
