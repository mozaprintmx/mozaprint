#!/usr/bin/env python3
"""
Crea la plantilla de cotización con las secciones «Producto» y «Personalización».

Paso 6 del reemplazo nativo del motor (ver `specs/personalizacion-nativa.md`).

El motor retirado organizaba la cotización en esas dos secciones por código. Una
`sale.order.template` hace lo mismo siendo **dato**: el vendedor la elige al
crear la cotización y las secciones ya están puestas. Ahorra dos clics por
cotización y, sobre todo, hace que todas salgan con la misma estructura.

No lleva productos: el físico y el servicio cambian en cada venta. Solo el
esqueleto.

    DRY-RUN POR DEFECTO. Sin --apply no escribe nada.

Uso:
    python scripts/crear_plantilla_cotizacion.py --target test
    python scripts/crear_plantilla_cotizacion.py --target test --apply
    python scripts/crear_plantilla_cotizacion.py --target test --probar
    python scripts/crear_plantilla_cotizacion.py --target prod --apply --si-produccion

`--probar` crea una cotización desechable APLICANDO la plantilla, verifica que
las secciones aparezcan y la borra.

Variables de entorno (analysis/supplier-sync/.env):
    ODOO_URL, ODOO_TEST_URL, ODOO_DB, ODOO_USER, ODOO_PASSWORD
"""

from __future__ import annotations

import argparse
import io
import os
import sys
import xmlrpc.client
from pathlib import Path

from dotenv import load_dotenv

if hasattr(sys.stdout, "buffer"):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

REPO = Path(__file__).resolve().parent.parent
PLANTILLA = "Cotización con personalización"
SECCIONES = ["Producto", "Personalización"]
# Vigencia de la cotización. El equipo maneja 7-15 días (ver docs/glossary.md).
DIAS_VIGENCIA = 15


def conectar(url: str, db: str, user: str, pwd: str):
    uid = xmlrpc.client.ServerProxy(f"{url}/xmlrpc/2/common").authenticate(db, user, pwd, {})
    if not uid:
        raise SystemExit(f"✗ Autenticación fallida en {url} (db={db})")
    models = xmlrpc.client.ServerProxy(f"{url}/xmlrpc/2/object")

    def call(model, method, *args, **kw):
        return models.execute_kw(db, uid, pwd, model, method, list(args), kw)

    return call


def uno(r):
    return r[0] if isinstance(r, list) and r else r


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--target", choices=["test", "prod"], default="test")
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--si-produccion", action="store_true")
    ap.add_argument("--probar", action="store_true",
                    help="Cotización desechable que aplica la plantilla y se borra")
    args = ap.parse_args()

    load_dotenv(REPO / "analysis" / "supplier-sync" / ".env")
    if args.target == "prod":
        url, db = os.environ["ODOO_URL"].rstrip("/"), os.environ["ODOO_DB"]
        if args.apply and not args.si_produccion:
            print("✗ Para escribir en PRODUCCIÓN agrega --si-produccion.", file=sys.stderr)
            return 2
    else:
        url = os.environ["ODOO_TEST_URL"].rstrip("/")
        db = url.split("//")[1].split(".")[0]

    call = conectar(url, db, os.environ["ODOO_USER"], os.environ["ODOO_PASSWORD"])
    print("=" * 78)
    print(f"  PLANTILLA DE COTIZACIÓN  [{args.target.upper()}]  ·  "
          f"{'PROBAR' if args.probar else ('APLICAR' if args.apply else 'DRY-RUN')}")
    print(f"  {url}  (db={db})")
    print("=" * 78)

    if args.probar:
        return probar(call, url)

    ex = call("sale.order.template", "search_read", [["name", "=", PLANTILLA]],
              fields=["name", "number_of_days"], context={"active_test": False})
    lineas = [(0, 0, {"display_type": "line_section", "name": s, "sequence": i * 10})
              for i, s in enumerate(SECCIONES)]
    vals = {"name": PLANTILLA, "number_of_days": DIAS_VIGENCIA,
            "sale_order_template_line_ids": lineas}

    if ex:
        tid = ex[0]["id"]
        actuales = call("sale.order.template.line", "search_read",
                        [["sale_order_template_id", "=", tid]],
                        fields=["name", "display_type"], order="sequence,id")
        nombres = [a["name"] for a in actuales]
        print(f"\n  · ya existe (id={tid}) con secciones: {nombres}")
        if nombres == SECCIONES:
            print("  ✓ sin cambios")
            return 0
        print(f"  ~ se rehacen las líneas ⇒ {SECCIONES}")
        if args.apply:
            call("sale.order.template", "write", [tid], vals)
            print("     → escrito")
    else:
        print(f"\n  + CREAR «{PLANTILLA}»  ·  vigencia {DIAS_VIGENCIA} días")
        for s in SECCIONES:
            print(f"       ── sección: {s}")
        if args.apply:
            tid = uno(call("sale.order.template", "create", [vals]))
            print(f"     → creada id={tid}")

    print("\n" + "-" * 78)
    if args.apply:
        print("  ✓ Listo. Pruébala con:  --probar")
        print(f"  El vendedor la elige en el campo «Plantilla de cotización» al crear una.")
    else:
        print("  (simulacro) Agrega --apply para escribir.")
    return 0


