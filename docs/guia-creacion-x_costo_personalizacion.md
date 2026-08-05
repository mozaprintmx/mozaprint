# Guía: crear `x_costo_personalizacion` vía Ajustes → Técnico

> Checklist paso a paso para crear el modelo y sus 16 campos directamente en
> **Ajustes → Técnico → Estructura de base de datos** (no Studio visual), como
> se decidió el 2026-08-05. Diseño completo de campos en `specs/data-model.md`.
> Después de crear, **verificar el nombre técnico real de cada campo** y
> actualizar `odoo-extensions/studio-fields.yaml` (`status: planned` → `created`
> + `created_date`), igual que se hizo con `x_tecnica_personalizacion`.

## 0. Activar modo desarrollador (si no está activo)

Ajustes → General Settings → baja hasta "Herramientas de desarrollador" →
**Activar el modo desarrollador**. (O añade `?debug=1` a la URL.)

Verifica que aparezca el menú **Técnico** en la barra superior de Ajustes.

## 1. Crear el modelo

Ajustes → Técnico → Estructura de base de datos → **Modelos** → Nuevo

| Campo del formulario | Valor |
|---|---|
| Descripción del modelo | `Costo de Personalización` |
| Nombre del modelo (técnico) | `x_costo_personalizacion` |

Guardar. Odoo crea automáticamente un campo `x_name` (Display Name) — verifica
si ya existe o si lo tienes que crear tú (varía según versión); si ya existe,
solo cámbiale el label a "Descripción" en el paso 2.

> ⚠️ No confundas esto con Studio: si el asistente de Studio se abre solo,
> ciérralo y sigue por Técnico → Modelos, para controlar el nombre exacto de
> cada campo sin que Odoo lo fuerce a `x_studio_*`.

## 2. Crear los 16 campos

Desde el modelo recién creado, entra a su pestaña/botón inteligente **Campos**
(o Ajustes → Técnico → Estructura de base de datos → Campos → Nuevo, y
selecciona el Modelo `x_costo_personalizacion` en cada uno).

Crea en este orden (más fácil: los many2one al catálogo de técnicas y
proveedores antes que el resto, para poder probarlos):

| # | Nombre técnico | Tipo | Relación / Selección | Requerido | Default | Label |
|---|---|---|---|:---:|---|---|
| 1 | `x_name` | Char | — | ✓ | — | Descripción |
| 2 | `x_tecnica_id` | Many2one | `x_tecnica_personalizacion` | ✓ | — | Técnica |
| 3 | `x_proveedor_id` | Many2one | `res.partner` | ✓ | — | Proveedor |
| 4 | `x_alcance_producto` | Char | — |  | — | Alcance (categoría/SKU) |
| 5 | `x_qty_from` | Integer | — | ✓ | — | Cantidad mínima |
| 6 | `x_qty_to` | Integer | — |  | — | Cantidad máxima |
| 7 | `x_area_from_cm2` | Float | — |  | — | Área mínima (cm²) |
| 8 | `x_area_to_cm2` | Float | — |  | — | Área máxima (cm²) |
| 9 | `x_tintas` | Integer | — |  | `1` | Tintas |
| 10 | `x_escala_por_tinta` | Boolean | — |  | `False` | Escala linealmente por tinta |
| 11 | `x_posiciones` | Integer | — |  | `1` | Posiciones |
| 12 | `x_unidad_cobro` | Selection | ver abajo | ✓ | `pieza` | Unidad de cobro |
| 13 | `x_costo_unit` | Float | — | ✓ | — | Costo (MXN) |
| 14 | `x_costo_setup` | Float | — |  | `0` | Costo de setup |
| 15 | `x_fecha_vigencia` | Date | — |  | — | Vigente hasta |
| 16 | `x_notas` | Text | — |  | — | Notas |
| 17 | `x_activa` | Boolean | — |  | `True` | Activa |

**Opciones de `x_unidad_cobro` (campo 12, tipo Selection)**:

```
pieza  → Por pieza
lote   → Por lote completo
```

## 3. Verificar nombres reales

Después de guardar, confirma que ningún campo quedó con prefijo `x_studio_`
(no debería pasar por crearlos vía Técnico, pero el propio repo tiene la regla
de "no asumir" — revisa con `/doc` o el listado de Campos). Si algo salió
distinto, avísame para actualizar `specs/data-model.md` y
`odoo-extensions/studio-fields.yaml` con el nombre real, igual que se
reconcilió `x_tecnica_personalizacion` en su momento.

## 4. Permisos

`x_tecnica_personalizacion` usa el grupo "Ventas/Usuario: todos los
documentos". Replica el mismo permiso en `x_costo_personalizacion` (Ajustes →
Técnico → Estructura de base de datos → Modelos → `x_costo_personalizacion` →
pestaña Permisos de acceso) para que el equipo de ventas pueda consultarlo al
cotizar.

## 5. Después de crear

Avísame en el chat cuando esté listo. El siguiente paso es el CSV de carga +
script `seed_costos.py` (mismo patrón dry-run/--apply que `seed_tecnicas.py`)
con los datos ya transcritos de INN y PO.
