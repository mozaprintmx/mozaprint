# Manual de administrador — precios de personalización

> Para quien **mantiene los precios**, no para quien cotiza. Cubre tres tareas:
> actualizar un costo, agregar una tarifa nueva y dar de alta una técnica que
> todavía no existe.
>
> Diseño completo en [`specs/personalizacion-nativa.md`](../specs/personalizacion-nativa.md).
>
> 📗 **Publicado en Odoo** → Información → *Manual de administrador — Precios de
> personalización* (artículo **74**, interno, no visible desde el sitio web).
> **Este archivo es la fuente**; si se edita, hay que volver a subirlo con
> `scripts/publicar_manual_knowledge.py`.

---

## 1. La idea que hay que tener clara antes de tocar nada

Hay **una sola fuente de verdad**: la matriz de costos.

```
   Ventas → Configuración → Costos de personalización     ← AQUÍ se edita
                    │
                    │   los scripts traducen
                    ▼
   ┌────────────────────────────────┬──────────────────────────────┐
   │ 53 productos de servicio       │ 77 reglas de lista de precios │
   │ (nombre, precio base, aviso)   │ (tramos de cantidad)          │
   └────────────────────────────────┴──────────────────────────────┘
                    ▲                            ▲
              NO se editan a mano — se sobrescriben
```

**Regla de oro**: si editas el precio de un producto de personalización desde la ficha
del producto, la próxima carga lo pisa. El cambio se hace **siempre en la matriz**.

### Por qué está montado así

Odoo **cobra por cada 100 líneas de código** que viva dentro de Studio. El motor
anterior costaba 3 cargos mensuales y por eso se retiró
([ADR 007](../decisions/007-retiro-motor-cotizacion-costo-codigo.md)). Los precios ahora
son **datos** —productos y reglas, que no se cobran— y la inteligencia vive en scripts
del repo, que corren desde tu computadora y tampoco se cobran.

---

## 2. Permisos: quién puede hacer qué

Verificado el 2026-08-25 en test y producción.

| Lo que se toca | Grupo necesario |
|---|---|
| Matriz de costos y técnicas | **Ventas / Usuario: todos los documentos** |
| Crear o editar productos de servicio | **Productos / Crear** |
| Reglas de lista de precios | **Ventas / Administrador** |
| Plantilla de cotización | **Ventas / Administrador** |

**Los tres usuarios internos actuales tienen los cuatro permisos**, así que cualquiera
puede hacer todo lo de esta guía. El detalle de quién tiene qué vive en
[`docs/usuarios-odoo.md`](usuarios-odoo.md), no aquí.

> ⚠️ **«Ventas / Administrador» NO incluye «Productos / Crear»** por herencia — se
> comprobó recorriendo los grupos heredados. Es un grupo aparte, marcado a mano en cada
> usuario. Si das de alta a alguien más para mantener precios, **hay que marcárselo
> explícitamente** o los scripts fallarán al crear productos.
>
> ⚠️ Para nada de este manual hace falta el permiso **«Permisos de acceso»**, que es la
> llave maestra de Odoo. Si alguien lo necesita para mantener precios, algo está mal
> configurado.

Los scripts se conectan con las credenciales de `analysis/supplier-sync/.env`, que hoy son
las de JC. Nunca se suben al repo.

---

## 3. Actualizar un costo que ya existe

El caso más común: el proveedor sube precios.

### 3.1 · Edítalo en la matriz

**Ventas → Configuración → Costos de personalización**. Filtra por técnica y proveedor,
y edita la columna **Costo (MXN)** directo en la lista. Cambia solo las filas que subieron.

> La columna **SKU del servicio** te dice qué producto se va a actualizar. Si la fila que
> editas dice `PERS-SERI-PO-BOLSATEXTI-H603`, ese es el que cambiará de precio.

Si el proveedor cambió los **tramos** —no solo los importes— edita también *Cantidad
mínima* y *Cantidad máxima*, o agrega filas nuevas.

### 3.2 · Propaga el cambio

