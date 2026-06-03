# Arquitectura del sistema Mozaprint

> Documento de referencia para Claude Code. Explica responsabilidades de cada componente y cómo se comunican.

## Diagrama de alto nivel

```
                          ┌────────────────────────┐
                          │      CLIENTE FINAL     │
                          │  (B2B, México)         │
                          └────────────┬───────────┘
                                       │
              ┌────────────────────────┼────────────────────────┐
              │                        │                        │
              ▼                        ▼                        ▼
        ┌──────────┐            ┌──────────────┐         ┌─────────────┐
        │ WhatsApp │            │ Sitio web    │         │ Email       │
        │ (Cloud   │            │ (Odoo Web)   │         │ (formularios│
        │  API)    │            │              │         │  o directos)│
        └────┬─────┘            └──────┬───────┘         └──────┬──────┘
             │                         │                        │
             │                         │                        │
             ▼                         ▼                        ▼
   ┌──────────────────────────────────────────────────────────────────┐
   │                          n8n (orquestador)                       │
   │                                                                  │
   │  ┌──────────────┐  ┌──────────────┐  ┌──────────────────────┐  │
   │  │ Webhook      │  │ Webhook      │  │ Cron schedules       │  │
   │  │ Meta WA      │  │ Odoo events  │  │ (sync, follow-ups)   │  │
   │  └──────┬───────┘  └──────┬───────┘  └─────────┬────────────┘  │
   │         │                 │                    │                │
   │         └─────────────────┼────────────────────┘                │
   │                           │                                     │
   │                           ▼                                     │
   │  ┌────────────────────────────────────────────────────────┐    │
   │  │              Workflows (lógica de negocio)              │    │
   │  │                                                          │    │
   │  │  • lead-intake-whatsapp                                  │    │
   │  │  • ai-agent-respond                                      │    │
   │  │  • cotizacion-aprobar                                    │    │
   │  │  • sync-proveedor-promo-opcion                          │    │
   │  │  • sync-proveedor-4promotional                          │    │
   │  │  • sync-proveedor-innovationline                         │    │
   │  │  • followup-cotizacion-24h                              │    │
   │  │  • inventory-en-vivo                                    │    │
   │  └────────────────────────────────────────────────────────┘    │
   │                           │                                     │
   └───────────────────────────┼─────────────────────────────────────┘
                               │
              ┌────────────────┼────────────────┐
              │                │                │
              ▼                ▼                ▼
   ┌──────────────────┐  ┌──────────────┐  ┌──────────────┐
   │ Odoo Online 19.0 │  │ Anthropic    │  │ APIs         │
   │ Custom           │  │ Claude API   │  │ Proveedores  │
   │                  │  │              │  │ (3)          │
   │ • product.*      │  │ • Haiku 4.5  │  │              │
   │ • crm.lead       │  │ • Sonnet 4.6 │  │ • Promo      │
   │ • sale.order     │  │              │  │   Opción     │
   │ • discuss.channel│  │ Conversación │  │ • 4Promotnl  │
   │ • mail.message   │  │ + tool use   │  │ • Innovation │
   │ • stock.*        │  │              │  │   Line       │
   │                  │  │              │  │              │
   │ JSON-2 API       │  │              │  │              │
   └──────────────────┘  └──────────────┘  └──────────────┘
```

## Principio de separación de responsabilidades

### Odoo = Verdad de datos
Todo lo que es **estado del negocio** vive en Odoo. Productos, clientes, leads, cotizaciones, inventario, órdenes, facturación. Cualquier consulta sobre "qué hay" se resuelve contra Odoo.

Odoo **NO debe**:
- Llamar directamente APIs externas (proveedores, Meta, Anthropic) en V1
- Tener lógica de orquestación compleja en Server Actions (Python sandbox limitado)
- Mantener estado de conversaciones AI fuera de `discuss.channel`

Odoo **SÍ debe**:
- Exponer eventos vía webhooks salientes a n8n
- Aceptar llamadas desde n8n vía JSON-2 API
- Mantener AI Agent nativo solo para livechat web
- Almacenar el resultado de conversaciones AI (mensajes, cotizaciones generadas)

