---
title: '2.4 Generacion de PDF profesional configurable'
type: 'feature'
created: '2026-08-28'
status: 'done'
review_loop_iteration: 0
baseline_commit: '6587e786606508ccda37fc70416daa280d73c4dc'
context:
  - '{project-root}/_bmad-output/implementation-artifacts/epic-2-context.md'
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** La historia 2.4 está en backlog: hoy el presupuesto se puede descargar en PDF, pero falta consolidar el contrato profesional configurable exigido por la épica (control explícito de fotos por configuración global, membrete server-side consistente para PDF y cobertura de expiración en la ruta pública de descarga). El flujo actual depende de una plantilla pensada para vista web y de branding por JavaScript, lo que no garantiza salida PDF consistente.

**Approach:** Implementar un flujo de renderizado PDF dedicado y server-side, reutilizando la configuración global (`show_product_photos_in_pdf`, logo, título, subtítulo), aplicando validación de expiración coherente en endpoints API/web de PDF, y añadiendo pruebas de contrato para 200/404/410 y para visibilidad de fotos según configuración.

## Boundaries & Constraints

**Always:** Mantener arquitectura asíncrona y Clean Architecture; tratar la generación PDF como operación de solo lectura; preservar compatibilidad con historias 2.1/2.2/2.3 (método de pago activo, expiración por UUID, montos congelados); mantener respuestas y errores HTTP explícitos (404 inexistente, 410 expirado); documentación y pruebas en español.

**Ask First:** Si durante implementación aparece necesidad de cambiar el contrato de datos del presupuesto para persistir snapshots de fotos por ítem (en lugar de resolverlas desde catálogo al render); si se requiere introducir nuevas dependencias para maquetación PDF.

**Never:** No recalcular montos de cotización; no alterar reglas de creación de presupuesto; no introducir autenticación/pasarela de pago; no depender de JavaScript cliente para contenido crítico del PDF; no modificar historias fuera de 2.4 excepto ajustes mínimos acoplados.

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| PDF API activo | `GET /api/v1/budgets/{uuid}/pdf` con presupuesto existente y vigente | Responde `200`, `Content-Type: application/pdf`, y documento incluye membrete y totales | N/A |
| UUID inexistente | `GET /api/v1/budgets/{uuid}/pdf` con UUID no registrado | No genera PDF | `404` con mensaje de recurso no encontrado |
| Presupuesto expirado | `GET /api/v1/budgets/{uuid}/pdf` o `/presupuesto/{uuid}/pdf` con `is_expired=true` | Bloquea entrega del PDF | `410` consistente con política de expiración |
| Fotos deshabilitadas | Config global `show_product_photos_in_pdf=false` | El HTML/PDF omite fotos de producto y mantiene legibilidad de tabla | N/A |
| Fotos habilitadas | Config global `show_product_photos_in_pdf=true` y producto con imagen | El HTML/PDF muestra foto por línea cuando exista recurso válido | Si falta archivo, no romper generación; mostrar layout sin imagen en esa línea |

</frozen-after-approval>

## Code Map

- `app/api/v1/budgets.py` -- agregar endpoint `GET /api/v1/budgets/{uuid}/pdf` y normalizar errores 404/410 para descarga PDF desde API.
- `app/application/use_cases/budget_use_cases.py` -- ampliar orquestación de PDF para aceptar opciones de render (branding, flag de fotos, base_url) sin tocar cálculo monetario.
- `app/infrastructure/repositories/config_repo.py` -- reutilizar `get_effective_global_config()` como fuente de `show_product_photos_in_pdf`, logo, título y subtítulo.
- `app/infrastructure/services/pdf_service.py` -- permitir `base_url` en WeasyPrint para resolver assets locales (CSS e imágenes) de forma estable.
- `web/views.py` -- alinear `/presupuesto/{uuid}/pdf` con validación de expiración y reutilizar mismo contexto de render PDF que API.
- `web/templates/public/budget_view.html` -- separar bloques web/PDF y condicionar columna de fotos por `show_product_photos_in_pdf`; imprimir membrete server-side.
- `web/static/styles.css` -- agregar reglas de impresión (`@page`, `@media print`) para preservar legibilidad y repetición de cabecera/membrete.
- `tests/test_budgets.py` -- extender cobertura con pruebas de descarga PDF (API y web), expiración 410 y visibilidad de fotos habilitada/deshabilitada.
- `_bmad-output/implementation-artifacts/spec-2-3-calculo-inmutable-de-montos-de-cotizacion.md` -- continuidad: mantener invariantes de montos inmutables y evitar cambios fuera del alcance.

