# Budget Maker

Sistema web de generación de presupuestos/cotizaciones con autenticación JWT, catálogo de productos con búsqueda e imágenes, categorías M2M y exportación PDF/WhatsApp.

## Stack Tecnológico

| Capa | Tecnología |
|------|-----------|
| Backend | Python 3.11+, FastAPI 0.115.x (async) |
| Base de Datos | MongoDB 7 (Beanie ODM + Motor) |
| Autenticación | JWT HS256 (python-jose + passlib bcrypt) |
| Frontend | Jinja2 Templates + Vanilla JS (sin build step) |
| PDF | WeasyPrint 62 + pydyf 0.11 |
| Excel | openpyxl (importación masiva) |
| Tests | pytest + httpx + pytest-asyncio |
| Contenedores | Docker + docker-compose |

## Arquitectura

```
budget_maker/
├── main.py                          # Entry point, lifespan, routers
├── settings/config.py               # Configuración (.env / pydantic-settings)
├── app/
│   ├── database.py                  # Conexión MongoDB + init Beanie
│   ├── domain/
│   │   ├── models/                  # Documentos Beanie (Product, Budget, User, Category, GlobalConfig)
│   │   └── schemas/                 # Pydantic v2 request/response
│   ├── infrastructure/
│   │   ├── repositories/            # Acceso a datos (CRUD async)
│   │   └── services/               # PDF, Excel, Auth, Image
│   ├── application/use_cases/       # Lógica de negocio
│   └── api/
│       ├── dependencies.py          # DI, OAuth2, get_current_user
│       └── v1/                      # Routers REST (auth, users, config, categories, products, budgets)
├── web/
│   ├── views.py                     # Rutas Jinja2 (catálogo, admin, presupuestos)
│   ├── templates/
│   │   ├── base.html                # Layout con navbar adaptativo
│   │   ├── public/                  # catalog, budget_view, budget_expired
│   │   └── admin/                   # login, dashboard
│   └── static/
│       ├── styles.css               # Estilos responsivos
│       └── js/                      # Módulos JS (api, auth, catalog, admin)
├── tests/                           # Tests E2E (pytest + httpx)
├── uploads/products/                # Compatibilidad legacy para referencias locales
├── supabase/migrations/             # Buckets y configuración declarativa de Storage
├── Dockerfile
└── docker-compose.yml
```

**Principios:** Clean Architecture, DI, async everywhere, SOLID.

## Despliegue

### Requisitos
- Docker + Docker Compose

### Configuración de entorno

1. Copia `.env.example` a `.env`.
2. Define `MONGO_URI` con la instancia que quieras usar fuera de Docker:
   - **Atlas / MongoDB externo:** pega únicamente la URI real `mongodb+srv://...` en tu `.env` local no versionado.
   - **MongoDB local autenticado:** usa una URI `mongodb://` con usuario, contraseña y `authSource=admin`.
3. Mantén `MONGO_DB_NAME=budget_maker`.
4. Configura `TEST_MONGO_URI` para que apunte **solo** a `budget_maker_test` en `localhost` con autenticación.
5. Ajusta `MONGO_LOCAL_ROOT_USERNAME` y `MONGO_LOCAL_ROOT_PASSWORD` para el stack Docker local. Usa una contraseña alfanumérica sin caracteres reservados de URI, porque Docker Compose interpola estas credenciales tanto como valores literales del servidor como dentro de la URI del cliente.
6. Mantén `CORS_ALLOWED_ORIGINS=https://budget-maker-frontend.vercel.app,http://localhost:3000,http://localhost:3001` para frontend productivo y desarrollo local. Para autorizar otros frontends en Render, agrega sus orígenes separados por comas, sin rutas; los espacios y las barras finales se normalizan.
7. Configura `SUPABASE_URL`, `SUPABASE_SECRET_KEY`, `SUPABASE_PRODUCTS_BUCKET`, `SUPABASE_MEDIA_BUCKET` y `SUPABASE_BRANDING_PREFIX` para que los uploads nuevos se persistan en Supabase Storage. Usa únicamente la **service role key** en backend y nunca la expongas al frontend.
8. Aplica la migración `supabase/migrations/20260914024000_storage_buckets.sql` en tu proyecto Supabase para declarar los buckets públicos `products` y `media` con límite de 2 MB y MIME restringidos.

