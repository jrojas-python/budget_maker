from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.database import close_db, init_db
from app.api.v1.auth import router as auth_router
from app.api.v1.budgets import router as budgets_router
from app.api.v1.categories import router as categories_router
from app.api.v1.config import router as config_router
from app.api.v1.products import router as products_router
from app.api.v1.users import router as users_router
from app.api.dependencies import get_auth_use_cases, get_config_use_cases
from settings.config import Settings, settings
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


def create_app(app_settings: Settings) -> FastAPI:
    """Crea la aplicación FastAPI con su política CORS configurada."""
    application = FastAPI(
        title="Budget Maker API",
        description="API de generación de presupuestos/cotizaciones",
        version="0.2.0",
        lifespan=lifespan,
    )

    application.add_middleware(
        CORSMiddleware,
        allow_origins=app_settings.cors_allowed_origins,
        allow_credentials=False,
        allow_methods=["GET", "HEAD", "POST", "PUT", "DELETE", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type"],
        expose_headers=["Content-Disposition"],
    )

    application.mount("/uploads", StaticFiles(directory="uploads"), name="uploads")
    application.mount("/static", StaticFiles(directory="web/static"), name="static")

    application.include_router(auth_router)
    application.include_router(users_router)
    application.include_router(config_router)
    application.include_router(categories_router)
    application.include_router(products_router)
    application.include_router(budgets_router)
    application.include_router(web_router)

    return application


app = create_app(settings)
