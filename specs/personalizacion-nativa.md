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
| `mapa_1_productos.csv` | 51 productos: llave, SKU, nombre, descripción de venta, precio, costo, markup, mínimo, aviso |
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

**Los SKU revisados a mano mandan.** JC corrigió los 51 el 2026-08-22; desde entonces el
generador relee la hoja anterior y **conserva el SKU de cada combinación**, generando solo
los que falten. El emparejamiento va por la columna `llave`
(`técnica|proveedor|alcance|área_desde|área_hasta|unidad`), y avisa si algún SKU de la
hoja ya no empata con ninguna tarifa. Los **nombres y descripciones sí se regeneran**:
salen de las reglas de diseño, no de edición manual.

### El error caro del diseño, y cómo se ataca

**11 de los 51 productos se cobran por lote Y por tinta** (serigrafía y tampografía de
Innovation Line). En esos, la **cantidad de la línea es el número de tintas**, no de
piezas — porque una línea de venta solo sabe hacer cantidad × precio, y la tarifa es un
monto fijo por lote multiplicado por cada tinta.

De los dos errores posibles, el peligroso no es el obvio:

| Lo que teclea el vendedor | Resultado en `PERS-SERI-INN-BOLILLAVE-LOTE` (500 pzas, 2 tintas) |
|---|---|
| **2** — correcto | $2,422.50 · costo $1,900 · margen $522.50 |
| **500** — cree que son piezas | $605,625. Absurdo, alguien lo ve antes de enviarlo |
| **1** — olvidó la segunda tinta | $1,211.25 · **costo $1,900 → pierde $688.75** |

El tercero es el caro: da un número creíble, nadie lo cuestiona, y el hueco aparece
cuando llega la factura del proveedor. En Aplaudidores, cotizar 2 tintas cuando eran 3
son **$2,700 de pérdida en una línea**. Nada en el sistema lo detecta.

> **Hueco reconocido**: si la cantidad son tintas, el número de PIEZAS nunca entra al
> sistema, y la tarifa solo vale hasta 1,000. Hoy nada impide cotizar 3,000 piezas al
> precio de un lote. Va en el nombre y en la descripción; no hay forma nativa de
> validarlo sin código.

**Decisión (JC, 2026-08-22): opción B + D.**

| | Qué se hace |
|---|---|
| **B — el nombre** | `Serigrafía POR TINTA · … · Innovation Line (lote ≤1,000 pzas)`. Se ve en la línea, en pantalla y en el PDF. **No se puede descartar como un aviso** |
| **D — `description_sale`** | Baja sola a la línea y al PDF: «Precio por lote de hasta 1,000 piezas y por tinta. Incluye 1 posición de impresión.» En tono comercial: la lee el cliente y de paso le explica el cargo |
| A — `sale_line_warn_msg` | Se genera igual, como refuerzo interno y en tono directo |

Se evaluaron y descartaron: **unidad de medida «Tinta»** —elegante y bien soportada en
19.3, pero el grupo *Manage Multiple Units of Measure* está apagado y encenderlo saca la
columna de unidad en TODAS las líneas de venta, un cambio global para el 20% de los
casos— y **un producto por número de tintas** (11 → 33), que hace el error imposible pero
alarga el catálogo. Si con B+D se sigue colando el error, esa es la siguiente parada.

También se descartó **convertirlo a precio por pieza**: $950 entre 100 piezas son $9.50
c/u y entre 1,000 son $0.95. El precio unitario cambia con cada cantidad y no hay tramos
que lo expresen sin una regla por cantidad posible.

### Los otros dos casos que el vendedor puede equivocar

| Caso | Cuántos | Cómo se marca |
|---|---|---|
| **Lote sin tinta** | 1 | `POR LOTE` en el nombre + rango de piezas |
| **Cantidad mínima > 1** | 16 | «Pedido mínimo N piezas» en la descripción + aviso |

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

## Paso 3 — categorías consolidadas (hecho en TEST el 2026-08-22)

`scripts/consolidar_categorias_servicio.py` — dry-run por defecto, respaldo y `--rollback`.

**Lo que había no era lo que parecía.** La categoría `[5]` no tenía «2 productos
sueltos» sino **3 de la era manual, con historial de ventas**:

| Producto | Precio | Uso |
|---|---|---|
| `Impresión con Serigrafía` (id 9) | $1.00 | **4 cotizaciones**, $23,760 |
| `FULL COLOR` (id 4996) | $990 | 1 cotización, $990 |
| `Impresión Serigrafía 1 tinta` (id 10) | $1,485 | archivado, sin uso |

> **Hallazgo que valida el diseño**: las 4 cotizaciones de `Impresión con Serigrafía`
> van con **cantidad 2 y precio $2,970**. El producto vale $1.00 —es un cascarón donde el
> vendedor teclea el precio— y **usan la cantidad para las tintas**. La convención
> «cantidad = tintas» que introducimos con B+D *ya es su forma de trabajar*.

### Qué se hizo

| Paso | Resultado |
|---|---|
| **3.1** Mover los 3 legado a `[435]` | ✓ incluido el archivado — sin uno solo dentro, la categoría no se puede borrar |
| **3.2** Borrar `[5]` | ✓ **borrada**. `product.category` **no tiene campo `active`**: no se archiva, se borra o se queda |
| **3.3** Renombrar la superviviente | · sin cambio, `[435]` ya se llamaba `Servicios de Personalización` |
| **3.4** Marcar los 20 genéricos | ✓ `Servicio de Bordado` ⇒ **`Bordado (precio a cotizar)`** |

`[435]` quedó con **23 productos**: 20 comodines + los 3 legado. El historial de ventas
sobrevivió intacto ($23,760 y $990 siguen en sus líneas — el precio vive en la línea, no
en el producto), y ambas categorías tenían las mismas cuentas contables, así que mover no
alteró nada contable.

### Decisiones tomadas (JC, 2026-08-22)

- **Los 20 genéricos se conservan como comodín**, no se archivan: de las 20 técnicas solo
  **9** tienen tarifa en la matriz, y 4Promotional no tiene ninguna. Sin comodín, esos
  casos se quedarían sin producto que usar.
- **Los 3 legado se archivan al final**, cuando los 51 estén probados y el equipo los use
  — no ahora.
- Se descartó ajustar el markup: el 1.1 que apareció en esas cotizaciones **es un caso
  especial**, no la práctica general. La hoja se queda con 1.275.

> Falsa alarma descartada: hay **96 templates sin categoría** en la base, pero están
> igual en producción sin haberla tocado. Son los productos de recompensa que Odoo genera
> solo para las promociones (`loyalty.program`). No tienen relación.

## Lo que sigue

- [x] ~~JC revisa `mapa_1_productos.csv`~~ — hecho el 2026-08-22: SKU corregidos y nombres aprobados
- [x] ~~Consolidar las dos categorías de servicio duplicadas~~ — hecho en TEST el 2026-08-22
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
