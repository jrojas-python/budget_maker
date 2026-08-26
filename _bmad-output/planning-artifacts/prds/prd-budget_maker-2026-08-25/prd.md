---
title: PRD — Budget Maker API
status: final
created: 2026-08-25
updated: 2026-08-26
---

# PRD: Budget Maker API

## 0. Propósito del Documento
Este Documento de Requisitos de Producto (PRD) define las capacidades del backend y la API REST del servicio **Budget Maker API**, la cual sirve de motor a un frontend desacoplado (ubicado en `C:/Users/JesusRojas/Documents/pyfiles/budget_maker_frontent`). Está dirigido al equipo de ingeniería (backend y frontend) para asegurar que las nuevas features de la fase de Lanzamiento (almacenamiento de imágenes, membrete dinámico en PDF, métodos de pago dinámicos, tags y búsqueda optimizada) se construyan con la consistencia y escalabilidad necesarias.

## 1. Visión
**Budget Maker** es un catálogo digital que permite a los administradores de comercios crear y compartir cotizaciones profesionales de productos de manera ágil. El sistema resuelve el problema del envío manual de cotizaciones desestructuradas facilitando la selección de productos y la generación instantánea de PDFs profesionales y links efímeros (con caducidad controlada) listos para enviar vía WhatsApp. 

La visión para esta versión de **Lanzamiento** es convertir la prueba de concepto inicial en un producto robusto, preparado para migrar a almacenamiento en la nube y listo para producción, ofreciendo un panel de control flexible y una experiencia de cotización sumamente personalizable (con o sin fotos, membrete de marca propia y métodos de pago seleccionables).

## 2. Target User

### 2.1 Jobs To Be Done (JTBD)
* **Funcional (Administrador):** Cargar productos (individualmente o por lote vía Excel), registrar precios, impuestos y tags, y generar presupuestos formales rápidamente para enviarlos al cliente.
* **Funcional (Cliente):** Visualizar de forma clara los productos seleccionados, el costo detallado, el membrete de la empresa emisora y las opciones de pago disponibles para proceder a la compra.
* **Emocional (Administrador):** Transmitir profesionalismo y formalidad a sus clientes mediante cotizaciones bien presentadas, con membrete y logotipo de su marca.
* **Contextual (Administrador):** Poder cotizar desde cualquier dispositivo (interfaz móvil a través de WhatsApp) y personalizar el formato del presupuesto en PDF de forma instantánea si el cliente no desea o no requiere imágenes de los productos.

### 2.2 Key User Journeys

* **UJ-1. Carlos (Administrador) personaliza el catálogo y genera un presupuesto.**
  * **Contexto:** Carlos gestiona una tienda minorista y necesita cotizar rápidamente.
  * **Estado inicial:** Autenticado en el frontend administrador de Budget Maker.
  * **Ruta:**
    1. Carlos entra al menú de Configuración del administrador.
    2. Sube el logo de la empresa (formato PNG o JPG) y define el título ("Smart Store") y subtítulo ("Tecnología a tu alcance") del membrete, y añade "Efectivo" y "Transferencia" a los métodos de pago dinámicos.
    3. Va a la sección de catálogo, busca "librer" en el buscador de productos y selecciona "Librería pequeña y roja" (que tiene tags "madera", "oficina").
    4. Crea un presupuesto: ingresa el documento, dirección y correo electrónico del cliente, selecciona "Transferencia" como método de pago y activa la casilla para incluir imágenes en el PDF.
  * **Clímax:** Carlos hace clic en "Generar". El sistema retorna el PDF con el membrete repetido en cada cabecera de página (sin exceder el 15% de la altura de la página), el método de pago seleccionado, las fotos de los productos incluidas, y le entrega la URL acortada de WhatsApp.
  * **Resolución:** El presupuesto queda almacenado en estado activo con un TTL de 30 minutos y Carlos lo envía al cliente vía WhatsApp.

* **UJ-2. Ana (Cliente) recibe y visualiza el presupuesto.**
  * **Contexto:** Ana solicitó una cotización de muebles para su nueva oficina.
  * **Estado inicial:** Recibe un mensaje de WhatsApp con la URL del presupuesto en su dispositivo móvil.
  * **Ruta:**
    1. Ana presiona el link del mensaje.
    2. Visualiza en su navegador la página del presupuesto con el membrete de "Smart Store", el desglose de precios, los impuestos calculados, sus datos de contacto y el método de pago "Transferencia".
    3. Descarga el archivo PDF adjunto.
  * **Clímax:** Ana descarga un PDF limpio y profesional que incluye la foto de la librería y el membrete de la tienda repetido en las páginas correspondientes.
  * **Resolución:** Ana procede a pagar a través de los datos de transferencia mostrados y el presupuesto expira automáticamente una vez alcanzado el TTL.

