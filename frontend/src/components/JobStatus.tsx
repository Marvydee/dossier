'use client';

import { useEffect, useState } from 'react';
import Link from 'next/link';
import { createClient } from '@/lib/supabase/client';
import { apiFetch } from '@/lib/api';
import type { Job } from '@/lib/types';

const STATUS_LABEL: Record<string, string> = {
  queued: 'Queued — waiting for a worker to pick this up',
  running: 'Running — searching sources now',
  completed: 'Completed',
  failed: 'Failed',
};

export default function JobStatus({ jobId }: { jobId: string }) {
  const [job, setJob] = useState<Job | null>(null);
  const [downloadUrl, setDownloadUrl] = useState<string | null>(null);
  const [downloading, setDownloading] = useState(false);

  useEffect(() => {
    const supabase = createClient();

    supabase
      .from('generation_jobs')
      .select('*')
      .eq('id', jobId)
      .single<Job>()
      .then(({ data }) => data && setJob(data));

    // Live updates as the worker processes this job — no polling needed.
    const channel = supabase
      .channel(`job-${jobId}`)
      .on(
        'postgres_changes',
        { event: 'UPDATE', schema: 'public', table: 'generation_jobs', filter: `id=eq.${jobId}` },
        (payload) => setJob(payload.new as Job)
      )
      .subscribe();

    return () => {
      supabase.removeChannel(channel);
    };
  }, [jobId]);

  async function handleDownload() {
    setDownloading(true);
    try {
      const { url } = await apiFetch<{ url: string }>(`/jobs/${jobId}/download`);
      setDownloadUrl(url);
      window.location.href = url;
    } finally {
      setDownloading(false);
    }
  }

  if (!job) {
    return <p className="text-ink-soft">Loading…</p>;
  }

  const progressPct =
    job.progress_total > 0 ? Math.round((job.progress_current / job.progress_total) * 100) : 0;

  return (
    <div>
      <Link href="/dashboard" className="text-sm text-ink-soft hover:text-ink">
        ← Back to dashboard
      </Link>

      <h1 className="mt-4 font-display text-3xl font-medium text-ink">
        {job.categories.join(', ')} <span className="text-ink-faint">in</span> {job.cities.join(', ')}
      </h1>

      <div className="mt-6 border-t border-paper-line pt-6">
        <p className="font-medium text-ink">{STATUS_LABEL[job.status]}</p>

        {(job.status === 'queued' || job.status === 'running') && (
          <div className="mt-4">
            <div className="h-1.5 w-full overflow-hidden bg-paper-dim">
              <div
                className="h-full bg-pine transition-all"
                style={{ width: `${Math.max(progressPct, 5)}%` }}
              />
            </div>
            <p className="mt-2 text-xs text-ink-faint">
              {job.progress_total > 0
                ? `${job.progress_current} / ${job.progress_total} searches complete`
                : 'Starting…'}
            </p>
          </div>
        )}

        {job.status === 'completed' && job.row_count === 0 && (
          <p className="mt-3 text-sm text-ink-soft">
            No contactable businesses turned up for this search — your token has been refunded.
            Try different categories or cities.
          </p>
        )}

        {job.status === 'completed' && (job.row_count ?? 0) > 0 && (
          <div className="mt-4">
            <p className="text-sm text-ink-soft">{job.row_count} businesses found.</p>
            <button
              onClick={handleDownload}
              disabled={downloading}
              className="mt-3 rounded bg-pine px-5 py-2 font-medium text-paper hover:bg-pine-hover disabled:opacity-50"
            >
              {downloading ? 'Preparing download…' : 'Download Excel file'}
            </button>
            {downloadUrl && (
              <p className="mt-2 text-xs text-ink-faint">
                If the download didn&apos;t start,{' '}
                <a href={downloadUrl} className="text-pine underline">
                  click here
                </a>
                .
              </p>
            )}
          </div>
        )}

        {job.status === 'failed' && (
          <p className="mt-3 text-sm text-brick">
            {job.error || 'Something went wrong.'} Your token has been refunded.
          </p>
        )}
      </div>
    </div>
  );
}
