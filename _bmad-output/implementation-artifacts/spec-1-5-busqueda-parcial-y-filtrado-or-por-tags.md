---
title: 'Historia 1.5 - Búsqueda parcial y filtrado OR por tags'
type: 'feature'
created: '2026-08-26'
baseline_commit: 'eb81a05'
status: 'done'
review_loop_iteration: 0
context:
  - '{project-root}/AGENTS.md'
  - '{project-root}/_bmad-output/implementation-artifacts/epic-1-context.md'
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** La búsqueda actual usa `$text` de MongoDB que solo encuentra palabras completas. Los administradores necesitan buscar por subcadenas parciales (ej. "cem" → "Cemento") en nombre, SKU y tags, y filtrar por múltiples tags con lógica OR para seleccionar productos rápidamente durante la cotización.

**Approach:** Reemplazar `$text` por `$regex` case-insensitive aplicado a `name`, `sku` y `tags` (OR entre campos) para el parámetro `q`. Agregar parámetro `tags` (lista) que filtre productos que tengan al menos uno de los tags indicados (OR). Ambos filtros se combinan con AND.

## Boundaries & Constraints

**Always:** Mantener paginación y ordenamiento existentes; respetar filtros acumulativos (precio, categoría); usar `$regex` con opción `i` para case-insensitive; buscar subcadenas de 1+ caracteres; combinar `q` y `tags` con AND; tags en filtro se comparan normalizados (lowercase).

**Ask First:** Introducir búsqueda full-text con scoring; cambiar a un motor de búsqueda externo (Elasticsearch); agregar índices compuestos en MongoDB.

**Never:** Romper la búsqueda por categoría/precio existente; aceptar regex arbitrario del usuario (escapar metacaracteres); degradar rendimiento en catálogos <10k productos.

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| PARTIAL_NAME | `q=cem` | Productos cuyo nombre contiene "cem" (case-insensitive) | N/A |
| PARTIAL_SKU | `q=CEM-0` | Productos cuyo SKU contiene "CEM-0" | N/A |
| PARTIAL_TAG | `q=indust` | Productos con tag que contiene "indust" | N/A |
| TAGS_FILTER_OR | `tags=metal&tags=madera` | Productos con tag "metal" O "madera" | N/A |
| COMBINED_Q_AND_TAGS | `q=tornillo&tags=metal` | Productos que contienen "tornillo" en nombre/sku/tags Y tienen tag "metal" | N/A |
| EMPTY_RESULTS | `q=xyznoexiste` | Lista vacía, total=0 | N/A |
| REGEX_METACHAR | `q=c++` | Metacaracteres escapados, búsqueda literal | N/A |
| NO_FILTERS | Sin `q` ni `tags` | Retorna todos los productos paginados | N/A |

</frozen-after-approval>

## Code Map

- `app/domain/schemas/search.py` -- `ProductSearchParams` (L18). Agregar campo `tags: list[str] | None = None`.
- `app/infrastructure/repositories/product_repo.py` -- método `search` (L82). Reemplazar `$text` por `$regex` multi-campo; agregar filtro `$in` sobre `tags`.
- `app/api/v1/products.py` -- endpoint `GET /products/search` (L12). Recibir `tags` como Query param lista.
- `tests/test_search.py` -- ampliar con tests de búsqueda parcial por subcadena, filtrado OR por tags, combinación, y metacaracteres.
- `README.md` -- documentar parámetros de búsqueda `q` (parcial) y `tags` (OR).

## Tasks & Acceptance

**Execution:**
- [x] `app/domain/schemas/search.py` -- agregar `tags: list[str] | None = Query(default=None)` a `ProductSearchParams` -- habilita filtro por tags en query params.
- [x] `app/infrastructure/repositories/product_repo.py` -- reemplazar `$text` por `$or` con `$regex` sobre `name`, `sku`, `tags` (case-insensitive, metacaracteres escapados); agregar filtro `{"tags": {"$in": [...]}}` cuando `params.tags` presente -- implementa búsqueda parcial y filtro OR.
- [x] `app/api/v1/products.py` -- asegurar que el endpoint de búsqueda pase `tags` desde query params a `ProductSearchParams` -- expone superficie API.
- [x] `tests/test_search.py` -- tests: parcial en nombre, parcial en SKU, parcial en tag, filtro OR por tags, combinación q+tags, metacaracteres escapados -- cubre matriz I/O.
- [ ] `README.md` -- documentar parámetros `q` (parcial multi-campo) y `tags` (filtro OR) -- alinea consumidores.

**Acceptance Criteria:**
- Given productos con nombres "Cemento Portland" y "Arena Fina", when busco `q=cem`, then solo aparece "Cemento Portland".
- Given productos con tags `["metal", "industrial"]` y `["madera"]`, when filtro `tags=metal&tags=madera`, then aparecen ambos productos.
- Given un producto con tag "industrial", when busco `q=indust`, then el producto aparece en resultados.
- Given `q=c++`, when busco, then no hay error de regex y se busca literalmente "c++".

## Spec Change Log

## Verification

**Commands:**
- `pytest tests/test_search.py -q` -- expected: todos los tests de búsqueda pasan.
- `pytest -q` -- expected: sin regresiones.

## Suggested Review Order

- Lógica central: `$regex` multi-campo reemplaza `$text`, filtro `$in` por tags.
  [`product_repo.py:84`](../../app/infrastructure/repositories/product_repo.py#L84)

- Nuevo campo `tags` en el schema de búsqueda.
  [`search.py:23`](../../app/domain/schemas/search.py#L23)

- Endpoint pasa `tags` query param al schema.
  [`products.py:19`](../../app/api/v1/products.py#L19)

- Tests: parcial nombre/SKU/tag, filtro OR, combinación, metacaracteres.
  [`test_search.py:50`](../../tests/test_search.py#L50)

- Documentación de parámetros de búsqueda actualizados.
  [`README.md:131`](../../README.md#L131)
