---
title: 'Listado público de presupuestos'
type: 'bugfix'
created: '2026-09-22'
status: 'done'
review_loop_iteration: 0
baseline_commit: '74cfe6d429160d3e1e718ab6625aa389fa47d8e0'
context:
  - '{project-root}/_bmad-output/planning-artifacts/prds/prd-budget_maker-2026-08-25/prd.md'
  - '{project-root}/_bmad-output/planning-artifacts/architecture/architecture-budget_maker-2026-08-26/ARCHITECTURE-SPINE.md'
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** `GET /api/v1/budgets/` responde HTTP 401 cuando no se envía un token JWT, impidiendo que cualquier consumidor consulte el listado de presupuestos. El comportamiento contradice el requisito explícito de que este endpoint sea libre.

**Approach:** Eliminar únicamente la dependencia de autenticación del handler de listado y mantener intactos sus filtros, paginación y contrato de respuesta. Añadir cobertura que demuestre el acceso anónimo y que las operaciones administrativas restantes conservan su protección actual.

## Boundaries & Constraints

**Always:** Mantener `GET /api/v1/budgets/` disponible sin encabezado `Authorization`; preservar los parámetros `q`, `client_id`, `from`, `to`, `is_expired`, `page` y `limit`; conservar la respuesta `PaginatedResponse[BudgetAdminResponse]`; actualizar README y changelog en español.

**Ask First:** Cualquier cambio que amplíe el alcance público a `POST`, `PUT`, `DELETE`, `GET /{uuid}/admin`, clientes, dashboard u otros routers; cualquier reducción de campos en la respuesta del listado.

**Never:** Desactivar JWT globalmente, volver opcional `get_current_user`, alterar la lógica de búsqueda o expiración, modificar modelos o repositorios, ni cambiar las rutas públicas por UUID/PDF/WhatsApp.

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| Listado anónimo | `GET /api/v1/budgets/` sin token | HTTP 200 y respuesta paginada | No debe responder 401 |
| Filtros anónimos | Consulta sin token con filtros y paginación válidos | Se aplican los filtros existentes y se conserva el contrato | Validaciones existentes permanecen |
| Escritura sin token | `POST`, `PUT` o `DELETE` sin token | Las rutas continúan protegidas | HTTP 401 |
| Detalle administrativo sin token | `GET /api/v1/budgets/{uuid}/admin` | La ruta continúa protegida | HTTP 401 |

</frozen-after-approval>

## Code Map

- `app/api/v1/budgets.py:44-74` -- `list_budgets` contiene la dependencia `Depends(get_current_user)` que provoca el HTTP 401; las demás rutas administrativas declaran su autenticación individualmente.
- `tests/test_budgets.py:1018-1058` -- prueba existente del listado, filtros y paginación; debe explicitar que la consulta funciona sin encabezados y añadir regresión para rutas que permanecen privadas.
- `README.md:246-258` -- tabla de endpoints marca actualmente el listado como autenticado y lo describe como administrativo.
- `.agents/changelog.md` -- registro obligatorio de la iteración y archivos modificados.
- `_bmad-output/planning-artifacts/prds/prd-budget_maker-2026-08-25/prd.md:137-144,203` -- identifica presupuestos mediante UUID público y difiere autenticación/control de acceso.

## Tasks & Acceptance

**Execution:**
- [x] `app/api/v1/budgets.py` -- retirar `Depends(get_current_user)` y el parámetro `User` solo de `list_budgets` -- permitir acceso anónimo sin afectar rutas protegidas.
- [x] `tests/test_budgets.py` -- añadir pruebas explícitas para listado anónimo, filtros anónimos y permanencia del HTTP 401 en operaciones privadas -- prevenir regresiones de autorización.
- [x] `README.md` -- marcar `GET /api/v1/budgets/` como público y describir su acceso sin JWT -- mantener el contrato documentado.
- [x] `.agents/changelog.md` -- registrar la corrección con fecha y archivos -- cumplir la política del repositorio.

**Acceptance Criteria:**
- Given un cliente sin token y una base de datos disponible, when solicita `GET /api/v1/budgets/`, then recibe HTTP 200 con `{items, total, page, limit, pages}`.
- Given parámetros de búsqueda y paginación válidos sin token, when se consulta el listado, then se conserva el filtrado y orden existentes.
- Given un cliente sin token, when intenta crear, editar, eliminar o consultar el detalle administrativo de un presupuesto, then recibe HTTP 401.
- Given un cliente autenticado, when usa las rutas de presupuestos existentes, then su comportamiento previo permanece compatible.

## Spec Change Log

- 2026-09-22: Implementado el listado público, la cobertura de regresión y la actualización documental.

## Verification

**Commands:**
- `pytest tests/test_budgets.py -q` -- expected: todas las pruebas de presupuestos pasan con MongoDB de pruebas disponible.

**Resultado:**
- `python -m pytest tests/test_budgets.py -q` -- 48 pruebas superadas.
- `python -m compileall -q app tests` -- compilación correcta.
- `git -c core.whitespace=cr-at-eol diff --check` -- sin errores.

## Suggested Review Order

**Acceso público y límites de autenticación**

- El handler elimina únicamente la dependencia JWT del listado.
  [`budgets.py:45`](../../app/api/v1/budgets.py#L45)

- La regresión prueba listado anónimo y operaciones administrativas protegidas.
  [`test_budgets.py:881`](../../tests/test_budgets.py#L881)

- Los filtros y paginación se ejercitan explícitamente sin autorización.
  [`test_budgets.py:1041`](../../tests/test_budgets.py#L1041)

**Documentación**

- La tabla y descripción identifican el listado como público.
  [`README.md:249`](../../README.md#L249)

- El changelog registra alcance y archivos de la iteración.
  [`changelog.md:7`](../../.agents/changelog.md#L7)
