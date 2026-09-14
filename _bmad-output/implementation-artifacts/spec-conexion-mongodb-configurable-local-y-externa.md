---
title: 'Conexión MongoDB configurable local y externa'
type: 'feature'
created: '2026-09-13'
status: 'done'
review_loop_iteration: 0
baseline_commit: '286d40b453f5e2a2ee787e653f59aeb3fe6a20a0'
context:
  - '{project-root}/_bmad-output/planning-artifacts/architecture/architecture-budget_maker-2026-08-26/ARCHITECTURE-SPINE.md'
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** El backend obtiene la URI de MongoDB desde configuración, pero el entorno Docker local no exige autenticación, las pruebas fijan una conexión anónima y no existe una guía segura para alternar entre MongoDB local y un servicio externo como Atlas. Esto limita el despliegue productivo y puede provocar que herramientas de desarrollo operen contra una base remota por accidente.

**Approach:** Consolidar la conexión mediante variables de entorno compatibles con `mongodb://` y `mongodb+srv://`, autenticar MongoDB local con las credenciales solicitadas y mantener los secretos reales exclusivamente en `.env`, que no se versiona. Documentar la conexión de nuevos servidores y el proceso automático de inicialización de Beanie y datos semilla.

## Boundaries & Constraints

**Always:** Mantener `MONGO_URI` y `MONGO_DB_NAME` como fuente de configuración del backend; aceptar URI estándar y SRV; conservar el flujo asíncrono `Motor`/Beanie; usar la URI Atlas suministrada únicamente en el `.env` ignorado; dejar comentada en ese mismo archivo la URI local autenticada; aislar las pruebas mediante `TEST_MONGO_URI` y una base `budget_maker_test`; mantener sincronizados Docker, documentación y ejemplos sin secretos reales.

**Ask First:** Cambiar el nombre de la base productiva, rotar credenciales suministradas, alterar el comportamiento de los seeds o introducir migraciones/scripts externos a Beanie.

**Never:** Versionar la contraseña o URI Atlas, ejecutar pruebas destructivas contra la base externa, eliminar datos o volúmenes existentes, desactivar autenticación en MongoDB local, ni modificar modelos o reglas de negocio que no sean necesarias para la conectividad.

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| Atlas | `MONGO_URI=mongodb+srv://...` y `MONGO_DB_NAME=budget_maker` | La aplicación inicia Motor y registra todos los modelos Beanie en la base remota | El arranque falla de forma visible ante DNS, red o autenticación inválida |
| Docker local | URI `mongodb://` con usuario, contraseña, host `mongodb` y `authSource=admin` | API, MongoDB y Mongo Express se conectan con autenticación | No se degrada silenciosamente a conexión anónima |
| Pruebas | `TEST_MONGO_URI` apunta al Mongo local autenticado | Pytest usa y limpia solo `budget_maker_test` | Se rechaza o evita usar `MONGO_URI` externa como fallback destructivo |
| Instalación nueva | Base vacía y primer arranque de la API | Beanie registra colecciones/índices y el lifespan crea configuración y superadministrador idempotentemente | Errores de índices o seeds impiden un arranque falsamente exitoso |

</frozen-after-approval>

## Code Map

- `settings/config.py` -- `Settings.mongo_uri` y `mongo_db_name`; punto único para validar esquemas `mongodb://`/`mongodb+srv://` sin acoplar el backend a Docker.
- `app/database.py:init_db` -- crea `AsyncIOMotorClient`, selecciona la base y registra `GlobalConfig`, `Product`, `Budget`, `User` y `Category` con `init_beanie`.
- `main.py` -- lifespan que llama `init_db()` y ejecuta los seeds idempotentes de configuración y superadministrador.
- `docker-compose.yml` -- servicios `mongodb`, `api` y `mongo-express`; debe consumir credenciales desde `.env` y habilitar autenticación raíz local.
- `.env` -- archivo ignorado donde se establece la URI Atlas real, credenciales locales, URI local comentada y URI de pruebas.
- `.env.example` -- nuevo contrato versionable con variables y ejemplos sanitizados para local/Atlas.
- `.gitignore` -- debe continuar excluyendo secretos y permitir explícitamente `.env.example`.
- `tests/conftest.py` -- cliente Motor de pruebas actualmente fijado a `mongodb://localhost:27017`; debe usar `TEST_MONGO_URI` sin fallback a Atlas.
- `README.md` -- documentará configuración local/externa, `authSource`, allowlist de Atlas, arranque limpio, creación de colecciones/índices y seeds.
- `.agents/changelog.md` -- registro obligatorio de la iteración y archivos modificados.

