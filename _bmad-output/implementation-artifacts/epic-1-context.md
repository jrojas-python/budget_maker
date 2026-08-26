# Epic 1 Context: Administración de catálogo y configuración comercial

<!-- Compiled from planning artifacts. Edit freely. Regenerate with compile-epic-context if planning docs change. -->

## Goal
Esta épica habilita el núcleo operativo para cotizar con velocidad y consistencia: un administrador puede configurar reglas comerciales globales, mantener la identidad de marca, gestionar métodos de pago activos y operar un catálogo enriquecido (imágenes, tags, búsqueda e importación masiva). Su impacto es directo en la calidad y rapidez de las cotizaciones, porque estandariza datos y reglas antes de la generación del presupuesto, reduce trabajo manual y evita fricciones al preparar propuestas comerciales repetibles.

## Stories
- Story 1.1: Configuración global tipada del negocio
- Story 1.2: Membrete y métodos de pago dinámicos
- Story 1.3: Catálogo de productos con imágenes y tags
- Story 1.4: Importación masiva por Excel con upsert
- Story 1.5: Búsqueda parcial y filtrado OR por tags

## Requirements & Constraints
La épica debe entregar una administración centralizada y segura de parámetros que afectan cotizaciones nuevas: tasa de impuesto, vigencia temporal de links y visibilidad de fotos en PDF. Estos parámetros no son opcionales ni dispersos; deben mantenerse coherentes para que la experiencia de cotización no dependa de configuraciones manuales por presupuesto.

La personalización de marca debe contemplar carga de logo únicamente en PNG/JPG, almacenamiento local en la ruta de uploads y uso posterior en salidas de cotización; formatos inválidos deben rechazarse con error de cliente. Además, el membrete debe conservar legibilidad y presencia consistente en documentos generados.

La gestión de métodos de pago debe ser dinámica (alta/baja/consulta) sin romper el histórico: opciones desactivadas no pueden seleccionarse en nuevas operaciones, pero sí deben preservarse en registros existentes que ya las usaron.

El catálogo debe soportar productos enriquecidos con listas de imágenes y tags dentro de límites operativos definidos para evitar sobrecarga de datos por ítem. La importación masiva por Excel debe acelerar mantenimiento del catálogo mediante upsert por SKU y normalización de tags separados por coma; en esta versión, la carga de imágenes no forma parte del flujo de importación tabular.

La búsqueda debe priorizar velocidad operativa de cotización: coincidencias parciales sobre nombre/SKU/tags y filtrado por múltiples tags con lógica OR, manteniendo precisión para términos de longitud útil. Como criterio de éxito del producto, las búsquedas parciales de 3+ caracteres deben resolver coincidencias correctas sin degradar la experiencia.

A nivel de alcance, esta épica no incorpora autenticación/autorización ni pasarela de pagos real; su foco es preparación de catálogo y reglas comerciales para que la siguiente épica pueda generar cotizaciones sobre bases confiables.

No se localizaron artefactos dedicados de product brief ni un contrato UX independiente (por ejemplo, DESIGN.md/EXPERIENCE.md) dentro del directorio de planificación; se compiló contexto UX con la información funcional disponible en PRD.

## Technical Decisions
La implementación se rige por Clean Architecture, separando dominio, casos de uso, infraestructura y presentación para mantener bajo acoplamiento entre reglas comerciales, persistencia y endpoints.

La configuración comercial se modela como un documento único y tipado (GlobalConfig), evitando estructuras clave-valor dispersas y asegurando consistencia de tipos para impuesto, TTL, branding, visibilidad de fotos y métodos de pago.

El backend debe mantenerse asíncrono de extremo a extremo (handlers, repositorios y casos de uso), con inyección de dependencias en FastAPI para componer repositorios y casos de uso sin mezclar capas.

El almacenamiento de imágenes se desacopla mediante rutas relativas persistidas en producto y un endpoint de carga multipart dedicado; esta decisión preserva compatibilidad con una migración futura a almacenamiento cloud sin rediseñar el modelo de catálogo.

La búsqueda parcial se implementa con expresiones regulares case-insensitive sobre SKU, nombre y tags, y el filtrado por múltiples tags aplica OR explícito. Esta decisión responde al objetivo de búsqueda por subcadenas y a la necesidad de recuperación rápida durante la selección de productos.

Convenciones transversales relevantes: snake_case en artefactos Python, type hints modernos (3.10+), logger por módulo y documentación técnica en español.

## UX & Interaction Patterns
El flujo principal de administrador en esta épica es: configurar identidad y reglas comerciales, mantener métodos de pago, buscar productos por fragmentos de texto/tags y preparar catálogo para cotización inmediata. La interacción debe minimizar pasos y cambios de contexto entre configuración y operación.

La búsqueda está diseñada para uso “en caliente” durante preparación de presupuestos: tolera entradas parciales (sin palabra completa), combina campos en una sola consulta mental del usuario y permite descubrir productos por atributos semánticos (tags), no solo por SKU exacto.

La importación por lote complementa el flujo manual: se usa para cargas grandes y mantenimiento recurrente, mientras la edición individual conserva precisión en campos enriquecidos como imágenes.

La identidad de marca (logo, título, subtítulo) se trata como configuración visible para el cliente final; por ello, el sistema debe favorecer consistencia visual y validación temprana de archivos para evitar resultados rotos en documentos compartidos.

## Cross-Story Dependencies
Story 1.1 establece la base de reglas globales consumidas por el resto de la plataforma (en especial impuestos, TTL y flags visuales), por lo que condiciona la coherencia operativa aguas abajo.

Story 1.2 depende de la disponibilidad de configuración global para integrar branding y métodos de pago dentro del mismo marco administrativo; además, sus métodos activos impactan directamente la validación de creación de presupuestos en la épica 2.

Story 1.3 define la estructura enriquecida del producto que habilita Story 1.5 (búsqueda por tags y coincidencias parciales) y también condiciona el valor práctico de Story 1.4 al importar/actualizar datos por SKU.

Story 1.4 y Story 1.5 se retroalimentan: la calidad de normalización en importación afecta la precisión del buscador, especialmente en tags y consistencia textual del catálogo.

La épica 1 completa desbloquea la épica 2: sin configuración comercial válida, catálogo confiable y métodos de pago activos, la generación de cotizaciones no puede sostenerse de forma estable.
