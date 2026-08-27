from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile

from app.application.use_cases.config_use_cases import ConfigUseCases
from app.api.dependencies import get_config_use_cases, get_current_user
from app.domain.models.user import User
from app.domain.schemas.global_config import (
    GlobalBusinessConfigResponse,
    GlobalBusinessConfigUpdate,
    GlobalConfigResponse,
    GlobalConfigUpdate,
    PaymentMethodCreate,
    PaymentMethodsResponse,
)
from settings.config import Settings

router = APIRouter(prefix="/api/v1/config", tags=["Configuración"])

_ALLOWED_IMAGE_TYPES = {"image/png", "image/jpeg", "image/webp", "image/svg+xml", "image/x-icon", "image/vnd.microsoft.icon"}
_ALLOWED_LOGO_TYPES = {"image/png", "image/jpeg", "image/jpg"}
_BRANDING_KEYS = {"site_logo", "site_icon"}


@router.get("/", response_model=list[GlobalConfigResponse])
async def list_config(uc: ConfigUseCases = Depends(get_config_use_cases)):
    configs = await uc.get_all()
    return [GlobalConfigResponse(key=c["key"], value=c["value"], description=str(c["description"])) for c in configs]


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
    if key == "site_logo":
        url = await _save_branding_file(
            key=key,
            file=file,
            allowed_types=_ALLOWED_LOGO_TYPES,
            invalid_type_status_code=400,
            invalid_type_detail="Formato de logo inválido. Usar PNG o JPG",
        )
    else:
        url = await _save_branding_file(
            key=key,
            file=file,
            allowed_types=_ALLOWED_IMAGE_TYPES,
            invalid_type_status_code=422,
            invalid_type_detail="Formato no soportado. Usar PNG, JPEG, WebP, SVG o ICO",
        )
    config = await uc.update(key, url, f"{'Logo' if key == 'site_logo' else 'Icono'} del sitio")
    return GlobalConfigResponse(key=str(config["key"]), value=config["value"], description=str(config["description"]))


@router.post("/logo", response_model=GlobalConfigResponse)
async def upload_logo(
    file: UploadFile = File(...),
    _: User = Depends(get_current_user),
    uc: ConfigUseCases = Depends(get_config_use_cases),
):
    url = await _save_branding_file(
        key="site_logo",
        file=file,
        allowed_types=_ALLOWED_LOGO_TYPES,
        invalid_type_status_code=400,
        invalid_type_detail="Formato de logo inválido. Usar PNG o JPG",
    )
    config = await uc.update("site_logo", url, "Logo del sitio")
    return GlobalConfigResponse(key=str(config["key"]), value=config["value"], description=str(config["description"]))


@router.delete("/branding/{key}", response_model=GlobalConfigResponse)
async def delete_branding(
    key: str,
    _: User = Depends(get_current_user),
    uc: ConfigUseCases = Depends(get_config_use_cases),
):
    """Elimina logo o icono del sitio."""
    if key not in _BRANDING_KEYS:
        raise HTTPException(status_code=422, detail=f"Clave inválida. Usar: {_BRANDING_KEYS}")
    settings = Settings()
    for old in Path(settings.branding_dir).glob(f"{key}.*"):
        old.unlink()
    config = await uc.update(key, "", f"{'Logo' if key == 'site_logo' else 'Icono'} del sitio")
    return GlobalConfigResponse(key=str(config["key"]), value=config["value"], description=str(config["description"]))


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
    return GlobalConfigResponse(key=str(config["key"]), value=config["value"], description=str(config["description"]))


@router.put("/{key}", response_model=GlobalConfigResponse)
async def update_config(
    key: str,
    body: GlobalConfigUpdate,
    _: User = Depends(get_current_user),
    uc: ConfigUseCases = Depends(get_config_use_cases),
):
    config = await uc.update(key, body.value, body.description)
    return GlobalConfigResponse(key=str(config["key"]), value=config["value"], description=str(config["description"]))


async def _save_branding_file(
    key: str,
    file: UploadFile,
    allowed_types: set[str],
    invalid_type_status_code: int,
    invalid_type_detail: str,
) -> str:
    if not file.content_type or file.content_type not in allowed_types:
        raise HTTPException(status_code=invalid_type_status_code, detail=invalid_type_detail)

    content = await file.read()
    settings = Settings()
    if len(content) > settings.max_image_size_mb * 1024 * 1024:
        raise HTTPException(status_code=422, detail=f"Archivo excede {settings.max_image_size_mb}MB")

    ext = Path(file.filename).suffix if file.filename else ".png"
    filename = f"{key}{ext}"
    branding_path = Path(settings.branding_dir)
    branding_path.mkdir(parents=True, exist_ok=True)
    for old in branding_path.glob(f"{key}.*"):
        old.unlink()
    (branding_path / filename).write_bytes(content)
    return f"/uploads/branding/{filename}"
