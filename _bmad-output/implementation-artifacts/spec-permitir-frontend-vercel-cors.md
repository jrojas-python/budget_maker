---
title: 'Permitir frontend de Vercel mediante CORS'
type: 'bugfix'
created: '2026-09-13'
status: 'done'
review_loop_iteration: 0
baseline_commit: 'e1cebc02eb12d52c09ad439c39ee9885b093b5fc'
context:
  - '{project-root}/_bmad-output/planning-artifacts/architecture/architecture-budget_maker-2026-08-26/ARCHITECTURE-SPINE.md'
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** El backend desplegado en Render no incluye middleware CORS, por lo que el navegador bloquea las solicitudes realizadas desde `https://budget-maker-frontend.vercel.app`.

**Approach:** Incorporar `CORSMiddleware` con una lista explícita y configurable de orígenes permitidos, incluyendo el dominio productivo de Vercel. Mantener una política restrictiva sin usar comodines y documentar cómo añadir otros frontends.

## Boundaries & Constraints

**Always:** Permitir exactamente `https://budget-maker-frontend.vercel.app` por defecto; aceptar configuración adicional mediante variable de entorno; normalizar espacios y barras finales; habilitar métodos y cabeceras requeridos por la API; cubrir solicitudes preflight y peticiones desde orígenes rechazados.

**Ask First:** Habilitar patrones comodín para previews de Vercel, permitir todos los orígenes o cambiar la política de credenciales.

**Never:** Usar `allow_origins=["*"]`, aceptar orígenes vacíos, incluir secretos en configuración versionada ni modificar autenticación o endpoints ajenos al problema CORS.

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| Frontend productivo | `Origin: https://budget-maker-frontend.vercel.app` | Preflight y respuesta incluyen `Access-Control-Allow-Origin` para ese origen | N/A |
| Origen no permitido | `Origin: https://sitio-no-autorizado.example` | La respuesta no concede acceso CORS | El navegador mantiene bloqueado el acceso |
| Configuración adicional | `CORS_ALLOWED_ORIGINS` contiene varios dominios separados por coma | Cada origen válido queda permitido tras eliminar espacios y `/` finales | Entradas vacías se descartan |

</frozen-after-approval>

## Code Map

- `settings/config.py:71` -- `Settings` centraliza variables de entorno; añadirá y normalizará la lista CORS.
- `main.py:39` -- instancia FastAPI donde debe registrarse `CORSMiddleware` antes de montar rutas.
- `.env.example:1` -- contrato versionable para documentar `CORS_ALLOWED_ORIGINS`.
- `tests/test_cors.py` -- nueva cobertura aislada para preflight permitido, origen rechazado y parsing de configuración.
- `README.md:58` -- sección de despliegue y tabla de variables para explicar configuración en Render.
- `.agents/changelog.md:1` -- registro obligatorio de la corrección.

## Tasks & Acceptance

**Execution:**
- [x] `settings/config.py` -- añadir configuración y normalización de orígenes CORS.
- [x] `main.py` -- registrar `CORSMiddleware` con la lista configurada.
- [x] `.env.example`, `README.md` -- documentar el dominio permitido y cómo ampliarlo en Render.
- [x] `tests/test_cors.py` -- verificar preflight permitido, rechazo de origen y normalización.
- [x] `.agents/changelog.md` -- registrar la iteración.

**Acceptance Criteria:**
- Given una solicitud desde `https://budget-maker-frontend.vercel.app`, when el navegador realiza el preflight, then el backend responde con el encabezado CORS para ese origen.
- Given un origen no incluido, when realiza una solicitud, then el backend no devuelve `Access-Control-Allow-Origin`.
- Given varios orígenes configurados con espacios o barras finales, when se carga `Settings`, then se obtiene una lista limpia sin entradas vacías.

## Spec Change Log

## Design Notes

Se usará una cadena separada por comas en `CORS_ALLOWED_ORIGINS` para evitar la sintaxis JSON obligatoria de listas en variables de entorno y facilitar la configuración en Render.

## Verification

**Commands:**
- `python -m pytest tests/test_cors.py -q` -- expected: escenarios CORS y parsing correctos.
- `python -m pytest -q` -- expected: suite completa sin regresiones.

## Suggested Review Order

**Integración de la aplicación**

- Centraliza la creación de FastAPI para aplicar cualquier configuración CORS validada.
  [`main.py:43`](../../main.py#L43)

- Registra métodos, cabeceras y credenciales explícitas antes de rutas y archivos estáticos.
  [`main.py:52`](../../main.py#L52)

**Configuración y normalización**

- Limpia espacios, barras, duplicados y comodines sin aceptar listas vacías.
  [`config.py:13`](../../settings/config.py#L13)

- Expone el dominio productivo exacto mediante la variable de entorno.
  [`config.py:113`](../../settings/config.py#L113)

**Verificación y operación**

- Verifica preflight para todos los métodos usados por la API.
  [`test_cors.py:23`](../../tests/test_cors.py#L23)

- Comprueba rechazo simple y preflight de orígenes no configurados.
  [`test_cors.py:61`](../../tests/test_cors.py#L61)

- Confirma el dominio predeterminado y múltiples orígenes a través del middleware.
  [`test_cors.py:99`](../../tests/test_cors.py#L99)

- Documenta la configuración completa de orígenes autorizados en Render.
  [`README.md:126`](../../README.md#L126)

- Publica el valor productivo seguro en el contrato de entorno.
  [`.env.example:19`](../../.env.example#L19)

- Registra implementación, revisión y cobertura incorporada.
  [`changelog.md:7`](../../.agents/changelog.md#L7)
