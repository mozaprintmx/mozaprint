# Decisiones del equipo · v1

> Snapshot de decisiones tomadas el 2026-05-24. Para detalle técnico de cada 
> decisión ver el ADR correspondiente en `decisions/`.

## Setup técnico

- **Camino WhatsApp**: A — Coexistence (app móvil + Cloud API mismo número)
- **LLM Provider**: A definir en piloto (Claude vs OpenAI, evaluación A/B)
- **DNS**: Cloudflare ya activo. Hostinger solo como registrar
- **Orquestador**: n8n self-hosted en VPS (Hetzner CX22, ~€5/mes)
- **Repo Git**: GitHub público
- **Subdominio n8n**: `n8n.mozaprintmx.com` (a crear en Cloudflare)

## Roles humanos

- **WhatsApp Admin**: Operador único
- **Dueño Knowledge Base**: Karina (Dir. Marketing) — ver manual en 
  `docs/manual-knowledge-base.md`
- **Aprobador de costos**: Manager de Finanzas
- **Implementador técnico**: Operador único (con Claude Code)

## Operación

- **Horarios humanos**: L-V 9-18, Sábado 10-13, Domingo cerrado
- **SLA aprobación costos**: 30 min hábil / 4h off-hours
- **Tono del agente**: Tutea por default
- **Comandos español**: `/tomar`, `/reactivar`, `/pausar` (alias inglés disponibles)
- **Modo toma vendedor**: Híbrido — pause automático al primer mensaje + override `/tomar`
- **Notificación interna por WA**: Sí, en escalados urgentes
- **Retención conversaciones**: 24 meses + borrado a petición

## Volumen actual

- 10-20 conversaciones WhatsApp por semana
- 1 operador WhatsApp activo (2 personas total acceso)
- 3 usuarios planeados en Odoo

## Comercial

- **Anticipo estándar**: 50%
- **Anticipo >$100k MXN**: valoración caso por caso
- **Métodos de pago**: Transferencia (principal) + Mercado Pago

## Catálogo

- **Técnicas prioritarias**: Serigrafía, Tampografía, Bordado, DTF Textil, DTF UV
- **Modelo de técnicas**: separado de productos (many2many)
- **Lista costos INN**: parsear documento online en sprint inicial
- **Lista costos 4P y PO**: construir desde histórico + crecimiento HITL

## Seguimiento proactivo

- **Piloto (semanas 1-6)**: 100% reactivo
- **Post-piloto (mes 3+)**: Nivel 1 (follow-ups de cotización)
- **Mes 6+**: Nivel 2 (recordatorios de eventos), evaluar Nivel 3 (cross-sell)

## Decisiones pendientes

- Nombre del agente (propuesto: "Moza", confirmar con Karina)
- Plantillas WhatsApp exactas para enviar a Meta (diseñar en sprint 4)
- Política para domingos/feriados (mensaje específico del agente)

---

**Fecha de toma de decisiones**: 2026-05-24
**Próxima revisión**: Final del sprint 3 (~semana 6)
