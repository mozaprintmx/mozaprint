# Setup de n8n self-hosted — Mozaprint

> Cómo levantar el orquestador desde cero. ~30 minutos de trabajo.

## Pre-requisitos

- VPS con Docker + Docker Compose
  - Recomendado: Hetzner CX22 (2vCPU/4GB RAM, ~€5/mes), DigitalOcean Droplet básico, o Linode Nanode
  - Mínimo: 2GB RAM, 1 vCPU, 20GB disco
- Subdominio configurado (ej. `n8n.mozaprintmx.com`) apuntando a IP del VPS
- Acceso SSH al VPS

## Paso 1: Conectar al VPS y preparar

```bash
ssh root@<ip-vps>

# Instalar Docker si no está
curl -fsSL https://get.docker.com | sh
systemctl enable --now docker

# Crear usuario no-root para mejor seguridad
adduser mozaprint
usermod -aG docker mozaprint
su - mozaprint
```

## Paso 2: Crear estructura

```bash
mkdir -p ~/n8n-mozaprint && cd ~/n8n-mozaprint
mkdir -p data caddy_data caddy_config
```

## Paso 3: Crear docker-compose.yml

```yaml
# ~/n8n-mozaprint/docker-compose.yml
version: '3.8'

services:
  caddy:
    image: caddy:2-alpine
    restart: unless-stopped
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./Caddyfile:/etc/caddy/Caddyfile
      - ./caddy_data:/data
      - ./caddy_config:/config
    depends_on:
      - n8n

  n8n:
    image: n8nio/n8n:latest
    restart: unless-stopped
    environment:
      # Auth básica del UI
      - N8N_BASIC_AUTH_ACTIVE=true
      - N8N_BASIC_AUTH_USER=${N8N_USER}
      - N8N_BASIC_AUTH_PASSWORD=${N8N_PASSWORD}
      
      # URL pública
      - N8N_HOST=n8n.mozaprintmx.com
      - N8N_PROTOCOL=https
      - N8N_PORT=5678
      - WEBHOOK_URL=https://n8n.mozaprintmx.com/
      
      # Encryption key (generar con: openssl rand -hex 32)
      - N8N_ENCRYPTION_KEY=${N8N_ENCRYPTION_KEY}
      
      # Database (default SQLite, suficiente para empezar)
      - DB_TYPE=sqlite
      
      # Logs
      - N8N_LOG_LEVEL=info
      
      # Timezone
      - GENERIC_TIMEZONE=America/Mexico_City
      - TZ=America/Mexico_City
      
      # Variables del proyecto (también disponibles en workflows)
      - ODOO_URL=${ODOO_URL}
      - ODOO_API_KEY=${ODOO_API_KEY}
      - ODOO_DATABASE=${ODOO_DATABASE}
      
      - ANTHROPIC_API_KEY=${ANTHROPIC_API_KEY}
      - ANTHROPIC_MODEL_FAST=claude-haiku-4-5-20251001
      - ANTHROPIC_MODEL_DEEP=claude-sonnet-4-6
      
      - META_WA_TOKEN=${META_WA_TOKEN}
      - META_WA_PHONE_NUMBER_ID=${META_WA_PHONE_NUMBER_ID}
      - META_WA_BUSINESS_ACCOUNT_ID=${META_WA_BUSINESS_ACCOUNT_ID}
      - META_APP_SECRET=${META_APP_SECRET}
      - META_WA_WEBHOOK_VERIFY_TOKEN=${META_WA_WEBHOOK_VERIFY_TOKEN}
      
      - ODOO_WEBHOOK_SECRET=${ODOO_WEBHOOK_SECRET}
      
    volumes:
      - ./data:/home/node/.n8n
```

## Paso 4: Crear Caddyfile (reverse proxy con SSL automático)

```caddy
# ~/n8n-mozaprint/Caddyfile
n8n.mozaprintmx.com {
    reverse_proxy n8n:5678
    
    encode gzip
    
    log {
        output file /data/access.log
        format json
    }
    
    # Solo permite acceso al UI desde IPs específicas (opcional pero recomendado)
    # @blocked not remote_ip <tu_ip_oficina> <tu_ip_casa>
    # respond @blocked "Forbidden" 403
    
    # Headers de seguridad
    header {
        Strict-Transport-Security "max-age=31536000; includeSubDomains"
        X-Frame-Options "DENY"
        X-Content-Type-Options "nosniff"
    }
}
```

