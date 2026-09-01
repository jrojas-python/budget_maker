<!-- bmad:context -->
<!-- Verified 2026-08-25 against fd45c06. Managed by bmad-project-context; edits inside this block are replaced on refresh. Keep anything you want preserved outside the markers. -->

## budget_maker

API RESTful para la generación y gestión de presupuestos y cotizaciones de productos. Python, FastAPI, MongoDB (Beanie ODM), Docker y WeasyPrint. El PRD oficial reside en [PRD.md](file:///C:/Users/JesusRojas/Documents/pyfiles/budget_maker/PRD.md) y el registro de cambios en [.agents/changelog.md](file:///C:/Users/JesusRojas/Documents/pyfiles/budget_maker/.agents/changelog.md).

## Policy

- Desarrollar bajo la metodología **Gitflow** (ramas de feature basadas en `develop`, integradas vía Pull Requests).
- Definir y mantener flujos de CI/CD mediante **GitHub Actions** para validar pruebas, linter y empaquetado.
- Actualizar el [README.md](file:///C:/Users/JesusRojas/Documents/pyfiles/budget_maker/README.md) con arquitectura, endpoints y flujo de uso tras realizar cualquier cambio.
- Registrar cada iteración completada en [.agents/changelog.md](file:///C:/Users/JesusRojas/Documents/pyfiles/budget_maker/.agents/changelog.md) con fecha, descripción y archivos modificados.

## Where things are

- Modelos de base de datos (Beanie): [models](file:///C:/Users/JesusRojas/Documents/pyfiles/budget_maker/app/domain/models)
- Schemas de validación (Pydantic): [schemas](file:///C:/Users/JesusRojas/Documents/pyfiles/budget_maker/app/domain/schemas)
- Lógica de negocio (casos de uso): [use_cases](file:///C:/Users/JesusRojas/Documents/pyfiles/budget_maker/app/application/use_cases)
- Capa de datos (repositorios): [repositories](file:///C:/Users/JesusRojas/Documents/pyfiles/budget_maker/app/infrastructure/repositories)
- Endpoints de la API: [v1](file:///C:/Users/JesusRojas/Documents/pyfiles/budget_maker/app/api/v1)
- Vistas HTML y templates (Jinja2): [views.py](file:///C:/Users/JesusRojas/Documents/pyfiles/budget_maker/web/views.py) y [templates](file:///C:/Users/JesusRojas/Documents/pyfiles/budget_maker/web/templates)

## Running and verifying

- Ejecutar las pruebas usando `pytest`.
- Las pruebas en [tests](file:///C:/Users/JesusRojas/Documents/pyfiles/budget_maker/tests) requieren una instancia de MongoDB escuchando en `localhost:27017` (e.g. iniciada mediante `docker compose up -d mongodb`).
- Para levantar el entorno local completo de desarrollo (API, MongoDB, Mongo Express), ejecutar `docker compose up --build`.

## Conventions that differ from defaults

- Escribir toda la documentación, logs de commits y docstrings en **español**.
- Usar snake_case para variables y nombres de funciones en Python.
- Usar anotaciones de tipos (Type hints) conformes a Python 3.10+ (e.g. `str | None`, `list[str]`).
- Instanciar un logger por módulo mediante `logger = logging.getLogger(__name__)`.
- Diseñar la arquitectura asíncrona de extremo a extremo (`async` en handlers, repositorios y casos de uso).
- Utilizar `Depends` de FastAPI para inyectar repositorios y casos de uso.
- Separar estrictamente los schemas de entrada y salida (Create, Update, Response) para cada entidad.

## Known pitfalls

- Al correr pruebas locales fuera del contenedor de la API, asegúrate de levantar únicamente el servicio `mongodb` (`docker compose up -d mongodb`) para evitar colisiones en el puerto `8000`.

<!-- /bmad:context -->
