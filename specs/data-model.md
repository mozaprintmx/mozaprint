# Modelo de datos custom — Mozaprint

> Referencia de campos y modelos custom (Studio) en Odoo. Claude Code consulta esto antes de crear nuevos campos o modificar existentes.

## Reglas de naming

- Todos los campos custom llevan prefijo `x_`
- Nombre en snake_case
- En español o inglés según contexto: `x_proveedor`, `x_tecnica_default`, `x_ai_score`
- Si es many2one, sufijo `_id`: `x_proveedor_id`
- Si es many2many, sufijo `_ids`: `x_servicios_compatibles_ids`
- Si es boolean, prefijo conceptual: `x_es_personalizable`, `x_tiene_arte`

## Extensiones a modelos estándar

### product.template (extendido)

```yaml
x_proveedor_id:
  type: many2one
  comodel: res.partner
  string: "Proveedor"
  help: "Proveedor del que se compra este producto (Promo Opción, 4Promotional, Innovation Line)"
  domain: [['supplier_rank', '>', 0]]

x_proveedor_sku:
  type: char
  string: "SKU del proveedor"
  help: "Código original del producto en el sistema del proveedor"

x_tecnica_default_id:
  type: many2one
  comodel: x_tecnica_personalizacion
  string: "Técnica de personalización default"
  help: "Técnica de impresión sugerida por defecto para este producto"

x_tecnicas_compatibles_ids:
  type: many2many
  comodel: x_tecnica_personalizacion
  string: "Técnicas compatibles"
  help: "Lista de técnicas que se pueden aplicar a este producto"

x_area_max_cm2:
  type: float
  string: "Área máxima de impresión (cm²)"
  help: "Superficie máxima disponible para imprimir el logo"

x_area_dimensiones:
  type: char
  string: "Dimensiones del área"
  help: "Texto descriptivo, ej. '10x10 cm', útil para mostrar al cliente"

x_tiempo_produccion_dias:
  type: integer
  string: "Tiempo de producción (días)"
  help: "Días hábiles desde aprobación de arte hasta producto terminado"

x_requiere_cotizacion:
  type: boolean
  string: "Requiere cotización"
  default: True
  help: "Si está marcado, el botón 'Agregar al carrito' se reemplaza por 'Solicitar cotización' en la ficha"

x_es_servicio_personalizacion:
  type: boolean
  string: "Es servicio de personalización"
  help: "Marcado para productos que son servicios de personalización (no productos físicos)"
```

### product.product (variants, extendido)

```yaml
# Hereda automáticamente los x_ de product.template
# Específicos de variant:

x_color_hex:
  type: char
  string: "Color hex"
  help: "Color HTML para variantes de color, ej. #3B82F6"
  computed_from: attribute_value
```

### crm.lead (extendido)

> **IMPORTANTE — prefijo x_studio_**: La instancia de Odoo Online fuerza el prefijo `x_studio_`
> en todos los campos creados vía Studio. Los nombres técnicos reales difieren de los planeados
> originalmente con prefijo `x_`. Los campos marcados con ✓ **ya existen en producción** con
> su nombre real. Los marcados con ○ son planificados y aún no creados.
> Ver `odoo-extensions/studio-fields.yaml` para el registro completo con fechas.

#### ✓ Creados en producción (2026-06-02)

```yaml
x_studio_collected_qty:
  type: integer
  string: "Cantidad solicitada"
  help: "Cantidad de piezas que pide el cliente"
  # Nombre original planeado: x_collected_qty

x_studio_collected_producto:
  type: char
  string: "Producto solicitado"
  help: "Producto de interés mencionado por el cliente"
  # Reemplaza x_collected_product_sku — se captura nombre/descripción, no SKU técnico

x_studio_collected_personalizacion:
  type: selection
  string: "Lleva personalización"
  selection:
    - [si, "Sí"]
    - [no, "No"]
    - [sin_decidir, "Aún no he decidido"]
  # Campo nuevo, no estaba en el plan original

x_studio_origen_form:
  type: char
  string: "Origen del formulario"
  help: "Clasificador del punto de entrada: Producto / Tienda / Contacto"
  # Campo nuevo, no estaba en el plan original

x_studio_origen_url:
  type: char
  string: "Origen URL"
  help: "URL exacta desde la que se generó el lead (pendiente: definir cómo se llena)"
  # Campo nuevo, no estaba en el plan original
```

