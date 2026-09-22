#!/usr/bin/env python3
"""
Configura el checkout de la tienda para que NO cobre en línea: el cliente envía
una **solicitud de pedido** (sin pago) y el cobro se hace después, por link,
cuando el vendedor ya validó existencias con el proveedor.

Qué hace (todo configuración; 0 líneas facturables — ver `decisions/007`)
-----------------------------------------------------------------------
1. **Vista A** (heredada de `website_sale.payment`): en el paso de pago deja
   solo el método manual `wire_transfer` y fija el texto del botón.
2. **Vista B** (heredada de `sale.sale_order_portal_pay_modal`): en el portal y
   en el link de pago quita ese mismo método, para que ahí solo se vea tarjeta.
3. Habilita el proveedor de transferencia como "solicitud sin pago" (con sus
   mensajes) y **apaga Pago contra entrega**, que confirma pedidos solo.
4. Renombra el método `wire_transfer` y traduce el botón "Pagar ahora".
5. Crea dos automatizaciones **declarativas**:
   - los pedidos de la tienda nacen con `require_payment = False`;
   - al pasar a "Cotización enviada" se crea la actividad "Validar existencias
     con proveedor" para el vendedor.

Por qué así: "contra entrega" confirma el pedido en automático (genera entrega y
cuenta como venta); la transferencia pendiente solo lo deja en "Cotización
enviada". Verificado en `delivery/models/payment_transaction.py` y
`sale/models/payment_transaction.py` (saas~19.3).

Guardarraíles
-------------
- **DRY-RUN POR DEFECTO.** Sin `--apply` no escribe nada.
- Aborta si las plantillas de Odoo no tienen los anclajes esperados (un upgrade
  pudo reestructurarlas): mejor no aplicar que dejar el checkout a medias.
- `--target prod` exige además `--si-produccion`.
- Todo cambio se respalda en `backups/checkout_sin_pago_<target>_<fecha>.json`
  y `--rollback` lo deshace.

Los campos de texto (`name`, `pre_msg`, `pending_msg`, `arch_db`, labels) son
**traducidos**: se escriben idioma por idioma empezando por `en_US`. Escribir
solo el idioma de la sesión deja el sitio roto para el visitante (incidencia
2026-08-15).

Uso:
    python scripts/configurar_checkout_sin_pago.py --target test            # simulacro
    python scripts/configurar_checkout_sin_pago.py --target test --apply
    python scripts/configurar_checkout_sin_pago.py --target test --rollback --apply
    python scripts/configurar_checkout_sin_pago.py --target prod --apply --si-produccion

Variables de entorno (analysis/supplier-sync/.env):
    ODOO_URL, ODOO_TEST_URL, ODOO_DB, ODOO_USER, ODOO_PASSWORD
"""

from __future__ import annotations

import argparse
import io
import json
import os
import re
import sys
import xml.etree.ElementTree as ET
import xmlrpc.client
from datetime import datetime
from pathlib import Path
from typing import Any, Callable

from dotenv import load_dotenv

# La consola de Windows (cp1252) no puede imprimir '→', 'ó', etc.
if hasattr(sys.stdout, "buffer"):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

REPO = Path(__file__).resolve().parent.parent
BACKUP_DIR = REPO / "backups"

# --- Objetos de Odoo sobre los que trabajamos -------------------------------

VISTA_CHECKOUT_BASE = "website_sale.payment"
VISTA_PORTAL_BASE = "sale.sale_order_portal_pay_modal"

# Anclajes que deben existir en las plantillas de Odoo. Si un upgrade los mueve,
# el script aborta en vez de crear una vista que no aplica (fallo silencioso).
ANCLA_CHECKOUT = 't-set="hide_payment_button"'
ANCLA_PORTAL = 't-call="payment.form"'

CLAVE_VISTA_CHECKOUT = "mozaprint.checkout_solo_solicitud"
CLAVE_VISTA_PORTAL = "mozaprint.portal_sin_solicitud"

METODO_SOLICITUD = "wire_transfer"       # el que se ofrece en el checkout
METODO_COD = "cash_on_delivery"          # se apaga: confirma pedidos solo

AUTO_SIN_COBRO = "Tienda · pedido nace sin cobro en línea"
AUTO_ACTIVIDAD = "Tienda · validar existencias de una solicitud"

# --- Textos de cara al cliente (traducidos) ---------------------------------

