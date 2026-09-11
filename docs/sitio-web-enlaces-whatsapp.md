# Sitio web — enlaces de WhatsApp y zonas editables

> **Para qué existe**: al conectar el número nuevo a Odoo (Fase 4, bloque E) hubo
> que averiguar **de dónde sale cada enlace de WhatsApp del sitio**. Derivarlo
> costó una sesión entera. Este documento evita repetirla.
>
> **Medido contra producción el 2026-09-09**, **revalidado el 2026-09-10** con
> consultas de solo lectura y `curl` contra el sitio público. Si cambia el sitio,
> vuelve a correr las consultas de la sección 8.
>
> **Estado del número nuevo** (2026-09-11): la migración del sitio está
> **terminada para todo lo que recibe tráfico**. Ver la sección 2 y, sobre todo,
> la **2.bis: la política de qué número va en cada lugar**, que es una decisión
> del operador y NO una migración a medias.

---

## 1. La regla que hay que saber antes de tocar nada

**Solo hay UN idioma activo en el sitio: `es_419`.**

```
Idiomas activos: ['es_419']
default_lang_id: Spanish (Latin America) / Español (América Latina)
```

`en_US` existe como **idioma origen** de los campos traducidos, pero el sitio no
lo sirve a ningún visitante.

Consecuencia práctica: la trampa clásica de `arch_db` —campo traducido, hay que
escribir idioma por idioma, ya mordió a dos scripts de este repo— **aquí pesa
poco**. Si una edición cae solo en `es_419`, el visitante igual ve el cambio. El
`en_US` queda desfasado, lo cual es basura pero no un sitio roto.

**Sigue siendo obligatorio iterar idiomas al escribir por API.** La regla no
cambia; lo que cambia es la severidad si se olvida.

---

## 2. Las 15 vistas con enlaces de WhatsApp

> **Corrección del 2026-09-10**: son **15**, no 14. Faltaba la `2521`
> (`website.s_share`), el snippet nativo de «compartir». Contiene `wa.me` pero
> **sin número**, así que no es un canal de contacto — se lista aquí justamente
> para que la próxima búsqueda no la reporte como hallazgo nuevo.

Columna **Nº**: `viejo` = `5632776277` · `NUEVO` = `5664705479` · `MIXTO` = los dos
en la misma vista.

| id | Vista | Dónde sale | Nº | Notas |
|---|---|---|---|---|
| 2342 | `website.inicio` | `/` | ⚠️ **MIXTO** | 1 nuevo («Solicita asesoría») + 2 viejos |
| 2521 | `website.s_share` | global | — | Snippet de compartir, **sin número** |
| 3884 | `website.servicios` | `/servicios` | viejo | |
| **4095** | `header_social_links` | **global** | viejo | Ícono de redes, en todas las páginas |
| 4122 | `website.contactanos` | `/contactanos` | ⚠️ **MIXTO** | 2 nuevos + 3 viejos. **Ver sección 4** |
| **4318** | `header_call_to_action` | **global** | viejo | Botón verde del header |
| **4504** | `template_footer_descriptive` | **global** | viejo | Pie de página, 5 ocurrencias |
| 4725 | `landing-page_321f1b` | `/lp-nadiveno-2025` | viejo | Prefijo `521`, no `52` |
| 5020 | `inicio_ed64ed` | `/testinicio` | viejo | **no publicada** |
| ~~5028~~ | `products_oe_structure_website_sale_products_1` | — | viejo | **ARCHIVADA**, no renderiza. Hero viejo de la tienda, reemplazado por 5029 el 2026-01-19 |
| **5029** | `products_oe_structure_products_header_shop` | Header de `/shop` | ✅ **NUEVO** | Botón «Cotiza ahora». **Migrado y limpio** |
| 5049 | `kits-de-bienvenida` | `/kits-de-bienvenida` | viejo | 4 enlaces, **con `utm_campaign`** |
| 5050 | `kits-de-bienvenida_0d8ee5` | `/eventos-y-agencias` | viejo | Texto precargado de brief |
| 5051 | `kits-de-bienvenida_3564e3` | `/catalogos` | viejo | **no publicada** |
| 5052 | `..._0d8ee5_4a6b20` | `/regalos-corporativos` | viejo | **con `utm_campaign`** |

