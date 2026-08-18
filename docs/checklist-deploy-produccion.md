# Checklist — despliegue del motor de cotización a PRODUCCIÓN

> Estado: desplegado el 2026-08-14 y **REVERTIDO el 2026-08-17** — el motor ya no
> existe en producción. Se retiró porque Odoo cobra por cada 100 líneas de código de
> Studio; ver `decisions/007-retiro-motor-cotizacion-costo-codigo.md`.
>
> El rollback fue **quirúrgico**: 64 de los 76 objetos. Se conservaron las vistas y
> menús de la matriz de costos y de las técnicas (son datos, no código, y no se
> facturan). Manifiesto usado: `backups/manifiesto_motor_prod_QUIRURGICO.json`.
>
> Este documento queda como registro y como procedimiento si se reconstruye.
>
> Diseño: `specs/motor-cotizacion.md` · Detalle de objetos:
> `odoo-extensions/studio-fields.yaml` · Guía conceptual: `docs/guia-motor-cotizacion.md`
>
> 🔄 **Para las actualizaciones de Odoo que vengan después**, el apartado completo vive
> en [upgrades/](upgrades/README.md), no aquí: checklist de revisión, incidencias
> registradas y el procedimiento específico del motor.

## 0. Versiones y compatibilidad (verificado 2026-08-13)

| | Producción | Staging |
|---|---|---|
| Versión | **19.0+e** | **saas~19.2+e** |
| URL | `mozaprintmx.odoo.com` | `mozaprintmx-test-saas19-0807.odoo.com` |
| BD (XML-RPC) | `mozaprintmx` | **el subdominio completo**, no `mozaprintmx` |

Sondeo de compatibilidad contra producción (solo lectura) — **sin bloqueantes**:

- ✅ `ir.model.fields` soporta `compute` / `depends` / `related` / `store` / `readonly`.
- ✅ Vistas `type='list'` (612 en uso; 0 `tree`) → los `<list>` del motor son válidos.
- ✅ Existen los xmlid que usa el deploy: `sale.view_order_form`, `sale.menu_sale_config`,
  `sale.sale_menu_root`, `base.group_user`.
- ✅ Prerequisitos presentes: modelos `x_tecnica_personalizacion` y
  `x_costo_personalizacion` (con todos sus campos), **20 servicios**, **20 técnicas**,
  **127 tarifas**.
- ✅ Ningún objeto a crear existe ya (base limpia).
- ⚠️ **Único punto no probado en 19.0**: campos manuales **computed** (prod tiene 0; sí tiene
  1 `related`). Mitigado: el deploy hace una **prueba de capacidad** (crea un campo computed
  desechable, verifica que calcula 6×7=42 y lo borra) y **aborta** si falla.

## 1. Antes de empezar

- [ ] Confirmar que **no hay cotizaciones en proceso** que se vayan a tocar (el deploy no
      modifica cotizaciones, pero el rollback sí deja huella si ya se usó el motor).
- [ ] Tener a mano `analysis/supplier-sync/.env` con `ODOO_URL`, `ODOO_DB`, `ODOO_USER`,
      `ODOO_PASSWORD` (admin).
- [ ] **Snapshot de la base**. ⚠️ Odoo Online **no deja descargarla** (demasiado grande, probado
      2026-08-14). Alternativas, en orden: **duplicar** la base desde el gestor (es del lado del
      servidor, a veces sí funciona), o pedir a soporte de Odoo un respaldo/restauración —
      ellos mantienen respaldos automáticos.
      **Si no hay snapshot, el riesgo sigue siendo acotado**: el deploy solo *crea* objetos
      (reversibles con el rollback) y el único dato preexistente que modifica son las tarifas
      de `x_costo_personalizacion`, que el propio script respalda a JSON antes de tocarlas.
      No toca productos, cotizaciones, clientes ni facturas.
- [x] **Ensayo general hecho en staging** (2026-08-14): rollback total + redeploy desde cero,
      con regresión funcional. Encontró 3 bugs que habrían roto el despliegue en producción
      (ver changelog v43). Ya corregidos y re-probados.
