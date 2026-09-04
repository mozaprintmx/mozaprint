# Roadmap — Mozaprint

> Estado del proyecto, qué está hecho, qué falta. Claude Code consulta esto para entender contexto temporal.

## Fases

### FASE 0: Higiene de fundamentos
**Estado**: 🟡 Casi completa · 4/9 — pendientes: cuentas Anthropic/OpenAI, rotar API key del sync, whitelist Googlebot. **El VPS y el subdominio dejaron de ser bloqueantes** el 2026-08-31 (ADR 008): Odoo Online es URL pública y toma el webhook. Quedan como opcionales de la Fase 6.
**Decisiones tomadas**: Camino A WhatsApp · DNS Cloudflare confirmado · Roles asignados
**Tareas**:
- [x] Auditar DNS con `scripts/dns_audit.py` (Cloudflare + Hostinger) — 2026-05-28
- [x] Crear repo GitHub público y subir paquete — 2026-05-24
- [x] Usuario técnico API Odoo — 2026-05-31 (ver `docs/usuarios-odoo.md`; se reutilizó Rosy Ponce con permisos reducidos en lugar de crear `integration@`)
- [ ] Rotar API key del script de proveedores
- [ ] Whitelist Googlebot en WAF si aplica
- [x] Iniciar trámite Meta Business Manager — 2026-06-01 (WABA aprobada, base lista; la conexión Cloud API ya NO depende del VPS: el webhook apunta a Odoo — ver `docs/meta-whatsapp-status.md`)
- [ ] Crear cuentas Anthropic + OpenAI (para evaluación)
- [ ] (opcional, Fase 6) Aprovisionar VPS Hetzner CX22 (~€5/mes) — solo si el experimento B falla
- [ ] (opcional, Fase 6) Crear subdominio n8n.mozaprintmx.com en Cloudflare

### FASE 1: Captura estructurada de leads
**Estado**: ✅ Completada (semana 3)
**Tareas**:
- [x] Activar Leads en CRM — 2026-06-03
- [x] Reconectar formulario /contactanos al CRM — 2026-06-03 (crea Lead, no Oportunidad; ver `docs/fase1-captura-leads.md`)
- [x] Crear 5 campos custom en crm.lead (Studio) — 2026-06-02 (ver `specs/data-model.md`)
- [x] Configurar Automation Rule de notificación de nuevos leads web — 2026-06-03
- [x] AI Lead Scoring — funciona nativamente en Odoo Online (no requiere Server Action propia)
- [x] Reconectar formularios /shop y ficha de producto al CRM — 2026-06-03
- [x] Actualizar plantilla notificación con campos qty/producto/personalización — 2026-06-03
- [x] Limpiar pipeline (leads/oportunidades estancados resueltos) — 2026-06-03
- [x] Crear etiquetas CRM y 3 alertas de seguimiento (Automation Rules) — 2026-06-03

**Mejoras futuras (no bloquean operación)**:
- Definir cómo llenar `x_studio_origen_url` automáticamente (opción JS/UTM, baja prioridad)
- Configurar asignación automática a Sales Team (manual funciona por ahora)
- Validar las 3 alertas en funcionamiento real (esperar a que se disparen naturalmente)

**Dependencia operativa documentada**: el equipo debe mover las tarjetas en el pipeline cada vez que actúa con un cliente (ver `docs/proceso-equipo-crm.md`). Se elimina con correo bidireccional o integración WhatsApp (Fase 4).

