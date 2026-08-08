# Guía: motor de cotización (Server Action + wizard) — replicación a producción

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
   `x_order_id` (m2o `sale.order`), `x_sale_order_line_id` (m2o `sale.order.line`, required),
   `x_tecnica_id` (m2o `x_tecnica_personalizacion`, required), `x_qty` (int), `x_tintas` (int),
   `x_posiciones` (int), `x_area_cm2` (float), `x_candidato_elegido_id`
   (m2o `x_costo_personalizacion`).
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
   `abrir_wizard_personalizacion.py`. Anotar su ID (lo usa el botón).

8. **Vista form del wizard** (`ir.ui.view`, model=`x_wizard_personalizacion`): el footer
   tiene un botón `type="action" name="<ID del Server Action Aplicar>"`. Sustituir el ID real.

9. **Botón en el encabezado de `sale.order`**: vista heredada de `sale.view_order_form`,
   `xpath //header position=inside`, botón `type="action" name="<ID del abridor>"`,
   `invisible="state not in ('draft','sent')"`.
   - **Validar** tras crear la vista heredada: `sale.order.get_views([[<id form base>,'form']])`
     debe cargar sin error. Si falla, **desactivar la vista heredada de inmediato** (rompe el
     form para todos). Un xpath contra el `order_line` (widget `sol_o2m`) NO funciona — por eso
     el botón va en el encabezado, no por línea.

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
