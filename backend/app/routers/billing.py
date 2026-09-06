import uuid

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel

from ..auth import get_current_user_id
from ..config import get_settings
from ..paystack import initialize_transaction, verify_transaction, verify_webhook_signature
from ..supabase_client import get_service_client

router = APIRouter(prefix='/billing', tags=['billing'])

PLAN_PRICES = {
    'tokens_10': lambda s: s.tokens_10_price_kobo,
    'unlimited_year': lambda s: s.unlimited_year_price_kobo,
}


class CheckoutRequest(BaseModel):
    plan: str


class VerifyRequest(BaseModel):
    reference: str


@router.post('/checkout')
def checkout(body: CheckoutRequest, user_id: str = Depends(get_current_user_id)):
    if body.plan not in PLAN_PRICES:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, 'Unknown plan')

    settings = get_settings()
    client = get_service_client()

    profile = client.table('profiles').select('email').eq('id', user_id).single().execute().data
    amount_kobo = PLAN_PRICES[body.plan](settings)
    reference = str(uuid.uuid4())

    client.table('payments').insert({
        'user_id': user_id,
        'paystack_reference': reference,
        'amount_kobo': amount_kobo,
        'plan': body.plan,
        'status': 'pending',
    }).execute()

    data = initialize_transaction(
        email=profile['email'],
        amount_kobo=amount_kobo,
        reference=reference,
        callback_url=f'{settings.frontend_origin}/billing/return',
        metadata={'user_id': user_id, 'plan': body.plan},
    )

    return {'authorization_url': data['authorization_url'], 'reference': reference}


def credit_if_paid(client, payment: dict) -> bool:
    """Verify a payment directly against Paystack's API and credit it if
    successful. Idempotent (credit_purchase() is a no-op on a reference
    that's already been credited) — safe to call repeatedly on the same
    payment from multiple paths (the return-page check and the background
    reconciler both call this).

    Returns True if the payment is now in a 'success' state (whether it was
    just credited or already had been).
    """
    if payment['status'] == 'success':
        return True

    reference = payment['paystack_reference']
    verified = verify_transaction(reference)
    paystack_status = verified.get('status')

    if paystack_status == 'success':
        client.table('payments').update({'status': 'success'}).eq('id', payment['id']).execute()
        client.rpc('credit_purchase', {
            'p_user_id': payment['user_id'],
            'p_plan': payment['plan'],
            'p_paystack_reference': reference,
        }).execute()
        return True

    if paystack_status in ('failed', 'abandoned'):
        client.table('payments').update({'status': 'failed'}).eq('id', payment['id']).execute()

    return False


@router.post('/verify')
def verify(body: VerifyRequest, user_id: str = Depends(get_current_user_id)):
    """Called from the frontend's /billing/return page right after Paystack
    redirects the user back. This project shares a Paystack account with
    another app that already owns the account's one allowed webhook URL, so
    payment confirmation happens this way instead: we verify directly against
    Paystack's API ourselves (an outbound call we make, unrelated to the
    inbound webhook slot) rather than waiting to be notified. See
    worker.py's reconcile_pending_payments() for the safety net covering a
    user who closes the tab before this ever runs.
    """
    client = get_service_client()
    rows = (client.table('payments').select('*')
            .eq('paystack_reference', body.reference).eq('user_id', user_id).execute().data)
    if not rows:
        raise HTTPException(status.HTTP_404_NOT_FOUND, 'Payment not found')

    credited = credit_if_paid(client, rows[0])
    return {'credited': credited}


@router.post('/webhook', status_code=status.HTTP_200_OK)
async def webhook(request: Request):
    """Not currently reachable in production — Paystack allows only one
    webhook URL per account, and this account's is already pointed at
    another project. Left in place (harmless, fully correct) in case this
    project ever gets its own dedicated Paystack account/webhook slot.
    Payment confirmation in the meantime happens via /billing/verify plus
    the background reconciler instead — see credit_if_paid() above.
    """
    raw_body = await request.body()
    signature = request.headers.get('x-paystack-signature', '')

    if not verify_webhook_signature(raw_body, signature):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, 'Invalid signature')

    event = await request.json()
    if event.get('event') != 'charge.success':
        return {'received': True}

    reference = event['data']['reference']
    client = get_service_client()
    payment_rows = (client.table('payments').select('*')
                     .eq('paystack_reference', reference).execute().data)
    if not payment_rows:
        return {'received': True}

    credit_if_paid(client, payment_rows[0])
    return {'received': True}
