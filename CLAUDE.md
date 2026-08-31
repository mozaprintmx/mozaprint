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

- **Odoo Online saas~19.3 Custom** (`mozaprint.odoo.com`): datos, CRM, ventas,
  catálogo, inventario, sitio web. Toda la lógica de negocio vive aquí.
- **n8n self-hosted** (VPS Hetzner): orquestador y **router único** del webhook
  de WhatsApp (Cloud API permite 1 webhook por número).
- **LLM** (Claude vs OpenAI — se decide en piloto, Fase 7): agente "Moza".
- **GitHub público** + Claude Code. Secretos en **Bitwarden**, NUNCA en el repo.

## Lo que NO debes asumir

- **No hay acceso a `addons/`**: es Odoo Online, no se instalan módulos custom
  **ni del Apps Store**. «Third-party applications can NOT be installed on Online
  (SaaS) databases» — solo módulos oficiales de Odoo (el plan Custom los trae
  todos). Antes de proponer un módulo del marketplace, descártalo: no es opción.
  Extensión SOLO vía Studio (campos `x_studio_`), Automation Rules, Server
  Actions (sandbox Python limitado) y AI Fields. Ver `decisions/009`.
- **El sandbox Python de Odoo Online no permite imports arbitrarios**: solo
  whitelist (`datetime`, `json`, `re`, `math`, `time`, `dateutil`, etc.). Si la
  lógica requiere librerías externas o HTTP saliente → va a **n8n**, no a Server
  Action.
- **No despliegues directos a producción**: validar primero en staging o en un
  entorno duplicado. Ambiente de pruebas: `ODOO_TEST_URL` en
  `analysis/supplier-sync/.env` (mismas credenciales, solo cambia la URL —
  agregado 2026-08-06 para probar el Server Action de cotización antes de
  tocar producción, ver `specs/motor-cotizacion.md`).

## Modelo de datos (detalle en `specs/data-model.md` — léelo antes de crear campos)

- Técnicas de personalización: modelo propio `x_tecnica_personalizacion`
  (NO selection). Producto → técnica por `x_tecnica_default_id` (m2o) y
  `x_tecnicas_compatibles_ids` (m2m). Costos en `x_costo_personalizacion`
  (m2o a la técnica).
- **Cuidado con el prefijo**: lo que fuerza `x_studio_` es la **UI de Studio**,
  NO que el modelo sea estándar (`crm.lead`) vs. custom propio. Creando el campo
  vía **Ajustes → Técnico → Estructura de BD** (en cualquier modelo, estándar o
  custom) el nombre técnico queda tal cual se escribe, sin prefijo forzado — así
  quedaron `x_tecnica_servicio_id`/`x_es_servicio_personalizacion` en
  `product.template` (confirmado 2026-08-06, ver changelog v27; corrige la
  suposición original). Los MODELOS custom salen como `x_<nombre>`. NO asumas
  nombres desde las specs — verifica el nombre real en Odoo antes de integrar
  (hay deuda histórica donde specs y realidad divergen).

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
- **Odoo COBRA por cada 100 líneas de código de Studio** («Mantenimiento de código
  personalizado»): aplica a Server Actions tipo *Execute Code* y a campos
  calculados. NO aplica a vistas, menús, campos simples, ACLs ni automatizaciones
  declarativas. Antes de proponer o desplegar cualquiera de los dos primeros,
  medir con `scripts/audit_lineas_facturables.py` y buscar alternativa nativa
  (listas de precios, productos, opcionales, webhook a n8n). Ver `decisions/007`.
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
- **Cuando termines — mantén la doc en sync, en el MISMO commit**: SIEMPRE
  `docs/changelog.md` (entrada de alto nivel). Según lo que cambió: modelo/campos
  → `specs/data-model.md` + `odoo-extensions/studio-fields.yaml`; fases o tareas
  completadas → `docs/roadmap.md`; scripts o `data/` nuevos → `README.md`; workflow
  n8n nuevo → exporta el JSON a `n8n-workflows/`. **NUNCA** documentes en el repo
  público detalle sensible del sync (endpoints, credenciales, lógica de proveedores,
  horarios): eso vive en `analysis/` (gitignored).
- **Scripts nuevos, generados por Claude Code (no por Cowork)**: cuando la pieza
  de trabajo requiere un script nuevo, Juan Carlos prefiere recibir el prompt
  (requisitos, spec de referencia, patrón a seguir) para pegarlo en Claude Code y
  que Claude Code lo genere, pruebe contra Odoo real y corrija ahí mismo — no que
  se entregue el código ya escrito desde otra herramienta sin acceso de red real
  a `mozaprintmx.odoo.com` (esa es la limitación de Cowork: puede diseñar/spec
  pero no probar).

## Proactivo

