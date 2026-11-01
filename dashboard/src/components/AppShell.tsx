import Image from "next/image";
import Link from "next/link";
import { MathToggle } from "@/components/MathToggle";

export function AppShell({ children }: { children: React.ReactNode }) {
  return (
    <div className="min-h-screen">
      <header className="sticky top-0 z-40 border-b border-[var(--border)] bg-[var(--surface)]/90 backdrop-blur-md">
        <div className="mx-auto flex max-w-6xl flex-col gap-3 px-4 py-3 sm:px-6">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <Link href="/" className="group flex items-center gap-2.5">
              <Image
                src="/thinko-icon.png"
                alt="Lil-Vro"
                width={32}
                height={32}
                className="h-8 w-8 rounded-lg shadow-sm transition group-hover:opacity-90"
                priority
              />
              <span className="display text-xl tracking-tight">Lil-Vro</span>
              <span className="hidden text-sm text-[var(--muted)] sm:inline">
                for parents
              </span>
            </Link>
          </div>
        </div>
      </header>
      <main className="mx-auto max-w-6xl px-4 py-8 sm:px-6 sm:py-10">{children}</main>
      <footer className="mx-auto max-w-6xl px-4 pb-10 text-sm text-[var(--muted)] sm:px-6">
        Study sessions stay on your family&apos;s account. No kid-facing screen during tutoring with
        Lil-Vro.
      </footer>
      <MathToggle targetHref="/child" label="Child view" />
    </div>
  );
}