#### ○ Planificados (pendiente crear en Odoo)

```yaml
x_studio_origen_canal:
  type: selection
  selection:
    - [whatsapp_ai, "WhatsApp (atendido por AI)"]
    - [whatsapp_human, "WhatsApp (atendido por humano)"]
    - [livechat_ai, "Livechat web (AI)"]
    - [livechat_human, "Livechat web (humano)"]
    - [website_form, "Formulario web"]
    - [email_direct, "Email directo"]
    - [referido, "Referido"]
    - [otro, "Otro"]
  string: "Canal de origen"

x_studio_ai_score:
  type: float
  string: "AI Lead Score (0-100)"
  help: "Puntuación generada por AI evaluando la probabilidad de cierre"

x_studio_ai_score_reasoning:
  type: text
  string: "Razonamiento del AI score"
  help: "Explicación de por qué se asignó este score (generado por AI)"

x_studio_collected_tecnica_id:
  type: many2one
  comodel: x_tecnica_personalizacion
  string: "Técnica solicitada"
  help: "Técnica de personalización que el cliente solicitó"

x_studio_collected_tecnica_no_se:
  type: boolean
  string: "Cliente no sabe la técnica"
  help: "True si el cliente dijo 'no sé, asesórenme'"

x_studio_collected_tiene_arte:
  type: selection
  selection:
    - [si_vectorial, "Sí, formato vectorial (AI/EPS/PDF)"]
    - [si_raster, "Sí, formato raster (PNG/JPG)"]
    - [solo_idea, "Sólo tengo una idea"]
    - [necesito_diseno, "Necesito que diseñen"]
  string: "Estado del arte"

x_studio_collected_fecha_entrega:
  type: date
  string: "Fecha objetivo de entrega"

x_studio_collected_industria:
  type: char
  string: "Industria del cliente"
  help: "Detectada de email o preguntada explícitamente"

x_studio_collected_presupuesto:
  type: selection
  selection:
    - [menor_5k, "Menor a $5,000"]
    - [5k_15k, "$5,000 - $15,000"]
    - [15k_50k, "$15,000 - $50,000"]
    - [mayor_50k, "Mayor a $50,000"]
    - [no_definido, "No definido"]
  string: "Presupuesto aproximado"

x_studio_conversation_summary:
  type: text
  string: "Resumen de conversación AI"
  help: "Resumen generado por AI de la conversación con el cliente"
```

### discuss.channel (extendido)

```yaml
x_ai_mode:
  type: selection
  selection:
    - [auto, "AI atiende automáticamente"]
    - [paused, "Pausado (humano atiende)"]
    - [manual, "Manual (AI no participa)"]
  string: "Modo AI"
  default: auto

x_ai_paused_at:
  type: datetime
  string: "AI pausado el"

x_ai_paused_by_id:
  type: many2one
  comodel: res.users
  string: "AI pausado por"

x_ai_paused_reason:
  type: text
  string: "Razón del pausado"

x_lead_id:
  type: many2one
  comodel: crm.lead
  string: "Lead asociado"

x_partner_phone:
  type: char
  string: "Teléfono del cliente"
  help: "Para conversaciones WhatsApp, el número del cliente"

x_last_ai_response_at:
  type: datetime
  string: "Última respuesta AI"

x_ai_turn_count:
  type: integer
  string: "Turnos del AI en esta conversación"
```

### res.partner (extendido)

> **IMPORTANTE — prefijo x_studio_**: Al igual que en `crm.lead`, los campos creados en `res.partner` vía Studio en Odoo Online tendrán el prefijo `x_studio_`. El campo aquí planificado como `x_no_agente` tendrá nombre técnico real `x_studio_no_agente`.

#### ○ Planificados (pendiente crear en Odoo · Fase 4)

