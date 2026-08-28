---
title: '2.2 Identificacion publica y expiracion del presupuesto'
type: 'feature'
created: '2026-08-28'
baseline_commit: '5ccb7065300d22fab84435573f26de4f9d62f1b3'
status: 'done'
review_loop_iteration: 0
context:
  - '{project-root}/_bmad-output/implementation-artifacts/epic-2-context.md'
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** Falta la spec formal de la historia 2.2 y el contrato de identificación pública/expiración no está completamente endurecido: hoy se generan `code` y `uuid`, pero no existe garantía de unicidad a nivel de base de datos ni validación explícita de UUID4 en rutas públicas/API.

**Approach:** Formalizar e implementar el contrato completo de 2.2 reforzando tres capas: persistencia (unicidad de `code` y `uuid`), transporte (UUID tipado/validado en endpoints), y pruebas de expiración/errores para asegurar comportamiento consistente y seguro en accesos públicos.

## Boundaries & Constraints

**Always:** Mantener arquitectura asíncrona y separación por capas; preservar formato de código `BM-YYYYMMDD-XXXX`; conservar política de expiración existente (presupuesto inexistente -> 404, expirado -> 410 en rutas que entregan el recurso); mantener compatibilidad con historias 2.1, 2.3, 2.4 y 2.5.

**Ask First:** Cambiar el comportamiento de `/presupuesto/{uuid}` expirado desde vista informativa a `HTTP 410` hard-fail; alterar el formato legible del código comercial; introducir migraciones destructivas sobre documentos existentes.

**Never:** No recalcular montos ni tocar reglas de impuestos; no introducir autenticación nueva; no romper URLs públicas ya emitidas; no relajar validaciones de expiración.

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| UUID_PUBLICO_VALIDO | GET de presupuesto por UUID4 vigente | Recupera presupuesto y/o recurso asociado según endpoint | N/A |
| UUID_MALFORMADO | UUID no válido (no UUID4) en ruta API/web | Rechaza request antes de acceder a repositorio | HTTP 422 |
| EXPIRADO | UUID4 existente con `expires_at` vencido | Bloquea entrega del recurso protegido | HTTP 410 |
| INEXISTENTE | UUID4 bien formado sin presupuesto asociado | No expone datos | HTTP 404 |
| COLISION_IDENTIFICADOR | Inserción/creación con `code` o `uuid` ya existentes | Evita persistencia duplicada | Error explícito de dominio/API |

</frozen-after-approval>

## Code Map

- `app/domain/models/budget.py` -- `Budget` define `code`, `uuid`, `link_ttl_minutes`, `expires_at`; agregar índices/constraints de unicidad para contrato público.
- `app/domain/schemas/budget.py` -- contratos de entrada/salida para presupuesto; evaluar tipado UUID en respuesta si corresponde.
- `app/application/use_cases/budget_use_cases.py` -- `create_budget`, `_generate_code`, `is_expired`; reforzar generación segura y manejo de colisiones.
- `app/infrastructure/repositories/budget_repo.py` -- punto de persistencia de presupuestos; superficie para propagar errores de duplicado sin silencios.
- `app/api/v1/budgets.py` -- endpoints `/{uuid}`, `/{uuid}/pdf`, `/{uuid}/whatsapp-share`; aplicar validación de UUID por tipado de ruta y conservar contrato 404/410.
- `web/views.py` -- rutas `/presupuesto/{uuid}` y `/presupuesto/{uuid}/pdf`; alinear validación de UUID y comportamiento de expiración esperado.
- `tests/test_budgets.py` -- casos de UUID inválido, expiración y robustez de identificadores públicos.
- `README.md` -- documentar validación UUID y garantía de unicidad/expiración.

## Tasks & Acceptance

**Execution:**
- [x] `app/domain/models/budget.py` -- definir índices únicos para `code` y `uuid` en la colección `budgets` -- garantiza no duplicar identificadores públicos.
- [x] `app/api/v1/budgets.py` + `web/views.py` -- tipar `uuid` en rutas con `UUID` y convertir a `str` al delegar a casos de uso -- fuerza validación HTTP 422 para UUID inválido.
- [x] `app/application/use_cases/budget_use_cases.py` + `app/infrastructure/repositories/budget_repo.py` -- manejar colisiones de identificadores con error explícito y reintento acotado de generación de `code` cuando aplique -- evita fallas silenciosas y fortalece contrato de unicidad.
- [x] `tests/test_budgets.py` -- agregar pruebas para UUID malformado (422), expiración (410), inexistente (404) y rechazo ante identificadores duplicados -- cubre matriz I/O y regresión.
- [x] `README.md` + `.agents/changelog.md` -- actualizar documentación funcional y bitácora con reglas de UUID/expiración/unicidad -- mantiene trazabilidad del cambio.

**Acceptance Criteria:**
- Given una creación de presupuesto, when se persiste el documento, then `code` y `uuid` quedan sujetos a unicidad en base de datos.
- Given un UUID inválido, when se consulta cualquier endpoint público de presupuesto, then la API responde HTTP 422 sin ejecutar lógica de repositorio.
- Given un presupuesto expirado, when se consulta recurso protegido por UUID, then se devuelve HTTP 410 de forma consistente.
- Given un UUID válido inexistente, when se consulta presupuesto por API o descarga PDF, then se devuelve HTTP 404.
- Given una colisión de identificador público, when se intenta crear presupuesto, then la operación falla de forma explícita sin crear duplicados.

## Spec Change Log

## Design Notes

El contrato público depende de identificadores estables y no ambiguos. La validación de UUID en frontera HTTP reduce carga innecesaria y evita consultas inválidas al repositorio.

La unicidad real debe estar en base de datos, no solo en probabilidad estadística del generador. Un reintento acotado para `code` ayuda a absorber colisiones raras sin ocultar errores estructurales.

## Verification

**Commands:**
- `uv run python -m pytest tests/test_budgets.py -q` -- expected: pasan pruebas existentes + nuevos casos de UUID/expiración/unicidad.

## Suggested Review Order

**Persistencia y contrato de unicidad**

- Define error de dominio e índices únicos para blindar identificadores públicos.
  [`budget.py:33`](../../app/domain/models/budget.py#L33)

- Traduce colisiones de Mongo a error semántico consumible por aplicación.
  [`budget_repo.py:31`](../../app/infrastructure/repositories/budget_repo.py#L31)

- Implementa reintentos acotados para `code` y fail-fast para `uuid`.
  [`budget_use_cases.py:86`](../../app/application/use_cases/budget_use_cases.py#L86)

**Frontera HTTP y validación UUID4**

- Aplica validación tipada de ruta y mapea colisiones a HTTP 409.
  [`budgets.py:42`](../../app/api/v1/budgets.py#L42)

- Alinea vistas públicas con UUID4 para rechazar entradas inválidas.
  [`views.py:36`](../../web/views.py#L36)

- Asegura consistencia de contrato de salida con UUID4 tipado.
  [`budget.py:23`](../../app/domain/schemas/budget.py#L23)

**Cobertura de regresión y documentación**

- Verifica fail-fast 422, 404 inexistente y colisiones con/ sin reintento.
  [`test_budgets.py:263`](../../tests/test_budgets.py#L263)

- Documenta contrato actualizado de UUID4, unicidad y expiración.
  [`README.md:182`](../../README.md#L182)

- Registra trazabilidad de la iteración implementada.
  [`changelog.md:7`](../../.agents/changelog.md#L7)
