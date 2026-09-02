# WhatsApp nativo en Odoo — guía de implementación

> Plan de ejecución de la [ADR 008](../decisions/008-whatsapp-nativo-odoo.md).
> Objetivo de esta primera etapa: **que el equipo trabaje WhatsApp desde Odoo como
> personas**. La IA es una capa posterior y no cambia nada de lo que sigue.
>
> Decisiones tomadas el 2026-09-01:
> - **Número nuevo y dedicado.** El número actual (`+52 1 56 3277 6277`) **NO se
>   toca**: sigue en la WhatsApp Business App y el equipo no cambia su día a día.
> - **El módulo se valida en una base de test**; el número real solo se conecta
>   cuando toque producción.

---

## Por qué un número nuevo y no el de siempre

Se investigó a fondo y **Coexistence no está a nuestro alcance**. Documentación de
Meta sobre el alta de números que vienen de la WhatsApp Business App:

> *"You must already be a Solution Partner or Tech Provider."*

Ese flujo (**Embedded Signup**) está pensado para que un proveedor dé de alta a sus
clientes, no para que un negocio conecte su propio número. Registrarse como Tech
Provider y pasar App Review es un proyecto entero, desproporcionado aquí.

Las tres salidas eran: migrar el número actual del todo a Cloud API (el equipo
pierde la app del celular), contratar un BSP con coexistence (que se quedaría con
el webhook, rompiendo el diseño), o **un número nuevo dedicado**. Se eligió la
tercera: es la única **reversible al 100%** y con **riesgo cero** para la operación
diaria.

> **Nota técnica que confirma el diagnóstico**: en coexistence, los mensajes que el
> equipo manda desde el celular llegan como **`smb_message_echoes`**, un campo de
> webhook **distinto** de `messages`. Odoo se suscribe a `messages`,
> `message_status` y `message_template_status_update` — no a ése. Aunque
> hubiéramos conseguido coexistence, **Odoo no habría visto lo que se contesta
> desde el teléfono**.

---

## Fase 1 · Validar el módulo en test (sin tocar nada real)

Se usa el **número de prueba gratuito de Meta**, que no requiere verificación de
negocio y permite mandar a **5 destinatarios verificados**. Riesgo: cero.

### 1.1 · Preparar la base de test

✅ **Lista desde el 2026-09-01**: `https://mozaprintmx-watest.odoo.com/`
(db `mozaprintmx-watest`, **saas~19.3+e**, copia de producción con 5,454 productos
y 468 cotizaciones). `ODOO_TEST_URL` ya apunta ahí.

Los cuatro módulos están **disponibles y sin instalar**: `whatsapp`,
`whatsapp_crm`, `whatsapp_sale`, `marketing_automation_whatsapp`.

> La base anterior (`…-0818`) quedó en estado `/_odoo/upgrade/` y se abandonó.

### 1.2 · Crear la app en Meta

