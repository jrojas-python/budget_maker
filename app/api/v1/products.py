from fastapi import APIRouter, Depends, HTTPException, Query, Request, UploadFile, File

from app.application.use_cases.product_use_cases import ProductUseCases, build_product_response
from app.api.dependencies import get_current_user, get_product_use_cases
from app.domain.models.user import User
from app.domain.schemas.product import ProductColorsUpdate, ProductCreate, ProductUpdate, ProductResponse
from app.domain.schemas.search import PaginatedResponse, ProductSearchParams, SortBy

router = APIRouter(prefix="/api/v1/products", tags=["Productos"])


@router.get("/search", response_model=PaginatedResponse[ProductResponse])
async def search_products(
    request: Request,
    q: str | None = None,
    sku: str | None = None,
    category_id: str | None = None,
    category_slug: str | None = None,
    min_price: float | None = None,
    max_price: float | None = None,
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    sort_by: SortBy = SortBy.name_asc,
    uc: ProductUseCases = Depends(get_product_use_cases),
):
    params = ProductSearchParams(
        q=q, sku=sku, category_id=category_id, category_slug=category_slug,
        min_price=min_price, max_price=max_price, page=page, limit=limit, sort_by=sort_by,
    )
    return await uc.search(params, str(request.base_url))


@router.get("/", response_model=list[ProductResponse])
async def list_products(request: Request, uc: ProductUseCases = Depends(get_product_use_cases)):
    products = await uc.list_all()
    return [build_product_response(p, str(request.base_url)) for p in products]


@router.get("/{product_id}", response_model=ProductResponse)
async def get_product(product_id: str, request: Request, uc: ProductUseCases = Depends(get_product_use_cases)):
    product = await uc.get_by_id(product_id)
    if not product:
        raise HTTPException(status_code=404, detail="Producto no encontrado")
    categories = await uc.enrich_categories(product)
    return build_product_response(product, str(request.base_url), categories)


@router.post("/", response_model=ProductResponse, status_code=201)
async def create_product(
    body: ProductCreate,
    request: Request,
    _: User = Depends(get_current_user),
    uc: ProductUseCases = Depends(get_product_use_cases),
):
    product = await uc.create(body)
    return build_product_response(product, str(request.base_url))


@router.put("/{product_id}", response_model=ProductResponse)
async def update_product(
    product_id: str,
    body: ProductUpdate,
    request: Request,
    _: User = Depends(get_current_user),
    uc: ProductUseCases = Depends(get_product_use_cases),
):
    product = await uc.update(product_id, body)
    if not product:
        raise HTTPException(status_code=404, detail="Producto no encontrado")
    return build_product_response(product, str(request.base_url))


@router.delete("/{product_id}", status_code=204)
async def delete_product(
    product_id: str,
    _: User = Depends(get_current_user),
    uc: ProductUseCases = Depends(get_product_use_cases),
):
    deleted = await uc.delete(product_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Producto no encontrado")


@router.post("/{product_id}/image", response_model=ProductResponse)
async def upload_product_image(
    product_id: str,
    request: Request,
    file: UploadFile = File(...),
    _: User = Depends(get_current_user),
    uc: ProductUseCases = Depends(get_product_use_cases),
):
    """Sube una imagen y la agrega a la galería del producto."""
    from app.infrastructure.services.image_service import ImageService
    svc = ImageService()
    try:
        content = await svc.validate_image(file)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    try:
        product = await uc.upload_image(product_id, content, file.filename or "image.jpg")
    except ValueError as e:
        detail = str(e)
        raise HTTPException(status_code=404 if detail == "Producto no encontrado" else 422, detail=detail)
    return build_product_response(product, str(request.base_url))


@router.delete("/{product_id}/images/{filename}", response_model=ProductResponse)
async def delete_product_image(
    product_id: str,
    filename: str,
    request: Request,
    _: User = Depends(get_current_user),
    uc: ProductUseCases = Depends(get_product_use_cases),
):
    """Elimina una imagen específica de un producto."""
    try:
        product = await uc.delete_image(product_id, filename)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    return build_product_response(product, str(request.base_url))


@router.put("/{product_id}/colors", response_model=ProductResponse)
async def update_product_colors(
    product_id: str,
    body: ProductColorsUpdate,
    request: Request,
    _: User = Depends(get_current_user),
    uc: ProductUseCases = Depends(get_product_use_cases),
):
    product = await uc.update_colors(product_id, body)
    if not product:
        raise HTTPException(status_code=404, detail="Producto no encontrado")
    return build_product_response(product, str(request.base_url))


@router.post("/import")
async def import_products(
    file: UploadFile = File(...),
    _: User = Depends(get_current_user),
    uc: ProductUseCases = Depends(get_product_use_cases),
):
    """Importa productos desde un archivo .xlsx con regla upsert por SKU."""
    if not file.filename or not file.filename.endswith(".xlsx"):
        raise HTTPException(status_code=422, detail="Solo se aceptan archivos .xlsx")
    content = await file.read()
    try:
        result = await uc.bulk_import_from_excel(content)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    return result