NOMBRE_METODO = {
    "en_US": "Request order (no online payment)",
    "es_419": "Solicitar pedido (sin pago en línea)",
}
NOMBRE_PROVEEDOR = {
    "en_US": "Order request (no payment)",
    "es_419": "Solicitud de pedido (sin pago)",
}
PRE_MSG = {
    "en_US": "<p>Nothing is charged now. We will check stock with the supplier and will contact "
             "you to confirm your order and the payment options.</p>",
    "es_419": "<p>No se cobra nada ahora. Revisaremos existencias con el proveedor y te "
              "contactaremos para confirmar tu pedido y las opciones de pago.</p>",
}
PENDING_MSG = {
    "en_US": "<p>We received your request. We will check stock and will send you the confirmation "
             "with the payment options: card, bank transfer or cash.</p>",
    "es_419": "<p>Recibimos tu solicitud. Validaremos las existencias y te enviaremos la "
              "confirmación con las opciones de pago: tarjeta, transferencia o efectivo.</p>",
}
BOTON_CHECKOUT = {"en_US": "Send request", "es_419": "Enviar solicitud"}
PAY_NOW_LABEL = {"en_US": "Pay now", "es_419": "Pagar ahora"}

# --- Correo al cliente ------------------------------------------------------
# Odoo manda `sale.mail_template_sale_payment_executed` cuando la transacción queda
# pendiente, que es SIEMPRE nuestro caso (la solicitud no cobra). El problema: la
# frase "El pago con la referencia X por un importe de Y" está FUERA del condicional,
# así que el cliente leería que hay un pago inexistente. La edición mueve esa frase a
# la rama del pago confirmado y deja la rama pendiente con nuestro texto.
# La plantilla es `noupdate=True`: el cambio sobrevive a las actualizaciones de Odoo.

TEXTO_CORREO = {
    "en_US": 'We received your order <span style="font-weight:bold;" t-out="object.name or \'\'">'
             'S00049</span>. No payment has been registered yet. We are checking stock with the '
             'supplier and will send you the confirmation along with the payment options.',
    "es_419": 'Recibimos tu pedido <span style="font-weight:bold;" t-out="object.name or \'\'">'
              'S00049</span>. Aún no se ha registrado ningún pago. Estamos validando existencias '
              'con el proveedor y te enviaremos la confirmación junto con las opciones de pago.',
}
# Huella para saber si ya se aplicó (el script es idempotente).
MARCA_CORREO = {
    "en_US": "No payment has been registered yet",
    "es_419": "Aún no se ha registrado ningún pago",
}
# Corta desde el saludo hasta la rama del pago confirmado, capturando la frase
# compartida (grupo 2) para reinsertarla donde sí aplica.
PATRON_CORREO = re.compile(
    r"((?:<br\s*/?>\s*){2})"   # el doble salto tras el saludo (sirva el idioma que sea)
    r"(.*?)"
    r"(<t t-if=\"transaction_sudo and transaction_sudo\.state == 'pending'\">)"
    r"(.*?)"
    r"(</t>\s*<t t-else=\"\">\s*(?:has been confirmed|ha sido confirmado))",
    re.S,
)

ACTIVIDAD_RESUMEN = "Validar existencias con proveedor"
ACTIVIDAD_DIAS = 1


def arch_checkout(lang: str) -> str:
    """Vista A: en el checkout, solo el método de solicitud."""
    return (
        "<data>"
        f'<xpath expr="//t[@t-set=\'hide_payment_button\']" position="before">'
        '<t t-set="payment_methods_sudo"'
        f" t-value=\"payment_methods_sudo.filtered(lambda pm: pm.code == '{METODO_SOLICITUD}')\"/>"
        '<t t-set="tokens_sudo"'
        " t-value=\"tokens_sudo.filtered(lambda t: t.provider_id.code == 'custom')\"/>"
        f'<t t-set="submit_button_label">{BOTON_CHECKOUT[lang]}</t>'
        "</xpath>"
        "</data>"
    )


def arch_portal(_lang: str) -> str:
    """Vista B: en el portal y el link de pago, todo menos el de solicitud."""
    return (
        "<data>"
        '<xpath expr="//t[@t-call=\'payment.form\']" position="before">'
        '<t t-set="payment_methods_sudo"'
        f" t-value=\"payment_methods_sudo.filtered(lambda pm: pm.code != '{METODO_SOLICITUD}')\"/>"
        "</xpath>"
        "</data>"
    )


# --- Conexión ---------------------------------------------------------------

def conectar(url: str, db: str, user: str, pwd: str) -> Callable:
    uid = xmlrpc.client.ServerProxy(f"{url}/xmlrpc/2/common").authenticate(db, user, pwd, {})
    if not uid:
        raise SystemExit(f"✗ Autenticación fallida en {url} (db={db})")
    models = xmlrpc.client.ServerProxy(f"{url}/xmlrpc/2/object")

    def call(model: str, method: str, *args: Any, **kw: Any) -> Any:
        return models.execute_kw(db, uid, pwd, model, method, list(args), kw)

    return call


