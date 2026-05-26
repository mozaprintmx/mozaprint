# Glosario Mozaprint

> Términos del negocio que Claude Code debe entender para escribir código correcto.

## Productos y catálogo

**Artículo promocional**: producto que se vende a empresas para regalar, identificar marca o entregar en eventos. Plumas, tazas, agendas, mochilas, USB, gorras, playeras, etc.

**SKU**: identificador único del producto. En Odoo es `default_code`. Mozaprint usa SKUs de tres proveedores con sus propios formatos.

**Variante**: combinación específica de atributos de un producto. Ej. "Pluma metálica color azul" es una variante de "Pluma metálica" (template).

**Atributo**: característica configurable de un producto. Color, material, capacidad, tamaño. En Odoo es `product.attribute`.

**Categoría (eCommerce)**: agrupación de productos para el catálogo. Ej. "Escritura", "Bebidas", "Textil". En Odoo es `product.public.category`.

**Categoría (interna)**: agrupación contable de productos. En Odoo es `product.category`.

**Optional product**: producto que se sugiere automáticamente cuando se agrega otro al carrito. Ej. si compras una agenda, sugerimos un bolígrafo a juego.

**Accessory product**: producto sugerido en el checkout. Más sutil que optional.

## Personalización

**Personalización**: acción de imprimir/grabar/bordar el logo del cliente en el producto. Es lo que diferencia a Mozaprint de un retail normal.

**Técnica de personalización**: método específico de marcado. Las principales:
- **Serigrafía**: tinta sobre superficie plana. Costo por tinta + setup. Buena para plumas, bolsas, vasos.
- **Bordado**: hilo sobre tela. Costo por puntada + setup. Para gorras, mochilas, polos.
- **Sublimación**: tinta que penetra el material con calor. Para tazas, playeras blancas/claras.
- **Láser / Grabado**: quema una capa del material. Para metal, madera. Color del fondo del material.
- **Tampografía**: tipo de serigrafía para superficies curvas o pequeñas. Para plumas, llaveros.
- **DTF (Direct to Film)**: impresión que se transfiere con calor. Para textil de colores.
- **Vinyl / Vinil**: corte de adhesivo que se aplica con calor. Para textil simple.
- **UV**: impresión digital UV de alta resolución. Versátil, costo alto.

**Tintas**: número de colores distintos en la impresión. Más tintas = más costoso. Setup por tinta extra.

**Posiciones**: cuántos lugares del producto se imprimen. Ej. logo al frente y atrás = 2 posiciones. Multiplica costo.

**Área de impresión**: superficie máxima disponible para imprimir. Limita qué tamaño de logo cabe. Medida en cm².

**Setup / Set-up**: costo único por orden, independiente de la cantidad. Cubre la preparación de la maquinaria (pantalla de serigrafía, archivo de bordado, etc.). Típicamente $200-$800 MXN según técnica.

**MOQ (Minimum Order Quantity)**: cantidad mínima que cobra un proveedor o una técnica. Si pides menos no es rentable. Típicamente 50-100 piezas para serigrafía, 24 para bordado.

**Prueba virtual / Mockup**: imagen digital que muestra cómo se vería el producto con el logo del cliente. Se manda al cliente para aprobación antes de producir.

**Arte / Archivo de arte**: el logo del cliente en formato listo para producir. Ideal: AI, EPS, PDF vectorial. Aceptable: PNG alta resolución. Problemático: JPG, foto de WhatsApp.

**Vectorizar**: convertir un logo rasterizado (JPG/PNG) a vectorial. Se cobra al cliente como servicio extra.

## Comercial y pricing

**Pricelist**: lista de precios. En Odoo se modela con reglas (`pricelist.item`). Mozaprint tiene pricelist público y pricelist mayoreo.

**Promoción / Promotion**: descuento condicional. En Odoo es `loyalty.program` tipo promotion. Mozaprint usa promotions con Minimum Purchase para los tiers $3000/$5000/$10000.

**Cotización / Quote**: propuesta de venta enviada al cliente con productos, cantidades y precios. En Odoo es `sale.order` en estado `draft` o `sent`.

**Orden / Pedido**: cotización confirmada por el cliente. En Odoo es `sale.order` en estado `sale`.

**Anticipo**: porcentaje del total que el cliente paga antes de empezar producción. Mozaprint pide típicamente 50%.

**Vigencia de cotización**: cuántos días la cotización mantiene los precios. Típicamente 7-15 días.

**Subsección de cotización**: agrupación visual de líneas en la cotización. Ej. "Producto base", "Personalización", "Logística". En Odoo 19 es nativo.

## Operación

**Lead**: contacto que mostró interés pero aún no es cliente. En Odoo es `crm.lead` con `type='lead'`.

**Opportunity / Oportunidad**: lead calificado que tiene potencial real de cerrar. En Odoo es `crm.lead` con `type='opportunity'`.

**Lead scoring**: puntuación 0-100 que indica qué tan probable es que el lead cierre. Mozaprint usa AI.

**Lead source / Fuente**: de dónde llegó el lead. Web, WhatsApp, referido, evento, etc.

