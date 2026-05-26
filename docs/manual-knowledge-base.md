# Manual de mantenimiento del agente IA Moza

> Para: Karina (Dirección de Marketing)
> Versión: 1.0 · 2026-05-24

## Tu rol

Eres la dueña del **knowledge base** del agente IA Moza. Esto significa que tu 
trabajo es asegurar que Moza tenga la información correcta y actualizada para 
responder bien a los clientes de Mozaprint.

No necesitas saber programar. Lo que sí necesitas:
- Tener acceso a Odoo (módulo Knowledge)
- Revisar conversaciones del agente periódicamente
- Identificar gaps de información y corregirlos
- Coordinar con el equipo cuando cambian políticas de la empresa

## ¿Qué es el knowledge base?

Es el conjunto de documentos que Moza "lee" para responder. Vive en Odoo 
en el módulo **Knowledge** (lo encuentras en el menú lateral izquierdo).

Está organizado en carpetas:

```
📚 Knowledge / Moza
├── 📄 FAQs (top 15 preguntas frecuentes)
├── 📄 Técnicas de personalización (una página por técnica)
├── 📄 Políticas comerciales (descuentos, anticipos, devoluciones)
├── 📄 Tiempos de entrega típicos
├── 📄 Información de la empresa (contacto, horarios)
└── 📄 Política de cambios y cancelaciones
```

## Tus tareas semanales (~1 hora total)

### Lunes (15 min): revisar conversaciones del fin de semana

1. Entra a Odoo → Discuss → Filtros: "WhatsApp" + "AI atendió"
2. Abre 5-10 conversaciones que el AI atendió sin escalar
3. Lee de principio a fin
4. Pregúntate:
   - ¿La respuesta fue correcta?
   - ¿Faltó información que Moza debía saber?
   - ¿El cliente quedó satisfecho?

Si encuentras algo mal, agrégalo a "Issues de la semana" (lista que mantienes 
tú o en Trello/Notion como prefieras).

### Miércoles (15 min): revisar escalamientos

1. Filtros: "WhatsApp" + "Escalada por AI"
2. Revisa los motivos de escalado
3. Identifica patrones: ¿siempre escala por X? Entonces falta cubrir X en el KB

### Viernes (30 min): actualizar el KB

1. Repasar los issues identificados
2. Para cada uno, decidir:
   - ¿Es una FAQ nueva? → Agregar a "FAQs"
   - ¿Es una política que cambió? → Actualizar la página correspondiente
   - ¿Es algo que requiere decisión del equipo? → Plantearlo en junta semanal

## Cómo agregar una FAQ nueva

1. Entra a Knowledge / Moza / FAQs
2. Click "Nueva página" o duplicar una existente como template
3. Completa siguiendo este formato:

```
# Pregunta canónica
[Escribe la pregunta tal como un cliente la haría]

## Variantes de la pregunta
[5-10 formas distintas en que un cliente puede preguntar lo mismo]
- ¿variante 1?
- ¿variante 2?
- ...

## Respuesta corta (la que Moza usa por default)
[2-3 oraciones, lenguaje natural, tono profesional cercano]

## Respuesta detallada (si el cliente pide más info)
[Hasta 1 párrafo, con detalle]

## Cuándo escalar a humano
- Cuando el cliente pregunte por X
- Cuando mencione Y
- ...

## Datos necesarios del cliente para responder bien
- Su industria (si aplica)
- Cantidad solicitada
- ...

## Última actualización
2026-05-24
## Responsable
Karina
```

4. Guarda
5. En 5 minutos Moza ya tiene la nueva FAQ disponible

## Cómo actualizar una política existente

Igual que arriba, pero editas la página existente. **No la borres**, solo edita. 
El historial se conserva en Odoo Knowledge.

Después de editar:
- Marca la sección "Última actualización" con la fecha de hoy
- Si el cambio es importante, agrega comentario al final explicando qué cambió

## Cómo agregar una técnica nueva

Si Mozaprint empieza a ofrecer una técnica nueva:

