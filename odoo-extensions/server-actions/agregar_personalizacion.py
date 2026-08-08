# Server Action: agregar_personalizacion  (motor de cotización, Fase 3)
# Modelo: x_wizard_personalizacion | tipo: code | invocado desde el botón "Aplicar" del wizard.
# Algoritmo: specs/motor-cotizacion.md §2 (matching) + §4 (resultado sobre la cotización).
# Consumidores: este Server Action (vendedor humano) y, a futuro, la tool create_quote_draft del AI.
#
# Correcciones vs. spec (verificadas contra datos reales de staging 2026-08-08):
#   - x_costo_personalizacion.x_qty_to == 0 significa "sin límite" (no False/null).
#   - x_approval_request es modelo manual: sus campos llevan prefijo x_ (x_sale_order_id, ...).
#   - price_unit se re-escribe tras crear la línea (el compute de servicios con list_price=0 lo pisa).
#
# Vars del sandbox usadas: env, record, log, UserError, json, datetime.

wiz = record if record else env['x_wizard_personalizacion'].browse(env.context.get('active_id'))
line = wiz.x_sale_order_line_id
order = line.order_id
tmpl = line.product_id.product_tmpl_id
tec = wiz.x_tecnica_id
qty = wiz.x_qty or int(line.product_uom_qty or 0) or 1
tintas = wiz.x_tintas or 1
posiciones = wiz.x_posiciones or 1
area = wiz.x_area_cm2 or 0.0


def _notif(titulo, mensaje, tipo):
    return {'type': 'ir.actions.client', 'tag': 'display_notification',
            'params': {'title': titulo, 'message': mensaje, 'type': tipo, 'sticky': tipo != 'success',
                       'next': {'type': 'ir.actions.act_window_close'}}}


def _solicitar_aprobacion(motivo):
    ctx = json.dumps({'producto': tmpl.display_name, 'sku': line.product_id.default_code or '',
                      'tecnica': tec.x_name, 'qty': qty, 'tintas': tintas,
                      'posiciones': posiciones, 'area_cm2': area, 'motivo': motivo})
    req = env['x_approval_request'].create({
        'x_name': 'Personalizacion %s - %s' % (tec.x_name, order.name),
        'x_sale_order_id': order.id, 'x_reason': motivo, 'x_context_json': ctx,
        'x_status': 'pending', 'x_requested_at': datetime.datetime.now()})
    order.write({'x_requires_human_approval': True, 'x_approval_request_id': req.id,
                 'x_customization_cost_source': 'manually_approved'})
    log('Personalizacion sin costo parametrizado (order=%s tecnica=%s): %s' % (order.id, tec.id, motivo))
    return _notif('Enviado a aprobacion',
                  'No hay costo parametrizado para esta combinacion. Se creo una solicitud de aprobacion; NO se agrego precio.',
                  'warning')


if not order or order.state not in ('draft', 'sent'):
    raise UserError('La cotizacion debe estar en borrador o enviada.')

servicio = env['product.product'].search(
    [('x_tecnica_servicio_id', '=', tec.id), ('x_es_servicio_personalizacion', '=', True)], limit=1)
proveedor = tmpl.seller_ids.sorted('sequence')[:1].partner_id

if not servicio:
    raise UserError('No hay producto-servicio configurado para la tecnica %s.' % tec.x_name)
elif not proveedor:
    action = _solicitar_aprobacion('El producto no tiene proveedor (supplierinfo); no se puede determinar la tabla de costos.')
else:
    dom = [('x_tecnica_id', '=', tec.id), ('x_proveedor_id', '=', proveedor.id),
           ('x_activa', '=', True), ('x_qty_from', '<=', qty),
           '|', ('x_qty_to', '=', 0), ('x_qty_to', '>=', qty)]
    cands = env['x_costo_personalizacion'].search(dom)
    cands = cands.filtered(lambda c: c.x_escala_por_tinta or c.x_tintas == tintas)

    def _area_ok(c):
        af, at = c.x_area_from_cm2 or 0.0, c.x_area_to_cm2 or 0.0
        if at > 0:
            return af <= area <= at
        return area >= af if af > 0 else True
    cands = cands.filtered(_area_ok)

    if not cands:
        action = _solicitar_aprobacion('Sin fila de costo para tecnica/proveedor/cantidad/tintas/area solicitados.')
    else:
        if len(cands) == 1:
            cand = cands
        elif wiz.x_candidato_elegido_id and wiz.x_candidato_elegido_id in cands:
            cand = wiz.x_candidato_elegido_id
        else:
            ops = '\n'.join('- %s : $%.2f (%s)' % (c.x_alcance_producto or 'generico', c.x_costo_unit, c.x_unidad_cobro) for c in cands)
            raise UserError('Hay %d alcances para esta combinacion. Elige uno en "Candidato elegido" y aplica de nuevo:\n%s' % (len(cands), ops))

        costo = cand.x_costo_unit * tintas if cand.x_escala_por_tinta else cand.x_costo_unit
        if cand.x_unidad_cobro == 'lote':
            qty_linea, precio = 1, costo
        else:
            qty_linea, precio = qty, costo

        SOL = env['sale.order.line']
        nombre = '%s - %s - %d tinta(s) - %d pza(s)' % (servicio.name, tec.x_name, tintas, qty)
        existente = SOL.search([('order_id', '=', order.id), ('x_source_line_id', '=', line.id),
                                ('display_type', '=', False)], limit=1)
        if existente:
            existente.write({'product_id': servicio.id, 'product_uom_qty': qty_linea})
            existente.write({'price_unit': precio, 'name': nombre})
        else:
            seqs = order.order_line.mapped('sequence') or [10]
            if not SOL.search_count([('order_id', '=', order.id), ('display_type', '=', 'line_section'), ('name', '=', 'Producto')]):
                SOL.create({'order_id': order.id, 'display_type': 'line_section', 'name': 'Producto', 'sequence': min(seqs) - 1})
            sec = SOL.search([('order_id', '=', order.id), ('display_type', '=', 'line_section'), ('name', '=', 'Personalizacion')], limit=1)
            if not sec:
                sec = SOL.create({'order_id': order.id, 'display_type': 'line_section', 'name': 'Personalizacion', 'sequence': max(seqs) + 10})
            nueva = SOL.create({'order_id': order.id, 'product_id': servicio.id, 'x_source_line_id': line.id,
                                'product_uom_qty': qty_linea, 'sequence': sec.sequence + 1})
            nueva.write({'price_unit': precio, 'name': nombre})

        order.write({'x_customization_cost_source': 'parametrized', 'x_requires_human_approval': False})
        log('Personalizacion parametrizada (order=%s servicio=%s precio=%.2f x%d)' % (order.id, servicio.id, precio, qty_linea))
        action = _notif('Personalizacion agregada', '%s : $%.2f (%s)' % (nombre, precio, cand.x_unidad_cobro), 'success')
