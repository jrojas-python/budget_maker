from fastapi import Depends, HTTPException
from fastapi.security import OAuth2PasswordBearer

from app.application.use_cases.auth_use_cases import AuthUseCases
from app.application.use_cases.budget_use_cases import BudgetUseCases
from app.application.use_cases.category_use_cases import CategoryUseCases
from app.application.use_cases.config_use_cases import ConfigUseCases
from app.application.use_cases.product_use_cases import ProductUseCases
from app.application.use_cases.user_use_cases import UserUseCases
from app.domain.models.user import User
from app.infrastructure.repositories.budget_repo import BudgetRepository
from app.infrastructure.repositories.category_repo import CategoryRepository
from app.infrastructure.repositories.config_repo import ConfigRepository
from app.infrastructure.repositories.product_repo import ProductRepository
from app.infrastructure.repositories.user_repo import UserRepository
from app.infrastructure.services.auth_service import decode_token
from app.infrastructure.services.excel_service import ExcelService
from app.infrastructure.services.image_service import ImageService
from app.infrastructure.services.pdf_service import PdfService

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")

# Instancias singleton de repositorios y servicios
_product_repo = ProductRepository()
_budget_repo = BudgetRepository()
_config_repo = ConfigRepository()
_user_repo = UserRepository()
_category_repo = CategoryRepository()
_excel_service = ExcelService()
_pdf_service = PdfService()
_image_service = ImageService()


async def get_current_user(token: str = Depends(oauth2_scheme)) -> User:
    """Dependency que valida el JWT y retorna el usuario autenticado."""
    payload = decode_token(token)
    if not payload or "sub" not in payload:
        raise HTTPException(status_code=401, detail="Token inválido o expirado")
    user = await _user_repo.get_by_id(payload["sub"])
    if not user:
        raise HTTPException(status_code=401, detail="Usuario no encontrado")
    if not user.is_active:
        raise HTTPException(status_code=403, detail="Usuario desactivado")
    return user


def get_auth_use_cases() -> AuthUseCases:
    return AuthUseCases(user_repo=_user_repo)


def get_user_use_cases() -> UserUseCases:
    return UserUseCases(repo=_user_repo)


def get_config_use_cases() -> ConfigUseCases:
    return ConfigUseCases(repo=_config_repo)


def get_product_use_cases() -> ProductUseCases:
    return ProductUseCases(
        repo=_product_repo,
        excel_service=_excel_service,
        image_service=_image_service,
        category_repo=_category_repo,
    )


def get_category_use_cases() -> CategoryUseCases:
    return CategoryUseCases(repo=_category_repo, product_repo=_product_repo)


def get_budget_use_cases() -> BudgetUseCases:
    return BudgetUseCases(
        budget_repo=_budget_repo,
        product_repo=_product_repo,
        config_repo=_config_repo,
        pdf_service=_pdf_service,
    )
