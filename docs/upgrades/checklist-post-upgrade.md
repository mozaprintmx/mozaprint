# Checklist post-upgrade de Odoo

> Qué revisar después de que Odoo Online actualice una base. Pensado para
> ejecutarse de arriba abajo: **lo automático primero** (2 comandos, ~3 min), y
> solo después lo manual. Si el paso 1 encuentra algo bloqueante, arréglalo antes
> de seguir — casi todo lo demás depende de que las vistas combinen bien.

Antes de empezar, anota la versión: `python scripts/audit_post_upgrade.py --target test --sin-http`
la imprime en el encabezado (`Odoo saas~19.2`).

---

## 1. Automático — los dos comandos

```bash
# a) Salud general: vistas, sitio web, censo de objetos custom
python scripts/audit_post_upgrade.py --target test

# b) Salud del PDF de cotización (columna de imagen + cuadre de columnas)
python scripts/deploy_reporte_cotizacion.py --target test --verificar

# c) Que no se haya colado código que Odoo factura
python scripts/audit_lineas_facturables.py --target test
```

Los tres son **solo lectura** y salen con código 1 si hay hallazgos.

- [ ] **(a) sale limpio** — `✓ Sin hallazgos bloqueantes.`
- [ ] **(b) sale limpio** — `✓ El reporte está completo y cuadrado.`
- [ ] **(c) sale limpio** — `✓ Dentro del máximo tolerado.` (0 bloques)

> El motor de cotización se **retiró de producción el 2026-08-17** por el cargo de
> Odoo por línea de código ([ADR 007](../../decisions/007-retiro-motor-cotizacion-costo-codigo.md)).
> `deploy_motor_cotizacion.py --verificar` solo aplica si se reconstruye.

Qué revisa (a), y qué significa cada hallazgo:

| # | Revisión | Si aparece algo |
|---|---|---|
| **1** | Vistas heredadas sin `position`/`xpath`/`<data>` | **Bloqueante.** Rompe con 500 toda página que combine esa vista. Es el fallo del [2026-08-15](incidencias/2026-08-15-ficha-producto-500.md) |
| **2** | `t-call` a plantillas que ya no existen | **Bloqueante.** 500 al renderizar esa página. Suele venir de un módulo que Odoo retiró |
| **3** | Keys de vista duplicadas y activas para el mismo website | ⚠ No siempre rompe: qweb elige una arbitrariamente. Revisar si algo se ve raro |
| **6** | Censo de modelos/campos `x_` y Server Actions | Compáralo con la corrida anterior. Un número que **baja** es señal de alarma |
| **7** | Vistas de módulo editadas **in-place por Studio** | ⚠ Aviso. El upgrade REESCRIBE esas vistas y se lleva la personalización sin error ni traza — es el fallo del [2026-08-16](incidencias/2026-08-16-columna-imagen-cotizacion.md). Confirma que lo personalizado viva en una vista propia heredada |
| **8** | Cuadre de columnas del reporte de cotización | **Bloqueante para el PDF.** Alguna fila (sección, combo, resumen) no suma las columnas del encabezado → el PDF sale corrido. Reparación: `deploy_reporte_cotizacion.py --apply` |
| **5** | Barrido HTTP de rutas públicas (incluye 3 fichas de producto reales) | Cualquier cosa que no sea 2xx/3xx |

### Comparar contra la otra base

```bash
python scripts/audit_post_upgrade.py --comparar
```

Como test y producción son la misma base duplicada, **los ids de vista coinciden**
y el diff es fiable:

- **[4] desactivadas en una y activas en la otra** → esas sí las apagó el upgrade.
- **[4b] solo cambiaron de key** → módulos fusionados o renombrados. Ruido, no impacto.
  (En 19.2: `website_sale_comparison` se fusionó en `website_sale`, 14 vistas.)
- **[4c] existen en una sola base** → vistas nuevas de la versión, o creadas a mano
  en una sola base. Diferencias esperables.

- [ ] **[4] está en cero** (o cada vista apagada tiene explicación)

---

## 2. Sitio web público

