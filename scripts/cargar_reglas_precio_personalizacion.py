#!/usr/bin/env python3
"""
Carga las reglas de lista de precios que dan los TRAMOS DE CANTIDAD a los
servicios de personalización, y hace que las demás listas hereden de la
principal.

Paso 5 del reemplazo nativo del motor (ver `specs/personalizacion-nativa.md`).
Es el paso que de verdad valida el diseño: sin estas reglas, un producto con
curva cotiza el precio del primer tramo a cualquier cantidad.

Dos tipos de regla
------------------
1. **Tramos** (74), en la lista principal, una por escalón de cantidad:

       applied_on='1_product' · product_tmpl_id=<el servicio>
       min_quantity=600 · compute_price='fixed' · fixed_price=6.08

   Odoo ordena los items por `min_quantity` descendente dentro del mismo nivel
   de especificidad, así que a 700 piezas gana la regla de 600. El precio del
   PRIMER tramo no lleva regla: vive en el `list_price` del producto.

2. **Delegación** (1 por cada otra lista). Sin ellas, un cliente con lista
   Volant o GMC caería al `list_price` del producto —el precio del tramo 1— y
   se le cobraría de más a cualquier cantidad, porque los tramos solo existen en
   la lista principal:

       applied_on='2_product_category' · categ_id=<Servicios de Personalización>
       compute_price='formula' · base='pricelist' · base_pricelist_id=<principal>
       price_discount=0

   Una regla por categoría es más específica que una global, así que también
   protege a la personalización de descuentos globales (GMC tiene uno al 0%).

Idempotencia: la llave de una regla es
(lista, applied_on, producto|categoría, min_quantity). Lo que ya existe con esos
valores se actualiza si el precio cambió; no se duplica.

    DRY-RUN POR DEFECTO. Sin --apply no escribe nada.

Uso:
    python scripts/cargar_reglas_precio_personalizacion.py --target test
    python scripts/cargar_reglas_precio_personalizacion.py --target test --apply
    python scripts/cargar_reglas_precio_personalizacion.py --target test --smoke
    python scripts/cargar_reglas_precio_personalizacion.py --target test --rollback --apply

`--smoke` crea una cotización desechable, prueba CADA tramo de CADA producto
—en el escalón exacto y justo por debajo— compara contra la hoja y borra la
cotización. Sale con código 1 si un solo precio no cuadra.

Variables de entorno (analysis/supplier-sync/.env):
    ODOO_URL, ODOO_TEST_URL, ODOO_DB, ODOO_USER, ODOO_PASSWORD
"""

from __future__ import annotations

import argparse
import csv
import io
import json
import os
import sys
import xmlrpc.client
from collections import defaultdict
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv

if hasattr(sys.stdout, "buffer"):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

REPO = Path(__file__).resolve().parent.parent
BACKUP_DIR = REPO / "backups"
HOJA_REGLAS = REPO / "analysis" / "costos-personalizacion" / "mapa_2_reglas_precio.csv"
HOJA_PRODS = REPO / "analysis" / "costos-personalizacion" / "mapa_1_productos.csv"
CATEGORIA = "Servicios de Personalización"
LISTA_PRINCIPAL = "Default"


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