Sugiere refactors ante duplicación; propón tests donde falten; marca pendientes
con `# TODO(mozaprint):`; cuestiona requerimientos ambiguos antes de implementar.

## No hagas

- No instalar librerías sin documentar por qué en el commit.
- No migrar datos sin script de rollback.
- No cambiar nombres de campos custom existentes (rompe integraciones).
- **NUNCA renombrar los partners de proveedor** `INNOVATIONLINE`, `PROMOOPCION` ni
  `4PROMOTIONAL` (ids 82, 11, 15). Esos nombres en mayúsculas son **identificadores
  técnicos, no etiquetas**: el sync los busca con `name = '<exacto>'` y, si no los
  encuentra, **crea un duplicado en silencio** — partiendo `product.supplierinfo` entre
  dos partners y rompiendo `seed_costos.py`, que exige exactamente 1 coincidencia. Ya hay
  otros partners con nombre parecido (ids 32 y 8) que NO son estos. Si hace falta un
  nombre presentable para el cliente, va en el texto del producto, no en el partner.
- No subir credenciales ni datos de clientes al repo.

## Comandos comunes

```bash
# Auditar DNS (Cloudflare + Hostinger)
python3 scripts/dns_audit.py --output reports/dns_$(date +%Y%m%d).json

# Backup catálogo antes de sync masivo
python3 scripts/backup_catalog.py --output backups/$(date +%Y%m%d).json

# Precios de personalización: matriz ↔ productos ↔ reglas (solo lectura)
python3 scripts/audit_personalizacion.py --target prod

# Auditar catálogo / atributos de /shop (solo lectura, JSON-2)
python3 scripts/audit_catalog.py
python3 scripts/audit_atributos.py

# Técnica de personalización (dry-run por defecto; --apply escribe).
# Seed de 20 técnicas en data/tecnicas_seed.csv.
python3 scripts/seed_tecnicas.py --apply     # carga el seed (idempotente)
python3 scripts/derive_tecnicas.py --apply   # deriva técnica canónica raw→modelo

# Test Server Action localmente
python3 scripts/test_server_action.py --action ai_handle_whatsapp_message \
  --input test/messages/sample_new_customer.json

# Anonimizar conversaciones WhatsApp para análisis
python3 scripts/anonymize_whatsapp.py "exports/*.txt" --output-dir anonymized/

# Imágenes de categorías del eCommerce (dry-run; --apply escribe). El filmstrip de
# /shop las incrusta en base64 y Odoo NO redimensiona image_128 por API → pesa image_1920.
python3 scripts/optimize_category_images.py --apply
python3 scripts/rollback_category_images.py --from backups/category_images_AAAAMMDD --apply
```

## Dónde está el resto del contexto

- Decisiones del equipo (horarios, anticipo, pago): `decisions/004-decisiones-equipo-v1.md`
- Términos del negocio: `docs/glossary.md`
- Estado por fases: `docs/roadmap.md` y `docs/punto-de-control.md`
- APIs externas y proveedores: `specs/integrations.md`
- Agente "Moza" (identidad, prompts, tools): `specs/ai-agent-spec.md`
- Personalización en cotizaciones: **reemplazo NATIVO en producción desde 2026-08-25**
  (`specs/personalizacion-nativa.md`). 53 productos de servicio + 77 reglas de lista de
  precios, con `x_costo_personalizacion` como única fuente de verdad. **Los precios NO se
  editan en el producto**: se editan en la matriz y se recargan. Manuales:
  `docs/manual-vendedor-personalizacion.md` y `docs/manual-admin-precios-personalizacion.md`.
  Verificación: `python scripts/audit_personalizacion.py --target prod`. El motor anterior
  se retiró el 2026-08-17 por el cargo por línea de código (`decisions/007`);
  `specs/motor-cotizacion.md` es histórica.
- WhatsApp/IA/Marketing: **Odoo será dueño del webhook** (`decisions/008`, propuesta,
  pendiente de 2 experimentos). Estado real de Marketing: `docs/marketing-diagnostico.md`.
- Actualizaciones de Odoo: `docs/upgrades/README.md`. Las dos bases corren **saas~19.3**
  desde 2026-08-22. Cuando diverjan, lo que falla en test es aviso anticipado de
  producción — no lo repares antes de tiempo, salvo que el arreglo valga en ambas.
- **`arch_db` y demás campos traducidos**: al escribirlos por API, itera los idiomas
  (`en_US` primero, luego los activos). Escribir solo el de la sesión deja el sitio roto
  para el visitante con el backend viéndose bien. Ya mordió a dos scripts.

<!-- Único import always-on: glossary.md fija la terminología en toda sesión.
     Si pasa de ~150 líneas, vuélvelo referencia por ruta y quita este import. -->
@docs/glossary.md
