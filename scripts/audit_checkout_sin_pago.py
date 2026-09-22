#!/usr/bin/env python3
"""
Verifica, **solo lectura**, que el checkout siga sin cobrar en línea y que el
cobro posterior por link siga disponible.

Existe por un riesgo concreto: el filtro del checkout vive en dos vistas
heredadas de plantillas de Odoo. Si un upgrade las reestructura, Odoo puede
desactivar las nuestras y **la tarjeta reaparecería en el checkout en silencio**
(es el patrón de las tres incidencias de `docs/upgrades/`). Este script lo caza.

Correrlo:
  - después de aplicar `configurar_checkout_sin_pago.py`;
  - como parte del checklist post-upgrade;
  - ante cualquier duda de "¿el cliente puede pagar antes de que yo valide?".

Qué revisa
----------
1. Las plantillas base de Odoo conservan los anclajes del XPath.
2. Las dos vistas propias existen, están activas y filtran en todos los idiomas.
3. Proveedor de solicitud habilitado y publicado, con sus mensajes.
4. Pago contra entrega apagado (confirma pedidos solo).
5. Mercado Pago habilitado, publicado y sin restricción de sitio.
6. El método de la solicitud está renombrado.
7. Las dos automatizaciones declarativas, activas y **sin código** (facturable).
8. Opcional (`--pedido`): descarga el portal del pedido como visitante anónimo y
   comprueba que ofrece tarjeta y NO la opción de solicitud.

Sale con código 1 si algo no cuadra, para poder encadenarlo en el checklist.

Uso:
    python scripts/audit_checkout_sin_pago.py --target test
    python scripts/audit_checkout_sin_pago.py --target prod
    python scripts/audit_checkout_sin_pago.py --target test --pedido 512

Variables de entorno (analysis/supplier-sync/.env):
    ODOO_URL, ODOO_TEST_URL, ODOO_DB, ODOO_USER, ODOO_PASSWORD
"""

from __future__ import annotations

import argparse
import io
import os
import re
import sys
import xmlrpc.client
from pathlib import Path
from typing import Any, Callable

import requests
from dotenv import load_dotenv

if hasattr(sys.stdout, "buffer"):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

REPO = Path(__file__).resolve().parent.parent

VISTA_CHECKOUT_BASE = "website_sale.payment"
VISTA_PORTAL_BASE = "sale.sale_order_portal_pay_modal"
ANCLA_CHECKOUT = 't-set="hide_payment_button"'
ANCLA_PORTAL = 't-call="payment.form"'

CLAVE_VISTA_CHECKOUT = "mozaprint.checkout_solo_solicitud"
CLAVE_VISTA_PORTAL = "mozaprint.portal_sin_solicitud"

METODO_SOLICITUD = "wire_transfer"
METODO_COD = "cash_on_delivery"
NOMBRE_ORIGINAL_METODO = "Wire Transfer"  # si sigue así, no se renombró

AUTO_SIN_COBRO = "Tienda · pedido nace sin cobro en línea"
AUTO_ACTIVIDAD = "Tienda · validar existencias de una solicitud"

# Lo que el filtro debe contener en el arch de cada vista.
FILTRO_CHECKOUT = f"pm.code == '{METODO_SOLICITUD}'"
FILTRO_PORTAL = f"pm.code != '{METODO_SOLICITUD}'"

# Huella del texto del correo al cliente (ver `configurar_checkout_sin_pago.py`).
MARCA_CORREO = {
    "en_US": "No payment has been registered yet",
    "es_419": "Aún no se ha registrado ningún pago",
}


class Reporte:
    """Acumula resultados para decidir el código de salida."""

    def __init__(self) -> None:
        self.fallos = 0
        self.avisos = 0

    def ok(self, texto: str) -> None:
        print(f"  ✓ {texto}")

    def fallo(self, texto: str) -> None:
        self.fallos += 1
        print(f"  ✗ {texto}")

    def aviso(self, texto: str) -> None:
        self.avisos += 1
        print(f"  ⚠ {texto}")


def conectar(url: str, db: str, user: str, pwd: str) -> Callable:
    uid = xmlrpc.client.ServerProxy(f"{url}/xmlrpc/2/common").authenticate(db, user, pwd, {})
    if not uid:
        raise SystemExit(f"✗ Autenticación fallida en {url} (db={db})")
    models = xmlrpc.client.ServerProxy(f"{url}/xmlrpc/2/object")

    def call(model: str, method: str, *args: Any, **kw: Any) -> Any:
        return models.execute_kw(db, uid, pwd, model, method, list(args), kw)

    return call