## 3. Glosario
* **Presupuesto (o Cotización):** Entidad transaccional con identificador público (UUID4) y código serializado `BM-YYYYMMDD-XXXX` que agrupa productos seleccionados, cantidades, impuestos, datos del cliente y un método de pago.
* **Link Efímero (o Link Temporal):** Enlace web generado para visualizar el Presupuesto, válido únicamente por un periodo determinado de tiempo (`TTL`).
* **Membrete:** Bloque visual superior (logotipo, nombre y subtítulo) configurado por el Administrador que aparece en el PDF y el visor HTML del Presupuesto.
* **Método de Pago Dinámico:** Modalidad de pago gestionable por el Administrador (ej. VISA, Efectivo) asignable individualmente a cada Presupuesto.
* **Tag (o Etiqueta):** Metadato corto asociado a un Producto que permite agruparlo y buscarlo (ej. "calzado", "madera").
* **Búsqueda Parcial:** Método de consulta que busca coincidencias parciales por caracteres (subcadenas) sobre SKU, Nombre de Producto o Tags.

## 4. Features

### 4.1 Configuración Global y Membrete
**Descripción:** El Administrador puede parametrizar las reglas de cálculo de presupuestos (porcentaje de impuestos), el tiempo de vida de los links compartidos y personalizar la identidad de marca de los PDFs que se generan. Esta configuración se persiste en MongoDB y se aplica de forma dinámica. Realiza UJ-1.

**Functional Requirements:**

#### FR-1: Gestión de Parámetros del Catálogo
El Administrador puede actualizar los siguientes valores globales de la aplicación a través de la API:
- `% de Impuesto` (`tax_rate`)
- `TTL del Link Temporal` (`link_ttl_minutes`)
- `Visibilidad de fotos en PDF` (`show_product_photos_in_pdf`)

**Consecuencias (testables):**
- La API expone un endpoint `PUT /api/v1/config/` para actualizar la configuración.
- Los valores actualizados se reflejan inmediatamente en la base de datos Beanie bajo el modelo `GlobalConfig`.
- Las cotizaciones generadas a partir de la actualización aplican los nuevos valores.

#### FR-2: Personalización del Membrete
El Administrador puede cargar los datos del membrete corporativo:
- `Logo de la empresa` (ruta local guardada en `/uploads/` tras subir un archivo de imagen en formato PNG o JPG únicamente).
- `Nombre/Título`
- `Subtítulo`

**Consecuencias (testables):**
- Endpoint `POST /api/v1/config/logo` acepta archivos de imagen PNG/JPG y los guarda en `/uploads/`. Cualquier otro formato de archivo retorna HTTP 400 Bad Request.
- El PDF generado por WeasyPrint incluye la imagen del logotipo escalada correctamente, el título y subtítulo en la cabecera. La altura máxima del membrete no excederá el 15% del alto total de la página en la hoja de estilos CSS.

#### FR-3: Métodos de Pago Dinámicos
El Administrador puede gestionar de forma dinámica una lista de métodos de pago válidos (ej. "VISA", "Mastercard", "Transferencia", "Efectivo").

**Consecuencias (testables):**
- Endpoint `GET /api/v1/config/payment-methods` retorna los métodos de pago.
- Endpoints `POST` y `DELETE` para agregar y remover métodos de la lista.
- Si un método de pago se remueve, los presupuestos preexistentes asociados a él mantienen su registro histórico de pago, pero no se puede seleccionar para nuevos presupuestos.

---

### 4.2 Catálogo de Productos e Importación Masiva
**Descripción:** Gestión de los productos que componen el catálogo. Los productos ahora soportan múltiples imágenes asociadas y etiquetas (tags) para categorización y filtrado rápido. Permite la importación por lotes para evitar la carga manual repetitiva. Realiza UJ-1.

**Functional Requirements:**

#### FR-4: Modelo de Producto Ampliado
El Administrador puede registrar productos con campos adicionales:
- `Imágenes` (lista de strings que guardan rutas locales en `/uploads/` o URLs externas)
- `Tags` (lista de strings, ej: `["calzado", "cuero"]`)

**Consecuencias (testables):**
- Un producto puede contener de 0 a 10 imágenes y de 0 a 15 tags.
- El esquema Pydantic de salida (`ProductResponse`) incluye campos `images` y `tags`.
- [ASSUMPTION: Al crear o editar un producto por la API REST, la subida de imágenes se gestiona a través de un endpoint de carga multimedia separado (`/api/v1/media/upload`) que almacena el archivo físicamente en `/uploads` y retorna la ruta relativa para ser guardada en la lista `images` del producto].