- [ ] Estar en horario de baja actividad: la vista heredada del formulario de ventas se
      recarga para todos los usuarios.

## 2. Ejecución (en orden)

### Paso 1 — Simulacro en producción (no escribe nada)
```bash
python scripts/deploy_motor_cotizacion.py --target prod
```
Revisar que el preflight pase y que la lista de cambios sea la esperada
(2 modelos, ~48 campos, 2 ACLs, **5 Server Actions**, 9 vistas, 3 acciones, 3 menús,
1 contacto, 2 defaults).
**Si el preflight reporta un problema, no continuar.**

> El script sube el código **sin comentarios** (~269 líneas en vez de 386); lo reporta al
> desplegar. Con `--con-comentarios` se sube tal cual está en el repo.
> `abrir_wizard_personalizacion_por_linea` **no se despliega** a propósito: no hay botón que
> lo llame (ver changelog v42).

### Paso 2 — Aplicar
```bash
python scripts/deploy_motor_cotizacion.py --target prod --apply --si-produccion
```
El script, en este orden: respalda `x_costo_personalizacion` a `backups/`, crea los
modelos, **prueba los campos computed** (aborta si 19.0 no los soporta), crea campos,
ACLs, contacto, defaults, Server Actions, vistas, acciones y menús, aplica el markup y
los renombres de alcance, corre el **smoke test** (cotización desechable que borra al
final) y escribe el **manifiesto** en `backups/manifiesto_motor_prod_<fecha>.json`.

> 📌 **Guarda la ruta del manifiesto**: es lo que necesita el rollback.

### Paso 3 — Cargar tarifas nuevas
El deploy renombra alcances y pone markup, pero **no** crea tarifas nuevas:
```bash
python scripts/seed_costos.py --csv analysis/costos-personalizacion/costos_seed.csv          # simulacro
python scripts/seed_costos.py --csv analysis/costos-personalizacion/costos_seed.csv --apply  # ejecuta
```
Esperado: **1 a crear** (el mínimo de cilindros), **127 a actualizar**, 0 errores.
⚠️ `seed_costos.py` usa `ODOO_URL` del entorno → apunta a producción por defecto. **Correcto
aquí**, pero verifica la URL que imprime antes de aceptar.

### Paso 4 — Verificación

Primero la automática (solo lectura, ~20 s; sale con código 1 si falta algo):
```bash
python scripts/deploy_motor_cotizacion.py --target prod --verificar
```
Comprueba que los 76 objetos existan, que los archivables sigan **activos** y que el
formulario de ventas **renderice** el botón. Luego, la funcional en la UI:

- [ ] **Ventas → Configuración → Costos de personalización** abre y se puede editar.
- [ ] **Ventas → Configuración → Técnicas de personalización** abre.
- [ ] **Ventas → Aprobaciones personalización** abre (vacío).
- [ ] Abrir una cotización en borrador → aparece el botón **"Agregar personalización"**.
- [ ] Caso A: producto con 1 tarifa → aplica y agrega la línea al **precio de venta**.
- [ ] Caso B: producto con varios alcances → pide elegir candidato.
- [ ] Caso C: producto sin tarifa → sale el **diálogo Aceptar/Cancelar**; al aceptar crea la
      solicitud y **no** pone precio.
- [ ] Aprobar esa solicitud con un costo → **genera la línea sola** y desmarca el aviso.
- [ ] Técnica con setup → aparece la **segunda línea "Setup / preparación"**.
- [ ] Re-aplicar sobre la misma línea → **actualiza, no duplica**.
- [ ] **Borrar la cotización de prueba** al terminar.

### Paso 5 — Manual para el equipo
- [ ] Publicar el artículo de Knowledge en producción (contenido en
      `docs/manual-personalizacion-cotizacion.md`), **quitando el aviso de "en pruebas"**.

## 3. Rollback