## Tasks & Acceptance

**Execution:**
- [x] `settings/config.py`, `app/database.py` -- endurecer y registrar de forma segura la configuración de conexión, preservando compatibilidad con URI estándar y SRV.
- [x] `.env`, `.env.example`, `.gitignore` -- configurar el entorno solicitado y separar secretos reales de ejemplos versionables.
- [x] `docker-compose.yml` -- activar autenticación local y conectar API/Mongo Express con variables coherentes.
- [x] `tests/conftest.py` -- aislar la URI de pruebas y proteger la base externa frente a limpieza destructiva.
- [x] `README.md` -- explicar alta de nuevas bases e inicialización automática desde cero.
- [x] `.agents/changelog.md` -- registrar la modificación.

**Acceptance Criteria:**
- Given un `.env` con una URI `mongodb+srv://` válida, when inicia la API, then Beanie se conecta a `MONGO_DB_NAME` sin depender del servicio Docker.
- Given el perfil local de Docker, when se levantan los servicios, then MongoDB exige `bm_local_admin` y la contraseña configurada en `.env`, y la API autentica correctamente.
- Given una base vacía, when ocurre el primer arranque, then existen los índices declarados y los seeds requeridos sin duplicados.
- Given la URI externa activa, when se ejecutan pruebas, then solo se usa `TEST_MONGO_URI` y se limpia exclusivamente `budget_maker_test`.
- Given un clon nuevo, when se consulta el README y `.env.example`, then se puede configurar otra instancia MongoDB sin copiar secretos del proyecto.

## Spec Change Log

- 2026-09-13: Implementada la conexión MongoDB configurable con validación de URI, stack Docker local autenticado, bootstrap idempotente del usuario raíz en volúmenes previos, aislamiento estricto de `TEST_MONGO_URI`, documentación actualizada y cobertura de verificación para configuración, seeds e índices.
- 2026-09-13 (revisión post-implementación): `blind-hunter`, `edge-case-hunter` y `verification-gap` revisaron el diff. Hallazgos `patch` aplicados: `app/database.py` ahora cierra y descarta el cliente Motor si `ping`/`init_beanie` fallan (evita fugas de conexión en reintentos); `settings/config.py::ensure_safe_test_mongo_uri` ahora exige contraseña no vacía y nombre de base explícito `budget_maker_test`; se añadieron pruebas para las ramas de `TEST_MONGO_URI` sin credenciales, sin `authSource=admin` y sin base explícita; se añadió una prueba que ejercita el `lifespan` real de `main.py` para asegurar que `init_db`/seeds/`close_db` se invocan en orden; se documentó en `README.md`/`.env.example` el riesgo de caracteres reservados de URI en `MONGO_LOCAL_ROOT_PASSWORD` y la necesidad de rotar el superadmin por defecto ante una base externa compartida. Hallazgo `defer`: `mongo-express` sin autenticación propia (`ME_CONFIG_BASICAUTH=false`) es preexistente a esta historia, registrado en `deferred-work.md`. Se descartó por falso positivo un hallazgo de "bucle infinito" en `docker/mongodb-entrypoint.sh`: se verificó manualmente contra un contenedor real que `ping` no requiere autenticación en MongoDB, por lo que el bucle de espera nunca cuelga.
- 2026-09-13 (revisión formal del workflow): se corrigió `.env` para activar exactamente la URI Atlas solicitada, conservar comentada la URI local y aplicar las credenciales solicitadas al Mongo local y a pruebas. Se bloquearon URIs de prueba con múltiples hosts o `authSource` ambiguo; `init_db` preserva el cliente anterior si un reintento falla y limpia cancelaciones; los fixtures cierran Motor con `finally`; el script Docker obtiene credenciales desde el entorno sin interpolarlas en JavaScript y `.gitattributes` fuerza LF. También se eliminaron instrucciones duplicadas o incorrectas del README y se añadieron pruebas de aliases, fallos de Beanie y fallos de seeds.

## Design Notes

