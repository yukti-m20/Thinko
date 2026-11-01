import { makeSupabaseStub } from "./stub";

// Supabase disabled — returns a no-op stub.
// To re-enable: comment the stub line, uncomment the block below, and set env vars.
export function createClient() {
  return makeSupabaseStub();
}

/*
import { createBrowserClient } from "@supabase/ssr";
import type { Database } from "@/types/database";

export function createClient() {
  return createBrowserClient<Database>(
    process.env.NEXT_PUBLIC_SUPABASE_URL ?? "https://placeholder.supabase.co",
    process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY ?? "placeholder-anon-key",
  );
}
*/
