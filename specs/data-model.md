# Modelo de datos custom — Mozaprint

> Referencia de campos y modelos custom (Studio) en Odoo. Claude Code consulta esto antes de crear nuevos campos o modificar existentes.

## Reglas de naming

- Todos los campos custom llevan prefijo `x_`
- Nombre en snake_case
- En español o inglés según contexto: `x_tecnica_default`, `x_ai_score`
- Si es many2one, sufijo `_id`: `x_tecnica_default_id`
- Si es many2many, sufijo `_ids`: `x_servicios_compatibles_ids`
- Si es boolean, prefijo conceptual: `x_es_personalizable`, `x_tiene_arte`

## Extensiones a modelos estándar

### product.template (extendido)

> **Estado de los campos** (verificado por el audit del 2026-06-11, ver
> `reports/catalog_audit_*` local):
> - ✓ **Existen en producción** (todos `char` legacy de texto libre, ver más
>   abajo): `x_tecnica_impresion`, `x_area_impresion`, `x_proveedor_carga`,
>   `x_material`, `x_capacidad`, `x_medidas`, `x_imagen_url_principal`.
> - ✓ **Creados y poblados en Fase 2** (vía `scripts/derive_tecnicas.py`):
>   `x_tecnica_default_id` (m2o) y `x_tecnicas_compatibles_ids` (m2m), ambos a
>   `x_tecnica_personalizacion`. ~5,203 templates derivados desde `x_tecnica_impresion`.
> - ○ **Planificados, NO existen aún** — se crean en Fase 2: `x_area_max_cm2`,
>   `x_area_dimensiones`, `x_tiempo_produccion_dias`, `x_requiere_cotizacion`,
>   `x_es_servicio_personalizacion`.
> - ✗ **Descartados**: `x_proveedor_id`, `x_proveedor_sku` — el vínculo con
>   proveedor usa el estándar `product.supplierinfo` (ver sección dedicada abajo),
>   NO un campo custom. Ojo: `x_proveedor_carga` (char) SÍ existe pero es solo una
>   **etiqueta legacy de texto libre** del proveedor que cargó el producto, NO el
>   vínculo estructurado (ese es `product.supplierinfo`).

#### Vínculo con proveedor — estándar `product.supplierinfo` (NO campo custom)

La fuente de verdad del vínculo producto↔proveedor es el modelo **estándar de
Odoo `product.supplierinfo`**, no un campo `x_`. El audit confirmó ~5275
templates activos con `supplierinfo` (cobertura ~98%).

| Campo de `product.supplierinfo` | Significado en Mozaprint |
|---|---|
| `partner_id` | Proveedor (`res.partner` con `supplier_rank > 0`) |
| `product_code` | **SKU del proveedor** (reemplaza al descartado `x_proveedor_sku`) |
| `product_name` | Nombre del producto en el sistema del proveedor |
| `price` | **Costo base** del producto por proveedor (MXN, sin IVA) |
| `min_qty` | Cantidad mínima de compra a ese proveedor |
| `delay` | Lead time del proveedor (días) |

> ⚠️ **`product.supplierinfo` es DISTINTO de `x_costo_personalizacion`** y se
> complementan:
> - `product.supplierinfo.price` = costo del **producto base** (lo que Mozaprint
>   paga al proveedor por la pieza sin marcar).
> - `x_costo_personalizacion.costo_unit` = costo de **aplicar la técnica** de
>   personalización (por cantidad/tintas/posiciones), independiente del producto.
>
> El costo total al cliente combina ambos: precio del producto (derivado de
> supplierinfo + markup) **más** el costo de personalización.
>
> **Hallazgo del audit (deuda de datos para Fase 6)**: de 5432 registros
> `supplierinfo`, solo ~2076 apuntan a partners con `supplier_rank > 0`; ~3356
> apuntan a partners sin rank de proveedor. El filtro de exclusión de proveedores
> del agente (Fase 6) se basa en `supplier_rank > 0`, así que esos partners deben
> marcarse correctamente.

#### Campos legacy existentes (texto libre, a deprecar tras migración)

