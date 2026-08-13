# Server Action: confirmar_aprobacion  (motor de cotización, Fase 3)
# Modelo: x_wizard_personalizacion | tipo: code | botón "Aceptar" del diálogo de confirmación.
#
# Es el ÚNICO lugar que crea x_approval_request desde el wizard: `agregar_personalizacion`
# detecta el caso (0 tarifas, candidato que no aplica, sin proveedor, "ninguna aplica") y solo
# abre el diálogo con el motivo en x_msg_confirmacion; si el vendedor cancela, no pasa nada.
# Ver specs/motor-cotizacion.md §11.
#
# Vars del sandbox usadas: env, record, log, UserError, json, datetime.

wiz = record if record else env['x_wizard_personalizacion'].browse(env.context.get('active_id'))
line = wiz.x_sale_order_line_id
order = line.order_id
tmpl = line.product_id.product_tmpl_id
tec = wiz.x_tecnica_id or tmpl.x_tecnica_default_id
qty = wiz.x_qty or int(line.product_uom_qty or 0) or 1
tintas = wiz.x_tintas or 1
motivo = wiz.x_msg_confirmacion or 'Costo de personalizacion no parametrizado.'

if not line or not tec:
    raise UserError('Faltan datos en el asistente (linea o tecnica).')
if not order or order.state not in ('draft', 'sent'):
    raise UserError('La cotizacion debe estar en borrador o enviada.')

servicio = env['product.product'].search(
    [('x_tecnica_servicio_id', '=', tec.id), ('x_es_servicio_personalizacion', '=', True)], limit=1)

ctx = json.dumps({'producto': tmpl.display_name, 'sku': line.product_id.default_code or '',
                  'tecnica': tec.x_name, 'qty': qty, 'tintas': tintas,
                  'posiciones': wiz.x_posiciones or 1, 'area_cm2': wiz.x_area_cm2 or 0.0,
                  'motivo': motivo}, ensure_ascii=False)

req = env['x_approval_request'].create({
    'x_name': 'Personalizacion %s - %s' % (tec.x_name, order.name),
    'x_sale_order_id': order.id, 'x_reason': motivo, 'x_context_json': ctx,
    'x_status': 'pending', 'x_requested_at': datetime.datetime.now(),
    'x_sale_order_line_id': line.id, 'x_tecnica_id': tec.id, 'x_qty': qty,
    'x_tintas': tintas, 'x_approved_servicio_id': servicio.id if servicio else False,
    'x_approved_unidad': 'pieza', 'x_guardar_tarifa': 'no', 'x_markup': 1.275,
    'x_alcance_nuevo': tmpl.name[:60], 'x_tarifa_qty_from': qty, 'x_tarifa_qty_to': 0})

order.write({'x_requires_human_approval': True, 'x_approval_request_id': req.id,
             'x_customization_cost_source': 'manually_approved'})
log('Solicitud de aprobacion %s creada (order=%s tecnica=%s)' % (req.id, order.id, tec.id))
action = {'type': 'ir.actions.client', 'tag': 'display_notification',
          'params': {'title': 'Solicitud enviada',
                     'message': 'Se creo la solicitud de aprobacion. NO se agrego precio; '
                                'la personalizacion se agregara cuando la autoricen.',
                     'type': 'warning', 'sticky': True,
                     'next': {'type': 'ir.actions.act_window_close'}}}