`.env.example` ya incluye:
- un ejemplo sanitizado de Atlas,
- las credenciales locales requeridas por Docker Compose,
- una URI local autenticada comentada para alternar `MONGO_URI`,
- y la URI aislada de pruebas.

### Iniciar entorno local completo

```bash
docker compose up --build
```

El servicio `api` siempre consume `MONGO_URI` y `MONGO_DB_NAME` como fuente de configuración. En Docker Compose, `MONGO_URI` se sobreescribe dentro del contenedor para apuntar al MongoDB local autenticado (`mongodb`) sin tocar la URI externa que puedas conservar en tu `.env`.

### Iniciar solo MongoDB para pruebas locales

```bash
docker compose up -d mongodb
```

MongoDB arranca con autenticación raíz habilitada. Si ejecutas la API fuera de Docker, usa la URI local autenticada de `localhost` o una URI externa válida.
Si ya existía un volumen local anónimo, el contenedor intenta crear el usuario raíz configurado sin borrar datos ni volúmenes; si las credenciales no coinciden con un usuario preexistente, el arranque falla de forma visible para evitar conexiones ambiguas.

### Servicios

| Servicio | URL |
|----------|-----|
| Aplicación | http://localhost:8000 |
| Swagger UI | http://localhost:8000/docs |
| mongo-express | http://localhost:8081 (solo desarrollo local; la interfaz web no tiene autenticación HTTP) |

### Variables de Entorno

| Variable | Ejemplo / Default | Descripción |
|----------|-------------------|-------------|
| `MONGO_URI` | `mongodb+srv://<usuario>:<password>@<cluster>.mongodb.net/?retryWrites=true&w=majority` | URI principal del backend. Acepta `mongodb://` y `mongodb+srv://`. |
| `MONGO_DB_NAME` | `budget_maker` | Base sobre la que Beanie registra colecciones e índices. |
| `TEST_MONGO_URI` | `mongodb://bm_local_admin:cambia-esta-clave-local@localhost:27017/budget_maker_test?authSource=admin` | URI exclusiva de pruebas. Nunca debe apuntar a Atlas ni a otra base. |
| `MONGO_LOCAL_ROOT_USERNAME` | `bm_local_admin` | Usuario raíz usado por el MongoDB local autenticado del stack Docker. |
| `MONGO_LOCAL_ROOT_PASSWORD` | `cambia-esta-clave-local` | Contraseña raíz usada por MongoDB local, `api` y `mongo-express`. |
| `CORS_ALLOWED_ORIGINS` | `https://budget-maker-frontend.vercel.app,http://localhost:3000,http://localhost:3001` | Orígenes CORS explícitos separados por comas. No admite comodines; para conservar el frontend productivo al añadir otro origen, incluye la lista completa. |
| `JWT_SECRET_KEY` | `change-me-in-production` | Secreto JWT (cambiar en producción). |
| `JWT_ALGORITHM` | `HS256` | Algoritmo JWT. |
| `JWT_EXPIRE_MINUTES` | `480` | Expiración del token (8h). |
| `UPLOAD_DIR` | `uploads/products` | Directorio local legacy usado solo para referencias previas al despliegue cloud. |
| `BRANDING_DIR` | `uploads/branding` | Directorio local legacy usado solo para branding previo al despliegue cloud. |
| `SUPABASE_URL` | `https://<project-ref>.supabase.co` | URL base del proyecto Supabase usada para Storage público. |
| `SUPABASE_SECRET_KEY` | `<service-role-key-backend-only>` | Service role key del backend. Nunca debe exponerse al frontend. |
| `SUPABASE_PRODUCTS_BUCKET` | `products` | Bucket público para imágenes nuevas de productos. |
| `SUPABASE_MEDIA_BUCKET` | `media` | Bucket público para branding nuevo. |
| `SUPABASE_BRANDING_PREFIX` | `branding` | Prefijo POSIX dentro del bucket `media` para logo y favicon. |

### Conectar una instancia MongoDB externa nueva

