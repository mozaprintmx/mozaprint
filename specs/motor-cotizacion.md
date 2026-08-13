# Motor de cotización — matriz de costos → línea de cotización

> Spec central del "matching" entre lo que pide el cliente (técnica, cantidad,
> tintas, área) y `x_costo_personalizacion`. La usan DOS consumidores:
> 1. **Server Action manual** (Fase 3, este doc) — botón/wizard que un vendedor
>    humano usa en Odoo mientras arma una cotización a mano.
> 2. **Tool `create_quote_draft` del agente AI** (Fase 4-6,
>    `specs/ai-agent-spec.md`) — mismo algoritmo, disparado por conversación de
>    WhatsApp en vez de un clic. Reutiliza esta lógica, no la reimplementa.
>
> Diseño 2026-08-06. Contexto: `specs/data-model.md` (`x_costo_personalizacion`,
> servicios de personalización), `docs/decisions` D7 (técnicas como lista plana,
> sin atributos ricos — por eso `x_alcance_producto` es texto libre y no hay
> matching automático producto↔categoría).

## 1. Disparador

Botón **"Agregar personalización"** en la línea de producto de una cotización
en borrador (`sale.order` estado `draft`/`sent`). Abre un wizard (modelo
transitorio, ver §3) precargado con datos de esa línea.

## 2. Algoritmo de matching (el corazón del motor)

Entradas: `product_id` (de la línea clickeada), `tecnica_id`, `qty`, `tintas`,
`posiciones`, `area_cm2` (si la técnica la usa).

```
1. proveedor_id = product.supplierinfo del product_id con menor `sequence`
   (mismo criterio que usa Compras para elegir proveedor preferido).
   Si el producto no tiene supplierinfo → ir directo a HITL (paso 5),
   no hay forma de saber qué tabla de costos aplica.

2. candidatos = search(x_costo_personalizacion, domain=[
     ('x_tecnica_id', '=', tecnica_id),
     ('x_proveedor_id', '=', proveedor_id),
     ('x_activa', '=', True),
     ('x_qty_from', '<=', qty),
     '|', ('x_qty_to', '>=', qty), ('x_qty_to', '=', False),
     ('x_tintas', '=', tintas),   # o ignorar si x_escala_por_tinta permite otro conteo
   ])
   + filtrar por área si la técnica la usa (area_cm2 dentro de
     x_area_from_cm2–x_area_to_cm2, o sin filtro si la fila no tiene área)

3. Si len(candidatos) == 0 → HITL (paso 5)

4. Si len(candidatos) == 1 → auto-poblar (paso 6)

5. Si len(candidatos) > 1 → difieren solo en x_alcance_producto (categoría).
   El wizard muestra la lista de x_alcance_producto + costo de cada candidato
   para que el vendedor elija 1 con un clic (decisión 2026-08-06: NO se manda
   a aprobación humana solo por esto — es casi automático, ya está
   parametrizado, solo falta 1 dato que el humano sabe de un vistazo:
   "esto que estoy cotizando es una bolsa, no un bolígrafo").
   → una vez elegido, continúa como paso 6 con ese candidato.

6. costo_final = candidato.x_costo_unit
   si candidato.x_escala_por_tinta: costo_final *= tintas
   si candidato.x_unidad_cobro == 'pieza': qty_linea = qty; precio_linea = costo_final
   si candidato.x_unidad_cobro == 'lote':  qty_linea = 1;   precio_linea = costo_final
   (¡el punto crítico! con 'lote' NO se multiplica por qty — ver
   analysis/costos-personalizacion/COSTOS_INN_20260805.md, INN cobra el lote
   completo fijo, no por pieza)

7. servicio_product_id = product.template donde x_tecnica_servicio_id = tecnica_id
   (uno de los 20 ya creados, Fase 3 anterior)
```

## 3. Wizard — modelo transitorio nuevo

`x_wizard_personalizacion` (crear con checkbox "Modelo transitorio" marcado,
vía Ajustes → Técnico → igual que los modelos anteriores — NO Studio, para
conservar nombre plano `x_`, ver lección documentada en
`docs/guia-creacion-servicios-personalizacion.md`).

