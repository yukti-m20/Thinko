import { AddChildForm } from "@/components/AddChildForm";
import { DeleteChildButton } from "@/components/DeleteChildButton";
import { PageHeader } from "@/components/ui";
import { getChildren, getSelectedChild } from "@/lib/data";
import { createClient } from "@/lib/supabase/server";

export default async function ChildrenPage() {
  const kids = await getChildren();
  const selected = await getSelectedChild();
  const supabase = await createClient();

  const statsByChild: Record<
    string,
    { sessions_completed: number; current_streak_days: number } | null
  > = {};
  for (const kid of kids) {
    const { data } = await supabase
      .from("child_stats")
      .select("sessions_completed, current_streak_days")
      .eq("child_id", kid.id)
      .maybeSingle();
    statsByChild[kid.id] = data;
  }

  return (
    <div className="space-y-6">
      <PageHeader
        eyebrow="Family"
        title="Children"
        description="Nickname-only profiles. Use each child’s ID in the voice agent .env so sessions sync here."
      />

      <ul className="grid gap-4 sm:grid-cols-2">
        {kids.map((kid, i) => (
          <li
            key={kid.id}
            className={`panel page-enter ${
              selected?.id === kid.id ? "ring-2 ring-[var(--accent)] ring-offset-2 ring-offset-[var(--bg1)]" : ""
            }`}
            style={{ animationDelay: `${i * 50}ms` }}
          >
            <div className="flex items-start justify-between gap-3">
              <div>
                <p className="display text-2xl">{kid.display_name}</p>
                <p className="mt-1 text-sm text-[var(--muted)]">
                  {statsByChild[kid.id]?.sessions_completed ?? 0} sessions ·{" "}
                  {statsByChild[kid.id]?.current_streak_days ?? 0}-day streak
                </p>
              </div>
              {selected?.id === kid.id ? (
                <span className="badge">Viewing</span>
              ) : null}
            </div>
            <div className="mt-4 rounded-xl bg-[var(--surface)] px-3 py-2.5">
              <p className="text-xs font-semibold uppercase tracking-wide text-[var(--muted)]">
                Voice agent CHILD_ID
              </p>
              <p className="mt-1 break-all font-mono text-xs text-[var(--ink-soft)]">
                {kid.id}
              </p>
            </div>
            <DeleteChildButton childId={kid.id} childName={kid.display_name} />
          </li>
        ))}
      </ul>

      {kids.length === 0 ? (
        <p className="text-sm text-[var(--muted)]">
          No children yet — add a nickname below to get started.
        </p>
      ) : null}

      <section className="panel max-w-md page-enter" style={{ animationDelay: "100ms" }}>
        <h2 className="display mb-1 text-xl">Add child</h2>
        <p className="mb-4 text-sm text-[var(--muted)]">
          First name or nickname only — never school, address, or full legal name.
        </p>
        <AddChildForm />
      </section>
    </div>
  );
}
