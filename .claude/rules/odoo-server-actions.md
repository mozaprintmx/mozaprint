---
paths:
  - "odoo-extensions/server-actions/**"
  - "odoo-extensions/**/*.py"
---

# Server Actions de Odoo (Python sandbox)

Entorno: **sandbox Python de Odoo Online**, restringido. No es Python completo.

## Restricciones del sandbox

- Solo imports whitelist: `datetime`, `json`, `re`, `math`, `time`, `dateutil`,
  y similares. **Nada** de `requests`, `pandas`, ni librerías externas.
- Sin HTTP saliente desde el action. Si la lógica requiere una librería externa
  o una llamada de red → **no va aquí, va a un workflow de n8n**.

## Convenciones

- Type hints donde el sandbox lo permita.
- Docstrings con ejemplo de uso.
- Manejo de errores explícito; **nunca** silenciar excepciones.
- `_logger.info()` en todo cambio de estado.
- Idempotencia siempre que sea posible (revisar antes de crear).

## Antes de tocar campos custom

Lee `specs/data-model.md`. No inventes nombres `x_`. Recuerda: campos custom
llevan prefijo `x_studio_` forzado por la instancia; verifica el nombre real en
Odoo antes de referenciarlo.

## Seguridad

- Precios SIEMPRE desde Odoo (`sale.order` / `product.pricelist`), nunca
  calculados en el action.
- Datos sensibles (nombres, teléfonos, emails) ofuscados en logs. SKU y montos OK.
- Mantén una copia versionada del action en este directorio aunque viva dentro
  de Odoo (tracking de cambios).
