# Changelog técnico — Mozaprint

> Historial de cambios significativos al sistema. Una entrada por cambio relevante.

---

## 2026-06-01 · infra · patch

**Tipo**: `infra`
**Descripción**: Setup base de Meta Business / WhatsApp completado. Documentada decisión de orden.

**Cambios**:
- Portfolio Meta confirmado: mozaprint_mx (Business ID: 100794159106337), admins Juan Carlos y Karina
- WABA "Moza Print" (ID: 358071354051207) aprobada, número +52 1 56 3277 6277 registrado
- Verificación de negocio Meta: no requerida para este caso de uso (no bloquea)
- Creado `docs/meta-whatsapp-status.md` con estado completo, pendientes y limitaciones de Coexistence
- Decisión documentada: pausar conexión Cloud API hasta tener VPS n8n con URL pública
- Roadmap actualizado: tarea Meta marcada `[x]`, bloqueante de Fase 4 corregido (era "verificación Meta", es "VPS n8n")

**Pendientes documentados** (se completan de corrido al tener n8n):
- Crear App en Meta for Developers (App ID, App Secret)
- Crear System User con token permanente
- Activar Coexistence en el número
- Configurar webhook hacia n8n
- Enviar 5 plantillas a aprobación Meta

**Impacto**: ninguno en producción. Solo documentación y configuración de accesos.

---

## 2026-05-31 · infra · patch

**Tipo**: `infra`
**Descripción**: Cierre de tareas DNS y usuario técnico API de Fase 0.

**DNS — completado**:
- Auditoría ejecutada 2026-05-28 con `scripts/dns_audit.py` (adaptado a dnspython para Windows)
- Cloudflare authoritative confirmado · Hostinger queda solo como registrar + email
- `old.mozaprintmx.com` eliminado de Cloudflare (residuo WooCommerce legacy)
- SPF reforzado de `~all` a `-all` (modo estricto)
- DKIM confirmado: 3 selectores Hostinger (`hostingermail-a/b/c._domainkey`) vía CNAME delegation
- DMARC en `p=none` — en observación, escalar a `quarantine` en ~4 semanas
- **Alerta futura documentada**: cuando Odoo envíe email con servidor propio, agregar `include:<spf-odoo>` al SPF antes del `-all` o los correos serán rechazados

**Usuario técnico API Odoo — completado**:
- Decisión: NO crear usuario `integration@` dedicado (evitar costo de usuario facturable adicional en Odoo Online)
- Se reutiliza usuario existente "Rosy Ponce" (`rosy_ponce@mozaprintmx.com`) con permisos reducidos desde casi-admin a mínimos necesarios para la API
- API key `"n8n-produccion"` generada y almacenada en Bitwarden
- API key `"proveedores-sync"` queda pendiente para la fase de migración del script
- Ver detalle completo en `docs/usuarios-odoo.md`

**Gestor de secretos**:
- Adoptado Bitwarden para centralizar API keys, tokens y contraseñas del proyecto

**Impacto**: DNS de producción modificado (SPF, eliminación de subdominio). Permisos de usuario Odoo reducidos.

---

## 2026-05-29 · docs · patch

**Tipo**: `docs`
**Descripción**: Creado `docs/dns-status.md` con arquitectura DNS completa de mozaprintmx.com.

**Cambios**:
- Nuevo documento `docs/dns-status.md` con: arquitectura actual (registrar/Cloudflare/Odoo/Hostinger email), tabla de registros activos, historial (WordPress→Odoo, Hostinger DNS→Cloudflare), configuración de email, y pendientes de optimización (SPF `-all`, DMARC `quarantine`, DKIM, subdominio n8n)

**Impacto**: ninguno en producción. Solo documentación.

---

## 2026-05-28 · scripts · patch

**Tipo**: `scripts`
**Descripción**: Migración de `scripts/dns_audit.py` de `subprocess + dig` a `dnspython` para compatibilidad nativa en Windows.

**Cambios**:
- Reemplazada función `run_dig()` por `dns_query()` usando `dns.resolver` de dnspython
- Eliminada dependencia de `subprocess` y del binario externo `dig`
- Añadido guard de import al inicio: mensaje de error claro si dnspython no está instalado
- Añadido `sys.stdout.reconfigure(encoding='utf-8')` para evitar errores de encoding en consola Windows (cp1252)
- Actualizado docstring del módulo
- Creada carpeta `reports/` y primer baseline: `reports/dns_20260528.json`
- Creado `requirements.txt` con dependencias del proyecto

