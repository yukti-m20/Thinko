import Link from "next/link";
import { notFound } from "next/navigation";
import { ModeBadge, PageHeader } from "@/components/ui";
import { formatDuration, getSelectedChild } from "@/lib/data";
import { createClient } from "@/lib/supabase/server";

export default async function SessionDetailPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  const child = await getSelectedChild();
  const supabase = await createClient();

  const { data: session } = await supabase
    .from("sessions")
    .select("*")
    .eq("id", id)
    .maybeSingle();

  if (!session || (child && session.child_id !== child.id)) {
    notFound();
  }

  const { data: turns } = await supabase
    .from("turns")
    .select("*")
    .eq("session_id", id)
    .order("idx", { ascending: true });

  const rows = turns ?? [];

  return (
    <div className="space-y-6">
      <div>
        <Link
          href="/activity"
          className="text-sm font-semibold text-[var(--accent)] hover:text-[var(--accent-hover)]"
        >
          ← Back to activity
        </Link>
        <PageHeader
          eyebrow={new Date(session.started_at).toLocaleString()}
          title={session.topic ? capitalize(session.topic) : "Study session"}
          description={`${formatDuration(session.duration_seconds)} · ${session.turn_count} turns`}
          action={<ModeBadge mode={session.primary_mode} />}
        />
      </div>

      <ol className="space-y-3">
        {rows.map((t, i) => {
          const isKid = t.role === "user";
          return (
            <li
              key={t.id}
              className={`page-enter flex ${isKid ? "justify-start" : "justify-end"}`}
              style={{ animationDelay: `${Math.min(i, 12) * 40}ms` }}
            >
              <div
                className={`max-w-[min(40rem,92%)] rounded-2xl px-4 py-3 shadow-sm ${
                  isKid
                    ? "rounded-tl-md bg-white border border-[var(--border)]"
                    : "rounded-tr-md bg-[var(--accent)] text-white"
                }`}
              >
                <p
                  className={`mb-1 text-xs font-semibold uppercase tracking-wide ${
                    isKid ? "text-[var(--muted)]" : "text-white/75"
                  }`}
                >
                  {isKid ? "Student" : "Lil-Vro"}
                  {t.mode ? ` · ${t.mode.replace(/_/g, " ")}` : ""}
                </p>
                <p className="leading-relaxed">{t.content}</p>
              </div>
            </li>
          );
        })}
        {rows.length === 0 ? (
          <li className="panel text-[var(--muted)]">No turns recorded for this session.</li>
        ) : null}
      </ol>
    </div>
  );
}

function capitalize(s: string) {
  return s.charAt(0).toUpperCase() + s.slice(1);
}
