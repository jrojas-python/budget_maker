---
title: 'Historia 1.1 - Configuración global tipada del negocio'
type: 'feature'
created: '2026-08-26'
baseline_commit: 'fd45c06f72aaf8f30fac336a226b1b30598c2550'
status: 'done'
review_loop_iteration: 0
context:
  - '{project-root}/AGENTS.md'
  - '{project-root}/_bmad-output/implementation-artifacts/epic-1-context.md'
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** La configuración comercial base (impuesto, TTL y visibilidad de fotos) está modelada hoy como pares clave/valor dispersos, lo que debilita validaciones por campo y dificulta mantener un contrato único y estable para nuevas cotizaciones.

**Approach:** Implementar un recurso global tipado y único para `tax_rate`, `link_ttl_minutes` y `show_product_photos_in_pdf`, manteniendo compatibilidad con el consumo actual donde sea necesario y conectando creación de presupuestos a ese recurso para aplicar cambios de inmediato en nuevas cotizaciones.

## Boundaries & Constraints

**Always:** Mantener arquitectura limpia por capas (API/use-cases/repositorio/modelo), asincronía extremo a extremo, type hints y manejo explícito de errores; validar rangos y tipos de campos de configuración; asegurar que cambios de configuración solo afectan presupuestos nuevos y no recalculan históricos.

**Ask First:** Cambiar contratos públicos existentes de `/api/v1/config/` que hoy consume frontend; eliminar claves legacy (`porcentaje_impuesto`, `tiempo_expiracion_link_minutos`) sin ruta de migración/compatibilidad; modificar semántica de expiración pública (410/404) ya definida para links vencidos.

**Never:** Introducir fallback silencioso ante datos inválidos; romper compatibilidad de branding/logo/métodos de pago por mezclar alcance de otras historias; meter autenticación/autorización nueva en esta historia; refactorizar módulos no relacionados.

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| GET_GLOBAL_CONFIG_HAPPY | Existe documento global tipado | API retorna `tax_rate`, `link_ttl_minutes`, `show_product_photos_in_pdf` con tipos correctos | N/A |
| PUT_GLOBAL_CONFIG_HAPPY | Payload válido con cambios de impuesto/TTL/flag | Persistencia del documento único y respuesta actualizada | N/A |
| PUT_GLOBAL_CONFIG_VALIDATION_ERROR | `tax_rate` fuera de rango, `link_ttl_minutes` inválido o tipo incorrecto | API rechaza actualización | HTTP 422 con detalle de validación |
| CREATE_BUDGET_AFTER_CONFIG_CHANGE | Config actualizada previamente | Presupuesto nuevo usa nuevos valores de impuesto/TTL | Error explícito si no existe configuración válida |
| MISSING_TYPED_DOC_WITH_LEGACY_KEYS | No existe doc tipado pero hay claves legacy persistidas | Use case compone config efectiva desde legacy y permite continuidad operativa temporal | Si faltan valores críticos, error claro de configuración |

</frozen-after-approval>

## Code Map

- `app/domain/models/global_config.py` -- Modelo Beanie actual de configuración; migrar de KV genérico a documento tipado único (o coexistencia controlada para transición).
- `app/domain/schemas/global_config.py` -- Contratos Pydantic de entrada/salida para exponer y validar `tax_rate`, `link_ttl_minutes`, `show_product_photos_in_pdf`.
- `app/infrastructure/repositories/config_repo.py` -- Punto de acceso de persistencia para lectura/escritura de configuración; agregar operaciones de singleton tipado y compatibilidad legacy temporal.
- `app/application/use_cases/config_use_cases.py` -- Orquestación de reglas de negocio de configuración; centralizar composición de config efectiva y validaciones de dominio.
- `app/api/v1/config.py` -- Endpoints de configuración; incorporar ruta de recurso tipado sin romper flujos existentes que aún dependan de claves legacy.
- `app/application/use_cases/budget_use_cases.py` -- Consume configuración para impuesto y expiración al crear presupuesto; conectar a recurso tipado para aplicar cambios inmediatos.
- `main.py` -- Flujo de arranque/seed; asegurar inicialización consistente del documento global tipado.
- `app/database.py` y `tests/conftest.py` -- Registro de modelos y setup de pruebas; mantener cobertura de inicialización.
- `web/static/js/catalog.js` y `web/templates/base.html` -- Evidencia de consumo frontend actual de config; tratar como superficie de compatibilidad para no romper UI.
- `README.md` -- Documentar el contrato final del recurso de configuración global.

## Tasks & Acceptance

