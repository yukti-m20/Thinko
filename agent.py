"""Turn normalized student text into a voice-friendly Codex response."""

import os
from typing import Any, Optional

import requests
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), ".env"), override=True)

OPENAI_BASE_URL = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1").rstrip("/")
RESPONSES_URL = f"{OPENAI_BASE_URL}/chat/completions"
DEFAULT_MODEL = "gpt-6-luna"
HISTORY_LIMIT = 20  # max messages kept (10 turns) — prevents unbounded context growth

# Distress phrases intercepted locally — never sent to external LLM
_DISTRESS_PHRASES = [
    "want to disappear", "want to die", "kill myself", "hurt myself",
    "hate myself", "want to give up on life", "nobody cares about me",
    "can't do anything right", "i'm worthless", "i want to end it",
]
_DISTRESS_RESPONSE = (
    "Hey, I heard something that made me stop. You matter a lot, and if "
    "you're having a hard time right now, please talk to a trusted adult — "
    "a parent, teacher, or school counselor. I'm just a study buddy and "
    "I really want you to be okay."
)

_BASE_SYSTEM = """
You are Lil-Vro, a sharp, honest STEM study partner and older buddy for students aged 8 to 14.
Your job is to build real understanding — not to make the student feel good in the moment.

LANGUAGE & VOICE (CRITICAL — STRICT HINGLISH):
- You MUST speak in natural, conversational HINGLISH (a smooth blend of Hindi and English written in the English/Latin alphabet).
- Do NOT use formal/textbook "Shuddh Hindi".
- Do NOT use Devanagari script (no क, ख, ग). Always use Roman/Latin script for Hinglish.
- Keep all STEM and technical terms in standard English (e.g., photosynthesis, gravity, friction, equation, fraction, velocity, cell, atom, molecule).
- Examples of your tone:
    * "Plants sunlight use karke apna food banate hain, jise photosynthesis bolte hain. Ek hint: socho sunlight kahan trap hoti hai?"
    * "Sahi direction hai! Ab agla step try karo."
    * "Dekho, 3x plus 2 equals 17 hai, toh pehle dono side se 2 subtract karenge. Ab batao kya bacha?"

TEACHING STYLE (SOCRATIC INQUIRY):
- NEVER give direct answers, textbook definitions, or solutions upfront. Your job is to build the child's thinking and problem-solving capability.
- When asked "What is X?" or "How to solve Y?", bounce back with an everyday curiosity question or thought experiment so they discover it themselves.
- Guide through reasoning, never hand over answers. Ask one precise question at a time (1-2 sentences max).
- When a student is wrong, say so directly and briefly in friendly Hinglish, then give a small clue or analogy to guide self-correction.
- Push back on vague answers. Ask them to be specific.
- Silence is not agreement. If the student skips a step, call it out.

LOGIC FIRST:
- Reason through problems step by step before responding. Show your working in your head.
- If the reasoning is wrong even though the answer is accidentally right, say so.

ANSWER VERIFICATION — NON-NEGOTIABLE:
- Silently compute the correct answer before every response.
- If the student's answer is WRONG: state clearly it is not right in Hinglish, identify which part failed, and ask one question to guide the correction.
- If RIGHT: confirm briefly and precisely, then move forward.
- Short responses (1 to 2 spoken sentences). No Markdown, LaTeX, tables, or visual formatting.
""".strip()

_MODES = {
    "walkthrough": (
        "Break the problem into steps. Ask one question per step. "
        "Do not move on until the current step is correct. "
        "If the student is stuck after two attempts, give a specific nudge — not the answer."
    ),
    "teach_back": (
        "The student is explaining a concept to you. Listen carefully and find gaps. "
        "If their explanation is vague or incomplete, say so and ask them to be more precise. "
        "Do not pretend to understand what you don't. Ask hard follow-up questions."
    ),
    "quiz": (
        "State one STEM fact with exactly one deliberate error embedded in it. "
        "Do not hint where the mistake is. Wait for the student to find it. "
        "If they miss it after two attempts, give one narrow clue. "
        "When they find it, confirm precisely why it was wrong."
    ),
}

_MOOD_NOTES = {
    "frustrated":  "The student sounds frustrated. Be extra warm, slow down, and simplify.",
    "confused":    "The student sounds confused. Try a different angle or a simple analogy.",
    "disengaged":  "The student sounds disengaged. Add a surprising fact or fun angle to pull them back in.",
    "confident":   "The student sounds confident. Push a little harder and introduce the next idea.",
    "neutral":     "",
}


class AgentError(RuntimeError):
    """Raised when the agent cannot produce a response."""


def _build_system(mode: str, mood: str) -> str:
    mode_note = _MODES.get(mode, _MODES["walkthrough"])
    mood_note = _MOOD_NOTES.get(mood, "")
    system = _BASE_SYSTEM + f"\n\nMode: {mode_note}"
    if mood_note:
        system += f"\n\nMood note: {mood_note}"
    return system


def _extract_output_text(payload: dict[str, Any]) -> str:
    """Extract assistant text from an OpenRouter chat completions payload."""
    try:
        msg = payload["choices"][0]["message"]
        text = (msg.get("content") or "").strip()
        if text:
            return text
    except (KeyError, IndexError):
        pass
    raise AgentError("OpenRouter returned no text.")


