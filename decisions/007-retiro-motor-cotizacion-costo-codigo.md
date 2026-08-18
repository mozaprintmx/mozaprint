# ADR 007 — Retiro del motor de cotización: Odoo cobra por línea de código

**Fecha**: 2026-08-17 · **Estado**: aceptada, **ejecutada en producción** ·
**Supersede parcialmente**: `specs/motor-cotizacion.md`

## Contexto

Odoo Online factura un concepto llamado **«Mantenimiento de código personalizado»**,
que se cobra **cada 100 líneas de código** e incluye solución de errores, soporte y
actualizaciones. Según su propia definición, aplica a **módulos personalizados o
código de la app Studio: acciones automatizadas y campos calculados**.

JC detectó **3 cargos** de ese concepto en la factura. La medición confirmó el
origen exacto:

| Pieza | Líneas |
|---|---|
| Agregar personalización (motor cotización) | 127 |
| Aprobar personalización y agregar a cotización | 85 |
| Confirmar solicitud de aprobación | 35 |
| Abrir wizard personalización (pedido) | 12 |
| Rechazar personalización | 10 |
| 7 campos calculados | 20 |
| **Total** | **289 → 3 bloques de 100** |

**El 100% del código facturable era el motor de cotización.** Las 4 automatizaciones
del CRM no aportan una sola línea: son de tipo declarativo (crear actividad, enviar
correo, escribir etiqueta), no «Execute Code». Las vistas del PDF son XML. Los campos
simples y los `related` tampoco cuentan.

## Qué se evaluó

| Opción | Resultado | Veredicto |
|---|---|---|
| **A.** Rollback total del motor | 289 → 0 líneas | Elegida, con matices (ver abajo) |
| **B.** Quitar solo el flujo de aprobación (130 líneas) | 159 → 2 bloques | Ahorra 1 de 3; deja el motor a medias |
| **C.** Refactor agresivo bajo 100 líneas | Dudoso | Ya se hizo una pasada 415 → 269 (−35%); otro −28% sin perder función no es realista |
| **D.** Mover la lógica a n8n vía webhook | 0 líneas conservando función | Viable (Odoo 19 tiene «Send Webhook Notification», sin Python), pero es rediseño y la respuesta pasa a ser asíncrona |

Además se descubrió que **el mecanismo nativo de precios por cantidad estaba
instalado y sin estrenar**: 4 listas de precios existentes con **0 reglas
`min_quantity`**, y 20 productos de servicio ya creados con precio 0.

## Decisión

Retirar del motor **todo lo que genera código facturable**, dejando producción en
**0 líneas**, y reconstruir la funcionalidad con **mecanismos nativos de Odoo**
(productos de servicio + reglas de lista de precios), que son datos y no se cobran.

El rollback fue **quirúrgico, no el estándar**: el script original borraba 76 objetos
e incluía vistas y menús de la matriz de costos y de las técnicas. Esas **no son
facturables** —son datos— y sin ellas la matriz se queda sin pantalla de consulta.
Se conservaron.

## Lo que se borró (64 objetos)

- **5 Server Actions** (269 líneas) y **7 campos calculados** (20 líneas)
- Modelos `x_approval_request` y `x_wizard_personalizacion` con sus 47 campos
- 5 vistas (wizard, aprobaciones y el botón del encabezado de ventas)
- 1 menú y 1 acción de ventana (Aprobaciones), 2 ACLs, 1 default

## Lo que se conservó, a propósito

| Objeto | Por qué |
|---|---|
| **128 tarifas** en `x_costo_personalizacion` | Es la fuente de datos del nuevo diseño |
| `x_markup` y `x_personalizacion_externa` | Campos simples, **no facturables** |
| Las 4 vistas (list/form de costos y técnicas) y sus 2 menús | Datos, no código: sin ellas la matriz no se puede consultar |
| **20 técnicas** y los 5,212 productos con técnica | Son de Fase 2, nada que ver con el motor |
| Contacto «Personalización Externa» y el default de markup | No facturables y referenciados |

Antes de borrar se limpiaron las vistas de la matriz para que no quedaran apuntando
a las dos columnas calculadas que desaparecían.

También se quitó a propósito el `data_backup` del manifiesto: revertir los nombres de
20 tarifas al estado pre-motor no tenía sentido si la matriz sigue viva como tabla de
trabajo.

## Consecuencias

**Se pierde**: la búsqueda automática de tarifa según el producto, la línea de setup
automática, el flujo de aprobación cuando no hay tarifa (había **0 solicitudes**), y
el «aprendizaje» de tarifas nuevas.

**Se gana**: 3 cargos mensuales menos, y una superficie de mantenimiento mucho menor
ante upgrades de Odoo.

**Queda pendiente** el diseño nativo de reemplazo (ver la sección siguiente). Hasta
que se construya, **las personalizaciones se cotizan a mano** consultando la matriz
en Ventas → Configuración → Costos de personalización.

**Reversible**: `scripts/deploy_motor_cotizacion.py` reconstruye los 76 objetos desde
el repo con un comando. El manifiesto quirúrgico quedó en
`backups/manifiesto_motor_prod_QUIRURGICO.json`.

## El diseño de reemplazo (evaluado, no construido)

La matriz de 128 tarifas se descompone en **52 combinaciones** de
(técnica × proveedor × alcance × área): 33 con precio plano y **19 con tramos de
cantidad** (2, 3, 5 o hasta 10 tramos). Tintas siempre vale 1 —esa dimensión no se
usa—, solo 5 filas llevan setup y 12 se cobran por lote.

Eso es exactamente lo que hace `product.pricelist.item` con `min_quantity` y
`fixed_price`:

```
Producto:  [SERI-PO-BOLIG] Serigrafía · Bolígrafos · PromoOpción
           standard_price = costo     list_price = costo × markup
Reglas:    min_qty 1 → $8.00 · min_qty 100 → $6.80 · min_qty 500 → $5.20
```

Ventajas nativas que el motor no daba: `date_start`/`date_end` por regla da la
**vigencia** de la tarifa, y con el costo en `standard_price` Odoo calcula el
**margen** solo.

**Descartado**: variantes de producto con atributos. El precio de una variante es
`list_price + suma de price_extra`, es decir **aditivo**, y la matriz no lo es
(Láser sobre Termos 6x8 = $8, sobre Termos 8x12 = $12, sobre Curpiel = $6, sin
relación entre sí). Además darían 9 × 42 × 2 = 756 variantes.

**Principio que queda**: los precios viven en Odoo como datos; la inteligencia
(cálculo de markup, carga, actualización) vive en **scripts del repo**, que corren
fuera de Odoo y **no se facturan**.

## Regla permanente

**Antes de agregar cualquier Server Action con código o campo calculado en Odoo,
medir el costo** con `scripts/audit_lineas_facturables.py`. Cada 100 líneas es un
cargo recurrente. Alternativas sin costo, en orden de preferencia:

1. Configuración nativa (listas de precios, productos, opcionales, plantillas)
2. Automatizaciones **declarativas** (crear actividad, enviar correo, escribir campo)
3. Acción de tipo **webhook** hacia n8n, con la lógica fuera de Odoo
4. Scripts del repo vía API