```yaml
# ✓ EXISTE en producción. Texto libre, SIN normalizar.
# 5227 productos con valor, 159 valores distintos (audit 2026-06-11).
# Es la FUENTE de migración hacia x_tecnica_default_id + x_tecnicas_compatibles_ids.
# Tratar como LEGACY / SOLO-LECTURA. NO borrar antes de validar la migración.
x_tecnica_impresion:
  type: char
  string: "Técnica de impresión"
  status: legacy
  help: "Técnica(s) en texto libre, muchas como combos ('Serigrafía-Tampografía'). Se migra al modelo x_tecnica_personalizacion en Fase 2."

# ✓ EXISTE en producción. Texto libre, ej. "5x5 cm.".
# Se reconciliará con los planeados x_area_dimensiones / x_area_max_cm2.
x_area_impresion:
  type: char
  string: "Área de impresión"
  status: legacy
  help: "Dimensiones del área de impresión en texto libre. Antecede a x_area_dimensiones (planeado)."

# ✓ EXISTE en producción. Etiqueta de texto libre del proveedor que cargó el
# producto. NO es el vínculo estructurado (ese es product.supplierinfo).
x_proveedor_carga:
  type: char
  string: "Proveedor Carga"
  status: legacy
  help: "Nombre del proveedor que cargó el producto (texto libre, metadato del sync)."

# ✓ EXISTEN en producción. Metadatos de catálogo en texto libre.
x_material:
  type: char
  string: "Material"
  status: legacy

x_capacidad:
  type: char
  string: "Capacidad"
  status: legacy

x_medidas:
  type: char
  string: "Medidas"
  status: legacy

x_imagen_url_principal:
  type: char
  string: "URL imagen principal"
  status: legacy
```

#### ✓ Campos de técnica creados y poblados en Fase 2

> Creados vía Studio y **poblados** por `scripts/derive_tecnicas.py` (derivación
> raw→canónica desde `x_tecnica_impresion` usando los `x_aliases` del modelo):
> ~5,203 templates. El script es idempotente (`--apply` / `--since` / dry-run por
> defecto) y agrupa los writes por derivación idéntica.

```yaml
x_tecnica_default_id:
  type: many2one
  comodel: x_tecnica_personalizacion
  string: "Técnica de personalización default"
  help: "Técnica de impresión sugerida por defecto para este producto"
  # ✓ EXISTE y poblado. Valor principal del combo de x_tecnica_impresion.

x_tecnicas_compatibles_ids:
  type: many2many
  comodel: x_tecnica_personalizacion
  string: "Técnicas compatibles"
  help: "Lista de técnicas que se pueden aplicar a este producto"
  # ✓ EXISTE y poblado. Combos de x_tecnica_impresion parseados por -/,.
```

#### Campos planificados (○ NO existen aún — se crean en Fase 2)

```yaml
x_area_max_cm2:
  type: float
  string: "Área máxima de impresión (cm²)"
  help: "Superficie máxima disponible para imprimir el logo"
  # ○ Planificado

x_area_dimensiones:
  type: char
  string: "Dimensiones del área"
  help: "Texto descriptivo, ej. '10x10 cm', útil para mostrar al cliente"
  # ○ Planificado. Reconciliar con el legacy x_area_impresion (misma intención)

x_tiempo_produccion_dias:
  type: integer
  string: "Tiempo de producción (días)"
  help: "Días hábiles desde aprobación de arte hasta producto terminado"
  # ○ Planificado

x_requiere_cotizacion:
  type: boolean
  string: "Requiere cotización"
  default: True
  help: "Si está marcado, el botón 'Agregar al carrito' se reemplaza por 'Solicitar cotización' en la ficha"
  # ○ Planificado

x_es_servicio_personalizacion:
  type: boolean
  string: "Es servicio de personalización"
  help: "Marcado para productos que son servicios de personalización (no productos físicos)"
  # ○ Planificado
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

### x_tecnica_personalizacion (modelo custom)

> **✓ CREADO Y POBLADO EN PRODUCCIÓN** (verificado contra Odoo; **20 técnicas
> cargadas** vía `scripts/seed_tecnicas.py`, idempotente). Catálogo maestro de
> técnicas de personalización (lista plana, decisión D7).
>
> **Naming**: los campos llevan prefijo `x_` (no `x_studio_`) por ser un modelo
> custom propio. Verificado en Odoo, NO asumir.

Campos reales en producción:

```yaml
x_code:
  type: char
  string: "Código"
  # Llave estable, requerido. Ej: "serigrafia", "dtf", "laser"

x_name:
  type: char
  string: "Name"
  # Nombre de display. Ej: "Serigrafía", "Láser (Grabado Láser)"

x_aliases:
  type: text
  string: "Aliases proveedor"
  # Variantes crudas que mandan los proveedores, separadas por " | ".
  # El sync hace match contra ellas para resolver la técnica canónica.

x_orden:
  type: integer
  string: "Orden"
  # Secuencia de despliegue (10, 20, 30, ...)

x_activa:
  type: boolean
  string: "Activa"
  # Se fija en True al cargar

x_descripcion:
  type: text
  string: "Descripción"
  # Vacío al inicio; se llena después para mostrar en el sitio
