# ADR 010 — La tienda pide, no cobra: checkout sin pago en línea

**Fecha**: 2026-09-22 · **Estado**: aceptada, **ejecutada en producción**

## Contexto

Mozaprint no tiene inventario propio: todo se pide al proveedor en cada venta. Aun así, la
tienda cobraba con Mercado Pago en el checkout. Cuando el cliente pagaba algo sin existencias,
el remedio era **devolver el dinero**, con comisión, tiempos y desgaste de confianza.

El aviso de "confirma existencias antes de pagar" en el paso de pago no servía: la fricción
informativa no gana contra un botón de pagar.

Medición previa (producción, 2026-09-14):

| Dato | Valor |
|---|---|
| Variantes publicadas con `x_stock_proveedor = 0` | 5,176 de 12,304 (**42 %**) |
| Productos publicados que permiten vender sin existencias | 5,012 (todos) |
| Cobros Mercado Pago completados | 9 en ~12 meses (6 web, 3 de cotizaciones del backend) |
| Cotizaciones creadas desde el backend (90 días) | 79 — es el canal principal |
| Pagos de factura en línea | 1 en toda la historia |

## Lo que se evaluó

| Opción | Veredicto |
|---|---|
| **A.** Cargar existencias del proveedor al inventario de Odoo | Descartada: obliga a productos almacenables, arrastra valuación contable y el dato igual se desfasa entre sincronizaciones |
| **B.** Despublicar Mercado Pago | Descartada: `payment/models/payment_provider.py:624` lo oculta a **todo** usuario no interno, portal incluido |
| **C.** Filtros de país, moneda o monto máximo | Descartada: ninguno distingue checkout de portal |
| **D.** Sitio web "estacionado" (el proveedor vive en un 2º sitio y el pedido se mueve al validar) | Viable y sin tocar plantillas, pero exige un sitio extra, mover pedidos entre sitios y automatizaciones adicionales |
| **E.** Ocultar "Añadir al carrito" por categorías | Descartada: elimina el carrito, que es justo lo que se quiere conservar |
| **F.** Vistas heredadas que filtran los medios de pago por pantalla | **Elegida** |

También se descartó de raíz cualquier app del marketplace (Odoo Online no las admite,
ADR 009) y cualquier Server Action con código (se factura, ADR 007).

## Decisión

Filtrar los medios de pago **por pantalla**, con dos vistas heredadas:

| Pantalla | Qué se ve |
|---|---|
| Checkout `/shop/payment` | Solo "Solicitar pedido (sin pago en línea)" |
| Portal del pedido y link de pago | Todo menos esa opción: tarjeta (Mercado Pago) |

El medio de la solicitud es el proveedor **manual de transferencia**, renombrado. Se eligió
sobre "Pago contra entrega" por una diferencia de comportamiento verificada en el código:

- `delivery/models/payment_transaction.py` → contra entrega **confirma el pedido solo**, lo que
  genera orden de entrega, cuenta como venta y obliga a cancelar ambas si no hay existencias.
- `sale/models/payment_transaction.py` → la transferencia pendiente solo pasa el pedido a
  **"Cotización enviada"**. Nada que cancelar, nada que devolver.

## Qué quedó construido

1. **Dos vistas** heredadas (`mozaprint.checkout_solo_solicitud`, `mozaprint.portal_sin_solicitud`).
2. **Proveedor de solicitud** habilitado y publicado, con su mensaje de ayuda y su mensaje de
   pantalla final; **contra entrega apagado**.
3. **Pago exprés apagado** en todos los proveedores: ese botón vive en el carrito y ninguna
   vista lo filtra.
4. **Método renombrado** a "Solicitar pedido (sin pago en línea)" y botón del portal traducido.
5. **Correo al cliente**: la rama del pago pendiente ahora dice que se recibió una solicitud, y
   la frase "El pago con la referencia X…" se movió a la rama donde sí hay pago.
6. **Dos automatizaciones declarativas** (0 líneas facturables): los pedidos de la tienda nacen
   con `require_payment = False`, y al pasar a "Cotización enviada" se crea la actividad
   *"Validar existencias con proveedor"*.
7. **213 carritos en borrador** ya existentes normalizados a `require_payment = False`.

Todo es configuración y datos: el auditor de líneas facturables sigue en **0**.

## Consecuencias

**Se gana**: ningún cliente puede pagar algo sin existencias confirmadas; si el pedido no
procede, no hay devolución, ni entrega, ni venta que cancelar; el vendedor recibe un pendiente
con fecha por cada solicitud.

**Se pierde**: el cobro por impulso en el checkout. Con 9 cobros en 12 meses y ticket promedio
de $1,168, el costo es marginal frente al riesgo.

**Riesgo principal**: las dos vistas se apoyan en plantillas de Odoo. Un upgrade que las
reestructure puede hacer que Odoo desactive las nuestras y **la tarjeta reaparezca en el
checkout en silencio** — el patrón de las tres incidencias de `docs/upgrades/`. Por eso
`scripts/audit_checkout_sin_pago.py` entra al checklist post-upgrade.

**Plan B** si esa fragilidad resulta inaceptable: la opción D (sitio estacionado), que no toca
plantillas.

## Reversible

```bash
python scripts/configurar_checkout_sin_pago.py --target prod --rollback --apply --si-produccion
```

La reversa es **compuesta**: reconstruye el estado original tomando, para cada pieza, el
respaldo más antiguo que la registró. Probada de punta a punta en test el 2026-09-21.

## Cómo se verificó

- Ciclo completo en test: aplicar → reversa → reaplicar, con verificación pieza por pieza.
- Prueba funcional de las dos automatizaciones, incluido el control de que las cotizaciones del
  backend no se ven afectadas.
- Render HTTP real del portal (el filtro se evalúa al dibujar la página, no solo al guardarla).
- Checkout probado a mano en test por JC, con y sin un proveedor de tarjeta activo.
- En producción: auditoría completa en verde y portal de un pedido real ofreciendo tarjeta y no
  la opción de solicitud.
