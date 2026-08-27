from pydantic import BaseModel, Field, field_validator

ConfigValue = float | str | int | bool


class GlobalConfigResponse(BaseModel):
    key: str
    value: ConfigValue
    description: str


class GlobalConfigUpdate(BaseModel):
    value: ConfigValue
    description: str | None = None


class GlobalBusinessConfigResponse(BaseModel):
    tax_rate: float
    link_ttl_minutes: int
    show_product_photos_in_pdf: bool


class GlobalBusinessConfigUpdate(BaseModel):
    tax_rate: float = Field(..., ge=0, le=100)
    link_ttl_minutes: int = Field(..., ge=1, le=10080)
    show_product_photos_in_pdf: bool


class PaymentMethodCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=80)

    @field_validator("name")
    @classmethod
    def validate_name(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("El nombre del método de pago no puede estar vacío")
        return normalized


class PaymentMethodsResponse(BaseModel):
    payment_methods: list[str]
