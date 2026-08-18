#!/usr/bin/env python3
"""
Cuenta las líneas de código de Studio que Odoo FACTURA. **Solo lectura.**

Odoo Online cobra el concepto «Mantenimiento de código personalizado» **cada 100
líneas**, y aplica a código de la app Studio: **acciones automatizadas (Server
Actions tipo "Execute Code") y campos calculados**. No aplica a vistas, menús,
campos simples, ACLs ni reglas de automatización declarativas.

Contexto: en agosto de 2026 el motor de cotización sumaba 289 líneas → 3 cargos.
Se retiró y producción quedó en 0 (ver `decisions/007-retiro-motor-cotizacion-costo-codigo.md`).
Este script existe para que eso no se vuelva a colar sin darse cuenta.

Correrlo ANTES de desplegar cualquier cosa que agregue Server Actions con código
o campos calculados, y como parte de la revisión post-upgrade.

Qué cuenta como propio: las Server Actions sin `ir.model.data` de módulo o cuyo
módulo es `studio_customization`. Las 200 de los módulos de Odoo no se facturan.

Uso:
    python scripts/audit_lineas_facturables.py                # prod
    python scripts/audit_lineas_facturables.py --target test
    python scripts/audit_lineas_facturables.py --max-bloques 0   # falla si hay algo

Sale con código 1 si se supera `--max-bloques` (default 0).

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

if hasattr(sys.stdout, "buffer") and (sys.stdout.encoding or "").lower() != "utf-8":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

REPO = Path(__file__).resolve().parent.parent
BLOQUE = 100  # Odoo factura por cada 100 líneas


def conectar(target: str):
    if target == "prod":
        url, db = os.environ["ODOO_URL"].rstrip("/"), os.environ["ODOO_DB"]
    else:
        url = os.environ["ODOO_TEST_URL"].rstrip("/")
        db = url.split("//")[1].split(".")[0]  # el subdominio ES la BD en staging
    pwd = os.environ["ODOO_PASSWORD"]
    uid = xmlrpc.client.ServerProxy(f"{url}/xmlrpc/2/common").authenticate(
        db, os.environ["ODOO_USER"], pwd, {})
    if not uid:
        raise SystemExit(f"✗ Autenticación fallida en {url} (db={db})")
    models = xmlrpc.client.ServerProxy(f"{url}/xmlrpc/2/object")

    def call(model: str, method: str, *args, **kw):
        return models.execute_kw(db, uid, pwd, model, method, list(args), kw)

    return url, call


def contar(codigo: str | bool) -> int:
    """Líneas con contenido real: sin vacías ni comentarios."""
    return len([l for l in (codigo or "").splitlines()
                if l.strip() and not l.strip().startswith("#")])


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--target", choices=["test", "prod"], default="prod")
    ap.add_argument("--max-bloques", type=int, default=0,
                    help="Bloques de 100 líneas tolerados antes de fallar (default 0)")
    args = ap.parse_args()

    load_dotenv(REPO / "analysis" / "supplier-sync" / ".env")
    url, call = conectar(args.target)

    print("=" * 74)
    print(f"  LÍNEAS DE CÓDIGO FACTURABLES  [{args.target.upper()}]")
    print(f"  {url}")
    print("=" * 74)

    # Server Actions: separar las de módulos de Odoo de las nuestras / de Studio.
    acciones = call("ir.actions.server", "search_read", [["state", "=", "code"]],
                    fields=["name", "code", "model_id"])
    modulo = {d["res_id"]: d["module"] for d in
              call("ir.model.data", "search_read",
                   [["model", "=", "ir.actions.server"]], fields=["module", "res_id"])}
    propias = [a for a in acciones if modulo.get(a["id"]) in (None, "studio_customization")]

    print(f"\n[1] Server Actions con código: {len(acciones)} "
          f"(de módulos de Odoo: {len(acciones) - len(propias)} · propias: {len(propias)})")
    total_sa = 0
    for a in sorted(propias, key=lambda x: -contar(x["code"])):
        n = contar(a["code"])
        total_sa += n
        mdl = a["model_id"][1] if a["model_id"] else "-"
        print(f"      {n:5} líneas   {a['name'][:46]:48} [{mdl[:20]}]")
    print(f"      {'-' * 62}\n      {total_sa:5} líneas   TOTAL")

    # Campos calculados manuales (los `related` NO llevan código).
    campos = call("ir.model.fields", "search_read",
                  [["state", "=", "manual"], ["compute", "!=", False]],
                  fields=["model", "name", "compute"])
    print(f"\n[2] Campos calculados: {len(campos)}")
    total_cf = 0
    for f in sorted(campos, key=lambda x: -contar(x["compute"])):
        n = contar(f["compute"])
        total_cf += n
        print(f"      {n:5} líneas   {f['model']}.{f['name']}")
    print(f"      {'-' * 62}\n      {total_cf:5} líneas   TOTAL")

    total = total_sa + total_cf
    bloques = -(-total // BLOQUE)
    print("\n" + "-" * 74)
    print(f"  TOTAL FACTURABLE: {total} líneas → {bloques} bloque(s) de {BLOQUE}")
    if bloques > args.max_bloques:
        print(f"  ✗ Supera el máximo tolerado ({args.max_bloques} bloque[s]).")
        return 1
    print("  ✓ Dentro del máximo tolerado.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
