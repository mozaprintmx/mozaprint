# Roadmap — Mozaprint

> Estado del proyecto, qué está hecho, qué falta. Claude Code consulta esto para entender contexto temporal.

## Fases

### FASE 0: Higiene de fundamentos
**Estado**: 🟡 Casi completa · 4/9 tareas — pendientes: VPS n8n, cuentas Anthropic/OpenAI, subdominio n8n, rotar API key del sync, whitelist Googlebot
**Decisiones tomadas**: Camino A WhatsApp · DNS Cloudflare confirmado · Roles asignados
**Tareas**:
- [x] Auditar DNS con `scripts/dns_audit.py` (Cloudflare + Hostinger) — 2026-05-28
- [x] Crear repo GitHub público y subir paquete — 2026-05-24
- [x] Usuario técnico API Odoo — 2026-05-31 (ver `docs/usuarios-odoo.md`; se reutilizó Rosy Ponce con permisos reducidos en lugar de crear `integration@`)
- [ ] Rotar API key del script de proveedores
- [ ] Whitelist Googlebot en WAF si aplica
- [x] Iniciar trámite Meta Business Manager — 2026-06-01 (WABA aprobada, base lista; conexión Cloud API pendiente VPS — ver `docs/meta-whatsapp-status.md`)
- [ ] Crear cuentas Anthropic + OpenAI (para evaluación)
- [ ] Aprovisionar VPS Hetzner CX22 (~€5/mes)
- [ ] Crear subdominio n8n.mozaprintmx.com en Cloudflare

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
**Estado**: 🟡 En curso — modelo de técnica y limpieza de /shop hechos; pendiente costos/swatches/optional/AI Fields
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
- [ ] Generar descripciones de producto con AI Fields

### FASE 3: Motor de cotización
**Estado**: 🔴 No iniciada (semana 7-8)
**Notas**:
- INN tiene lista digital de costos: parsear desde https://online.flippingbook.com/view/291441550/4/
- 4P y PO no tienen lista digital, construir desde histórico + HITL
**Tareas**:
- [ ] Crear modelo `x_costo_personalizacion` vía Studio (referencia a x_tecnica_personalizacion)
- [ ] Modelar servicios de personalización como product.product type=service
- [ ] Script para parsear lista costos INN y cargar al modelo
- [ ] Extraer top 20 combinaciones técnica×qty del histórico 4P y PO
- [ ] Activar Quote Subsections en Sales
- [ ] Implementar Server Action de auto-populado de servicios
- [ ] Crear AI Cotizador asistente para vendedor

### FASE 4: Setup técnico WhatsApp + n8n
**Estado**: 🔴 No iniciada (semana 9)
**Bloquea hasta**: VPS n8n desplegado con URL pública (verificación Meta NO requerida — ver `docs/meta-whatsapp-status.md`)
**Tareas**:
- [ ] Aprovisionar VPS para n8n (Hetzner CX22 o equivalente)
- [ ] Instalar n8n + Docker + Caddy
- [ ] Configurar dominio n8n.mozaprintmx.com con SSL
- [ ] Crear credentials en n8n: Odoo, Anthropic, Meta WA
- [ ] Configurar webhooks salientes en Odoo
- [ ] Activar Coexistence con número actual de Mozaprint
- [ ] Probar envío/recepción manual desde n8n

### FASE 5: Agente WhatsApp (preparación)
**Estado**: 🔴 No iniciada (semana 10-11)
**Tareas**:
- [ ] Extraer y anonimizar conversaciones WA históricas
- [ ] Categorizar y analizar patrones
- [ ] Documentar top 15 FAQs
- [ ] Cargar knowledge base en Odoo Knowledge
- [ ] Implementar tools 1-6 en n8n (sin agente activo aún)
- [ ] Test individual de cada tool
- [ ] Enviar plantillas Meta a aprobación
- [ ] Crear campo `x_studio_no_agente` en res.partner (Studio) y marcar contactos a excluir (empleados, números internos)
- [ ] Verificar que todos los proveedores activos estén en Odoo con número de WhatsApp en campo teléfono/móvil (requerido para el filtro de exclusión)

