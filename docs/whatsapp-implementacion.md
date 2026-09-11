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

## ✅ Fecha límite del 30 de septiembre — RESUELTA el 2026-09-08

**Método de pago registrado en Meta el 2026-09-08** (Mastercard, en la WABA
nueva `1055533050656636`). **El riesgo de bloqueo del 1 de octubre ya no
aplica.** Se conserva el contexto porque explica por qué el método de pago fue
el paso A2 y no el último, y porque el costo por mensaje sigue vigente.

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

## Bloque A · Meta — ✅ COMPLETADO (A4 se cerró dentro del bloque C)

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
| 6 | **Contestar desde la app móvil** | ✅ **confirmado en producción el 2026-09-09** |
| 7 | `audit_lineas_facturables --target test` | ✅ **0 líneas** · 242 acciones, todas de módulos de Odoo |

**La prueba 7 era la que podía matar el proyecto y salió limpia**: instalar
WhatsApp no genera código facturable de Studio. La ADR 007 sigue a salvo.

**Dato de paso**: instalar `whatsapp` arrastra **14 módulos puente** por
auto-instalación (`whatsapp_crm`, `whatsapp_sale`, `whatsapp_account`,
`whatsapp_pos`, `marketing_automation_whatsapp`…). Es normal —los bridges se
instalan solos cuando sus dos dependencias están presentes— pero es más
superficie de la prevista. Ninguno genera código facturable.

---

## ⚠️ Los cuatro hallazgos que costaron la noche

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

### Hallazgo 4 · Un App Secret mal pegado no da NINGÚN error

**El más traicionero de los cuatro**, y el que costó producción.

**Síntoma**: **se envía perfecto** —las plantillas llegan al celular con su PDF—
pero **no entra absolutamente nada**. Ni mensajes ni acuses. Y el registro de
depuración de Odoo está **vacío**: ni siquiera aparece un intento rechazado.

**Causa**: enviar y recibir usan credenciales distintas.

| Operación | Qué usa |
|---|---|
| **Enviar** | el **token** de acceso |
| **Recibir** | el **App Secret**, para validar la firma `X-Hub-Signature-256` de Meta |

Con un App Secret equivocado, Odoo recibe cada webhook, calcula la firma, no
coincide, y lo descarta **sin registrar nada** — para Odoo esa petición nunca fue
legítima. Y como enviar no lo usa, todo lo demás sigue funcionando.

En producción se había pegado un valor de **12 caracteres**. Un App Secret de Meta
son **32 hexadecimales**.

> ⚠️ **«Probar credenciales» NO detecta esto**, porque esa prueba solo llama a la
> Graph API con el token. Puede salir en verde con el App Secret completamente mal.

**Cómo detectarlo en 10 segundos** — comparando la huella del secreto entre dos
bases, o simplemente midiendo:

```python
# app_secret debe cumplir: 32 caracteres, solo [0-9a-f]
re.fullmatch(r"[0-9a-f]{32}", app_secret)
```

**Regla práctica**: si envías pero no recibes, y el log de depuración está vacío,
**mide el App Secret antes de tocar cualquier otra cosa.**

### Un bug de Odoo, de paso

`_compute_callback_url` llama `self.get_base_url()` sobre el conjunto completo en
vez de registro por registro. **Con dos cuentas activas, leer la Callback URL de
ambas a la vez lanza «Expected singleton».** Razón práctica para archivar la
cuenta demo en cuanto exista la propia.

---

## Bloque C · Producción — ✅ CIRCUITO COMPLETO (2026-09-09)

**WhatsApp funciona en producción.** Entra, sale, liga al contacto, manda
cotizaciones con PDF, y **0 líneas facturables**.

### Configuración final

| Dato | Valor |
|---|---|
| WABA de producción | `1055533050656636` («MozaPrint MX») |
| Phone Number ID | `1299638423233370` |
| Número | `+52 1 56 6470 5479` |
| Callback URL | `https://www.mozaprintmx.com/whatsapp/webhook` |
| Campos suscritos | `messages` · `message_template_status_update` |
| App Secret y token | **en Bitwarden** — nunca en el repo |

