import { makeSupabaseStub } from "./stub";

// Supabase disabled — returns a no-op stub.
// To re-enable: comment the stub line, uncomment the block below, and set env vars.
export function createAdminClient() {
  return makeSupabaseStub();
}

/*
import { createClient } from "@supabase/supabase-js";
import type { Database } from "@/types/database";

export function createAdminClient() {
  const url = process.env.NEXT_PUBLIC_SUPABASE_URL ?? "https://placeholder.supabase.co";
  const key = process.env.SUPABASE_SERVICE_ROLE_KEY ?? "placeholder-service-role-key";
  return createClient<Database>(url, key, {
    auth: { persistSession: false, autoRefreshToken: false },
  });
}
*/
