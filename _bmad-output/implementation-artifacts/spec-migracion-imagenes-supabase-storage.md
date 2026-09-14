---
title: 'Migración de imágenes a Supabase Storage'
type: 'feature'
created: '2026-09-14'
baseline_commit: 'b1caab02872b4a0f54304efcdcb3af5637c03017'
status: 'done'
review_loop_iteration: 0
context:
  - '{project-root}/_bmad-output/planning-artifacts/architecture/architecture-budget_maker-2026-08-26/ARCHITECTURE-SPINE.md'
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** Los uploads de productos, logo y favicon dependen del disco local y del volumen Docker, por lo que no son persistentes ni directamente consumibles desde una infraestructura cloud. El frontend y WeasyPrint deben recibir URLs públicas estables de Supabase sin cambiar los endpoints existentes.

**Approach:** Enviar todos los uploads nuevos a Supabase Storage mediante un cliente asíncrono de backend, usar los buckets públicos `products` y `media/branding`, y persistir URLs públicas completas. Mantener lectura y eliminación de referencias locales legacy porque los archivos existentes no se migrarán.

## Boundaries & Constraints

**Always:** Configurar URL, secreto, buckets y prefijo mediante variables de entorno; usar una clave secreta solo en backend; preservar `image_urls`, rutas REST, límites de 2 MB/10 imágenes y formatos actuales; mantener asincronía end-to-end, inyección de dependencias, logging y compensación ante fallos entre Storage y MongoDB.

**Ask First:** Cambiar buckets, volver privado algún asset público, migrar archivos existentes o eliminar el montaje/volumen local legacy.

**Never:** Exponer `SUPABASE_SECRET_KEY`; habilitar escritura anónima; almacenar binarios en MongoDB; requerir SDK Supabase en frontend; borrar archivos legacy; ocultar errores de Storage con respuestas exitosas.

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| PRODUCT_UPLOAD | Imagen válida, producto con menos de 10 imágenes | Objeto en `products`; MongoDB y `image_urls` conservan URL pública Supabase | Si MongoDB falla, borrar objeto remoto |
| PRODUCT_DELETE | URL Supabase perteneciente al producto | Borrar objeto remoto y referencia exacta | Error explícito; no borrar otra referencia |
| LEGACY_PRODUCT | Nombre local o `image_filename` existente | Servir URL local actual y permitir borrado local | 404 si no pertenece al producto |
| BRANDING_REPLACE | Logo/favicon válido | Upsert en `media/branding`, guardar URL pública y limpiar extensión anterior | Conservar valor previo si upload/persistencia falla |
| BRANDING_DELETE | URL Supabase o ruta legacy | Borrar en almacenamiento correspondiente y vaciar configuración | Error explícito si falla el borrado |
| PDF_REMOTE | Presupuesto con URLs HTTPS públicas | HTML y PDF usan directamente las URLs Supabase | Propagar error operativo de generación |

</frozen-after-approval>

## Code Map

- `settings/config.py` -- settings Pydantic; agregar URL, secreto, buckets y prefijo con validadores.
- `app/infrastructure/services/image_service.py` -- validación y almacenamiento local actual; convertir en fachada asíncrona con compatibilidad legacy.
- `app/infrastructure/services/supabase_storage_service.py` -- nuevo adaptador del cliente asíncrono oficial para upload, remove y URL pública.
- `app/api/dependencies.py` -- singleton e inyección del servicio; evitar instancias ad hoc.
- `app/application/use_cases/product_use_cases.py` -- persistencia de referencias, URLs de respuesta, rollback y cascada.
- `app/api/v1/products.py` -- endpoint multipart; delegar validación al caso de uso.
- `app/application/use_cases/config_use_cases.py` y `app/api/v1/config.py` -- cargar, reemplazar y borrar branding remoto conservando códigos HTTP.
- `app/application/use_cases/budget_use_cases.py` -- reconocer URLs HTTPS en HTML/PDF y mantener fallback local.
- `main.py` y `docker-compose.yml` -- conservar `/uploads` y volumen exclusivamente para referencias legacy.
- `tests/conftest.py` -- fake Storage inyectado para impedir llamadas reales.
- `tests/test_products.py`, `tests/test_config.py`, `tests/test_budgets.py`, `tests/test_mongo_config.py` -- contratos cloud, compensaciones y compatibilidad.
- `README.md`, `.env.example`, `.gitignore`, `.agents/changelog.md` -- operación, secretos, transición legacy y trazabilidad.

