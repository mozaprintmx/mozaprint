# Estado Meta Business / WhatsApp — Mozaprint

> Estado de la configuración de Meta y WhatsApp Cloud API para el proyecto.
> Última actualización: **2026-09-01** — cambió el diseño: el webhook apunta a
> **Odoo**, no a n8n, y se usará un **número nuevo dedicado**. Ver
> [ADR 008](../decisions/008-whatsapp-nativo-odoo.md) y
> [guía de implementación](whatsapp-implementacion.md).
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

## Número nuevo para Odoo (decidido 2026-09-04)

| Campo | Valor |
|---|---|
| Uso | **Cloud API → Odoo**. Clientes, cotizaciones, seguimiento |
| Nombre visible | **`Mozaprint MX`** (lo revisa Meta; cambiarlo después es trámite) |
| WABA | La existente, **Moza Print** (`358071354051207`) |
| Número | Conseguido el 2026-09-04. **El número y sus IDs viven en Bitwarden**, no aquí |
| Estado | Pendiente de alta y verificación en Meta |

El número actual **`+52 1 56 3277 6277` NO se toca**: sigue en la WhatsApp Business
App, con sus llamadas, grupos y archivos pesados. Tras 6 semanas de prueba se
decide si se **intercambia** (ver bloque F de la guía de implementación).

> **Pasar un número a Cloud API no apaga la SIM.** Sigue recibiendo llamadas y SMS
> normales. Lo que se apaga es la **app de WhatsApp** en ese número: se pierden
> llamadas de WhatsApp y grupos, no la línea telefónica.

---

## ⚠️ Método de pago — antes del 30 de septiembre de 2026

Desde el **1 de octubre** Meta cobra los *service messages* (las respuestas dentro
de la ventana de 24 h, gratis hasta ahora). **Sin tarjeta registrada al 30 de
septiembre, Meta bloquea los mensajes salientes**: la cuenta recibe, pero no
puedes contestar.

- Tarjeta Visa/Mastercard/Amex que **permita cargos internacionales**
- Business Settings → WhatsApp Accounts → «Moza Print» → *Payment settings*
- Costo a nuestro volumen: ~$0.0080 USD por respuesta → **$2-3 USD/mes**

**Verificación de negocio: NO hace falta.** Sin verificar son 250 destinatarios
únicos por 24 h; el volumen real es de 40-80 conversaciones al mes.

---

## Pendientes — YA NO dependen de n8n

> **Cambio del 2026-09-01**: Odoo Online es URL pública, así que el webhook apunta
> a Odoo y **el VPS dejó de ser prerrequisito**. Pasos detallados en
> [`whatsapp-implementacion.md`](whatsapp-implementacion.md).

1. **Crear App en Meta for Developers** — tipo *Business*, portfolio `mozaprint_mx`
2. **Crear System User** — token permanente con `whatsapp_business_messaging` y
   `whatsapp_business_management`. A Bitwarden, nunca al repo
3. **Conseguir y verificar el número nuevo** — no debe estar registrado en WhatsApp
4. **Configurar webhook apuntando a la Callback URL de Odoo**, suscrito a
   `messages`, `message_status` y `message_template_status_update`
5. **Crear y enviar plantillas a aprobación de Meta** (24-72 h por plantilla).
   Empezar por las de **utilidad** ($0.0080 USD vs $0.0436 de marketing):
   - `cotizacion_lista`
   - `anticipo_recibido`
   - `pedido_en_produccion`
   - `arte_requerido`

---

## ⚠️ Coexistence — DESCARTADO el 2026-09-01

**Meta no lo ofrece a un negocio final.** El alta de un número que viene de la
WhatsApp Business App se hace por *Embedded Signup*, que exige ser **Solution
Partner o Tech Provider**. Ver `decisions/003` (cerrada) y `decisions/008`.

**En su lugar**: número nuevo dedicado para Odoo. El número actual
`+52 1 56 3277 6277` **no se toca** y sigue en la app del celular.

La tabla de abajo se conserva solo como referencia de qué se pierde al migrar un
número a Cloud API, por si algún día se decide migrar el principal.

| Funcionalidad | Estado en Coexistence |
|---|---|
| Mensajes 1:1 con clientes | ✓ Funcionan en app y en Cloud API |
| Llamadas | ✓ Solo en la app móvil, no accesibles desde API |
| Grupos | ✓ Solo en la app, NO sincronizan a la API |
| Listas de difusión | ✗ Desactivadas — reemplazar con plantillas API |
| Editar / Revocar mensajes | ✗ No disponible en mensajes 1:1 vía API |
| View-once / Mensajes que desaparecen | ✗ No disponible |

~~**Requisito operativo crítico**: abrir la WA Business App cada 14 días.~~ **Ya no
aplica**: sin Coexistence no hay conexión que expire. El número actual sigue siendo
una cuenta normal de WhatsApp Business App.

---

## Decisión de orden

La base de Meta está lista (WABA aprobada, número registrado, accesos configurados). Los pasos restantes dependen de tener un endpoint público para el webhook.

~~**Decisión**: pausar y priorizar el VPS de n8n.~~ **Revertida el 2026-09-01.**

**Decisión vigente**: el webhook apunta a **Odoo**, que ya tiene URL pública, así
que no hay que esperar a ningún VPS. El orden es: validar el módulo en una base de
test con el número de prueba de Meta → conseguir el número nuevo → conectar en
producción. La IA viene después y no cambia esta arquitectura.

---

## Notas de acceso

- El correo `mozaprintmx@gmail.com` pertenece a la cuenta de Facebook de Karina
- El acceso de administrador principal es vía cuenta personal de Juan Carlos
- Los tokens e IDs de la App (App Secret, System User token) se almacenan en **Bitwarden** — no en el repo
