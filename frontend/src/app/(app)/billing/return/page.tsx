'use client';

import { Suspense, useEffect, useState } from 'react';
import Link from 'next/link';
import { useSearchParams } from 'next/navigation';
import { createClient } from '@/lib/supabase/client';
import { apiFetch } from '@/lib/api';
import type { Profile } from '@/lib/types';

type Phase = 'verifying' | 'done' | 'error';

function BillingReturnContent() {
  const searchParams = useSearchParams();
  const reference = searchParams.get('reference') ?? searchParams.get('trxref');

  const [phase, setPhase] = useState<Phase>('verifying');
  const [profile, setProfile] = useState<Profile | null>(null);

  useEffect(() => {
    let cancelled = false;

    async function run() {
      if (!reference) {
        setPhase('error');
        return;
      }

      // This is the actual crediting step — a direct server-to-server check
      // against Paystack's API, not a webhook (this Paystack account's one
      // allowed webhook URL already belongs to another project). The
      // backend also reconciles any payment that never reaches this page
      // (closed tab, dropped connection) a couple of minutes later, as a
      // safety net.
      try {
        await apiFetch('/billing/verify', {
          method: 'POST',
          body: JSON.stringify({ reference }),
        });
      } catch {
        // fall through and still check the profile — the payment may have
        // already been credited by the background reconciler
      }

      const supabase = createClient();
      const {
        data: { user },
      } = await supabase.auth.getUser();
      if (!user || cancelled) return;

      const { data } = await supabase.from('profiles').select('*').eq('id', user.id).single<Profile>();
      if (cancelled) return;
      if (data) setProfile(data);
      setPhase('done');
    }

    run();
    return () => {
      cancelled = true;
    };
  }, [reference]);

  return (
    <div className="mx-auto max-w-md text-center">
      <h1 className="font-display text-3xl font-medium text-ink">
        {phase === 'verifying' && 'Confirming your payment…'}
        {phase === 'done' && "You're all set"}
        {phase === 'error' && 'Something went wrong'}
      </h1>
      <p className="mt-3 text-ink-soft">
        {phase === 'verifying' && 'This usually takes a couple of seconds.'}
        {phase === 'done' &&
          (profile?.plan === 'unlimited'
            ? 'Your unlimited plan is now active.'
            : `You now have ${profile?.token_balance ?? '—'} tokens.`)}
        {phase === 'error' &&
          "We couldn't find a payment reference for this page. If you completed a payment, it'll be picked up automatically within a couple of minutes — check your dashboard shortly."}
      </p>
      <Link href="/dashboard" className="mt-6 inline-block font-medium text-pine underline underline-offset-4">
        Go to dashboard
      </Link>
    </div>
  );
}

export default function BillingReturn() {
  return (
    <Suspense>
      <BillingReturnContent />
    </Suspense>
  );
}
