from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from ..auth import get_current_user_id
from ..config import get_settings
from ..supabase_client import get_service_client

router = APIRouter(prefix='/jobs', tags=['jobs'])


class JobCreate(BaseModel):
    categories: list[str] = Field(min_length=1)
    cities: list[str] = Field(min_length=1)


def _validate_selection(client, categories: list[str], cities: list[str]):
    settings = get_settings()

    if len(categories) > settings.max_categories_per_job:
        raise HTTPException(status.HTTP_400_BAD_REQUEST,
                             f'Maximum {settings.max_categories_per_job} categories per job')
    if len(cities) > settings.max_cities_per_job:
        raise HTTPException(status.HTTP_400_BAD_REQUEST,
                             f'Maximum {settings.max_cities_per_job} cities per job')

    cat_rows = (client.table('categories').select('slug')
                .in_('slug', categories).eq('active', True).execute().data)
    if len(cat_rows) != len(set(categories)):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, 'One or more categories are invalid')

    city_rows = (client.table('cities').select('slug')
                 .in_('slug', cities).eq('active', True).execute().data)
    if len(city_rows) != len(set(cities)):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, 'One or more cities are invalid')


@router.post('', status_code=status.HTTP_201_CREATED)
def create_job(body: JobCreate, user_id: str = Depends(get_current_user_id)):
    client = get_service_client()

    # Never trust category/city strings from the client beyond checking they
    # exist and are active — they flow straight into scrape URLs downstream.
    _validate_selection(client, body.categories, body.cities)

    job = (client.table('generation_jobs').insert({
        'user_id': user_id,
        'status': 'queued',
        'categories': body.categories,
        'cities': body.cities,
    }).execute().data[0])

    spent = client.rpc('spend_token', {'p_user_id': user_id, 'p_job_id': job['id']}).execute().data

    if not spent:
        client.table('generation_jobs').delete().eq('id', job['id']).execute()
        raise HTTPException(status.HTTP_402_PAYMENT_REQUIRED,
                             'No tokens remaining — buy more or go unlimited')

    return job


@router.get('')
def list_jobs(user_id: str = Depends(get_current_user_id)):
    client = get_service_client()
    return (client.table('generation_jobs').select('*')
            .eq('user_id', user_id).order('created_at', desc=True).execute().data)


def _get_own_job(client, job_id: str, user_id: str) -> dict:
    rows = (client.table('generation_jobs').select('*')
            .eq('id', job_id).eq('user_id', user_id).execute().data)
    if not rows:
        raise HTTPException(status.HTTP_404_NOT_FOUND, 'Job not found')
    return rows[0]


@router.get('/{job_id}')
def get_job(job_id: str, user_id: str = Depends(get_current_user_id)):
    return _get_own_job(get_service_client(), job_id, user_id)


@router.get('/{job_id}/download')
def download_job(job_id: str, user_id: str = Depends(get_current_user_id)):
    client = get_service_client()
    job = _get_own_job(client, job_id, user_id)

    if job['status'] != 'completed' or not job.get('result_path'):
        raise HTTPException(status.HTTP_409_CONFLICT, 'Job is not complete yet')

    # Private bucket — never a public link. Expires quickly since it's
    # regenerated on demand each time this endpoint is called.
    signed = client.storage.from_('generation-results').create_signed_url(
        job['result_path'], 60 * 5
    )
    return {'url': signed['signedURL']}
