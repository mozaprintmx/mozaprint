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

### Dónde vive cada regla, y por qué ahí

Ninguna de estas reglas es código dentro de Odoo — eso es lo que se factura
([ADR 007](../decisions/007-retiro-motor-cotizacion-costo-codigo.md)). Se reparten así:

| Regla | Dónde se decide | Dónde acaba en Odoo | ¿Cuesta? |
|---|---|---|---|
| Qué combinación es un producto | `mapa_servicios_personalizacion.py` | `product.template` | no, es dato |
| Cómo se llama y qué dice al cliente | función `descripcion()` del mismo script | `name`, `description_sale` | no |
| Cuándo la línea se resalta | función `aviso()` | `sale_line_warn_msg` | no |
| Qué precio a qué cantidad | la matriz `x_costo_personalizacion` | `list_price` + `product.pricelist.item` | no |
| Que el ámbar signifique «ojo» | **Odoo, de fábrica** | `decoration-warning` de `sale.view_order_form` | no |

El único eslabón que no controlamos es el último, y no hace falta: Odoo ya trae
`or sale_line_warn_msg` en su regla de color.

### El resaltado ámbar: cuándo sí y cuándo no

Odoo pinta de ámbar **toda** línea cuyo producto tenga `sale_line_warn_msg` — la regla
`decoration-warning` de `sale.view_order_form` incluye `or sale_line_warn_msg`. Se
descubrió el 2026-08-23 porque JC notó el color en una línea de serigrafía.

> Eso confirma que el mecanismo de aviso **sigue vivo en Odoo 19** pese a que
> desapareció el selector `sale_line_warn`. Y funciona mejor de lo esperado: un
> resaltado permanente en la línea, en vez de un popup que se descarta por reflejo.

**Pero si los 53 productos llevan aviso, todas las líneas salen ámbar y el color deja de
significar nada.** Se reserva para los casos en que **la cantidad no se teclea como en el
resto de la cotización** y equivocarse cuesta dinero:

| Se resalta | Cuántos | Por qué |
|---|---|---|
| Lote **por tinta** | 11 | la cantidad son TINTAS |
| Lote sin tinta | 1 | la cantidad es 1 |
| Setups | 2 | la cantidad es 1 |
| Cantidad mínima | 16 | por debajo, la tarifa no aplica |
| **Total ámbar** | **30 de 53** | |

Los 23 restantes quedan **sin color**: 7 solo informaban del área máxima —que ya viaja en
el nombre y en la descripción— y 16 no tenían nada que advertir. Un área máxima es un
dato, no un riesgo.

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

## Paso 4 — carga de productos (piloto en TEST el 2026-08-22)

`scripts/cargar_servicios_personalizacion.py` — lee la hoja revisada, dry-run por
defecto, `--filtro` por prefijo de SKU, `--verificar` y `--rollback`.

Se cargó primero **solo láser Innovation Line: 14 productos**, el caso más simple —sin
tramos, sin lote, sin setup— para validar el mecanismo antes de soltar las 51.

**Qué escribe en cada producto**

| Campo | Valor |
|---|---|
| `default_code` / `name` / `description_sale` | de la hoja |
| `type` | `service` |
| `list_price` / `standard_price` | precio de venta / costo → Odoo calcula el margen solo |
| `categ_id` | `Servicios de Personalización` |
| `sale_ok` / `purchase_ok` / `is_published` | `True` / `False` / `False` |
| `sale_line_warn_msg` | el aviso interno |
| `x_es_servicio_personalizacion` / `x_tecnica_servicio_id` | marca y técnica |

**Resultado**: piloto de 14, y después **los 37 restantes**. Los **51 están cargados en
TEST**; `--verificar` sale con código 0 y la corrida repetida reporta «51 sin cambio».
La llave es el `default_code`. La categoría quedó con **73 productos activos**: 51
tarifados + 20 comodines + 2 legado (el tercero sigue archivado).

### Smoke test, sobre una cotización desechable

