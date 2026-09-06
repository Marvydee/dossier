"""Tests the worker's job-processing logic in isolation: get_service_client
and run_job are both patched, so this never touches the network or a real
database. Covers the behaviour added alongside the quality filter — a job
that completes with zero deliverable rows must refund the spent token, same
as a hard failure, without being marked 'failed' itself (nothing errored).

Also covers reconcile_pending_payments() — the safety net for a user who
pays but never lands back on /billing/return (closed the tab, connection
dropped). This project has no webhook fallback (its Paystack account's one
allowed webhook URL already belongs to another project — see billing.py),
so this periodic sweep is the only thing that catches that case.
"""
from datetime import datetime, timezone, timedelta
from unittest.mock import patch

from app import worker
from tests.fakes import FakeSupabaseClient

CATEGORY_ROW = {'slug': 'pharmacy', 'label': 'Pharmacy', 'businesslist_slug': 'pharmacies',
                'finelib_slug': None, 'osm_shop_tag': None, 'osm_amenity_tag': None}
CITY_ROW = {'slug': 'lagos', 'label': 'Lagos', 'is_nigeria': True, 'lat': 6.5244, 'lon': 3.3792}


def _seeded_db(job):
    db = FakeSupabaseClient()
    db.seed('categories', [CATEGORY_ROW])
    db.seed('cities', [CITY_ROW])
    db.seed('generation_jobs', [job])
    db.on_rpc('claim_next_job', lambda params: [job])
    db.on_rpc('refund_token', lambda params: None)
    return db


def _base_job():
    return {
        'id': 'job-1', 'user_id': 'user-1', 'status': 'queued',
        'categories': ['pharmacy'], 'cities': ['lagos'],
        'progress_current': 0, 'progress_total': 0,
    }


class TestProcessNextJob:

    def test_no_queued_job_is_a_silent_no_op(self):
        db = FakeSupabaseClient()
        db.on_rpc('claim_next_job', lambda params: [])
        with patch.object(worker, 'get_service_client', return_value=db):
            worker._process_next_job()   # must not raise
        assert db.rpc_calls == [('claim_next_job', {})]

    def test_successful_job_with_results_does_not_refund(self):
        job = _base_job()
        db = _seeded_db(job)
        rows = [{'Business Name': 'Alpha Pharmacy', 'Email': '', 'Phone Number': '08031234567',
                  'Website': '', 'Address': '', 'City': 'lagos', 'Category': 'pharmacy',
                  'Source': 'BusinessList'}]

        with patch.object(worker, 'get_service_client', return_value=db), \
             patch.object(worker, 'run_job', return_value=rows):
            worker._process_next_job()

        updated = db.tables['generation_jobs'][0]
        assert updated['status'] == 'completed'
        assert updated['row_count'] == 1
        assert 'refund_token' not in [name for name, _ in db.rpc_calls]

    def test_zero_row_result_still_completes_but_refunds_the_token(self):
        job = _base_job()
        db = _seeded_db(job)

        with patch.object(worker, 'get_service_client', return_value=db), \
             patch.object(worker, 'run_job', return_value=[]):
            worker._process_next_job()

        updated = db.tables['generation_jobs'][0]
        assert updated['status'] == 'completed'   # not 'failed' — nothing errored
        assert updated['row_count'] == 0
        refund_calls = [params for name, params in db.rpc_calls if name == 'refund_token']
        assert refund_calls == [{'p_user_id': 'user-1', 'p_job_id': 'job-1'}]

    def test_exception_during_scraping_marks_failed_and_refunds(self):
        job = _base_job()
        db = _seeded_db(job)

        with patch.object(worker, 'get_service_client', return_value=db), \
             patch.object(worker, 'run_job', side_effect=Exception('boom')):
            worker._process_next_job()

        updated = db.tables['generation_jobs'][0]
        assert updated['status'] == 'failed'
        assert 'boom' in updated['error']
        refund_calls = [params for name, params in db.rpc_calls if name == 'refund_token']
        assert refund_calls == [{'p_user_id': 'user-1', 'p_job_id': 'job-1'}]

    def test_progress_callback_updates_the_job_row(self):
        job = _base_job()
        db = _seeded_db(job)

        def fake_run_job(categories, cities, **kwargs):
            kwargs['progress_cb'](3, 10, 'halfway there')
            return []

        with patch.object(worker, 'get_service_client', return_value=db), \
             patch.object(worker, 'run_job', side_effect=fake_run_job):
            worker._process_next_job()

        updated = db.tables['generation_jobs'][0]
        assert updated['progress_current'] == 3
        assert updated['progress_total'] == 10


