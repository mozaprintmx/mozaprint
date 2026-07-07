# Colores — procedencia, strip tokens y no-colores

Insumos del swatch derivation (`scripts/derive_colores.py`). Documenta de dónde salen
los hex, cómo se resuelve la cola larga por reglas, y qué valores del atributo `Color`
**no son color** (hallazgo de la auditoría del 2026-07-06).

## Origen

Reconciliación de `reports/color_values_20260706.csv` (dump de solo lectura de los
**204** valores reales del atributo `Color`, `create_variant=always`, ~5,444 productos).
El sync crea los valores por **string exacto sin normalizar** y **sin `html_color`**
(ver `analysis/supplier-sync/AUDITORIA_COLORES.md`), así que el swatch es 100% derivado.

## Estrategia de resolución (cascada en `derive_colores.py`)

Todo sobre `normalize()` (minúsculas + sin acentos + trim + colapsa espacios), la misma
de `derive_tecnicas.py`:

1. **Lex** — match exacto contra `colores_seed.csv` clase=`lex`. Hex curado, gana sobre el motor.
2. **Strip de tokens no-color** — quita sufijos de talla/género (ver abajo) y re-matchea el remanente.
3. **Base + modificador** — `colores_seed.csv` clase=`base` + `colores_modifiers.csv` (transformada HLS).
4. **Sin base resoluble** — no escribe `html_color`; marca `flag`. El reporte de flagged = inventario de contaminación.

Cobertura medida: **96.6%** de prod-hits solo con reglas; **~97.5%** con los alias de una
palabra ya incorporados al seed (humo, hueso, marino, aqua, oxford, menta, rose gold,
titanium, magenta/fucsia, frost).

## STRIP_TOKENS — se remueven antes de matchear el color base

Sufijos que el proveedor mezcló en el eje Color. Tras removerlos, el remanente se resuelve
como color normal (ej. `NEGRO-SMALL` → `negro`).

- **Talla**: `small`, `medium`, `large`, `xl`, `xs`, `xxl`, `xxxl`, `s`, `m`, `l`, `extra large`, `extra small`
- **Género**: `dama`, `caballero`, `unisex`

Separadores de sufijo reconocidos: `-` y espacio. Ej.: `AZUL-XL`, `NEGRO DAMA`.

## NON_COLOR — valores que NO reciben swatch (marcados `flag`)

No son color; el swatch derivation los deja sin `html_color` y los reporta. **NO se borran
ni se tocan aquí** — su limpieza es el proyecto diferido de de-contaminación de variantes
(ver más abajo).

- **Talla pura**: `small`, `medium`, `large`, `xl`, `xs`, `xxl`, `extra large`, `extra small`, `7x4cm`
- **Basura / no-color**: `unico`, `volteador`, `pelota`, `cucharon`, `cuchara`, `arnes`, `arbol`, `copo`, `proyecto especial`, `pride`
- **Material sin color claro**: `rpet`, `pasta`, `marmol`, `mezclilla`
- **Patrón / bicolor** (→ imagen de patrón, no hex plano): `tricolor`, `mexico`, `arcoiris`, `blanco con negro`, `negro/plata`, `negro/gris`, `negro/cafe`, `blanco/negro`, y cualquier valor con `/` o token `con`
- **Efecto no representable con hex plano** (→ patrón): `tornasol`, `jaspeado`, `marmol`

## MATERIAL_APROX — materiales con color natural asignable (opcional, tipo=flat)

Materiales que sí tienen un color visual razonable; se les da un hex aproximado en vez de
marcarlos. Decisión de UX: en promocionales el comprador reconoce el tono del material.

| Valor | Hex aprox | Nota |
|---|---|---|
| carton | #C8A97E | tono kraft |
| corcho | #C6A664 | |
| madera | #A0522D | |
| bambu / bambú | #E3C888 | (unifica la única fragmentación real BAMBU/BAMBÚ) |
| coco | #8B5A2B | |
| caoba | #6A342A | |
| cebada | #D8C89A | |
| caña / cana | #DAB86A | |
| periodico | #D9D2C5 | gris papel |

## HALLAZGO — contaminación del atributo `Color` (proyecto diferido, NO en Fase 2)

La reconciliación destapó que `Color` (con `create_variant=always`) contiene no-colores que
**generan variantes reales**:

| Contaminante | Valores | prod-hits | Ejemplos |
|---|---|---|---|
| Talla como color (pura + compuesta) | 8 + 34 | ~217 | `SMALL`, `NEGRO-SMALL`, `AZUL-XL` |
| Basura / no-color | 12 | ~98 | `UNICO` (87), `7X4CM`, `PELOTA` |
| Material como color | ~6 | ~200 | `RPET`, `PASTA`, `MARMOL` |
| Género como color | 9 | ~3 | `NEGRO DAMA`, `PLATA CABALLERO` (casi todos huérfanos) |
| Patrón / bicolor | 9 | ~106 | `TRICOLOR`, `BLANCO CON NEGRO`, `NEGRO/PLATA` |

Casos notables: `NEGRO-SMALL/MEDIUM/LARGE` deberían ser `Color=Negro × Talla=S/M/L`
(talla filtrada al eje color, inflando variantes); `UNICO` (87 productos) es catch-all de
"color único / como se muestra" — esos productos probablemente **no deberían tener eje Color**.

**Este hallazgo NO se arregla en la tarea de swatches.** Corregirlo es una migración de
variantes bajo `create_variant=always`: preservar/transferir `default_code` (SKU proveedor),
`x_stock_proveedor`, `image_1920`, `standard_price` por variante antes de colapsar valores,
con dry-run, backup y ajuste de inventario. Se agenda como proyecto/ADR aparte. Además, sin
un fix de normalización en ingesta (o alias en el sync), el sync **re-crea** el valor sucio
en la siguiente corrida.