```

**Datos seed**: el catálogo canónico de 20 técnicas vive en
[`data/tecnicas_seed.csv`](../data/tecnicas_seed.csv) (columnas `code`, `nombre`,
`x_aliases`, `x_orden`). Su procedencia y reglas de limpieza están en
[`data/tecnicas_seed.md`](../data/tecnicas_seed.md). El mapeo CSV → modelo:
`code → x_code`, `nombre → x_name`, `x_aliases → x_aliases`, `x_orden → x_orden`;
`x_activa` se fija True y `x_descripcion` queda vacío al cargar.

> **Nota de diseño**: el diseño original de este modelo incluía atributos ricos
> (`casos_uso_tipicos`, `materiales_compatibles`, `max_tintas_default`,
> `requiere_arte_vectorial`, `tiempo_extra_dias`, etc.) que **NO se implementaron**.
> Se optó por una lista plana (D7); cualquier metadata descriptiva va en
> `x_descripcion`. Si más adelante se requieren esos atributos, se agregan vía
> Studio y se documentan aquí.

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

> **✓ CREADO en Odoo el 2026-08-05** (17 campos, vía Ajustes → Técnico →
> Estructura de BD). Nombres técnicos confirmados con prefijo `x_` (no
> `x_studio_`) — mismo patrón que `x_tecnica_personalizacion`. Los dos many2one
> requeridos (`x_tecnica_id`, `x_proveedor_id`) usan `ondelete='restrict'`.
> `x_name` confirmado `required=True`. Permisos del grupo "Ventas/Usuario:
> todos los documentos" replicados (mismo grupo que `x_tecnica_personalizacion`),
> confirmado 2026-08-05.
>
> **✓ POBLADO 2026-08-05** vía `scripts/seed_costos.py --apply`: **127 filas**
> (47 INN, 80 PO), 0 errores, idempotencia confirmada en un segundo dry-run.
> `x_proveedor_id` resuelve por nombre EXACTO de partner (no `ilike` — hay
> partners de proveedor duplicados en Odoo, ver `docs/changelog.md` v25 y
> `analysis/costos-personalizacion/costos_seed.md`). 4P pendiente (sin lista
> documentada, requiere extracción empírica de histórico).
> Rediseñado tras leer
> las listas de costos reales de INN (`analysis/costos-personalizacion/COSTOS_INN_20260805.md`,
> gitignored) y PO (`analysis/costos-personalizacion/COSTOS_PO_20260805.md`, gitignored).
> El diseño original (una sola tabla técnica×proveedor×cantidad con `costo_unit`
> en $/pieza) no alcanzaba: **la unidad de cobro y si el costo escala por
> cantidad/tintas son propiedades de la fila (técnica + proveedor), no de la
> técnica sola** — ej. INN cobra serigrafía por LOTE (hasta 1000 pzas) por
> tinta, mientras PO cobra la misma técnica genuinamente por pieza con curva de
> cantidad. 4P queda pendiente (sin lista documentada; se construirá empírico
> desde histórico de WhatsApp/cotizaciones, pieza aparte).
>
> **Naming**: mismo patrón que `x_tecnica_personalizacion` — todos los campos
> con prefijo `x_` (no `x_studio_`) por ser modelo custom propio. Se crea vía
> **Ajustes → Técnico → Estructura de BD → Modelos/Campos** (no Studio visual),
> lo que da control exacto del nombre técnico al escribirlo directamente.
> Verificar el nombre real tras crear cada campo, igual que se hizo con
> `x_tecnica_personalizacion` (D8).

Matriz de costos de personalización por proveedor / técnica / alcance / cantidad / área.

```yaml
x_name:
  type: char
  string: "Descripción"
  required: True
  # Ej: "PO - Serigrafía Bolsas ≤603cm² - 400-599 pzas"

x_tecnica_id:
  type: many2one
  comodel: x_tecnica_personalizacion
  required: True
  string: "Técnica"

x_proveedor_id:
  type: many2one
  comodel: res.partner
  string: "Proveedor"
  required: True

x_alcance_producto:
  type: char
  string: "Alcance (categoría/SKU)"
  help: "Categoría de producto o SKU específico al que aplica esta fila, ej. 'Bolsas ≤603cm²' (PO) o 'TE-146' (INN Sublimado). Vacío = aplica genérico a la técnica. Texto libre (D7: sin modelar categorías ricas); si la matching automática a producto se vuelve necesaria para el Server Action de auto-populado, revisar entonces."

x_qty_from:
  type: integer
  string: "Cantidad mínima"
  required: True

x_qty_to:
  type: integer
  string: "Cantidad máxima"
  # null = sin límite. Curvas de proveedor con muchos escalones (PO: hasta 10
  # por técnica) son solo más filas, no requieren cambio de esquema.

x_area_from_cm2:
  type: float
  string: "Área mínima (cm²)"
  help: "Reemplaza al x_area_max_cm2 original (un solo tope). Para técnicas donde el precio varía por tamaño de diseño (Full Color, Vinil, Termograbado PO) es un tramo real de precio. Para técnicas con tamaño base fijo (Bordado INN: 7x7cm) es simplemente ese valor único; tamaños mayores sin fila → cae a cotización manual por ausencia de match (mismo mecanismo que técnicas sin tabla, ej. Sand Blast)."

