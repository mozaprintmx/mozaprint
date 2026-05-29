# Estado DNS — mozaprintmx.com

> Referencia de la arquitectura DNS actual, historial de cambios y pendientes de optimización.
> Última auditoría: 2026-05-28 · Reporte: `reports/dns_20260528.json`

---

## Arquitectura actual

```
Registrar (renovación del dominio)
└── Hostinger
    └── Nameservers apuntando a Cloudflare →

DNS Authoritative
└── Cloudflare
    ├── anita.ns.cloudflare.com
    └── noel.ns.cloudflare.com

Sitio web
└── Registros A en Cloudflare → proxy CDN → Odoo Online
    ├── 104.21.18.145  (IP proxy Cloudflare)
    └── 172.67.182.84  (IP proxy Cloudflare)
    Backend real: mozaprintmx.odoo.com (Odoo Online 19.0)

Correo electrónico
└── Registros MX en Cloudflare → servidores Hostinger
    ├── mx1.hostinger.com  (prioridad 5)
    └── mx2.hostinger.com  (prioridad 10)
```

**Regla operativa**: Hostinger se usa exclusivamente como registrar (renovación del dominio). Toda la administración de registros DNS se hace desde el panel de Cloudflare.

---

## Registros activos (2026-05-28)

| Tipo | Nombre | Valor | Notas |
|------|--------|-------|-------|
| NS | mozaprintmx.com | anita.ns.cloudflare.com | Cloudflare authoritative |
| NS | mozaprintmx.com | noel.ns.cloudflare.com | Cloudflare authoritative |
| A | mozaprintmx.com | 104.21.18.145 | Proxy Cloudflare → Odoo |
| A | mozaprintmx.com | 172.67.182.84 | Proxy Cloudflare → Odoo |
| A | www.mozaprintmx.com | 172.67.182.84 | Proxy Cloudflare → Odoo |
| MX | mozaprintmx.com | 5 mx1.hostinger.com | Email Hostinger |
| MX | mozaprintmx.com | 10 mx2.hostinger.com | Email Hostinger (fallback) |
| TXT | mozaprintmx.com | `v=spf1 include:_spf.mail.hostinger.com ~all` | SPF (ver pendientes) |
| TXT | mozaprintmx.com | `google-site-verification=MBGZHf8Yy81bMZ...` | Google Search Console |
| TXT | _dmarc.mozaprintmx.com | `v=DMARC1; p=none` | DMARC (ver pendientes) |
| A | autodiscover.mozaprintmx.com | 104.21.18.145 | Autodescubrimiento email |

---

## Historia

### WordPress + WooCommerce en Hostinger (origen)
El sitio original de Mozaprint corría sobre WordPress + WooCommerce alojado directamente en Hostinger. Los nameservers eran de Hostinger y el hosting del sitio también.

### Migración a Odoo Online
El sitio fue migrado a Odoo Online (mozaprintmx.odoo.com). Motivos: unificar catálogo, CRM, cotizaciones y e-commerce en una sola plataforma.

### Migración DNS a Cloudflare
Los nameservers se migraron de Hostinger a Cloudflare. Motivo: mejoras de rendimiento y SEO identificadas vía PageSpeed Insights (CDN, caching, headers de seguridad, HTTP/2). Hostinger quedó solo como registrar.

### Sitio WordPress respaldado en old.mozaprintmx.com
El sitio WordPress original fue conservado en `old.mozaprintmx.com` como respaldo. Según la auditoría del 2026-05-28 aún está activo apuntando a `104.21.18.145`.

> **TODO**: confirmar fecha de eliminación del registro A de `old.mozaprintmx.com` en Cloudflare y actualizar esta línea. Verificar que el contenido no sea necesario antes de eliminar.

---

## Configuración de email

El correo `@mozaprintmx.com` está gestionado por Hostinger. El flujo es:

```
Envío entrante → MX en Cloudflare → mx1/mx2.hostinger.com → buzón Hostinger
Envío saliente → Hostinger SMTP → SPF valida _spf.mail.hostinger.com
```

Para que los correos transaccionales de Odoo (cotizaciones, follow-ups) lleguen correctamente, el registro SPF debe incluir los servidores de Odoo además de Hostinger. Pendiente de resolver (ver sección de pendientes).

---

## Pendientes de optimización

### 1. SPF: cambiar `~all` por `-all`
**Estado**: pendiente
**Registro actual**: `v=spf1 include:_spf.mail.hostinger.com ~all`
**Riesgo actual**: `~all` (softfail) permite que servidores no autorizados envíen con el dominio sin ser bloqueados.
**Acción**: cuando se active el envío de correo desde Odoo, actualizar a:
```
v=spf1 include:_spf.mail.hostinger.com include:<spf-odoo> -all
```
Verificar el include de Odoo en su documentación antes de cambiar.

### 2. DMARC: escalar de `p=none` a `p=quarantine`
**Estado**: pendiente — esperar 2-4 semanas de reportes primero
**Registro actual**: `v=DMARC1; p=none`
**Acción secuencial**:
1. Agregar `rua=mailto:ops@mozaprintmx.com` para recibir reportes agregados
2. Revisar reportes durante 2-4 semanas
3. Escalar a `p=quarantine`
4. Eventualmente a `p=reject`

### 3. DKIM: verificar y documentar selector de Hostinger
**Estado**: pendiente investigación
**Contexto**: la auditoría buscó los selectores comunes (`default`, `google`, `selector1`, `selector2`) y no encontró ninguno activo. Hostinger puede usar un selector diferente.
**Acción**: revisar en panel Hostinger → Email → DKIM, identificar el selector activo y documentarlo aquí.

### 4. Subdominio n8n
**Estado**: pendiente — crear cuando se aprovisione el VPS Hetzner
**Registro a crear**: `A n8n.mozaprintmx.com → <IP del VPS>` en Cloudflare (sin proxy, DNS-only)

---

## Auditorías registradas

| Fecha | Archivo | Notas |
|-------|---------|-------|
| 2026-05-28 | `reports/dns_20260528.json` | Primera auditoría — baseline |

Para correr una nueva auditoría:
```bash
python scripts/dns_audit.py --output reports/dns_$(date +%Y%m%d).json
```