def idiomas(call: Callable) -> list[str]:
    activos = [l["code"] for l in
               call("res.lang", "search_read", [["active", "=", True]], fields=["code"])]
    return list(dict.fromkeys(["en_US"] + activos))


def rev_plantillas_base(call: Callable, r: Reporte) -> None:
    print("\n[1] Plantillas de Odoo: ¿siguen los anclajes del XPath?")
    for clave, ancla in ((VISTA_CHECKOUT_BASE, ANCLA_CHECKOUT), (VISTA_PORTAL_BASE, ANCLA_PORTAL)):
        vistas = call("ir.ui.view", "search_read",
                      [["key", "=", clave], ["website_id", "=", False]],
                      fields=["id"], context={"lang": "en_US"})
        if not vistas:
            r.fallo(f"`{clave}` no existe")
            continue
        arch = call("ir.ui.view", "read", [vistas[0]["id"]], fields=["arch_db"],
                    context={"lang": "en_US"})[0]["arch_db"] or ""
        if ancla in arch:
            r.ok(f"`{clave}` conserva el anclaje")
        else:
            r.fallo(f"`{clave}` YA NO tiene {ancla} — el XPath de nuestra vista puede fallar")


def rev_vistas_propias(call: Callable, langs: list[str], r: Reporte) -> None:
    print("\n[2] Nuestras vistas: existen, activas y filtrando en todos los idiomas")
    for clave, filtro, padre in ((CLAVE_VISTA_CHECKOUT, FILTRO_CHECKOUT, VISTA_CHECKOUT_BASE),
                                 (CLAVE_VISTA_PORTAL, FILTRO_PORTAL, VISTA_PORTAL_BASE)):
        vistas = call("ir.ui.view", "search_read", [["key", "=", clave]],
                      fields=["id", "active", "inherit_id"], context={"active_test": False})
        if not vistas:
            r.fallo(f"`{clave}` NO EXISTE")
            continue
        v = vistas[0]
        if not v["active"]:
            r.fallo(f"`{clave}` (id={v['id']}) está DESACTIVADA — el filtro no se aplica")
            continue
        if not v["inherit_id"] or not str(v["inherit_id"][1]):
            r.aviso(f"`{clave}` no hereda de ninguna vista")
        faltan = []
        for lang in langs:
            arch = call("ir.ui.view", "read", [v["id"]], fields=["arch_db"],
                        context={"lang": lang})[0]["arch_db"] or ""
            if filtro not in arch:
                faltan.append(lang)
        if faltan:
            r.fallo(f"`{clave}` sin el filtro esperado en: {', '.join(faltan)}")
        else:
            r.ok(f"`{clave}` (id={v['id']}) activa y con el filtro en {', '.join(langs)}")


def rev_proveedores(call: Callable, r: Reporte) -> None:
    print("\n[3] Proveedores de pago")
    ctx = {"active_test": False}
    provs = call("payment.provider", "search_read", [["code", "=", "custom"]],
                 fields=["id", "name", "custom_mode", "state", "is_published",
                         "pre_msg", "pending_msg"], context=ctx)
    sol = next((p for p in provs if p["custom_mode"] == METODO_SOLICITUD), None)
    cod = next((p for p in provs if p["custom_mode"] == METODO_COD), None)

    if not sol:
        r.fallo("no existe el proveedor de la solicitud (custom/wire_transfer)")
    elif sol["state"] != "enabled" or not sol["is_published"]:
        r.fallo(f"solicitud id={sol['id']}: estado={sol['state']}, publicado={sol['is_published']}"
                " — el checkout se quedaría SIN opciones")
    else:
        r.ok(f"solicitud id={sol['id']} «{sol['name']}» habilitada y publicada")
        if not (sol["pre_msg"] or "").strip():
            r.aviso("el proveedor de solicitud no tiene mensaje de ayuda (pre_msg)")

    if cod and cod["state"] != "disabled":
        r.fallo(f"contra entrega id={cod['id']} está {cod['state']}: confirmaría pedidos solo")
    elif cod:
        r.ok("contra entrega apagado")

    mp = call("payment.provider", "search_read", [["code", "=", "mercado_pago"]],
              fields=["id", "state", "is_published", "website_id"], context=ctx)
    if not mp:
        r.aviso("no hay proveedor Mercado Pago en esta base")
    elif mp[0]["state"] == "disabled":
        r.aviso("Mercado Pago deshabilitado: el cobro posterior no funcionará "
                "(normal en la base de test, que va neutralizada)")
    elif not mp[0]["is_published"]:
        r.fallo("Mercado Pago no está publicado: no se vería en el portal ni en el link")
    elif mp[0]["website_id"]:
        r.fallo(f"Mercado Pago está restringido al sitio {mp[0]['website_id']}: "
                "no aparecería en pedidos de otro sitio")
    else:
        r.ok("Mercado Pago habilitado, publicado y sin restricción de sitio")

    # El botón de pago exprés vive en el carrito, no en `/shop/payment`: ninguna de
    # nuestras vistas lo filtra, así que se cierra apagando la opción en el proveedor.
    expres = call("payment.provider", "search_read",
                  [["allow_express_checkout", "=", True], ["state", "!=", "disabled"]],
                  fields=["id", "name"], context={"active_test": False})
    if expres:
        r.fallo(f"con pago exprés activo: {[p['name'] for p in expres]} — el carrito mostraría "
                "un botón que cobra saltándose el checkout")
    else:
        r.ok("ningún proveedor con pago exprés: el carrito no puede cobrar")


