# Fase 1: Captura estructurada de leads — Estado

> Referencia completa de la Fase 1 — captura y seguimiento de leads.
> Estado: ✅ COMPLETADA · Última actualización: 2026-06-03 (v3)

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
| Limpieza del pipeline | ✓ Completado | 2026-06-03 |
| Etiquetas CRM (Urge contactar / Peligro) | ✓ En producción | 2026-06-03 |
| 3 alertas de seguimiento (Automation Rules) | ✓ En producción | 2026-06-03 |
| `x_studio_origen_url` automático | 🔵 Mejora futura | — |
| Asignación automática a Sales Team | 🔵 Mejora futura | — |

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

### 6. Etiquetas CRM

Dos etiquetas creadas en CRM para identificar visualmente el estado de urgencia en el pipeline:

| Etiqueta | Color | Cuándo aparece |
|---|---|---|
| Urge contactar | Naranja/amarillo | Alerta 2 la agrega al día de sin avanzar en "Nuevo lead" |
| Peligro, posible pérdida | Rojo | Alerta 3 la agrega a los 3 días sin avanzar en "Nuevo lead" |

Las etiquetas son **acumulativas**: a los 3 días una oportunidad tendrá ambas etiquetas, mostrando la escalada en el pipeline sin perder el contexto de la alerta anterior.

---

### 7. Alertas de seguimiento (3 Automation Rules)

Tres reglas basadas en tiempo configuradas en CRM → Automation Rules:

| Regla | Modelo | Campo tiempo | Espera | Filtro | Acciones |
|---|---|---|---|---|---|
| Alerta - Lead sin calificar 1 día | crm.lead | Creado el (`date`) | 1 día | Tipo = Lead | Actividad: "Calificar o descartar este lead" → Juan Carlos |
| Alerta - Oportunidad sin avanzar 1 día | crm.lead | Últ. act. etapa (`date_last_stage_update`) | 1 día | Tipo = Oportunidad + Etapa = Nuevo lead | Actividad: "Urge contactar" → Juan Carlos · Agregar etiqueta "Urge contactar" |
| Alerta - Oportunidad en peligro 3 días | crm.lead | Últ. act. etapa (`date_last_stage_update`) | 3 días | Tipo = Oportunidad + Etapa = Nuevo lead | Actividad: "PELIGRO" → Juan Carlos · Agregar etiqueta "Peligro, posible pérdida" · Correo a `mozaprintmx@gmail.com` |

**Comportamiento acumulativo**: las etiquetas se configuran con modo "Agregar" (no reemplazar), por lo que a los 3 días una oportunidad tendrá ambas etiquetas simultáneamente.

**Nota de calibración**: la Alerta 1 se ajustó de 2 días a 1 día para alinearse con el SLA de 24h del negocio.

**Validación pendiente**: esperar a que se disparen naturalmente con el pipeline real, o forzar el cron para verificar.

---

### 8. Regla de proceso crítica del equipo

> ⚠️ **IMPORTANTE — Comunicar a Karina y a todo vendedor que use el CRM**

**Contexto**: Odoo no está conectado al correo. La comunicación con clientes se hace desde Gmail. Odoo solo sabe que el vendedor actuó si el vendedor **mueve la tarjeta en el pipeline**.

**La regla**: cada vez que el vendedor actúe con un cliente (contactó, cotizó, envió info, llamó), debe mover la oportunidad/lead a la siguiente etapa en el CRM.

**Qué pasa si no se hace**: las alertas basadas en tiempo (`date_last_stage_update`) se disparan aunque el vendedor ya haya actuado, generando falsos positivos. La Alerta 3 manda correo al equipo, lo cual se vuelve ruido si el motivo fue solo no mover la tarjeta.

**Cuándo desaparece esta dependencia**:
1. Al implementar correo bidireccional `@mozaprintmx.com` en Odoo (tarea prioridad media en roadmap) — Odoo detectará las respuestas del cliente automáticamente
2. Al implementar integración WhatsApp (Fase 4) — los mensajes de WA se registrarán directamente en Odoo

