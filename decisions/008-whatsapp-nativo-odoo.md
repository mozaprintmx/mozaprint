# ADR 008: WhatsApp nativo de Odoo, con Odoo como dueño del webhook

**Fecha**: 2026-08-31
**Estado**: Propuesto — condicionado a los experimentos A y B (ver «Criterios de aceptación»)
**Decisores**: Juan Carlos Asomoza
**Reemplaza a**: `005-n8n-router-unico-inbox-escalable.md`

## Contexto

La ADR 005 (2026-06-02) decidió que **n8n** fuera el receptor único del webhook de
la Cloud API y prohibió explícitamente conectar el módulo nativo de WhatsApp de
Odoo al mismo número. Esa decisión se tomó cuando:

- Odoo no traía agentes de IA ni MCP.
- El inbox multiagente había que construirlo.
- Se asumía que un solo sistema podía hablar con Meta.

Tres meses después el panorama es otro, y el negocio pidió explícitamente el
módulo nativo para tener campañas de marketing, seguimiento pegado al CRM y envío
de cotizaciones y links **desde Odoo**.

### Lo que cambió

1. **Entrante y saliente no son el mismo problema.** El webhook (entrante) admite
   **un solo** receptor por número. El envío (Graph API) lo puede hacer
   **cualquier** sistema en paralelo. La ADR 005 los trataba como una sola cosa.
2. **Meta permite override de webhook por número y por WABA**, así que un segundo
   número puede enrutarse a otro destino sin pelearse con el primero.
3. **Odoo Online ya es una URL pública HTTPS**, así que el módulo nativo no
   necesita VPS: el VPS deja de ser prerrequisito de las fases 4-7.
4. **Odoo Online NO admite módulos de terceros** (ver ADR 009), así que el catálogo
   de «AI WhatsApp Chatbot for Odoo» del Apps Store no es opción.
5. **El WhatsApp nativo de Odoo no trae IA**: enruta a Discuss y ahí contesta una
   persona. El agente nativo de IA solo responde en el **livechat del sitio web**.

## Decisión

**Odoo es el dueño del webhook de WhatsApp.** Se instalan `whatsapp`,
`whatsapp_crm`, `whatsapp_sale` y `marketing_automation_whatsapp`.

La IA que contesta se resuelve en capas, **después** de que WhatsApp funcione con
personas:

```
Meta Cloud API
     │ webhook
     ▼
  ODOO ONLINE
     ├─ Discuss        conversaciones + inbox del equipo
     ├─ CRM/chatter    pegado al lead y al cliente
     ├─ Cotizaciones   enviar PDF y links desde sale.order
     └─ Mkt Automation campañas visuales con paso de WhatsApp
     │
     │ regla de automatización → acción de servidor `webhook`
     │ (DECLARATIVA — no cuenta como código facturable)
     ▼
  Servicio externo mínimo
     │ lee contexto por JSON-2 / MCP · Claude redacta
     ▼
  Escribe de vuelta en Odoo → Odoo envía por WhatsApp
```

**WhatsApp funciona desde el día 1 con personas.** La IA es una capa posterior que
no cambia la arquitectura: si nunca se enciende, no se pierde nada de lo demás.

## Razones

1. **Es lo que el negocio pidió**: campañas, seguimiento en el CRM y envío de
   cotizaciones desde Odoo. Con n8n como dueño, nada de eso existe sin construirlo.
2. **El historial queda completo dentro de Odoo**, pegado al lead y al cliente.
3. **Cero líneas facturables**: la acción de servidor tipo `webhook` es
   declarativa. Ver ADR 007 para por qué esto no es negociable.
4. **Marketing obtiene UI visual sin código** vía `marketing_automation_whatsapp`,
   módulo oficial de Odoo.
5. **El VPS deja de bloquear.** Pasa de prerrequisito de 4 fases a host opcional
   de una sola capa.
6. **Claude se conserva** (ADR 002), corriendo fuera de Odoo. El agente nativo solo
   habla OpenAI y Gemini.

