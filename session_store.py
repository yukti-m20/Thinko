"""Persist voice-session snapshots to Supabase (local or hosted).

Uses the PostgREST API with the service-role key so writes bypass RLS.
If SUPABASE_URL / SUPABASE_SERVICE_ROLE_KEY / CHILD_ID are unset, all
methods no-op so the voice loop still works offline.
"""

from __future__ import annotations

import os
from datetime import date, datetime, timezone
from typing import Any
from uuid import uuid4

import requests
from dotenv import load_dotenv

load_dotenv()


def _env(name: str) -> str:
    return (os.getenv(name) or "").strip().strip("\"'")


class SessionStore:
    """Best-effort session writer for the parent dashboard."""

    def __init__(
        self,
        *,
        url: str | None = None,
        service_key: str | None = None,
        child_id: str | None = None,
    ) -> None:
        self.url = (url or _env("SUPABASE_URL") or _env("NEXT_PUBLIC_SUPABASE_URL")).rstrip("/")
        self.service_key = service_key or _env("SUPABASE_SERVICE_ROLE_KEY")
        self.child_id = child_id or _env("CHILD_ID")
        self.session_id: str | None = None
        self._started_at: datetime | None = None
        self._turn_idx = 0
        self._primary_mode = "walkthrough"
        self._topic: str | None = None
        self._enabled = bool(self.url and self.service_key and self.child_id)

    @property
    def enabled(self) -> bool:
        return self._enabled

    def _headers(self) -> dict[str, str]:
        return {
            "apikey": self.service_key,
            "Authorization": f"Bearer {self.service_key}",
            "Content-Type": "application/json",
            "Prefer": "return=minimal",
        }

    def _request(self, method: str, path: str, **kwargs: Any) -> bool:
        if not self._enabled:
            return False
        try:
            response = requests.request(
                method,
                f"{self.url}/rest/v1/{path}",
                headers=self._headers(),
                timeout=8,
                **kwargs,
            )
            if response.status_code >= 400:
                print(f"  [session_store {response.status_code}: {response.text[:200]}]")
                return False
            return True
        except Exception as exc:
            print(f"  [session_store error: {exc}]")
            return False

    def start_session(self, *, mode: str = "walkthrough", topic: str | None = None) -> None:
        if not self._enabled:
            return
        self.session_id = str(uuid4())
        self._started_at = datetime.now(timezone.utc)
        self._turn_idx = 0
        self._primary_mode = mode
        self._topic = topic
        self._request(
            "POST",
            "sessions",
            json={
                "id": self.session_id,
                "child_id": self.child_id,
                "started_at": self._started_at.isoformat(),
                "turn_count": 0,
                "primary_mode": mode,
                "topic": topic,
            },
        )

    def ensure_session(self, *, mode: str) -> None:
        if not self._enabled:
            return
        if self.session_id is None:
            self.start_session(mode=mode)
        else:
            self._primary_mode = mode

    def record_turn(
        self,
        *,
        role: str,
        content: str,
        mode: str | None = None,
        topic: str | None = None,
        phase: str | None = None,
        tool: str | None = None,
    ) -> None:
        if not self._enabled:
            return
        self.ensure_session(mode=mode or self._primary_mode)
        if topic:
            self._topic = topic
        if mode:
            self._primary_mode = mode
        ok = self._request(
            "POST",
            "turns",
            json={
                "session_id": self.session_id,
                "idx": self._turn_idx,
                "role": role,
                "content": content,
                "mode": mode or self._primary_mode,
                "phase": phase,
                "tool": tool,
                "topic": topic or self._topic,
            },
        )
        if ok:
            self._turn_idx += 1
            # Keep session row fresh for the dashboard.
            self._request(
                "PATCH",
                f"sessions?id=eq.{self.session_id}",
                json={
                    "turn_count": self._turn_idx,
                    "primary_mode": self._primary_mode,
                    "topic": self._topic,
                },
            )

    def upsert_mastery(self, scores: dict[str, float], *, event: str | None = None) -> None:
        if not self._enabled or not scores:
            return
        rows = [
            {
                "child_id": self.child_id,
                "topic": topic,
                "score": max(0.0, min(1.0, float(score))),
                "updated_at": datetime.now(timezone.utc).isoformat(),
            }
            for topic, score in scores.items()
        ]
        headers = self._headers()
        headers["Prefer"] = "resolution=merge-duplicates,return=minimal"
        try:
            response = requests.post(
                f"{self.url}/rest/v1/mastery_scores",
                headers=headers,
                json=rows,
                timeout=8,
            )
            if response.status_code >= 400:
                print(f"  [session_store mastery {response.status_code}: {response.text[:200]}]")
        except Exception as exc:
            print(f"  [session_store mastery error: {exc}]")

        if event and self._topic:
            score = scores.get(self._topic)
            self._request(
                "POST",
                "mastery_events",
                json={
                    "child_id": self.child_id,
                    "session_id": self.session_id,
                    "event": event,
                    "topic": self._topic,
                    "score": score,
                },
            )

    def record_session_stats(
        self,
        *,
        mood_counts: dict,
        problems_solved: int,
        subjects: dict,
        topics_needing_help: list,
    ) -> None:
        """Write per-session statistics (mood, problems, subjects) to session_stats."""
        if not self._enabled or not self.session_id:
            return
        from datetime import date
        week_of = date.today().isoformat()
        self._request(
            "POST",
            "session_stats",
            json={
                "session_id": self.session_id,
                "child_id": self.child_id,
                "mood_counts": mood_counts,
                "problems_solved": problems_solved,
                "subjects": subjects,
                "topics_needing_help": {t: True for t in topics_needing_help},
                "week_of": week_of,
            },
        )

    def record_emergency_stop(self, transcript: str) -> None:
        """Log an emergency stop with the full conversation transcript."""
        if not self._enabled:
            return
        self._request(
            "POST",
            "emergency_stops",
            json={
                "child_id": self.child_id,
                "session_id": self.session_id,
                "transcript": transcript,
            },
        )

    def end_session(self) -> None:
        if not self._enabled or not self.session_id or not self._started_at:
            return
        ended = datetime.now(timezone.utc)
        duration = max(0, int((ended - self._started_at).total_seconds()))
        self._request(
            "PATCH",
            f"sessions?id=eq.{self.session_id}",
            json={
                "ended_at": ended.isoformat(),
                "turn_count": self._turn_idx,
                "primary_mode": self._primary_mode,
                "topic": self._topic,
                "duration_seconds": duration,
            },
        )
        self._bump_stats(ended.date())
        self.session_id = None
        self._started_at = None
        self._turn_idx = 0

    def _bump_stats(self, session_day: date) -> None:
        # Read-modify-write via REST (service role).
        try:
            response = requests.get(
                f"{self.url}/rest/v1/child_stats?child_id=eq.{self.child_id}&select=*",
                headers=self._headers(),
                timeout=8,
            )
            rows = response.json() if response.ok else []
            row = rows[0] if isinstance(rows, list) and rows else None
        except Exception:
            row = None

        last = row.get("last_session_on") if row else None
        current = int(row.get("current_streak_days") or 0) if row else 0
        longest = int(row.get("longest_streak_days") or 0) if row else 0
        completed = int(row.get("sessions_completed") or 0) if row else 0

        if last == session_day.isoformat():
            streak = current
        elif last:
            try:
                prev = date.fromisoformat(last)
                streak = current + 1 if (session_day - prev).days == 1 else 1
            except ValueError:
                streak = 1
        else:
            streak = 1

        longest = max(longest, streak)
        payload = {
            "child_id": self.child_id,
            "current_streak_days": streak,
            "longest_streak_days": longest,
            "sessions_completed": completed + 1,
            "last_session_on": session_day.isoformat(),
        }
        headers = self._headers()
        headers["Prefer"] = "resolution=merge-duplicates,return=minimal"
        try:
            requests.post(
                f"{self.url}/rest/v1/child_stats",
                headers=headers,
                json=payload,
                timeout=8,
            )
        except Exception as exc:
            print(f"  [session_store stats error: {exc}]")
