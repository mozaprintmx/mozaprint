# Changelog técnico — Mozaprint

> Historial de cambios significativos al sistema. Una entrada por cambio relevante.

---

## 2026-08-07 · perf (v31) — /shop de 5,041 KB a 913 KB: imágenes de categoría optimizadas

**Tipo**: `perf` (datos en Odoo) — 41 registros de `product.public.category` reescritos.
NO se tocó ninguna vista, snippet ni configuración del sitio.

**Síntoma reportado**: el submenú de categorías de la tienda cargaba muy lento y arrastraba
al sitio entero.

**Diagnóstico** (medido contra producción, no supuesto):

- El bloque es `o_wsale_categories_filmstrip`, la tira de categorías **nativa de
  `website_sale`** — no un snippet pegado a mano. Se renderiza sola desde
  `product.public.category`, así que una actualización de Odoo no la borra.
- El filmstrip **no sirve las imágenes por `/web/image/`**: las incrusta en el HTML de
  `/shop` como `data:image` en `style="background-image:url(...)"`, una por categoría raíz.
  Al vivir dentro del HTML no se cachean, se re-descargan en cada visita, no admiten
  lazy-load y bloquean el render. Base64 agrega además ~33%.
- **Odoo NO redimensiona `image_128` al escribir `image_1920` por API**: la deja byte a byte
  idéntica (verificado leyendo de vuelta después de escribir). Las únicas categorías que
  tenían miniatura real eran las subidas por el editor web. Conclusión operativa: **el peso
  de `/shop` es la suma de los `image_1920` × 4/3**, y el único control es escribirlas ya
  pequeñas.
- Punto de partida: `/shop` = 5,041 KB de HTML, de los cuales **4,598 KB (91%)** eran las 38
  miniaturas, a **121 KB de promedio** cada una (la peor, `OFICINA`, 389 KB).

**Resultado**: `/shop` **5,041 KB → 913 KB (−82%)**; las miniaturas **4,598 → 470 KB (−90%)**,
de 121 KB a 12 KB de promedio. Las 41 categorías con imagen quedaron en WebP 256 px @ q82.

Los 256 px salieron de calibrar localmente sobre los originales: el filmstrip dibuja fichas de
~128 px, así que 256 da nitidez 2× en retina al mínimo costo (128 px daría 603 KB pero sin
margen; 512 px daba 1,893 KB). Los 41 originales quedaron respaldados en
`backups/category_images_20260807/` (gitignored, 9.3 MB) — es la fuente de todo re-encodado,
para no comprimir sobre comprimido en corridas sucesivas.

**Permisos**: al **usuario técnico de la API** le faltaba escritura sobre
`product.public.category` (ACL de `website_sale`: lectura a cualquier usuario interno,
escritura a Administrador de Ventas); se le concedió el grupo. No es el usuario del operador.
Nota operativa: **todas las escrituras de los scripts quedan registradas a nombre de esa
cuenta**, no de quien ejecuta. Detalle de la cuenta en `analysis/` (gitignored).

### Impacto en repo

- `scripts/optimize_category_images.py` (nuevo): dry-run por defecto, `--apply`,
  `--only-broken`, `--ids`, `--max-px`, `--quality`. Respalda originales, re-encoda siempre
  desde el respaldo, verifica leyendo de vuelta. Idempotente byte a byte.
- `scripts/rollback_category_images.py` (nuevo): restaura `image_1920` desde el respaldo.
- `requirements.txt`: `Pillow>=11.0`.
- `.gitignore`: `reports/optimize_category_images_*`.
- `docs/roadmap.md`: Fase 9, "Optimizar Core Web Vitals" avanzado.

### Pendientes detectados (no abordados aquí)

- **347 de 388 categorías siguen sin imagen** y el árbol trae deuda del sync: duplicados por
  acento (`TECNOLOGIA`/`TECNOLOGÍA`, `TEXTIL`/`TEXTILES`, `FUTBOL`/`FÚTBOL`,
  `ECOLÓGICA`/`ECOLÓGICOS`), categorías con nombre vacío (ids 359, 288, 375, 396) y ~30 con
  cero productos. Conviene consolidar ANTES de generar imágenes nuevas.
- El API key no puede leer ni escribir `ir.ui.view` / `website.page` (403), así que cualquier
  cambio de plantilla sigue siendo manual en el editor web.

---

## 2026-08-06 · design (v30) — Motor de cotización: diseño del Server Action de auto-populado

**Tipo**: `design` (spec nueva) — NADA implementado todavía en Odoo

**Descripción**: diseño completo del Server Action de Fase 3 en `specs/motor-cotizacion.md`
(spec nueva, referenciada desde `CLAUDE.md`). Reutilizable después por el tool `create_quote_draft`
del agente AI (Fase 4-6) — mismo algoritmo, disparado por WhatsApp en vez de un botón.

- **Disparador**: botón "Agregar personalización" en la línea de producto → wizard.
- **Wizard nuevo**: `x_wizard_personalizacion` (modelo transitorio, campos en la spec).
- **Algoritmo**: resuelve proveedor por `product.supplierinfo` (menor `sequence`), busca en
  `x_costo_personalizacion` por técnica+proveedor+cantidad+área+tintas, respeta
  `x_unidad_cobro` (pieza vs lote — NO multiplicar por cantidad si es lote) y
  `x_escala_por_tinta`.
- **Ambigüedad por categoría** (varias filas difieren solo en `x_alcance_producto`, común en
  PO): el vendedor elige de una lista corta con 1 clic — decisión 2026-08-06, se prefirió esto
  sobre mandar a aprobación humana (ya está parametrizado, solo falta 1 dato que el humano
  reconoce a simple vista).
- **Sin match**: crea `x_approval_request` + `sale.order.x_requires_human_approval=True` — nunca
  inventa un precio (regla de `CLAUDE.md`).
- Sandbox de Server Actions no bloquea nada de esto (es solo ORM, sin librerías externas).

### Impacto en repo

- `specs/motor-cotizacion.md` (nuevo).
- `CLAUDE.md`: referencia agregada.
- `docs/roadmap.md`: tarea en progreso (diseño listo, falta implementar).

---

## 2026-08-06 · design (v29) — Quote Subsections: convención de secciones decidida

**Tipo**: `design` (specs) — NADA que crear en Odoo, es una feature nativa de Sales

**Descripción**: siguiente pieza de Fase 3. "Quote Subsections" = feature nativa de Odoo Sales
("Sections and Notes"): líneas `sale.order.line` con `display_type='line_section'`, sin producto
ni precio propio, que agrupan visualmente las demás líneas con subtotal automático. No requiere
campos custom ni Studio.

- **Convención decidida**: 2 secciones fijas por cotización — "Producto" (líneas de producto
  físico) y "Personalización" (líneas de los 20 servicios de la Fase 3 anterior) — en vez de una
  sección por cada producto distinto. Documentado en `specs/ai-agent-spec.md`, tool
  `create_quote_draft`.
- **Confirmado por Juan Carlos en la instancia real (2026-08-06)**: el botón "Agregar una
  sección" ya está disponible en las cotizaciones, sin toggle que activar — coincide con la
  documentación oficial. Tarea de Fase 3 cerrada.

### Impacto en repo

- `specs/ai-agent-spec.md`: nueva sección "Estructura de líneas (secciones)" en `create_quote_draft`.
- `docs/roadmap.md`: tarea marcada en progreso, pendiente confirmación de UI.

### Fuentes

