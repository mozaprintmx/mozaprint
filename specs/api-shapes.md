# API Shapes — Payloads JSON entre componentes

> Contratos de datos entre Odoo, n8n, Claude y WhatsApp. Claude Code consulta esto para validar payloads.

## Convención

- Snake_case en payloads de Odoo
- camelCase en payloads de Meta y Anthropic
- Cada shape tiene ejemplo de input y output
- Cuando un campo es opcional, se marca con `?`

---

## 1. Webhook entrante de Meta WhatsApp → n8n

**Endpoint**: `https://n8n.mozaprintmx.com/webhook/wa-incoming`

**Shape body**:
```json
{
  "object": "whatsapp_business_account",
  "entry": [{
    "id": "<WABA_ID>",
    "changes": [{
      "field": "messages",
      "value": {
        "messaging_product": "whatsapp",
        "metadata": {
          "display_phone_number": "5215277226277",
          "phone_number_id": "<PHONE_NUMBER_ID>"
        },
        "contacts": [{
          "profile": {"name": "Juan Pérez"},
          "wa_id": "5215555555555"
        }],
        "messages": [{
          "from": "5215555555555",
          "id": "wamid.XXX",
          "timestamp": "1729728000",
          "type": "text|image|document|audio|video|location",
          "text": {"body": "<contenido>"}
        }]
      }
    }]
  }]
}
```

**Headers críticos**:
- `X-Hub-Signature-256`: HMAC SHA256 del body con app secret de Meta

---

## 2. n8n → Anthropic API

**Endpoint**: `POST https://api.anthropic.com/v1/messages`

**Shape request**:
```json
{
  "model": "claude-haiku-4-5-20251001",
  "max_tokens": 1024,
  "system": [
    {
      "type": "text",
      "text": "<system prompt>",
      "cache_control": {"type": "ephemeral"}
    }
  ],
  "messages": [
    {
      "role": "user",
      "content": "Hola, quiero cotizar plumas"
    },
    {
      "role": "assistant",
      "content": [
        {
          "type": "tool_use",
          "id": "toolu_XXX",
          "name": "search_product",
          "input": {"query": "plumas"}
        }
      ]
    },
    {
      "role": "user",
      "content": [{
        "type": "tool_result",
        "tool_use_id": "toolu_XXX",
        "content": "[{\"id\": 123, \"name\": \"Pluma metálica\"}]"
      }]
    }
  ],
  "tools": [
    {
      "name": "search_product",
      "description": "...",
      "input_schema": {"type": "object", "properties": {...}}
    }
  ]
}
```

**Shape response (text)**:
```json
{
  "id": "msg_XXX",
  "type": "message",
  "role": "assistant",
  "content": [
    {"type": "text", "text": "Mucho gusto Juan. ¿Cuántas plumas necesitas?"}
  ],
  "stop_reason": "end_turn",
  "usage": {
    "input_tokens": 1234,
    "output_tokens": 56,
    "cache_creation_input_tokens": 0,
    "cache_read_input_tokens": 1000
  }
}
```

**Shape response (tool use)**:
```json
{
  "id": "msg_YYY",
  "content": [
    {"type": "text", "text": "Déjame buscar..."},
    {
      "type": "tool_use",
      "id": "toolu_ZZZ",
      "name": "create_quote_draft",
      "input": {
        "partner_id": 42,
        "product_id": 567,
        "qty": 500,
        "tecnica": "serigrafia",
        "tintas": 1
      }
    }
  ],
  "stop_reason": "tool_use",
  "usage": {...}
}
```

---

## 3. n8n → Odoo JSON-2 API

> ⚠️ **La JSON-2 API devuelve el resultado CRUDO** del método (una lista en
> `search_read`, una lista de ids en `create`, un `bool` en `write`), **NO**
> envuelto en `{"result": ...}`. Los errores llegan como status HTTP no-2xx.

### 3.1 Search & Read

**Endpoint**: `POST /json/2/<model>/search_read`

**Request**:
```json
{
  "domain": [["state", "=", "draft"], ["partner_id", "=", 42]],
  "fields": ["id", "name", "amount_total"],
  "limit": 10,
  "order": "create_date desc"
}
```