> La WABA `358071354051207` («Moza Print») **quedó descartada**: está atada a la
> WhatsApp Business App del `5632776277` y por eso no dejaba agregar números.
> La nueva se creó para Cloud API, con su propio método de pago y la verificación
> del negocio ya aprobada.

### Resultado de las validaciones

| # | Prueba | Resultado |
|---|---|---|
| 1 | Enviar desde Odoo | ✅ |
| 2 | Recibir en Discuss | ✅ canal creado automáticamente |
| 3 | Ligar a un contacto | ✅ con nombre del cliente |
| 4 | **Cotización con PDF desde `sale.order`** | ✅ llega el PDF y el link de seguimiento |
| 5 | Ver la conversación en el chatter | ✅ |
| 6 | **Contestar desde la app móvil de Odoo** | ✅ **PASA** — se contestó desde la app el 2026-09-09. Criterio (a) del bloque F **cumplido** |
| 7 | Código facturable | ✅ **0 líneas** |

**Nombre visible**: `MozaPrint MX` aparece correctamente en el chat del cliente.

**Pendiente menor**: la plantilla usada es la de *Orden de venta*; conviene una
específica de **cotización**.

---

## Bloque C · Los pasos, para repetirlos

> **Nada de esto se improvisa.** Los tres hallazgos del bloque B se repiten aquí
> con síntomas idénticos si se saltan pasos. El orden importa.

### C0 · Antes de tocar producción — ✅ hecho el 2026-09-09

- [x] **Línea base de código facturable**: `python scripts/audit_lineas_facturables.py --max-bloques 0` → **0** ✅
- [x] **Salud del sitio**: `python scripts/audit_post_upgrade.py` → sin hallazgos ✅
- [ ] Confirmar en Bitwarden: App ID, App Secret, token permanente, WABA de
      producción, y —tras C1— el Phone Number ID real

> **Sin backup de catálogo, a propósito.** Instalar WhatsApp no toca productos ni
> cotizaciones: crea modelos y menús propios. Un respaldo de catálogo protegería
> algo que este cambio no puede romper. *(`backup_catalog.py` además requiere
> `ODOO_API_KEY` para JSON-2, que no está configurada en este entorno.)*
>
> **El rollback real es archivar la cuenta** (ver tabla al final del bloque), no
> restaurar datos. La línea base que sí importa es la de código facturable: si
> deja de dar 0 después de instalar, hay que parar.

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

### C8 · Encender el canal de entrada — ⏳ PENDIENTE

**Replanteado el 2026-09-09: cambió de forma y de destino.** Se hace **a mano
desde el editor web**, no con script, y el destino recomendado ya no es el header
de `/shop`. Ver el bloque E.

### Rollback

| Si falla | Qué hacer |
|---|---|
| El webhook no entrega | `GET subscribed_apps`. Es la causa en el 90% de los casos |
| Odoo descarta los webhooks | Revisar que el **App Secret** sea el de esta app: uno bien formado pero equivocado los tira en silencio, y «Probar credenciales» **no lo detecta** porque no usa el App Secret |
| Hay que revertir el canal | Editor web: regresar el enlace al `5632776277`. Si se cambió por API, restaurar desde `backups/` |
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

> Con un canal de entrada al número nuevo hay tráfico entrante, así que muchas conversaciones abrirán
> con el cliente escribiendo — ahí contestas libre, sin plantilla. Las plantillas
> son para **reabrir conversaciones frías**.

---

## Bloque E · El canal de entrada — ✅ HECHO el 2026-09-11

> **Replanteado el 2026-09-09; ejecutado a mano entre el 10 y el 11.** El plan
> original —cambiar la vista `5029` con un script— se descartó: el sitio tiene un
> solo idioma activo, así que el editor web basta. JC hizo las ediciones.

### ⚠️ El tráfico: una medición equivocada, y la trampa que la causó

> **Corrección del 2026-09-11.** Una versión anterior de este documento afirmaba que
> `/shop` tenía **0 visitas en 90 días** y concluía que el listado «está muerto».
> **Era falso**, y el error fue de instrumento.

**Hay dos analíticas en esta instancia y miden cosas distintas:**

