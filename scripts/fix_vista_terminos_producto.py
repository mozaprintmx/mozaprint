#!/usr/bin/env python3
"""
Repara la vista `website_sale.product_terms_and_conditions` por-website, que el
upgrade a saas~19.2 dejó inconsistente y rompe TODA la ficha de producto (500).

Qué pasó
--------
En 19.0 esa vista era una PLANTILLA INDEPENDIENTE (`<t t-name="...">`) invocada
con `t-call` desde la ficha de producto. En saas~19.2 pasó a ser una VISTA
HEREDADA de `website_sale.product` que inyecta su contenido con
`<div id="o_wsale_product_cta_section" position="inside">`.

El upgrade convirtió la vista genérica (website_id=False) y le puso `inherit_id`
a la copia POR-WEBSITE (la que crea el editor del sitio al traducir el texto al
español, mecanismo COW), pero NO convirtió su `arch`: quedó una vista con
`inherit_id` y un arch de plantilla independiente. Al combinar vistas, Odoo no
encuentra ninguna especificación de herencia válida y revienta — por eso el 500
es un error "crudo" de werkzeug, sin la página de error de Odoo: el fallo ocurre
al armar la vista, antes de poder renderizar nada.

Solo la ficha de producto se cae; /shop, carrito y el resto del sitio siguen
sirviendo 200 porque no combinan esta vista.

⚠️ PRODUCCIÓN: hoy corre 19.0 y NO está afectada, pero tiene exactamente la
misma copia por-website. Cuando Odoo suba producción a 19.2 el mismo fallo
aparecerá ahí. Este script sirve para las dos (`--target prod`).

    DRY-RUN POR DEFECTO. Sin --apply no escribe nada.

Uso:
    python scripts/fix_vista_terminos_producto.py --target test            # simulacro
    python scripts/fix_vista_terminos_producto.py --target test --apply
    python scripts/fix_vista_terminos_producto.py --target test --rollback --apply
    python scripts/fix_vista_terminos_producto.py --target prod --apply --si-produccion

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
import xmlrpc.client
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv

# La consola de Windows (cp1252) no puede imprimir '→', 'ó', etc.
if hasattr(sys.stdout, "buffer"):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

REPO = Path(__file__).resolve().parent.parent
BACKUP_DIR = REPO / "backups"
KEY = "website_sale.product_terms_and_conditions"
ANCLA = "o_wsale_product_cta_section"
# Detecta si un arch YA es una especificación de herencia válida.
SPEC_HERENCIA = re.compile(r"\b(position=|xpath\b|<data\b)", re.I)


def conectar(url: str, db: str, user: str, pwd: str):
    uid = xmlrpc.client.ServerProxy(f"{url}/xmlrpc/2/common").authenticate(db, user, pwd, {})
    if not uid:
        raise SystemExit(f"✗ Autenticación fallida en {url} (db={db})")
    models = xmlrpc.client.ServerProxy(f"{url}/xmlrpc/2/object")

    def call(model, method, *args, **kw):
        return models.execute_kw(db, uid, pwd, model, method, list(args), kw)

    return call


def idiomas(call) -> list[str]:
    """`arch_db` es un campo TRADUCIDO: escribir sin fijar idioma deja los demás
    con el arch viejo. Se escribe en todos, empezando por el origen `en_US`."""
    activos = [l["code"] for l in
               call("res.lang", "search_read", [["active", "=", True]], fields=["code"])]
    return list(dict.fromkeys(["en_US"] + activos))


def cuerpo_interno(arch: str) -> str:
    """Extrae el contenido de dentro del `<t t-name=...>` raíz."""
    m = re.match(r"\s*<t\b[^>]*>(.*)</t>\s*$", arch, re.S)
    if not m:
        raise SystemExit("✗ El arch no tiene la forma <t ...>…</t> esperada; revisar a mano.")
    return m.group(1).strip()


def envolver(cuerpo: str) -> str:
    """Arch de herencia equivalente al de la vista genérica de 19.2."""
    return (
        f'<data name="Terms and Conditions">\n'
        f'    <div id="{ANCLA}" position="inside">\n'
        f'        {cuerpo}\n'
        f'    </div>\n'
        f'</data>'
    )


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--target", choices=["test", "prod"], default="test")
    ap.add_argument("--apply", action="store_true", help="Escribe. Sin esto, simulacro.")
    ap.add_argument("--si-produccion", action="store_true", help="Guardarraíl para --target prod")
    ap.add_argument("--rollback", action="store_true",
                    help="Restaura el arch original desde el respaldo más reciente")
    args = ap.parse_args()

    load_dotenv(REPO / "analysis" / "supplier-sync" / ".env")
    if args.target == "prod":
        url, db = os.environ["ODOO_URL"].rstrip("/"), os.environ["ODOO_DB"]
        if args.apply and not args.si_produccion:
            print("✗ Para escribir en PRODUCCIÓN agrega --si-produccion (guardarraíl).", file=sys.stderr)
            return 2
    else:
        url = os.environ["ODOO_TEST_URL"].rstrip("/")
        db = url.split("//")[1].split(".")[0]  # el subdominio ES la BD en staging

    call = conectar(url, db, os.environ["ODOO_USER"], os.environ["ODOO_PASSWORD"])
    modo = "APLICAR" if args.apply else "DRY-RUN (no escribe)"
    print("=" * 74)
    print(f"  FIX vista de términos en la ficha de producto  [{args.target.upper()}]  ·  {modo}")
    print(f"  {url}  (db={db})")
    print("=" * 74)

    if args.rollback:
        return rollback(call, args)

    langs = idiomas(call)
    vistas = call("ir.ui.view", "search_read", [["key", "=", KEY]],
                  fields=["id", "name", "active", "website_id", "inherit_id"],
                  context={"active_test": False})
    if not vistas:
        print(f"✗ No existe ninguna vista con key {KEY}.")
        return 1

    # `arch_db` es traducido: se lee (y se repara) idioma por idioma.
    for v in vistas:
        v["archs"] = {
            lang: call("ir.ui.view", "read", [v["id"]], fields=["arch_db"],
                       context={"lang": lang})[0]["arch_db"] or ""
            for lang in langs
        }
        v["rotos"] = [lang for lang, a in v["archs"].items()
                      if v["inherit_id"] and not SPEC_HERENCIA.search(a)]

    rotas = [v for v in vistas if v["rotos"]]

    print(f"\nVistas con key {KEY}: {len(vistas)}   ·   idiomas: {', '.join(langs)}")
    for v in vistas:
        estado = f"ROTA en {', '.join(v['rotos'])}" if v["rotos"] else "ok"
        print(f"  id={v['id']:5}  act={v['active']}  website={v['website_id']}  "
              f"inherit={v['inherit_id']}  [{estado}]")

    if not rotas:
        print("\n✓ Nada que reparar: ninguna vista heredada tiene arch de plantilla independiente.")
        return 0

    respaldo = {"target": args.target, "url": url, "db": db,
                "fecha": datetime.now().isoformat(timespec="seconds"),
                "idiomas": langs,
                "vistas": [{"id": v["id"], "archs": v["archs"]} for v in rotas]}

    for v in rotas:
        print(f"\n--- id={v['id']} ---")
        for lang in langs:
            if lang not in v["rotos"]:
                print(f"[{lang}] ya está bien, no se toca")
                continue
            nuevo = envolver(cuerpo_interno(v["archs"][lang]))
            print(f"\n[{lang}] ANTES:\n" + v["archs"][lang].strip())
            print(f"\n[{lang}] DESPUÉS:\n" + nuevo)
            if args.apply:
                call("ir.ui.view", "write", [v["id"]], {"arch_db": nuevo},
                     context={"lang": lang})
                print("→ escrito")

    if args.apply:
        BACKUP_DIR.mkdir(exist_ok=True)
        p = BACKUP_DIR / f"vista_terminos_{args.target}_{datetime.now():%Y%m%d_%H%M%S}.json"
        p.write_text(json.dumps(respaldo, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"\n✓ Reparadas {len(rotas)} vista(s). Respaldo: {p}")
        print("  Verifica una ficha de producto en el sitio antes de dar por cerrado.")
    else:
        print(f"\n(simulacro) Se repararían {len(rotas)} vista(s). Agrega --apply para escribir.")
    return 0


def rollback(call, args) -> int:
    reps = sorted(BACKUP_DIR.glob(f"vista_terminos_{args.target}_*.json"))
    if not reps:
        print(f"✗ No hay respaldo para {args.target} en {BACKUP_DIR}.")
        return 1
    datos = json.loads(reps[-1].read_text(encoding="utf-8"))
    print(f"Respaldo: {reps[-1].name} ({datos['fecha']})")
    for v in datos["vistas"]:
        # Respaldos nuevos guardan un arch por idioma; los viejos, uno solo.
        archs = v.get("archs") or {"en_US": v["arch_db"]}
        for lang, arch in archs.items():
            print(f"  id={v['id']} [{lang}] → restaurar arch original ({len(arch)} chars)")
            if args.apply:
                call("ir.ui.view", "write", [v["id"]], {"arch_db": arch},
                     context={"lang": lang})
                print("    → restaurado")
    if not args.apply:
        print("\n(simulacro) Agrega --apply para restaurar.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
