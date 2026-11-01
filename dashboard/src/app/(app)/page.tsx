import Link from "next/link";
import { WeekActivityChart } from "@/components/WeekActivityChart";
import {
  MasteryBar,
  ModeBadge,
  PageHeader,
  StatCard,
  TextLink,
} from "@/components/ui";
import { formatDuration, formatPct } from "@/lib/data";

// ─── Mock data ────────────────────────────────────────────────────────────────

function daysAgo(n: number, hour = 16) {
  const d = new Date();
  d.setDate(d.getDate() - n);
  d.setHours(hour, 30, 0, 0);
  return d.toISOString();
}

const CHILD_NAME = "Alex";

const MOCK_STATS = {
  current_streak_days: 7,
  longest_streak_days: 12,
  sessions_completed: 34,
};

const MOCK_SESSIONS = [
  { id: "s1", started_at: daysAgo(0), duration_seconds: 1800, topic: "algebra",     primary_mode: "walkthrough", turn_count: 24 },
  { id: "s2", started_at: daysAgo(1), duration_seconds: 1320, topic: "fractions",   primary_mode: "practice",    turn_count: 18 },
  { id: "s3", started_at: daysAgo(2), duration_seconds: 2700, topic: "geometry",    primary_mode: "teach-back",  turn_count: 31 },
  { id: "s4", started_at: daysAgo(4), duration_seconds: 1080, topic: "percentages", primary_mode: "practice",    turn_count: 14 },
  { id: "s5", started_at: daysAgo(5), duration_seconds: 1680, topic: "algebra",     primary_mode: "walkthrough", turn_count: 21 },
];

const MOCK_MASTERY = [
  { topic: "Fractions",   score: 0.82 },
  { topic: "Algebra",     score: 0.74 },
  { topic: "Geometry",    score: 0.61 },
  { topic: "Percentages", score: 0.55 },
  { topic: "Ratios",      score: 0.48 },
];

// ─── Page ─────────────────────────────────────────────────────────────────────

export default function OverviewPage() {
  const weekMinutes = Math.round(
    MOCK_SESSIONS.reduce((sum, s) => sum + (s.duration_seconds ?? 0), 0) / 60,
  );
  const topTopic = MOCK_MASTERY[0];
  const weekProblems = 23;
  const topSubject: [string, number] = ["algebra", 12];

  return (
    <div className="space-y-6">
      <PageHeader
        eyebrow="Parent dashboard"
        title={`${CHILD_NAME}'s week`}
        description="Motivation, study time, and what they're getting more confident with — without interrupting the voice session."
        action={
          <div className="flex items-center gap-2 rounded-full bg-white/80 px-3 py-1.5 text-sm text-[var(--muted)] shadow-sm">
            <span className="live-dot h-2 w-2 rounded-full bg-[var(--accent)]" />
            Synced from study sessions
          </div>
        }
      />

      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <StatCard
          label="Current streak"
          value={`${MOCK_STATS.current_streak_days} days`}
          hint={`Best: ${MOCK_STATS.longest_streak_days} days`}
          delay={40}
        />
        <StatCard
          label="Sessions this week"
          value={MOCK_SESSIONS.length}
          hint={`${MOCK_STATS.sessions_completed} all time`}
          delay={90}
        />
        <StatCard
          label="Problems solved"
          value={weekProblems}
          hint={`Top subject: ${topSubject[0]} (${topSubject[1]})`}
          delay={130}
        />
        <StatCard
          label="Study time"
          value={`${weekMinutes} min`}
          hint={`Strongest: ${topTopic.topic} (${formatPct(topTopic.score)})`}
          delay={170}
        />
      </div>

      <div className="grid gap-4 lg:grid-cols-5">
        <div className="lg:col-span-3">
          <WeekActivityChart sessions={MOCK_SESSIONS} />
        </div>
        <section className="panel page-enter lg:col-span-2" style={{ animationDelay: "120ms" }}>
          <div className="mb-4 flex items-center justify-between gap-3">
            <h2 className="display text-xl">Top topics</h2>
            <TextLink href="#">Mastery</TextLink>
          </div>
          <div className="space-y-4">
            {MOCK_MASTERY.map((m, i) => (
              <MasteryBar key={m.topic} topic={m.topic} score={m.score} delay={i * 60} />
            ))}
          </div>
        </section>
      </div>

      <section className="panel page-enter" style={{ animationDelay: "160ms" }}>
        <div className="mb-4 flex items-center justify-between gap-3">
          <h2 className="display text-xl">Recent sessions</h2>
          <TextLink href="#">All activity</TextLink>
        </div>
        <ul className="divide-y divide-[var(--border)]">
          {MOCK_SESSIONS.slice(0, 5).map((s) => (
            <li key={s.id}>
              <Link
                href="#"
                className="flex flex-wrap items-center justify-between gap-3 py-3 transition hover:bg-[var(--surface)]/60 sm:px-2"
              >
                <div className="min-w-0">
                  <p className="font-semibold capitalize text-[var(--ink-soft)]">
                    {s.topic ?? "General practice"}
                  </p>
                  <p className="mt-1 flex flex-wrap items-center gap-2 text-sm text-[var(--muted)]">
                    <ModeBadge mode={s.primary_mode} />
                    <span>{formatDuration(s.duration_seconds)}</span>
                    <span>·</span>
                    <span>{s.turn_count} turns</span>
                  </p>
                </div>
                <span className="text-sm text-[var(--muted)]">
                  {new Date(s.started_at).toLocaleDateString(undefined, {
                    weekday: "short",
                    month: "short",
                    day: "numeric",
                  })}
                </span>
              </Link>
            </li>
          ))}
        </ul>
      </section>
    </div>
  );
}
