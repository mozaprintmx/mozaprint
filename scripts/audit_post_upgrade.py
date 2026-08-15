#!/usr/bin/env python3
"""
Auditoría de salud tras una actualización de Odoo. **Solo lectura.**

Busca los modos de fallo que un upgrade introduce de verdad, no los imaginarios.
Nace del incidente del 2026-08-15: el salto a saas~19.2 convirtió una vista de
plantilla independiente a vista heredada, pero dejó la copia por-website con el
arch viejo — y eso tumbó TODAS las fichas de producto con un 500 sin traza
(ver `docs/upgrades/incidencias/2026-08-15-ficha-producto-500.md`).

Complementa `deploy_motor_cotizacion.py --verificar`, que cubre el motor de
cotización. Este cubre el resto: sitio web, vistas y metadatos custom.

Revisiones
----------
1. Vistas heredadas cuyo arch NO es especificación de herencia  → 500 duro
2. `t-call` a plantillas que ya no existen                      → 500 al renderizar
3. Keys de vista duplicadas para el mismo website               → qweb impredecible
4. Vistas desactivadas por el upgrade (compara con la otra base)
5. Barrido HTTP de rutas públicas clave (la ficha se toma del /shop real)
6. Campos manuales `x_` y Server Actions manuales (censo, para comparar bases)

Uso:
    python scripts/audit_post_upgrade.py --target test
    python scripts/audit_post_upgrade.py --target prod
    python scripts/audit_post_upgrade.py --comparar        # test vs prod, lado a lado
    python scripts/audit_post_upgrade.py --target test --sin-http

Sale con código 1 si hay hallazgos BLOQUEANTES (revisiones 1-3 o rutas con 5xx).

Variables de entorno (analysis/supplier-sync/.env):
    ODOO_URL, ODOO_TEST_URL, ODOO_DB, ODOO_USER, ODOO_PASSWORD
"""

from __future__ import annotations

import argparse
import io
import os
import re
import sys
import xmlrpc.client
from collections import Counter
from pathlib import Path

import requests
from dotenv import load_dotenv

if hasattr(sys.stdout, "buffer"):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

REPO = Path(__file__).resolve().parent.parent

# Un arch de vista heredada DEBE traer una de estas: si no, Odoo no sabe dónde
# injertarlo y revienta al combinar. `<t/>` vacío es legítimo (marcador COW).
SPEC_HERENCIA = re.compile(r"\b(position=|xpath\b|<data\b)", re.I)
T_CALL = re.compile(r"""t-call=["']([a-zA-Z0-9_]+\.[a-zA-Z0-9_]+)["']""")

# Rutas públicas que deben responder 200. La ficha de producto se resuelve en
# vivo desde /shop porque los slugs cambian con el catálogo.
RUTAS = ["/", "/shop", "/shop/cart", "/contactanos", "/terms"]


class Base:
    """Una base de Odoo (test o prod) con acceso XML-RPC de administrador."""

    def __init__(self, target: str):
        self.target = target
        if target == "prod":
            self.url = os.environ["ODOO_URL"].rstrip("/")
            self.db = os.environ["ODOO_DB"]
        else:
            self.url = os.environ["ODOO_TEST_URL"].rstrip("/")
            self.db = self.url.split("//")[1].split(".")[0]  # el subdominio ES la BD
        self.pwd = os.environ["ODOO_PASSWORD"]
        common = xmlrpc.client.ServerProxy(f"{self.url}/xmlrpc/2/common")
        self.version = common.version().get("server_serie", "?")
        self.uid = common.authenticate(self.db, os.environ["ODOO_USER"], self.pwd, {})
        if not self.uid:
            raise SystemExit(f"✗ Autenticación fallida en {self.url} (db={self.db})")
        self._m = xmlrpc.client.ServerProxy(f"{self.url}/xmlrpc/2/object")

    def call(self, model: str, method: str, *args, **kw):
        return self._m.execute_kw(self.db, self.uid, self.pwd, model, method, list(args), kw)

    def vistas(self) -> list[dict]:
        """Todas las vistas, incluidas las archivadas (Odoo las oculta por defecto)."""
        if not hasattr(self, "_vistas"):
            self._vistas = self.call(
                "ir.ui.view", "search_read", [],
                fields=["id", "key", "name", "type", "active", "website_id",
                        "inherit_id", "priority", "arch_db"],
                context={"active_test": False})
        return self._vistas


# ------------------------------------------------------------- revisiones ---
def rev_herencia_invalida(b: Base) -> list[str]:
    """1. Vista con inherit_id pero arch de plantilla independiente → 500 duro."""
    malas = []
    for v in b.vistas():
        arch = v["arch_db"] or ""
        if v["inherit_id"] and "t-name=" in arch and not SPEC_HERENCIA.search(arch):
            malas.append(f"id={v['id']} key={v['key']} website={v['website_id']} "
                         f"padre={v['inherit_id'][1] if v['inherit_id'] else '-'}")
    return malas


