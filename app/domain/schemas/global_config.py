from typing import Literal

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
    use_tax: bool = True
    link_ttl_minutes: int
    show_product_photos_in_pdf: bool


class GlobalBusinessConfigUpdate(BaseModel):
    tax_rate: float = Field(..., ge=0, le=100)
    use_tax: bool = True
    link_ttl_minutes: int = Field(..., ge=1, le=10080)
    show_product_photos_in_pdf: bool


class PaymentMethodCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=80)

    @field_validator("name")
    @classmethod
    def validate_name(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("El nombre del mÃ©todo de pago no puede estar vacÃ­o")
        return normalized


class PaymentMethodsResponse(BaseModel):
    payment_methods: list[str]


CompanyInfoPosition = Literal["header", "footer"]


class CompanyInfoResponse(BaseModel):
    """Datos de compaÃ±Ã­a y preferencias de visualizaciÃ³n."""

    company_name: str = ""
    company_phone: str = ""
    company_address: str = ""
    company_ruc: str = ""
    show_company_info: bool = False
    company_info_position: CompanyInfoPosition = "footer"


class CompanyInfoUpdate(BaseModel):
    """ActualizaciÃ³n parcial de datos de compaÃ±Ã­a."""

    company_name: str | None = Field(default=None, max_length=200)
    company_phone: str | None = Field(default=None, max_length=50)
    company_address: str | None = Field(default=None, max_length=200)
    company_ruc: str | None = Field(default=None, max_length=50)
    show_company_info: bool | None = None
    company_info_position: CompanyInfoPosition | None = None

    @field_validator("company_name", "company_phone", "company_address", "company_ruc")
    @classmethod
    def strip_text(cls, value: str | None) -> str | None:
        return value.strip() if value is not None else None