def idiomas(call: Callable) -> list[str]:
    """Los campos traducidos se escriben en todos los idiomas, `en_US` primero."""
    activos = [l["code"] for l in
               call("res.lang", "search_read", [["active", "=", True]], fields=["code"])]
    return list(dict.fromkeys(["en_US"] + activos))


# Los cuerpos de correo son HTML, no XML: traen `<br>` e `<img>` sin cerrar y
# entidades como `&nbsp;`. Se normalizan antes de validar para no rechazar
# plantillas perfectamente válidas (el español de Odoo usa `<br>`).
_VACIOS = re.compile(r"<(br|hr|img|input|meta|link)(\s[^>]*?)?/?>", re.I)
_ENTIDAD = re.compile(r"&(?!amp;|lt;|gt;|quot;|apos;|#)")


def _cerrar_vacio(m: re.Match) -> str:
    """`<br>` y `<br attr="x"/>` → `<br/>` y `<br attr="x"/>`, sin duplicar la barra."""
    return f"<{m.group(1)}{(m.group(2) or '').rstrip('/')}/>"


def xml_valido(html: str) -> bool:
    """¿El cuerpo está bien formado? Si no, el correo revienta al enviarse."""
    normalizado = _VACIOS.sub(_cerrar_vacio, html or "")
    normalizado = _ENTIDAD.sub("&amp;", normalizado)
    try:
        ET.fromstring(f"<root>{normalizado}</root>")
        return True
    except ET.ParseError:
        return False


def leer_traducido(call: Callable, modelo: str, rid: int, campos: list[str],
                   langs: list[str]) -> dict[str, dict[str, Any]]:
    """{lang: {campo: valor}} — para respaldar campos traducidos."""
    return {
        lang: call(modelo, "read", [rid], fields=campos, context={"lang": lang})[0]
        for lang in langs
    }


# --- Comprobaciones previas -------------------------------------------------

def preflight(call: Callable, langs: list[str]) -> dict[str, Any]:
    """Reúne los ids necesarios y aborta si la base no es la esperada."""
    ctx = {"active_test": False}
    ref: dict[str, Any] = {}

    for clave, ancla, destino in (
        (VISTA_CHECKOUT_BASE, ANCLA_CHECKOUT, "vista_checkout"),
        (VISTA_PORTAL_BASE, ANCLA_PORTAL, "vista_portal"),
    ):
        vistas = call("ir.ui.view", "search_read",
                      [["key", "=", clave], ["website_id", "=", False]],
                      fields=["id", "name", "active"], context={"lang": "en_US"})
        if not vistas:
            raise SystemExit(f"✗ ABORTADO: no existe la plantilla base `{clave}`.")
        arch = call("ir.ui.view", "read", [vistas[0]["id"]], fields=["arch_db"],
                    context={"lang": "en_US"})[0]["arch_db"] or ""
        if ancla not in arch:
            raise SystemExit(
                f"✗ ABORTADO: la plantilla `{clave}` ya no contiene el anclaje esperado\n"
                f"  ({ancla}). Probablemente un upgrade la reestructuró: revisa el XPath\n"
                f"  antes de aplicar, o el checkout quedaría sin filtrar."
            )
        ref[destino] = vistas[0]["id"]

    metodos = call("payment.method", "search_read",
                   [["code", "in", [METODO_SOLICITUD, METODO_COD]]],
                   fields=["id", "code", "active"], context=ctx)
    ref["metodos"] = {m["code"]: m for m in metodos}
    if METODO_SOLICITUD not in ref["metodos"]:
        raise SystemExit(f"✗ ABORTADO: no existe el método de pago `{METODO_SOLICITUD}`.")

    provs = call("payment.provider", "search_read", [["code", "=", "custom"]],
                 fields=["id", "name", "custom_mode", "state", "is_published"], context=ctx)
    ref["prov_solicitud"] = next((p for p in provs if p["custom_mode"] == METODO_SOLICITUD), None)
    ref["prov_cod"] = next((p for p in provs if p["custom_mode"] == METODO_COD), None)
    if not ref["prov_solicitud"]:
        raise SystemExit("✗ ABORTADO: no existe el proveedor de transferencia (custom/wire_transfer).")

    for campo in ("website_id", "require_payment"):
        if not call("ir.model.fields", "search_count",
                    [["model", "=", "sale.order"], ["name", "=", campo]]):
            raise SystemExit(f"✗ ABORTADO: `sale.order` no tiene el campo `{campo}`.")

    ref["modelo_so"] = call("ir.model", "search_read", [["model", "=", "sale.order"]],
                            fields=["id"])[0]["id"]

    sel = call("ir.model.fields.selection", "search_read",
               [["field_id.model", "=", "sale.order"], ["field_id.name", "=", "state"],
                ["value", "=", "sent"]], fields=["id"])
    if not sel:
        raise SystemExit("✗ ABORTADO: no se encontró el estado `sent` de `sale.order`.")
    ref["sel_sent"] = sel[0]["id"]

    tipo = call("ir.model.data", "search_read",
                [["model", "=", "mail.activity.type"], ["module", "=", "mail"],
                 ["name", "=", "mail_activity_data_todo"]], fields=["res_id"])
    if not tipo:
        raise SystemExit("✗ ABORTADO: no existe el tipo de actividad 'To-Do' (mail.mail_activity_data_todo).")
    ref["tipo_actividad"] = tipo[0]["res_id"]

    usuario = call("res.users", "search_read", [["login", "=", os.environ["ODOO_USER"]]],
                   fields=["id", "name"])
    if not usuario:
        raise SystemExit(f"✗ ABORTADO: no se encontró el usuario {os.environ['ODOO_USER']}.")
    ref["usuario"] = usuario[0]

    mp = call("payment.provider", "search_read", [["code", "=", "mercado_pago"]],
              fields=["id", "state", "is_published", "website_id"], context=ctx)
    ref["mercado_pago"] = mp[0] if mp else None

    ref["langs"] = langs
    return ref


