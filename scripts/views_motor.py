"""
Vistas del motor de cotización (arch XML), separadas de la lógica de despliegue.

Las usa `scripts/deploy_motor_cotizacion.py`. Los IDs de los Server Actions se
inyectan en tiempo de despliegue (`aid`), porque difieren entre instancias.

Compatibilidad: se usa `<list>` (no `<tree>`, renombrado en Odoo 17) y atributos
`invisible="..."`/`readonly="..."` con expresión Python (Odoo 17+, sin `attrs=`).
Verificado contra 19.0 (producción) y saas~19.2 (staging).
"""


def ARCHS(aid: dict, o=None) -> list[dict]:
    """Devuelve las vistas a crear. `o` (cliente Odoo) solo se usa para resolver
    el form base de sale.order al heredar."""
    base_form = o.xmlid("sale", "view_order_form") if o else None

    wizard = """<form string="Agregar personalización">
  <sheet>
    <field name="x_order_id" invisible="1"/>
    <group>
      <group string="Producto a personalizar">
        <field name="x_sale_order_line_id"
               domain="[('order_id','=',x_order_id),('display_type','=',False),('product_id','!=',False)]"
               options="{'no_create': True}"/>
        <field name="x_producto_id" readonly="1"/>
        <field name="x_proveedor_id" readonly="1"/>
        <field name="x_qty"/>
      </group>
      <group string="Personalización">
        <field name="x_tecnicas_producto_ids" widget="many2many_tags" readonly="1" options="{'no_create': True}"/>
        <field name="x_tecnica_id" options="{'no_create': True}"/>
        <field name="x_aviso_tecnica" readonly="1" invisible="not x_aviso_tecnica"/>
        <field name="x_tintas"/>
        <field name="x_posiciones"/>
        <field name="x_area_cm2"/>
      </group>
    </group>
    <group string="Si el proveedor del producto tiene varios alcances para esta técnica, elige uno">
      <field name="x_candidato_elegido_id" options="{'no_create': True}" invisible="x_forzar_aprobacion"
             domain="[('x_tecnica_id','=',x_tecnica_id),('x_proveedor_id','=',x_proveedor_id),('x_personalizacion_externa','=',False),('x_activa','=',True)]"/>
      <field name="x_forzar_aprobacion"/>
    </group>
    <group string="O cotiza con un proveedor de personalización EXTERNO (in-house/maquila, no ligado al producto)"
           invisible="x_forzar_aprobacion">
      <field name="x_candidato_externo_id" options="{'no_create': True}"
             domain="[('x_tecnica_id','=',x_tecnica_id),('x_personalizacion_externa','=',True),('x_activa','=',True)]"/>
    </group>
  </sheet>
  <footer>
    <button string="Aplicar" type="action" name="%(apply)s" class="btn-primary"/>
    <button string="Cancelar" special="cancel" class="btn-secondary"/>
  </footer>
</form>""" % aid

    confirmar = """<form string="Se solicitará una aprobación">
  <sheet>
    <div class="alert alert-warning" role="alert">
      <field name="x_msg_confirmacion" readonly="1" nolabel="1"/>
    </div>
  </sheet>
  <footer>
    <button string="Aceptar y solicitar aprobación" type="action" name="%(confirmar)s" class="btn-primary"/>
    <button string="Cancelar" special="cancel" class="btn-secondary"/>
  </footer>
</form>""" % aid

    ar_list = """<list string="Solicitudes de aprobación">
  <field name="x_name"/>
  <field name="x_sale_order_id"/>
  <field name="x_tecnica_id"/>
  <field name="x_qty"/>
  <field name="x_approved_cost_unit"/>
  <field name="x_approved_precio_venta"/>
  <field name="x_status" widget="badge" decoration-warning="x_status=='pending'"
         decoration-success="x_status=='approved'" decoration-danger="x_status=='rejected'"/>
  <field name="x_requested_at"/>
</list>"""

    ar_form = """<form string="Solicitud de aprobación">
  <header>
    <button name="%(aprobar)s" type="action" string="Aprobar y agregar a la cotización"
            class="btn-primary" invisible="x_status != 'pending'"/>
    <button name="%(rechazar)s" type="action" string="Rechazar" invisible="x_status != 'pending'"/>
    <field name="x_status" widget="statusbar" statusbar_visible="pending,approved,rejected"/>
  </header>
  <sheet>
    <div class="oe_title"><h1><field name="x_name" readonly="1"/></h1></div>
    <group>
      <group string="Cotización">
        <field name="x_sale_order_id" readonly="1"/>
        <field name="x_sale_order_line_id" readonly="x_status != 'pending'"
               domain="[('order_id','=',x_sale_order_id),('display_type','=',False),('product_id','!=',False)]"
               options="{'no_create': True}"/>
        <field name="x_tecnica_id" readonly="x_status != 'pending'" options="{'no_create': True}"/>
        <field name="x_qty" readonly="x_status != 'pending'"/>
        <field name="x_tintas" readonly="x_status != 'pending'"/>
        <field name="x_approved_servicio_id" readonly="x_status != 'pending'"/>
      </group>
      <group string="Costo del proveedor (gasto)">
        <field name="x_approved_cost_unit" readonly="x_status != 'pending'"/>
        <field name="x_approved_unidad" readonly="x_status != 'pending'"/>
        <field name="x_approved_setup_cost" readonly="x_status != 'pending'"/>
        <field name="x_markup" readonly="x_status != 'pending'"/>
        <field name="x_approved_precio_venta" readonly="1"/>
        <field name="x_approved_precio_setup" readonly="1"/>
        <field name="x_responded_by_id" readonly="1"/>
        <field name="x_responded_at" readonly="1"/>
      </group>
    </group>
    <group string="¿Reutilizar esta tarifa en el futuro? (opcional)">
      <field name="x_guardar_tarifa" readonly="x_status != 'pending'"/>
      <field name="x_alcance_nuevo" readonly="x_status != 'pending'"
             invisible="x_guardar_tarifa == 'no' or not x_guardar_tarifa"/>
      <field name="x_tarifa_qty_from" readonly="x_status != 'pending'"
             invisible="x_guardar_tarifa == 'no' or not x_guardar_tarifa"/>
      <field name="x_tarifa_qty_to" readonly="x_status != 'pending'"
             invisible="x_guardar_tarifa == 'no' or not x_guardar_tarifa"/>
    </group>
    <group string="Motivo / contexto (por qué se pidió aprobación)">
      <field name="x_reason" readonly="1"/>
      <field name="x_context_json" readonly="1"/>
    </group>
    <group string="Notas internas"><field name="x_notes" nolabel="1"/></group>
  </sheet>
</form>""" % aid

    costos_list = """<list string="Costos de personalización" editable="bottom">
  <field name="x_tecnica_id"/>
  <field name="x_proveedor_id"/>
  <field name="x_alcance_producto"/>
  <field name="x_qty_from"/>
  <field name="x_qty_to"/>
  <field name="x_tintas"/>
  <field name="x_unidad_cobro"/>
  <field name="x_costo_unit"/>
  <field name="x_markup"/>
  <field name="x_precio_venta" decoration-bf="1"/>
  <field name="x_costo_setup"/>
  <field name="x_precio_setup"/>
  <field name="x_escala_por_tinta"/>
  <field name="x_personalizacion_externa"/>
  <field name="x_activa"/>
</list>"""

    costos_form = """<form string="Costo de personalización">
  <sheet>
    <div class="oe_title"><h1><field name="x_name" placeholder="Descripción"/></h1></div>
    <group>
      <group string="A qué aplica">
        <field name="x_tecnica_id" options="{'no_create': True}"/>
        <field name="x_proveedor_id" options="{'no_create': True}"/>
        <field name="x_alcance_producto"/>
        <field name="x_personalizacion_externa"/>
        <field name="x_activa"/>
      </group>
      <group string="Rangos">
        <field name="x_qty_from"/>
        <field name="x_qty_to" help="0 = sin límite"/>
        <field name="x_tintas"/>
        <field name="x_escala_por_tinta"/>
        <field name="x_posiciones"/>
        <field name="x_area_from_cm2"/>
        <field name="x_area_to_cm2"/>
      </group>
    </group>
    <group>
      <group string="Costo del proveedor (gasto)">
        <field name="x_unidad_cobro"/>
        <field name="x_costo_unit"/>
        <field name="x_costo_setup"/>
      </group>
      <group string="Precio de venta (cliente)">
        <field name="x_markup"/>
        <field name="x_precio_venta"/>
        <field name="x_precio_setup"/>
        <field name="x_fecha_vigencia"/>
      </group>
    </group>
    <group string="Notas internas"><field name="x_notas" nolabel="1"/></group>
  </sheet>
</form>"""

    tec_list = """<list string="Técnicas de personalización">
  <field name="x_orden"/><field name="x_code"/><field name="x_name"/><field name="x_activa"/>
</list>"""

    tec_form = """<form string="Técnica de personalización">
  <sheet>
    <div class="oe_title"><h1><field name="x_name"/></h1></div>
    <group><group><field name="x_code"/><field name="x_orden"/><field name="x_activa"/></group></group>
    <group string="Aliases de proveedor (separados por |)"><field name="x_aliases" nolabel="1"/></group>
    <group string="Descripción"><field name="x_descripcion" nolabel="1"/></group>
  </sheet>
</form>"""

    header_btn = """<data>
  <xpath expr="//header" position="inside">
    <button name="%(opener)s" type="action" string="Agregar personalización"
            invisible="state not in ('draft','sent')"/>
  </xpath>
</data>""" % aid

    v = [
        {"name": "x_wizard_personalizacion.form",
         "vals": {"name": "x_wizard_personalizacion.form", "model": "x_wizard_personalizacion",
                  "type": "form", "arch": wizard}},
        {"name": "x_wizard_personalizacion.confirmar",
         "vals": {"name": "x_wizard_personalizacion.confirmar", "model": "x_wizard_personalizacion",
                  "type": "form", "arch": confirmar, "priority": 99}},
        {"name": "x_approval_request.list",
         "vals": {"name": "x_approval_request.list", "model": "x_approval_request",
                  "type": "list", "arch": ar_list}},
        {"name": "x_approval_request.form",
         "vals": {"name": "x_approval_request.form", "model": "x_approval_request",
                  "type": "form", "arch": ar_form}},
        {"name": "x_costo_personalizacion.list",
         "vals": {"name": "x_costo_personalizacion.list", "model": "x_costo_personalizacion",
                  "type": "list", "arch": costos_list}},
        {"name": "x_costo_personalizacion.form",
         "vals": {"name": "x_costo_personalizacion.form", "model": "x_costo_personalizacion",
                  "type": "form", "arch": costos_form}},
        {"name": "x_tecnica_personalizacion.list",
         "vals": {"name": "x_tecnica_personalizacion.list", "model": "x_tecnica_personalizacion",
                  "type": "list", "arch": tec_list}},
        {"name": "x_tecnica_personalizacion.form",
         "vals": {"name": "x_tecnica_personalizacion.form", "model": "x_tecnica_personalizacion",
                  "type": "form", "arch": tec_form}},
    ]
    if base_form:
        # Vista heredada: es la ÚNICA que puede romper el form de ventas para todos.
        # El deploy la valida con get_views justo después de crearla.
        v.append({"name": "sale.order.personalizar.header.button",
                  "vals": {"name": "sale.order.personalizar.header.button", "model": "sale.order",
                           "inherit_id": base_form, "arch": header_btn, "active": True}})
    return v
