# Revisión de saas~19.2 — qué cambia y qué probamos

> Fecha: 2026-08-16/17. Test corre `saas~19.2` desde el 2026-08-07; producción sigue
> en `19.0` y **el upgrade se pide a mano** (Odoo no lo agenda solo en esta base).
> Este documento es el trabajo adelantado: qué trae la versión, qué reportan otros,
> y qué se midió contra nuestras bases.

## De dónde salió

- Notas oficiales: <https://www.odoo.com/odoo-19-2-release-notes> — 19.1 y 19.2 son
  **exclusivas de Odoo Online**; on-premise y Odoo.sh las reciben en la anual.
- Foro de Odoo: reportes de otros usuarios tras el salto a 19 / 19.2.
- **Diff empírico entre nuestras dos bases**, que es lo que de verdad decide.

## Lo que trae, acotado a lo que usamos

- **eCommerce**: impedir venta a nivel categoría manteniendo el precio visible;
  categorías excluibles de /shop; SEO con `srcset` adaptativo y anti-contenido
  duplicado en páginas paginadas; opciones de tema y fondo unificadas.
- **CRM**: distribución de leads con tres reglas de asignación; generación de leads
  pasó de Clearbit a Dun & Bradstreet; el autocompletado **ya no agrega la industria
  como etiqueta**.
- **Contabilidad**: estados de pago renombrados (ver abajo, sí nos toca).
- **Studio**: las automatizaciones ahora pueden disparar planes de actividad.
- Se descontinúan Field Service y el consumo flexible en fabricación — no los usamos.

## Lo que reportan en foros

Vale la pena saber que **la incidencia de las fichas de producto no fue solo nuestra**:
hay reportes de usuarios «atascados en saas-19.2 sin poder ver la vista web de
productos, con Internal Server Error», y otro de error 500 renderizando
`website_sale.product_title`. El patrón coincide con el nuestro: **vistas heredadas o
temas que referencian plantillas renombradas** (ver
[incidencia 2026-08-15](incidencias/2026-08-15-ficha-producto-500.md)).

Otros reportes del foro, contrastados contra nuestras bases: plantillas de correo
fallando, pérdida del segundo número telefónico en contactos, precios de variante que
no se actualizan en /shop, y módulos custom rompiéndose por herencia de vistas.
**Ninguno se reprodujo aquí** — el detalle está más abajo.

---

## Campos que 19.2 quitó o renombró

Del diff completo (18,388 campos en prod vs 18,998 en test): **406 quitados, 1,016
nuevos**. Estos son los que tocan modelos que usamos:

| Antes (19.0) | Ahora (saas~19.2) | ¿Nos afecta? |
|---|---|---|
| `product.supplierinfo.product_uom_id` | **`uom_id`** | El sync escribe supplierinfo — hoy no usa ese campo, pero ojo al agregarlo |
| `stock.quant.product_uom_id` | **`uom_id`** | Igual, para el stock_sync |
| `res.partner.company_type` | eliminado (queda `is_company`) | No lo usa nuestro código |
| `res.partner.company_name` | eliminado | No lo usa nuestro código |
| `website.prevent_zero_price_sale` | `prevent_sale` + `prevent_sale_for` | **Migró bien**: sigue activo con `prevent_sale_for='zero_price'` |
| `website.contact_us_button_url` | `contact_us_link_url` | No lo usamos |
| `product.template.attribute.value.exclude_for` | `excluded_value_ids` | No lo usamos |
| `crm.lead.email_cc` | eliminado | No lo usamos |
| `res.company.layout_background` | eliminado (opciones de tema unificadas) | Ver diseño del PDF |

**Módulos**: desaparecen 8 (`website_sale_comparison` fusionado en `website_sale`,
`hr_homeworking`, `hr_hourly_cost`, `hr_org_chart`, `iot_base`, `theme_common`,
`sale_project_stock_account`). Llegan 16, de los cuales **7 son de IA** (`ai_sale`,
`ai_stock`, `ai_project`, `ai_purchase`, `ai_calendar`, `ai_mass_mailing`,
`ai_sale_stock`).

## Tres cambios de comportamiento que sí nos tocan

### 1. Los estados de pago cambiaron de significado

`in_process` desapareció. La migración mapeó:

| Prod 19.0 | Test 19.2 |
|---|---|
| `in_process` (8 pagos) | → **`paid`** |
| `paid` (3 pagos) | → **`reconciled`** |

No se perdió nada, pero **«Pagado» ya no implica conciliado**. Si algún criterio
operativo lee ese estado, hay que ajustarlo.

### 2. Veinte categorías del eCommerce quedaron despublicadas

