# Motor de cotización — matriz de costos → línea de cotización

> Spec central del "matching" entre lo que pide el cliente (técnica, cantidad,
> tintas, área) y `x_costo_personalizacion`. La usan DOS consumidores:
> 1. **Server Action manual** (Fase 3, este doc) — botón/wizard que un vendedor
>    humano usa en Odoo mientras arma una cotización a mano.
> 2. **Tool `create_quote_draft` del agente AI** (Fase 4-6,
>    `specs/ai-agent-spec.md`) — mismo algoritmo, disparado por conversación de
>    WhatsApp en vez de un clic. Reutiliza esta lógica, no la reimplementa.
>
> Diseño 2026-08-06. Contexto: `specs/data-model.md` (`x_costo_personalizacion`,
> servicios de personalización), `docs/decisions` D7 (técnicas como lista plana,
> sin atributos ricos — por eso `x_alcance_producto` es texto libre y no hay
> matching automático producto↔categoría).

## 1. Disparador

Botón **"Agregar personalización"** en la línea de producto de una cotización
en borrador (`sale.order` estado `draft`/`sent`). Abre un wizard (modelo
transitorio, ver §3) precargado con datos de esa línea.

## 2. Algoritmo de matching (el corazón del motor)

Entradas: `product_id` (de la línea clickeada), `tecnica_id`, `qty`, `tintas`,
`posiciones`, `area_cm2` (si la técnica la usa).

```
1. proveedor_id = product.supplierinfo del product_id con menor `sequence`
   (mismo criterio que usa Compras para elegir proveedor preferido).
   Si el producto no tiene supplierinfo → ir directo a HITL (paso 5),
   no hay forma de saber qué tabla de costos aplica.

2. candidatos = search(x_costo_personalizacion, domain=[
     ('x_tecnica_id', '=', tecnica_id),
     ('x_proveedor_id', '=', proveedor_id),
     ('x_activa', '=', True),
     ('x_qty_from', '<=', qty),
     '|', ('x_qty_to', '>=', qty), ('x_qty_to', '=', False),
     ('x_tintas', '=', tintas),   # o ignorar si x_escala_por_tinta permite otro conteo
   ])
   + filtrar por área si la técnica la usa (area_cm2 dentro de
     x_area_from_cm2–x_area_to_cm2, o sin filtro si la fila no tiene área)

3. Si len(candidatos) == 0 → HITL (paso 5)

4. Si len(candidatos) == 1 → auto-poblar (paso 6)

5. Si len(candidatos) > 1 → difieren solo en x_alcance_producto (categoría).
   El wizard muestra la lista de x_alcance_producto + costo de cada candidato
   para que el vendedor elija 1 con un clic (decisión 2026-08-06: NO se manda
   a aprobación humana solo por esto — es casi automático, ya está
   parametrizado, solo falta 1 dato que el humano sabe de un vistazo:
   "esto que estoy cotizando es una bolsa, no un bolígrafo").
   → una vez elegido, continúa como paso 6 con ese candidato.

6. costo_final = candidato.x_costo_unit
   si candidato.x_escala_por_tinta: costo_final *= tintas
   si candidato.x_unidad_cobro == 'pieza': qty_linea = qty; precio_linea = costo_final
   si candidato.x_unidad_cobro == 'lote':  qty_linea = 1;   precio_linea = costo_final
   (¡el punto crítico! con 'lote' NO se multiplica por qty — ver
   analysis/costos-personalizacion/COSTOS_INN_20260805.md, INN cobra el lote
   completo fijo, no por pieza)

7. servicio_product_id = product.template donde x_tecnica_servicio_id = tecnica_id
   (uno de los 20 ya creados, Fase 3 anterior)
```

## 3. Wizard — modelo transitorio nuevo

`x_wizard_personalizacion` (crear con checkbox "Modelo transitorio" marcado,
vía Ajustes → Técnico → igual que los modelos anteriores — NO Studio, para
conservar nombre plano `x_`, ver lección documentada en
`docs/guia-creacion-servicios-personalizacion.md`).

| Campo | Tipo | Notas |
|---|---|---|
| `x_sale_order_line_id` | many2one → `sale.order.line` | La línea de producto sobre la que se agrega personalización |
| `x_tecnica_id` | many2one → `x_tecnica_personalizacion` | Precargado con `product_id.x_tecnica_default_id`; dominio limitado a `x_tecnicas_compatibles_ids` del producto |
| `x_qty` | integer | Precargado con la cantidad de la línea |
| `x_tintas` | integer, default 1 | |
| `x_posiciones` | integer, default 1 | |
| `x_area_cm2` | float, opcional | Solo relevante si la técnica usa área (mostrar/ocultar en la vista según técnica elegida) |
| `x_candidato_elegido_id` | many2one → `x_costo_personalizacion`, opcional | Se llena solo si hubo ambigüedad (§2 paso 5) y el vendedor eligió uno de la lista |

