import Link from "next/link";
import { EmptyState, MasteryBar, PageHeader } from "@/components/ui";
import { formatPct, getSelectedChild } from "@/lib/data";
import { createClient } from "@/lib/supabase/server";

export default async function MasteryPage() {
  const child = await getSelectedChild();
  if (!child) {
    return (
      <>
        <PageHeader title="Mastery" />
        <EmptyState
          title="Select a child"
          body="Mastery scores are tracked per child."
          action={
            <Link href="/children" className="btn-primary inline-block">
              Go to Children
            </Link>
          }
        />
      </>
    );
  }

  const supabase = await createClient();
  const [{ data: scores }, { data: events }] = await Promise.all([
    supabase
      .from("mastery_scores")
      .select("*")
      .eq("child_id", child.id)
      .order("score", { ascending: false }),
    supabase
      .from("mastery_events")
      .select("*")
      .eq("child_id", child.id)
      .order("created_at", { ascending: false })
      .limit(12),
  ]);

  const scoreRows = scores ?? [];
  const eventRows = events ?? [];
  const avg =
    scoreRows.length > 0
      ? scoreRows.reduce((sum, s) => sum + s.score, 0) / scoreRows.length
      : 0;

  return (
    <div className="space-y-6">
      <PageHeader
        eyebrow="Understanding"
        title="Mastery"
        description={`Per-topic confidence for ${child.display_name}, built from walkthroughs and teach-backs.`}
      />

      <div className="grid gap-4 sm:grid-cols-3">
        <div className="panel page-enter">
          <p className="text-sm text-[var(--muted)]">Topics tracked</p>
          <p className="stat-value mt-2">{scoreRows.length}</p>
        </div>
        <div className="panel page-enter" style={{ animationDelay: "60ms" }}>
          <p className="text-sm text-[var(--muted)]">Average confidence</p>
          <p className="stat-value mt-2">{scoreRows.length ? formatPct(avg) : "—"}</p>
        </div>
        <div className="panel page-enter" style={{ animationDelay: "120ms" }}>
          <p className="text-sm text-[var(--muted)]">Strongest topic</p>
          <p className="stat-value mt-2 capitalize">
            {scoreRows[0]?.topic ?? "—"}
          </p>
        </div>
      </div>

      <section className="panel page-enter space-y-5" style={{ animationDelay: "80ms" }}>
        <h2 className="display text-xl">By topic</h2>
        {scoreRows.length === 0 ? (
          <p className="text-sm text-[var(--muted)]">No scores yet.</p>
        ) : (
          scoreRows.map((m, i) => (
            <MasteryBar key={m.topic} topic={m.topic} score={m.score} delay={i * 50} />
          ))
        )}
      </section>

      <section className="panel page-enter" style={{ animationDelay: "120ms" }}>
        <h2 className="mb-4 display text-xl">Recent signals</h2>
        <ul className="divide-y divide-[var(--border)]">
          {eventRows.map((e) => (
            <li
              key={e.id}
              className="flex flex-wrap items-center justify-between gap-2 py-3 text-sm"
            >
              <span>
                <span className="font-medium capitalize">{e.topic}</span>
                <span className="text-[var(--muted)]"> · {e.event.replace(/_/g, " ")}</span>
              </span>
              <span className="tabular-nums text-[var(--muted)]">
                {e.score != null ? formatPct(e.score) : "—"}
              </span>
            </li>
          ))}
          {eventRows.length === 0 ? (
            <li className="py-2 text-sm text-[var(--muted)]">No mastery events yet.</li>
          ) : null}
        </ul>
      </section>
    </div>
  );
}
