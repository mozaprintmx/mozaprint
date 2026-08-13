# Guía: motor de cotización (Server Action + wizard) — replicación a producción

> ⚠️ **Para DESPLEGAR usa los scripts, no esta guía a mano.** Esta guía quedó como
> referencia conceptual (el porqué de cada objeto) pero **no es un checklist completo**:
> se detectó el 2026-08-13 que le faltaban 12 objetos añadidos entre v38 y v40, y seguir
> una lista a mano de ~50 objetos es frágil.
>
> - **Plan de ejecución y rollback**: `docs/checklist-deploy-produccion.md`
> - **Despliegue** (idempotente, dry-run por defecto): `scripts/deploy_motor_cotizacion.py`
> - **Reversión**: `scripts/rollback_motor_cotizacion.py`
> - **Definición de objetos** (fuente de verdad ejecutable): las tablas `CAMPOS` /
>   `SERVER_ACTIONS` del script de deploy y `scripts/views_motor.py`.

> Diseño y algoritmo: `specs/motor-cotizacion.md`. Campos/modelos:
> `odoo-extensions/studio-fields.yaml` (status `staging`). Código versionado:
> `odoo-extensions/server-actions/agregar_personalizacion.py` (Aplicar) y
> `abrir_wizard_personalizacion.py` (abridor).
>
> **✓ Construido y probado en STAGING (`ODOO_TEST_URL`) el 2026-08-08.**
> **Pendiente de replicar a PRODUCCIÓN** (espera visto bueno). Los IDs que aparecen
> abajo son de staging — en prod los objetos se crean nuevos y tomarán otros IDs.

## Por qué admin XML-RPC (y no JSON-2)

Crear metadata (modelos, campos, ACLs, Server Actions, vistas) requiere permisos que el
usuario JSON-2 reducido ("Rosy") **no tiene** (403 en `ir.model.fields` create, precedente
2026-08-06). El admin (`ODOO_USER`/`ODOO_PASSWORD` de `analysis/supplier-sync/.env`, vía
XML-RPC) sí puede. En staging la BD para XML-RPC es el **subdominio** (ej.
`mozaprintmx-test-saas19-0807`), no `mozaprintmx` — JSON-2 resuelve la BD por host, XML-RPC
exige el nombre exacto. En prod la BD es `mozaprintmx`.

> ⚠ Guardarraíl: cualquier script de setup debe **abortar si la URL/BD no es la esperada**.
> No correr el setup contra prod sin visto bueno explícito.

## Orden de creación (idempotente)

1. **Modelo `x_approval_request`** (custom, NO transitorio). Modelo manual → **los campos
   llevan prefijo `x_`** (Odoo lo exige en campos manuales; los nombres sin prefijo de la
   spec original no son creables). Campos: `x_name` (rec_name auto, Descripción, required),
   `x_sale_order_id` (m2o `sale.order`, required, on_delete=cascade), `x_channel_id`,
   `x_reason`, `x_context_json`, `x_requested_at`, `x_responded_at`, `x_responded_by_id`,
   `x_status` (selection pending/approved/rejected), `x_approved_cost_unit`,
   `x_approved_setup_cost`, `x_approved_servicio_id` (m2o `product.product`), `x_notes`,
   `x_assigned_user_id`.

2. **Campos en `sale.order`**: `x_requires_human_approval` (bool),
   `x_approval_request_id` (m2o `x_approval_request`, on_delete=set null),
   `x_customization_cost_source` (selection parametrized/manually_approved/no_aplica).

3. **Campo en `sale.order.line`**: `x_source_line_id` (m2o `sale.order.line`,
   on_delete=cascade) — idempotencia/trazabilidad de la línea de personalización.

4. **Modelo `x_wizard_personalizacion`** (transitorio, `transient=True`). Campos:
   `x_order_id` (m2o `sale.order`), `x_sale_order_line_id` (m2o `sale.order.line`,
   **NO required** — se valida en el Aplicar; ver nota abajo), `x_tecnica_id`
   (m2o `x_tecnica_personalizacion`, **NO required**), `x_qty` (int), `x_tintas` (int),
   `x_posiciones` (int), `x_area_cm2` (float), `x_candidato_elegido_id`
   (m2o `x_costo_personalizacion`).
   - **Por qué no required**: en cotizaciones multi-línea el wizard abre con el selector de
     línea vacío (modelos manuales no tienen `onchange`); si fueran `required`, el abridor no
     podría crear el registro. La obligatoriedad la valida el Server Action Aplicar.
   - **on_delete de los m2o del wizard = `cascade`/`set null`, NO `restrict`**: en un
     transitorio, `restrict` bloquearía borrar líneas/técnicas reales por un wizard efímero.
     (La spec §3 mencionaba `restrict` "en los obligatorios"; se documenta esta desviación).

