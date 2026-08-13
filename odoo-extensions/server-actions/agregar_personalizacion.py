# Server Action: agregar_personalizacion  (motor de cotización, Fase 3)
# Modelo: x_wizard_personalizacion | tipo: code | invocado desde el botón "Aplicar" del wizard.
# Algoritmo: specs/motor-cotizacion.md §2 (matching) + §4 (resultado sobre la cotización).
# Consumidores: este Server Action (vendedor humano) y, a futuro, la tool create_quote_draft del AI.
#
# Regla de proveedor (decisión 2026-08-08, híbrido):
#   - Default: se AMARRA al proveedor del producto (supplierinfo de menor sequence). El vendedor
#     NO puede cotizar con filas de otros proveedores de PRODUCTOS.
#   - Opción manual "Proveedor externo": filas marcadas x_personalizacion_externa=True (maquila
#     in-house), sin relación con los proveedores de productos. Si se elige, ignora al del producto.
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
# Fallback: si el vendedor no eligió técnica (multi-línea, sin onchange), usa la del producto.
tec = wiz.x_tecnica_id or tmpl.x_tecnica_default_id
qty = wiz.x_qty or int(line.product_uom_qty or 0) or 1
tintas = wiz.x_tintas or 1
posiciones = wiz.x_posiciones or 1
area = wiz.x_area_cm2 or 0.0


def _notif(titulo, mensaje, tipo):
    return {'type': 'ir.actions.client', 'tag': 'display_notification',
            'params': {'title': titulo, 'message': mensaje, 'type': tipo, 'sticky': tipo != 'success',
                       'next': {'type': 'ir.actions.act_window_close'}}}


def _pedir_confirmacion(motivo):
    """No crea nada: guarda el motivo y abre el diálogo Aceptar/Cancelar.
    La solicitud la crea el Server Action 'confirmar_aprobacion' si el vendedor acepta."""
    wiz.write({'x_msg_confirmacion': motivo})
    vid = env['ir.ui.view'].sudo().search(
        [('name', '=', 'x_wizard_personalizacion.confirmar')], limit=1).id
    if not vid:
        # Sin la vista, Odoo abriria el form normal del wizard y el vendedor no veria el
        # aviso. Falla ruidosamente: es un error de instalacion, no un caso de negocio.
        raise UserError('Falta la vista "x_wizard_personalizacion.confirmar" en esta base. '
                        'Revisa la replicacion del motor de cotizacion.')
    return {'type': 'ir.actions.act_window', 'name': 'Se solicitara una aprobacion',
            'res_model': 'x_wizard_personalizacion', 'res_id': wiz.id,
            'view_mode': 'form', 'views': [(vid, 'form')], 'target': 'new'}


if not line:
    raise UserError('Selecciona la linea de cotizacion a personalizar.')
if not tec:
    raise UserError('Selecciona la tecnica de personalizacion.')
if not order or order.state not in ('draft', 'sent'):
    raise UserError('La cotizacion debe estar en borrador o enviada.')

servicio = env['product.product'].search(
    [('x_tecnica_servicio_id', '=', tec.id), ('x_es_servicio_personalizacion', '=', True)], limit=1)
if not servicio:
    raise UserError('No hay producto-servicio configurado para la tecnica %s.' % tec.x_name)

proveedor = tmpl.seller_ids.sorted('sequence')[:1].partner_id
cand = None

if wiz.x_forzar_aprobacion:
    # El vendedor indica que ninguna tarifa tabulada aplica a ESTE producto (aunque
    # técnica/proveedor/cantidad sí matcheen alguna fila de otro alcance).
    action = _pedir_confirmacion(
        'Indicaste que NINGUNA tarifa tabulada aplica a este producto '
        '(alcance no tabulado para %s).\n\nSe solicitara una aprobacion y NO se agregara precio '
        'hasta que un responsable la autorice.' % (proveedor.name or 'el proveedor'))
elif wiz.x_candidato_externo_id:
    # Opción manual: proveedor externo de personalización (ignora al del producto).
    # Se valida igual que las del proveedor: cantidad y tintas deben aplicar.
    ext = wiz.x_candidato_externo_id
    if (ext.x_qty_from <= qty and (ext.x_qty_to == 0 or ext.x_qty_to >= qty)
            and (ext.x_escala_por_tinta or ext.x_tintas == tintas)):
        cand = ext
    else:
        action = _pedir_confirmacion(
            'La tarifa EXTERNA elegida ("%s", %s-%s pzas, %d tinta(s)) NO aplica a lo que estas '
            'cotizando (cantidad %d, %d tinta(s)).\n\nPuedes CANCELAR y elegir otra, o ACEPTAR '
            'para solicitar una aprobacion.'
            % (ext.x_alcance_producto or 'generico', ext.x_qty_from, ext.x_qty_to or 'sin limite',
               ext.x_tintas, qty, tintas))