**Impacto**: ninguno en producción. El script produce output idéntico al anterior.

**Dependencia nueva**: `dnspython>=2.6` — instalar con `pip install dnspython`

**Primera ejecución**: mozaprintmx.com auditado el 2026-05-28. Hallazgos:
- Cloudflare authoritative ✓
- SPF presente pero `~all` (no estricto) ⚠
- DMARC presente con `p=none` ⚠
- Subdominio `old.mozaprintmx.com` activo — verificar si es legacy
- `n8n.mozaprintmx.com` pendiente de crear

---

## 2026-05-28 · docs · patch

**Tipo**: `docs`
**Descripción**: Añadida regla de autonomía epistémica a CLAUDE.md.

**Cambios**:
- Nueva subsección `### Antes de preguntar` en `## Cómo trabajamos`
- Define que Claude debe buscar en `docs/`, `decisions/`, `specs/`, `scripts/`,
  `n8n-workflows/` y `odoo-extensions/` antes de escalar una duda al operador
- Solo se escala lo que realmente no puede resolverse leyendo el repo

**Impacto**: ninguno en producción. Solo cambia comportamiento del asistente.

---

## 2026-05-24 · decision · v0.2.0

**Tipo**: `decision`
**Descripción**: Consolidación de decisiones del equipo tras revisar plan general.

**Cambios**:
- ADR 004 creado con todas las decisiones confirmadas
- Modelo de datos actualizado: técnicas de personalización ahora son modelo 
  separado (`x_tecnica_personalizacion`) en lugar de selection
- Cada producto tiene `x_tecnica_default_id` (many2one) + 
  `x_tecnicas_compatibles_ids` (many2many)
- ai-agent-spec.md ampliado con horarios, comandos en español, anticipo, 
  política de seguimiento proactivo
- Script de auditoría DNS creado: `scripts/dns_audit.py`
- Manual de mantenimiento del KB para Karina: `docs/manual-knowledge-base.md`
- Decisión revisada de orquestador: VPS self-hosted (Hetzner CX22) en lugar 
  de n8n Cloud, basado en volumen real de 10-20 conv/sem
- Decisión LLM (Claude vs OpenAI) se mantiene abierta hasta piloto sprint 5-6

**Impacto**: 
- Hay que crear modelo `x_tecnica_personalizacion` en Odoo antes de productos
- Datos seed iniciales: 8 técnicas a cargar en sprint 1
- Hay que cargar técnicas antes de poder vincular productos
- Workflows de n8n deben referenciar técnicas por many2one (no selection)
- Knowledge base de cada técnica debe vivir en Odoo Knowledge módulo (no en KB del agente directamente)

**Tareas seguimiento**:
- [ ] Crear modelo de técnicas vía Studio
- [ ] Cargar 8 técnicas seed
- [ ] Migrar productos existentes para que apunten a técnicas (script de migración)
- [ ] Actualizar workflows n8n (cuando se construyan) para usar tecnica_id
- [ ] Entregar manual a Karina

---

## 2026-05-23 · docs · v0.1.0

**Tipo**: `docs`
**Descripción**: Bootstrap del paquete de contexto para Claude Code.

**Cambios**:
- Creado CLAUDE.md raíz con convenciones del proyecto
- Creado docs/architecture.md con diagrama y responsabilidades
- Creado docs/glossary.md con términos del negocio
- Creado docs/roadmap.md con fases y estado
- Creado specs/data-model.md con campos custom de Odoo
- Creado specs/integrations.md con APIs externas
- Creado specs/ai-agent-spec.md con identidad y tools del agente Moza
- ADR 001: n8n self-hosted como orquestador
- ADR 002: Claude como LLM primario
- ADR 003: WhatsApp Coexistence Mode (propuesto)

**Impacto**: ninguno en producción. Solo documentación.

---

## Versionado

- **Major** (v1.0.0): cambios incompatibles en modelo de datos o API
- **Minor** (v0.x.0): features nuevos sin breaking
- **Patch** (v0.0.x): fixes, refactors, docs

