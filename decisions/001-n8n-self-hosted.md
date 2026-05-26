# ADR 001: n8n self-hosted como orquestador

**Fecha**: 2026-05-23
**Estado**: Aceptado
**Decisores**: Equipo Mozaprint (3 personas)

## Contexto

Necesitamos un orquestador entre Odoo, Meta WhatsApp y APIs externas (Anthropic, proveedores). Las opciones evaluadas fueron:

1. Lógica directa en Server Actions de Odoo
2. Make.com (managed, SaaS)
3. Zapier (managed, SaaS)
4. n8n self-hosted
5. Código custom Node/Python en VPS

## Decisión

Vamos con **n8n self-hosted** en VPS pequeño.

## Razones

- **Pricing predecible**: n8n cobra por workflow execution si es cloud, pero self-hosted es gratis. Make/Zapier cobran por operación, lo que escala mal con tráfico de WhatsApp (cada mensaje son N operaciones).
- **Datos sensibles**: conversaciones con clientes pasan por el orquestador. Mejor en infraestructura nuestra.
- **Sin vendor lock-in**: workflows son JSON exportables, podemos migrar.
- **Node nativo para Odoo y WhatsApp Cloud API**: existen y funcionan bien.
- **Versionable como código**: JSON de workflows va al repo.
- **Open source**: parche disponible, comunidad activa.
- **Soporta HITL nativo**: el node WhatsApp Business Cloud puede usarse como step de human review para AI Agent tools.

## Alternativas descartadas

### Lógica en Server Actions de Odoo
- Sandbox Python limitado (sin imports arbitrarios)
- No tiene UI visual para debugging
- Si una llamada tarda, bloquea el thread de Odoo
- Difícil de testear

### Make.com / Zapier
- Costo escalable con tráfico (deal-breaker para volumen WA)
- Datos sensibles en infraestructura de terceros
- Vendor lock-in
- Menor flexibilidad para lógica compleja

### Código custom en VPS
- Reinventamos la rueda
- Más código que mantener
- Sin UI para que el ejecutor revise/depure
- Más lento de iterar

## Consecuencias

### Positivas
- Costo mensual: ~$10-20 USD (VPS pequeño tipo Hetzner CX22 o DigitalOcean droplet básico)
- Control total
- Workflows como código, versionables
- Fácil onboarding de nuevos contribuyentes vía UI

### Negativas
- Hay que mantener la VPS (updates, backups, monitoreo)
- Si la VPS cae, se cae el agente WA (mitigación: monitoreo + auto-restart)
- Curva de aprendizaje inicial (mitigación: una persona única, fácil de aprender)

## Mitigaciones operativas

- VPS con backup snapshots diarios
- Healthcheck endpoint expuesto, monitoreado con BetterStack/Uptime Robot
- Workflows críticos con error handling y notificación
- Backup de credentials encriptado

## Tareas derivadas

- [ ] Aprovisionar VPS (recomendado: Hetzner CX22, 2vCPU/4GB, ~€5/mes)
- [ ] Instalar n8n con Docker Compose
- [ ] Configurar reverse proxy con SSL (Caddy o Traefik)
- [ ] Configurar backups automáticos
- [ ] Crear primeras credentials (Odoo, Anthropic, Meta)
- [ ] Importar primer workflow piloto
