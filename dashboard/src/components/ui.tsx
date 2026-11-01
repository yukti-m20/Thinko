import Link from "next/link";

export function PageHeader({
  eyebrow,
  title,
  description,
  action,
}: {
  eyebrow?: string;
  title: string;
  description?: string;
  action?: React.ReactNode;
}) {
  return (
    <div className="page-enter mb-8 flex flex-wrap items-end justify-between gap-4">
      <div className="max-w-2xl">
        {eyebrow ? (
          <p className="mb-1 text-sm font-medium tracking-wide text-[var(--muted)]">
            {eyebrow}
          </p>
        ) : null}
        <h1 className="display text-3xl text-[var(--ink)] sm:text-4xl">{title}</h1>
        {description ? (
          <p className="mt-2 text-[var(--muted)] leading-relaxed">{description}</p>
        ) : null}
      </div>
      {action}
    </div>
  );
}

export function StatCard({
  label,
  value,
  hint,
  delay = 0,
}: {
  label: string;
  value: React.ReactNode;
  hint?: string;
  delay?: number;
}) {
  return (
    <div
      className="panel page-enter"
      style={{ animationDelay: `${delay}ms` }}
    >
      <p className="text-sm font-medium text-[var(--muted)]">{label}</p>
      <p className="stat-value mt-2">{value}</p>
      {hint ? <p className="mt-2 text-sm text-[var(--muted)]">{hint}</p> : null}
    </div>
  );
}

export function EmptyState({
  title,
  body,
  action,
}: {
  title: string;
  body: string;
  action?: React.ReactNode;
}) {
  return (
    <div className="panel-quiet flex flex-col items-start gap-3 py-10 text-center sm:items-center">
      <h3 className="display text-xl">{title}</h3>
      <p className="max-w-md text-sm text-[var(--muted)]">{body}</p>
      {action}
    </div>
  );
}

export function ModeBadge({ mode }: { mode: string }) {
  const label = mode.replace(/_/g, " ");
  const warm = label.includes("quiz") || label.includes("mistake");
  return <span className={warm ? "badge badge-warm" : "badge"}>{label}</span>;
}

export function MasteryBar({
  topic,
  score,
  delay = 0,
}: {
  topic: string;
  score: number;
  delay?: number;
}) {
  const pct = Math.round(Math.max(0, Math.min(1, score)) * 100);
  return (
    <div style={{ animationDelay: `${delay}ms` }} className="page-enter">
      <div className="mb-1.5 flex items-baseline justify-between gap-3 text-sm">
        <span className="font-medium capitalize text-[var(--ink-soft)]">{topic}</span>
        <span className="tabular-nums text-[var(--muted)]">{pct}%</span>
      </div>
      <div className="h-2.5 overflow-hidden rounded-full bg-[var(--surface)]">
        <div
          className="mastery-fill h-full rounded-full bg-[var(--accent)]"
          style={{ width: `${pct}%`, animationDelay: `${delay + 80}ms` }}
        />
      </div>
    </div>
  );
}

export function TextLink({
  href,
  children,
}: {
  href: string;
  children: React.ReactNode;
}) {
  return (
    <Link
      href={href}
      className="text-sm font-semibold text-[var(--accent)] transition hover:text-[var(--accent-hover)]"
    >
      {children}
    </Link>
  );
}