#### FR-5: Importación Masiva de Catálogo (Excel)
El Administrador puede subir un archivo de Excel (`.xlsx`) para actualizar masivamente el catálogo mediante una lógica de `upsert`.

**Consecuencias (testables):**
- Si el `SKU` de una fila de Excel ya existe en MongoDB, se actualizan sus datos (nombre, costo, unidad, moneda y tags).
- Si el `SKU` no existe, se crea un producto nuevo.
- La columna de Excel llamada `tags` (o `etiquetas`) debe contener strings separados por comas (ej. `"calzado, cuero, moda"`). El backend dividirá el texto por comas y eliminará los espacios sobrantes para almacenar una lista limpia en base de datos.
- [ASSUMPTION: Las imágenes no se manejan en la importación masiva por Excel en la versión v1 debido al formato tabular; estas se administran exclusivamente mediante la API REST individual/interfaz].

---

### 4.3 Generación de Presupuestos (Budgets)
**Descripción:** Creación y almacenamiento de presupuestos personalizados para clientes. Cada presupuesto asocia los datos del cliente, el método de pago específico y los productos seleccionados con cálculo matemático automático y expiración controlada por el TTL global. Realiza UJ-1 y UJ-2.

**Functional Requirements:**

#### FR-6: Creación de Presupuesto con Campos de Cliente y Métodos de Pago
El Administrador puede generar un presupuesto ingresando:
- `Número de documento` (DNI/RUT/RFC) del cliente.
- `Dirección` física del cliente.
- `Correo electrónico` del cliente.
- `Método de pago` (seleccionado obligatoriamente de la lista de métodos de pago dinámicos configurados en FR-3).

**Consecuencias (testables):**
- El modelo `Budget` de Beanie persiste estos datos.
- Si el método de pago enviado no está activo en la configuración global, la API retorna HTTP 422 Unprocessable Entity.

#### FR-7: Serialización y Expiración del Presupuesto
Cada presupuesto genera dos identificadores al ser creado:
- Un código legible único basado en la fecha y un serial alfanumérico aleatorio: `BM-YYYYMMDD-XXXX` (XXXX en mayúsculas).
- Un identificador de base de datos UUID4 público y no adivinable para uso en URLs temporales.
- El presupuesto almacena un campo `expires_at` calculado como: `created_at` + `link_ttl_minutes` (tomado de la configuración global actual).

**Consecuencias (testables):**
- Intentar acceder al endpoint público de visualización de un presupuesto cuyo `expires_at` sea menor al tiempo del servidor actual retorna un código HTTP 410 Gone o 404 Not Found.
- El código legible serializado es único en la colección.

#### FR-8: Lógica de Cálculos de Costos
El sistema calcula de manera automática los montos del presupuesto:
- `Subtotal` = Σ(costo_producto * cantidad)
- `Impuesto` = Subtotal * (% de impuesto configurado en `GlobalConfig` en el momento de creación)
- `Total` = Subtotal + Impuesto

**Consecuencias (testables):**
- Los montos calculados se persisten directamente en el documento del presupuesto para evitar que cambios de costos en el catálogo modifiquen cotizaciones pasadas.

---

### 4.4 Buscador Optimizado de Productos
**Descripción:** Motor de búsqueda rápida de productos para facilitar la cotización interactiva. Soporta coincidencias de subcadenas parciales y búsqueda cruzada por SKU, tags y nombre. Realiza UJ-1.

**Functional Requirements:**

#### FR-9: Coincidencia Parcial y Multi-campo
Cualquier usuario o el Administrador puede buscar productos ingresando un término de búsqueda. El buscador debe procesar la consulta buscando coincidencias parciales por caracteres (sin requerir coincidencia de palabra completa).

**Consecuencias (testables):**
- Si el término es "librer", el sistema retorna el producto "Librería pequeña y roja".
- La búsqueda busca de manera simultánea en: Nombre de Producto, SKU y Tags.

#### FR-10: Filtrado por Múltiples Tags (Lógica OR)
La API permite enviar una lista de tags en la consulta para filtrar los productos del catálogo.

**Consecuencias (testables):**
- Si se envían los tags `["calzado", "cuero"]`, la consulta implementa una lógica OR y retorna productos que tengan la etiqueta "calzado", "cuero", o ambas.

---

### 4.5 Salidas: PDF y Compartición en WhatsApp
**Descripción:** Formateo y distribución de los presupuestos generados. Soporta WeasyPrint para salida en PDF con membrete y fotos opcionales, y preparación de link codificado para WhatsApp. Realiza UJ-1 y UJ-2.