# --- Utilidades de escritura ------------------------------------------------

def upsert_vista(call: Callable, apply_: bool, clave: str, nombre: str, padre: int,
                 arch_por_lang: dict[str, str], langs: list[str],
                 respaldo: dict) -> None:
    """Crea o actualiza una vista heredada, idioma por idioma."""
    existentes = call("ir.ui.view", "search_read", [["key", "=", clave]],
                      fields=["id", "active"], context={"active_test": False})
    if existentes:
        vid = existentes[0]["id"]
        previo = leer_traducido(call, "ir.ui.view", vid, ["arch_db", "active"], langs)
        respaldo["vistas"].append({"clave": clave, "id": vid, "existia": True, "previo": previo})
        print(f"  · vista `{clave}` ya existe (id={vid}) → se actualiza")
        if apply_:
            call("ir.ui.view", "write", [vid], {"active": True})
            for lang in langs:
                call("ir.ui.view", "write", [vid], {"arch_db": arch_por_lang[lang]},
                     context={"lang": lang})
            print("    → actualizada en " + ", ".join(langs))
        return

    print(f"  · vista `{clave}` no existe → se crea heredando de id={padre}")
    respaldo["vistas"].append({"clave": clave, "id": None, "existia": False, "previo": None})
    if apply_:
        vid = call("ir.ui.view", "create", {
            "name": nombre,
            "key": clave,
            "type": "qweb",
            "mode": "extension",
            "inherit_id": padre,
            "active": True,
            "arch_db": arch_por_lang["en_US"],
        })
        for lang in langs:
            call("ir.ui.view", "write", [vid], {"arch_db": arch_por_lang[lang]},
                 context={"lang": lang})
        respaldo["vistas"][-1]["id"] = vid
        print(f"    → creada id={vid} en " + ", ".join(langs))


def upsert_automatizacion(call: Callable, apply_: bool, nombre: str, base_vals: dict,
                          accion_vals: dict, respaldo: dict) -> None:
    """Crea o actualiza una automatización declarativa (nunca tipo `code`).

    En saas~19.3 la regla (`base.automation`) y su acción (`ir.actions.server`)
    son registros separados: la acción cuelga de `action_server_ids`.
    """
    if accion_vals.get("state") == "code":  # cinturón: el código de Studio se factura
        raise SystemExit("✗ ABORTADO: este script no crea automatizaciones con código.")

    accion = {**accion_vals, "name": nombre, "model_id": base_vals["model_id"],
              "usage": "base_automation"}
    resumen = f"{base_vals['trigger']} → {accion_vals['state']}"

    existentes = call("base.automation", "search_read", [["name", "=", nombre]],
                      fields=["id"], context={"active_test": False})
    if existentes:
        aid = existentes[0]["id"]
        respaldo["automatizaciones"].append({"nombre": nombre, "id": aid, "existia": True})
        print(f"  · «{nombre}» ya existe (id={aid}) → se actualiza [{resumen}]")
        if apply_:
            call("base.automation", "write", [aid], {
                **base_vals, "active": True,
                "action_server_ids": [[5, 0, 0], [0, 0, accion]],
            })
            print("    → actualizada")
        return

    print(f"  · «{nombre}» no existe → se crea [{resumen}]")
    respaldo["automatizaciones"].append({"nombre": nombre, "id": None, "existia": False})
    if apply_:
        aid = call("base.automation", "create", {
            **base_vals, "name": nombre, "active": True,
            "action_server_ids": [[0, 0, accion]],
        })
        respaldo["automatizaciones"][-1]["id"] = aid
        print(f"    → creada id={aid}")