Ver `docs/proceso-equipo-crm.md` para la guía operativa del equipo.

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

## Mejoras futuras (no bloquean operación)

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

### Validar alertas en funcionamiento real
Esperar a que las 3 alertas se disparen naturalmente con el pipeline real, o forzar el cron de Odoo para verificar que las acciones (actividades, etiquetas, correo) se ejecutan correctamente.

### Asignación automática a Sales Team
Manual funciona por ahora (equipo es de una persona). Configurar cuando crezca el equipo de ventas.

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

## Hallazgos del pipeline (se resuelven en Fase 4-6)

Estos dos problemas se identificaron durante la limpieza manual del pipeline de leads. No tienen solución completa en Fase 1; se resuelven cuando se conecta WhatsApp Cloud API + n8n.

---

### Hallazgo 1 — Identificación de contactos de WhatsApp

**Problema actual**: la mayoría de leads entran por WhatsApp. Sin conexión WhatsApp-Odoo, los clientes se ven solo por número en la WA Business App si no están guardados manualmente en el celular. Al crear el lead en Odoo solo queda el número, sin nombre, dificultando la limpieza del pipeline.

**Por qué no se resuelve hoy**: la agenda de la WA Business App no tiene API de escritura. Herramientas de terceros que prometen sincronizar nombres hacia la app violan términos de Meta (riesgo de ban del número) — descartadas.

**Solución en Fase 4-6**: la Cloud API con Coexistence entrega `profile.name` (el nombre que el cliente puso en su propio WhatsApp) en cada mensaje entrante. n8n lo usará para auto-crear o actualizar el contacto en Odoo antes de llamar al agente. Odoo se convierte en la fuente de verdad de contactos.

**Mitigación temporal (hasta Fase 4)**:
- Al registrar manualmente un lead de WhatsApp, poner SIEMPRE el número en el campo teléfono (formato +52 10 dígitos) para poder buscar por número en Odoo
- Mantener la práctica de guardar contactos en el celular con formato consistente (Nombre Apellido - Empresa) al cotizar

---

### Hallazgo 2 — Exclusión de proveedores del agente

**Problema actual**: el negocio contacta proveedores por WhatsApp para comprar mercancía. El agente Moza no debe responder a esos números (sería confuso y potencialmente problemático). Hoy se identifican con etiquetas en la WA Business App, pero esas etiquetas son locales del celular y no se exponen vía Cloud API.

**Solución en Fase 4-6**: pre-flight filter en n8n. Antes de que el agente responda cualquier mensaje, n8n verifica que el remitente no sea proveedor (`supplier_rank > 0` en Odoo), no esté marcado con `x_studio_no_agente = True`, ni sea un número interno. Si está excluido: conversación en modo manual, sin respuesta del agente, sin lead de venta en CRM.

**Preparación del terreno (se puede hacer antes de Fase 4)**:
- Asegurar que los proveedores activos estén registrados en Odoo (Compras → Contactos) con su número de WhatsApp en el campo teléfono o móvil
- Sin ese número en Odoo, el match por número no funcionará y el agente podría responder a un proveedor

Ver especificación completa del filtro en `specs/ai-agent-spec.md` → sección "Pipeline de mensajes entrantes".

---

## Referencias

- Campos custom detalle: `specs/data-model.md` → sección crm.lead
- Registro de campos en Studio: `odoo-extensions/studio-fields.yaml`
- Nota sobre prefijo x_studio_: `CLAUDE.md` y `odoo-extensions/studio-fields.yaml`
- Filtro de exclusión y auto-identificación: `specs/ai-agent-spec.md` → "Pipeline de mensajes entrantes"
- Campo x_studio_no_agente en res.partner: `specs/data-model.md` → sección res.partner
