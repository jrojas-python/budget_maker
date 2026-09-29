# PRD — Budget Maker API (POC)

## Producto

Servicio de generación de presupuestos/cotizaciones de productos. API RESTful como Prueba de Concepto (POC) sin autenticación.

## Stack Tecnológico

| Componente | Tecnología |
|------------|-----------|
| Backend | Python 3.11+, FastAPI |
| Base de Datos | MongoDB (Beanie ODM + Motor async) |
| Cliente DB | mongo-express (Docker) |
| Frontend MVP | Jinja2 Templates desde FastAPI |
| PDF | WeasyPrint |
| Excel | openpyxl |
| Contenedores | Docker + docker-compose |

## Alcance del POC

### Incluido
- Configuración global dinámica (impuesto, expiración de links)
- CRUD completo de productos
- Importación masiva vía Excel (.xlsx) con upsert por SKU
- Creación de presupuestos con cálculos automáticos
- Vista HTML temporal con expiración configurable
- Descarga PDF del presupuesto
- Compartición vía WhatsApp (link con texto formateado)
- Dockerización completa

### Excluido
- Autenticación / autorización
- Tests automatizados (fase futura)
- CI/CD
- Deploy a cloud
- Envío real de mensajes WhatsApp

## Principios de Diseño

- **Clean Architecture**: Dominio → Aplicación → Infraestructura → Presentación (API/Web)
- **POO**: Clases con responsabilidades claras
- **DRY**: No repetir lógica; abstraer en servicios/repositorios reutilizables
- **SOLID**: Interfaces segregadas, inversión de dependencias, responsabilidad única

## Reglas de Trabajo del Agente

1. **Siempre documentar en README.md** — Mantener actualizado con arquitectura, setup, endpoints y flujo de uso.
2. **Changelog por iteración** — Registrar cada iteración completada en `.agents/changelog.md` con fecha, descripción y archivos afectados.
3. **Coding style** — Seguir convenciones del skill `coding-style`:
   - snake_case para variables/funciones
   - Type hints Python 3.10+ (`str | None`, `list[str]`)
   - Logger por módulo: `logger = logging.getLogger(__name__)`
   - Docstrings en español para funciones públicas
   - Imports ordenados: stdlib → terceros → proyecto
4. **Async end-to-end** — Handlers, repositorios y servicios siempre async.
5. **Inyección de dependencias** — Vía `FastAPI Depends` para repos y use cases.
6. **Schemas separados** — Create, Update, Response por cada entidad.
7. **Errores HTTP uniformes** — HTTPException con códigos consistentes (404, 422, 409, 500).

## Lógica de Negocio Clave

### Presupuesto
- Código formato: `BM-YYYYMMDD-XXXX` (4 chars alfanuméricos random uppercase)
- UUID4 como identificador público para URLs
- Cálculo: subtotal = Σ(costo × cantidad), impuesto = subtotal × porcentaje_config, total = subtotal + impuesto
- Expiración de link: `created_at + tiempo_expiracion_link_minutos` vs `utcnow()`

### Importación Excel
- Columnas esperadas: nombre, sku, costo, unidad, moneda
- Columna opcional: colores (formato `Nombre:#HEX,Nombre:#HEX`)
- Regla de colisión: si SKU existe → actualizar; si no → crear

### Colores de Producto
- Cada producto puede tener de 0 a 6 colores
- Cada color tiene nombre descriptivo y código hexadecimal (`#RRGGBB`)
- El primer color de la lista es el default
- Al crear presupuesto: el usuario elige un color o se asigna el default
- El color seleccionado aparece en la vista HTML, PDF y texto WhatsApp

### WhatsApp
- Formato con markdown WhatsApp (`*bold*`)
- URL: `https://wa.me/?text={url_encoded_text}`

## Protocolo de Orquestación Multi-Agente con Herdr

### Identidades y Roles
- **backend-agent**: Agente local (FastAPI, MongoDB Beanie ODM, Clean Architecture en `budget_maker`). Orquestador principal cuando recibe tareas de negocio o API.
- **frontend-agent**: Agente vecino (React SPA, Vite en `~/Documents/pyfiles/budget_maker_frontend`). Encargado del consumo de la API, estado del cliente y UI.
- **Entorno de Comunicación**: Terminal multiplexer Herdr (`herdr agent prompt`, `herdr agent read`, etc.).

### Flujo de Trabajo Autónomo (Backend-First)
Siempre que el usuario solicite implementar una nueva lógica de negocio, crear/modificar/eliminar endpoints o alterar features:
1. **Implementación y Validación Backend**: `backend-agent` diseña e implementa primero el modelo, schema, caso de uso, repositorio y endpoint FastAPI, asegurando su correcto funcionamiento.
2. **Generación Automática de Tarea para Frontend**: Sin solicitar permiso previo al usuario, `backend-agent` define la tarea equivalente correspondiente para la SPA de frontend.
3. **Delegación Vía Herdr**: `backend-agent` envía la tarea a `frontend-agent` mediante:
   ```bash
   herdr agent prompt frontend-agent "<payload_estructurado>" --wait
   ```
4. **Estructura Obligatoria del Mensaje de Delegación**:
   - **Título**: Descripción concisa de la tarea delegada.
   - **Contexto / Motivación**: Qué cambio se efectuó en el sistema y por qué.
   - **Contrato de API**: Método HTTP, URL, parámetros, headers, schemas/payloads JSON de solicitud y respuesta, códigos de estado.
   - **Cambios Esperados en Frontend**: Archivos/servicios a modificar (`src/services/api.js`, `src/services/adminApi.js`), rutas, páginas o componentes de React.
   - **Criterios de Aceptación**: Reglas funcionales requeridas en la vista.
   - **Comando de Verificación**: Ejecución obligatoria de `npm run build` en el frontend para validar que no haya regresiones.
5. **Manejo de Bloqueos y Escalado Inmediato**:
   - Si `frontend-agent` completa su labor exitosamente, `backend-agent` valida la respuesta con `herdr agent read frontend-agent` y consolida el reporte final al usuario.
   - Si `frontend-agent` falla, genera errores no recuperables o queda en estado `blocked`, `backend-agent` detiene de inmediato el flujo, consulta los logs con `herdr agent read frontend-agent` y escala la incidencia al usuario explicando el bloqueo.