# --- Acción principal -------------------------------------------------------

def aplicar(call: Callable, args, ref: dict) -> int:
    langs = ref["langs"]
    apply_ = args.apply
    respaldo: dict[str, Any] = {
        "target": args.target,
        "fecha": datetime.now().isoformat(timespec="seconds"),
        "idiomas": langs,
        "vistas": [],
        "automatizaciones": [],
        "proveedores": [],
        "express": [],
        "metodo": None,
        "compania": None,
        "correo": None,
        "carritos": None,
    }

    print("\n[1/9] Vistas")
    upsert_vista(call, apply_, CLAVE_VISTA_CHECKOUT,
                 "Checkout: solo solicitud sin pago", ref["vista_checkout"],
                 {lang: arch_checkout(lang) for lang in langs}, langs, respaldo)
    upsert_vista(call, apply_, CLAVE_VISTA_PORTAL,
                 "Portal: sin la opción de solicitud", ref["vista_portal"],
                 {lang: arch_portal(lang) for lang in langs}, langs, respaldo)

    print("\n[2/9] Proveedor de la solicitud (transferencia)")
    prov = ref["prov_solicitud"]
    previo = leer_traducido(call, "payment.provider", prov["id"],
                            ["name", "pre_msg", "pending_msg", "state", "is_published"], langs)
    respaldo["proveedores"].append({"id": prov["id"], "rol": "solicitud", "previo": previo})
    print(f"  · id={prov['id']} «{prov['name']}»  estado {prov['state']} → enabled, publicado")
    if apply_:
        call("payment.provider", "write", [prov["id"]],
             {"state": "enabled", "is_published": True})
        for lang in langs:
            call("payment.provider", "write", [prov["id"]], {
                "name": NOMBRE_PROVEEDOR.get(lang, NOMBRE_PROVEEDOR["en_US"]),
                "pre_msg": PRE_MSG.get(lang, PRE_MSG["en_US"]),
                "pending_msg": PENDING_MSG.get(lang, PENDING_MSG["en_US"]),
            }, context={"lang": lang})
        print("    → habilitado y textos escritos en " + ", ".join(langs))

    print("\n[3/9] Pago contra entrega (se apaga: confirma pedidos solo)")
    cod = ref["prov_cod"]
    if not cod:
        print("  · no existe el proveedor de contra entrega; nada que apagar")
    else:
        respaldo["proveedores"].append({
            "id": cod["id"], "rol": "cod",
            "previo": {"en_US": {"state": cod["state"], "is_published": cod["is_published"]}},
        })
        print(f"  · id={cod['id']} «{cod['name']}»  estado {cod['state']} → disabled")
        if apply_ and cod["state"] != "disabled":
            call("payment.provider", "write", [cod["id"]], {"state": "disabled"})
            print("    → apagado")

    print("\n[4/9] Pago exprés del carrito (se apaga: salta el checkout entero)")
    # El botón "Pagar con ..." del carrito no pasa por `/shop/payment`, así que la
    # Vista A no lo filtra. Hoy ningún proveedor de producción lo soporta, pero si
    # mañana se habilita uno (Stripe, PayPal), el cliente podría pagar desde el
    # carrito saltándose la solicitud.
    expres = call("payment.provider", "search_read", [["allow_express_checkout", "=", True]],
                  fields=["id", "name", "state"], context={"active_test": False})
    if not expres:
        print("  · ningún proveedor tiene pago exprés activo")
    for p in expres:
        respaldo["express"].append({"id": p["id"], "previo": True})
        print(f"  · id={p['id']} «{p['name']}» ({p['state']}) → pago exprés apagado")
        if apply_:
            call("payment.provider", "write", [p["id"]], {"allow_express_checkout": False})
            print("    → apagado")

    print("\n[5/9] Nombre del método y texto del botón del portal")
    met = ref["metodos"][METODO_SOLICITUD]
    respaldo["metodo"] = {
        "id": met["id"],
        "previo": leer_traducido(call, "payment.method", met["id"], ["name", "active"], langs),
    }
    print(f"  · método id={met['id']} `{METODO_SOLICITUD}` → «{NOMBRE_METODO['es_419']}»")
    if apply_:
        for lang in langs:
            call("payment.method", "write", [met["id"]],
                 {"name": NOMBRE_METODO.get(lang, NOMBRE_METODO["en_US"])},
                 context={"lang": lang})
        print("    → renombrado en " + ", ".join(langs))

    compania = call("res.company", "search_read", [], fields=["id"], limit=1)[0]["id"]
    respaldo["compania"] = {
        "id": compania,
        "previo": leer_traducido(call, "res.company", compania, ["pay_now_label"], langs),
    }
    print(f"  · compañía id={compania}: pay_now_label es_419 → «{PAY_NOW_LABEL['es_419']}»")
    if apply_:
        for lang in langs:
            call("res.company", "write", [compania],
                 {"pay_now_label": PAY_NOW_LABEL.get(lang, PAY_NOW_LABEL["en_US"])},
                 context={"lang": lang})
        print("    → traducido")

    print("\n[6/9] Correo al cliente: rama del pago pendiente")
    plantilla = call("ir.model.data", "search_read",
                     [["model", "=", "mail.template"], ["module", "=", "sale"],
                      ["name", "=", "mail_template_sale_payment_executed"]], fields=["res_id"])
    if not plantilla:
        print("  ⚠ no existe la plantilla de estado de pago: se omite")
    else:
        tid = plantilla[0]["res_id"]
        respaldo["correo"] = {
            "id": tid,
            "previo": leer_traducido(call, "mail.template", tid, ["body_html"], langs),
        }
        for lang in langs:
            cuerpo = respaldo["correo"]["previo"][lang]["body_html"] or ""
            ya = [l for l, marca in MARCA_CORREO.items() if marca in cuerpo]
            if ya:
                print(f"  · [{lang}] ya tiene el texto de solicitud (en {', '.join(ya)})")
                continue

            def _rehacer(m, _lang=lang):
                saludo, compartida, _abre, _pendiente, cierre = m.groups()
                palabra = ("has been confirmed" if "has been confirmed" in cierre
                           else "ha sido confirmado")
                nuevo = TEXTO_CORREO.get(_lang, TEXTO_CORREO["en_US"])
                return (f"{saludo}"
                        f"<t t-if=\"transaction_sudo and transaction_sudo.state == 'pending'\">"
                        f"{nuevo}</t>"
                        f"<t t-else=\"\">{compartida} {palabra}")

            cuerpo_nuevo, n = PATRON_CORREO.subn(_rehacer, cuerpo)
            if not n:
                print(f"  ⚠ [{lang}] no se reconoció la estructura del correo: se deja como está")
                continue
            if not xml_valido(cuerpo_nuevo):
                print(f"  ⚠ [{lang}] el cuerpo resultante no sería XML válido: se deja como está")
                continue
            print(f"  · [{lang}] rama pendiente reescrita; la frase del pago se mueve al caso "
                  f"de pago confirmado")
            if apply_:
                call("mail.template", "write", [tid], {"body_html": cuerpo_nuevo},
                     context={"lang": lang})
                print("    → escrito")

        # `body_html` se traduce por términos: al REESTRUCTURAR la plantilla (que es lo
        # que hacemos), Odoo no conserva cuerpos distintos por idioma y el último idioma
        # escrito queda para todos. Con es_419 como único idioma activo del sitio, eso es
        # justo lo que el cliente debe leer. Se relee para no irse con la idea equivocada.
        if apply_:
            for lang in langs:
                cuerpo = call("mail.template", "read", [tid], fields=["body_html"],
                              context={"lang": lang})[0]["body_html"] or ""
                puesto = [l for l, marca in MARCA_CORREO.items() if marca in cuerpo]
                print(f"    verificación [{lang}]: "
                      + (f"✓ texto de solicitud (en {', '.join(puesto)})" if puesto
                         else "✗ NO quedó el texto"))

    print("\n[7/9] Automatización 1: el pedido de la tienda nace sin cobro en línea")
    upsert_automatizacion(
        call, apply_, AUTO_SIN_COBRO,
        base_vals={
            "model_id": ref["modelo_so"],
            "trigger": "on_create",
            "filter_domain": "[('website_id', '!=', False)]",
        },
        accion_vals={
            "state": "object_write",
            "update_path": "require_payment",
            "update_boolean_value": "false",
        },
        respaldo=respaldo,
    )

    print("\n[8/9] Automatización 2: actividad de validación al recibir la solicitud")
    upsert_automatizacion(
        call, apply_, AUTO_ACTIVIDAD,
        base_vals={
            "model_id": ref["modelo_so"],
            "trigger": "on_state_set",
            "trg_selection_field_id": ref["sel_sent"],
            "filter_domain": "[('state', '=', 'sent'), ('website_id', '!=', False)]",
        },
        accion_vals={
            "state": "next_activity",
            "activity_type_id": ref["tipo_actividad"],
            "activity_summary": ACTIVIDAD_RESUMEN,
            "activity_user_type": "specific",
            "activity_user_id": ref["usuario"]["id"],
            "activity_date_deadline_range": ACTIVIDAD_DIAS,
            "activity_date_deadline_range_type": "days",
        },
        respaldo=respaldo,
    )

    print("\n[9/9] Carritos en borrador que nacieron con cobro en línea")
    # La automatización 1 solo alcanza a los pedidos NUEVOS. Los carritos que ya estaban
    # en la base conservan «Pago en línea = Sí»: si uno de esos clientes vuelve y termina
    # su solicitud, el portal le ofrecería pagar antes de que el vendedor valide.
    carritos = call("sale.order", "search",
                    [["website_id", "!=", False], ["state", "=", "draft"],
                     ["require_payment", "=", True]])
    respaldo["carritos"] = {"ids": carritos, "previo": True}
    print(f"  · {len(carritos)} carrito(s) de la tienda → «Pago en línea = No»")
    if carritos and apply_:
        call("sale.order", "write", carritos, {"require_payment": False})
        print("    → actualizados")

    if ref["mercado_pago"] and ref["mercado_pago"]["state"] == "disabled":
        print("\n⚠  Mercado Pago está DESHABILITADO en esta base: el cobro posterior no se podrá")
        print("   probar aquí (en test es normal, la base neutralizada no guarda credenciales).")

    if apply_:
        # Un segundo `--apply` fotografía un estado YA configurado: ese respaldo no
        # sirve para volver al origen. Se marca cuál es el "virgen" para que la
        # reversa elija bien.
        respaldo["virgen"] = all(not v["existia"] for v in respaldo["vistas"])
        BACKUP_DIR.mkdir(exist_ok=True)
        p = BACKUP_DIR / f"checkout_sin_pago_{args.target}_{datetime.now():%Y%m%d_%H%M%S}.json"
        p.write_text(json.dumps(respaldo, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"\n✓ Aplicado. Respaldo: {p}")
        print("  Siguiente: python scripts/audit_checkout_sin_pago.py --target " + args.target)
    else:
        print("\n(simulacro) Nada se escribió. Agrega --apply para aplicar.")
    return 0


# --- Rollback ---------------------------------------------------------------

def rollback(call: Callable, args) -> int:
    reps = sorted(BACKUP_DIR.glob(f"checkout_sin_pago_{args.target}_*.json"))
    if args.desde:
        reps = [Path(args.desde)]
    if not reps:
        print(f"✗ No hay respaldo para {args.target} en {BACKUP_DIR}.")
        return 1

    # Reversa COMPUESTA: una segunda aplicación fotografía un estado ya configurado, y
    # si el script creció entre corridas, ningún respaldo suelto tiene el origen completo.
    # Para cada pieza se toma el registro MÁS ANTIGUO, que es el único que vio el estado
    # sin configurar.
    datos: dict[str, Any] = {"vistas": [], "automatizaciones": [], "proveedores": [],
                             "express": [], "metodo": None, "compania": None, "correo": None,
                             "fecha": "varios respaldos"}
    vistos: dict[str, set] = {"vistas": set(), "automatizaciones": set(),
                              "proveedores": set(), "express": set()}
    usados = []
    for p in reps:
        d = json.loads(p.read_text(encoding="utf-8"))
        aporta = False
        for clave, id_key in (("vistas", "clave"), ("automatizaciones", "nombre"),
                              ("proveedores", "id"), ("express", "id")):
            for item in d.get(clave) or []:
                if item[id_key] not in vistos[clave]:
                    vistos[clave].add(item[id_key])
                    datos[clave].append(item)
                    aporta = True
        for clave in ("metodo", "compania", "correo"):
            if datos[clave] is None and d.get(clave):
                datos[clave] = d[clave]
                aporta = True
        if aporta:
            usados.append(f"{p.name} ({d.get('fecha', '?')})")

    print("Respaldos usados para reconstruir el estado original:")
    for u in usados:
        print(f"  · {u}")
    print()

    for v in datos["vistas"]:
        if not v["existia"]:
            print(f"  · vista `{v['clave']}` (id={v['id']}) → se creó aquí, se elimina")
            if args.apply and v["id"]:
                call("ir.ui.view", "unlink", [v["id"]])
                print("    → eliminada")
        else:
            print(f"  · vista `{v['clave']}` (id={v['id']}) → restaurar arch previo")
            if args.apply:
                for lang, vals in v["previo"].items():
                    call("ir.ui.view", "write", [v["id"]],
                         {"arch_db": vals["arch_db"], "active": vals["active"]},
                         context={"lang": lang})
                print("    → restaurada")

    for a in datos["automatizaciones"]:
        if not a["existia"]:
            print(f"  · automatización «{a['nombre']}» (id={a['id']}) → se creó aquí, se elimina")
            if args.apply and a["id"]:
                call("base.automation", "unlink", [a["id"]])
                print("    → eliminada")
        else:
            print(f"  · automatización «{a['nombre']}» ya existía antes: se deja como está")

    for p in datos["proveedores"]:
        print(f"  · proveedor id={p['id']} ({p['rol']}) → restaurar estado y textos")
        if args.apply:
            base = p["previo"].get("en_US", {})
            call("payment.provider", "write", [p["id"]],
                 {k: base[k] for k in ("state", "is_published") if k in base})
            for lang, vals in p["previo"].items():
                campos = {k: vals[k] for k in ("name", "pre_msg", "pending_msg") if k in vals}
                if campos:
                    call("payment.provider", "write", [p["id"]], campos, context={"lang": lang})
            print("    → restaurado")

    for p in datos.get("express", []):
        print(f"  · proveedor id={p['id']} → restaurar pago exprés (estaba activo)")
        if args.apply:
            call("payment.provider", "write", [p["id"]], {"allow_express_checkout": p["previo"]})
            print("    → restaurado")

    if datos.get("metodo"):
        m = datos["metodo"]
        print(f"  · método id={m['id']} → restaurar nombre original")
        if args.apply:
            for lang, vals in m["previo"].items():
                call("payment.method", "write", [m["id"]], {"name": vals["name"]},
                     context={"lang": lang})
            print("    → restaurado")

    if datos.get("carritos") and datos["carritos"]["ids"]:
        # Algunos pudieron confirmarse o borrarse desde entonces: solo los que siguen ahí.
        vivos = call("sale.order", "search", [["id", "in", datos["carritos"]["ids"]]])
        print(f"  · {len(vivos)} carrito(s) → restaurar «Pago en línea = Sí»")
        if args.apply and vivos:
            call("sale.order", "write", vivos, {"require_payment": True})
            print("    → restaurados")

    if datos.get("correo"):
        t = datos["correo"]
        print(f"  · plantilla de correo id={t['id']} → restaurar cuerpo original")
        if args.apply:
            for lang, vals in t["previo"].items():
                call("mail.template", "write", [t["id"]], {"body_html": vals["body_html"]},
                     context={"lang": lang})
            print("    → restaurada")

    if datos.get("compania"):
        c = datos["compania"]
        print(f"  · compañía id={c['id']} → restaurar pay_now_label")
        if args.apply:
            for lang, vals in c["previo"].items():
                call("res.company", "write", [c["id"]], {"pay_now_label": vals["pay_now_label"]},
                     context={"lang": lang})
            print("    → restaurado")

    if not args.apply:
        print("\n(simulacro) Agrega --apply para restaurar.")
    else:
        print("\n✓ Reversa aplicada.")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--target", choices=["test", "prod"], default="test")
    ap.add_argument("--apply", action="store_true", help="Escribe. Sin esto, simulacro.")
    ap.add_argument("--si-produccion", action="store_true", help="Guardarraíl para --target prod")
    ap.add_argument("--rollback", action="store_true", help="Deshace desde el respaldo más reciente")
    ap.add_argument("--desde", help="Ruta a un respaldo específico (con --rollback)")
    args = ap.parse_args()

    load_dotenv(REPO / "analysis" / "supplier-sync" / ".env")
    if args.target == "prod":
        url, db = os.environ["ODOO_URL"].rstrip("/"), os.environ["ODOO_DB"]
        if args.apply and not args.si_produccion:
            print("✗ Para escribir en PRODUCCIÓN agrega --si-produccion (guardarraíl).",
                  file=sys.stderr)
            return 2
    else:
        url = os.environ["ODOO_TEST_URL"].rstrip("/")
        db = url.split("//")[1].split(".")[0]  # el subdominio ES la BD en staging

    call = conectar(url, db, os.environ["ODOO_USER"], os.environ["ODOO_PASSWORD"])
    modo = "APLICAR" if args.apply else "DRY-RUN (no escribe)"
    accion = "ROLLBACK" if args.rollback else "CONFIGURAR"
    print("=" * 78)
    print(f"  {accion} checkout sin pago en línea  [{args.target.upper()}]  ·  {modo}")
    print(f"  {url}  (db={db})")
    print("=" * 78)

    if args.rollback:
        return rollback(call, args)

    langs = idiomas(call)
    print(f"\nIdiomas a escribir: {', '.join(langs)}")
    ref = preflight(call, langs)
    print("✓ Comprobaciones previas: plantillas, métodos, proveedores y campos en su sitio.")
    return aplicar(call, args, ref)


if __name__ == "__main__":
    sys.exit(main())
