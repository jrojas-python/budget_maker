from pydantic import BaseModel


class GlobalConfigResponse(BaseModel):
    key: str
    value: float | str | int
    description: str


class GlobalConfigUpdate(BaseModel):
    value: float | str | int
    description: str | None = None
