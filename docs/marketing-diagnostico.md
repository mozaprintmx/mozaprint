# Diagnóstico de Marketing — estado real medido

> Medido contra producción el **2026-08-26** con consultas de solo lectura.
> Existe porque el plan de replanteo asumía que Marketing estaba en cero. **No lo
> está**: arrancó en marzo-abril de 2026 y se detuvo. Este documento registra qué
> hay, para no volver a recomendar desde una suposición.

---

## 1. Lo que existe

### Listas de correo — 6 listas, ~850 contactos

| Contactos | Lista |
|---|---|
| **731** | `bdd sf` |
| **100** | `CDMX,GDL,EDO,VER,PUEB-Top scoring-54-Prioridad alta` |
| 13 | `BDD cdmx score alto` |
| 3 | `Segmentada por score y edo.` |
| 3 | `Newsletter` |
| 0 | *(lista de prueba con un correo personal como nombre)* |

**Hay audiencia real.** Las dos primeras concentran el 98% y ya vienen segmentadas
por score y estado de la República.

### Envíos — 5, todos en marzo-abril

| Fecha | Enviados | Abiertos | Clics |
|---|---|---|---|
| 2026-04-13 | **0** | 0 | 0 |
| 2026-04-11 | 12 | 4 | 0 |
| 2026-03-10 | 12 | 3 | 0 |
| 2026-03-10 | 3 | 1 | 0 |
| 2026-03-10 | 3 | 1 | 0 |

**Aperturas de ~30%**, que para B2B es sano. **Cero clics** en todos.

### Campaña de automatización — creada y detenida

| Campo | Valor |
|---|---|
| Nombre | `Nurturing Lead nuevos Mozaprint` |
| Creada | 2026-04-12 |
| Modelo | `crm.lead` |
| Filtro | `stage_id in [6]` |
| Pasos | **1** (Email 1 · Presentación MP) |
| Estado | **`stopped`** |

---

## 2. La lectura

**El problema no es de herramientas.** Marketing Automation, Email Marketing y SMS
están instalados; hay 850 contactos segmentados y una campaña armada.

Lo que pasó se parece más a esto: se hicieron pruebas diminutas (3 a 12
destinatarios), las aperturas salieron bien, **y aun así no se escaló a los 731**.

### Hipótesis principal: entregabilidad

Enviar a 731 contactos desde `mozaprintmx.odoo.com` con el **SPF en `-all`
estricto** es la forma clásica de quemar un dominio. Y el correo bidireccional
`@mozaprintmx.com` sigue pendiente en el roadmap, en la sección de infraestructura.

Encaja con los síntomas: envíos de prueba pequeños, ningún envío grande, y un
último intento de 0 enviados.

> ⚠️ **Es una hipótesis, no un hallazgo.** Encaja con los datos, pero **hay que
> preguntarle a Karina antes de rediseñar nada**: puede haber una razón mucho más
> simple —falta de contenido, prioridades, o que el filtro de la campaña no
> encontraba leads— y rediseñar sobre una suposición sería repetir el error que
> este documento existe para evitar.

### La otra lectura: cero clics

Cinco envíos, ~11 aperturas, **cero clics**. Con volúmenes tan bajos no es
concluyente, pero apunta a que el correo no llevaba a ninguna parte accionable.
Si se reactiva, conviene que cada envío tenga un destino claro y medible.

---

## 3. La audiencia que nadie está trabajando

Aparte de las listas, hay una audiencia mejor y sin tocar:

| | |
|---|---|
| Cotizaciones creadas | **447** desde jul-2025 (~36/mes, creciendo) |
| Convertidas a venta | **64 = 14%** |
| **En borrador, nunca cerradas** | **379** |

**379 personas que pidieron precio y se enfriaron.** Es la señal de intención más
fuerte que existe en el negocio y no hay ningún seguimiento automático sobre ella.
Es el equivalente, en cotizaciones, a las 3 alertas de pipeline que ya existen
para leads.

Secuencia propuesta: recordatorio a los 3 días · seguimiento a los 10 ·
reactivación a los 30.

---

## 4. El chatbot que ya existe y está vacío

| | |
|---|---|
| Agentes IA activos | **6** — incluye **«ChatBot MozaPrint»** y «Live Chat AI Agent» |
| Skills nativas | Create Leads · Information retrieval for Products · Create/Update Records · Web Search |
| Artículos en Información | **73** (incluidos los dos manuales de personalización) |
| **Fuentes cargadas en los agentes** | **0** |
| Canal de livechat | 1, aún llamado «YourWebsite.com», 1 conversación |

Alguien construyó el chatbot y **nunca se le dio de comer**. Tiene skills que crean
leads y consultan productos, y cero conocimiento del negocio.

`ai.agent.source` acepta `article_id` → los artículos de Información se pueden
cargar como fuentes **por API**, sin código y sin costo.

Es la acción de mayor retorno por hora invertida que hay hoy sobre la mesa: en el
livechat del sitio, la IA **sí contesta sola**, es nativa y ya está instalada.

---

## 5. Qué hacer con esto

1. **Preguntar a Karina** por qué se detuvo la campaña de abril. Antes que nada.
2. **Cargar los 73 artículos** como fuentes del ChatBot MozaPrint.
3. **Configurar y publicar el livechat** (sigue con el nombre por defecto).
4. **Atender el dominio de correo** si la hipótesis de entregabilidad se confirma.
5. **Armar la secuencia de las 379 cotizaciones frías**, que no depende de WhatsApp.

Ver `decisions/008-whatsapp-nativo-odoo.md` para dónde entra WhatsApp en todo esto.