### 2.bis · La política: qué número va en cada lugar

> **Decidida por JC el 2026-09-11.** No es una migración incompleta: es el diseño.
> Si ves el número viejo en alguno de estos lugares, **está bien así**.

| Grupo | Número | Por qué |
|---|---|---|
| Botón del header, redes, `/shop`, `/servicios` | **Nuevo** | Son los canales de entrada de la prueba del bloque F |
| Portada, `/contactanos`, **pie de página** | **Los dos** | Los clientes de siempre conocen el `5632776277` y lo buscan. En estos tres lugares se publica a propósito |
| **Todos los enlaces `tel:`** | **Viejo, permanente** | **El `5632776277` sí recibe llamadas. El número nuevo es una línea de WhatsApp Cloud API: gestiona mensajes, no llamadas.** Poner el nuevo en un `tel:` manda al cliente que marca a un número que no timbra — y eso **no lo detecta ninguna prueba del bloque F**, porque la llamada nunca llega a Odoo |
| Landings de marketing (`4725`, `5049`, `5050`, `5052`) | **Viejo** | Son landings de **prueba**, con tráfico marginal. Migrarlas no aporta muestra |

> ⚠️ **Para medir tráfico de páginas usa `Sitio web → Analítica`** (Plausible), no
> `website.track`. Ese modelo solo registra páginas con `website.page` o con
> `product_id`: `/shop` **nunca** aparece ahí —es ruta de controlador— y devuelve un
> cero que parece dato. Ya causó una conclusión equivocada el 2026-09-11.

> ⛔ **No "completes" los `tel:` por consistencia.** Es el error que este cuadro
> existe para prevenir.

### El estado por vista (2026-09-11)

| Estado | Vistas |
|---|---|
| ✅ **Limpias en el nuevo** | `3884` `/servicios` · `4095` redes del header · `4318` botón del header · `5029` `/shop` |
| 🔵 **Mixtas a propósito** | `2342` portada · `4122` `/contactanos` · `4504` pie |
| ⚪ **Viejo, descartadas** | `4725` · `5049` · `5050` · `5052` (landings de prueba) |
| ⚫ **Sin efecto** | `5020` y `5051` no publicadas · `5028` archivada · `2521` sin número |

El enlace canónico del número nuevo es:

```
https://wa.me/525664705479?text=Hola%2C%20me%20interesa%20cotizar
```

Correcto: `+52 1 56 6470 5479` → nacional `5664705479` → `52` + 10 dígitos.

**Lo único que sigue apuntando al viejo donde sí hay tráfico es el JavaScript del
pie** (sección 7), que el editor web no alcanza.

**Tres son globales** (4095, 4318, 4504): salen en **todas** las páginas. Es el
dato que más cambia una decisión — cualquier botón que se ponga en una página
concreta convive con estos tres en la misma pantalla.

**Dos no están publicadas** (5020, 5051): cambiarlas no sirve de nada.

**Dos traen `utm_campaign`** (5049, 5052): son las únicas con atribución medible
que ya existe.

### Lo que realmente renderiza (verificado con `curl`, sin sesión)

Medido el 2026-09-10 con `curl`, sin sesión:

| Página | Total | Al **nuevo** | Al viejo |
|---|---:|---:|---:|
| `/` (portada) | 9 | **1** | 8 |
| `/shop` (listado) | 8 | **1** | 7 |
| `/contactanos` | 8 | **1** | 7 |
| `/shop/<producto>` (ficha) | 7 | **0** | 7 |
| `/servicios` | 8 | 0 | 8 |
| `/kits-de-bienvenida` | 11 | 0 | 11 |
| `/lp-nadiveno-2025` | 9 | 0 | 9 |

**Los 7 del piso son globales** y salen en TODAS las páginas: 2 del botón del
header (`4318`, desktop + móvil), 2 del ícono de redes (`4095`, desktop + móvil),
2 del pie (`4504`) y 1 del JavaScript del pie (sección 7). Cualquier botón que se
ponga en una página concreta convive con esos siete.

**La ficha de producto sigue en cero.** Es el destino que la sección 5 recomienda y
la zona `oe_structure_website_sale_product_1` sigue vacía.

