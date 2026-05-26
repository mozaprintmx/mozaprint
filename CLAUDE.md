# CLAUDE.md — Proyecto Mozaprint

> Contexto persistente para Claude Code. Este archivo se carga automáticamente en cada sesión. Mantener corto y accionable.

## Quién eres en este proyecto

Eres un asistente de desarrollo trabajando junto a un ingeniero en computación que es operador único del proyecto Mozaprint MX (artículos promocionales personalizados).

El stack es **Odoo Online 19.0 Custom + n8n self-hosted + Claude/OpenAI API** (provider definitivo se evalúa en piloto). Toda la lógica de negocio vive en Odoo. La orquestación entre sistemas vive en n8n. Tú escribes el código que el operador despliega en ambos.

## Decisiones del equipo (v1 · 2026-05-24)

Las decisiones operativas ya están tomadas. Ver detalle completo en 
`docs/decisiones-equipo-v1.md` y `decisions/004-decisiones-equipo-v1.md`.

Resumen ejecutivo:
- WhatsApp: **Coexistence Mode** (app móvil + Cloud API mismo número)
- LLM: **Pendiente piloto** (Claude vs OpenAI, evaluación A/B en sprint 5-6)
- DNS: **Cloudflare** authoritative, Hostinger solo registrar
- Orquestador: **n8n self-hosted** en VPS Hetzner CX22 (~€5/mes)
- Repo: **GitHub público**
- Tono del agente: **Tutea por default**, español MX
- Comandos: **en español** (`/tomar`, `/reactivar`, `/pausar`)
- Modo toma vendedor: **híbrido** (auto al primer mensaje + override manual)
- Horario humano: L-V 9-18, Sáb 10-13, Dom cerrado
- Anticipo: 50% estándar / valoración en órdenes >$100k MXN
- Pago: Transferencia (principal) + Mercado Pago
- Técnicas prioritarias: Serigrafía, Tampografía, Bordado, DTF Textil, DTF UV

## Lo que NO debes asumir

- **No tenemos acceso a `addons/` de Odoo**: es Online, no se instalan módulos custom propios. Toda extensión se hace vía Studio (campos custom prefijo `x_`), Automation Rules, Server Actions (Python sandbox limitado), y AI Fields.
- **El sandbox Python de Odoo Online no permite imports arbitrarios**: sólo módulos whitelist (`datetime`, `json`, `re`, `math`, `time`, `dateutil`, etc.). Si una lógica requiere librerías externas, va a n8n, no a Server Action.
- **No despliegues directos a producción**: todo cambio se valida primero en staging o en un entorno duplicado.

## Stack y dónde vive cada cosa

```
Odoo Online 19.0 Custom (mozaprint.odoo.com)
├── Datos: products, partners, leads, sale orders, inventory
├── UI: website /shop, CRM, Sales, Inventory, Knowledge (para KB de Moza)
├── Extensiones permitidas: Studio fields, Automation Rules, Server Actions
└── AI Agent nativo: livechat web + tools internos

n8n self-hosted en VPS Hetzner (n8n.mozaprintmx.com)
├── Orquestación entre Odoo, Meta WhatsApp, LLM provider
├── Workflows de captura, sync de proveedores, follow-ups
├── Webhooks receiver de Odoo y de Meta
└── Punto único de logging y observabilidad

LLM Provider (Claude o OpenAI, a definir)
├── Modelo conversacional del agente WhatsApp "Moza"
├── Haiku 4.5 / GPT-4o-mini para FAQ
├── Sonnet 4.6 / GPT-4o para cotizaciones complejas
└── Llamado desde n8n vía HTTP node (provider-agnostic)
```

## Modelo de datos clave

**Técnicas de personalización**: viven en modelo `x_tecnica_personalizacion` 
(NO selection). Productos las referencian por many2one (`x_tecnica_default_id`) 
y many2many (`x_tecnicas_compatibles_ids`). Costos por proveedor/qty viven en 
`x_costo_personalizacion` con many2one a la técnica.

Ver `specs/data-model.md` para detalle completo.

## Convenciones de código

