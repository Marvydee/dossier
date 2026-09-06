"""Tests /billing/verify — the primary payment-confirmation path. This
project shares a Paystack account with another app that already owns the
account's one allowed webhook URL, so confirmation happens by verifying
directly against Paystack's API when the user lands on /billing/return,
rather than via webhook. Covers the things that matter: only the payment's
owner can trigger a credit, it's idempotent, and an unverified/failed
transaction never credits — the same guarantees the webhook tests cover,
now for the path that's actually reachable in production.
"""
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.routers import billing as billing_module
from app.auth import get_current_user_id
from tests.fakes import FakeSupabaseClient

OWNER = 'user-1'
OTHER_USER = 'user-2'


def _make_client(fake_db: FakeSupabaseClient, *, as_user=OWNER) -> TestClient:
    app = FastAPI()
    app.include_router(billing_module.router)
    app.dependency_overrides[get_current_user_id] = lambda: as_user
    billing_module.get_service_client = lambda: fake_db
    return TestClient(app)


def _seeded_db(*, payment_plan='tokens_10', payment_status='pending'):
    db = FakeSupabaseClient()
    db.seed('profiles', [
        {'id': OWNER, 'email': 'owner@example.com', 'token_balance': 3,
         'plan': 'free', 'plan_expires_at': None},
    ])
    db.seed('payments', [
        {'id': 'pay-1', 'user_id': OWNER, 'paystack_reference': 'ref-123',
         'amount_kobo': 200_000, 'plan': payment_plan, 'status': payment_status},
    ])

    def credit_purchase(params):
        ref = params['p_paystack_reference']
        already = any(t.get('paystack_reference') == ref
                       for t in db.tables.get('token_transactions', []))
        if already:
            return None
        profile = next(p for p in db.tables['profiles'] if p['id'] == params['p_user_id'])
        if params['p_plan'] == 'tokens_10':
            profile['token_balance'] += 10
        else:
            profile['plan'] = 'unlimited'
        db.tables.setdefault('token_transactions', []).append({
            'user_id': params['p_user_id'], 'paystack_reference': ref,
        })
        return None

    db.on_rpc('credit_purchase', credit_purchase)
    return db


class TestVerifyEndpoint:

    def test_successful_payment_is_credited(self, monkeypatch):
        db = _seeded_db()
        client = _make_client(db)
        monkeypatch.setattr(billing_module, 'verify_transaction', lambda ref: {'status': 'success'})

        resp = client.post('/billing/verify', json={'reference': 'ref-123'})

        assert resp.status_code == 200
        assert resp.json() == {'credited': True}
        assert db.tables['profiles'][0]['token_balance'] == 13

    def test_unverified_payment_is_not_credited(self, monkeypatch):
        db = _seeded_db()
        client = _make_client(db)
        monkeypatch.setattr(billing_module, 'verify_transaction', lambda ref: {'status': 'abandoned'})

        resp = client.post('/billing/verify', json={'reference': 'ref-123'})

        assert resp.status_code == 200
        assert resp.json() == {'credited': False}
        assert db.tables['profiles'][0]['token_balance'] == 3

    def test_abandoned_payment_marked_failed_not_left_pending_forever(self, monkeypatch):
        db = _seeded_db()
        client = _make_client(db)
        monkeypatch.setattr(billing_module, 'verify_transaction', lambda ref: {'status': 'abandoned'})

        client.post('/billing/verify', json={'reference': 'ref-123'})

        assert db.tables['payments'][0]['status'] == 'failed'

    def test_calling_twice_does_not_double_credit(self, monkeypatch):
        db = _seeded_db()
        client = _make_client(db)
        monkeypatch.setattr(billing_module, 'verify_transaction', lambda ref: {'status': 'success'})

        client.post('/billing/verify', json={'reference': 'ref-123'})
        client.post('/billing/verify', json={'reference': 'ref-123'})

        assert db.tables['profiles'][0]['token_balance'] == 13   # not 23

    def test_cannot_verify_another_users_payment(self, monkeypatch):
        db = _seeded_db()
        client = _make_client(db, as_user=OTHER_USER)
        monkeypatch.setattr(billing_module, 'verify_transaction', lambda ref: {'status': 'success'})

        resp = client.post('/billing/verify', json={'reference': 'ref-123'})

        assert resp.status_code == 404
        assert db.tables['profiles'][0]['token_balance'] == 3   # untouched

    def test_unknown_reference_returns_404(self, monkeypatch):
        db = _seeded_db()
        client = _make_client(db)

        resp = client.post('/billing/verify', json={'reference': 'not-a-real-reference'})

        assert resp.status_code == 404

    def test_missing_auth_rejected(self):
        db = _seeded_db()
        app = FastAPI()
        app.include_router(billing_module.router)
        billing_module.get_service_client = lambda: db
        client = TestClient(app)

        resp = client.post('/billing/verify', json={'reference': 'ref-123'})

        assert resp.status_code == 401

    def test_unlimited_plan_purchase_activates_plan(self, monkeypatch):
        db = _seeded_db(payment_plan='unlimited_year')
        client = _make_client(db)
        monkeypatch.setattr(billing_module, 'verify_transaction', lambda ref: {'status': 'success'})

        resp = client.post('/billing/verify', json={'reference': 'ref-123'})

        assert resp.json() == {'credited': True}
        assert db.tables['profiles'][0]['plan'] == 'unlimited'

    def test_already_credited_payment_is_reported_credited_without_reverifying(self, monkeypatch):
        db = _seeded_db(payment_status='success')
        client = _make_client(db)

        def boom(ref):
            raise AssertionError('should not call Paystack again for an already-settled payment')
        monkeypatch.setattr(billing_module, 'verify_transaction', boom)

        resp = client.post('/billing/verify', json={'reference': 'ref-123'})

        assert resp.json() == {'credited': True}