```yaml
x_studio_no_agente:
  type: boolean
  string: "No atender con agente IA"
  default: False
  help: "True para excluir este contacto del agente Moza. Aplica a proveedores, empleados, números internos y cualquier contacto que no deba recibir respuesta automática de WhatsApp."
  # Usada por n8n en el pre-flight check antes de cada mensaje entrante.
  # Los proveedores con supplier_rank > 0 ya quedan excluidos por lógica en n8n
  # sin necesidad de marcar este campo; x_studio_no_agente es para exclusiones
  # adicionales que no se detectan por supplier_rank.
```

---

### sale.order (extendido)

```yaml
x_generated_by_ai:
  type: boolean
  string: "Generado por AI"
  help: "True si la cotización fue armada por el AI Agent"

x_requires_human_approval:
  type: boolean
  string: "Requiere aprobación humana"

x_approval_request_id:
  type: many2one
  comodel: x_approval_request
  string: "Solicitud de aprobación"

x_approval_status:
  type: selection
  selection:
    - [no_aplica, "No aplica"]
    - [pending, "Pendiente"]
    - [approved, "Aprobada"]
    - [rejected, "Rechazada"]
    - [edited, "Editada por humano"]
  string: "Estado de aprobación"
  default: no_aplica

x_customization_cost_source:
  type: selection
  selection:
    - [parametrized, "Parametrizado en sistema"]
    - [manually_approved, "Aprobado manualmente"]
    - [no_aplica, "No aplica"]
  string: "Fuente del costo de personalización"
  default: no_aplica

x_origen_lead_id:
  type: many2one
  comodel: crm.lead
  string: "Lead origen"
```

## Modelos nuevos (custom)

### x_tecnica_personalizacion (nuevo modelo)

Catálogo maestro de técnicas de personalización. Permite extender técnicas sin
modificar selections en múltiples lugares.

```yaml
name:
  type: char
  string: "Nombre"
  required: True
  # Ej: "Serigrafía", "Bordado", "DTF Textil", "DTF UV"

code:
  type: char
  string: "Código técnico"
  required: True
  # Ej: "serigrafia", "bordado", "dtf_textil"
  # Único, usado para referencias programáticas

descripcion:
  type: text
  string: "Descripción para el cliente"
  # Para mostrar en ficha de producto y para que el agente IA explique al cliente

casos_uso_tipicos:
  type: text
  string: "Casos de uso típicos"
  # Ej: "Bolsas, vasos, plumas con áreas planas"

materiales_compatibles:
  type: char
  string: "Materiales compatibles"
  # Ej: "Plástico, metal, vidrio"

materiales_incompatibles:
  type: char
  string: "Materiales incompatibles"
  # Ej: "Tela, cuero"

max_tintas_default:
  type: integer
  string: "Máximo de tintas por default"
  default: 4

requiere_arte_vectorial:
  type: boolean
  string: "Requiere arte vectorial"
  default: True

tiempo_extra_dias:
  type: integer
  string: "Días extra de producción típicos"
  default: 0

active:
  type: boolean
  default: True

sequence:
  type: integer
  string: "Orden de aparición"
  default: 10
```

**Datos seed iniciales** (cargar al crear el modelo):

