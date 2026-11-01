"use client";

import { useRouter } from "next/navigation";
import { useTransition } from "react";

type ChildOption = { id: string; display_name: string };

export function ChildSwitcher({
  childrenList,
  selectedId,
}: {
  childrenList: ChildOption[];
  selectedId: string | null;
}) {
  const router = useRouter();
  const [pending, start] = useTransition();

  if (!childrenList.length) {
    return (
      <span className="rounded-full bg-white/70 px-3 py-1 text-sm text-[var(--muted)]">
        No children yet
      </span>
    );
  }

  return (
    <label className="flex items-center gap-2 text-sm">
      <span className="hidden text-[var(--muted)] sm:inline">Viewing</span>
      <select
        className="rounded-lg border border-[var(--border)] bg-white px-2.5 py-1.5 font-medium shadow-sm outline-none transition focus:border-[var(--accent)] focus:ring-2 focus:ring-[color-mix(in_srgb,var(--accent)_25%,transparent)]"
        disabled={pending}
        value={selectedId ?? childrenList[0].id}
        onChange={(e) => {
          const id = e.target.value;
          start(async () => {
            await fetch("/api/child", {
              method: "POST",
              headers: { "Content-Type": "application/json" },
              body: JSON.stringify({ childId: id }),
            });
            router.refresh();
          });
        }}
      >
        {childrenList.map((c) => (
          <option key={c.id} value={c.id}>
            {c.display_name}
          </option>
        ))}
      </select>
    </label>
  );
}
