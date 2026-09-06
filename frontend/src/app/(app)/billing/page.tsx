'use client';

import { useState } from 'react';
import { apiFetch, ApiError } from '@/lib/api';

const PLANS = [
  { id: 'tokens_10', name: '10 Tokens', price: '₦2,000', description: '₦200 per generation' },
  { id: 'unlimited_year', name: 'Unlimited / Year', price: '₦15,000', description: 'Unlimited generations for 12 months' },
] as const;

export default function Billing() {
  const [loadingPlan, setLoadingPlan] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function handleCheckout(plan: string) {
    setError(null);
    setLoadingPlan(plan);
    try {
      const { authorization_url } = await apiFetch<{ authorization_url: string }>('/billing/checkout', {
        method: 'POST',
        body: JSON.stringify({ plan }),
      });
      window.location.href = authorization_url;
    } catch (e) {
      setError(e instanceof ApiError ? e.message : 'Could not start checkout. Please try again.');
      setLoadingPlan(null);
    }
  }

  return (
    <div>
      <h1 className="font-display text-3xl font-medium text-ink">Billing</h1>
      <p className="mt-1 text-sm text-ink-soft">Buy more tokens or go unlimited, via Paystack.</p>

      {error && <p className="mt-4 text-sm text-brick">{error}</p>}

      <div className="mt-8 grid gap-px overflow-hidden border border-paper-line bg-paper-line sm:grid-cols-2">
        {PLANS.map((plan) => (
          <div key={plan.id} className="bg-paper p-6">
            <h2 className="font-display text-lg font-medium text-ink">{plan.name}</h2>
            <p className="mt-2 font-display text-3xl text-ink">{plan.price}</p>
            <p className="mt-1 text-sm text-ink-soft">{plan.description}</p>
            <button
              onClick={() => handleCheckout(plan.id)}
              disabled={loadingPlan !== null}
              className="mt-6 w-full rounded bg-pine px-4 py-2.5 font-medium text-paper hover:bg-pine-hover disabled:opacity-50"
            >
              {loadingPlan === plan.id ? 'Redirecting to Paystack…' : 'Buy'}
            </button>
          </div>
        ))}
      </div>
    </div>
  );
}
