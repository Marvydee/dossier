'use client';

import { useEffect, useState } from 'react';
import Link from 'next/link';
import { createClient } from '@/lib/supabase/client';
import type { Profile } from '@/lib/types';

export default function BillingReturn() {
  const [profile, setProfile] = useState<Profile | null>(null);
  const [checks, setChecks] = useState(0);

  useEffect(() => {
    const supabase = createClient();
    let cancelled = false;

    async function poll() {
      const {
        data: { user },
      } = await supabase.auth.getUser();
      if (!user || cancelled) return;

      const { data } = await supabase.from('profiles').select('*').eq('id', user.id).single<Profile>();
      if (!cancelled && data) setProfile(data);
    }

    // Paystack's webhook usually lands within a couple of seconds — poll a
    // few times rather than relying on a single fetch racing the webhook.
    const interval = setInterval(() => {
      poll();
      setChecks((c) => c + 1);
    }, 2000);
    poll();

    return () => {
      cancelled = true;
      clearInterval(interval);
    };
  }, []);

  const stillWaiting = checks < 8 && !profile;

  return (
    <div className="mx-auto max-w-md text-center">
      <h1 className="font-display text-3xl font-medium text-ink">
        {stillWaiting ? 'Confirming your payment…' : "You're all set"}
      </h1>
      <p className="mt-3 text-ink-soft">
        {stillWaiting
          ? "This usually takes a few seconds while we confirm with Paystack."
          : profile?.plan === 'unlimited'
            ? 'Your unlimited plan is now active.'
            : `You now have ${profile?.token_balance ?? '—'} tokens.`}
      </p>
      <Link href="/dashboard" className="mt-6 inline-block font-medium text-pine underline underline-offset-4">
        Go to dashboard
      </Link>
    </div>
  );
}