## Paso 5: Crear .env

```bash
# ~/n8n-mozaprint/.env
# IMPORTANTE: chmod 600 después de crear, no commitear

# n8n auth
N8N_USER=admin
N8N_PASSWORD=<password fuerte generado>
N8N_ENCRYPTION_KEY=<generado con: openssl rand -hex 32>

# Odoo
ODOO_URL=https://mozaprint.odoo.com
ODOO_API_KEY=<api key del usuario integration@>
ODOO_DATABASE=

# Anthropic
ANTHROPIC_API_KEY=sk-ant-...

# Meta WhatsApp (se llenan después del setup de WA)
META_WA_TOKEN=
META_WA_PHONE_NUMBER_ID=
META_WA_BUSINESS_ACCOUNT_ID=
META_APP_SECRET=
META_WA_WEBHOOK_VERIFY_TOKEN=<token custom random>

# Webhooks
ODOO_WEBHOOK_SECRET=<generado con: openssl rand -hex 32>
```

```bash
chmod 600 .env
```

## Paso 6: Levantar

```bash
docker compose up -d

# Ver logs
docker compose logs -f n8n
```

Acceder a `https://n8n.mozaprintmx.com` con las credentials del .env.

## Paso 7: Backup automático

Crear cron diario:
```bash
crontab -e
```

```cron
# Backup diario de n8n data
0 3 * * * tar czf ~/backups/n8n-$(date +\%Y\%m\%d).tar.gz -C ~/n8n-mozaprint data 2>&1 | tee -a ~/backups/n8n-backup.log

# Mantener solo últimos 30 días
0 4 * * * find ~/backups -name "n8n-*.tar.gz" -mtime +30 -delete
```

## Paso 8: Monitoreo

Opciones:
- **BetterStack** (gratis hasta cierto volumen): healthcheck cada 30s a `https://n8n.mozaprintmx.com/healthz`
- **Uptime Kuma** self-hosted: si quieres todo en tus servers
- **Healthchecks.io**: dead-man-switch para verificar que el cron de backup corrió

Configurar al menos uno antes de poner el agente IA en producción.

## Paso 9: Importar workflows

Desde la UI:
1. Workflows → Import from File
2. Subir `ai-agent-respond.json` del repo
3. Configurar credentials (las que tengan IDs específicos requieren crearlas con los mismos nombres)
4. Test workflow con datos de prueba
5. Activate

## Comandos útiles

```bash
# Reiniciar n8n
docker compose restart n8n

# Ver logs en vivo
docker compose logs -f n8n

# Actualizar a última versión
docker compose pull
docker compose up -d

# Restaurar desde backup
docker compose down
tar xzf ~/backups/n8n-20260501.tar.gz -C ~/n8n-mozaprint/
docker compose up -d

# Entrar al container
docker compose exec n8n sh
```

## Troubleshooting

### Workflow no se dispara
- Verificar que esté "Active" (toggle arriba a la derecha)
- Verificar credentials en el nodo
- Ver execution log

### Error de SSL
- Verificar que el subdominio apunta a la IP del VPS
- Logs de Caddy: `docker compose logs caddy`

### Webhooks de Meta no llegan
- Verificar URL pública accesible: `curl https://n8n.mozaprintmx.com/healthz`
- Verificar verify token configurado en Meta
- Logs en tiempo real durante webhook test: `docker compose logs -f n8n`

### Performance lenta
- 2GB RAM puede ser poco si hay muchos workflows simultáneos
- Upgrade a CX31 (4GB) si la memoria está al 80%+ sostenido
- Para producción seria: migrar de SQLite a PostgreSQL

## Hardening adicional para producción

- Habilitar UFW: `ufw allow 22,80,443/tcp && ufw enable`
- Fail2ban para SSH
- SSH key only, no password
- Auto-updates de seguridad: `unattended-upgrades`
- Whitelist IPs en Caddyfile para acceso al UI de n8n
- Logs centralizados con Loki o similar (opcional)
