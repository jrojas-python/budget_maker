from __future__ import annotations

from urllib.parse import parse_qs, urlsplit, urlunsplit

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

TEST_MONGO_DB_NAME = "budget_maker_test"
LOCAL_TEST_MONGO_HOSTS = frozenset({"localhost", "127.0.0.1", "::1"})
DEFAULT_CORS_ALLOWED_ORIGIN = "https://budget-maker-frontend.vercel.app"


def normalize_cors_allowed_origins(value: str | list[str]) -> list[str]:
    """Normaliza una lista o cadena de orígenes CORS sin aceptar comodines."""
    if not isinstance(value, (str, list)):
        raise ValueError("CORS_ALLOWED_ORIGINS debe ser una cadena o lista de cadenas.")

    origins = value.split(",") if isinstance(value, str) else value
    normalized_origins: list[str] = []

    for origin in origins:
        if not isinstance(origin, str):
            raise ValueError("CORS_ALLOWED_ORIGINS debe contener únicamente cadenas.")

        candidate = origin.strip().rstrip("/")
        if not candidate:
            continue
        if "*" in candidate:
            raise ValueError("CORS_ALLOWED_ORIGINS no permite patrones comodín.")

        parsed = urlsplit(candidate)
        if (
            parsed.scheme.lower() not in {"http", "https"}
            or not parsed.hostname
            or parsed.username
            or parsed.password
            or parsed.path
            or parsed.query
            or parsed.fragment
        ):
            raise ValueError("Cada origen CORS debe contener solo esquema, host y puerto opcional.")

        try:
            port = parsed.port
        except ValueError as exc:
            raise ValueError("El puerto del origen CORS no es válido.") from exc

        host = parsed.hostname.lower()
        if ":" in host:
            host = f"[{host}]"
        default_port = (parsed.scheme.lower() == "http" and port == 80) or (
            parsed.scheme.lower() == "https" and port == 443
        )
        port_suffix = f":{port}" if port and not default_port else ""
        normalized_origin = f"{parsed.scheme.lower()}://{host}{port_suffix}"

        if normalized_origin not in normalized_origins:
            normalized_origins.append(normalized_origin)

    if not normalized_origins:
        raise ValueError("CORS_ALLOWED_ORIGINS requiere al menos un origen.")

    return normalized_origins


def validate_mongo_uri(value: str) -> str:
    """Valida URIs MongoDB estándar y SRV."""
    mongo_uri = value.strip()
    if not mongo_uri:
        raise ValueError("La URI de MongoDB no puede estar vacía.")

    parsed = urlsplit(mongo_uri)
    if parsed.scheme not in {"mongodb", "mongodb+srv"}:
        raise ValueError("La URI de MongoDB debe usar mongodb:// o mongodb+srv://.")
    if not parsed.netloc or not parsed.hostname:
        raise ValueError("La URI de MongoDB debe incluir al menos un host.")

    return mongo_uri


def mask_mongo_uri(value: str) -> str:
    """Oculta la contraseña antes de registrar una URI de MongoDB."""
    parsed = urlsplit(value)
    if "@" not in parsed.netloc:
        return value

    credentials, host = parsed.netloc.rsplit("@", maxsplit=1)
    if ":" not in credentials:
        masked_netloc = parsed.netloc
    else:
        username, _ = credentials.split(":", maxsplit=1)
        masked_netloc = f"{username}:******@{host}"

    return urlunsplit((parsed.scheme, masked_netloc, parsed.path, "", parsed.fragment))