Ninguno es flotante: `position: fixed` aparece **0 veces** en el HTML público.

---

## 3. Las zonas editables de la ficha de producto

La ficha de producto tiene **dos** `oe_structure` (zonas donde el editor web
permite poner bloques). Las dos renderizan:

```
id="oe_structure_website_sale_product_1"   <- VACÍA, sin vista en la base
id="oe_structure_website_sale_product_2"   <- vista id=5019
```

| Zona | Vista | Contenido hoy |
|---|---|---|
| `_1` | **ninguna** | Vacía. Ver sección 5 |
| `_2` | `id=5019` | Formulario **«Solicita una cotización gratis»** (`crm.lead`), ancla `#Solicita-una-cotizacion-gratis-producto`. Creada 2025-12-18, modificada **2026-06-03** |

En `/shop` (listado) las zonas equivalentes son `4623` (vacía), `5029` (header,
con WhatsApp) y `5031` (texto SEO + acordeón de preguntas frecuentes).

---

## 4. ✅ RESUELTO — el header ya no manda `[NOMBRE_PRODUCTO]` y `[SKU]` literales

> **Revalidado el 2026-09-10: el bug ya no existe.** El `href` de la vista `4318`
> hoy es `https://wa.me/525632776277`, **sin parámetro `?text=`**. Un `grep` de
> `NOMBRE_PRODUCTO` sobre la portada, `/shop` y una ficha de producto devuelve
> **0** en las tres. Se arregló quitando el texto, que era una de las dos salidas
> que proponía este documento.
>
> Lo que sigue se conserva como registro de qué era el bug y por qué pasó.

La vista **4318** (`header_call_to_action`, global) **tenía** este enlace:

```
https://wa.me/525632776277?text=Hola%2C%20me%20interesa%20cotizar%20%5BNOMBRE_PRODUCTO%5D%20SKU%3A%20%5BSKU%5D
```

Que decodificado es:

> Hola, me interesa cotizar **[NOMBRE_PRODUCTO]** SKU: **[SKU]**

**Los corchetes son texto literal, no variables.** La vista no tiene un solo
`t-esc`, `t-out` ni `t-attf-href` — el `href` es una cadena fija. Cada persona
que da clic en el botón verde del header manda ese mensaje tal cual.

**Por qué pasó**: el JavaScript del código personalizado del sitio **sí calcula**
el nombre del producto y el SKU de la ficha, y los usa para otra cosa. Nunca
reescribe este enlace. Es trabajo que quedó a medias.

Arreglarlo era una de dos: quitar los corchetes del texto, o conectar el JS al
`href`. **Se tomó la primera**: hoy el botón del header no lleva mensaje precargado.

> La segunda opción sigue sin hacerse, y ahí queda valor: el JavaScript del pie
> (sección 7) **sí** calcula nombre y SKU reales, pero solo los usa en su propio
> enlace. Un botón de la ficha de producto que aproveche ese cálculo mandaría el
> mensaje con el producto ya escrito.

---

## 5. El botón «Cotizar por WhatsApp» de la ficha de producto — PERDIDO

Existió, puesto desde el editor, y **ya no está en ninguna parte**. Se buscó el
2026-09-09 en los siete lugares posibles:

| Dónde | Resultado |
|---|---|
| Las **238 vistas propias del sitio**, activas y archivadas | La ficha solo tiene la 5019, con el formulario |
| `id=5019`, arch completo (10,082 caracteres) | `wa.me` **0** · `whatsapp` **0** · `5632776277` **0** |
| Los **10 campos de descripción** de `product.template` | **0 productos** |
| Código personalizado del `<head>` y del pie | Sin botón flotante ni de ficha |
| `user_custom_javascript.js` | Plantilla de Odoo, **todo comentado** |
| `ir.asset` fuera de módulos estándar | 22, todos de Odoo |
| Wayback Machine | **Ninguna captura de `/shop/*`**; lo archivado es del WordPress viejo |

**No es recuperable.** `custom_code_head` / `custom_code_footer` no guardan
historial, y las vistas borradas tampoco.

