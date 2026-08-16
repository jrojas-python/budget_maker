from fastapi import APIRouter, Depends, HTTPException, UploadFile, File

from app.application.use_cases.product_use_cases import ProductUseCases
from app.api.dependencies import get_product_use_cases
from app.domain.schemas.product import ProductCreate, ProductUpdate, ProductResponse

router = APIRouter(prefix="/api/v1/products", tags=["Productos"])


@router.get("/", response_model=list[ProductResponse])
async def list_products(uc: ProductUseCases = Depends(get_product_use_cases)):
    products = await uc.list_all()
    return [
        ProductResponse(id=str(p.id), name=p.name, sku=p.sku, cost=p.cost, unit=p.unit, currency=p.currency)
        for p in products
    ]


@router.get("/{product_id}", response_model=ProductResponse)
async def get_product(product_id: str, uc: ProductUseCases = Depends(get_product_use_cases)):
    product = await uc.get_by_id(product_id)
    if not product:
        raise HTTPException(status_code=404, detail="Producto no encontrado")
    return ProductResponse(id=str(product.id), name=product.name, sku=product.sku, cost=product.cost, unit=product.unit, currency=product.currency)


@router.post("/", response_model=ProductResponse, status_code=201)
async def create_product(body: ProductCreate, uc: ProductUseCases = Depends(get_product_use_cases)):
    product = await uc.create(body)
    return ProductResponse(id=str(product.id), name=product.name, sku=product.sku, cost=product.cost, unit=product.unit, currency=product.currency)


@router.put("/{product_id}", response_model=ProductResponse)
async def update_product(product_id: str, body: ProductUpdate, uc: ProductUseCases = Depends(get_product_use_cases)):
    product = await uc.update(product_id, body)
    if not product:
        raise HTTPException(status_code=404, detail="Producto no encontrado")
    return ProductResponse(id=str(product.id), name=product.name, sku=product.sku, cost=product.cost, unit=product.unit, currency=product.currency)


@router.delete("/{product_id}", status_code=204)
async def delete_product(product_id: str, uc: ProductUseCases = Depends(get_product_use_cases)):
    deleted = await uc.delete(product_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Producto no encontrado")


@router.post("/import")
async def import_products(file: UploadFile = File(...), uc: ProductUseCases = Depends(get_product_use_cases)):
    """Importa productos desde un archivo .xlsx con regla upsert por SKU."""
    if not file.filename or not file.filename.endswith(".xlsx"):
        raise HTTPException(status_code=422, detail="Solo se aceptan archivos .xlsx")
    content = await file.read()
    try:
        result = await uc.bulk_import_from_excel(content)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    return result