La separación `MONGO_URI`/`TEST_MONGO_URI` es una barrera de seguridad, no solo una comodidad. Docker Compose debe recibir usuario y contraseña mediante interpolación desde `.env`; `.env.example` mostrará placeholders, mientras que la URI local completa solicitada permanecerá comentada únicamente en `.env`.

## Verification

**Commands:**
- `docker compose config` -- expected: configuración válida con variables resueltas y autenticación MongoDB habilitada.
- `docker compose up -d mongodb` -- expected: MongoDB local inicia y exige autenticación.
- `pytest` -- expected: pruebas conectadas a `budget_maker_test`, sin acceso a Atlas.

**Results:**
- `docker compose config` -- OK. La interpolación resolvió `MONGO_URI`, credenciales locales, `mongo-express` autenticado y el bootstrap del contenedor Mongo.
- `docker compose up -d mongodb` -- OK. El contenedor quedó `healthy`; se confirmó manualmente contra el contenedor real que una escritura sin credenciales (`insertOne`) es rechazada con `Command insert requires authentication`, mientras que `bm_local_admin` autentica correctamente (el `ping` no autenticado siempre responde por diseño de MongoDB y no representa una brecha).
- `python -m pytest` -- OK. `109 passed`; la suite ejerció la carga por variables de entorno, validación de URIs `mongodb://`/`mongodb+srv://`, aislamiento de `TEST_MONGO_URI` incluyendo múltiples hosts y `authSource` ambiguo, limpieza ante fallos de conexión/Beanie/seeds, el `lifespan` real de `main.py` y la idempotencia de seeds/índices.
- Conexión externa -- OK. Se ejecutó `ping` contra la URI Atlas activa en `.env` sobre `budget_maker`.
- Autenticación local -- OK. `bm_local_admin` autenticó con la contraseña solicitada y una escritura anónima fue rechazada.

## Suggested Review Order

**Configuración y validación de URI**

- Punto de entrada: valida esquemas `mongodb://`/`mongodb+srv://` y enmascara credenciales antes de loguear.
  [`config.py:10`](../../settings/config.py#L10)

- Endurece `TEST_MONGO_URI`: exige host local, credenciales no vacías, `authSource=admin` y base `budget_maker_test` explícita.
  [`config.py:41`](../../settings/config.py#L41)

- `Settings` enlaza variables de entorno y aplica validación segura al URI exclusivo de pruebas.
  [`config.py:71`](../../settings/config.py#L71)

**Conexión y ciclo de vida de Mongo**

- `init_db` crea el cliente Motor, valida con `ping`, registra Beanie y solo publica el cliente global si todo tuvo éxito.
  [`database.py:12`](../../app/database.py#L12)

- Un reintento fallido conserva la conexión previa y cierra únicamente el cliente candidato.
  [`database.py:12`](../../app/database.py#L12)

- El `lifespan` de FastAPI encadena `init_db`, los seeds idempotentes y `close_db` en el `finally`.
  [`main.py:27`](../../main.py#L27)

**Stack Docker local autenticado**

- El servicio `api` recibe `MONGO_URI` autenticado por interpolación desde `.env`, sin tocar la URI externa real.
  [`docker-compose.yml:10`](../../docker-compose.yml#L10)

- `mongodb` usa un entrypoint idempotente para crear el usuario raíz en volúmenes preexistentes y expone un healthcheck autenticado.
  [`docker-compose.yml:23`](../../docker-compose.yml#L23)

- El bootstrap usa variables de entorno y detecta la terminación prematura de Mongo.
  [`mongodb-entrypoint.sh:25`](../../docker/mongodb-entrypoint.sh#L25)

- Los scripts shell conservan finales LF al clonarse en Windows.
  [`.gitattributes:1`](../../.gitattributes#L1)

**Pruebas y documentación**

- Pruebas cubren aliases, hosts múltiples, reintentos fallidos y cierre ante errores de seeds.
  [`test_mongo_config.py:36`](../../tests/test_mongo_config.py#L36)

- Aísla las pruebas con `TEST_MONGO_URI` en lugar de una conexión anónima fija.
  [`conftest.py:13`](../../tests/conftest.py#L13)

- Documenta el flujo local/externo y la configuración del superadmin antes del primer arranque.
  [`README.md:58`](../../README.md#L58)

- Contrato versionable de variables de entorno sin secretos reales.
  [`.env.example:1`](../../.env.example#L1)
