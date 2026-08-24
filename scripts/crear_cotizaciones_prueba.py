#!/usr/bin/env python3
"""
Crea en TEST dos cotizaciones PERMANENTES para revisar el diseño de
personalización con los ojos, no solo por consola.

Las hace falta porque el smoke test de `cargar_reglas_precio_personalizacion.py`
crea su cotización y **la borra al terminar**: prueba los precios pero no deja
nada que abrir. Estas se quedan.

    ZZ PRUEBA TRAMOS         una línea por cada producto con curva de cantidad,
                             en un escalón intermedio. Sirve para verificar a
                             ojo que Odoo aplica el tramo correcto.

    ZZ EJEMPLO COTIZACIÓN    cómo se ve una cotización real, con las secciones
                             «Producto» y «Personalización», un caso por tinta
                             y su línea de setup.

Es idempotente: si ya existen (por el nombre del cliente de prueba), las borra y
las vuelve a crear, para que siempre reflejen el estado actual de los precios.

⚠️ SOLO PARA TEST. Se niega a correr contra producción.

Uso:
    python scripts/crear_cotizaciones_prueba.py --target test
    python scripts/crear_cotizaciones_prueba.py --target test --apply
    python scripts/crear_cotizaciones_prueba.py --target test --borrar --apply

Variables de entorno (analysis/supplier-sync/.env):
    ODOO_TEST_URL, ODOO_USER, ODOO_PASSWORD
"""

from __future__ import annotations

import argparse
import csv
import io
import os
import sys
import xmlrpc.client
from collections import defaultdict
from pathlib import Path

from dotenv import load_dotenv

if hasattr(sys.stdout, "buffer"):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

REPO = Path(__file__).resolve().parent.parent
ANALISIS = REPO / "analysis" / "costos-personalizacion"
CLIENTE = "ZZ PRUEBA PERSONALIZACIÓN"


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


