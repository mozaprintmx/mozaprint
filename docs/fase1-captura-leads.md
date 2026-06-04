# Fase 1: Captura estructurada de leads — Estado

> Estado de implementación de la captura de leads en Odoo.
> Última actualización: 2026-06-03 (v2)

---

## Resumen de estado

| Componente | Estado | Fecha |
|---|---|---|
| Leads activados en CRM | ✓ En producción | 2026-06-03 |
| 5 campos custom en crm.lead | ✓ En producción | 2026-06-02 |
| Formulario /contactanos → CRM | ✓ En producción | 2026-06-03 |
| Automation Rule notificación web | ✓ En producción | 2026-06-03 |
| AI Lead Scoring | ✓ Funciona nativo | 2026-06-03 |
| Formularios /shop y ficha de producto | ✓ En producción | 2026-06-03 |
| Plantilla notificación (qty/producto/personalización) | ✓ En producción | 2026-06-03 |
| `x_studio_origen_url` automático | ⏳ Pendiente definición | — |
| Alertas de leads estancados | ⏳ Pendiente | — |
| Limpieza del pipeline actual | ⏳ Pendiente | — |
| Asignación automática a Sales Team | ⏳ Pendiente | — |

---

## Componentes implementados

### 1. Leads activados en CRM

La etapa "Leads" está activada en CRM → Configuración. Antes de esto, todos los contactos entraban directamente como Oportunidad. Ahora el flujo es:

```
Contacto entra → Lead → (revisar) → Convertir a Oportunidad → Pipeline de ventas
                                  ↘ Marcar Perdido (si no califica)
```

**Flujo de contactos**: Odoo NO crea un `res.partner` (Contacto) automáticamente al entrar un Lead. Los datos (nombre, teléfono, email) viven como texto dentro del lead. El Contacto formal se crea al "Convertir a Oportunidad", donde Odoo ofrece crear o vincular uno existente. Esto evita llenar el directorio de curiosos o spam.

---

### 2. Campos custom en crm.lead

Cinco campos creados vía Studio, disponibles en el formulario de lead. Ver `specs/data-model.md` y `odoo-extensions/studio-fields.yaml` para la lista completa.

> **IMPORTANTE**: Odoo Online fuerza el prefijo `x_studio_` en todos los campos de Studio. Usar siempre `x_studio_<nombre>` en Server Actions, workflows n8n y referencias de formulario.

| Nombre técnico | Etiqueta | Tipo |
|---|---|---|
| `x_studio_collected_qty` | Cantidad solicitada | Integer |
| `x_studio_collected_producto` | Producto solicitado | Char |
| `x_studio_collected_personalizacion` | Lleva personalización | Selection |
| `x_studio_origen_form` | Origen del formulario | Char |
| `x_studio_origen_url` | Origen URL | Char (pendiente: cómo se llena) |

---

### 3. Formulario /contactanos reconectado al CRM

**Configuración actual**:
- Acción: "Crear registro" → modelo `crm.lead`
- Tipo de lead: campo `type` oculto con valor `lead` (no `opportunity`)
- Mapeo de campos:

| Campo del formulario | Campo en crm.lead |
|---|---|
| Nombre | `contact_name` |
| Teléfono | `phone` |
| Correo | `email_from` |
| Empresa | `partner_name` |
| Asunto | `name` (título del lead) |
| Pregunta / Mensaje | `description` (aparece en pestaña Notas) |
| _(fijo)_ | `x_studio_origen_form` = "Contactanos" |

- Al enviar: muestra mensaje de confirmación al usuario
- Probado en producción: el Lead se crea correctamente con todos los campos

**Aclaración importante**: conectar el formulario al CRM **no impide** responder por correo. Se puede tener el Lead en CRM y además enviar notificaciones por correo simultáneamente — no son mutuamente excluyentes.

---

### 3b. Formularios /shop y ficha de producto

**Estado**: ✓ En producción 2026-06-03

Ambos formularios reconectados al CRM. Mapeo de campos:

**Formulario /shop (tienda)**:

| Campo del formulario | Campo en crm.lead |
|---|---|
| Nombre | `contact_name` |
| Correo | `email_from` |
| Teléfono | `phone` |
| Empresa | `partner_name` |
| Producto de interés | `x_studio_collected_producto` |
| Cantidad | `x_studio_collected_qty` |
| Personalización | `x_studio_collected_personalizacion` |
| Comentarios / Mensaje | `description` |
| _(fijo)_ | `x_studio_origen_form` = "Tienda" |

**Formulario de ficha de producto**:

| Campo del formulario | Campo en crm.lead |
|---|---|
| Nombre | `contact_name` |
| Correo | `email_from` |
| Teléfono | `phone` |
| Empresa | `partner_name` |
| Producto _(pre-rellenado con el producto de la ficha)_ | `x_studio_collected_producto` |
| Cantidad | `x_studio_collected_qty` |
| Personalización | `x_studio_collected_personalizacion` |
| Mensaje | `description` |
| _(fijo)_ | `x_studio_origen_form` = "Producto" |

**Diferenciadores respecto a /contactanos**:
- Incluyen campos de cantidad, producto y personalización (mapean a los campos custom)
- El producto viene pre-rellenado con el nombre del producto de la ficha cuando el cliente abre el formulario desde una ficha
- `x_studio_origen_form` toma valores distintos para identificar la fuente exacta

**Corrección aplicada**: el typo `"Si"` (sin tilde) en el dropdown web de personalización fue corregido a `"Sí"` para coincidir con el valor del campo `x_studio_collected_personalizacion` en Odoo. Sin esta corrección, el valor no se mapeaba.

