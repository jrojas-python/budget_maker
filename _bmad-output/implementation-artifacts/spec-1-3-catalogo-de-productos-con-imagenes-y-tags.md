---
title: 'Historia 1.3 - Catálogo de productos con imágenes y tags'
type: 'feature'
created: '2026-08-26'
baseline_commit: '02ca1591a036b90d8b7352b371d72b78c706f648'
status: 'done'
review_loop_iteration: 0
context:
  - '{project-root}/AGENTS.md'
  - '{project-root}/_bmad-output/implementation-artifacts/epic-1-context.md'
  - '{project-root}/_bmad-output/implementation-artifacts/spec-1-2-membrete-y-metodos-de-pago-dinamicos.md'
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** El modelo de producto actual soporta una sola imagen (`image_filename`) y no tiene campo de etiquetas (`tags`). La historia 1.3 requiere que productos soporten múltiples imágenes (0-10) y tags normalizados (0-15) para enriquecer el catálogo y habilitar búsqueda por tags en la historia 1.5.

**Approach:** Ampliar el modelo `Product` con campos `images: list[str]` (rutas relativas, máx 10) y `tags: list[str]` (máx 15), migrar la imagen singular existente al nuevo campo plural, actualizar schemas Create/Update/Response, exponer endpoints de carga y eliminación de imágenes individuales contra la lista, y devolver ambos campos en `ProductResponse`.

## Boundaries & Constraints

**Always:** Mantener Clean Architecture; conservar asincronía end-to-end; persistir rutas relativas (`/uploads/products/...`) en `images`; normalizar tags a minúsculas y sin espacios extremos; respetar límites (0-10 imágenes, 0-15 tags); preservar compatibilidad con el endpoint de importación Excel (no carga imágenes por Excel).

**Ask First:** Eliminar el campo legacy `image_filename` vs. mantenerlo como alias de lectura; cambiar el formato de almacenamiento de imágenes (ej. cloud); agregar validación de dimensiones/resolución de imagen.

**Never:** Romper el flujo de importación Excel existente; introducir carga de imágenes por Excel en esta historia; eliminar imágenes de disco de productos existentes durante la migración de schema; degradar rendimiento de listado de productos por carga masiva de archivos.

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| CREATE_WITH_TAGS | Producto con `tags: ["metal", "industrial"]` | Producto creado con tags normalizados persistidos | N/A |
| CREATE_EXCEEDS_TAGS | Producto con 16+ tags | Operación rechazada | HTTP 422 — máximo 15 tags |
| UPLOAD_IMAGE_HAPPY | PNG/JPG válido a producto con <10 imágenes | Imagen guardada, ruta agregada a `images` | N/A |
| UPLOAD_IMAGE_LIMIT | Producto ya con 10 imágenes | Carga rechazada | HTTP 422 — límite alcanzado |
| UPLOAD_IMAGE_INVALID | Archivo no PNG/JPG/WEBP | Carga rechazada | HTTP 400 — formato inválido |
| DELETE_IMAGE_HAPPY | Filename existente en `images` del producto | Archivo eliminado de disco y de la lista | N/A |
| DELETE_IMAGE_NOT_FOUND | Filename no pertenece al producto | Operación rechazada | HTTP 404 — imagen no encontrada |
| RESPONSE_FIELDS | GET de producto existente | `images` y `tags` presentes en respuesta con URLs completas | N/A |
| LEGACY_MIGRATION | Producto con `image_filename` pero sin `images` | `image_filename` migrado a `images[0]` en lectura | N/A |

</frozen-after-approval>

## Code Map

- `app/domain/models/product.py` -- modelo Beanie; actualmente tiene `image_filename: str | None` (L15). Agregar `images: list[str] = []` y `tags: list[str] = []`. Deprecar `image_filename`.
- `app/domain/schemas/product.py` -- schemas Pydantic. `ProductCreate` (L32), `ProductUpdate` (L50), `ProductResponse` (L66). Agregar `tags` con validación max 15 en Create/Update, `images` y `tags` en Response. Reemplazar `image_url: str | None` por `image_urls: list[str]`.
- `app/infrastructure/repositories/product_repo.py` -- repositorio; métodos `create` (L31), `update` (L36). Agregar `add_image(doc_id, filename)` y `remove_image(doc_id, filename)`.
- `app/application/use_cases/product_use_cases.py` -- casos de uso; `upload_image` (L85), `delete_image` (L95), `build_product_response` (helper). Refactorizar para multi-imagen y tags.
- `app/api/v1/products.py` -- endpoints; `POST /{id}/image` (L72), `DELETE /{id}/image` (L89). Adaptar a multi-imagen (agregar/eliminar individual).
- `app/infrastructure/services/image_service.py` -- servicio de imágenes; `save_image`, `delete_image`, `validate_image`. Sin cambios funcionales, solo se invoca múltiples veces.
- `tests/test_products.py` -- 7 tests existentes. Agregar tests para multi-imagen y tags.
- `README.md` -- documentar campos nuevos y cambios de contrato API.