1. **No edites el KB primero**. Primero pide al equipo técnico (operador) 
   que cree la técnica en Odoo > Configuración > Técnicas de Personalización.
2. Una vez creada, vuelve al Knowledge / Moza / Técnicas
3. Crea página nueva siguiendo el formato:

```
# [Nombre de la técnica]

## Qué es
[2-3 oraciones explicando]

## En qué materiales funciona
[Lista]

## En qué materiales NO funciona
[Lista]

## Cantidad mínima recomendada
[Número]

## Tiempo típico de producción
[Días hábiles]

## Casos de uso típicos
[Ejemplos]

## Ventajas vs otras técnicas
[Diferenciadores]

## Limitaciones
[Honestos, lo que no se puede]
```

## Cómo identificar conversaciones problemáticas

Patrones que indican que algo va mal:

| Patrón | Qué significa | Acción |
|---|---|---|
| Cliente repite la pregunta 3+ veces | Moza no entendió, o respuesta no satisfactoria | Revisar FAQ relacionada, mejorar variantes |
| Conversación >15 turnos sin resolución | Tema más complejo que el KB | ¿Falta info? ¿Debe escalar antes? |
| Cliente molesto / quejas explícitas | Algo se manejó mal | Revisar URGENTE, ajustar políticas |
| Moza dijo algo incorrecto | Alucinación o KB desactualizado | Corregir KB inmediatamente |
| Cliente preguntó algo no en KB y Moza no escaló | Faltó regla de escalado | Avisar al operador para ajustar prompt |

## Cómo medir si Moza está mejorando

Cada mes el operador te envía un reporte con:

- **Tasa de resolución sin escalar**: % de conversaciones que Moza cerró sin humano
- **Tasa de satisfacción**: encuesta post-conversación
- **Alucinaciones detectadas**: errores de Moza encontrados en review
- **FAQs nuevas agregadas en el mes**
- **Cambios de política reflejados en KB**

Tu meta: subir resolución, bajar alucinaciones. Si después de 2 meses la 
resolución no sube, hay que replantear.

## Reglas que NO debes hacer

❌ **Borrar páginas del KB**. Edita siempre, nunca borres. Si algo queda 
obsoleto, mueve a carpeta "Histórico" o marca como inactivo.

❌ **Agregar precios específicos al KB**. Los precios viven en Odoo (productos 
y matriz de costos). Si pones un precio en el KB y cambia, Moza dará dato 
equivocado.

❌ **Crear FAQs sin testear**. Después de agregar, escribe a Moza como cliente 
y verifica que responde lo que esperabas. Si no, ajusta variantes de la pregunta.

❌ **Cambiar reglas del agente sin avisar al equipo**. Si quieres que Moza 
deje de escalar en cierto caso, hay que coordinar con operador y vendedores.

❌ **Compartir el KB con clientes**. Es información interna. Si un cliente 
pide "el catálogo", se le manda el catálogo del sitio web, no el KB.

## Cuándo escalar al operador / equipo técnico

- Si descubres patrones de error sistemáticos en Moza
- Si una política cambia y no sabes cómo reflejarla en el KB
- Si Moza responde con tono inadecuado (muy formal, muy informal)
- Si Meta rechazó alguna plantilla de WhatsApp
- Si la tasa de resolución cae mes contra mes

## Junta mensual de revisión

Cada último viernes del mes, junta de 1h con operador y vendedores:

**Agenda**:
1. Reporte del mes (5 min)
2. Top 5 issues encontrados (15 min)
3. Cambios al KB acordados (15 min)
4. Cambios a políticas si aplican (15 min)
5. Métricas y siguiente mes (10 min)

## Recursos

- **Manual completo del agente**: `specs/ai-agent-spec.md` en el repo del proyecto
- **Glossary de términos**: `docs/glossary.md` en el repo
- **Operador**: [nombre / contacto]
- **Ayuda con Odoo**: documentación de Odoo Knowledge

## Cambios a este manual

Este manual lo mantiene **el operador** del proyecto. Si necesitas que cambie 
algo, avísale. Cualquier cambio se documenta en el repo Git.

Versión actual: 1.0 (2026-05-24)
