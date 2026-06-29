# Integraciones — Mozaprint

> Documentación de APIs externas y patrones de integración. Claude Code consulta esto para implementar conexiones.

## Resumen

Mozaprint integra con:
1. **Meta WhatsApp Cloud API** (entrante y saliente)
2. **Anthropic Claude API** (LLM)
3. **Odoo JSON-2 API** (entrante a Odoo desde n8n)
4. **Proveedor: Promo Opción** (catálogo, precios, stock)
5. **Proveedor: 4Promotional** (catálogo, precios, stock)
6. **Proveedor: Innovation Line** (catálogo, precios, stock)

Todas las integraciones pasan por n8n. Odoo no llama APIs externas en V1.

---

## 1. Meta WhatsApp Cloud API

### Auth
- Bearer token de larga duración del Business Manager
- Phone Number ID del número conectado
- WhatsApp Business Account ID

### Endpoints clave

**Enviar mensaje de texto (free-form, dentro de ventana 24h)**:
```http
POST https://graph.facebook.com/v18.0/{phone_number_id}/messages
Authorization: Bearer {token}
Content-Type: application/json

{
  "messaging_product": "whatsapp",
  "to": "5215555555555",
  "type": "text",
  "text": {
    "body": "Hola Juan, anoto tu solicitud..."
  }
}
```

**Enviar plantilla aprobada (cualquier momento)**:
```http
POST https://graph.facebook.com/v18.0/{phone_number_id}/messages

{
  "messaging_product": "whatsapp",
  "to": "5215555555555",
  "type": "template",
  "template": {
    "name": "cotizacion_lista",
    "language": {"code": "es_MX"},
    "components": [
      {
        "type": "header",
        "parameters": [{
          "type": "document",
          "document": {
            "link": "https://mozaprintmx.odoo.com/web/content/...",
            "filename": "Cotizacion_S00123.pdf"
          }
        }]
      },
      {
        "type": "body",
        "parameters": [
          {"type": "text", "text": "Juan Pérez"},
          {"type": "text", "text": "S00123"},
          {"type": "text", "text": "$15,094.93"},
          {"type": "text", "text": "29/05/2026"}
        ]
      }
    ]
  }
}
```

**Recibir mensajes (webhook)**:
n8n expone un webhook. Meta lo verifica con GET una vez, luego envía POST por cada mensaje.

Shape del POST entrante:
```json
{
  "object": "whatsapp_business_account",
  "entry": [{
    "id": "WABA_ID",
    "changes": [{
      "field": "messages",
      "value": {
        "messaging_product": "whatsapp",
        "metadata": {
          "display_phone_number": "5215277226277",
          "phone_number_id": "PHONE_NUMBER_ID"
        },
        "contacts": [{
          "profile": {"name": "Juan Pérez"},
          "wa_id": "5215555555555"
        }],
        "messages": [{
          "from": "5215555555555",
          "id": "wamid.XXX",
          "timestamp": "1729728000",
          "type": "text",
          "text": {"body": "hola, quiero cotizar plumas"}
        }]
      }
    }]
  }]
}
```

### Reglas y limits
- Ventana de 24h: después del último mensaje del cliente, podemos enviar free-form 24h. Después, sólo templates.
- Templates: deben aprobarse por Meta. Tiempo: 24-72h. Idioma: `es_MX`.
- Rate limit: depende del tier de la cuenta. Empezamos en Tier 1 (1000 conversaciones/día), suficiente.
- Costos: cada conversación iniciada por la empresa cuenta como utility/marketing según template. ~$0.005-0.04 USD por conversación en México.

### Errores comunes
- `131047`: ventana de 24h cerrada, debes usar template
- `131051`: número del destinatario no es válido o no en WA
- `132000`: número de Meta no verificado / business no aprobado
- `100`: parámetro inválido en payload

### Verificación de firma (seguridad)
Cada POST de Meta incluye header `X-Hub-Signature-256` con HMAC SHA256 del payload con el `app_secret`. Verificar en n8n antes de procesar.

```javascript
// Pseudocódigo n8n function node
const crypto = require('crypto');
const signature = $input.headers['x-hub-signature-256'].replace('sha256=', '');
const computed = crypto
  .createHmac('sha256', $env.META_APP_SECRET)
  .update(JSON.stringify($input.body))
  .digest('hex');
if (signature !== computed) {
  throw new Error('Invalid Meta signature');
}
```

---

## 2. Anthropic Claude API

### Auth
- API key (formato `sk-ant-api03-...`)
- Set en `ANTHROPIC_API_KEY` env var

### Endpoint
```http
POST https://api.anthropic.com/v1/messages
Authorization: x-api-key: {api_key}
anthropic-version: 2023-06-01
Content-Type: application/json
```

