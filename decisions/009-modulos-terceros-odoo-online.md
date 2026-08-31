# ADR 009: Módulos de terceros imposibles en Odoo Online — y cuándo evaluar Odoo.sh

**Fecha**: 2026-08-31
**Estado**: Aceptado (es una restricción de la plataforma, no una preferencia)
**Decisores**: Juan Carlos Asomoza

## Contexto

Al buscar una IA que conteste WhatsApp dentro de Odoo aparecen **decenas** de
módulos en el Apps Store que hacen exactamente eso: *AI WhatsApp Chatbot*,
*AI WhatsApp Assistant*, *AI WhatsApp MCP Agent*, y varios más para 19.0. Se ven
bien, están mantenidos y resolverían el problema sin construir nada.

**Ninguno se puede instalar en Mozaprint.**

## La restricción

Documentación y respuestas oficiales de Odoo:

> *"Third-party applications can NOT be installed on Online (SaaS) databases."*
>
> *"Third-party apps sold on Odoo Apps cannot be used on Odoo Online, unless they
> are data-modules (that do not include any python files)."*

Mozaprint corre **Odoo Online Custom** (`mozaprintmx.odoo.com`). Por tanto:

- ❌ Módulos del Apps Store con código Python — **imposible**
- ❌ Módulos propios — **imposible**
- ✅ Módulos oficiales de Odoo — sí, todos (el plan Custom los incluye)
- ✅ Studio, Automation Rules, Server Actions, AI Fields — sí, con el matiz del
  cargo por línea de código (ver ADR 007)

Esto ya estaba dicho en `CLAUDE.md` («No hay acceso a `addons/`»), pero **no
estaba dicho que el Apps Store completo queda fuera**, y esa es la parte que
cuesta descubrir a mitad de una evaluación.

### Consecuencia concreta para el proyecto

**El WhatsApp nativo de Odoo no trae chatbot ni IA.** Enruta mensajes a Discuss y
ahí los contesta una persona. El agente nativo de IA responde en el **livechat del
sitio web**, no en WhatsApp. Como los módulos que sí lo hacen no son instalables,
la IA sobre WhatsApp tiene que venir de fuera. Ver ADR 008.

## Cuándo reconsiderar Odoo.sh

Migrar a **Odoo.sh** levanta la restricción: admite módulos de terceros y código
propio. No se propone hoy, pero conviene tener escritos los números y el umbral
para no rediscutirlo desde cero.

### Costo

| Concepto | Aproximado |
|---|---|
| Worker adicional | **~$58-70 USD/mes** |
| Almacenamiento | ~$0.20-0.25 USD/GB/mes |
| Entorno de staging | ~$14-18 USD/mes |
| Licencias Enterprise | **igual que hoy** |

Para Mozaprint: **~$70-100 USD/mes** encima de lo actual, más la licencia de los
módulos que se compren.

### Qué se gana
- Chatbot de IA sobre WhatsApp **dentro** de Odoo, visual, sin construirlo.
- Código propio sin las limitaciones del sandbox de Server Actions.
- Entornos de staging de verdad, versionados con git.

### Qué se pierde
- **El riesgo de upgrade pasa a ser nuestro.** El historial de este proyecto dice
  que los upgrades rompen lo que se sale del camino nativo: 5,012 fichas de
  producto caídas en 19.2, la columna de imagen del PDF borrada dos veces,
  `/contactanos` en 500 en 19.3. Con módulos de terceros eso se multiplica y ya no
  hay a quién reclamarle.
- Hay que mantener infraestructura, que hoy no se mantiene.

### Umbral propuesto

Evaluar Odoo.sh **solo si** se cumplen las dos:

1. La opción externa de la ADR 008 se probó y **se quedó corta** — no por falta de
   ganas de mantenerla, sino por un límite real.
2. El costo de la solución externa **se acerca a los $70-100 USD/mes**, punto en
   el que Odoo.sh deja de ser más caro.

Mientras el servicio externo cueste ~€5/mes, la comparación no está ni cerca.

## Nota sobre el cargo por líneas de código

Investigando esto apareció un dato que **matiza la ADR 007**. Un empleado de Odoo,
en el foro oficial:

> *"Opting out is possible. You need to implement yourself, or work with a Partner
> under their arrangement for maintenance. If Odoo implements your database via a
> Success Pack, you can't opt out."*

Mozaprint implementa por su cuenta y no tiene Success Pack, así que **calificaría**.

⚠️ **Sin confirmar**: en el mismo hilo, un Account Manager de Odoo sostuvo lo
contrario («mandatory for Online customer»). Hay que confirmarlo con el ejecutivo
de cuenta antes de apoyarse en ello.

**Esto NO reabre la ADR 007.** El diseño nativo de la Fase 3 —productos y reglas
de lista de precios en lugar de un motor en Python— es mejor por robustez, no por
precio: son datos, sobreviven upgrades y cualquiera los puede auditar. El motor
seguiría siendo peor aunque fuera gratis. Lo que cambia es que **la restricción
económica es más blanda de lo que asumimos**, y eso amplía el abanico hacia
adelante.

## Tareas derivadas

- [ ] Confirmar con el ejecutivo de cuenta de Odoo si el opt-out del cargo por
      código aplica a Mozaprint
- [ ] Anotar en `CLAUDE.md` que el Apps Store completo queda fuera del alcance
