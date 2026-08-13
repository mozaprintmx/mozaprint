#!/usr/bin/env python3
"""
Rollback del MOTOR DE COTIZACIÓN a partir del manifiesto que escribe
`scripts/deploy_motor_cotizacion.py`.

Borra en ORDEN INVERSO a la creación (menús → acciones → vistas → Server Actions
→ ACLs → campos → modelos → contacto/defaults) y restaura los datos de
`x_costo_personalizacion` desde el respaldo JSON del deploy.

    DRY-RUN POR DEFECTO. Sin --apply no borra nada.

Uso:
    python scripts/rollback_motor_cotizacion.py --manifiesto backups/manifiesto_motor_test_XXXX.json
    python scripts/rollback_motor_cotizacion.py --manifiesto ... --apply
    python scripts/rollback_motor_cotizacion.py --manifiesto ... --apply --si-produccion

Qué NO revierte (a propósito):
  - Las cotizaciones que ya tengan líneas de personalización: al borrar los campos
    x_source_line_id / x_es_setup esas líneas quedan como líneas normales de
    servicio. Revísalas a mano si hubo cotizaciones reales (el listado se imprime).
  - Los datos de x_costo_personalizacion se restauran SOLO en los campos
    respaldados (nombre y alcance); x_markup/x_precio_* desaparecen con el campo.
"""

from __future__ import annotations

import argparse
import io
import json
import os
import sys
import xmlrpc.client
from pathlib import Path

from dotenv import load_dotenv

# Consola Windows (cp1252): sin esto, un acento revienta el rollback a media ejecución.
if hasattr(sys.stdout, "buffer"):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

REPO = Path(__file__).resolve().parent.parent

# Orden de borrado: lo que depende de otros va primero.
ORDEN = [("menus", "ir.ui.menu"), ("views", "ir.ui.view"), ("actions", None),
         ("acls", "ir.model.access"), ("defaults", "ir.default"),
         ("fields", "ir.model.fields"), ("models", "ir.model"), ("partners", "res.partner")]


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--manifiesto", required=True)
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--si-produccion", action="store_true")
    ap.add_argument("--conservar-partner", action="store_true",
                    help="no borrar el contacto de personalización externa")
    args = ap.parse_args()

    man = json.loads(Path(args.manifiesto).read_text(encoding="utf-8"))
    load_dotenv(REPO / "analysis" / "supplier-sync" / ".env")

    if man["target"] == "prod" and args.apply and not args.si_produccion:
        print("✗ Para revertir en PRODUCCIÓN agrega --si-produccion.", file=sys.stderr)
        return 2

    url, db = man["url"], man["db"]
    uid = xmlrpc.client.ServerProxy(f"{url}/xmlrpc/2/common").authenticate(
        db, os.environ["ODOO_USER"], os.environ["ODOO_PASSWORD"], {})
    if not uid:
        raise SystemExit("✗ autenticación fallida")
    m = xmlrpc.client.ServerProxy(f"{url}/xmlrpc/2/object")
    pwd = os.environ["ODOO_PASSWORD"]

    def call(model, method, *a, **k):
        return m.execute_kw(db, uid, pwd, model, method, list(a), k)

    modo = "APLICAR" if args.apply else "DRY-RUN (no borra)"
    print("=" * 74)
    print(f"  ROLLBACK motor de cotización  [{man['target'].upper()}]  ·  {modo}")
    print(f"  {url} (db={db})  ·  desplegado {man['ts']}")
    print("=" * 74)

    # Aviso: líneas de personalización vivas que quedarán huérfanas
    try:
        vivas = call("sale.order.line", "search_count", [["x_source_line_id", "!=", False]])
        if vivas:
            print(f"\n⚠ Hay {vivas} líneas de personalización en cotizaciones. Al borrar los campos "
                  f"quedarán como líneas de servicio normales (no se borran solas).")
    except Exception:
        pass

    # 1. Restaurar datos de la matriz de costos
    bkp = man.get("data_backup")
    if bkp and Path(bkp).exists():
        filas = json.loads(Path(bkp).read_text(encoding="utf-8"))
        print(f"\n=== RESTAURAR DATOS ({len(filas)} filas del respaldo) ===")
        cambiados = 0
        for f in filas:
            act = call("x_costo_personalizacion", "read", [f["id"]],
                       fields=["x_name", "x_alcance_producto"])
            if not act:
                continue
            a = act[0]
            if a["x_name"] != f["x_name"] or a["x_alcance_producto"] != f["x_alcance_producto"]:
                if args.apply:
                    call("x_costo_personalizacion", "write", [f["id"]],
                         {"x_name": f["x_name"], "x_alcance_producto": f["x_alcance_producto"]})
                cambiados += 1
        print(f"  {cambiados} filas a restaurar (nombre/alcance)")
        nuevas = call("x_costo_personalizacion", "search",
                      [["id", "not in", [f["id"] for f in filas]]])
        if nuevas:
            print(f"  ⚠ {len(nuevas)} filas de costo creadas DESPUÉS del deploy: NO se borran "
                  f"automáticamente (ids {nuevas[:10]}...). Revísalas a mano.")
    else:
        print("\n⚠ Sin respaldo de datos en el manifiesto: no se restauran nombres/alcances.")

    # 2. Borrar objetos en orden inverso
    total = 0
    for clave, modelo in ORDEN:
        objetos = man.get(clave) or []
        if clave == "partners" and args.conservar_partner:
            print(f"\n=== {clave}: conservado por --conservar-partner ===")
            continue
        if not objetos:
            continue
        print(f"\n=== BORRAR {clave} ({len(objetos)}) ===")
        for ob in reversed(objetos):
            mdl = modelo or ob.get("model")
            oid = ob["id"]
            etiqueta = ob.get("label") or ob.get("name") or ob.get("model") or ""
            try:
                if args.apply:
                    call(mdl, "unlink", [oid])
                print(f"  {'✓' if args.apply else '·'} {mdl} id={oid} {etiqueta}")
                total += 1
            except xmlrpc.client.Fault as e:
                print(f"  ✗ {mdl} id={oid} {etiqueta}: {e.faultString.strip().splitlines()[-1][:90]}")

    print("\n" + "=" * 74)
    print(f"  {'REVERTIDO' if args.apply else 'SIMULACRO'}: {total} objetos "
          f"{'borrados' if args.apply else 'se borrarían'}")
    if not args.apply:
        print("  Nada se borró. Re-corre con --apply para ejecutar.")
    print("=" * 74)
    return 0


if __name__ == "__main__":
    sys.exit(main())
