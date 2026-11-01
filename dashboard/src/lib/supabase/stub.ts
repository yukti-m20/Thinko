/**
 * No-op Supabase stubs — used when Supabase is disabled.
 *
 * makeQueryStub()  — thenable Proxy for query chains (.from → .select → .eq …).
 *                    Awaiting it yields { data: [], error: null }.
 *                    .maybeSingle() / .single() yield { data: null, error: null }.
 *
 * makeSupabaseStub() — the top-level client. NOT thenable so it survives being
 *                      returned from an async function (async functions wrap their
 *                      return value in Promise.resolve(), which would unwrap any
 *                      thenable and lose the stub object).
 */

// eslint-disable-next-line @typescript-eslint/no-explicit-any
function makeQueryStub(): any {
  return new Proxy({}, {
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    get(_t, prop: string): any {
      // Thenable — `await queryStub` resolves to { data: [], error: null }
      if (prop === "then") {
        return (resolve: (v: unknown) => void) =>
          resolve({ data: [], error: null });
      }
      if (prop === "maybeSingle" || prop === "single") {
        return () => Promise.resolve({ data: null, error: null });
      }
      // Any other method (select, eq, order, limit, insert, …) chains another query stub
      return () => makeQueryStub();
    },
  });
}

// eslint-disable-next-line @typescript-eslint/no-explicit-any
export function makeSupabaseStub(): any {
  // Plain object — intentionally NOT thenable so async functions can safely return it
  return {
    from: () => makeQueryStub(),
    rpc:  () => makeQueryStub(),
    auth: {
      getUser:                () => Promise.resolve({ data: { user: null }, error: null }),
      signInWithOtp:          () => Promise.resolve({ data: null, error: null }),
      signOut:                () => Promise.resolve({ error: null }),
      exchangeCodeForSession: () => Promise.resolve({ data: null, error: null }),
    },
  };
}