| | Qué es | Qué ve |
|---|---|---|
| `website.track` | Rastreo **server-side** de Odoo | Solo lo que puede atribuir: un `website.page` o un `product_id` |
| **Analítica** (`Sitio web → Analítica`) | **Plausible**, client-side por JS (`plausible_site` en el modelo `website`) | Todas las páginas |

**`/shop` no es un `website.page`.** Es una ruta del controlador de `website_sale`, y
no está entre los 28 registros de `website.page`. Por eso `website.track` **nunca**
la registra: en sus **28,870 registros históricos**, la URL exacta `/shop` aparece
**0 veces**. No es ausencia de tráfico, es ceguera del modelo.

Plausible sí la ve: **34 visitantes únicos / 37 visitas / 71 páginas vistas en 28
días**.

**Y hay un segundo sesgo, de escala**: `website.track` contaba **5,630** páginas
vistas en 30 días; Plausible cuenta **1,259**. La diferencia son **bots** —
`website.track` mide server-side e incluye crawlers; Plausible corre en el navegador
y no los ve. La lectura del tamaño del sitio estaba inflada ~4.5×.

> 📌 **La regla que queda**: para tráfico de páginas usa **la Analítica (Plausible)**,
> no `website.track`. `website.track` sirve para lo que sí sabe atribuir —vistas de
> **producto** y de las páginas con registro— y para ligar visitantes con leads.
> Un cero perfecto en `website.track` es sospecha de ruta no atribuible, no un dato.
> Cómo consultar Plausible por API: `docs/sitio-web-enlaces-whatsapp.md` §8.

### El tráfico real (Plausible, 28 días al 2026-09-10)

**357 visitantes únicos · 477 visitas · 1,259 páginas vistas · rebote 67%**

| Grupo | Visitantes | % |
|---|---:|---:|
| **Ficha de producto** | 275 | **37.3%** |
| **`/shop/category/*`** | 184 | **24.9%** |
| Portada | 116 | 15.7% |
| *(backend `/web`, `/odoo`)* | 39 | 5.3% |
| **`/shop` (listado)** | 34 | 4.6% |
| Carrito / checkout | 27 | 3.7% |
| `/blog/*` | 14 | 1.9% |
| `/contactanos` | 11 | 1.5% |

A 6 meses la forma se repite: ficha 37.1%, categorías 21.6%, portada 20.6%,
`/shop` 5.8%.

**Las landings de marketing no existen para el visitante**: `/kits-de-bienvenida` 4
visitantes en 6 meses, `/eventos-y-agencias` 4, `/regalos-corporativos` 3,
`/lp-nadiveno-2025` 0. `/servicios` tiene 7. Las cifras altas que se habían anotado
antes (211, 50, 47) venían de `website.track` y eran casi puro bot.

**Tres lecturas:**

1. **La ficha de producto es la página #1**, y ahí sigue sin haber botón propio.
2. **`/shop` no está muerta**: 4.6%, una octava parte de las fichas. El botón que se
   migró ahí es modesto, no inútil.
3. **Las páginas de categoría son el #2 con 24.9%** — casi el doble que la portada y
   cinco veces `/shop`. En `website.track` parecían ruido y se descartaron. Es un
   dato con consecuencias más allá de WhatsApp: es la palanca 2 de la Fase 9
   (linking interno).

**Y el dato que no depende de tracking**: de 62 leads en 90 días solo 13 traen origen
de formulario, y **«Producto» es el primero** (7 de 13), por encima de «Contactanos»
(4). La ficha es donde el visitante convierte.

**Dimensiona el bloque F**: a ~357 visitantes únicos al mes, pasarán unos **535 por
el sitio en las 6 semanas** de prueba.

Por eso el peso de la migración se movió a los **elementos globales**, que salen en
todas las páginas —ficha, categorías, `/shop` y portada— y hacen la decisión robusta
a esta clase de error de medición.

### La política — qué número va en cada lugar

> No es una migración a medias: es el diseño. Si ves el viejo en estos lugares,
> **está bien así**.

