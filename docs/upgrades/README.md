# Upgrades de Odoo — seguimiento

> Todo lo relacionado con actualizaciones de Odoo Online vive aquí: qué revisar,
> qué se rompió antes, y cómo se reparó. Odoo Online actualiza **cuando ellos
> deciden**; nosotros no elegimos la fecha, solo qué tan preparados llegamos.

## Por qué existe este apartado

Mozaprint corre sobre Odoo Online: no hay `addons/`, no hay control de versión
del código de Odoo, y no hay entorno donde probar el upgrade antes de que ocurra
— salvo la base de test. Toda nuestra extensión son **datos** dentro de la base
(campos `x_`, Server Actions, vistas). Un upgrade no los borra, pero **sí puede
dejarlos inconsistentes con el código nuevo de Odoo**, y ahí es donde duele.

El incidente del 2026-08-15 es el caso de manual: el salto a `saas~19.2` convirtió
una vista de plantilla independiente a vista heredada, dejó nuestra copia
traducida con el formato viejo, y **tumbó las 5,000+ fichas de producto con un
500**. No hubo aviso, no hubo traza en los logs, y `/shop` seguía respondiendo
200 — el catálogo se veía sano desde fuera.

## Contenido

| Documento | Para qué |
|---|---|
| [checklist-post-upgrade.md](checklist-post-upgrade.md) | **Empieza aquí** tras cualquier actualización. Qué revisar, en qué orden y con qué comando |
| [revision-saas-19-2.md](revision-saas-19-2.md) | **Antes del upgrade a 19.2**: qué cambia, campos renombrados, los 3 cambios de comportamiento, qué se probó y el runbook del día |
| [motor-cotizacion.md](motor-cotizacion.md) | Procedimiento del motor de cotización. ⚠️ **El motor se retiró de producción el 2026-08-17** (ver [ADR 007](../../decisions/007-retiro-motor-cotizacion-costo-codigo.md)); vale solo si se reconstruye |
| [incidencias/](incidencias/) | Un archivo por fallo real, con causa raíz y reparación. Se consultan por síntoma |

## Estado actual

| Base | Versión | Última auditoría | Resultado |
|---|---|---|---|
| Producción `mozaprintmx.odoo.com` | **saas~19.2** | 2026-08-17 | ✓ limpia (tras reparar la ficha de producto; el PDF sobrevivió solo) |
| Test `mozaprintmx-test-saas19-0807.odoo.com` | **saas~19.2** | 2026-08-16 | ✓ limpia (tras reparar la ficha de producto y la columna de imagen) |

**Las dos bases van parejas desde el 2026-08-17.** Se pierde el margen de aviso
anticipado hasta que Odoo libere la siguiente versión y test la tome primero.

**Test va una versión adelante de producción.** Eso no es un accidente: es el
mejor activo que tenemos para estos upgrades. Cada fallo que aparece en test es
un fallo que producción va a tener cuando Odoo la suba a 19.2, con semanas o
meses de anticipación para resolverlo.

> ⚠️ Corolario: **no reparar en producción lo que solo falla en la versión nueva.**
> El fix de la ficha de producto, aplicado en producción mientras corría 19.0,
> habría roto lo que funcionaba: ahí esa vista todavía debía ser plantilla
> independiente. Se aplicó **el día del upgrade** (2026-08-17) y funcionó a la
> primera — la estrategia se validó en la práctica.
>
> Pero no todo hallazgo es de ese tipo. Si el arreglo **funciona igual en las dos
> versiones** y además corrige algo que producción ya tiene mal, conviene aplicarlo
> **antes** — es el caso de la columna de imagen del PDF (2026-08-16). La pregunta
> correcta no es "¿ya actualizamos?", sino "¿este cambio es válido en 19.0?".
> Cada incidencia lo dice explícitamente en *¿Aplica a producción?*.

## Incidencias registradas

| Fecha | Síntoma | Versión | Estado |
|---|---|---|---|
| [2026-08-15](incidencias/2026-08-15-ficha-producto-500.md) | Internal Server Error en **todas** las fichas de producto | saas~19.2 | ✓ **resuelto en test y en producción** — el fix preparado en test se aplicó el día del upgrade (2026-08-17) |
| [2026-08-16](incidencias/2026-08-16-columna-imagen-cotizacion.md) | Desapareció la columna de **Imagen** del PDF de cotización | saas~19.2 | ✓ **resuelto en test y en producción** — se aplicó antes del upgrade porque arreglaba descuadres ya existentes |

> Las dos incidencias son la misma lección con distinta cara: **lo que Studio edita
> dentro de una vista de módulo, el upgrade lo pisa**. La diferencia es que la primera
> falla ruidosamente (500) y la segunda en silencio.

## Los tres comandos

```bash
# 1. Salud general: sitio web, vistas, metadatos custom  (solo lectura)
python scripts/audit_post_upgrade.py --target test
python scripts/audit_post_upgrade.py --comparar        # test vs prod, lado a lado

# 2. Salud del PDF de cotización: columna de imagen y cuadre de columnas
python scripts/deploy_reporte_cotizacion.py --target test --verificar

# 3. Que no se haya colado código que Odoo factura
python scripts/audit_lineas_facturables.py --target test
```

Los tres son de solo lectura y salen con código 1 si encuentran algo. Se
complementan: el primero cubre el sitio y las vistas, el segundo el PDF, y el
tercero vigila que no reaparezca código facturable (ver
[ADR 007](../../decisions/007-retiro-motor-cotizacion-costo-codigo.md)).

> El cuarto comando histórico, `deploy_motor_cotizacion.py --verificar`, solo aplica
> si algún día se reconstruye el motor: se retiró de producción el 2026-08-17.

## Cómo se registra una incidencia nueva

Un archivo en `incidencias/` con nombre `AAAA-MM-DD-sintoma-corto.md` y estas
secciones: **síntoma** (lo que ve el usuario), **por qué costó verlo** (si
aplica), **causa raíz**, **reparación**, **¿aplica a producción?** y **cómo se
detecta automáticamente** (qué revisión del auditor lo cacha — y si ninguna, ese
es el trabajo pendiente: agregarla).

Después: alta en la tabla de arriba y entrada en `docs/changelog.md`.