def leer(ruta: Path) -> list[dict]:
    if not ruta.exists():
        raise SystemExit(f"✗ No existe {ruta}. Genera la hoja con "
                         f"mapa_servicios_personalizacion.py")
    with ruta.open(encoding="utf-8-sig") as fh:
        return list(csv.DictReader(fh))


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--target", choices=["test", "prod"], default="test")
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--si-produccion", action="store_true")
    ap.add_argument("--smoke", action="store_true", help="Prueba cada tramo con una cotización desechable")
    ap.add_argument("--rollback", action="store_true")
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
    modo = "SMOKE" if args.smoke else ("APLICAR" if args.apply else "DRY-RUN (no escribe)")
    print("=" * 78)
    print(f"  REGLAS DE PRECIO DE PERSONALIZACIÓN  [{args.target.upper()}]  ·  {modo}")
    print(f"  {url}  (db={db})")
    print("=" * 78)

    if args.rollback:
        return rollback(call, args)
    if args.smoke:
        return smoke(call)

    principal = call("product.pricelist", "search_read", [["name", "=", LISTA_PRINCIPAL]],
                     fields=["name", "currency_id"])
    if not principal:
        raise SystemExit(f"✗ No existe la lista «{LISTA_PRINCIPAL}».")
    principal = principal[0]
    otras = [p for p in call("product.pricelist", "search_read", [], fields=["name", "currency_id"])
             if p["id"] != principal["id"]]
    categ_id = uno(call("product.category", "search", [["name", "=", CATEGORIA]]))
    print(f"\nLista principal: «{principal['name']}» ({principal['currency_id'][1]})")
    print(f"Otras listas: {[p['name'] for p in otras]}")

    creadas, actualizadas, iguales = [], [], 0

    # ------------------------------------------------------- 1. TRAMOS ------
    print(f"\n[1] Tramos de cantidad en «{principal['name']}»")
    reglas = leer(HOJA_REGLAS)
    por_sku = defaultdict(list)
    for r in reglas:
        por_sku[r["sku"]].append(r)

    for sku in sorted(por_sku):
        tmpl = call("product.template", "search", [["default_code", "=", sku]])
        if not tmpl:
            print(f"  ✗ {sku}: el producto NO existe en Odoo — corre antes el paso 4")
            return 1
        tmpl_id = uno(tmpl)
        print(f"\n  {sku}")
        for r in sorted(por_sku[sku], key=lambda z: int(z["min_quantity"])):
            mq, precio = int(r["min_quantity"]), float(r["fixed_price"])
            dom = [["pricelist_id", "=", principal["id"]], ["applied_on", "=", "1_product"],
                   ["product_tmpl_id", "=", tmpl_id], ["min_quantity", "=", mq]]
            ex = call("product.pricelist.item", "search_read", dom,
                      fields=["fixed_price", "compute_price"])
            vals = {"pricelist_id": principal["id"], "applied_on": "1_product",
                    "product_tmpl_id": tmpl_id, "min_quantity": mq,
                    "compute_price": "fixed", "fixed_price": precio}
            if not ex:
                print(f"     + min_qty {mq:>6,} → ${precio:>9,.2f}")
                creadas.append({"sku": sku, "min_quantity": mq})
                if args.apply:
                    nid = uno(call("product.pricelist.item", "create", [vals]))
                    creadas[-1]["id"] = nid
            elif abs(ex[0]["fixed_price"] - precio) > 0.005:
                print(f"     ~ min_qty {mq:>6,} → ${ex[0]['fixed_price']:,.2f} ⇒ ${precio:,.2f}")
                actualizadas.append({"id": ex[0]["id"], "sku": sku,
                                     "antes": {"fixed_price": ex[0]["fixed_price"]}})
                if args.apply:
                    call("product.pricelist.item", "write", [ex[0]["id"]], vals)
            else:
                iguales += 1

    # -------------------------------------------------- 2. DELEGACIÓN ------
    print(f"\n[2] Delegación de las otras listas hacia «{principal['name']}»")
    for pl in otras:
        dom = [["pricelist_id", "=", pl["id"]], ["applied_on", "=", "2_product_category"],
               ["categ_id", "=", categ_id]]
        ex = call("product.pricelist.item", "search_read", dom, fields=["base", "base_pricelist_id"])
        vals = {"pricelist_id": pl["id"], "applied_on": "2_product_category",
                "categ_id": categ_id, "compute_price": "formula", "base": "pricelist",
                "base_pricelist_id": principal["id"], "price_discount": 0}
        if not ex:
            print(f"  + «{pl['name']}» ({pl['currency_id'][1]}) → hereda la categoría "
                  f"«{CATEGORIA}» de «{principal['name']}»")
            creadas.append({"lista": pl["name"], "delegacion": True})
            if args.apply:
                creadas[-1]["id"] = uno(call("product.pricelist.item", "create", [vals]))
        else:
            iguales += 1
            print(f"  · «{pl['name']}»: ya delega")

    print("\n" + "-" * 78)
    print(f"  crear: {len(creadas)} · actualizar: {len(actualizadas)} · sin cambio: {iguales}")
    if args.apply:
        BACKUP_DIR.mkdir(exist_ok=True)
        p = BACKUP_DIR / f"reglas_pers_{args.target}_{datetime.now():%Y%m%d_%H%M%S}.json"
        p.write_text(json.dumps({"target": args.target, "fecha": datetime.now().isoformat(timespec="seconds"),
                                 "creadas": creadas, "actualizadas": actualizadas},
                                ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"  Respaldo: {p}")
        print("\n  Ahora corre el smoke test:  --smoke")
    else:
        print("  (simulacro) Agrega --apply para escribir.")
    return 0


def smoke(call) -> int:
    """Prueba CADA tramo de CADA producto contra la hoja, en el escalón exacto y
    justo por debajo — que es donde se ve si el orden de las reglas es correcto."""
    prods = {p["sku"]: p for p in leer(HOJA_PRODS)}
    reglas = defaultdict(list)
    for r in leer(HOJA_REGLAS):
        reglas[r["sku"]].append(r)

    principal = uno(call("product.pricelist", "search", [["name", "=", LISTA_PRINCIPAL]]))
    partner = uno(call("res.partner", "search", [["customer_rank", ">", 0]], limit=1))
    so = uno(call("sale.order", "create", [{"partner_id": partner, "pricelist_id": principal}]))
    print(f"\nCotización desechable id={so} · lista «{LISTA_PRINCIPAL}»\n")

    fallos, probados = [], 0
    for sku in sorted(reglas):
        tramos = sorted(reglas[sku], key=lambda z: int(z["min_quantity"]))
        base = float(prods[sku]["list_price"])
        # (cantidad, precio esperado): el escalón exacto, y uno menos que el primero.
        casos = [(max(1, int(tramos[0]["min_quantity"]) - 1), base)]
        for t in tramos:
            casos.append((int(t["min_quantity"]), float(t["fixed_price"])))
        prod = uno(call("product.product", "search", [["default_code", "=", sku]]))
        linea = []
        for qty, esperado in casos:
            lid = uno(call("sale.order.line", "create",
                           [{"order_id": so, "product_id": prod, "product_uom_qty": qty}]))
            real = call("sale.order.line", "read", [lid], fields=["price_unit"])[0]["price_unit"]
            probados += 1
            ok = abs(real - esperado) < 0.005
            if not ok:
                fallos.append(f"{sku} qty={qty}: esperaba ${esperado:,.2f}, Odoo ${real:,.2f}")
            linea.append(f"{'✓' if ok else '✗'}{qty:,}→${real:,.2f}")
        print(f"  {sku:<32} {' '.join(linea)}")

    call("sale.order", "unlink", [so])
    print(f"\n  (cotización {so} borrada) · {probados} precios probados")
    print("-" * 78)
    if fallos:
        print(f"  ✗ {len(fallos)} PRECIO(S) NO CUADRAN:")
        for f in fallos:
            print(f"      {f}")
        return 1
    print("  ✓ TODOS los tramos cotizan el precio de la matriz.")
    return 0


def rollback(call, args) -> int:
    reps = sorted(BACKUP_DIR.glob(f"reglas_pers_{args.target}_*.json"))
    if not reps:
        print(f"✗ No hay respaldo para {args.target}.")
        return 1
    d = json.loads(reps[-1].read_text(encoding="utf-8"))
    print(f"Respaldo: {reps[-1].name} ({d['fecha']})\n")
    ids = [c["id"] for c in d.get("creadas", []) if c.get("id")]
    print(f"  borrar {len(ids)} regla(s) creada(s)")
    if args.apply and ids:
        call("product.pricelist.item", "unlink", ids)
        print("    → borradas")
    for a in d.get("actualizadas", []):
        print(f"  restaurar regla id={a['id']} ⇒ {a['antes']}")
        if args.apply:
            call("product.pricelist.item", "write", [a["id"]], a["antes"])
    if not args.apply:
        print("\n(simulacro) Agrega --apply para deshacer.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
