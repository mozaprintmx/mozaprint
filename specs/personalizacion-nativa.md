# Personalización nativa — spec del reemplazo del motor

> Reemplazo del motor de cotización retirado el 2026-08-17 por el cargo de Odoo por
> línea de código ([ADR 007](../decisions/007-retiro-motor-cotizacion-costo-codigo.md)).
>
> **Principio**: los precios viven en Odoo como **datos** (productos + reglas de lista de
> precios). La inteligencia —calcular markup, cargar, actualizar, verificar— vive en
> **scripts del repo**, que corren fuera de Odoo y no se facturan.
>
> **Estado**: paso 0 (sondeo) y paso 1 (hoja de mapeo) hechos el 2026-08-21 contra
> test `saas~19.3`. **Nada cargado en Odoo todavía.**

## Paso 0 — sondeo de capacidades (hecho, solo lectura)

| Capacidad | Resultado |
|---|---|
| `product.pricelist.item`: `applied_on` (`1_product`), `min_quantity`, `fixed_price`, `compute_price='fixed'`, `date_start`/`date_end` | ✅ todo existe |
| `base='pricelist'` + `base_pricelist_id` (para que Volant/GMC hereden de Público) | ✅ existe |
| `sale.order.template.line.display_type` | ✅ `line_section`, `line_subsection`, `line_note`. **0 plantillas creadas hoy** |
| `product.supplierinfo` con `min_qty`, `price`, `date_start`/`date_end` | ✅ existe — habilita la fase 2 (costos por tramo del lado de compra) |
| **`sale_line_warn`** (el selector no-message/warning/block) | ❌ **YA NO EXISTE en 19** |
| `sale_line_warn_msg` | ✅ existe y sigue expuesto en las vistas de `product.template` y `sale.order` |

> **El aviso al elegir el producto se simplificó**: en 19 desapareció el selector y quedó
> solo el texto. Si el mensaje está puesto, se muestra. Para nosotros es mejor —una cosa
> menos que configurar— pero hay que **confirmarlo a ojo** al cargar el primero, porque
> ninguna documentación lo dice.

### Hallazgos del sondeo que condicionan el diseño

1. **Hay dos categorías de servicio duplicadas**: `[435] "Servicios de Personalización"`
   (los 20 servicios viven aquí) y `[5] "Servicios de personalización"` (2 productos
   sueltos, solo cambia una mayúscula). **Hay que consolidarlas antes** de crear las
   reglas de delegación, que se apoyan en la categoría: un producto en la categoría
   equivocada no heredaría el precio.
2. **Las 23 reglas de lista de precios existentes son todas de imprenta** —Volantes,
   Tarjetas de presentación, Banner Roll-Up— a nivel de variante y con `min_qty=0`.
   **No chocan** con nada de personalización.
3. **GMC tiene una sola regla global de 0% de descuento**, que es un no-op. Nuestra regla
   por categoría es más específica y gana, así que tampoco estorba.
4. **Los 20 servicios que ya existen** (`SERV-*`, precio 0, uno por técnica) solo se usan
   en **1 línea de cotización** en toda la base. Se pueden reetiquetar sin romper nada.

## El mapa: 51 productos + 74 reglas + 2 setups

Generado por [`scripts/mapa_servicios_personalizacion.py`](../scripts/mapa_servicios_personalizacion.py)
leyendo la matriz viva. Salidas en `analysis/costos-personalizacion/` (gitignored — son
costos de proveedor):

| Archivo | Qué trae |
|---|---|
| `mapa_1_productos.csv` | 51 productos: SKU, nombre, precio, costo, markup, mínimo, aviso |
| `mapa_2_reglas_precio.csv` | 74 reglas `min_quantity` → `fixed_price` |
| `mapa_3_setups.csv` | 2 productos de setup, con su condición |

De las **126 tarifas activas**: 51 combinaciones de (técnica × proveedor × alcance ×
área × unidad). Se omiten las reglas cuyo precio repite el del tramo anterior.

### El SKU

`PERS-<TÉCNICA>-<PROVEEDOR>-<ALCANCE>[-H|D<área>][-LOTE]`

El alcance toma **dos palabras significativas de 5 letras más los dígitos**. Truncar a
las primeras N letras **no funciona**: «Llaveros y bolígrafos» y «Llaveros de bambú»
comparten prefijo y lo que las separa viene después — colisionaban. `-H603` es «hasta
603 cm²» y `-D603` «desde 603»: la matriz tiene tarifas distintas con el mismo número.

El generador **falla ruidosamente si dos combinaciones caen en el mismo SKU**. Es la
llave del diseño entero: un choque haría que una tarifa pisara a la otra.

### Los tres casos que el vendedor puede equivocar

Van en `sale_line_warn_msg`, que salta al elegir el producto en la línea:

| Caso | Cuántos | Qué dice el aviso |
|---|---|---|
| **Lote con escala por tinta** (todos INN) | 11 | «La CANTIDAD de esta línea es el NÚMERO DE TINTAS, no de piezas» |
| **Lote sin tinta** | 1 | «Precio POR LOTE: pon cantidad 1» |
| **Cantidad mínima > 1** | 16 | «Mínimo N pzas; por debajo esta tarifa NO aplica» |

El setup de bordado es **condicional**: no se cobra a partir de 201 pzas. Eso no cabe en
el producto, así que va como condición en la hoja de setups.

## Decisiones tomadas

1. **La matriz `x_costo_personalizacion` sigue siendo la fuente de verdad.** Las listas
   de precios son derivadas. La matriz guarda costo, markup, unidad, escala por tinta y
   notas — cosas que la lista no puede sostener. El script traduce en una dirección.
2. **51 productos, no 9 por técnica.** Los datos lo obligan: láser sobre Tumbler $10.38 y
   sobre Bolígrafos $4.69 no guardan relación.
3. **Las 74 reglas van solo en «Default»**; Volant, GMC y Dólar reciben **una regla cada
   una** con `base='pricelist'` apuntando a Default sobre la categoría de personalización.
4. **No se ligan los servicios a los 5,212 productos** vía `optional_product_ids`.

## Lo que sigue (nada de esto está hecho)

- [ ] **JC revisa `mapa_1_productos.csv`** — es el punto de control antes de cargar nada
- [ ] Consolidar las dos categorías de servicio duplicadas
- [ ] Escribir el cargador (idempotente, dry-run, `--apply`, rollback) y correrlo en test
- [ ] Las 74 reglas + las 3 de delegación, con **smoke test**: cotización desechable que
      compara `price_unit` contra la matriz en varias cantidades
- [ ] Plantilla de cotización con las secciones «Producto» y «Personalización»
- [ ] Confirmar a ojo que `sale_line_warn_msg` sigue saltando en 19
- [ ] Verificador permanente matriz ↔ productos ↔ reglas, al checklist trimestral
- [ ] Manual nuevo para el equipo (el anterior se archivó de Knowledge el 2026-08-21)

### Fase 2, opcional

Meter los costos como `product.supplierinfo` con sus propios `min_qty` — la misma
estructura de tramos, pero del lado de compra. Con eso las personalizaciones
subcontratadas podrían mandarse como orden de compra real al proveedor. También es dato
puro, no cuesta.