- [Create quotations — Odoo 19.0 documentation](https://www.odoo.com/documentation/19.0/applications/sales/sales/sales_quotations/create_quotations.html)

---

## 2026-08-06 · odoo (v28) — Servicios de personalización: 20 product.template creados

**Tipo**: `odoo` (datos) — `scripts/seed_servicios_personalizacion.py --apply` ejecutado

**Descripción**: con los 2 prerrequisitos de v27 listos (categoría id 435, campos
`x_es_servicio_personalizacion`/`x_tecnica_servicio_id` confirmados sin `x_studio_`), se corrió
el seed contra Odoo real. **Los 20 `product.template` de servicio existen**, uno por cada técnica
activa de `x_tecnica_personalizacion` (type=service, categ_id=435, x_tecnica_servicio_id poblado).

### Impacto en repo

- `specs/data-model.md`: sección "Servicios de personalización" marcada como poblada.
- `docs/roadmap.md`: tarea de Fase 3 "Modelar servicios de personalización" completada.

---

## 2026-08-06 · odoo (v27) — Servicios de personalización: setup previo (categoría + 2 campos)

**Tipo**: `odoo` (config) — ambos prerrequisitos listos (categoría por API, campos manual)

**Descripción**: los 2 prerrequisitos en Odoo para `seed_servicios_personalizacion.py`, hechos
lo más por API posible (script temporal, no permanente).

### PASO 1 — categoría ✓ (por API)

- Se investigaron las categorías de productos físicos: **todas** usan la misma cuenta de ingresos
  `id=104` ("Sales and/or services taxed at the general rate", que cubre servicios) y gasto `id=121`.
- Creada `product.category` **"Servicios de Personalización" (id=435)** copiando esas cuentas
  (income=104, expense=121), verificado. **El IVA NO es campo de categoría** (`product.category`
  solo tiene cuentas, no impuesto de cliente) → el 16% lo hereda el producto del default de la
  compañía; el `seed_servicios` no setea `taxes_id`.

### PASO 2 — campos en product.template ✓ (manual, tras bloqueo de API)

- Crear vía API `ir.model.fields` dio **403 AccessError** (*"permitido para: Access Rights"*): el
  usuario API (Rosy Ponce) no está en el grupo `Access Rights` (`base.group_erp_manager`). No se
  elevó el usuario de integración (decisión de seguridad) → los creó **Juan Carlos manualmente**
  vía Ajustes → Técnico → Estructura de BD.
- **Nombres técnicos REALES (verificados por `fields_get`)**: `x_es_servicio_personalizacion`
  (boolean) y `x_tecnica_servicio_id` (m2o a `x_tecnica_personalizacion`) — **SIN** prefijo
  `x_studio_`.
- **Lección (corrige la guía y `.claude/rules/data-model.md`)**: crear campos vía **Técnico →
  Estructura de BD** conserva el nombre `x_` que escribes; **solo Studio UI** fuerza `x_studio_`.
  El script/guía originales asumían `x_studio_` para `product.template` (modelo estándar) — falso:
  lo que fuerza el prefijo es Studio, no que el modelo sea estándar (igual que `x_costo_personalizacion`,
  también plano vía Técnico). Se revirtieron script/specs a los nombres reales.

### Impacto en repo

- `scripts/seed_servicios_personalizacion.py`: usa los nombres reales `x_es_servicio_personalizacion`
  / `x_tecnica_servicio_id` (se quitó el `x_studio_` erróneo).
- `specs/data-model.md` + `odoo-extensions/studio-fields.yaml`: 2 campos `status: created`
  (2026-08-06), nombres reales; categoría documentada (id 435).
- `docs/guia-creacion-servicios-personalizacion.md` y `.claude/rules/data-model.md`: corregida la
  regla del prefijo (`x_studio_` lo fuerza Studio, no Técnico).
- `docs/roadmap.md`: prerrequisitos listos; falta correr el seed (siguiente paso).

---

## 2026-08-05 · design + scripts (v26) — Servicios de personalización: 1 product.template por técnica

**Tipo**: `design` (specs) + `scripts` (nuevo loader) — NADA creado todavía en Odoo

**Descripción**: siguiente pieza de Fase 3. Decisión de granularidad: **1 `product.template`
type=service por técnica** (20 hoy, no un servicio genérico ni uno por técnica×proveedor) —
mejor reporte de ingresos/margen por técnica y encaja con `x_approval_request.approved_servicio_id`.
El proveedor no es eje del catálogo de servicios, sigue viviendo solo en `x_costo_personalizacion`.

- 2 campos nuevos planificados en `product.template`: `x_es_servicio_personalizacion` (bool) y
  `x_tecnica_servicio_id` (m2o a `x_tecnica_personalizacion`, llave de idempotencia). (Nota: el
  diseño original asumió prefijo `x_studio_`; **resultó falso** al crearlos vía Técnico — ver v27.)
- Categoría de producto dedicada "Servicios de Personalización" (a crear por Juan Carlos) para
  heredar cuenta de ingresos e IVA por default, sin hardcodear cuentas contables en el script.
- `scripts/seed_servicios_personalizacion.py` (dry-run/--apply, idempotente por
  `x_tecnica_servicio_id`): lee el catálogo de técnicas **en vivo** de Odoo (no CSV) —
  si se agregan técnicas después, re-correr solo crea las nuevas. Validado offline con las 20
  técnicas de `data/tecnicas_seed.csv` (20 nombres únicos generados correctamente).
- **Limitación documentada**: `standard_price` no puede representar el costo real (varía por
  fila de `x_costo_personalizacion`) — margen de personalización se calcula aparte, no vía
  contabilidad de costos nativa de Odoo.

### Impacto en repo

- `specs/data-model.md`: nueva sección "Servicios de personalización" + 2 campos planificados.
- `odoo-extensions/studio-fields.yaml`: 2 campos nuevos en `product.template`.
- `docs/guia-creacion-servicios-personalizacion.md` (nuevo).
- `scripts/seed_servicios_personalizacion.py` (nuevo).

---

## 2026-08-05 · scripts + data (v25) — seed_costos.py + costos_seed.csv (INN+PO, 127 filas)

**Tipo**: `scripts` (nuevo loader) + `data` (seed gitignored, dato de proveedor)

**Descripción**: `scripts/seed_costos.py` (dry-run/--apply, idempotente, mismo patrón que
`seed_tecnicas.py`) para cargar `x_costo_personalizacion` desde
`analysis/costos-personalizacion/costos_seed.csv` (127 filas: 47 INN + 80 PO, gitignored —
dato comercial de proveedor, ver `costos_seed.md` para procedencia y filas marcadas para
revisión).

- Idempotencia por llave compuesta (técnica+proveedor+alcance+qty+área+tintas), no por código
  único — no existe un "código" natural para una fila de costo.
- Resuelve `tecnica_code → x_tecnica_id` (por `x_code`) y `proveedor_nombre → x_proveedor_id`
  (`res.partner` por **`name` EXACTO (`=`)**, alineado con `get_or_create_supplier` del sync;
  **aborta si no matchea exactamente 1** — evita adivinar el proveedor correcto).
- `x_name` se arma automáticamente (proveedor + técnica + alcance + rango de cantidad), no se
  captura a mano en el CSV.
- **Ejecutado y validado contra Odoo real (2026-08-05)**. El dry-run local destapó que el
  match de proveedor original (`name ilike`) era **ambiguo**: hay partners duplicados por
  proveedor (ej. `INNOVATIONLINE` id 82 vs `(InnovationLine) INNOVA PROMOCIONALES…` id 32;
  `PROMOOPCION` id 11 vs `(PROMOOPCION) Promocionales de Occidente…` id 8), y ambos contienen
  el token → `ilike` nunca resolvía a 1. **Corrección (opción A)**: match exacto `name =` +
  `proveedor_nombre` del CSV a los nombres canónicos (`INNOVATIONLINE`/`PROMOOPCION`, los que
  usa el `supplierinfo` del sync). Tras la corrección, `--apply` creó **127 registros**
  (47 INN → partner 82, 80 PO → partner 11), 0 errores; validado (total, distribución por
  técnica/proveedor, spot-check de valores contra el CSV) y **re-dry-run idempotente
  (0 crear / 127 actualizar)** — confirma que la llave natural se guardó bien.
- Deuda anotada (aparte): los partners de proveedor **duplicados** (id 32/8, con el nombre
  legal) son higiene pendiente; el costo se ancló al partner canónico del sync (82/11).

### Impacto en repo

- `scripts/seed_costos.py` (nuevo; match de proveedor por `name =`).
- `analysis/costos-personalizacion/costos_seed.csv` + `costos_seed.md` (nuevos, gitignored;
  `proveedor_nombre` = nombres canónicos exactos).

---

## 2026-08-05 · odoo (v24) — x_costo_personalizacion creado en producción

**Tipo**: `odoo` (creación de modelo/campos, sin datos aún)

**Descripción**: Juan Carlos creó el modelo `x_costo_personalizacion` y sus 17 campos en
Odoo vía Ajustes → Técnico → Estructura de BD, siguiendo `docs/guia-creacion-x_costo_personalizacion.md`
(diseño de v23). Nombres técnicos confirmados con prefijo `x_` (no `x_studio_`).

- Los dos many2one requeridos (`x_tecnica_id`, `x_proveedor_id`) dispararon el error de
  validación de Odoo "campo m2o obligatorio con política 'set null'" — se corrigieron a
  `ondelete='restrict'` (evita borrado en cascada silencioso de costos si se borra una
  técnica o proveedor).
- **Pendiente de confirmar**: `x_name` quedó sin el checkbox "Requerido" marcado (la spec
  pide `required=True`) — falta corregirlo o confirmar que ya se hizo.
- **Pendiente**: configurar permisos del grupo "Ventas/Usuario: todos los documentos"
  (mismo grupo que `x_tecnica_personalizacion`) — sin esto el equipo de ventas no puede
  consultar la tabla al cotizar.
- Modelo sin datos todavía. Siguiente pieza: CSV seed + `scripts/seed_costos.py`.

### Impacto en repo

- `odoo-extensions/studio-fields.yaml`: v0.6.0 → v0.6.1, 17 campos `status: planned` → `created`.
- `specs/data-model.md`: sección `x_costo_personalizacion` marcada como creada, con las 2
  pendientes anotadas.

---

## 2026-08-05 · design (v23) — x_costo_personalizacion: diseño final (Fase 3, arranque)

**Tipo**: `design` (solo specs/docs; NADA se creó todavía en Odoo)

**Descripción**: arranque de Fase 3 (motor de cotización). Se leyeron las listas de costos
reales de personalización de INN (`MANUAL-SI-OK.pdf`, 10 págs.) y PO (4 tabuladores PDF) y se
descubrió que el diseño original de `x_costo_personalizacion` (specs desde Fase 0) no alcanza:
la unidad de cobro (por pieza vs. por lote completo) y si el costo escala por tinta son
propiedades de la fila técnica+proveedor, no de la técnica sola. Ej.: INN cobra serigrafía como
lote fijo (1-1000 pzas) por tinta; PO cobra la misma técnica genuinamente por pieza con curva de
cantidad de hasta 10 escalones.

### Cambios al modelo

`x_costo_personalizacion` pasa de 12 a 16 campos. Nuevos: `x_alcance_producto` (categoría/SKU
en texto libre), `x_unidad_cobro` (pieza/lote — crítico para no sobrecotizar), `x_escala_por_tinta`
(bool). `area_max_cm2` se parte en `x_area_from_cm2`/`x_area_to_cm2` (tramo, no tope único). Todos
los campos se renombran con prefijo `x_` (el diseño original no lo tenía, inconsistente con
`x_tecnica_personalizacion`). Se decide crear el modelo vía **Ajustes → Técnico → Estructura de
BD** (no Studio visual) para controlar el nombre técnico exacto de cada campo — mismo resultado
que se verificó para `x_tecnica_personalizacion` (D8).

### Datos de proveedor recopilados (gitignored, NO en repo público)

- `analysis/costos-personalizacion/COSTOS_INN_20260805.md` — transcripción completa (9 técnicas).
- `analysis/costos-personalizacion/COSTOS_PO_20260805.md` — transcripción completa (4 técnicas)
  + comparación INN vs PO por técnica.
- `analysis/costos-personalizacion/fuentes/` — PDFs originales (INN, PO).

### Pendiente

- 4P no tiene lista documentada — se construirá empírico desde histórico de WhatsApp/cotizaciones
  (pieza separada, no bloquea la creación del modelo con lo que ya se sabe de INN+PO).
- Crear el modelo y sus 16 campos en Odoo (guía paso a paso, siguiente pieza).
- CSV seed + script loader idempotente (dry-run/--apply, patrón `seed_tecnicas.py`).

### Impacto en repo

- `specs/data-model.md`: sección `x_costo_personalizacion` reescrita.
- `odoo-extensions/studio-fields.yaml`: v0.5.0 → v0.6.0, 16 campos con prefijo `x_`.
- `analysis/costos-personalizacion/` (nuevo, gitignored): transcripciones + PDFs fuente.

---

## 2026-08-05 · feat (v22) — Limpieza de product tags (material/técnicas/huérfanos)

**Tipo**: `feat` (script de repo) + limpieza de datos en Odoo

**Descripción**: tras poner en producción el fix del sync que deja de generar tags de
material (cambio en la copia de análisis, gitignored), se depuran los tags que ya no se
quieren. Nuevo `scripts/cleanup_tags.py` (JSON-2, dry-run por defecto) que borra por
REGLA: elimina todo `product.tag` cuyo nombre normalizado NO esté en una **lista blanca**
de 9 tags que el sync regenera (proveedor 4P/PO/INN + gama Normal/Promo/Unico/Outlet/
Economico/Premium).

### Resultado (aplicado en Odoo)

- **155 → 9 tags**: borrados **146** (material + técnicas coladas + basura + 11 huérfanos),
  0 fallidos. Conservados exactamente los 9 de la lista blanca.
- Solo `product.tag` (unlink); productos y variantes intactos (el m2m se desasocia solo).

### Salvaguardas del script

- `--apply` exige `--confirmar-fix-en-produccion` (borrar antes del fix haría que el sync
  regenere el material).
- Aborta si la lista blanca no matchea Odoo (grafía cambiada) o si el nº a borrar supera
  un umbral (default 160). Imprime ambas listas antes de borrar; borra por lotes
  (huérfanos primero) con aislamiento de fallos por-tag. Prohibido tocar
  product.template/product/attribute*.

### Impacto en repo

- `scripts/cleanup_tags.py` (nuevo). `.gitignore`: `reports/cleanup_tags_*`.
- Canario: si tras la próxima corrida del sync reaparece un tag de material, el fix no
  quedó en producción.

---

## 2026-07-09 · audit (v21) — Product Tags: estado en Odoo + escritura del sync

**Tipo**: `audit` (solo lectura; no modifica Odoo, código ni sync)

**Descripción**: auditoría previa a agregar tags de familia de color. Nuevo script
`scripts/audit_tags.py` (JSON-2, read-only, sin PII: solo nombres de tag y conteos)
que fotografía `product.tag`: campos reales, uso por templates/variantes, huérfanos,
duplicados por nombre normalizado, prefijos y colisiones con las 14 familias.

### Hallazgos clave

- Campos reales: `product.tag.color` es **char con hex** (no índice de paleta);
  `visible_to_customers` (bool) controla visibilidad al cliente.
- 154 tags · 9 huérfanos · 11 grupos duplicados por acento/case (`Poliéster`/`Poliester`/
  `Políester`, `Cartón`/`Carton`, …) · **0 colisiones** con nombres de familia.
- **Sync (crítico)**: escribe los tags de **template** con `[(6,0,[material])]` = REPLACE
  TOTAL → pisaría cualquier tag de color-familia. El de **variante** es read-modify-write
  (aditivo). `get_or_create_tag` no normaliza (dedup exacto) → misma fragmentación que Color.
- **Convivencia**: para meter color en `product_tag_ids` hay que arreglar primero el write
  de template del sync a read-modify-write (o usar un mecanismo dedicado fuera de la bolsa
  compartida). Detalle en `analysis/supplier-sync/AUDITORIA_TAGS.md` (gitignored).

### Impacto en repo

- `scripts/audit_tags.py` (nuevo). `.gitignore`: `reports/audit_tags_*`.
- Reportes y análisis del sync viven en `reports/` y `analysis/` (gitignored).

---

## 2026-07-09 · feat + revert (v20) — Color (familia): motor compartido, derivación y rollback

**Tipo**: `feat` (código conservado) + `revert` (efecto en Odoo revertido)

**Qué se hizo y por qué se revirtió**: se implementó un atributo `no_variant`
**"Color (familia)"** para un filtro limpio de color en `/shop` (agrupa los 204 valores
crudos del atributo Color en 14 familias). Se derivó y aplicó sobre 5290 templates. Se
**revirtió en Odoo** porque un atributo `no_variant` se renderiza como **selector
seleccionable en la ficha de producto** (comportamiento nativo), duplicando el selector
del Color REAL. El **código se conserva** (la lógica es correcta; el problema fue el
render del `no_variant`, no la derivación) para un futuro filtro de `/shop` bien montado.

### Refactor — `scripts/colores_engine.py` (motor compartido)

- Se extrajo `normalize()` / `resolve()` + carga del seed de `derive_colores.py` a
  `colores_engine.py`. `derive_colores.py` ahora lo importa **sin cambiar comportamiento**
  (swatch sigue en 97.36%; verificado con `--self-check`).
- El motor expone además `familia(name) -> str | None`, **más laxo** que `resolve()`:
  agrupa por color base/lex dominante aunque el modificador sea desconocido
  (`ROJO JASPEADO`→Rojo), y trata `tricolor`/`mexico`/`arcoiris`/`/`/`con` como Multicolor.
  Cobertura de familia: **98.25% de prod-hits, 26 valores sin familia**.

### Scripts nuevos

- `scripts/derive_color_familia.py`: deriva la línea 'Color (familia)' por template desde
  sus valores reales de Color. Incremental (`--since`, idempotente), dry-run por defecto,
  `--self-check`, `--published-only`. Guardas: crea el atributo con
  `create_variant='no_variant'` (aborta si difiere); escribe solo
  `product.template.attribute_line_ids` con `(0,0)`/`(1,…)`; nunca toca `product.product`,
  `create_variant`, ni el atributo Color real.
- `scripts/rollback_color_familia.py`: rollback **seguro** del atributo. Guardas duras
  (objetivo debe ser `no_variant`; id ≠ Color real `always`); elimina líneas → valores →
  atributo (o `--archive-only`); tolerante a fallos por-línea. Se usó para revertir
  (5290 líneas + 14 valores + atributo, 0 errores).

### Datos / docs

- `data/colores_seed.csv`: **columna `familia`** por color (+ se restauró el alias
  `blanco ivory` de Hueso perdido en una regeneración). `data/colores_familias.csv`:
  14 familias (name, hex, orden, tipo; Multicolor sin hex). `data/colores_noncolor.md`:
  mapeo material→familia (carton/corcho/madera/periodico→Café, bambú/cebada/caña→Beige,
  coco→Blanco, caoba→Rojo) + estrategia de `familia()`.
- `.gitignore`: `reports/derive_familia_*` y `reports/rollback_familia_*`.

### Auditoría de soporte (analysis/, gitignored)

- Se confirmó que el sync opera por-línea sobre `attribute_line_ids` (solo Color/Talla,
  sin `(5,0,0)`), así que una línea `no_variant` externa **sobreviviría** sus corridas —
  base del diseño incremental + hook. (Auditoría 2 en `AUDITORIA_COLORES.md`.)

---

## 2026-07-06 · feat (v19) — Swatches de color: dump + motor de derivación de html_color

**Tipo**: `feat`
**Descripción**: El sync crea los valores del atributo `Color` por string exacto y
**sin `html_color`** (swatch), así que el swatch es 100% derivado. Se agregan dos
scripts JSON-2 (solo lectura salvo `--apply`) para poblarlo:

- `scripts/dump_color_values.py`: volcado de solo lectura de los 204 valores del
  atributo Color (nombre, html_color, conteo de productos, `name_normalizado`) para
  reconciliar el seed. Salida a `reports/color_values_*` (gitignored).
- `scripts/derive_colores.py`: deriva `html_color` con un motor de reglas
  **base + modificador**. Cascada `resolve()`: LEX → BICOLOR → NON_COLOR → MATERIAL
  → STRIP (talla/género) → BASE+MOD (deltas HLS vía `colorsys`, stdlib) → sin_base.
  Espejo arquitectónico de `derive_tecnicas.py`: `normalize()` idéntica, DRY-RUN por
  defecto, escritura agrupada por hex e idempotente, reporte JSON+MD.

**Insumos** (`data/`): `colores_seed.csv` (30 base + 24 lex curados),
`colores_modifiers.csv` (11 modificadores HLS), `colores_noncolor.md`
(STRIP/NON_COLOR/MATERIAL_APROX + inventario de contaminación del eje Color).

### Cobertura (self-check offline sobre el dump de 204 valores)

- **97.36%** de prod-hits reciben swatch (163/204 valores; 12,482/12,820 prod-hits).
- **41 sin swatch**: 9 `especial` (intencional: transparente/multicolor/bicolor) +
  32 `flag` (contaminación real: `UNICO`, tallas, patrones `TRICOLOR/MEXICO`, basura).
- Afinación: `blanco ivory` agregado como alias de la LEX `Hueso` (rescata el único
  color real que quedaba flagged).

### Seguridad

- **Escribe solo `html_color` de `product.attribute.value`.** Guardas duras que
  abortan ante cualquier otro modelo (`product.product`, `.attribute.line`,
  `product.attribute`) o cualquier clave ≠ `html_color`. Nunca toca `create_variant`
  ni variantes.
- Reportes `reports/derive_colores_*` gitignored (nombres de color + contaminación).
- **Hook post-sync documentado, no cableado**: vars `DERIVE_COLORES_ENABLED/_SCRIPT_PATH/
  _PYTHON_PATH` + snippet de invocación (entorno limpio) para copiar a `analysis/`.

### Diferido (no en esta tarea)

- De-contaminación del eje Color (tallas/basura/patrones que generan variantes bajo
  `create_variant=always`): migración con backup y preservación de SKU/stock/imagen.
  Documentado en `data/colores_noncolor.md`.

---

## 2026-07-06 · decision · patch (v18) — Descripciones con IA: descope de Fase 2, reencuadre SEO dirigido (Fase 9)

**Tipo**: `decision`
**Descripción**: Revisión de la Tarea 2 de Fase 2. La generación **masiva** de
descripciones de producto con IA se **descarta de Fase 2** (no se hace ahora, no
bloquea el cierre de la fase). La idea NO se mata: se **reencuadra** como iniciativa
SEO **dirigida** (targeted) de Fase 9, condicionada a un diagnóstico de Google Search
Console. Detalle y diseño en `decisions/006-descripciones-ia-seo-dirigido.md`.

### Por qué (señal de negocio nueva)

- Adquisición real: clientes que buscan un producto AGOTADO en otros revendedores
  caen en Mozaprint, que comparte catálogo (y la MISMA descripción duplicada) de los
  proveedores INN/4P/PO. Google deprioritiza el contenido duplicado justo en ese
  escenario que hoy trae clientes.
- Pero hoy probablemente nos encuentran por nombre/SKU (title/H1), no por el cuerpo:
  el body prose no es la palanca de mayor leverage.

### Prioridad SEO real (documentada en Fase 9)

1. `title` / meta / H1 únicos por producto. 2. Alternativos/accesorios para linking
interno (conecta con Tarea 3 de Fase 2). 3. schema.org/Product + Open Graph.
4. Descripciones únicas **dirigidas** (no masivas), solo tras diagnóstico GSC.

### Impacto en docs

- `docs/roadmap.md`: Fase 2 marca la tarea de descripciones IA como descartada/diferida;
  Fase 9 gana las 4 palancas priorizadas + descripciones dirigidas + diagnóstico GSC.
- `docs/punto-de-control.md`: descripciones IA salen del alcance de cierre de Fase 2.
- `decisions/006`: ADR con justificación ("buscador de agotados") y diseño si se implementa.
- `specs/integrations.md` + `decisions/002`: coherencia — el caso de uso "generación
  de descripciones" queda como DIRIGIDO (no masivo), sin cambiar la decisión de LLM.

---

## 2026-06-28 · docs · patch (v17) — Reconciliación de documentación + limpieza de filtros /shop

**Tipo**: `docs`
**Descripción**: Tras varias sesiones de trabajo, la documentación del repo quedó
atrasada respecto a la realidad. Se reconcilió a partir de un diagnóstico por
archivo, y se registra un cambio en producción que faltaba documentar.

### Documentación reconciliada

- **Modelo de técnica = creado y poblado** (antes figuraba como "planificado"):
  `x_tecnica_personalizacion` con 20 técnicas, y `x_tecnica_default_id` /
  `x_tecnicas_compatibles_ids` en `product.template` poblados por
  `scripts/derive_tecnicas.py` (~5,203 templates). Actualizados `docs/roadmap.md`
  (Fase 2), `specs/data-model.md` y `odoo-extensions/studio-fields.yaml` (v0.5.0).
- **Specs de API/integración corregidos**: la JSON-2 API devuelve respuestas
  **crudas** (sin `{"result":...}`); `create` usa `vals_list`; usuario API = Rosy
  Ponce; `ODOO_URL = mozaprintmx.odoo.com`. (`specs/api-shapes.md`,
  `specs/integrations.md`, `docs/architecture.md`).
- **README**: árbol de `scripts/` real + carpeta `data/`; historial apunta a este
  changelog.
- **Higiene**: `docs/decisiones-equipo-v1.md` se convirtió en puntero al ADR
  `decisions/004` (fuente única); se contradecía la cuenta "8 vs 20 técnicas"
  (queda 20 en toda la doc de estado).
- **Detalle del sync de proveedores** se mantiene fuera del repo público (vive en
  `analysis/AUDITORIA_SYNC.md`, gitignored); la doc pública queda a alto nivel.

### Cambio en producción (catálogo)

- **Filtros de /shop depurados**: se ocultaron como filtros los atributos que no
  son **Color** ni **Talla** (campo "Visibilidad del filtro de eCommerce"), tras el
  diagnóstico de `scripts/audit_atributos.py` (17 atributos, solo 2 en uso real). El
  /shop público muestra ahora solo Color, Talla y Precio. El filtro por técnica se
  **descartó** (el cliente busca producto, no técnica). No se borraron atributos ni
  valores (limpieza fina queda como backlog opcional).

---

## 2026-06-26 · scripts · patch (v16) — audit_atributos.py: auditoría de atributos para limpiar filtros de /shop

**Tipo**: `scripts`
**Descripción**: Script de **solo lectura** que fotografía los atributos de producto
(`product.attribute`, `product.attribute.value`, `product.template.attribute.line`)
para decidir qué filtros del sidebar de /shop quitar, consolidar o limpiar. No
escribe nada en Odoo. Reutiliza el `OdooClient` JSON-2 y el `.env`.

### `scripts/audit_atributos.py` (nuevo)

- **Por atributo**: nº de valores, nº de productos que lo usan (distinct en las
  líneas de atributo), tipo, modo de variante, visibilidad en web; banderas
  `usado_por_1_producto` / `usado_por_pocos` (≤3) → candidatos a quitar del filtro.
- **Valores huérfanos**: para atributos grandes (>50 valores), desglosa total vs
  en uso vs huérfanos (definidos sin producto) y la cola de valores de 1 producto.
- **Solapados**: señala pares de atributos con nombres similares (por substring o
  primera palabra; solo marca, no asume) como candidatos a consolidar.
- **Top valores** por nº de productos y **resumen accionable** (ELIMINAR /
  CONSOLIDAR / LIMPIAR valores).
- Salida: `reports/audit_atributos_YYYYMMDD.json` + `.md`. Paginado, idempotente,
  manejo de errores por sección, sin PII (solo nombres de atributo/valor y conteos,
  no nombres de producto).

### Hallazgo de la primera corrida (alto nivel)

- 17 atributos, pero solo **3 en uso real** (Color, Talla, Género). 14 son
  candidatos a eliminar/ocultar (7 vacíos heredados + 7 creados para 1 producto).
- `Color` concentra el catálogo (204 valores, ~10 huérfanos + ~40 de 1 producto):
  cola larga depurable.

### `.gitignore`

- `reports/audit_atributos_*` (dato de negocio del catálogo; no va al repo público).

---

## 2026-06-25 · sync · minor (v15) — INN: página más chica (504) + auto-desactivación de sobrantes con tope

**Tipo**: `sync`
**Descripción**: Dos arreglos al sistema de sincronización de proveedores surgidos
al validar el sync real: el de obtención de datos de InnovationLine y la
desactivación de productos descontinuados.

> El código del sync vive en un área de análisis local **no versionada**
> (`analysis/`, gitignored). Esta entrada registra los cambios a alto nivel para
> la trazabilidad del proyecto.

### Cambios

- **Fix de timeouts de InnovationLine (504)**: la API de INN empezó a responder
  `504 Gateway Timeout` al pedir páginas grandes (su backend excede el límite de
  ~29s del gateway). Se redujo el tamaño de página a un valor con margen cómodo,
  de modo que el sync vuelve a traer datos **frescos** de la API en vez de caer al
  respaldo local. Diagnóstico confirmado midiendo la API directamente (páginas
  chicas responden en segundos; las grandes cortan a los 29s).
- **Auto-desactivación de sobrantes con tope de seguridad**: la corrida automática
  ahora **desactiva** los productos que ya no vienen en el catálogo del proveedor,
  pero **solo si son menos del 10%** del total del proveedor en Odoo. Si se supera
  ese tope (señal de un catálogo truncado por una API a medias), **no desactiva** y
  avisa para revisión manual. Antes la corrida automática nunca desactivaba (solo
  avisaba), por lo que los descontinuados se acumulaban; la desactivación solo
  ocurría al correr el flujo interactivo a mano.
  - Umbral configurable; por defecto 10% y activado.
  - Se evalúa aun cuando no haya altas/actualizaciones (un descontinuado sin otros
    cambios igual se desactiva). Los productos se marcan inactivos, no se borran.

### Notas

- Configuración nueva (activación y umbral de la auto-desactivación) documentada
  como variables opcionales con defaults sensatos.
- Validado en producción: corrida real de INN con datos frescos, imágenes AVIF/WEBP
  convertidas, 0 errores de producto y derivación canónica disparada al cierre.

---

## 2026-06-25 · sync · minor (v14) — Endurecimiento del sync: imágenes, backup INN, derivación automática

**Tipo**: `sync`
**Descripción**: Tanda de mejoras de robustez al sistema de sincronización de
proveedores, centradas en que una corrida no se bloquee por causas secundarias
(imágenes) y en automatizar/respaldar pasos que antes eran manuales.

> El código del sync vive en un área de análisis local **no versionada**
> (`analysis/`, gitignored): contiene detalle operativo sensible. Esta entrada
> registra los cambios a alto nivel para la trazabilidad del proyecto.

### Cambios

- **Manejo robusto de imágenes**: ante imágenes que Odoo rechazaba (formato AVIF,
  entre otros), ahora el sync (1) **diagnostica** el problema real de cada imagen
  (formato detectado por contenido, tamaño, tipo de respuesta), (2) **convierte**
  los formatos recuperables (AVIF/WEBP) a uno que Odoo acepta, conservando la
  imagen del producto, y (3) **desacopla** el fallo de imagen del conteo de errores
  de producto. Resultado: una corrida donde solo fallan imágenes termina con 0
  errores de producto y **ya no bloquea la derivación canónica posterior**.
  - Las imágenes genuinamente inválidas (inexistentes, vacías, corruptas) se saltan
    con un aviso detallado, sin reintentar; el resto del producto se sincroniza.
  - El resumen final reporta cuántas imágenes se convirtieron y cuántas se saltaron.
  - Nueva dependencia **opcional** en runtime: Pillow (≥11.3, AVIF/WEBP nativos).
    Si no está instalado, esas imágenes simplemente se saltan (no rompe el sync).
- **Derivación canónica automática post-sync**: al terminar un sync **sin errores**,
  se dispara `scripts/derive_tecnicas.py` de forma incremental para mantener
  actualizados `x_tecnica_default_id` / `x_tecnicas_compatibles_ids` sin paso manual.
  Es un paso independiente: si falla, se avisa pero no afecta al sync.
- **Backup con fecha de InnovationLine**: cada corrida exitosa de la API guarda la
  respuesta cruda como respaldo fechado, y el fallback de lectura pasa a usar **el
  respaldo más reciente** (antes leía un archivo fijo y desactualizado). Incluye
  rotación de respaldos antiguos. Se migró el snapshot manual previo al nuevo esquema.
- **Despliegue asistido análisis → producción**: utilidad que compara por contenido
  los archivos del paquete y, con respaldo previo, copia solo los que cambiaron
  (detección dinámica; evita olvidar archivos al desplegar). Vive en el área no
  versionada.

### Notas

- Configuración nueva (rutas/flags de la derivación automática y del backup de INN)
  documentada como variables opcionales con defaults sensatos.
- Sin cambios en la lógica de técnica/precio/stock/categorías ni en
  `scripts/derive_tecnicas.py` (repo principal).

---

## 2026-06-24 · sync · minor (v13) — INN: técnicas multivalor completas + re-derivación

**Tipo**: `sync`
**Descripción**: El adaptador de InnovationLine en el sistema de sincronización de
proveedores truncaba los productos multi-técnica a una sola técnica. Se corrige para
que conserve todas las técnicas de cada producto, y se re-deriva la técnica canónica
para propagar el cambio a los campos estructurados.

> El código del sync de proveedores vive en un área de análisis local **no
> versionada** (`analysis/`, gitignored): contiene detalle operativo sensible. Esta
> entrada registra el cambio a alto nivel para la trazabilidad del proyecto.

### Cambios

- **Fix de truncación de técnicas (INN)**: los productos con varias técnicas de
  personalización ahora conservan **todas** sus técnicas en el sync, no solo la
  primera. Antes se perdía información de personalización en el catálogo.
- **Re-derivación canónica aplicada**: tras refrescar el catálogo de INN, se corrió
  `scripts/derive_tecnicas.py --apply` para propagar los combos completos a
  `x_tecnica_default_id` y `x_tecnicas_compatibles_ids`. **~415 productos
  actualizados**, 0 errores; idempotencia re-confirmada (corrida posterior: 0
  pendientes).
- **Endurecimiento de logging del sync**: se reforzó el manejo de logs para evitar
  exponer credenciales en texto plano. (Detalle del mecanismo en el área de análisis
  no versionada.)

### Relacionado

- La optimización de la fase de escritura de `derive_tecnicas.py` (writes agrupados
  + flag `--since`) está documentada en la entrada v12 (2026-06-22).

---

## 2026-06-22 · scripts · patch (v12) — derive_tecnicas.py: escritura agrupada + flag --since

**Tipo**: `scripts`
**Descripción**: Optimización de la fase de escritura de `derive_tecnicas.py` (la lectura ya era óptima: ~12 llamadas, sin N+1). No cambia la lógica de derivación validada.

### Cambios

- **Writes agrupados por derivación idéntica**: los templates que requieren cambio (`_needs_write`) se agrupan por `(x_tecnica_default_id, frozenset(compatibles_ids))` y se escribe **un `write` por grupo** con todos los ids. Como un `write` de Odoo aplica los mismos vals a todos los ids, es seguro (cada grupo comparte la misma derivación por construcción).
  - Un `--apply` fresco pasa de **~5,203 writes a ~104** (un write por combinación distinta; reducción ~50×).
- **Flag `--since <ISO8601|YYYY-MM-DD>`**: filtra la lectura con `write_date >= since` para reprocesar solo lo cambiado recientemente (uso post-sync). Sin el flag, comportamiento actual (todos).
- **Reporte** ahora muestra "X templates en Y grupos" en ambos modos (dry-run y apply).

### Invariantes preservadas

- Sin cambios en `derive()`, parsing, matching de aliases, regla de default, `_needs_write` ni el mini-test m2m (sigue corriendo en `--apply` antes del lote).
- **Idempotente**: re-correr no reescribe lo no cambiado; m2m con `[(6,0,[ids])]`.
- Errores por grupo aislados (uno que falle no detiene los demás).

### Validación

DRY-RUN tras la derivación ya aplicada en producción: 5226 sin cambio, 1 pendiente (cambio real introducido por el sync de proveedores entre el 13 y el 22). `--apply`: 1 template escrito en 1 grupo, 0 errores. Confirmada la idempotencia y el camino de escritura agrupado end-to-end.

---

## 2026-06-13 · scripts · minor (v11) — derive_tecnicas.py: derivación de técnica canónica

**Tipo**: `scripts`
**Descripción**: Script que deriva la técnica canónica de cada producto desde el campo legacy `x_tecnica_impresion` (texto libre, read-only) hacia los campos estructurados `x_tecnica_default_id` (m2o) y `x_tecnicas_compatibles_ids` (m2m). Aplicado en producción.

### `scripts/derive_tecnicas.py` (nuevo)

- **Match raw→canónica** vía `x_aliases` del modelo `x_tecnica_personalizacion`. Normaliza (minúsculas + sin acentos + trim), segmenta el crudo por `- / , +` y `" y "`, limpia parentéticos/puntuación, y matchea cada segmento por: (1) igualdad exacta normalizada; (2) substring normalizado **más largo** (p. ej. `dtf uv` → DTF UV, no DTF).
- **default** = primera técnica del crudo; **compatibles** = todas, en orden, dedup.
- **Status**: FULL / PARTIAL / NONE / NULL. Marca para revisión PARTIAL + NONE + multi-componente (segmentos con palabra de producto, p. ej. bolígrafo/libreta — con límite de palabra para no confundir `termo` ⊂ `termograbado`).
- **DRY-RUN por defecto**; `--apply` escribe. **Idempotente**: m2m con `[(6,0,[ids])]` y solo escribe si el valor calculado difiere del actual. Mini-test m2m auto-restaurado antes del lote. Errores por registro no abortan.
- **NO escribe** `x_tecnica_impresion` (lo pisa el sync de proveedores; ver `analysis/supplier-sync/AUDITORIA_SYNC.md`).
- Salida: `reports/tecnica_derivacion_YYYYMMDD.csv` (gitignored).

### Resultado en producción (5227 templates con técnica)

- **5203 escritos** (FULL 5196 + PARTIAL 7), NONE 0, NULL 24 sin tocar.
- 0 errores tras reintento (2 fallos de red transitorios resueltos por idempotencia).
- 15 marcados para revisión (kits multi-componente, asignación manual diferida a F5).

### `.gitignore`

- `reports/tecnica_derivacion_*` (nombres de producto + datos de negocio; no va al repo público).

---

## 2026-06-13 · data · patch (v10) — 3 aliases de técnica tras dry-run de derivación

**Tipo**: `data`
**Descripción**: El dry-run de `scripts/derive_tecnicas.py` (derivación raw→canónica de técnica desde `x_tecnica_impresion`) reveló variantes crudas frecuentes sin alias, que generaban PARTIAL/NONE. Se agregaron 3 aliases al seed y se propagaron a Odoo (`x_aliases` del modelo `x_tecnica_personalizacion`, vía `seed_tecnicas.py --apply`).

### Aliases agregadas (`data/tecnicas_seed.csv`)

| code | alias agregada | resolvía |
|---|---|---|
| `bajo_relieve` | `Grabado en bajo relieve` | PARTIAL de combos "Grabado en bajo relieve-…" |
| `doming` | `Goteado en Resina` | NONE "Goteado en Resina" |
| `sandblast` | `Grabado en Arena` | ~14 PARTIAL ("Grabado Arena" no matcheaba por la "en") |

### Impacto en la derivación (dry-run, 5227 templates)

- Antes: FULL 5110, PARTIAL 89, NONE 4.
- Después: **FULL 5196, PARTIAL 7, NONE 0**, NULL 24. Revisión total: 15.
- Los 7 PARTIAL restantes son kits **multi-componente** reales (asignación manual diferida a F5), no fixeables con alias.

### Notas

- Solo se versiona el dato del seed (`data/tecnicas_seed.csv` + `data/tecnicas_seed.md`). El cambio en `x_aliases` dentro de Odoo es dato de la instancia (no se commitea).
- No se modificaron `derive_tecnicas.py` ni `seed_tecnicas.py`.

---

## 2026-06-12 · scripts · minor (v9) — Loader de seed de técnicas + escritura en OdooClient

**Tipo**: `scripts`
**Descripción**: Se carga el catálogo de técnicas en producción y se añade soporte de escritura al cliente JSON-2.

### `scripts/seed_tecnicas.py` (nuevo)

Carga idempotente del CSV `data/tecnicas_seed.csv` al modelo `x_tecnica_personalizacion`.

- **Mapeo**: `code→x_code`, `nombre→x_name`, `x_aliases→x_aliases`, `x_orden` (del CSV o `(línea+1)*10`); fija `x_activa=True`, `x_descripcion=""`.
- **Idempotente**: busca por `x_code`; si existe `write`, si no `create`. Re-correr no duplica.
- **DRY-RUN por defecto**: sin `--apply` solo imprime el plan, no escribe.
- **Validación previa**: `x_code` no vacío y único en el CSV; aborta con error claro si falla.
- Logging por registro y manejo de errores explícito (cuenta fallos, exit ≠0 si hay).

### `scripts/odoo_client.py`

Agregados `create()`, `write()`, `unlink()` (antes solo lectura). Contratos JSON-2 verificados contra Odoo (2026-06-12) con un smoke test auto-limpiante:
- `create`: `{'vals_list': [vals]}` (Odoo 19 `model_create_multi`), devuelve lista de ids.
- `write`: `{'ids': [...], 'vals': {...}}`. `unlink`: `{'ids': [...]}`.

### Resultado en producción

20 técnicas creadas en `x_tecnica_personalizacion` (ids 4-23), todas activas, `x_orden` 10..200. Idempotencia confirmada (re-corrida dry-run reporta 20 UPDATE, 0 CREATE).

> Pendiente F5 (sin cambios): asignar los 26 valores multi-componente y la regla de default en combos (ver `data/tecnicas_seed.md`).

---

## 2026-06-12 · data · patch (v8) — Modelo x_tecnica_personalizacion reconciliado con producción

**Tipo**: `data`
**Descripción**: El modelo `x_tecnica_personalizacion` ya fue creado en producción. Se reconcilian `specs/data-model.md` y `odoo-extensions/studio-fields.yaml` con los nombres de campo reales (verificados contra Odoo el 2026-06-12), resolviendo la divergencia de naming señalada al versionar el seed (v7).

### Campos reales en producción

`x_code` (char), `x_name` (char), `x_aliases` (text), `x_orden` (integer), `x_activa` (boolean), `x_descripcion` (text). 0 registros aún — el seed (`data/tecnicas_seed.csv`) se carga con `scripts/seed_tecnicas.py` (F4b, pendiente).

### Cambios

- **Naming**: campos con prefijo `x_` (NO `x_studio_`) por ser modelo custom propio. Documentado para no asumir la regla general.
- **Diseño simplificado**: los atributos ricos del diseño original (`casos_uso_tipicos`, `materiales_compatibles`, `max_tintas_default`, `requiere_arte_vectorial`, `tiempo_extra_dias`, `sequence`) **NO se implementaron** (D7: lista plana). La metadata descriptiva va en `x_descripcion`.
- `specs/data-model.md`: definición del modelo reemplazada por los 6 campos reales; el bloque inline de seed (8 técnicas) sustituido por un puntero a `data/tecnicas_seed.csv` (20 técnicas) y `data/tecnicas_seed.md`.
- `odoo-extensions/studio-fields.yaml`: campos reales con `status: created`; versión 0.3.0 → 0.4.0.

### Fuera de alcance (siguen ○ planificados)

`x_costo_personalizacion` (Fase 3) y `x_tecnica_default_id` / `x_tecnicas_compatibles_ids` en `product.template` (Fase 2) — aún no están en producción.

---

## 2026-06-12 · data · minor (v7) — Seed canónico de técnicas de personalización

**Tipo**: `data`
**Descripción**: Se versiona el catálogo canónico de técnicas de personalización (`data/tecnicas_seed.csv`) y su documento de procedencia/limpieza (`data/tecnicas_seed.md`). Es el insumo para crear y poblar el modelo `x_tecnica_personalizacion` en Fase 2. Apto para repo público (sin datos sensibles).

### Origen

Derivado de los **159 valores crudos** del campo legacy `x_tecnica_impresion` (char, texto libre, **alimentado por el API de cada proveedor**) sobre ~5227 productos, detectados en el audit del 2026-06-11.

### Decisiones de taxonomía (D7)

- **Lista plana de 20 técnicas**, sin familias (el precio varía por técnica, no por familia).
- **DTF genérico** (los proveedores no distinguen DTF Textil vs UV de forma consistente); se conserva además `DTF UV` aparte.
- **Nombres dobles conservados**: Doming (Gota de Resina), Sand Blast (Grabado en Arena), Láser (Grabado Láser), Transfer (Termocalca), Bajo Relieve (Embozado).
- **4 técnicas raras de 1 producto** (`vinyl`, `dtf_uv`, `offset`, `transfer`) marcadas para confirmar con producción.

### Limpieza de aliases

- **Typos conservados a propósito** (`Serigafía`, `Seigrafía`): el proveedor los manda y el sync debe reconocerlos.
- **Contaminación de componentes removida** ("Serigrafía en Vidrio" → "Serigrafía").
- **Dedup por forma normalizada** (sin acentos, minúsculas).
- Detalle completo en `data/tecnicas_seed.md`.

### Pendiente (F5)

- Asignación de los **26 valores multi-componente** (~61 productos, kits).
- Regla para elegir la técnica default (`x_tecnica_default_id`) en combos.

### Nota técnica

- CSV normalizado a UTF-8 sin BOM (el archivo original traía BOM, que rompía el nombre de la primera columna `code`).
- ⚠️ Divergencia pendiente de reconciliar: el seed mapea a campos `x_code`/`x_name`/`x_aliases`/`x_orden`/`x_activa`, pero `specs/data-model.md` define el modelo con `code`/`name`/`descripcion`. A resolver al crear el modelo en Fase 2.

---

## 2026-06-11 · docs · patch (v6) — Reconciliación spec-vs-realidad (catálogo)

**Tipo**: `docs`
**Descripción**: Tras el audit del catálogo (`scripts/audit_catalog.py`, reporte local `reports/catalog_audit_20260611.md`), se reconcilia la documentación con la realidad descubierta. Decisiones del operador.

### A · Proveedor → `product.supplierinfo` (no campo custom) — `specs/data-model.md`

- **Eliminados** `x_proveedor_id` y `x_proveedor_sku` del modelo de producto: nunca existieron en Odoo; el vínculo producto↔proveedor usa el estándar `product.supplierinfo`.
- Documentada la fuente de verdad: `product_code` = SKU del proveedor; `price` + `min_qty` = costo base por proveedor.
- Aclarado que `product.supplierinfo` (costo del producto base) es **distinto y complementario** de `x_costo_personalizacion` (costo de aplicar la técnica, por cantidad).
- Actualizados diagrama de relaciones, notas de migración y ejemplos de naming.
- Registrada deuda de datos para Fase 6: ~3356 de 5432 `supplierinfo` apuntan a partners sin `supplier_rank > 0`.

### B · Técnica: campos legacy reales — `specs/data-model.md`

- Documentado que **`x_tecnica_impresion`** (char, texto libre) YA EXISTE con datos (5227 productos, 159 valores sin normalizar) y es la **fuente de migración** hacia el modelo nuevo. Marcado legacy/solo-lectura; **no borrar antes de validar la migración**.
- Documentado el set completo de campos legacy reales verificados por el audit: `x_tecnica_impresion`, `x_area_impresion`, `x_proveedor_carga`, `x_material`, `x_capacidad`, `x_medidas`, `x_imagen_url_principal` (todos char de texto libre).
- Marcados explícitamente como ○ "NO existen aún, se crean en Fase 2": `x_tecnica_default_id`, `x_tecnicas_compatibles_ids`, `x_costo_personalizacion`, `x_area_max_cm2`, `x_area_dimensiones`, etc. El diseño objetivo no cambia.
- **Hallazgo**: existe un campo `x_proveedor_carga` (char) — etiqueta legacy de texto libre del proveedor que cargó el producto. NO es el vínculo estructurado (ese es `product.supplierinfo`); se documenta como tal para evitar confusión.

### C · Descuentos: de-scope — `docs/roadmap.md`

- Eliminada la tarea "Migrar tabla de descuentos a Promotions": los descuentos YA viven en `loyalty.program` (Tipo: Promociones, por compra mínima). No hay migración.
- Reemplazada por dos notas de backlog: (1) auditar/arreglar los `loyalty.program` existentes con comportamiento extraño; (2) limpiar pricelists de prueba no usadas (conservar solo Default), validando antes que ninguna esté referenciada por partners u órdenes.

### D · Limpieza de referencias residuales (alineación con la realidad)

Archivos que aún referenciaban los campos descartados/inexistentes, corregidos para usar `product.supplierinfo` y los campos legacy reales:

- `odoo-extensions/studio-fields.yaml`: eliminados `x_proveedor_id`/`x_proveedor_sku`; agregados los 7 campos legacy reales (`status: created`); marcados los planificados con `status: planned`; documentado supplierinfo. Versión 0.2.0 → 0.3.0.
- `odoo-extensions/automation-rules.yaml`: la regla "Producto nuevo de proveedor" ahora filtra por `seller_ids` (supplierinfo estándar) en vez de `x_proveedor_id`.
- `scripts/backup_catalog.py`: el filtro `--supplier` usa `seller_ids.partner_id`; la lista de campos usa los legacy reales (antes pedía campos inexistentes que romperían la llamada). TODO para capturar el supplierinfo completo.
- `test/fixtures.json`: las plantillas de producto usan campos reales + `seller_ids`, con fixtures de `product.supplierinfo`; `type` corregido a `consu` (Goods en Odoo 19).

---

## 2026-06-11 · scripts · patch (v5) — Fixes audit_catalog + corrección de spec JSON-2

**Tipo**: `scripts`
**Descripción**: La primera corrida real de `scripts/audit_catalog.py` (con credenciales en `.env`) falló en todas las llamadas. Diagnóstico y 5 fixes; se corrige además el endpoint JSON-2 mal documentado en el repo.

### 5 fixes en el audit

1. **Endpoint `/json/2/`** (era `/json2/`): la ruta JSON-2 real de la instancia es `/json/2/{model}/{method}`. Todas las llamadas daban 404. Corregido en `scripts/odoo_client.py`.
2. **stdout UTF-8**: la consola de Windows (cp1252) no podía imprimir `→`/`✓`/`⚠` y reventaba con `UnicodeEncodeError`. `audit_catalog.py` ahora hace `sys.stdout.reconfigure(encoding='utf-8')`.
3. **Parseo de respuesta cruda**: la JSON-2 API devuelve el resultado directo (lista/dict), NO envuelto en `{"result": ...}`. `OdooClient._post()` devuelve el JSON crudo; los errores se detectan por status HTTP (`raise_for_status`).
4. **Ranking de campo técnica**: existían dos candidatos (`x_area_impresion` y `x_tecnica_impresion`); el código tomaba el primero sin priorizar y reportaba el área en vez de la técnica. Se prioriza el campo con señal de "método" (`TECNICA_STRONG`). El campo real es `x_tecnica_impresion`.
5. **Universo proveedor/activos**: la cobertura de `supplierinfo` daba >100% por mezclar templates archivados (numerador) con activos (denominador). Se intersecta con el universo de templates activos y se expone cuánto `supplierinfo` apunta a partners sin `supplier_rank>0`.

### CORRECCIÓN DE SPEC — endpoint JSON-2

El endpoint estaba documentado como `/json2/` en todo el repo, pero la instancia real usa **`/json/2/`** (verificado empíricamente). Es la "deuda histórica specs vs realidad" que advierte `CLAUDE.md`. Reemplazado `/json2/` → `/json/2/` en:
- `specs/integrations.md`, `specs/api-shapes.md`, `docs/architecture.md`, `docs/glossary.md`
- `.claude/rules/n8n-workflows.md` (regla de n8n)
- `n8n-workflows/ai-agent-respond.json`

> ⚠️ Pendiente (fuera de alcance de este cambio): `specs/api-shapes.md` aún documenta respuestas envueltas en `{"result": ...}`; la JSON-2 API las devuelve crudas (ver fix #3).

### .gitignore

Reemplazado el patrón `catalog_*.json` por `reports/catalog_audit_*` para ignorar AMBOS artefactos del audit (`.json` y `.md`). El `.md` no se commitea: repo público con nombres de pricelist tipo cliente y métricas de negocio.

---

## 2026-06-03 · odoo · minor (v4) — Cierre Fase 1

**Tipo**: `odoo`
**Descripción**: Cierre de Fase 1 — limpieza del pipeline, etiquetas CRM y 3 alertas de seguimiento configuradas.

### Limpieza del pipeline

Leads y oportunidades estancados revisados manualmente. Las etapas "Nuevo lead" y "Contactado" quedaron en cero antes de activar alertas, estableciendo una línea base limpia.

### Etiquetas CRM creadas

| Etiqueta | Color | Uso |
|---|---|---|
| Urge contactar | Naranja/amarillo | Oportunidad sin avanzar 1 día en etapa "Nuevo lead" |
| Peligro, posible pérdida | Rojo | Oportunidad sin avanzar 3 días en etapa "Nuevo lead" |

Las etiquetas se acumulan: a los 3 días una oportunidad tendrá ambas, mostrando la escalada visualmente en el pipeline.

### 3 Automation Rules de alerta

**Alerta 1 — "Alerta - Lead sin calificar 1 día"**
- Disparador: basado en tiempo / campo `date` (Creado el) / espera 1 día
- Filtro: `Tipo = Lead`
- Acción: crear actividad "Calificar o descartar este lead" asignada a Juan Carlos Asomoza
- Nota: ajustada de 2 a 1 día para cumplir SLA de 24h del negocio

**Alerta 2 — "Alerta - Oportunidad sin avanzar 1 día"**
- Disparador: basado en tiempo / campo `date_last_stage_update` (Última actualización de etapa) / espera 1 día
- Filtro: `Tipo = Oportunidad` Y `Etapa = Nuevo lead`
- Acción 1: crear actividad "Urge contactar" asignada a Juan Carlos Asomoza
- Acción 2: actualizar registro — AGREGAR etiqueta "Urge contactar" (modo agregar, no reemplazar)

**Alerta 3 — "Alerta - Oportunidad en peligro 3 días"**
- Disparador: basado en tiempo / campo `date_last_stage_update` / espera 3 días
- Filtro: `Tipo = Oportunidad` Y `Etapa = Nuevo lead`
- Acción 1: crear actividad "PELIGRO - posible pérdida" asignada a Juan Carlos Asomoza
- Acción 2: actualizar registro — AGREGAR etiqueta "Peligro, posible pérdida"
- Acción 3: enviar correo a `mozaprintmx@gmail.com` con plantilla de alerta (variables con `/campo`)

### Regla de proceso crítica documentada

Odoo no está conectado al correo (comunicación con clientes se hace desde Gmail). Odoo solo detecta actividad cuando el vendedor **mueve la tarjeta en el pipeline**. Si el vendedor contacta o cotiza desde Gmail sin mover la tarjeta, las alertas se disparan como falsos positivos (incluyendo la Alerta 3 que manda correo al equipo).

**Comunicar a Karina y a todo vendedor**: mover la tarjeta en el pipeline cada vez que se actúa con un cliente. Ver `docs/proceso-equipo-crm.md`.

Esta dependencia desaparece cuando se implemente correo bidireccional (tarea prioridad media documentada) o la integración WhatsApp (Fase 4), donde Odoo detectará actividad automáticamente.

**Documentación actualizada**: `docs/fase1-captura-leads.md` (estado final), `docs/roadmap.md` (Fase 1 marcada completa), nuevo `docs/proceso-equipo-crm.md`.

---

## 2026-06-03 · docs · patch (v3)

**Tipo**: `docs`
**Descripción**: Documentados dos hallazgos técnicos surgidos en la limpieza del pipeline (Fase 1), que condicionan el diseño del agente WhatsApp (Fase 4-6).

### Hallazgo 1 — Identificación de contactos de WhatsApp

**Problema**: sin conexión WhatsApp-Odoo, los clientes se ven solo por número en la WA Business App si no están guardados manualmente. Guardar contactos es manual y tedioso; al pasar al CRM solo queda un número sin nombre.

**Limitación técnica confirmada**: la agenda de la WA Business App no tiene API para escritura automática. Herramientas de terceros que prometen esto violan términos de Meta (riesgo de ban del número) — descartadas.

**Solución planeada (Fase 4-6)**: la Cloud API con Coexistence entrega `profile.name` en cada mensaje entrante. n8n lo usará para auto-crear o actualizar el contacto en Odoo (find-or-create) antes de llamar al agente. Odoo pasa a ser la fuente de verdad de contactos.

**Mitigación temporal**: poner siempre el número en el campo teléfono al registrar leads manuales de WhatsApp; mantener práctica de guardar contactos en celular con formato consistente.

### Hallazgo 2 — Exclusión de proveedores del agente

**Problema**: el negocio contacta proveedores por WhatsApp para comprar. El agente Moza no debe responder a esos números. Las etiquetas de la WA Business App son locales del celular y no se exponen vía Cloud API.

**Solución planeada (Fase 4-6)**: pre-flight filter en n8n antes de cada respuesta del agente. Verifica que el remitente no sea: (1) proveedor (`supplier_rank > 0` en res.partner), (2) marcado con `x_studio_no_agente = True`, (3) número interno. Si excluido: conversación en modo manual, sin respuesta del agente, sin lead de venta en CRM.

**Preparación del terreno (hacer antes de Fase 4)**: registrar proveedores activos en Odoo con número de WhatsApp en campo teléfono/móvil.

**Cambios en documentación**:
- `specs/ai-agent-spec.md`: nueva sección `## Pipeline de mensajes entrantes` con pre-flight filter y auto-identificación de contacto; nota al tool `find_or_create_partner` (#5)
- `specs/data-model.md`: nueva sección `res.partner (extendido)` con campo `x_studio_no_agente` (booleano, status: planned, Fase 4)
- `docs/roadmap.md`: tareas de preparación en Fase 5; tareas de implementación en Fase 6
- `docs/fase1-captura-leads.md`: nueva sección con ambos hallazgos y mitigaciones temporales

---

## 2026-06-03 · odoo · minor (v2)

**Tipo**: `odoo`
**Descripción**: Fase 1 completada al 7/9 — tres formularios web funcionando en producción, plantilla de notificación actualizada.

**Cambios en Odoo (producción)**:
- Formulario /shop reconectado al CRM: acción "Crear registro" en `crm.lead`, mapeo completo incluyendo `x_studio_collected_qty`, `x_studio_collected_producto`, `x_studio_collected_personalizacion`. `x_studio_origen_form = "Tienda"`.
- Formulario de ficha de producto reconectado al CRM: mismo mapeo que /shop, producto pre-rellenado con nombre del artículo. `x_studio_origen_form = "Producto"`.
- Typo corregido en dropdown de personalización web: `"Si"` → `"Sí"` para que coincida con el valor del campo `x_studio_collected_personalizacion` en Odoo.
- Plantilla de notificación "Notificación nuevo lead web" actualizada: ahora incluye Cantidad (`x_studio_collected_qty`), Producto (`x_studio_collected_producto`) y Personalización (`x_studio_collected_personalizacion`) además de los datos de contacto y origen.

**Pendientes documentados en `docs/fase1-captura-leads.md`**:
- `x_studio_origen_url`: definir mecanismo de captura automática (JavaScript en formulario, variable nativa Odoo, o UTM)
- Alertas de leads estancados: hay leads de hasta 42 días sin movimiento; configurar Automation Rule con umbral a definir
- Limpieza del pipeline actual: pasada manual antes de activar alertas
- Asignación automática a Sales Team

---

## 2026-06-03 · odoo · minor

**Tipo**: `odoo`
**Descripción**: Fase 1 parcialmente completada — CRM activo, /contactanos conectado, automation rule de notificación funcionando.

**Cambios en Odoo (producción)**:
- Etapa "Leads" activada en CRM (antes todo entraba como Oportunidad directamente)
- Formulario /contactanos reconectado: acción cambiada de "Enviar correo" a "Crear registro" en `crm.lead`, tipo forzado a Lead (no Oportunidad). Mapeo: Nombre→`contact_name`, Teléfono→`phone`, Correo→`email_from`, Empresa→`partner_name`, Asunto→`name`, Pregunta→`description`, Origen→`x_studio_origen_form="Contactanos"`. Probado en producción.
- Automation Rule "Notificar nuevo lead de formulario web": dispara al crear `crm.lead` con `x_studio_origen_form` establecido; envía correo a `info@mozaprintmx.com`. Probado en producción.

**Hallazgos técnicos documentados**:
- Odoo Online procesa cola de correo vía cron (~cada hora). Notificación de lead puede tardar hasta ~1h. Aceptado: el lead se crea al instante, WhatsApp vía n8n será instantáneo.
- AI Lead Scoring funciona nativamente en Odoo Online sin configuración adicional (tier IA incluido en el plan Custom, no requiere API key propia).
- Odoo detecta "leads similares" y rastrea "visitas a página" automáticamente.
- Las Automation Rules no tienen costo extra en el plan Custom de Odoo Online.
- Conectar formulario al CRM NO impide responder por correo — se puede tener Lead en CRM + notificación por correo simultáneamente.
- Odoo NO crea Contacto (`res.partner`) al entrar un Lead. El contacto se crea al "Convertir a Oportunidad". Flujo recomendado: lead entra → revisar → si vale, convertir y crear contacto; si no, marcar Perdido.

**Nota en template**: las variables en cuerpos de correo de Automation Rules deben insertarse con el comando `/campo` del editor. Escribir `{{ object.campo }}` a mano se guarda como texto literal y no se sustituye.

**Pendientes de Fase 1 documentados**:
- Reconectar formularios /shop y ficha de producto (mapeo más complejo)
- Corregir typo "Si"→"Sí" en dropdown web antes de reconectar
- Definir cómo llenar `x_studio_origen_url` automáticamente
- Configurar asignación automática a Sales Team

**Nueva tarea registrada en roadmap**: Correo bidireccional `@mozaprintmx.com` en Odoo (prioridad media, requiere ajuste de SPF antes de activar).

---

## 2026-06-02 · odoo · patch

**Tipo**: `odoo`
**Descripción**: Creación de 5 campos custom en `crm.lead` vía Studio. Documentada divergencia de prefijo `x_studio_` en Odoo Online.

**Campos creados en producción**:
| Nombre técnico real | Etiqueta | Tipo |
|---|---|---|
| `x_studio_collected_qty` | Cantidad solicitada | Integer |
| `x_studio_collected_producto` | Producto solicitado | Char |
| `x_studio_collected_personalizacion` | Lleva personalización | Selection (Sí/No/Aún no he decidido) |
| `x_studio_origen_form` | Origen del formulario | Char |
| `x_studio_origen_url` | Origen URL | Char |

**Hallazgo importante**: Odoo Online fuerza el prefijo `x_studio_` en todos los campos creados vía Studio (no editable). Los nombres planeados originalmente con prefijo `x_` tienen nombres reales `x_studio_<nombre>`. Todos los campos custom futuros tendrán este prefijo.

**Documentación actualizada**:
- `specs/data-model.md`: sección `crm.lead` separada en "Creados en producción" vs "Planificados"; nombres técnicos reales; nota sobre el prefijo
- `odoo-extensions/studio-fields.yaml`: `status: created/planned` en cada campo; nota global sobre el prefijo `x_studio_`; versión `0.2.0`

**Impacto**: los workflows de n8n y Server Actions que referencien estos campos deben usar los nombres `x_studio_*`, no `x_*`.

---

## 2026-06-02 · architecture · patch

**Tipo**: `architecture`
**Descripción**: ADR 005 — n8n como router único de WhatsApp + camino de inbox escalable en Odoo.

**Cambios**:
- Nuevo `decisions/005-n8n-router-unico-inbox-escalable.md`: documenta la restricción técnica de webhook único por número, la decisión de construir inbox sobre Odoo en lugar de adoptar un BSP, y el plan de crecimiento en 3 etapas
- `docs/architecture.md`: agregado bullet en `n8n SÍ debe` sobre la restricción de webhook único (con referencia a ADR 005); agregada entrada en `Decisiones arquitectónicas clave`; corregido comentario de `ODOO_API_KEY` de `integration@` a `Rosy Ponce` (consistente con `docs/usuarios-odoo.md`)

**Impacto**: ninguno en producción. Define una restricción arquitectónica crítica que Claude Code debe respetar al sugerir integraciones.

---

## 2026-06-01 · infra · patch

**Tipo**: `infra`
**Descripción**: Setup base de Meta Business / WhatsApp completado. Documentada decisión de orden.

**Cambios**:
- Portfolio Meta confirmado: mozaprint_mx (Business ID: 100794159106337), admins Juan Carlos y Karina
- WABA "Moza Print" (ID: 358071354051207) aprobada, número +52 1 56 3277 6277 registrado
- Verificación de negocio Meta: no requerida para este caso de uso (no bloquea)
- Creado `docs/meta-whatsapp-status.md` con estado completo, pendientes y limitaciones de Coexistence
- Decisión documentada: pausar conexión Cloud API hasta tener VPS n8n con URL pública
- Roadmap actualizado: tarea Meta marcada `[x]`, bloqueante de Fase 4 corregido (era "verificación Meta", es "VPS n8n")

**Pendientes documentados** (se completan de corrido al tener n8n):
- Crear App en Meta for Developers (App ID, App Secret)
- Crear System User con token permanente
- Activar Coexistence en el número
- Configurar webhook hacia n8n
- Enviar 5 plantillas a aprobación Meta

**Impacto**: ninguno en producción. Solo documentación y configuración de accesos.

---

## 2026-05-31 · infra · patch

**Tipo**: `infra`
**Descripción**: Cierre de tareas DNS y usuario técnico API de Fase 0.

**DNS — completado**:
- Auditoría ejecutada 2026-05-28 con `scripts/dns_audit.py` (adaptado a dnspython para Windows)
- Cloudflare authoritative confirmado · Hostinger queda solo como registrar + email
- `old.mozaprintmx.com` eliminado de Cloudflare (residuo WooCommerce legacy)
- SPF reforzado de `~all` a `-all` (modo estricto)
- DKIM confirmado: 3 selectores Hostinger (`hostingermail-a/b/c._domainkey`) vía CNAME delegation
- DMARC en `p=none` — en observación, escalar a `quarantine` en ~4 semanas
- **Alerta futura documentada**: cuando Odoo envíe email con servidor propio, agregar `include:<spf-odoo>` al SPF antes del `-all` o los correos serán rechazados

**Usuario técnico API Odoo — completado**:
- Decisión: NO crear usuario `integration@` dedicado (evitar costo de usuario facturable adicional en Odoo Online)
- Se reutiliza usuario existente "Rosy Ponce" (`rosy_ponce@mozaprintmx.com`) con permisos reducidos desde casi-admin a mínimos necesarios para la API
- API key `"n8n-produccion"` generada y almacenada en Bitwarden
- API key `"proveedores-sync"` queda pendiente para la fase de migración del script
- Ver detalle completo en `docs/usuarios-odoo.md`

**Gestor de secretos**:
- Adoptado Bitwarden para centralizar API keys, tokens y contraseñas del proyecto

**Impacto**: DNS de producción modificado (SPF, eliminación de subdominio). Permisos de usuario Odoo reducidos.

---

## 2026-05-29 · docs · patch

**Tipo**: `docs`
**Descripción**: Creado `docs/dns-status.md` con arquitectura DNS completa de mozaprintmx.com.

**Cambios**:
- Nuevo documento `docs/dns-status.md` con: arquitectura actual (registrar/Cloudflare/Odoo/Hostinger email), tabla de registros activos, historial (WordPress→Odoo, Hostinger DNS→Cloudflare), configuración de email, y pendientes de optimización (SPF `-all`, DMARC `quarantine`, DKIM, subdominio n8n)

**Impacto**: ninguno en producción. Solo documentación.

---

## 2026-05-28 · scripts · patch

**Tipo**: `scripts`
**Descripción**: Migración de `scripts/dns_audit.py` de `subprocess + dig` a `dnspython` para compatibilidad nativa en Windows.

**Cambios**:
- Reemplazada función `run_dig()` por `dns_query()` usando `dns.resolver` de dnspython
- Eliminada dependencia de `subprocess` y del binario externo `dig`
- Añadido guard de import al inicio: mensaje de error claro si dnspython no está instalado
- Añadido `sys.stdout.reconfigure(encoding='utf-8')` para evitar errores de encoding en consola Windows (cp1252)
- Actualizado docstring del módulo
- Creada carpeta `reports/` y primer baseline: `reports/dns_20260528.json`
- Creado `requirements.txt` con dependencias del proyecto

**Impacto**: ninguno en producción. El script produce output idéntico al anterior.

**Dependencia nueva**: `dnspython>=2.6` — instalar con `pip install dnspython`

**Primera ejecución**: mozaprintmx.com auditado el 2026-05-28. Hallazgos:
- Cloudflare authoritative ✓
- SPF presente pero `~all` (no estricto) ⚠
- DMARC presente con `p=none` ⚠
- Subdominio `old.mozaprintmx.com` activo — verificar si es legacy
- `n8n.mozaprintmx.com` pendiente de crear

---

## 2026-05-28 · docs · patch

**Tipo**: `docs`
**Descripción**: Añadida regla de autonomía epistémica a CLAUDE.md.

**Cambios**:
- Nueva subsección `### Antes de preguntar` en `## Cómo trabajamos`
- Define que Claude debe buscar en `docs/`, `decisions/`, `specs/`, `scripts/`,
  `n8n-workflows/` y `odoo-extensions/` antes de escalar una duda al operador
- Solo se escala lo que realmente no puede resolverse leyendo el repo

**Impacto**: ninguno en producción. Solo cambia comportamiento del asistente.

---

## 2026-05-24 · decision · v0.2.0

**Tipo**: `decision`
**Descripción**: Consolidación de decisiones del equipo tras revisar plan general.

**Cambios**:
- ADR 004 creado con todas las decisiones confirmadas
- Modelo de datos actualizado: técnicas de personalización ahora son modelo 
  separado (`x_tecnica_personalizacion`) en lugar de selection
- Cada producto tiene `x_tecnica_default_id` (many2one) + 
  `x_tecnicas_compatibles_ids` (many2many)
- ai-agent-spec.md ampliado con horarios, comandos en español, anticipo, 
  política de seguimiento proactivo
- Script de auditoría DNS creado: `scripts/dns_audit.py`
- Manual de mantenimiento del KB para Karina: `docs/manual-knowledge-base.md`
- Decisión revisada de orquestador: VPS self-hosted (Hetzner CX22) en lugar 
  de n8n Cloud, basado en volumen real de 10-20 conv/sem
- Decisión LLM (Claude vs OpenAI) se mantiene abierta hasta piloto sprint 5-6

**Impacto**: 
- Hay que crear modelo `x_tecnica_personalizacion` en Odoo antes de productos
- Datos seed iniciales: 8 técnicas a cargar en sprint 1
- Hay que cargar técnicas antes de poder vincular productos
- Workflows de n8n deben referenciar técnicas por many2one (no selection)
- Knowledge base de cada técnica debe vivir en Odoo Knowledge módulo (no en KB del agente directamente)

**Tareas seguimiento**:
- [ ] Crear modelo de técnicas vía Studio
- [ ] Cargar 8 técnicas seed
- [ ] Migrar productos existentes para que apunten a técnicas (script de migración)
- [ ] Actualizar workflows n8n (cuando se construyan) para usar tecnica_id
- [ ] Entregar manual a Karina

---

## 2026-05-23 · docs · v0.1.0

**Tipo**: `docs`
**Descripción**: Bootstrap del paquete de contexto para Claude Code.

**Cambios**:
- Creado CLAUDE.md raíz con convenciones del proyecto
- Creado docs/architecture.md con diagrama y responsabilidades
- Creado docs/glossary.md con términos del negocio
- Creado docs/roadmap.md con fases y estado
- Creado specs/data-model.md con campos custom de Odoo
- Creado specs/integrations.md con APIs externas
- Creado specs/ai-agent-spec.md con identidad y tools del agente Moza
- ADR 001: n8n self-hosted como orquestador
- ADR 002: Claude como LLM primario
- ADR 003: WhatsApp Coexistence Mode (propuesto)

**Impacto**: ninguno en producción. Solo documentación.

---

## Versionado

- **Major** (v1.0.0): cambios incompatibles en modelo de datos o API
- **Minor** (v0.x.0): features nuevos sin breaking
- **Patch** (v0.0.x): fixes, refactors, docs

