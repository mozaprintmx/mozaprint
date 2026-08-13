# Server Action: aprobar_personalizacion  (motor de cotización, Fase 3)
# Modelo: x_approval_request | tipo: code | botón "Aprobar y agregar a la cotización".
#
# Qué hace: al aprobar una solicitud (costo no parametrizado), toma el "Costo unitario
# aprobado" capturado por el administrador y GENERA/actualiza automáticamente la línea de
# personalización en la cotización (misma sección "Personalización" que el flujo normal),
# marca la solicitud como aprobada y desmarca "requiere aprobación" en la cotización.
#
# Vars del sandbox usadas: env, record, log, UserError, datetime.

req = record if record else env['x_approval_request'].browse(env.context.get('active_id'))
if req.x_status != 'pending':
    raise UserError('Esta solicitud ya fue respondida (estado: %s).' % req.x_status)

order = req.x_sale_order_id
line = req.x_sale_order_line_id
if not order or not line:
    raise UserError('La solicitud no tiene cotizacion/linea asociada; no se puede generar la linea.')
if order.state not in ('draft', 'sent'):
    raise UserError('La cotizacion %s ya no esta en borrador/enviada.' % order.name)
if not req.x_approved_cost_unit or req.x_approved_cost_unit <= 0:
    raise UserError('Captura el "Costo unitario aprobado" (> 0) antes de aprobar.')
if not req.x_tecnica_id:
    # Sin técnica no se puede nombrar la línea ni, si se pide, guardar la tarifa.
    raise UserError('Selecciona la Tecnica antes de aprobar.')

servicio = req.x_approved_servicio_id
if not servicio and req.x_tecnica_id:
    servicio = env['product.product'].search(
        [('x_tecnica_servicio_id', '=', req.x_tecnica_id.id),
         ('x_es_servicio_personalizacion', '=', True)], limit=1)
if not servicio:
    raise UserError('No hay producto-servicio configurado para la tecnica.')

qty = req.x_qty or int(line.product_uom_qty or 1)
# A la cotización va el PRECIO DE VENTA (costo aprobado x markup); el costo queda registrado
# en la solicitud y, si se guarda la tarifa, en la matriz. Ver specs §10.
mk = req.x_markup or 1.275
pv = req.x_approved_precio_venta or round(req.x_approved_cost_unit * mk, 2)
if req.x_approved_unidad == 'lote':
    qty_linea, precio = 1, pv
else:
    qty_linea, precio = qty, pv

SOL = env['sale.order.line']
nombre = '%s - %s - %d pza(s) (aprobado)' % (servicio.name, req.x_tecnica_id.x_name or '', qty)
seqs = order.order_line.mapped('sequence') or [10]
if not SOL.search_count([('order_id', '=', order.id), ('display_type', '=', 'line_section'), ('name', '=', 'Producto')]):
    SOL.create({'order_id': order.id, 'display_type': 'line_section', 'name': 'Producto', 'sequence': min(seqs) - 1})
sec = SOL.search([('order_id', '=', order.id), ('display_type', '=', 'line_section'), ('name', '=', 'Personalizacion')], limit=1)
if not sec:
    sec = SOL.create({'order_id': order.id, 'display_type': 'line_section', 'name': 'Personalizacion', 'sequence': max(seqs) + 10})


def _upsert(es_setup, monto, cant, nom):
    """Crea/actualiza (o borra si monto<=0) la línea de personalización o la de setup."""
    prev = SOL.search([('order_id', '=', order.id), ('x_source_line_id', '=', line.id),
                       ('x_es_setup', '=', es_setup), ('display_type', '=', False)], limit=1)
    if monto <= 0 and es_setup:
        prev.unlink()
        return
    if prev:
        prev.write({'product_id': servicio.id, 'product_uom_qty': cant})
        prev.write({'price_unit': monto, 'name': nom})
    else:
        nueva = SOL.create({'order_id': order.id, 'product_id': servicio.id,
                            'x_source_line_id': line.id, 'x_es_setup': es_setup,
                            'product_uom_qty': cant, 'sequence': sec.sequence + (2 if es_setup else 1)})
        nueva.write({'price_unit': monto, 'name': nom})


_upsert(False, precio, qty_linea, nombre)
# Setup aprobado: cargo único por orden, no se multiplica por cantidad. También con markup.
ps = req.x_approved_precio_setup or round((req.x_approved_setup_cost or 0.0) * mk, 2)
_upsert(True, ps, 1, 'Setup / preparacion - %s (aprobado)' % (req.x_tecnica_id.x_name or ''))

# Opcional: guardar la tarifa aprobada en la matriz de costos para que la próxima vez
# SÍ esté tabulada. Opt-in: por defecto x_guardar_tarifa='no' y no se toca la matriz.
if req.x_guardar_tarifa in ('proveedor', 'externo'):
    externa = req.x_guardar_tarifa == 'externo'
    if externa:
        prov = env['res.partner'].search([('name', '=', 'Personalización Externa (Mozaprint)')], limit=1)
        if not prov:
            raise UserError('Falta el contacto "Personalización Externa (Mozaprint)" para guardar tarifas externas.')
    else:
        prov = line.product_id.product_tmpl_id.seller_ids.sorted('sequence')[:1].partner_id
        if not prov:
            raise UserError('El producto no tiene proveedor; usa la opcion de tarifa EXTERNA.')
    alc = req.x_alcance_nuevo or line.product_id.name or ''
    qf = req.x_tarifa_qty_from or qty
    qt = req.x_tarifa_qty_to or 0
    vals_t = {'x_name': '%s - %s - %s - qty %d-%s' % (prov.name, req.x_tecnica_id.x_name, alc, qf, qt or '+'),
              'x_tecnica_id': req.x_tecnica_id.id, 'x_proveedor_id': prov.id,
              'x_alcance_producto': alc, 'x_qty_from': qf, 'x_qty_to': qt,
              'x_tintas': req.x_tintas or 1, 'x_unidad_cobro': req.x_approved_unidad or 'pieza',
              'x_costo_unit': req.x_approved_cost_unit, 'x_costo_setup': req.x_approved_setup_cost,
              'x_markup': mk,
              'x_personalizacion_externa': externa, 'x_activa': True,
              'x_notas': 'Alta automatica desde la aprobacion %s (%s).' % (req.id, order.name)}
    dom_t = [('x_tecnica_id', '=', req.x_tecnica_id.id), ('x_proveedor_id', '=', prov.id),
             ('x_alcance_producto', '=', alc), ('x_qty_from', '=', qf), ('x_qty_to', '=', qt)]
    fila = env['x_costo_personalizacion'].search(dom_t, limit=1)
    fila.write(vals_t) if fila else env['x_costo_personalizacion'].create(vals_t)
    log('Tarifa (%s) guardada en la matriz desde aprobacion %s' % (req.x_guardar_tarifa, req.id))

req.write({'x_status': 'approved', 'x_responded_at': datetime.datetime.now(), 'x_responded_by_id': env.user.id})
order.write({'x_requires_human_approval': False, 'x_customization_cost_source': 'manually_approved'})
log('Aprobacion %s aplicada (order=%s servicio=%s precio=%.2f x%d)' % (req.id, order.id, servicio.id, precio, qty_linea))
action = {'type': 'ir.actions.client', 'tag': 'display_notification',
          'params': {'title': 'Aprobado', 'message': 'Se agrego la linea de personalizacion a %s.' % order.name,
                     'type': 'success', 'next': {'type': 'ir.actions.act_window_close'}}}