| Grupo | Número | Por qué |
|---|---|---|
| Botón del header (`4318`), redes (`4095`), `/shop` (`5029`), `/servicios` (`3884`) | **Nuevo** | Canales de entrada de la prueba del bloque F |
| Portada (`2342`), `/contactanos` (`4122`), **pie** (`4504`) | **Los dos** | Los clientes de siempre conocen el `5632776277` y lo buscan ahí |
| **Todos los enlaces `tel:`** | **Viejo, permanente** | El `5632776277` **sí recibe llamadas**. El nuevo es una línea de **Cloud API**: gestiona mensajes, no llamadas |
| Landings de marketing (`4725`, `5049`, `5050`, `5052`) | **Viejo** | Son de prueba y su **tráfico prácticamente nulo**: 0-4 visitantes en 6 meses cada una (Plausible). Migrarlas no aporta muestra |

> ⛔ **No "completes" los `tel:` por consistencia.** Quien marque al número nuevo no
> timbra en ningún lado, y **el bloque F no lo detecta**: la llamada nunca llega a
> Odoo.

El enlace canónico del nuevo:

```
https://wa.me/525664705479?text=Hola%2C%20me%20interesa%20cotizar
```

Correcto: `+52 1 56 6470 5479` → nacional `5664705479` → `52` + 10 dígitos.

### Lo que queda abierto (y no es del bloque E)

**1. El JS del pie ya apunta al nuevo, pero su pendiente de fondo sigue abierto.**
`custom_code_footer` pasó a `wa.me/5215664705479` el 2026-09-11. El botón
«Consultar inventario» no está en el HTML: lo inyecta el JS, y el enlace de WhatsApp
solo aparece **tras el clic** y solo cuando el producto **no** trae etiqueta `4P` ni
`PO` — el JS nunca pregunta por `INN`:

| Rama | Templates publicados | |
|---|---:|---|
| `4P` → consulta la API y pinta tabla | 1,872 | 37.3% |
| `PO` → consulta la API y pinta tabla | 1,732 | 34.5% |
| **sin `4P` ni `PO` → WhatsApp** | **1,412** | **28.1%** |

Es además **el único enlace del sitio que manda nombre de producto y SKU**.

🟠 **Cambiar el número no cerró nada de fondo**: la consulta a los proveedores sigue
saliendo del navegador del visitante. Eso es arquitectura y va con el rediseño de
«Consultar inventario» (Fase 8).

**2. La ficha de producto sigue sin botón propio**, con la zona
`oe_structure_website_sale_product_1` vacía — y es el **primer origen de leads de
formulario** (7 de 13 con origen, por encima de «Contactanos»). Para dimensionar su
tráfico frente al resto, usa la **Analítica**, no `website.track`.

### Las correcciones de la revalidación

**El inventario son 15 vistas, no 14.** Faltaba la `2521` (`website.s_share`), el
snippet de compartir: trae `wa.me` pero **sin número**, así que no es un canal.

**El bug de los corchetes ya no existe.** La vista `4318` renderizaba
`?text=…%5BNOMBRE_PRODUCTO%5D%20SKU%3A%20%5BSKU%5D`. Hoy el `href` es
`https://wa.me/525632776277`, sin `?text=`. Verificado con `grep` en portada,
`/shop` y ficha: **0 ocurrencias** en las tres.

**El número estaba hardcodeado en el JS del pie**, fuera del alcance del editor
web. `custom_code_footer` (el de «Consultar inventario») ofrecía
`wa.me/5215632776277` cuando el producto no trae etiqueta de proveedor. **Migrado el
2026-09-11** a `wa.me/5215664705479`. Sigue siendo el **único** enlace del sitio que
arma el mensaje con nombre de producto y SKU reales — y el pendiente de arquitectura
de ese bloque sigue abierto (`analysis/supplier-sync/HALLAZGO_JS_INVENTARIO.md`).

### Qué se supo el 2026-09-09 y sigue vigente

**1. El inventario estaba mal.** El plan decía «8 vistas». El barrido completo
encontró 14 (hoy 15). El error: se buscó `arch_db ilike 'whatsapp'`, y **`wa.me` no
contiene esa palabra**.