**Response** (lista directa, sin envoltura):
```json
[
  {"id": 1234, "name": "S00123", "amount_total": 15094.93}
]
```

### 3.2 Create

**Endpoint**: `POST /json/2/<model>/create`

> Odoo 19 usa `model_create_multi`: el payload es `vals_list` (una **lista** de
> dicts) y la respuesta es la **lista de ids** creados.

**Request**:
```json
{
  "vals_list": [
    {
      "name": "Lead nuevo",
      "contact_name": "Juan Pérez",
      "phone": "+525555555555",
      "x_studio_collected_qty": 500
    }
  ]
}
```

**Response** (lista de ids cruda):
```json
[<new_id>]
```

### 3.3 Write

**Endpoint**: `POST /json/2/<model>/write`

**Request**:
```json
{
  "ids": [1234],
  "vals": {
    "state": "sent",
    "x_ai_mode": "paused"
  }
}
```

**Response** (bool crudo):
```json
true
```

### 3.4 Call method

**Endpoint**: `POST /json/2/<model>/<method>`

**Request**:
```json
{
  "ids": [1234],
  "kwargs": {}
}
```

---

## 4. Tool responses (n8n → Claude)

Cada tool tiene su shape de respuesta. Claude Code consulta `specs/ai-agent-spec.md` para signatures completas. Ejemplos clave:

### 4.1 search_product

```json
[
  {
    "id": 567,
    "sku": "EX-086",
    "name": "AGENDA DIARIA FALUN",
    "category": "Sets > Agendas",
    "price_base": 154.35,
    "tecnica_default": "serigrafia",
    "area_max_cm2": 100,
    "in_stock": true,
    "variants_count": 3,
    "image_url": "https://..."
  }
]
```

### 4.2 create_quote_draft (caso parametrizado)

```json
{
  "sale_order_id": 1234,
  "sale_order_name": "S00123",
  "subtotal": 15350.00,
  "discount_applied": 2302.50,
  "discount_label": "Descuento volumen 15%",
  "tax_amount": 2086.43,
  "total_with_tax": 15094.93,
  "requires_human_approval": false,
  "missing_info": [],
  "estimated_delivery_days": 10,
  "estimated_delivery_date": "2026-06-05",
  "lines": [
    {
      "section": "Producto",
      "product": "AGENDA FALUN AZUL",
      "qty": 500,
      "unit_price": 147.35,
      "subtotal": 73675.00
    },
    {
      "section": "Personalización",
      "product": "Serigrafía 1 tinta",
      "qty": 500,
      "unit_price": 17.00,
      "subtotal": 8500.00
    }
  ]
}
```

### 4.3 create_quote_draft (caso requiere aprobación humana)

```json
{
  "sale_order_id": 1234,
  "sale_order_name": "S00123",
  "subtotal": 73675.00,
  "requires_human_approval": true,
  "missing_info": ["costo_personalizacion_bordado_2_colores_500pza"],
  "approval_request_id": 56,
  "estimated_human_response_minutes": 30,
  "lines": [
    {
      "section": "Producto",
      "product": "AGENDA FALUN AZUL",
      "qty": 500,
      "unit_price": 147.35,
      "subtotal": 73675.00
    }
  ],
  "pending_lines_description": "Bordado 2 colores en 500 piezas - en cotización con proveedor"
}
```

### 4.4 escalate_to_human

```json
{
  "success": true,
  "channel_id": 89,
  "activity_id": 123,
  "assigned_to": {
    "user_id": 5,
    "name": "María Vendedora",
    "email": "maria@mozaprintmx.com"
  },
  "estimated_response_minutes": 30,
  "notification_sent_via": ["odoo_discuss", "email", "whatsapp_internal"]
}
```

---

## 5. n8n → Meta WhatsApp (saliente)

### 5.1 Texto libre (ventana 24h)

**Endpoint**: `POST https://graph.facebook.com/v18.0/<phone_number_id>/messages`

**Headers**: `Authorization: Bearer <token>`

**Request**:
```json
{
  "messaging_product": "whatsapp",
  "to": "5215555555555",
  "type": "text",
  "text": {
    "body": "Hola Juan, anoto: 500 plumas con serigrafía 1 tinta. ¿Para cuándo?",
    "preview_url": false
  }
}
```