1. Crea la base `budget_maker` (o la que definas en `MONGO_DB_NAME`) en tu proveedor MongoDB.
2. Añade la IP pública del entorno donde corre la API a la allowlist/regla de red del proveedor.
3. Crea un usuario con permisos sobre esa base.
4. Pega la URI real `mongodb+srv://...` o `mongodb://...` únicamente en `.env`.
5. Inicia la API; durante el lifespan se ejecuta `init_db()`, se valida la conexión con `ping`, Beanie registra colecciones/índices y luego se crean de forma idempotente la configuración global y el superadministrador.

Si la URI es inválida, falla DNS/red o la autenticación es incorrecta, el arranque falla de forma visible; la aplicación no degrada silenciosamente a una conexión anónima.

En Render, configura `CORS_ALLOWED_ORIGINS` con la lista completa de frontends autorizados, por ejemplo:

```dotenv
CORS_ALLOWED_ORIGINS=https://budget-maker-frontend.vercel.app,https://admin.example.com
```

Cada origen debe incluir `http://` o `https://`, host y puerto opcional, sin ruta,
query, fragmento, credenciales ni comodines. CORS permite `GET`, `HEAD`, `POST`,
`PUT`, `DELETE` y `OPTIONS`, acepta `Authorization` y `Content-Type`, y expone
`Content-Disposition` para descargas. La autenticación continúa mediante el
header Bearer; no se habilitan credenciales CORS basadas en cookies.

No uses `*` ni patrones para previews de Vercel. Cada preview debe declararse explícitamente si se decide autorizarlo.

### Datos Iniciales (Seeds)

Al iniciar, la app crea automáticamente:
- **Superadmin:** usuario `admin` / contraseña `admin1234`
- **Configuración global tipada:** `tax_rate` (18), `link_ttl_minutes` (30), `show_product_photos_in_pdf` (`true`)
- **Configuración auxiliar:** `site_title`, `site_subtitle`

Las semillas son idempotentes: un arranque limpio crea colecciones, índices y datos iniciales; reinicios posteriores no duplican ni la configuración global ni el superadministrador. En una base externa compartida o productiva, configura `DEFAULT_ADMIN_USERNAME`, `DEFAULT_ADMIN_PASSWORD` y `DEFAULT_ADMIN_EMAIL` **antes del primer arranque**. Cambiar esas variables después no rota un usuario existente; la rotación posterior debe realizarse mediante la gestión de usuarios.

## Referencia API

### Autenticación
| Método | Ruta | Auth | Descripción |
|--------|------|------|-------------|
| POST | `/api/v1/auth/login` | — | Login → JWT token |
| GET | `/api/v1/auth/me` | Bearer | Datos del usuario actual |

### Usuarios
| Método | Ruta | Auth | Descripción |
|--------|------|------|-------------|
| GET | `/api/v1/users/` | Bearer | Listar usuarios |
| POST | `/api/v1/users/` | Bearer | Crear usuario |
| DELETE | `/api/v1/users/{id}` | Bearer | Eliminar usuario |

### Categorías
| Método | Ruta | Auth | Descripción |
|--------|------|------|-------------|
| GET | `/api/v1/categories/` | — | Listar categorías (`?active_only=true`) |
| GET | `/api/v1/categories/{id}` | — | Obtener categoría |
| POST | `/api/v1/categories/` | Bearer | Crear categoría (slug auto) |
| PUT | `/api/v1/categories/{id}` | Bearer | Actualizar categoría |
| DELETE | `/api/v1/categories/{id}` | Bearer | Eliminar categoría |

### Productos
| Método | Ruta | Auth | Descripción |
|--------|------|------|-------------|
| GET | `/api/v1/products/` | — | Listar todos los productos (sin filtros) |
| GET | `/api/v1/products/{id}` | — | Obtener producto (con categorías y colores) |
| GET | `/api/v1/products/search` | — | Búsqueda y filtrado de productos (ver parámetros abajo) |
| POST | `/api/v1/products/` | ****** Crear producto (acepta `colors`, `description`, `brand`, `tags`, `category_ids`; retorna 422 si algún category_id es inválido) |
| PUT | `/api/v1/products/{id}` | ****** Actualizar producto (acepta `colors`, `description`, `brand`, `tags`, `category_ids`; retorna 422 si algún category_id es inválido) |
| DELETE | `/api/v1/products/{id}` | Bearer | Eliminar producto |
| PUT | `/api/v1/products/{id}/colors` | Bearer | Gestionar colores del producto (máx 6) |
| POST | `/api/v1/products/{id}/image` | ****** Subir una imagen (PNG/JPEG/WebP, max 2MB, hasta 10 por producto; persiste URL pública en Supabase) |
| DELETE | `/api/v1/products/{id}/images/{filename}` | ****** Eliminar una imagen específica por basename sin cambiar el contrato del endpoint |
| POST | `/api/v1/products/import` | Bearer | Importar desde Excel (.xlsx) |

