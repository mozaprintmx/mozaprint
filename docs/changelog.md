# Changelog técnico — Mozaprint

> Historial de cambios significativos al sistema. Una entrada por cambio relevante.

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

