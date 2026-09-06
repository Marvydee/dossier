"""Tests JWT verification against a real EC keypair and a mocked JWKS
endpoint — this is the exact area where a real bug slipped past manual
review: the code originally assumed HS256 (a shared secret), but a freshly
created Supabase project actually signs tokens with ES256 against a public
JWKS, which was only caught by testing against a live project. These tests
exist so that regression can't happen silently again.
"""
import time

import pytest
from fastapi import FastAPI, Depends
from fastapi.testclient import TestClient
from jose import jwt as jose_jwt
from jose.backends.cryptography_backend import CryptographyECKey
from cryptography.hazmat.primitives.asymmetric import ec

from app.auth import get_current_user_id, _jwks_cache

KID = 'test-key-1'


@pytest.fixture
def keypair():
    private_key = ec.generate_private_key(ec.SECP256R1())
    jose_ec_key = CryptographyECKey(private_key, algorithm='ES256')
    public_jwk = jose_ec_key.public_key().to_dict()
    public_jwk['kid'] = KID
    return private_key, public_jwk


def _make_token(private_key, *, user_id='user-abc', aud='authenticated', exp_delta=3600, kid=KID):
    headers = {'kid': kid}
    payload = {'sub': user_id, 'aud': aud, 'exp': time.time() + exp_delta, 'role': 'authenticated'}
    return jose_jwt.encode(payload, private_key, algorithm='ES256', headers=headers)


@pytest.fixture(autouse=True)
def _reset_jwks_cache():
    _jwks_cache['keys'] = []
    _jwks_cache['fetched_at'] = 0.0
    yield
    _jwks_cache['keys'] = []
    _jwks_cache['fetched_at'] = 0.0


def _test_app(public_jwk, monkeypatch):
    def fake_get_jwks():
        return [public_jwk]
    monkeypatch.setattr('app.auth._get_jwks', fake_get_jwks)

    app = FastAPI()

    @app.get('/protected')
    def protected(user_id: str = Depends(get_current_user_id)):
        return {'user_id': user_id}

    return TestClient(app)


class TestJwtVerification:

    def test_valid_es256_token_is_accepted(self, keypair, monkeypatch):
        private_key, public_jwk = keypair
        client = _test_app(public_jwk, monkeypatch)
        token = _make_token(private_key, user_id='user-abc')

        resp = client.get('/protected', headers={'Authorization': f'Bearer {token}'})

        assert resp.status_code == 200
        assert resp.json()['user_id'] == 'user-abc'

    def test_missing_authorization_header_rejected(self, keypair, monkeypatch):
        _, public_jwk = keypair
        client = _test_app(public_jwk, monkeypatch)

        resp = client.get('/protected')

        assert resp.status_code == 401

    def test_token_signed_by_a_different_key_rejected(self, keypair, monkeypatch):
        _, public_jwk = keypair
        other_private_key = ec.generate_private_key(ec.SECP256R1())
        client = _test_app(public_jwk, monkeypatch)
        # Signed by a key whose public half was never published in the JWKS
        forged_token = _make_token(other_private_key, user_id='attacker')

        resp = client.get('/protected', headers={'Authorization': f'Bearer {forged_token}'})

        assert resp.status_code == 401

    def test_unknown_kid_rejected(self, keypair, monkeypatch):
        private_key, public_jwk = keypair
        client = _test_app(public_jwk, monkeypatch)
        token = _make_token(private_key, kid='some-other-kid-not-in-jwks')

        resp = client.get('/protected', headers={'Authorization': f'Bearer {token}'})

        assert resp.status_code == 401

    def test_expired_token_rejected(self, keypair, monkeypatch):
        private_key, public_jwk = keypair
        client = _test_app(public_jwk, monkeypatch)
        token = _make_token(private_key, exp_delta=-3600)

        resp = client.get('/protected', headers={'Authorization': f'Bearer {token}'})

        assert resp.status_code == 401

    def test_wrong_audience_rejected(self, keypair, monkeypatch):
        private_key, public_jwk = keypair
        client = _test_app(public_jwk, monkeypatch)
        token = _make_token(private_key, aud='some-other-service')

        resp = client.get('/protected', headers={'Authorization': f'Bearer {token}'})

        assert resp.status_code == 401

    def test_malformed_token_rejected(self, keypair, monkeypatch):
        _, public_jwk = keypair
        client = _test_app(public_jwk, monkeypatch)

        resp = client.get('/protected', headers={'Authorization': 'Bearer not-a-real-jwt'})

        assert resp.status_code == 401