| Prueba | Resultado |
|---|---|
| Precio unitario contra la hoja, en 3 productos × 2 cantidades | ✓ los 6 exactos |
| `description_sale` baja sola a la línea | ✓ |
| Se encuentran tecleando `laser`, `termo`, `curpiel` o el SKU | ✓ |
| Categoría, `is_published=False`, costo para margen | ✓ |
| **Lote por tinta** — qty 1/2/3 multiplica bien ($1,211.25 → $3,633.75) | ✓ |
| **Lote sin tinta** — qty 1 = $1,753.12 | ✓ |
| **Con cantidad mínima** — qty 10 y 50 | ✓ el precio, ⚠ ver abajo |
| **Con curva de cantidad** — qty 100 y 600 | ✓ el precio base (los tramos son el paso 5) |

Las cotizaciones se borraron al terminar.

> **Dos huecos que el smoke test deja a la vista, y son los esperados:**
>
> 1. `PERS-SUBLI-INN-MODELTE146` tiene mínimo 50 pzas, y con qty=10 cobra
>    10 × $40.80 = $408 tan campante. La tarifa **no aplica** por debajo del mínimo, pero
>    nada lo impide: solo lo advierten la descripción y el aviso.
> 2. `PERS-SERI-PO-BOLSATEXTI-H603` con 600 pzas cobra el precio del tramo 100 ($11.96)
>    en vez del de 600 ($6.08). **Correcto por ahora**: las reglas de tramo son el paso 5,
>    y hasta que existan todos los productos con curva cotizan de más.

> **Bug corregido de camino**: `consolidar_categorias_servicio.py` buscaba los comodines
> por `x_es_servicio_personalizacion`, y los 51 tarifados también llevan esa marca — una
> segunda corrida habría renombrado «Láser · Curpiel · Innovation Line» a «Láser (precio a
> cotizar)». Ahora filtra por el prefijo de SKU `SERV-`.

## Paso 5 — tramos de cantidad y delegación (hecho en TEST el 2026-08-23)

`scripts/cargar_reglas_precio_personalizacion.py` — dry-run, `--apply`, `--smoke`,
`--rollback`. **77 reglas: 74 tramos + 3 de delegación.**

### Los tramos

Una regla por escalón, en la lista principal:

```
applied_on='1_product' · product_tmpl_id=<servicio>
min_quantity=600 · compute_price='fixed' · fixed_price=6.08
```

Odoo ordena por `min_quantity` descendente dentro del mismo nivel de especificidad, así
que a 700 piezas gana la regla de 600. **El primer tramo no lleva regla**: vive en el
`list_price` del producto.

### La delegación

Sin ella, un cliente con lista Volant o GMC caería al `list_price` —el precio del tramo
1— y se le cobraría de más a cualquier cantidad, porque los tramos solo existen en la
principal. Una regla por lista:

```
applied_on='2_product_category' · categ_id=<Servicios de Personalización>
compute_price='formula' · base='pricelist' · base_pricelist_id=<Default> · price_discount=0
```

Al ser por categoría es más específica que una global, así que además **protege la
personalización de descuentos globales** (GMC tiene uno al 0%).

### Smoke test — 92 precios, todos correctos

Prueba **cada tramo de cada uno de los 18 productos con curva**, en el escalón exacto y
justo por debajo, que es donde se ve si el orden de las reglas está bien:

```
PERS-SERI-PO-BOLSATEXTI-H603  ✓199→$11.96 ✓200→$8.78 ✓400→$6.76 ✓600→$6.08
                              ✓800→$5.41 ✓1,000→$4.73 ✓2,000→$4.05 ✓5,000→$3.38
                              ✓10,000→$2.70 ✓20,000→$2.44
```

Sale con **código 1 si un solo precio no cuadra**. La cotización desechable se borra.

### Delegación verificada en las cuatro listas

| Lista | 199 pzas | 600 | 5,000 |
|---|---|---|---|
| Default (MXN) | $11.96 | $6.08 | $3.38 |
| Volant (MXN) | $11.96 | $6.08 | $3.38 |
| GMC (MXN) | $11.96 | $6.08 | $3.38 |
| Dólar (USD) | $0.70 | $0.36 | $0.20 |

**Control de daño colateral**: los precios de imprenta (Volantes $250, Tarjetas $225)
siguen idénticos en Default y en Volant. La regla por categoría no los toca.

