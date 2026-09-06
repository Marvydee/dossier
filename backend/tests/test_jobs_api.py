"""Tests the jobs router in isolation (not the full app with its worker
lifespan) — a bare FastAPI app with just this router mounted, the auth
dependency overridden to a fixed test user, and get_service_client patched to
a FakeSupabaseClient. Covers exactly the things that matter for a paid,
per-job-token product: the cap is enforced, invalid input never reaches a
scrape, no JWT means no access, and a job costs exactly one token.
"""
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.routers import jobs as jobs_module
from app.auth import get_current_user_id
from tests.fakes import FakeSupabaseClient

TEST_USER = 'user-1'


def _make_client(fake_db: FakeSupabaseClient, *, authed=True) -> TestClient:
    app = FastAPI()
    app.include_router(jobs_module.router)

    if authed:
        app.dependency_overrides[get_current_user_id] = lambda: TEST_USER

    jobs_module.get_service_client = lambda: fake_db
    return TestClient(app)


def _seeded_db(*, token_balance=3, plan='free'):
    db = FakeSupabaseClient()
    db.seed('categories', [
        {'slug': 'pharmacy', 'label': 'Pharmacy', 'active': True},
        {'slug': 'supermarket', 'label': 'Supermarket', 'active': True},
    ])
    db.seed('cities', [
        {'slug': 'lagos', 'label': 'Lagos', 'active': True},
        {'slug': 'abuja', 'label': 'Abuja', 'active': True},
    ])
    db.seed('profiles', [
        {'id': TEST_USER, 'email': 'user@example.com',
         'token_balance': token_balance, 'plan': plan, 'plan_expires_at': None},
    ])

    def spend_token(params):
        profile = next(p for p in db.tables['profiles'] if p['id'] == params['p_user_id'])
        if profile['plan'] == 'unlimited':
            return True
        if profile['token_balance'] > 0:
            profile['token_balance'] -= 1
            return True
        return False

    db.on_rpc('spend_token', spend_token)
    return db


class TestCreateJob:

    def test_valid_job_spends_one_token(self):
        db = _seeded_db(token_balance=3)
        client = _make_client(db)

        resp = client.post('/jobs', json={'categories': ['pharmacy'], 'cities': ['lagos']})

        assert resp.status_code == 201
        assert db.tables['profiles'][0]['token_balance'] == 2
        assert resp.json()['status'] == 'queued'

    def test_no_tokens_remaining_returns_402_and_does_not_leave_a_job_row(self):
        db = _seeded_db(token_balance=0)
        client = _make_client(db)

        resp = client.post('/jobs', json={'categories': ['pharmacy'], 'cities': ['lagos']})

        assert resp.status_code == 402
        assert db.tables['generation_jobs'] == []

    def test_unlimited_plan_never_runs_out(self):
        db = _seeded_db(token_balance=0, plan='unlimited')
        client = _make_client(db)

        resp = client.post('/jobs', json={'categories': ['pharmacy'], 'cities': ['lagos']})

        assert resp.status_code == 201

    def test_invalid_category_rejected_before_spending_a_token(self):
        db = _seeded_db(token_balance=3)
        client = _make_client(db)

        resp = client.post('/jobs', json={'categories': ['not-a-real-category'], 'cities': ['lagos']})

        assert resp.status_code == 400
        assert db.tables['profiles'][0]['token_balance'] == 3   # untouched
        assert db.tables.get('generation_jobs', []) == []

    def test_invalid_city_rejected(self):
        db = _seeded_db(token_balance=3)
        client = _make_client(db)

        resp = client.post('/jobs', json={'categories': ['pharmacy'], 'cities': ['not-a-real-city']})

        assert resp.status_code == 400

    def test_too_many_categories_rejected(self):
        db = _seeded_db(token_balance=3)
        db.seed('categories', [
            {'slug': f'cat-{i}', 'label': f'Cat {i}', 'active': True} for i in range(9)
        ])
        client = _make_client(db)

        resp = client.post('/jobs', json={
            'categories': [f'cat-{i}' for i in range(9)],  # over the 8-category cap
            'cities': ['lagos'],
        })

        assert resp.status_code == 400

    def test_missing_auth_returns_401(self):
        db = _seeded_db(token_balance=3)
        client = _make_client(db, authed=False)

        resp = client.post('/jobs', json={'categories': ['pharmacy'], 'cities': ['lagos']})

        assert resp.status_code == 401

    def test_empty_category_list_rejected_by_schema(self):
        db = _seeded_db(token_balance=3)
        client = _make_client(db)

        resp = client.post('/jobs', json={'categories': [], 'cities': ['lagos']})

        assert resp.status_code == 422


class TestGetJob:

    def test_cannot_read_another_users_job(self):
        db = _seeded_db(token_balance=3)
        db.seed('generation_jobs', [
            {'id': 'job-1', 'user_id': 'someone-else', 'status': 'completed',
             'categories': ['pharmacy'], 'cities': ['lagos']},
        ])
        client = _make_client(db)

        resp = client.get('/jobs/job-1')

        assert resp.status_code == 404

    def test_can_read_own_job(self):
        db = _seeded_db(token_balance=3)
        db.seed('generation_jobs', [
            {'id': 'job-1', 'user_id': TEST_USER, 'status': 'completed',
             'categories': ['pharmacy'], 'cities': ['lagos']},
        ])
        client = _make_client(db)

        resp = client.get('/jobs/job-1')

        assert resp.status_code == 200
        assert resp.json()['id'] == 'job-1'


class TestDownloadJob:

    def test_incomplete_job_cannot_be_downloaded(self):
        db = _seeded_db(token_balance=3)
        db.seed('generation_jobs', [
            {'id': 'job-1', 'user_id': TEST_USER, 'status': 'running',
             'categories': ['pharmacy'], 'cities': ['lagos']},
        ])
        client = _make_client(db)

        resp = client.get('/jobs/job-1/download')

        assert resp.status_code == 409

    def test_completed_job_returns_a_signed_url(self):
        db = _seeded_db(token_balance=3)
        db.seed('generation_jobs', [
            {'id': 'job-1', 'user_id': TEST_USER, 'status': 'completed',
             'result_path': f'{TEST_USER}/job-1.xlsx',
             'categories': ['pharmacy'], 'cities': ['lagos']},
        ])
        client = _make_client(db)

        resp = client.get('/jobs/job-1/download')

        assert resp.status_code == 200
        assert resp.json()['url'].startswith('https://')