| Campo | Tipo | Notas |
|---|---|---|
| `x_sale_order_line_id` | many2one → `sale.order.line` | La línea de producto sobre la que se agrega personalización |
| `x_tecnica_id` | many2one → `x_tecnica_personalizacion` | Precargado con `product_id.x_tecnica_default_id`; dominio limitado a `x_tecnicas_compatibles_ids` del producto |
| `x_qty` | integer | Precargado con la cantidad de la línea |
| `x_tintas` | integer, default 1 | |
| `x_posiciones` | integer, default 1 | |
| `x_area_cm2` | float, opcional | Solo relevante si la técnica usa área (mostrar/ocultar en la vista según técnica elegida) |
| `x_candidato_elegido_id` | many2one → `x_costo_personalizacion`, opcional | Se llena solo si hubo ambigüedad (§2 paso 5) y el vendedor eligió uno de la lista |

## 4. Resultado sobre la cotización

- Si auto-pobló o el vendedor eligió candidato: crea/actualiza `sale.order.line`
  bajo la sección "Personalización" (crea las 2 secciones — "Producto" /
  "Personalización" — si la cotización no las tiene), `product_id` = servicio
  correspondiente, `product_uom_qty`/`price_unit` según §2 paso 6.
  `sale.order.x_customization_cost_source = 'parametrized'`.
- Si 0 candidatos: crea `x_approval_request` (modelo ya existe, ver
  `specs/data-model.md`) con `context_json` = producto/técnica/qty/tintas/área
  pedidos, `sale.order.x_requires_human_approval = True`,
  `x_customization_cost_source = 'manually_approved'` (queda pendiente hasta
  que un humano responda la solicitud). El wizard cierra con aviso claro de
  que se mandó a aprobación, NO con un precio inventado.

## 5. Fuera de alcance de esta pieza (deliberado)

- Matching automático de `x_alcance_producto` (texto libre) contra el producto
  específico — se resuelve con 1 clic del vendedor (§2 paso 5), no con NLP o
  reglas de texto. Evita sobre-ingeniería (mismo criterio que D7).
- Reordenar/mezclar secciones si la cotización ya tiene líneas fuera de
  "Producto"/"Personalización" (ej. un vendedor que agregó una nota manual) —
  el Server Action solo garantiza que sus propias líneas caigan en la sección
  correcta, no reorganiza lo que ya había.

## 6. Estado de implementación (✓ probado en STAGING 2026-08-08)

Implementado y probado end-to-end contra `ODOO_TEST_URL` (admin XML-RPC).
**Pendiente de replicar a producción** (espera visto bueno). Artefactos versionados:
`odoo-extensions/server-actions/agregar_personalizacion.py` (Aplicar) y
`.../abrir_wizard_personalizacion.py` (abridor). Guía de replicación:
`docs/guia-motor-cotizacion.md`. Modelos/campos: `odoo-extensions/studio-fields.yaml`
(status `staging`).

**Pruebas (§2 casos):** (a) 1 candidato → auto-pobla; (b) N candidatos → UserError
lista los alcances y el vendedor elige `x_candidato_elegido_id`; (c) 0 candidatos →
crea `x_approval_request` y NO inventa precio. Idempotencia: re-ejecutar sobre la
misma línea actualiza (no duplica), vía `sale.order.line.x_source_line_id`.

### Correcciones a esta spec (verificadas contra datos reales)

1. **`x_qty_to == 0` = "sin límite"** (no `False`/null como decía §2 paso 2). El
   dominio real es `'|', ('x_qty_to','=',0), ('x_qty_to','>=',qty)`.
2. **Filtro de tintas**: no se filtra en el dominio (depende de `x_escala_por_tinta`);
   se filtra en Python: se conserva la fila si `x_escala_por_tinta` **o**
   `x_tintas == tintas`.
3. **Semántica de área** cuando el wizard no la especifica (`area=0`): matchea filas
   cuyo rango inicia en 0 (`x_area_from_cm2 == 0`) y excluye las de área mínima > 0
   (ej. "Bolsas >603 cm²"). Si dos filas `[0, X]` compiten → cae al caso N (elegir).
