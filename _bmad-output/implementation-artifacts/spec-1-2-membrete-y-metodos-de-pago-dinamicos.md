---
title: 'Historia 1.2 - Membrete y métodos de pago dinámicos'
type: 'feature'
created: '2026-08-26'
baseline_commit: '605dd03f34d338da63128c4de40490778d076053'
status: 'done'
review_loop_iteration: 0
context:
  - '{project-root}/AGENTS.md'
  - '{project-root}/_bmad-output/implementation-artifacts/epic-1-context.md'
  - '{project-root}/_bmad-output/implementation-artifacts/spec-1-1-configuracion-global-tipada-del-negocio.md'
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** La plataforma aún no cubre de forma completa y consistente la historia 1.2: el branding debe poder cargarse como logo válido bajo reglas claras de formato/error y la gestión de métodos de pago dinámicos debe existir como capacidad API explícita para que administración y futuros flujos de presupuesto no dependan de cambios de código.

**Approach:** Consolidar en la capa de configuración global dos superficies funcionales de administración: carga de membrete (logo) con validación estricta y estado de error alineado a la historia, y CRUD mínimo de métodos de pago dinámicos con persistencia estable en `GlobalConfig`, manteniendo compatibilidad con endpoints/configuración existentes.

## Boundaries & Constraints

**Always:** Mantener Clean Architecture por capas; conservar asincronía; usar validación tipada y errores explícitos; persistir métodos de pago en configuración global tipada; mantener compatibilidad de endpoints de configuración ya usados por frontend; documentar contrato final de branding y métodos.

**Ask First:** Romper rutas existentes de branding (`/api/v1/config/branding/{key}`); exigir método de pago en creación de presupuesto dentro de esta historia; cambiar políticas de tipos de imagen fuera de lo que pide la historia (PNG/JPG para logo) sin compatibilidad.

**Never:** Introducir fallback silencioso para payload inválido; mezclar esta historia con refactors amplios de catálogo/auth; degradar rutas legacy de configuración que hoy consume el frontend; reescribir histórico de presupuestos existentes.

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| LOGO_UPLOAD_HAPPY | Archivo PNG/JPG válido y autenticación válida | Se guarda archivo en `/uploads/branding`, se actualiza clave de configuración del logo y se responde URL persistida | N/A |
| LOGO_UPLOAD_INVALID_FORMAT | Archivo no PNG/JPG | Operación rechazada | HTTP 400 con detalle de formato inválido |
| PAYMENT_METHODS_LIST_HAPPY | Configuración con o sin métodos iniciales | Retorna lista actual de métodos de pago dinámicos | N/A |
| PAYMENT_METHOD_ADD_HAPPY | Nombre de método nuevo válido | Método agregado y persistido en configuración global | N/A |
| PAYMENT_METHOD_REMOVE_HAPPY | Método existente | Método removido para nuevas selecciones y persistencia actualizada | N/A |
| PAYMENT_METHOD_DUPLICATE_OR_EMPTY | Método vacío o duplicado | Operación rechazada sin modificar persistencia | HTTP 422 con detalle de validación |

</frozen-after-approval>

## Code Map

- `app/domain/models/global_config.py` -- modelo tipado central; incorporar almacenamiento explícito de métodos de pago dinámicos.
- `app/domain/schemas/global_config.py` -- schemas para listado/alta/baja de métodos y respuestas de branding/config.
- `app/infrastructure/repositories/config_repo.py` -- operaciones de persistencia para obtener/agregar/remover métodos de pago y persistir branding.
- `app/application/use_cases/config_use_cases.py` -- orquestar reglas de negocio para métodos y branding sin duplicar lógica en API.
- `app/api/v1/config.py` -- entrypoint de endpoints: alias/endpoint de logo con validación PNG/JPG y gestión de métodos dinámicos.
- `settings/config.py` -- límites/rutas de archivos de branding reutilizadas por endpoint de logo.
- `web/static/js/admin.js` -- evidencia de consumo actual de branding/config; mantener compatibilidad sin ruptura.
- `tests/test_config.py` -- ampliar cobertura de config global para branding y métodos dinámicos.
- `README.md` -- contrato de endpoints y payloads de historia 1.2.

