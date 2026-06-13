# Seed de técnicas de personalización — procedencia y limpieza

Catálogo canónico para el modelo `x_tecnica_personalizacion`. Lo carga
`scripts/seed_tecnicas.py` (F4b) y lo usa la normalización de técnica en el sync
de proveedores. Este documento registra de dónde sale y qué limpieza se aplicó.

## Origen

Derivado de los valores reales del campo legacy `x_tecnica_impresion`
(char, texto libre, **alimentado por el API de cada proveedor**) en
`product.template`. La auditoría del 2026-06-11 encontró **159 valores distintos
sin normalizar** sobre ~5,227 productos con valor (combos, mayúsculas/minúsculas
inconsistentes, separadores mezclados `-` `/` `,`, typos y notas a mano).

## Decisiones de taxonomía (D7)

- **Lista plana de 20 técnicas**, sin familias. Razón: el precio varía por
  técnica (grabado láser ≠ bajo relieve en costo y descripción), no por familia;
  y permite listarlas con descripción propia en el sitio.
- **DTF genérico**: los proveedores no distinguen DTF Textil vs DTF UV de forma
  consistente. Se conserva además `DTF UV` como técnica aparte (1 producto de
  otro proveedor que sí lo especifica).
- **Nombres dobles conservados**: Doming (Gota de Resina), Sand Blast (Grabado en
  Arena), Láser (Grabado Láser), Transfer (Termocalca), Bajo Relieve (Embozado).
- **Técnicas raras (1 producto)** marcadas para confirmar con producción si son
  técnica real o dato suelto: `vinyl`, `dtf_uv`, `offset`, `transfer`. Se
  conservan distintas porque cada una tendría costo/descripción propios.

## Limpieza de aliases

La columna `x_aliases` contiene las variantes crudas que los proveedores envían;
el sync hace match contra ellas para resolver la técnica canónica. Limpieza:

- **Se conservaron los typos a propósito** (p. ej. `Serigafía`, `Seigrafía`): el
  proveedor los manda y el sync debe reconocerlos.
- **Se quitó la contaminación de componentes**: variantes tipo
  "Bolígrafo: Serigrafía" o "Serigrafía en Vidrio" — quedan cubiertas por la
  forma limpia "Serigrafía".
- Se quitaron parentéticos ("(se ilumina el logo)"), puntuación final y notas
  de más de 5 palabras.
- Dedup por forma normalizada (sin acentos, minúsculas).

La lista de aliases es un **punto de partida**, no exhaustiva. Por diseño (ver
abajo), cualquier valor crudo que un proveedor mande y no esté en estas aliases
se **marca para revisión** y se agrega manualmente desde Odoo (campo `x_aliases`).

### Aliases agregadas tras el dry-run de derivación (2026-06-13)

El dry-run de `scripts/derive_tecnicas.py` reveló 2 variantes crudas frecuentes
sin alias. Se agregaron al seed (y se propagaron a Odoo):

- `bajo_relieve`: + `Grabado en bajo relieve` (resolvía casos PARTIAL de combos
  tipo "Grabado en bajo relieve-Grabado Láser-Serigrafía").
- `doming`: + `Goteado en Resina` (resolvía los casos NONE "Goteado en Resina").
- `sandblast`: + `Grabado en Arena` (el alias previo "Grabado Arena" no matcheaba
  por la "en"; resolvía ~14 casos PARTIAL de combos con "Grabado en Arena").

## Cobertura al momento de derivar

- ~98.6% de los productos con valor mapean automático a una o más canónicas.
- 26 valores crudos (~61 productos) son notas a mano por componente de kit
  (p. ej. "Serigrafía en Power Bank / Grabado Espejo en Bolígrafo") → asignación
  manual pendiente (decisión diferida a F5).
- 2 valores (~24 productos) son nulos (`N/A`, `S/Metodo`) → técnica vacía.

## Mapeo de columnas → modelo

| CSV | Campo Odoo | Nota |
|---|---|---|
| code | x_code | llave estable, requerido |
| nombre | x_name | display |
| x_aliases | x_aliases | variantes crudas, separadas por ` \| ` |
| x_orden | x_orden | secuencia de despliegue (10,20,...) |
| — | x_activa | se fija en True al cargar |
| — | x_descripcion | vacío; se llena después para el sitio |

## No es una migración de una sola vez

`x_tecnica_impresion` lo sobreescribe el sync de proveedores. Por eso este mapeo
**no se aplica una vez y se olvida**: la tabla de aliases es la transformación
**permanente** que el sync aplica en cada actualización (raw → canónica). Valores
nuevos no reconocidos se marcan, no se descartan.

## Decisiones pendientes (F5)

- Asignación de los 26 valores multi-componente.
- Regla para elegir la técnica "default" (`x_tecnica_default_id`) en combos.
- Confirmar las 4 técnicas raras de 1 producto.
