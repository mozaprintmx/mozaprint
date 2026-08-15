# Procedimiento ante una actualización de Odoo

> Qué revisar —y cómo reparar— cuando Odoo Online actualiza la base donde vive el
> motor de cotización. Complementa `docs/checklist-deploy-produccion.md` (que cubre
> el despliegue inicial, hecho el 2026-08-14).

## Por qué existe este documento

El motor **no es un módulo**: son ~76 objetos creados como **datos** dentro de la base
(`ir.model`, `ir.model.fields`, `ir.ui.view`, `ir.actions.server`, `ir.ui.menu`). Un
upgrade de Odoo actualiza el código de los módulos; **no borra registros marcados
`state='manual'`**. Es decir: el motor no "se pierde".

Lo que sí puede pasar es que algo quede **desactivado** o **deje de funcionar**. Eso se
repara re-desplegando desde este repo, que es la fuente de verdad — no se recupera de
un respaldo.

## Qué es frágil y qué no

| Pieza | ¿Se borra? | Riesgo real |
|---|---|---|
| 128 tarifas, aprobaciones, líneas ya cotizadas | Nunca | **Ninguno** — son datos de negocio, viajan como cualquier factura |
| 2 modelos + 49 campos | No | Bajo |
| 8 vistas propias del motor | No | Bajo — no dependen de nada de Odoo |
| 3 menús + 3 acciones de ventana | No | Bajo — cuelgan de `sale.menu_sale_config` y `sale.sale_menu_root` |
| 5 Server Actions (269 líneas) | No | **Medio** — nadie valida el código en el upgrade; falla en tiempo de ejecución si cambia una API |
| **Vista heredada `sale.order.personalizar.header.button`** | No, pero **se desactiva** | **El más alto** |

### El punto débil, con nombre y apellido

La vista heredada inyecta el botón "Agregar personalización" con
`xpath expr="//header"` sobre `sale.view_order_form`
([scripts/views_motor.py](../scripts/views_motor.py)). Si un upgrade cambiara ese nodo,
Odoo **desactiva** la vista durante la migración en vez de romper el formulario.
Consecuencia: desaparece el botón; todo lo demás (menús, tarifas, aprobaciones,
Server Actions) sigue funcionando.

Atenuante: `//header` es un ancla genérica y estable, no un xpath frágil del tipo
`//field[@name='x']/parent::div`. Es de lo más resistente que se puede escribir.

## Los tres tipos de actualización

| Tipo | Frecuencia | Qué hacer |
|---|---|---|
| **Parches** dentro de 19.0 | Continuo, automático | Nada |
| **Rollforward SaaS** (19.0 → saas~19.x) | Meses | Correr `--verificar` cuando lo notes |
| **Versión mayor** (19 → 20) | ~1 año | El procedimiento completo de abajo |

> Dato útil: **staging ya corre `saas~19.2` con los mismos 76 objetos y funciona**,
> mientras producción está en `19.0`. El siguiente salto SaaS ya está probado.

## El comando que hay que recordar

```bash
python scripts/deploy_motor_cotizacion.py --target prod --verificar
```

Solo lectura, no escribe nada, tarda ~20 segundos. Sale con **código 1** si algo falta.
Revisa tres niveles, de menos a más exigente:

1. que los objetos **existan** (modelos, campos, ACLs, acciones, vistas, menús, defaults);
2. que los archivables sigan **activos** — busca incluyendo archivados, justo porque Odoo
   los oculta y ese es el modo de fallo esperado;
3. que el formulario de ventas **renderice el botón** (`get_views`). Esta es la prueba de
   verdad: valida que la herencia se aplica, no solo que la vista está guardada.

Salida sana:

```
  ✓ modelos 2/2 · campos 49/49 · ACLs 2/2 · Server Actions 5/5 (269 líneas)
  ✓ vistas 9/9 · acciones 3/3 · menús 3/3 · contacto externo 1/1 · defaults 2/2
  ✓ el formulario de ventas renderiza el botón «Agregar personalización»
  ✓ El motor está completo y operativo.
```

## Antes de un upgrade mayor

1. **No actualizar producción directo.** Odoo avisa con anticipación; pedir primero una
   **base de prueba ya migrada** desde el gestor de bases de datos. (Confirma el flujo
   exacto en la notificación de Odoo: el detalle del proceso cambia entre versiones.)