### Opción A — Rollback por script (quirúrgico)
```bash
python scripts/rollback_motor_cotizacion.py --manifiesto backups/manifiesto_motor_prod_<fecha>.json
python scripts/rollback_motor_cotizacion.py --manifiesto backups/manifiesto_motor_prod_<fecha>.json --apply --si-produccion
```
Borra en **orden inverso** (menús → acciones → vistas → Server Actions → ACLs → defaults →
campos → modelos → contacto) y restaura nombre/alcance de la matriz desde el respaldo JSON.
Probado en staging con un ciclo completo: limpió los 77 objetos del motor y dejó intactos los
datos preexistentes (tarifas, servicios, técnicas).

> ⏱️ **Tarda más de 2 minutos** (borra objeto por objeto vía XML-RPC). **No lo interrumpas**;
> si se corta, es seguro volver a correrlo: lo ya borrado se reporta como error y continúa.
>
> 📌 Si perdiste el manifiesto, genera uno del estado actual:
> `python scripts/deploy_motor_cotizacion.py --target prod --inventario`
>
> 📌 El contacto de personalización externa **no se puede borrar** si alguna tarifa lo usa;
> el script lo **archiva** en ese caso (equivalente correcto).

**Lo que el rollback NO deshace** (lo avisa al correr):
- Las **líneas de personalización ya agregadas** a cotizaciones: al borrarse los campos
  quedan como líneas de servicio normales. El script cuenta cuántas hay antes de borrar.
- Las **tarifas creadas después del deploy** (por aprobaciones): las lista pero no las borra.
- `x_markup` / `x_precio_venta` / `x_precio_setup` desaparecen con el campo (no hace falta
  restaurarlos).

### Opción B — Restaurar snapshot (nuclear)
Si algo sale mal a media ejecución o el rollback no alcanza: restaurar el backup de Odoo
Online del Paso 1. Se pierde lo capturado en producción desde el snapshot.

### Fallos parciales — qué hacer
| Síntoma | Acción |
|---|---|
| El preflight aborta | Nada se escribió. Corregir y repetir el Paso 1. |
| La prueba de campos computed falla | El deploy aborta tras crear solo los 2 modelos. Correr el rollback con el manifiesto que escribió. **19.0 no soportaría el motor tal cual** → avisar. |
| Se rompe el formulario de Ventas | Es la vista heredada `sale.order.personalizar.header.button`. Desactivarla de inmediato (Ajustes → Técnico → Vistas → desmarcar *Activo*); el resto sigue funcionando. |
| El diálogo de confirmación abre el form equivocado | Falta la vista `x_wizard_personalizacion.confirmar`. Desde v-fix el Server Action falla con mensaje claro en vez de abrir la vista equivocada. Re-correr el deploy. |
| El seed duplica filas | Se renombró un alcance en Odoo sin actualizar el CSV (la llave de idempotencia incluye el alcance). Comparar CSV vs Odoo antes de `--apply`. |

## 4. Decisiones tomadas (JC, 2026-08-13)

- ✅ **Las 3 tarifas creadas desde la UI en staging** (`TAZAS`, `POWER BANK` externo,
      `VELA ITCHI` externo) son **solo de prueba**: NO se exportan al CSV y NO deben existir
      en producción. Producción quedará con las 128 tarifas del CSV.
- ✅ **Mínimo de cilindros: rango 100–499 confirmado** (no incluye el 500, que ya tiene tarifa
      por pieza). Así está en el CSV y así lo cargará el seed.
- ✅ **Permisos de aprobación**: por ahora **cualquier usuario interno** puede aprobar. No se
      restringe en este despliegue.

### Pendientes que NO bloquean el despliegue

- [ ] Las tarifas de **personalización externa** siguen sin cargarse (el mecanismo ya está
      listo y probado; solo faltan los datos).
- [ ] El **markup 1.275** queda visible en el repo público (política de margen). Si se quiere
      ocultar, moverlo a un parámetro del sistema (`ir.config_parameter`).
- [ ] **5 solicitudes de aprobación de prueba** viven en staging (no afectan a producción).
- [ ] Costos de **4PROMOTIONAL**: sigue sin lista tabulada; sus cotizaciones caerán al flujo
      de aprobación hasta que se construya (ver `docs/roadmap.md`).
