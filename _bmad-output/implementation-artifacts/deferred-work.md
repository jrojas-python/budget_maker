- source_spec: `C:\Users\JesusRojas\Documents\pyfiles\budget_maker\_bmad-output\implementation-artifacts\spec-1-1-configuracion-global-tipada-del-negocio.md`
  summary: Validar y endurecer conversión de `category_ids`/`category_id` para evitar 500 ante IDs inválidos en productos/búsqueda.
  evidence: El review detectó casteos directos a `PydanticObjectId` en `product_use_cases` y `product_repo` sin manejo explícito de error, riesgo no originado por esta historia.

- source_spec: `C:\Users\JesusRojas\Documents\pyfiles\budget_maker\_bmad-output\implementation-artifacts\spec-1-1-configuracion-global-tipada-del-negocio.md`
  summary: Añadir cobertura de pruebas para endpoints de branding y flujo de importación Excel.
  evidence: La capa de verificación reportó cambios funcionales en branding/import sin pruebas dedicadas en `tests/`, fuera del alcance directo de historia 1.1.

- source_spec: `C:\Users\JesusRojas\Documents\pyfiles\budget_maker\_bmad-output\implementation-artifacts\spec-1-1-configuracion-global-tipada-del-negocio.md`
  summary: Asegurar creación previa de directorio `uploads` antes de montar `StaticFiles` para evitar fallo de arranque en entornos limpios.
  evidence: Hallazgo de revisión sobre orden de inicialización en `main.py` no ligado al objetivo de configuración tipada de esta historia.

- source_spec: `spec-2-2-identificacion-publica-y-expiracion-del-presupuesto.md`
  summary: La ruta PDF publica /presupuesto/{uuid}/pdf no bloquea acceso a presupuestos expirados
  evidence: El endpoint GET /{uuid} ahora devuelve 410 para expirados, pero la ruta PDF no aplica la misma regla

- source_spec: `C:\Users\JesusRojas\Documents\pyfiles\budget_maker\_bmad-output\implementation-artifacts\spec-2-3-calculo-inmutable-de-montos-de-cotizacion.md`
  summary: Alinear la descarga pública de PDF con la política de expiración del presupuesto.
  evidence: La validación de expiración está en `GET /api/v1/budgets/{uuid}`, pero `web/views.py` en `/presupuesto/{uuid}/pdf` no aplica el mismo bloqueo.

## Deferred from: code review of spec-2-5-enlace-de-whatsapp-para-compartir-cotizacion.md (2026-08-28)

- Falta cobertura E2E del flujo JavaScript de catálogo para asegurar que `#modal-whatsapp` salga habilitado con URL canónica después de crear presupuesto; hoy la suite valida backend y vista pública, pero no ejecuta `catalog.js`.