def rev_metodo(call: Callable, langs: list[str], r: Reporte) -> None:
    print("\n[4] Nombre del método que ve el cliente")
    met = call("payment.method", "search_read", [["code", "=", METODO_SOLICITUD]],
               fields=["id", "active"], context={"active_test": False})
    if not met:
        r.fallo(f"no existe el método `{METODO_SOLICITUD}`")
        return
    mid = met[0]["id"]
    if not met[0]["active"]:
        r.fallo(f"el método `{METODO_SOLICITUD}` está inactivo: no se ofrecería en el checkout")
    for lang in langs:
        nombre = call("payment.method", "read", [mid], fields=["name"],
                      context={"lang": lang, "active_test": False})[0]["name"]
        if nombre == NOMBRE_ORIGINAL_METODO:
            r.fallo(f"[{lang}] el método sigue llamándose «{nombre}»: confunde en el checkout")
        else:
            r.ok(f"[{lang}] «{nombre}»")


def rev_automatizaciones(call: Callable, r: Reporte) -> None:
    print("\n[5] Automatizaciones declarativas")
    esperado = {
        AUTO_SIN_COBRO: ("on_create", "object_write"),
        AUTO_ACTIVIDAD: ("on_state_set", "next_activity"),
    }
    # En saas~19.3 la acción vive en `ir.actions.server`, enlazada por action_server_ids.
    for nombre, (trigger, estado) in esperado.items():
        autos = call("base.automation", "search_read", [["name", "=", nombre]],
                     fields=["id", "active", "trigger", "filter_domain", "action_server_ids"],
                     context={"active_test": False})
        if not autos:
            r.fallo(f"falta la automatización «{nombre}»")
            continue
        a = autos[0]
        if not a["active"]:
            r.fallo(f"«{nombre}» (id={a['id']}) está DESACTIVADA")
            continue
        if a["trigger"] != trigger:
            r.fallo(f"«{nombre}»: disparador={a['trigger']} (esperado {trigger})")
            continue
        if "website_id" not in (a["filter_domain"] or ""):
            r.fallo(f"«{nombre}»: el filtro no limita a pedidos de la tienda "
                    f"({a['filter_domain']}) — afectaría cotizaciones del backend")
            continue
        if not a["action_server_ids"]:
            r.fallo(f"«{nombre}» no tiene ninguna acción asociada: no hace nada")
            continue
        acciones = call("ir.actions.server", "read", a["action_server_ids"],
                        fields=["state", "update_path", "activity_summary"])
        estados = [ac["state"] for ac in acciones]
        if estado not in estados:
            r.fallo(f"«{nombre}»: acciones={estados} (esperada {estado})")
            continue
        detalle = next((ac["update_path"] or ac["activity_summary"] or "" for ac in acciones
                        if ac["state"] == estado), "")
        r.ok(f"«{nombre}» activa, {a['trigger']} → {estado} ({detalle}), solo tienda")

    con_codigo = call("ir.actions.server", "search_read",
                      [["state", "=", "code"], ["usage", "=", "base_automation"]],
                      fields=["id", "name"], context={"active_test": False})
    if con_codigo:
        r.aviso(f"hay {len(con_codigo)} automatización(es) con código (facturables): "
                f"{[a['name'] for a in con_codigo]}")
    else:
        r.ok("ninguna automatización con código: 0 líneas facturables")


