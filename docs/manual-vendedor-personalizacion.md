# Cotizar personalización — manual del vendedor

> Para quien **hace cotizaciones**. Si lo que buscas es cambiar precios, ese es otro
> manual: [`manual-admin-precios-personalizacion.md`](manual-admin-precios-personalizacion.md).
>
> 📗 **Publicado en Odoo** → Información → *Cotizar personalización — manual del vendedor*.

---

## 1. Qué estás cotizando

Una cotización con personalización lleva **siempre al menos dos líneas**:

```
── PRODUCTO
   [SOC 984 MX] CILINDRO ODESA                    500 × $10.05  =  $5,025.00
── PERSONALIZACIÓN
   [PERS-SERI-INN-TEXTIHIELE-LOTE] Serigrafía…      2 × $3,442.50 = $6,885.00
   [PERS-SETUP-TAMPO-INN] Setup / preparación       1 × $280.50   =   $280.50
```

El **artículo** y el **servicio de marcarlo** se cobran por separado, porque el proveedor
nos los cobra por separado. **Tú no calculas el precio de la personalización**: eliges el
servicio correcto, pones la cantidad, y Odoo pone el precio.

---

## 2. Las tres reglas que tienes que saber

Todo lo demás es mecánico. Esto no.

### Regla 1 · La cantidad casi siempre son piezas… pero no siempre

| Si el nombre dice | La cantidad que tecleas es | Cuántos productos |
|---|---|---|
| *(nada especial)* | **piezas** | 39 |
| **POR TINTA** | **el número de tintas** del logo | 11 |
| **POR LOTE** | **1** | 1 |
| *Setup / preparación* | **1** | 2 |

**Ejemplo del caso POR TINTA.** El cliente quiere 500 bolígrafos con logo a 2 colores:

```
── PRODUCTO
   Bolígrafo                                      cantidad 500   ← piezas
── PERSONALIZACIÓN
   Serigrafía POR TINTA · Bolígrafos… (lote ≤1,000 pzas)
                                                  cantidad 2     ← TINTAS
```

Si ahí tecleas 500, la cotización sale con un número absurdo y alguien lo va a notar. **El
error caro es el otro**: teclear 1 cuando el logo lleva 2 tintas. El total se ve creíble,
nadie lo cuestiona, y descubrimos el hueco cuando llega la factura del proveedor.

> **Cuenta las tintas del logo antes de teclear.** Es el único dato que el sistema no
> puede adivinar por ti.

### Regla 2 · Hay tarifas con cantidad mínima

Muchas tarifas de **Promo Opción** empiezan en 50, 100, 500 o 1,000 piezas. Por debajo de
ese mínimo **la tarifa no existe** — y Odoo no te lo va a impedir: multiplicará tan
tranquilo y te dará un precio que el proveedor no nos va a respetar.

El mínimo está escrito en la descripción de la línea («Pedido mínimo 100 piezas»).

> Como la mayoría de nuestros pedidos son de menos de 100 piezas, **este es el caso con el
> que más te vas a topar**. Si tu cantidad es menor al mínimo, ve al punto 6.

### Regla 3 · El precio baja solo al subir la cantidad

No busques descuentos ni tablas: pones la cantidad y **Odoo aplica el tramo que
corresponde**. Si cambias la cantidad, el precio se recalcula.

---

## 3. Cómo cotizar, paso a paso

1. **Ventas → Cotizaciones → Nuevo**, y elige el cliente.
2. En **Plantilla de cotización**, elige **«Cotización con personalización»**. Aparecen las
   secciones `Producto` y `Personalización`.
3. Bajo **Producto**: agrega el artículo con la cantidad de piezas.
4. Bajo **Personalización**: en el campo de producto, **teclea la técnica** — `seri`,
   `laser`, `bordado`, `vinyl`… — y elige de la lista.
5. **Pon la cantidad** según la Regla 1.
6. Si la técnica lleva **setup**, agrega esa línea con cantidad 1 (punto 5).
7. Revisa el total y envía.

---

## 4. Encontrar el servicio correcto

### Camino rápido: teclear en la línea

Escribe la técnica y el desplegable filtra. También funciona por alcance (`termo`,
`bolsas`, `curpiel`) o por código (`PERS-LASER`).

Los nombres se leen así:

```
Serigrafía POR TINTA · Bolsas (Textiles) máximo 603 cm² · Promo Opción (lote ≤1,000 pzas)
└─ técnica ─┘└ regla ┘└──────── a qué aplica ────────┘  └ proveedor ┘└─ límite ─┘
```

### Camino seguro: la matriz de costos

**Ventas → Configuración → Costos de personalización.** Filtra por técnica y proveedor y
verás todas las tarifas con su rango de cantidad. La columna **SKU del servicio** te dice
exactamente qué producto teclear.

> Úsala cuando dudes cuál de dos alcances parecidos aplica, o para confirmar un mínimo.

### Cómo se lee un código

```
PERS - SERI - PO - BOLSATEXTI - H603 - LOTE
  │      │     │        │        │      └── se cobra por lote
  │      │     │        │        └── hasta 603 cm² (D = desde)
  │      │     │        └── a qué aplica
  │      │     └── proveedor: INN, PO, 4P
  │      └── técnica
  └── siempre PERS- en los servicios con precio cargado
```

---

## 5. La línea de setup

El **setup** es el cargo único por preparar la máquina —la pantalla de serigrafía, el
ponchado del bordado—. **No se multiplica por la cantidad**: pidas 50 o 5,000 piezas, se
cobra una vez.

Hay dos, y son de Innovation Line:

