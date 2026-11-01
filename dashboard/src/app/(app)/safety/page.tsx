import { EmptyState, PageHeader } from "@/components/ui";
import { getSelectedChild } from "@/lib/data";
import { createClient } from "@/lib/supabase/server";

export default async function SafetyPage() {
  const child = await getSelectedChild();
  if (!child) {
    return (
      <>
        <PageHeader title="Safety" description="Emergency stop events will appear here." />
        <EmptyState title="Select a child" body="Add or choose a child profile first." />
      </>
    );
  }

  const supabase = await createClient();
  const { data: stops } = await supabase
    .from("emergency_stops")
    .select("*")
    .eq("child_id", child.id)
    .order("triggered_at", { ascending: false })
    .limit(50);

  const rows = stops ?? [];

  return (
    <div className="space-y-6">
      <PageHeader
        eyebrow="Safety"
        title="Emergency stops"
        description={`Full conversation transcripts when ${child.display_name} pressed the stop button.`}
      />

      {rows.length === 0 ? (
        <EmptyState
          title="No emergency stops"
          body="If the child presses the stop button on their learning page, the full session transcript lands here."
        />
      ) : (
        <div className="space-y-4">
          {rows.map((stop, i) => (
            <details
              key={stop.id}
              className="panel page-enter"
              style={{ animationDelay: `${i * 40}ms` }}
            >
              <summary className="flex cursor-pointer items-center justify-between gap-3 py-1 font-semibold">
                <span className="flex items-center gap-2">
                  <span className="inline-block h-2.5 w-2.5 rounded-full bg-red-500" />
                  {new Date(stop.triggered_at).toLocaleString(undefined, {
                    weekday: "short",
                    month: "short",
                    day: "numeric",
                    hour: "numeric",
                    minute: "2-digit",
                  })}
                </span>
                <span className="text-xs font-normal text-[var(--muted)]">click to expand transcript</span>
              </summary>

              <div className="mt-4 space-y-2 border-t border-[var(--border)] pt-4">
                {stop.transcript.split("\n").filter(Boolean).map((line, j) => {
                  const isKid = line.startsWith("USER:");
                  const content = line.replace(/^(USER|ASSISTANT):\s*/, "");
                  return (
                    <div
                      key={j}
                      className={`flex ${isKid ? "justify-start" : "justify-end"}`}
                    >
                      <div
                        className={`max-w-[min(36rem,90%)] rounded-xl px-3 py-2 text-sm ${
                          isKid
                            ? "bg-white border border-[var(--border)] text-[var(--ink-soft)]"
                            : "bg-[var(--accent)] text-white"
                        }`}
                      >
                        <p className="mb-0.5 text-[10px] font-semibold uppercase tracking-wide opacity-60">
                          {isKid ? child.display_name : "Thinko"}
                        </p>
                        {content}
                      </div>
                    </div>
                  );
                })}
              </div>
            </details>
          ))}
        </div>
      )}
    </div>
  );
}
