from __future__ import annotations

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile

from app.api.dependencies import get_config_use_cases, get_current_user
from app.application.use_cases.config_use_cases import ConfigUseCases
from app.domain.models.user import User
from app.domain.schemas.global_config import (
    GlobalBusinessConfigResponse,
    GlobalBusinessConfigUpdate,
    GlobalConfigResponse,
    GlobalConfigUpdate,
    PaymentMethodCreate,
    PaymentMethodsResponse,
)
from app.infrastructure.services.image_service import ImageReferenceError, ImageValidationError
from app.infrastructure.services.supabase_storage_service import (
    SupabaseStorageConfigurationError,
    SupabaseStorageOperationError,
)

router = APIRouter(prefix="/api/v1/config", tags=["Configuración"])
_BRANDING_KEYS = {"site_logo", "site_icon"}


@router.get("/", response_model=list[GlobalConfigResponse])
async def list_config(uc: ConfigUseCases = Depends(get_config_use_cases)):
    configs = await uc.get_all()
    return [
        GlobalConfigResponse(
            key=config["key"],
            value=config["value"],
            description=str(config["description"]),
        )
        for config in configs
    ]


@router.get("/global", response_model=GlobalBusinessConfigResponse)
async def get_global_config(uc: ConfigUseCases = Depends(get_config_use_cases)):
    config = await uc.get_global_config()
    return GlobalBusinessConfigResponse(
        tax_rate=config.tax_rate,
        link_ttl_minutes=config.link_ttl_minutes,
        show_product_photos_in_pdf=config.show_product_photos_in_pdf,
    )


@router.put("/global", response_model=GlobalBusinessConfigResponse)
async def update_global_config(
    body: GlobalBusinessConfigUpdate,
    _: User = Depends(get_current_user),
    uc: ConfigUseCases = Depends(get_config_use_cases),
):
    config = await uc.update_global_config(
        tax_rate=body.tax_rate,
        link_ttl_minutes=body.link_ttl_minutes,
        show_product_photos_in_pdf=body.show_product_photos_in_pdf,
    )
    return GlobalBusinessConfigResponse(
        tax_rate=config.tax_rate,
        link_ttl_minutes=config.link_ttl_minutes,
        show_product_photos_in_pdf=config.show_product_photos_in_pdf,
    )


@router.post("/branding/{key}", response_model=GlobalConfigResponse)
async def upload_branding(
    key: str,
    file: UploadFile = File(...),
    _: User = Depends(get_current_user),
    uc: ConfigUseCases = Depends(get_config_use_cases),
):
    """Sube logo o icono del sitio. key debe ser 'site_logo' o 'site_icon'."""
    if key not in _BRANDING_KEYS:
        raise HTTPException(status_code=422, detail=f"Clave inválida. Usar: {_BRANDING_KEYS}")
    try:
        config = await uc.upload_branding(key, file)
    except ImageValidationError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc
    except ImageReferenceError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc
    except SupabaseStorageConfigurationError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except SupabaseStorageOperationError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    return GlobalConfigResponse(
        key=str(config["key"]),
        value=config["value"],
        description=str(config["description"]),
    )


@router.post("/logo", response_model=GlobalConfigResponse)
async def upload_logo(
    file: UploadFile = File(...),
    _: User = Depends(get_current_user),
    uc: ConfigUseCases = Depends(get_config_use_cases),
):
    try:
        config = await uc.upload_branding("site_logo", file)
    except ImageValidationError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc
    except ImageReferenceError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc
    except SupabaseStorageConfigurationError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except SupabaseStorageOperationError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    return GlobalConfigResponse(
        key=str(config["key"]),
        value=config["value"],
        description=str(config["description"]),
    )


@router.delete("/branding/{key}", response_model=GlobalConfigResponse)
async def delete_branding(
    key: str,
    _: User = Depends(get_current_user),
    uc: ConfigUseCases = Depends(get_config_use_cases),
):
    """Elimina logo o icono del sitio."""
    if key not in _BRANDING_KEYS:
        raise HTTPException(status_code=422, detail=f"Clave inválida. Usar: {_BRANDING_KEYS}")
    try:
        config = await uc.delete_branding(key)
    except ImageReferenceError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc
    except SupabaseStorageConfigurationError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except SupabaseStorageOperationError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    return GlobalConfigResponse(
        key=str(config["key"]),
        value=config["value"],
        description=str(config["description"]),
    )


@router.get("/payment-methods", response_model=PaymentMethodsResponse)
async def list_payment_methods(uc: ConfigUseCases = Depends(get_config_use_cases)):
    payment_methods = await uc.get_payment_methods()
    return PaymentMethodsResponse(payment_methods=payment_methods)


@router.post("/payment-methods", response_model=PaymentMethodsResponse)
async def add_payment_method(
    body: PaymentMethodCreate,
    _: User = Depends(get_current_user),
    uc: ConfigUseCases = Depends(get_config_use_cases),
):
    try:
        payment_methods = await uc.add_payment_method(body.name)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return PaymentMethodsResponse(payment_methods=payment_methods)


@router.delete("/payment-methods/{method_name}", response_model=PaymentMethodsResponse)
async def remove_payment_method(
    method_name: str,
    _: User = Depends(get_current_user),
    uc: ConfigUseCases = Depends(get_config_use_cases),
):
    try:
        payment_methods = await uc.remove_payment_method(method_name)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except KeyError as exc:
        detail = str(exc.args[0]) if exc.args else "El método de pago no existe"
        raise HTTPException(status_code=404, detail=detail) from exc
    return PaymentMethodsResponse(payment_methods=payment_methods)


@router.get("/{key}", response_model=GlobalConfigResponse)
async def get_config(key: str, uc: ConfigUseCases = Depends(get_config_use_cases)):
    config = await uc.get_by_key(key)
    if not config:
        raise HTTPException(status_code=404, detail=f"Config '{key}' no encontrada")
    return GlobalConfigResponse(
        key=str(config["key"]),
        value=config["value"],
        description=str(config["description"]),
    )


@router.put("/{key}", response_model=GlobalConfigResponse)
async def update_config(
    key: str,
    body: GlobalConfigUpdate,
    _: User = Depends(get_current_user),
    uc: ConfigUseCases = Depends(get_config_use_cases),
):
    config = await uc.update(key, body.value, body.description)
    return GlobalConfigResponse(
        key=str(config["key"]),
        value=config["value"],
        description=str(config["description"]),
    )