### FASE 2: Precios y catálogo
**Estado**: 🟡 En curso — modelo de técnica y limpieza de /shop hechos; pendiente swatches/optional. Descripciones con IA DESCARTADAS de Fase 2 (reencuadradas a Fase 9)
**Tareas**:
- [x] Crear modelo `x_tecnica_personalizacion` vía Studio — creado en producción
- [x] Cargar 20 técnicas seed — `scripts/seed_tecnicas.py` (idempotente); ver `data/tecnicas_seed.csv`
- [x] Migrar productos existentes para apuntar a técnicas (script) — `scripts/derive_tecnicas.py` derivó ~5,203 templates desde `x_tecnica_impresion`
- [x] Configurar `x_tecnicas_compatibles_ids` en productos — poblado por la derivación (combos parseados); 15 kits multicomponente quedan para refinamiento manual (no bloqueante)
- [ ] (backlog) Auditar/arreglar los `loyalty.program` existentes con comportamiento extraño — los descuentos YA viven en `loyalty.program` (Tipo: Promociones, por compra mínima); NO hay que migrar nada (confirmado por audit 2026-06-11: 6 programas existentes)
- [ ] (backlog) Limpiar pricelists de prueba no usadas, conservando solo Default — validar ANTES que ninguna esté referenciada por partners u órdenes (audit detectó 4: Default, Volant, GMC, Dólar)
- [x] Configurar filtros laterales en /shop — limpieza hecha: ocultos los atributos no-Color/Talla (campo "Visibilidad del filtro de eCommerce"); /shop público muestra solo Color, Talla, Precio. Filtro por técnica DESCARTADO (el cliente busca producto, no técnica). Audit: `scripts/audit_atributos.py`
- [ ] Cambiar color attribute a display_type=color con swatches
- [ ] Configurar optional/accessory products por categoría
- [ ] ~~Generar descripciones de producto con AI Fields (masivo)~~ → **DESCARTADO de Fase 2** (no bloquea el cierre). Reencuadrado como iniciativa SEO **dirigida** de Fase 9, condicionada a diagnóstico GSC. Ver Fase 9 y `decisions/006-descripciones-ia-seo-dirigido.md`

### FASE 3: Precios de personalización en la cotización
**Estado**: ✅ **COMPLETA — reemplazo nativo en producción (2026-08-25)**

> **El motor de cotización se retiró el 2026-08-17** por el cargo de Odoo por línea de
> código ([ADR 007](../decisions/007-retiro-motor-cotizacion-costo-codigo.md)) y se
> reconstruyó con mecanismos **nativos**: 53 productos de servicio + 77 reglas de lista de
> precios. **0 líneas facturables.** Diseño en
> [`specs/personalizacion-nativa.md`](../specs/personalizacion-nativa.md).
>
> Pendiente de negocio, no técnico: **4Promotional sigue sin tarifas**, y las de Promo
> Opción arrancan en 50–1,000 piezas cuando la mediana de pedido es de 20 — hay que
> preguntarles si tienen lista para pedidos chicos. Mientras, esos casos van por los
> productos comodín «(precio a cotizar)».
**Notas**:
- INN: manual de costos por PDF (`MANUAL-SI-OK.pdf`, no el flippingbook — el visor JS del link
  público no se pudo leer, se usó el PDF exportado). Ver `analysis/costos-personalizacion/COSTOS_INN_20260805.md`.
- PO: 4 tabuladores PDF por técnica (láser, serigrafía, tampografía, termograbado). Ver
  `analysis/costos-personalizacion/COSTOS_PO_20260805.md`.
- 4P: **sin lista documentada** — es el único proveedor que requiere construir el tabulador
  desde histórico de WhatsApp/cotizaciones + HITL.
**Tareas**:
- [x] Crear modelo `x_costo_personalizacion` vía Técnico/Estructura de BD (2026-08-05, 17 campos `x_`)
- [x] Modelar servicios de personalización como product.product type=service (2026-08-06):
      categoría `Servicios de Personalización` (id=435, por API) + 2 campos en `product.template`
      (`x_es_servicio_personalizacion`, `x_tecnica_servicio_id`, creados manual por JC, sin
      `x_studio_` — Técnico no lo fuerza, solo Studio) + **20 servicios creados** (ids 5985–6004,
      1 por técnica) vía `scripts/seed_servicios_personalizacion.py`, validado e idempotente.
- [x] Script `seed_costos.py` + carga de costos INN y PO (2026-08-05, **127 costos** cargados,
      validados y confirmados idempotentes en un segundo dry-run — ver `docs/changelog.md` v25)
- [ ] Costos de 4P (sin lista digital; construir desde histórico WhatsApp/cotizaciones)
- [ ] Extraer top 20 combinaciones técnica×qty del histórico de 4P
- [ ] (backlog, higiene) Partners de proveedor duplicados en Odoo (INN: id 82 vs 32; PO: id 11
      vs 8) — el costo se ancló a los ids canónicos (82/11, los que usa el sync), pero conviene
      fusionar o desactivar los duplicados
