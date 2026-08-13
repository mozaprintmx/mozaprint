# Server Action: abrir_wizard_personalizacion_por_linea  (motor de cotización, Fase 3)
# Modelo: sale.order.line | tipo: code | disparado por un botón POR LÍNEA agregado en Studio
# a la lista de líneas de la cotización (el widget sol_o2m no admite el botón vía API/vista
# heredada; Studio sí se engancha). active_id = la línea clickeada.
#
# Ventaja vs. el botón de encabezado: al conocer la línea desde el inicio, precarga
# proveedor/técnica/cantidad SIN necesidad de onchange (que los modelos manuales no tienen).
# Resuelve: mostrar proveedor (2a), no pedir elegir línea (2b), y que el desplegable
# "Candidato elegido" se filtre correctamente (2c).
#
# Vars del sandbox usadas: env, UserError.

line = env['sale.order.line'].browse(env.context.get('active_id'))
if not line or line.display_type or not line.product_id:
    raise UserError('Selecciona una linea de producto (no una seccion/nota).')
if line.product_id.x_es_servicio_personalizacion:
    raise UserError('Esa linea ya es un servicio de personalizacion.')

# producto/proveedor (related) y técnica/cantidad (computed editables) se resuelven
# solos desde la línea; aquí solo se fija la línea.
wiz = env['x_wizard_personalizacion'].create({
    'x_order_id': line.order_id.id,
    'x_sale_order_line_id': line.id,
    'x_tintas': 1, 'x_posiciones': 1})
action = {'type': 'ir.actions.act_window', 'name': 'Agregar personalizacion',
          'res_model': 'x_wizard_personalizacion', 'view_mode': 'form',
          'res_id': wiz.id, 'target': 'new'}