4. **`x_approval_request` es modelo manual → sus campos llevan prefijo `x_`**
   (`x_sale_order_id`, `x_reason`, `x_context_json`, `x_status`, ...). Los nombres sin
   prefijo de `specs/data-model.md` NO son creables en un modelo custom manual.
5. **Prerequisitos que no existían** y se crearon en staging: el modelo
   `x_approval_request` y los campos `sale.order.x_requires_human_approval /
   x_approval_request_id / x_customization_cost_source`.
6. **Precio de la línea = costo de `x_costo_personalizacion`** (§2 paso 6, sin markup
   adicional sobre la personalización). Si se quiere margen sobre personalización,
   es una decisión aparte — hoy se factura al costo parametrizado.
7. **Setup (`x_costo_setup`) → línea propia** (decisión 2026-08-12). §2 paso 6 no lo
   contemplaba y el motor lo ignoraba, así que se estaba **subcotizando** toda técnica con
   setup publicado (INN: tampografía y bordado; montos en `analysis/`). Ver §9.

### Disparador (§1) — realidad de Odoo 19

El botón **por línea** de la spec §1 no es posible solo por API: en Odoo 19 el
`order_line` usa el widget OWL `sol_o2m` (sin `<list>`/`<tree>` en el arch donde
inyectar un botón de fila). Se implementó un botón de **encabezado** "Agregar
personalización" (robusto, versión-estable) que abre el wizard precargando la línea
cuando la cotización tiene una sola línea de producto; con varias, el vendedor elige
la línea en el wizard. El botón por línea exacto de la spec puede añadirse en
**Studio** (que sí se engancha al widget) si se prefiere esa UX.

## 7. Regla de proveedor — híbrida (decisión 2026-08-08)

Corrige el §2 paso 1 tras probar con datos reales (un producto surtido por PO solo
mostraba las filas de láser de PO, no las de INN — comportamiento correcto pero que
destapó la decisión de negocio):

- **Default — amarrado al proveedor del producto**: el motor resuelve el proveedor
  desde `product.supplierinfo` (menor `sequence`) y **solo** considera filas de
  `x_costo_personalizacion` de **ese** proveedor con `x_personalizacion_externa = False`.
  El vendedor **no** puede cotizar con filas de **otros proveedores de productos**
  (el dominó de PO no puede cotizarse con la tarifa de INN). El desplegable
  "Candidato elegido" queda acotado a ese proveedor.
- **Opción manual — proveedor externo de personalización**: filas marcadas
  `x_personalizacion_externa = True`, ancladas al partner dedicado
  **"Personalización Externa (Mozaprint)"** (maquila/in-house, NO surte productos).
  Se eligen en el campo `x_candidato_externo_id` del wizard; si se elige una, el motor
  la usa e **ignora** al proveedor del producto. Independiente del catálogo de
  proveedores de productos.

Campos añadidos: `x_costo_personalizacion.x_personalizacion_externa` (bool);
`x_wizard_personalizacion.x_proveedor_id` (proveedor del producto, lo precarga el
abridor) y `x_candidato_externo_id`.

**Estado de datos**: el mecanismo está listo en staging; **las filas de costo externas
aún no existen** (se cargan después). Hasta entonces, la opción externa está vacía.

### Multi-línea resuelto con campos `related` (2026-08-08)

Problema: los modelos manuales **no tienen `onchange`**, así que al elegir la línea dentro
del wizard (cotización con varias líneas) el proveedor no se recalculaba → "Proveedor del
producto" vacío y el desplegable "Candidato elegido" mostraba *Sin registros* (aunque
**Aplicar sí cotizaba bien**, porque el motor resuelve el proveedor desde la línea).

Solución sin campos nuevos en el catálogo: `x_proveedor_id` y `x_producto_id` del wizard son
campos **`related`** sobre el `product.supplierinfo` que el producto ya tiene:

- `x_proveedor_id` → `x_sale_order_line_id.product_id.seller_ids.partner_id`
- `x_producto_id` → `x_sale_order_line_id.product_id`

