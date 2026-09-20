---
title: 'Gestión integral de presupuestos, clientes y dashboard'
type: 'feature'
created: '2026-09-19'
status: 'done'
review_loop_iteration: 0
baseline_commit: 'e97367f64cafd65bc376d6a6fc76f7c93aa33472'
context:
  - '{project-root}/AGENTS.md'
  - '{project-root}/_bmad-output/planning-artifacts/epics.md'
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** Los presupuestos no registran compañía u observaciones, carecen de gestión administrativa completa y no existe una entidad cliente ni métricas para el dashboard. La vista web y el PDF tampoco muestran toda la información disponible del cliente.

**Approach:** Mantener `client_info` como snapshot histórico, añadir una referencia opcional a una nueva colección `clients`, completar el CRUD administrativo autenticado, incorporar un resumen analítico UTC y migrar asociaciones históricas mediante un script idempotente.

## Boundaries & Constraints

**Always:** `nombres` es el único dato obligatorio del cliente. Sin documento, el presupuesto conserva `client_id=null` y no crea cliente; con documento normalizado, crea o actualiza el cliente y congela sus datos en `client_info`. Las rutas públicas por UUID, PDF y WhatsApp conservan expiración y compatibilidad. Editar recalcula líneas e importes, pero preserva código, UUID, creación, expiración y TTL. Clientes usan borrado lógico; presupuestos, físico. Fechas y métricas usan UTC.

**Ask First:** Cambiar nombres/rutas públicas, renovar expiración al editar, deduplicar por email, introducir roles, modificar snapshots desde el CRUD de clientes o cambiar la política de borrado.

**Never:** Implementar UI administrativa, auditoría, caché, tracking de vistas/conversiones o presentar montos presupuestados como ventas confirmadas. No renombrar `client_info` ni introducir claves JSON acentuadas.

</frozen-after-approval>

## Code Map

- `app/domain/models/budget.py` -- `ClientInfo`, `Budget`; snapshot e identidad opcional.
- `app/domain/models/client.py` -- nuevo documento Beanie con índice único parcial por documento.
- `app/domain/schemas/{budget,client,dashboard}.py` -- contratos Create/Update/Response, filtros y métricas.
- `app/infrastructure/repositories/{budget,client}_repo.py` -- paginación, upsert, CRUD y agregaciones.
- `app/application/use_cases/{budget,client,dashboard}_use_cases.py` -- reglas de vínculo, recálculo, borrado y periodos UTC.
- `app/api/v1/{budgets,clients,dashboard}.py` -- rutas públicas compatibles y administración JWT.
- `app/api/dependencies.py`, `app/database.py`, `main.py` -- composición, registro Beanie y routers.
- `web/templates/public/budget_view.html` -- plantilla compartida HTML/PDF.
- `scripts/backfill_budget_clients.py` -- migración CLI con `--dry-run` y lotes.
- `tests/` -- patrones JWT/AsyncClient en `conftest.py` y regresión principal en `test_budgets.py`.

## Tasks & Acceptance

**Execution:**

- [x] `app/domain/models/` y `app/domain/schemas/` -- añadir cliente, ampliar snapshot y definir contratos paginados/administrativos/analíticos.
- [x] `app/infrastructure/repositories/` -- implementar CRUD/búsqueda de clientes, búsqueda de presupuestos por UUID/filtros y agregaciones acotadas.
- [x] `app/application/use_cases/` -- centralizar cálculo de presupuesto, upsert por documento, update/delete y métricas con días faltantes en cero.
- [x] `app/api/`, `app/database.py`, `main.py` -- inyectar dependencias, registrar `Client` y exponer CRUD JWT y `GET /api/v1/dashboard/metrics`.
- [x] `web/templates/public/budget_view.html` -- renderizar nombre, apellidos, email, documento, compañía, dirección y observaciones con fallbacks.
- [x] `scripts/backfill_budget_clients.py` -- asociar históricos por documento sin alterar snapshots ni montos.
- [x] `tests/` -- cubrir auth, CRUD, anonimato, upsert, snapshot, filtros, recálculo, expiración, métricas y backfill idempotente.
- [x] `README.md`, `.agents/changelog.md` -- documentar contratos, migración y la iteración.