def respond(
    normalized_text: str,
    history: Optional[list[dict]] = None,
    mood: str = "neutral",
    mode: str = "walkthrough",
    *,
    api_key: Optional[str] = None,
    model: Optional[str] = None,
    timeout: float = 30.0,
) -> tuple[str, list[dict]]:
    """
    Return a spoken response for normalized student input.

    Args:
        normalized_text: Student input (from speech_normalizer.normalize())
        history:         Conversation so far — list of {"role": ..., "content": ...}
        mood:            "neutral" | "frustrated" | "confused" | "confident" | "disengaged"
        mode:            "walkthrough" | "teach_back" | "quiz"

    Returns:
        (response_text, updated_history)

    Raises:
        ValueError: if the utterance is empty (caller should not speak yet)
    """
    normalized_text = normalized_text.strip()
    if not normalized_text:
        raise ValueError("normalized_text cannot be empty — wait until the student finishes speaking")

    # Soft guard: do not invent a reply from pure hesitation noise.
    lowered = normalized_text.lower().strip(".,!? ")
    if lowered in {"um", "uh", "erm", "hmm", "hm", "ah", "oh", "mm", "mmm"}:
        raise ValueError("utterance is filler only — keep listening")

    # Distress detection — intercept locally, never forward to external LLM
    lower_text = normalized_text.lower()
    if any(phrase in lower_text for phrase in _DISTRESS_PHRASES):
        history = list(history or [])
        history.append({"role": "user", "content": normalized_text})
        history.append({"role": "assistant", "content": _DISTRESS_RESPONSE})
        return _DISTRESS_RESPONSE, history

    gemini_key = os.getenv("GEMINI_API_KEY")
    api_key = api_key or gemini_key or os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise AgentError("OPENAI_API_KEY or GEMINI_API_KEY is not set.")

    history = list(history or [])
    history.append({"role": "user", "content": normalized_text})

    if len(history) > HISTORY_LIMIT:
        history = history[-HISTORY_LIMIT:]

    # Check if this is a Google Gemini request
    is_gemini = bool(gemini_key or (api_key and (api_key.startswith("AIzaSy") or api_key.startswith("AQ."))))

    if is_gemini:
        gemini_model = model or os.getenv("CODEX_MODEL", "gemini-2.5-flash")
        # Format conversation contents for Google Gemini API
        contents = []
        for msg in history:
            role = "user" if msg["role"] == "user" else "model"
            contents.append({
                "role": role,
                "parts": [{"text": msg["content"]}]
            })

        system_instruction = {"parts": [{"text": _build_system(mode, mood)}]}

        url = f"https://generativelanguage.googleapis.com/v1beta/models/{gemini_model}:generateContent?key={api_key}"
        payload = {
            "contents": contents,
            "system_instruction": system_instruction,
            "generationConfig": {
                "maxOutputTokens": 500,
                "temperature": 0.6,
            }
        }

        response = requests.post(
            url,
            headers={"Content-Type": "application/json"},
            json=payload,
            timeout=timeout,
        )

        try:
            response.raise_for_status()
        except requests.HTTPError as exc:
            try:
                detail = response.json().get("error", {}).get("message")
            except Exception:
                detail = None
            raise AgentError(detail or f"Gemini API request failed ({response.status_code}).") from exc

        res_json = response.json()
        try:
            reply = res_json["candidates"][0]["content"]["parts"][0]["text"].strip()
        except (KeyError, IndexError):
            reply = ""

        if not reply:
            raise AgentError("Gemini returned empty text — not speaking yet.")
        history.append({"role": "assistant", "content": reply})
        return reply, history

    # OpenAI / OpenAI-compatible endpoint
    base_url = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1").rstrip("/")
    endpoint = f"{base_url}/chat/completions"
    chosen_model = model or os.getenv("CODEX_MODEL", DEFAULT_MODEL)

    messages = [{"role": "system", "content": _build_system(mode, mood)}] + [
        {"role": msg["role"], "content": msg["content"]}
        for msg in history
    ]

    response = requests.post(
        endpoint,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        json={
            "model": chosen_model,
            "messages": messages,
            "max_completion_tokens": 500,
        },
        timeout=timeout,
    )

    try:
        response.raise_for_status()
    except requests.HTTPError as exc:
        try:
            payload = response.json()
            if isinstance(payload, list):
                payload = payload[0] if payload else {}
            detail = payload.get("error", {}).get("message")
        except (ValueError, AttributeError):
            detail = None
        raise AgentError(detail or f"OpenAI request failed ({response.status_code}).") from exc

    reply = _extract_output_text(response.json())
    if not reply.strip():
        raise AgentError("OpenAI returned empty text — not speaking yet.")
    history.append({"role": "assistant", "content": reply})
    return reply, history


def detect_mode(text: str, current_mode: str) -> str:
    """Switch mode based on student wake phrases."""
    lower = text.lower()
    if any(p in lower for p in ["quiz mode", "quiz me", "test me", "find the mistake"]):
        return "quiz"
    if any(p in lower for p in ["teach back", "let me explain", "i'll explain", "teach you"]):
        return "teach_back"
    if any(p in lower for p in ["help me", "walk me through", "walkthrough", "explain this"]):
        return "walkthrough"
    return current_mode


if __name__ == "__main__":
    print("agent.py terminal test — type to chat, Ctrl+C to quit")
    print("Switch modes: 'quiz mode' | 'teach back' | 'help me'\n")
    history = []
    mode = "walkthrough"
    while True:
        try:
            user_input = input("You: ").strip()
            if not user_input:
                continue
            mode = detect_mode(user_input, mode)
            print(f"  [mode: {mode}]")
            response, history = respond(user_input, history, mode=mode)
            print(f"Agent: {response}\n")
        except KeyboardInterrupt:
            print("\nDone.")
            break