#### Búsqueda y filtrado — `GET /api/v1/products/search`

Todos los parámetros son opcionales y combinables (filtros acumulativos AND).

| Parámetro | Tipo | Descripción |
|-----------|------|-------------|
| `q` | string | Búsqueda parcial por subcadena (case-insensitive) en nombre, SKU y tags |
| `sku` | string | Filtro exacto por código SKU |
| `category_id` | string | Filtro por ObjectId de categoría; retorna 422 si el valor no es un ObjectId válido |
| `category_slug` | string | Filtro por slug de categoría (se resuelve internamente a `category_id`) |
| `tags` | list[string] | Filtro por tags con lógica OR (ejemplo: `?tags=metal&tags=madera`) |
| `min_price` | float | Precio mínimo (inclusive) |
| `max_price` | float | Precio máximo (inclusive) |
| `page` | int | Página (default: 1, mínimo: 1) |
| `limit` | int | Resultados por página (default: 20, rango: 1-100) |
| `sort_by` | enum | Ordenamiento: `name_asc`, `name_desc`, `price_asc`, `price_desc` (default: `name_asc`) |

**Ejemplos:**
```
# Solo categoría
GET /api/v1/products/search?category_slug=pisos

# Texto + categoría + rango de precios
GET /api/v1/products/search?q=porcelanato&category_slug=pisos&min_price=10&max_price=50

# Solo rango de precios, ordenado por precio
GET /api/v1/products/search?min_price=5&max_price=100&sort_by=price_asc

# Paginado
GET /api/v1/products/search?page=2&limit=12

# Filtrar por tags (OR)
GET /api/v1/products/search?tags=metal&tags=madera

# Búsqueda parcial + filtro por tags (AND)
GET /api/v1/products/search?q=tornillo&tags=metal
```

**Respuesta:** `PaginatedResponse<ProductResponse>`
```json
{
  "items": [ ... ],
  "total": 45,
  "page": 1,
  "limit": 12,
  "pages": 4
}
```

Si envías `category_ids` inválidos al crear o actualizar productos, o un `category_id` malformado en búsqueda, la API responde `422` en lugar de propagar un error interno.

### Presupuestos
| Método | Ruta | Auth | Descripción |
|--------|------|------|-------------|
| GET | `/api/v1/budgets/` | No (público) | Listar y filtrar presupuestos con paginación |
| POST | `/api/v1/budgets/` | No (público) | Crear presupuesto y vincular cliente por documento cuando exista |
| GET | `/api/v1/budgets/{uuid}/admin` | Bearer | Obtener detalle administrativo, incluso si expiró |
| PUT | `/api/v1/budgets/{uuid}` | Bearer | Actualizar cliente, ítems o método de pago y recalcular montos |
| DELETE | `/api/v1/budgets/{uuid}` | Bearer | Eliminar físicamente el presupuesto |
| GET | `/api/v1/budgets/{uuid}` | — | Obtener presupuesto por UUID4 (422 si UUID inválido, 410 si expiró) |
| GET | `/api/v1/budgets/{uuid}/pdf` | No | Descargar PDF (422 UUID inválido, 404 si no existe, 410 si expira) |
| GET | `/api/v1/budgets/{uuid}/whatsapp-share` | — | Obtener enlace canónico `wa.me` (422 UUID inválido, 404/410 según vigencia) |

El listado y la creación pública no requieren JWT. El listado acepta `q`, `client_id`, `from`, `to`, `is_expired`, `page` y `limit`. La respuesta usa el contrato paginado `{items, total, page, limit, pages}` y ordena los presupuestos más recientes primero. La edición, eliminación y consulta del detalle administrativo continúan requiriendo autenticación.