> **Para decidir algún día**: la lista Dólar convierte al tipo de cambio de Odoo
> (~17.1 MXN/USD). Si la personalización no se vende en USD, o se vende a otro tipo de
> cambio, esa regla de delegación se quita o se ajusta.

## Cotizaciones de prueba permanentes (TEST)

`scripts/crear_cotizaciones_prueba.py` — idempotente, las borra y recrea. Existen porque
el smoke test **borra su cotización al terminar**: prueba los precios pero no deja nada
que abrir. Ambas cuelgan del cliente `ZZ PRUEBA PERSONALIZACIÓN`, para que nunca se
mezclen con cotizaciones reales.

| Cotización | Para qué |
|---|---|
| **S00458** «ZZ PRUEBA TRAMOS» | Una línea por cada uno de los 18 productos con curva, en un escalón intermedio. Para verificar el tramo a ojo |
| **S00459** «ZZ EJEMPLO COTIZACIÓN» | Cómo se ve una real: secciones «Producto» y «Personalización», un caso POR TINTA y su línea de setup |

⚠️ Solo TEST: el script se niega a correr contra producción.

## Las listas de precios: solo Default está viva

Verificado el 2026-08-23, y corrige la impresión que daba el paso 5:

| Lista | Cotizaciones | Confirmadas | Clientes asignados |
|---|---|---|---|
| **Default** | 421 | 61 | **los 147** |
| Volant | 16 (la última de 2025-09) | 1 | 0 |
| GMC | **0** | 0 | 0 |
| Dólar | 1 (una prueba) | 0 | 0 |

Las tres reglas de delegación son correctas y no estorban, pero **protegen un escenario
que hoy no ocurre**. Si alguna de esas listas se activa algún día, ya está resuelto.

## El tamaño real de los pedidos, y por qué importa

Medido el 2026-08-24 sobre **874 líneas de producto físico** en cotizaciones reales
(excluyendo las de prueba). Salió al verificar si el aviso de «cantidad mínima» era ruido
o señal:

| Piezas por línea | % |
|---|---|
| 1 – 24 | **52.9 %** |
| 25 – 49 | 9.5 % |
| 50 – 99 | 11.4 % |
| 100 – 499 | 20.8 % |
| 500 – 999 | 3.0 % |
| 1,000+ | 2.2 % |

**Mediana: 20 piezas.** El 74 % de las líneas está por debajo de 100. En las cotizaciones
**confirmadas** —lo que de verdad se vendió— la mediana baja a **7 piezas** y el 88 % está
bajo 100.

### Las dos consecuencias

1. **El aviso de mínimo no es ruido, es la advertencia que más veces va a saltar.** Un
   producto con mínimo de 100 se topará con el caso en ~3 de cada 4 líneas.
2. **Las tarifas de Promo Opción apenas cubren la operación típica.** Arrancan en 50, 100,
   500 o 1,000 piezas; el negocio real se mueve entre 7 y 20.

| De los 51 productos | |
|---|---|
| Sirven **desde 1 pieza** | 23 — casi todos Innovation Line (láser, vinyl, digital, doming, bordado) |
| Tienen **mínimo de 50 a 1,000** | 16 — casi todos Promo Opción |
| Son **por lote** (cubren 1–1,000) | 12 |

Para una cotización típica de 20 piezas, los de Promo Opción **no aplican**. Ahí entran los
**comodines «(precio a cotizar)»**, y esto confirma que conservarlos fue más importante de
lo que parecía cuando se decidió.

> **Pendiente de negocio, para JC**: preguntar a Promo Opción si tienen tarifa para
> pedidos chicos. Si la mediana es 20 piezas y su tabla empieza en 100, o falta una lista
> de cantidades menores, o buena parte del volumen se está cotizando a mano fuera del
> sistema. Las dos cosas conviene saberlas.

## Pasos 6 y 7 — plantilla y puente entre pantallas (TEST, 2026-08-24)

### 6 · Plantilla de cotización

`scripts/crear_plantilla_cotizacion.py`. Una `sale.order.template` llamada
**«Cotización con personalización»**, con vigencia de 15 días y dos secciones vacías:
**Producto** y **Personalización**. No lleva productos —cambian en cada venta—, solo el
esqueleto que el motor retirado armaba por código.