**2. Tres de los enlaces son globales.** Las vistas `4095` (redes del header),
`4318` (botón verde del header) y `4504` (pie de página) salen en **todas** las
páginas. Eso rompe la premisa del plan original: cambiar la `5029` no crea un
«canal único» — crea una página donde conviven **dos números** en pantalla, y el
del header compite con el nuevo.

**3. El script se descartó.** `scripts/cambiar_whatsapp_shop.py` se escribió y se
borró el 2026-09-09 sin llegar a producción. Razón: **el sitio tiene un solo
idioma activo** (`es_419`), así que la trampa de `arch_db` traducido —que era el
argumento para usar script en vez del editor— pesa mucho menos de lo supuesto.
Para **un** enlace, el editor web es más simple y deja ver el resultado.

> El inventario completo, las zonas editables y el procedimiento manual están en
> **`docs/sitio-web-enlaces-whatsapp.md`**. No los repitas aquí.

### El destino recomendado

**`oe_structure_website_sale_product_1`** — la zona editable superior de la ficha
de producto. Hoy está **vacía**: renderiza en la página pero no tiene vista.

| Por qué | |
|---|---|
| **Intención más alta** | La persona ya está viendo un producto concreto, no navegando |
| **Aislada** | Una zona, una vista. Revertir es borrar el bloque |
| **No compite** | Header y pie se quedan con el número de siempre |
| **Puede llevar contexto** | El JS del sitio ya calcula nombre de producto y SKU |

Ahí vivió un botón «Cotizar por WhatsApp» que se perdió (ver
`docs/sitio-web-enlaces-whatsapp.md`, sección 5). Rehacerlo apuntando al número
nuevo resuelve dos cosas de una vez.

### Alternativas consideradas — y cómo se resolvió

| Opción | Veredicto |
|---|---|
| **Ficha de producto** (`_1`) | Era la recomendada y **sigue sin hacerse**. Es el primer origen de leads de formulario (7 de 13) |
| Header de `/shop` (`5029`) | Migrada. Tráfico real pero modesto: **34 visitantes únicos en 28 días** (4.6%) |
| Páginas de categoría (`/shop/category/*`) | **Nunca se consideró, y son el #2 con 24.9%.** Candidato real para un botón, pendiente de evaluar |
| **Botón del header** (`4318`) | ⬅️ **la que resolvió la prueba.** Se descartó al principio por «toda la exposición», pero es lo que sí sale en la ficha, que es donde está la gente |
| Landings con UTM (`5049`, `5052`) | Descartadas: son de prueba y su tráfico es marginal |

**La lección, en dos partes.** La primera: elegir el destino por intuición sobre la
intención del visitante (`/shop` → «está comprando») no basta; hay que mirar el
tráfico. La segunda, más cara: **mirarlo con el instrumento equivocado es peor que no
mirarlo**, porque produce una conclusión con apariencia de dato. `website.track` no
ve `/shop` y devolvió un cero que se leyó como «página muerta».

Lo que salvó la decisión fue que **no dependía de ese número**: los elementos
globales salen en todas las páginas, así que la entrada queda cubierta sin importar
cuál gane.

### El procedimiento (para cualquier enlace que se quiera cambiar después)

1. Editor web, **no** `Ajustes → Técnico → Vistas`
2. Enlace: `https://wa.me/525664705479?text=Hola%2C%20me%20interesa%20cotizar`
3. **Reemplaza** el enlace viejo de esa pantalla; no agregues el nuevo al lado. Eso
   es lo que dejó mixtas la portada y `/contactanos`
4. Verificar como visitante en ventana privada
5. **Dar clic real desde un celular ajeno al negocio**: debe abrir chat con
   `MozaPrint MX`. Es el único paso que prueba que Meta enruta
6. Volver a correr el barrido de `docs/sitio-web-enlaces-whatsapp.md` §8 para
   confirmar qué quedó en cada vista

**Pendiente de verificación**: el paso 5 —el clic real desde un celular ajeno— **no
consta** para ninguna de las vistas migradas. Es lo único que prueba que Meta enruta
el número nuevo desde el sitio. Es lo único que prueba que Meta
enruta el número nuevo desde el sitio.

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
