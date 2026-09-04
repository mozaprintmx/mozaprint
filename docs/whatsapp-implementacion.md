# WhatsApp nativo en Odoo — guía de implementación

> Plan de ejecución de la [ADR 008](../decisions/008-whatsapp-nativo-odoo.md).
> Objetivo: **que el equipo trabaje WhatsApp desde Odoo como personas**. La IA es
> una capa posterior y no cambia nada de lo que sigue.

## El escenario, decidido el 2026-09-04

1. **Número nuevo**, ya conseguido.
2. Se instala el módulo **WhatsApp** en Odoo.
3. El número nuevo se integra y **se prueba con clientes reales** unas semanas.
4. Al final se decide el definitivo: quedarse con el nuevo, o **intercambiar** y
   pasar el actual (`5632776277`) a Odoo, ya con la herramienta probada.

| Decisión | Valor |
|---|---|
| Tráfico durante la prueba | **Un solo canal**: el header de `/shop` |
| Nombre visible del remitente | **`Mozaprint MX`** |
| Criterios de decisión final | (a) contestar desde el celular · (b) ahorrar tiempo al cotizar |

### Por qué un número nuevo y no el de siempre

**Coexistence no está a nuestro alcance.** El alta de un número que viene de la
WhatsApp Business App se hace por *Embedded Signup*, y Meta es explícita:

> *"You must already be a Solution Partner or Tech Provider."*

Y aunque se hubiera conseguido, no habría servido: los mensajes enviados desde el
celular llegan como **`smb_message_echoes`**, un campo de webhook **distinto** de
`messages`, que es al que se suscribe Odoo. El historial habría quedado partido
igual.

---

## ⚠️ Fecha límite: 30 de septiembre de 2026

**Desde el 1 de octubre Meta cobra los *service messages*** — las respuestas
normales dentro de la ventana de 24 h, gratis hasta hoy.

> *"Effective October 1, 2026, Meta will charge for service messages, which have
> not been charged since November 2024."*

**Sin método de pago registrado al 30 de septiembre, Meta bloquea los mensajes
salientes**: la cuenta sigue recibiendo, pero no puedes contestar.

Por eso **el método de pago es el paso A2, no el último**.

| | |
|---|---|
| Costo por respuesta | ~**$0.0080 USD** |
| A 40-80 conversaciones/mes | **$2-3 USD/mes** — no es factor de decisión |
| Verificación de negocio | **NO hace falta**: sin verificar son 250 destinatarios únicos/24 h |

---

## Bloque A · Meta

### A1 · App y WABA