## Tasks & Acceptance

**Execution:**
- [x] `app/domain/models/product.py` -- agregar campos `images: list[str] = []` y `tags: list[str] = []` al modelo `Product`; mantener `image_filename` temporalmente para compatibilidad -- habilita persistencia multi-imagen y tags.
- [x] `app/domain/schemas/product.py` -- agregar `tags: list[str] = Field(default=[], max_length=15)` a `ProductCreate` y `ProductUpdate`; reemplazar `image_url` por `image_urls: list[str]` en `ProductResponse`; agregar `tags` a Response -- define contrato API para campos nuevos.
- [x] `app/infrastructure/repositories/product_repo.py` -- agregar `add_image(doc_id, filename)` con `$push` y `remove_image(doc_id, filename)` con `$pull` -- operaciones atómicas sobre la lista de imágenes.
- [x] `app/application/use_cases/product_use_cases.py` -- refactorizar `upload_image` para validar límite de 10 y hacer push a `images`; refactorizar `delete_image` para recibir filename y hacer pull; actualizar `build_product_response` para generar `image_urls` (lista) con fallback de `image_filename` legacy; normalizar tags en create/update -- orquesta reglas de negocio de multi-imagen y tags.
- [x] `app/api/v1/products.py` -- adaptar `POST /{id}/image` para multi-imagen; cambiar `DELETE /{id}/image` a `DELETE /{id}/images/{filename}` -- expone superficie API actualizada.
- [x] `tests/test_products.py` -- tests para: crear con tags, exceder 15 tags, subir segunda imagen, límite 10 imágenes, eliminar imagen específica, respuesta incluye `image_urls` y `tags` -- cubre matriz I/O.
- [x] `README.md` -- documentar campos `images`/`tags`, nuevos endpoints y límites -- alinea consumidores.

**Acceptance Criteria:**
- Given un producto creado con tags `["Metal", " industrial "]`, when consulto el producto, then `tags` contiene `["metal", "industrial"]` normalizados.
- Given un producto con 9 imágenes, when subo una imagen válida, then se agrega como décima imagen y la respuesta muestra 10 URLs.
- Given un producto con 10 imágenes, when intento subir otra, then la API responde HTTP 422.
- Given un producto con `image_filename` legacy y sin `images`, when consulto el producto, then `image_urls` contiene la URL de la imagen legacy.

## Spec Change Log

## Design Notes

La migración de `image_filename` a `images` se maneja en tiempo de lectura (fallback en `build_product_response`), no como migración de base de datos, para evitar un script de migración y mantener simplicidad. El campo `image_filename` se preserva temporalmente; una tarea de limpieza futura puede eliminarlo.

## Verification

**Commands:**
- `pytest tests/test_products.py -q` -- expected: todos los tests pasan, incluyendo nuevos de multi-imagen y tags.
- `pytest -q` -- expected: sin regresiones en otros módulos.

## Suggested Review Order

**Contrato API y orquestacion**

- Punto de entrada del flujo de imagenes multiples y manejo de errores HTTP.
  [`products.py:85`](../../app/api/v1/products.py#L85)

- Centraliza fallback legacy, `image_urls` y tags normalizados en respuestas.
  [`product_use_cases.py:62`](../../app/application/use_cases/product_use_cases.py#L62)

- Aplica limite de 10 imagenes y borra archivos por nombre exacto.
  [`product_use_cases.py:135`](../../app/application/use_cases/product_use_cases.py#L135)

**Modelo, validacion y persistencia**

- Define almacenamiento canonico de `images` y `tags` en Beanie.
  [`product.py:22`](../../app/domain/models/product.py#L22)

- Valida y normaliza tags en create/update y expone `image_urls`.
  [`product.py:52`](../../app/domain/schemas/product.py#L52)

- Ejecuta operaciones atomicas `$push`/`$pull` sobre la galeria.
  [`product_repo.py:48`](../../app/infrastructure/repositories/product_repo.py#L48)

**Compatibilidad web**

- Expone captura de tags y tabla admin para operar el nuevo contrato.
  [`dashboard.html:54`](../../web/templates/admin/dashboard.html#L54)

- Renderiza galeria editable y adapta borrado individual en admin.
  [`admin.js:60`](../../web/static/js/admin.js#L60)

- Mantiene el catalogo publico usando la primera URL disponible.
  [`catalog.js:89`](../../web/static/js/catalog.js#L89)

**Verificacion y documentacion**

- Cubre normalizacion, limite 10, errores y fallback legacy.
  [`test_products.py:58`](../../tests/test_products.py#L58)

- Documenta contrato REST actualizado y limites operativos.
  [`README.md:120`](../../README.md#L120)

- Registra la iteracion implementada para trazabilidad del proyecto.
  [`.agents/changelog.md:80`](../../.agents/changelog.md#L80)
