import hashlib
import hmac

import requests

from .config import get_settings

PAYSTACK_BASE_URL = 'https://api.paystack.co'


def initialize_transaction(*, email: str, amount_kobo: int, reference: str,
                            callback_url: str, metadata: dict) -> dict:
    settings = get_settings()
    resp = requests.post(
        f'{PAYSTACK_BASE_URL}/transaction/initialize',
        headers={'Authorization': f'Bearer {settings.paystack_secret_key}'},
        json={
            'email': email,
            'amount': amount_kobo,
            'reference': reference,
            'callback_url': callback_url,
            'metadata': metadata,
        },
        timeout=15,
    )
    resp.raise_for_status()
    return resp.json()['data']


def verify_transaction(reference: str) -> dict:
    """Server-side check that a transaction genuinely succeeded — used as a
    second, independent confirmation alongside the webhook signature check,
    rather than trusting either one alone."""
    settings = get_settings()
    resp = requests.get(
        f'{PAYSTACK_BASE_URL}/transaction/verify/{reference}',
        headers={'Authorization': f'Bearer {settings.paystack_secret_key}'},
        timeout=15,
    )
    resp.raise_for_status()
    return resp.json()['data']


def verify_webhook_signature(raw_body: bytes, signature_header: str) -> bool:
    """Paystack signs each webhook payload with HMAC-SHA512 using the account's
    secret key. Skipping this check and trusting the callback/redirect instead
    is the most common real-world payment-integration vulnerability — every
    webhook must pass this before any token is credited."""
    settings = get_settings()
    if not signature_header:
        return False
    computed = hmac.new(
        settings.paystack_secret_key.encode('utf-8'),
        raw_body,
        hashlib.sha512,
    ).hexdigest()
    return hmac.compare_digest(computed, signature_header)
