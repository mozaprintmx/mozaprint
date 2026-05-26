# Server Action: ai_handle_whatsapp_message
# 
# Modelo trigger: mail.message
# Trigger: On Create
# Filtro: model = 'discuss.channel' AND channel.channel_type = 'whatsapp'
#         AND channel.x_ai_mode = 'auto'
#         AND author is external (not internal user)
#
# Responsabilidad: cuando llega un mensaje del cliente a un channel WhatsApp 
# en modo auto, enviar el contexto a n8n para que el agente IA responda.
#
# Por qué Server Action en lugar de Webhook outbound directo:
# - Necesitamos lógica de filtrado fina (modo, tipo, autor) que Webhook básico no soporta
# - Necesitamos enriquecer payload con datos relacionados (partner, lead, conversación)
# - Necesitamos retry inteligente si n8n no responde
#
# Variables disponibles:
# - env: Odoo environment
# - record: mail.message recibido
# - _logger: logger de Odoo
#
# Imports permitidos en sandbox Odoo Online: datetime, json, re, math, time, 
#   dateutil, collections, itertools, functools
# NO permitidos: requests, urllib, os, subprocess

# ============================================================================
# CONFIG
# ============================================================================
N8N_WEBHOOK_URL_PARAM = 'mozaprint.n8n_ai_agent_webhook_url'
N8N_WEBHOOK_SECRET_PARAM = 'mozaprint.n8n_webhook_secret'
MAX_HISTORY_MESSAGES = 20
ESCALATION_KEYWORDS = [
    'asesor', 'humano', 'persona real', 'alguien me atiende',
    'no quiero ia', 'no quiero bot', 'pasame con alguien',
    'quiero hablar con',
]

# ============================================================================
# VALIDACIONES INICIALES
# ============================================================================

# Solo procesar si el mensaje es del tipo correcto
if record.message_type not in ('whatsapp', 'comment'):
    _logger.info('AI Agent: skip mensaje type=%s', record.message_type)
    # Variable 'action' es opcional; si no se setea, Odoo simplemente termina
    
elif not record.res_id or record.model != 'discuss.channel':
    _logger.info('AI Agent: skip mensaje sin discuss.channel asociado')
    