def rev_correo(call: Callable, langs: list[str], r: Reporte) -> None:
    print("\n[6] Correo al cliente: la rama del pago pendiente")
    d = call("ir.model.data", "search_read",
             [["model", "=", "mail.template"], ["module", "=", "sale"],
              ["name", "=", "mail_template_sale_payment_executed"]], fields=["res_id"])
    if not d:
        r.aviso("no existe la plantilla de estado de pago")
        return
    # Ojo: al reestructurar la plantilla, Odoo deja un solo cuerpo para todos los
    # idiomas (el último escrito). Por eso basta con encontrar cualquiera de las huellas.
    for lang in langs:
        cuerpo = call("mail.template", "read", [d[0]["res_id"]], fields=["body_html"],
                      context={"lang": lang})[0]["body_html"] or ""
        puesto = [l for l, marca in MARCA_CORREO.items() if marca in cuerpo]
        if puesto:
            r.ok(f"[{lang}] el correo habla de una solicitud recibida (en {', '.join(puesto)})")
        else:
            r.fallo(f"[{lang}] el correo volvió al texto de Odoo: le diría al cliente que tiene "
                    "un pago pendiente que nunca hizo")


def rev_portal_http(call: Callable, url: str, pedido_id: int, r: Reporte) -> None:
    print(f"\n[7] Portal del pedido {pedido_id} como visitante anónimo")
    datos = call("sale.order", "read", [pedido_id],
                 fields=["name", "state", "access_token", "require_payment", "website_id"])
    if not datos:
        r.fallo(f"no existe el pedido {pedido_id}")
        return
    so = datos[0]
    if not so["access_token"]:
        r.fallo(f"{so['name']} no tiene token de acceso; ábrelo una vez en el portal")
        return

    destino = f"{url}/my/orders/{pedido_id}?access_token={so['access_token']}&payment_amount=1"
    try:
        resp = requests.get(destino, timeout=30)
    except requests.RequestException as exc:
        r.fallo(f"no se pudo abrir el portal: {exc}")
        return
    if resp.status_code != 200:
        r.fallo(f"el portal respondió {resp.status_code}")
        return

    # Se leen los métodos realmente pintados, sin depender de un proveedor concreto:
    # en test suele ser `demo`; en producción, `card` de Mercado Pago.
    metodos = sorted(set(re.findall(r'data-payment-method-code="([^"]+)"', resp.text)))
    otros = [m for m in metodos if m != METODO_SOLICITUD]

    print(f"  pedido {so['name']} · estado={so['state']} · pago en línea={so['require_payment']}")
    print(f"  métodos ofrecidos: {', '.join(metodos) if metodos else '(ninguno)'}")
    if METODO_SOLICITUD in metodos:
        r.fallo("el portal ofrece la opción de SOLICITUD: la Vista B no está filtrando")
    else:
        r.ok("el portal no ofrece la opción de solicitud")
    if otros:
        r.ok(f"el portal ofrece cobro en línea ({', '.join(otros)}): el link de pago funcionará")
    else:
        r.aviso("el portal no ofrece ningún medio de cobro: revisa que haya un proveedor "
                "habilitado y publicado, y que el pedido no esté vencido")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--target", choices=["test", "prod"], default="prod")
    ap.add_argument("--pedido", type=int, help="Id de un pedido para probar el portal por HTTP")
    args = ap.parse_args()

    load_dotenv(REPO / "analysis" / "supplier-sync" / ".env")
    if args.target == "prod":
        url, db = os.environ["ODOO_URL"].rstrip("/"), os.environ["ODOO_DB"]
    else:
        url = os.environ["ODOO_TEST_URL"].rstrip("/")
        db = url.split("//")[1].split(".")[0]

    call = conectar(url, db, os.environ["ODOO_USER"], os.environ["ODOO_PASSWORD"])
    print("=" * 78)
    print(f"  AUDITORÍA checkout sin pago en línea  [{args.target.upper()}]  ·  solo lectura")
    print(f"  {url}  (db={db})")
    print("=" * 78)

    r = Reporte()
    langs = idiomas(call)
    rev_plantillas_base(call, r)
    rev_vistas_propias(call, langs, r)
    rev_proveedores(call, r)
    rev_metodo(call, langs, r)
    rev_automatizaciones(call, r)
    rev_correo(call, langs, r)
    if args.pedido:
        rev_portal_http(call, url, args.pedido, r)
    else:
        print("\n[7] Portal por HTTP: omitido (agrega --pedido <id> para probarlo)")

    print("\n" + "=" * 78)
    if r.fallos:
        print(f"  ✗ {r.fallos} fallo(s) y {r.avisos} aviso(s). El checkout PUEDE estar cobrando.")
        return 1
    print(f"  ✓ Todo en orden ({r.avisos} aviso/s).")
    print("  El checkout por navegador se prueba a mano: no hay forma fiable de simular")
    print("  el carrito y la dirección desde un script.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
