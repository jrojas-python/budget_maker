from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Configuración global cargada desde variables de entorno."""

    mongo_uri: str = "mongodb://mongodb:27017"
    mongo_db_name: str = "budget_maker"
    app_host: str = "0.0.0.0"
    app_port: int = 8000

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()
