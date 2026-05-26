# Cómo trabajar con Claude Code en este proyecto

> Guía paso a paso para que el operador inicie y mantenga el flujo de desarrollo con Claude Code.

## Setup inicial (una sola vez)

### 1. Instalar Claude Code

```bash
# Requiere Node.js 18+
npm install -g @anthropic-ai/claude-code

# Verificar
claude --version
```

### 2. Autenticar

```bash
claude auth
```

Esto abre el navegador para login con cuenta Anthropic. Usa la misma cuenta donde tienes el plan que prefieras (Pro, Max o créditos de API).

### 3. Clonar este repo como base del proyecto

```bash
cd ~/projects  # o donde guardes tus proyectos
git clone <url-del-repo> mozaprint
cd mozaprint
```

### 4. Verificar estructura

```bash
ls -la
# Debes ver: CLAUDE.md, README.md, docs/, specs/, decisions/, etc.
```

### 5. Crear CLAUDE.local.md (preferencias personales)

```bash
cp CLAUDE.local.md.template CLAUDE.local.md
# Edita con tus preferencias
```

### 6. Configurar variables de entorno locales

```bash
cp .env.template .env  # si existe; si no, créalo
# Llenar con tus API keys de desarrollo
chmod 600 .env
```

## Flujo de trabajo típico

### Empezar una sesión

```bash
cd ~/projects/mozaprint
claude
```

Claude Code automáticamente:
- Lee `CLAUDE.md` (contexto del proyecto)
- Lee `CLAUDE.local.md` (tus preferencias)
- Carga archivos referenciados con `@docs/...` en el CLAUDE.md

Verifica con:
```
/memory
```

Te muestra qué archivos están cargados.

### Implementar una tarea

**❌ Mal**: 
```
> implementa el agente de WhatsApp
```

**✓ Bien** (workflow estructurado):

```
> Lee specs/ai-agent-spec.md y odoo-extensions/server-actions/ai_handle_whatsapp_message.py.
> 
> Necesito implementar el tool 'search_product' como workflow de n8n. 
> Antes de codear, dame:
> 1. Análisis de lo que el tool necesita hacer según el spec
> 2. Lista de nodos n8n que usarías
> 3. Pseudocódigo de la lógica
> 4. Errores potenciales y cómo manejarlos
> 
> Espera mi aprobación antes de generar el JSON del workflow.
```

Claude propone plan → tú revisas → autorizas → Claude implementa.

### Cuando Claude te entregue código

Siempre revisa antes de aplicar:

1. **¿Hace lo que pedí?**
2. **¿Sigue las convenciones del proyecto?** (CLAUDE.md)
3. **¿Funciona con los datos reales?** (no asume estructuras)
4. **¿Maneja errores?**
5. **¿Está testeado o testeable?**

Si todo OK:
```
> Aplico esto manualmente en n8n / Odoo. ¿Algo más que deba 
> documentar antes? Actualiza el changelog.
```

### Documentar después de cada cambio

```
> Acabamos de implementar X. 
> 1. Actualiza docs/changelog.md con la entrada
> 2. Si cambió algún campo, actualiza specs/data-model.md
> 3. Si cambió un workflow, exporta el JSON actualizado
```

### Tomar decisiones técnicas grandes

Si vas a hacer una elección arquitectónica:
```
> Estoy decidiendo entre A y B para X. 
> Lee decisions/ y arma un ADR comparativo en formato del proyecto.
> No implementes nada, solo el doc para discutir.
```

Después de discutir con el equipo:
```
> El equipo decidió B. Actualiza el ADR a estado 'Aceptado' y arma 
> las tareas derivadas.
```

## Comandos útiles de Claude Code

| Comando | Propósito |
|---|---|
| `/init` | Genera CLAUDE.md inicial (ya lo hicimos) |
| `/memory` | Muestra archivos cargados en contexto |
| `/compact` | Comprime historia cuando se llena el contexto |
| `/compact <instrucciones>` | Compacta enfocándose en algo específico |
| `/clear` | Limpia chat, mantiene CLAUDE.md |
| `/rewind` | Vuelve a un checkpoint anterior |
| Esc Esc | Acceso rápido a /rewind |
| `/exit` | Salir |

## Patrones que funcionan bien

### Patrón 1: Investigación primero, código después

```
> Antes de implementar nada, lee X, Y, Z y dime:
> - Qué entiendes del requerimiento
> - Qué dudas tienes
> - Qué propones
> 
> Si todo claro, te doy luz verde.
```

### Patrón 2: Una tarea atómica a la vez

