from fastapi import APIRouter, Depends, HTTPException

from app.api.dependencies import get_auth_use_cases, get_current_user
from app.application.use_cases.auth_use_cases import AuthUseCases
from app.domain.models.user import User
from app.domain.schemas.user import LoginRequest, TokenResponse, UserResponse

router = APIRouter(prefix="/api/v1/auth", tags=["Autenticación"])


@router.post("/login", response_model=TokenResponse)
async def login(body: LoginRequest, uc: AuthUseCases = Depends(get_auth_use_cases)):
    token = await uc.login(body)
    if not token:
        raise HTTPException(status_code=401, detail="Credenciales inválidas")
    return TokenResponse(access_token=token)


@router.get("/me", response_model=UserResponse)
async def me(current_user: User = Depends(get_current_user)):
    return UserResponse(
        id=str(current_user.id),
        username=current_user.username,
        email=current_user.email,
        is_active=current_user.is_active,
        created_at=current_user.created_at,
    )
