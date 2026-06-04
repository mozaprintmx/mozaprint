# Proceso del equipo — CRM y pipeline de ventas

> Guía operativa para Karina y el equipo de ventas. Cómo usar el CRM de Odoo
> para que las alertas automáticas funcionen correctamente.

---

## La regla más importante

**Cada vez que actúes con un cliente, mueve su tarjeta en el pipeline.**

Eso es todo. Si haces esto consistentemente, el sistema funciona solo.

---

## Por qué es importante mover la tarjeta

Odoo tiene alertas automáticas que se disparan cuando una oportunidad lleva
demasiado tiempo sin avanzar. Estas alertas miden el tiempo desde la
**última vez que moviste la tarjeta de etapa**.

Odoo **no sabe** que enviaste un correo desde Gmail, que llamaste al cliente,
o que mandaste una cotización por WhatsApp — a menos que muevas la tarjeta.

**Resultado si no mueves la tarjeta**: la alerta se dispara aunque ya hayas
actuado con el cliente. La Alerta 3 manda un correo al equipo, lo cual se
convierte en ruido innecesario.

---

## Qué hacer en cada situación

| Acción que tomaste | Qué hacer en el CRM |
|---|---|
| Contactaste al cliente por primera vez | Mover de "Nuevo lead" a "Contactado" |
| Enviaste una cotización | Mover a "Cotización enviada" (o la etapa que corresponda) |
| El cliente pidió pensar / no respondió | Dejar donde está, agregar nota interna con fecha |
| El cliente confirmó interés | Mover a la siguiente etapa |
| El cliente no está interesado | Marcar como **Perdido** con la razón |
| El lead no califica | Marcar como **Perdido** con razón "No califica" |

> **Regla de oro**: si dudas si moverlo o no, muévelo. Es mejor un historial
> activo que alertas falsas.

---

## Las alertas automáticas y qué significan

### Alerta 1 — "Alerta: Lead sin calificar 1 día"

Se dispara cuando un **Lead** (todavía no calificado como Oportunidad) lleva
más de 1 día sin ser revisado.

**Qué hacer**: revisar el lead, decidir si se convierte a Oportunidad o se
marca Perdido. No dejar leads sin resolver.

---

### Alerta 2 — "Alerta: Oportunidad sin avanzar 1 día"

Se dispara cuando una **Oportunidad** en la etapa "Nuevo lead" lleva 1 día
sin que se haya movido de etapa.

**Qué ves**: actividad "Urge contactar" asignada a Juan Carlos + etiqueta
naranja **Urge contactar** en la tarjeta.

**Qué hacer**: contactar al cliente si no lo has hecho, o mover la tarjeta
si ya lo contactaste.

---

### Alerta 3 — "Alerta: Oportunidad en peligro 3 días"

Se dispara cuando una **Oportunidad** en la etapa "Nuevo lead" lleva 3 días
sin avanzar.

**Qué ves**: actividad "PELIGRO - posible pérdida" + etiqueta roja
**Peligro, posible pérdida** + correo de alerta al equipo.

**Qué hacer**: acción inmediata — contactar al cliente, decidir si sigue
siendo viable, o marcar Perdido si ya no aplica.

---

## Las etiquetas y qué significan

| Etiqueta | Color | Significado |
|---|---|---|
| Urge contactar | 🟡 Naranja | Lleva 1 día sin avanzar — actuar hoy |
| Peligro, posible pérdida | 🔴 Rojo | Lleva 3 días sin avanzar — actuar ahora |

Cuando una oportunidad tiene **ambas etiquetas**, lleva 3+ días sin moverse.
Es la prioridad más alta del pipeline.

Para quitar las etiquetas: editar el lead y eliminarlas manualmente una vez
que la situación se resolvió.

---

## Cuándo cambia este proceso

Esta dependencia de "mover tarjetas manualmente" es temporal. Desaparecerá
cuando se implemente una de las siguientes mejoras:

1. **Correo bidireccional `@mozaprintmx.com` en Odoo** (prioridad media en
   el roadmap): Odoo detectará automáticamente las respuestas de clientes
   por correo, sin que el vendedor tenga que mover nada.

2. **Integración WhatsApp (Fase 4)**: los mensajes de WhatsApp se registrarán
   directamente en Odoo, actualizando automáticamente la actividad del lead.

Hasta entonces, mover la tarjeta es la forma de decirle a Odoo "ya actué".

---

## Preguntas frecuentes

**¿Qué pasa si marco un lead como Perdido por error?**
Se puede reabrir desde el filtro "Perdidos" en el CRM (filtrar → Perdido → abrir → botón Reactivar).

**¿Debo mover la tarjeta si solo agregué una nota interna?**
No es obligatorio, pero si la nota implica que tomaste acción con el cliente, mueve la tarjeta para resetear el contador de alertas.

**¿Qué etapa uso si el cliente pidió tiempo para decidir?**
Déjalo en la etapa actual (no retrocedas) y agrega una nota con la fecha y lo acordado. Si pasa 1 día sin novedad, la alerta te recordará revisarlo.

**¿Puedo desactivar las alertas si molestan?**
Las alertas están calibradas al SLA del negocio (24h para calificar, 1-3 días para oportunidades). Si se disparan frecuentemente como falsos positivos, probablemente haya leads sin mover. La solución es mover las tarjetas, no desactivar las alertas.