### n8n = Orquestador
n8n es el **pegamento**. Recibe eventos, llama APIs, transforma datos, decide qué hacer.

n8n **SÍ debe**:
- **Ser el receptor único del webhook de Meta WhatsApp** — la Cloud API solo permite un webhook por número; Odoo y cualquier otro sistema reciben los mensajes a través de n8n, nunca directamente desde Meta (ver ADR 005)
- Llamar a Anthropic API con el prompt y contexto
- Llamar a Odoo vía JSON-2 API para crear/actualizar registros
- Llamar a APIs de proveedores para sync
- Mantener logs de cada ejecución
- Manejar reintentos, errores, timeouts
- Ejecutar lógica condicional compleja

n8n **NO debe**:
- Almacenar estado de negocio (eso es Odoo)
- Tener su propia base de datos de productos/clientes
- Reemplazar la UI de Odoo

### Claude (Anthropic API) = Cerebro conversacional
Claude responde mensajes, decide cuándo escalar, identifica intent, llama tools.

Claude **SÍ debe**:
- Conversar en español natural con clientes
- Llamar tools que n8n expone (búsqueda de producto, creación de lead, etc.)
- Razonar sobre el contexto de la conversación
- Decidir escalado a humano

Claude **NO debe**:
- Calcular precios (siempre vienen de Odoo)
- Comprometer plazos sin verificar (vía tool)
- Almacenar memoria entre sesiones (cada turno es stateless desde su perspectiva)
- Tomar decisiones comerciales (aprobaciones, cierre de venta)

## Flujos principales

### Flujo 1: Cliente escribe a WhatsApp por primera vez

```
1. Cliente envía "hola, quiero cotizar plumas"
2. Meta Cloud API → Webhook → n8n (workflow: ai-agent-respond)
3. n8n consulta Odoo: ¿partner existe por phone?
   → No existe → crea contacto básico
4. n8n consulta Odoo: ¿discuss.channel existe?
   → No existe → crea channel con x_ai_mode=auto
5. n8n llama a Claude (Haiku 4.5) con:
   - System prompt (cargado de Odoo o de archivo)
   - Mensaje del cliente
   - Contexto: cliente nuevo
6. Claude responde con saludo + petición de datos
7. n8n envía respuesta vía Meta Cloud API
8. n8n guarda mensaje en mail.message del channel Odoo
9. n8n loggea la interacción
```

### Flujo 2: Cotización con costo parametrizado

```
1. Cliente da datos completos (producto, qty, técnica)
2. Claude (Sonnet 4.6) decide que tiene info suficiente
3. Claude llama tool: create_quote_draft
4. n8n recibe la llamada del tool:
   a. Consulta Odoo: producto, pricelist, servicio personalización
   b. Crea sale.order en draft con líneas
   c. Aplica Promotions de descuento automáticamente
5. n8n llama tool: get_quote_pdf
6. Odoo genera PDF y devuelve URL firmada
7. n8n envía PDF por WhatsApp con plantilla cotizacion_lista
8. Claude responde con mensaje de cierre
9. Conversación queda en modo auto esperando respuesta del cliente
```

### Flujo 3: Cotización con costo NO parametrizado (human-in-the-loop)

```
1. Cliente pide algo que requiere costo no parametrizado (ej. bordado 2 colores)
2. Claude detecta vía tool get_customization_options
3. Claude llama tool: request_human_approval con contexto
4. n8n crea custom.approval.request en Odoo
5. n8n notifica al vendedor (Discuss + actividad + opcional WA al celular)
6. Claude responde al cliente "le paso a un asesor"
7. Vendedor humano cotiza con proveedor (su flujo actual)
8. Vendedor regresa a Odoo y aprueba en custom.approval.request
9. Webhook saliente de Odoo → n8n (workflow: cotizacion-aprobar)
10. n8n actualiza sale.order con la línea aprobada
11. n8n genera PDF y lo envía al cliente
12. Conversación sigue en modo auto
```

### Flujo 4: Sync nocturno de proveedor