## 4. Resultado sobre la cotización

- Si auto-pobló o el vendedor eligió candidato: crea/actualiza `sale.order.line`
  bajo la sección "Personalización" (crea las 2 secciones — "Producto" /
  "Personalización" — si la cotización no las tiene), `product_id` = servicio
  correspondiente, `product_uom_qty`/`price_unit` según §2 paso 6.
  `sale.order.x_customization_cost_source = 'parametrized'`.
- Si 0 candidatos: crea `x_approval_request` (modelo ya existe, ver
  `specs/data-model.md`) con `context_json` = producto/técnica/qty/tintas/área
  pedidos, `sale.order.x_requires_human_approval = True`,
  `x_customization_cost_source = 'manually_approved'` (queda pendiente hasta
  que un humano responda la solicitud). El wizard cierra con aviso claro de
  que se mandó a aprobación, NO con un precio inventado.

## 5. Fuera de alcance de esta pieza (deliberado)

- Matching automático de `x_alcance_producto` (texto libre) contra el producto
  específico — se resuelve con 1 clic del vendedor (§2 paso 5), no con NLP o
  reglas de texto. Evita sobre-ingeniería (mismo criterio que D7).
- Reordenar/mezclar secciones si la cotización ya tiene líneas fuera de
  "Producto"/"Personalización" (ej. un vendedor que agregó una nota manual) —
  el Server Action solo garantiza que sus propias líneas caigan en la sección
  correcta, no reorganiza lo que ya había.

## 6. Estado de implementación (✓ probado en STAGING 2026-08-08)

Implementado y probado end-to-end contra `ODOO_TEST_URL` (admin XML-RPC).
**Pendiente de replicar a producción** (espera visto bueno). Artefactos versionados:
`odoo-extensions/server-actions/agregar_personalizacion.py` (Aplicar) y
`.../abrir_wizard_personalizacion.py` (abridor). Guía de replicación:
`docs/guia-motor-cotizacion.md`. Modelos/campos: `odoo-extensions/studio-fields.yaml`
(status `staging`).

**Pruebas (§2 casos):** (a) 1 candidato → auto-pobla; (b) N candidatos → UserError
lista los alcances y el vendedor elige `x_candidato_elegido_id`; (c) 0 candidatos →
crea `x_approval_request` y NO inventa precio. Idempotencia: re-ejecutar sobre la
misma línea actualiza (no duplica), vía `sale.order.line.x_source_line_id`.

### Correcciones a esta spec (verificadas contra datos reales)

1. **`x_qty_to == 0` = "sin límite"** (no `False`/null como decía §2 paso 2). El
   dominio real es `'|', ('x_qty_to','=',0), ('x_qty_to','>=',qty)`.
2. **Filtro de tintas**: no se filtra en el dominio (depende de `x_escala_por_tinta`);
   se filtra en Python: se conserva la fila si `x_escala_por_tinta` **o**
   `x_tintas == tintas`.
3. **Semántica de área** cuando el wizard no la especifica (`area=0`): matchea filas
   cuyo rango inicia en 0 (`x_area_from_cm2 == 0`) y excluye las de área mínima > 0
   (ej. "Bolsas >603 cm²"). Si dos filas `[0, X]` compiten → cae al caso N (elegir).
4. **`x_approval_request` es modelo manual → sus campos llevan prefijo `x_`**
   (`x_sale_order_id`, `x_reason`, `x_context_json`, `x_status`, ...). Los nombres sin
   prefijo de `specs/data-model.md` NO son creables en un modelo custom manual.
5. **Prerequisitos que no existían** y se crearon en staging: el modelo
   `x_approval_request` y los campos `sale.order.x_requires_human_approval /
   x_approval_request_id / x_customization_cost_source`.
6. **Precio de la línea = costo de `x_costo_personalizacion`** (§2 paso 6, sin markup
   adicional sobre la personalización). Si se quiere margen sobre personalización,
   es una decisión aparte — hoy se factura al costo parametrizado.

### Disparador (§1) — realidad de Odoo 19

El botón **por línea** de la spec §1 no es posible solo por API: en Odoo 19 el
`order_line` usa el widget OWL `sol_o2m` (sin `<list>`/`<tree>` en el arch donde
inyectar un botón de fila). Se implementó un botón de **encabezado** "Agregar
personalización" (robusto, versión-estable) que abre el wizard precargando la línea
cuando la cotización tiene una sola línea de producto; con varias, el vendedor elige
la línea en el wizard. El botón por línea exacto de la spec puede añadirse en
**Studio** (que sí se engancha al widget) si se prefiere esa UX.
