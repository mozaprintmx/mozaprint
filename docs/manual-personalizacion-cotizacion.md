# Manual de uso — Agregar personalización a una cotización

> Para el equipo de ventas. Explica cómo agregar el costo de personalización
> (serigrafía, bordado, láser, etc.) a una cotización, paso a paso.
>
> **Estado**: **activo en producción** desde el 2026-08-14. También publicado en
> **Información (Knowledge)** de Odoo para el equipo.

---

## ¿Qué hace esta función?

Cuando cotizas un producto que se va a **personalizar**, el sistema **calcula solo** el
precio de la personalización —según la **técnica**, el **proveedor** del producto, la
**cantidad** y las **tintas**— y lo agrega como una **línea aparte** en la cotización,
dentro de una sección "Personalización".

> **Precio de venta, no costo**: la matriz guarda el **costo del proveedor** (para control de
> gasto) y el **precio de venta** = costo × **1.275**. A la cotización va el **precio de venta**.
> El markup se puede ajustar por fila en la matriz de costos.

Si **no** hay un costo cargado para esa combinación, el sistema **no inventa un precio**:
crea una **solicitud de aprobación** para que un responsable lo defina.

> El precio de la personalización **siempre** sale de la matriz de costos del sistema.
> El vendedor no lo teclea a mano.

---

## Antes de empezar

- La cotización debe estar en **Cotización (borrador)** o **Cotización enviada**.
- Debe tener al menos **una línea de producto** (el artículo físico, con su cantidad).
- El producto debe tener un **proveedor** asignado (para saber qué tabla de costos aplica).

---

## Paso a paso

1. Entra a **Ventas → Cotizaciones** y abre (o crea) la cotización.
2. Agrega el **producto físico** como una línea normal, con la **cantidad** que pide el cliente.
3. Arriba, en el encabezado, haz clic en el botón **"Agregar personalización"**.
4. Se abre una ventana (asistente). Revisa y completa los campos:

   | Campo | Qué es | Nota |
   |---|---|---|
   | **Línea de cotización** | La línea del producto a personalizar | Si hay una sola línea, ya viene puesta. Si hay varias, elígela. |
   | **Técnicas del producto** | Las técnicas que el producto tiene asignadas | Informativo (solo lectura), se muestran como etiquetas. Úsalo de guía para elegir la técnica. |
   | **Técnica** | El método (serigrafía, bordado, láser…) | Viene precargada con la técnica sugerida del producto; puedes cambiarla. **Puedes elegir cualquiera**, incluso una que el producto no tenga asignada (útil para cotizar con proveedor externo). |
   | **¿Asignada al producto?** | Distintivo de la técnica elegida | Informativo. Dice **OK** si la técnica está asignada al producto, o **AVISO** si no lo está (no bloquea; solo te advierte para que verifiques o cotices externo). |
   | **Cantidad** | Piezas a personalizar | Viene de la línea del producto. |
   | **Número de tintas** | Colores de la impresión | Por defecto 1. Súbelo si el logo lleva más colores. |
   | **Número de posiciones** | Cuántos lugares se imprimen | Por defecto 1 (ej. solo el frente). |
   | **Área (cm²)** | Tamaño del grabado | Solo para técnicas que cobran por tamaño. Si no aplica, déjalo en 0. |
   | **Producto** | El artículo de esa línea, con su SKU | Informativo (solo lectura). Se llena solo al elegir la línea; úsalo para confirmar que es el producto correcto. |
   | **Proveedor del producto** | Quién surte el producto | Informativo (solo lectura). Se llena solo al elegir la línea. Es el proveedor con cuyas tarifas se cotiza la personalización. |
   | **Proveedor externo (opcional)** | Maquila / grabado in-house | Úsalo solo si la personalización la hace un proveedor externo (no el del producto). Ver más abajo. |

5. Haz clic en **"Aplicar"**.

---

## Qué puede pasar (3 variantes)

### ✅ A) Se agrega automáticamente
Cuando hay **exactamente un** costo que corresponde. Aparece una **línea nueva** bajo la
sección **"Personalización"** con el servicio y el precio ya calculado. Listo.

### 🔀 B) Te pide elegir el alcance
Cuando hay **varias** opciones **del proveedor del producto** para la misma técnica (por
ejemplo, ese proveedor cobra distinto según el tipo de producto: "Bolígrafos",
"Personalizado", etc.). El sistema te muestra la lista con sus precios.

**Qué hacer:** cierra el aviso, y en el asistente, en el campo **"Candidato elegido"**,
selecciona la opción que corresponde a tu producto. Vuelve a hacer clic en **"Aplicar"**.

> Solo aparecen las opciones **del proveedor que surte el producto**. Si el producto lo
> surte el proveedor X, no verás las tarifas del proveedor Y (aunque Y también haga esa
> técnica). Para grabar con alguien distinto, usa **"Proveedor externo"** (ver abajo).

