import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.database import init_db
from app.api.v1.config import router as config_router
from app.api.v1.products import router as products_router
from app.api.v1.budgets import router as budgets_router
from app.api.dependencies import get_config_use_cases
from web.views import router as web_router

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(name)s | %(levelname)s | %(message)s")
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    # Seed de configuración por defecto
    config_uc = get_config_use_cases()
    await config_uc.seed_defaults()
    logger.info("Aplicación iniciada correctamente")
    yield


app = FastAPI(
    title="Budget Maker API",
    description="API de generación de presupuestos/cotizaciones",
    version="0.1.0",
    lifespan=lifespan,
)

app.mount("/static", StaticFiles(directory="web/static"), name="static")

app.include_router(config_router)
app.include_router(products_router)
app.include_router(budgets_router)
app.include_router(web_router)