> **Cómo se aplica realmente**: elegir la plantilla **no vuelca las secciones con un
> `write`**; el volcado vive en un onchange que dispara el cliente web. Por RPC se puede
> comprobar *cuántas* líneas propone, no *cuáles* — los comandos llegan con los valores
> vacíos porque el cliente los resuelve aparte. Por eso `--probar` contrasta el contenido
> contra la plantilla, que es su fuente, y el número contra el onchange.
>
> ⚠️ Al investigarlo se llamó `action_confirm` por descarte sobre una cotización de
> prueba y quedó confirmada, ya sin poder borrarse. Se limpió cancelándola. **No probar
> métodos privados a tientas sobre registros reales.**

### 7 · El SKU en la matriz

`scripts/enlazar_matriz_servicios.py`, re-ejecutable. Cierra el hueco entre las dos
pantallas: el vendedor consultaba la tarifa en **Ventas → Configuración → Costos de
personalización** y luego tenía que adivinar cuál de los 53 productos le tocaba.

| | |
|---|---|
| Campo | `x_sku_servicio`, **char** — `compute` y `related` vacíos: es un dato, **no se factura** |
| Dónde se ve | columna nueva en la lista de la matriz, junto a «Alcance» |
| Cómo se llena | desde la columna `llave` de `mapa_1_productos.csv` |
| Cobertura | **126 de 126** tarifas activas, 0 huérfanas |

```
Técnica         Alcance                   desde    costo   SKU del servicio
Láser           Termos 6x8 cm                 1     8.00   PERS-LASER-INN-TERMO68
Láser           Termos grabado 360°           1    22.00   PERS-LASER-INN-TERMOGRAB360
```

El auditor sigue reportando **0 líneas facturables** después de crear el campo.

## Paso 8 — el verificador permanente (TEST, 2026-08-24)

`scripts/audit_personalizacion.py`, solo lectura, **sale con código 1 si hay hallazgos**.

Existe porque el diseño tiene una fuente de verdad —la matriz— y dos derivados que se
cargan con scripts, y **nada obliga a que sigan sincronizados**. Alguien edita un costo,
nadie recarga, y las cotizaciones salen con el precio viejo sin que nada avise.

**No compara contra la hoja CSV**, a propósito: la hoja es un intermedio que puede estar
tan desactualizado como los productos. Recalcula todo desde la **matriz viva** y lee el
SKU de cada tarifa de su propio `x_sku_servicio`. Y reutiliza la función `aviso()` del
generador, para que el criterio del ámbar no pueda desincronizarse entre carga y
auditoría.

| # | Revisa |
|---|---|
| 1 | cada tarifa activa tiene SKU único y ese producto existe |
| 2 | `list_price` = costo × markup · `standard_price` = costo |
| 3 | cada escalón de la matriz tiene su regla, con su precio |
| 4 | productos `PERS-*` sin tarifa que los respalde |
| 5 | las demás listas heredan la categoría de la principal |
| 6 | categoría, tipo servicio, no publicado, no comprable |
| 7 | el aviso está donde debe y **solo** donde debe |

### Probado rompiendo cosas a propósito

Un verificador que solo sabe decir «bien» no vale nada. Se sabotearon tres cosas en TEST
y **las tres se detectaron**, con código de salida 1:

| Sabotaje | Lo que reportó |
|---|---|
| Cambiar un costo en la matriz | `PERS-LASER-INN-CURPI: precio $7.65 ≠ $12.74 (matriz)` + el costo |
| Borrar una regla de tramo | `regla FALTA: PERS-TERMO-PO-GEN-H70 min_qty 600 → $8.36` |
| Publicar un servicio en la tienda | `PERS-VINYL-INN-GEN-H81: PUBLICADO en la tienda` |

Restaurado todo, vuelve a salir limpio. El informe termina imprimiendo la secuencia de
reparación, para no tener que recordarla.

## Permisos (verificado 2026-08-25)

| Lo que se toca | Grupo necesario |
|---|---|
| Matriz de costos y técnicas | Ventas / Usuario: todos los documentos |
| Crear o editar productos `PERS-*` | **Productos / Crear** |
| Reglas de lista de precios | Ventas / Administrador |
| Plantilla de cotización | Ventas / Administrador |

