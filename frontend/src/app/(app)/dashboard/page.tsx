import Link from 'next/link';
import { createClient } from '@/lib/supabase/server';
import type { Job, Profile } from '@/lib/types';

const STATUS_STYLES: Record<string, string> = {
  queued: 'border-ink-faint text-ink-soft',
  running: 'border-pine text-pine',
  completed: 'border-brass text-brass',
  failed: 'border-brick text-brick',
};

export default async function Dashboard() {
  const supabase = await createClient();
  const {
    data: { user },
  } = await supabase.auth.getUser();

  const { data: profile } = await supabase
    .from('profiles')
    .select('*')
    .eq('id', user!.id)
    .single<Profile>();

  const { data: jobs } = await supabase
    .from('generation_jobs')
    .select('*')
    .order('created_at', { ascending: false })
    .limit(10)
    .returns<Job[]>();

  return (
    <div>
      <div className="flex flex-wrap items-center justify-between gap-4">
        <h1 className="font-display text-3xl font-medium text-ink">Your record</h1>
        <Link
          href="/generate"
          className="rounded bg-pine px-4 py-2 text-sm font-medium text-paper hover:bg-pine-hover"
        >
          New Generation
        </Link>
      </div>

      <div className="mt-8 flex items-baseline gap-4 border-y border-paper-line py-6">
        {profile?.plan === 'unlimited' ? (
          <>
            <span className="font-display text-4xl text-ink">Unlimited</span>
            <span className="text-sm text-ink-soft">
              active until {new Date(profile.plan_expires_at!).toLocaleDateString()}
            </span>
          </>
        ) : (
          <>
            <span className="font-display text-5xl tabular-nums text-ink">
              {profile?.token_balance ?? 0}
            </span>
            <span className="text-xs uppercase tracking-wide text-ink-faint">
              tokens remaining
            </span>
          </>
        )}
        {profile?.plan !== 'unlimited' && (profile?.token_balance ?? 0) === 0 && (
          <Link href="/billing" className="ml-auto text-sm font-medium text-pine underline underline-offset-4">
            Buy more →
          </Link>
        )}
      </div>

      <h2 className="mt-10 text-xs uppercase tracking-widest text-ink-faint">Recent generations</h2>
      {!jobs || jobs.length === 0 ? (
        <p className="mt-3 text-sm text-ink-soft">
          No generations yet.{' '}
          <Link href="/generate" className="font-medium text-pine">
            Start your first one
          </Link>
          .
        </p>
      ) : (
        <div className="mt-3 divide-y divide-paper-line border-y border-paper-line">
          {jobs.map((job) => (
            <Link
              key={job.id}
              href={`/jobs/${job.id}`}
              className="flex items-center justify-between gap-4 py-4 hover:bg-paper-dim"
            >
              <div>
                <p className="font-display text-lg text-ink">
                  {job.categories.join(', ')} <span className="text-ink-faint">in</span> {job.cities.join(', ')}
                </p>
                <p className="text-xs text-ink-faint">
                  {new Date(job.created_at).toLocaleString()}
                  {job.row_count != null && ` · ${job.row_count} businesses`}
                </p>
              </div>
              <span
                className={`shrink-0 rounded border px-2.5 py-1 text-xs uppercase tracking-wide ${STATUS_STYLES[job.status]}`}
              >
                {job.status}
              </span>
            </Link>
          ))}
        </div>
      )}
    </div>
  );
}
