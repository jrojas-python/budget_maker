# Budget Maker

Aplicación web para generación de presupuestos/cotizaciones de productos. Prueba de Concepto (POC).

## Stack

- **Backend:** Python 3.11+, FastAPI (async)
- **Base de Datos:** MongoDB 7 (Beanie ODM + Motor async)
- **Cliente DB:** mongo-express (puerto 8081)
- **Frontend:** Jinja2 Templates + CSS responsive (SPA-like con fetch API)
- **PDF:** WeasyPrint 62 + pydyf 0.11
- **Excel:** openpyxl (importación/exportación)
- **Contenedores:** Docker + docker-compose

## Setup

```bash
docker-compose up --build
```

Servicios disponibles:
- API: http://localhost:8000
- Swagger UI: http://localhost:8000/docs
- mongo-express: http://localhost:8081

## Arquitectura

```
budget_maker/
├── main.py                     # Entry point
├── settings/config.py          # Configuración (.env)
├── app/
│   ├── database.py             # Conexión MongoDB
│   ├── domain/models/          # Documentos Beanie
│   ├── domain/schemas/         # Pydantic v2 schemas
│   ├── infrastructure/
│   │   ├── repositories/       # Acceso a datos
│   │   └── services/           # PDF, Excel
│   ├── application/use_cases/  # Lógica de negocio
│   └── api/v1/                 # Routers REST
├── web/
│   ├── views.py                # Rutas Jinja2
│   ├── templates/              # HTML
│   └── static/                 # CSS
└── docker-compose.yml
```

**Principios:** Clean Architecture, POO, DRY, SOLID.

## Endpoints

### Configuración Global
| Método | Ruta | Descripción |
|--------|------|-------------|
| GET | `/api/v1/config/` | Listar toda la configuración |
| GET | `/api/v1/config/{key}` | Obtener config por clave |
| PUT | `/api/v1/config/{key}` | Actualizar config |

### Productos
| Método | Ruta | Descripción |
|--------|------|-------------|
| GET | `/api/v1/products/` | Listar productos |
| GET | `/api/v1/products/{id}` | Obtener producto |
| POST | `/api/v1/products/` | Crear producto |
| PUT | `/api/v1/products/{id}` | Actualizar producto |
| DELETE | `/api/v1/products/{id}` | Eliminar producto |
| POST | `/api/v1/products/import` | Importar desde Excel (.xlsx) |

### Presupuestos
| Método | Ruta | Descripción |
|--------|------|-------------|
| GET | `/api/v1/budgets/` | Listar presupuestos |
| POST | `/api/v1/budgets/` | Crear presupuesto |
| GET | `/api/v1/budgets/{uuid}` | Obtener presupuesto |

### Frontend Web
| Método | Ruta | Descripción |
|--------|------|-------------|
| GET | `/` | Catálogo de productos + creación de presupuestos |
| GET | `/admin` | Panel admin (CRUD productos, config, import Excel) |
| GET | `/presupuesto/{uuid}` | Vista HTML del presupuesto (link temporal) |
| GET | `/presupuesto/{uuid}/pdf` | Descargar presupuesto como PDF |

## POC Frontend

### Catálogo (`/`)
- Grid de productos con buscador y filtros
- Panel lateral para armar presupuesto (seleccionar productos + cantidades)
- Formulario de datos del cliente (nombre, empresa, teléfono)
- Modal de confirmación con detalle completo del presupuesto generado
- Acciones post-creación: **Ver presupuesto**, **Descargar PDF**, **Enviar por WhatsApp**

### Admin (`/admin`)
- **Tab Productos:** CRUD completo (crear, editar, eliminar)
- **Tab Configuración:** Editar porcentaje de impuesto y tiempo de expiración
- **Tab Importar:** Carga masiva de productos desde archivo Excel (.xlsx)

## Flujo de Uso

1. **Configurar** — Los valores de impuesto y expiración se crean automáticamente al iniciar
2. **Agregar productos** — Vía CRUD individual o importación Excel masiva desde `/admin`
3. **Crear presupuesto** — Desde el catálogo (`/`): seleccionar productos, llenar datos del cliente, confirmar
4. **Compartir** — Desde el modal de confirmación:
   - **Link temporal** — Vista HTML con expiración configurable
   - **PDF** — Descarga directa del presupuesto
   - **WhatsApp** — Mensaje pre-armado con resumen y link

## Notas Técnicas

- Los links de presupuesto expiran según `tiempo_expiracion_link_minutos` (default: 30 min)
- MongoDB almacena `created_at` como datetime naive (sin timezone); el sistema normaliza a UTC antes de comparar
- WeasyPrint requiere `pydyf==0.11.*` (la versión 0.12+ tiene incompatibilidad con WeasyPrint 62)
- El Dockerfile incluye las dependencias del sistema necesarias para WeasyPrint (libpango, libcairo, etc.)

## Importación Excel

El archivo `.xlsx` debe tener estas columnas (primera fila como headers):

| nombre | sku | costo | unidad | moneda |
|--------|-----|-------|--------|--------|
| Producto A | SKU-001 | 25.50 | unidad | USD |

**Regla de colisión:** Si el SKU ya existe → actualiza. Si no → crea.

## Variables de Entorno

| Variable | Valor por defecto | Descripción |
|----------|-------------------|-------------|
| `MONGO_URI` | `mongodb://mongodb:27017` | URI de conexión a MongoDB |
| `MONGO_DB_NAME` | `budget_maker` | Nombre de la base de datos |
| `APP_HOST` | `0.0.0.0` | Host del servidor |
| `APP_PORT` | `8000` | Puerto del servidor |

## Configuración Global (seed automático)

| Clave | Valor | Descripción |
|-------|-------|-------------|
| `porcentaje_impuesto` | 18 | % de impuesto sobre subtotal |
| `tiempo_expiracion_link_minutos` | 30 | Minutos de validez del link |