Los tres usuarios internos (JC, Karina, Rosy) pueden hacer **todo** lo necesario: los tres
tienen *Ventas / Administrador* **y** *Productos / Crear*.

> ⚠️ **«Ventas / Administrador» NO implica «Productos / Crear»** — se comprobó recorriendo
> los grupos heredados. Es un grupo aparte que los tres tienen marcado a mano. A cualquier
> usuario nuevo que mantenga precios **hay que marcárselo explícitamente**, o los scripts
> fallarán al crear productos.
>
> JC y Karina además tienen **«Permisos de acceso»**, la llave maestra de Odoo. No hace
> falta para mantener precios.

## Códigos de técnica: las 20, no solo las 9

`TEC` en el generador mapea el `x_code` de cada técnica a su código corto de SKU. **Estaba
incompleto**: solo 13 de 20, y las 7 faltantes caían al `slug()` del código produciendo
cosas como `grab_co2` → **«GRAB2»**, que pierde el «CO».

No había mordido porque **esas 7 son justo las técnicas sin tarifa**. Habría salido a la
luz el día que se tabulara una — es decir, en el caso de uso «técnica nueva». Se
completaron las 20, usando los mismos códigos que ya llevan los comodines `SERV-*`.

**Al dar de alta una técnica nueva hay que agregarle su línea en `TEC` antes de cargarle
tarifas.** Queda dicho en el manual de administrador.

## Manual de administrador

[`docs/manual-admin-precios-personalizacion.md`](../docs/manual-admin-precios-personalizacion.md)
— para quien mantiene los precios, no para quien cotiza. Cubre actualizar un costo,
agregar una tarifa nueva y dar de alta una técnica, cada uno con su verificación y su
rollback, más la lista de lo que nunca hay que hacer.

**Publicado en Odoo** el 2026-08-25 (Información → artículo **74**, interno,
`is_published=False`, no visible desde el sitio web) con
`scripts/publicar_manual_knowledge.py`. El archivo del repo es la fuente; el artículo es
una copia que hay que volver a subir cuando cambie — es justo lo que se descuidó con el
manual anterior, que quedó describiendo un botón inexistente y acabó archivado.

### Revisión de contenido sensible, antes de publicar

| Revisado | Resultado |
|---|---|
| Credenciales, tokens, API keys | ✓ ninguno |
| Correos electrónicos | ✓ ninguno |
| Costos de proveedor concretos | ✓ ninguno — solo el factor de markup |
| Nombres de personas | **se quitaron**: la tabla de quién-tiene-qué se cambió por un puntero a `docs/usuarios-odoo.md` |

El markup **1.275** sí aparece, pero es una exposición ya conocida y aceptada del repo
público (anotada desde antes en `docs/checklist-deploy-produccion.md`). Si algún día se
quiere ocultar, va a `ir.config_parameter`.

## Lo que sigue

- [x] ~~JC revisa `mapa_1_productos.csv`~~ — hecho el 2026-08-22: SKU corregidos y nombres aprobados
- [x] ~~Consolidar las dos categorías de servicio duplicadas~~ — hecho en TEST el 2026-08-22
- [x] ~~Escribir el cargador y correrlo en test~~ — hecho
- [x] ~~Cargar los 51 productos + los 2 setups~~ — **53 en total**
- [x] ~~Las 74 reglas + las 3 de delegación, con smoke test~~ — hecho: 92 precios correctos
- [x] ~~Plantilla de cotización con secciones~~ — hecha en test
- [x] ~~Confirmar que `sale_line_warn_msg` sigue vivo en 19~~ — sí: pinta la línea de ámbar
- [x] ~~Verificador permanente matriz ↔ productos ↔ reglas~~ — hecho y probado con sabotajes
- [ ] Sumarlo al checklist trimestral del README cuando se despliegue en producción
- [ ] Manual nuevo para el equipo (el anterior se archivó de Knowledge el 2026-08-21)

### Fase 2, opcional

Meter los costos como `product.supplierinfo` con sus propios `min_qty` — la misma
estructura de tramos, pero del lado de compra. Con eso las personalizaciones
subcontratadas podrían mandarse como orden de compra real al proveedor. También es dato
puro, no cuesta.
