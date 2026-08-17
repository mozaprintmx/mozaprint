# 2026-08-16 · La columna de Imagen desapareció del PDF de cotización

**Versión**: `saas~19.2` (test). **Estado**: ✓ resuelto en test · ⏳ pendiente en producción.

## Síntoma

En el PDF de cotización de test ya no sale la columna de **Imagen** del producto. En
producción (19.0) sigue saliendo. No hubo error, ni vista desactivada, ni traza: la
columna simplemente dejó de existir.

JC ya lo había visto en una actualización anterior, sin identificar la causa.

## Por qué costó verlo

Porque no falla nada: el reporte se genera bien, sin la columna. Ninguna de las
revisiones del auditor lo detectaba — todas buscaban vistas *rotas* o *desactivadas*,
y aquí la vista está sana; lo que cambió es su contenido.

## Causa raíz

La columna se había agregado con **Studio editando en sitio la plantilla del módulo**:
`sale.report_saleorder_document` (id 1025), cuyo registro `ir.model.data` pertenece al
módulo `sale` con `noupdate=False`.

Cada actualización recarga los datos XML de los módulos y **reescribe `arch_db`**. La
personalización vive dentro de ese campo, así que se va con la reescritura. Las fechas
lo confirman:

| Base | `write_date` de la vista 1025 | Contenido |
|---|---|---|
| Producción 19.0 | 2025-11-05 (la edición de Studio) | con `td_image` |
| Test saas~19.2 | **2026-08-07 17:50** = el upgrade | de fábrica, sin `td_image` |

Al editar reportes de módulos estándar Studio **no hace copia-al-escribir** (a
diferencia de las vistas de website, que se duplican por-website): modifica el original
y guarda una copia inerte con key `web_studio.__backup__._1025_.…`. Esa copia no
participa en el render; solo delata que hubo edición in-place.

Contraste útil: la vista que inyecta el botón «Agregar personalización» en ventas es
**propia y heredada**. Un upgrade no la reescribe; a lo mucho la desactiva si el xpath
deja de resolver — fallo ruidoso y detectable, no pérdida silenciosa.

## Hallazgos de paso

Al auditar la tabla de líneas aparecieron descuadres **que ya existían en producción**,
independientes del upgrade:

| Reporte | Fila | Faltan |
|---|---|---|
| Cotización | `tr_combo`, `tr_section_group` | 1 columna |
| Proforma MX | `tr_section` | 2 columnas |
| Proforma MX | `tr_combo`, `tr_section_group` | 3 columnas |

Los 2 de la proforma son **bug de fábrica de `l10n_mx_edi_sale`**: agrega las columnas
*Product code* y *Unit code* al encabezado y a la fila de producto, y nunca ajusta el
`colspan` de las demás filas. Se comprueba solo: en test, **antes** de instalar nada,
la proforma ya salía descuadrada por 2.

## Reparación

`scripts/deploy_reporte_cotizacion.py` — idempotente, dry-run por defecto.

Crea dos **vistas propias heredadas**, que el upgrade no reescribe:

| Vista | Qué hace |
|---|---|
| `mozaprint.report_saleorder_imagen` | La columna de Imagen |
| `mozaprint.report_saleorder_proforma_columnas` | Cuadra las 2 columnas de l10n_mx |

El diseño evita **toda aritmética de `colspan`**: por cada columna que se agrega al
encabezado y a la fila de producto, se agrega **una celda vacía** a las demás filas
(`tr_section`, `tr_combo`, `tr_section_group`; `tr_note` usa `colspan="99"` y es
inmune). La fórmula del `colspan` y hasta la estructura de la fila de combo cambian
entre 19.0 y 19.2 — las celdas vacías no dependen de ninguna de las dos.

Con `--limpiar-base` quita además la columna que Studio dejó incrustada en la plantilla
del módulo. Sin eso, con las vistas nuevas activas **la columna saldría duplicada**.

⚠️ La limpieza se hace **idioma por idioma**: `arch_db` es un campo traducido y en
producción la edición de Studio está tanto en `en_US` como en `es_419`. Limpiar uno solo
dejaría el PDF duplicado para los clientes que lo reciban en el otro idioma.

## ¿Aplica a producción?

**Sí, y conviene aplicarlo antes del upgrade**, no el día del upgrade. Motivos:

1. Arregla descuadres que producción **ya tiene hoy** (tabla de arriba).
2. Los 5 anclajes que usan las vistas existen igual en 19.0 y en saas~19.2 — verificado
   contra ambas bases, la misma vista sirve para las dos.
3. Cuando Odoo suba producción a 19.2, la plantilla del módulo se reescribirá otra vez,
   pero ya sin nada que perder: la columna vivirá en vistas propias.

```bash
python scripts/deploy_reporte_cotizacion.py --target prod --apply --si-produccion --limpiar-base
python scripts/deploy_reporte_cotizacion.py --target prod --verificar
```

Revertible con `--rollback` (manifiesto en `backups/`, incluye el `arch` previo por idioma).

## Cómo se detecta automáticamente

Dos revisiones nuevas en `scripts/audit_post_upgrade.py`:

- **[7] Vistas de módulo editadas in-place por Studio** — busca los respaldos
  `web_studio.__backup__._<id>_.*`. Aviso, no fallo: delata el patrón que causa esta
  pérdida silenciosa, sea en esta vista o en otra.
- **[8] Cuadre de columnas del reporte** — suma las columnas de cada fila del arch
  combinado en los cuatro escenarios de descuento/impuestos y las compara con el
  encabezado. Es el invariante de verdad: no "existe la columna", sino "ninguna fila
  queda corta".

## No relacionado, encontrado al validar

- **El diseño del PDF cambia en 19.2**: campo nuevo `res.company.report_tables_id`
  («Table Design»), que el upgrade deja en `Striped`. Ese estilo tiñe la fila de sección
  con el **color secundario** de la compañía (#006b4d) en vez del gris de 19.0. No se
  perdió nada; es un ajuste. `Light` es el único valor sin reglas de tabla, o sea el
  más parecido a 19.0. **JC revisó las opciones y decidió dejarlo como está.**
- **Cotización y proforma usan motores de PDF distintos** — la cotización el motor
  propio de Odoo, la proforma `wkhtmltopdf 0.12.6.1`. El reparto es **idéntico en 19.0 y
  en 19.2**, así que no lo trajo el upgrade. Se nota con descripciones largas: ante una
  fila más alta que el espacio restante, el motor de Odoo la empuja entera a la hoja
  siguiente (hueco blanco) y wkhtmltopdf la parte. El disparador es el largo de
  `description_sale`: con 793 caracteres el PDF sale en 3 páginas y con 60 en 1, en los
  dos reportes.
