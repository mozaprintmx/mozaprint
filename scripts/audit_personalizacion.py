#!/usr/bin/env python3
"""
Verifica que la matriz de costos, los productos de servicio y las reglas de
precio sigan diciendo lo mismo. SOLO LECTURA.

Paso 8 del reemplazo nativo del motor (ver `specs/personalizacion-nativa.md`).

Por qué existe
--------------
El diseño tiene una fuente de verdad —la matriz `x_costo_personalizacion`— y dos
derivados que se cargan con scripts: los productos y las reglas de lista de
precios. **Nada obliga a que sigan sincronizados.** Alguien edita un costo en la
matriz, nadie vuelve a cargar, y las cotizaciones salen con el precio viejo sin
que nada avise. Este comando es lo que avisa.

**No se compara contra la hoja CSV**, a propósito: la hoja es un intermedio que
puede estar tan desactualizado como los productos. Se recalcula todo desde la
matriz viva de Odoo, y el SKU de cada tarifa se lee de su propio campo
`x_sku_servicio`. Así el chequeo es autocontenido y detecta justo el fallo que
importa.

Qué revisa
----------
    [1] cobertura     cada tarifa activa tiene SKU y ese producto existe
    [2] precio base   list_price = costo × markup · standard_price = costo
    [3] tramos        cada escalón de la matriz tiene su regla, con su precio
    [4] huérfanos     reglas o productos PERS-* sin tarifa que los respalde
    [5] delegación    las demás listas heredan la categoría de la principal
    [6] higiene       categoría, tipo servicio, no publicado, no comprable
    [7] ámbar         el aviso está donde debe y solo donde debe

Sale con **código 1** si hay cualquier hallazgo. Pensado para el checklist
trimestral, junto a `audit_post_upgrade.py`, `audit_lineas_facturables.py` y
`deploy_reporte_cotizacion.py --verificar`.

Uso:
    python scripts/audit_personalizacion.py --target test
    python scripts/audit_personalizacion.py --target prod

Variables de entorno (analysis/supplier-sync/.env):
    ODOO_URL, ODOO_TEST_URL, ODOO_DB, ODOO_USER, ODOO_PASSWORD
"""

from __future__ import annotations

import argparse
import io
import os
import sys
import xmlrpc.client
from collections import OrderedDict
from pathlib import Path

from dotenv import load_dotenv

# La consola de Windows (cp1252) no puede imprimir '→', 'ó', etc. El guardarraíl
# de codificación es necesario: sin él, importar este módulo desde otro script
# que ya envolvió stdout crea un segundo envoltorio y cierra el primero
# («I/O operation on closed file»).
if hasattr(sys.stdout, "buffer") and (sys.stdout.encoding or "").lower() not in ("utf-8", "utf8"):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(Path(__file__).resolve().parent))
# Se reutiliza la MISMA función que genera los avisos al cargar: si un día
# cambia el criterio del ámbar, el auditor cambia con él y no se desincroniza.
from mapa_servicios_personalizacion import aviso as aviso_esperado  # noqa: E402

CATEGORIA = "Servicios de Personalización"
LISTA_PRINCIPAL = "Default"
PREFIJO = "PERS-"
CENT = 0.005