- [ ] Ir a [Meta for Developers](https://developers.facebook.com) → **My Apps** →
      **Create App**
- [ ] Nombre: `Odoo` · Tipo: **Business** · Portfolio: `mozaprint_mx`
      (Business ID `100794159106337`)
- [ ] En el panel, sección **WhatsApp** → **Set up**
- [ ] Seleccionar la WABA existente: **Moza Print** (`358071354051207`)

> Meta entrega aquí un **número de prueba** con su Phone Number ID. Ese es el que
> se usa en toda la fase 1.

### 1.3 · Generar el token permanente

⚠️ **No usar el token temporal** que Meta muestra por defecto: caduca en 24 h.

- [ ] Business Settings → **System Users** → crear uno
- [ ] Asignarle la app y la WABA con permiso de administración
- [ ] Generar token con **exactamente** estos permisos:
      - `whatsapp_business_messaging`
      - `whatsapp_business_management`
- [ ] **Guardar el token en Bitwarden.** Nunca en el repo, nunca en un commit.

### 1.4 · Anotar los cinco valores

| Valor | Dónde se obtiene |
|---|---|
| **App ID** | Panel de la app |
| **App Secret** | Panel de la app → Settings → Basic |
| **Account ID** (WABA ID) | WhatsApp → API Setup |
| **Phone Number ID** | WhatsApp → API Setup (el del número de prueba) |
| **Token permanente** | El del System User (1.3) |

Todo a **Bitwarden**.

### 1.5 · Instalar y configurar el módulo en test

- [ ] Instalar **`whatsapp`** (Aplicaciones → buscar «WhatsApp»)
- [ ] Instalar `whatsapp_crm` y `whatsapp_sale`
- [ ] WhatsApp → Configuración → **Cuentas de WhatsApp Business** → nueva
- [ ] Capturar los cinco valores de 1.4
- [ ] Inventar un **Webhook Verify Token** propio (cadena aleatoria) y guardarlo
- [ ] Copiar de Odoo la **Callback URL** (aparece bajo «Recibiendo mensajes»)

### 1.6 · Cerrar el circuito del webhook en Meta

- [ ] Meta → WhatsApp → **Configuration** → Webhooks → Edit
- [ ] Pegar la **Callback URL** de Odoo y el **Verify Token**
- [ ] Suscribirse a los tres campos:
      `messages` · `message_status` · `message_template_status_update`
- [ ] Meta → **Send and receive messages** → agregar hasta 5 números de prueba
      (el celular de JC entre ellos) y confirmar el código

### 1.7 · Las pruebas que de verdad importan

Estas son la puerta de decisión. **Ninguna requiere el número real.**

| # | Prueba | Qué demuestra |
|---|---|---|
| 1 | Mandar un mensaje **desde Odoo** al celular de prueba | El saliente funciona |
| 2 | Contestar **desde el celular** y verlo llegar a Discuss | El webhook entra |
| 3 | Que la conversación quede ligada a un **contacto** de Odoo | La integración con CRM sirve |
| 4 | Enviar una **cotización con su PDF** desde `sale.order` | El caso de uso central |
| 5 | Abrir la conversación desde el **chatter** del cliente | El seguimiento en contexto |
| 6 | Crear una plantilla en Odoo y **mandarla a aprobación** | El circuito de plantillas cierra |
| 7 | `python scripts/audit_lineas_facturables.py --target test --max-bloques 0` | El módulo **no** genera código facturable |

> Si la prueba 7 falla, **detenerse**: algo del módulo está creando código de
> Studio y eso reabre el problema de la ADR 007.

---

## Fase 2 · Conseguir el número nuevo

Se hace en paralelo a la fase 1, porque los tiempos de Meta no dependen de nosotros.

### Lo primero: Meta NO vende números

El número de prueba que da Meta es **solo para desarrollo** — no se puede usar en
producción y solo alcanza a 5 destinatarios verificados. **El número de producción
lo consigues tú**, por fuera, y luego lo das de alta en Meta.

### Los tres requisitos, y son los tres

| Requisito | Por qué muerde |
|---|---|
| **Que NO esté registrado en WhatsApp** | Ni personal ni Business App. Si lo estuvo, hay que **borrar esa cuenta** desde la app (Ajustes → Cuenta → Eliminar) y esperar. No basta con desinstalar |
| **Que reciba SMS o llamada** | Meta manda un PIN de 6 dígitos. Los móviles reciben SMS; los fijos y 800 se verifican **por llamada de voz** |
| **Que sea del negocio y se quede** | Una vez verificado, ese número es la identidad de Mozaprint en WhatsApp. Cambiarlo después es engorroso |

> ⚠️ **Ese número queda inutilizable para la app de WhatsApp.** Pasa a ser
> exclusivo de Cloud API. **No uses un celular personal ni el de nadie del equipo.**

### Qué tipo de número sirve

Cloud API es **más permisivo que la app gratuita**: acepta móvil, fijo, 800 y
también **virtuales/VoIP**, siempre que el proveedor deje recibir SMS o llamada.
(La WhatsApp Business App gratuita, en cambio, rechaza los VoIP — por eso hay
tanta información contradictoria en internet: casi toda habla de la app, no de la
API.)

| Opción | Costo | Veredicto |
|---|---|---|
| **SIM prepago mexicana** (Telcel, AT&T, Movistar) | ~$50-200 MXN + recargas | ✅ **Recomendada.** Lo más barato y lo que menos falla. Lada 55 = identidad local, que en B2B mexicano importa |
| **Fijo de la oficina** | $0 si ya existe y está libre | ✅ Buena si hay uno sin usar. Se verifica por llamada y refuerza la identidad de empresa |
| **Virtual / VoIP** (Twilio, Telnyx…) | Mensualidad en USD | ⚠️ Funciona con Cloud API, pero **agrega un punto de falla**: hay proveedores que bloquean el SMS de verificación de WhatsApp. Solo si ya usas uno y sabes que deja recibir |
| Número de prueba de Meta | $0 | ❌ Solo desarrollo. No sirve en producción |

**Recomendación**: SIM prepago de Telcel con lada **55**. Es lo más simple, cuesta
casi nada y no dependes de la política de un tercero.

> 🔁 **Mantén la SIM activa.** Para la operación diaria el número vive en Meta y no
> necesitas el chip encendido, pero si dejas morir la línea la operadora **recicla
> el número** y se lo asigna a alguien más. Ponle recarga con calendario.

### Pasos

- [ ] Conseguir el número (SIM nueva, sin registrar en WhatsApp)
- [ ] Verificar que recibe SMS antes de tocar nada en Meta
- [ ] Decidir el **nombre visible** del remitente — es lo que ve el cliente en el
      chat. Debe cumplir las reglas de nombre comercial de Meta y **cambiarlo
      después es un trámite**. Sugerido: `Mozaprint`
- [ ] Meta → WhatsApp → **API Setup** → *Add phone number*
- [ ] Recibir el PIN de 6 dígitos y verificar
- [ ] Anotar su **Phone Number ID** (distinto al del número de prueba) → Bitwarden

> **Decisión de negocio pendiente**: si este número aparece en el sitio, en las
> cotizaciones o en la firma de correo. Se puede posponer — arranca siendo interno,
> para avisos y cotizaciones a clientes que ya nos escribieron, y se publica cuando
> el equipo lo tenga dominado.

---

## Fase 3 · Producción

Solo cuando las 7 pruebas de 1.7 estén en verde.

- [ ] Instalar `whatsapp`, `whatsapp_crm`, `whatsapp_sale` en producción
- [ ] Configurar la cuenta con los mismos App ID / Secret / WABA / token, pero con
      el **Phone Number ID del número nuevo**
- [ ] Repuntar el webhook de Meta a la **Callback URL de producción**
- [ ] `python scripts/audit_lineas_facturables.py --max-bloques 0` → debe seguir en **0**
- [ ] Mandar una cotización real a un número propio antes de usarlo con un cliente

### Plantillas a aprobación de Meta (24-72 h)

Empezar por las de **utilidad**, que cuestan **$0.0080 USD** contra $0.0436 de las
de marketing, y son las que un cliente B2B agradece:

- `cotizacion_lista` — con link o PDF
- `anticipo_recibido`
- `pedido_en_produccion`
- `arte_requerido`

---

## Cómo se trabaja el día a día (lo que hay que explicarle al equipo)

### La ventana de 24 horas — la regla que más confunde

| Situación | Qué se puede mandar |
|---|---|
| El cliente escribió hace **menos de 24 h** | **Lo que sea**: texto libre, PDF, imágenes |
| Pasaron **más de 24 h** | **Solo una plantilla aprobada** por Meta |

Es de Meta, no de Odoo, y no hay forma de saltársela. En la práctica: **si el
cliente escribió hoy, contesta normal; si la conversación se enfrió, arranca con
plantilla.**

### Dónde vive cada cosa

| Qué | Dónde en Odoo |
|---|---|
| Conversaciones | **Discuss**, un canal por cliente |
| Historial de un cliente | **Chatter** de su ficha |
| Mandar una cotización | Botón de WhatsApp en `sale.order` |
| Plantillas | WhatsApp → Configuración → Plantillas |

---

## Riesgos y qué hacer

| Riesgo | Mitigación |
|---|---|
| Que el módulo genere código facturable | Prueba 7 en test **antes** de producción |
| Que el token permanente caduque o se revoque | En Bitwarden; si Odoo deja de enviar, sospechar de esto primero |
| Que el número nuevo confunda a los clientes | Arranca interno: solo a quien ya nos escribió |
| Que el equipo no adopte Discuss | Es la razón de haber elegido número nuevo: la app del celular sigue viva |
| Que un upgrade rompa el módulo | Es módulo oficial de Odoo. Entra al checklist post-upgrade |

---

## Lo que esta etapa NO incluye

- **IA que conteste.** Es la Fase 6 del roadmap y depende de esto, no al revés.
- **El livechat del sitio.** Descartado explícitamente el 2026-09-01.
- **Migrar el número principal.** Se decide después, con datos de uso real.
- **Campañas de marketing por WhatsApp.** Necesita `marketing_automation_whatsapp`
  y plantillas de marketing aprobadas; va después de que esto funcione.
