# Manual del vendedor — pedidos que llegan de la tienda

> Desde el 2026-09-22 la tienda **no cobra**. El cliente arma su carrito y envía una
> solicitud; tú validas existencias y decides cuándo se puede pagar.
> El porqué está en `decisions/010-checkout-sin-pago-en-linea.md`.

## Qué ve el cliente

En el paso de pago hay **una sola opción**: *"Solicitar pedido (sin pago en línea)"*, con este
mensaje debajo:

> No se cobra nada ahora. Revisaremos existencias con el proveedor y te contactaremos para
> confirmar tu pedido y las opciones de pago.

El botón dice **"Enviar solicitud"**. No hay forma de pagar con tarjeta en la tienda.

Al enviar, el cliente recibe un correo con el PDF adjunto que dice que recibimos su pedido y que
**aún no se ha registrado ningún pago**.

## Qué te llega a ti

Una actividad **"Validar existencias con proveedor"**, a tu nombre, con vencimiento al día
siguiente. Aparece en tu tablero de actividades y en la conversación del pedido.

No llega correo: la actividad es el aviso. Si quieres verlas todas juntas, filtra las
cotizaciones por el equipo de ventas **Website** — la tienda lo asigna solo.

El pedido entra como **cotización enviada**. No es una venta confirmada y **no genera entrega**.

## Qué haces tú

### 1. Validar existencias
Con el proveedor, como siempre. El dato de `x_stock_proveedor` en el producto es referencia, no
promesa: se sincroniza varias veces al día pero el proveedor puede vender esas piezas mientras
tanto.

### 2a. Si procede — habilitar el cobro
Dos caminos equivalentes:

- **Enlace de pago** (recomendado): en la cotización, *Generar enlace de pago* por el monto que
  quieras (por ejemplo el anticipo del 50 %) y mándalo por WhatsApp o correo. Funciona siempre.
- **Casilla "Pago en línea"**: en la pestaña *Otra información*. Al marcarla, el cliente ve el
  botón de pagar en su portal y se le pide el 50 %.

Cuando el cliente paga, **la orden se confirma sola**, nace la entrega y el pago queda
registrado y conciliado. No se emite factura automáticamente: tú decides cuándo.

### 2b. Si no procede
Edita la cotización (cambia cantidades, productos o precios) y vuelve a enviarla, o descártala.
**No hay nada que cancelar**: ni entrega, ni venta, ni pago que devolver.

### 3. Si el cliente prefiere transferencia o efectivo
Se acuerda por fuera y registras el pago a mano. La tienda no ofrece esas opciones en línea.

## Cosas que conviene saber

| Situación | Qué pasa |
|---|---|
| La cotización cumple **7 días** | Vence y el enlace de pago deja de funcionar. Extiende la *fecha de validez* y vuelve a enviarlo |
| Regresas una cotización a borrador y la reenvías | Se crea otra actividad de validación. Es inofensivo: márcala como hecha |
| Cotizaciones que tú creas desde el backend | No cambian en nada: conservan el pago en línea y no generan actividad |
| Un cliente dice que no puede pagar | Revisa que la cotización no esté vencida y que tenga el pago en línea marcado, o mándale un enlace nuevo |

## Si algo se ve raro

Si en el checkout llegara a aparecer una opción de tarjeta, algo se rompió (normalmente tras una
actualización de Odoo). Se revisa con:

```bash
python scripts/audit_checkout_sin_pago.py --target prod
```
