---
stepsCompleted:
  - step-01-validate-prerequisites
  - step-02-design-epics
  - step-03-create-stories
  - step-04-final-validation
inputDocuments:
  - C:/Users/JesusRojas/Documents/pyfiles/budget_maker/_bmad-output/planning-artifacts/prds/prd-budget_maker-2026-08-25/prd.md
  - C:/Users/JesusRojas/Documents/pyfiles/budget_maker/_bmad-output/planning-artifacts/architecture/architecture-budget_maker-2026-08-26/ARCHITECTURE-SPINE.md
---

# budget_maker - Epic Breakdown

## Overview

This document provides the complete epic and story breakdown for budget_maker, decomposing the requirements from the PRD, UX Design if it exists, and Architecture requirements into implementable stories.

## Requirements Inventory

### Functional Requirements

FR1: El sistema debe permitir actualizar configuración global (`tax_rate`, `link_ttl_minutes`, `show_product_photos_in_pdf`) mediante `PUT /api/v1/config/`, persistiendo cambios en `GlobalConfig` y aplicándolos a nuevas cotizaciones.  
FR2: El sistema debe permitir personalizar membrete (logo, título, subtítulo) y cargar logo PNG/JPG vía `POST /api/v1/config/logo`, guardando en `/uploads/` y devolviendo HTTP 400 para formatos inválidos.  
FR3: El sistema debe permitir gestionar métodos de pago dinámicos (consultar, crear, eliminar) y preservar histórico en presupuestos existentes cuando un método se desactiva.  
FR4: El sistema debe soportar productos con `images` (0-10) y `tags` (0-15), exponiéndolos en `ProductResponse`.  
FR5: El sistema debe permitir importación masiva `.xlsx` con upsert por SKU, normalización de tags separados por coma y sin carga de imágenes por Excel.  
FR6: El sistema debe crear presupuestos con datos de cliente (documento, dirección, email) y método de pago activo; métodos inactivos deben retornar HTTP 422.  
FR7: El sistema debe generar código legible único `BM-YYYYMMDD-XXXX`, UUID4 público no adivinable y `expires_at = created_at + link_ttl_minutes`.  
FR8: El sistema debe calcular y persistir `subtotal`, `impuesto` y `total` en creación del presupuesto para evitar recalcular históricos.  
FR9: El sistema debe permitir búsqueda parcial por subcadenas en nombre, SKU y tags.  
FR10: El sistema debe soportar filtrado por múltiples tags con lógica OR.  
FR11: El sistema debe generar PDF vía WeasyPrint con membrete en todas las páginas, mostrar/ocultar fotos según configuración y exponer `GET /api/v1/budgets/{uuid}/pdf`.  
FR12: El sistema debe generar enlace de WhatsApp en formato `https://wa.me/?text={url_encoded_text}` con empresa, código de cotización, total y link temporal.

### NonFunctional Requirements

NFR1: La generación de cotización (HTML + PDF + respuesta API) debe completarse en menos de 1.8 segundos bajo carga ordinaria.  
NFR2: El 100% de las búsquedas parciales con términos de 3+ caracteres deben devolver coincidencias correctas sin errores de latencia.  
NFR3: No se debe degradar la legibilidad visual del PDF por optimizaciones agresivas de compresión de imágenes.  
NFR4: Los identificadores públicos de presupuestos deben ser UUID4 no adivinables para minimizar exposición por enumeración.  
NFR5: Las fechas de negocio críticas (como expiración) deben manejarse en UTC e interoperar con formato ISO 8601 cuando aplique.

### Additional Requirements