Ejemplo de payload `POST /api/v1/budgets/`:

```json
{
  "client_info": {
    "nombres": "Cliente Demo",
    "apellidos": "Pérez",
    "direccion": "Calle 1 #2-3",
    "documento": "12345678",
    "email": "cliente@test.com",
    "compania": "Empresa Demo",
    "observaciones": "Entregar en horario comercial"
  },
  "payment_method": "Transferencia",
  "items": [
    {
      "sku": "BGT-001",
      "quantity": 1
    }
  ]
}
```

`nombres` es el único dato obligatorio de `client_info`. Cuando `documento` está informado, se normaliza y se crea o actualiza un cliente reutilizable; el presupuesto conserva además una copia histórica en `client_info`. Sin documento no se crea cliente. `payment_method` se valida al crear y actualizar; si se omite al crear, se guarda como `null`.

Ejemplo de respuesta `GET /api/v1/budgets/{uuid}/whatsapp-share`:

```json
{
  "whatsapp_url": "https://wa.me/?text=Empresa%3A%20Mi%20Empresa%0AC%C3%B3digo%3A%20BM-20260828-AB12%0ATotal%3A%20%24123.45%0ALink%3A%20http%3A%2F%2Flocalhost%3A8000%2Fpresupuesto%2F550e8400-e29b-41d4-a716-446655440000"
}
```

### Clientes
| Método | Ruta | Auth | Descripción |
|--------|------|------|-------------|
| GET | `/api/v1/clients/` | Bearer | Buscar clientes por texto, estado y paginación |
| POST | `/api/v1/clients/` | Bearer | Crear cliente; documento único cuando está informado |
| GET | `/api/v1/clients/{id}` | Bearer | Obtener cliente |
| PUT | `/api/v1/clients/{id}` | Bearer | Actualizar cliente sin modificar snapshots históricos |
| DELETE | `/api/v1/clients/{id}` | Bearer | Desactivar cliente mediante borrado lógico |

### Dashboard
| Método | Ruta | Auth | Descripción |
|--------|------|------|-------------|
| GET | `/api/v1/dashboard/metrics` | Bearer | Métricas UTC de presupuestos para el dashboard |

Acepta `from`, `to` y `top_limit`. Sin rango usa los últimos 30 días; el máximo permitido es 366 días. Devuelve conteos del día, semana ISO y mes actuales, serie diaria con días vacíos en cero, clientes únicos/recurrentes, productos más cotizados y distribución por método de pago. Los importes representan cotizaciones, no ventas confirmadas.

### Configuración Global
| Método | Ruta | Auth | Descripción |
|--------|------|------|-------------|
| GET | `/api/v1/config/` | — | Listar configuración |
| GET | `/api/v1/config/global` | — | Obtener configuración global tipada |
| PUT | `/api/v1/config/global` | Requerida | Actualizar configuración global tipada |
| GET | `/api/v1/config/payment-methods` | — | Listar métodos de pago dinámicos |
| POST | `/api/v1/config/payment-methods` | Requerida | Agregar método de pago dinámico |
| DELETE | `/api/v1/config/payment-methods/{method_name}` | Requerida | Eliminar método de pago dinámico |
| POST | `/api/v1/config/logo` | Requerida | Subir logo explícito (solo PNG/JPG) a `media/branding` en Supabase |
| GET | `/api/v1/config/{key}` | — | Obtener config por clave |
| PUT | `/api/v1/config/{key}` | Requerida | Actualizar config; `site_logo` y `site_icon` solo aceptan referencias administradas y deben cargarse mediante sus endpoints multipart |
| POST | `/api/v1/config/branding/{key}` | Requerida | Subir branding compatible (`site_logo`, `site_icon`) a `media/branding` manteniendo el endpoint |
| DELETE | `/api/v1/config/branding/{key}` | Requerida | Eliminar logo o icono |