## Tasks & Acceptance

**Execution:**
- [x] `app/domain/models/global_config.py` -- añadir campo tipado para métodos de pago dinámicos (con default consistente) -- evita serialización ad hoc en `extra_settings`.
- [x] `app/domain/schemas/global_config.py` -- incorporar schemas de request/response para métodos de pago y logo -- define contrato API estable y validable.
- [x] `app/infrastructure/repositories/config_repo.py` -- implementar operaciones `get/add/remove payment_methods` con normalización y deduplicación -- encapsula persistencia y reglas básicas.
- [x] `app/application/use_cases/config_use_cases.py` -- exponer casos de uso para listar/agregar/remover métodos y actualizar branding -- mantiene API delgada y reusable.
- [x] `app/api/v1/config.py` -- agregar endpoint explícito de logo (PNG/JPG + HTTP 400 en formato inválido) y endpoints de métodos dinámicos (`GET/POST/DELETE`) preservando compatibilidad existente -- cumple historia 1.2 sin ruptura.
- [x] `tests/test_config.py` -- agregar pruebas de matriz I/O para branding y métodos (happy/error) -- cierra brechas de verificación.
- [x] `README.md` -- actualizar documentación de rutas, validaciones y ejemplos de uso de métodos de pago/branding -- alinea consumidores.

**Acceptance Criteria:**
- Given un admin autenticado y un archivo PNG/JPG válido, when sube el logo, then el backend guarda el archivo y actualiza la configuración del membrete con ruta reutilizable.
- Given un archivo con formato inválido para logo, when se intenta cargar, then la API rechaza con HTTP 400 y no altera la configuración.
- Given una configuración global inicial, when se consultan métodos de pago, then la API retorna la lista dinámica actual sin errores de tipado.
- Given un método nuevo válido, when se agrega por API, then queda persistido y aparece en lecturas posteriores.
- Given un método existente, when se elimina por API, then deja de estar disponible para nuevas selecciones sin fallar la persistencia de configuración.
- Given un método vacío o duplicado, when se intenta registrar, then la API responde error de validación y preserva el estado previo.

## Spec Change Log

## Design Notes

Se prioriza compatibilidad: en lugar de reemplazar rutas existentes, se introducen endpoints explícitos para historia 1.2 y se conserva el comportamiento actual que ya consume el frontend. La validación de logo se acota al contrato pedido por historia (PNG/JPG con 400) en la ruta explícita de logo, evitando cambios sorpresivos en flujos legacy de branding más amplios.

## Verification

**Commands:**
- `pytest tests/test_config.py -q` -- expected: pruebas de branding y métodos dinámicos pasan en happy/error.
- `pytest tests/test_budgets.py -q` -- expected: no regresiones en comportamiento de historia 1.1.
- `pytest -q` -- expected: sin regresiones nuevas atribuibles a esta historia.

## Suggested Review Order

**Punto de entrada API y contratos funcionales**

- Define rutas nuevas y compatibilidad de branding sin romper flujos existentes.
  [`config.py:89`](../../app/api/v1/config.py#L89)

- Delimita el contrato tipado para altas/listados de métodos dinámicos.
  [`global_config.py:29`](../../app/domain/schemas/global_config.py#L29)

**Persistencia y normalización de métodos de pago**

- Introduce almacenamiento tipado de métodos en configuración global.
  [`global_config.py:13`](../../app/domain/models/global_config.py#L13)

- Encapsula CRUD de métodos con deduplicación y normalización consistente.
  [`config_repo.py:117`](../../app/infrastructure/repositories/config_repo.py#L117)

- Expone la orquestación de negocio para API sin duplicar lógica.
  [`config_use_cases.py:57`](../../app/application/use_cases/config_use_cases.py#L57)

**Verificación y documentación**

- Cubre matriz I/O de logo y métodos, incluyendo errores y compatibilidad legacy.
  [`test_config.py:84`](../../tests/test_config.py#L84)

- Alinea contratos públicos y ejemplos operativos para consumidores.
  [`README.md:177`](../../README.md#L177)

- Registra la iteración entregada y los artefactos afectados.
  [`.agents/changelog.md:80`](../../.agents/changelog.md#L80)
