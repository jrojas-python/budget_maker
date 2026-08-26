- source_spec: `C:\Users\JesusRojas\Documents\pyfiles\budget_maker\_bmad-output\implementation-artifacts\spec-1-1-configuracion-global-tipada-del-negocio.md`
  summary: Validar y endurecer conversión de `category_ids`/`category_id` para evitar 500 ante IDs inválidos en productos/búsqueda.
  evidence: El review detectó casteos directos a `PydanticObjectId` en `product_use_cases` y `product_repo` sin manejo explícito de error, riesgo no originado por esta historia.

- source_spec: `C:\Users\JesusRojas\Documents\pyfiles\budget_maker\_bmad-output\implementation-artifacts\spec-1-1-configuracion-global-tipada-del-negocio.md`
  summary: Añadir cobertura de pruebas para endpoints de branding y flujo de importación Excel.
  evidence: La capa de verificación reportó cambios funcionales en branding/import sin pruebas dedicadas en `tests/`, fuera del alcance directo de historia 1.1.

- source_spec: `C:\Users\JesusRojas\Documents\pyfiles\budget_maker\_bmad-output\implementation-artifacts\spec-1-1-configuracion-global-tipada-del-negocio.md`
  summary: Asegurar creación previa de directorio `uploads` antes de montar `StaticFiles` para evitar fallo de arranque en entornos limpios.
  evidence: Hallazgo de revisión sobre orden de inicialización en `main.py` no ligado al objetivo de configuración tipada de esta historia.