**Dónde estaba**: la zona `oe_structure_website_sale_product_1` renderiza en la
página pero **no tiene vista asociada**. Esa es la firma de contenido borrado —
Odoo elimina la vista en lugar de dejarla vacía.

**Qué pasó, probablemente**: la 5019 se modificó el **2026-06-03** y hoy tiene el
formulario de captura de lead, cuya ancla es la misma a la que salta un botón que
inyecta el JavaScript del pie. Formulario, ancla y botón son la misma pieza de
trabajo. La lectura es que en junio se cambió la ruta de WhatsApp por captura al
CRM. **Es interpretación de fechas, no un registro.**

> ⚠️ **Lección**: el código del editor web y el código personalizado del sitio
> **no tienen control de versiones**. Lo que se borra ahí, se pierde. Si un bloque
> importa, que viva en un script del repo o al menos quede respaldado en
> `backups/`.

---

## 6. Cómo editar un enlace a mano, sin romper nada

**Usa el editor web**, no `Ajustes → Técnico → Vistas`. El editor escribe los
idiomas correctamente; la ruta técnica escribe solo el de tu sesión y deja el
`en_US` desfasado.

1. Abre cualquier página → **Editar**
2. Clic en el botón. Si es global (4095, 4318, 4504) Odoo avisa que el elemento
   se comparte en todas las páginas — esa alerta **confirma** que es el correcto
3. Barra de herramientas → editor de enlace → reemplaza la URL. La canónica del
   número nuevo es:
   `https://wa.me/525664705479?text=Hola%2C%20me%20interesa%20cotizar`
4. **Guardar**

> Si la página ya tenía un enlace al número viejo, **reemplázalo**; no agregues el
> nuevo al lado. Dos números en la misma pantalla es lo que dejó mixtas la portada
> y `/contactanos` (sección 2).

Si el campo de URL aparece bloqueado, estás en **modo traducción**: el editor
deja cambiar texto pero no atributos `href`.

### Verificación obligatoria

1. Ventana privada → abre la página como visitante
2. Clic derecho sobre el botón → copiar dirección → confirma el número
3. **Desde un celular que no sea el del negocio, dale clic real**: debe abrir
   chat con el destinatario correcto

El paso 3 es el único que prueba que Meta enruta. Los otros dos solo prueban que
el HTML quedó bien.

---

## 7. Código personalizado del sitio

`Ajustes → Sitio web → Código personalizado` tiene dos campos, y **los dos se
inyectan en TODAS las páginas**, no solo donde el código actúa:

| Campo | Qué trae hoy |
|---|---|
| `custom_code_head` | Google tag (`AW-17130962991`), la fuente Calistoga, y CSS para `#o_wsale_floating_bar` |
| `custom_code_footer` | ~8,855 caracteres: el botón «Consultar inventario» de la ficha de producto |

### ✅ Migrado al número nuevo el 2026-09-11 — pero lee esto antes de tocarlo

**Cuándo aparece** (medido el 2026-09-11). El botón «Consultar inventario» no está
en el HTML: el JS lo crea al cargar y lo inserta después de `#product_option_block`.
El enlace de WhatsApp **no existe hasta que alguien da clic**, y solo sale en una de
las tres ramas:

```js
if (tags.includes("4P")) tagType = "4P";
else if (tags.includes("PO")) tagType = "PO";

if (!tagType) { … <a href="https://wa.me/5215664705479?text=${msg}">WhatsApp</a>
                return; }          // ← nunca consulta la API
```

**El JS solo pregunta por `4P` y `PO`; nunca por `INN`.** Como los proveedores son
tres, todo Innovation Line cae en el `else`. No es la rama de «sin inventario»: es
la de «no sé consultar este proveedor, pregunta por WhatsApp».

| Rama | Templates publicados | |
|---|---:|---|
| `4P` → consulta la API y pinta tabla | 1,872 | 37.3% |
| `PO` → consulta la API y pinta tabla | 1,732 | 34.5% |
| **sin `4P` ni `PO` → WhatsApp** | **1,412** | **28.1%** |

Los 1,412 son los 1,400 con etiqueta `INN` más 12 sin etiqueta.

El enlace está escrito a mano en el JS, y desde el 2026-09-11 apunta al **número
nuevo**:

