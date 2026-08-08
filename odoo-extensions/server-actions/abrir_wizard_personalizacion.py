# Server Action: abrir_wizard_personalizacion  (motor de cotización, Fase 3)
# Modelo: sale.order | tipo: code | disparado por el botón "Agregar personalización"
# del ENCABEZADO de la cotización (ver nota de UI abajo).
#
# Responsabilidad: crear el registro transitorio x_wizard_personalizacion y abrirlo
# en un diálogo, precargando la línea/técnica/cantidad cuando la cotización tiene una
# sola línea de producto (si tiene varias, el vendedor elige la línea en el wizard).
#
# NOTA DE UI (por qué encabezado y no por línea): la spec §1 pedía un botón POR LÍNEA
# de producto. En Odoo 19 el campo order_line usa el widget OWL `sol_o2m` (sin un
# <list>/<tree> estándar en el arch), por lo que NO es posible inyectar un botón por
# fila solo vía API/vista heredada. El botón por línea SÍ puede añadirse desde Studio
# (que se engancha a ese widget). Entre tanto, el botón de encabezado da la misma
# funcionalidad de forma robusta y versión-estable. Ver docs/guia-motor-cotizacion.md.
#
# Vars del sandbox usadas: env, UserError.

order = env['sale.order'].browse(env.context.get('active_id'))
lines = order.order_line.filtered(lambda l: not l.display_type and l.product_id)
if not lines:
    raise UserError('La cotizacion no tiene lineas de producto.')

vals = {'x_order_id': order.id, 'x_tintas': 1, 'x_posiciones': 1}
if len(lines) == 1:
    ln = lines
    vals.update({'x_sale_order_line_id': ln.id,
                 'x_tecnica_id': ln.product_id.product_tmpl_id.x_tecnica_default_id.id or False,
                 'x_qty': int(ln.product_uom_qty or 1)})

wiz = env['x_wizard_personalizacion'].create(vals)
action = {'type': 'ir.actions.act_window', 'name': 'Agregar personalizacion',
          'res_model': 'x_wizard_personalizacion', 'view_mode': 'form',
          'res_id': wiz.id, 'target': 'new'}
