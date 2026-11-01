import { cookies } from "next/headers";
import { createClient } from "@/lib/supabase/server";
import type { Database } from "@/types/database";

export type Child = Database["public"]["Tables"]["children"]["Row"];

export const SELECTED_CHILD_COOKIE = "thinko_child_id";

export async function requireUser() {
  const supabase = await createClient();
  const {
    data: { user },
  } = await supabase.auth.getUser();
  // When Supabase is disabled, user is null — callers handle gracefully.
  // if (!user) throw new Error("Unauthorized");
  return { supabase, user };
}

export async function getChildren() {
  const { supabase, user } = await requireUser();
  if (!user) return [];
  const { data, error } = await supabase
    .from("children")
    .select("*")
    .order("created_at", { ascending: true });
  if (error) throw error;
  return data ?? [];
}

export async function getSelectedChild(): Promise<Child | null> {
  const kids = await getChildren();
  if (!kids.length) return null;
  const jar = await cookies();
  const preferred = jar.get(SELECTED_CHILD_COOKIE)?.value;
  return kids.find((c) => c.id === preferred) ?? kids[0];
}

export function formatDuration(seconds: number | null | undefined) {
  if (seconds == null) return "—";
  const m = Math.round(seconds / 60);
  if (m < 60) return `${m} min`;
  const h = Math.floor(m / 60);
  return `${h}h ${m % 60}m`;
}

export function formatPct(score: number) {
  return `${Math.round(score * 100)}%`;
}
