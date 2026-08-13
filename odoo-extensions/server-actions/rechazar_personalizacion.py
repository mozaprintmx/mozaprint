# Server Action: rechazar_personalizacion  (motor de cotización, Fase 3)
# Modelo: x_approval_request | tipo: code | botón "Rechazar".
# Marca la solicitud como rechazada y quita el flag "requiere aprobación" de la cotización.
# NO agrega línea de personalización. Vars: env, record, log, UserError, datetime.

req = record if record else env['x_approval_request'].browse(env.context.get('active_id'))
if req.x_status != 'pending':
    raise UserError('Esta solicitud ya fue respondida (estado: %s).' % req.x_status)

req.write({'x_status': 'rejected', 'x_responded_at': datetime.datetime.now(), 'x_responded_by_id': env.user.id})
if req.x_sale_order_id:
    req.x_sale_order_id.write({'x_requires_human_approval': False})
log('Aprobacion %s rechazada por user=%s' % (req.id, env.user.id))
action = {'type': 'ir.actions.client', 'tag': 'display_notification',
          'params': {'title': 'Rechazada', 'message': 'La solicitud fue rechazada; no se agrego personalizacion.',
                     'type': 'warning', 'next': {'type': 'ir.actions.act_window_close'}}}
