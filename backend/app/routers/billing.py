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


@router.post('/webhook', status_code=status.HTTP_200_OK)
async def webhook(request: Request):
    raw_body = await request.body()
    signature = request.headers.get('x-paystack-signature', '')

    # The #1 real-world payment-integration vulnerability is trusting a
    # webhook (or a frontend redirect) without verifying this signature.
    if not verify_webhook_signature(raw_body, signature):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, 'Invalid signature')

    event = await request.json()
    if event.get('event') != 'charge.success':
        return {'received': True}

    reference = event['data']['reference']

    # Second, independent confirmation directly from Paystack's API — never
    # credit tokens off the webhook payload alone.
    verified = verify_transaction(reference)
    if verified.get('status') != 'success':
        return {'received': True}

    client = get_service_client()
    payment_rows = (client.table('payments').select('*')
                     .eq('paystack_reference', reference).execute().data)
    if not payment_rows:
        return {'received': True}

    payment = payment_rows[0]
    client.table('payments').update({'status': 'success'}).eq('id', payment['id']).execute()

    # credit_purchase() is idempotent on paystack_reference — safe even if
    # Paystack redelivers this webhook.
    client.rpc('credit_purchase', {
        'p_user_id': payment['user_id'],
        'p_plan': payment['plan'],
        'p_paystack_reference': reference,
    }).execute()

    return {'received': True}
