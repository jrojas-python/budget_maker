# Changelog — Budget Maker API

Registro de iteraciones del proyecto.

---

## [2026-08-31] Iteración 11 — Cierre operativo de historias 2.1, 2.2 y 2.3

### Realizado
- Se validó con pruebas enfocadas la historia 2.2 sobre UUID malformado, expiración y descarga PDF pública, confirmando el contrato 422/404/410 y la protección del recurso expirado.
- Se validó con pruebas enfocadas la historia 2.3 sobre snapshot e inmutabilidad de montos para confirmar que presupuestos emitidos no se recalculan tras cambios posteriores.
- Se validó con pruebas enfocadas la historia 2.1 sobre persistencia de `client_info.email`, aceptación de método de pago activo, rechazo de método inactivo con HTTP 422 y compatibilidad cuando el campo se omite.
- Se endureció la validación de `category_ids` y `category_id` en productos/búsqueda para responder HTTP 422 ante ObjectIds inválidos, evitando errores 500 en Epic 1.
- Se adelantó la creación de directorios de uploads antes del mount de `StaticFiles`, eliminando el riesgo de fallo de arranque en entornos limpios.
- Se validó Epic 1 con pruebas enfocadas de configuración tipada, branding, importación Excel y búsqueda para habilitar su cierre operativo.
- Se actualizó README para documentar `payment_method` y `client_info.email` en la creación de presupuestos.
- Se actualizó README para documentar validaciones 422 de `category_ids`/`category_id` en productos y búsqueda.
- Se sincronizó `sprint-status.yaml` marcando Epic 2 en `done` y dejando Epic 1 listo para sincronización final.

### Archivos modificados
- `_bmad-output/implementation-artifacts/sprint-status.yaml`
- `README.md`
- `.agents/changelog.md`
- `app/application/use_cases/product_use_cases.py`
- `app/api/v1/products.py`
- `main.py`
- `tests/test_products.py`

---

## [2026-08-28] Iteración 10 — Historia 2.2 identificación pública y expiración

### Realizado
- Se endureció el modelo `Budget` con índices únicos en MongoDB para `code` y `uuid`, garantizando unicidad persistente de identificadores públicos.
- Se tiparon como `UUID4` las rutas públicas/API de presupuesto y PDF/WhatsApp, habilitando rechazo automático con HTTP 422 para UUID malformado antes de ejecutar lógica de consulta.
- Se incorporó manejo explícito de colisiones de identificadores: el repositorio detecta `DuplicateKeyError`, la capa de aplicación reintenta de forma acotada ante colisión de `code` y falla explícitamente para colisiones de `uuid`.
- Se actualizó el contrato API para responder HTTP 409 en colisiones de identificador público durante creación de presupuestos.
- Se añadieron pruebas para UUID inválido (422), reintento ante colisión de `code` y falla explícita por colisión de `uuid` (409).
- Se documentó en README la política de unicidad, validación UUID en frontera HTTP y comportamiento de reintento.

### Archivos modificados
- `app/domain/models/budget.py`
- `app/domain/schemas/budget.py`
- `app/infrastructure/repositories/budget_repo.py`
- `app/application/use_cases/budget_use_cases.py`
- `app/api/v1/budgets.py`
- `web/views.py`
- `tests/test_budgets.py`
- `README.md`
- `.agents/changelog.md`

---

## [2026-08-28] Iteración 9 — Code review Story 2.4 (hardening y cobertura)

### Realizado
- Se corrigió la generación de `base_url` para PDF en API y web pública para que no dependa de `Path.cwd()` y sea estable aunque el proceso arranque fuera de la raíz.
- Se eliminó el patrón `N+1` al resolver imágenes de productos en render de presupuesto/PDF mediante consulta por lote de SKUs.
- Se añadió cobertura del camino exitoso de descarga PDF pública (`GET /presupuesto/{uuid}/pdf`), validando `200`, `application/pdf` y firma `%PDF`.
- Se reforzó la prueba de branding server-side verificando la presencia del logo en el HTML renderizado para PDF.
- Se marcaron como resueltos los hallazgos `patch` del code review en la spec de la historia 2.4 y se sincronizó su estado en sprint-status.