- [ ] [Meta for Developers](https://developers.facebook.com) → **My Apps** →
      *Create App*. Nombre `Odoo`, tipo **Business**, portfolio `mozaprint_mx`
      (Business ID `100794159106337`)
- [ ] Panel → **WhatsApp** → *Set up*
- [ ] **Usar la WABA existente** «Moza Print» (`358071354051207`), no crear otra:
      conserva la identidad de negocio y facilita el intercambio de números del
      paso 4. Una WABA admite varios números
- [ ] Anotar **App ID** y **App Secret** (Settings → Basic) → **Bitwarden**

### A2 · Método de pago ← primero, no al final

- [ ] Business Settings → **WhatsApp Accounts** → «Moza Print» → *Payment settings*
- [ ] Tarjeta Visa/Mastercard/Amex que **permita cargos internacionales**
- [ ] Confirmar que quedó activa **antes del 30 de septiembre**

### A3 · Token permanente

⚠️ El token que Meta muestra por defecto **caduca en 24 h**. No sirve.

- [ ] Business Settings → **System Users** → crear uno
- [ ] Asignarle la app y la WABA con permiso de administración
- [ ] Generar token con **exactamente**: `whatsapp_business_messaging` y
      `whatsapp_business_management`
- [ ] → **Bitwarden**. Nunca en el repo, nunca en un commit

### A4 · Alta del número nuevo

- [ ] Confirmar que **no está registrado en WhatsApp** (ni personal ni Business
      App). Si lo estuvo: **borrar la cuenta** desde la app — desinstalar no basta
- [ ] WhatsApp → **API Setup** → *Add phone number*
- [ ] **Nombre visible: `Mozaprint MX`** — lo revisa Meta y cambiarlo después es
      trámite. Si lo rechaza, reintentar con `Mozaprint`
- [ ] Verificar con el PIN de 6 dígitos (SMS o llamada)
- [ ] Anotar su **Phone Number ID** → Bitwarden
- [ ] Completar el perfil: descripción, categoría, logo, sitio web

> 🔁 **Mantén la línea activa.** Para operar, el número vive en Meta y no necesitas
> el chip encendido; pero si dejas morir la línea, la operadora **recicla el
> número**. Ponle recargas en calendario.

---

## Bloque B · Validar el módulo en test

Base lista: `https://mozaprintmx-watest.odoo.com/` (db `mozaprintmx-watest`,
**saas~19.3+e**, copia de producción). `ODOO_TEST_URL` ya apunta ahí.

Se usa el **número de prueba gratuito de Meta** — 5 destinatarios verificados, sin
tocar el número real. Riesgo: cero.

- [ ] Instalar `whatsapp`, `whatsapp_crm`, `whatsapp_sale`
- [ ] WhatsApp → Configuración → **Cuentas de WhatsApp Business** → nueva, con los
      valores de A1/A3 y el **Phone Number ID del número de prueba**
- [ ] Inventar un **Webhook Verify Token** propio y guardarlo
- [ ] Copiar la **Callback URL** que genera Odoo (bajo «Recibiendo mensajes»)
- [ ] Meta → WhatsApp → *Configuration* → Webhooks: pegar URL y token, y suscribir
      `messages` · `message_status` · `message_template_status_update`
- [ ] Meta → *Send and receive messages* → agregar tu celular como destinatario

### Las 7 pruebas

| # | Prueba | Qué demuestra |
|---|---|---|
| 1 | Mensaje **desde Odoo** al celular | Saliente |
| 2 | Responder **desde el celular** y verlo en Discuss | Entrante |
| 3 | La conversación queda ligada a un **contacto** | Integración CRM |
| 4 | Enviar **cotización con PDF** desde `sale.order` | Caso de uso central |
| 5 | Abrirla desde el **chatter** del cliente | Seguimiento en contexto |
| 6 | ⭐ **Contestar desde la app móvil de Odoo** | Criterio (a) de la decisión final |
| 7 | `audit_lineas_facturables.py --target test --max-bloques 0` | El módulo no genera código facturable |

> **Si la 7 falla, detenerse**: algo está creando código de Studio y eso reabre el
> problema de la [ADR 007](../decisions/007-retiro-motor-cotizacion-costo-codigo.md).
>
> **La 6 es la más importante.** Es la preocupación principal del operador y lo
> único que no se puede predecir leyendo. Hacerla en serio, no de paso.

---

## Bloque C · Producción

Solo con las 7 en verde.

- [ ] Instalar `whatsapp`, `whatsapp_crm`, `whatsapp_sale` en producción
- [ ] Configurar la cuenta con el **Phone Number ID del número nuevo**
- [ ] Repuntar el webhook de Meta a la **Callback URL de producción**
- [ ] `python scripts/audit_lineas_facturables.py --max-bloques 0` → sigue en **0**
- [ ] Enviar una cotización real a un número propio **antes** de usarlo con cliente

---

## Bloque D · Plantillas

Se mandan a aprobación **en paralelo al bloque B**: Meta tarda 24-72 h por
plantilla y son el cuello de botella del arranque.

Empezar por las de **utilidad** ($0.0080 vs $0.0436 de marketing):

| Plantilla | Para qué |
|---|---|
| `cotizacion_lista` | Con link o PDF. **La más importante** |
| `anticipo_recibido` | |
| `pedido_en_produccion` | |
| `arte_requerido` | |

> Con el canal único hay tráfico entrante, así que muchas conversaciones abrirán
> con el cliente escribiendo — ahí contestas libre, sin plantilla. Las plantillas
> son para **reabrir conversaciones frías**.

---

## Bloque E · El canal único

El sitio tiene enlaces de WhatsApp al `5632776277` en **8 vistas**:

| Vista | Dónde | En la prueba |
|---|---|---|
| **5029** `website_sale.products_oe_structure_products_header_shop` | Header de `/shop` | ⬅️ **cambia al número nuevo** |
| 4095 `header_social_links` | Header global | se queda |
| 2342 `inicio` · 5020 `inicio_ed64ed` | Home | se queda |
| 3884 `servicios` | Página de servicios | se queda |
| 5049 · 5052 `kits-de-bienvenida` | Landings con UTM | se queda |
| 4725 `landing-page_321f1b` | Landing de catálogos | se queda |

*(Además hay `tel:` y texto plano en 4121, 4548 y 3886 — son teléfono, no
WhatsApp, y no se tocan.)*

**Por qué `/shop`**: es donde alguien mira productos y pregunta precio —la
intención más alta—, está aislado en una sola vista, y revertirlo es un cambio.

> ⚠️ **`arch_db` es campo traducido.** Al escribirlo por API hay que **iterar los
> idiomas** (`en_US` primero, luego los activos). Escribir solo el de la sesión
> deja el sitio roto para el visitante con el backend viéndose bien. **Ya mordió a
> dos scripts de este repo.**
>
> Por eso el cambio va con **script** (`scripts/cambiar_whatsapp_shop.py`, dry-run
> por defecto y `--rollback`, siguiendo el patrón de `fix_vista_contactanos.py`),
> **no editando a mano en el editor web**.

---

## Bloque F · El período de prueba

**Duración: 6 semanas**, con revisión a las 3. A ~36 cotizaciones/mes son ~50 de
muestra, suficiente para decidir con datos y no con corazonada.

### Criterio (a) · ¿Puedes contestar desde el celular?

Lleva la cuenta de las conversaciones que respondiste **desde la app de Odoo**
frente a las que pospusiste hasta llegar a la computadora. Si el segundo número es
alto, **el intercambio de números es mala idea** y conviene quedarse con dos líneas.

### Criterio (b) · ¿Ahorra tiempo al cotizar?

Compara contra hoy: de lead a cotización enviada. Hoy es todo manual. La señal
buena es mandarla desde el propio `sale.order`, con el historial pegado al cliente,
sin copiar datos entre ventanas.

### Cómo se decide

| Resultado | Decisión |
|---|---|
| Los dos criterios bien | **Intercambiar**: el `5632776277` pasa a Odoo y el sitio vuelve a un solo número |
| Solo (b) bien | Dos números: Odoo para cotizar, celular para conversar |
| (a) mal | No intercambiar. Reevaluar si Odoo es el canal de conversación correcto |

---

## Cómo se trabaja el día a día

### La ventana de 24 horas — la regla que más confunde

| Situación | Qué se puede mandar |
|---|---|
| El cliente escribió hace **menos de 24 h** | **Lo que sea**: texto libre, PDF, imágenes |
| Pasaron **más de 24 h** | **Solo una plantilla aprobada** |

Es de Meta, no de Odoo. En la práctica: si el cliente escribió hoy, contesta
normal; si la conversación se enfrió, arranca con plantilla.

### Límites de archivos

| Tipo | Máximo |
|---|---|
| **Documentos** (PDF, AI, EPS) | **100 MB** |
| Imágenes | **5 MB** — una foto grande va como documento |
| Video / audio | 16 MB |

### Dónde vive cada cosa

| Qué | Dónde en Odoo |
|---|---|
| Conversaciones | **Discuss**, un canal por cliente |
| Historial de un cliente | **Chatter** de su ficha |
| Mandar una cotización | Botón de WhatsApp en `sale.order` |
| Plantillas | WhatsApp → Configuración → Plantillas |

---

## Riesgos

| Riesgo | Mitigación |
|---|---|
| **No registrar la tarjeta antes del 30-sep** | Es A2 y va primero. Sin eso no puedes contestar desde el 1 de octubre |
| Meta rechaza el nombre visible | `Mozaprint MX` coincide con marca y dominio; riesgo bajo. Reintentar con `Mozaprint` |
| El módulo genera código facturable | Prueba 7 antes de producción |
| Romper `/shop` al cambiar el enlace | Script con dry-run, rollback y escritura por idioma |
| Que el token se revoque | En Bitwarden; si Odoo deja de enviar, es lo primero que hay que mirar |
| Clientes escribiendo a dos números | Costo aceptado del canal único, acotado a 6 semanas |
| Que un upgrade rompa el módulo | Es módulo oficial de Odoo. Entra al checklist post-upgrade |

---

## Lo que esta etapa NO incluye

- **IA que conteste** — Fase 6 del roadmap; depende de esto, no al revés.
- **Campañas de marketing por WhatsApp** — necesita `marketing_automation_whatsapp`
  y plantillas de marketing aprobadas; va después.
- **El intercambio de números** — se decide al final del bloque F, con datos.
- **El livechat del sitio** — descartado explícitamente el 2026-09-01.