### Python (Odoo Server Actions)
- Type hints obligatorios donde el sandbox lo permita
- Docstrings con ejemplos de uso
- Manejo de errores explícito; nunca silenciar excepciones
- Logging con `_logger.info()` para todo cambio de estado
- Idempotencia siempre que sea posible (revisar antes de crear)

### JavaScript (n8n Function nodes)
- Usar arrow functions
- Validar inputs al inicio del nodo
- Output siempre array de items con la forma estándar de n8n: `[{ json: {...} }]`
- Comentarios explicando el "por qué", no el "qué"

### JSON / API payloads
- Snake_case en payloads de Odoo (sigue la convención del modelo)
- camelCase en payloads de Meta WhatsApp (sigue la convención de Meta)
- Documentar cada campo nuevo en `specs/api-shapes.md`

## Cómo trabajamos

### Antes de implementar
1. Leer `docs/architecture.md` para entender el sistema completo
2. Revisar `decisions/` para decisiones tomadas previamente
3. Si el feature toca un modelo custom, leer `specs/data-model.md`
4. Si el feature toca una API externa, revisar `specs/integrations.md`

### Al implementar
1. **Una tarea a la vez**: no metas múltiples cambios en un mismo PR/commit
2. **Tests primero cuando sea posible**: especialmente para Server Actions con lógica de negocio
3. **Documenta side effects**: si tu cambio afecta otros modelos, hazlo explícito en el commit
4. **No inventes nombres de campos**: revisa `specs/data-model.md` antes de crear `x_` nuevos

### Cuando termines
1. Actualiza `docs/changelog.md` con qué cambió y por qué
2. Si introduces un nuevo modelo/campo custom, agrégalo a `specs/data-model.md` y `odoo-extensions/studio-fields.yaml`
3. Si introduces un nuevo workflow en n8n, exporta el JSON y guárdalo en `n8n-workflows/`

## Reglas de seguridad

- **Precios SIEMPRE vienen de Odoo**: el AI nunca calcula montos. Si necesitas un precio, consulta `sale.order` o `product.pricelist` vía tool.
- **Datos sensibles NUNCA en logs**: nombres, teléfonos, emails completos quedan ofuscados. SKU y montos OK.
- **API keys SIEMPRE en variables de entorno**: nunca hardcodeadas, nunca en commits.
- **Human-in-the-loop obligatorio** para: cotizaciones con costos no parametrizados, mensajes salientes a clientes nuevos, cambios masivos de catálogo (>10 productos).

## Lo que SÍ debes hacer proactivamente

- Sugerir refactors cuando veas duplicación
- Proponer tests cuando veas funciones sin cobertura
- Marcar TODOs claros con `# TODO(mozaprint):` cuando dejes algo pendiente
- Cuestionar requerimientos ambiguos antes de implementar

## Lo que NO debes hacer

- No instalar librerías sin documentar por qué en el commit
- No hacer migraciones de datos sin script de rollback
- No cambiar nombres de campos custom existentes (rompe integraciones)
- No subir credenciales ni datos de clientes a ningún repo
- No usar XML-RPC para integraciones nuevas (deprecación 2027 en Online); usar JSON-2 API

## Comandos comunes

```bash
# Auditar DNS (Cloudflare + Hostinger)
python3 scripts/dns_audit.py --output reports/dns_$(date +%Y%m%d).json

# Backup catálogo antes de sync masivo
python3 scripts/backup_catalog.py --output backups/$(date +%Y%m%d).json

# Test Server Action localmente
python3 scripts/test_server_action.py --action ai_handle_whatsapp_message --input test/messages/sample_new_customer.json

# Anonimizar conversaciones WhatsApp para análisis
python3 scripts/anonymize_whatsapp.py "exports/*.txt" --output-dir anonymized/
```

## Lectura recomendada antes de empezar

1. `docs/architecture.md` — Diagrama y responsabilidades de cada componente
2. `docs/decisiones-equipo-v1.md` — Decisiones tomadas, contexto operativo
3. `docs/glossary.md` — Términos del negocio
4. `specs/data-model.md` — Modelos custom, campos, relaciones
5. `decisions/` — Decisiones técnicas previas (cada decisión es un .md)

@docs/architecture.md
@docs/decisiones-equipo-v1.md
@docs/glossary.md
@specs/data-model.md