**Acceptance Criteria:**
- Given un usuario autenticado, when gestiona clientes o presupuestos, then dispone de listados paginados, detalle, alta, edición y las políticas de borrado acordadas.
- Given un presupuesto con documento, when se crea o cambia su cliente, then se enlaza por documento y su snapshot no cambia por ediciones posteriores del cliente.
- Given un presupuesto sin documento, when se crea con nombre, then no genera un registro cliente y sigue disponible en HTML/PDF con todos los campos aplicables.
- Given un presupuesto editado, when cambian ítems o método, then los montos se recalculan y sus identificadores y vencimiento permanecen iguales.
- Given un rango válido, when se consultan métricas, then devuelve día, semana ISO, mes, serie diaria, clientes únicos/recurrentes, productos y métodos de pago.
- Given datos históricos, when el backfill se ejecuta dos veces, then no duplica clientes ni modifica snapshots, importes o expiraciones.

## Spec Change Log

- 2026-09-19: revisión completada; se endurecieron nulos/cantidades, upsert, backfill, expiración legacy, rango analítico y pruebas de salidas públicas.

## Design Notes

La referencia `client_id` es opcional y `client_info` continúa siendo la fuente para documentos históricos y salidas públicas. El listado administrativo cambia deliberadamente de una lista ilimitada a `PaginatedResponse`; el detalle público permanece separado del detalle administrativo para que la expiración no impida gestionar registros vencidos.

## Verification

**Commands:**
- `docker compose up -d mongodb` -- MongoDB de pruebas disponible sin ocupar el puerto de la API.
- `pytest tests/test_clients.py tests/test_budgets.py tests/test_dashboard.py tests/test_backfill_budget_clients.py` -- funcionalidades nuevas y regresiones pasan.
- `pytest` -- suite completa sin regresiones.
- `python scripts/backfill_budget_clients.py --dry-run` -- informa cambios sin persistirlos.

**Manual checks (if no CLI):**
- Verificar HTML y PDF con datos completos, campos vacíos y observaciones largas; confirmar 410 público tras expirar y acceso administrativo autenticado.

## Suggested Review Order

**Vínculo histórico y edición**

- Orquesta snapshots, vínculo opcional, validación previa y recálculo sin renovar expiración.
  [`budget_use_cases.py:21`](../../app/application/use_cases/budget_use_cases.py#L21)

- Conserva datos existentes durante upserts parciales y evita escrituras sin cambios.
  [`client_repo.py:98`](../../app/infrastructure/repositories/client_repo.py#L98)

- Define snapshot histórico y referencia opcional al cliente reutilizable.
  [`budget.py:10`](../../app/domain/models/budget.py#L10)

**Frontera administrativa**

- Expone listado, alta, detalle, edición y borrado JWT de presupuestos.
  [`budgets.py:44`](../../app/api/v1/budgets.py#L44)

- Expone CRUD JWT de clientes con borrado lógico.
  [`clients.py:19`](../../app/api/v1/clients.py#L19)

- Filtra históricos con expiración efectiva, incluso sin `expires_at` persistido.
  [`budget_repo.py:31`](../../app/infrastructure/repositories/budget_repo.py#L31)

**Analítica y migración**

- Construye periodos UTC y completa días sin presupuestos con cero.
  [`dashboard_use_cases.py:24`](../../app/application/use_cases/dashboard_use_cases.py#L24)

- Asocia históricos por documento sin alterar snapshots ni clientes ya vigentes.
  [`backfill_budget_clients.py:20`](../../scripts/backfill_budget_clients.py#L20)

**Verificación**

- Prueba vínculo, snapshots y recálculo administrativo.
  [`test_budgets.py:917`](../../tests/test_budgets.py#L917)

- Comprueba datos completos del cliente en HTML y PDF.
  [`test_budgets.py:643`](../../tests/test_budgets.py#L643)

- Verifica métricas UTC, recurrencia, productos y pagos.
  [`test_dashboard.py:33`](../../tests/test_dashboard.py#L33)

- Demuestra simulación, asociación e idempotencia del backfill.
  [`test_backfill_budget_clients.py:31`](../../tests/test_backfill_budget_clients.py#L31)