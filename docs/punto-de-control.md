# Punto de control — Mozaprint MX

Última actualización: 2026-06-26. Pegar/leer al iniciar un chat nuevo para retomar con contexto mínimo.

## Cómo trabajar (para ahorrar tokens)
- Un chat nuevo por pieza de trabajo; cortar al cerrar cada pieza, no a media tarea.
- No pegar salidas completas de Claude Code: resumir ("aplicó OK, 3 archivos, 0 errores") + solo el dato para decidir.
- Capturas solo cuando lo visual importa; si se puede decir el resultado en texto, mejor.
- Pasos uno a uno con validación; no asumir herramientas/versiones; español MX; honestidad sobre trade-offs.

## Stack
- Odoo Online 19.0 Custom (db `mozaprintmx`, mozaprintmx.com). Extensión solo vía Studio / Ajustes→Técnico / Automation Rules / Server Actions. JSON-2 API (no XML-RPC) para integraciones nuevas.
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

## PENDIENTES / próximas piezas (cada una = chat nuevo)
- **Vigilar** primeras corridas: desactivación de sobrantes (riesgo API inestable bajo umbral 10%); que imágenes AVIF se conviertan/salten; que la derivación se dispare sola post-sync; que el backup productos_INN_*.json se genere. Revisar logs en ProductSync\logs\.
- **Limpieza fina opcional** (higiene, sin prisa): borrar de verdad los atributos basura; limpiar valores de Color (10 huérfanos + 40 de-1-producto).
- **Piezas de Fase 2 sin tocar**: swatches de color, optional/accessory products, **descripciones con AI Fields** (alto valor SEO; OJO: el sync reescribe description_ecommerce, mismo patrón "el sync lo pisa" que la técnica — diseñar con cuidado). Recomendación: saltar a descripciones AI por mayor impacto.
- **15 kits multicomponente**: refinamiento manual de default (cosmético).
- **Backlog del sync** (Fase 8 / mini-proyectos): XML-RPC→JSON-2; precio en pricelist en vez de ×1.5 en código; supplierinfo completo (product_code/min_qty para matriz de costos Fase 3); Materiales[] en PO/4P; tags de material palabra-completa vs primera palabra; "esperar 2-3 corridas antes de desactivar sobrantes".
- **changelog.md** del repo: confirmar entrada de alto nivel del fix INN.
- **Fases siguientes**: 3 (motor cotización / matriz de costos por técnica×área×cantidad×proveedor — el área viene en texto sin parsear en x_area_impresion/x_medidas), 4-6 (WhatsApp+n8n, agente), 7+ (SEO, expansión).