def rev_tcall_roto(b: Base) -> list[str]:
    """2. `t-call` a una key que no existe → 500 al renderizar esa página.

    Solo vistas `type='qweb'`: las de backend (form/kanban/list) también traen
    `t-call`, pero resuelven contra plantillas OWL de cliente, que no viven en
    `ir.ui.view`. Contarlas daba falsos positivos (p. ej. `social_twitter`).
    """
    existentes = {v["key"] for v in b.vistas() if v["key"]}
    rotos = []
    for v in b.vistas():
        if not v["active"] or v["type"] != "qweb":
            continue
        for key in set(T_CALL.findall(v["arch_db"] or "")):
            if key not in existentes:
                rotos.append(f"id={v['id']} {v['key']} → t-call a «{key}» (no existe)")
    return rotos


def rev_keys_duplicadas(b: Base) -> list[str]:
    """3. Misma key para el mismo website: qweb elige una arbitrariamente."""
    activas = [v for v in b.vistas() if v["active"] and v["key"]]
    c = Counter((v["key"], v["website_id"] and v["website_id"][0]) for v in activas)
    out = []
    for (key, ws), n in sorted(c.items()):
        if n > 1:
            ids = [v["id"] for v in activas
                   if v["key"] == key and (v["website_id"] and v["website_id"][0]) == ws]
            out.append(f"{key} (website={ws}) ×{n} → ids {ids}")
    return out


def rev_estado_vistas(b: Base) -> dict[int, tuple]:
    """4. Estado por **id**, no por key.

    Comparar por key da falsos positivos: en saas~19.2 el módulo
    `website_sale_comparison` se fusionó en `website_sale` y todas sus vistas
    cambiaron de key sin cambiar de id ni de estado. El id sí es estable porque
    la base de test es un duplicado de producción.
    """
    return {v["id"]: (v["key"], v["active"]) for v in b.vistas()}


def rev_censo(b: Base) -> dict:
    """6. Metadatos custom: si un upgrade se llevara algo, aquí se nota."""
    campos = b.call("ir.model.fields", "search_read",
                    [["state", "=", "manual"]], fields=["model", "name"])
    acciones = b.call("ir.actions.server", "search_read",
                      [["state", "=", "code"]], fields=["name", "code"])
    modelos = b.call("ir.model", "search_read", [["state", "=", "manual"]], fields=["model"])
    return {
        "modelos_manual": len(modelos),
        "campos_manual": len(campos),
        "campos_por_modelo": Counter(f["model"] for f in campos),
        "server_actions_code": len(acciones),
        "server_actions_sin_codigo": [a["name"] for a in acciones if not (a["code"] or "").strip()],
        "vistas_totales": len(b.vistas()),
        "vistas_activas": sum(1 for v in b.vistas() if v["active"]),
    }


def rev_http(b: Base) -> list[tuple[str, str]]:
    """5. Barrido de rutas públicas. La ficha se toma del /shop real."""
    s = requests.Session()
    rutas = list(RUTAS)
    try:
        r = s.get(f"{b.url}/shop", timeout=90)
        slugs = re.findall(r'/shop/([a-z0-9][a-z0-9-]*-\d+)"', r.text)
        for slug in list(dict.fromkeys(slugs))[:3]:  # 3 fichas distintas
            rutas.append(f"/shop/{slug}")
    except Exception as e:
        rutas.append(f"(no se pudo leer /shop: {type(e).__name__})")

    out = []
    for ruta in rutas:
        if ruta.startswith("("):
            out.append((ruta, "ERR"))
            continue
        try:
            r = s.get(f"{b.url}{ruta}", timeout=90, allow_redirects=True)
            out.append((ruta, str(r.status_code)))
        except Exception as e:
            out.append((ruta, type(e).__name__))
    return out