`product.public.category.is_published` es **campo nuevo**. Tras la migración, 20 de
388 categorías quedaron sin publicar. Revisadas una por una: **19 están vacías** y solo
**JARDINERIA** tiene 1 producto, que dejaría de aparecer en /shop. Impacto mínimo,
pero es una decisión a tomar.

### 3. El diseño del PDF cambia de colores

`res.company.report_tables_id` («Table Design») es **campo nuevo**, y el upgrade lo
deja en **`Striped`**. Ese estilo tiñe la fila de sección con el **color secundario**
de la compañía (#006b4d) en vez del gris de 19.0, y el zebra pasa a ser verde claro.

No se perdió nada: es un ajuste con seis valores (`Light`, `Boxed`, `Bold`, `Striped`,
`Bubble`, `Column`). **`Light` es el único sin reglas de tabla**, o sea el más parecido
a 19.0. **JC revisó las opciones y decidió dejarlo como quedó.**

---

## Lo que se probó, y con qué resultado

| Prueba | Resultado |
|---|---|
| Campos custom `x_` perdidos | **0** |
| Vistas que el upgrade desactivó | **0** |
| Automatizaciones | 4/4, idénticas en trigger y dominio |
| Plantillas de correo | ninguna faltante · **render de 5 plantillas: 0 marcadores sin resolver** |
| Formulario web → lead → automatización → correo | ✅ end-to-end |
| Rutas públicas | 8/8 en 200, incluidas 3 fichas reales |
| **Sync de proveedores contra 19.2** | stock: 4,477 productos, **0 errores** · productos: 195 procesados, **0 errores** |
| XML-RPC y JSON-2 | ambas responden igual en las dos bases |
| Precio por variante en /shop (bug del foro) | el endpoint devuelve lo mismo en 19.0 y 19.2 |
| PDF de cotización y proforma | columna de imagen y filas cuadradas |

El sync se probó con el **código de producción** (`sync_odoo_paquete_v2`) apuntado a
TEST vía `ODOO_URL`/`ODOO_DB`, verificando el override **antes** de ejecutar para no
arrancarlo contra producción por accidente.

### Diferencia que NO es del upgrade

Test tiene 14 atributos y prod 9. Los 5 de más (`age group`, `brand`, `color`,
`manufacturer`, `pattern`) son los atributos basura que se **borraron en prod después**
de copiar test. No es regresión.

---

## El correo saliente no se puede probar en TEST

Hallazgo que cambia el procedimiento: la base de test tiene el correo
**neutralizado por Odoo**:

```
ir.mail_server: 'neutralization - disable emails'  ·  smtp_host: 'invalid'  ·  puerto 1025
```

Es lo que Odoo Online hace al duplicar una base, para que una copia no le escriba a
clientes reales. Bien por seguridad, pero significa que **la entrega de correo solo se
verifica en producción, después del upgrade** — no se puede adelantar.

Lo que sí se probó en TEST es el **render** de las plantillas, que es el fallo que
reporta el foro: se genera el `mail.mail` sin enviarlo (`force_send=False`), se
inspecciona y se borra.

---

## Runbook del día del upgrade

Pedir la actualización **en horario de bajo tráfico y con JC presente**, porque hay una
**caída garantizada**: las fichas de producto darán 500 hasta que corra el fix. Está
verificado que **no se puede pre-aplicar** — en 19.0 esas vistas aún no tienen
`inherit_id`; es el upgrade quien se lo pone.

```bash
# 1. PRIMERO: reparar las fichas de producto
python scripts/fix_vista_terminos_producto.py --target prod --apply --si-produccion

# 2. Salud general
python scripts/audit_post_upgrade.py --target prod

# 3. PDF de cotización
python scripts/deploy_reporte_cotizacion.py --target prod --verificar

# 4. Que no se haya colado código facturable
python scripts/audit_lineas_facturables.py --target prod
```

Después, a mano:

- [ ] Abrir una ficha de producto en el sitio
- [ ] **Enviar un correo de prueba real** — el único punto que no se pudo adelantar
- [ ] Revisar los estados de pago: ahora dicen «Pagado» donde antes «En proceso»
- [ ] Decidir si se republica la categoría JARDINERIA
- [ ] §2–§5 del [checklist](checklist-post-upgrade.md)

## Riesgo de fondo que no se elimina con pruebas

**No hay respaldo descargable**: Odoo Online rechaza el backup de esta base por tamaño
(probado 2026-08-14). Si algo sale mal, el rollback pasa por soporte de Odoo. Ninguna
prueba previa cambia eso — es un factor a ponderar, no a resolver.
