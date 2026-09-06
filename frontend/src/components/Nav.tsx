'use client';

import { useState } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { createClient } from '@/lib/supabase/client';

const linkClass = 'uppercase tracking-wide text-xs text-ink-soft hover:text-ink';

export default function Nav({ email }: { email?: string }) {
  const router = useRouter();
  const supabase = createClient();
  const [open, setOpen] = useState(false);

  async function signOut() {
    await supabase.auth.signOut();
    router.push('/login');
    router.refresh();
  }

  return (
    <nav className="border-b border-paper-line bg-paper">
      <div className="mx-auto flex max-w-5xl items-center justify-between px-6 py-5">
        <Link
          href={email ? '/dashboard' : '/'}
          className="font-display text-2xl italic text-ink"
          onClick={() => setOpen(false)}
        >
          Dossier
        </Link>

        {/* Desktop nav — collapses to a menu button below md */}
        {email ? (
          <div className="hidden items-center gap-6 text-sm md:flex">
            <Link href="/dashboard" className={linkClass}>Dashboard</Link>
            <Link href="/generate" className={linkClass}>Generate</Link>
            <Link href="/billing" className={linkClass}>Billing</Link>
            <span className="max-w-40 truncate text-ink-faint">{email}</span>
            <button
              onClick={signOut}
              className="rounded border border-paper-line px-3 py-1.5 uppercase tracking-wide text-xs text-ink-soft hover:border-ink-soft hover:text-ink"
            >
              Sign out
            </button>
          </div>
        ) : (
          <div className="hidden items-center gap-5 text-sm md:flex">
            <Link href="/pricing" className={linkClass}>Pricing</Link>
            <Link href="/login" className={linkClass}>Log in</Link>
            <Link href="/signup" className="rounded bg-pine px-4 py-2 text-sm font-medium text-paper hover:bg-pine-hover">
              Sign up
            </Link>
          </div>
        )}

        {/* Mobile menu button */}
        <button
          onClick={() => setOpen((v) => !v)}
          aria-label="Toggle menu"
          aria-expanded={open}
          className="flex h-9 w-9 flex-col items-center justify-center gap-1.5 md:hidden"
        >
          <span className={`block h-px w-5 bg-ink transition ${open ? 'translate-y-2 rotate-45' : ''}`} />
          <span className={`block h-px w-5 bg-ink transition ${open ? 'opacity-0' : ''}`} />
          <span className={`block h-px w-5 bg-ink transition ${open ? '-translate-y-2 -rotate-45' : ''}`} />
        </button>
      </div>

      {/* Mobile menu panel */}
      {open && (
        <div className="border-t border-paper-line px-6 py-4 md:hidden">
          {email ? (
            <div className="flex flex-col gap-4 text-sm">
              <Link href="/dashboard" className={linkClass} onClick={() => setOpen(false)}>Dashboard</Link>
              <Link href="/generate" className={linkClass} onClick={() => setOpen(false)}>Generate</Link>
              <Link href="/billing" className={linkClass} onClick={() => setOpen(false)}>Billing</Link>
              <span className="truncate text-ink-faint">{email}</span>
              <button
                onClick={signOut}
                className="w-fit rounded border border-paper-line px-3 py-1.5 uppercase tracking-wide text-xs text-ink-soft hover:border-ink-soft hover:text-ink"
              >
                Sign out
              </button>
            </div>
          ) : (
            <div className="flex flex-col gap-4 text-sm">
              <Link href="/pricing" className={linkClass} onClick={() => setOpen(false)}>Pricing</Link>
              <Link href="/login" className={linkClass} onClick={() => setOpen(false)}>Log in</Link>
              <Link
                href="/signup"
                onClick={() => setOpen(false)}
                className="w-fit rounded bg-pine px-4 py-2 text-sm font-medium text-paper hover:bg-pine-hover"
              >
                Sign up
              </Link>
            </div>
          )}
        </div>
      )}
    </nav>
  );
}