```js
const msg = encodeURIComponent(
    `Estoy interesado en saber la disponibilidad del inventario del producto
     "${productName}" (SKU ${sku || "sin SKU"}).`
);
… <a href="https://wa.me/5215664705479?text=${msg}" …>WhatsApp</a>
```

> 📌 **Ojo con el prefijo, para el día que algo falle.** El sitio tiene el número
> nuevo en **dos formatos**: `525664705479` en los enlaces del editor web y
> `5215664705479` aquí. Se conservó el `521` que ya traía este JS con el número
> viejo, porque es el formato que llevaba años funcionando. WhatsApp normaliza el
> `1` extra en móviles de México, así que los dos deben resolver — pero **si un día
> este enlace concreto falla y los demás no, la causa es ésta.**

Tres cosas importan aquí:

1. **Sale en todas las páginas** (el campo se inyecta global), aunque solo *actúa*
   en la ficha de producto.
2. **Es el único enlace del sitio que arma el mensaje con el nombre de producto y
   el SKU reales.** Es la función que el bloque E quería en la ficha: ya existía,
   solo que escondida tras un clic y apuntando al número equivocado.
3. **El editor web no lo alcanza**: se edita en
   `Ajustes → Sitio web → Código personalizado`, que **no tiene historial**. Si lo
   cambias, respalda el bloque antes.

> 🟠 **Cambiar el número NO cerró el pendiente de este bloque.** El problema de
> fondo —que la consulta a los proveedores sale del navegador del visitante— sigue
> intacto y es de **arquitectura**, no de configuración. Lee
> `analysis/supplier-sync/HALLAZGO_JS_INVENTARIO.md` (gitignored) antes de
> rediseñarlo.

> ⚠️ **No lo cambies suelto.** Va en el mismo bloque que el rediseño de «Consultar
> inventario»: tocar ese JS sin resolver la arquitectura deja el problema de fondo
> intacto y gasta el único intento. Lee primero el archivo de `analysis/`.

> 🟠 **El bloque del pie tiene un pendiente abierto con riesgo aceptado.** El
> detalle **no va en este repo porque es público**: está en
> `analysis/supplier-sync/HALLAZGO_JS_INVENTARIO.md` (gitignored). Antes de tocar
> ese código, **léelo**.

---

## 8. Cómo regenerar este inventario

```python
# Vistas con enlaces de WhatsApp (incluye archivadas) Y con qué número tiene cada una
VIEJO, NUEVO = "5632776277", "5664705479"
vistas = call("ir.ui.view", "search_read",
              ["|", ("arch_db", "like", "wa.me"), ("arch_db", "like", "api.whatsapp")],
              fields=["id", "name", "key", "active", "website_id"],
              context={"active_test": False})
for v in sorted(vistas, key=lambda x: x["id"]):
    # arch_db es computado: se lee con read(), NO con search_read()
    arch = call("ir.ui.view", "read", [v["id"]], fields=["arch_db"])[0]["arch_db"] or ""
    n, o = arch.count(NUEVO), arch.count(VIEJO)
    estado = "NUEVO" if n and not o else ("MIXTO" if n and o else "viejo")
    print(f'{v["id"]:>5}  {"ON " if v["active"] else "OFF"}  {estado:<6} '
          f'nuevo={n} viejo={o}  {v["key"] or v["name"]}')
```

⚠️ **`arch_db ilike 'whatsapp'` NO basta**: `wa.me` no contiene esa palabra. Hay
que buscar los dos patrones o se escapan vistas. Ese error hizo que en la primera
pasada faltaran enlaces.

### ⚠️ Para medir TRÁFICO, no uses `website.track`

Hay dos analíticas en la instancia y miden cosas distintas:

| | Qué es | Qué ve |
|---|---|---|
| `website.track` | Rastreo **server-side** de Odoo | Solo lo atribuible: un `website.page` o un `product_id` |
| **`Sitio web → Analítica`** | **Plausible**, client-side (`website.plausible_site`) | Todas las páginas |

**`/shop` no tiene registro en `website.page`** —es una ruta del controlador de
`website_sale`—, así que `website.track` **nunca** la registra: 0 apariciones en sus
28,870 registros históricos. Plausible sí la ve (34 visitantes únicos / 28 días).

