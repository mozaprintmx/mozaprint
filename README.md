# Mozaprint — Paquete de contexto para Claude Code

> Este paquete contiene todo el contexto que Claude Code necesita para trabajar en el proyecto Mozaprint. Está diseñado para clonarse como repo y usarse desde Claude Code en la terminal.

## Qué hay aquí

```
mozaprint-context/
├── CLAUDE.md                    ← Archivo principal, se carga auto en cada sesión
├── README.md                    ← Este archivo
│
├── docs/                        ← Documentación viva del proyecto
│   ├── architecture.md          ← Diagrama y responsabilidades
│   ├── glossary.md              ← Términos del negocio
│   ├── roadmap.md               ← Qué está hecho, qué falta
│   ├── changelog.md             ← Historial de cambios técnicos
│   └── upgrades/                ← Actualizaciones de Odoo: checklist e incidencias
│       ├── README.md            ← Índice, estado por base y los dos comandos
│       ├── checklist-post-upgrade.md  ← Qué revisar tras cada actualización
│       ├── motor-cotizacion.md  ← Procedimiento específico del motor
│       └── incidencias/         ← Un archivo por fallo real, con causa y reparación
│
├── specs/                       ← Especificaciones técnicas estables
│   ├── data-model.md            ← Modelos custom de Odoo
│   ├── integrations.md          ← APIs externas
│   ├── ai-agent-spec.md         ← Identidad, prompts, tools del agente Moza
│   ├── personalizacion-nativa.md ← Reemplazo del motor: productos + listas de precios
│   └── api-shapes.md            ← Shapes de payloads JSON
│
├── decisions/                   ← Architecture Decision Records (ADRs)
│   ├── 001-n8n-self-hosted.md
│   ├── 002-claude-vs-openai.md
│   ├── 003-coexistence-whatsapp.md
│   └── ...
│
├── scripts/                     ← Scripts ejecutables (Python) sobre JSON-2
│   ├── odoo_client.py           ← Cliente JSON-2 compartido (paginación)
│   ├── audit_catalog.py         ← Auditoría de catálogo (solo lectura)
│   ├── audit_atributos.py       ← Auditoría de atributos /shop (solo lectura)
│   ├── audit_tags.py            ← Auditoría de product tags (solo lectura)
│   ├── audit_post_upgrade.py    ← Salud tras una actualización de Odoo (solo lectura)
│   ├── fix_vista_terminos_producto.py ← Repara la ficha de producto tras el salto a 19.2
│   ├── fix_vista_contactanos.py ← Repara /contactanos tras el salto a 19.3 (aborta en 19.2)
│   ├── deploy_reporte_cotizacion.py ← Columna de imagen del PDF, en vistas propias (idempotente)
│   ├── audit_lineas_facturables.py ← Código de Studio que Odoo COBRA por cada 100 líneas
│   ├── cleanup_tags.py         ← Borrado por reglas de product tags (lista blanca)
│   ├── dump_tecnica_values.py   ← Volcado de valores de x_tecnica_impresion
│   ├── dump_color_values.py     ← Volcado de valores del atributo Color (solo lectura)
│   ├── seed_tecnicas.py         ← Carga el seed de técnicas (idempotente)
│   ├── seed_costos.py          ← Carga costos de personalización (idempotente)
│   ├── mapa_servicios_personalizacion.py ← Matriz de costos → diseño nativo (solo lectura)
│   ├── derive_tecnicas.py       ← Deriva técnica canónica raw→modelo
│   ├── colores_engine.py        ← Motor de color compartido (normalize/resolve/familia)
│   ├── derive_colores.py        ← Deriva swatches html_color del atributo Color
│   ├── derive_color_familia.py  ← Deriva atributo no_variant "Color (familia)" (revertido)
│   ├── rollback_color_familia.py ← Rollback seguro de "Color (familia)"
│   ├── optimize_category_images.py  ← Optimiza image_1920 de categorías (peso de /shop)
│   ├── rollback_category_images.py  ← Rollback de imágenes desde backups/
│   ├── backup_catalog.py        ← Backup del catálogo antes de sync masivo
│   ├── dns_audit.py             ← Auditoría DNS
│   ├── anonymize_whatsapp.py    ← Anonimiza exports de WhatsApp
│   └── test_server_action.py    ← Prueba local de Server Actions
│
├── data/                        ← Datos seed versionados
│   ├── tecnicas_seed.csv        ← 20 técnicas de personalización (seed)
│   ├── tecnicas_seed.md         ← Procedencia y reglas de limpieza del seed
│   ├── colores_seed.csv         ← Colores curados (base + lex, con familia) para swatches
│   ├── colores_modifiers.csv    ← Modificadores HLS (claro/oscuro/pastel/…)
│   ├── colores_familias.csv     ← 14 familias de color para filtro de /shop
│   └── colores_noncolor.md      ← STRIP/NON_COLOR/MATERIAL + familias + contaminación
│
├── n8n-workflows/               ← Workflows exportados como JSON
│   ├── ai-agent-respond.json
│   ├── lead-intake-whatsapp.json
│   ├── sync-proveedor-promo-opcion.json
│   └── ...
│
├── odoo-extensions/             ← Configuraciones Studio + Server Actions
│   ├── studio-fields.yaml
│   ├── automation-rules.yaml
│   └── server-actions/
│       ├── ai_handle_whatsapp_message.py
│       └── create_quote_with_personalization.py
│
└── test/                        ← Datos de prueba y test cases
    ├── conversations/
    ├── products/
    └── leads/
```