```
1. Cron de n8n dispara workflow sync-proveedor-* a las 00:00
2. n8n llama API del proveedor (Promo Opción, etc.)
3. n8n diff contra estado actual (Odoo via JSON-2 search_read)
4. Para cada cambio:
   - Producto nuevo → crea product.template + variants
   - Precio cambió → actualiza product.pricelist
   - Stock cambió → actualiza stock.quant
   - Producto discontinuado → archive (active=false)
5. n8n envía resumen por email al equipo
6. n8n loggea cualquier error para revisión
```

## Webhooks y eventos

### Salientes desde Odoo (configurar en Settings → Technical → Webhooks)

| Evento | Modelo | Trigger | Workflow n8n receptor |
|---|---|---|---|
| Cotización aprobada manualmente | custom.approval.request | status='approved' | cotizacion-aprobar |
| Lead con score alto | crm.lead | x_ai_score > 80 | notificacion-lead-hot |
| Sale order confirmada | sale.order | state='sale' | po-automatica-proveedor |
| Producto creado/modificado | product.template | create or write | sync-back-providers |
| Channel con modo=auto recibe mensaje del cliente | mail.message | create + condiciones | ai-agent-respond |

### Entrantes a Odoo (vía JSON-2 API)

| Endpoint | Llamado por | Propósito |
|---|---|---|
| POST /json2/crm.lead/create | n8n (lead-intake) | Crear lead desde WA o web |
| POST /json2/sale.order/create | n8n (ai-agent) | Crear cotización draft |
| POST /json2/sale.order/{id}/action_quotation_send | n8n | Marcar cotización enviada |
| GET /json2/product.product/search_read | n8n | Búsqueda de producto |
| POST /json2/discuss.channel/{id}/message_post | n8n | Postear mensaje del AI en chatter |

## Variables de entorno necesarias

### En n8n
```
ODOO_URL=https://mozaprint.odoo.com
ODOO_API_KEY=<api key "n8n-produccion" — usuario Rosy Ponce, ver docs/usuarios-odoo.md>
ODOO_DATABASE=<nombre db si multi-db>

ANTHROPIC_API_KEY=<sk-ant-...>
ANTHROPIC_MODEL_FAST=claude-haiku-4-5-20251001
ANTHROPIC_MODEL_DEEP=claude-sonnet-4-6

META_WA_TOKEN=<token de Meta>
META_WA_PHONE_NUMBER_ID=<id del número>
META_WA_BUSINESS_ACCOUNT_ID=<waba id>
META_WA_WEBHOOK_VERIFY_TOKEN=<token custom para verificar webhooks entrantes>

PROVEEDOR_PROMO_OPCION_API_KEY=<...>
PROVEEDOR_4PROMOTIONAL_API_KEY=<...>
PROVEEDOR_INNOVATIONLINE_API_KEY=<...>

LOG_LEVEL=info
NOTIFICATION_EMAIL=ops@mozaprintmx.com
```

### En Odoo
- Webhooks salientes configurados con URL del n8n + token HMAC
- AI Agent nativo configurado con Anthropic provider (vía módulo del marketplace) — sólo para livechat web

## Decisiones arquitectónicas clave

Ver carpeta `decisions/` para detalle. Resumen:

- **n8n self-hosted vs cloud**: self-hosted en VPS chico. Razón: control total, sin per-execution pricing, datos sensibles del cliente.
- **Claude vs OpenAI**: Claude (Haiku + Sonnet). Razón: mejor razonamiento para tool use complejo, prompt caching 90% off.
- **Bridge custom vs BSP**: Bridge custom con n8n. Razón: control total, conversaciones en Odoo, sin vendor lock-in.
- **n8n como router único / inbox escalable en Odoo**: un número de Cloud API = un webhook = n8n. El inbox para escalar el equipo de vendedores se construye sobre Odoo en etapas. Ver ADR 005.
- **JSON-2 vs XML-RPC**: JSON-2 para todo lo nuevo. Razón: XML-RPC deprecado en Online 21.1 (2027).

## Lo que no está construido todavía

Ver `docs/roadmap.md` para qué está en cada fase. Reglas para Claude Code:
- Si trabajas en algo de Fase A, B o C, está documentado y validado
- Si te piden algo que parece de Fase D+, pregunta primero
- Si no aparece en el roadmap, definitivamente pregunta
