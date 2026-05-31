# Usuarios Odoo — Mozaprint

> Referencia de usuarios con acceso a Odoo, sus roles, permisos, y las decisiones detrás de la configuración de acceso para integraciones técnicas.

---

## Usuario técnico para API / integraciones

### Decisión: reutilizar Rosy Ponce en lugar de crear `integration@`

**Fecha**: 2026-05-31

**Contexto**: para conectar n8n a Odoo vía JSON-2 API se necesita un usuario con API key. La opción ideal sería un usuario dedicado `integration@mozaprintmx.com` con scope mínimo.

**Decisión tomada**: reutilizar el usuario existente **Rosy Ponce** (`rosy_ponce@mozaprintmx.com`).

**Razón**: en Odoo Online cada usuario activo es facturable. Rosy es usuaria administrativa que casi no usa Odoo activamente — crear un usuario adicional dedicado agregaría costo sin necesidad real en esta etapa.

**Condición de revisión**: cuando el negocio crezca y el costo de un usuario adicional sea menor que el riesgo de mezclar permisos, crear `integration@` con scope mínimo y devolver a Rosy solo permisos financieros.

---

## Permisos de Rosy Ponce (rosy_ponce@mozaprintmx.com)

Antes de esta configuración tenía permisos casi-admin. Se redujeron al mínimo necesario para las integraciones de la API.

| Módulo / Permiso | Antes | Después | Razón |
|---|---|---|---|
| Ventas | Administrador | Usuario | La API no necesita gestionar equipos ni configuración |
| Inventario | Administrador | Usuario | La API lee/escribe stock, no configura almacenes |
| Compras | Administrador | Usuario | La API crea POs, no configura proveedores |
| Contabilidad | Administrador | Facturación | Suficiente para los reportes que descarga Rosy |
| Banco — Validar cuenta bancaria | Habilitado | **Quitado** | No necesario para ningún flujo de la API |
| Productos — Crear/editar | Habilitado | Crear (mantenido) | La API necesita crear/actualizar productos en sync de proveedores |
| Contactos — Crear | Habilitado | Crear (mantenido) | La API crea clientes nuevos desde WhatsApp |

---

## API keys generadas

| Nombre | Propósito | Estado | Almacenamiento |
|---|---|---|---|
| `n8n-produccion` | Autenticación de n8n → Odoo JSON-2 API | ✓ Activa | Bitwarden |
| `proveedores-sync` | Script de sync de catálogo de proveedores | Pendiente — generar en Fase 8 | — |

**Regla**: ninguna API key se guarda en el repo ni en variables de entorno sin cifrar. Todas van a Bitwarden y se inyectan en n8n como credentials.

---

## Gestor de secretos

**Herramienta adoptada**: Bitwarden

Centraliza:
- API keys de Odoo
- Tokens de Meta WhatsApp
- API keys de Anthropic / OpenAI
- Credenciales de proveedores (Promo Opción, 4Promotional, Innovation Line)
- Contraseñas de infraestructura (VPS, n8n)

---

## Ruta de migración futura

Cuando el negocio crezca y justifique el costo:

1. Crear usuario `integration@mozaprintmx.com` en Odoo con **solo** los permisos mínimos de API:
   - Ventas: Usuario
   - Productos: Crear
   - Contactos: Crear
   - Inventario: Usuario
   - Sin acceso a Contabilidad ni Compras
2. Generar nueva API key `n8n-produccion-v2` con ese usuario
3. Actualizar credentials en n8n
4. Revocar API key del usuario Rosy
5. Devolver a Rosy permisos solo financieros (Contabilidad: Facturación)
6. Archivar este documento con la nota de migración completada