### Payload típico (Mozaprint)
```json
{
  "model": "claude-haiku-4-5-20251001",
  "max_tokens": 1024,
  "system": "Eres Moza, asistente virtual de Mozaprint...",
  "messages": [
    {"role": "user", "content": "Hola, quiero cotizar plumas"}
  ],
  "tools": [
    {
      "name": "search_product",
      "description": "Busca producto en catálogo Mozaprint",
      "input_schema": {
        "type": "object",
        "properties": {
          "query": {"type": "string"},
          "limit": {"type": "integer", "default": 5}
        },
        "required": ["query"]
      }
    }
  ]
}
```

### Modelo según caso de uso

| Caso | Modelo | Razón |
|---|---|---|
| FAQ y conversación general | `claude-haiku-4-5-20251001` | Más barato, latencia baja, suficiente para FAQ |
| Cotización con tool use complejo | `claude-sonnet-4-6` | Mejor razonamiento, multi-step tool calls |
| Análisis de listas de precios (PDFs) | `claude-sonnet-4-6` | Mejor extracción de datos estructurados |
| Generación de descripciones de producto | `claude-haiku-4-5-20251001` | Volumen alto, suficiente calidad |

### Tool use loop
Cuando Claude decide llamar un tool, devuelve:
```json
{
  "content": [
    {"type": "text", "text": "Déjame buscar..."},
    {
      "type": "tool_use",
      "id": "toolu_XXX",
      "name": "search_product",
      "input": {"query": "plumas metálicas", "limit": 5}
    }
  ],
  "stop_reason": "tool_use"
}
```

n8n ejecuta el tool, devuelve el resultado en el siguiente turno:
```json
{
  "messages": [
    {"role": "user", "content": "..."},
    {"role": "assistant", "content": [...tool_use...]},
    {
      "role": "user",
      "content": [{
        "type": "tool_result",
        "tool_use_id": "toolu_XXX",
        "content": "[{\"id\": 123, \"name\": \"Pluma metálica X\", ...}]"
      }]
    }
  ]
}
```

Continuar el loop hasta que `stop_reason = "end_turn"`.

### Prompt caching (importante para reducir costos)
System prompts grandes (knowledge base) se cachean con:
```json
{
  "system": [
    {
      "type": "text",
      "text": "Eres Moza...",
      "cache_control": {"type": "ephemeral"}
    }
  ]
}
```

Cache vive 5 min por default. Repetir el system prompt en siguientes llamadas en esa ventana cuesta 10% del precio normal.

### Errores comunes
- `429`: rate limit, hacer backoff exponencial
- `500/503`: error de Anthropic, retry
- `overloaded_error`: modelo saturado, retry con jitter
- `invalid_request_error`: payload mal formado

---

## 3. Odoo JSON-2 API

### Auth
- Bearer token de API key del usuario **Rosy Ponce** (`rosy_ponce@mozaprintmx.com`,
  permisos reducidos; ver `docs/usuarios-odoo.md`). NO existe un usuario `integration@`.
- Header `Authorization: Bearer {key}`
- Header `DATABASE: {db_name}` si la instancia tiene multi-db

> ⚠️ Las respuestas de la JSON-2 API son **crudas** (lista/dict/bool), sin
> envoltura `{"result": ...}`. Ver `specs/api-shapes.md` §3 para los shapes.

### Endpoints base

```http
POST https://mozaprintmx.odoo.com/json/2/{model}/{method}
Authorization: Bearer {api_key}
Content-Type: application/json
```

### Operaciones típicas

**Buscar y leer**:
```bash
POST /json/2/product.product/search_read
{
  "domain": [
    ["default_code", "in", ["EX-086", "MTZ-100"]]
  ],
  "fields": ["id", "default_code", "name", "list_price", "qty_available"],
  "limit": 100
}
```

**Crear** (Odoo 19 `model_create_multi`: `vals_list` es una lista; devuelve `[id]` crudo):
```bash
POST /json/2/crm.lead/create
{
  "vals_list": [
    {
      "name": "Cotización plumas - Empresa X",
      "contact_name": "Juan Pérez",
      "email_from": "juan@empresax.com",
      "phone": "+525555555555",
      "x_studio_collected_qty": 500
    }
  ]
}
```

**Actualizar**:
```bash
POST /json/2/sale.order/write
{
  "ids": [1234],
  "vals": {"state": "sent"}
}
```

**Llamar método del modelo**:
```bash
POST /json/2/sale.order/action_quotation_send
{
  "ids": [1234]
}
```

### Documentación dinámica
La instancia expone su propia doc en:
```
GET https://mozaprintmx.odoo.com/doc
```

Muestra todos los modelos y campos disponibles con su tipo. Útil consultarla cuando se duda de un nombre de campo.