### Frontend Web
| Ruta | Descripción |
|------|-------------|
| `/` | Catálogo público con búsqueda, filtros y carrito |
| `/admin/login` | Login de administrador |
| `/admin` | Dashboard admin (productos, categorías, usuarios, config, import) |
| `/presupuesto/{uuid}` | Vista HTML del presupuesto (link con expiración) |
| `/presupuesto/{uuid}/pdf` | Descarga PDF del presupuesto (retorna 410 si expira) |

## Manual Funcional

### Login (`/admin/login`)
1. Ingresar con `admin` / `admin1234` (o credenciales creadas)
2. El token JWT se guarda en localStorage (8h de duración)
3. Todas las rutas admin verifican autenticación automáticamente

### Catálogo (`/`)
- **Búsqueda:** barra con debounce (300ms) que busca en MongoDB text index
- **Filtros laterales:** categoría, rango de precios, ordenamiento
- **Tarjetas:** imagen, badges de categoría, selector de colores, marca, descripción, SKU, precio, controles de cantidad
- **Carrito lateral:** subtotal, impuesto, total, formulario de cliente (color seleccionado visible)
- **Presupuesto:** modal con detalle completo + acciones (ver, PDF, WhatsApp)

### Dashboard Admin (`/admin`)
- **Productos:** CRUD con imagenes (hasta 10), tags normalizados, descripcion, marca, selector de categorias, gestion de colores (hasta 6), thumbnail en tabla
- **Categorías:** CRUD con slug auto-generado
- **Usuarios:** Crear/eliminar administradores
- **Configuración:** Editar impuesto, expiración de links, título, subtítulo, logo e icono del sitio
- **Importar:** Carga masiva desde Excel (.xlsx)

## Tests

```bash
# Instalar dependencias de test
pip install pytest httpx pytest-asyncio

# Ejecutar tests (requiere MongoDB en localhost:27017)
pytest tests/ -v
```

Los tests usan una BD separada (`budget_maker_test`) que se elimina al finalizar.

## Notas Técnicas

- Los links de presupuesto toman el TTL vigente al momento de creación (`link_ttl_minutes`) y no cambian retroactivamente.
- Los identificadores públicos `code` y `uuid` tienen índice único en MongoDB para evitar duplicados persistentes.
- `code` mantiene el formato comercial `BM-YYYYMMDD-XXXX`; si hay colisión se reintenta de forma acotada.
- Todas las rutas públicas por UUID validan el formato en la frontera HTTP y rechazan UUID inválidos con 422.
- Los montos de cotización se congelan para lectura histórica. Una edición administrativa explícita de ítems los recalcula con el catálogo y el impuesto vigentes, sin renovar identificadores ni expiración.
- La generación de PDF aplica branding en servidor (`site_logo`, `site_title`, `site_subtitle`) y no depende de JavaScript cliente.
- El render de PDF usa `base_url` absoluto del proyecto detectado por módulo (no depende del directorio actual de arranque).
- El enlace de WhatsApp se genera en backend con formato canónico `https://wa.me/?text={url_encoded_text}` e incluye empresa, código, total y link temporal.
- La visibilidad de fotos en PDF está gobernada por `show_product_photos_in_pdf`; si está en `false`, se oculta la columna completa.
- La resolución de imágenes para PDF se consulta por lote de SKU para evitar patrón `N+1` durante el render.
- En rutas de descarga PDF (`/api/v1/budgets/{uuid}/pdf` y `/presupuesto/{uuid}/pdf`) los presupuestos expirados retornan HTTP 410.
- Los uploads nuevos de productos se almacenan en Supabase Storage (`products`) y persisten `image_urls` públicas absolutas.
- Logo y favicon nuevos se almacenan en Supabase Storage (`media/branding`) con URLs públicas absolutas.
- `uploads/products/` y `uploads/branding/` permanecen montados solo para compatibilidad con referencias legacy previas al despliegue cloud.
- Formatos de imagen permitidos: PNG, JPEG, WebP para productos; PNG/JPG para logo y PNG/JPEG/WebP/SVG/ICO para favicon. Tamaño máximo: 2MB
- Cada producto soporta entre 0 y 10 imagenes; la API responde `image_urls` con URLs absolutas sin requerir SDK Supabase en frontend.
- Cada producto soporta entre 0 y 15 tags; el backend los normaliza a minusculas y sin espacios laterales
- WeasyPrint requiere `pydyf==0.11.*` (incompatibilidad con 0.12+)
- MongoDB text index en `Product.name` para búsqueda full-text
- Las categorías tienen relación M2M con productos vía `category_ids`
- Los productos soportan hasta 6 colores (`colors: [{name, hex}]`); el primero es el default
- Los productos tienen campos opcionales `description` (texto libre) y `brand` (marca)
- Al crear presupuesto, cada item registra `color_name` y `color_hex` del color seleccionado
- El slug de categoría se genera automáticamente con `python-slugify`

