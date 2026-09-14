import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.database import close_db, init_db
from app.api.v1.auth import router as auth_router
from app.api.v1.budgets import router as budgets_router
from app.api.v1.categories import router as categories_router
from app.api.v1.config import router as config_router
from app.api.v1.products import router as products_router
from app.api.v1.users import router as users_router
from app.api.dependencies import get_auth_use_cases, get_config_use_cases
from settings.config import settings
from web.views import router as web_router

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(name)s | %(levelname)s | %(message)s")
logger = logging.getLogger(__name__)

Path(settings.upload_dir).mkdir(parents=True, exist_ok=True)
Path(settings.branding_dir).mkdir(parents=True, exist_ok=True)


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    try:
        config_uc = get_config_use_cases()
        await config_uc.seed_defaults()
        auth_uc = get_auth_use_cases()
        await auth_uc.seed_superadmin()
        logger.info("Aplicación iniciada correctamente")
        yield
    finally:
        await close_db()


app = FastAPI(
    title="Budget Maker API",
    description="API de generación de presupuestos/cotizaciones",
    version="0.2.0",
    lifespan=lifespan,
)

app.mount("/uploads", StaticFiles(directory="uploads"), name="uploads")
app.mount("/static", StaticFiles(directory="web/static"), name="static")

app.include_router(auth_router)
app.include_router(users_router)
app.include_router(config_router)
app.include_router(categories_router)
app.include_router(products_router)
app.include_router(budgets_router)
app.include_router(web_router)