### FASE 6: Bridge custom Odoo↔AI↔WA (V1)
**Estado**: 🔴 No iniciada (semana 12-13)
**Bloquea hasta**: Fase 5 completa + plantillas Meta aprobadas
**Tareas**:
- [ ] Implementar workflow ai-agent-respond en n8n
- [ ] Implementar pre-flight filter en n8n: excluir proveedores (`supplier_rank > 0`), contactos con `x_studio_no_agente = True` y números internos — antes de llamar al agente (ver `specs/ai-agent-spec.md`)
- [ ] Implementar auto-identificación de contacto desde WA `profile.name` al recibir primer mensaje: find-or-create en Odoo antes de llamar a Claude (ver `specs/ai-agent-spec.md`)
- [ ] Implementar tools 7-12 en n8n
- [ ] Crear modelo x_approval_request en Odoo
- [ ] Implementar Server Action ai_handle_whatsapp_message
- [ ] Configurar campos x_ai_mode en discuss.channel
- [ ] Tests end-to-end de 10 escenarios
- [ ] Pulir prompts según resultados

### FASE 7: Piloto controlado
**Estado**: 🔴 No iniciada (semana 14-15)
**Tareas**:
- [ ] Activar AI solo en horario off-hours
- [ ] Monitoreo diario de conversaciones
- [ ] Loop de feedback semanal
- [ ] Iteración de prompts según hallazgos
- [ ] Documentar issues encontrados

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
**Tareas**:
- [ ] Schema.org markup en productos
- [ ] Open Graph para WhatsApp share
- [ ] Optimizar Core Web Vitals
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

| Hito | Semana | Bloquea |
|---|---|---|
| Verificación Meta Business completa | 3 | Setup WA Cloud API (fase 4) |
| Aprobación primera plantilla WA | 4 | Mensajes salientes con templates |
| Aprobación todas las plantillas core | 8 | Piloto del agente (fase 7) |
| 50+ FAQs documentadas | 11 | Agente útil en producción |
| Primer test end-to-end exitoso | 13 | Piloto controlado |
| 3 semanas piloto sin incidente grave | 15 | Expansión del agente |

## Estado actual de capacidades

### Lo que YA funciona en producción
- Catálogo en sitio web con atributos y variantes
- **Modelo de técnica de personalización** (`x_tecnica_personalizacion`, 20 técnicas) con la técnica canónica **derivada** en cada producto (`x_tecnica_default_id` + `x_tecnicas_compatibles_ids`, ~5,203 templates) desde el campo raw `x_tecnica_impresion`
- **/shop depurado**: filtros laterales reducidos a Color, Talla y Precio (atributos basura ocultos)
- **Scripts de catálogo** (solo lectura / migración): `audit_catalog.py`, `audit_atributos.py`, `dump_tecnica_values.py`, `seed_tecnicas.py`, `derive_tecnicas.py` (todos sobre JSON-2 vía `odoo_client.py`)
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
- Cotizaciones se arman 100% manualmente
- Sin trazabilidad de WhatsApp en Odoo
- Sin agente IA
- Sin matriz de costos de personalización formal
- Sin webhooks Odoo → externo
- Correo desde @mozaprintmx.com no configurado en Odoo (sale desde dominio Odoo)

## Notas para Claude Code

- **Si te piden trabajar en algo de fase ≤2**, está en docs, podemos arrancar
- **Si te piden trabajar en algo de fase 3-5**, verifica primero que las fases previas estén listas
- **Si te piden trabajar en algo de fase 6+**, lo más probable es que falten dependencias críticas, pregunta antes de codear
- **Si te piden algo que NO aparece en este roadmap**, ABSOLUTAMENTE pregunta antes de implementar nada
