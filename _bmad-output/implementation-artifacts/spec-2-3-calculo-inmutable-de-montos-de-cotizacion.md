---
title: '2.3 Calculo inmutable de montos de cotizacion'
type: 'feature'
created: '2026-08-28'
status: 'done'
review_loop_iteration: 0
baseline_commit: 'f650d85f41cecc2473b77f13551b98646c3f52bc'
context:
  - '{project-root}/_bmad-output/implementation-artifacts/epic-2-context.md'
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** La historia 2.3 exige que subtotal, impuesto y total queden congelados al crear la cotización para que cambios posteriores en configuración o catálogo no alteren presupuestos emitidos. Hoy ya existe cálculo en creación, pero falta cerrar explícitamente la inmutabilidad frente a cambios de precio de producto y dejarlo cubierto por pruebas.

**Approach:** Mantener el cálculo solo en `create_budget`, persistir los montos como snapshot en `Budget`, evitar cualquier recálculo en lecturas y reforzar el contrato con pruebas de no regresión que validen que un presupuesto existente no cambia aunque se modifique el costo del producto después.

## Boundaries & Constraints

**Always:** Mantener Clean Architecture y asincronía actual; reutilizar `BudgetUseCases.create_budget` y el modelo/schemas existentes; preservar compatibilidad con historias 2.1 y 2.2 (método de pago activo, expiración por `expires_at`); mantener docstrings, mensajes y pruebas en español.

**Ask First:** Si aparece necesidad de cambiar reglas de redondeo (por línea vs total), tipo numérico (`float` a `Decimal`) o contrato API público de montos.

**Never:** No recalcular montos en `GET /api/v1/budgets` ni en vistas/PDF/WhatsApp; no agregar endpoints para editar montos de presupuestos emitidos; no alterar alcance con autenticación, pagos reales o refactors amplios fuera de historia 2.3.

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| Creación de cotización | Payload válido con items, precios y `tax_rate` vigente | Se persisten `items[].unit_cost`, `items[].line_total`, `subtotal`, `tax_percent`, `tax_amount`, `total` en el `Budget` creado | 422 si SKU no existe o método de pago no está disponible |
| Cambio posterior de configuración | Presupuesto A creado con `tax_rate=10`; luego `tax_rate` cambia a 20 | Presupuesto A mantiene sus montos originales al consultarlo; presupuestos nuevos usan la nueva configuración | N/A |
| Cambio posterior de costo de producto | Presupuesto A creado con `product.cost=100`; luego producto cambia a 150 | Presupuesto A mantiene `unit_cost`, `line_total`, `subtotal`, `tax_amount` y `total` originales | N/A |

</frozen-after-approval>

## Code Map

- `app/application/use_cases/budget_use_cases.py` -- `BudgetUseCases.create_budget` (L30) concentra cálculo y snapshot de montos; `is_expired` (L101) pertenece a 2.2 y no debe alterarse.
- `app/domain/models/budget.py` -- `Budget` (L32) persiste `subtotal`, `tax_percent`, `tax_amount`, `total` y `items[].line_total` como estado histórico.
- `app/domain/schemas/budget.py` -- `BudgetResponse` (L20) expone montos persistidos sin recálculo.
- `app/api/v1/budgets.py` -- `list_budgets` (L11), `create_budget` (L26), `get_budget` (L44) devuelven valores persistidos; no introducir recomputación en capa API.
- `app/infrastructure/repositories/budget_repo.py` -- `create` (L25) inserta snapshot; `update` (L31) existe como mutación genérica y se mantiene fuera de alcance mientras no haya endpoint de edición de montos.
- `tests/test_budgets.py` -- `test_new_budget_uses_updated_tax_and_ttl` (L30) y `test_existing_budget_not_recalculated_after_config_change` (L50) ya cubren configuración; extender con caso de inmutabilidad ante cambio de costo de producto.
- `C:\Users\JesusRojas\Documents\pyfiles\budget_maker\_bmad-output\implementation-artifacts\spec-2-2-identificacion-publica-y-expiracion-del-presupuesto.md` -- continuidad: preservar enfoque de compatibilidad backward y pruebas de contrato público ya aprobadas en revisión.

