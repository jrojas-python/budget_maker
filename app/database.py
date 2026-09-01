import logging

from beanie import init_beanie
from motor.motor_asyncio import AsyncIOMotorClient

from settings.config import settings

logger = logging.getLogger(__name__)


async def init_db() -> None:
    """Inicializa la conexión a MongoDB y registra los documentos Beanie."""
    from app.domain.models.budget import Budget
    from app.domain.models.category import Category
    from app.domain.models.global_config import GlobalConfig
    from app.domain.models.product import Product
    from app.domain.models.user import User

    client = AsyncIOMotorClient(settings.mongo_uri)
    await init_beanie(
        database=client[settings.mongo_db_name],
        document_models=[GlobalConfig, Product, Budget, User, Category],
    )
    logger.info("Base de datos inicializada: %s", settings.mongo_db_name)
