#!/usr/bin/env python3
"""
Consolida las DOS categorías de servicio de personalización en una sola, y marca
los 20 servicios genéricos como comodín de «precio a cotizar».

Paso 3 del reemplazo nativo del motor (ver `specs/personalizacion-nativa.md`).

El problema
-----------
Existen dos categorías que solo difieren en una mayúscula:

    [5]   'Servicios de personalización'   → 3 productos de la era MANUAL, con
                                             historial de ventas (uno archivado)
    [435] 'Servicios de Personalización'   → los 20 SERV-*, precio 0

Las reglas de delegación entre listas de precios se apoyan en la categoría, así
que un producto en la categoría equivocada no heredaría el precio. Hay que dejar
una sola.

Qué hace, en orden
------------------
1. Mueve TODOS los productos de la categoría 5 a la 435, incluidos los
   archivados: si queda uno, la categoría no se puede borrar.
2. Borra la categoría 5.
3. Renombra la 435 al nombre canónico (si ya lo tiene, no hace nada).
4. Renombra los 20 servicios genéricos a «<Técnica> (precio a cotizar)», para
   que no se confundan con los 51 productos tarifados que vienen después. Se
   conservan a propósito: de las 20 técnicas solo 9 tienen tarifa en la matriz,
   y 4Promotional no tiene ninguna — sin comodín, esos casos se quedan sin
   producto que usar.

Mover de categoría NO altera la contabilidad (ambas tienen las mismas cuentas,
104 ingreso / 121 gasto) ni el historial: el precio vive en la línea de la
cotización, no en el producto.

⚠️ `product.category` NO tiene campo `active`: no se puede archivar, solo borrar.
Por eso el borrado es el único paso NO reversible — el rollback puede recrear la
categoría con su nombre y cuentas, pero con un id nuevo. Como lo único que la
referenciaba eran esos 3 productos, no tiene consecuencias prácticas.

    DRY-RUN POR DEFECTO. Sin --apply no escribe nada.

Uso:
    python scripts/consolidar_categorias_servicio.py --target test
    python scripts/consolidar_categorias_servicio.py --target test --apply
    python scripts/consolidar_categorias_servicio.py --target test --rollback --apply
    python scripts/consolidar_categorias_servicio.py --target prod --apply --si-produccion

Variables de entorno (analysis/supplier-sync/.env):
    ODOO_URL, ODOO_TEST_URL, ODOO_DB, ODOO_USER, ODOO_PASSWORD
"""

from __future__ import annotations

import argparse
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

CAT_ORIGEN = "Servicios de personalización"   # la que se elimina (minúscula)
CAT_DESTINO = "Servicios de Personalización"  # la que sobrevive
PREFIJO_COMODIN = "SERV-"          # SKU de los 20 servicios genéricos
SUFIJO_COMODIN = " (precio a cotizar)"
CTX = {"active_test": False}   # los archivados también cuentan para poder borrar


def conectar(url: str, db: str, user: str, pwd: str):
    uid = xmlrpc.client.ServerProxy(f"{url}/xmlrpc/2/common").authenticate(db, user, pwd, {})
    if not uid:
        raise SystemExit(f"✗ Autenticación fallida en {url} (db={db})")
    models = xmlrpc.client.ServerProxy(f"{url}/xmlrpc/2/object")

    def call(model, method, *args, **kw):
        return models.execute_kw(db, uid, pwd, model, method, list(args), kw)

    return call


