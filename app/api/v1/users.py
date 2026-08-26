from fastapi import APIRouter, Depends, HTTPException

from app.api.dependencies import get_current_user, get_user_use_cases
from app.application.use_cases.user_use_cases import UserUseCases
from app.domain.models.user import User
from app.domain.schemas.user import UserCreate, UserUpdate, UserResponse

router = APIRouter(prefix="/api/v1/users", tags=["Usuarios"])


@router.get("/", response_model=list[UserResponse])
async def list_users(
    _: User = Depends(get_current_user),
    uc: UserUseCases = Depends(get_user_use_cases),
):
    users = await uc.list_all()
    return [
        UserResponse(id=str(u.id), username=u.username, email=u.email, is_active=u.is_active, created_at=u.created_at)
        for u in users
    ]


@router.get("/{user_id}", response_model=UserResponse)
async def get_user(
    user_id: str,
    _: User = Depends(get_current_user),
    uc: UserUseCases = Depends(get_user_use_cases),
):
    user = await uc.get_by_id(user_id)
    if not user:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")
    return UserResponse(id=str(user.id), username=user.username, email=user.email, is_active=user.is_active, created_at=user.created_at)


@router.post("/", response_model=UserResponse, status_code=201)
async def create_user(
    body: UserCreate,
    _: User = Depends(get_current_user),
    uc: UserUseCases = Depends(get_user_use_cases),
):
    try:
        user = await uc.create(body)
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e))
    return UserResponse(id=str(user.id), username=user.username, email=user.email, is_active=user.is_active, created_at=user.created_at)


@router.put("/{user_id}", response_model=UserResponse)
async def update_user(
    user_id: str,
    body: UserUpdate,
    _: User = Depends(get_current_user),
    uc: UserUseCases = Depends(get_user_use_cases),
):
    try:
        user = await uc.update(user_id, body)
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e))
    if not user:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")
    return UserResponse(id=str(user.id), username=user.username, email=user.email, is_active=user.is_active, created_at=user.created_at)


@router.delete("/{user_id}", status_code=204)
async def delete_user(
    user_id: str,
    current_user: User = Depends(get_current_user),
    uc: UserUseCases = Depends(get_user_use_cases),
):
    if str(current_user.id) == user_id:
        raise HTTPException(status_code=400, detail="No puedes eliminarte a ti mismo")
    deleted = await uc.delete(user_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")