Lo que un cliente puede tocar. El auditor ya barre las rutas, pero **el 200 no
garantiza que se vea bien** — esto se revisa con los ojos.

- [ ] **Ficha de producto** — abre 2-3 productos de proveedores distintos (INN, PO, 4P).
      Precio, imagen, variantes de color, botón de compra, bloque de "Términos y
      condiciones" **en español**
- [ ] **/shop** — filtros laterales muestran solo **Color, Talla y Precio**
      (si aparecen atributos basura, se revirtió la limpieza de Fase 2)
- [ ] **Filmstrip de categorías** — se ve y la página no pesa de más
      (`scripts/optimize_category_images.py` dejó `/shop` en ~913 KB)
- [ ] **Búsqueda** — `/shop?search=<algo>` devuelve resultados
- [ ] **Carrito** — agregar un producto y llegar al checkout
- [ ] **Formularios que alimentan el CRM** — `/contactanos`, el de `/shop` y el de la
      ficha de producto. **Envía uno de prueba** y confirma que cae el Lead con sus
      campos custom (ver `docs/fase1-captura-leads.md`)
- [ ] **Móvil** — al menos la ficha de producto

---

## 3. Backend — operación diaria

- [ ] **CRM**: el pipeline abre, las tarjetas se mueven de etapa, las etiquetas siguen
- [ ] **Automation Rules**: notificación de lead web + las 3 alertas de seguimiento
      (Ajustes → Técnico → Automatizaciones; que sigan **activas**)
- [ ] **Cotización**: abre una `sale.order` en borrador — el formulario **debe abrir**
      y mostrar el botón «Agregar personalización» en el encabezado
- [ ] **Campos `x_` en producto**: abre una ficha en backend y confirma que
      `x_tecnica_default_id`, `x_tecnicas_compatibles_ids`, `x_area_impresion` y
      `x_material` tienen valor
- [ ] **Menús del motor**: Ventas → Configuración → *Costos de personalización*,
      *Técnicas de personalización* y *Solicitudes de aprobación*
- [ ] **Knowledge**: el manual de personalización sigue publicado

> Si el formulario de ventas **no abre**, es la vista heredada del motor: ve a
> [motor-cotizacion.md](motor-cotizacion.md) § *Reparación por síntoma*.

---

## 4. Motor de cotización y PDF — prueba funcional

`--verificar` valida la estructura; esto valida el **comportamiento**. Correr el
paso 4 del [checklist de despliegue](../checklist-deploy-produccion.md): casos
A/B/C, flujo de aprobación, línea de setup, y re-aplicar sin duplicar.

- [ ] **Caso A** — técnica con tarifa parametrizada → línea directa
- [ ] **Caso B** — varios alcances → pide elegir candidato
- [ ] **Caso C** — sin tarifa → genera solicitud de aprobación
- [ ] **Aprobación** — al aprobar, aparece la línea en la cotización
- [ ] **Precio de venta** = costo × markup, y la **línea de setup** cuando aplica

### El PDF, a ojo

La revisión 8 del auditor cuadra las columnas, pero el aspecto se mira. En test hay
una cotización de prueba permanente, **S00474** (cliente `ZZ PRUEBA COLUMNAS PDF`),
armada para ejercitar los **cinco tipos de fila**: sección, subsección, producto con
descuento, nota, resumen de sección colapsada y combo.

- [ ] **Cotización** (`sale.report_saleorder`) — la columna de **Imagen** sale, y
      ninguna fila queda corta ni corrida
- [ ] **Proforma MX** (`sale.report_saleorder_pro_forma`) — igual, con sus dos
      columnas extra (*Product code*, *Unit code*)
- [ ] **Diseño** — si los colores cambiaron, es `res.company.report_tables_id`
      («Table Design»), no una pérdida. Ver la incidencia del [2026-08-16](incidencias/2026-08-16-columna-imagen-cotizacion.md)

> Los PDFs se pueden bajar sin abrir Odoo: `/report/pdf/sale.report_saleorder/474`
> y `/report/pdf/sale.report_saleorder_pro_forma/474` con sesión iniciada.

---

## 5. Integraciones

