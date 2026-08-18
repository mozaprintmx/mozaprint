#!/usr/bin/env python3
"""
Repara las vistas que llaman `_get_visitor_from_request()` sobre el modelo
equivocado, lo que rompe `/contactanos` con un 500 en saas~19.3.

Qué pasó
--------
En saas~19.3 el método `_get_visitor_from_request()` se MUDÓ del modelo
`website.visitor` al modelo `ir.http`. Odoo migró su propia plantilla
(`website.contactus`, website_id=False) y dejó intacta NUESTRA copia
por-website (`website.contactanos`, la que crea el editor del sitio al
traducir/renombrar la página — mecanismo COW).

Resultado: la vista combina perfectamente y revienta al RENDERIZAR, con

    AttributeError: 'website.visitor' object has no attribute
                    '_get_visitor_from_request'

Por eso este fallo NO lo caza ninguna revisión estructural del auditor (la
revisión [1] busca herencias mal formadas, y aquí la herencia está bien): solo
lo ve el barrido HTTP. Es un error de ejecución, no de estructura.

Solo `/contactanos` se cae — que es el formulario que alimenta el CRM. El resto
del sitio, fichas de producto incluidas, sigue en 200.

⚠️ NO APLICAR ANTES DEL UPGRADE. En saas~19.2 el método vive en
`website.visitor` (lo confirma la propia plantilla genérica de Odoo en
producción, que ahí lo llama así), de modo que aplicar el cambio en 19.2
rompería lo que hoy funciona. Va EL DÍA del upgrade a 19.3.

El script comprueba el estado real antes de escribir: si no encuentra el patrón
viejo, reporta "nada que reparar" y sale sin tocar nada. Correrlo por error
contra 19.2 no hace daño, pero tampoco sirve de nada.

`arch_db` es un campo TRADUCIDO: se lee y se escribe idioma por idioma,
empezando por el origen `en_US`. Escribir solo el idioma de la sesión dejaría el
sitio roto para el visitante con el backend viéndose bien (lección de la
incidencia 2026-08-15).

    DRY-RUN POR DEFECTO. Sin --apply no escribe nada.

Uso:
    python scripts/fix_vista_contactanos.py --target test            # simulacro
    python scripts/fix_vista_contactanos.py --target test --apply
    python scripts/fix_vista_contactanos.py --target test --rollback --apply
    python scripts/fix_vista_contactanos.py --target prod --apply --si-produccion

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

# El método se llamaba sobre este modelo hasta 19.2...
MODELO_VIEJO = "website.visitor"
# ...y desde 19.3 vive aquí.
MODELO_NUEVO = "ir.http"
METODO = "_get_visitor_from_request"

# Captura `env['website.visitor']._get_visitor_from_request` con comillas simples
# o dobles y con o sin `request.` delante. Solo sustituye el nombre del modelo.
PATRON = re.compile(
    r"(env\[\s*['\"])" + re.escape(MODELO_VIEJO) + r"(['\"]\s*\]\s*\.\s*" + re.escape(METODO) + r")"
)


def conectar(url: str, db: str, user: str, pwd: str):
    uid = xmlrpc.client.ServerProxy(f"{url}/xmlrpc/2/common").authenticate(db, user, pwd, {})
    if not uid:
        raise SystemExit(f"✗ Autenticación fallida en {url} (db={db})")
    models = xmlrpc.client.ServerProxy(f"{url}/xmlrpc/2/object")

    def call(model, method, *args, **kw):
        return models.execute_kw(db, uid, pwd, model, method, list(args), kw)

    return call


def idiomas(call) -> list[str]:
    """`arch_db` es traducido: escribir sin fijar idioma deja los demás con el
    arch viejo. Se escribe en todos, empezando por el origen `en_US`."""
    activos = [l["code"] for l in
               call("res.lang", "search_read", [["active", "=", True]], fields=["code"])]
    return list(dict.fromkeys(["en_US"] + activos))


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
    print(f"  FIX llamada a {METODO}  [{args.target.upper()}]  ·  {modo}")
    print(f"  {url}  (db={db})")
    print("=" * 74)

    if args.rollback:
        return rollback(call, args)

    version = call("ir.module.module", "search_read", [["name", "=", "base"]],
                   fields=["latest_version"])[0]["latest_version"]
    print(f"\nVersión de la base: {version}")

    # Se busca por contenido, no por key: si otra copia por-website arrastra la
    # misma llamada, también hay que repararla.
    langs = idiomas(call)
    vistas = call("ir.ui.view", "search_read", [["arch_db", "like", METODO]],
                  fields=["id", "name", "key", "active", "website_id"],
                  context={"active_test": False})

    for v in vistas:
        v["archs"] = {
            lang: call("ir.ui.view", "read", [v["id"]], fields=["arch_db"],
                       context={"lang": lang})[0]["arch_db"] or ""
            for lang in langs
        }
        v["rotos"] = [lang for lang, a in v["archs"].items() if PATRON.search(a)]

    # GUARDARRAÍL DE VERSIÓN, y no por el número de versión sino por la evidencia:
    # las vistas GENÉRICAS de Odoo (website_id=False) son la fuente de verdad de
    # dónde vive el método en esta versión. Si Odoo todavía lo llama sobre el
    # modelo viejo, entonces el método sigue ahí y "reparar" rompería la base.
    genericas = [v for v in vistas if not v["website_id"]]
    if any(v["rotos"] for v in genericas):
        print(f"\n✗ ABORTADO. Las plantillas propias de Odoo en esta base todavía llaman al")
        print(f"  método sobre `{MODELO_VIEJO}`:")
        for v in genericas:
            if v["rotos"]:
                print(f"      id={v['id']} {v['key']}")
        print(f"\n  Es decir: en esta versión el método AÚN VIVE en `{MODELO_VIEJO}`, y")
        print(f"  cambiarlo a `{MODELO_NUEVO}` rompería lo que hoy funciona.")
        print("  Este fix es para saas~19.3+. Aplícalo EL DÍA del upgrade, no antes.")
        return 1

    # Solo se tocan NUESTRAS copias por-website. Las de Odoo las migra Odoo; si
    # alguna quedara mal, es un bug suyo y se reporta, no se parcha aquí.
    rotas = [v for v in vistas if v["rotos"] and v["website_id"]]

    print(f"\nVistas que llaman a {METODO}: {len(vistas)}   ·   idiomas: {', '.join(langs)}")
    for v in vistas:
        estado = f"USA {MODELO_VIEJO} en {', '.join(v['rotos'])}" if v["rotos"] else "ok"
        propia = "NUESTRA (por-website)" if v["website_id"] else "de Odoo"
        print(f"  id={v['id']:5}  act={v['active']}  {propia:<22} {v['key']}  [{estado}]")

    if not rotas:
        print(f"\n✓ Nada que reparar: ninguna vista llama al método sobre `{MODELO_VIEJO}`.")
        return 0

    respaldo = {"target": args.target, "url": url, "db": db,
                "fecha": datetime.now().isoformat(timespec="seconds"),
                "idiomas": langs,
                "vistas": [{"id": v["id"], "key": v["key"], "archs": v["archs"]} for v in rotas]}

    for v in rotas:
        print(f"\n--- id={v['id']}  {v['key']} ---")
        for lang in langs:
            if lang not in v["rotos"]:
                print(f"[{lang}] ya está bien, no se toca")
                continue
            nuevo, n = PATRON.subn(r"\g<1>" + MODELO_NUEVO + r"\g<2>", v["archs"][lang])
            for ln in nuevo.splitlines():
                if METODO in ln:
                    print(f"[{lang}] ({n} reemplazo/s)")
                    print(f"    ANTES:   ...env['{MODELO_VIEJO}'].{METODO}...")
                    print(f"    DESPUÉS: {ln.strip()[:150]}")
            if args.apply:
                call("ir.ui.view", "write", [v["id"]], {"arch_db": nuevo},
                     context={"lang": lang})
                print("    → escrito")

    if args.apply:
        BACKUP_DIR.mkdir(exist_ok=True)
        p = BACKUP_DIR / f"vista_contactanos_{args.target}_{datetime.now():%Y%m%d_%H%M%S}.json"
        p.write_text(json.dumps(respaldo, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"\n✓ Reparadas {len(rotas)} vista(s). Respaldo: {p}")
        print("  Verifica /contactanos en el sitio antes de dar por cerrado.")
    else:
        print(f"\n(simulacro) Se repararían {len(rotas)} vista(s). Agrega --apply para escribir.")
    return 0


def rollback(call, args) -> int:
    reps = sorted(BACKUP_DIR.glob(f"vista_contactanos_{args.target}_*.json"))
    if not reps:
        print(f"✗ No hay respaldo para {args.target} en {BACKUP_DIR}.")
        return 1
    datos = json.loads(reps[-1].read_text(encoding="utf-8"))
    print(f"Respaldo: {reps[-1].name} ({datos['fecha']})")
    for v in datos["vistas"]:
        for lang, arch in v["archs"].items():
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