---

### 4. Automation Rule: notificación de nuevo lead web

**Nombre**: "Notificar nuevo lead de formulario web"

| Parámetro | Valor |
|---|---|
| Modelo | `crm.lead` |
| Disparador | Al crear |
| Filtro | `x_studio_origen_form` está establecido (≠ vacío) |
| Acción | Enviar correo electrónico (modo "Correo electrónico", no "Mensaje") |
| Plantilla | "Notificación nuevo lead web" |
| Destinatario | `info@mozaprintmx.com` |

El filtro limita la regla a leads de formularios web — no dispara para leads creados manualmente en Odoo.

**Plantilla actualizada (2026-06-03)**: la plantilla de notificación ahora incluye los campos `x_studio_collected_qty` (Cantidad), `x_studio_collected_producto` (Producto) y `x_studio_collected_personalizacion` (Personalización), además del nombre, teléfono, correo y origen. Esto aplica a los tres formularios (/contactanos, /shop, ficha de producto) porque todos comparten la misma regla de notificación.

**Nota técnica sobre variables en plantillas**: las variables dinámicas (`nombre del cliente`, `teléfono`, etc.) deben insertarse usando el comando `/campo` dentro del editor de plantillas de Odoo. **No** escribir `{{ object.campo }}` a mano — se guarda como texto literal y no se sustituye al enviar.

---

### 5. AI Lead Scoring nativo

Odoo Online calcula automáticamente la probabilidad de cierre de cada lead sin configuración adicional. Usa el tier de IA incluido en el plan Custom — no requiere API key de OpenAI ni Server Action propia.

Odoo también detecta automáticamente:
- **Leads similares**: contactos con mismo email/teléfono
- **Visitas a página**: si el visitor ID del lead coincide con visitas al sitio

---

## Hallazgos técnicos importantes

### Cola de correo en Odoo Online (~1h de latencia)
Odoo Online procesa el envío de correos en cola vía cron, aproximadamente cada hora. La notificación de nuevo lead por correo **puede tardar hasta ~1h** en llegar.

**Aceptado por ahora porque**:
1. El Lead se crea al instante en el CRM — lo operativamente crítico
2. El formulario /contactanos no es el canal principal (el grueso entra por WhatsApp)
3. Las notificaciones de WhatsApp vía n8n (Fase 4) serán instantáneas

**Reconsiderar si**: se detecta pérdida de leads web por respuesta tardía, o si los formularios web se vuelven el canal principal.

### Automation Rules sin costo extra
Las Automation Rules no tienen costo adicional en el plan Custom de Odoo Online. Se pueden crear las que hagan falta.

---

## Pendientes

### Definir cómo llenar x_studio_origen_url
El campo existe en Odoo pero la lógica de captura está pendiente. Opciones a evaluar:
- Variable nativa de Odoo en el formulario web (si existe)
- JavaScript en el sitio que capture `window.location.href` y lo inyecte en un campo oculto del formulario
- Parámetro UTM en la URL

**Consideración**: el sitio usa Cloudflare como proxy/CDN. Verificar que el cache de Cloudflare no interfiera con la captura de URLs dinámicas.

### Alertas de leads estancados
Hay leads en el CRM de hasta 42 días sin movimiento. Pendiente configurar una Automation Rule que:
- Dispare cuando un lead lleva X días sin actividad (sin notas, sin cambio de etapa)
- Notifique al vendedor asignado (o a `info@`) con el nombre y datos del lead
- Criterio sugerido: alerta a los 7, 14 y 30 días sin movimiento

**Por definir**: umbral exacto de días y acción (solo notificar, o marcar perdido automáticamente después de cierto tiempo).

### Limpieza del pipeline actual
El CRM tiene leads acumulados de semanas anteriores sin clasificar. Antes de activar alertas automáticas, conviene hacer una pasada manual para:
- Revisar leads viejos y marcar los que ya se perdieron
- Convertir a Oportunidad los que sí avanzan
- Establecer una línea base limpia

### Asignación automática a Sales Team
Pendiente configurar reglas de asignación de leads al equipo de ventas correcto según origen o criterios del negocio.

---

## Flujo completo de un lead (actual)

```
1. Cliente llena formulario web (cualquiera de los tres):
   ├── /contactanos → x_studio_origen_form = "Contactanos"
   ├── /shop (tienda) → x_studio_origen_form = "Tienda"
   └── Ficha de producto → x_studio_origen_form = "Producto"

2. Odoo crea crm.lead con todos los campos mapeados:
   ├── Datos de contacto: nombre, teléfono, correo, empresa
   ├── Datos del pedido: qty, producto, personalización (si aplica)
   ├── Origen: x_studio_origen_form según punto de entrada
   └── AI Lead Score calculado automáticamente al crear

3. Automation Rule detecta x_studio_origen_form establecido
4. Cola de correo procesa (≤1h) → notificación a info@mozaprintmx.com
   └── Incluye: nombre, teléfono, correo, producto, cantidad, personalización, origen

5. Vendedor revisa el lead en CRM
   ├── Si califica → Convertir a Oportunidad → crear/vincular Contacto → pipeline
   └── Si no califica → Marcar Perdido con razón
```

---

## Referencias

- Campos custom detalle: `specs/data-model.md` → sección crm.lead
- Registro de campos en Studio: `odoo-extensions/studio-fields.yaml`
- Nota sobre prefijo x_studio_: `CLAUDE.md` y `odoo-extensions/studio-fields.yaml`
