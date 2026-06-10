---
paths:
  - "specs/data-model.md"
  - "odoo-extensions/studio-fields.yaml"
---

# Naming de modelos y campos custom

Antes de crear o modificar cualquier `x_`, lee `specs/data-model.md` completo:
es el contrato.

## Reglas de naming

- **CAMPOS custom**: la instancia FUERZA el prefijo `x_studio_` (no editable).
  Ej.: `x_studio_collected_qty`, `x_studio_origen_form`.
- **MODELOS custom**: salen como `x_<nombre>`. Ej.: `x_tecnica_personalizacion`,
  `x_costo_personalizacion`.
- NO asumas el nombre desde la spec, el README o el changelog: **verifica el
  nombre real en Odoo** (`/doc` o Studio) antes de integrar. Hay deuda histórica
  donde la documentación y la realidad divergen en el prefijo.

## Relaciones clave (técnicas de personalización)

- `x_tecnica_personalizacion`: modelo propio (NO selection).
- Producto → técnica: `x_tecnica_default_id` (many2one),
  `x_tecnicas_compatibles_ids` (many2many).
- `x_costo_personalizacion`: costos por proveedor/cantidad, many2one a la técnica.

## Al cambiar el modelo

Las specs son contratos. Si cambias un campo aquí, propágalo a:

1. El modelo Studio en Odoo.
2. Cualquier workflow de n8n que lo use.
3. Las tools del agente "Moza" que lo consuman.

Y actualiza `specs/data-model.md` + `odoo-extensions/studio-fields.yaml`.