- [x] Activar Quote Subsections en Sales — confirmado 2026-08-06: nativo en la instancia, sin
      toggle que activar. Convención: 2 secciones fijas "Producto" / "Personalización"
      (`sale.order.line.display_type='line_section'`). Documentado en `specs/ai-agent-spec.md`
      (tool `create_quote_draft`)
- [~] Implementar Server Action de auto-populado de servicios — desplegado el 2026-08-14 y
      **RETIRADO el 2026-08-17**: Odoo cobra por cada 100 líneas de código de Studio y el motor
      sumaba 289 (3 cargos). Se rehará con mecanismos nativos —productos de servicio + reglas de
      lista de precios con `min_quantity`— que no generan cargo. Ver
      `decisions/007-retiro-motor-cotizacion-costo-codigo.md`. Lo que sigue describe lo que
      llegó a existir:
      desplegado con `scripts/deploy_motor_cotizacion.py` (76 objetos, 0 errores) tras un ensayo
      general de rollback+redeploy en staging. Incluye: wizard `x_wizard_personalizacion`,
      matching contra la matriz, proveedor externo, línea de **setup**, **precio de venta**
      (costo × markup), diálogo de confirmación y administración de **aprobaciones** (que al
      aprobar generan la línea y opcionalmente guardan la tarifa). Manual publicado en Knowledge.
      Ver `docs/checklist-deploy-produccion.md` y `docs/changelog.md` v32–v44.
      Sub-pendiente opcional: botón **por línea** vía Studio (el widget `sol_o2m` no admite
      botón de fila solo por API; el Server Action ya está escrito y probado).
- [ ] Crear AI Cotizador asistente para vendedor

### FASE 4: WhatsApp nativo en Odoo (con personas)
**Estado**: 🟡 Diseñada, no iniciada — ver `decisions/008-whatsapp-nativo-odoo.md`
**Cambio de rumbo (2026-08-31)**: se revirtió la ADR 005. **Odoo es el dueño del
webhook**, no n8n. Odoo Online ya es URL pública, así que **el VPS deja de ser
prerrequisito** de esta fase y de las siguientes.
**Decisión del 2026-09-01**: **número NUEVO y dedicado**. Coexistence quedó
descartado — Meta exige ser Solution Partner o Tech Provider para dar de alta un
número que viene de la WhatsApp Business App. El número actual **no se toca** y el
equipo conserva la app del celular. Pasos: `docs/whatsapp-implementacion.md`.
**Escenario aprobado el 2026-09-04**: número nuevo → Odoo → probar con clientes
reales 6 semanas → decidir si se **intercambia** por el actual. Nombre visible
`Mozaprint MX`. Tráfico de prueba por **un solo canal**: el header de `/shop`.
**⚠️ Fecha límite 30-sep**: sin método de pago en Meta, desde el **1 de octubre**
se bloquean los mensajes salientes (Meta empieza a cobrar los *service messages*).
**Bloquea hasta**: las 7 pruebas del módulo en test
**Tareas** — detalle en `docs/whatsapp-implementacion.md`:
- [x] ~~Experimento A (Coexistence)~~ — descartado, Meta no lo permite (2026-09-01)
- [x] Base de test operativa: `mozaprintmx-watest` — 2026-09-01
- [x] Conseguir el número nuevo — 2026-09-04
- [ ] **A1** App en Meta + WABA existente «Moza Print»
- [ ] **A2** ⚠️ **Método de pago antes del 30-sep** — va primero, no al final
- [ ] **A3** System User + token permanente (`whatsapp_business_messaging`,
      `whatsapp_business_management`) → Bitwarden
- [ ] **A4** Alta y verificación del número, nombre visible `Mozaprint MX`
- [ ] **B** Las 7 pruebas en test con el número de prueba de Meta. La 6ª
      (contestar desde la app móvil) es criterio de la decisión final; la 7ª
      (`audit_lineas_facturables --target test`) es innegociable
- [ ] **D** Plantillas de utilidad a aprobación (en paralelo a B)
- [ ] **C** Instalar en producción y repuntar el webhook al número nuevo
- [ ] **E** `scripts/cambiar_whatsapp_shop.py` — cambiar la vista 5029 iterando
      idiomas (`arch_db` es campo traducido)
