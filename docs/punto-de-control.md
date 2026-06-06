# Punto de Control — Proyecto Mozaprint MX

> Documento de migración. Resume el estado completo del proyecto al momento de
> cambiar de cuenta de Claude (personal → cuenta Mozaprint Pro).
> Subir al knowledge del Proyecto nuevo para que Claude tenga contexto inmediato.
> Fuente de verdad detallada: repo github.com/mozaprintmx/mozaprint

---

## QUÉ ES EL PROYECTO

Optimización del ecosistema digital de **Mozaprint MX**: empresa de artículos
promocionales personalizados B2B en CDMX. Gestión integral: diseño,
personalización, asesoría de producto, hasta entrega.

**Objetivo**: automatizar actividades repetitivas para facilitar el trato con
el cliente, empezando por captura de leads y, eventualmente, un agente IA de
WhatsApp que atienda y cotice.

## STACK TÉCNICO

```
Odoo Online 19.0 Custom (mozaprintmx.com / mozaprintmx.odoo.com)
  - Sistema central: datos, CRM, ventas, catálogo, inventario, sitio web
  - Extensiones vía Studio (campos x_studio_), Automation Rules, Server Actions
  - Módulo IA nativo (tier incluido, sin API key propia necesaria)

n8n self-hosted en VPS (PLANEADO, espera aprobación de pago)
  - Será el orquestador / router único del webhook de WhatsApp
  - Conecta Odoo <-> Meta WhatsApp <-> LLM

LLM (Claude vs OpenAI — decisión en piloto, Fase 7)
  - Para el agente conversacional "Moza"

GitHub: github.com/mozaprintmx/mozaprint (PÚBLICO)
  - Todo el código, documentación y decisiones versionadas

Claude Code: herramienta principal de trabajo técnico (conectada al repo)
```

## QUIÉN ES EL USUARIO

- **Juan Carlos Asomoza Ponce**: ingeniero en computación, operador único,
  persona física con actividad empresarial.
- **Karina Asomoza**: Dirección de Marketing / Community Manager. Será dueña
  del knowledge base del agente. Maneja redes (cuenta mozaprintmx@gmail.com).
- **Rosy Ponce**: usuario administrativo de Odoo (reutilizado para API).
- **Manager de Finanzas**: aprobador de costos no parametrizados (rol futuro).

## ESTADO POR FASES

| Fase | Estado | Resumen |
|---|---|---|
| 0 - Fundamentos | ✅ Completa* | DNS, usuario API Odoo, entorno dev, Meta validado |
| 1 - Captura de leads | ✅ Completa | Formularios->CRM, campos custom, notificación, alertas |
| 2 - Precios y catálogo | 🔵 SIGUIENTE | Técnicas, descuentos, /shop |
| 3 - Motor de cotización | 🔴 Pendiente | Matriz de costos, parsear INN |
| 4 - Setup WhatsApp + n8n | 🔴 Bloqueada por VPS | App Meta, Coexistence, webhooks |
| 5 - Agente preparación | 🔴 Pendiente | KB, FAQs, tools 1-6, plantillas |
| 6 - Bridge producción | 🔴 Pendiente | Tools 7-12, Server Action, x_ai_mode |
| 7 - Piloto | 🔴 Pendiente | Off-hours, DECIDIR Claude vs OpenAI |
| 8 - Proveedores | 🔴 Pendiente | Migrar sync a n8n, JSON-2 |
| 9 - SEO + dashboard | 🔴 Pendiente | |
| 10 - Expansión agente | 🔴 Pendiente | 24/7, proactivo |

*Fase 0: solo falta desplegar VPS de n8n (espera aprobación de pago).
Fases 1-3 son Odoo puro, NO requieren n8n. Fases 4+ sí.

## LO QUE SE COMPLETÓ EN FASE 0

- **DNS**: Cloudflare authoritative (migrado para SEO), Hostinger solo email +
  registrar. Eliminado old.mozaprintmx.com. SPF reforzado a -all (estricto).
  DKIM de Hostinger confirmado (3 selectores). DMARC en p=none.
  ADVERTENCIA: SPF en -all estricto. Cuando Odoo envíe correo con servidor
  propio, agregar su include o serán rechazados.