❌ "Implementa todos los tools del agente"
✓ "Implementa solo search_product. Cuando termine y valide, seguimos con get_product_details."

### Patrón 3: Validar contra el spec

```
> Implementa lo que pide specs/ai-agent-spec.md sección 'tool search_product'. 
> Compara tu implementación contra ese spec al final y dime qué quedó 
> distinto y por qué.
```

### Patrón 4: Tests primero cuando es código de negocio

```
> Antes de implementar el cálculo de descuentos, escribe los casos de test:
> - Cliente con orden de $2,500 → sin descuento
> - Cliente con orden de $5,000 → 10% de descuento
> - Cliente con orden de $5,000 + IVA = $5,800 → ¿aplica o no según config?
> 
> Después implementa el cálculo y corre los tests.
```

### Patrón 5: Refactor con red de seguridad

```
> Vamos a refactorizar el script de sync de proveedor.
> 1. Snapshot del comportamiento actual: corre los tests existentes y captura resultados
> 2. Refactor
> 3. Vuelve a correr los tests y compara contra el snapshot
> 4. Si difiere, dime exactamente dónde y por qué
```

## Anti-patrones que NO funcionan

### ❌ Pedir cosas grandes y vagas
"Mejora el sistema" → Claude no sabe qué priorizar.

### ❌ Saltarse el spec
Si no hay spec, primero pedir que Claude lo escriba, luego implementar.

### ❌ Aplicar código sin revisar
Aunque Claude sea bueno, siempre hay matices del entorno real que no conoce.

### ❌ No documentar cambios
El proyecto se vuelve un misterio para el próximo (que puede ser Claude en otra sesión, o tú en 3 meses).

### ❌ Iterar sin commit
Si Claude itera 5 veces sobre un archivo y no commiteas en medio, perder el avance es muy fácil.

## Cuándo NO usar Claude Code

- **Tareas de UI clicable en Odoo**: configurar Studio fields, Automation Rules, programas de Loyalty → más rápido en la UI
- **Tareas de configuración de Meta Business Manager**: requiere browser
- **Tareas de configuración VPS**: SSH directo, no requiere Claude
- **Test manual end-to-end**: alguien debe escribir mensajes de WA reales

## Cuándo SÍ es genial

- **Escribir Server Actions de Odoo**: Claude maneja el sandbox sintaxis bien
- **Construir workflows de n8n**: JSON denso que Claude genera limpio
- **Refactor de scripts existentes**: dale el código + el objetivo, propone refactor
- **Generar tests**: dale función + casos esperados, escribe los tests
- **Actualizar documentación**: el changelog, los specs, los ADRs
- **Análisis de logs/datos**: dale un dump y pídele patrones
- **Generación de plantillas**: emails, plantillas WhatsApp, copy del agente IA

## Costos esperados

Si usas la API de Claude para Claude Code (no Pro/Max):

- **Desarrollo del proyecto Mozaprint** (semanas 1-3): ~$30-80 USD total
- **Mantenimiento mensual** (cambios y refactors menores): ~$10-30 USD/mes
- **Pico**: si hay sprint pesado de implementación, puede ser $50/semana

Si tienes Claude Pro/Max, el uso de Claude Code está incluido hasta cierto límite.

## Lo que NO debes hacer

- **No commitear datos reales** (clientes, conversaciones reales)
- **No commitear `.env` ni API keys** (`.gitignore` ya lo previene)
- **No pasar conversaciones de WA con PII a Claude** sin anonimizar (usa `scripts/anonymize_whatsapp.py`)
- **No darle a Claude la API key de producción de Odoo en context** (usa env vars, no copia/pega)

## Mantenimiento del paquete

Cada trimestre:
- ¿CLAUDE.md sigue siendo conciso? Limpiar si crece >500 líneas
- ¿Algún spec quedó desactualizado vs Odoo real? Reconciliar
- ¿Algún ADR fue revertido? Marcar como "Superseded"
- ¿Hay workflows en n8n no exportados aquí? Exportar
- ¿El changelog está al día? Actualizar entradas faltantes

## Soporte y siguiente paso

Si tienes duda específica:
1. Buscar en `docs/`, `specs/`, `decisions/`
2. Si no está documentado, preguntar a Claude Code (es probable que sepa generalidades de Odoo/n8n/Anthropic)
3. Si tampoco aparece, ir a docs oficiales (linkeadas en cada spec)

**Próximo paso recomendado al iniciar este proyecto**: empezar con la Fase 0 (DNS, API keys). Mientras tanto, en una sesión de Claude Code, leer todo el paquete y discutir el plan de la Fase 1.