- [ ] **Sync de proveedores** (XML-RPC + usuario/contraseña, `analysis/supplier-sync/`):
      correr una vez a mano y revisar `ProductSync\logs\`. **XML-RPC se deprecia en
      2027**; un upgrade mayor es el momento de comprobar que sigue vivo
- [ ] **Scripts JSON-2 del repo** (`audit_catalog.py`, `audit_atributos.py`):
      solo lectura, confirman que la API y el token siguen sirviendo
- [ ] **Derivación de técnicas encadenada al sync** — que se dispare sola al terminar
- [ ] **Correo saliente**: que las notificaciones de lead sigan llegando

---

## 6. Cierre

- [ ] Actualizar la tabla **Estado actual** del [README del apartado](README.md)
      (versión y fecha de auditoría de cada base)
- [ ] Si hubo un fallo: **archivo nuevo** en [incidencias/](incidencias/) siguiendo
      el formato del README
- [ ] Si el auditor **no lo detectaba**: agregarle la revisión. Una incidencia que no
      queda automatizada se repite
- [ ] Entrada en `docs/changelog.md`

---

## Antes de un upgrade mayor (19 → 20)

Cuando Odoo avise con anticipación:

1. **Pedir una base de prueba ya migrada** desde el gestor de bases de datos.
2. Correr este checklist completo contra ella.
3. Resolver todo lo bloqueante y **registrarlo en incidencias/** con la nota de
   "aplicar el día del upgrade a producción".
4. Recién entonces, actualizar producción — y volver a correr el checklist.

> ⚠️ **No cuentes con un snapshot descargable**: Odoo Online rechaza el respaldo de
> esta base por tamaño (probado 2026-08-14). Alternativas: duplicar desde el gestor,
> o pedir el respaldo a soporte de Odoo.

---

## Revisión de `saas~19.2` — estado

Test corre `saas~19.2` desde el 2026-08-07; producción sigue en `19.0`. Todo lo
que se encuentre aquí es trabajo adelantado para el día que Odoo suba producción.

| Área | Estado | Notas |
|---|---|---|
| Automático (auditor + los dos `--verificar`) | ✅ limpio | 2026-08-16 |
| Ficha de producto | ✅ resuelto | [incidencia 2026-08-15](incidencias/2026-08-15-ficha-producto-500.md) — pendiente aplicar en prod el día del upgrade |
| Columna de imagen del PDF | ✅ resuelto | [incidencia 2026-08-16](incidencias/2026-08-16-columna-imagen-cotizacion.md) — **ya aplicado también en producción**, antes del upgrade |
| PDF a ojo, 5 tipos de fila (§4) | ✅ validado | Cotización y proforma sobre S00474 |
| Diseño del PDF (colores) | ✅ decidido | Cambia por `report_tables_id`; JC lo deja como quedó |
| Rutas públicas (8 probadas) | ✅ 200 | Incluye 3 fichas reales |
| Sitio web a ojo (§2) | ⏳ **pendiente** | Requiere revisión visual de JC |
| Backend / operación (§3) | ⏳ **pendiente** | |
| Motor — prueba funcional (§4) | ⏳ **pendiente** | La estructura ya sale limpia |
| Integraciones (§5) | ⏳ **pendiente** | |

### Diferencias test vs prod ya explicadas (no investigar de nuevo)

| Diferencia | Explicación |
|---|---|
| 14 vistas cambiaron de key | `website_sale_comparison` se fusionó en `website_sale` en 19.2. Mismos ids, mismo estado |
| `campos_manual` 101 vs 100 | Un campo `x_` de más en `sale.order.line` en test (pruebas del botón por línea) |
| `server_actions_code` 224 vs 205 | Server Actions extra en test, de los ensayos del motor |
| `website.step_wizard` ×3 y `website_sale.filter_products_price` ×2 duplicadas | **Preexistentes: están igual en producción.** No las causó el upgrade. Higiene pendiente, no urgente |
| Vista kanban de `social_twitter` con `t-call` "roto" | Falso positivo ya corregido en el auditor: las vistas de backend resuelven `t-call` contra plantillas OWL de cliente, que no viven en `ir.ui.view` |
