"""Tests the worker's job-processing logic in isolation: get_service_client
and run_job are both patched, so this never touches the network or a real
database. Covers the behaviour added alongside the quality filter — a job
that completes with zero deliverable rows must refund the spent token, same
as a hard failure, without being marked 'failed' itself (nothing errored).
"""
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
