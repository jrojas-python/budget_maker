from app.application.use_cases.budget_use_cases import BudgetUseCases
from app.application.use_cases.config_use_cases import ConfigUseCases
from app.application.use_cases.product_use_cases import ProductUseCases
from app.infrastructure.repositories.budget_repo import BudgetRepository
from app.infrastructure.repositories.config_repo import ConfigRepository
from app.infrastructure.repositories.product_repo import ProductRepository
from app.infrastructure.services.excel_service import ExcelService
from app.infrastructure.services.pdf_service import PdfService

# Instancias singleton de repositorios y servicios
_product_repo = ProductRepository()
_budget_repo = BudgetRepository()
_config_repo = ConfigRepository()
_excel_service = ExcelService()
_pdf_service = PdfService()


def get_config_use_cases() -> ConfigUseCases:
    return ConfigUseCases(repo=_config_repo)


def get_product_use_cases() -> ProductUseCases:
    return ProductUseCases(repo=_product_repo, excel_service=_excel_service)


def get_budget_use_cases() -> BudgetUseCases:
    return BudgetUseCases(
        budget_repo=_budget_repo,
        product_repo=_product_repo,
        config_repo=_config_repo,
        pdf_service=_pdf_service,
    )
