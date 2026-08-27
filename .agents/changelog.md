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

## [2026-08-26] Iteracion 4 - Catalogo de productos con imagenes y tags

### Realizado
- Se amplio el modelo `Product` para soportar listas de imagenes (`images`) y tags normalizados (`tags`) manteniendo compatibilidad temporal con `image_filename`.
- Se actualizo el contrato API de productos para responder `image_urls` y `tags`, y se agregaron validaciones de maximo 10 imagenes y 15 tags.
- Se refactorizo la logica de carga/eliminacion de imagenes para operar por archivo individual, con fallback de lectura para productos legacy.
- Se adapto el frontend web para consumir `image_urls` y gestionar eliminacion individual de imagenes existentes.
- Se incorporo cobertura de pruebas para normalizacion de tags, limites de imagenes, errores de formato y compatibilidad legacy.
- Se actualizo README con el contrato de imagenes/tags y los nuevos limites operativos.

### Archivos modificados
- `app/domain/models/product.py`
- `app/domain/schemas/product.py`
- `app/infrastructure/repositories/product_repo.py`
- `app/application/use_cases/product_use_cases.py`
- `app/api/v1/products.py`
- `web/templates/admin/dashboard.html`
- `web/static/js/catalog.js`
- `web/static/js/admin.js`
- `tests/test_products.py`
- `README.md`
- `.agents/changelog.md`
- `_bmad-output/implementation-artifacts/spec-1-3-catalogo-de-productos-con-imagenes-y-tags.md`
- `_bmad-output/implementation-artifacts/sprint-status.yaml`

---

## [2026-08-26] Iteración 5 — Contexto compilado de la épica 2

### Realizado
- Se compiló el contexto ejecutable de la épica 2 a partir de los artefactos de planificación disponibles.
- Se destilaron objetivo, historias, restricciones, decisiones técnicas, patrones de interacción y dependencias relevantes para desarrollo.
- Se omitió contenido no soportado por los artefactos y se mantuvo el foco en información útil para implementar historias de cotizaciones.

### Archivos modificados
- `_bmad-output/implementation-artifacts/epic-2-context.md`
- `.agents/changelog.md`
