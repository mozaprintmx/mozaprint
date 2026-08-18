# 2026-08-15 · Internal Server Error en todas las fichas de producto

**Base**: test (`saas~19.2`) · **Estado**: ✓ **resuelto en test y en producción**
**Aplicado en producción**: 2026-08-17, el mismo día que Odoo subió la base a `saas~19.2`
**Severidad si pasara en producción**: **crítica** — el catálogo completo deja de ser
comprable. Ningún cliente puede abrir un producto.

## Síntoma

```
https://mozaprintmx-test-saas19-0807.odoo.com/shop/acme-bl-191-1898

Internal Server Error
The server encountered an internal error and was unable to complete your request.
```

Las **5,000+** fichas fallan, no una. Lo que despista es que el resto del sitio
está perfectamente sano:

| Ruta | Test (19.2) | Prod (19.0) |
|---|---|---|
| `/` , `/shop`, `/shop/cart`, `/contactanos`, `/terms` | 200 | 200 |
| `/shop/<cualquier-producto>` | **500** | 200 |

## Por qué costó verlo

Tres cosas apuntaban en la dirección equivocada:

1. **No hay traza en ningún lado.** `ir.logging` solo tenía autenticaciones RPC.
2. **La página de error de Odoo no aparece.** El 500 es el HTML crudo de werkzeug
   (265 bytes), sin la plantilla de error de Odoo, **incluso con sesión de
   administrador** — que normalmente muestra el traceback completo.
3. **Los datos están sanos.** Leer el producto por RPC funciona: nombre, precio,
   variantes, atributos, categorías, alternativos. Los 208 campos se leen sin error.

Los tres tienen la misma explicación: el fallo ocurre al **combinar las vistas**,
antes de que exista nada que renderizar. Y como el manejador de errores del sitio
web necesita combinar vistas para dibujar su propia página de error, tampoco
puede. De ahí el error pelón de werkzeug.

> Regla que dejó el incidente: **un 500 sin página de error de Odoo y sin traza
> apunta a la capa de vistas, no a los datos.** No pierdas tiempo auditando el
> producto.

## Causa raíz

La vista `website_sale.product_terms_and_conditions` — el bloque de "Términos y
condiciones · Envío: 2-3 días hábiles" al pie del botón de compra.

| | Odoo 19.0 (prod) | saas~19.2 (test) |
|---|---|---|
| Qué es | Plantilla **independiente** (`<t t-name="…">`), invocada con `t-call` | Vista **heredada** de `website_sale.product`, se injerta con `<div id="o_wsale_product_cta_section" position="inside">` |

Existen **dos** registros con esa key, por el mecanismo COW del editor del sitio:
la genérica de Odoo (id 3352, `website_id=False`) y **nuestra copia traducida al
español** (id 3951, `website_id=1`), creada cuando alguien editó ese texto desde
el editor web.

El upgrade convirtió correctamente la genérica… y a la copia le puso el
`inherit_id` nuevo **pero le dejó el `arch` viejo**:

```xml
<!-- id=3951, DESPUÉS del upgrade: inherit_id=3342, pero arch de plantilla suelta -->
<t name="Terms and Conditions" t-name="website_sale.product_terms_and_conditions">
    <small class="text-muted mb-0">…Términos y condiciones…</small>
</t>
```

Una vista con `inherit_id` **debe** decir dónde injertarse (`position=`, `xpath`
o `<data>`). Esta no dice nada → Odoo no puede combinarla → excepción → 500.

**Es exactamente el precio de haber personalizado ese texto.** Una instalación
que hubiera dejado el bloque en inglés no tendría copia por-website y no se
habría roto. El upgrade migra bien lo suyo; lo nuestro no lo mira.

## Reparación

[`scripts/fix_vista_terminos_producto.py`](../../../scripts/fix_vista_terminos_producto.py)
— dry-run por defecto, respaldo en `backups/` y `--rollback`. Convierte el `arch`
al formato de herencia **conservando el texto en español** (borrar la copia
también arreglaría el 500, pero devolvería el bloque a inglés).

```bash
python scripts/fix_vista_terminos_producto.py --target test            # simulacro
python scripts/fix_vista_terminos_producto.py --target test --apply
python scripts/fix_vista_terminos_producto.py --target test --rollback --apply
```

Resultado (`<data>` envolviendo el mismo contenido):

```xml
<data name="Terms and Conditions">
    <div id="o_wsale_product_cta_section" position="inside">
        <small class="text-muted mb-0"><a href="/terms" …><u>Términos y condiciones</u></a><br/>Envío: 2-3 días hábiles (sin personalización)</small>
    </div>
</data>
```

**Verificado el 2026-08-15**: 7 de 7 fichas pasaron de 500 a 200 y el texto en
español sigue saliendo. Respaldo del arch original en
`backups/vista_terminos_test_20260815_001317.json`.

## ¿Aplica a producción? — SÍ, y ya se aplicó

**Odoo subió producción a `saas~19.2` el 2026-08-17** y el fallo apareció idéntico,
como estaba previsto: mismo id de vista (3951), mismo arch, y las **5,012 fichas
publicadas** devolviendo 500. El resto del sitio (`/`, `/shop`, carrito,
`/contactanos`, `/terms`) siguió en 200, igual que en test.

```bash
python scripts/fix_vista_terminos_producto.py --target prod                      # simulacro
python scripts/fix_vista_terminos_producto.py --target prod --apply --si-produccion
```

Reparado en un solo registro. Verificación inmediata: **10 de 10 fichas en 200**
con el bloque en español intacto, y el auditor pasó de `✗ BLOQUEANTE — 1` a
`✓ ninguna`. Respaldo en `backups/vista_terminos_prod_20260817_234900.json`.

### El detalle que se descubrió al aplicarlo: `arch_db` es un campo traducido

El script escribía `arch_db` **una sola vez, sin fijar idioma**. En un campo
traducido (`translate=xml_translate`) eso arriesga reparar `en_US` y dejar
`es_419` con el arch viejo — y `es_419` es justo el idioma que ve el cliente. El
sondeo previo confirmó que **los dos idiomas estaban rotos**, con el mismo texto
en español en ambos.

Es exactamente la trampa que ya había mordido a `deploy_reporte_cotizacion.py` en
su función `limpiar_base`. Se endureció igual: leer y escribir **idioma por
idioma**, empezando por el origen `en_US`.

> Regla que deja el incidente: **antes de escribir `arch_db` —o cualquier campo
> traducido— por API, itera los idiomas.** Reparar solo el idioma de la sesión
> deja el sitio roto para los visitantes y el error no se ve desde el backend.

El respaldo también pasó a guardar un arch **por idioma**; el `--rollback` sigue
leyendo los respaldos viejos de un solo idioma.

## Cómo se detecta automáticamente

Revisión **[1]** de [`scripts/audit_post_upgrade.py`](../../../scripts/audit_post_upgrade.py):
*vistas heredadas cuyo arch no es una especificación de herencia*. Barre las
~4,800 vistas de la base y marca el hallazgo como bloqueante.

En test, antes del fix reportaba la vista 3951; después, cero. Producción (19.0)
sale limpia, como debe ser.

## Lección general

El riesgo no está en lo que Odoo trae de fábrica ni en nuestros campos `x_` — está
en **lo que personalizamos encima de algo que Odoo después reestructura**. Cada
texto editado desde el editor del sitio web crea una copia por-website que el
upgrade migra peor que la original.

Vale la pena tener inventariadas esas copias: son **64** en test. Ver la revisión
correspondiente en el [checklist](../checklist-post-upgrade.md).