5. **ACLs (`ir.model.access`)**: crear por API NO genera ACLs (Studio sí). Sin ellas, ni el
   admin puede crear registros ("Ningún grupo permite esta operación"). Dar CRUD al grupo
   **usuario interno** (`base.group_user`) sobre `x_wizard_personalizacion` y
   `x_approval_request`.

6. **Server Action "Aplicar"** (`ir.actions.server`, state=code, model=`x_wizard_personalizacion`):
   pegar `odoo-extensions/server-actions/agregar_personalizacion.py`.

7. **Server Action "Abrir wizard"** (state=code, model=`sale.order`): pegar
   `abrir_wizard_personalizacion.py`. Anotar su ID (lo usa el botón). Ojo: el código
   **excluye las líneas de servicio de personalización** (`x_es_servicio_personalizacion`)
   al contar las líneas de producto — si no, al reabrir el wizard, la línea `[SERV-...]`
   contaría como producto y rompería el preselect de línea única / el re-aplicar.

8. **Vista form del wizard** (`ir.ui.view`, model=`x_wizard_personalizacion`): el footer
   tiene un botón `type="action" name="<ID del Server Action Aplicar>"`. Sustituir el ID real.

9. **Botón en el encabezado de `sale.order`**: vista heredada de `sale.view_order_form`,
   `xpath //header position=inside`, botón `type="action" name="<ID del abridor>"`,
   `invisible="state not in ('draft','sent')"`.
   - **Validar** tras crear la vista heredada: `sale.order.get_views([[<id form base>,'form']])`
     debe cargar sin error. Si falla, **desactivar la vista heredada de inmediato** (rompe el
     form para todos). Un xpath contra el `order_line` (widget `sol_o2m`) NO funciona — por eso
     el botón va en el encabezado, no por línea.

## Regla híbrida de proveedor (añadido 2026-08-08)

Objetos extra a crear en la replicación (ver `specs/motor-cotizacion.md` §7):

- **Campo** `x_costo_personalizacion.x_personalizacion_externa` (bool, default False) —
  marca filas de personalización **externa** (maquila/in-house), disponibles para
  cualquier producto sin importar su proveedor.
- **Partner** dedicado **"Personalización Externa (Mozaprint)"** (`res.partner`,
  `supplier_rank=0`) para anclar esas filas — NO surte productos.
- **Campos del wizard**: `x_candidato_externo_id` (m2o `x_costo_personalizacion`) y los dos
  **`related`** (readonly, `store=False`, **no escribir desde los Server Actions**):
  - `x_proveedor_id` (m2o `res.partner`) → related `x_sale_order_line_id.product_id.seller_ids.partner_id`
  - `x_producto_id` (m2o `product.product`) → related `x_sale_order_line_id.product_id`

  Son la clave para que el wizard funcione en cotizaciones **multi-línea**: los related se
  recalculan al cambiar la línea en el formulario (los modelos manuales no tienen `onchange`),
  y `seller_ids[:1]` es el proveedor preferido por el `_order` de `product.supplierinfo`.
- **`x_tecnica_id` y `x_qty`**: computed + `store=True` + `readonly=False` +
  `depends='x_sale_order_line_id'`, con el código en `ir.model.fields.compute` (ver
  `specs/motor-cotizacion.md` §7 para el snippet). Así se autollenan desde la línea pero el
  vendedor puede cambiarlos. **No usar `related`** aquí: escribiría de vuelta en el producto.
- **Vista del wizard**: el desplegable "Candidato elegido" se acota al proveedor del
  producto — dominio
  `[('x_tecnica_id','=',x_tecnica_id),('x_proveedor_id','=',x_proveedor_id),('x_personalizacion_externa','=',False),('x_activa','=',True)]`;
  y un campo aparte "Proveedor externo (opcional)" con dominio
  `[('x_tecnica_id','=',x_tecnica_id),('x_personalizacion_externa','=',True),('x_activa','=',True)]`.

Comportamiento: por defecto solo cotiza con el proveedor del producto (no se pueden usar
filas de otros proveedores de productos); si se elige una fila externa, el motor la usa e
ignora al del producto. **Las filas de costo externas se cargan aparte** (aún no existen).

