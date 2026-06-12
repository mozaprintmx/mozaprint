---
paths:
  - "n8n-workflows/**"
---

# Workflows de n8n (JavaScript de Function nodes)

## Convenciones JS

- Arrow functions.
- Validar inputs al inicio del nodo.
- Output SIEMPRE array con la forma estándar de n8n: `[{ json: {...} }]`.
- Comentarios que expliquen el "por qué", no el "qué".

## Payloads

- Odoo: **snake_case** (sigue la convención del modelo).
- Meta WhatsApp: **camelCase** (sigue la convención de Meta).
- Documenta cada campo nuevo en `specs/api-shapes.md`.

## Odoo desde n8n

- **JSON-2 API, no XML-RPC** (deprecación 2027). Patrón de auth (`Bearer` +
  header `DATABASE`), endpoints `POST /json/2/{model}/{method}` y retry con
  backoff: ver `specs/integrations.md`.
- Rate limit empírico ~30 req/seg sostenido; usa `batch` en syncs masivos.
- La instancia expone su modelo de datos en `GET /doc`; consúltalo cuando dudes
  de un nombre de campo.

## Proveedores

Cada proveedor mapea su respuesta al shape estándar `ProductoProveedor`
(ver `specs/integrations.md`). Sub-workflows: `fetch-catalog`, `fetch-pricing`,
`fetch-inventory`, `create-po`.

## Versionado

Exporta el JSON del workflow y guárdalo aquí en cada cambio relevante. Si se
rompe algo, se restaura desde el repo.