Los related **sí se recalculan** al cambiar su origen en el formulario (son campos computados
con `depends` sobre la ruta), y al atravesar el one2many `seller_ids` Odoo toma el primer
registro — que por el `_order` de `product.supplierinfo` (`sequence, ...`) es **el proveedor
preferido**, el mismo criterio del motor (§2 paso 1). Ambos van `readonly` + no almacenados,
y los Server Actions **ya no los escriben** (escribir un related propagaría al origen).

`x_tecnica_id` y `x_qty` **no pueden ser `related`** (un related editable escribiría de vuelta
en el producto/la línea). Se resuelven con el patrón nativo de Odoo **computed + store +
`readonly=False`** (el mismo de `sale.order.line.price_unit`): se autollenan desde la línea y
se recalculan al cambiarla, pero el vendedor puede sobrescribirlos. El `compute` de los campos
manuales se escribe en `ir.model.fields.compute` con `depends = x_sale_order_line_id`:

```python
for r in self:
    r['x_tecnica_id'] = r.x_sale_order_line_id.product_id.product_tmpl_id.x_tecnica_default_id
for r in self:
    r['x_qty'] = int(r.x_sale_order_line_id.product_uom_qty or 0)
```

Con esto los abridores solo fijan la línea (el resto se calcula solo): quedaron en 12 líneas
de código cada uno.

### Visibilidad de las técnicas del producto (2026-08-08)

El selector de Técnica deja elegir **cualquiera** de las 20 —deliberado: se puede querer cotizar
con un proveedor externo una técnica que el producto no trae asignada— pero eso dejaba al
vendedor sin saber **cuáles sí** están asignadas. Se agregaron dos campos de referencia:

- `x_tecnicas_producto_ids`: m2m **related** a
  `x_sale_order_line_id.product_id.product_tmpl_id.x_tecnicas_compatibles_ids`, readonly, se
  muestra con `widget="many2many_tags"` → el vendedor ve las técnicas del producto como etiquetas.
- `x_aviso_tecnica`: char **computed** (no almacenado, `depends='x_sale_order_line_id,x_tecnica_id'`)
  que indica `OK - tecnica asignada a este producto` o
  `AVISO - esta tecnica NO esta asignada al producto (verifica o cotiza externo)`. Es el
  "distintivo": no bloquea nada, solo advierte.

**Limitación restante (cosmética)**: el desplegable de "Línea de cotización" muestra la
*descripción* de la línea (es el `display_name` nativo de `sale.order.line`, no configurable
sin módulo). Por eso se agregó `x_producto_id` como referencia visible con SKU. El botón
**por línea** (Server Action `abrir_wizard_personalizacion_por_linea`, ya escrito y probado)
eliminaría por completo el paso de elegir línea, pero **Studio de esta instancia no permite
agregar botones a la lista embebida de líneas** (solo campos), así que queda disponible por si
en el futuro hay forma de engancharlo.

## 8. Administración de aprobaciones (caso 0 candidatos)

Cuando §2 no encuentra costo, `agregar_personalizacion` crea una `x_approval_request`
**pendiente** precargando lo necesario para reconstruir la línea al aprobar:
`x_sale_order_line_id` (línea de producto origen), `x_tecnica_id`, `x_qty`,
`x_approved_servicio_id` (el servicio de la técnica) y `x_approved_unidad` (default `pieza`).
Marca `sale.order.x_requires_human_approval=True` y `x_customization_cost_source='manually_approved'`.

**UI**: menú **Ventas → "Aprobaciones personalización"** (acción de ventana + vistas lista/
formulario de `x_approval_request`, con statusbar `pending/approved/rejected`).

**Aprobar** (Server Action `aprobar_personalizacion`, botón del formulario): valida que
`x_approved_cost_unit > 0`, calcula `precio`/`qty_linea` según `x_approved_unidad`
(pieza → ×cantidad; lote → fija), **genera o actualiza** la línea de personalización en la
sección "Personalización" (misma lógica idempotente por `x_source_line_id` que §4), marca la
solicitud `approved` con `x_responded_by_id`/`x_responded_at`, y desmarca
`x_requires_human_approval`. Bloquea si la solicitud ya fue respondida o si la cotización salió
de borrador/enviada.