- [ ] **F** 6 semanas de prueba, revisión a las 3, y decisión del número definitivo
- [ ] **Experimento B** (IA): ¿un agente nativo contesta en un canal de WhatsApp?
      Si sí, la Fase 6 se cae entera. Va después de que C funcione
- [x] Actualizar `docs/meta-whatsapp-status.md` — 2026-09-01

### FASE 5: Campañas y seguimiento
**Estado**: 🟡 **No está en cero — está detenida.** Diagnóstico medido en
`docs/marketing-diagnostico.md`
**Contexto**: hay 6 listas con ~850 contactos, 5 envíos (marzo-abril 2026, máximo 12
destinatarios) con ~30% de apertura y **0 clics**, y una campaña de nurturing en
estado `stopped` desde el 2026-04-12. Herramientas ya instaladas: `marketing_automation`,
`mass_mailing`, `sms`.
**Tareas**:
- [ ] **Preguntar a Karina por qué se detuvo la campaña de abril** — antes de rediseñar
      nada. La hipótesis es entregabilidad (SPF `-all` estricto + dominio pendiente),
      pero es hipótesis, no hallazgo
- [ ] Secuencia sobre las **379 cotizaciones en borrador que nunca cerraron**:
      recordatorio a 3 días, seguimiento a 10, reactivación a 30. Es la audiencia de
      mayor intención del negocio y nadie la trabaja
- [ ] Reactivar el nurturing de leads, ahora con paso de WhatsApp
- [ ] Atribución con `utm.campaign` hasta la cotización
- [ ] Resolver el dominio de correo si se confirma la hipótesis de entregabilidad

### FASE 6: La IA que contesta
**Estado**: 🔴 No iniciada — **depende del experimento B de la Fase 4**
**Restricción dura**: Odoo Online no admite módulos de terceros, así que los chatbots
de IA sobre WhatsApp del Apps Store **no son opción** (ver `decisions/009`). El WhatsApp
nativo de Odoo no trae IA: enruta a Discuss y ahí contesta una persona.
**Tareas**:
- [ ] Si el experimento B sale bien → configurar el agente nativo en los canales de
      WhatsApp y cerrar la fase
- [ ] Si no → servicio externo mínimo: regla de automatización → acción de servidor
      `webhook` (declarativa, 0 líneas facturables) → Claude → respuesta escrita de
      vuelta por la API de Odoo
- [ ] **Humano en medio al principio**: la IA redacta, el vendedor aprueba y envía
- [ ] Soltar por tipo de mensaje, solo cuando cada uno demuestre que acierta

### FASE 7: El cotizador automático
**Estado**: 🔴 No iniciada
**Por qué ahora es viable**: la Fase 3 dejó a **Odoo calculando el precio**. La IA no
calcula nada — solo elige producto, cantidad y servicio de personalización. Eso
satisface por construcción la regla «Precios SIEMPRE de Odoo».
**Dimensión del problema**: ~36 cotizaciones/mes, 14% de conversión, y solo 9 de 71
leads traen datos del formulario → **el disparador es el vendedor**, que pega lo que
pidió el cliente venga del canal que venga. Alimentarlo solo del formulario cubriría 4
de las 36.
**Tareas**:
- [ ] `scripts/cotizador_ia.py` — dry-run por defecto, como todos
- [ ] Prompt derivado de `docs/manual-vendedor-personalizacion.md`: POR TINTA (11
      servicios), mínimos de Promo Opción, comodines «(precio a cotizar)»
- [ ] **Nunca inventar precio**: sin tarifa → comodín + marca de revisión humana
- [ ] Validar contra una muestra de las **447 cotizaciones ya hechas a mano**, midiendo
      aciertos en producto, servicio y cantidad
### FASE 8: Madurar integración con proveedores
**Estado**: 🔴 No iniciada (semana 16+)
**Tareas**:
- [ ] Migrar script actual a workflows de n8n
- [ ] Migrar XML-RPC → JSON-2 API
- [ ] Configurar webhooks salientes para sync inverso
- [ ] Implementar "Consultar inventario" en vivo en ficha
- [ ] Cron de sync nocturno consolidado

### FASE 9: SEO + Home + Dashboard
**Estado**: 🔴 No iniciada (paralelizable, semana 4+)

