# ADR 011 — El sync de proveedores se rediseña: v3 en Python, con plan, guardas y dueños por campo

**Fecha**: 2026-10-01 · **Estado**: aceptada (diseño). La construcción sigue en la Fase 8.

## Contexto

El sync mantiene en Odoo el catálogo, los precios y las existencias de los tres proveedores (Promo
Opción, 4Promotional e Innovation Line): unos 5,270 productos y 12,800 variantes. Es un paquete
Python de ~4,700 líneas que corre en la PC de operación con Task Scheduler, por XML-RPC. Hasta
septiembre de 2026 no tenía control de versiones.

En septiembre de 2026 se auditó completo: cada función de la v2 quedó asignada a una acción
documentada, y cada hallazgo se verificó con logs, respaldos o lecturas de producción. Hubo 17
hallazgos. Los que más pesan para el negocio:

| Problema | Efecto visible |
|---|---|
| El sync reconoce los productos **por nombre** | Un producto que regresa o se renombra crea una ficha nueva: duplicados, URL nueva, historial partido |
| Reescribe descripciones, categorías y más **cada vez** que procesa un producto | Toda edición manual (incluido el trabajo de SEO de la Fase 9) se pierde sin aviso |
| Convierte en **cero** un dato que el proveedor no manda | «Pocas piezas» falso en 1,438 productos cuando un proveedor dejó de informar existencias |
| Decide la publicación **color por color** | Productos con colores mixtos se ocultaban y volvían a aparecer; 53 quedaron ocultos |
| Trabajo repetido cada día (imágenes descargadas de nuevo, existencias peleadas entre colores) | Corridas de horas; una se cortó a las 2 h sin aviso |
| Fallas en silencio | La derivación de técnicas estuvo caída un mes sin que nada lo dijera |

El roadmap preveía migrar el sync a n8n.

## Lo que se evaluó

| Opción | Veredicto |
|---|---|
| **A.** Migrar a workflows de n8n | Descartada: n8n no está aprovisionado (ADR 008 llevó el webhook a Odoo). La lógica es pesada (imágenes, lecturas en lote, comparación por campo) y en n8n sería difícil de probar con un golden master |
| **B.** Server Actions de Odoo | Descartada: el sandbox no permite HTTP saliente ni librerías, y cada línea se factura (ADR 007) |
| **C.** Seguir parchando la v2 | Descartada como camino principal: los problemas vienen del diseño (identidad por nombre, escritura sin dueño, sin plan). Se aceptaron solo **excepciones** urgentes y acotadas (abajo) |
| **D.** Reescribir en Python, en paralelo y con corte gradual | **Elegida** |

## Decisión

1. **La v3 es Python en la misma PC**, con Task Scheduler. Se construye en paralelo y reemplaza a la
   v2 proveedor por proveedor; mientras tanto la v2 sigue corriendo.
2. **Vive en un repo privado** (`mozaprint-sync`). El detalle del sync (endpoints, autenticación,
   lógica por proveedor y horarios) no se publica; este repo guarda solo decisiones y cambios
   visibles.
3. **Odoo por JSON-2**, con una llave propia de un usuario técnico y no la cuenta personal de
   operación. La llave tiene fecha de caducidad registrada y aviso previo.
4. **Planear antes de aplicar**: cada corrida arma un plan de lo que cambiaría, lo pasa por unas
   guardas, aplica lo seguro, retiene lo riesgoso y reporta siempre.
5. **Cada campo tiene dueño**:
   - el SEO del sitio y el bloque de contenido de la ficha son de la persona; el sync nunca los toca;
   - nombre, descripción e imágenes los actualiza el sync **solo si nadie los editó**; si alguien
     los editó y el proveedor cambió los suyos, no los pisa y avisa;
   - de las categorías de la tienda, el sync mueve solo la que él puso.
6. **Los productos se reconocen por el código del proveedor**, incluidos los archivados. Un producto
   que regresa se reactiva y conserva su ficha y su URL. Un renombre dudoso espera confirmación.
7. **«Sin dato» no es «cero»**: si un proveedor no informa algo, la tienda no muestra nada en vez
   de un dato falso. «Pocas piezas» se muestra **solo con el listón**, que se recalcula varias veces
   al día; ya no hay aviso dentro de la descripción.
8. **Reporte**: un correo diario que llega siempre, aunque todo salga bien (si no llega, es la
   alarma), y un correo inmediato ante una falla o un plan que espera aprobación.

### Política de aprobación del sync

El `CLAUDE.md` pide aprobación humana para cambios masivos de catálogo (más de 10 productos).
Para el sync, esa regla se aterriza así:

- **Se aplica solo** (y se reporta):
  - existencias y listón;
  - precios que cambian hasta ±30 % por producto;
  - contenido del proveedor que nadie editó;
  - hasta 20 altas y 10 bajas por proveedor y corrida.
- **Espera aprobación**:
  - precios que cambian más de 30 %;
  - más de 20 altas o 10 bajas;
  - contenido de más de 100 productos en una corrida;
  - un catálogo que llega incompleto (falta más del 10 %);
  - los renombres dudosos.

Todos los umbrales son configurables. Con datos de 30 días, la regla literal habría generado
pendientes varias veces por semana por precios de rutina.

## Excepciones aplicadas a la v2 mientras se construye la v3

| Fecha | Qué | Alcance |
|---|---|---|
| 2026-09-30 | Un dato faltante de existencias deja de leerse como cero; la publicación se decide una vez por producto | 1,438 listones y avisos falsos quitados; 53 productos republicados |
| 2026-09-30 | Las existencias de un proveedor vuelven, ahora por el método que el proveedor indicó | Listón «Pocas piezas» con datos reales en 58 productos |
| 2026-10-01 | «Pocas piezas» solo con el listón | 684 avisos quitados de las descripciones |
| 2026-09-30 | Derivación de técnicas restablecida con llave nueva | 420 plantillas al día |

Cada una se aplicó con respaldo previo, simulacro, plantilla de prueba y reversa.

## Consecuencias

**Se gana**:
- las ediciones manuales y el SEO dejan de perderse;
- no más duplicados por nombre;
- la tienda deja de mostrar datos inventados;
- los cambios grandes o raros esperan revisión;
- el silencio deja de significar «todo bien»;
- cada regla tiene una prueba automática.

**Se pierde o queda pendiente**:
- dos bases de código conviven hasta el corte;
- el sync sigue dependiendo de una PC encendida;
- hay que crear una base de test nueva antes del corte;
- la migración de identidad (asignar el código del proveedor a ~5,270 productos y limpiar
  duplicados) es un cambio masivo que requiere su propia aprobación;
- el botón «Consultar inventario» de la ficha sigue dependiendo de las etiquetas PO/4P y del
  formato de SKU: su rediseño sigue como tarea aparte de la Fase 8.