2. Correr `--verificar --target test` en esa base migrada.
3. Si sale limpio: correr también el **checklist funcional** de
   [checklist-deploy-produccion.md](checklist-deploy-produccion.md) paso 4 (casos A/B/C,
   aprobación, línea de setup, re-aplicar sin duplicar). El `--verificar` prueba la
   estructura; el checklist prueba el comportamiento.
4. Solo entonces, actualizar producción.

> ⚠️ **No cuentes con un snapshot descargable.** Odoo Online rechaza el respaldo de esta
> base por tamaño (probado 2026-08-14). Alternativas: duplicar desde el gestor, o pedir a
> soporte de Odoo un respaldo. Ellos mantienen respaldos automáticos.

## Después de cualquier actualización

```bash
python scripts/deploy_motor_cotizacion.py --target prod --verificar
```

Si el upgrade generó un **reporte**, búscalo por vistas personalizadas desactivadas: ahí
saldría la nuestra.

## Reparación por síntoma

| Síntoma | Causa | Reparación |
|---|---|---|
| `vista ... está DESACTIVADA` | El xpath dejó de resolver | Re-correr el deploy (abajo): **reactiva** la vista existente, no crea otra |
| `el formulario de ventas NO muestra el botón` con la vista activa | El xpath resuelve pero el nodo cambió | Ajustar `header_btn` en [views_motor.py](../scripts/views_motor.py) y re-correr el deploy |
| `el formulario de ventas NO ABRE` | La vista rompe el form para todos | **Urgente**: Ajustes → Técnico → Vistas → desmarcar *Activo* en `sale.order.personalizar.header.button`. El resto del motor sigue vivo |
| `falta el campo ...` / `falta el modelo ...` | Improbable | Re-correr el deploy |
| `Server Action ... quedó SIN CÓDIGO` | Improbable | Re-correr el deploy (re-sube el código del repo) |
| El motor truena al usarlo, pero `--verificar` sale limpio | Cambió una API del sandbox | Leer el error en la UI y ajustar el `.py` en `odoo-extensions/server-actions/`; probar en staging; re-correr el deploy |

### El comando de reparación

```bash
# 1. Simulacro
python scripts/deploy_motor_cotizacion.py --target prod --saltar-datos
# 2. Aplicar
python scripts/deploy_motor_cotizacion.py --target prod --apply --si-produccion --saltar-datos
```

`--saltar-datos` es importante en una reparación: evita volver a aplicar el markup y los
renombres de alcance sobre tarifas que ya se editaron a mano desde el despliegue.

El deploy es **idempotente**: lo que ya existe y está bien lo deja igual, lo desactivado lo
reactiva, lo que falta lo crea. Correrlo de más no hace daño.

### Si todo falla: reconstrucción desde cero

El repo puede rebuildear el motor completo. Es el mismo camino que se ensayó en staging el
2026-08-14 (rollback total + redespliegue con regresión funcional):

```bash
python scripts/deploy_motor_cotizacion.py --target prod --inventario   # manifiesto del estado actual
python scripts/rollback_motor_cotizacion.py --manifiesto backups/manifiesto_INVENTARIO_prod_<fecha>.json --apply --si-produccion
python scripts/deploy_motor_cotizacion.py --target prod --apply --si-produccion
python scripts/seed_costos.py --csv analysis/costos-personalizacion/costos_seed.csv --apply
```

⚠️ El rollback **no** borra las tarifas creadas después del deploy ni limpia las líneas de
personalización ya agregadas a cotizaciones (las lista para revisión manual). Lee el
apartado 3 del [checklist](checklist-deploy-produccion.md) antes de usarlo.

## Nota de mantenimiento

Si algún día se agregan objetos al motor, hay que reflejarlos en tres listas de
[deploy_motor_cotizacion.py](../scripts/deploy_motor_cotizacion.py) para que `--verificar`
los cuente: `CAMPOS`, `SERVER_ACTIONS` y `ARCHS_NOMBRES` (más `MENUS_ESPERADOS` /
`MODELOS_CON_MENU` si es un menú nuevo). El resto se deriva solo.
