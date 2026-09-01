---
title: 'Historia 1.4 - Importación masiva por Excel con upsert'
type: 'feature'
created: '2026-08-26'
baseline_commit: 'e86d00a'
status: 'done'
review_loop_iteration: 0
context:
  - '{project-root}/AGENTS.md'
  - '{project-root}/_bmad-output/implementation-artifacts/epic-1-context.md'
  - '{project-root}/_bmad-output/implementation-artifacts/spec-1-3-catalogo-de-productos-con-imagenes-y-tags.md'
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** El endpoint de importación Excel (`POST /api/v1/products/import`) ya ejecuta upsert por SKU, pero no soporta la columna `tags` introducida en la historia 1.3. Los administradores necesitan importar/actualizar grandes volúmenes de productos con tags normalizados desde un archivo `.xlsx`.

**Approach:** Ampliar `ExcelService.parse_products()` para reconocer la columna opcional `tags` (separados por coma), normalizar tags (lowercase, trim, dedup, max 15) antes de persistir, y agregar tests end-to-end del flujo completo de importación incluyendo upsert con tags.

## Boundaries & Constraints

**Always:** Mantener lógica de upsert por SKU existente sin regresión; normalizar tags con las mismas reglas de la historia 1.3 (`_normalize_tags`); respetar el límite de 15 tags por producto; no cargar imágenes por Excel; devolver resumen con conteo de creados/actualizados.

**Ask First:** Cambiar la estructura del resumen de respuesta de la importación; agregar columnas obligatorias al Excel; requerir encabezado exacto de capitalización.

**Never:** Importar imágenes por Excel en esta historia; romper compatibilidad del parser con archivos Excel que no tienen columna `tags`; ignorar productos con SKU vacío o nulo; silenciar errores de parseo sin contabilizarlos.

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| IMPORT_NEW_PRODUCTS | Excel con 3 productos nuevos y columna `tags` | 3 creados, 0 actualizados, tags normalizados persistidos | N/A |
| IMPORT_UPSERT_EXISTING | Excel con SKU existente y datos modificados | 0 creados, 1 actualizado, tags reescritos | N/A |
| IMPORT_TAGS_NORMALIZED | Columna tags con `"Metal, INDUSTRIAL, metal "` | Tags persistidos como `["metal", "industrial"]` (dedup + trim + lower) | N/A |
| IMPORT_NO_TAGS_COLUMN | Excel sin columna `tags` | Importación normal sin modificar tags de productos existentes | N/A |
| IMPORT_EXCEEDS_TAG_LIMIT | Fila con 16+ tags separados por coma | Tags truncados a los primeros 15 válidos (sin error) | N/A |
| IMPORT_EMPTY_FILE | Excel sin filas de datos | `{"created": 0, "updated": 0, "total": 0}` | N/A |
| IMPORT_MISSING_COLUMNS | Excel sin columna obligatoria `sku` | Operación rechazada | HTTP 422 con detalle de columnas faltantes |
| IMPORT_INVALID_FORMAT | Archivo no .xlsx | Operación rechazada | HTTP 400 con detalle de formato inválido |

</frozen-after-approval>

## Code Map

- `app/infrastructure/services/excel_service.py` -- parser de Excel; `OPTIONAL_COLUMNS` (L10), `parse_products` (L28). Agregar `"tags"` a `OPTIONAL_COLUMNS` y parsear columna tags separada por comas.
- `app/application/use_cases/product_use_cases.py` -- `bulk_import_from_excel` (L199). Aplicar `_normalize_tags` a los datos parseados antes del upsert.
- `app/api/v1/products.py` -- endpoint `POST /api/v1/products/import` (L114). Validar content-type/extensión.
- `app/infrastructure/repositories/product_repo.py` -- `upsert_by_sku` (L48). Sin cambios esperados.
- `tests/test_products.py` -- agregar tests de importación con tags, upsert, sin columna tags, límite excedido.
- `README.md` -- documentar columna `tags` en flujo de importación.

## Tasks & Acceptance

**Execution:**
- [x] `app/infrastructure/services/excel_service.py` -- agregar `"tags"` a `OPTIONAL_COLUMNS`; detectar índice de columna `tags` en headers; parsear valor como split por coma con trim; incluir campo `tags` en el dict de producto retornado -- habilita extracción de tags desde Excel.
- [x] `app/application/use_cases/product_use_cases.py` -- en `bulk_import_from_excel`, aplicar `_normalize_tags` a `data.get("tags")` antes del upsert; truncar a 15 tags sin error -- normaliza y limita tags importados.
- [x] `tests/test_products.py` -- tests: importación con tags normalizados, upsert que reescribe tags, Excel sin columna tags no rompe, Excel con 16+ tags trunca a 15 -- cubre matriz I/O.
- [x] `README.md` -- documentar columna opcional `tags` en especificación del Excel de importación -- alinea consumidores.

**Acceptance Criteria:**
- Given un archivo Excel con columna `tags` conteniendo `"Metal, INDUSTRIAL, metal "`, when importo, then el producto tiene `tags: ["metal", "industrial"]`.
- Given un archivo Excel con SKU existente y tags nuevos, when importo, then los tags del producto se reescriben con los nuevos valores normalizados.
- Given un archivo Excel sin columna `tags`, when importo, then la importación completa sin error y no modifica tags existentes.
- Given una fila con 16+ tags, when importo, then solo se persisten los primeros 15 tags válidos.

## Spec Change Log

## Verification

**Commands:**
- `pytest tests/test_products.py -q -k "import"` -- expected: tests de importación pasan.
- `pytest -q` -- expected: sin regresiones.

## Suggested Review Order

- Parseo de columna `tags` separada por comas en el Excel.
  [`excel_service.py:44`](../../app/infrastructure/services/excel_service.py#L44)

- Normalización y truncado a 15 tags antes del upsert.
  [`product_use_cases.py:209`](../../app/application/use_cases/product_use_cases.py#L209)

- Tests de importación: normalización, upsert, sin columna, exceso.
  [`test_products.py:352`](../../tests/test_products.py#L352)

- Documentación de columna opcional `tags` en el formato Excel.
  [`README.md:249`](../../README.md#L249)