- **Usuario API Odoo**: se reutiliza "Rosy Ponce" (rosy_ponce@mozaprintmx.com)
  con permisos REDUCIDOS por seguridad (de casi-admin a: Ventas Usuario,
  Inventario Usuario, Compras Usuario, Contabilidad Facturación, Productos Crear,
  Contacto Creación; quitado Banco). API key "n8n-produccion" generada (en
  gestor de secretos). Ruta futura: crear usuario integration@ dedicado al crecer.
- **Entorno dev**: Windows 10, Git, Node, VS Code, GitHub CLI, Claude Code, todo
  funcionando. Proyecto en D:\MozaPrint\Odoo\Proyectos\mozaprint.
- **Meta Business**: portfolio mozaprint_mx (Business ID 100794159106337).
  WABA "Moza Print" (ID 358071354051207) APROBADA. Número +52 1 56 3277 6277
  registrado, estado "Sin conexión" (falta conectar a Cloud API vía Coexistence).
  Verificación de negocio NO necesaria (Meta no la requiere para este caso).

## LO QUE SE COMPLETÓ EN FASE 1

### Campos custom en crm.lead (creados vía Studio, en producción)
La instancia FUERZA prefijo x_studio_ (no editable). Campos:
- x_studio_collected_qty (Integer) - cantidad
- x_studio_collected_producto (Text) - producto
- x_studio_collected_personalizacion (Selection: Sí/No/Aún no he decidido)
- x_studio_origen_form (Text) - clasificador origen
- x_studio_origen_url (Text) - URL exacta (PENDIENTE definir cómo se llena)

### Formularios web conectados al CRM
Los 3 formularios (/contactanos, /shop, ficha de producto) ahora crean LEADS
(no Oportunidades) en el CRM en vez de solo mandar correo. Mapeo de campos
estándar + custom. El campo Tipo oculto fija "Lead". Probados en producción.
ACLARACIÓN: conectar al CRM NO impide responder por correo; se puede tener ambos.

### Etapa "Leads" activada en CRM.

### Automation Rule de notificación
"Notificar nuevo lead de formulario web": al crear un lead con
x_studio_origen_form establecido, envía correo a info@mozaprintmx.com.
LECCIÓN: las variables en plantillas se insertan con comando /campo, NO escribir
{{ object.campo }} a mano (se guarda literal). El correo "Enviar como" debe ser
"Correo electrónico", no "Mensaje".

### 3 Alertas de seguimiento (Automation Rules basadas en tiempo)
1. Lead sin calificar 1 día -> actividad a Juan
2. Oportunidad en "Nuevo lead" 1 día -> actividad + etiqueta "Urge contactar"
3. Oportunidad en "Nuevo lead" 3 días -> actividad + etiqueta "Peligro, posible
   pérdida" + correo a mozaprintmx@gmail.com
Disparador por campo "Última actualización de etapa". Etiquetas acumulativas.
PENDIENTE: validar que se disparen en funcionamiento real (esperar cron).

### Pipeline limpiado.

### REGLA DE PROCESO CRÍTICA
Odoo NO está conectado al correo (se responde desde Gmail), así que Odoo solo
detecta actividad cuando el vendedor MUEVE la tarjeta en el pipeline. El equipo
DEBE mover las tarjetas al actuar, o las alertas darán falsos positivos. Esto se
elimina con el correo bidireccional o la integración WhatsApp.

## DECISIONES DE ARQUITECTURA CLAVE

- **WhatsApp**: Coexistence Mode (app móvil + Cloud API mismo número).
- **n8n es ROUTER ÚNICO** del webhook de WhatsApp (la Cloud API permite 1 solo
  webhook por número). Odoo y todo lo demás reciben datos A TRAVÉS de n8n.
- **Inbox multi-agente para escalar vendedores**: se construye sobre Odoo (no BSP),
  en 3 etapas. NO conectar módulo WhatsApp nativo de Odoo al mismo número.
