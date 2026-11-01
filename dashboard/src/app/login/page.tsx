"use client";

import { FormEvent, useState } from "react";
import Image from "next/image";
import { createClient } from "@/lib/supabase/client";
import { useRouter } from "next/navigation";

export default function LoginPage() {
  const router = useRouter();
  const [email, setEmail] = useState("parent@thinko.local");
  const [password, setPassword] = useState("password123");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    setLoading(true);
    setError(null);
    const supabase = createClient();
    const { error: err } = await supabase.auth.signInWithPassword({ email, password });
    setLoading(false);
    if (err) {
      setError(err.message);
      return;
    }
    router.replace("/");
    router.refresh();
  }

  return (
    <div className="relative mx-auto flex min-h-screen max-w-lg flex-col justify-center px-4 py-12">
      <div
        aria-hidden
        className="pointer-events-none absolute inset-x-0 top-0 h-64 bg-[radial-gradient(ellipse_at_top,var(--accent-soft),transparent_70%)]"
      />
      <div className="page-enter relative panel shadow-[var(--shadow)]">
        <div className="mb-6 flex items-center gap-3">
          <Image
            src="/thinko-icon.png"
            alt="Lil-Vro"
            width={48}
            height={48}
            className="h-12 w-12 rounded-xl shadow-sm"
            priority
          />
          <div>
            <p className="text-sm font-medium text-[var(--muted)]">Parent access</p>
            <h1 className="display text-3xl tracking-tight">Lil-Vro</h1>
          </div>
        </div>
        <p className="text-[var(--muted)] leading-relaxed">
          See streaks, study time, and mastery while your child learns by voice with Lil-Vro —
          no screen during the session.
        </p>
        <form onSubmit={onSubmit} className="mt-8 space-y-4">
          <label className="block text-sm font-medium">
            <span className="text-[var(--muted)]">Email</span>
            <input
              className="input"
              type="email"
              autoComplete="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              required
            />
          </label>
          <label className="block text-sm font-medium">
            <span className="text-[var(--muted)]">Password</span>
            <input
              className="input"
              type="password"
              autoComplete="current-password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
            />
          </label>
          {error ? <p className="text-sm text-red-700">{error}</p> : null}
          <button type="submit" disabled={loading} className="btn-primary w-full">
            {loading ? "Signing in…" : "Sign in to dashboard"}
          </button>
        </form>
        <p className="mt-5 text-xs leading-relaxed text-[var(--muted)]">
          Local demo: parent@thinko.local / password123. On Vercel, point env vars at your
          hosted Supabase project and create a real parent account.
        </p>
      </div>
    </div>
  );
}
