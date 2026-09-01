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
