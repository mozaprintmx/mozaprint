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
| [revision-saas-19-3.md](revision-saas-19-3.md) | **Antes del upgrade a 19.3**: qué cambia, qué se rompe, la imagen nativa del PDF, los módulos mexicanos y el runbook del día |
| [revision-saas-19-2.md](revision-saas-19-2.md) | Histórico del salto a 19.2, ya aplicado en producción el 2026-08-17 |
| [motor-cotizacion.md](motor-cotizacion.md) | Procedimiento del motor de cotización. ⚠️ **El motor se retiró de producción el 2026-08-17** (ver [ADR 007](../../decisions/007-retiro-motor-cotizacion-costo-codigo.md)); vale solo si se reconstruye |
| [incidencias/](incidencias/) | Un archivo por fallo real, con causa raíz y reparación. Se consultan por síntoma |

## Estado actual

| Base | Versión | Última auditoría | Resultado |
|---|---|---|---|
| Producción `mozaprintmx.odoo.com` | **saas~19.3** | 2026-09-22 | ✓ limpia — las cinco auditorías (`checklist_upgrade.py`) |
| Test (la vigente vive en `ODOO_TEST_URL`) | **saas~19.3** | 2026-09-22 | ✓ limpia — hoy es `mp-watest`, **caduca el 2026-09-24** |

> ⚠️ **La base de test es desechable.** Es un duplicado de producción en modo *trial*: dura
> unos 15 días y Odoo la elimina. Ya pasó dos veces (`…-0807` → `…-0818` → `mp-watest`). Por
> eso ningún documento debe depender de su nombre: **la vigente es siempre la de
> `ODOO_TEST_URL`** en `analysis/supplier-sync/.env` (gitignored).
>
> **Antes del próximo upgrade —o de cualquier cambio que vaya a tocar producción—**: duplicar
> producción desde el gestor de bases de Odoo, actualizar `ODOO_TEST_URL` y comprobar con
> `python scripts/checklist_upgrade.py --target test`. Sin base de test no hay dónde validar, y
> la regla de "no desplegar directo a producción" se queda sin sustento.
>
> Ojo al duplicar: la copia va **neutralizada** (sin credenciales de pago ni correo saliente).
> Para probar cobros hay que instalar `payment_demo` **solo ahí**.

**Las dos bases van parejas otra vez** desde el 2026-08-22. Se pierde el aviso
anticipado hasta que Odoo libere la siguiente versión y test la tome primero.
Revisión de la versión: [revision-saas-19-3.md](revision-saas-19-3.md).

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
| [2026-08-18](incidencias/2026-08-18-contactanos-500.md) | Internal Server Error en **/contactanos** (el formulario del CRM) | saas~19.3 | ✓ **resuelto en test y en producción** — aplicado el día del upgrade (2026-08-22) |

> Las tres incidencias son la misma lección con distinta cara: **lo que personalizamos
> encima de algo que Odoo después reestructura, el upgrade lo pisa** — sea una edición
> de Studio dentro de una vista de módulo, o una copia por-website del editor del sitio.
> Cambia solo cómo avisan: 500 ruidoso, silencio total, o 500 con traceback.
>
> Y cambia dónde se cazan: las dos primeras eran **estructurales** (revisión [1] y [7]);
> la tercera es un **error de ejecución** que solo ve el barrido HTTP [5] — por eso ese
> barrido pasó a cubrir todas las páginas publicadas y no una lista fija.

## Los cinco comandos (o uno solo)

Los cinco de una vez, con resumen en tabla y código 1 si alguno encuentra algo:

```bash
python scripts/checklist_upgrade.py --target test
```

Uno por uno:

```bash
# 1. Salud general: sitio web, vistas, metadatos custom  (solo lectura)
python scripts/audit_post_upgrade.py --target test
python scripts/audit_post_upgrade.py --comparar        # test vs prod, lado a lado

# 2. Salud del PDF de cotización: columna de imagen y cuadre de columnas
python scripts/deploy_reporte_cotizacion.py --target test --verificar

# 3. Que no se haya colado código que Odoo factura
python scripts/audit_lineas_facturables.py --target test

# 4. Que matriz, productos y reglas de personalización sigan diciendo lo mismo
python scripts/audit_personalizacion.py --target test

# 5. Que la tienda siga SIN cobrar en línea (y el portal sí cobrando)
python scripts/audit_checkout_sin_pago.py --target test
```

Los cinco son de solo lectura y salen con código 1 si encuentran algo. Se
complementan: el primero cubre el sitio y las vistas, el segundo el PDF, el
tercero vigila que no reaparezca código facturable (ver
[ADR 007](../../decisions/007-retiro-motor-cotizacion-costo-codigo.md)), el cuarto
la personalización nativa y el quinto el checkout sin cobro
([ADR 010](../../decisions/010-checkout-sin-pago-en-linea.md)).

> **El quinto es el más urgente.** Su filtro vive en dos vistas heredadas de plantillas
> de Odoo: si el upgrade las reestructura y Odoo desactiva las nuestras, la tarjeta
> reaparece en el checkout **sin avisar** y un cliente puede pagar algo sin existencias.
> El barrido HTTP del comando 1 no lo ve: `/shop/payment` necesita un carrito con
> dirección, que no se puede simular desde un script.

> El cuarto comando histórico, `deploy_motor_cotizacion.py --verificar`, solo aplica
> si algún día se reconstruye el motor: se retiró de producción el 2026-08-17.

## Cómo se registra una incidencia nueva

Un archivo en `incidencias/` con nombre `AAAA-MM-DD-sintoma-corto.md` y estas
secciones: **síntoma** (lo que ve el usuario), **por qué costó verlo** (si
aplica), **causa raíz**, **reparación**, **¿aplica a producción?** y **cómo se
detecta automáticamente** (qué revisión del auditor lo cacha — y si ninguna, ese
es el trabajo pendiente: agregarla).

Después: alta en la tabla de arriba y entrada en `docs/changelog.md`.