def _old_timestamp(minutes_ago=5):
    return (datetime.now(timezone.utc) - timedelta(minutes=minutes_ago)).isoformat()


def _recent_timestamp(seconds_ago=10):
    return (datetime.now(timezone.utc) - timedelta(seconds=seconds_ago)).isoformat()


class TestReconcilePendingPayments:

    def _seeded_db(self, payments):
        db = FakeSupabaseClient()
        db.seed('profiles', [
            {'id': 'user-1', 'email': 'user@example.com', 'token_balance': 3,
             'plan': 'free', 'plan_expires_at': None},
        ])
        db.seed('payments', payments)

        def credit_purchase(params):
            profile = next(p for p in db.tables['profiles'] if p['id'] == params['p_user_id'])
            if params['p_plan'] == 'tokens_10':
                profile['token_balance'] += 10
            else:
                profile['plan'] = 'unlimited'
            db.tables.setdefault('token_transactions', []).append(
                {'user_id': params['p_user_id'], 'paystack_reference': params['p_paystack_reference']})
            return None

        db.on_rpc('credit_purchase', credit_purchase)
        return db

    def test_old_pending_payment_that_actually_succeeded_gets_credited(self):
        db = self._seeded_db([
            {'id': 'pay-1', 'user_id': 'user-1', 'paystack_reference': 'ref-1',
             'amount_kobo': 200_000, 'plan': 'tokens_10', 'status': 'pending',
             'created_at': _old_timestamp()},
        ])
        with patch.object(worker, 'get_service_client', return_value=db), \
             patch('app.routers.billing.verify_transaction', return_value={'status': 'success'}):
            worker.reconcile_pending_payments()

        assert db.tables['profiles'][0]['token_balance'] == 13
        assert db.tables['payments'][0]['status'] == 'success'

    def test_recent_pending_payment_is_left_alone(self):
        """The return-page verify call gets the first chance — reconciliation
        shouldn't race it by checking payments that are only seconds old."""
        db = self._seeded_db([
            {'id': 'pay-1', 'user_id': 'user-1', 'paystack_reference': 'ref-1',
             'amount_kobo': 200_000, 'plan': 'tokens_10', 'status': 'pending',
             'created_at': _recent_timestamp()},
        ])
        with patch.object(worker, 'get_service_client', return_value=db), \
             patch('app.routers.billing.verify_transaction') as mock_verify:
            worker.reconcile_pending_payments()

        mock_verify.assert_not_called()
        assert db.tables['profiles'][0]['token_balance'] == 3

    def test_already_settled_payments_are_not_rechecked(self):
        db = self._seeded_db([
            {'id': 'pay-1', 'user_id': 'user-1', 'paystack_reference': 'ref-1',
             'amount_kobo': 200_000, 'plan': 'tokens_10', 'status': 'success',
             'created_at': _old_timestamp()},
        ])
        with patch.object(worker, 'get_service_client', return_value=db), \
             patch('app.routers.billing.verify_transaction') as mock_verify:
            worker.reconcile_pending_payments()

        mock_verify.assert_not_called()

    def test_one_failing_payment_does_not_block_others(self):
        db = self._seeded_db([
            {'id': 'pay-1', 'user_id': 'user-1', 'paystack_reference': 'ref-1',
             'amount_kobo': 200_000, 'plan': 'tokens_10', 'status': 'pending',
             'created_at': _old_timestamp()},
            {'id': 'pay-2', 'user_id': 'user-1', 'paystack_reference': 'ref-2',
             'amount_kobo': 200_000, 'plan': 'tokens_10', 'status': 'pending',
             'created_at': _old_timestamp()},
        ])

        def flaky_verify(ref):
            if ref == 'ref-1':
                raise Exception('Paystack timed out')
            return {'status': 'success'}

        with patch.object(worker, 'get_service_client', return_value=db), \
             patch('app.routers.billing.verify_transaction', side_effect=flaky_verify):
            worker.reconcile_pending_payments()   # must not raise

        assert db.tables['profiles'][0]['token_balance'] == 13   # ref-2 still got credited