`website.track` además **cuenta bots**: 5,630 páginas vistas en 30 días contra las
1,259 de Plausible (que corre en el navegador y no los ve). Infla ~4.5×.

El 2026-09-11 ese cero se leyó como «la página está muerta» y la conclusión llegó a
cuatro documentos antes de que JC la desmintiera con la pantalla de Analítica.
**Un cero perfecto es sospecha de ruta no atribuible, no un dato.**

### Cómo consultar Plausible por API (sin abrir el navegador)

Costó una sesión encontrarlo. El servidor **no** es `plausible.io`: Odoo Online usa
**`https://saas-analytics.odoo.com`**, y ese dato no está en `ir.config_parameter`
—`website.plausible_server` no existe en esta base— ni se puede leer por XML-RPC
(`_get_plausible_share_url` es privado y `get_plausible_share_url` no existe).

**Dónde sí está**: en la respuesta de `/website/fetch_dashboard_data`, la ruta JSON
que consume el panel. Requiere **sesión web**, no XML-RPC:

```python
import requests
s = requests.Session()
s.post(f"{ODOO_URL}/web/session/authenticate", json={"jsonrpc":"2.0","params":{
    "db": ODOO_DB, "login": ODOO_USER, "password": ODOO_PASSWORD}})
r = s.post(f"{ODOO_URL}/website/fetch_dashboard_data",
           json={"jsonrpc":"2.0","method":"call","params":{"website_id":1}}).json()
print(r["result"]["dashboards"]["plausible_share_url"])
# https://saas-analytics.odoo.com/share/<site>?auth=<key>&embed=true&theme=system
```

El `site` y la `key` también están en el modelo `website`
(`plausible_site`, `plausible_shared_key`) y **sí** se leen por XML-RPC. Con eso, la
API interna del panel responde en abierto:

```python
HOST = "https://saas-analytics.odoo.com"
s.get(f"{HOST}/share/{SITE}?auth={KEY}&embed=true")          # abre la sesión compartida
s.get(f"{HOST}/api/stats/{SITE}/top-stats?auth={KEY}&period=28d")
s.get(f"{HOST}/api/stats/{SITE}/pages?auth={KEY}&period=28d&limit=500")
s.get(f"{HOST}/api/stats/{SITE}/sources?auth={KEY}&period=28d")
```

`period` acepta `day`, `7d`, `28d`, `month`, `6mo`, `12mo`. El rango a la medida
(`period=custom&date=...`) **no** respondió con este formato — usa los periodos
predefinidos.

> 🔑 La `plausible_shared_key` es de **solo lectura** y vive en Odoo. **No la
> escribas en este repo**: léela del modelo `website` en cada corrida.

Para saber qué renderiza de verdad, contra el sitio público:

```bash
curl -s -A "Mozilla/5.0" https://www.mozaprintmx.com/ -o home.html
grep -o 'href="[^"]*\(wa\.me\|api\.whatsapp\)[^"]*"' home.html | sort | uniq -c

# Cuántos van a cada número en esa página
grep -c '5664705479' home.html   # nuevo (Odoo)
grep -c '5632776277' home.html   # viejo (celular)
```

Tres notas de API que costaron tiempo:

- El dominio vacío se pasa como `[]`, no como `[[]]` — `[[]]` revienta con
  `ValueError: Domain() invalid item in domain: []`.
- En saas~19.3 `ir.attachment` **no tiene campo `datas`**: el contenido se lee
  con `raw`, y con `read`, no con `search_read` (es computado, no almacenado).
- La API key **JSON-2** del `.env` del repo devolvía **401** el 2026-09-10. Estas
  consultas se corrieron por **XML-RPC** con las credenciales de
  `analysis/supplier-sync/.env` (`ODOO_URL` / `ODOO_DB` / `ODOO_USER` /
  `ODOO_PASSWORD`), que es el camino que usan los scripts recientes del repo.

---

## Relacionado

- `docs/whatsapp-implementacion.md` — la guía de la Fase 4, bloque E
- `decisions/008-whatsapp-nativo-odoo.md` — por qué Odoo es dueño del webhook
- `docs/upgrades/README.md` — incidencias donde `arch_db` traducido rompió el sitio