**Execution:**
- [x] `app/domain/models/global_config.py` -- definir documento global tipado con campos requeridos y restricciones básicas -- establece fuente de verdad estructurada.
- [x] `app/domain/schemas/global_config.py` -- crear/ajustar schemas Create/Update/Response con validación fuerte -- asegura contrato de API consistente y testeable.
- [x] `app/infrastructure/repositories/config_repo.py` -- implementar get/upsert del singleton tipado y lectura de compatibilidad legacy temporal -- habilita transición sin caída de funcionalidades.
- [x] `app/application/use_cases/config_use_cases.py` -- encapsular obtención de config efectiva, actualización y seed tipado -- evita lógica duplicada entre API y presupuesto.
- [x] `app/api/v1/config.py` -- exponer lectura/actualización de la configuración tipada y preservar compatibilidad operativa vigente -- cumple historia sin ruptura abrupta.
- [x] `app/application/use_cases/budget_use_cases.py` -- usar config tipada para cálculo de impuesto y expiración en nuevas cotizaciones -- materializa el impacto funcional principal.
- [x] `main.py` -- garantizar bootstrap de configuración tipada al iniciar la app -- evita estados sin configuración.
- [x] `tests/test_config.py` -- agregar pruebas de happy path y validaciones de GET/PUT tipado -- cubre contrato central de historia.
- [x] `tests/test_budgets.py` -- verificar que presupuesto nuevo toma valores actualizados de impuesto/TTL -- cubre criterio de aplicación inmediata.
- [x] `README.md` -- actualizar endpoints y estructura de configuración global -- alinea documentación con implementación.

**Acceptance Criteria:**
- Given una instancia sin documento tipado, when se inicializa la aplicación, then existe una configuración global única con `tax_rate`, `link_ttl_minutes` y `show_product_photos_in_pdf`.
- Given un payload válido de actualización, when se ejecuta el endpoint de update de configuración global, then los nuevos valores se persisten y se retornan tipados correctamente.
- Given un payload inválido (tipo o rango), when se intenta actualizar configuración global, then la API responde con error de validación sin persistir cambios parciales.
- Given que la configuración global cambia, when se crea un presupuesto nuevo, then impuesto y expiración se calculan usando los valores vigentes al momento de creación.
- Given un presupuesto ya emitido, when luego cambia la configuración global, then sus montos persistidos no se recalculan retroactivamente.

## Spec Change Log

## Design Notes

Se permite una capa de compatibilidad temporal con claves legacy para reducir riesgo de ruptura del frontend ya existente mientras se migra al contrato tipado. La prioridad de lectura debe favorecer el documento tipado; el fallback legacy solo aplica cuando el documento tipado aún no existe o está incompleto por transición.

## Verification

**Commands:**
- `pytest tests/test_config.py` -- expected: endpoints de configuración tipada pasan happy-path y validaciones.
- `pytest tests/test_budgets.py` -- expected: creación de presupuesto toma impuesto/TTL vigentes y no altera históricos.
- `pytest` -- expected: sin regresiones fuera del alcance directo.

## Suggested Review Order

**Flujo tipado de configuración global**

- Punto de entrada del contrato tipado y validaciones de negocio.
  [`config.py:28`](../../app/api/v1/config.py#L28)

- Centraliza lectura efectiva y migración temporal desde claves legacy.
  [`config_repo.py:23`](../../app/infrastructure/repositories/config_repo.py#L23)

- Persistencia única tipada y restricciones de esquema en Mongo/Beanie.
  [`global_config.py:6`](../../app/domain/models/global_config.py#L6)

- Define input/output tipado con límites explícitos para update.
  [`global_config.py:17`](../../app/domain/schemas/global_config.py#L17)

**Integración con generación de presupuestos**

- Aplica `tax_rate` y `link_ttl_minutes` vigentes al crear presupuesto.
  [`budget_use_cases.py:66`](../../app/application/use_cases/budget_use_cases.py#L66)

- Propaga reglas tipadas a capa de casos de uso de configuración.
  [`config_use_cases.py:22`](../../app/application/use_cases/config_use_cases.py#L22)

- Garantiza bootstrap de defaults para evitar estados sin configuración.
  [`main.py:30`](../../main.py#L30)

**Cobertura de verificación**

- Valida contrato global, fallback legacy y coerción booleana segura.
  [`test_config.py:7`](../../tests/test_config.py#L7)

- Verifica aplicación inmediata en presupuestos nuevos sin recálculo histórico.
  [`test_budgets.py:30`](../../tests/test_budgets.py#L30)
