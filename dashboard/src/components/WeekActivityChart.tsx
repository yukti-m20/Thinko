type DayBucket = { label: string; minutes: number };

export function WeekActivityChart({
  sessions,
}: {
  sessions: { started_at: string; duration_seconds: number | null }[];
}) {
  const today = new Date();
  today.setHours(0, 0, 0, 0);

  const days: DayBucket[] = [];
  for (let i = 6; i >= 0; i--) {
    const d = new Date(today);
    d.setDate(today.getDate() - i);
    days.push({
      label: d.toLocaleDateString(undefined, { weekday: "short" }),
      minutes: 0,
    });
  }

  for (const s of sessions) {
    const started = new Date(s.started_at);
    started.setHours(0, 0, 0, 0);
    const diff = Math.round((today.getTime() - started.getTime()) / (1000 * 60 * 60 * 24));
    if (diff >= 0 && diff <= 6) {
      days[6 - diff].minutes += Math.round((s.duration_seconds ?? 0) / 60);
    }
  }

  const max = Math.max(1, ...days.map((d) => d.minutes));

  return (
    <div className="panel page-enter-delay">
      <div className="mb-4 flex items-baseline justify-between gap-3">
        <h2 className="display text-xl">This week</h2>
        <p className="text-sm text-[var(--muted)]">Minutes studying</p>
      </div>
      <div className="flex h-36 items-end gap-2 sm:gap-3">
        {days.map((d, i) => {
          const h = Math.max(d.minutes > 0 ? 12 : 4, Math.round((d.minutes / max) * 120));
          return (
            <div key={`${d.label}-${i}`} className="flex flex-1 flex-col items-center gap-2">
              <div className="flex h-28 w-full items-end justify-center">
                <div
                  className="week-bar w-full max-w-[2.25rem] rounded-t-md bg-[var(--accent)]"
                  style={{
                    height: h,
                    opacity: d.minutes ? 1 : 0.25,
                    animationDelay: `${i * 40}ms`,
                  }}
                  title={`${d.minutes} min`}
                />
              </div>
              <span className="text-xs text-[var(--muted)]">{d.label}</span>
            </div>
          );
        })}
      </div>
    </div>
  );
}
