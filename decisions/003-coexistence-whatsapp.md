# ADR 003: WhatsApp Coexistence Mode

**Fecha**: 2026-05-23
**Estado**: Propuesto (pendiente aprobación equipo)
**Decisores**: Equipo Mozaprint

## Contexto

Mozaprint usa hoy WhatsApp Business app en celular del negocio, sin integración programática. Para meter el agente IA necesitamos WhatsApp Cloud API. Las opciones:

1. **Coexistence**: app móvil + Cloud API en mismo número
2. **Cloud API directo**: migrar el número y perder la app
3. **BSP intermediario** (Wati, Sleekflow, 360dialog): managed solution

## Decisión

**Coexistence Mode** con el número actual del negocio.

## Razones

1. **Cero disrupción al equipo**: siguen usando la app móvil como hasta hoy
2. **Llamadas y grupos siguen funcionando** en la app
3. **Costo casi nulo**: ~$10-20 USD/mes en mensajes (vs $30-500 USD/mes de un BSP)
4. **Sin vendor lock-in**: directo con Meta
5. **Mismo número que clientes conocen**: cero confusión
6. **Reversible**: si conviene migrar a Cloud API directo en 12 meses, se puede

## Alternativas descartadas

### Cloud API directo (sin app)
- Pros: trazabilidad total, multi-agente nativo en Odoo
- Contras: equipo pierde la app, sin llamadas, sin grupos
- Veredicto: muy disruptivo para arrancar; eventualmente puede ser el destino, no el punto de partida

### BSP intermediario
- Pros: UX pulida, soporte humano
- Contras: $30-500 USD/mes, vendor lock-in, conversaciones fuera de Odoo
- Veredicto: no necesario para volumen actual

## Implicaciones operativas

### Lo que cambia para el equipo
- Mensajes siguen llegando al celular como siempre
- También llegan a Odoo (via webhook → n8n → discuss.channel)
- Los del agente IA salen desde Odoo/n8n, también se ven en celular
- Si un cliente responde, el equipo lo ve en celular Y en Odoo

### Lo que se pierde (limitaciones de Coexistence)
- **Listas de difusión** en la app: desactivadas. Reemplazar con plantillas API
- **Mensajes que desaparecen, view-once, editar/borrar**: no funcionan en 1:1
- **WhatsApp Pay**: no aplica (no usamos)
- **Grupos**: siguen funcionando en la app pero NO sincronizan a la API. Para automatización solo 1:1
- **Llamadas**: siguen en la app pero no se pueden hacer desde Odoo

### Requisito crítico
**Alguien del equipo DEBE abrir la WA Business app al menos 1 vez cada 14 días**. Si no se abre, la conexión expira y hay que reconectar.

Responsable propuesto: [definir en reunión]
Frecuencia: semanal (recordatorio en calendario)

## Setup técnico

```
1. Verificar requisitos:
   - WA Business app versión 2.24.17+ instalada
   - Número en uso activo en la app >7 días
   - No registrado en otra Cloud API actualmente

2. Meta Business Manager (business.facebook.com):
   - Crear cuenta si no existe
   - Verificar identidad de la empresa (1-3 semanas)
   - Crear WhatsApp Business Account (WABA)
   - Asignar permisos a usuarios

3. Embedded Signup (desde n8n o Meta UI):
   - Conectar el número del negocio
   - Activar opción Coexistence
   - Sincronizar últimos 6 meses de historial

4. Configurar webhooks:
   - URL: n8n endpoint
   - Verify token: custom
   - Subscribe a: messages, message_status, account_update

5. Crear plantillas iniciales:
   - lead_received
   - cotizacion_lista
   - quote_followup_24h
   - orden_confirmada
   - arte_requerido

6. Cada plantilla: 24-72h de aprobación Meta
```

## Riesgos

| Riesgo | Probabilidad | Mitigación |
|---|---|---|
| Verificación Meta tarda más de 3 semanas | Media | Iniciar trámite YA, en paralelo a otras fases |
| Plantilla rechazada por Meta | Media | Diseñar conservadoras, evitar lenguaje promocional |
| Equipo olvida abrir app y expira conexión | Media | Recordatorio semanal en calendario + monitoreo n8n |
| Número marcado como spam | Baja | Política: nunca enviar masivos no solicitados |
| Quality rating del número baja | Baja | Monitorear en Meta Business Manager |
| Cliente confundido por mensajes "robóticos" | Baja | Disclosure transparente desde primer mensaje |

## Costos

- **Suscripción**: $0 USD (Cloud API directo de Meta)
- **Mensajes recibidos del cliente**: gratis siempre
- **Mensajes salientes dentro de ventana 24h**: gratis (service messages)
- **Plantillas Utility** (cotización, status): ~$0.005-0.01 USD/mensaje en México
- **Plantillas Marketing** (campañas): ~$0.04 USD/mensaje

**Estimación mensual** (200 leads, 5 mensajes utility cada uno + 50 marketing):
- 1000 utility × $0.008 = $8
- 50 marketing × $0.04 = $2
- **Total ~$10-15 USD/mes**

## Tareas derivadas

- [ ] Decisión final del equipo (pendiente reunión)
- [ ] Designar "WhatsApp Admin" responsable
- [ ] Designar persona que abre la app cada 14 días
- [ ] Iniciar trámite Meta Business Manager
- [ ] Esperar verificación (1-3 semanas)
- [ ] Activar Coexistence
- [ ] Diseñar y enviar plantillas a aprobación
- [ ] Setup webhook endpoint en n8n
- [ ] Test manual de envío/recepción antes del piloto del agente

## Plan de migración futura (opcional)

Si en 6-12 meses queremos pasar a Cloud API directo (camino B), el proceso es:
1. Migración técnica: ~1 día (deshabilitar Coexistence, reconfigurar webhooks)
2. Capacitación del equipo: ~1 semana
3. Período de transición con 2 personas usando ambos canales: ~2 semanas
4. Cierre definitivo de la app móvil

Esta migración solo conviene cuando todo el equipo esté usando Odoo de manera fluida y el volumen justifique perder llamadas/grupos.