else:
    channel = env['discuss.channel'].browse(record.res_id)
    
    if not channel.exists():
        _logger.warning('AI Agent: channel %s no existe', record.res_id)
    
    elif channel.channel_type != 'whatsapp':
        _logger.info('AI Agent: skip channel type=%s', channel.channel_type)
    
    elif channel.x_ai_mode != 'auto':
        _logger.info('AI Agent: skip channel id=%s mode=%s', 
                     channel.id, channel.x_ai_mode)
    
    elif record.author_id and record.author_id.user_ids:
        # Mensaje de usuario interno (vendedor humano), no del cliente
        _logger.info('AI Agent: skip mensaje de usuario interno')
    
    else:
        # ====================================================================
        # PROCESAMIENTO PRINCIPAL
        # ====================================================================
        
        # 1. Detectar opt-out explícito ANTES de llamar al agente
        body_lower = (record.body or '').lower()
        # Quitar HTML tags básico (sandbox no tiene BeautifulSoup)
        import re
        body_plain = re.sub(r'<[^>]+>', '', body_lower).strip()
        
        opt_out_detected = any(kw in body_plain for kw in ESCALATION_KEYWORDS)
        
        if opt_out_detected:
            # Escalado inmediato sin llamar al agente
            _logger.info('AI Agent: opt-out detectado en channel %s', channel.id)
            channel.write({
                'x_ai_mode': 'paused',
                'x_ai_paused_at': datetime.datetime.now(),
                'x_ai_paused_reason': 'Cliente solicitó humano explícitamente',
            })
            # Crear actividad urgente
            env['mail.activity'].create({
                'res_model_id': env['ir.model']._get('discuss.channel').id,
                'res_id': channel.id,
                'activity_type_id': env.ref('mail.mail_activity_data_todo').id,
                'summary': 'Cliente WA solicitó hablar con asesor',
                'note': 'Cliente expresó preferencia por humano. Conversación pausada.',
                'date_deadline': datetime.date.today(),
                'user_id': channel.x_assigned_user_id.id if channel.x_assigned_user_id else env.user.id,
            })
            # Mensaje de transición al cliente (se enviará por n8n al detectar el cambio)
            # En lugar de enviar desde aquí, marcamos un flag para que el workflow
            # de n8n lo procese (mejor manejo de errores allá)
            channel.message_post(
                body='[AI escalated to human - opt-out detected]',
                message_type='comment',
                subtype_xmlid='mail.mt_note',  # nota interna, no visible al cliente
            )
            
        else:
            # 2. Construir contexto de la conversación
            recent_messages = env['mail.message'].search([
                ('model', '=', 'discuss.channel'),
                ('res_id', '=', channel.id),
                ('message_type', 'in', ['comment', 'whatsapp']),
            ], order='date desc', limit=MAX_HISTORY_MESSAGES)
            
            # Construir historial en orden cronológico (oldest first)
            history = []
            for msg in reversed(recent_messages):
                is_customer = not (msg.author_id and msg.author_id.user_ids)
                history.append({
                    'role': 'user' if is_customer else 'assistant',
                    'content': re.sub(r'<[^>]+>', '', msg.body or '').strip(),
                    'timestamp': msg.date.isoformat() if msg.date else None,
                })
            
            # 3. Identificar partner y contexto del cliente
            partner = channel.whatsapp_partner_id
            customer_context = {
                'is_new': not bool(partner),
                'partner_id': partner.id if partner else False,
                'name': partner.name if partner else False,
                'email': partner.email if partner else False,
                'phone': partner.phone or partner.mobile if partner else False,
                'company': partner.parent_id.name if partner and partner.parent_id else False,
            }
            
            if partner:
                # Cotizaciones abiertas
                open_quotes = env['sale.order'].search([
                    ('partner_id', '=', partner.id),
                    ('state', 'in', ['draft', 'sent']),
                ], limit=5)
                customer_context['open_quotes'] = [
                    {'id': q.id, 'name': q.name, 'total': q.amount_total}
                    for q in open_quotes
                ]
                
                # Lead asociado al channel si existe
                if channel.x_lead_id:
                    lead = channel.x_lead_id
                    customer_context['lead'] = {
                        'id': lead.id,
                        'collected_qty': lead.x_collected_qty,
                        'collected_tecnica': lead.x_collected_tecnica_id.code if lead.x_collected_tecnica_id else None,
                        'collected_tecnica_no_se': lead.x_collected_tecnica_no_se,
                        'collected_fecha_entrega': lead.x_collected_fecha_entrega.isoformat() if lead.x_collected_fecha_entrega else None,
                    }
            
            # 4. Construir payload para n8n
            now = datetime.datetime.now()
            business_hour = 9 <= now.hour < 19 and now.weekday() < 6  # L-S 9-19
            
            payload = {
                'event': 'whatsapp.message.received',
                'timestamp': now.isoformat() + 'Z',
                'channel': {
                    'id': channel.id,
                    'name': channel.name,
                    'whatsapp_number': channel.whatsapp_number if hasattr(channel, 'whatsapp_number') else False,
                    'x_ai_mode': channel.x_ai_mode,
                    'x_ai_turn_count': channel.x_ai_turn_count or 0,
                },
                'message': {
                    'id': record.id,
                    'body': re.sub(r'<[^>]+>', '', record.body or '').strip(),
                    'date': record.date.isoformat() if record.date else None,
                    'attachment_ids': record.attachment_ids.ids,
                },
                'customer': customer_context,
                'system': {
                    'business_hours_now': business_hour,
                    'expected_human_response_minutes': 30 if business_hour else 240,
                },
                'history': history,
            }
            
            # 5. Disparar webhook a n8n
            # NOTA: requests no está disponible en sandbox. Usamos http_request_handler
            # o webhook outbound nativo de Odoo.
            # Estrategia: registrar el evento en un modelo intermedio y que un cron
            # o webhook de Odoo lo dispare. Más simple: usar webhook outbound nativo
            # que Odoo 19 soporta y configurarlo aparte.
            
            # Aquí: marcamos el mensaje como "pending_ai_processing" y el webhook
            # outbound configurado en Settings → Technical → Webhooks lo dispara.
            
            # Crear el log de interacción (sirve como cola)
            interaction = env['x_ai_interaction_log'].create({
                'channel_id': channel.id,
                'conversation_id': str(channel.id),
                'turn_number': (channel.x_ai_turn_count or 0) + 1,
                'user_message': payload['message']['body'][:1000],
                'action_taken': 'no_action',  # se actualizará cuando n8n responda
                'outcome': 'ongoing',
                'timestamp': now,
                'context_json': json.dumps(payload, default=str),
            })
            
            # Incrementar turn count
            channel.write({
                'x_ai_turn_count': (channel.x_ai_turn_count or 0) + 1,
                'x_last_ai_response_at': now,
            })
            
            _logger.info(
                'AI Agent: interaction %s enqueued for channel %s, turn %s',
                interaction.id, channel.id, channel.x_ai_turn_count
            )
            
            # El webhook outbound configurado en Odoo dispara al crearse 
            # x_ai_interaction_log con outcome='ongoing' → llega a n8n
            # n8n procesa, llama a Claude, ejecuta tools, responde por WhatsApp,
            # y actualiza el x_ai_interaction_log con outcome final.

# Fin del Server Action
