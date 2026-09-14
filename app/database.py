import logging

from beanie import init_beanie
from motor.motor_asyncio import AsyncIOMotorClient

from settings.config import settings

logger = logging.getLogger(__name__)
mongo_client: AsyncIOMotorClient | None = None


async def init_db() -> None:
    """Inicializa la conexión a MongoDB y registra los documentos Beanie."""
    global mongo_client

    from app.domain.models.budget import Budget
    from app.domain.models.category import Category
    from app.domain.models.global_config import GlobalConfig
    from app.domain.models.product import Product
    from app.domain.models.user import User

    previous_client = mongo_client

    logger.info(
        "Inicializando MongoDB con uri=%s y base=%s",
        settings.masked_mongo_uri(),
        settings.mongo_db_name,
    )
    candidate_client = AsyncIOMotorClient(settings.mongo_uri)
    try:
        database = candidate_client[settings.mongo_db_name]
        await database.command("ping")
        await init_beanie(
            database=database,
            document_models=[GlobalConfig, Product, Budget, User, Category],
        )
    except BaseException:
        candidate_client.close()
        raise

    mongo_client = candidate_client
    if previous_client is not None:
        previous_client.close()
    logger.info("Base de datos inicializada: %s", settings.mongo_db_name)


async def close_db() -> None:
    """Cierra la conexión global a MongoDB si existe."""
    global mongo_client

    if mongo_client is None:
        return

    mongo_client.close()
    mongo_client = None
    logger.info("Conexión a MongoDB cerrada")