**Pipeline**: secuencia de etapas comerciales. Ej. Nuevo → Contactado → Cotizado → Negociación → Ganado/Perdido.

**Stage / Etapa**: paso específico del pipeline.

**Activity / Actividad**: tarea con fecha asignada a un usuario. Ej. "Llamar al cliente", "Enviar cotización". En Odoo es `mail.activity`.

**Sales team / Equipo de ventas**: agrupación de vendedores con su pipeline propio.

## Proveedores

**Proveedor**: empresa de la cual Mozaprint compra los productos para revender. Tres principales:
- **Promo Opción** (Promoopcion): proveedor grande, catálogo amplio.
- **4Promotional**: proveedor especializado.
- **Innovation Line** (Innovationline): proveedor con productos premium tipo agendas, escritura.

**API de proveedor**: cada uno tiene su propia API REST que Mozaprint consume para sincronizar catálogo y precios.

**Sync de proveedor**: proceso periódico (nocturno) que actualiza Odoo con los datos más recientes del proveedor.

**Cost (costo)**: lo que Mozaprint paga al proveedor. En Odoo es `standard_price` o se modela vía `product.supplierinfo`.

**Markup / Margen**: diferencia entre precio de venta y costo. Típicamente 40-100% según producto.

**Drop-shipping**: cuando el proveedor envía directo al cliente final. Mozaprint algunas veces lo hace.

**PO (Purchase Order)**: orden de compra de Mozaprint hacia el proveedor. En Odoo es `purchase.order`.

## WhatsApp y comunicación

**WA Business app**: aplicación móvil de WhatsApp para negocios. Lo que el equipo usa hoy.

**WA Cloud API**: API REST de Meta para enviar/recibir WhatsApp programáticamente.

**Coexistence**: modo que permite usar la app móvil + Cloud API simultáneamente con el mismo número.

**Plantilla / Template**: mensaje pre-aprobado por Meta que se puede enviar fuera de ventana de 24h. Tiene placeholders ({{1}}, {{2}}).

**Ventana de 24h / Service window**: período en el que el cliente nos escribió. Dentro de esta ventana, podemos enviar mensajes libres sin plantilla.

**Free-form / Mensaje libre**: mensaje con texto arbitrario, sólo permitido dentro de ventana 24h.

**Utility template**: plantilla transaccional (cotización, status). Costo bajo por mensaje.

**Marketing template**: plantilla promocional. Costo más alto.

**WABA (WhatsApp Business Account)**: cuenta de WA Business en Meta Business Manager.

**Phone Number ID**: identificador del número en la WABA, distinto del número telefónico mismo.

## Agente IA

**Agente / AI Agent**: sistema que recibe mensajes, decide respuestas, llama tools. En este proyecto se llama "Moza".

**Tool / Function**: capacidad específica del agente. Ej. `search_product`, `create_lead`. Implementadas como workflows de n8n.

**System prompt**: instrucciones fijas del agente. Define identidad, reglas, comportamiento.

**Context / Contexto**: información que se le pasa al modelo en cada llamada. Incluye system prompt + historial reciente + datos del cliente.

**Confidence**: qué tan seguro está el agente de su respuesta. Si baja, escala a humano.

**Escalado / Escalation**: pasar la conversación de AI a humano.

**Opt-out**: cliente pide hablar con humano. Palabra clave: "asesor".

**Knowledge base / KB**: documentos que el agente puede consultar. FAQs, políticas, catálogo.

**RAG (Retrieval Augmented Generation)**: técnica donde el agente busca info relevante antes de responder. Usado para knowledge base.

**Turno**: cada par mensaje cliente → respuesta agente.

**Human-in-the-loop / HITL**: workflow donde el AI hace borrador pero humano confirma antes de ejecutar.

## Términos técnicos del stack

**Odoo Online**: hospedaje SaaS de Odoo, manejado por Odoo S.A. Sin acceso a addons/.

**Odoo.sh**: hospedaje semi-cloud con acceso a addons/. No es lo que usa Mozaprint.

**Studio**: módulo de Odoo Enterprise que permite extender modelos sin código. Es lo que se usa para campos `x_` custom.

**Automation Rule**: regla declarativa que dispara acciones cuando algo pasa. UI en Studio.

**Server Action**: acción ejecutable, puede ser Python sandbox. Más flexible que Automation Rule.

**AI Field (Studio)**: campo computado por AI con prompt definido en Studio. Nuevo en Odoo 19.

**JSON-2 API**: nueva API REST de Odoo, reemplazo de XML-RPC. Usa bearer token, endpoints `/json2/<model>/<method>`.

**Sandbox Python**: entorno Python restringido donde corren Server Actions. Sin imports arbitrarios.

**n8n**: orquestador de workflows open-source. Nodes visuales, JavaScript en function nodes.

**Workflow**: flujo en n8n con trigger + nodes encadenados.

**Webhook**: endpoint HTTP que recibe eventos. n8n los expone fácilmente.

**MCP (Model Context Protocol)**: protocolo de Anthropic para que Claude llame tools. No usado directamente en V1 (usamos n8n como wrapper).
