# Epic 2 Context: Generación y distribución de cotizaciones profesionales

<!-- Compiled from planning artifacts. Edit freely. Regenerate with compile-epic-context if planning docs change. -->

## Goal
Esta épica habilita la emisión de cotizaciones completas, persistentes y listas para compartirse con clientes sin retrabajo manual. Su propósito es que el administrador pueda generar un presupuesto formal con datos del cliente, montos congelados, identificadores públicos seguros, vencimiento temporal, salida PDF profesional y un enlace directo para WhatsApp, de modo que la propuesta comercial sea clara, confiable y fácil de distribuir desde cualquier dispositivo.

## Stories
- Story 2.1: Creación de presupuesto con datos de cliente y método activo
- Story 2.2: Identificación pública y expiración del presupuesto
- Story 2.3: Cálculo inmutable de montos de cotización
- Story 2.4: Generación de PDF profesional configurable
- Story 2.5: Enlace de WhatsApp para compartir cotización

## Requirements & Constraints
La creación del presupuesto debe capturar y persistir, como parte del documento emitido, el número de documento del cliente, su dirección, su correo electrónico y un método de pago seleccionado de la lista activa de métodos configurados para el negocio. El método de pago no puede aceptarse si ya no está activo; en ese caso la API debe rechazar la operación con HTTP 422.

Cada presupuesto nuevo debe nacer con dos identificadores públicos distintos: un código legible y único con formato `BM-YYYYMMDD-XXXX`, y un UUID4 no adivinable para exposición en URLs temporales. Además, debe calcularse y almacenarse `expires_at` usando el TTL vigente del negocio en el momento de creación, porque la vigencia del enlace forma parte del contrato visible para compartir cotizaciones.

La validez temporal no es decorativa: cualquier acceso público a una cotización vencida debe bloquearse. El comportamiento esperado es devolver HTTP 410 o 404 cuando el recurso ya expiró, para evitar reutilización de enlaces fuera de la ventana configurada.

Los montos comerciales deben calcularse una sola vez al emitir la cotización. Subtotal, impuesto y total se derivan de los ítems seleccionados y de la tasa de impuesto vigente en ese instante, y luego quedan persistidos dentro del presupuesto. Cambios futuros en precios de catálogo o en configuración global no deben alterar cotizaciones ya emitidas.

La salida PDF debe ser apta para envío al cliente: incluir membrete completo en todas las páginas, respetar la preferencia global de mostrar u ocultar fotos de productos y reajustar el layout cuando las fotos no se muestren. La implementación debe proteger la legibilidad visual del documento y sostener tiempos de generación acotados bajo carga ordinaria.

La compartición por WhatsApp debe resolverse como generación de URL, no como integración directa con la red de mensajería. La respuesta debe seguir el formato `https://wa.me/?text={url_encoded_text}` e incluir, dentro del texto codificado, el nombre de la empresa, el código legible de la cotización, el total y el link temporal de visualización.

Como restricción de alcance, esta épica no incorpora autenticación, pasarela de pagos real ni edición histórica del presupuesto después de emitido. El presupuesto se trata como una pieza de salida comercial estable y de solo lectura una vez generado.

## Technical Decisions
La implementación debe respetar Clean Architecture, manteniendo separadas las responsabilidades entre dominio, casos de uso, infraestructura y presentación. La lógica de creación, validación, renderizado y compartición de cotizaciones no debe mezclarse con detalles de transporte HTTP ni con persistencia concreta.

La épica depende de una configuración global única y tipada que provee la tasa de impuesto, el TTL de links, la visibilidad de fotos en PDF, el branding del membrete y la lista de métodos de pago activos. Esa configuración se consume al momento de crear y presentar la cotización, por lo que su lectura debe integrarse como dependencia explícita de los casos de uso.

El documento `Budget` debe persistir no solo referencias básicas, sino también los datos calculados que fijan el estado histórico de la cotización: identificadores públicos, fecha de expiración, método de pago elegido y montos finales. La lectura posterior de una cotización no debe depender de recalcular contra el catálogo ni de reinterpretar reglas globales cambiantes.

Los identificadores públicos y las fechas críticas deben seguir convenciones estrictas: UUID4 para exposición segura, código legible para operación comercial y timestamps en UTC para evitar ambigüedad al evaluar vencimiento o serializar respuestas.

La arquitectura del proyecto exige asincronía de extremo a extremo en handlers, repositorios y casos de uso, con inyección de dependencias mediante `Depends` en FastAPI. Los servicios de renderizado PDF y otras integraciones externas deben vivir en infraestructura, manteniendo a la capa de aplicación enfocada en reglas de negocio.

En la generación de PDF, la presencia de fotos debe resolverse antes del render final: si la configuración indica ocultarlas, no deben insertarse en el HTML intermedio y el documento debe reorganizar sus columnas sin degradar claridad. El render debe apoyarse en WeasyPrint como motor de salida.

## UX & Interaction Patterns
El flujo principal para el administrador es lineal y orientado a velocidad: seleccionar productos, completar datos del cliente, elegir un método de pago válido, generar la cotización y obtener inmediatamente un recurso compartible. La experiencia debe reducir pasos manuales posteriores, especialmente al entregar el PDF y el enlace listo para mensajería.

La experiencia del cliente se apoya en un enlace temporal fácil de abrir desde el móvil. Al acceder, debe encontrar una cotización clara con identidad visual de la empresa, desglose de precios, impuestos, datos de contacto y método de pago, además de la opción de descargar el PDF como respaldo formal.

La compartición por WhatsApp debe sentirse de un clic: el mensaje preformateado resume la cotización sin exigir edición manual y dirige al cliente al enlace temporal correcto. Esto es clave para el escenario de uso móvil definido para el producto.

En la salida visual, el membrete debe mantener consistencia de marca en todas las páginas y las fotos de producto deben ser opcionales sin romper la lectura. Cuando no se muestren, el diseño debe aprovechar mejor el espacio disponible para priorizar descripción e importes.

## Cross-Story Dependencies
Story 2.1 establece el presupuesto base con datos del cliente y método de pago válido; sin ese núcleo documental, el resto de historias no tiene una entidad sobre la cual fijar identificadores, montos, PDF o enlaces de compartición.

Story 2.2 y Story 2.3 definen el contrato persistente que consumen Story 2.4 y Story 2.5. El PDF y el enlace de WhatsApp dependen de que el presupuesto ya tenga código legible, UUID público, vencimiento calculado y total final congelado.

La épica depende directamente de entregables de la épica 1: métodos de pago activos para validar creación, tasa de impuesto y TTL para calcular montos y expiración, y branding/configuración visual para producir PDFs coherentes con la identidad del negocio.

También existe una dependencia funcional con el catálogo de productos, porque la cotización se construye sobre ítems seleccionados previamente. Aunque esta épica no amplía el catálogo, necesita que sus datos sean confiables para que los cálculos y la presentación final tengan valor comercial.
