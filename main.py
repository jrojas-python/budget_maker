from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.api import dependencies
from app.api.dependencies import get_auth_use_cases, get_config_use_cases
from app.application.use_cases.budget_use_cases import BudgetUseCases
from app.application.use_cases.config_use_cases import ConfigUseCases
from app.application.use_cases.product_use_cases import ProductUseCases
from app.api.v1.auth import router as auth_router
from app.api.v1.budgets import router as budgets_router
from app.api.v1.categories import router as categories_router
from app.api.v1.config import router as config_router
from app.api.v1.products import router as products_router
from app.api.v1.users import router as users_router
from app.database import close_db, init_db
from app.infrastructure.services.image_service import ImageService
from app.infrastructure.services.supabase_storage_service import SupabaseStorageService
from settings.config import Settings, settings
from web.views import router as web_router

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(name)s | %(levelname)s | %(message)s")
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    try:
        config_factory = getattr(app.state, "get_config_use_cases", get_config_use_cases)
        config_uc = config_factory()
        await config_uc.seed_defaults()
        auth_uc = get_auth_use_cases()
        await auth_uc.seed_superadmin()
        logger.info("Aplicación iniciada correctamente")
        yield
    finally:
        await close_db()


def create_app(app_settings: Settings) -> FastAPI:
    """Crea la aplicación FastAPI con su política CORS configurada."""
    upload_dir = Path(app_settings.upload_dir)
    branding_dir = Path(app_settings.branding_dir)
    upload_dir.mkdir(parents=True, exist_ok=True)
    branding_dir.mkdir(parents=True, exist_ok=True)

    application = FastAPI(
        title="Budget Maker API",
        description="API de generación de presupuestos/cotizaciones",
        version="0.2.0",
        lifespan=lifespan,
    )
    application.state.app_settings = app_settings

    if app_settings is not settings:
        storage_service = SupabaseStorageService(app_settings)
        image_service = ImageService(
            storage_service=storage_service,
            app_settings=app_settings,
        )

        def get_scoped_config_use_cases() -> ConfigUseCases:
            return ConfigUseCases(
                repo=dependencies._config_repo,
                image_service=image_service,
            )

        def get_scoped_product_use_cases() -> ProductUseCases:
            return ProductUseCases(
                repo=dependencies._product_repo,
                excel_service=dependencies._excel_service,
                image_service=image_service,
                category_repo=dependencies._category_repo,
            )

        def get_scoped_budget_use_cases() -> BudgetUseCases:
            return BudgetUseCases(
                budget_repo=dependencies._budget_repo,
                product_repo=dependencies._product_repo,
                config_repo=dependencies._config_repo,
                pdf_service=dependencies._pdf_service,
                image_service=image_service,
            )

        application.state.get_config_use_cases = get_scoped_config_use_cases
        application.dependency_overrides[dependencies.get_config_use_cases] = (
            get_scoped_config_use_cases
        )
        application.dependency_overrides[dependencies.get_product_use_cases] = (
            get_scoped_product_use_cases
        )
        application.dependency_overrides[dependencies.get_budget_use_cases] = (
            get_scoped_budget_use_cases
        )

    application.add_middleware(
        CORSMiddleware,
        allow_origins=app_settings.cors_allowed_origins,
        allow_credentials=False,
        allow_methods=["GET", "HEAD", "POST", "PUT", "DELETE", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type"],
        expose_headers=["Content-Disposition"],
    )

    application.mount(
        "/uploads/products",
        StaticFiles(directory=str(upload_dir)),
        name="product_uploads",
    )
    application.mount(
        "/uploads/branding",
        StaticFiles(directory=str(branding_dir)),
        name="branding_uploads",
    )
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