- Mantener Clean Architecture con separación estricta entre `domain`, `application`, `infrastructure`, `api` y `web`.
- Modelar configuración global como documento único tipado (`GlobalConfig`) y no como clave-valor disperso.
- Implementar búsqueda parcial con `$regex` case-insensitive sobre SKU, nombre y tags; para múltiples tags usar lógica OR.
- Persistir rutas relativas de imágenes (`/uploads/...`) en `Product.images` y desacoplar almacenamiento para futura migración cloud.
- Preservar inmutabilidad de costos/impuestos en `Budget` al momento de creación (sin recálculo contra catálogo en lectura).
- Validar caducidad de cotización con `expires_at < utcnow()` y responder con error HTTP 410/404 en visor público.
- Aplicar asincronía end-to-end (`async/await`) en handlers, repositorios y casos de uso.
- Mantener logger por módulo (`logger = logging.getLogger(__name__)`) y documentación técnica en español.
- Mantener seed estructural del proyecto (`app/api`, `app/application`, `app/domain`, `app/infrastructure`, `web`, `tests`) como guía de implementación.
- Excluir de esta iteración autenticación/autorización y pasarela de pagos real (diferido explícitamente en arquitectura/PRD).

### UX Design Requirements

No se encontró contrato UX (`DESIGN.md` + `EXPERIENCE.md`) en `planning-artifacts`, por lo que no se extraen UX-DR en esta iteración.

### FR Coverage Map

FR1: Epic 1 - Configuración global de negocio (impuestos, TTL, visibilidad de fotos).  
FR2: Epic 1 - Personalización de membrete y carga de logo válida.  
FR3: Epic 1 - Gestión de métodos de pago dinámicos con preservación histórica.  
FR4: Epic 1 - Modelo de producto ampliado con imágenes y tags.  
FR5: Epic 1 - Importación masiva Excel con upsert por SKU y normalización de tags.  
FR6: Epic 2 - Creación de presupuesto con datos de cliente y método de pago activo.  
FR7: Epic 2 - Identificación pública (UUID4/código legible) y expiración temporal.  
FR8: Epic 2 - Cálculo y persistencia inmutable de subtotal, impuesto y total.  
FR9: Epic 1 - Búsqueda parcial multi-campo por subcadenas.  
FR10: Epic 1 - Filtro por múltiples tags con lógica OR.  
FR11: Epic 2 - Generación de PDF con membrete y control de fotos por configuración.  
FR12: Epic 2 - Generación de URL de WhatsApp con contenido de cotización.

## Epic List

### Epic 1: Administración de catálogo y configuración comercial
Permitir que el administrador configure reglas comerciales y mantenga un catálogo completo, buscable e importable para preparar cotizaciones de forma ágil y consistente.
**FRs covered:** FR1, FR2, FR3, FR4, FR5, FR9, FR10.

### Epic 2: Generación y distribución de cotizaciones profesionales
Permitir crear cotizaciones completas, persistentes y compartibles con ciclo de vida temporal, salida PDF profesional y enlace directo para mensajería al cliente.
**FRs covered:** FR6, FR7, FR8, FR11, FR12.

<!-- Repeat for each epic in epics_list (N = 1, 2, 3...) -->

## Epic 1: Administración de catálogo y configuración comercial

Permitir que el administrador configure reglas comerciales y mantenga un catálogo completo, buscable e importable para preparar cotizaciones de forma ágil y consistente.

### Story 1.1: Configuración global tipada del negocio

As a administrador,
I want gestionar en un único recurso la configuración global (impuestos, TTL y visibilidad de fotos),
So that las cotizaciones nuevas usen reglas consistentes y trazables.
**FRs:** FR1.

**Acceptance Criteria:**

**Given** que existe o no existe documento de configuración global
**When** consulto o actualizo la configuración por API
**Then** el sistema persiste un único documento `GlobalConfig` tipado
**And** los nuevos presupuestos usan inmediatamente los valores actualizados.

### Story 1.2: Membrete y métodos de pago dinámicos

As a administrador,
I want cargar logo válido y administrar métodos de pago,
So that la marca y opciones de cobro sean configurables sin cambios de código.
**FRs:** FR2, FR3.

**Acceptance Criteria:**

**Given** un archivo de logo y operaciones sobre métodos de pago
**When** subo PNG/JPG o gestiono métodos por endpoints de configuración
**Then** el logo se guarda en `/uploads` y la lista de métodos se actualiza dinámicamente
**And** formatos no permitidos retornan HTTP 400.

### Story 1.3: Catálogo de productos con imágenes y tags

As a administrador,
I want crear y editar productos con imágenes y etiquetas,
So that el catálogo represente mejor los productos cotizables.
**FRs:** FR4.

**Acceptance Criteria:**

