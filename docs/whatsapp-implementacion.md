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

## Bloque A · Meta — ✅ COMPLETADO salvo A4

App creada: **`Mozaprintmx Odoo`**, App ID `1417946286897018`, portfolio
`mozaprint_mx`. Usuario del sistema `odoo-whatsapp` con token permanente.
Método de pago **agregado**. Falta solo dar de alta el número real (A4), que
se hace ya en el bloque C.

> ⚠️ Meta usa ahora un flujo **por casos de uso**: no hay producto «WhatsApp»
> en la barra lateral, todo vive dentro de *Casos de uso → Conectar en WhatsApp*.
> Y **ignora «Conviértete en proveedor de tecnología»**: es el camino de Tech
> Provider que descartamos.

### A1 · App y WABA ✅

- [x] [Meta for Developers](https://developers.facebook.com) → **My Apps** →
      *Create App*. Nombre `Odoo`, tipo **Business**, portfolio `mozaprint_mx`
      (Business ID `100794159106337`)
- [x] Panel → **WhatsApp** → *Set up*
- [ ] **Usar la WABA existente** «Moza Print» (`358071354051207`), no crear otra:
      conserva la identidad de negocio y facilita el intercambio de números del
      paso 4. Una WABA admite varios números
- [x] Anotar **App ID** y **App Secret** (Settings → Basic) → **Bitwarden**

### A2 · Método de pago ✅ — figura como «Agregada»

- [x] Business Settings → **WhatsApp Accounts** → «Moza Print» → *Payment settings*
- [x] Tarjeta Visa/Mastercard/Amex que **permita cargos internacionales**
- [x] Confirmar que quedó activa **antes del 30 de septiembre** — hecho el 2026-09-08

### A3 · Token permanente ✅

⚠️ El token que Meta muestra por defecto **caduca en 24 h**. No sirve.

- [x] Business Settings → **System Users** → `odoo-whatsapp`
- [x] Asignarle la app y la WABA con permiso de administración
- [x] Generar token con **exactamente**: `whatsapp_business_messaging` y
      `whatsapp_business_management`. **NO** marcar `manage_app_solution` ni
      `whatsapp_business_manage_events`: no se usan
- [x] → **Bitwarden**. Nunca en el repo, nunca en un commit

### A4 · Alta del número nuevo — ⏳ se hace en el bloque C (paso C1)

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

## Bloque B · Validar el módulo en test — ✅ COMPLETADO (2026-09-09)

Base: `https://mp-watest.odoo.com/` (db `mp-watest`, saas~19.3+e, copia de
producción). Número de prueba de Meta `+1 555-678-0188`.

### Resultado de las 7 pruebas

| # | Prueba | Resultado |
|---|---|---|
| 1 | Enviar desde Odoo | ✅ `state=sent`, con `msg_uid` real de Meta |
| 2 | Recibir en Discuss | ✅ entrante «Gracias» en `received` |
| 3 | Ligar a un contacto | ✅ canal creado como *Juan Carlos Asomoza Ponce (525548118158)* |
| 4 | Cotización con PDF desde `sale.order` | ⏳ **pendiente** — falta plantilla propia (ver hallazgo 2) |
| 5 | Abrir desde el chatter | ⏳ pendiente |
| 6 | **Contestar desde la app móvil** | ⏳ **pendiente — es criterio de decisión** |
| 7 | `audit_lineas_facturables --target test` | ✅ **0 líneas** · 242 acciones, todas de módulos de Odoo |

**La prueba 7 era la que podía matar el proyecto y salió limpia**: instalar
WhatsApp no genera código facturable de Studio. La ADR 007 sigue a salvo.

**Dato de paso**: instalar `whatsapp` arrastra **14 módulos puente** por
auto-instalación (`whatsapp_crm`, `whatsapp_sale`, `whatsapp_account`,
`whatsapp_pos`, `marketing_automation_whatsapp`…). Es normal —los bridges se
instalan solos cuando sus dos dependencias están presentes— pero es más
superficie de la prevista. Ninguno genera código facturable.

---

## ⚠️ Los tres hallazgos que costaron la noche

Ninguno está en la documentación de Odoo ni en la de Meta. **Si se repiten en
producción, el síntoma es idéntico y el diagnóstico vuelve a costar horas.**

### Hallazgo 1 · La app debe suscribirse a la WABA, y no hay botón

**Síntoma**: todo verde —URL verificada, campos suscritos, envío funcionando— y
**cero webhooks**. Ni mensajes entrantes ni acuses de entrega: los salientes se
quedan clavados en `sent` para siempre.

**Causa**: en Cloud API hay **dos registros distintos**, y la consola solo expone
uno.

| Registro | Qué declara | Dónde |
|---|---|---|
| A nivel **app** | «mis eventos, a esta URL, de estos campos» | Panel de la app, con palomita verde |
| A nivel **WABA** | «esta cuenta entrega sus eventos a estas apps» | **Solo por API. No hay botón** |

Peor aún: el flujo nuevo de Meta por «casos de uso» crea la WABA de prueba y
**suscribe su propia app** (`WA DevX Webhook Events 1P App`, id
`2202427980234937`) para que funcionen los botones «Probar» del panel. La tuya
nunca entra, y nada en la interfaz lo dice.

**Verificar** — en el [Explorador de la API Graph](https://developers.facebook.com/tools/explorer/),
con el token permanente y la app seleccionada:

```
GET   <WABA_ID>/subscribed_apps
```

Si tu app no aparece en `data`, ese es el problema.

**Corregir** — misma ruta, método `POST`:

```
POST  <WABA_ID>/subscribed_apps      →  {"success": true}
```

> ⚠️ **Es por WABA.** Hacerlo en la de prueba **no** sirve para la de producción.
> En el bloque C hay que repetirlo con `358071354051207`.
>
> La suscripción **no rellena hacia atrás**: solo aplica a eventos posteriores.

### Hallazgo 2 · Las plantillas se atan a una cuenta y a un modelo

**Síntoma**: desde un contacto se envía bien, pero al mandar una cotización desde
`sale.order` Odoo avisa *«Este mensaje se enviará con una cuenta de demostración»*
y usa la cuenta demo — **incluso archivada**.

**Causa**: `whatsapp.template` tiene `wa_account_id` y `model_id`. Odoo ofrece las
plantillas cuyo modelo coincide con el registro. En la base había:

| Cuenta | Plantillas | Modelo *Orden de venta* |
|---|---|---|
| Odoo Demo Account *(archivada)* | 12 | ✅ `Sale Order` |
| Mozaprint MX (prueba) | 6 | ❌ las 6 son de *Contacto* |

Las 6 propias son las de ejemplo que Meta regala con el número de prueba
(`Hello World`, las de *Jaspers Market*), todas del modelo *Contacto*. Como no
había ninguna de *Orden de venta* en la cuenta propia, Odoo caía en la demo.

**Corregir**: duplicar la plantilla `Sale Order`, cambiarle la cuenta a la propia
y enviarla a aprobación.

> ⚠️ **Las plantillas NO se heredan entre cuentas.** Al crear la cuenta de
> producción hay que crearlas de nuevo ahí y volver a esperar la aprobación de
> Meta. Es la razón por la que el bloque D va en paralelo y no al final.

### Hallazgo 3 · La app tiene que estar publicada

Con la app en modo desarrollo, Meta **no entrega webhooks de producción** — ni
siquiera a los administradores de la app. Lo dice su propio aviso, pero es fácil
leerlo como una advertencia menor.

Con la app sin publicar no solo no llegan los mensajes entrantes: **tampoco los
acuses de entrega**, así que nunca sabes si tus mensajes llegaron. Para un
vendedor mandando cotizaciones, eso lo vuelve obligatorio.

### Un bug de Odoo, de paso

`_compute_callback_url` llama `self.get_base_url()` sobre el conjunto completo en
vez de registro por registro. **Con dos cuentas activas, leer la Callback URL de
ambas a la vez lanza «Expected singleton».** Razón práctica para archivar la
cuenta demo en cuanto exista la propia.

---

## Bloque C · Producción — plan detallado

> **Nada de esto se improvisa.** Los tres hallazgos del bloque B se repiten aquí
> con síntomas idénticos si se saltan pasos. El orden importa.

### C0 · Antes de tocar producción

- [ ] **Backup de referencia**: `python scripts/backup_catalog.py --output backups/pre_whatsapp_AAAAMMDD.json`
- [ ] **Línea base de código facturable**: `python scripts/audit_lineas_facturables.py --max-bloques 0` → debe dar **0**
- [ ] **Salud del sitio**: `python scripts/audit_post_upgrade.py --comparar` → limpio
- [ ] Confirmar en Bitwarden que están los 5 datos: App ID, App Secret, token
      permanente, WABA de producción, y —tras C1— el Phone Number ID real

### C1 · Dar de alta el número real en Meta

- [ ] Meta → WhatsApp → **API Setup** → *Add phone number*
- [ ] **WABA: «Moza Print» `358071354051207`** — la de producción, NO la de prueba
- [ ] **Nombre visible: `Mozaprint MX`**. Lo revisa Meta; si lo rechaza, `Mozaprint`
- [ ] Verificar con el PIN de 6 dígitos
- [ ] Anotar el **Phone Number ID real** → Bitwarden

> ⚠️ **Tope de 2 números sin verificación de negocio.** Con el de prueba ya usas
> uno. Si más adelante quieres meter también el `5632776277` para el intercambio,
> hará falta **verificación del negocio** (2-4 días hábiles). Conviene iniciarla
> con tiempo — hoy figura como *No iniciado*.

### C2 · Suscribir la app a la WABA de producción ← el paso invisible

**Este es el hallazgo 1 y no tiene botón en la consola.** Si se salta, producción
falla exactamente como falló test: todo verde y cero webhooks.

- [ ] [Explorador de la API Graph](https://developers.facebook.com/tools/explorer/),
      app `Mozaprintmx Odoo`, token permanente
- [ ] Comprobar:  `GET 358071354051207/subscribed_apps`
- [ ] Si no aparece `Mozaprintmx Odoo` → `POST 358071354051207/subscribed_apps`
- [ ] Confirmar `{"success": true}` y repetir el `GET`

### C3 · Instalar el módulo en producción

- [ ] Aplicaciones → **WhatsApp** → Instalar
- [ ] Aceptar que se auto-instalen los ~14 módulos puente
- [ ] `python scripts/audit_lineas_facturables.py --max-bloques 0` → **sigue en 0**

> Si este auditor deja de dar 0, **detenerse**: algo generó código de Studio y eso
> reabre el cargo de la ADR 007.

### C4 · Crear la cuenta en Odoo

WhatsApp → Configuración → Cuentas de WhatsApp Business → **Nuevo**

| Campo (en español) | Valor |
|---|---|
| Nombre | `Mozaprint MX` |
| ID de la aplicación | `1417946286897018` |
| Secreto de la aplicación | *(Bitwarden)* |
| **ID del número de teléfono** ⬅️ izquierda | *(el real, de C1)* |
| **ID de la cuenta de WhatsApp Business** ➡️ derecha | `358071354051207` |
| Token de acceso | *(el permanente, de Bitwarden)* |
| Usuarios predeterminados | Juan Carlos |

- [ ] **Probar credenciales** → debe autocompletar el **Número de teléfono**.
      Ese autocompletado es la prueba de que el token y los IDs son correctos
- [ ] Copiar **URL de retrollamada** y **Token de verificación** → Bitwarden
- [ ] **Archivar la cuenta demo** si aparece — por el bug del *singleton*

> ⚠️ Los dos IDs numéricos están uno frente al otro y son el error clásico.
> Izquierda = número, derecha = cuenta.

### C5 · Webhook en Meta

- [ ] Pegar la **Callback URL de producción** y el **Verify Token**
- [ ] **Verificar y guardar**
- [ ] Suscribir **`messages`** y **`message_template_status_update`**
      *(`message_status` no existe: los acuses viajan dentro de `messages`)*

Comprobación independiente, sin salir de la terminal:

```bash
curl -s -o /dev/null -w "HTTP %{http_code}
"   "https://mozaprintmx.odoo.com/whatsapp/webhook?hub.mode=subscribe&hub.verify_token=<TOKEN>&hub.challenge=PRUEBA"
```

Debe responder **HTTP 200** y devolver `PRUEBA`.

### C6 · Plantillas ← no se heredan

**Hallazgo 2**: las plantillas de test **no sirven** en producción. Hay que
crearlas en la cuenta nueva y esperar aprobación de Meta (24-72 h en una WABA
real, no minutos como en la de prueba).

- [ ] Duplicar `Sale Order` → cuenta **Mozaprint MX**, nombre `Cotización Mozaprint`
- [ ] Crear las de **utilidad** ($0.0080 vs $0.0436 de marketing):
      `cotizacion_lista` · `anticipo_recibido` · `pedido_en_produccion` · `arte_requerido`
- [ ] Enviar todas a aprobación **el mismo día que se instala el módulo**, para que
      la espera corra en paralelo

### C7 · Validación en producción

Antes de usarlo con un cliente real, contra un número propio:

| # | Prueba | Por qué |
|---|---|---|
| 1 | Enviar un mensaje desde Odoo | Saliente |
| 2 | Contestar desde el celular → llega a Discuss | **Valida C2** |
| 3 | Que el saliente pase de `sent` a `delivered` | Confirma el webhook completo |
| 4 | **Cotización con PDF desde `sale.order`** | El caso de uso central — pendiente desde test |
| 5 | Abrirla desde el chatter del cliente | Seguimiento en contexto |
| 6 | **Contestar desde la app móvil de Odoo** | ⭐ **Criterio (a) de la decisión final** |

> **La 6 no se puede saltar.** Es uno de los dos criterios con los que vas a
> decidir si intercambias el número. Sin ella, las 6 semanas del bloque F terminan
> en corazonada.

### C8 · Encender el canal único

Solo cuando C7 esté completo. Ver bloque E: cambiar **únicamente** la vista
`5029` con `scripts/cambiar_whatsapp_shop.py` (dry-run, rollback, y escritura
**idioma por idioma** porque `arch_db` es campo traducido).

### Rollback

| Si falla | Qué hacer |
|---|---|
| El webhook no entrega | `GET subscribed_apps`. Es la causa en el 90% de los casos |
| Odoo descarta los webhooks | Revisar que el **App Secret** sea el de esta app: uno bien formado pero equivocado los tira en silencio, y «Probar credenciales» **no lo detecta** porque no usa el App Secret |
| Hay que revertir el canal | `cambiar_whatsapp_shop.py --rollback` |
| Hay que apagar todo | Archivar la cuenta en Odoo: deja de enviar y de recibir sin desinstalar nada |

> **No desinstales el módulo** para revertir. Desinstalar en Odoo Online no es
> limpio. Archivar la cuenta corta el servicio sin tocar la estructura.

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