**Rechazar** (Server Action `rechazar_personalizacion`): marca `rejected` y libera el aviso de
la cotización, sin agregar línea.

**Permisos**: hoy `base.group_user` (cualquier usuario interno) puede aprobar. Restringir a un
rol es configuración aparte. **Setup cost** (`x_approved_setup_cost`) aún no se refleja como
línea (futuro).

### 8.1 Pedir aprobación aunque HAYA candidatos (2026-08-12)

Caso real: serigrafía en un producto de PO que **no está en su lista tabulada** (no es cilindro,
bolsa ni bolígrafo). Técnica + proveedor + cantidad **sí** matchean otras filas, así que el motor
obligaba a elegir un alcance que no aplica. Se agregó al wizard el booleano
**`x_forzar_aprobacion`** ("Ninguna tarifa aplica - solicitar aprobación"): si está marcado, el
Aplicar **salta el matching** y crea la `x_approval_request` directamente (motivo: "alcance no
tabulado para <proveedor>"). Cuando está marcado, la vista oculta los selectores de candidato.

### 8.2 Guardar la tarifa aprobada en la matriz (2026-08-12)

Al aprobar, el administrador puede decidir si esa tarifa **se queda** en
`x_costo_personalizacion` para que la próxima vez ya esté tabulada. Campo
**`x_guardar_tarifa`** (selection, **default `no` — es opt-in**):

| Valor | Efecto |
|---|---|
| `no` | Solo aplica a esta cotización; la matriz no se toca. |
| `proveedor` | Crea la fila con `x_proveedor_id` = proveedor del producto, `x_personalizacion_externa=False` → aparecerá entre los **candidatos** de ese proveedor. |
| `externo` | Crea la fila anclada al partner **"Personalización Externa (Mozaprint)"** con `x_personalizacion_externa=True` → aparecerá en **proveedor externo**. |

La fila se arma con `x_alcance_nuevo` (precargado con el nombre del producto),
`x_tarifa_qty_from`/`x_tarifa_qty_to` (precargados con la cantidad pedida y "sin límite"),
`x_tintas`, `x_approved_unidad` y `x_approved_cost_unit`. Es idempotente: si ya existe una fila
con la misma llave (técnica+proveedor+alcance+rango), la actualiza en vez de duplicar. Queda
`x_notas` con la trazabilidad ("Alta automatica desde la aprobacion N").

⚠ **Deriva del CSV**: estas filas nacen en Odoo y **no** están en
`analysis/costos-personalizacion/costos_seed.csv`. `seed_costos.py` no las borra (solo crea/
actualiza lo que trae el CSV), pero conviene exportarlas al CSV periódicamente para que el CSV
siga siendo la fuente de verdad reproducible.

## 9. Setup como línea propia (2026-08-12)

El **setup** es el costo único por orden (pantalla de serigrafía, ponchado de bordado,
placa/cliché de tampografía): **no se multiplica por la cantidad**. Estaba modelado en
`x_costo_personalizacion.x_costo_setup` y en `x_approval_request.x_approved_setup_cost`, pero
**ningún flujo lo cobraba** — se detectó al preguntar para qué servía el campo. Impacto real:
5 de 129 filas tienen setup > 0 (INN tampografía; INN bordado en 1–50 y 51–200 pzas,
exento arriba de 200), y ese monto no llegaba a la cotización.

**Decisión (JC, 2026-08-12): línea aparte**, no prorrateado en el precio unitario — es
transparente para el cliente, editable/eliminable por separado y no ensucia el margen unitario.

Implementación (en los dos flujos: Aplicar y Aprobar):

- La línea de setup **reutiliza el mismo producto-servicio de la técnica**, para no perder el
  reporte de ingresos por técnica (ver `specs/data-model.md`, servicios de personalización).
- Se distingue con **`sale.order.line.x_es_setup`** (bool). La idempotencia pasa a ser por
  `(x_source_line_id, x_es_setup)`: hay como máximo una línea normal y una de setup por línea
  de producto.
- `product_uom_qty = 1`, `price_unit = x_costo_setup` (o `x_approved_setup_cost` al aprobar),
  nombre `"Setup / preparacion - <técnica>"`, y se coloca justo debajo de la línea de
  personalización (`sec.sequence + 2`).
- Si el setup es 0 (o se cambia a una técnica sin setup), la línea de setup **se elimina**
  — comportamiento verificado.

**Probado en staging**: Tampografía INN 300 pzas → línea de personalización + línea de setup
re-aplicar no duplica; cambiar a Láser (sin setup) borra la línea de setup.

## 10. Costo vs. precio de venta (2026-08-12)

Hasta ahora el motor escribía en la cotización el **costo del proveedor** — es decir, se
vendía la personalización **sin margen**. Decisión (JC, 2026-08-12): separar ambos conceptos,
guardando los dos **en la matriz de costos** (no en la línea de cotización: no se instaló
`sale_margin` ni se agregó costo a `sale.order.line`).

Campos nuevos en `x_costo_personalizacion`:

| Campo | Qué es |
|---|---|
| `x_markup` | Factor costo → precio. **Estándar 1.275** (backfill en las filas existentes + `ir.default` para nuevas). |
| `x_precio_venta` | computed+store+**editable** = `round(x_costo_unit * x_markup, 2)` |
| `x_precio_setup` | computed+store+**editable** = `round(x_costo_setup * x_markup, 2)` |

Equivalentes en `x_approval_request`: `x_markup`, `x_approved_precio_venta`,
`x_approved_precio_setup` (derivados de `x_approved_cost_unit` / `x_approved_setup_cost`).

**El motor cotiza con el precio de venta** (`x_precio_venta`, y `x_precio_setup` para la línea
de setup). `x_escala_por_tinta` multiplica el **precio**, no el costo. El costo se conserva solo
como referencia de gasto en la matriz / en la solicitud de aprobación. Al guardar una tarifa
desde una aprobación se copia también el markup.

Como son computed **editables**, se puede fijar un precio manual en una fila concreta; ese
override se conserva mientras no cambien el costo ni el markup (si cambian, se recalcula).

**Seed**: `scripts/seed_costos.py` acepta la columna opcional `markup` (default
`DEFAULT_MARKUP = 1.275`) y carga **costo + markup**; el precio de venta lo calcula Odoo. El CSV
de `analysis/` ya trae la columna. Dry-run tras el cambio: *0 a crear, 128 a actualizar, 0 error*.

## 11. Confirmación antes de solicitar aprobación (2026-08-12)

Antes, cualquier caso sin tarifa creaba la solicitud **de inmediato**, sin avisar. Ahora
`agregar_personalizacion` **no crea nada**: guarda el motivo en `x_msg_confirmacion` y abre un
diálogo (vista `x_wizard_personalizacion.confirmar`, `target=new`) con el mensaje explicando qué
pasó y dos botones: **"Aceptar y solicitar aprobación"** / **"Cancelar"**. La solicitud la crea
el Server Action **`confirmar_aprobacion`** — el único lugar que la crea, sin lógica duplicada.

Casos que abren el diálogo (cada uno con su mensaje):
1. **Candidato elegido que no aplica** a la cantidad/área pedidas (antes: `UserError` seco).
   El mensaje invita a *cancelar y elegir otro* o *aceptar y pedir aprobación*.
2. **Sin tarifa tabulada** para técnica/proveedor/cantidad/tintas/área.
3. **Producto sin proveedor** (no hay tabla de costos que aplique).
4. **"Ninguna tarifa aplica"** marcado por el vendedor (§8.1).

Sigue siendo `UserError` (sin diálogo) el caso de **N candidatos sin elegir**: ahí no hay
aprobación que pedir, solo falta que el vendedor elija.

> La vista del diálogo se localiza **por nombre** (`ir.ui.view` con
> `name='x_wizard_personalizacion.confirmar'`), no por ID — así el mismo código funciona en
> staging y en producción sin editar el Server Action.
