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
├── uploads/products/                # Imágenes de productos (montado como volumen)
├── Dockerfile
└── docker-compose.yml
```

**Principios:** Clean Architecture, DI, async everywhere, SOLID.

## Despliegue

### Requisitos
- Docker + Docker Compose

### Iniciar

```bash
docker-compose up --build
```

### Servicios

| Servicio | URL |
|----------|-----|
| Aplicación | http://localhost:8000 |
| Swagger UI | http://localhost:8000/docs |
| mongo-express | http://localhost:8081 |

### Variables de Entorno

| Variable | Default | Descripción |
|----------|---------|-------------|
| `MONGO_URI` | `mongodb://mongodb:27017` | URI de MongoDB |
| `MONGO_DB_NAME` | `budget_maker` | Nombre de la BD |
| `JWT_SECRET_KEY` | `change-me-in-production` | Secreto JWT (cambiar en producción) |
| `JWT_ALGORITHM` | `HS256` | Algoritmo JWT |
| `JWT_EXPIRE_MINUTES` | `480` | Expiración del token (8h) |
| `UPLOAD_DIR` | `uploads/products` | Directorio de imágenes |

### Datos Iniciales (Seeds)

Al iniciar, la app crea automáticamente:
- **Superadmin:** usuario `admin` / contraseña `admin1234`
- **Configuración global tipada:** `tax_rate` (18), `link_ttl_minutes` (30), `show_product_photos_in_pdf` (`true`)
- **Configuración auxiliar:** `site_title`, `site_subtitle`

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
| POST | `/api/v1/products/` | ****** Crear producto (acepta `colors`, `description`, `brand`, `tags`) |
| PUT | `/api/v1/products/{id}` | ****** Actualizar producto (acepta `colors`, `description`, `brand`, `tags`) |
| DELETE | `/api/v1/products/{id}` | Bearer | Eliminar producto |
| PUT | `/api/v1/products/{id}/colors` | Bearer | Gestionar colores del producto (máx 6) |
| POST | `/api/v1/products/{id}/image` | ****** Subir una imagen (PNG/JPEG/WebP, max 2MB, hasta 10 por producto) |
| DELETE | `/api/v1/products/{id}/images/{filename}` | ****** Eliminar una imagen especifica |
| POST | `/api/v1/products/import` | Bearer | Importar desde Excel (.xlsx) |

#### Búsqueda y filtrado — `GET /api/v1/products/search`

Todos los parámetros son opcionales y combinables (filtros acumulativos AND).

| Parámetro | Tipo | Descripción |
|-----------|------|-------------|
| `q` | string | Búsqueda de texto libre (usa MongoDB text index sobre `name`) |
| `sku` | string | Filtro exacto por código SKU |
| `category_id` | string | Filtro por ObjectId de categoría |
| `category_slug` | string | Filtro por slug de categoría (se resuelve internamente a `category_id`) |
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

### Presupuestos
| Método | Ruta | Auth | Descripción |
|--------|------|------|-------------|
| GET | `/api/v1/budgets/` | — | Listar presupuestos |
| POST | `/api/v1/budgets/` | Bearer | Crear presupuesto |
| GET | `/api/v1/budgets/{uuid}` | — | Obtener presupuesto por UUID |

### Configuración Global
| Método | Ruta | Auth | Descripción |
|--------|------|------|-------------|
| GET | `/api/v1/config/` | — | Listar configuración |
| GET | `/api/v1/config/global` | — | Obtener configuración global tipada |
| PUT | `/api/v1/config/global` | Requerida | Actualizar configuración global tipada |
| GET | `/api/v1/config/payment-methods` | — | Listar métodos de pago dinámicos |
| POST | `/api/v1/config/payment-methods` | Requerida | Agregar método de pago dinámico |
| DELETE | `/api/v1/config/payment-methods/{method_name}` | Requerida | Eliminar método de pago dinámico |
| POST | `/api/v1/config/logo` | Requerida | Subir logo explícito (solo PNG/JPG) |
| GET | `/api/v1/config/{key}` | — | Obtener config por clave |
| PUT | `/api/v1/config/{key}` | Requerida | Actualizar config |
| POST | `/api/v1/config/branding/{key}` | Requerida | Subir branding legacy (`site_logo`, `site_icon`) |
| DELETE | `/api/v1/config/branding/{key}` | Requerida | Eliminar logo o icono |

### Frontend Web
| Ruta | Descripción |
|------|-------------|
| `/` | Catálogo público con búsqueda, filtros y carrito |
| `/admin/login` | Login de administrador |
| `/admin` | Dashboard admin (productos, categorías, usuarios, config, import) |
| `/presupuesto/{uuid}` | Vista HTML del presupuesto (link con expiración) |
| `/presupuesto/{uuid}/pdf` | Descarga PDF del presupuesto |

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
- Las imágenes se almacenan en `uploads/products/` (montado como volumen Docker)
- Formatos de imagen permitidos: PNG, JPEG, WebP. Tamaño máximo: 2MB
- Cada producto soporta entre 0 y 10 imagenes; la API responde `image_urls` con URLs absolutas
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

| nombre | sku | costo | unidad | moneda | categoría (opcional) | descripción (opcional) | marca (opcional) | colores (opcional) |
|--------|-----|-------|--------|--------|---------------------|----------------------|-----------------|--------------------|
| Producto A | SKU-001 | 25.50 | unidad | USD | pisos,acabados | Porcelanato premium | MarcaX | Rojo:#FF0000,Azul:#0000FF |

**Regla de colisión:** Si el SKU ya existe → actualiza. Si no → crea.

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
    "http://localhost:8000/uploads/products/66cf00000000000000000001_ab12cd34.png"
  ],
  "tags": ["ferreteria", "galvanizado"],
  "category_ids": [],
  "categories": [],
  "colors": []
}
```

## Variables de Entorno

| Variable | Default | Descripción |
|----------|---------|-------------|
| `MONGO_URI` | `mongodb://mongodb:27017` | URI de MongoDB |
| `MONGO_DB_NAME` | `budget_maker` | Nombre de la BD |
| `JWT_SECRET_KEY` | `change-me-in-production` | Secreto JWT (cambiar en producción) |
| `JWT_ALGORITHM` | `HS256` | Algoritmo JWT |
| `JWT_EXPIRE_MINUTES` | `480` | Expiración del token (8h) |
| `UPLOAD_DIR` | `uploads/products` | Directorio de imágenes |

### Datos Iniciales (Seeds)

Al iniciar, la app crea automáticamente:
- **Superadmin:** usuario `admin` / contraseña `admin1234`
- **Configuración global tipada:** `tax_rate` (18), `link_ttl_minutes` (30), `show_product_photos_in_pdf` (`true`)
- **Configuración auxiliar:** `site_title`, `site_subtitle`