def ensure_safe_test_mongo_uri(mongo_uri: str, expected_db_name: str = TEST_MONGO_DB_NAME) -> str:
    """Impide que las pruebas limpien una base remota o un nombre inesperado."""
    validated_uri = validate_mongo_uri(mongo_uri)
    parsed = urlsplit(validated_uri)

    if parsed.scheme != "mongodb":
        raise ValueError("TEST_MONGO_URI debe usar mongodb:// para apuntar al MongoDB local autenticado.")

    hosts = parsed.netloc.rsplit("@", maxsplit=1)[-1]
    if "," in hosts:
        raise ValueError("TEST_MONGO_URI debe incluir un único host local.")

    host = (parsed.hostname or "").lower()
    if host not in LOCAL_TEST_MONGO_HOSTS:
        raise ValueError("TEST_MONGO_URI debe apuntar únicamente a localhost, 127.0.0.1 o ::1.")

    if not parsed.username or not parsed.password:
        raise ValueError("TEST_MONGO_URI debe incluir usuario y contraseña para la autenticación local.")

    auth_sources = [value.lower() for value in parse_qs(parsed.query).get("authSource", [])]
    if auth_sources != ["admin"]:
        raise ValueError("TEST_MONGO_URI debe incluir un único authSource=admin.")

    db_name = parsed.path.lstrip("/")
    if db_name != expected_db_name:
        raise ValueError(f"TEST_MONGO_URI solo puede usar la base {expected_db_name}.")

    return validated_uri


class Settings(BaseSettings):
    """Configuración global cargada desde variables de entorno."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
        populate_by_name=True,
    )

    mongo_uri: str = Field(default="mongodb://mongodb:27017", validation_alias="MONGO_URI")
    mongo_db_name: str = Field(default="budget_maker", validation_alias="MONGO_DB_NAME")
    test_mongo_uri: str = Field(
        default="mongodb://bm_local_admin:bm_local_password@localhost:27017/budget_maker_test?authSource=admin",
        validation_alias="TEST_MONGO_URI",
    )
    app_host: str = Field(default="0.0.0.0", validation_alias="APP_HOST")
    app_port: int = Field(default=8000, validation_alias="APP_PORT")
    cors_allowed_origins: list[str] | str = Field(
        default=DEFAULT_CORS_ALLOWED_ORIGIN,
        validation_alias="CORS_ALLOWED_ORIGINS",
    )

    # JWT
    jwt_secret_key: str = Field(default="change-me-in-production", validation_alias="JWT_SECRET_KEY")
    jwt_algorithm: str = Field(default="HS256", validation_alias="JWT_ALGORITHM")
    jwt_expire_minutes: int = Field(default=480, validation_alias="JWT_EXPIRE_MINUTES")

    # Uploads
    upload_dir: str = Field(default="uploads/products", validation_alias="UPLOAD_DIR")
    branding_dir: str = Field(default="uploads/branding", validation_alias="BRANDING_DIR")
    max_image_size_mb: int = Field(default=2, validation_alias="MAX_IMAGE_SIZE_MB")

    # Default admin seed
    default_admin_username: str = Field(default="admin", validation_alias="DEFAULT_ADMIN_USERNAME")
    default_admin_password: str = Field(default="admin1234", validation_alias="DEFAULT_ADMIN_PASSWORD")
    default_admin_email: str = Field(default="admin@budgetmaker.local", validation_alias="DEFAULT_ADMIN_EMAIL")

    @field_validator("mongo_uri")
    @classmethod
    def _validate_mongo_uri(cls, value: str) -> str:
        return validate_mongo_uri(value)

    @field_validator("test_mongo_uri")
    @classmethod
    def _validate_test_mongo_uri(cls, value: str) -> str:
        return ensure_safe_test_mongo_uri(value)

    @field_validator("mongo_db_name")
    @classmethod
    def _validate_mongo_db_name(cls, value: str) -> str:
        mongo_db_name = value.strip()
        if not mongo_db_name:
            raise ValueError("MONGO_DB_NAME no puede estar vacío.")
        return mongo_db_name

    @field_validator("cors_allowed_origins", mode="before")
    @classmethod
    def _normalize_cors_allowed_origins(cls, value: str | list[str]) -> list[str]:
        return normalize_cors_allowed_origins(value)

    def masked_mongo_uri(self) -> str:
        """Retorna la URI principal sin exponer la contraseña."""
        return mask_mongo_uri(self.mongo_uri)


settings = Settings()
