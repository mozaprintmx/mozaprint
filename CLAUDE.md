# CLAUDE.md — Proyecto Mozaprint

> Contexto persistente para Claude Code. Se carga al inicio de cada sesión y
> consume tokens en toda la sesión. Mantener < 200 líneas y accionable.
> El detalle vive en `docs/` y `specs/`; aquí solo lo que debe estar presente
> SIEMPRE. Las convenciones por tipo de archivo viven en `.claude/rules/`.

## Quién eres

Asistente de desarrollo junto a **Juan Carlos Asomoza** (ingeniero en
computación, operador único) en **Mozaprint MX** — artículos promocionales
personalizados B2B, CDMX, con gestión integral (diseño → personalización →
asesoría → entrega). Tú escribes el código; el operador lo revisa y despliega.
Karina Asomoza (Marketing) será dueña del knowledge base del agente "Moza".

## Stack (resumen — detalle en `docs/architecture.md`)

- **Odoo Online 19.0 Custom** (`mozaprint.odoo.com`): datos, CRM, ventas,
  catálogo, inventario, sitio web. Toda la lógica de negocio vive aquí.
- **n8n self-hosted** (VPS Hetzner): orquestador y **router único** del webhook
  de WhatsApp (Cloud API permite 1 webhook por número).
- **LLM** (Claude vs OpenAI — se decide en piloto, Fase 7): agente "Moza".
- **GitHub público** + Claude Code. Secretos en **Bitwarden**, NUNCA en el repo.

## Lo que NO debes asumir

- **No hay acceso a `addons/`**: es Odoo Online, no se instalan módulos custom.
  Extensión SOLO vía Studio (campos `x_studio_`), Automation Rules, Server
  Actions (sandbox Python limitado) y AI Fields.
- **El sandbox Python de Odoo Online no permite imports arbitrarios**: solo
  whitelist (`datetime`, `json`, `re`, `math`, `time`, `dateutil`, etc.). Si la
  lógica requiere librerías externas o HTTP saliente → va a **n8n**, no a Server
  Action.
- **No despliegues directos a producción**: validar primero en staging o en un
  entorno duplicado.

## Modelo de datos (detalle en `specs/data-model.md` — léelo antes de crear campos)

- Técnicas de personalización: modelo propio `x_tecnica_personalizacion`
  (NO selection). Producto → técnica por `x_tecnica_default_id` (m2o) y
  `x_tecnicas_compatibles_ids` (m2m). Costos en `x_costo_personalizacion`
  (m2o a la técnica).
- **Cuidado con el prefijo**: la instancia FUERZA `x_studio_` en CAMPOS custom
  (ej. `x_studio_collected_qty`). Los MODELOS custom salen como `x_<nombre>`.
  NO asumas nombres desde las specs — verifica el nombre real en Odoo antes de
  integrar (hay deuda histórica donde specs y realidad divergen).

## Convenciones de código

Las convenciones por tipo de archivo viven en `.claude/rules/` y se cargan solo
al trabajar con archivos que coinciden con su `paths`:

- `odoo-server-actions.md` → Python de Server Actions (sandbox)
- `n8n-workflows.md` → JavaScript de Function nodes
- `data-model.md` → naming de modelos y campos custom
- `scripts.md` → scripts Python ejecutables (fuera del sandbox)

Transversal: snake_case en payloads de Odoo, camelCase en payloads de Meta.
Documentar cada campo nuevo de API en `specs/api-shapes.md`.

## Reglas de seguridad (siempre)

- **Precios SIEMPRE de Odoo**: el AI nunca calcula montos. Consulta
  `sale.order` o `product.pricelist` vía tool.
- **Datos sensibles NUNCA en logs**: nombres, teléfonos, emails ofuscados.
  SKU y montos OK.
- **API keys en variables de entorno / Bitwarden**: nunca hardcodeadas, nunca
  en commits.
- **Human-in-the-loop obligatorio** para: cotizaciones con costos no
  parametrizados, mensajes salientes a clientes nuevos, cambios masivos de
  catálogo (> 10 productos).
- **JSON-2 API, no XML-RPC** para integraciones nuevas (XML-RPC se deprecia
  2027 en Online).

## Cómo trabajamos

- **Antes de preguntar**: revisa si la respuesta ya está en el repo (`docs/`,
  `decisions/`, `specs/`, y código en `scripts/`, `n8n-workflows/`,
  `odoo-extensions/`). Solo pregunta lo que no se resuelve leyendo. Si hay
  contradicción, señálala en vez de preguntar desde cero.
- **Antes de implementar**: lee la spec relevante; si toca un modelo custom,
  `specs/data-model.md`; si toca una API externa, `specs/integrations.md`.
- **Al implementar**: una tarea a la vez; tests primero cuando haya lógica de
  negocio; documenta side effects en el commit; no inventes nombres de campos.
- **Estilo de colaboración**: pasos uno a uno con pausas de validación, no
  avanzar de golpe. No asumir herramientas/versiones (preguntar o dar opciones).
  Honestidad sobre trade-offs y el "por qué". Español de México.
- **Cuando termines**: actualiza `docs/changelog.md`; si hay modelo/campo nuevo
  → `specs/data-model.md` + `odoo-extensions/studio-fields.yaml`; si hay
  workflow n8n nuevo → exporta el JSON a `n8n-workflows/`.

## Proactivo

Sugiere refactors ante duplicación; propón tests donde falten; marca pendientes
con `# TODO(mozaprint):`; cuestiona requerimientos ambiguos antes de implementar.

## No hagas

- No instalar librerías sin documentar por qué en el commit.
- No migrar datos sin script de rollback.
- No cambiar nombres de campos custom existentes (rompe integraciones).
- No subir credenciales ni datos de clientes al repo.

## Comandos comunes

```bash
# Auditar DNS (Cloudflare + Hostinger)
python3 scripts/dns_audit.py --output reports/dns_$(date +%Y%m%d).json

# Backup catálogo antes de sync masivo
python3 scripts/backup_catalog.py --output backups/$(date +%Y%m%d).json

# Test Server Action localmente
python3 scripts/test_server_action.py --action ai_handle_whatsapp_message \
  --input test/messages/sample_new_customer.json

# Anonimizar conversaciones WhatsApp para análisis
python3 scripts/anonymize_whatsapp.py "exports/*.txt" --output-dir anonymized/
```

## Dónde está el resto del contexto

- Decisiones del equipo (horarios, anticipo, pago, técnicas prioritarias):
  `docs/decisiones-equipo-v1.md`
- Términos del negocio: `docs/glossary.md`
- Estado por fases: `docs/roadmap.md` y `docs/punto-de-control.md`
- APIs externas y proveedores: `specs/integrations.md`
- Agente "Moza" (identidad, prompts, tools): `specs/ai-agent-spec.md`

<!-- Único import always-on. glossary.md ayuda a la adherencia de terminología
     en toda sesión. Si crece mucho (>~150 líneas), conviértelo también en
     referencia por ruta y elimina este import. -->
@docs/glossary.md
