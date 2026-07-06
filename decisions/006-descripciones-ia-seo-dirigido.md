# ADR 006: Descripciones con IA — descope de Fase 2, reencuadre como SEO dirigido (Fase 9)

**Fecha**: 2026-07-06
**Estado**: Aceptado
**Decisores**: Equipo Mozaprint

## Contexto

Fase 2 incluía "Generar descripciones de producto con AI Fields" como generación
**masiva** de texto. Al revisar la Tarea 2 apareció una señal de negocio que cambia
el análisis:

- **Patrón de adquisición real**: una parte de los clientes que llegan a Mozaprint
  venían buscando un producto que estaba **AGOTADO** en otro revendedor.
- Mozaprint revende el catálogo de los mismos proveedores (INN / 4P / PO), así que
  publica la **MISMA descripción duplicada** que esos competidores.
- Efecto SEO: ante contenido duplicado, Google elige una URL canónica y
  **deprioritiza** las demás — es decir, deprioritiza las fichas de Mozaprint justo
  en el escenario que hoy trae clientes.
- **Matiz clave**: hoy probablemente nos encuentran por **nombre / SKU** (title/H1),
  no por el cuerpo de la descripción. Por eso reescribir el *body prose* NO es la
  palanca de mayor leverage; hacerlo masivo sería caro y de bajo retorno.

## Decisión

1. **Descartar de Fase 2** la generación **masiva** de descripciones con IA. No se
   hace ahora y **no bloquea** el cierre de Fase 2.
2. **No matar la idea**: reencuadrarla como iniciativa **dirigida** (targeted) dentro
   de **Fase 9 (SEO)**, y **condicionarla a un diagnóstico previo de GSC** (abajo).

## Prioridad de palancas SEO (Fase 9, en este orden)

1. `title` / meta description / H1 **únicos** por producto — mayor leverage, ataca el
   duplicado donde hoy sí nos rankean (nombre/SKU).
2. **Productos alternativos / accesorios** para *linking interno* — automatiza la
   retención manual de "te consigo un similar disponible"; conecta con la Tarea 3 de
   Fase 2 (optional/accessory products).
3. **schema.org/Product** + Open Graph (rich results + share en WhatsApp).
4. **Descripciones únicas DIRIGIDAS** (top productos / categorías ancla), **no
   masivas** — solo si el diagnóstico GSC lo justifica.

## Diagnóstico previo (condición para pasar de "targeted" a "hacer")

En Google Search Console → Performance, filtrado a URLs de producto:

- Impresiones totales vs por página.
- **Posición media** (rango 15-30 ≈ señal de filtrado por duplicado).
- Si las *queries* son **nombre/SKU** (nos encuentran por identificador) vs
  **genéricas** (nos encuentran por categoría/atributos, donde el body sí ayudaría).

El resultado decide si las descripciones dirigidas valen la pena y sobre qué páginas.

## Diseño si se implementa (nota para cuando toque)

- **Conservar SIEMPRE la tabla de specs** (dato estructurado) en la ficha.
- La **descripción única va PRIMERO y prominente**; el texto del proveedor queda
  secundario o recortado.
- Diseñarla como **superficie de RETENCIÓN**, no relleno de keywords: reaseguro de
  disponibilidad, productos similares, personalización + gestión integral, y CTA a
  cotización.
- **Anclada estrictamente a campos estructurados** (`name`, `categ`, `x_material`,
  `x_capacidad`, `x_medidas`, técnica) para evitar que la IA **alucine specs**.
- **Convivencia con el sync** = mismo patrón raw/derivado que la técnica:
  - el sync escribe el crudo del proveedor en `x_studio_descripcion_proveedor`;
  - la descripción única vive en `description_ecommerce`, **protegida por un flag**
    `x_studio_desc_ai_generada` para que el sync **no la pise** en cada corrida.
  - (Ambos campos son de diseño futuro; NO existen aún.)

## Consecuencias

### Positivas
- Fase 2 puede cerrar sin una tarea cara de bajo retorno inmediato.
- El esfuerzo SEO se enfoca en la palanca real (identificadores + linking interno).
- Si se hace, se hace con datos (GSC) y con un diseño que protege la inversión del sync.

### Negativas / trade-offs
- Se posterga un posible beneficio SEO del contenido único (aceptable: hoy no es la
  palanca dominante).
- Requiere el diagnóstico GSC antes de decidir, lo que añade un paso.

## Referencias
- `docs/roadmap.md` (Fase 2 tarea descartada; Fase 9 palancas + diagnóstico GSC)
- `docs/changelog.md` (entrada v18, 2026-07-06)