## Administración de aprobaciones (añadido 2026-08-08)

Objetos extra a crear en la replicación (ver `specs/motor-cotizacion.md` §8):

- **Campos** en `x_approval_request`: `x_sale_order_line_id` (m2o `sale.order.line`,
  on_delete cascade), `x_tecnica_id` (m2o `x_tecnica_personalizacion`), `x_qty` (int),
  `x_approved_unidad` (selection pieza/lote). Permiten generar la línea al aprobar.
- **Server Actions** (state=code, model=`x_approval_request`): pegar
  `aprobar_personalizacion.py` (botón "Aprobar y agregar a la cotización") y
  `rechazar_personalizacion.py` (botón "Rechazar"). Anotar sus IDs (los usan los botones).
- **Vistas** `ir.ui.view` de `x_approval_request`: lista (con `x_status` widget badge) y
  formulario (header con los 2 botones `type="action"` referenciando los IDs anteriores,
  `invisible="x_status != 'pending'"`, y statusbar de `x_status`). En el formulario,
  `x_sale_order_line_id`/`x_tecnica_id`/`x_qty`/`x_approved_*` son **editables mientras la
  solicitud está Pendiente** (`readonly="x_status != 'pending'"`) para poder completar
  solicitudes incompletas; `x_sale_order_line_id` con dominio
  `[('order_id','=',x_sale_order_id),('display_type','=',False),('product_id','!=',False)]`.
- **Acción de ventana** + **menú** "Ventas → Aprobaciones personalización"
  (`ir.actions.act_window` sobre `x_approval_request` + `ir.ui.menu` con
  `parent_id = sale.sale_menu_root`).
- El Server Action `agregar_personalizacion` (caso 0 candidatos) precarga en la solicitud la
  línea/técnica/cantidad y el servicio, para que el aprobador solo capture el costo.

Nota: la vista de búsqueda personalizada se omitió (una search view inválida rompe el listado);
el filtrado se hace con la columna de estado. Los botones NO se validan solo con `create` —
correr `x_approval_request.get_views([[list_id,'list'],[form_id,'form']])` tras crearlas.

## Disparador: encabezado, no por línea

La spec §1 pedía botón **por línea de producto**. En Odoo 19 `order_line` usa el widget OWL
`sol_o2m` (sin `<list>`/`<tree>` en el arch), así que un botón de fila **no es inyectable solo
por API**. El botón de encabezado da la misma función de forma robusta: abre el wizard y, si la
cotización tiene una sola línea de producto, precarga línea/técnica/cantidad; con varias, el
vendedor elige la línea en el wizard. El botón por línea exacto puede añadirse en **Studio**
(que sí se engancha al widget) si se prefiere esa UX.

## Prueba de aceptación (repetir en prod tras replicar)

Con una cotización borrador y un producto que tenga `x_tecnica_default_id` y `supplierinfo`:
- **1 candidato** → auto-pobla la línea de personalización bajo la sección "Personalización".
- **N candidatos** (misma técnica+proveedor+qty, distinto alcance) → el wizard pide elegir
  `x_candidato_elegido_id`; al aplicar de nuevo, se agrega.
- **0 candidatos** (ej. proveedor sin costos parametrizados) → crea `x_approval_request` y
  **no** agrega precio; marca `x_customization_cost_source = manually_approved`.
- **Idempotencia**: aplicar dos veces sobre la misma línea actualiza la línea, no duplica.

## UI de administración de datos maestros (añadido 2026-08-12)

`x_costo_personalizacion` y `x_tecnica_personalizacion` se crearon vía Técnico y se poblaron por
script, así que **nacieron sin vistas ni menú**: no había forma de corregir una tarifa desde la
interfaz. Al replicar a producción hay que crear también:

- **Vistas** `ir.ui.view` (lista + formulario) para `x_costo_personalizacion` — la lista conviene
  `editable="bottom"` para corregir rápido (ej. cambiar `x_unidad_cobro` de pieza a lote).
- **Vistas** (lista + formulario) para `x_tecnica_personalizacion`.
- **Acciones de ventana** + **menús** bajo **Ventas → Configuración**
  (`parent_id = sale.menu_sale_config`).

Ambos modelos ya tienen ACL de "Sales / User: All Documents" con escritura, así que no hace falta
tocar permisos. Validar siempre con `get_views` tras crear las vistas.

> ⚠ Recordatorio: **no crear vistas de búsqueda (`search`) a la ligera** — una search view
> inválida rompe el listado del modelo. Si se agrega, validar y borrarla si falla.