- **Bridge custom** (no módulo Odoo nativo, no BSP) para flexibilidad del agente.
- **Precios SIEMPRE de Odoo**: el agente NUNCA inventa montos.
- **Human-in-the-loop** obligatorio para costos no parametrizados.
- **LLM**: decisión Claude vs OpenAI se pospone al piloto (Fase 7).

## HALLAZGOS IMPORTANTES (descubiertos en campo)

1. **Contactos de WhatsApp**: hoy los clientes solo se ven por número (sin nombre)
   porque guardar contactos es manual y la agenda de la app no tiene API. SOLUCIÓN
   (Fase 4): la Cloud API entrega el nombre de perfil en cada mensaje; n8n
   crea/actualiza contactos en Odoo automáticamente. Odoo se vuelve fuente de verdad.

2. **Exclusión de proveedores**: el agente NO debe responder a proveedores (a
   quienes Mozaprint COMPRA). Las etiquetas de la app no se exponen vía API.
   SOLUCIÓN (Fase 4): filtro pre-respuesta en n8n que consulta Odoo: si es
   proveedor (supplier_rank>0), o marcado "no atender", o número interno -> el
   agente no responde, queda en modo manual. Preparar: registrar proveedores en
   Odoo con su número de WhatsApp.

## DATOS OPERATIVOS DEL NEGOCIO

- Volumen: 10-20 conversaciones WhatsApp/semana, 1-2 operadores.
- Horario: L-V 9-18, Sáb 10-13, Dom cerrado.
- SLA: cotizaciones en menos de 24h (el sitio lo promociona).
- Anticipo: 50% estándar / caso por caso en >$100k MXN.
- Pago: transferencia (principal) + Mercado Pago.
- Agente: tono tutea, español MX, nombre "Moza" (confirmar con Karina).
- Comandos: /tomar, /reactivar, /pausar (alias inglés).
- Proveedores: 4PROMOTIONAL (4P), PROMOOPCION (PO), INNOVATIONLINE (INN).
  INN tiene lista de costos digital; 4P y PO no (construir desde histórico).

## TAREAS PENDIENTES NO BLOQUEANTES

- **VPS de n8n** - espera aprobación de pago. Desbloquea Fases 4-6.
- **Correo bidireccional** desde @mozaprintmx.com (prioridad MEDIA): configurar
  SMTP saliente + entrante en Odoo, ajustar SPF, DKIM. Mini-proyecto dedicado.
- **x_studio_origen_url**: definir cómo capturar URL dinámica.
- **Validar las 3 alertas** en funcionamiento real.

## SIGUIENTE PASO: FASE 2 (precios y catálogo)

Abarca: modelo de técnicas de personalización (x_tecnica_personalizacion + 8
técnicas seed: Serigrafía, Tampografía, Bordado, DTF Textil, DTF UV, Sublimación,
Láser, Vinyl), vincular productos con técnicas, migrar descuentos a Promotions,
filtros en /shop, color swatches, optional/accessory products.

ANTES de empezar Fase 2, se necesita conocer el estado del catálogo actual:
cuántos productos, cómo se cargan (script de proveedores), cómo está hoy el campo
"Técnica de impresión" en las tarjetas, si hay tabla de descuentos, estado de /shop.

## CÓMO TRABAJAR (preferencias del usuario)

- Pasos uno a uno con pausas de validación. No avanzar de golpe.
- No asumir herramientas/versiones; preguntar o dar formulario de opciones.
- Ser específico; cuando la decisión es clara, ser directo sin tantas vueltas.
- UI (Odoo/Meta): el usuario ejecuta y manda capturas; Claude guía y valida.
- Código: Claude Code construye, usuario revisa/aplica.
- Documentar en el repo tras cada hito (prompts específicos para Claude Code).
- Claude Code: plan -> revisar -> aprobar -> ejecutar -> validar -> commit+push.
- Repo PÚBLICO: NUNCA credenciales en él. Secretos en Bitwarden.
- Honestidad sobre trade-offs y riesgos; explicar brevemente el "por qué".
- Español México.