## Cómo usar con Claude Code

### Setup inicial (una sola vez)

```bash
# 1. Tener Claude Code instalado
npm install -g @anthropic-ai/claude-code

# 2. Clonar este repo
git clone <url> mozaprint
cd mozaprint

# 3. Iniciar Claude Code en el directorio
claude

# 4. (Opcional) ejecutar /init para que Claude analice el repo y proponga refinamientos a CLAUDE.md
```

A partir de aquí, **cada vez que arrancas `claude` en este directorio**, automáticamente lee `CLAUDE.md` y los archivos referenciados con `@docs/...`. No tienes que recordarle nada.

### Workflow de trabajo recomendado

#### Para implementar un feature nuevo

1. **Investigar primero, codear después**:
   ```
   > Lee la spec del feature X en specs/ y dime qué falta, qué dudas tienes,
     y propón un plan de implementación antes de tocar código
   ```

2. **Pedir plan explícito**:
   ```
   > Antes de implementar, dame el plan en pasos. No empieces a codear todavía.
   ```

3. **Implementar paso por paso**:
   ```
   > OK, empecemos por el paso 1. Implementa solo eso y vamos validando.
   ```

4. **Validar antes de avanzar**:
   ```
   > Antes de seguir, corre los tests de esa parte y revisa que no
     rompimos lo que ya funciona
   ```

#### Para debuggear

```
> Algo está mal con el flujo de cotización: el AI no agrega la línea de personalización.
  Lee specs/ai-agent-spec.md y revisa el server action en
  odoo-extensions/server-actions/ai_handle_whatsapp_message.py.
  ¿Dónde podría estar fallando?
```

#### Para revisar código antes de desplegar

```
> Hice estos cambios manualmente en Odoo. Aquí está la diff conceptual: [...]
  ¿Detectas algún riesgo? ¿Se rompe algo en el flujo?
```

#### Para mantener documentación viva

```
> Acabamos de cambiar X. Actualiza docs/changelog.md con una entrada hoy
  y si afecta el modelo de datos, también specs/data-model.md
```

### Comandos Claude Code que vale la pena conocer

| Comando | Para qué |
|---|---|
| `/init` | Genera CLAUDE.md inicial analizando el repo |
| `/memory` | Muestra qué archivos de contexto están cargados |
| `/compact` | Comprime el historial cuando se llena el contexto |
| `/clear` | Limpia el chat actual, mantiene CLAUDE.md |
| `/rewind` | Vuelve a un checkpoint anterior de la conversación |

### Buenas prácticas específicas para este proyecto

1. **Una decisión grande = un ADR**. Si proponemos algo arquitectónico, crear archivo en `decisions/` con número incremental, contexto, opciones, decisión y consecuencias.

2. **Specs son contratos**. Si cambias un campo en `specs/data-model.md`, ese cambio debe propagarse a:
   - El modelo Studio en Odoo
   - Cualquier workflow de n8n que lo use
   - Las tools del agente AI si lo consumen