## Tasks & Acceptance

**Execution:**
- [x] `tests/test_budgets.py` -- agregar prueba que cree presupuesto, cambie `Product.cost` vía API y verifique que el presupuesto original conserva `unit_cost`, `line_total`, `subtotal`, `tax_amount` y `total` -- garantiza inmutabilidad frente a cambios de catálogo.
- [x] `app/application/use_cases/budget_use_cases.py` -- confirmar/ajustar cálculo de montos para que siempre se congele en creación y nunca dependa de lecturas posteriores del catálogo/configuración -- fija el contrato de snapshot.
- [x] `app/api/v1/budgets.py` -- mantener respuesta basada en campos persistidos sin recálculo y sin alterar comportamiento de expiración 2.2 -- evita regresiones cruzadas.

**Acceptance Criteria:**
- Given un presupuesto creado con costo unitario y tasa de impuesto vigentes, when se persiste, then `unit_cost`, `line_total`, `subtotal`, `tax_percent`, `tax_amount` y `total` quedan guardados en el documento `Budget`.
- Given un presupuesto ya emitido, when cambia la configuración global de impuestos, then al consultar ese presupuesto conserva sus montos originales.
- Given un presupuesto ya emitido, when cambia el costo del producto en el catálogo, then al consultar ese presupuesto conserva sus montos originales de líneas y totales.
- Given una consulta de presupuesto por UUID, when se obtiene la respuesta, then la API devuelve montos persistidos sin recalcular contra catálogo ni configuración actual.

## Spec Change Log

## Verification

**Commands:**
- `pytest tests/test_budgets.py -q` -- expected: pasan pruebas existentes y nueva cobertura de inmutabilidad.
- `pytest -q` -- expected: no hay regresiones en suites relacionadas.

## Suggested Review Order

**Punto de congelamiento de montos**

- El snapshot inmutable se fija al crear presupuesto, no al consultarlo.
  [`budget_use_cases.py:30`](../../app/application/use_cases/budget_use_cases.py#L30)

**Contrato de lectura sin recálculo**

- La consulta por UUID responde montos persistidos y respeta expiración existente.
  [`budgets.py:44`](../../app/api/v1/budgets.py#L44)

**Cobertura de regresión**

- Prueba principal: cambio de costo posterior no altera presupuesto ya emitido.
  [`test_budgets.py:91`](../../tests/test_budgets.py#L91)

- Prueba de error: SKU inexistente mantiene contrato HTTP 422.
  [`test_budgets.py:169`](../../tests/test_budgets.py#L169)

## Suggested Review Order

**Punto de entrada del cálculo**

- Aquí se congela el snapshot económico al crear la cotización.
  [`budget_use_cases.py:30`](../../app/application/use_cases/budget_use_cases.py#L30)

- Se homologa el borde de expiración legacy con el flujo moderno.
  [`budget_use_cases.py:111`](../../app/application/use_cases/budget_use_cases.py#L111)

**Cobertura de inmutabilidad**

- Prueba principal: cambios de precio no alteran cotizaciones ya emitidas.
  [`test_budgets.py:93`](../../tests/test_budgets.py#L93)

- Se asegura contrato 422 para SKU inexistente en creación.
  [`test_budgets.py:169`](../../tests/test_budgets.py#L169)

**Soporte y trazabilidad**

- Documenta comportamiento 410 y montos congelados para consumidores API.
  [`README.md:182`](../../README.md#L182)

- Registra la iteración y alcance exacto de la historia 2.3.
  [`.agents/changelog.md:7`](../../.agents/changelog.md#L7)
