# Sitio web — enlaces de WhatsApp y zonas editables

> **Para qué existe**: al conectar el número nuevo a Odoo (Fase 4, bloque E) hubo
> que averiguar **de dónde sale cada enlace de WhatsApp del sitio**. Derivarlo
> costó una sesión entera. Este documento evita repetirla.
>
> **Medido contra producción el 2026-09-09** con consultas de solo lectura y
> `curl` contra el sitio público. Si cambia el sitio, vuelve a correr las
> consultas de la sección 8.

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

## 2. Las 14 vistas con enlaces de WhatsApp

Todas apuntan al número **de siempre**, `5632776277`. Ninguna al número nuevo de
Odoo.

| id | Vista | Dónde sale | Notas |
|---|---|---|---|
| 2342 | `website.inicio` | `/` | 2 enlaces |
| 3884 | `website.servicios` | `/servicios` | |
| **4095** | `header_social_links` | **global** | Ícono de redes, en todas las páginas |
| 4122 | `website.contactanos` | `/contactanos` | |
| **4318** | `header_call_to_action` | **global** | Botón verde del header. **Ver sección 4** |
| **4504** | `template_footer_descriptive` | **global** | Pie de página, 2 enlaces |
| 4725 | `landing-page_321f1b` | `/lp-nadiveno-2025` | Prefijo `521`, no `52` |
| 5020 | `inicio_ed64ed` | `/testinicio` | **no publicada** |
| ~~5028~~ | `products_oe_structure_website_sale_products_1` | — | **ARCHIVADA**, no renderiza. Hero viejo de la tienda, reemplazado por 5029 el 2026-01-19 |
| 5029 | `products_oe_structure_products_header_shop` | Header de `/shop` | Botón «Cotiza ahora» |
| 5049 | `kits-de-bienvenida` | `/kits-de-bienvenida` | 4 enlaces, **con `utm_campaign`** |
| 5050 | `kits-de-bienvenida_0d8ee5` | `/eventos-y-agencias` | Texto precargado de brief |
| 5051 | `kits-de-bienvenida_3564e3` | `/catalogos` | **no publicada** |
| 5052 | `..._0d8ee5_4a6b20` | `/regalos-corporativos` | **con `utm_campaign`** |

**Tres son globales** (4095, 4318, 4504): salen en **todas** las páginas. Es el
dato que más cambia una decisión — cualquier botón que se ponga en una página
concreta convive con estos tres en la misma pantalla.

**Dos no están publicadas** (5020, 5051): cambiarlas no sirve de nada.

**Dos traen `utm_campaign`** (5049, 5052): son las únicas con atribución medible
que ya existe.

### Lo que realmente renderiza (verificado con `curl`, sin sesión)

| Página | Enlaces de WhatsApp en el HTML |
|---|---|
| `/` (portada) | **9** |
| `/shop/<producto>` | **7** |

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

## 4. Bug vivo: el header manda `[NOMBRE_PRODUCTO]` y `[SKU]` literales

La vista **4318** (`header_call_to_action`, global) tiene este enlace:

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

Arreglarlo es una de dos: quitar los corchetes del texto, o conectar el JS al
`href`.

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
3. Barra de herramientas → editor de enlace → reemplaza la URL
4. **Guardar**

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

> 🟠 **El bloque del pie tiene un pendiente abierto con riesgo aceptado.** El
> detalle **no va en este repo porque es público**: está en
> `analysis/supplier-sync/HALLAZGO_JS_INVENTARIO.md` (gitignored). Antes de tocar
> ese código, **léelo**.

---

## 8. Cómo regenerar este inventario

```python
# Vistas con enlaces de WhatsApp (incluye archivadas)
call("ir.ui.view", "search_read",
     ["|", ("arch_db", "like", "wa.me"), ("arch_db", "like", "api.whatsapp")],
     fields=["id", "name", "key", "active", "website_id"],
     context={"active_test": False})
```

⚠️ **`arch_db ilike 'whatsapp'` NO basta**: `wa.me` no contiene esa palabra. Hay
que buscar los dos patrones o se escapan vistas. Ese error hizo que en la primera
pasada faltaran enlaces.

Para saber qué renderiza de verdad, contra el sitio público:

```bash
curl -s -A "Mozilla/5.0" https://www.mozaprintmx.com/ -o /tmp/home.html
grep -o 'href="[^"]*\(wa\.me\|api\.whatsapp\)[^"]*"' /tmp/home.html | sort | uniq -c
```

Dos notas de API que costaron tiempo:

- El dominio vacío se pasa como `[]`, no como `[[]]` — `[[]]` revienta con
  `ValueError: Domain() invalid item in domain: []`.
- En saas~19.3 `ir.attachment` **no tiene campo `datas`**: el contenido se lee
  con `raw`, y con `read`, no con `search_read` (es computado, no almacenado).

---

## Relacionado

- `docs/whatsapp-implementacion.md` — la guía de la Fase 4, bloque E
- `decisions/008-whatsapp-nativo-odoo.md` — por qué Odoo es dueño del webhook
- `docs/upgrades/README.md` — incidencias donde `arch_db` traducido rompió el sitio
