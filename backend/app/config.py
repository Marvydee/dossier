from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file='.env', extra='ignore')

    supabase_url: str = ''
    supabase_anon_key: str = ''
    supabase_service_role_key: str = ''
    supabase_jwt_secret: str = ''

    paystack_secret_key: str = ''
    paystack_public_key: str = ''

    frontend_origin: str = 'http://localhost:3000'

    max_categories_per_job: int = 8
    max_cities_per_job: int = 8
    max_pages_per_search: int = 3
    request_delay_seconds: float = 1.5
    website_timeout_seconds: int = 8
    results_per_job: int = 10

    # Token pack pricing, in kobo (1 naira = 100 kobo)
    tokens_10_price_kobo: int = 200_000       # ₦2,000
    unlimited_year_price_kobo: int = 1_500_000  # ₦15,000


@lru_cache
def get_settings() -> Settings:
    return Settings()
