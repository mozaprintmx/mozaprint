# ADR 005: n8n como router único de WhatsApp + camino de inbox escalable en Odoo

**Fecha**: 2026-06-02
**Estado**: Aceptado
**Decisores**: Equipo Mozaprint

## Contexto

La WhatsApp Cloud API permite configurar **UN SOLO webhook por número de teléfono**. Esto significa que solo un sistema puede recibir directamente los mensajes entrantes de Meta. No es posible conectar simultáneamente n8n y Odoo (ni n8n y un BSP) como receptores directos del mismo número.

Además, el negocio planea crecer el equipo de vendedores. Hoy son 2 operadores que contestan desde la WhatsApp Business App + WhatsApp Web/Desktop, pero ese modelo no escala bien más allá de 4-5 personas (límite de dispositivos vinculados, sin asignación de conversaciones, sin supervisión).

Se evaluaron dos arquitecturas:

- **Opción A**: n8n es el dueño del webhook, el inbox multi-agente se construye sobre Odoo
- **Opción B**: un BSP (Wati, Chatwoot, etc.) es el dueño del webhook, con inbox profesional listo

## Decisión

**n8n es el receptor único del webhook de la Cloud API (Opción A)**. Odoo y el resto de sistemas reciben la información a través de n8n, que actúa como router central. El inbox multi-agente para escalar el equipo de vendedores se construirá sobre Odoo en etapas, no mediante un BSP.

## Razones

1. **Integración total**: el inbox en Odoo queda pegado a leads, cotizaciones, clientes e historial. Un vendedor ve la conversación y el contexto completo del cliente sin salir de Odoo.
2. **Sin costo por agente**: los BSP cobran por agente/mes. Crecer vendedores en Odoo solo implica el costo del usuario interno que ya se paga.
3. **El agente IA mantiene flexibilidad**: vive en n8n con sus 12 tools y human-in-the-loop, sin restricciones de un BSP.
4. **Un solo sistema**: el equipo aprende Odoo, no Odoo + una plataforma externa.
5. **Sin vendor lock-in**.

## Arquitectura resultante

```
Cliente → Meta Cloud API → (webhook único) → n8n → reparte a:
   ├── Odoo          (datos: leads, cotizaciones, registro de conversaciones)
   ├── LLM provider  (Claude/OpenAI)
   └── Meta          (respuestas de vuelta al cliente)
```

## Plan de crecimiento por etapas

### Etapa 1 — actual (pocos vendedores)
n8n recibe todos los mensajes. El agente responde lo automatizable. Al escalar, el vendedor contesta desde la WhatsApp Business App / Desktop (gracias a Coexistence, ve toda la conversación espejada).

El manejo de doble-respuesta se controla vía `x_ai_mode` (`auto` / `paused` / `manual`): cuando el vendedor escribe desde la app, n8n detecta el mensaje saliente no generado por el agente y pausa el agente automáticamente.

### Etapa 2 — creciendo (4-8 vendedores)
Construir inbox en Odoo. Las conversaciones se sincronizan a `discuss.channel`; los vendedores se asignan y contestan desde Odoo; n8n envía sus mensajes a Meta. El agente sigue atendiendo lo automatizable.

### Etapa 3 — escala mayor (8+ vendedores)
Inbox maduro en Odoo con asignación (round-robin o manual), métricas por vendedor y supervisión.

## Consecuencias

### Positivas
- Camino de crecimiento sin rehacer arquitectura (n8n siempre es el router)
- Costo controlado, integración total con el negocio
- Agente IA flexible sin restricciones de BSP

### Negativas / trade-offs
- El inbox en Odoo requiere más desarrollo que comprar un BSP
- La UI de Discuss de Odoo para WhatsApp es funcional pero menos pulida que Wati/Chatwoot
- Si el volumen llegara a ser muy alto (cientos de conversaciones/día, 10+ agentes), reevaluar Chatwoot self-hosted o un BSP

## Limitación técnica documentada (clave)

**UN número de Cloud API = UN webhook = UN receptor (n8n).** Cualquier otro sistema (Odoo, inbox, BSP) recibe los datos a través de n8n, nunca en paralelo desde Meta.

**No intentar** conectar el módulo nativo de WhatsApp de Odoo al mismo número mientras n8n sea el webhook: pelearían por el webhook y solo uno funcionaría.

## Tareas derivadas (futuras, no inmediatas)

- [ ] Definir política de notificación al escalar (grupo interno, round-robin o vendedor fijo) — pendiente de decisión del equipo
- [ ] Diseñar el inbox de Odoo cuando se llegue a Etapa 2
- [ ] Documentar el flujo de sincronización bidireccional Odoo ↔ n8n ↔ Meta
