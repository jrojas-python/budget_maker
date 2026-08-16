from beanie import Document, Indexed


class GlobalConfig(Document):
    """Configuración global dinámica del sistema."""

    key: Indexed(str, unique=True)
    value: float | str | int
    description: str = ""

    class Settings:
        name = "global_config"