## Criterios de aceptación (experimentos, en TEST primero)

Esta ADR **no pasa a Aceptado** hasta que ambos se resuelvan.

### Experimento A · ¿Odoo acepta el número en Coexistence?

Es el único que puede tumbar la decisión. La documentación de Odoo dice que el
módulo *"is only compatible with WhatsApp Business Platform Accounts"* y que las
cuentas de **WhatsApp Business App no son compatibles** — pero un número en
Coexistence sí queda registrado en la Business Platform. Nadie lo documenta.

1. Que el módulo acepte las credenciales del número en Coexistence.
2. Que **entre** un mensaje del cliente a Discuss.
3. Que **salga** un mensaje desde Odoo y llegue al celular.
4. ⚠️ **Riesgo principal**: que un mensaje enviado **desde la app del celular**
   aparezca en Odoo. Meta lo manda como *message echo* y el módulo nativo
   probablemente lo ignora → **el historial quedaría partido**.

**Si el punto 4 falla**, las salidas son: migrar el número del todo a Cloud API
(el equipo pierde la app móvil, contra lo decidido en ADR 003), vivir con el
historial partido, o dedicar un segundo número a Odoo.

### Experimento B · ¿El agente nativo contesta en un canal de WhatsApp?

La documentación dice que los agentes trabajan «dentro de Discuss», y las
conversaciones de WhatsApp **son** canales de Discuss. Si un agente se puede sumar
a uno y responder, **se elimina el servicio externo por completo**.

Sin documentar ni a favor ni en contra. Barato de probar, premio grande: va antes
de construir nada externo.

## Alternativas descartadas

### Mantener la ADR 005 (n8n dueño del webhook)
Marketing se queda sin herramienta visual y el VPS sigue bloqueando cuatro fases.
Además obliga a construir tools que las skills nativas y MCP ya cubren.

### Migrar a Odoo.sh para usar módulos de terceros
Desbloquea los chatbots de IA sobre WhatsApp ya hechos, pero cuesta **~$70-100
USD/mes** de hosting sobre las licencias y traslada a Mozaprint el riesgo de
upgrade de código ajeno — justo lo que más dolor ha causado. Ver ADR 009.

### BSP externo con IA incluida (Wati, Respond.io, Chatwoot)
Lo más rápido a una IA contestando, pero **las conversaciones viven fuera de
Odoo**, que contradice de frente el objetivo declarado. Y cobran por agente/mes.

## Consecuencias

### Positivas
- Todo el beneficio nativo pedido, sin código facturable.
- El inbox en Odoo de la «Etapa 2» de la ADR 005 llega gratis con el módulo.
- El VPS pasa a ser opcional y diferible.

### Negativas / trade-offs
- **Se pierde el control fino del agente** que daba n8n como dueño del flujo.
- El riesgo de los *message echoes* puede partir el historial (experimento A).
- Odoo no trae IA sobre WhatsApp: hay que ponerla, y eso reintroduce una pieza
  externa salvo que el experimento B salga bien.
- Depender del módulo nativo nos ata a su ritmo de cambios en cada upgrade.

## Costos operativos

Mensajería directa con Meta, sin BSP, México (por mensaje desde jul-2025):

| Categoría | USD/mensaje | Uso |
|---|---|---|
| Utilidad | **$0.0080** | Cotización lista, anticipo, pedido en producción |
| Marketing | **$0.0436** | Promos masivas |

Las transaccionales son ruido presupuestal al volumen actual; las promos masivas
hay que dosificar.

## Tareas derivadas

- [ ] Experimento A en la base de test (los 4 puntos, en orden)
- [ ] Experimento B en la base de test
- [ ] Decidir la salida si el punto A.4 falla — requiere decisión del negocio
- [ ] Instalar los 4 módulos en producción
- [ ] Plantillas de utilidad a aprobación de Meta (24-72 h)
- [ ] Actualizar `docs/meta-whatsapp-status.md`: el webhook apunta a Odoo, no a n8n
- [ ] Reabrir ADR 003 con el resultado del experimento A