### Rate limits
- Odoo Online no documenta rate limits oficiales
- Empíricamente: 30 req/seg sostenido funciona
- Para sync masivos, usar `batch` cuando sea posible

### Patrón retry recomendado
```javascript
async function odooCall(model, method, payload, retries = 3) {
  for (let i = 0; i < retries; i++) {
    try {
      const response = await fetch(`${ODOO_URL}/json/2/${model}/${method}`, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${API_KEY}`,
          'Content-Type': 'application/json'
        },
        body: JSON.stringify(payload)
      });
      if (response.ok) return await response.json();
      if (response.status >= 500) {
        await sleep(Math.pow(2, i) * 1000);
        continue;
      }
      throw new Error(`Odoo error: ${response.status}`);
    } catch (e) {
      if (i === retries - 1) throw e;
      await sleep(Math.pow(2, i) * 1000);
    }
  }
}
```

---

## 4. Webhooks salientes desde Odoo

Configurar en `Settings → Technical → Webhooks`. Cada uno apunta a un endpoint de n8n con HMAC signature.

### Configuración estándar

| Field | Valor |
|---|---|
| Model | (según evento) |
| Trigger | On creation / On update / On deletion |
| URL | `https://n8n.mozaprintmx.com/webhook/{workflow-id}` |
| HTTP method | POST |
| Sign with key | (clave HMAC compartida) |

### Payload típico
```json
{
  "model": "sale.order",
  "event": "create",
  "record_ids": [1234],
  "record_data": {
    "id": 1234,
    "name": "S00123",
    "state": "draft",
    ...
  },
  "timestamp": "2026-05-22T18:45:00Z",
  "signature": "sha256=abc123..."
}
```

### Verificación en n8n
```javascript
const crypto = require('crypto');
const expected = crypto
  .createHmac('sha256', $env.ODOO_WEBHOOK_SECRET)
  .update(JSON.stringify($input.body))
  .digest('hex');
if (`sha256=${expected}` !== $input.headers['x-odoo-signature']) {
  throw new Error('Invalid Odoo webhook signature');
}
```

---

## 5. Proveedores

Mozaprint sincroniza catálogo, precios y stock de tres proveedores:
**4Promotional (4P)**, **Innovation Line (INN)** y **Promo Opción (PO)**.

> 🔒 El **detalle de integración del sync** (endpoints, autenticación, paginación,
> lógica por proveedor, cadencia/horarios) **NO se documenta en este repo público**.
> Vive en `analysis/AUDITORIA_SYNC.md` (local, **gitignored**). Hoy el sync corre
> como un paquete Python independiente (XML-RPC); su migración a n8n/JSON-2 es Fase 8.

### Interfaz común propuesta

Cada proveedor implementa un workflow n8n con estos sub-workflows:

```
proveedor-{nombre}-fetch-catalog
  → output: lista de productos con shape estándar

proveedor-{nombre}-fetch-pricing(skus[])
  → output: precios actuales

proveedor-{nombre}-fetch-inventory(skus[])
  → output: stock disponible

proveedor-{nombre}-create-po(sale_order_id)
  → output: po_id del proveedor
```

### Shape estándar de producto del proveedor

Para que el código de orquestación sea uniforme, cada proveedor mapea su respuesta a:

```typescript
type ProductoProveedor = {
  proveedor: 'promo_opcion' | '4promotional' | 'innovationline';
  sku_proveedor: string;
  nombre: string;
  descripcion: string;
  categoria_proveedor: string;
  costo: number; // sin IVA, MXN
  moneda: 'MXN' | 'USD';
  stock_disponible: number;
  unidad_minima: number;
  imagenes_urls: string[];
  atributos: {
    color?: string;
    material?: string;
    medidas?: string;
    [key: string]: any;
  };
  tecnicas_disponibles?: string[];
  area_impresion?: string;
  fecha_actualizacion: string; // ISO datetime
};
```

Cada workflow proveedor transforma su payload propio a esta forma.

---

## Seguridad transversal

### Secrets management
- **Nunca** hardcodear API keys
- En n8n: usar Credentials con vault
- En Odoo: usar `ir.config_parameter` con scope private
- Rotación trimestral mínima

### Rate limiting outbound
n8n debe respetar rate limits de cada API:
- Anthropic: max 50 req/min en tier 1
- Meta WA: depende de quality rating del número
- Odoo: ~30 req/seg sostenido
- Proveedores: variable, conservador 10 req/min

### Logging
Toda llamada a API externa loggea:
- Timestamp
- Endpoint
- Status code
- Latencia
- ID de la entidad relacionada (lead_id, sale_order_id)
- En errores: payload anonimizado

NO loggear:
- Bodies completos de mensajes WA (PII)
- API keys
- Tokens de sesión
- Datos personales del cliente