**Contexto SEO (por qué importa)**: parte de la adquisición real llega de clientes que buscan un producto AGOTADO en otros revendedores. Mozaprint comparte catálogo (y por tanto la MISMA descripción duplicada) de los proveedores INN/4P/PO, así que Google deprioritiza las fichas por contenido duplicado justo en ese escenario. Hoy probablemente nos encuentran por nombre/SKU (title/H1), no por el cuerpo — por eso el body prose NO es la palanca de mayor leverage. Ver `decisions/006-descripciones-ia-seo-dirigido.md`.

**Palancas SEO en orden de prioridad**:
- [ ] 1. `title` / meta description / H1 **únicos** por producto (mayor leverage)
- [ ] 2. Productos alternativos/accesorios para **linking interno** — automatiza la retención manual de "similar disponible"; conecta con Fase 2 (optional/accessory products)
- [ ] 3. schema.org/Product markup + Open Graph (para WhatsApp share)
- [ ] 4. Descripciones únicas **DIRIGIDAS** (top productos / categorías ancla), NO masivas — solo tras el diagnóstico GSC. Diseño en `decisions/006`
- [ ] **Diagnóstico GSC previo** (condición para pasar de "targeted" a "hacer"): en Search Console → Performance filtrado a URLs de producto, medir impresiones totales vs por página, posición media (15-30 ≈ filtrado por duplicado) y si las queries son nombre/SKU vs genéricas

**Otras tareas de fase**:
- [~] Optimizar Core Web Vitals — **`/shop` de 5,041 KB a 913 KB (−82%)** el 2026-08-07
      optimizando las imágenes de `product.public.category` a WebP 256px. El filmstrip nativo
      las incrusta como base64 en el HTML (no cacheables, bloquean render) y Odoo no
      redimensiona `image_128` al escribir por API, así que el peso de la página es el de
      `image_1920`. Ver changelog v31 y `scripts/optimize_category_images.py`.
      Falta: medir LCP/CLS reales en PageSpeed y revisar el resto de páginas.
- [ ] Home redesign con value props claras
- [ ] Dashboard KPIs con Studio

### FASE 10: Expansión del agente
**Estado**: 🔴 No iniciada (mes 4+)
**Bloquea hasta**: Piloto exitoso 3+ semanas
**Tareas**:
- [ ] Ampliar AI a 24/7
- [ ] Follow-ups proactivos
- [ ] Más combinaciones técnica/qty parametrizadas (reduce HITL)
- [ ] Agente proactivo (cross-sell, reactivación)

### INFRAESTRUCTURA: Correo bidireccional @mozaprintmx.com en Odoo
**Estado**: 🔴 Pendiente
**Prioridad**: Media — no urgente, la notificación desde dominio Odoo ya cumple su función
**Objetivo**: Que Odoo envíe y reciba correos desde `@mozaprintmx.com` (no desde `mozaprintmx.odoo.com`), para gestionar comunicación con clientes directamente desde Odoo con consistencia de marca.
**Tareas**:
- [ ] Configurar servidor de correo saliente en Odoo (SMTP de Hostinger)
- [ ] Configurar servidor de correo entrante (recibir respuestas de clientes en Odoo)
- [ ] Ajustar SPF para incluir el servidor SMTP de Hostinger como emisor autorizado de Odoo ⚠️ SPF está en `-all` estricto — agregar el `include` antes o los correos serán rechazados
- [ ] Verificar DKIM para ese envío
- [ ] Configurar alias de correo en Odoo (ej. `ventas@` o `info@`)
**Nota**: mini-proyecto con su complejidad de deliverability. Ejecutar como bloque dedicado para no romper la configuración de email actual.

## Hitos críticos

> Reescritos el 2026-08-31. Los anteriores colgaban del VPS y de un agente
> conversacional que ya no es el primer paso.