```yaml
- name: "Serigrafía"
  code: "serigrafia"
  descripcion: "Impresión de tinta sobre superficie. Ideal para producción a volumen."
  casos_uso_tipicos: "Plumas, vasos, bolsas, libretas con superficie plana"
  materiales_compatibles: "Plástico, metal, vidrio, tela rígida"
  max_tintas_default: 4
  requiere_arte_vectorial: True
  sequence: 10

- name: "Tampografía"
  code: "tampografia"
  descripcion: "Similar a serigrafía pero para superficies pequeñas o curvas."
  casos_uso_tipicos: "Plumas, llaveros, USB, productos pequeños"
  materiales_compatibles: "Plástico, metal, cerámica"
  max_tintas_default: 4
  requiere_arte_vectorial: True
  sequence: 20

- name: "Bordado"
  code: "bordado"
  descripcion: "Hilo sobre tela. Acabado premium para productos textiles."
  casos_uso_tipicos: "Gorras, polos, mochilas, toallas"
  materiales_compatibles: "Textil"
  materiales_incompatibles: "Plástico, metal"
  max_tintas_default: 8
  requiere_arte_vectorial: True
  tiempo_extra_dias: 3
  sequence: 30

- name: "DTF Textil"
  code: "dtf_textil"
  descripcion: "Transferencia digital sobre textil. Alta resolución, multicolor sin costo extra."
  casos_uso_tipicos: "Playeras, sudaderas, mochilas con diseños complejos o fotografía"
  materiales_compatibles: "Algodón, poliéster, mezclas textiles"
  max_tintas_default: 999
  requiere_arte_vectorial: False
  sequence: 40

- name: "DTF UV"
  code: "dtf_uv"
  descripcion: "Impresión UV de alta resolución sobre superficies rígidas."
  casos_uso_tipicos: "Plumas, llaveros, USB, productos rígidos con diseños complejos"
  materiales_compatibles: "Plástico, metal, madera, vidrio"
  max_tintas_default: 999
  requiere_arte_vectorial: False
  sequence: 50

- name: "Sublimación"
  code: "sublimacion"
  descripcion: "Tinta que penetra el material con calor. Color permanente."
  casos_uso_tipicos: "Tazas, playeras blancas/claras, mousepads"
  materiales_compatibles: "Cerámica, poliéster, materiales sublimables"
  materiales_incompatibles: "Algodón, materiales oscuros"
  max_tintas_default: 999
  requiere_arte_vectorial: False
  sequence: 60

- name: "Láser / Grabado"
  code: "laser"
  descripcion: "Grabado del material. Color del fondo. Acabado elegante y permanente."
  casos_uso_tipicos: "Plumas metálicas, llaveros metal, productos premium"
  materiales_compatibles: "Metal, madera, acrílico, cuero"
  max_tintas_default: 1
  requiere_arte_vectorial: True
  sequence: 70

- name: "Vinyl"
  code: "vinyl"
  descripcion: "Corte de vinil adhesivo aplicado con calor."
  casos_uso_tipicos: "Textil simple, números, letras de tamaño grande"
  materiales_compatibles: "Textil"
  max_tintas_default: 3
  requiere_arte_vectorial: True
  sequence: 80
```

### x_approval_request (nuevo modelo)

Solicitudes de aprobación humana para costos no parametrizados.

```yaml
name:
  type: char
  string: "Descripción"
  required: True

sale_order_id:
  type: many2one
  comodel: sale.order
  string: "Cotización"
  required: True

channel_id:
  type: many2one
  comodel: discuss.channel
  string: "Conversación WA"

reason:
  type: text
  string: "Razón de aprobación necesaria"

context_json:
  type: text
  string: "Contexto serializado"
  help: "JSON con cliente, producto, técnica, qty, fecha"

requested_at:
  type: datetime
  string: "Solicitado en"
  default: now

responded_at:
  type: datetime
  string: "Respondido en"

responded_by_id:
  type: many2one
  comodel: res.users
  string: "Respondido por"

status:
  type: selection
  selection:
    - [pending, "Pendiente"]
    - [approved, "Aprobada"]
    - [rejected, "Rechazada"]
  default: pending

approved_cost_unit:
  type: float
  string: "Costo unitario aprobado"

approved_setup_cost:
  type: float
  string: "Costo de setup aprobado"

approved_servicio_id:
  type: many2one
  comodel: product.product
  string: "Servicio aplicado"
  help: "Producto servicio que se agregó a la cotización"

notes:
  type: text
  string: "Notas internas"

assigned_user_id:
  type: many2one
  comodel: res.users
  string: "Asignado a"
```

### x_costo_personalizacion (nuevo modelo)

Matriz de costos de personalización por proveedor / técnica / cantidad.

