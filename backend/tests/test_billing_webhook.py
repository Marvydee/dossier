"""Tests the Paystack webhook handler in isolation. Covers exactly the things
that matter for a payment integration: an unsigned/tampered payload is
rejected before touching the database, a valid one credits exactly once, and
a replayed webhook (Paystack's delivery is at-least-once) never double-credits.
"""
import hashlib
import hmac
import json

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.routers import billing as billing_module
from tests.fakes import FakeSupabaseClient

TEST_SECRET = 'sk_test_fake_secret_for_tests'


@pytest.fixture(autouse=True)
def _configure_secret(monkeypatch):
    from app.config import get_settings
    get_settings.cache_clear()
    monkeypatch.setenv('PAYSTACK_SECRET_KEY', TEST_SECRET)
    yield
    get_settings.cache_clear()


def _sign(body: bytes) -> str:
    return hmac.new(TEST_SECRET.encode(), body, hashlib.sha512).hexdigest()


def _make_client(fake_db: FakeSupabaseClient) -> TestClient:
    app = FastAPI()
    app.include_router(billing_module.router)
    billing_module.get_service_client = lambda: fake_db
    return TestClient(app)


def _seeded_db(*, payment_plan='tokens_10', payment_status='pending'):
    db = FakeSupabaseClient()
    db.seed('profiles', [
        {'id': 'user-1', 'email': 'user@example.com', 'token_balance': 3,
         'plan': 'free', 'plan_expires_at': None},
    ])
    db.seed('payments', [
        {'id': 'pay-1', 'user_id': 'user-1', 'paystack_reference': 'ref-123',
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
            delta = 10
            reason = 'purchase'
        else:
            profile['plan'] = 'unlimited'
            delta = 0
            reason = 'unlimited_plan'
        db.tables.setdefault('token_transactions', []).append({
            'user_id': params['p_user_id'], 'delta': delta, 'reason': reason,
            'paystack_reference': ref,
        })
        return None

    db.on_rpc('credit_purchase', credit_purchase)
    return db


CHARGE_SUCCESS_EVENT = {
    'event': 'charge.success',
    'data': {'reference': 'ref-123', 'status': 'success'},
}


class TestWebhookSignature:

    def test_missing_signature_rejected(self, monkeypatch):
        db = _seeded_db()
        client = _make_client(db)

        resp = client.post('/billing/webhook', json=CHARGE_SUCCESS_EVENT)

        assert resp.status_code == 401
        assert db.tables['profiles'][0]['token_balance'] == 3   # untouched

    def test_tampered_signature_rejected(self):
        db = _seeded_db()
        client = _make_client(db)
        body = json.dumps(CHARGE_SUCCESS_EVENT).encode()

        resp = client.post('/billing/webhook', content=body,
                            headers={'x-paystack-signature': 'not-the-real-signature'})

        assert resp.status_code == 401
        assert db.tables['profiles'][0]['token_balance'] == 3

    def test_valid_signature_is_accepted(self, monkeypatch):
        db = _seeded_db()
        client = _make_client(db)
        body = json.dumps(CHARGE_SUCCESS_EVENT).encode()

        monkeypatch.setattr(billing_module, 'verify_transaction',
                             lambda ref: {'status': 'success'})

        resp = client.post('/billing/webhook', content=body,
                            headers={'x-paystack-signature': _sign(body)})

        assert resp.status_code == 200
        assert db.tables['profiles'][0]['token_balance'] == 13


class TestWebhookCrediting:

    def _post_signed(self, client, event=CHARGE_SUCCESS_EVENT):
        body = json.dumps(event).encode()
        return client.post('/billing/webhook', content=body,
                            headers={'x-paystack-signature': _sign(body)})

    def test_tokens_10_credits_ten_tokens(self, monkeypatch):
        db = _seeded_db(payment_plan='tokens_10')
        client = _make_client(db)
        monkeypatch.setattr(billing_module, 'verify_transaction', lambda ref: {'status': 'success'})

        self._post_signed(client)

        assert db.tables['profiles'][0]['token_balance'] == 13

    def test_unlimited_year_sets_plan(self, monkeypatch):
        db = _seeded_db(payment_plan='unlimited_year')
        client = _make_client(db)
        monkeypatch.setattr(billing_module, 'verify_transaction', lambda ref: {'status': 'success'})

        self._post_signed(client)

        assert db.tables['profiles'][0]['plan'] == 'unlimited'

    def test_replayed_webhook_does_not_double_credit(self, monkeypatch):
        db = _seeded_db(payment_plan='tokens_10')
        client = _make_client(db)
        monkeypatch.setattr(billing_module, 'verify_transaction', lambda ref: {'status': 'success'})

        self._post_signed(client)
        self._post_signed(client)   # Paystack redelivers the same event

        assert db.tables['profiles'][0]['token_balance'] == 13   # not 23

    def test_unverified_transaction_does_not_credit(self, monkeypatch):
        db = _seeded_db(payment_plan='tokens_10')
        client = _make_client(db)
        # Signature is valid, but Paystack's own verify API says it's NOT actually successful —
        # the webhook payload alone must never be trusted.
        monkeypatch.setattr(billing_module, 'verify_transaction', lambda ref: {'status': 'failed'})

        resp = self._post_signed(client)

        assert resp.status_code == 200
        assert db.tables['profiles'][0]['token_balance'] == 3

    def test_unknown_reference_is_ignored_not_errored(self, monkeypatch):
        db = _seeded_db()
        client = _make_client(db)
        monkeypatch.setattr(billing_module, 'verify_transaction', lambda ref: {'status': 'success'})
        event = {'event': 'charge.success', 'data': {'reference': 'ref-does-not-exist'}}

        resp = self._post_signed(client, event=event)

        assert resp.status_code == 200

    def test_non_charge_success_events_are_ignored(self):
        db = _seeded_db()
        client = _make_client(db)
        event = {'event': 'transfer.success', 'data': {}}

        resp = self._post_signed(client, event=event)

        assert resp.status_code == 200
        assert db.tables['profiles'][0]['token_balance'] == 3