# ---------------------------------------------------------------- informe ---
def auditar(b: Base, con_http: bool) -> bool:
    """Devuelve True si todo está sano."""
    print("=" * 74)
    print(f"  AUDITORÍA POST-UPGRADE  [{b.target.upper()}]  ·  Odoo {b.version}")
    print(f"  {b.url}  (db={b.db})")
    print("=" * 74)
    sano = True

    print("\n[1] Vistas heredadas sin especificación de herencia (position/xpath/data)")
    malas = rev_herencia_invalida(b)
    if malas:
        sano = False
        print(f"  ✗ BLOQUEANTE — {len(malas)}. Rompen con 500 toda página que las combine:")
        for m in malas:
            print(f"      {m}")
        print("      Reparación: scripts/fix_vista_terminos_producto.py (si es la de términos)")
        print("      o convertir el arch a <data><... position=\"inside\">…</></data>.")
    else:
        print("  ✓ ninguna")

    print("\n[2] t-call a plantillas inexistentes")
    rotos = rev_tcall_roto(b)
    if rotos:
        sano = False
        print(f"  ✗ BLOQUEANTE — {len(rotos)}:")
        for r in rotos[:20]:
            print(f"      {r}")
        if len(rotos) > 20:
            print(f"      … y {len(rotos) - 20} más")
    else:
        print("  ✓ ninguna")

    print("\n[3] Keys de vista duplicadas (mismo website, ambas activas)")
    dups = rev_keys_duplicadas(b)
    if dups:
        print(f"  ⚠ {len(dups)} — no siempre rompen, pero hacen el render impredecible:")
        for d in dups:
            print(f"      {d}")
    else:
        print("  ✓ ninguna")

    print("\n[6] Censo de objetos custom")
    c = rev_censo(b)
    print(f"  modelos manual: {c['modelos_manual']} · campos manual: {c['campos_manual']} · "
          f"Server Actions (código): {c['server_actions_code']}")
    print(f"  vistas: {c['vistas_activas']} activas de {c['vistas_totales']}")
    for modelo, n in sorted(c["campos_por_modelo"].items()):
        print(f"      {modelo:38} {n:3} campos x_")
    if c["server_actions_sin_codigo"]:
        sano = False
        print(f"  ✗ Server Actions SIN CÓDIGO: {c['server_actions_sin_codigo']}")

    if con_http:
        print("\n[5] Rutas públicas")
        for ruta, code in rev_http(b):
            marca = "✓" if code == "200" else "✗"
            if not code.startswith(("2", "3")):
                sano = False
            print(f"  {marca} {code:4}  {ruta}")

    print("\n" + "-" * 74)
    print("  ✓ Sin hallazgos bloqueantes." if sano else "  ✗ HAY HALLAZGOS BLOQUEANTES (arriba).")
    return sano


def comparar(a: Base, b: Base) -> None:
    """Diff entre dos bases: lo que cambió es lo que el upgrade tocó."""
    print("\n" + "=" * 74)
    print(f"  COMPARACIÓN  {a.target.upper()} (Odoo {a.version})  vs  "
          f"{b.target.upper()} (Odoo {b.version})")
    print("=" * 74)

    ea, eb = rev_estado_vistas(a), rev_estado_vistas(b)
    comunes = set(ea) & set(eb)
    apagadas = sorted(i for i in comunes if not ea[i][1] and eb[i][1])
    renombradas = sorted(i for i in comunes if ea[i][0] != eb[i][0])

    print(f"\n[4] Vistas que {a.target.upper()} tiene DESACTIVADAS y {b.target.upper()} activas "
          f"({len(apagadas)}) — esto sí es «las apagó el upgrade»:")
    for i in apagadas[:40]:
        print(f"      id={i} {eb[i][0]}")
    if len(apagadas) > 40:
        print(f"      … y {len(apagadas) - 40} más")
    if not apagadas:
        print("      (ninguna)")

    print(f"\n[4b] Vistas que solo cambiaron de key ({len(renombradas)}) — módulos fusionados "
          f"o renombrados en el upgrade, sin impacto funcional:")
    for i in renombradas[:15]:
        print(f"      id={i} {eb[i][0]}  →  {ea[i][0]}")
    if len(renombradas) > 15:
        print(f"      … y {len(renombradas) - 15} más")
    if not renombradas:
        print("      (ninguna)")

    solo_test = sorted(set(ea) - set(eb))
    solo_prod = sorted(set(eb) - set(ea))
    print(f"\n[4c] Vistas que existen solo en {a.target} ({len(solo_test)}) "
          f"/ solo en {b.target} ({len(solo_prod)}) — normalmente vistas nuevas de la "
          f"versión, o creadas a mano en una sola base.")

    ca, cb = rev_censo(a), rev_censo(b)
    print("\n[6] Censo lado a lado")
    print(f"  {'métrica':32} {a.target:>12} {b.target:>12}")
    for k in ("modelos_manual", "campos_manual", "server_actions_code",
              "vistas_activas", "vistas_totales"):
        marca = "" if ca[k] == cb[k] else "   ← difiere"
        print(f"  {k:32} {ca[k]:>12} {cb[k]:>12}{marca}")

    faltantes = set(ca["campos_por_modelo"]) - set(cb["campos_por_modelo"])
    if faltantes:
        print(f"  modelos con campos x_ solo en {a.target}: {sorted(faltantes)}")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--target", choices=["test", "prod"], default="test")
    ap.add_argument("--comparar", action="store_true", help="Audita test y prod y las compara")
    ap.add_argument("--sin-http", action="store_true", help="Omite el barrido de rutas (más rápido)")
    args = ap.parse_args()

    load_dotenv(REPO / "analysis" / "supplier-sync" / ".env")
    con_http = not args.sin_http

    if args.comparar:
        test, prod = Base("test"), Base("prod")
        ok = auditar(test, con_http)
        ok = auditar(prod, con_http) and ok
        comparar(test, prod)
        return 0 if ok else 1

    return 0 if auditar(Base(args.target), con_http) else 1


if __name__ == "__main__":
    sys.exit(main())
