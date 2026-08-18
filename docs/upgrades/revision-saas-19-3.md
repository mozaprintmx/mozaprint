# Revisión de saas~19.3 — qué cambia y qué probamos

> **Producción corre `saas~19.2`** (subió el 2026-08-17). **Test corre `saas~19.3`**
> (base `mozaprintmx-test-saas19-0818`, creada el 2026-08-18). Volvemos a tener el
> margen de aviso anticipado que se había perdido cuando las dos bases quedaron parejas.
>
> Este documento es el equivalente de [revision-saas-19-2.md](revision-saas-19-2.md)
> para el salto **19.2 → 19.3**: qué cambió, qué probamos contra la base real, qué se
> rompe, y el runbook del día.

## De dónde salió

- **Notas oficiales**: [Odoo 19.3 Release Notes](https://www.odoo.com/odoo-19-3-release-notes).
- **Diff de esquema contra las bases reales**: módulos, campos, selecciones y vistas de
  prod (19.2) contra test (19.3), vía XML-RPC. Es la fuente que manda — las notas
  oficiales no mencionan nada de lo que de verdad nos rompió.
- **Foros**: los reportes de problemas con 19.x siguen siendo del mismo tipo (herencias
  de vistas que dejan de resolver, módulos custom, reconfiguración post-upgrade). Nada
  específico de 19.3 que nos aplique.

## El resumen en una línea

**Un solo fallo real, y es exactamente el mismo patrón que en 19.2**: una copia nuestra
de una plantilla de Odoo se quedó llamando a un método que 19.3 movió de sitio. Todo lo
demás pasó limpio.

---

## Lo que se rompe: `/contactanos` devuelve 500

> ✓ **Resuelto en test el 2026-08-18** con `scripts/fix_vista_contactanos.py`.
> Detalle completo en la [incidencia](incidencias/2026-08-18-contactanos-500.md).
> Pendiente aplicarlo en producción **el día del upgrade**.

**Severidad: alta.** Es el formulario que alimenta el CRM (Fase 1). El resto del sitio
—incluidas **las 5,012 fichas de producto**— está perfecto; en 19.3 no se repite el
fallo de 19.2.

```
AttributeError: 'website.visitor' object has no attribute '_get_visitor_from_request'
Template: website.contactanos · Reference: 4122
Element: <t t-set="logged_partner"
            t-value="request.env['website.visitor']._get_visitor_from_request().partner_id"/>
```

**Causa raíz**: el método `_get_visitor_from_request()` **se mudó del modelo
`website.visitor` al modelo `ir.http`**.

| Vista | Qué es | 19.2 | 19.3 |
|---|---|---|---|
| **2335** `website.contactus` | La genérica de Odoo | `env['website.visitor']…` | ✅ migrada a `env['ir.http']…` |
| **4122** `website.contactanos` | **Nuestra copia por-website** | `request.env['website.visitor']…` | ❌ **sin tocar** → 500 |

Odoo migró su plantilla y no miró la nuestra. La copia existe porque en su día se
tradujo/renombró la página desde el editor del sitio (mecanismo COW).

**Es la tercera vez que nos pasa lo mismo** (ficha de producto en 19.2, columna de
imagen del PDF, y ahora esto). El riesgo nunca está en lo que Odoo trae de fábrica ni
en nuestros campos `x_`: está en **lo que personalizamos encima de algo que Odoo
después reestructura**.

### La reparación

Cambiar en la vista 4122 el modelo sobre el que se llama el método:

```diff
- request.env['website.visitor']._get_visitor_from_request().partner_id
+ request.env['ir.http']._get_visitor_from_request().partner_id
```

⚠️ **NO aplicar en producción hoy.** En 19.2 el método vive en `website.visitor` —lo
confirma la propia vista genérica de Odoo en producción, que ahí lo llama así—, de modo
que el cambio rompería lo que hoy funciona. **Va el día del upgrade**, igual que el fix
de la ficha de producto.

### Por qué el auditor casi no lo caza

El fallo de 19.2 era **estructural** (una vista heredada sin `position`/`xpath`) y lo
cazaba la revisión **[1]**. Este es un **error de ejecución**: la vista combina perfecto
y revienta al renderizar. Ninguna revisión estática lo ve.

Lo detectó el **barrido HTTP [5]** — y solo porque `/contactanos` estaba en su lista fija
de rutas. Si el fallo hubiera caído en `/nosotros` o en un catálogo, habría pasado
inadvertido hasta que un cliente se topara con él.

✓ **Corregido**: la revisión [5] ahora barre **todas las `website.page` publicadas**
además de las rutas fijas y 3 fichas reales. Pasó de 8 rutas a **26** en esta base.

---

## Lo que cambia y sí nos toca

### 1. El PDF de cotización ahora trae imagen de producto NATIVA

19.3 agrega la imagen del producto al reporte de venta, con interruptor
`res.company.display_product_images_on_so` («Display Product Images»).

**No es una columna**: la dibuja **dentro de la celda de descripción**, en flex con el
nombre:

```xml
<td name="td_product_name">
  <div class="d-flex align-items-start">
    <img t-if="doc.company_id.display_product_images_on_so and line.product_id.image_128" …/>
```

**Hoy el interruptor está en `False`**, así que no hay conflicto: nuestra columna propia
(`th_image`/`td_image`, vistas **5062** y **5063**) sigue siendo la única. Pero es un
**conflicto latente**: si alguien activa esa opción en Ajustes, **la imagen sale dos
veces** — una en nuestra columna y otra pegada al nombre.

> **Decisión pendiente para JC**, no urgente: adoptar la nativa y retirar nuestras dos
> vistas (cero mantenimiento, alineado con el principio del
> [ADR 007](../../decisions/007-retiro-motor-cotizacion-costo-codigo.md)), o conservar la
> nuestra —que ya sobrevivió dos upgrades sin tocarla— y dejar el interruptor apagado a
> propósito. La nativa **no** da columna con encabezado «Imagen»; es otro diseño, no el
> mismo con menos trabajo.

### 2. Dos módulos de la localización mexicana desaparecen

| Módulo | En 19.2 | En 19.3 |
|---|---|---|
| `l10n_mx_reports_closing` — *Month 13 Trial Balance* | instalado | **no existe** |
| `l10n_mx_xml_polizas` — *XML Pólizas Export* | instalado | **no existe** |

`l10n_mx_reports` sigue instalado, y las notas oficiales de 19.3 mencionan reportes
mexicanos nuevos (balance NIF B-6, estado de resultados NIF B-3, y **generación del XML
de balanza complementaria**). Todo apunta a que la funcionalidad **se absorbió** en
`l10n_mx_reports`, no a que se perdiera.

> ⚠️ **Verificar en test antes de subir producción**: que el **XML de pólizas** (lo que
> pide el SAT) siga saliendo desde Contabilidad → Reportes. Es obligación fiscal; no se
> descubre el día que se necesita.

### 3. Ocho módulos nuevos, tres de ellos de AI

Nuevos en 19.3: `ai_html_builder`, `ai_product`, `ai_website_sale`, `mail_tracking`,
`hr_calendar_google`, `pos_sale_stock`, `pos_stock`, `pos_stock_enterprise`.

Los tres `ai_*` son de mirar con calma: `ai_product` y `ai_website_sale` tocan justo el
catálogo y la tienda. No hacen nada sin configurarse, pero conviene saber que están.

---

## Campos que 19.3 quitó, y si nos afectan

De los **235 campos quitados**, 43 caen en modelos que sí usamos. Los que valía la pena
revisar:

| Campo quitado | Modelo | ¿Nos afecta? |
|---|---|---|
| `social_facebook`, `social_instagram`, `social_linkedin`, `social_twitter`, `social_youtube`, `social_tiktok`, `social_github`, `social_discord` | `website` | **No.** Las 6 vistas que los usan son de Odoo y Odoo las migró. Ninguna copia nuestra los toca |
| `amount_undiscounted` | `sale.order` | **No.** Ninguna vista nuestra lo referencia |
| `expense_policy`, `service_to_purchase`, `visible_expense_policy` | `product.template` / `product.product` | **No.** No los usamos |
| `followup_*`, `unpaid_invoice_ids`, `im_status`, `is_pickup_location` | `res.partner` / `res.users` | **No** |
| `l10n_mx_edi_force_pue_payment_needed` | `account.move` / `account.payment` | **No** directamente, pero va con el punto 2 de arriba |

**Campos manuales `x_` perdidos: 0.** Los 51 campos y 2 modelos custom están completos,
igual que las 4 automatizaciones del CRM y nuestras 2 vistas del PDF.

### Selecciones que cambiaron de valores

| Campo | Cambio | Impacto |
|---|---|---|
| `account.move.review_state` | valor nuevo `no_review` | Ninguno hoy |
| `product.template.service_tracking` y `sale.order.line.service_tracking` | valor nuevo `subcontract` | Ninguno hoy — **pero es interesante** para el diseño nativo de personalización, donde la maquila externa es un caso real |
| `product.template.tracking` | solo cambió el orden | Cosmético |

---

## Lo que se probó, y con qué resultado

Todo contra `mozaprintmx-test-saas19-0818` (`saas~19.3+e`), duplicado de producción:
**5,387 productos, 5,012 publicados, 128 tarifas, 20 técnicas**.

| Prueba | Resultado |
|---|---|
| Auditor de salud general | ✗ **1 bloqueante**: `/contactanos` en 500 → ✓ limpio tras el fix |
| Vistas heredadas sin especificación de herencia | ✓ ninguna — no se repite el fallo de 19.2 |
| `t-call` a plantillas inexistentes | ✓ ninguna |
| **Fichas de producto** | ✓ 200 — el fix de 19.2 aguantó el salto |
| Barrido de **las 24 páginas publicadas** | 22/24 antes del fix → ✓ **24/24** después |
| **PDF de cotización y proforma** | ✓ vistas 5062/5063 activas, plantilla del módulo limpia, columnas cuadradas e imagen presente en los 4 casos (2 reportes × 2 idiomas) |
| **Líneas facturables** | ✓ 0 líneas / 0 bloques |
| Campos `x_`, modelos custom, automatizaciones | ✓ completos (51 campos, 2 modelos, 4 automatizaciones activas) |
| XML-RPC y JSON-2 | ✓ funcionan |

### Pendiente de probar en test

- [ ] **XML de pólizas / balanza** (punto 2 de arriba) — obligación fiscal
- [ ] Rearmar la **cotización de prueba de los 5 tipos de fila**. La S00474 vivía en la
      base de test vieja (0807), que Odoo eliminó al caducar; la base nueva es copia de
      producción y no la tiene
- [ ] **Correo saliente**: igual que en 19.2, Odoo neutraliza el SMTP en las bases
      duplicadas (`smtp_host: 'invalid'`), así que **no se puede probar en test**. Se
      valida en producción después del upgrade
- [ ] Sitio y backend a ojo (§2 y §3 del [checklist](checklist-post-upgrade.md))

---

## Runbook del día del upgrade

```bash
# 1. PRIMERO: reparar /contactanos (el formulario del CRM)
python scripts/fix_vista_contactanos.py --target prod                      # simulacro
python scripts/fix_vista_contactanos.py --target prod --apply --si-produccion

# 2. Salud general (incluye el barrido HTTP)
python scripts/audit_post_upgrade.py --target prod

# 3. PDF de cotización
python scripts/deploy_reporte_cotizacion.py --target prod --verificar

# 4. Que no se haya colado código facturable
python scripts/audit_lineas_facturables.py --target prod
```

Después: el [checklist post-upgrade](checklist-post-upgrade.md) de arriba abajo, y
verificar el XML de pólizas.

> **Recordatorio de la lección de 19.2**: `arch_db` es un campo **traducido**. Cualquier
> reparación que lo escriba debe iterar los idiomas (`en_US` primero, luego los activos).
> Escribir solo el de la sesión deja el sitio roto para el visitante con el backend
> viéndose bien.

## Riesgo de fondo que no se elimina con pruebas

El mismo de siempre, y ya van tres repeticiones: **cada texto o página que
personalizamos desde el editor del sitio crea una copia por-website que el upgrade migra
peor que el original**. Cuantas menos copias haya, menos superficie de fallo.

Vale la pena inventariar esas copias y preguntarse, una por una, si la personalización
justifica el riesgo. Es trabajo de higiene, no urgente, pero es la única medida que ataca
la causa en vez del síntoma.
