from fastapi import APIRouter

from ..supabase_client import get_service_client

router = APIRouter(tags=['catalog'])


@router.get('/categories')
def list_categories():
    client = get_service_client()
    resp = (
        client.table('categories')
        .select('slug, label')
        .eq('active', True)
        .order('label')
        .execute()
    )
    return resp.data


@router.get('/cities')
def list_cities():
    client = get_service_client()
    resp = (
        client.table('cities')
        .select('slug, label, country, is_nigeria')
        .eq('active', True)
        .order('is_nigeria', desc=True)
        .order('label')
        .execute()
    )
    return resp.data
