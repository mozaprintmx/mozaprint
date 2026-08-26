# Punto de control — Mozaprint MX

Última actualización: 2026-08-25. Pegar/leer al iniciar un chat nuevo para retomar con contexto mínimo.

## Cómo trabajar (para ahorrar tokens)
- Un chat nuevo por pieza de trabajo; cortar al cerrar cada pieza, no a media tarea.
- No pegar salidas completas de Claude Code: resumir ("aplicó OK, 3 archivos, 0 errores") + solo el dato para decidir.
- Capturas solo cuando lo visual importa; si se puede decir el resultado en texto, mejor.
- Pasos uno a uno con validación; no asumir herramientas/versiones; español MX; honestidad sobre trade-offs.

## Stack
- Odoo Online **saas~19.3** Custom (db `mozaprintmx`, mozaprintmx.com) — subió el 2026-08-22. Extensión solo vía Studio / Ajustes→Técnico / Automation Rules / Server Actions. JSON-2 API (no XML-RPC) para integraciones nuevas.
- Repo PÚBLICO `github.com/mozaprintmx/mozaprint`, local `D:\MozaPrint\Odoo\Proyectos\mozaprint`. NUNCA credenciales.
- Sync de proveedores (4P, INN, PO): paquete Python `sync_odoo_paquete_v2`. Producción: `D:\MozaPrint\Odoo\Scripts PY\ProductSync\`. Copia de análisis (editable por Claude Code, gitignored): `analysis\supplier-sync\`. Usa XML-RPC + usuario/contraseña. Python global Python312.
- Negocio: artículos promocionales personalizados B2B, CDMX. Operador único (Juan Carlos). Volumen bajo (~10-20 conversaciones/semana).

## Modelo de datos de técnica (Fase 2) — COMPLETO
- Modelo `x_tecnica_personalizacion`: campos `x_name`, `x_code` (req), `x_aliases` (text, variantes crudas sep " | "), `x_descripcion`, `x_orden`, `x_activa`. 20 técnicas cargadas (seed_tecnicas.py, idempotente). Permiso: grupo "Ventas/Usuario: todos los documentos".
- En `product.template`: `x_tecnica_default_id` (m2o), `x_tecnicas_compatibles_ids` (m2m) → ambos a x_tecnica_personalizacion. Legacy `x_tecnica_impresion` (char) = fuente raw, lo pisa el sync.
- Regla default en combos: primera técnica del string crudo; si hay una sola, esa.
- Derivación: `scripts/derive_tecnicas.py` (raw→canónico vía aliases, dry-run/--apply/--since, writes agrupados por derivación idéntica ~50x, mini-test m2m antes del lote). Aplicada: 5,203 productos. Quedan 15 kits multicomponente marcados (cola opcional F5, no bloqueante).
- Seed versionado: `data/tecnicas_seed.csv` + `data/tecnicas_seed.md` (procedencia). 3 aliases agregadas tras dry-runs: "Grabado en bajo relieve", "Goteado en Resina", "Grabado en Arena".

## Desvío al SYNC — COMPLETO (en producción)
Auditoría completa en `analysis/supplier-sync/AUDITORIA_SYNC.md` (local, gitignored). Piezas hechas:
1. **Dry-run** en auto_sync/stock_sync (guard centralizado en OdooClient._call). --dry-run no escribe nada. Limitación: creates no enumeran variantes.
2. **Fix truncación INN**: conserva TODAS las TecnicasImpresion[] (une con "-") y Materiales[] (une con ", "). Antes tomaba solo [0]. ~437 productos recuperaron multi-técnica. Verificado: TX-119, TX-311 con Serigrafía+Bordado.
3. **Fuga de credenciales CORREGIDA**: la Clave de INN se escribía en claro en logs. Solución: redact() + RedactingFilter global en logger.py (cubre mensaje y traceback). Logs viejos purgados. Sync NO se respalda → no hace falta rotar clave.
4. **Encadenamiento sync→derivación**: auto_sync, al terminar sin errores, invoca derive_tecnicas.py del repo (subprocess, --since hora_inicio-1h UTC, entorno sin heredar vars Odoo del sync). Config .env: DERIVE_ENABLED/DERIVE_SCRIPT_PATH/DERIVE_PYTHON_PATH.
5. **Imágenes AVIF**: diagnóstico detallado + conversión AVIF→PNG/JPEG (Pillow) + saltar rotas. Fallo de imagen ya NO cuenta como error de producto (desacoplado) → ya no bloquea la derivación.
6. **Backup diario INN**: cada respuesta exitosa guarda productos_INN_AAAAMMDD.json (rotación 14d) + actualiza fallback. Escritura atómica, solo si datos válidos.
7. **Ajustes del usuario** (ya en prod): _PAGE_LIMIT INN 800→400 (API no respondía con 800). **Desactivación de sobrantes**: auto_sync desactiva productos que el proveedor ya no manda SI sobrantes <10% del catálogo DE ESE PROVEEDOR (confirmado); si ≥10% avisa "posible catálogo truncado" sin tocar. Config SURPLUS_AUTO_DEACTIVATE/SURPLUS_MAX_PCT.

Horarios reales (Task Scheduler, no en código): stock_sync INN 09:15/13:15/17:15; stock_sync PO+4P cada 4h; auto_sync productos INN 09:15 (ventana API 09:00–10:00), PO+4P 03:00.

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

## PENDIENTES / próximas piezas (cada una = chat nuevo)
- **Vigilar** primeras corridas: desactivación de sobrantes (riesgo API inestable bajo umbral 10%); que imágenes AVIF se conviertan/salten; que la derivación se dispare sola post-sync; que el backup productos_INN_*.json se genere. Revisar logs en ProductSync\logs\.
- **Limpieza fina opcional** (higiene, sin prisa): borrar de verdad los atributos basura; limpiar valores de Color (10 huérfanos + 40 de-1-producto).
- **Piezas de Fase 2 sin tocar**: swatches de color, optional/accessory products. **Descripciones con IA DESCARTADAS del cierre de Fase 2** (2026-07-06) — reencuadradas como iniciativa SEO DIRIGIDA de Fase 9, condicionada a diagnóstico GSC. Señal: clientes que buscan productos agotados en otros revendedores caen aquí, pero compartimos la descripción duplicada del proveedor → Google deprioritiza. Palanca real = title/H1 únicos, no el body. Ver `decisions/006` y roadmap Fase 9.
- **15 kits multicomponente**: refinamiento manual de default (cosmético).
- **Backlog del sync** (Fase 8 / mini-proyectos): XML-RPC→JSON-2; precio en pricelist en vez de ×1.5 en código; supplierinfo completo (product_code/min_qty para matriz de costos Fase 3); Materiales[] en PO/4P; tags de material palabra-completa vs primera palabra; "esperar 2-3 corridas antes de desactivar sobrantes".
- **Fase 3 CERRADA** (2026-08-25). Lo que queda no es código: **costos de 4P** (único proveedor sin lista tabulada) y preguntarle a **Promo Opción** si tiene tarifa para pedidos por debajo de sus mínimos. Falta también la **prueba manual de JC**: armar una cotización completa en producción con el manual del vendedor delante — es lo único que puede decir si el flujo funciona para quien lo usa a diario. Higiene: partners de proveedor duplicados (INN 82/32, PO 11/8).
- **Fases siguientes**: el cuello de botella es el **VPS de n8n** (~€5/mes, Fase 0) — bloquea enteras las fases 4-7 (WhatsApp + agente), que son el corazón del proyecto. La WABA de Meta ya está aprobada; solo falta una URL pública. La **Fase 9 (SEO)** no depende de nada y se puede avanzar en paralelo.

## Upgrades de Odoo (apartado nuevo, 2026-08-15)
- Producción y test corren **las dos saas~19.3** desde el 2026-08-22. Test es la base `mozaprintmx-test-saas19-0818` (la anterior, `…-0807`, caducó y Odoo la eliminó). Test vuelve a ir una versión adelante. Seguimiento en `docs/upgrades/` (README + checklist + incidencias).
- **Incidencia 19.3 RESUELTA en PROD el 2026-08-22**: `/contactanos` se cae con 500 porque `_get_visitor_from_request()` se mudó de `website.visitor` a `ir.http` y nuestra copia por-website (vista 4122) quedó atrás. Reparado con `scripts/fix_vista_contactanos.py`; **el fix aborta a propósito si la base todavía tiene el método en el modelo viejo**. Tercer upgrade seguido en que el fix preparado en test se aplica el mismo día sin sorpresas.
- **19.3 trae imagen de producto nativa en el PDF** (`display_product_images_on_so`). **Probada y DESCARTADA el 2026-08-18**: recorta la imagen a cuadrado y la deforma. Nos quedamos con nuestra columna y el interruptor apagado; `deploy_reporte_cotizacion.py --verificar` ahora falla si alguien lo enciende.
- **Reemplazo nativo de personalización — ✅ EN PRODUCCIÓN desde 2026-08-25**: 53 productos de servicio + 77 reglas de lista de precios, con la matriz `x_costo_personalizacion` como única fuente de verdad y los scripts del repo traduciendo. 0 líneas facturables. Spec en `specs/personalizacion-nativa.md`; manuales de vendedor y de administrador en `docs/` y publicados en Información (artículos 75 y 74). Verificación permanente: `python scripts/audit_personalizacion.py --target prod`.
- **Contabilidad**: se lleva en Odoo (126 asientos, 21 facturas publicadas) pero **no se timbra nada desde Odoo** (0 CFDI, sin RFC en la compañía) — la presentación ante el SAT ocurre fuera. El asistente de XML de pólizas sobrevivió a 19.3, solo cambió de módulo.
- **Incidencia resuelta**: el salto a 19.2 tumbó TODAS las fichas de producto (500 sin traza). Causa: la copia por-website traducida de `website_sale.product_terms_and_conditions` quedó con `inherit_id` y arch de plantilla suelta. **Aplicado en producción el 2026-08-17**, el día del upgrade: cayeron las 5,012 fichas y `scripts/fix_vista_terminos_producto.py --target prod --apply --si-produccion` las devolvió a 200. Al aplicarlo se descubrió que `arch_db` es un campo **traducido**: el script ahora escribe idioma por idioma (`en_US` primero).
- **Incidencia 2026-08-16 — RESUELTA en test y en PROD**: desapareció la **columna de Imagen** del PDF de cotización en test. Misma causa raíz que la anterior: Studio la había incrustado en `sale.report_saleorder_document` (vista del módulo `sale`, `noupdate=False`) y el upgrade reescribió el `arch_db`. Solución: dos **vistas propias heredadas** creadas por `scripts/deploy_reporte_cotizacion.py` (idempotente, dry-run, `--verificar`, `--rollback`). En PROD son las vistas **5062** y **5063**, y **sobrevivieron el upgrade a 19.2 sin tocar nada** (2026-08-17) — la reparación de raíz se pagó sola. Se aplicó **antes** del upgrade —no el día del upgrade— porque el arreglo es válido en 19.0 y ya corregía descuadres existentes (`tr_combo` y `tr_section_group` −1; proforma −2/−3 por bug de fábrica de `l10n_mx_edi_sale`). Cotización de prueba permanente en test: **S00474**, con los 5 tipos de fila.
- Tres comandos de salud, solo lectura: `scripts/audit_post_upgrade.py --comparar` (sitio y vistas, ahora con [7] Studio in-place y [8] cuadre de columnas), `deploy_motor_cotizacion.py --verificar` (motor) y `deploy_reporte_cotizacion.py --verificar` (PDF).
- **Regla que queda**: lo que Studio edita dentro de una vista de módulo, el upgrade lo pisa. Antes de personalizar un reporte con Studio, ver `docs/upgrades/`.
- **Pendiente de JC**: revisión manual §2-§5 del checklist (sitio a ojo, backend, prueba funcional del motor, integraciones).
