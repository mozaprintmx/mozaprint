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

> ⚠️ **LO DE ABAJO ES HISTÓRICO. Los permisos de Rosy cambiaron después** (confirmado por
> JC el 2026-08-25). Estado real verificado ese día en producción y en test:
>
> | Usuario | Ventas | Productos / Crear | Permisos de acceso |
> |---|---|---|---|
> | Juan Carlos Asomoza | **Administrador** | ✓ | ✓ |
> | Karina Asomoza | **Administrador** | ✓ | ✓ |
> | Rosy Ponce | **Administrador** | ✓ | — |
>
> La reducción de 2026-05-31 que describe la tabla siguiente **ya no está vigente**: Rosy
> volvió a *Ventas / Administrador*. Se conserva el registro porque explica el criterio con
> el que se decidió en su momento —usuario técnico con permiso mínimo— y ese criterio
> sigue siendo válido aunque la configuración de hoy sea otra.

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
| `scripts-repo-2026-09` | Scripts JSON-2 de este repo (`ODOO_API_KEY` del `.env` raíz): derivación de técnicas post-sync, respaldos, auditorías y herramientas de la Fase 8 | ✓ Activa desde 2026-09-30 · **vence 2026-12-28** | Bitwarden + `.env` raíz local (fuera de git) |
| `n8n-produccion` (probable) | La llave anterior del `.env` raíz, la que usaban esos mismos scripts | ✗ Caducó ~2026-08-29 (primer 401 en los logs del sync); ya no aparece en Odoo | — |
| `proveedores-sync` | Sync de catálogo de proveedores (v3, por JSON-2) | Pendiente — se genera al construir la v3 (Fase 8) | — |

**Rotación**: las llaves de Odoo caducan en silencio y, cuando mueren, lo que dependía de
ellas falla sin avisar (la derivación de técnicas estuvo un mes caída por eso). Generar la
sucesora **antes** del vencimiento, cambiarla en el `.env` y probar con una lectura.

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
