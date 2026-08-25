#!/usr/bin/env python3
"""
Une la matriz de costos con los productos de servicio: cada tarifa muestra el
SKU que hay que teclear en la cotización.

Paso 7 del reemplazo nativo del motor (ver `specs/personalizacion-nativa.md`).

El problema que resuelve
-----------------------
Hoy son dos pantallas sin puente. El vendedor consulta la tarifa en
**Ventas → Configuración → Costos de personalización**, y luego tiene que
adivinar cuál de los 53 productos le corresponde. Con esto, la propia fila de la
matriz trae el código.

Crea un campo `x_sku_servicio` de tipo **char** — un dato, no un campo calculado:
Odoo **no lo factura**. Lo llena leyendo la hoja `mapa_1_productos.csv`, que trae
la columna `llave` con la combinación (técnica, proveedor, alcance, área,
unidad) que originó cada producto. Todas las filas de tramo de una misma
combinación reciben el mismo SKU.

Es re-ejecutable: cuando se agreguen tarifas nuevas y se regenere la hoja, basta
correrlo otra vez.

    DRY-RUN POR DEFECTO. Sin --apply no escribe nada.

Uso:
    python scripts/enlazar_matriz_servicios.py --target test
    python scripts/enlazar_matriz_servicios.py --target test --apply
    python scripts/enlazar_matriz_servicios.py --target prod --apply --si-produccion

Variables de entorno (analysis/supplier-sync/.env):
    ODOO_URL, ODOO_TEST_URL, ODOO_DB, ODOO_USER, ODOO_PASSWORD
"""

from __future__ import annotations

import argparse
import csv
import io
import os
import re
import sys
import xmlrpc.client
from pathlib import Path

from dotenv import load_dotenv

if hasattr(sys.stdout, "buffer"):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

REPO = Path(__file__).resolve().parent.parent
HOJA = REPO / "analysis" / "costos-personalizacion" / "mapa_1_productos.csv"
MODELO = "x_costo_personalizacion"
CAMPO = "x_sku_servicio"
ETIQUETA = "SKU del servicio"
AYUDA = ("Código del producto de servicio que corresponde a esta tarifa. Es lo que "
         "se teclea en la línea de la cotización. Lo llena "
         "scripts/enlazar_matriz_servicios.py desde la hoja de mapeo; no se edita "
         "a mano.")


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


def idiomas(call) -> list[str]:
    """`arch_db` es traducido: se escribe en todos, empezando por el origen."""
    act = [l["code"] for l in call("res.lang", "search_read", [["active", "=", True]],
                                   fields=["code"])]
    return list(dict.fromkeys(["en_US"] + act))


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--target", choices=["test", "prod"], default="test")
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--si-produccion", action="store_true")
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
    print(f"  ENLAZAR MATRIZ ↔ SERVICIOS  [{args.target.upper()}]  ·  "
          f"{'APLICAR' if args.apply else 'DRY-RUN'}")
    print(f"  {url}  (db={db})")
    print("=" * 78)

    # ------------------------------------------------------ 1. EL CAMPO -----
    print(f"\n[1] Campo {CAMPO} en {MODELO}")
    campos = call(MODELO, "fields_get", [], attributes=["string"])
    if CAMPO in campos:
        print(f"  · ya existe")
    else:
        modelo_id = uno(call("ir.model", "search", [["model", "=", MODELO]]))
        print(f"  + CREAR char «{ETIQUETA}»  (dato simple, NO calculado → no se factura)")
        if args.apply:
            fid = uno(call("ir.model.fields", "create", [{
                "name": CAMPO, "model_id": modelo_id, "model": MODELO,
                "field_description": ETIQUETA, "ttype": "char",
                "state": "manual", "help": AYUDA,
            }]))
            print(f"     → creado id={fid}")

    # ------------------------------------------------- 2. EN LA VISTA -------
    print(f"\n[2] Mostrarlo en la lista de la matriz")
    vista = call("ir.ui.view", "search_read",
                 [["model", "=", MODELO], ["type", "=", "list"]],
                 fields=["name"], limit=1, context={"active_test": False})
    if not vista:
        print("  ✗ no encontré la vista de lista de la matriz")
    else:
        vid = vista[0]["id"]
        langs = idiomas(call)
        for lang in langs:
            arch = call("ir.ui.view", "read", [vid], fields=["arch_db"],
                        context={"lang": lang})[0]["arch_db"] or ""
            if CAMPO in arch:
                print(f"  · [{lang}] ya está en la vista")
                continue
            # Se inserta después del alcance: es la columna con la que el
            # vendedor identifica la fila, así que el SKU queda a su lado.
            ancla = '<field name="x_alcance_producto"'
            i = arch.find(ancla)
            if i < 0:
                print(f"  ✗ [{lang}] no encontré el ancla {ancla}")
                continue
            fin = arch.find("/>", i) + 2
            nuevo = (arch[:fin] + f'\n                <field name="{CAMPO}" '
                     f'optional="show"/>' + arch[fin:])
            print(f"  + [{lang}] insertar la columna tras «Alcance»")
            if args.apply:
                call("ir.ui.view", "write", [vid], {"arch_db": nuevo},
                     context={"lang": lang})
                print("     → escrito")

    # -------------------------------------------------- 3. LOS DATOS --------
    print(f"\n[3] Llenar el SKU en cada tarifa")
    if not HOJA.exists():
        print(f"  ✗ falta {HOJA}")
        return 1
    with HOJA.open(encoding="utf-8-sig") as fh:
        por_llave = {f["llave"]: f["sku"] for f in csv.DictReader(fh) if f.get("llave")}
    print(f"  hoja: {len(por_llave)} combinaciones")

    tarifas = call(MODELO, "search_read", [["x_activa", "=", True]],
                   fields=["x_tecnica_id", "x_proveedor_id", "x_alcance_producto",
                           "x_area_from_cm2", "x_area_to_cm2", "x_unidad_cobro"]
                          + ([CAMPO] if CAMPO in campos else []))
    puestos, iguales, huerfanas = 0, 0, []
    for t in tarifas:
        llave = (f"{t['x_tecnica_id'][0]}|{t['x_proveedor_id'][0]}|"
                 f"{t['x_alcance_producto'] or ''}|{t['x_area_from_cm2']:g}|"
                 f"{t['x_area_to_cm2']:g}|{t['x_unidad_cobro']}")
        sku = por_llave.get(llave)
        if not sku:
            huerfanas.append(t["id"])
            continue
        if t.get(CAMPO) == sku:
            iguales += 1
            continue
        puestos += 1
        if args.apply:
            call(MODELO, "write", [t["id"]], {CAMPO: sku})

    print(f"  tarifas activas: {len(tarifas)}")
    print(f"     a escribir : {puestos}")
    print(f"     ya correctas: {iguales}")
    if huerfanas:
        print(f"  ⚠ {len(huerfanas)} tarifa(s) sin producto que las represente "
              f"(ids {huerfanas[:8]}{'…' if len(huerfanas) > 8 else ''})")
        print("     Suele significar que la matriz cambió y falta regenerar la hoja.")

    print("\n" + "-" * 78)
    if args.apply:
        print("  ✓ Listo. La matriz ya muestra el SKU de cada tarifa.")
        print("    Ventas → Configuración → Costos de personalización")
    else:
        print("  (simulacro) Agrega --apply para escribir.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
