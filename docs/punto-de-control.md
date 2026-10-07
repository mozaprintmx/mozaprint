# Punto de control — Mozaprint MX

Última actualización: 2026-10-06. Pegar/leer al iniciar un chat nuevo para retomar con contexto mínimo.

## Cómo trabajar (para ahorrar tokens)
- Un chat nuevo por pieza de trabajo; cortar al cerrar cada pieza, no a media tarea.
- No pegar salidas completas de Claude Code: resumir ("aplicó OK, 3 archivos, 0 errores") + solo el dato para decidir.
- Capturas solo cuando lo visual importa; si se puede decir el resultado en texto, mejor.
- Pasos uno a uno con validación; no asumir herramientas/versiones; español MX; honestidad sobre trade-offs.

## Stack
- Odoo Online **saas~19.3** Custom (db `mozaprintmx`, mozaprintmx.com) — subió el 2026-08-22. Extensión solo vía Studio / Ajustes→Técnico / Automation Rules / Server Actions. JSON-2 API (no XML-RPC) para integraciones nuevas.
- Repo PÚBLICO `github.com/mozaprintmx/mozaprint`, local `D:\MozaPrint\Odoo\Proyectos\mozaprint`. NUNCA credenciales.
- Sync de proveedores (PO, 4P, INN): **v3** (`mozasync`, JSON-2) desde 2026-10-04/05/06, en el repo **privado** `mozaprint-sync` (`D:\MozaPrint\Odoo\Proyectos\mozaprint-sync\`; ADR 011). Operación, horarios y reversas: su `docs/OPERACION.md`. La v2 (`sync_odoo_paquete_v2`) ya no corre.
- Negocio: artículos promocionales personalizados B2B, CDMX. Operador único (Juan Carlos). Volumen bajo (~10-20 conversaciones/semana).

## Modelo de datos de técnica (Fase 2) — COMPLETO
- Modelo `x_tecnica_personalizacion`: campos `x_name`, `x_code` (req), `x_aliases` (text, variantes crudas sep " | "), `x_descripcion`, `x_orden`, `x_activa`. 20 técnicas cargadas (seed_tecnicas.py, idempotente). Permiso: grupo "Ventas/Usuario: todos los documentos".
- En `product.template`: `x_tecnica_default_id` (m2o), `x_tecnicas_compatibles_ids` (m2m) → ambos a x_tecnica_personalizacion. Legacy `x_tecnica_impresion` (char) = fuente raw, lo pisa el sync.
- Regla default en combos: primera técnica del string crudo; si hay una sola, esa.
- Derivación: `scripts/derive_tecnicas.py` (raw→canónico vía aliases, dry-run/--apply/--since, writes agrupados por derivación idéntica ~50x, mini-test m2m antes del lote). Aplicada: 5,203 productos. Quedan 15 kits multicomponente marcados (cola opcional F5, no bloqueante).
- Seed versionado: `data/tecnicas_seed.csv` + `data/tecnicas_seed.md` (procedencia). 3 aliases agregadas tras dry-runs: "Grabado en bajo relieve", "Goteado en Resina", "Grabado en Arena".

## Sync de proveedores — v3 en producción (Fase 8)
La v2 (auditoría y mejoras de julio–septiembre) quedó sustituida por la **v3**: los tres
proveedores corren con ella desde el 2026-10-06 y la v2 ya no corre. Todo el detalle (diseño,
decisiones, horarios, bitácora y reversas) vive en el repo **privado** `mozaprint-sync` (ADR 011);
aquí no se documenta.

## Fase 2 — /shop filtros — COMPLETO (limpieza)
- Audit: `scripts/audit_atributos.py` (reportes gitignored). 17 atributos, solo 2 reales: **Color** (204 valores, 5,444 productos, create_variant=always — NO TOCAR esa mecánica de variantes) y **Talla** (29 productos). Los otros 15 son basura (0 o 1 producto), con duplicados Brand/brand, color/Color.
- El sidebar PÚBLICO ya estaba sano (solo Color/Talla/Precio); los filtros sucios solo se veían como ADMIN (productos no publicados).
- **Hecho**: limpieza de atributos vía campo "Visibilidad del filtro de eCommerce" — todo lo que no es Color/Talla quedó Oculto. Validado: /shop público muestra solo Color, Talla, Precio.
- **Filtro de técnica DESCARTADO/baja prioridad**: por experiencia del operador, el cliente busca producto y luego pregunta por personalización; no navega por técnica. (Odoo no tiene reporte de términos de búsqueda para confirmarlo con datos.)
- Si se hiciera técnica-como-filtro algún día: requiere modelarla como product.attribute con create_variant="no_variant" (no se puede filtrar /shop por campo custom en Online sin tocar el controlador).

## Fase 3 — Personalización en la cotización — ✅ EN PRODUCCIÓN (2026-08-25)

Los precios de personalización se cotizan con mecanismos **nativos**: productos de
servicio + reglas de lista de precios. **0 líneas facturables.** Diseño completo en
`specs/personalizacion-nativa.md`.

- **Cómo funciona**: la matriz `x_costo_personalizacion` (Ventas → Configuración →
  Costos de personalización, **128 tarifas**) es la **única fuente de verdad**. Los
  scripts del repo la traducen a **53 productos de servicio** (`PERS-*` tarifados,
  `SERV-*` comodín) y **77 reglas de `product.pricelist.item`** con tramos de
  `min_quantity`. El vendedor elige el servicio y teclea la cantidad; **Odoo pone el
  precio**.
- **Regla de oro**: los precios **NO se editan en la ficha del producto** — se editan en
  la matriz y se recargan. Lo que se escriba en el producto lo pisa la siguiente carga.
- **Ojo con la cantidad**: 11 servicios se cobran **POR TINTA** y 3 van siempre en 1
  (lote o setup). Odoo pinta esas líneas de ámbar como aviso. Teclear piezas donde van
  tintas es el error caro del diseño.
- **Manuales**: vendedor `docs/manual-vendedor-personalizacion.md` (Información, art. 75)
  y administrador `docs/manual-admin-precios-personalizacion.md` (art. 74).
- **Verificación**: `python scripts/audit_personalizacion.py --target prod` — sale con
  código 1 si matriz, productos y reglas dejan de decir lo mismo.
- **Pendientes de NEGOCIO, no técnicos**: 4Promotional sigue sin tarifas, y las de Promo
  Opción arrancan en 50–1,000 piezas cuando la mediana de pedido es de **20** — hay que
  preguntarles si tienen lista para pedidos chicos. Mientras, esos casos van por los
  comodines «(precio a cotizar)» con el precio tecleado a mano tras pedírselo al
  proveedor.

### Por qué NO es un Server Action (lección permanente)

El **motor de cotización anterior se retiró el 2026-08-17**: Odoo cobra «Mantenimiento de
código personalizado» **cada 100 líneas** de código de Studio (acciones automatizadas y
campos calculados). El motor sumaba **289 líneas = 3 cargos** y era el **100%** del código
facturable de la base. Ver `decisions/007-retiro-motor-cotizacion-costo-codigo.md`. Los
precios ahora son **datos** —productos y reglas, que no se cobran— y la inteligencia vive
en scripts del repo, que corren desde la computadora del operador.

- **Guarda permanente**: `scripts/audit_lineas_facturables.py` mide el código facturable y
  falla si supera `--max-bloques` (default 0). Está en el checklist post-upgrade.
- **Docs históricos** (describen el motor retirado; se conservan por si algún día se
  revisa la decisión): `specs/motor-cotizacion.md`,
  `docs/checklist-deploy-produccion.md` y `docs/manual-personalizacion-cotizacion.md`.

## Fase 4 — WhatsApp nativo en Odoo — 🟢 EN PRODUCCIÓN (2026-09-09)

Odoo es **dueño del webhook** (ADR 008 revirtió la 005: n8n ya no es el router).
Odoo Online es URL pública, así que **el VPS dejó de ser prerrequisito** de las
fases 4-7.

| Dato | Valor |
|---|---|
| Número | `+52 1 56 6470 5479` · nombre visible `MozaPrint MX` |
| WABA | `1055533050656636` (**nueva**; la vieja «Moza Print» no admitía números) |
| Phone Number ID | `1299638423233370` |
| Callback | `https://www.mozaprintmx.com/whatsapp/webhook` |
| Código facturable | **0 líneas** |

**Validado en producción**: envía, recibe, liga al contacto, manda cotizaciones
con PDF, y **se contesta desde la app móvil de Odoo** (criterio (a) del bloque F,
cumplido). Método de pago en Meta registrado — la fecha límite del 30-sep ya no
aplica.

**Falta**: bloque D (plantillas propias a aprobación) y bloque F (6 semanas de
prueba). El **bloque E se cerró el 2026-09-11** con política explícita — ver abajo.

### Los cuatro hallazgos que costaron la noche

Están completos en `docs/whatsapp-implementacion.md`. En una línea cada uno:

1. **`subscribed_apps` no tiene botón**: hay dos registros, el de la app (visible
   en la consola) y el de la **WABA**, que solo se hace por API. Sin el segundo no
   llega **ningún** webhook, y no hay error. Causa del 90% de las fallas.
2. **Las plantillas se atan a cuenta + modelo**: no se heredan entre cuentas.
3. **La app debe estar publicada** o Meta no entrega webhooks de producción.
4. **Un App Secret mal pegado no da ningún error**: solo rompe la **entrada**, y
   «Probar credenciales» **no lo detecta** porque esa prueba usa el token, no el
   secret. Debe ser **32 caracteres hexadecimales**.

### Bloque E — ✅ HECHO el 2026-09-11, con política explícita

El script se descartó (un solo idioma activo → el editor web basta). JC migró las
vistas a mano; se validó contra producción con `curl` + `ir.ui.view`, solo lectura.

**La política, que NO es una migración a medias sino el diseño:**

| Grupo | Número | Por qué |
|---|---|---|
| Header (`4318`), redes (`4095`), `/shop` (`5029`), `/servicios` (`3884`) | **nuevo** | Canales de entrada de la prueba |
| Portada (`2342`), `/contactanos` (`4122`), pie (`4504`) | **los dos** | Los clientes de siempre buscan el `5632776277` ahí |
| **Todos los `tel:`** | **viejo, permanente** | Ése sí recibe llamadas; el nuevo es Cloud API y **solo gestiona mensajes** |
| Landings `4725`, `5049`, `5050`, `5052` | viejo | De prueba, tráfico marginal |

> ⛔ **No "completes" los `tel:` por consistencia.** Un cliente que marque al número
> nuevo no timbra en ningún lado, y eso **no lo detecta el bloque F**: la llamada
> nunca llega a Odoo.

**El JS de `custom_code_footer` también se migró** el 2026-09-11
(`wa.me/5215664705479`). Alcanza al **28% del catálogo** (1,412 de 5,016 publicados
— todo INN, porque el JS pregunta por `4P` y `PO` y **nunca por `INN`**) y es **el
único enlace del sitio que manda nombre de producto y SKU**.
🟠 **Cambiar el número NO cerró el pendiente**: la consulta a proveedores sigue
saliendo del navegador del visitante. Eso es arquitectura y va en Fase 8.
📌 El sitio quedó con el nuevo en **dos formatos**: `52…` en los enlaces del editor
y `521…` en el JS. Ambos deben resolver; si un día falla solo ese, ahí está la causa.

**La ficha de producto sigue sin botón propio** (`oe_structure_website_sale_product_1`
vacía), que es el **primer origen de leads de formulario** (7 de 13 con origen).

**Corrección**: el bug de los corchetes (`[NOMBRE_PRODUCTO]` / `[SKU]`) **ya no
existe**. El inventario real es de **15 vistas**, no 14 (faltaba `2521` `s_share`,
sin número).

> ⚠️ **Trampa de medición que ya costó una conclusión equivocada**: para tráfico de
> páginas usa **`Sitio web → Analítica`** (es **Plausible**), NO `website.track`. Ese
> modelo solo registra lo que puede atribuir a un `website.page` o a un `product_id`,
> así que rutas de controlador como **`/shop` devuelven 0 siempre** — 0 en 28,870
> registros históricos, aunque Plausible le cuente 34 visitantes únicos en 28 días.

**Política completa, estado por vista y procedimiento en
`docs/sitio-web-enlaces-whatsapp.md` §2.bis.**

## Tienda sin cobro en línea — 🟢 EN PRODUCCIÓN (2026-09-22)
- El checkout **ya no cobra**: única opción "Solicitar pedido (sin pago en línea)" (el proveedor manual de transferencia, renombrado). El pedido queda en **Cotización enviada**: sin venta confirmada, sin entrega, sin dinero de por medio. Motivo: 42% de las variantes publicadas están en cero con el proveedor y cada cobro podía acabar en devolución.
- El cobro va DESPUÉS: enlace de pago desde la cotización, o marcar "Pago en línea". Al pagar, la orden se confirma sola, nace la entrega y el pago se registra. Mercado Pago intacto para portal y enlaces.
- **"Pago contra entrega" se APAGÓ**: confirmaba pedidos en automático (entrega + venta que cancelar). El pago exprés del carrito también, en todos los proveedores: ese botón no pasa por el paso de pago y ninguna vista lo filtra.
- Dos automatizaciones declarativas (0 líneas facturables): los pedidos de tienda nacen con `require_payment=False`, y al pasar a "Cotización enviada" se crea la actividad "Validar existencias con proveedor". Esa actividad es el **único** aviso: Odoo no asigna vendedor a pedidos web sin confirmar, así que no llega correo. Las cotizaciones del backend no se tocaron.
- Riesgo vivo: el filtro son dos vistas heredadas de plantillas de Odoo → comando **(e)** del checklist post-upgrade, `python scripts/audit_checkout_sin_pago.py --target prod`.
- Reversa compuesta y probada: `python scripts/configurar_checkout_sin_pago.py --target prod --rollback --apply --si-produccion`.
- Aviso del paso de pago ya reescrito (2026-09-22): "PREVIO A SOLICITARTE UN PAGO TENEMOS QUE VALIDAR EXISTENCIAS… GENERA TU SOLICITUD Y UNA VEZ CONFIRMADO TE CONTACTAREMOS PARA LOS PAGOS".
- Detalle: `decisions/010-checkout-sin-pago-en-linea.md` · operación: `docs/manual-vendedor-pedidos-web.md`.

## PENDIENTES / próximas piezas (cada una = chat nuevo)
- ✅ **«Consultar inventario» rehecho** (2026-10-05): consulta solo el producto de la página por un servicio intermedio, sin credenciales en el navegador. Detalle en el repo privado (`docs/BOTON_INVENTARIO.md`).
- **Sync v3**: vigilar las primeras corridas de INN y 4P en el correo diario de las 10:30; pendiente el retiro de la v2 (Fase 8, Etapa 4).
- **Limpieza fina opcional** (higiene, sin prisa): borrar de verdad los atributos basura; limpiar valores de Color (10 huérfanos + 40 de-1-producto).
- **Piezas de Fase 2 sin tocar**: swatches de color, optional/accessory products. **Descripciones con IA DESCARTADAS del cierre de Fase 2** (2026-07-06) — reencuadradas como iniciativa SEO DIRIGIDA de Fase 9, condicionada a diagnóstico GSC. Señal: clientes que buscan productos agotados en otros revendedores caen aquí, pero compartimos la descripción duplicada del proveedor → Google deprioritiza. Palanca real = title/H1 únicos, no el body. Ver `decisions/006` y roadmap Fase 9.
- **15 kits multicomponente**: refinamiento manual de default (cosmético).
- **Backlog del sync**: vive en el repo privado `mozaprint-sync` (XML-RPC→JSON-2 ya quedó con la v3).
- **Fase 3 CERRADA** (2026-08-25). Lo que queda no es código: **costos de 4P** (único proveedor sin lista tabulada) y preguntarle a **Promo Opción** si tiene tarifa para pedidos por debajo de sus mínimos. Falta también la **prueba manual de JC**: armar una cotización completa en producción con el manual del vendedor delante — es lo único que puede decir si el flujo funciona para quien lo usa a diario. Higiene: partners de proveedor duplicados (INN 82/32, PO 11/8).
- **Fases siguientes**: ~~el cuello de botella es el VPS de n8n~~ — **falso desde el 2026-08-31** (ADR 008): Odoo Online es URL pública y es dueño del webhook, así que el VPS dejó de ser prerrequisito de las fases 4-7. La Fase 4 está en producción sin él. Los cuellos de botella reales hoy son **las plantillas de Meta** (bloque D, 24-72 h de aprobación cada una) y **el bloque F** (6 semanas de prueba). La **Fase 9 (SEO)** sigue sin depender de nada y se puede avanzar en paralelo — ya tiene línea base de tráfico, ver `docs/roadmap.md` Fase 9.

## Upgrades de Odoo (apartado nuevo, 2026-08-15)
- Producción y test corren **las dos saas~19.3** desde el 2026-08-22. La base de test es **desechable**: un duplicado en modo *trial* que dura ~15 días y Odoo elimina (ya van `…-0807` → `…-0818` → `mp-watest`, que **caduca el 2026-09-24**). La vigente es siempre la de `ODOO_TEST_URL` en `analysis/supplier-sync/.env`; antes del próximo upgrade hay que crear una nueva y actualizar esa variable. Seguimiento en `docs/upgrades/` (README + checklist + incidencias).
- **Incidencia 19.3 RESUELTA en PROD el 2026-08-22**: `/contactanos` se cae con 500 porque `_get_visitor_from_request()` se mudó de `website.visitor` a `ir.http` y nuestra copia por-website (vista 4122) quedó atrás. Reparado con `scripts/fix_vista_contactanos.py`; **el fix aborta a propósito si la base todavía tiene el método en el modelo viejo**. Tercer upgrade seguido en que el fix preparado en test se aplica el mismo día sin sorpresas.
- **19.3 trae imagen de producto nativa en el PDF** (`display_product_images_on_so`). **Probada y DESCARTADA el 2026-08-18**: recorta la imagen a cuadrado y la deforma. Nos quedamos con nuestra columna y el interruptor apagado; `deploy_reporte_cotizacion.py --verificar` ahora falla si alguien lo enciende.
- **Reemplazo nativo de personalización — ✅ EN PRODUCCIÓN desde 2026-08-25**: 53 productos de servicio + 77 reglas de lista de precios, con la matriz `x_costo_personalizacion` como única fuente de verdad y los scripts del repo traduciendo. 0 líneas facturables. Spec en `specs/personalizacion-nativa.md`; manuales de vendedor y de administrador en `docs/` y publicados en Información (artículos 75 y 74). Verificación permanente: `python scripts/audit_personalizacion.py --target prod`.
- **Contabilidad**: se lleva en Odoo (126 asientos, 21 facturas publicadas) pero **no se timbra nada desde Odoo** (0 CFDI, sin RFC en la compañía) — la presentación ante el SAT ocurre fuera. El asistente de XML de pólizas sobrevivió a 19.3, solo cambió de módulo.
- **Incidencia resuelta**: el salto a 19.2 tumbó TODAS las fichas de producto (500 sin traza). Causa: la copia por-website traducida de `website_sale.product_terms_and_conditions` quedó con `inherit_id` y arch de plantilla suelta. **Aplicado en producción el 2026-08-17**, el día del upgrade: cayeron las 5,012 fichas y `scripts/fix_vista_terminos_producto.py --target prod --apply --si-produccion` las devolvió a 200. Al aplicarlo se descubrió que `arch_db` es un campo **traducido**: el script ahora escribe idioma por idioma (`en_US` primero).
- **Incidencia 2026-08-16 — RESUELTA en test y en PROD**: desapareció la **columna de Imagen** del PDF de cotización en test. Misma causa raíz que la anterior: Studio la había incrustado en `sale.report_saleorder_document` (vista del módulo `sale`, `noupdate=False`) y el upgrade reescribió el `arch_db`. Solución: dos **vistas propias heredadas** creadas por `scripts/deploy_reporte_cotizacion.py` (idempotente, dry-run, `--verificar`, `--rollback`). En PROD son las vistas **5062** y **5063**, y **sobrevivieron el upgrade a 19.2 sin tocar nada** (2026-08-17) — la reparación de raíz se pagó sola. Se aplicó **antes** del upgrade —no el día del upgrade— porque el arreglo es válido en 19.0 y ya corregía descuadres existentes (`tr_combo` y `tr_section_group` −1; proforma −2/−3 por bug de fábrica de `l10n_mx_edi_sale`). Cotización de prueba permanente en test: **S00474**, con los 5 tipos de fila.
- Tres comandos de salud, solo lectura: `scripts/audit_post_upgrade.py --comparar` (sitio y vistas, ahora con [7] Studio in-place y [8] cuadre de columnas), `deploy_motor_cotizacion.py --verificar` (motor) y `deploy_reporte_cotizacion.py --verificar` (PDF).
- **Regla que queda**: lo que Studio edita dentro de una vista de módulo, el upgrade lo pisa. Antes de personalizar un reporte con Studio, ver `docs/upgrades/`.
- **Pendiente de JC**: revisión manual §2-§5 del checklist (sitio a ojo, backend, prueba funcional del motor, integraciones).
