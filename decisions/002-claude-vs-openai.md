# ADR 002: Claude (Anthropic) como LLM primario

**Fecha**: 2026-05-23
**Estado**: Aceptado
**Decisores**: Equipo Mozaprint

## Contexto

Necesitamos un proveedor de LLM para el agente conversacional, generación de descripciones, lead scoring y análisis de documentos. Las opciones evaluadas:

1. OpenAI (GPT-4o, GPT-4o-mini)
2. Anthropic Claude (Haiku 4.5, Sonnet 4.6)
3. Google Gemini

## Decisión

Vamos con **Claude (Anthropic API)** como proveedor primario:
- **Haiku 4.5** para conversación general y FAQ
- **Sonnet 4.6** para tool use complejo en cotizaciones y análisis de PDFs

## Razones

1. **El equipo ya usa Claude Pro y conoce su estilo de razonamiento**: facilita iterar prompts.
2. **Mejor desempeño en tool use multi-step**: el flujo de cotización requiere encadenar 5-8 tool calls. Claude maneja esto con más consistencia que GPT-4o-mini.
3. **Prompt caching nativo con 90% off**: el system prompt es ~3000 tokens (knowledge base + reglas). Con caching es trivial.
4. **Costo aceptable**: a volumen Mozaprint (~200 leads/mes), el delta vs OpenAI es ~$30-80 USD/mes. Justificable.
5. **Claude Code workflow**: el ejecutor usa Claude Code. Tener el mismo provider en producción simplifica desarrollo y debugging.
6. **Mejor manejo de instrucciones complejas**: el system prompt tiene reglas anidadas (cuándo escalar, qué nunca decir, etc.). Claude las respeta mejor.

## Alternativas descartadas

### OpenAI GPT-4o-mini
- Pros: nativo en Odoo, más barato, ecosistema mayor
- Contras: razonamiento en tool use multi-step menos consistente, less reliable cuando hay reglas anidadas complejas
- Veredicto: backup secundario, no primario

### Google Gemini
- Pros: tier gratuito generoso, nativo en Odoo
- Contras: calidad inferior para B2B en español MX, manejo de tool use menos maduro
- Veredicto: no recomendado para contexto cliente pagante

## Implicaciones técnicas

### Sin soporte nativo en Odoo 19
Odoo 19 base soporta OpenAI y Gemini nativamente, pero NO Claude. Implicaciones:
- Para el AI Agent en livechat web de Odoo: usar módulo del marketplace (ej. `viavista_ai_claude`)
- Verificar compatibilidad del módulo con Odoo Online (no todos son)
- Si no es compatible: usar OpenAI en el AI Agent nativo de Odoo, Claude vía n8n para WhatsApp
- Para el bridge custom (lo más importante): Claude se llama directo desde n8n con HTTP node, sin necesidad de módulo Odoo

### Estimación de costos

Asumiendo:
- 200 leads/mes vía WhatsApp
- 5 turnos promedio por conversación
- System prompt cacheado (~3000 tokens, 90% off después de primer hit)
- Mensajes promedio: 50 tokens input, 100 tokens output

**Sin caching** (peor caso):
- 200 × 5 × (3050 input + 100 output) = 3.05M input + 100K output mensual
- Haiku 4.5: $3.05 × $1.00 + $0.10 × $5.00 = $3.55/mes
- Sonnet 4.6: $3.05 × $3.00 + $0.10 × $15.00 = $10.65/mes

**Con caching** (caso real):
- Primer turno por conversación: full prompt → ~$0.005
- Turnos 2-5: prompt cacheado → ~$0.0005 cada uno
- Por conversación: $0.005 + 4 × $0.0005 = $0.007
- Mensual: 200 × $0.007 = $1.40 USD con Haiku
- Con Sonnet: ~$4.20 USD

**Más volumen anticipado** (generación de descripciones, lead scoring, análisis de PDFs):
- ~$10-30 USD/mes adicional
- Total: $15-50 USD/mes

## Tareas derivadas

- [ ] Crear cuenta Anthropic API y generar key
- [ ] Configurar billing limit a $200/mes inicial como salvaguarda
- [ ] Setup credenciales en n8n
- [ ] Decidir si instalar módulo Claude en Odoo (verificar compat Online) o usar OpenAI para AI Agent nativo de livechat
- [ ] Implementar prompt caching en todas las llamadas a Claude
- [ ] Monitoreo de gasto mensual con alertas

## Reversibilidad

Si después de 3 meses Claude no resulta como esperamos:
- Cambiar provider en n8n es solo cambiar credentials y modelo en HTTP node
- Los prompts mismos son portables a OpenAI con ajustes menores
- Costo de switching: ~1 día de re-tuning de prompts

## Referencias

- Anthropic pricing 2026: https://www.anthropic.com/pricing
- Prompt caching docs: https://docs.anthropic.com/claude/docs/prompt-caching
- Comparativa benchmark tool use multi-step: [añadir cuando esté el dato]
