"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";

export function DeleteChildButton({ childId, childName }: { childId: string; childName: string }) {
  const router = useRouter();
  const [confirming, setConfirming] = useState(false);
  const [loading, setLoading] = useState(false);

  async function handleDelete() {
    if (!confirming) { setConfirming(true); return; }
    setLoading(true);
    await fetch(`/api/delete-child/${childId}`, { method: "DELETE" });
    setLoading(false);
    setConfirming(false);
    router.refresh();
  }

  return (
    <button
      onClick={handleDelete}
      disabled={loading}
      className="mt-3 w-full rounded-xl border border-red-200 bg-red-50 px-3 py-2 text-xs font-semibold text-red-600 transition hover:bg-red-100 disabled:opacity-50"
    >
      {loading ? "Deleting…" : confirming ? `Confirm — delete all data for ${childName}?` : "Delete all data"}
    </button>
  );
}
