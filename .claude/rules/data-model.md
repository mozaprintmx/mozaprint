---
paths:
  - "specs/data-model.md"
  - "odoo-extensions/studio-fields.yaml"
---

# Naming de modelos y campos custom

Antes de crear o modificar cualquier `x_`, lee `specs/data-model.md` completo:
es el contrato.

## Reglas de naming

- **CAMPOS custom — el prefijo depende de CÓMO se crean, no del modelo**:
  - Vía **Studio UI**: Odoo FUERZA `x_studio_` (no editable). Ej.: `x_studio_collected_qty`,
    `x_studio_origen_form` (creados en Studio sobre `crm.lead`).
  - Vía **Ajustes → Técnico → Estructura de BD** (`ir.model.fields`): se conserva el nombre
    `x_` que escribes, SIN `x_studio_` — incluso en modelos estándar como `product.template`.
    Ej.: `x_es_servicio_personalizacion`, `x_tecnica_servicio_id` (creados así 2026-08-06),
    y los 17 campos de `x_costo_personalizacion`.
  - ⚠ NO asumas que "modelo estándar ⇒ x_studio_": lo que fuerza el prefijo es **Studio**, no
    que el modelo sea estándar.
- **MODELOS custom**: salen como `x_<nombre>`. Ej.: `x_tecnica_personalizacion`,
  `x_costo_personalizacion`.
- NO asumas el nombre desde la spec, el README o el changelog: **verifica el
  nombre real en Odoo** (`fields_get` / `/doc` / Studio) antes de integrar. Hay deuda histórica
  donde la documentación y la realidad divergen en el prefijo.

## Relaciones clave (técnicas de personalización)

- `x_tecnica_personalizacion`: modelo propio (NO selection). **Creado y poblado**
  (20 técnicas, seed `data/tecnicas_seed.csv`).
- Producto → técnica: `x_tecnica_default_id` (many2one),
  `x_tecnicas_compatibles_ids` (many2many). **Ya existen y están poblados** en
  producción (derivados por `scripts/derive_tecnicas.py`); NO son planificados.
- `x_costo_personalizacion`: costos por proveedor/cantidad, many2one a la técnica
  (○ planificado, aún no creado).

## Al cambiar el modelo

Las specs son contratos. Si cambias un campo aquí, propágalo a:

1. El modelo Studio en Odoo.
2. Cualquier workflow de n8n que lo use.
3. Las tools del agente "Moza" que lo consuman.

Y actualiza `specs/data-model.md` + `odoo-extensions/studio-fields.yaml`.
