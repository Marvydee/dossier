'use client';

import { Suspense, useState } from 'react';
import Link from 'next/link';
import { useRouter, useSearchParams } from 'next/navigation';
import Nav from '@/components/Nav';
import { createClient } from '@/lib/supabase/client';

function LoginForm() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const supabase = createClient();

  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setLoading(true);

    const { error } = await supabase.auth.signInWithPassword({ email, password });

    setLoading(false);
    if (error) {
      setError(error.message);
      return;
    }
    router.push(searchParams.get('redirect') || '/dashboard');
    router.refresh();
  }

  return (
    <main className="mx-auto flex w-full max-w-sm flex-1 flex-col justify-center px-6 py-16">
      <h1 className="font-display text-3xl font-medium text-ink">Welcome back</h1>

      <form onSubmit={handleSubmit} className="mt-8 space-y-4">
        <div>
          <label className="text-xs uppercase tracking-wide text-ink-faint">Email</label>
          <input
            type="email"
            required
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            className="mt-1 w-full rounded border border-paper-line bg-white/60 px-3 py-2 text-ink focus:border-pine focus:outline-none"
          />
        </div>
        <div>
          <label className="text-xs uppercase tracking-wide text-ink-faint">Password</label>
          <input
            type="password"
            required
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            className="mt-1 w-full rounded border border-paper-line bg-white/60 px-3 py-2 text-ink focus:border-pine focus:outline-none"
          />
        </div>

        {error && <p className="text-sm text-brick">{error}</p>}

        <button
          type="submit"
          disabled={loading}
          className="w-full rounded bg-pine px-4 py-2.5 font-medium text-paper hover:bg-pine-hover disabled:opacity-50"
        >
          {loading ? 'Logging in…' : 'Log in'}
        </button>
      </form>

      <p className="mt-6 text-center text-sm text-ink-soft">
        Don&apos;t have an account?{' '}
        <Link href="/signup" className="font-medium text-ink underline decoration-paper-line underline-offset-4">
          Sign up
        </Link>
      </p>
    </main>
  );
}

export default function Login() {
  return (
    <div className="flex min-h-screen flex-col">
      <Nav />
      <Suspense>
        <LoginForm />
      </Suspense>
    </div>
  );
}