def probar(call, url: str) -> int:
    tid = uno(call("sale.order.template", "search", [["name", "=", PLANTILLA]]))
    if not tid:
        print("✗ La plantilla no existe todavía. Córrelo con --apply primero.")
        return 1
    partner = uno(call("res.partner", "search", [["customer_rank", ">", 0]], limit=1))
    so = uno(call("sale.order", "create", [{"partner_id": partner}]))
    # Elegir la plantilla NO vuelca las secciones por sí solo: el volcado vive en
    # un onchange, que el cliente web dispara al seleccionarla. Un `write` por
    # RPC se lo salta. Se llama al `onchange` genérico —lo mismo que hace la
    # interfaz— para probar de verdad lo que verá el vendedor.
    #
    # ⚠️ No usar métodos privados a tientas para forzarlo: en una versión previa
    # de esta prueba se llamó `action_confirm` por descarte y dejó una cotización
    # confirmada que ya no se podía borrar.
    r = call("sale.order", "onchange", [so],
             {"partner_id": partner, "sale_order_template_id": tid},
             ["sale_order_template_id"],
             {"order_line": {}, "sale_order_template_id": {}})
    propuestas = (r or {}).get("value", {}).get("order_line", [])
    call("sale.order", "unlink", [so])

    # El onchange devuelve los comandos con los valores VACÍOS: el cliente web
    # resuelve el contenido de cada línea en una llamada aparte. Así que por RPC
    # se puede comprobar CUÁNTAS líneas propone, no cuáles. El QUÉ se verifica
    # contra la plantilla, que es su fuente.
    plantilla = call("sale.order.template.line", "search_read",
                     [["sale_order_template_id", "=", tid]],
                     fields=["name", "display_type"], order="sequence,id")
    print(f"\n  [1] Contenido de la plantilla (id={tid})")
    for x in plantilla:
        print(f"        {'──' if x['display_type'] == 'line_section' else '  '} {x['name']}")
    print(f"\n  [2] Al elegirla en una cotización, el onchange propone "
          f"{len(propuestas)} línea(s)")

    secciones = [x["name"] for x in plantilla if x["display_type"] == "line_section"]
    ok = secciones == SECCIONES and len(propuestas) == len(plantilla)
    print("\n" + "-" * 78)
    if ok:
        print(f"  ✓ La plantilla tiene las secciones {SECCIONES} y se vuelcan las "
              f"{len(propuestas)} al elegirla.")
        print("    El aspecto final se confirma abriendo una cotización en la interfaz.")
        return 0
    print(f"  ✗ Plantilla={secciones} · propuestas={len(propuestas)} de {len(plantilla)}")
    return 1


if __name__ == "__main__":
    sys.exit(main())