**Functional Requirements:**

#### FR-11: Generación de PDF con Membrete y Visibilidad de Fotos
El sistema compila un archivo PDF a través de WeasyPrint. El PDF debe:
- Mostrar el membrete (logo, título y subtítulo) en la cabecera de **todas las páginas** si el documento tiene más de una página.
- Mostrar la foto del producto al lado de cada ítem de la cotización si `show_product_photos_in_pdf` es verdadero.
- Ocultar la columna de fotos y reajustar el ancho de las celdas del listado de ítems si `show_product_photos_in_pdf` es falso.

**Consecuencias (testables):**
- La API expone un endpoint `GET /api/v1/budgets/{uuid}/pdf` que retorna el archivo binario PDF.
- Si se cambia la opción a falso, las fotos no se insertan en el HTML intermedio de Jinja2 antes de enviarse a WeasyPrint.

#### FR-12: Enlace Formateado de WhatsApp
La API expone un endpoint que genera y entrega la URL para compartir en WhatsApp.

**Consecuencias (testables):**
- URL de salida sigue el formato: `https://wa.me/?text={url_encoded_text}`.
- El texto codificado incluye el nombre de la empresa, el código legible `BM-YYYYMMDD-XXXX`, el total de la cotización y el link de visualización temporal.

---

## 5. Non-Goals (Explicit)
* No se implementará autenticación ni control de accesos (roles) para esta iteración de Lanzamiento (se delega a fases futuras de seguridad).
* El backend no realiza el envío directo de mensajes a la red de WhatsApp (no integra APIs de Meta/WhatsApp Business); solo genera la URL de redirección.
* La importación masiva desde Excel no soporta la carga física de imágenes (solo se configuran por tags de texto del Excel e imágenes vía API REST / administrador individual).
* No se incluye historial de modificaciones de presupuestos; el presupuesto es de lectura única tras su generación.

---

## 6. MVP Scope

### 6.1 In Scope
* CRUD completo de productos con soporte para múltiples imágenes (locales) y tags.
* Buscador de productos con coincidencia parcial y filtrado OR por múltiples tags.
* CRUD de métodos de pago dinámicos.
* Configuración global (tax, TTL, flag de fotos, membrete con subida de logotipo).
* Modelo de presupuestos con campos de cliente (documento, dirección, email), método de pago, código serializado y UUID4 temporal.
* Generación de PDF mediante WeasyPrint con cabecera repetitiva y fotos opcionales.
* Generación de enlace formateado para WhatsApp.
* Persistencia local de imágenes en `/uploads` montada sobre volumen Docker.
* Importación masiva de catálogo vía Excel, con soporte para importar etiquetas separadas por comas.

### 6.2 Out of Scope for MVP
* Almacenamiento en nube (S3/Azure Storage) — [NOTE FOR PM: Requerido en v2 para escalabilidad multi-región].
* Autenticación / Roles (Admin vs. Cliente) — [NOTE FOR PM: Requerido para restringir la API antes del lanzamiento al público].
* Integración real con pasarelas de pago (Stripe, Paypal) — los métodos de pago registrados son solo de carácter informativo.

---

## 7. Success Metrics

**Primary**
* **SM-1:** Tiempo de generación de presupuestos. El backend debe compilar el HTML, PDF (con imágenes opcionales) y retornar la respuesta en menos de 1.8 segundos bajo carga ordinaria. Validates FR-11.
* **SM-2:** Coincidencia en búsqueda parcial. El 100% de las búsquedas con términos parciales de 3 o más caracteres deben retornar los productos correspondientes sin errores de latencia. Validates FR-9.

**Counter-metrics (do not optimize)**
* **SM-C1:** Tamaño del PDF. No se debe reducir la calidad del PDF (compresión excesiva de imágenes de membrete o producto) al punto de degradar la legibilidad de la marca para optimizar el tiempo de renderizado de SM-1.

---

## 8. Open Questions
*No hay preguntas abiertas pendientes.*

---

## 9. Assumptions Index
* **[ASSUMPTION en FR-4]:** Al crear o editar un producto por la API REST, la subida de imágenes se gestiona a través de un endpoint de carga multimedia separado (`/api/v1/media/upload`) que almacena el archivo físicamente en `/uploads` y retorna la ruta relativa para ser guardada en la lista `images` del producto.
* **[ASSUMPTION en FR-5]:** Las imágenes no se manejan en la importación masiva por Excel en la versión v1 debido al formato tabular; estas se administran exclusivamente mediante la API REST individual/interfaz.