**Response success**:
```json
{
  "messaging_product": "whatsapp",
  "contacts": [{"input": "5215555555555", "wa_id": "5215555555555"}],
  "messages": [{"id": "wamid.XXX"}]
}
```

### 5.2 Plantilla con documento PDF

**Request**:
```json
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
            "link": "https://mozaprintmx.odoo.com/web/content/12345?access_token=abc&download=true",
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

---

## 6. Webhook saliente de Odoo → n8n

**Headers**: `X-Odoo-Signature: sha256=<hmac>`

**Shape body**:
```json
{
  "event": "<model>.<event_type>",
  "timestamp": "2026-05-22T18:45:00Z",
  "database": "mozaprint-prod",
  "record": {
    "id": 1234,
    "model": "sale.order",
    "values": {
      "id": 1234,
      "name": "S00123",
      "state": "sale",
      "partner_id": [42, "Empresa X SA de CV"],
      "amount_total": 15094.93,
      "order_line": [
        {"product_id": [567, "AGENDA FALUN"], "qty": 500}
      ]
    }
  }
}
```

**Eventos esperados**:
- `sale.order.create`
- `sale.order.write` (con state cambiado a 'sale')
- `crm.lead.create`
- `x_approval_request.write` (con status='approved')
- `product.template.create`
- `mail.message.create` (en discuss.channel whatsapp con ai_mode=auto)

---

## 7. Shape interno: contexto del agente

Cuando n8n llama a Claude para responder en una conversación, construye este contexto:

```json
{
  "channel": {
    "id": 89,
    "channel_type": "whatsapp",
    "x_ai_mode": "auto",
    "x_ai_turn_count": 3
  },
  "customer": {
    "is_new": false,
    "partner_id": 42,
    "name": "Juan Pérez",
    "company": "Empresa X SA de CV",
    "email": "juan@empresax.com",
    "phone": "+525555555555",
    "open_quotes_count": 1,
    "recent_orders_count": 3,
    "industry_detected": "marketing_agency",
    "language_preference": "es"
  },
  "conversation": {
    "started_at": "2026-05-22T17:00:00Z",
    "last_message_at": "2026-05-22T18:43:00Z",
    "messages": [
      {
        "role": "user",
        "content": "hola, quiero cotizar plumas",
        "timestamp": "2026-05-22T17:00:00Z"
      },
      {
        "role": "assistant",
        "content": "¡Hola Juan! ...",
        "timestamp": "2026-05-22T17:00:05Z",
        "tools_called": []
      }
    ]
  },
  "system": {
    "current_time": "2026-05-22T18:45:00Z",
    "business_hours_now": false,
    "expected_human_response_minutes": 240
  }
}
```

---

## 8. Anonimización para logging

Cuando se loggean payloads, los siguientes campos se ofuscan:

| Campo original | Campo loggeado |
|---|---|
| `phone: "+525555555555"` | `phone: "+52***5555"` |
| `email: "juan@empresax.com"` | `email: "j***@empresax.com"` |
| `name: "Juan Pérez Martínez"` | `name: "J*** P***"` |
| `address: "..."` | `address: "[REDACTED]"` |
| `rfc: "..."` | `rfc: "[REDACTED]"` |
| `body: "<contenido mensaje>"` | Sólo primeros 100 chars + length |

SKUs, IDs, montos y categorías NO se ofuscan (no son PII).

---

## 9. Errores estándar

Todos los errores devueltos por workflows de n8n siguen este shape:

```json
{
  "error": true,
  "error_code": "AGENT_TIMEOUT|TOOL_NOT_FOUND|ODOO_5XX|META_RATE_LIMIT|...",
  "error_message": "Descripción humana",
  "context": {
    "workflow": "ai-agent-respond",
    "node": "Anthropic API call",
    "attempt": 3,
    "channel_id": 89
  },
  "retry_after_seconds": 60,
  "should_escalate": true
}
```

Cuando un workflow devuelve este error:
- Si `should_escalate=true`, escalar conversación a humano
- Si `retry_after_seconds > 0`, programar retry
- Loggear siempre el error completo (anonimizado)
