# Estado Meta Business / WhatsApp — Mozaprint

> Estado de la configuración de Meta y WhatsApp Cloud API para el proyecto.
> Última actualización: 2026-06-01
> Para el análisis técnico de Coexistence Mode ver `decisions/003-coexistence-whatsapp.md`

---

## Portfolio comercial (Meta Business Manager)

| Campo | Valor |
|---|---|
| Nombre | mozaprint_mx |
| Business ID | 100794159106337 |
| Verificación de negocio | No requerida para este caso de uso |
| Administrador principal | Juan Carlos Asomoza Ponce (control total) |
| Acceso adicional | Karina Asomoza — Community Manager (control total) |

La verificación formal de negocio ante Meta **no es cuello de botella** para el caso de uso de Mozaprint (volumen bajo, sin necesidad de créditos publicitarios elevados). No bloquea el avance.

---

## WhatsApp Business Account (WABA)

| Campo | Valor |
|---|---|
| Nombre | Moza Print |
| WABA ID | 358071354051207 |
| Estado | Aprobada |
| Número registrado | +52 1 56 3277 6277 |
| Estado del número | Sin conexión a Cloud API (registrado en WA Business App únicamente) |

El número está activo en la **WhatsApp Business App** del celular del negocio. La conexión a Cloud API (que habilita el agente IA) se activa en Fase 4, una vez que n8n tenga URL pública.

---

## Pendientes — requieren n8n desplegado

Estos pasos se completan de corrido una vez que el VPS de n8n esté levantado y `n8n.mozaprintmx.com` tenga URL pública:

1. **Crear App en Meta for Developers** — obtener App ID y App Secret
2. **Crear System User** — token permanente para la integración (no usar token personal)
3. **Activar Coexistence** — conectar el número a Cloud API manteniendo la app móvil activa
4. **Configurar webhook** — URL apuntando al endpoint de n8n, verify token custom
5. **Crear y enviar plantillas a aprobación de Meta**:
   - `lead_received`
   - `cotizacion_lista`
   - `quote_followup_24h`
   - `orden_confirmada`
   - `arte_requerido`
   - Tiempo estimado de aprobación por plantilla: 24-72h

---

## Limitaciones conocidas de Coexistence

Documentadas aquí como referencia rápida. Ver análisis completo en `decisions/003-coexistence-whatsapp.md`.

| Funcionalidad | Estado en Coexistence |
|---|---|
| Mensajes 1:1 con clientes | ✓ Funcionan en app y en Cloud API |
| Llamadas | ✓ Solo en la app móvil, no accesibles desde API |
| Grupos | ✓ Solo en la app, NO sincronizan a la API |
| Listas de difusión | ✗ Desactivadas — reemplazar con plantillas API |
| Editar / Revocar mensajes | ✗ No disponible en mensajes 1:1 vía API |
| View-once / Mensajes que desaparecen | ✗ No disponible |

**Requisito operativo crítico**: alguien del equipo debe abrir la WA Business App **al menos una vez cada 14 días**. Si no se abre, la conexión Coexistence expira y hay que reconectar. Responsable: Juan Carlos Asomoza (WhatsApp Admin).

---

## Decisión de orden

La base de Meta está lista (WABA aprobada, número registrado, accesos configurados). Los pasos restantes dependen de tener un endpoint público para el webhook.

**Decisión**: pausar la configuración de WhatsApp aquí y priorizar el despliegue del VPS de n8n (Fase 4). Una vez que `n8n.mozaprintmx.com` esté operativo, se completa toda la conexión de WhatsApp de corrido en una sola sesión.

Esto elimina el riesgo de configurar webhooks hacia una URL temporal o local.

---

## Notas de acceso

- El correo `mozaprintmx@gmail.com` pertenece a la cuenta de Facebook de Karina
- El acceso de administrador principal es vía cuenta personal de Juan Carlos
- Los tokens e IDs de la App (App Secret, System User token) se almacenan en **Bitwarden** — no en el repo
