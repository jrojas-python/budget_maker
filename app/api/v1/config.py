from fastapi import APIRouter, Depends, HTTPException

from app.application.use_cases.config_use_cases import ConfigUseCases
from app.api.dependencies import get_config_use_cases
from app.domain.schemas.global_config import GlobalConfigResponse, GlobalConfigUpdate

router = APIRouter(prefix="/api/v1/config", tags=["Configuración"])


@router.get("/", response_model=list[GlobalConfigResponse])
async def list_config(uc: ConfigUseCases = Depends(get_config_use_cases)):
    configs = await uc.get_all()
    return [GlobalConfigResponse(key=c.key, value=c.value, description=c.description) for c in configs]


@router.get("/{key}", response_model=GlobalConfigResponse)
async def get_config(key: str, uc: ConfigUseCases = Depends(get_config_use_cases)):
    config = await uc.get_by_key(key)
    if not config:
        raise HTTPException(status_code=404, detail=f"Config '{key}' no encontrada")
    return GlobalConfigResponse(key=config.key, value=config.value, description=config.description)


@router.put("/{key}", response_model=GlobalConfigResponse)
async def update_config(key: str, body: GlobalConfigUpdate, uc: ConfigUseCases = Depends(get_config_use_cases)):
    config = await uc.update(key, body.value, body.description)
    return GlobalConfigResponse(key=config.key, value=config.value, description=config.description)
