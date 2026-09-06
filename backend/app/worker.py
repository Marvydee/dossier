"""In-process background worker: polls generation_jobs for queued work and
runs it, and periodically reconciles any payments that were never confirmed.
Started as an asyncio task from main.py's lifespan — no separate worker dyno
for MVP (see the build plan for the cost/complexity tradeoff).
"""
import asyncio
import logging
import tempfile
from datetime import datetime, timezone, timedelta
from pathlib import Path

from .config import get_settings
from .supabase_client import get_service_client
from .scraping.engine import run_job
from .scraping.excel import save_to_excel
from .routers.billing import credit_if_paid

logger = logging.getLogger('worker')

POLL_INTERVAL_SECONDS = 5
RESULT_BUCKET = 'generation-results'

# Payment reconciliation runs far less often than job polling — it's a
# safety net, not the primary path (that's /billing/verify, called from the
# frontend right after Paystack redirects back), and hitting Paystack's API
# every 5s for this would be wasteful.
PAYMENT_RECONCILE_EVERY_N_TICKS = 12   # ~60s at a 5s poll interval


async def poll_loop():
    tick = 0
    while True:
        try:
            await asyncio.to_thread(_process_next_job)
        except Exception:
            logger.exception('Worker tick failed')

        tick += 1
        if tick % PAYMENT_RECONCILE_EVERY_N_TICKS == 0:
            try:
                await asyncio.to_thread(reconcile_pending_payments)
            except Exception:
                logger.exception('Payment reconciliation tick failed')

        await asyncio.sleep(POLL_INTERVAL_SECONDS)


def reconcile_pending_payments():
    """Catches the case where a user pays but never lands back on
    /billing/return to trigger the normal verify-and-credit path (closed the
    tab, connection dropped, etc.) — there's no webhook to fall back on here
    (see billing.py's module docstring on the webhook for why), so this is
    the only safety net. Only checks payments old enough that the return-page
    call has clearly already had its chance, and gives up (marks failed, via
    credit_if_paid) once Paystack itself reports the charge as dead rather
    than retrying forever.
    """
    client = get_service_client()
    cutoff = (datetime.now(timezone.utc) - timedelta(minutes=2)).isoformat()
    pending = (client.table('payments').select('*')
               .eq('status', 'pending').lt('created_at', cutoff).execute().data)

    for payment in pending:
        try:
            credit_if_paid(client, payment)
        except Exception:
            logger.exception('Reconciliation failed for payment %s', payment['id'])


def _process_next_job():
    client = get_service_client()
    claimed = client.rpc('claim_next_job', {}).execute().data
    if not claimed:
        return

    job = claimed[0]
    logger.info('Processing job %s', job['id'])

    try:
        categories = (client.table('categories').select('*')
                      .in_('slug', job['categories']).execute().data)
        cities = (client.table('cities').select('*')
                  .in_('slug', job['cities']).execute().data)

        settings = get_settings()

        def report(current, total, message):
            client.table('generation_jobs').update({
                'progress_current': current,
                'progress_total': total,
            }).eq('id', job['id']).execute()

        rows = run_job(
            categories, cities,
            max_pages_per_search=settings.max_pages_per_search,
            request_delay=settings.request_delay_seconds,
            website_timeout=settings.website_timeout_seconds,
            results_per_job=settings.results_per_job,
            progress_cb=report,
        )

        with tempfile.TemporaryDirectory() as tmp_dir:
            file_path = Path(tmp_dir) / f'{job["id"]}.xlsx'
            save_to_excel(rows, str(file_path))

            storage_path = f'{job["user_id"]}/{job["id"]}.xlsx'
            with open(file_path, 'rb') as f:
                client.storage.from_(RESULT_BUCKET).upload(
                    storage_path, f,
                    {'content-type': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'},
                )

        client.table('generation_jobs').update({
            'status': 'completed',
            'result_path': storage_path,
            'row_count': len(rows),
            'completed_at': datetime.now(timezone.utc).isoformat(),
        }).eq('id', job['id']).execute()

        if not rows:
            # The search ran fine — nothing errored — but the quality filter
            # left nothing contactable to deliver. That's not the user's
            # fault and they shouldn't pay for it: refund, same mechanism as
            # a hard failure, even though the job itself stays 'completed'.
            client.rpc('refund_token', {'p_user_id': job['user_id'], 'p_job_id': job['id']}).execute()

        logger.info('Job %s completed with %d rows', job['id'], len(rows))

    except Exception as e:
        logger.exception('Job %s failed', job['id'])
        client.table('generation_jobs').update({
            'status': 'failed',
            'error': str(e)[:2000],
            'completed_at': datetime.now(timezone.utc).isoformat(),
        }).eq('id', job['id']).execute()
        client.rpc('refund_token', {'p_user_id': job['user_id'], 'p_job_id': job['id']}).execute()