## Tasks & Acceptance

**Execution:**
- [x] Configurar los buckets mediante migración Supabase: `products` y `media` públicos, 2 MB y MIME restringidos.
- [x] `requirements.txt`, `settings/config.py`, `.env.example` -- incorporar cliente y configuración segura.
- [x] Servicios, dependencias y casos de uso -- implementar Storage asíncrono, URLs públicas, rollback y compatibilidad local.
- [x] Routers y PDF -- preservar contratos HTTP y consumir referencias remotas.
- [x] Pruebas -- simular Storage y cubrir la matriz sin secretos ni red.
- [x] Documentación y changelog -- describir despliegue y transición.

**Acceptance Criteria:**
- Given un upload nuevo de producto, when la API responde, then cada URL nueva pertenece al dominio Supabase y el frontend no cambia su consumo.
- Given logo o favicon nuevo, when se consulta configuración, then el valor es una URL pública de `media/branding`.
- Given referencias locales anteriores al despliegue, when se listan productos o se genera un PDF, then continúan funcionando desde `/uploads`.
- Given un entorno sin secreto válido, when arranca una operación de escritura, then falla de forma explícita sin registrar ni exponer el secreto.

## Spec Change Log

## Design Notes

`Product.images` admite temporalmente dos formatos: URL HTTPS Supabase para uploads nuevos y nombre local para legacy. La fachada de imágenes clasifica cada referencia, valida que las URLs pertenezcan al proyecto/bucket configurado y extrae el object path antes de eliminar. El endpoint de borrado conserva `{filename}` resolviendo por basename contra la referencia exacta almacenada.

## Verification

**Commands:**
- `pytest tests/test_products.py tests/test_config.py tests/test_budgets.py tests/test_mongo_config.py -q` -- expected: flujos Storage y legacy pasan.
- `pytest -q` -- expected: suite completa sin llamadas al Supabase real.

## Suggested Review Order

**Orquestación de almacenamiento**

- Punto de entrada que decide remoto vs legacy sin cambiar contratos HTTP.
  [`image_service.py:69`](../../app/infrastructure/services/image_service.py#L69)

- Adaptador async que sube, borra y valida URLs públicas de Supabase.
  [`supabase_storage_service.py:58`](../../app/infrastructure/services/supabase_storage_service.py#L58)

- Settings tipados para URL, secreto, buckets y prefijo de branding.
  [`config.py:229`](../../settings/config.py#L229)

- Migración declarativa de buckets públicos con restricciones de Storage.
  [`20260914024000_storage_buckets.sql:4`](../../supabase/migrations/20260914024000_storage_buckets.sql#L4)

**Flujos de dominio**

- Cascada de borrado que conserva consistencia entre MongoDB y Storage.
  [`product_use_cases.py:174`](../../app/application/use_cases/product_use_cases.py#L174)

- Upload de producto con rollback remoto si la persistencia falla.
  [`product_use_cases.py:228`](../../app/application/use_cases/product_use_cases.py#L228)

- Reemplazo de branding con restauración del valor previo ante fallos.
  [`config_use_cases.py:81`](../../app/application/use_cases/config_use_cases.py#L81)

- Los routers preservan endpoints y traducen errores operativos a HTTP.
  [`products.py:110`](../../app/api/v1/products.py#L110)

- Branding mantiene rutas existentes y códigos HTTP explícitos.
  [`config.py:67`](../../app/api/v1/config.py#L67)

**Salida y compatibilidad legacy**

- PDF consume URLs HTTPS públicas y solo cae a local para legacy.
  [`budget_use_cases.py:221`](../../app/application/use_cases/budget_use_cases.py#L221)

- `/uploads` sigue montado desde el root legacy configurado.
  [`main.py:41`](../../main.py#L41)

- La guía operacional documenta Supabase, transición legacy y ejemplo actualizado.
  [`README.md:356`](../../README.md#L356)

**Verificación**

- El fake de Storage evita red real y permite inyección consistente.
  [`conftest.py:33`](../../tests/conftest.py#L33)

- Cobertura de cascada, rollback parcial y contrato del adaptador async.
  [`test_products.py:452`](../../tests/test_products.py#L452)

- Cobertura de restauración de branding cuando falla la limpieza previa.
  [`test_config.py:339`](../../tests/test_config.py#L339)

- Cobertura de PDF con assets remotos y propagación de errores.
  [`test_budgets.py:690`](../../tests/test_budgets.py#L690)
