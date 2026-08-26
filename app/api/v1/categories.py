from fastapi import APIRouter, Depends, HTTPException

from app.api.dependencies import get_category_use_cases, get_current_user
from app.application.use_cases.category_use_cases import CategoryUseCases
from app.domain.models.user import User
from app.domain.schemas.category import CategoryCreate, CategoryUpdate, CategoryResponse

router = APIRouter(prefix="/api/v1/categories", tags=["Categorías"])


@router.get("/", response_model=list[CategoryResponse])
async def list_categories(
    active_only: bool = False,
    uc: CategoryUseCases = Depends(get_category_use_cases),
):
    categories = await uc.list_all(active_only=active_only)
    return [
        CategoryResponse(id=str(c.id), name=c.name, slug=c.slug, description=c.description, is_active=c.is_active)
        for c in categories
    ]


@router.get("/{category_id}", response_model=CategoryResponse)
async def get_category(category_id: str, uc: CategoryUseCases = Depends(get_category_use_cases)):
    category = await uc.get_by_id(category_id)
    if not category:
        raise HTTPException(status_code=404, detail="Categoría no encontrada")
    return CategoryResponse(id=str(category.id), name=category.name, slug=category.slug, description=category.description, is_active=category.is_active)


@router.post("/", response_model=CategoryResponse, status_code=201)
async def create_category(
    body: CategoryCreate,
    _: User = Depends(get_current_user),
    uc: CategoryUseCases = Depends(get_category_use_cases),
):
    try:
        category = await uc.create(body)
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e))
    return CategoryResponse(id=str(category.id), name=category.name, slug=category.slug, description=category.description, is_active=category.is_active)


@router.put("/{category_id}", response_model=CategoryResponse)
async def update_category(
    category_id: str,
    body: CategoryUpdate,
    _: User = Depends(get_current_user),
    uc: CategoryUseCases = Depends(get_category_use_cases),
):
    try:
        category = await uc.update(category_id, body)
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e))
    if not category:
        raise HTTPException(status_code=404, detail="Categoría no encontrada")
    return CategoryResponse(id=str(category.id), name=category.name, slug=category.slug, description=category.description, is_active=category.is_active)


@router.delete("/{category_id}", status_code=204)
async def delete_category(
    category_id: str,
    _: User = Depends(get_current_user),
    uc: CategoryUseCases = Depends(get_category_use_cases),
):
    deleted = await uc.delete(category_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Categoría no encontrada")