def conectar(url: str, db: str, user: str, pwd: str):
    uid = xmlrpc.client.ServerProxy(f"{url}/xmlrpc/2/common").authenticate(db, user, pwd, {})
    if not uid:
        raise SystemExit(f"✗ Autenticación fallida en {url} (db={db})")
    models = xmlrpc.client.ServerProxy(f"{url}/xmlrpc/2/object")

    def call(model, method, *args, **kw):
        return models.execute_kw(db, uid, pwd, model, method, list(args), kw)

    return call


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--target", choices=["test", "prod"], default="test")
    args = ap.parse_args()

    load_dotenv(REPO / "analysis" / "supplier-sync" / ".env")
    if args.target == "prod":
        url, db = os.environ["ODOO_URL"].rstrip("/"), os.environ["ODOO_DB"]
    else:
        url = os.environ["ODOO_TEST_URL"].rstrip("/")
        db = url.split("//")[1].split(".")[0]

    call = conectar(url, db, os.environ["ODOO_USER"], os.environ["ODOO_PASSWORD"])
    print("=" * 78)
    print(f"  AUDITORÍA DE PERSONALIZACIÓN  [{args.target.upper()}]  ·  solo lectura")
    print(f"  {url}  (db={db})")
    print("=" * 78)

    hallazgos: list[str] = []

    # ------------------------------------------------ la matriz, agrupada ---
    filas = call("x_costo_personalizacion", "search_read", [["x_activa", "=", True]],
                 fields=["x_tecnica_id", "x_proveedor_id", "x_alcance_producto",
                         "x_qty_from", "x_qty_to", "x_area_from_cm2", "x_area_to_cm2",
                         "x_unidad_cobro", "x_escala_por_tinta", "x_costo_unit",
                         "x_costo_setup", "x_markup", "x_sku_servicio"])
    combos: OrderedDict[tuple, list[dict]] = OrderedDict()
    for f in filas:
        k = (f["x_tecnica_id"][0], f["x_proveedor_id"][0], f["x_alcance_producto"] or "",
             f["x_area_from_cm2"], f["x_area_to_cm2"], f["x_unidad_cobro"])
        combos.setdefault(k, []).append(f)
    for v in combos.values():
        v.sort(key=lambda r: int(r["x_qty_from"]))
    print(f"\nMatriz: {len(filas)} tarifas activas en {len(combos)} combinaciones")

    # ------------------------------------------------------- [1] cobertura --
    print("\n[1] Cada tarifa tiene SKU y su producto existe")
    prods = {p["default_code"]: p for p in call(
        "product.template", "search_read", [["default_code", "=like", f"{PREFIJO}%"]],
        fields=["default_code", "name", "list_price", "standard_price", "categ_id",
                "type", "sale_ok", "purchase_ok", "is_published", "active",
                "sale_line_warn_msg"], context={"active_test": False})}
    sin_sku, sin_producto = [], []
    esperados = {}
    for k, fs in combos.items():
        skus = {f["x_sku_servicio"] for f in fs}
        sku = next(iter(skus)) if len(skus) == 1 else None
        if not sku:
            sin_sku.append((k, sorted(str(s) for s in skus)))
            continue
        esperados[sku] = fs
        if sku not in prods:
            sin_producto.append(sku)
    for k, skus in sin_sku:
        hallazgos.append(f"combinación sin SKU único: {k[2] or '(general)'} → {skus}")
        print(f"  ✗ sin SKU único: {k[2] or '(general)'} → {skus}")
    for s in sin_producto:
        hallazgos.append(f"la tarifa apunta a {s}, que no existe como producto")
        print(f"  ✗ {s}: la matriz lo referencia pero NO existe")
    if not sin_sku and not sin_producto:
        print(f"  ✓ las {len(combos)} combinaciones tienen SKU y producto")

    # ----------------------------------------------------- [2] precio base --
    print("\n[2] Precio base y costo del producto")
    malos = 0
    for sku, fs in esperados.items():
        p = prods.get(sku)
        if not p:
            continue
        primera = fs[0]
        markup = primera["x_markup"] or 1.275
        esp_pv = round(primera["x_costo_unit"] * markup, 2)
        if abs(p["list_price"] - esp_pv) > CENT:
            malos += 1
            hallazgos.append(f"{sku}: precio ${p['list_price']:,.2f} ≠ ${esp_pv:,.2f} (matriz)")
            print(f"  ✗ {sku}: precio ${p['list_price']:,.2f} ⇒ debería ser ${esp_pv:,.2f}")
        if abs(p["standard_price"] - primera["x_costo_unit"]) > CENT:
            malos += 1
            hallazgos.append(f"{sku}: costo ${p['standard_price']:,.2f} ≠ "
                             f"${primera['x_costo_unit']:,.2f} (matriz)")
            print(f"  ✗ {sku}: costo ${p['standard_price']:,.2f} ⇒ "
                  f"${primera['x_costo_unit']:,.2f}")
    if not malos:
        print(f"  ✓ los {len(esperados)} productos cuadran con la matriz")

    # ---------------------------------------------------------- [3] tramos --
    print("\n[3] Tramos de cantidad")
    principal = call("product.pricelist", "search_read", [["name", "=", LISTA_PRINCIPAL]],
                     fields=["name"])
    if not principal:
        hallazgos.append(f"no existe la lista «{LISTA_PRINCIPAL}»")
        print(f"  ✗ no existe la lista «{LISTA_PRINCIPAL}»")
        principal_id = None
    else:
        principal_id = principal[0]["id"]
    faltan, sobran, difieren = [], [], []
    reglas_vistas = set()
    if principal_id:
        tmpl_ids = {p["default_code"]: p["id"] for p in prods.values()}
        items = call("product.pricelist.item", "search_read",
                     [["pricelist_id", "=", principal_id], ["applied_on", "=", "1_product"]],
                     fields=["product_tmpl_id", "min_quantity", "fixed_price", "compute_price"])
        por_tmpl: dict[int, dict[int, dict]] = {}
        for it in items:
            if it["product_tmpl_id"]:
                por_tmpl.setdefault(it["product_tmpl_id"][0], {})[int(it["min_quantity"])] = it
        for sku, fs in esperados.items():
            tid = tmpl_ids.get(sku)
            if not tid:
                continue
            reales = por_tmpl.get(tid, {})
            prev = fs[0]["x_costo_unit"]
            esperadas = {}
            for f in fs[1:]:
                if f["x_costo_unit"] == prev:      # tramo redundante, no lleva regla
                    continue
                esperadas[int(f["x_qty_from"])] = round(
                    f["x_costo_unit"] * (f["x_markup"] or 1.275), 2)
                prev = f["x_costo_unit"]
            for mq, precio in esperadas.items():
                r = reales.get(mq)
                if not r:
                    faltan.append(f"{sku} min_qty {mq:,} → ${precio:,.2f}")
                elif abs(r["fixed_price"] - precio) > CENT:
                    difieren.append(f"{sku} min_qty {mq:,}: ${r['fixed_price']:,.2f} "
                                    f"⇒ ${precio:,.2f}")
                if r:
                    reglas_vistas.add(r["id"])
            for mq, r in reales.items():
                if mq not in esperadas:
                    sobran.append(f"{sku} min_qty {mq:,} (${r['fixed_price']:,.2f}) "
                                  f"no está en la matriz")
                    reglas_vistas.add(r["id"])
    for lista, etiqueta in ((faltan, "FALTA"), (difieren, "DIFIERE"), (sobran, "SOBRA")):
        for x in lista:
            hallazgos.append(f"regla {etiqueta}: {x}")
            print(f"  ✗ {etiqueta}: {x}")
    if not (faltan or difieren or sobran):
        print(f"  ✓ los tramos de la matriz coinciden con las reglas ({len(reglas_vistas)})")

    # ------------------------------------------------------- [4] huérfanos --
    print("\n[4] Productos sin tarifa que los respalde")
    setups = {s for s in prods if s.startswith(f"{PREFIJO}SETUP-")}
    huerfanos = [s for s, p in prods.items()
                 if s not in esperados and s not in setups and p["active"]]
    for s in huerfanos:
        hallazgos.append(f"producto {s} sin tarifa en la matriz")
        print(f"  ✗ {s}: existe como producto pero ninguna tarifa lo referencia")
    if not huerfanos:
        print(f"  ✓ ninguno ({len(setups)} productos de setup, excluidos a propósito)")

    # ------------------------------------------------------ [5] delegación --
    print("\n[5] Las otras listas heredan la categoría")
    categ_id = call("product.category", "search", [["name", "=", CATEGORIA]])
    categ_id = categ_id[0] if categ_id else None
    if not categ_id:
        hallazgos.append(f"no existe la categoría «{CATEGORIA}»")
        print(f"  ✗ no existe la categoría «{CATEGORIA}»")
    else:
        for pl in call("product.pricelist", "search_read", [], fields=["name"]):
            if pl["id"] == principal_id:
                continue
            n = call("product.pricelist.item", "search_count",
                     [["pricelist_id", "=", pl["id"]],
                      ["applied_on", "=", "2_product_category"],
                      ["categ_id", "=", categ_id]])
            if n:
                print(f"  ✓ «{pl['name']}» delega")
            else:
                hallazgos.append(f"la lista «{pl['name']}» no delega la personalización")
                print(f"  ✗ «{pl['name']}» NO delega → cobraría el precio del tramo 1")

    # --------------------------------------------------------- [6] higiene --
    print("\n[6] Higiene de los productos")
    problemas = []
    for sku, p in prods.items():
        if not p["active"]:
            continue
        if p["categ_id"] and p["categ_id"][1] != CATEGORIA:
            problemas.append(f"{sku}: categoría «{p['categ_id'][1]}»")
        if p["type"] != "service":
            problemas.append(f"{sku}: tipo «{p['type']}», debería ser servicio")
        if p["is_published"]:
            problemas.append(f"{sku}: PUBLICADO en la tienda")
        if p["purchase_ok"]:
            problemas.append(f"{sku}: marcado como comprable")
    for x in problemas:
        hallazgos.append(x)
        print(f"  ✗ {x}")
    if not problemas:
        print(f"  ✓ los {sum(1 for p in prods.values() if p['active'])} activos, en orden")

    # ----------------------------------------------------------- [7] ámbar --
    print("\n[7] El aviso está donde debe (y solo donde debe)")
    difs = 0
    for sku, fs in esperados.items():
        p = prods.get(sku)
        if not p:
            continue
        esp = aviso_esperado(fs).strip()
        real = (p["sale_line_warn_msg"] or "").strip()
        if bool(esp) != bool(real):
            difs += 1
            hallazgos.append(f"{sku}: aviso {'FALTA' if esp else 'SOBRA'}")
            print(f"  ✗ {sku}: el aviso {'falta' if esp else 'sobra'}")
    if not difs:
        con = sum(1 for s in esperados if (prods[s]["sale_line_warn_msg"] or "").strip())
        print(f"  ✓ {con} de {len(esperados)} tarifados llevan aviso, como corresponde")

    # ----------------------------------------------------------- resumen ----
    print("\n" + "-" * 78)
    if hallazgos:
        print(f"  ✗ {len(hallazgos)} HALLAZGO(S):")
        for h in hallazgos[:25]:
            print(f"      - {h}")
        if len(hallazgos) > 25:
            print(f"      … y {len(hallazgos) - 25} más")
        print("\n  Reparación habitual, en este orden:")
        print("      python scripts/mapa_servicios_personalizacion.py --target <t>")
        print("      python scripts/cargar_servicios_personalizacion.py --target <t> --apply")
        print("      python scripts/cargar_reglas_precio_personalizacion.py --target <t> --apply")
        print("      python scripts/enlazar_matriz_servicios.py --target <t> --apply")
        return 1
    print("  ✓ Matriz, productos y reglas dicen lo mismo.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
