---
title: 'Historia 2.1 - Creación de presupuesto con datos de cliente y método activo'
type: 'feature'
created: '2026-08-26'
baseline_commit: 'f6ef5af'
status: 'done'
review_loop_iteration: 0
context:
  - '{project-root}/AGENTS.md'
  - '{project-root}/_bmad-output/implementation-artifacts/epic-2-context.md'
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** El presupuesto actual no captura el email del cliente ni el método de pago seleccionado. La historia 2.1 requiere que cada cotización persista datos completos del cliente (documento, dirección, email) y un método de pago que debe estar activo en la configuración global al momento de la creación.

**Approach:** Agregar `email` a `ClientInfo` y `payment_method: str` al modelo `Budget` y schemas. En `create_budget`, validar que el método de pago exista en `GlobalConfig.payment_methods` y rechazar con HTTP 422 si no está activo.

## Boundaries & Constraints

**Always:** Persistir el método de pago como string inmutable en el presupuesto (preservar histórico); validar método contra la lista activa en creación; mantener compatibilidad con presupuestos existentes sin método de pago (campo opcional con default None).

**Ask First:** Requerir email como campo obligatorio vs. opcional; agregar validación de formato de email; cambiar la estructura de `payment_methods` de `list[str]` a objetos con estado activo/inactivo.

**Never:** Modificar presupuestos existentes al cambiar métodos de pago; bloquear lectura de presupuestos con método ya no activo; validar método de pago en lectura/consulta (solo en creación).

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| CREATE_HAPPY | Datos completos + método activo | Presupuesto creado con email y payment_method persistidos | N/A |
| CREATE_INACTIVE_METHOD | Método que no está en `payment_methods` | Operación rechazada | HTTP 422 — método de pago no disponible |
| CREATE_NO_METHOD | Sin campo `payment_method` | Presupuesto creado sin método (compatibilidad) | N/A |
| CREATE_WITH_EMAIL | Client info con email válido | Email persistido en `client_info` | N/A |
| READ_LEGACY | Presupuesto existente sin `payment_method` | Respuesta incluye `payment_method: null` | N/A |
| METHOD_REMOVED_AFTER | Método activo al crear, luego eliminado | Presupuesto conserva el método original intacto | N/A |

</frozen-after-approval>

## Code Map

- `app/domain/models/budget.py` -- `ClientInfo` (L7), `Budget` (L18). Agregar `email` a ClientInfo y `payment_method` a Budget.
- `app/domain/schemas/budget.py` -- `BudgetCreate`, `BudgetResponse`. Agregar `payment_method` y asegurar `email` en ClientInfo.
- `app/application/use_cases/budget_use_cases.py` -- `create_budget`. Validar método de pago contra `GlobalConfig.payment_methods`.
- `app/api/v1/budgets.py` -- endpoint `POST /`. Capturar ValueError como HTTP 422.
- `app/domain/models/global_config.py` -- `payment_methods: list[str]`. Solo lectura, sin cambios.
- `tests/test_budgets.py` -- tests: creación con método activo, rechazo con método inactivo, compatibilidad sin método.
- `README.md` -- documentar campo `payment_method` y validación.

## Tasks & Acceptance

**Execution:**
- [x] `app/domain/models/budget.py` -- agregar `email: str = ""` a `ClientInfo` y `payment_method: str | None = None` a `Budget` -- habilita persistencia de datos de cliente y método de pago.
- [x] `app/domain/schemas/budget.py` -- agregar `payment_method: str | None = None` a `BudgetCreate` y `BudgetResponse`; asegurar que `ClientInfo` expone `email` -- define contrato API.
- [x] `app/application/use_cases/budget_use_cases.py` -- en `create_budget`, si `payment_method` presente, validar contra `config.payment_methods`; si no está en la lista, `raise ValueError`; persistir método en el presupuesto -- orquesta regla de negocio.
- [x] `app/api/v1/budgets.py` -- capturar `ValueError` del use case como HTTP 422 -- expone error de validación al cliente.
- [x] `tests/test_budgets.py` -- tests: crear con método activo, rechazar método inactivo (422), crear sin método (compatibilidad), email persistido -- cubre matriz I/O.
- [ ] `README.md` -- documentar `payment_method` en creación de presupuesto -- alinea consumidores.

**Acceptance Criteria:**
- Given un método "Transferencia" activo en config, when creo presupuesto con `payment_method: "Transferencia"`, then el presupuesto persiste el método y lo devuelve en la respuesta.
- Given un método "Bitcoin" que no está en `payment_methods`, when intento crear presupuesto con él, then la API responde HTTP 422.
- Given un presupuesto creado sin `payment_method`, when consulto el presupuesto, then `payment_method` es null.
- Given un presupuesto con email "cliente@email.com", when consulto el presupuesto, then `client_info.email` es "cliente@email.com".

## Spec Change Log

## Verification

**Commands:**
- `pytest tests/test_budgets.py -q` -- expected: todos los tests pasan.
- `pytest -q` -- expected: sin regresiones.