## Importación Excel

El archivo `.xlsx` debe tener estas columnas (primera fila como headers):

| nombre | sku | costo | unidad | moneda | categoría (opcional) | descripción (opcional) | marca (opcional) | colores (opcional) | tags (opcional) |
|--------|-----|-------|--------|--------|---------------------|----------------------|-----------------|--------------------|--------------------|
| Producto A | SKU-001 | 25.50 | unidad | USD | pisos,acabados | Porcelanato premium | MarcaX | Rojo:#FF0000,Azul:#0000FF | metal, industrial |

**Regla de colisión:** Si el SKU ya existe → actualiza. Si no → crea.

**Tags:** Columna opcional. Separar múltiples tags por comas. Se normalizan a minúsculas, se eliminan duplicados y se limitan a 15 por producto.

## Script de asignación masiva de metadatos de catálogo

Para poblar rápidamente productos existentes con **marca inventada**, **categorías aleatorias**, **colores** y **tags**, usa:

```bash
python scripts\bulk_assign_product_catalog_metadata.py
```

Opciones disponibles:

- `--seed <int>`: fija la semilla para obtener resultados reproducibles.
- `--dry-run`: simula la asignación sin escribir cambios en MongoDB.

Comportamiento:
- Crea (si no existen) 10 categorías base inventadas.
- Recorre todos los productos de la colección `products`.
- Asigna a cada producto:
  - 1 marca aleatoria,
  - 1 a 3 categorías aleatorias (`category_ids`),
  - 1 a 3 colores con nombre + hex,
  - 3 a 6 tags aleatorios.

## Backfill de clientes históricos

Para asociar presupuestos existentes con la colección `clients` usando el documento normalizado:

```bash
python scripts\backfill_budget_clients.py --dry-run
python scripts\backfill_budget_clients.py --batch-size 100
```

El modo `--dry-run` informa cuántos clientes y asociaciones produciría sin persistir cambios. El proceso es idempotente, omite presupuestos sin documento y nunca modifica `client_info`, montos, UUID ni expiración.

## Colores de Producto

- Cada producto soporta de 0 a 6 colores con nombre descriptivo + codigo hexadecimal
- Gestion desde el formulario admin (color picker + nombre) o via endpoint `PUT /api/v1/products/{id}/colors`
- Tambien importables desde Excel (columnas opcionales: `categoria`, `descripcion`, `marca`, `colores`)
- En el catalogo, el usuario selecciona un color antes de agregar al carrito (default: primer color)
- El color seleccionado aparece en: vista HTML del presupuesto, PDF descargable, texto WhatsApp y modal de confirmacion

## Contrato de tags e imagenes de producto

### Payload de creacion/actualizacion

```json
{
  "name": "Tornillo galvanizado",
  "sku": "TOR-001",
  "cost": 1.25,
  "tags": ["ferreteria", " galvanizado "]
}
```

- `tags`: lista opcional de 0 a 15 valores. El backend elimina espacios laterales, descarta vacios y normaliza a minusculas.
- `images`: no se envia en JSON; se administra via `POST /api/v1/products/{id}/image`.

### Respuesta de producto

```json
{
  "id": "66cf00000000000000000001",
  "name": "Tornillo galvanizado",
  "sku": "TOR-001",
  "cost": 1.25,
  "unit": "unidad",
  "currency": "USD",
  "image_urls": [
    "https://tu-proyecto.supabase.co/storage/v1/object/public/products/66cf00000000000000000001/ab12cd34ef56ab78cd90ef12ab34cd56.png"
  ],
  "tags": ["ferreteria", "galvanizado"],
  "category_ids": [],
  "categories": [],
  "colors": []
}
```