x_area_to_cm2:
  type: float
  string: "Área máxima (cm²)"

x_tintas:
  type: integer
  string: "Número de tintas"
  default: 1
  help: "Número de tintas que asume esta fila."

x_escala_por_tinta:
  type: boolean
  string: "Escala linealmente por tinta"
  default: False
  help: "Si True, el costo (x_costo_unit o x_costo_lote según x_unidad_cobro) se multiplica por el número de tintas solicitadas en la cotización. Confirmado True para INN serigrafía/tampografía/láser ('costo por tinta', ver manual). PO NO publica esta regla (sus T&C solo dicen 'precio a 1 tinta') — dejar False ahí hasta confirmar con el proveedor; 2+ tintas en PO cae a cotización manual por diseño, no por descuido."

x_posiciones:
  type: integer
  string: "Número de posiciones"
  default: 1
  help: "Ambos proveedores (INN, PO) publican precios asumiendo 1 sola posición de impresión/grabado. Más de 1 posición no está tabulado → cae a cotización manual por ausencia de fila, igual que el área fuera de rango."

x_unidad_cobro:
  type: selection
  selection:
    - [pieza, "Por pieza"]
    - [lote, "Por lote (x_qty_from–x_qty_to completo)"]
  string: "Unidad de cobro"
  required: True
  default: pieza
  help: "CRÍTICO para no sobrecotizar: INN serigrafía/tampografía cobran x_costo_unit como precio del LOTE completo (hasta 1000 pzas), no por pieza. PO cobra todo genuinamente por pieza. El motor de cotización debe multiplicar por cantidad SOLO si x_unidad_cobro='pieza'."

x_costo_unit:
  type: float
  string: "Costo (MXN)"
  required: True
  help: "Costo por pieza o por lote completo, según x_unidad_cobro."

x_costo_setup:
  type: float
  string: "Costo de setup único (MXN)"
  default: 0
  help: "Placa/ponchado/cliché cuando el monto está publicado (ej. INN tampografía $220/color/placa). Si el proveedor no publica el monto (ej. cliché de termograbado PO, 'consultar con ejecutivo'), se deja en 0 y se documenta en x_notas — NO se inventa el monto. Para setup condicional (ej. ponchado de bordado INN exento en pedidos >200 pzas) se modela con dos filas de x_qty_from/x_qty_to, no un campo nuevo."

x_fecha_vigencia:
  type: date
  string: "Vigente hasta"

x_notas:
  type: text
  string: "Notas internas"
  # Ej: restricciones de los T&C del proveedor que aplican a la fila:
  # "No aplica en acabados metálicos/rubber/vidrio/cristal (T&C PO #3)"

x_activa:
  type: boolean
  string: "Activa"
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

product.template ──→ res.partner (proveedor, via product.supplierinfo estándar)

x_costo_personalizacion ──→ res.partner (via x_proveedor_id)
                        └──→ x_tecnica_personalizacion (via x_tecnica_id)
```

## Reglas de validación

- `x_costo_personalizacion`: `x_qty_from < x_qty_to` siempre (o `x_qty_to = NULL` para infinito);
  `x_area_from_cm2 <= x_area_to_cm2` cuando ambos tienen valor; si `x_unidad_cobro='lote'`, el motor
  de cotización NO debe multiplicar `x_costo_unit` por cantidad
- `x_approval_request`: si `status='approved'`, debe tener `approved_cost_unit > 0` y `responded_by_id`
- `sale.order` con `x_generated_by_ai = True` debe tener `x_origen_lead_id`
- `discuss.channel` con `x_ai_mode='paused'`: requiere `x_ai_paused_by_id`, `x_ai_paused_at`, `x_ai_paused_reason`

## Notas de migración

- Si un producto cambia de proveedor (cambia su `product.supplierinfo`), recalcular `x_costo_personalizacion` aplicable
- Migración de técnica: **YA REALIZADA** — `x_tecnica_impresion` (legacy, texto libre) → `x_tecnica_default_id` + `x_tecnicas_compatibles_ids` vía `scripts/derive_tecnicas.py` (~5,203 templates). ⚠️ **NO borrar `x_tecnica_impresion`**: sigue siendo la fuente raw y **el sync de proveedores la repisa en cada corrida**; mantener la técnica canónica al día = re-ejecutar `derive_tecnicas.py` (lo hace el sync automáticamente al terminar sin errores)
- Si una técnica se renombra en la selection, hacer migración explícita; nunca cambiar valores en producción sin script
- Los modelos `x_ai_interaction_log` se pueden purgar después de 12 meses (analytics)
- Los modelos `x_approval_request` se conservan indefinidamente (auditoría)