| Hito | Bloquea |
|---|---|
| ⚠️ **Método de pago en Meta antes del 30-sep** | Poder contestar desde el 1 de octubre |
| **Las 7 pruebas del módulo en test** | Instalar en producción |
| Nombre visible `Mozaprint MX` aprobado por Meta | Dar de alta el número |
| Plantillas de utilidad aprobadas | Reabrir conversaciones frías |
| 6 semanas de prueba con clientes reales | Decidir el número definitivo |
| **Experimento B**: agente nativo contesta en canal de WhatsApp | Decide si la Fase 6 necesita infraestructura externa |
| Aprobación de las plantillas de utilidad | Enviar cotizaciones y avisos por WhatsApp |
| Respuesta de Karina sobre la campaña detenida | Rediseñar campañas (Fase 5) |
| Cotizador con acierto medido contra las 447 | Soltarlo sin revisión humana (Fase 7) |

## Estado actual de capacidades

### Lo que YA funciona en producción
- Catálogo en sitio web con atributos y variantes
- **Modelo de técnica de personalización** (`x_tecnica_personalizacion`, 20 técnicas) con la técnica canónica **derivada** en cada producto (`x_tecnica_default_id` + `x_tecnicas_compatibles_ids`, ~5,203 templates) desde el campo raw `x_tecnica_impresion`
- **/shop depurado**: filtros laterales reducidos a Color, Talla y Precio (atributos basura ocultos)
- **Scripts de catálogo** (solo lectura / migración): `audit_catalog.py`, `audit_atributos.py`, `dump_tecnica_values.py`, `seed_tecnicas.py`, `derive_tecnicas.py` (todos sobre JSON-2 vía `odoo_client.py`)
- **Precios de personalización en la cotización** (2026-08-25): 53 productos de servicio + 77 reglas de lista de precios derivados de la matriz `x_costo_personalizacion`. El vendedor elige el servicio, teclea la cantidad y **Odoo pone el precio**; 0 líneas facturables. Ver `specs/personalizacion-nativa.md` y los manuales de vendedor y administrador
- Integración con 3 proveedores vía script (XML-RPC actual)
- Descuentos por monto visibles en ficha (manual)
- Los tres formularios web conectados al CRM: /contactanos, /shop y ficha de producto (crean Lead con campos custom; origen diferenciado por x_studio_origen_form)
- Automation Rule: notificación por correo al entrar un lead web (incluye qty, producto, personalización y origen)
- AI Lead Scoring nativo de Odoo (probabilidad automática)
- Pipeline limpio con etiquetas "Urge contactar" y "Peligro, posible pérdida"
- 3 alertas automáticas: lead sin calificar en 1 día, oportunidad sin avanzar en 1 día, oportunidad en peligro a los 3 días
- WhatsApp del negocio operado manualmente desde celular

### Lo que NO funciona aún
- `x_studio_origen_url` sin captura automática aún
- Descuentos no se aplican automáticamente en cotización
- Odoo no detecta actividad si el vendedor actúa desde Gmail (depende de mover tarjetas manualmente — ver `docs/proceso-equipo-crm.md`)
- La cotización se arma a mano línea por línea — el **precio** de personalización ya lo pone Odoo, lo que no existe es el auto-populado de las líneas
- Sin trazabilidad de WhatsApp en Odoo
- **Agente IA a medias**: hay 6 agentes activos (incluido «ChatBot MozaPrint») pero con **0 fuentes cargadas** — sabe usar skills, no sabe del negocio. El livechat del sitio sigue con el nombre por defecto y sin publicar. Ver `docs/marketing-diagnostico.md`
- **4Promotional sin tarifas de personalización**, y las de Promo Opción arrancan por encima de la mediana de pedido → esos casos van por comodín «(precio a cotizar)», con el precio tecleado a mano
- Sin webhooks Odoo → externo
- Correo desde @mozaprintmx.com no configurado en Odoo (sale desde dominio Odoo) — **sospechoso de haber detenido las campañas de marketing**, ver `docs/marketing-diagnostico.md`
- **Campañas de marketing detenidas** desde abril de 2026, con ~850 contactos ya segmentados sin trabajar
- **379 cotizaciones en borrador** sin ninguna secuencia de seguimiento

## Notas para Claude Code

- **Si te piden trabajar en algo de fase ≤2**, está en docs, podemos arrancar
- **Si te piden trabajar en algo de fase 3-5**, verifica primero que las fases previas estén listas
- **Si te piden trabajar en algo de fase 6+**, lo más probable es que falten dependencias críticas, pregunta antes de codear
- **Si te piden algo que NO aparece en este roadmap**, ABSOLUTAMENTE pregunta antes de implementar nada
