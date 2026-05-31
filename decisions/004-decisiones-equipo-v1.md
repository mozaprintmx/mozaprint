# ADR 004: Decisiones consolidadas del equipo · v1

**Fecha**: 2026-05-24
**Estado**: Aceptado
**Decisores**: Equipo Mozaprint

## Contexto

Tras revisar el plan general y los tres documentos previos (presentación, 
checklist, plan agente WhatsApp), el equipo tomó las decisiones operativas 
que estaban pendientes.

## Decisiones tomadas

### Setup técnico

| Decisión | Resultado | Notas |
|---|---|---|
| Camino WhatsApp | **A — Coexistence** | Mantener app móvil + Cloud API en mismo número |
| LLM Provider | **A definir en piloto (Claude vs OpenAI)** | Evaluación A/B en sprint 5-6 con conversaciones reales |
| DNS | **Cloudflare authoritative** | ✓ Validado 2026-05-28. Hostinger solo registrar + email. Ver `docs/dns-status.md` |
| Gestor de secretos | **Bitwarden** | Centraliza API keys, tokens y contraseñas. Adoptado 2026-05-31 |
| Usuario técnico API | **Reutilizar Rosy Ponce** | No crear `integration@` (costo facturable). Ver `docs/usuarios-odoo.md` |
| Orquestador | **n8n self-hosted en VPS** | Decisión revisada: 10-20 conv/sem genera 2,300-3,500 ejec/mes, Starter ($24/mes) queda chico, Pro ($60/mes) caro. VPS Hetzner ~$6/mes es mejor |
| Repo Git | **GitHub público** | El paquete de contexto se versiona ahí |
| Seguimiento proactivo | **Progresivo en 3 fases** | Reactivo en piloto → Nivel 1 post-piloto → Nivel 2 mes 6+ |

### Roles humanos

| Rol | Persona | Responsabilidades |
|---|---|---|
| **WhatsApp Admin** | Operador único | Setup Meta Business, mantener Coexistence (abrir app cada 14 días), responder a Meta sobre plantillas |
| **Dueño Knowledge Base** | Karina (Dirección de Marketing) | Mantener FAQs, revisar conversaciones piloto, agregar políticas. Requiere manual de mantenimiento (a entregar) |
| **Aprobador de costos** | Manager de Finanzas | Recibe notificaciones de costos no parametrizados, valida con proveedor, aprueba en Odoo |
| **Implementador técnico** | Operador único | Construye el sistema con Claude Code |

### Operación

| Tema | Decisión |
|---|---|
| Horario humano | **L-V 9-18, Sábado 10-13, Domingo cerrado** |
| SLA aprobación costos | **30 min en horario hábil, 4h off-hours** |
| Tono del agente | **Tutea por default**, cambia a "usted" si cliente lo usa |
| Comandos en español | `/tomar`, `/reactivar`, `/pausar` (con alias en inglés `/take`, `/resume`, `/pause`) |
| Modo de toma | **Híbrido**: pause automático al primer mensaje del vendedor + override con `/tomar` |
| Notificación interna | **Sí, por WhatsApp** cuando hay escalado urgente |
| Retención conversaciones | **24 meses + borrado a petición del cliente** |
| Piloto del agente | **Off-hours/weekends** primero |

### Comercial

| Tema | Decisión |
|---|---|
| Anticipo estándar | **50% para 90% de las órdenes** |
| Anticipo en órdenes >$100k MXN | **Valoración caso por caso** |
| Métodos de pago | Transferencia bancaria (principal) + Mercado Pago (link Odoo) |
| Volumen actual | **10-20 conversaciones/semana, 1 operador WA** |
| Operadores totales WA | **2 personas** |
| Usuarios Odoo planeados | **3 personas** |

### Catálogo

| Tema | Decisión |
|---|---|
| Técnicas prioritarias | Serigrafía, Tampografía, Bordado, DTF Textil, DTF UV |
| Técnicas en modelo de datos | **Modelo separado `x_tecnica_personalizacion`** (no selection), para relación many2many con productos |
| Productos × técnicas | Cada producto puede tener N técnicas compatibles + 1 default sugerida |
| Lista costos INN | Disponible online — parsear y cargar al inicio |
| Lista costos 4P y PO | Construir desde histórico de cotizaciones + crecimiento orgánico con aprobaciones HITL |

## Decisiones pendientes (no bloqueantes hoy)

1. **OpenAI vs Claude** — decisión definitiva en piloto (sprint 5-6)
2. **Nombre del agente** — propuesta "Moza", confirmar con Karina
3. **Plantillas de WhatsApp** — diseñar exactas en sprint 4, antes de enviar a Meta
4. **Domingo y feriados** — política exacta de qué mensaje envía el agente

## Tareas derivadas

### Esta semana
- [x] Ejecutar script de auditoría DNS (`scripts/dns_audit.py`) — 2026-05-28
- [x] Crear repo GitHub público con el paquete — 2026-05-24
- [x] Usuario técnico API Odoo configurado (Rosy Ponce, permisos reducidos) — 2026-05-31
- [ ] Crear cuentas: Anthropic API + OpenAI API (para evaluación)
- [ ] Iniciar trámite Meta Business Manager
- [ ] Aprovisionar VPS Hetzner CX22 (~€5/mes)

### Próxima semana
- [ ] Setup n8n en VPS (seguir `docs/n8n-setup.md`)
- [ ] Crear subdominio `n8n.mozaprintmx.com` en Cloudflare
- [ ] 5 quick wins en Odoo (Promotions, formulario→CRM, etc.)
- [ ] Empezar manual de mantenimiento para Karina

### Sprint 1-2
- [ ] Extender modelo de datos con técnicas como modelo separado
- [ ] Implementar campos custom en crm.lead, discuss.channel
- [ ] Diseñar plantillas WhatsApp para Meta

## Consecuencias

### Positivas
- Decisiones operativas claras, sin ambigüedad para Claude Code
- Roles humanos definidos con responsabilidades
- Métricas y SLAs concretos
- Modelo flexible: técnicas no acopladas a producto, permite evolución

### Negativas
- Más complejidad inicial en modelado (modelo de técnicas en lugar de selection)
- VPS requiere setup técnico inicial vs Cloud
- Decisión LLM se mantiene abierta hasta piloto (overhead leve de mantener dos providers)

## Revisión

Esta decisión se revisa al final del sprint 3 (semana 6) para ajustar 
según hallazgos durante implementación.