def buscar_categoria(call, nombre: str) -> dict | None:
    """Busca por nombre EXACTO — las dos solo difieren en una mayúscula y un
    `ilike` devolvería ambas."""
    for c in call("product.category", "search_read", [["name", "=", nombre]],
                  fields=["name", "complete_name", "parent_id",
                          "property_account_income_categ_id",
                          "property_account_expense_categ_id"]):
        if c["name"] == nombre:      # Odoo compara sin distinguir mayúsculas
            return c
    return None


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--target", choices=["test", "prod"], default="test")
    ap.add_argument("--apply", action="store_true", help="Escribe. Sin esto, simulacro.")
    ap.add_argument("--si-produccion", action="store_true", help="Guardarraíl para --target prod")
    ap.add_argument("--rollback", action="store_true",
                    help="Deshace desde el respaldo más reciente")
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
    modo = "APLICAR" if args.apply else "DRY-RUN (no escribe)"
    print("=" * 76)
    print(f"  CONSOLIDAR CATEGORÍAS DE SERVICIO  [{args.target.upper()}]  ·  {modo}")
    print(f"  {url}  (db={db})")
    print("=" * 76)

    if args.rollback:
        return rollback(call, args)

    destino = buscar_categoria(call, CAT_DESTINO)
    origen = buscar_categoria(call, CAT_ORIGEN)
    if not destino:
        print(f"✗ No existe la categoría destino {CAT_DESTINO!r}. Nada que hacer.")
        return 1

    respaldo = {"target": args.target, "url": url, "db": db,
                "fecha": datetime.now().isoformat(timespec="seconds"),
                "cat_destino": destino, "cat_origen": origen,
                "movidos": [], "renombrados": []}

    # ---------------------------------------------------------------- 3.1 ---
    print(f"\n[3.1] Mover productos a «{CAT_DESTINO}» (id={destino['id']})")
    if not origen:
        print(f"  · la categoría {CAT_ORIGEN!r} ya no existe — nada que mover")
        mover = []
    else:
        mover = call("product.template", "search_read", [["categ_id", "=", origen["id"]]],
                     fields=["name", "default_code", "active", "list_price"], context=CTX)
        if not mover:
            print(f"  · «{CAT_ORIGEN}» (id={origen['id']}) ya está vacía")
        for m in mover:
            print(f"  → id={m['id']:<5} act={str(m['active']):<5} "
                  f"{str(m.get('default_code') or '—'):<10} ${m['list_price']:<9} {m['name'][:44]}")
            respaldo["movidos"].append({"id": m["id"], "categ_id": origen["id"],
                                        "name": m["name"]})
            if args.apply:
                call("product.template", "write", [m["id"]], {"categ_id": destino["id"]})

    # ---------------------------------------------------------------- 3.2 ---
    print(f"\n[3.2] Borrar la categoría «{CAT_ORIGEN}»")
    borrada = False
    if not origen:
        print("  · ya no existe")
    elif not args.apply:
        print(f"  (simulacro) se intentaría borrar id={origen['id']} tras quedar vacía")
    else:
        restantes = call("product.category", "read", [origen["id"]],
                         fields=["product_count"])[0]["product_count"]
        try:
            call("product.category", "unlink", [origen["id"]])
            borrada = True
            print(f"  ✓ borrada (id={origen['id']}, product_count previo={restantes})")
        except Exception as e:
            msg = str(e).split("\\n")[-1][:220]
            print(f"  ✗ NO se pudo borrar id={origen['id']}: {msg}")
            print("     Algo más la referencia. Queda vacía y sin uso; revisar a mano.")
    respaldo["cat_origen_borrada"] = borrada

    # ---------------------------------------------------------------- 3.3 ---
    print(f"\n[3.3] Nombre de la categoría que sobrevive")
    if destino["name"] == CAT_DESTINO:
        print(f"  · ya se llama «{CAT_DESTINO}» — sin cambio")
    else:
        print(f"  → «{destino['name']}» ⇒ «{CAT_DESTINO}»")
        if args.apply:
            call("product.category", "write", [destino["id"]], {"name": CAT_DESTINO})

    # ---------------------------------------------------------------- 3.4 ---
    print(f"\n[3.4] Marcar los servicios genéricos como comodín")
    # Se filtra por el prefijo del SKU, NO por `x_es_servicio_personalizacion`:
    # los 51 productos tarifados también llevan esa marca, y buscarlos por ahí
    # renombraría «Láser · Curpiel · Innovation Line» a «Láser (precio a
    # cotizar)» en la segunda corrida. Los comodines son exactamente los SERV-*.
    genericos = call("product.template", "search_read",
                     [["default_code", "=like", f"{PREFIJO_COMODIN}%"]],
                     fields=["name", "default_code", "x_tecnica_servicio_id"], context=CTX)
    n_ren = 0
    for g in sorted(genericos, key=lambda z: z["name"]):
        tec = g.get("x_tecnica_servicio_id")
        base = tec[1] if tec else g["name"].replace("Servicio de ", "")
        nuevo = f"{base}{SUFIJO_COMODIN}"
        if g["name"] == nuevo:
            continue
        n_ren += 1
        print(f"  → {str(g.get('default_code') or '—'):<12} «{g['name']}» ⇒ «{nuevo}»")
        respaldo["renombrados"].append({"id": g["id"], "name": g["name"]})
        if args.apply:
            call("product.template", "write", [g["id"]], {"name": nuevo})
    if not n_ren:
        print("  · los 20 ya están marcados — sin cambio")

    # ------------------------------------------------------------ cierre ---
    print("\n" + "-" * 76)
    if args.apply:
        BACKUP_DIR.mkdir(exist_ok=True)
        p = BACKUP_DIR / f"categorias_servicio_{args.target}_{datetime.now():%Y%m%d_%H%M%S}.json"
        p.write_text(json.dumps(respaldo, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"  ✓ {len(respaldo['movidos'])} movido(s) · {n_ren} renombrado(s) · "
              f"categoría borrada: {'sí' if borrada else 'no'}")
        print(f"  Respaldo: {p}")
        if borrada:
            print("  ⚠ El borrado de la categoría NO se deshace con el mismo id; el "
                  "rollback la recrea con uno nuevo.")
    else:
        print(f"  (simulacro) {len(mover)} a mover · {n_ren} a renombrar. "
              "Agrega --apply para escribir.")
    return 0


def rollback(call, args) -> int:
    reps = sorted(BACKUP_DIR.glob(f"categorias_servicio_{args.target}_*.json"))
    if not reps:
        print(f"✗ No hay respaldo para {args.target} en {BACKUP_DIR}.")
        return 1
    d = json.loads(reps[-1].read_text(encoding="utf-8"))
    print(f"Respaldo: {reps[-1].name} ({d['fecha']})\n")

    cat_id = None
    if d.get("cat_origen") and d.get("cat_origen_borrada"):
        o = d["cat_origen"]
        print(f"  recrear categoría «{o['name']}» (id original {o['id']}, se creará uno nuevo)")
        if args.apply:
            vals = {"name": o["name"]}
            for k in ("property_account_income_categ_id", "property_account_expense_categ_id"):
                if o.get(k):
                    vals[k] = o[k][0]
            cat_id = call("product.category", "create", [vals])
            cat_id = cat_id[0] if isinstance(cat_id, list) else cat_id
            print(f"    → creada con id={cat_id}")
    elif d.get("cat_origen"):
        cat_id = d["cat_origen"]["id"]

    for m in d.get("movidos", []):
        print(f"  devolver producto id={m['id']} a la categoría original")
        if args.apply and cat_id:
            call("product.template", "write", [m["id"]], {"categ_id": cat_id})

    for r in d.get("renombrados", []):
        print(f"  restaurar nombre id={r['id']} ⇒ «{r['name']}»")
        if args.apply:
            call("product.template", "write", [r["id"]], {"name": r["name"]})

    if not args.apply:
        print("\n(simulacro) Agrega --apply para deshacer.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
