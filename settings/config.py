from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Configuración global cargada desde variables de entorno."""

    mongo_uri: str = "mongodb://mongodb:27017"
    mongo_db_name: str = "budget_maker"
    app_host: str = "0.0.0.0"
    app_port: int = 8000

    # JWT
    jwt_secret_key: str = "change-me-in-production"
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 480

    # Uploads
    upload_dir: str = "uploads/products"
    branding_dir: str = "uploads/branding"
    max_image_size_mb: int = 2

    # Default admin seed
    default_admin_username: str = "admin"
    default_admin_password: str = "admin1234"
    default_admin_email: str = "admin@budgetmaker.local"

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()
