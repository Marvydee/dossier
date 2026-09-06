import Link from 'next/link';
import Nav from '@/components/Nav';

const STEPS = [
  {
    n: '01',
    title: 'Name what you need',
    body: 'Pick up to 8 categories and 8 cities — Lagos to London, pharmacies to printers.',
  },
  {
    n: '02',
    title: 'We compile the record',
    body: 'Three sources cross-checked, deduplicated, and phone numbers normalised — no guesswork.',
  },
  {
    n: '03',
    title: 'Ten entries, verified',
    body: 'A random, evenly-spread sample where every business has a real phone or email. No dead ends.',
  },
];

export default function Home() {
  return (
    <div className="flex min-h-screen flex-col">
      <Nav />

      <main className="flex-1">
        <section className="mx-auto max-w-5xl px-6 pt-20 pb-16 sm:pt-28">
          <div className="grid gap-12 sm:grid-cols-[1.2fr_1fr] sm:items-start">
            <div>
              <p className="text-xs uppercase tracking-widest text-pine">
                A record of real businesses
              </p>
              <h1 className="mt-4 font-display text-5xl font-medium leading-[1.1] text-ink sm:text-6xl">
                Every list,
                <br />
                compiled to order.
              </h1>
              <p className="mt-6 max-w-md text-lg text-ink-soft">
                Every search opens a fresh dossier — real Nigerian businesses, and beyond.
                Name a category and a city; we hand back ten verified contacts, drawn fresh
                each time.
              </p>
              <div className="mt-9 flex flex-wrap items-center gap-5">
                <Link
                  href="/signup"
                  className="rounded bg-pine px-6 py-3 font-medium text-paper hover:bg-pine-hover"
                >
                  Get 3 free generations
                </Link>
                <Link href="/pricing" className="text-sm font-medium text-ink underline decoration-paper-line underline-offset-4 hover:decoration-ink">
                  See pricing
                </Link>
              </div>
            </div>

            {/* A tangible sample of the actual product — not decoration */}
            <div className="rounded border border-paper-line bg-white/40 p-5">
              <p className="text-xs uppercase tracking-widest text-ink-faint">Sample entry</p>
              <div className="mt-3 space-y-2 border-t border-paper-line pt-3 font-body text-sm">
                <p className="font-display text-lg text-ink">Alpha Pharmacy &amp; Stores</p>
                <dl className="grid grid-cols-[auto_1fr] gap-x-3 gap-y-1 text-ink-soft">
                  <dt className="uppercase text-xs tracking-wide text-ink-faint">Phone</dt>
                  <dd className="tabular-nums">0803 123 4567</dd>
                  <dt className="uppercase text-xs tracking-wide text-ink-faint">City</dt>
                  <dd>Lagos</dd>
                  <dt className="uppercase text-xs tracking-wide text-ink-faint">Category</dt>
                  <dd>Pharmacy</dd>
                  <dt className="uppercase text-xs tracking-wide text-ink-faint">Source</dt>
                  <dd>BusinessList</dd>
                </dl>
              </div>
            </div>
          </div>
        </section>

        <section className="ruled border-y border-paper-line bg-paper-dim">
          <div className="mx-auto max-w-5xl px-6 py-16">
            <ol className="divide-y divide-paper-line">
              {STEPS.map((step) => (
                <li key={step.n} className="grid gap-2 py-6 sm:grid-cols-[80px_1fr] sm:gap-8">
                  <span className="font-display text-3xl text-pine">{step.n}</span>
                  <div>
                    <h3 className="font-display text-xl text-ink">{step.title}</h3>
                    <p className="mt-1 max-w-xl text-ink-soft">{step.body}</p>
                  </div>
                </li>
              ))}
            </ol>
          </div>
        </section>
      </main>

      <footer className="border-t border-paper-line px-6 py-8 text-center text-xs uppercase tracking-widest text-ink-faint">
        Dossier — compiled by MDJ FORGE
      </footer>
    </div>
  );
}
