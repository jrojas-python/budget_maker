# Changelog — Budget Maker API

Registro de iteraciones del proyecto.

---

## [2026-08-15] Iteración 1 — Scaffolding inicial

### Realizado
- Creación de estructura base del proyecto
- PRD.md con reglas de trabajo y alcance
- Docker setup (Dockerfile, docker-compose.yml)
- Configuración (settings/config.py, .env)
- Entry point (main.py)
- Base de datos (app/database.py)
- Modelos de dominio (Product, Budget, GlobalConfig)
- Schemas Pydantic v2
- Repositorios (base, product, budget, config)
- Servicios de infraestructura (PDF, Excel)
- Casos de uso (config, product, budget)
- API routers v1 (config, products, budgets)
- Frontend MVP (web/views.py, templates)
- README.md completo

### Archivos creados
- `PRD.md`
- `.agents/changelog.md`
- `Dockerfile`
- `docker-compose.yml`
- `requirements.txt`
- `.env`
- `settings/config.py`
- `app/__init__.py`
- `app/database.py`
- `app/domain/models/*.py`
- `app/domain/schemas/*.py`
- `app/infrastructure/repositories/*.py`
- `app/infrastructure/services/*.py`
- `app/application/use_cases/*.py`
- `app/api/dependencies.py`
- `app/api/v1/*.py`
- `web/views.py`
- `web/templates/*.html`
- `web/static/styles.css`
- `main.py`
- `README.md`

---

## [2026-08-26] Iteración 2 — Configuración global tipada del negocio

### Realizado
- Implementación de documento global tipado (`tax_rate`, `link_ttl_minutes`, `show_product_photos_in_pdf`) con índice singleton.
- Compatibilidad temporal para consumo legacy (`porcentaje_impuesto`, `tiempo_expiracion_link_minutos`) y claves auxiliares de UI.
- Nuevos endpoints tipados `GET/PUT /api/v1/config/global` manteniendo `/api/v1/config/` y `/api/v1/config/{key}`.
- Integración en creación de presupuestos para aplicar impuesto y TTL vigentes al momento de emisión.
- Persistencia de `link_ttl_minutes` en cada presupuesto para evitar cambios retroactivos de expiración.
- Cobertura de pruebas para configuración tipada y comportamiento de presupuestos ante cambios de configuración.
- Actualización de README con nuevo contrato y comportamiento de configuración global.

### Archivos modificados
- `app/domain/models/global_config.py`
- `app/domain/schemas/global_config.py`
- `app/infrastructure/repositories/config_repo.py`
- `app/application/use_cases/config_use_cases.py`
- `app/api/v1/config.py`
- `app/domain/models/budget.py`
- `app/domain/schemas/budget.py`
- `app/application/use_cases/budget_use_cases.py`
- `app/api/v1/budgets.py`
- `README.md`
- `.agents/changelog.md`

### Archivos creados
- `tests/test_config.py`
- `tests/test_budgets.py`

---

## [2026-08-26] Iteración 3 — Membrete y métodos de pago dinámicos

### Realizado
- Se añadió almacenamiento tipado de métodos de pago dinámicos en `GlobalConfig`.
- Se implementó CRUD mínimo de métodos de pago (`GET/POST/DELETE`) con normalización, deduplicación y validaciones explícitas.
- Se agregó endpoint explícito de logo `POST /api/v1/config/logo` con validación estricta PNG/JPG y HTTP 400 para formato inválido.
- Se mantuvo compatibilidad del endpoint legacy `POST /api/v1/config/branding/{key}` y para `site_logo` se alineó la validación al contrato de logo.
- Se amplió la suite de pruebas para cubrir matriz de escenarios de branding y métodos de pago.
- Se actualizó README con el contrato final de endpoints, validaciones y uso.

### Archivos modificados
- `app/domain/models/global_config.py`
- `app/domain/schemas/global_config.py`
- `app/infrastructure/repositories/config_repo.py`
- `app/application/use_cases/config_use_cases.py`
- `app/api/v1/config.py`
- `tests/test_config.py`
- `README.md`
- `.agents/changelog.md`