### 💬 Antes de mandar a aprobación: siempre te pregunta
En cualquier caso que requiera aprobación, **no se envía nada de inmediato**: aparece un aviso
que explica **por qué** (ej. *"El candidato elegido no aplica a la cantidad"* o *"No hay tarifa
tabulada para esta combinación"*) con dos botones:

- **Cancelar** — no pasa nada; puedes corregir (elegir otro candidato, cambiar la cantidad…).
- **Aceptar y solicitar aprobación** — recién ahí se crea la solicitud.

### ⏳ C) Se manda a aprobación
Cuando **no hay un costo cargado** para esa combinación (técnica / proveedor / cantidad /
tintas / área). El sistema **no pone precio**: crea una **Solicitud de aprobación** con los
datos y marca la cotización como **"Requiere aprobación humana"**. Un responsable revisa y
define el costo (ver **"Para administradores"** más abajo).

> Es lo correcto: mejor pedir aprobación que cotizar un precio inventado.
> **Como vendedor no haces nada más**: el asistente se cierra con el aviso y la
> personalización quedará agregada en cuanto un administrador apruebe.

### 🚩 D) Hay opciones, pero **ninguna aplica** a tu producto
A veces el sistema te ofrece alcances que **no corresponden** al producto. Ejemplo: serigrafía
en un dominó de madera, y solo te ofrece "Cilindros", "Bolsas" y "Bolígrafos" — porque el
proveedor no tiene tabulado ese tipo de producto.

**Qué hacer:** marca la casilla **"Ninguna tarifa aplica - solicitar aprobación"** y haz clic en
**Aplicar**. El sistema **no te obliga** a elegir un alcance equivocado: manda la solicitud a
aprobación (igual que la variante C).

---

## Proveedor externo (personalización con maquila / in-house)

Por defecto, la personalización se cotiza con las tarifas del **proveedor que surte el
producto**. Si el grabado/impresión lo va a hacer **otro** proveedor (maquila externa o
in-house), usa el campo **"Proveedor externo (opcional)"** del asistente: elige ahí la
tarifa externa y aplica. El sistema usará ese costo e **ignorará** al proveedor del producto.

> **Nota**: esta opción estará **vacía hasta que se carguen las tarifas de personalización
> externa**. Mientras tanto, cotiza con el proveedor del producto (variantes A/B) o manda a
> aprobación (variante C).

---

## Para administradores — aprobar solicitudes (variante C)

### ¿Dónde están las solicitudes?
En **Ventas → Aprobaciones personalización** (menú). Ahí ves todas las solicitudes con su
**estado**: 🟠 Pendiente / 🟢 Aprobada / 🔴 Rechazada.

### ¿Cómo apruebo una?
1. Abre la solicitud **Pendiente**.
2. Revisa el contexto (**cotización, línea, técnica, cantidad**) y el **motivo** por el que
   se pidió aprobación.
3. Captura el **"Costo unitario aprobado"** (lo que te cobra el proveedor) y, si aplica, el
   **"Costo de setup aprobado"**. El **precio de venta** se calcula solo (costo × **markup**,
   estándar 1.275) y es el que se cobrará al cliente; puedes ajustar el markup de esa solicitud.
4. Revisa **"Unidad del costo aprobado"**: **Por pieza** (se multiplica por la cantidad) o
   **Por lote** (precio fijo del lote completo).
5. El **servicio** ya viene precargado según la técnica (puedes cambiarlo).
6. Clic en **"Aprobar y agregar a la cotización"**.

### ¿Reutilizar esta tarifa en el futuro? (opcional pero muy útil)
Antes de aprobar, en la sección **"¿Reutilizar esta tarifa en el futuro?"** puedes decidir si ese
precio **se guarda en la matriz de costos**, para que la próxima vez ya salga tabulado y nadie
tenga que volver a pedir aprobación:

| Opción | Qué hace |
|---|---|
| **No guardar** (por defecto) | El precio aplica solo a esta cotización. La matriz no cambia. |
| **Guardar como tarifa del proveedor del producto** | Se agrega a las tarifas de ese proveedor → la próxima vez aparecerá en **"Candidato elegido"**. |
| **Guardar como tarifa de personalización EXTERNA** | Se agrega como tarifa de maquila/in-house → aparecerá en **"Proveedor externo"**. |

Si eliges guardar, revisa también:
- **Alcance de la nueva tarifa**: el nombre con el que la verán después (ej. "Dominó / juegos de
  madera"). Viene precargado con el nombre del producto; ponle un nombre de **categoría**, no de
  un solo producto, si aplica a varios.
- **Cantidad desde / hasta**: el rango de piezas para el que vale esa tarifa (**0 = sin límite**).

> Es **opcional**: si no estás seguro, deja "No guardar". Nunca se modifica la matriz sin que tú
> lo elijas.

### ¿Qué pasa al aprobar?
El sistema **genera automáticamente la línea de personalización** en la cotización (bajo la
sección "Personalización", con el costo que aprobaste), marca la solicitud como **Aprobada**
(registra quién y cuándo) y **quita** el aviso de "requiere aprobación". No hay que agregar la
línea a mano. Si elegiste guardar la tarifa, además la deja registrada en la matriz de costos.

### ¿Y si no procede?
Usa **"Rechazar"**: la solicitud queda Rechazada y la cotización se libera del aviso, **sin**
agregar personalización.

> **Nota**: hoy cualquier usuario interno puede aprobar. Si quieres restringirlo a ciertos
> roles, se puede configurar aparte.

---

## Cómo queda la cotización

Al aplicar, la cotización se organiza en dos secciones:

- **Producto** — el artículo físico.
- **Personalización** — el servicio de personalización con su precio, y **si la técnica tiene
  costo de setup**, una segunda línea **"Setup / preparación"**.

### ¿Qué es la línea de "Setup / preparación"?
El **setup** es el cargo **único por orden** que cobra el proveedor por preparar la máquina:
la pantalla de serigrafía, el ponchado del bordado, la placa de tampografía. **No se multiplica
por la cantidad** (por eso va en cantidad 1). Si pides 100 o 1,000 piezas, se cobra una sola vez.

El sistema la agrega **automáticamente** cuando la tarifa tiene setup. Si cambias a una técnica
sin setup, la línea desaparece sola. Algunos setups son condicionales (ej. bordado sin costo de
ponchado arriba de cierta cantidad): eso ya está contemplado en la matriz de costos.

---

## Notas y buenas prácticas

- **Re-aplicar no duplica**: si vuelves a usar el botón sobre la misma línea, la
  personalización se **actualiza** (no se agrega otra vez).
- **Por pieza vs. por lote**: algunos proveedores cobran la personalización por lote
  completo, no por pieza. El sistema ya lo distingue automáticamente.
- **Precio = costo parametrizado**: hoy la personalización se cotiza al costo cargado
  (sin margen adicional). Si se decide agregar margen, se avisará.

---

## Errores y mensajes comunes

| Mensaje | Qué significa / qué hacer |
|---|---|
| "La cotización debe estar en borrador o enviada" | La cotización ya está confirmada/cancelada. Solo funciona en borrador o enviada. |
| "La cotización no tiene líneas de producto" | Agrega primero el producto físico. |
| "Hay N alcances para esta combinación…" | Es la variante **B**: elige el alcance en "Candidato elegido" y aplica de nuevo. |
| Se creó una solicitud de aprobación | Es la variante **C**: no había costo cargado; queda pendiente de que un responsable lo defina. |
| "No hay producto-servicio configurado para la técnica" | Falta dar de alta el servicio de esa técnica (avísale al administrador). |

---

## Preguntas frecuentes

**¿Puedo cambiar la técnica que sugiere el sistema?**
Sí, en el asistente, en el campo "Técnica".

**¿Y si el logo lleva 2 tintas o se imprime en 2 posiciones y no aparece precio?**
Esos casos no siempre están tabulados; si no hay costo, se va a aprobación (variante C).

**¿El cliente ve las dos secciones?**
Sí, la cotización muestra "Producto" y "Personalización" como secciones separadas.

---

## Para administradores — la matriz de costos

**Ventas → Configuración → Costos de personalización**: aquí vive cada tarifa (técnica ×
proveedor × alcance × rango de cantidad). Se puede editar **directo en la lista**.

Columnas clave:

| Columna | Qué es |
|---|---|
| **Alcance** | La categoría a la que aplica (ej. "Cilindros", "Bolsas (Textiles) máximo 603 cm2"). Es lo que ves al elegir candidato. |
| **Cantidad desde / hasta** | El tramo de piezas (**0 = sin límite**). |
| **Unidad de cobro** | **Por pieza** (se multiplica por la cantidad) o **Por lote** (monto fijo). ⚠ Es el error más caro si se equivoca. |
| **Costo** | Lo que cobra el proveedor (control de gasto). |
| **Markup** | Factor costo → precio. Estándar **1.275**. |
| **Precio de venta** | Se calcula solo (costo × markup). **Puedes sobrescribirlo** si necesitas un precio especial. |
| **Costo/Precio de setup** | El cargo único por orden y su precio de venta. |
| **Escala por tinta** | Si el precio se multiplica por el número de tintas. |
| **Externa** | Marca las tarifas de maquila/in-house (no ligadas al proveedor del producto). |
| **Activa** | Desmarcar retira la tarifa del motor sin borrarla. |

También existe **Ventas → Configuración → Técnicas de personalización** para el catálogo de
técnicas (código, nombre, orden, aliases de proveedor).

> Si te equivocaste al guardar una tarifa desde una aprobación (ej. elegiste "por pieza" en vez
> de "por lote"), aquí es donde se corrige.
