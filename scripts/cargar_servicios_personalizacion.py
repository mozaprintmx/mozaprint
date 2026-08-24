#!/usr/bin/env python3
"""
Carga en Odoo los productos de servicio de personalización desde la hoja revisada.

Paso 4 del reemplazo nativo del motor (ver `specs/personalizacion-nativa.md`).
Lee `analysis/costos-personalizacion/mapa_1_productos.csv` — la hoja que genera
`mapa_servicios_personalizacion.py` y que JC revisó — y crea o actualiza un
`product.template` por fila.

Es IDEMPOTENTE: la llave es el `default_code` (SKU). Lo que ya existe y coincide
se deja igual; lo que difiere se actualiza campo por campo, reportando el cambio.

Qué escribe en cada producto
----------------------------
    default_code          el SKU de la hoja
    name                  «Técnica [POR TINTA] · Alcance · Proveedor (…)»
    description_sale      baja sola a la línea de la cotización y al PDF
    type                  'service'
    list_price            costo del primer tramo × markup
    standard_price        costo del proveedor → Odoo calcula el margen solo
    categ_id              «Servicios de Personalización»
    sale_ok / purchase_ok True / False
    is_published          False — no van al catálogo público
    sale_line_warn_msg    aviso interno al elegirlo en la línea
    x_es_servicio_personalizacion / x_tecnica_servicio_id

Los TRAMOS de cantidad NO se cargan aquí: son reglas de lista de precios y van
en el paso 5. Este script solo pone el precio del primer tramo.

    DRY-RUN POR DEFECTO. Sin --apply no escribe nada.

Uso:
    python scripts/cargar_servicios_personalizacion.py --target test
    python scripts/cargar_servicios_personalizacion.py --target test --filtro PERS-LASER-INN
    python scripts/cargar_servicios_personalizacion.py --target test --filtro PERS-LASER-INN --apply
    python scripts/cargar_servicios_personalizacion.py --target test --verificar
    python scripts/cargar_servicios_personalizacion.py --target test --rollback --apply

`--filtro` acota por prefijo de SKU: sirve para cargar una técnica a la vez y
validar el mecanismo antes de soltar las 51.

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
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv

if hasattr(sys.stdout, "buffer"):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

REPO = Path(__file__).resolve().parent.parent
BACKUP_DIR = REPO / "backups"
HOJA = REPO / "analysis" / "costos-personalizacion" / "mapa_1_productos.csv"
HOJA_SETUPS = REPO / "analysis" / "costos-personalizacion" / "mapa_3_setups.csv"
CATEGORIA = "Servicios de Personalización"
CTX = {"active_test": False}


def conectar(url: str, db: str, user: str, pwd: str):
    uid = xmlrpc.client.ServerProxy(f"{url}/xmlrpc/2/common").authenticate(db, user, pwd, {})
    if not uid:
        raise SystemExit(f"✗ Autenticación fallida en {url} (db={db})")
    models = xmlrpc.client.ServerProxy(f"{url}/xmlrpc/2/object")

    def call(model, method, *args, **kw):
        return models.execute_kw(db, uid, pwd, model, method, list(args), kw)

    return call


def uno(res):
    """`create` por RPC devuelve una lista de un elemento; `search` también."""
    return res[0] if isinstance(res, list) and res else res


def leer_hoja(filtro: str | None) -> list[dict]:
    """Lee las DOS hojas de productos: los tarifados y los de setup.

    El setup es un cargo ÚNICO por orden —la pantalla de serigrafía, el ponchado
    del bordado— que no se multiplica por la cantidad. Va como producto aparte
    porque una línea de venta no sabe cobrar un fijo además del por-pieza.
    """
    if not HOJA.exists():
        raise SystemExit(f"✗ No existe la hoja {HOJA}.\n"
                         f"  Genérala antes con: python scripts/mapa_servicios_personalizacion.py")
    with HOJA.open(encoding="utf-8-sig") as fh:
        filas = list(csv.DictReader(fh))

    if HOJA_SETUPS.exists():
        with HOJA_SETUPS.open(encoding="utf-8-sig") as fh:
            for s in csv.DictReader(fh):
                cond = (s.get("condicion") or "").strip()
                desc = ("Cargo único de preparación de la orden (pantalla, ponchado, "
                        "placa). No se multiplica por la cantidad de piezas.")
                aviso = "Cantidad 1: es un cargo por orden, no por pieza."
                if cond:
                    desc += f" {cond}."
                    aviso += f" {cond}."
                filas.append({
                    "sku": s["sku"], "nombre": s["nombre"],
                    "descripcion_venta": desc, "aviso_en_la_linea": aviso,
                    "list_price": s["list_price"], "standard_price": s["costo"],
                    "tecnica": "", "unidad_cobro": "lote", "escala_por_tinta": "",
                    "qty_minima": "1", "num_tramos": "1",
                })

    if filtro:
        filas = [f for f in filas if f["sku"].startswith(filtro)]
    return filas


def valores(fila: dict, categ_id: int, tecnicas: dict[str, int]) -> dict:
    tec_id = tecnicas.get(fila["tecnica"])
    v = {
        "name": fila["nombre"],
        "default_code": fila["sku"],
        "description_sale": fila["descripcion_venta"],
        "type": "service",
        "list_price": float(fila["list_price"]),
        "standard_price": float(fila["standard_price"]),
        "categ_id": categ_id,
        "sale_ok": True,
        "purchase_ok": False,
        "is_published": False,
        "sale_line_warn_msg": fila["aviso_en_la_linea"],
        "x_es_servicio_personalizacion": True,
    }
    if tec_id:
        v["x_tecnica_servicio_id"] = tec_id
    return v


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--target", choices=["test", "prod"], default="test")
    ap.add_argument("--filtro", help="Prefijo de SKU, ej. PERS-LASER-INN")
    ap.add_argument("--apply", action="store_true", help="Escribe. Sin esto, simulacro.")
    ap.add_argument("--si-produccion", action="store_true", help="Guardarraíl para --target prod")
    ap.add_argument("--verificar", action="store_true", help="Solo lectura: hoja vs Odoo")
    ap.add_argument("--rollback", action="store_true", help="Archiva lo creado en la última corrida")
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
        db = url.split("//")[1].split(".")[0]

    call = conectar(url, db, os.environ["ODOO_USER"], os.environ["ODOO_PASSWORD"])
    modo = "VERIFICAR" if args.verificar else ("APLICAR" if args.apply else "DRY-RUN (no escribe)")
    print("=" * 78)
    print(f"  CARGA DE SERVICIOS DE PERSONALIZACIÓN  [{args.target.upper()}]  ·  {modo}")
    print(f"  {url}  (db={db})" + (f"  ·  filtro: {args.filtro}" if args.filtro else ""))
    print("=" * 78)

    if args.rollback:
        return rollback(call, args)

    filas = leer_hoja(args.filtro)
    if not filas:
        print("✗ La hoja no tiene filas para ese filtro.")
        return 1
    print(f"\nFilas de la hoja: {len(filas)}")

    categ = call("product.category", "search", [["name", "=", CATEGORIA]])
    if not categ:
        raise SystemExit(f"✗ No existe la categoría «{CATEGORIA}». "
                         f"Corre antes consolidar_categorias_servicio.py")
    categ_id = uno(categ)
    tecnicas = {t["x_name"]: t["id"] for t in
                call("x_tecnica_personalizacion", "search_read", [], fields=["x_name"])}

    creados, actualizados, iguales, problemas = [], [], 0, []
    for f in sorted(filas, key=lambda z: z["sku"]):
        v = valores(f, categ_id, tecnicas)
        existe = call("product.template", "search_read", [["default_code", "=", f["sku"]]],
                      fields=list(v.keys()), context=CTX)
        if not existe:
            print(f"\n  + CREAR  {f['sku']}")
            print(f"      {v['name']}")
            print(f"      precio ${v['list_price']:,.2f} · costo ${v['standard_price']:,.2f}")
            creados.append(f["sku"])
            if args.apply:
                nid = uno(call("product.template", "create", [v]))
                print(f"      → creado id={nid}")
            continue

        actual = existe[0]
        difs = {}
        for k, nuevo in v.items():
            viejo = actual.get(k)
            if isinstance(viejo, list):        # many2one llega como [id, nombre]
                viejo = viejo[0] if viejo else False
            if isinstance(nuevo, float):
                if abs(float(viejo or 0) - nuevo) > 0.005:
                    difs[k] = (viejo, nuevo)
            elif (viejo or "") != (nuevo or ""):
                difs[k] = (viejo, nuevo)
        if not difs:
            iguales += 1
            continue
        print(f"\n  ~ ACTUALIZAR  {f['sku']}  (id={actual['id']})")
        for k, (viejo, nuevo) in difs.items():
            print(f"      {k}: {str(viejo)[:44]!r} ⇒ {str(nuevo)[:44]!r}")
        actualizados.append({"id": actual["id"], "sku": f["sku"],
                             "antes": {k: actual.get(k) for k in difs}})
        if args.apply:
            call("product.template", "write", [actual["id"]], v)
            print("      → escrito")

    print("\n" + "-" * 78)
    print(f"  crear: {len(creados)} · actualizar: {len(actualizados)} · sin cambio: {iguales}")
    if problemas:
        for p in problemas:
            print(f"  ✗ {p}")

    if args.verificar:
        return 1 if (creados or actualizados) else 0

    if args.apply:
        BACKUP_DIR.mkdir(exist_ok=True)
        p = BACKUP_DIR / f"servicios_pers_{args.target}_{datetime.now():%Y%m%d_%H%M%S}.json"
        p.write_text(json.dumps({"target": args.target, "url": url, "db": db,
                                 "fecha": datetime.now().isoformat(timespec="seconds"),
                                 "filtro": args.filtro, "creados": creados,
                                 "actualizados": actualizados},
                                ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"  Respaldo: {p}")
    else:
        print("  (simulacro) Agrega --apply para escribir.")
    return 0


def rollback(call, args) -> int:
    """Archiva lo creado y restaura lo actualizado. No borra: archivar conserva
    cualquier línea de cotización que ya los referencie."""
    reps = sorted(BACKUP_DIR.glob(f"servicios_pers_{args.target}_*.json"))
    if not reps:
        print(f"✗ No hay respaldo para {args.target} en {BACKUP_DIR}.")
        return 1
    d = json.loads(reps[-1].read_text(encoding="utf-8"))
    print(f"Respaldo: {reps[-1].name} ({d['fecha']})\n")
    for sku in d.get("creados", []):
        ids = call("product.template", "search", [["default_code", "=", sku]], context=CTX)
        print(f"  archivar {sku}  ids={ids}")
        if args.apply and ids:
            call("product.template", "write", ids, {"active": False})
    for a in d.get("actualizados", []):
        print(f"  restaurar {a['sku']} (id={a['id']}): {list(a['antes'])}")
        if args.apply:
            vals = {k: (v[0] if isinstance(v, list) and v else v) for k, v in a["antes"].items()}
            call("product.template", "write", [a["id"]], vals)
    if not args.apply:
        print("\n(simulacro) Agrega --apply para deshacer.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
