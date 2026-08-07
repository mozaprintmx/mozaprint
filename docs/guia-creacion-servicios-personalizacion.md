# Guía: servicios de personalización (1 `product.template` por técnica)

> Setup previo en Odoo antes de correr `scripts/seed_servicios_personalizacion.py`.
> Decisión de diseño y campos completos en `specs/data-model.md` (sección "Servicios
> de personalización").
>
> **✓ COMPLETADO 2026-08-06** (categoría por API, campos manuales por JC). **Corrección
> importante**: se creyó que `product.template`, por ser modelo estándar, forzaría el prefijo
> `x_studio_`. **Falso** — lo que fuerza `x_studio_` es **Studio UI**, no que el modelo sea
> estándar. Creando vía **Ajustes → Técnico → Estructura de BD** el nombre queda como se escribe:
> los campos reales son `x_es_servicio_personalizacion` y `x_tecnica_servicio_id` (sin `x_studio_`),
> igual que `x_costo_personalizacion`.

## 1. Categoría de producto "Servicios de Personalización"

Ventas (o Inventario) → Configuración → Categorías de producto → Nueva.

| Campo | Valor |
|---|---|
| Nombre | `Servicios de Personalización` |
| Cuenta de ingresos | La que quieras usar para reportar ingresos de personalización separado de venta de producto físico (pregúntale a tu contador si no estás seguro de cuál) |
| Impuesto de cliente por defecto | IVA 16% |

Así los 20 productos heredan cuenta e impuesto por default, sin que el script tenga
que hardcodear IDs de cuentas contables (varían por instalación).

## 2. Dos campos nuevos en `product.template`

Ajustes → Técnico → Estructura de base de datos → Campos → Nuevo. **Crear por Técnico (NO por
Studio)** para conservar el nombre plano `x_` — Studio forzaría `x_studio_`.

| Nombre técnico REAL (creado) | Tipo | Relación | Label |
|---|---|---|---|
| `x_es_servicio_personalizacion` | Boolean | — | Es servicio de personalización |
| `x_tecnica_servicio_id` | Many2one | `x_tecnica_personalizacion` | Técnica que representa este servicio |

Para el many2one, igual que con `x_costo_personalizacion`: si el campo es
obligatorio en algún flujo futuro, usa `ondelete='restrict'` (aquí lo dejamos
opcional por ahora, no hace falta tocar esa política).

## 3. Verificar nombres reales ✓

Verificado por `fields_get(product.template)` el 2026-08-06: los campos quedaron como
`x_es_servicio_personalizacion` y `x_tecnica_servicio_id` (**sin** `x_studio_`).
`specs/data-model.md` y `odoo-extensions/studio-fields.yaml` ya actualizados a `status: created`.

## 4. Correr el script

```bash
python scripts/seed_servicios_personalizacion.py            # dry-run
python scripts/seed_servicios_personalizacion.py --apply    # ejecuta
```

Crea 1 `product.template` por cada técnica **activa** en `x_tecnica_personalizacion`
(lee el catálogo en vivo, no un CSV — si agregas técnicas después, vuelve a correr
el script y solo crea las nuevas). Idempotente por `x_tecnica_servicio_id`.

Corre el dry-run primero y revisa el resumen antes de `--apply`.