### Archivos modificados
- `app/infrastructure/repositories/product_repo.py`
- `app/application/use_cases/budget_use_cases.py`
- `app/api/v1/budgets.py`
- `web/views.py`
- `tests/test_budgets.py`
- `_bmad-output/implementation-artifacts/spec-2-4-generacion-de-pdf-profesional-configurable.md`
- `_bmad-output/implementation-artifacts/sprint-status.yaml`
- `README.md`
- `.agents/changelog.md`

---

## [2026-08-28] Iteración 8 — Historia 2.5 enlace canónico de WhatsApp

### Realizado
- Se reemplazó la composición de WhatsApp por un builder canónico en backend (`BudgetUseCases.generate_whatsapp_share_url`) con formato `wa.me` URL-encoded UTF-8 e inclusión explícita de empresa, código, total y link temporal.
- Se unificó la vista pública para construir el link temporal con `request.url_for(...)` y delegar la URL de WhatsApp al builder backend usando `site_title` del contexto render.
- Se incorporó el endpoint `GET /api/v1/budgets/{uuid}/whatsapp-share` para que el flujo de catálogo consuma exactamente el mismo formato canónico sin duplicar lógica en JavaScript.
- Se eliminó el armado manual del mensaje WhatsApp en `web/static/js/catalog.js` y se reemplazó por consumo del endpoint backend.
- Se añadieron pruebas de presupuesto para validar formato canónico, fallback de empresa, encoding de caracteres especiales y consistencia entre flujo API y vista web.
- Se documentó en README el endpoint de compartición y la política de formato canónico.

### Archivos modificados
- `app/application/use_cases/budget_use_cases.py`
- `app/api/v1/budgets.py`
- `web/views.py`
- `web/static/js/catalog.js`
- `tests/test_budgets.py`
- `README.md`
- `.agents/changelog.md`

---

## [2026-08-28] Iteración 7 — Historia 2.4 PDF profesional configurable

### Realizado
- Se creó el endpoint `GET /api/v1/budgets/{uuid}/pdf` con contrato explícito: 200 para vigente, 404 para inexistente y 410 para expirado.
- Se alineó `/presupuesto/{uuid}/pdf` para bloquear presupuestos expirados con HTTP 410 y reutilizar el mismo contexto de render PDF.
- Se amplió la orquestación de `BudgetUseCases` para construir contexto PDF server-side con branding (`site_logo`, `site_title`, `site_subtitle`) y bandera `show_product_photos_in_pdf`.
- Se actualizó la plantilla pública para separar comportamiento web/PDF y mostrar/ocultar la columna de fotos según configuración global.
- Se incorporaron reglas de impresión en CSS (`@page`, cabecera repetible, tabla legible) para salida PDF consistente.
- Se añadieron pruebas de contrato para PDF API (200/404/410), ruta web expirado (410) y visibilidad de fotos según configuración.
- Se documentó en README el nuevo endpoint API PDF y la política de expiración/fotos.

### Archivos modificados
- `app/api/v1/budgets.py`
- `app/application/use_cases/budget_use_cases.py`
- `app/domain/models/budget.py`
- `app/domain/schemas/budget.py`
- `app/infrastructure/services/pdf_service.py`
- `web/views.py`
- `web/templates/base.html`
- `web/templates/public/budget_view.html`
- `web/static/styles.css`
- `tests/test_budgets.py`
- `README.md`
- `.agents/changelog.md`

---

## [2026-08-28] Iteración 6 — Historia 2.3 montos inmutables de cotización

### Realizado
- Se reforzó el contrato de snapshot de montos al crear presupuestos para mantener `unit_cost`, `line_total`, `subtotal`, `tax_amount` y `total` inmutables en presupuestos emitidos.
- Se agregó cobertura de pruebas para garantizar que un cambio posterior de costo de producto no altera cotizaciones existentes y sí impacta cotizaciones nuevas.
- Se añadió prueba de error para SKU inexistente al crear presupuesto (HTTP 422).
- Se alineó la evaluación de expiración en fallback legacy para usar el mismo borde temporal que presupuestos con `expires_at`.
- Se actualizó README con el comportamiento de expiración (410) e inmutabilidad de montos.

### Archivos modificados
- `app/application/use_cases/budget_use_cases.py`
- `tests/test_budgets.py`
- `README.md`
- `.agents/changelog.md`
- `_bmad-output/implementation-artifacts/spec-2-3-calculo-inmutable-de-montos-de-cotizacion.md`
- `_bmad-output/implementation-artifacts/sprint-status.yaml`

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
