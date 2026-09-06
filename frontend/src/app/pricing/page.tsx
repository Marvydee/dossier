import Link from 'next/link';
import Nav from '@/components/Nav';

const PLANS = [
  {
    name: 'Free',
    price: '₦0',
    period: 'to start',
    features: ['3 free generations', 'Up to 8 categories × 8 cities', 'Excel export'],
    cta: 'Sign up free',
    href: '/signup',
  },
  {
    name: 'Token Pack',
    price: '₦2,000',
    period: 'for 10 generations',
    features: ['10 generations, ₦200 each', 'Same coverage as free', 'Tokens never expire'],
    cta: 'Get started',
    href: '/signup',
    highlight: true,
  },
  {
    name: 'Unlimited',
    price: '₦15,000',
    period: 'per year',
    features: ['Unlimited generations, 12 months', 'Priority processing', 'Best for regular use'],
    cta: 'Go unlimited',
    href: '/signup',
  },
];

export default function Pricing() {
  return (
    <div className="flex min-h-screen flex-col">
      <Nav />
      <main className="mx-auto max-w-5xl flex-1 px-6 py-20">
        <p className="text-xs uppercase tracking-widest text-pine">Pricing</p>
        <h1 className="mt-3 font-display text-4xl font-medium text-ink">Pay for the record, not the guesswork.</h1>
        <p className="mt-3 max-w-xl text-ink-soft">
          Every account opens with 3 free generations. Top up tokens or go unlimited whenever
          you need to.
        </p>

        <div className="mt-14 grid gap-px overflow-hidden rounded border border-paper-line bg-paper-line sm:grid-cols-3">
          {PLANS.map((plan) => (
            <div
              key={plan.name}
              className={`flex flex-col p-7 ${plan.highlight ? 'bg-pine-tint' : 'bg-paper'}`}
            >
              <h2 className="font-display text-xl font-medium text-ink">{plan.name}</h2>
              <p className="mt-4">
                <span className="font-display text-4xl text-ink">{plan.price}</span>
              </p>
              <p className="text-xs uppercase tracking-wide text-ink-faint">{plan.period}</p>
              <ul className="mt-6 flex-1 space-y-2.5 text-sm text-ink-soft">
                {plan.features.map((f) => (
                  <li key={f} className="flex gap-2">
                    <span className="text-pine">—</span> {f}
                  </li>
                ))}
              </ul>
              <Link
                href={plan.href}
                className={`mt-8 block rounded px-4 py-2.5 text-center text-sm font-medium ${
                  plan.highlight
                    ? 'bg-pine text-paper hover:bg-pine-hover'
                    : 'border border-paper-line text-ink hover:border-ink-soft'
                }`}
              >
                {plan.cta}
              </Link>
            </div>
          ))}
        </div>
      </main>
    </div>
  );
}
