import time

import requests
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import jwt, JWTError

from .config import get_settings

_bearer = HTTPBearer(auto_error=False)

_jwks_cache: dict = {'keys': [], 'fetched_at': 0.0}
_JWKS_TTL_SECONDS = 3600


def _get_jwks() -> list[dict]:
    """Supabase projects created with the newer asymmetric signing keys sign
    JWTs with ES256, verified against a public JWKS rather than a shared
    secret (the legacy HS256 SUPABASE_JWT_SECRET only applies to older
    projects). Cached for an hour; refreshed early if a kid isn't found,
    to ride out key rotation."""
    now = time.time()
    if _jwks_cache['keys'] and now - _jwks_cache['fetched_at'] < _JWKS_TTL_SECONDS:
        return _jwks_cache['keys']

    settings = get_settings()
    resp = requests.get(f'{settings.supabase_url}/auth/v1/.well-known/jwks.json', timeout=10)
    resp.raise_for_status()
    keys = resp.json().get('keys', [])
    _jwks_cache['keys'] = keys
    _jwks_cache['fetched_at'] = now
    return keys


def _find_key(kid: str, *, force_refresh: bool = False) -> dict | None:
    if force_refresh:
        _jwks_cache['fetched_at'] = 0.0
    for key in _get_jwks():
        if key.get('kid') == kid:
            return key
    return None


def get_current_user_id(
    credentials: HTTPAuthorizationCredentials = Depends(_bearer),
) -> str:
    """Verifies the Supabase-issued JWT from the Authorization header and
    returns the authenticated user's id. Every protected route depends on
    this — no session state is ever trusted from the client beyond a valid,
    unexpired, correctly-signed token."""
    if credentials is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED,
                             detail='Missing Authorization header')

    token = credentials.credentials

    try:
        header = jwt.get_unverified_header(token)
    except JWTError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail='Malformed token')

    kid = header.get('kid')
    alg = header.get('alg', 'ES256')

    key = _find_key(kid) if kid else None
    if key is None:
        key = _find_key(kid, force_refresh=True) if kid else None
    if key is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail='Unknown signing key')

    try:
        payload = jwt.decode(token, key, algorithms=[alg], audience='authenticated')
    except JWTError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED,
                             detail='Invalid or expired token')

    user_id = payload.get('sub')
    if not user_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED,
                             detail='Token missing subject claim')

    return user_id
