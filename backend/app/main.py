import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .config import get_settings
from .routers import catalog, jobs, billing
from .worker import poll_loop


@asynccontextmanager
async def lifespan(app: FastAPI):
    worker_task = asyncio.create_task(poll_loop())
    try:
        yield
    finally:
        worker_task.cancel()


app = FastAPI(title='Docket Prospector API', lifespan=lifespan)

settings = get_settings()
app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.frontend_origin],
    allow_credentials=True,
    allow_methods=['*'],
    allow_headers=['*'],
)

app.include_router(catalog.router)
app.include_router(jobs.router)
app.include_router(billing.router)


@app.get('/health')
def health():
    return {'status': 'ok'}