```yaml
name:
  type: char
  string: "Descripción"
  required: True
  # Ej: "Promo Opción - Serigrafía 1 tinta - 100-499 pzas"

tecnica_id:
  type: many2one
  comodel: x_tecnica_personalizacion
  required: True
  string: "Técnica"

proveedor_id:
  type: many2one
  comodel: res.partner
  string: "Proveedor"
  required: True

qty_from:
  type: integer
  string: "Cantidad mínima"
  required: True

qty_to:
  type: integer
  string: "Cantidad máxima"
  # null = sin límite

tintas:
  type: integer
  string: "Número de tintas"
  default: 1

posiciones:
  type: integer
  string: "Número de posiciones"
  default: 1

area_max_cm2:
  type: float
  string: "Área máxima soportada (cm²)"

costo_unit:
  type: float
  string: "Costo unitario (MXN)"
  required: True

costo_setup:
  type: float
  string: "Costo de setup único (MXN)"
  default: 0

fecha_vigencia:
  type: date
  string: "Vigente hasta"

notas:
  type: text
  string: "Notas internas"
  # Ej: "Validado con María el 15/04/2026 vía WhatsApp"

ultima_actualizacion:
  type: datetime
  string: "Última actualización"
  auto: True

active:
  type: boolean
  string: "Activo"
  default: True
```

### x_ai_interaction_log (nuevo modelo)

Telemetría de cada interacción del AI Agent. Útil para análisis y debug.

```yaml
timestamp:
  type: datetime
  required: True
  default: now

channel_id:
  type: many2one
  comodel: discuss.channel

conversation_id:
  type: char
  string: "ID conversación"
  # Agrupador de turnos de la misma conversación

turn_number:
  type: integer
  string: "Turno"

user_message:
  type: text
  string: "Mensaje del usuario"
  # ofuscar PII en logs

ai_response:
  type: text
  string: "Respuesta AI"

tools_called:
  type: text
  string: "Tools llamados (JSON)"

confidence_score:
  type: float
  string: "Confidence"

action_taken:
  type: selection
  selection:
    - [respond, "Responder al cliente"]
    - [escalate, "Escalar a humano"]
    - [wait_approval, "Esperar aprobación humana"]
    - [send_quote, "Enviar cotización"]
    - [no_action, "Sin acción"]

escalation_reason:
  type: char
  string: "Razón de escalado"

latency_ms:
  type: integer
  string: "Latencia (ms)"

tokens_input:
  type: integer
  string: "Tokens input"

tokens_output:
  type: integer
  string: "Tokens output"

cost_usd:
  type: float
  string: "Costo (USD)"

model_used:
  type: char
  string: "Modelo usado"
  # ej. claude-haiku-4-5-20251001

outcome:
  type: selection
  selection:
    - [ongoing, "En curso"]
    - [escalated, "Escalada"]
    - [closed_ai, "Cerrada por AI"]
    - [closed_quoted, "Cerrada con cotización"]
    - [error, "Error"]
```

## Relaciones entre modelos

```
crm.lead ──┐
           ├──→ sale.order (via x_origen_lead_id)
           │
discuss.channel ──┬──→ crm.lead (via x_lead_id)
                  └──→ sale.order (vía contexto, no foreign key)

sale.order ──→ x_approval_request (via x_approval_request_id)

x_approval_request ──→ sale.order (via sale_order_id)
                  └──→ discuss.channel (via channel_id)

product.template ──→ res.partner (proveedor, via x_proveedor_id)

x_costo_personalizacion ──→ res.partner (via proveedor_id)
```

## Reglas de validación

- `x_costo_personalizacion`: `qty_from < qty_to` siempre (o `qty_to = NULL` para infinito)
- `x_approval_request`: si `status='approved'`, debe tener `approved_cost_unit > 0` y `responded_by_id`
- `sale.order` con `x_generated_by_ai = True` debe tener `x_origen_lead_id`
- `discuss.channel` con `x_ai_mode='paused'`: requiere `x_ai_paused_by_id`, `x_ai_paused_at`, `x_ai_paused_reason`

## Notas de migración

- Si un producto cambia de proveedor (cambia `x_proveedor_id`), recalcular `x_costo_personalizacion` aplicable
- Si una técnica se renombra en la selection, hacer migración explícita; nunca cambiar valores en producción sin script
- Los modelos `x_ai_interaction_log` se pueden purgar después de 12 meses (analytics)
- Los modelos `x_approval_request` se conservan indefinidamente (auditoría)