Desde la carpeta del repo, uno tras otro:

```bash
python scripts/mapa_servicios_personalizacion.py --target prod
python scripts/cargar_servicios_personalizacion.py --target prod
python scripts/cargar_reglas_precio_personalizacion.py --target prod
```

**Los tres primeros son simulacros: no escriben nada.** Léelos. El segundo y el tercero te
dicen exactamente qué productos y qué reglas van a cambiar, con el precio de antes y el de
después. Si eso es lo que esperabas, repite los dos últimos con `--apply --si-produccion`:

```bash
python scripts/cargar_servicios_personalizacion.py --target prod --apply --si-produccion
python scripts/cargar_reglas_precio_personalizacion.py --target prod --apply --si-produccion
```

### 3.3 · Verifica

```bash
python scripts/audit_personalizacion.py --target prod
python scripts/cargar_reglas_precio_personalizacion.py --target prod --smoke
```

El primero comprueba que matriz, productos y reglas digan lo mismo. El segundo arma una
cotización desechable, prueba **cada tramo de cada producto** contra la matriz y la borra.
Los dos salen con **código 1** si algo no cuadra.

### 3.4 · Si algo salió mal

Cada script deja un respaldo en `backups/` y tiene `--rollback`:

```bash
python scripts/cargar_servicios_personalizacion.py --target prod --rollback --apply
python scripts/cargar_reglas_precio_personalizacion.py --target prod --rollback --apply
```

**Las cotizaciones ya hechas no se tocan**: el precio vive en la línea de la cotización, no
en el producto. Cambiar un precio nunca modifica una cotización existente.

---

## 4. Agregar una tarifa nueva a una técnica que ya está tabulada

Ejemplo: Promo Opción saca precio para un alcance que no teníamos.

### 4.1 · Da de alta la fila

En la misma pantalla, botón **Nuevo**. Lo que no puede faltar:

| Campo | Cuidado |
|---|---|
| **Técnica** y **Proveedor** | Deben existir ya |
| **Alcance** | El texto que distingue esta tarifa de las demás del mismo proveedor y técnica. **De aquí sale el SKU** |
| **Cantidad desde / hasta** | 0 en «hasta» = sin límite |
| **Unidad de cobro** | ⚠️ **El error más caro.** *Por pieza* multiplica por la cantidad; *Por lote* es monto fijo |
| **Costo (MXN)** | Lo que cobra el proveedor, sin markup |
| **Markup** | 1.275 salvo indicación |
| **Escala por tinta** | Solo si el proveedor cobra el precio **por cada tinta** |
| **Activa** | Marcada |

**Deja «SKU del servicio» vacío**: lo llena el script.

Si la tarifa tiene **varios tramos de cantidad**, da de alta **una fila por tramo**, todas
con la misma técnica, proveedor y alcance, cambiando solo *cantidad desde/hasta* y el
costo.

### 4.2 · Revisa el SKU ANTES de cargar

```bash
python scripts/mapa_servicios_personalizacion.py --target prod
```

Abre `analysis/costos-personalizacion/mapa_1_productos.csv` y busca la fila nueva.
**Revisa el SKU y el nombre**: el SKU se arma solo con dos palabras del alcance más los
dígitos, y a veces sale feo. **Puedes corregirlo a mano en el CSV** — el generador respeta
los SKU ya escritos y solo inventa los que faltan.

> Si sale un error de **SKU duplicado**, el generador se detiene. Significa que el alcance
> nuevo se parece demasiado a uno existente: cámbialo en la matriz para que se distingan.

### 4.3 · Carga y enlaza

```bash
python scripts/cargar_servicios_personalizacion.py --target prod --apply --si-produccion
python scripts/cargar_reglas_precio_personalizacion.py --target prod --apply --si-produccion
python scripts/enlazar_matriz_servicios.py --target prod --apply --si-produccion
```

El tercero es el que escribe el SKU de vuelta en la matriz. Luego verifica como en 3.3.

---

## 5. Agregar una técnica que todavía no existe