**Given** datos de producto con listas `images` y `tags`
**When** creo o actualizo un producto
**Then** se persisten rutas relativas de imágenes y tags normalizados
**And** la respuesta incluye ambos campos respetando límites (0-10 imágenes, 0-15 tags).

### Story 1.4: Importación masiva por Excel con upsert

As a administrador,
I want importar catálogo por `.xlsx` con lógica upsert por SKU,
So that pueda actualizar grandes volúmenes de productos rápidamente.
**FRs:** FR5.

**Acceptance Criteria:**

**Given** un archivo Excel válido con SKU y columna de tags
**When** ejecuto la importación
**Then** filas con SKU existente se actualizan y filas nuevas crean productos
**And** la columna de tags se divide por comas y limpia espacios sobrantes.

### Story 1.5: Búsqueda parcial y filtrado OR por tags

As a administrador,
I want buscar por subcadenas en nombre/SKU/tags y filtrar por múltiples tags,
So that encuentre productos en segundos durante la cotización.
**FRs:** FR9, FR10.

**Acceptance Criteria:**

**Given** términos parciales y/o una lista de tags
**When** consulto el buscador de catálogo
**Then** se aplican coincidencias parciales case-insensitive en nombre, SKU y tags
**And** el filtro por múltiples tags usa lógica OR.

<!-- End story repeat -->

## Epic 2: Generación y distribución de cotizaciones profesionales

Permitir crear cotizaciones completas, persistentes y compartibles con ciclo de vida temporal, salida PDF profesional y enlace directo para mensajería al cliente.

### Story 2.1: Creación de presupuesto con datos de cliente y método activo

As a administrador,
I want crear presupuestos con datos del cliente y método de pago válido,
So that pueda emitir cotizaciones formales y cobrables.
**FRs:** FR6.

**Acceptance Criteria:**

**Given** datos de cliente y método de pago seleccionado
**When** creo un presupuesto
**Then** se persisten documento, dirección, email y método de pago
**And** si el método no está activo, la API responde HTTP 422.

### Story 2.2: Identificación pública y expiración del presupuesto

As a administrador,
I want que cada presupuesto tenga código legible, UUID4 público y vencimiento automático,
So that pueda compartirlo de forma segura y temporal.
**FRs:** FR7.

**Acceptance Criteria:**

**Given** un presupuesto nuevo
**When** se genera
**Then** se asigna código único `BM-YYYYMMDD-XXXX` y UUID4 público
**And** se calcula `expires_at` con `created_at + link_ttl_minutes` y se bloquea acceso al expirar (HTTP 410/404).

### Story 2.3: Cálculo inmutable de montos de cotización

As a administrador,
I want que subtotal, impuesto y total se calculen y congelen al crear la cotización,
So that cambios futuros del catálogo no alteren presupuestos emitidos.
**FRs:** FR8.

**Acceptance Criteria:**

**Given** ítems de presupuesto y tasa de impuesto vigente
**When** confirmo la creación de la cotización
**Then** se calculan y persisten subtotal, impuesto y total con las fórmulas definidas
**And** no se recalculan en visualizaciones posteriores.

### Story 2.4: Generación de PDF profesional configurable

As a administrador,
I want generar PDF con membrete y control de fotos por configuración,
So that el cliente reciba una cotización clara y de marca.
**FRs:** FR11.

**Acceptance Criteria:**

**Given** un presupuesto válido y configuración visual
**When** solicito `GET /api/v1/budgets/{uuid}/pdf`
**Then** el PDF incluye membrete en todas las páginas
**And** muestra u oculta fotos según `show_product_photos_in_pdf` sin degradar legibilidad.

### Story 2.5: Enlace de WhatsApp para compartir cotización

As a administrador,
I want obtener un link de WhatsApp con mensaje preformateado,
So that pueda enviar la cotización al cliente en un clic.
**FRs:** FR12.

**Acceptance Criteria:**

**Given** un presupuesto existente
**When** solicito la URL de compartición
**Then** la respuesta usa formato `https://wa.me/?text={url_encoded_text}`
**And** incluye nombre de empresa, código `BM-YYYYMMDD-XXXX`, total y link temporal.