elif not proveedor:
    action = _pedir_confirmacion(
        'El producto no tiene proveedor asignado, asi que no se puede determinar que tabla de '
        'costos aplica.\n\nSe solicitara una aprobacion y NO se agregara precio hasta que un '
        'responsable la autorice.')
else:
    dom = [('x_tecnica_id', '=', tec.id), ('x_proveedor_id', '=', proveedor.id),
           ('x_activa', '=', True), ('x_personalizacion_externa', '=', False),
           ('x_qty_from', '<=', qty), '|', ('x_qty_to', '=', 0), ('x_qty_to', '>=', qty)]
    cands = env['x_costo_personalizacion'].search(dom)
    cands = cands.filtered(lambda c: c.x_escala_por_tinta or c.x_tintas == tintas)

    def _area_ok(c):
        af, at = c.x_area_from_cm2 or 0.0, c.x_area_to_cm2 or 0.0
        if at > 0:
            return af <= area <= at
        return area >= af if af > 0 else True
    cands = cands.filtered(_area_ok)

    elegido = wiz.x_candidato_elegido_id
    if elegido and elegido not in cands:
        action = _pedir_confirmacion(
            'El candidato elegido ("%s", %s-%s pzas) NO aplica a lo que estas cotizando '
            '(cantidad %d, %d tinta(s), area %s cm2).\n\nPuedes CANCELAR y elegir otro candidato, '
            'o ACEPTAR para solicitar una aprobacion (no se agregara precio hasta autorizarla).'
            % (elegido.x_alcance_producto or 'generico', elegido.x_qty_from,
               elegido.x_qty_to or 'sin limite', qty, tintas, area))
    elif not cands:
        action = _pedir_confirmacion(
            'No hay tarifa tabulada para esta combinacion (tecnica %s, proveedor %s, %d pzas, '
            '%d tinta(s), area %s cm2).\n\nSe solicitara una aprobacion y NO se agregara precio '
            'hasta que un responsable la autorice.' % (tec.x_name, proveedor.name, qty, tintas, area))
    elif elegido:
        cand = elegido
    elif len(cands) == 1:
        cand = cands
    else:
        ops = '\n'.join('- %s : $%.2f (%s)' % (c.x_alcance_producto or 'generico', c.x_precio_venta, c.x_unidad_cobro) for c in cands)
        raise UserError('Hay %d alcances para esta combinacion (proveedor %s). Elige uno en "Candidato elegido" y aplica de nuevo:\n%s' % (len(cands), proveedor.name, ops))

if cand:
    # PRECIO DE VENTA (costo x markup), no el costo del proveedor. El costo queda solo en
    # la matriz para referencia/gasto — ver specs/motor-cotizacion.md §10.
    pv = cand.x_precio_venta or round((cand.x_costo_unit or 0.0) * (cand.x_markup or 1.275), 2)
    costo = pv * tintas if cand.x_escala_por_tinta else pv
    if cand.x_unidad_cobro == 'lote':
        qty_linea, precio = 1, costo
    else:
        qty_linea, precio = qty, costo

    SOL = env['sale.order.line']
    fuente = 'externo' if cand.x_personalizacion_externa else (cand.x_proveedor_id.name or '')
    nombre = '%s - %s - %d tinta(s) - %d pza(s)' % (servicio.name, tec.x_name, tintas, qty)

    # Secciones (idempotente) y sección destino
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
    # Setup: cargo único por orden (placa/pantalla/ponchado), no se multiplica por cantidad.
    # También a precio de venta (markup aplicado), decisión 2026-08-12.
    ps = cand.x_precio_setup or round((cand.x_costo_setup or 0.0) * (cand.x_markup or 1.275), 2)
    _upsert(True, ps, 1, 'Setup / preparacion - %s' % tec.x_name)

    order.write({'x_customization_cost_source': 'parametrized', 'x_requires_human_approval': False})
    log('Personalizacion parametrizada (order=%s servicio=%s precio=%.2f x%d fuente=%s)' % (order.id, servicio.id, precio, qty_linea, fuente))
    action = _notif('Personalizacion agregada', '%s : $%.2f (%s)' % (nombre, precio, cand.x_unidad_cobro), 'success')
