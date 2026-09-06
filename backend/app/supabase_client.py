from functools import lru_cache

from supabase import create_client, Client

from .config import get_settings


@lru_cache
def get_service_client() -> Client:
    """Service-role Supabase client for backend writes. Bypasses RLS by design —
    never expose the service role key to the frontend. Only the backend holds it."""
    settings = get_settings()
    return create_client(settings.supabase_url, settings.supabase_service_role_key)
