---
title: '2.5 Enlace de WhatsApp para compartir cotizacion'
type: 'feature'
created: '2026-08-28'
status: 'done'
review_loop_iteration: 0
baseline_commit: 'b30a12393d63a6facbe6f5482f5a30bb0ae572c5'
context:
  - '{project-root}/_bmad-output/implementation-artifacts/epic-2-context.md'
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** La historia 2.5 requiere un enlace de WhatsApp consistente con formato `https://wa.me/?text={url_encoded_text}` que incluya empresa, código de cotización, total y link temporal. Hoy existen dos flujos distintos (backend y frontend) con formato divergente: uno no incluye link temporal y otro no incluye empresa dinámica.

**Approach:** Unificar la construcción del mensaje de WhatsApp en backend para que web pública y flujo de catálogo usen el mismo formato canónico, tomando `site_title` desde configuración global, manteniendo código/total del presupuesto congelado y añadiendo el enlace temporal público de la cotización en el texto codificado.

## Boundaries & Constraints

**Always:** Preservar compatibilidad con historias 2.1/2.2/2.3/2.4; mantener `wa.me` con encoding URL correcto UTF-8; usar `site_title` desde configuración con fallback razonable; incluir exactamente empresa, código, total y link temporal en el texto; mantener arquitectura asíncrona y separación de capas.

**Ask First:** Si para unificar el flujo hace falta cambiar el contrato público de la API de presupuestos (por ejemplo, exponer `whatsapp_url` en `BudgetResponse`) o alterar de forma visible el copy comercial más allá de los campos obligatorios.

**Never:** No recalcular montos; no cambiar la lógica de expiración; no introducir librerías nuevas para encoding; no mantener dos formatos paralelos backend/frontend para el mismo mensaje.

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| Enlace válido mínimo | Presupuesto vigente con `site_title` configurado | Se retorna URL `https://wa.me/?text=...` con empresa, código, total y link temporal | N/A |
| Fallback de empresa | `site_title` vacío/no definido | Mensaje usa nombre por defecto del sistema y conserva demás campos | N/A |
| Caracteres especiales | Texto con acentos/ñ/espacios/saltos de línea | URL queda correctamente percent-encoded y navegable por WhatsApp | N/A |
| Flujo unificado web | Vista pública y modal de catálogo para mismo presupuesto | Ambos muestran el mismo mensaje/formato canónico | Si no hay presupuesto válido, mantener errores existentes (404/410) |

</frozen-after-approval>

## Code Map

- `app/application/use_cases/budget_use_cases.py` -- `generate_whatsapp_text` (actual L144+) debe pasar a builder canónico con empresa dinámica y link temporal.
- `app/application/use_cases/budget_use_cases.py` -- `build_budget_render_context` ya lee `site_title`; reutilizable para evitar duplicar lectura de config.
- `web/views.py` -- `view_budget` construye `whatsapp_url`; debe usar el builder unificado con URL temporal explícita.
- `web/static/js/catalog.js` -- hoy arma mensaje propio en cliente; punto crítico para eliminar divergencia con backend.
- `web/templates/public/budget_view.html` -- consume `whatsapp_url`; validar que no rompe flujo web existente.
- `app/api/v1/budgets.py` -- evaluar si conviene exponer/centralizar helper de share sin alterar contratos no acordados.
- `tests/test_budgets.py` -- agregar cobertura de formato canónico y encoding (incluyendo caracteres internacionales y presencia de link temporal).
- `_bmad-output/implementation-artifacts/spec-2-4-generacion-de-pdf-profesional-configurable.md` -- continuidad: preservar estructura de render y comportamiento de rutas públicas.

## Tasks & Acceptance

**Execution:**
- [x] `app/application/use_cases/budget_use_cases.py` -- crear/ajustar builder canónico de mensaje WhatsApp que reciba presupuesto + URL temporal y produzca `wa.me` con empresa dinámica, código y total -- establece una sola fuente de verdad.
- [x] `web/views.py` -- construir URL temporal pública y delegar generación del texto al builder backend -- unifica salida de la vista de presupuesto.
- [x] `web/static/js/catalog.js` -- reemplazar armado manual del mensaje por uso del formato/backend canónico (o consumir payload ya construido) -- elimina divergencia entre flujos.
- [x] `web/templates/public/budget_view.html` -- mantener botón de WhatsApp usando el enlace unificado sin cambios de UX no requeridos -- conserva navegación actual.
- [x] `tests/test_budgets.py` -- cubrir matriz I/O: formato `wa.me`, presencia de empresa/código/total/link temporal, fallback de empresa y encoding de caracteres especiales -- evita regresiones funcionales.
- [x] `README.md` + `.agents/changelog.md` -- documentar formato del enlace WhatsApp y registrar iteración 2.5 -- mantiene trazabilidad.

**Acceptance Criteria:**
- Given un presupuesto vigente con configuración de empresa, when se genera el enlace de WhatsApp, then el resultado usa `https://wa.me/?text=` e incluye empresa, código, total y link temporal.
- Given un presupuesto vigente sin `site_title` definido, when se genera el enlace, then se usa fallback de empresa sin romper el enlace.
- Given datos con caracteres especiales, when se genera el enlace, then el texto queda correctamente URL-encoded.
- Given los flujos de vista pública y catálogo, when generan enlace para una misma cotización, then ambos producen el mismo formato canónico.

## Spec Change Log

## Design Notes

La principal decisión de diseño es evitar doble implementación del mismo mensaje (Python y JavaScript) porque eso ya causó drift funcional frente al AC. El formato debe ser único y derivado del backend, que conoce estado de negocio y branding.

El enlace temporal debe apuntar a la vista pública (`/presupuesto/{uuid}`), respetando expiración ya implementada. La historia 2.5 no modifica control de acceso ni vida útil; solo estandariza la composición del mensaje.

## Verification

**Commands:**
- `uv run python -m pytest tests/test_budgets.py -q` -- expected: pasan pruebas nuevas y existentes de presupuestos/compartición.
- `uv run python -m pytest -q` -- expected: sin regresiones en el sistema.

## Suggested Review Order

**Punto de entrada del enlace canónico**

- Endpoint dedicado centraliza contrato 404/410 y payload tipado.
  [`budgets.py:85`](../../app/api/v1/budgets.py#L85)

- Modelo de salida fija shape de respuesta para OpenAPI y clientes.
  [`budget.py:35`](../../app/domain/schemas/budget.py#L35)

**Generación de mensaje en backend**

- Builder canónico incorpora empresa, código, total y link temporal.
  [`budget_use_cases.py:146`](../../app/application/use_cases/budget_use_cases.py#L146)

- Sanitización garantiza fallback robusto para `site_title` vacío.
  [`budget_use_cases.py:198`](../../app/application/use_cases/budget_use_cases.py#L198)

**Integración en superficies web**

- Vista pública delega a builder unificado y evita divergencias.
  [`views.py:44`](../../web/views.py#L44)

- Catálogo consume endpoint backend y bloquea botón ante fallo.
  [`catalog.js:297`](../../web/static/js/catalog.js#L297)

**Cobertura y documentación**

- Pruebas cubren formato, fallback, encoding y errores 404/410.
  [`test_budgets.py:386`](../../tests/test_budgets.py#L386)

- README documenta endpoint y ejemplo de respuesta canónica.
  [`README.md:184`](../../README.md#L184)

- Changelog registra iteración y alcance de la historia 2.5.
  [`.agents/changelog.md:7`](../../.agents/changelog.md#L7)