## Tasks & Acceptance

**Execution:**
- [x] `app/api/v1/budgets.py` -- crear endpoint `GET /api/v1/budgets/{uuid}/pdf` que valide existencia/expiración y retorne bytes PDF con `application/pdf` -- habilita contrato API de historia 2.4.
- [x] `web/views.py` -- aplicar la misma validación de expiración en `/presupuesto/{uuid}/pdf` y factorizar construcción de contexto PDF reutilizable -- elimina bypass de recursos expirados y evita divergencia entre API/web.
- [x] `app/application/use_cases/budget_use_cases.py` + `app/infrastructure/services/pdf_service.py` -- soportar render PDF con contexto server-side (branding, flag de fotos, base_url) sin tocar montos -- asegura PDF profesional configurable.
- [x] `web/templates/public/budget_view.html` + `web/static/styles.css` -- implementar presentación PDF con membrete repetible y control visual de fotos por configuración global -- garantiza legibilidad y personalización.
- [x] `tests/test_budgets.py` -- agregar pruebas para matriz I/O: PDF API 200/404/410, PDF web expirado 410, y foto visible/oculta según `show_product_photos_in_pdf` -- cierra cobertura funcional.
- [x] `README.md` + `.agents/changelog.md` -- documentar endpoint PDF API, comportamiento 410 y control de fotos en PDF; registrar iteración -- mantiene trazabilidad del cambio.

**Acceptance Criteria:**
- Given un presupuesto vigente, when se solicita `GET /api/v1/budgets/{uuid}/pdf`, then responde 200 con PDF válido y contenido de cotización completo.
- Given un presupuesto expirado, when se solicita PDF por API o ruta pública web, then la respuesta es HTTP 410 sin entregar archivo.
- Given `show_product_photos_in_pdf=false`, when se genera el PDF, then no se renderizan fotos de productos y el layout permanece legible.
- Given `show_product_photos_in_pdf=true` y productos con imágenes, when se genera el PDF, then se muestran las fotos disponibles en el documento.
- Given la personalización de branding configurada, when se genera el PDF, then el membrete (logo, título y subtítulo) se renderiza en servidor de forma consistente.

## Spec Change Log

## Design Notes

El HTML para PDF debe desacoplarse de dependencias cliente (scripts de `base.html`) porque WeasyPrint no ejecuta JavaScript. Por eso el contexto del render debe inyectar branding y flags desde backend.

La estrategia de resiliencia visual para fotos debe ser “best effort”: cuando falte imagen física o URL resoluble, se omite solo esa miniatura y continúa el documento; el objetivo es no fallar la cotización completa por un asset no crítico.

## Verification

**Commands:**
- `uv run python -m pytest tests/test_budgets.py -q` -- expected: pasan pruebas existentes y nuevas de PDF configurable.
- `uv run python -m pytest -q` -- expected: sin regresiones en el resto del sistema.

## Suggested Review Order

**Entrada de contrato PDF**

- Nuevo endpoint API concentra descarga PDF con validación unificada.
  [`budgets.py:62`](../../app/api/v1/budgets.py#L62)

- Reutiliza guardia de presupuesto activo para 404/410 consistentes.
  [`budgets.py:85`](../../app/api/v1/budgets.py#L85)

**Orquestación server-side configurable**

- Contexto de render inyecta branding y flags sin depender de JavaScript.
  [`budget_use_cases.py:116`](../../app/application/use_cases/budget_use_cases.py#L116)

- Resolución de imágenes normaliza nombres y evita rutas inválidas.
  [`budget_use_cases.py:194`](../../app/application/use_cases/budget_use_cases.py#L194)

- Servicio PDF ahora recibe base_url para assets locales estables.
  [`pdf_service.py:11`](../../app/infrastructure/services/pdf_service.py#L11)

**Superficies web y plantilla**

- Vista pública y descarga web aplican la misma regla de expiración.
  [`views.py:56`](../../web/views.py#L56)

- Plantilla limita columna de fotos al modo PDF configurable.
  [`budget_view.html:38`](../../web/templates/public/budget_view.html#L38)

**Cobertura y trazabilidad**

- Pruebas cubren PDF API/web, expiración y visibilidad de fotos.
  [`test_budgets.py:299`](../../tests/test_budgets.py#L299)

- README documenta endpoints PDF, 410 y bandera de fotos.
  [`README.md:183`](../../README.md#L183)

- Changelog registra la iteración de la historia 2.4.
  [`.agents/changelog.md:7`](../../.agents/changelog.md#L7)