3. **Workflows de n8n versionados como código**. Exportar JSON cada vez que se haga cambio relevante. Commit al repo. Si se rompe algo, se puede restaurar.

4. **Server Actions de Odoo también versionados**. Aunque viven dentro de Odoo, mantener copia en `odoo-extensions/server-actions/` para tracking de cambios.

5. **Tests de regresión obligatorios** para:
   - Cualquier cálculo de cotización (afecta dinero)
   - Cualquier llamada al AI (afecta UX cliente)
   - Cualquier sync de proveedor (afecta catálogo)

## Cómo extender este paquete

Si introduces un nuevo componente al sistema:

### Es un proveedor nuevo
1. Agregar entrada en `specs/integrations.md` sección proveedores
2. Crear workflow en `n8n-workflows/sync-proveedor-{nombre}.json`
3. Agregar credentials necesarias a la lista de env vars en `docs/architecture.md`
4. Crear ADR en `decisions/` si la integración tiene decisiones no obvias

### Es un nuevo modelo de datos
1. Documentar en `specs/data-model.md`
2. Si tiene relaciones con modelos existentes, dibujar en la sección "Relaciones"
3. Si requiere migración de datos, agregar script en `scripts/`

### Es un nuevo flujo del agente
1. Documentar en `specs/ai-agent-spec.md`
2. Si requiere tool nuevo, especificarlo con signature y comportamiento
3. Si requiere prompt nuevo, agregarlo a la sección de prompts
4. Probar con casos en `test/conversations/`

### Es una decisión técnica nueva
1. Crear ADR en `decisions/NNN-titulo.md` con la plantilla estándar
2. Linkear desde `docs/architecture.md` si afecta arquitectura
3. Mencionar en `docs/changelog.md`

## Cómo compartir cambios con el equipo

Aunque solo una persona implementa, las decisiones son de 3 personas. Workflow:

1. Claude Code propone cambio (con ADR si aplica)
2. El ejecutor revisa, ajusta
3. Commit a una rama `proposal/{nombre}`
4. Compartir la rama con el equipo (link al repo o PR)
5. Equipo revisa, comenta
6. Aprobado → merge a `main` y se ejecuta el cambio en Odoo / n8n

## Seguridad

- **NUNCA commitear**: API keys, tokens, datos de clientes reales, exports completos de WhatsApp
- `.gitignore` ya excluye: `secrets/`, `.env`, `*.key`, `whatsapp-exports/`
- Para datos de prueba en `test/`, usar datos anonimizados/sintéticos solamente

## Mantenimiento

Cada trimestre, revisar:
- ¿CLAUDE.md sigue siendo conciso (<500 líneas)?
- ¿Algún spec quedó desactualizado vs realidad en Odoo?
- ¿Algún ADR quedó superseded? Marcarlo
- ¿Hay workflows en n8n que no estén versionados aquí?
- ¿Se coló código que Odoo factura? Cobra **cada 100 líneas** de Server Actions con
  código y campos calculados (solo lectura):
  ```bash
  python scripts/audit_lineas_facturables.py --target prod
  ```
  Producción debe salir en **0 bloques**. El motor de cotización se retiró por esto
  el 2026-08-17 — ver `decisions/007-retiro-motor-cotizacion-costo-codigo.md`.
- ¿El sitio web y las vistas sobrevivieron la última actualización? (solo lectura):
  ```bash
  python scripts/audit_post_upgrade.py --target prod
  ```
- ¿El PDF de cotización sigue con su columna de imagen y las columnas cuadradas?
  (solo lectura):
  ```bash
  python scripts/deploy_reporte_cotizacion.py --target prod --verificar
  ```
  Apartado completo de actualizaciones — checklist, incidencias y reparaciones:
  `docs/upgrades/README.md`.

## Siguiente paso si llegas nuevo al proyecto

1. Leer este README completo
2. Leer `CLAUDE.md`
3. Leer `docs/architecture.md` y `docs/glossary.md`
4. Hojear `specs/data-model.md` para entender qué modelos tocamos
5. Revisar `decisions/` para entender por qué el stack es como es
6. Empezar a trabajar

---

## Historial de cambios

Ver `docs/changelog.md` — entradas fechadas por versión (la fuente de verdad del
historial técnico). El estado actual por fases vive en `docs/roadmap.md` y el
resumen de arranque rápido en `docs/punto-de-control.md`.
