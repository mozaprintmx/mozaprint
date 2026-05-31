# Roadmap — Mozaprint

> Estado del proyecto, qué está hecho, qué falta. Claude Code consulta esto para entender contexto temporal.

## Fases

### FASE 0: Higiene de fundamentos
**Estado**: 🟡 En curso (semana 2) · 3/9 tareas completadas
**Decisiones tomadas**: Camino A WhatsApp · DNS Cloudflare confirmado · Roles asignados
**Tareas**:
- [x] Auditar DNS con `scripts/dns_audit.py` (Cloudflare + Hostinger) — 2026-05-28
- [x] Crear repo GitHub público y subir paquete — 2026-05-24
- [x] Usuario técnico API Odoo — 2026-05-31 (ver `docs/usuarios-odoo.md`; se reutilizó Rosy Ponce con permisos reducidos en lugar de crear `integration@`)
- [ ] Rotar API key del script de proveedores
- [ ] Whitelist Googlebot en WAF si aplica
- [ ] Iniciar trámite Meta Business Manager
- [ ] Crear cuentas Anthropic + OpenAI (para evaluación)
- [ ] Aprovisionar VPS Hetzner CX22 (~€5/mes)
- [ ] Crear subdominio n8n.mozaprintmx.com en Cloudflare

### FASE 1: Captura estructurada de leads
**Estado**: 🔴 No iniciada (semana 2-4)
**Tareas**:
- [ ] Activar Leads en CRM
- [ ] Cambiar acción del formulario /contactanos a Create Opportunity
- [ ] Crear campos custom en crm.lead (Studio)
- [ ] Crear formulario contextual desde ficha de producto
- [ ] Configurar AI Lead Scoring con Server Action
- [ ] Configurar Automation Rules de acuse
- [ ] Configurar asignación automática a Sales Team

### FASE 2: Precios y catálogo
**Estado**: 🔴 No iniciada (semana 5-6)
**Tareas**:
- [ ] Crear modelo `x_tecnica_personalizacion` vía Studio
- [ ] Cargar 8 técnicas seed (ver specs/data-model.md)
- [ ] Migrar productos existentes para apuntar a técnicas (script)
- [ ] Configurar `x_tecnicas_compatibles_ids` en productos clave
- [ ] Migrar tabla de descuentos a Promotions (Discount & Loyalty)
- [ ] Configurar filtros laterales en /shop
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
**Bloquea hasta**: Verificación Meta Business completa
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

### FASE 6: Bridge custom Odoo↔AI↔WA (V1)
**Estado**: 🔴 No iniciada (semana 12-13)
**Bloquea hasta**: Fase 5 completa + plantillas Meta aprobadas
**Tareas**:
- [ ] Implementar workflow ai-agent-respond en n8n
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
- Integración con 3 proveedores vía script (XML-RPC actual)
- Descuentos por monto visibles en ficha (manual)
- Formulario /contactanos (envía email)
- WhatsApp del negocio operado manualmente desde celular

### Lo que NO funciona aún
- Leads no se capturan estructuradamente
- Descuentos no se aplican automáticamente en cotización
- Cotizaciones se arman 100% manualmente
- Sin trazabilidad de WhatsApp en Odoo
- Sin agente IA
- Sin matriz de costos de personalización formal
- Sin webhooks Odoo → externo

## Notas para Claude Code

- **Si te piden trabajar en algo de fase ≤2**, está en docs, podemos arrancar
- **Si te piden trabajar en algo de fase 3-5**, verifica primero que las fases previas estén listas
- **Si te piden trabajar en algo de fase 6+**, lo más probable es que falten dependencias críticas, pregunta antes de codear
- **Si te piden algo que NO aparece en este roadmap**, ABSOLUTAMENTE pregunta antes de implementar nada