def leer(nombre: str) -> list[dict]:
    with (ANALISIS / nombre).open(encoding="utf-8-sig") as fh:
        return list(csv.DictReader(fh))


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--target", choices=["test"], default="test",
                    help="Solo test: estas cotizaciones no deben existir en producción")
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--borrar", action="store_true", help="Solo borra las de prueba")
    args = ap.parse_args()

    load_dotenv(REPO / "analysis" / "supplier-sync" / ".env")
    url = os.environ["ODOO_TEST_URL"].rstrip("/")
    db = url.split("//")[1].split(".")[0]
    call = conectar(url, db, os.environ["ODOO_USER"], os.environ["ODOO_PASSWORD"])
    print("=" * 78)
    print(f"  COTIZACIONES DE PRUEBA  [TEST]  ·  "
          f"{'BORRAR' if args.borrar else ('APLICAR' if args.apply else 'DRY-RUN')}")
    print(f"  {url}")
    print("=" * 78)

    # Cliente dedicado, para que nunca se mezclen con cotizaciones reales.
    partner = uno(call("res.partner", "search", [["name", "=", CLIENTE]]))
    if not partner:
        print(f"\n  cliente «{CLIENTE}» no existe → se creará")
        if args.apply:
            partner = uno(call("res.partner", "create", [{"name": CLIENTE, "customer_rank": 1}]))
            print(f"     creado id={partner}")
    else:
        print(f"\n  cliente «{CLIENTE}» id={partner}")

    viejas = call("sale.order", "search", [["partner_id", "=", partner]]) if partner else []
    if viejas:
        print(f"  cotizaciones previas a reemplazar: {viejas}")
        if args.apply:
            call("sale.order", "unlink", viejas)
    if args.borrar:
        print("\n  (solo borrado)" if args.apply else "\n  (simulacro) Agrega --apply para borrar.")
        return 0

    prods = {p["sku"]: p for p in leer("mapa_1_productos.csv")}
    reglas = defaultdict(list)
    for r in leer("mapa_2_reglas_precio.csv"):
        reglas[r["sku"]].append(r)
    setups = {s["sku"]: s for s in leer("mapa_3_setups.csv")}

    def prod_id(sku):
        return uno(call("product.product", "search", [["default_code", "=", sku]]))

    # ------------------------------------------------ 1. PRUEBA DE TRAMOS ---
    print(f"\n[1] «ZZ PRUEBA TRAMOS» — los {len(reglas)} productos con curva")
    lineas, esperados = [], []
    for sku in sorted(reglas):
        tramos = sorted(reglas[sku], key=lambda z: int(z["min_quantity"]))
        # Un escalón intermedio: el de en medio de la curva, que es donde un
        # error de ordenamiento de reglas se notaría.
        t = tramos[len(tramos) // 2]
        qty, esperado = int(t["min_quantity"]), float(t["fixed_price"])
        pid = prod_id(sku)
        if not pid:
            print(f"  ✗ {sku} no existe en Odoo")
            continue
        lineas.append((0, 0, {"product_id": pid, "product_uom_qty": qty}))
        esperados.append((sku, qty, esperado))
        print(f"  · {sku:<32} qty {qty:>6,} → esperado ${esperado:>9,.2f}")

    if args.apply:
        so1 = uno(call("sale.order", "create", [{"partner_id": partner, "order_line": lineas}]))
        ls = call("sale.order.line", "search_read", [["order_id", "=", so1]],
                  fields=["product_id", "product_uom_qty", "price_unit"], order="sequence,id")
        malos = 0
        for (sku, qty, esp), ln in zip(esperados, ls):
            if abs(ln["price_unit"] - esp) > 0.005:
                malos += 1
                print(f"  ✗ {sku}: ${ln['price_unit']:,.2f} ≠ ${esp:,.2f}")
        nombre = call("sale.order", "read", [so1], fields=["name"])[0]["name"]
        print(f"  → creada {nombre} (id={so1}) · {len(ls)} líneas · "
              f"{'TODAS CUADRAN' if not malos else f'{malos} NO cuadran'}")

    # ------------------------------------------- 2. EJEMPLO DE COTIZACIÓN ---
    print("\n[2] «ZZ EJEMPLO COTIZACIÓN» — cómo se ve una real, con secciones")
    fisico = call("product.product", "search_read",
                  [["is_published", "=", True], ["sale_ok", "=", True]],
                  fields=["name", "default_code"], limit=1, order="id desc")
    if not fisico:
        print("  ✗ no encontré un producto físico publicado")
        return 1
    fisico = fisico[0]
    sku_tinta = "PERS-SERI-INN-TEXTIHIELE-LOTE"     # por tinta, el caso delicado
    sku_setup = next(iter(setups))                   # una línea de setup
    guion = [
        ("sec", "Producto"),
        ("prod", fisico["id"], 500, f"{fisico['name'][:40]} — 500 pzas"),
        ("sec", "Personalización"),
        ("pers", prod_id(sku_tinta), 2, "2 tintas (la cantidad son TINTAS, no piezas)"),
        ("pers", prod_id(sku_setup), 1, "setup, cantidad 1"),
    ]
    # Las líneas se crean UNA A UNA sobre un pedido ya existente: creándolas en
    # bloque dentro del `create` del pedido, Odoo no precalcula el `name` desde
    # el producto y falla con «Missing required field 'Description'».
    so2 = uno(call("sale.order", "create", [{"partner_id": partner}])) if args.apply else None
    for g in guion:
        if g[0] == "sec":
            print(f"  ── sección: {g[1]}")
            if args.apply:
                call("sale.order.line", "create",
                     [{"order_id": so2, "display_type": "line_section", "name": g[1]}])
        else:
            print(f"     línea: qty {g[2]:<5} {g[3]}")
            if args.apply:
                call("sale.order.line", "create",
                     [{"order_id": so2, "product_id": g[1], "product_uom_qty": g[2]}])

    if args.apply:
        d = call("sale.order", "read", [so2], fields=["name", "amount_total"])[0]
        print(f"  → creada {d['name']} (id={so2}) · total ${d['amount_total']:,.2f}")
        print(f"\n  Ábrelas en:  {url}/odoo/sales")
        print(f"  PDF directo: {url}/report/pdf/sale.report_saleorder/{so2}")
    else:
        print("\n  (simulacro) Agrega --apply para crearlas.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
