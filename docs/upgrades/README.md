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
| [motor-cotizacion.md](motor-cotizacion.md) | Procedimiento específico del motor de cotización: qué es frágil, reparación por síntoma, reconstrucción desde cero |
| [incidencias/](incidencias/) | Un archivo por fallo real, con causa raíz y reparación. Se consultan por síntoma |

## Estado actual

| Base | Versión | Última auditoría | Resultado |
|---|---|---|---|
| Producción `mozaprintmx.odoo.com` | **19.0** | 2026-08-16 | ✓ limpia (tras mover la columna de imagen a vistas propias) |
| Test `mozaprintmx-test-saas19-0807.odoo.com` | **saas~19.2** | 2026-08-16 | ✓ limpia (tras reparar la ficha de producto y la columna de imagen) |

**Test va una versión adelante de producción.** Eso no es un accidente: es el
mejor activo que tenemos para estos upgrades. Cada fallo que aparece en test es
un fallo que producción va a tener cuando Odoo la suba a 19.2, con semanas o
meses de anticipación para resolverlo.

> ⚠️ Corolario: **no reparar en producción lo que solo falla en 19.2.** El fix de
> la ficha de producto, aplicado hoy en producción (19.0), rompería lo que
> funciona: ahí esa vista todavía debe ser plantilla independiente. Esas
> reparaciones se aplican **el día del upgrade**, no antes.
>
> Pero no todo hallazgo es de ese tipo. Si el arreglo **funciona igual en las dos
> versiones** y además corrige algo que producción ya tiene mal, conviene aplicarlo
> **antes** — es el caso de la columna de imagen del PDF (2026-08-16). La pregunta
> correcta no es "¿ya actualizamos?", sino "¿este cambio es válido en 19.0?".
> Cada incidencia lo dice explícitamente en *¿Aplica a producción?*.

## Incidencias registradas

| Fecha | Síntoma | Versión | Estado |
|---|---|---|---|
| [2026-08-15](incidencias/2026-08-15-ficha-producto-500.md) | Internal Server Error en **todas** las fichas de producto | saas~19.2 | ✓ resuelto en test · ⏳ pendiente aplicar en prod el día del upgrade |
| [2026-08-16](incidencias/2026-08-16-columna-imagen-cotizacion.md) | Desapareció la columna de **Imagen** del PDF de cotización | saas~19.2 | ✓ **resuelto en test y en producción** — se aplicó antes del upgrade porque arreglaba descuadres ya existentes |

> Las dos incidencias son la misma lección con distinta cara: **lo que Studio edita
> dentro de una vista de módulo, el upgrade lo pisa**. La diferencia es que la primera
> falla ruidosamente (500) y la segunda en silencio.

## Los dos comandos

```bash
# Salud general: sitio web, vistas, metadatos custom  (solo lectura)
python scripts/audit_post_upgrade.py --target test
python scripts/audit_post_upgrade.py --comparar        # test vs prod, lado a lado

# Salud del motor de cotización  (solo lectura)
python scripts/deploy_motor_cotizacion.py --target test --verificar

# Salud del PDF de cotización: columna de imagen y cuadre de columnas  (solo lectura)
python scripts/deploy_reporte_cotizacion.py --target test --verificar
```

Los tres son de solo lectura y salen con código 1 si encuentran algo. Se
complementan: el primero cubre el sitio y las vistas, el segundo el motor de
cotización y el tercero el PDF.

## Cómo se registra una incidencia nueva

Un archivo en `incidencias/` con nombre `AAAA-MM-DD-sintoma-corto.md` y estas
secciones: **síntoma** (lo que ve el usuario), **por qué costó verlo** (si
aplica), **causa raíz**, **reparación**, **¿aplica a producción?** y **cómo se
detecta automáticamente** (qué revisión del auditor lo cacha — y si ninguna, ese
es el trabajo pendiente: agregarla).

Después: alta en la tabla de arriba y entrada en `docs/changelog.md`.
