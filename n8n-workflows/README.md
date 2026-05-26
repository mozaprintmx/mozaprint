# Workflows n8n — Mozaprint

> Workflows exportados como JSON, versionados con el resto del código.

## Workflows actuales

### ai-agent-respond.json
**Estado**: 🟡 Borrador de referencia
**Trigger**: Webhook Meta WhatsApp (POST /webhook/wa-incoming)
**Propósito**: Loop principal del agente WhatsApp. Recibe mensaje del cliente, verifica modo del channel, llama a Claude con tools, envía respuesta.

### lead-intake-whatsapp.json (pendiente)
**Estado**: 🔴 Sin crear
**Propósito**: Cuando llega un mensaje de un número no registrado, crea contacto, channel y lead en Odoo, inicia conversación.

### cotizacion-aprobar.json (pendiente)
**Estado**: 🔴 Sin crear
**Trigger**: Webhook saliente de Odoo cuando x_approval_request cambia a status='approved'
**Propósito**: Cuando un humano aprueba un costo de personalización, actualiza el sale.order, genera PDF y lo envía al cliente.

### sync-proveedor-promo-opcion.json (pendiente)
**Estado**: 🔴 Sin crear
**Trigger**: Cron nocturno
**Propósito**: Sync de catálogo de Promo Opción a Odoo.

### sync-proveedor-4promotional.json (pendiente)
**Estado**: 🔴 Sin crear
**Trigger**: Cron nocturno

### sync-proveedor-innovationline.json (pendiente)
**Estado**: 🔴 Sin crear
**Trigger**: Cron nocturno

### tool-execute-*.json (pendiente, 12 workflows)
**Estado**: 🔴 Sin crear
**Propósito**: Una por cada tool del agente. Reciben input del agente, ejecutan, devuelven resultado.

Lista:
- tool-execute-search-product
- tool-execute-get-product-details
- tool-execute-check-inventory
- tool-execute-get-customization-options
- tool-execute-find-or-create-partner
- tool-execute-create-lead
- tool-execute-create-quote-draft
- tool-execute-request-human-approval
- tool-execute-get-quote-pdf
- tool-execute-send-whatsapp-document
- tool-execute-escalate-to-human
- tool-execute-get-customer-orders

## Cómo agregar un workflow nuevo

1. Construir el workflow en la UI de n8n
2. Testear con datos de prueba reales (no producción)
3. Click derecho → Download → JSON
4. Guardar como `nombre-del-workflow.json` en este directorio
5. Actualizar este README con descripción
6. Commit al repo

## Cómo importar un workflow

1. En n8n: Workflows → Import from File
2. Seleccionar el JSON
3. **Revisar credenciales**: las credentials no se importan, se referencian por ID. Asegurar que el destino tenga las credenciales correspondientes creadas con el mismo ID/nombre.
4. Revisar variables de entorno usadas (`{{$env.XXX}}`)
5. Activar el workflow

## Convenciones

- Nombres en kebab-case: `ai-agent-respond`, `sync-proveedor-promo-opcion`
- Cada workflow debe tener un comentario inicial (sticky note) explicando:
  - Trigger
  - Inputs esperados
  - Outputs
  - Dependencias (otros workflows, credentials, env vars)
- Error handling: cada workflow debe tener un node "Error Trigger" o equivalente que loggee en Odoo
- Timeouts: HTTP requests con `timeout: 30000` por default
- Retries: usar `Retry On Fail` en nodos críticos (Odoo, Anthropic)

## Variables de entorno usadas

Ver `docs/architecture.md` sección "Variables de entorno necesarias" para la lista completa.

## Convenciones de naming dentro de workflows

- Nodos: Verbo · Servicio · Acción (`Odoo · Find Channel`)
- Function nodes: Verbo descriptivo (`Build Conversation Context`)
- IF nodes: pregunta clara (`¿Channel existe?`, `¿Tool use o end_turn?`)

## Testing

Para test local antes de deploy:
```bash
# Si n8n CLI está instalado:
n8n execute --file ai-agent-respond.json --input test-data/sample-message.json

# Alternativa: usar UI de n8n con "Test Workflow" y mock data
```

## Debugging

- En cada nodo crítico, agregar un "Log Output" o Sticky Note con la forma esperada del data
- Para problemas de producción: revisar el execution log en n8n y la entrada correspondiente en `x_ai_interaction_log` de Odoo
- Si latencia alta: ver tiempos por nodo en el execution log
