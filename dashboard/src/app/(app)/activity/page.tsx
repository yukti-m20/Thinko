import Link from "next/link";
import { EmptyState, ModeBadge, PageHeader } from "@/components/ui";
import { formatDuration, getSelectedChild } from "@/lib/data";
import { createClient } from "@/lib/supabase/server";

export default async function ActivityPage() {
  const child = await getSelectedChild();
  if (!child) {
    return (
      <>
        <PageHeader title="Activity" description="Session history will appear here." />
        <EmptyState
          title="Select a child"
          body="Add or choose a child profile to browse their study sessions."
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
  const { data: sessions } = await supabase
    .from("sessions")
    .select("*")
    .eq("child_id", child.id)
    .order("started_at", { ascending: false })
    .limit(50);

  const rows = sessions ?? [];

  return (
    <div className="space-y-2">
      <PageHeader
        eyebrow="Progression"
        title="Activity"
        description={`Every study session for ${child.display_name} — time, mode, and topic.`}
      />

      {rows.length === 0 ? (
        <EmptyState
          title="No sessions yet"
          body="When the voice agent is linked with this child’s ID, finished sessions will land here automatically."
        />
      ) : (
        <div className="panel overflow-hidden p-0 page-enter">
          <div className="hidden border-b border-[var(--border)] bg-[var(--surface)]/60 px-4 py-3 text-xs font-semibold uppercase tracking-wide text-[var(--muted)] sm:grid sm:grid-cols-12 sm:gap-3">
            <span className="sm:col-span-4">When</span>
            <span className="sm:col-span-3">Topic</span>
            <span className="sm:col-span-2">Mode</span>
            <span className="sm:col-span-1">Turns</span>
            <span className="sm:col-span-2">Duration</span>
          </div>
          <ul>
            {rows.map((s, i) => (
              <li
                key={s.id}
                className="border-b border-[var(--border)] last:border-0"
                style={{ animationDelay: `${i * 30}ms` }}
              >
                <Link
                  href={`/sessions/${s.id}`}
                  className="grid gap-1 px-4 py-3.5 transition hover:bg-[var(--surface)]/70 sm:grid-cols-12 sm:items-center sm:gap-3"
                >
                  <span className="text-sm font-medium text-[var(--ink-soft)] sm:col-span-4">
                    {new Date(s.started_at).toLocaleString(undefined, {
                      month: "short",
                      day: "numeric",
                      hour: "numeric",
                      minute: "2-digit",
                    })}
                  </span>
                  <span className="capitalize sm:col-span-3">
                    {s.topic ?? "General"}
                  </span>
                  <span className="sm:col-span-2">
                    <ModeBadge mode={s.primary_mode} />
                  </span>
                  <span className="text-sm text-[var(--muted)] sm:col-span-1">
                    {s.turn_count}
                  </span>
                  <span className="text-sm text-[var(--muted)] sm:col-span-2">
                    {formatDuration(s.duration_seconds)}
                  </span>
                </Link>
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}