| Código | Cuándo |
|---|---|
| `PERS-SETUP-TAMPO-INN` | Tampografía |
| `PERS-SETUP-BORD-INN` | Bordado — ⚠️ **no se cobra a partir de 201 piezas** |

Van **siempre con cantidad 1**. Si no estás seguro de si aplica, la descripción del
servicio principal lo dice.

---

## 6. Cuando no hay tarifa cargada

Pasa a menudo, y es normal. Los casos:

- La técnica no está tabulada — **11 de las 20** solo existen como comodín
- El proveedor es **4Promotional**, que no tiene ninguna tarifa cargada
- Tu cantidad está **por debajo del mínimo**
- El logo lleva **más de 1 tinta o más de 1 posición** en una tarifa que no escala

**Qué haces:** usa el producto comodín de esa técnica, que se llama
**«… (precio a cotizar)»** — por ejemplo `Serigrafía (precio a cotizar)`. Sale con precio
0 y **tecleas el precio a mano**, después de pedirle la cotización al proveedor.

> ⚠️ **Nunca inventes el precio.** Si no está tabulado, es porque nadie lo ha negociado
> para ese caso. Pídelo antes de enviar.

---

## 7. ¿Por qué algunas líneas salen de color naranja?

Odoo pinta de **ámbar** las líneas cuyo producto lleva un aviso. **No es un error**: es el
sistema diciéndote *«ojo, esta línea no se cotiza como las demás»*.

Salen en ámbar **30 de 53** servicios, y siempre por la misma razón: **la cantidad no se
teclea como en el resto de la cotización**.

| Ámbar porque | Cuántos |
|---|---|
| La cantidad son **tintas** | 11 |
| La cantidad es **1** (lote o setup) | 3 |
| Hay **cantidad mínima** | 16 |

Si una línea de personalización sale **en blanco**, es una tarifa normal por pieza y sin
mínimo: teclea las piezas y ya.

---

## 8. Catálogo de referencia

**Los precios no se listan aquí a propósito**: cambian cuando el proveedor los sube, y una
tabla impresa se queda vieja sin avisar. **El precio bueno es siempre el que Odoo pone al
teclear la cantidad.** Esto es para saber *qué existe*.

De las 20 técnicas, **9 tienen tarifa** (51 servicios). Las otras 11 van por comodín.

| Técnica | Servicios | Cuidado |
|---|---|---|
| **Láser** | 18 | Los 14 de Innovation Line sirven **desde 1 pieza**; los 4 de Promo Opción piden **mínimo 50** |
| **Serigrafía** | 14 | 8 de INN son **POR TINTA**; 5 de PO tienen mínimos de 100 a 1,000; 1 es por lote |
| **Sublimación** | 4 | Modelos TE-146/147/148/176 · **mínimo 50** |
| **Tampografía** | 4 | 3 de INN son **POR TINTA** y llevan setup; 1 de PO con **mínimo 500** |
| **Impresión Digital** | 3 | Por tramo de área: ≤25, ≤100 y ≤200 cm² · desde 1 pieza |
| **Vinyl** | 3 | Por tramo de área: ≤81, ≤324 y ≤784 cm² · desde 1 pieza |
| **Doming** | 2 | Porta gafete (YOYO) y Pop Socket · desde 1 pieza |
| **Termograbado** | 2 | ≤70 y ≤150 cm² · **mínimo 100** |
| **Bordado** | 1 | Hasta 49 cm² · lleva setup hasta 200 piezas |

**Sin tarifa, solo comodín**: Bajo Relieve, DTF, DTF UV, Grabado CO2, Grabado Espejo,
Impresión UV, Offset, Pantógrafo, Punta Diamante, Sand Blast y Transfer.

> ⚠️ **No uses** `FULL COLOR` ni `Impresión con Serigrafía`. Son productos viejos de cuando
> se cotizaba a mano; siguen ahí solo para que las cotizaciones antiguas se puedan
> consultar.

---

## 9. Dónde consultar cada cosa

| Qué necesitas | Dónde |
|---|---|
| El precio de una personalización | **En la cotización**: pon la cantidad y Odoo lo calcula |
| Qué tarifas existen y sus rangos | Ventas → Configuración → **Costos de personalización** |
| Qué técnicas hay | Ventas → Configuración → **Técnicas de personalización** |
| Qué técnica admite un producto | Ficha del producto → campo **Técnica** |
| Qué significa un término | [Glosario](glossary.md) |

---

## 10. Errores comunes

| Síntoma | Qué pasó |
|---|---|
| La personalización sale carísima | Tecleaste piezas en una línea **POR TINTA**. Pon el número de tintas |
| El precio no baja al subir la cantidad | Puede que ya estés en el último tramo, o que la tarifa sea por lote |
| No encuentro la técnica en el desplegable | No está tabulada: usa el comodín **«(precio a cotizar)»** |
| El cliente pide menos que el mínimo | La tarifa no aplica. Pide precio al proveedor y usa el comodín |
| El precio de mi cotización vieja cambió | **No pasa.** El precio se congela en la línea cuando la creas |

---

## 11. Lo que nunca hay que hacer

- **No cambies el precio** de una línea de personalización tarifada. Si el precio está mal,
  avísale a quien mantiene la matriz — está mal para todos, no solo para tu cotización.
- **No inventes un precio** cuando no hay tarifa. Usa el comodín y pide la cotización.
- **No uses una tarifa por debajo de su mínimo** aunque Odoo te deje.
- **No borres la sección** «Personalización». Es lo que hace legible el PDF para el cliente.