Ejemplo: empiezan a ofrecer **Grabado CO2** y el proveedor manda su lista.

De las 20 técnicas del catálogo, **solo 9 tienen tarifa** hoy. Las otras 11 existen como
comodín «(precio a cotizar)» y se cotizan a mano.

### 5.1 · ¿La técnica existe en el catálogo?

**Ventas → Configuración → Técnicas de personalización**. Si ya está, salta al 5.2. Si no,
créala con su **Código** en minúsculas y sin acentos (`grab_co2`, `sandblast`).

### 5.2 · Asegura su código corto — este paso es fácil de olvidar

Abre [`scripts/mapa_servicios_personalizacion.py`](../scripts/mapa_servicios_personalizacion.py)
y busca el diccionario `TEC`. **Las 20 técnicas actuales ya están ahí.** Si diste de alta
una nueva, agrégale su línea:

```python
TEC = {
    …
    "mi_tecnica_nueva": "MITEC",
}
```

> **Por qué importa**: sin entrada, el SKU se deriva del código y salen cosas como
> `grab_co2` → **«GRAB2»**, que pierde el «CO» y no se entiende. Esto ya pasó y por eso
> las 20 están cargadas explícitamente.

### 5.3 · El resto es como el punto 4

Da de alta las tarifas, genera la hoja, **revisa los SKU nuevos**, carga y verifica.

### 5.4 · Retira el comodín, si procede

Cuando una técnica pasa a estar tabulada, su producto **«… (precio a cotizar)»** deja de
tener sentido para los casos cubiertos. Puedes archivarlo desde la ficha del producto —
pero **solo si la tarifa cubre todo el rango de cantidades que cotizan**. Como la mediana
de pedido está en **20 piezas** y varias tarifas arrancan en 50 o 100, casi siempre
conviene **dejar el comodín**.

---

## 6. Lo que NUNCA hay que hacer

| No hagas | Por qué |
|---|---|
| Editar el precio en la ficha del producto `PERS-*` | La próxima carga lo pisa. Se edita en la matriz |
| Crear reglas de lista de precios a mano | El auditor las marcará como sobrantes y las cargas las pueden borrar |
| **Borrar** una tarifa que ya se usó | Desmárcale **Activa**. Borrarla deja el producto huérfano |
| Renombrar los proveedores `INNOVATIONLINE`, `PROMOOPCION`, `4PROMOTIONAL` | El sync los busca por nombre exacto y **crea un duplicado en silencio** |
| Publicar un producto `PERS-*` en la tienda | Son precios internos de personalización, no artículos de catálogo |
| Cambiar el markup fila por fila sin avisar | Es la política de margen. El estándar es 1.275 |

---

## 7. Chuleta

```bash
# ── ver qué cambiaría (nunca escriben) ─────────────────────────────
python scripts/mapa_servicios_personalizacion.py      --target prod
python scripts/cargar_servicios_personalizacion.py    --target prod
python scripts/cargar_reglas_precio_personalizacion.py --target prod

# ── aplicar ────────────────────────────────────────────────────────
python scripts/cargar_servicios_personalizacion.py    --target prod --apply --si-produccion
python scripts/cargar_reglas_precio_personalizacion.py --target prod --apply --si-produccion
python scripts/enlazar_matriz_servicios.py            --target prod --apply --si-produccion

# ── verificar (código 1 si algo no cuadra) ─────────────────────────
python scripts/audit_personalizacion.py               --target prod
python scripts/cargar_reglas_precio_personalizacion.py --target prod --smoke

# ── deshacer ───────────────────────────────────────────────────────
python scripts/cargar_servicios_personalizacion.py    --target prod --rollback --apply
python scripts/cargar_reglas_precio_personalizacion.py --target prod --rollback --apply
```

**Cambia `prod` por `test` para ensayar primero.** Es gratis y es la costumbre correcta con
cualquier cambio grande.

> Todos los scripts son **simulacro por defecto** y **idempotentes**: correrlos de más no
> hace daño. Si no hay nada que cambiar, lo dicen y salen.
