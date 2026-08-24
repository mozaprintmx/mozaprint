#!/usr/bin/env python3
"""
Traduce la matriz `x_costo_personalizacion` al diseño NATIVO de personalización:
productos de servicio + reglas de lista de precios. SOLO LECTURA.

No escribe nada en Odoo. Emite una hoja para revisión humana antes de cargar
nada — es el paso 1 del plan de reemplazo del motor de cotización retirado
(ver `decisions/007-retiro-motor-cotizacion-costo-codigo.md`).

Cómo traduce
------------
Cada COMBINACIÓN de (técnica × proveedor × alcance × tramo de área) se vuelve
UN producto de servicio. Sus tramos de cantidad se vuelven reglas de lista de
precios con `min_quantity` + `fixed_price`:

    [PERS-SERI-PO-BOLSA603]  Serigrafía · Bolsas ≤603 cm² · Promo Opción
      list_price     = costo del primer tramo × markup
      standard_price = costo del primer tramo   (Odoo calcula el margen solo)
      reglas: min_qty 200 → $8.78 · min_qty 400 → $6.76 · …

Se omiten las reglas cuyo precio es idéntico al del tramo anterior: no aportan
nada y ensucian la lista.

Casos especiales que el nombre y el aviso tienen que dejar clarísimos:
  · unidad de cobro LOTE  → la cantidad de la línea NO son piezas
  · escala por tinta      → la cantidad de la línea es el NÚMERO DE TINTAS
  · tramo que no arranca en 1 → hay un mínimo, y por debajo aplica otra tarifa

Uso:
    python scripts/mapa_servicios_personalizacion.py --target test
    python scripts/mapa_servicios_personalizacion.py --target test --salida <dir>

Las salidas van a `analysis/costos-personalizacion/` por defecto, que está en
.gitignore: son costos de proveedor y NO deben subirse al repo público.

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
import unicodedata
import xmlrpc.client
from collections import OrderedDict
from pathlib import Path

from dotenv import load_dotenv

if hasattr(sys.stdout, "buffer"):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

REPO = Path(__file__).resolve().parent.parent
SALIDA_DEF = REPO / "analysis" / "costos-personalizacion"

# Código corto por proveedor, para el SKU.
PROV = {"INNOVATIONLINE": "INN", "PROMOOPCION": "PO", "4PROMOTIONAL": "4P"}
# Cómo se escribe el proveedor DE CARA AL CLIENTE (el partner está en mayúsculas
# y `.title()` da 'Innovationline'). Nombres según docs/glossary.md.
PROV_NOMBRE = {"INNOVATIONLINE": "Innovation Line", "PROMOOPCION": "Promo Opción",
               "4PROMOTIONAL": "4Promotional"}
# Código corto por técnica (x_code de x_tecnica_personalizacion → 4-6 letras).
TEC = {
    "serigrafia": "SERI", "tampografia": "TAMPO", "laser": "LASER", "bordado": "BORD",
    "sublimacion": "SUBLI", "doming": "DOMING", "imp_digital": "DIGIT", "vinyl": "VINYL",
    "termograbado": "TERMO", "dtf": "DTF", "dtf_uv": "DTFUV", "uv": "UV",
    "offset": "OFFSET", "transfer": "TRANS", "grabado_co2": "CO2",
}


# Unidades que ensucian el slug sin distinguir nada ("603 cm2" → el 2 sobra).
UNIDADES = re.compile(r"\b(cm2|cm²|cm|mm|pzas?|pz|piezas?)\b", re.I)
# Palabras que no distinguen un alcance de otro.
VACIAS = {"Y", "O", "DE", "DEL", "A", "AL", "CON", "PARA", "EN", "LA", "LAS",
          "EL", "LOS", "UN", "UNA", "POR", "SIN", "MENOS", "MAS"}


def slug(texto: str, omitir: set[str] | None = None) -> str:
    """'Llaveros de bambú' → 'LLAVEBAMBU'.

    Toma las DOS primeras palabras con contenido (5 letras cada una) más los
    dígitos. Tomar simplemente las primeras N letras no sirve: 'Llaveros y
    bolígrafos' y 'Llaveros de bambú' comparten prefijo y lo que las separa
    viene después — colisionaban en el mismo código.

    `omitir` son dígitos que ya viajan en otra parte del SKU (el área), para no
    repetirlos.
    """
    t = unicodedata.normalize("NFKD", texto or "").encode("ascii", "ignore").decode()
    t = UNIDADES.sub(" ", t).upper()
    palabras = [w for w in re.split(r"[^A-Z0-9]+", t) if w]
    letras = [w[:5] for w in palabras if w.isalpha() and w not in VACIAS][:2]
    digitos = "".join(w for w in palabras if not w.isalpha())
    digitos = re.sub(r"[^0-9]+", "", digitos)
    for d in (omitir or set()):
        digitos = digitos.replace(d, "", 1)
    return ("".join(letras) + digitos[:6]) or "GEN"


def conectar(url: str, db: str, user: str, pwd: str):
    uid = xmlrpc.client.ServerProxy(f"{url}/xmlrpc/2/common").authenticate(db, user, pwd, {})
    if not uid:
        raise SystemExit(f"✗ Autenticación fallida en {url} (db={db})")
    models = xmlrpc.client.ServerProxy(f"{url}/xmlrpc/2/object")

    def call(model, method, *args, **kw):
        return models.execute_kw(db, uid, pwd, model, method, list(args), kw)

    return call


def leer_skus_previos(ruta: Path, combos: dict, tecnicas: dict) -> dict[str, str]:
    """Recupera los SKU de una hoja ya revisada, indexados por `llave`.

    Las hojas nuevas traen la columna `llave` y el emparejamiento es directo.
    Las viejas no la tenían, así que se reconstruye desde (técnica, proveedor,
    alcance, área, unidad) — que es única porque el alcance ya distingue los
    casos ambiguos ('máximo 603' vs 'mayor a 603').
    """
    if not ruta.exists():
        return {}
    with ruta.open(encoding="utf-8-sig") as fh:
        filas = list(csv.DictReader(fh))
    if not filas:
        return {}
    if "llave" in filas[0]:
        return {f["llave"]: f["sku"] for f in filas if f.get("sku")}

    # Reconstrucción para hojas anteriores a la columna `llave`.
    por_texto = {}
    for k in combos:
        tid, pid, alcance, a_de, a_a, unidad = k
        tec = tecnicas.get(tid, {}).get("x_name", "")
        prov = combos[k][0]["x_proveedor_id"][1]
        por_texto[(tec, prov, alcance, str(int(a_a)) if a_a else "", unidad)] = \
            f"{tid}|{pid}|{alcance}|{a_de:g}|{a_a:g}|{unidad}"

    previos, huerfanos = {}, []
    for f in filas:
        clave = (f.get("tecnica", ""), f.get("proveedor", ""), f.get("alcance", ""),
                 f.get("area_hasta_cm2", ""), f.get("unidad_cobro", ""))
        llave = por_texto.get(clave)
        if llave:
            previos[llave] = f["sku"]
        else:
            huerfanos.append(f.get("sku", "?"))
    if huerfanos:
        print(f"⚠ {len(huerfanos)} SKU de la hoja anterior no empatan con ninguna "
              f"tarifa actual (¿cambió la matriz?): {', '.join(huerfanos[:5])}")
    return previos


def descripcion(filas: list[dict], tecnica: str) -> str:
    """(D) `description_sale`: baja sola a la línea de la cotización y al PDF.

    La ve EL CLIENTE, así que va en tono comercial y sin jerga interna — pero
    dice lo mismo que el vendedor necesita recordar. El recordatorio crudo
    ('la cantidad son tintas') vive en el nombre y en el aviso, no aquí.
    """
    r = filas[0]
    p = [f"{tecnica}."]
    if r["x_unidad_cobro"] == "lote":
        tope = f"{int(r['x_qty_to']):,}" if r["x_qty_to"] else None
        if r["x_escala_por_tinta"]:
            p.append(f"Precio por lote de hasta {tope or 'sin tope'} piezas y por tinta.")
        else:
            p.append(f"Precio por lote completo de {int(r['x_qty_from']):,}"
                     f"–{tope or '∞'} piezas.")
    minimo = min(int(f["x_qty_from"]) for f in filas)
    if minimo > 1 and r["x_unidad_cobro"] != "lote":
        p.append(f"Pedido mínimo {minimo:,} piezas.")
    if r["x_area_to_cm2"]:
        p.append(f"Área máxima de impresión: {r['x_area_to_cm2']:.0f} cm².")
    p.append("Incluye 1 posición de impresión.")
    return " ".join(p)


def aviso(filas: list[dict]) -> str:
    """(A) `sale_line_warn_msg`. Vacío = la línea NO se resalta.

    Odoo pinta de ámbar **toda** línea cuyo producto tenga este mensaje — la
    regla `decoration-warning` de `sale.view_order_form` incluye
    `or sale_line_warn_msg`. Si los 53 productos lo llevaran, todas las líneas
    de personalización saldrían ámbar y el resaltado dejaría de significar nada.

    Se reserva para los dos casos en que **la cantidad no se teclea como en el
    resto de la cotización** y equivocarse cuesta dinero: lote/por tinta y
    cantidad mínima. El área máxima y el «a 1 tinta y 1 posición» son
    informativos, no riesgos: viven en la descripción y en el nombre.
    """
    r = filas[0]
    partes = []
    if r["x_unidad_cobro"] == "lote":
        if r["x_escala_por_tinta"]:
            partes.append("La CANTIDAD de esta línea es el NÚMERO DE TINTAS, no de piezas. "
                          f"Precio por lote de hasta {r['x_qty_to'] or 'sin límite'} pzas, por tinta.")
        else:
            partes.append("Precio POR LOTE: pon cantidad 1. "
                          f"Válido para {r['x_qty_from']}–{r['x_qty_to'] or '∞'} pzas.")
    minimo = min(int(f["x_qty_from"]) for f in filas)
    if minimo > 1 and r["x_unidad_cobro"] != "lote":
        partes.append(f"Mínimo {minimo:,} pzas. Por debajo de esa cantidad esta tarifa NO aplica: "
                      "consulta la matriz de costos.")
    return " ".join(partes)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--target", choices=["test", "prod"], default="test")
    ap.add_argument("--salida", type=Path, default=SALIDA_DEF)
    args = ap.parse_args()

    load_dotenv(REPO / "analysis" / "supplier-sync" / ".env")
    if args.target == "prod":
        url, db = os.environ["ODOO_URL"].rstrip("/"), os.environ["ODOO_DB"]
    else:
        url = os.environ["ODOO_TEST_URL"].rstrip("/")
        db = url.split("//")[1].split(".")[0]

    call = conectar(url, db, os.environ["ODOO_USER"], os.environ["ODOO_PASSWORD"])
    print("=" * 76)
    print(f"  MAPA matriz de costos → diseño NATIVO  [{args.target.upper()}]  ·  SOLO LECTURA")
    print(f"  {url}  (db={db})")
    print("=" * 76)

    tecnicas = {t["id"]: t for t in
                call("x_tecnica_personalizacion", "search_read", [],
                     fields=["x_name", "x_code"])}
    filas = call("x_costo_personalizacion", "search_read", [["x_activa", "=", True]],
                 fields=["x_tecnica_id", "x_proveedor_id", "x_alcance_producto",
                         "x_qty_from", "x_qty_to", "x_area_from_cm2", "x_area_to_cm2",
                         "x_unidad_cobro", "x_escala_por_tinta", "x_costo_unit",
                         "x_costo_setup", "x_markup", "x_personalizacion_externa",
                         "x_fecha_vigencia", "x_notas"])
    print(f"\nTarifas activas leídas: {len(filas)}")

    # Agrupar en combinaciones. El tramo de CANTIDAD es lo único que NO entra en
    # la llave: es justo lo que se vuelve regla de lista de precios.
    combos: OrderedDict[tuple, list[dict]] = OrderedDict()
    for f in filas:
        k = (f["x_tecnica_id"][0], f["x_proveedor_id"][0], f["x_alcance_producto"] or "",
             f["x_area_from_cm2"], f["x_area_to_cm2"], f["x_unidad_cobro"])
        combos.setdefault(k, []).append(f)
    for v in combos.values():
        v.sort(key=lambda r: int(r["x_qty_from"]))

    # Los SKU que JC ya revisó y corrigió a mano MANDAN: se releen de la hoja
    # anterior y se conservan. Solo se generan los que no existan todavía. Sin
    # esto, cada corrida pisaría su trabajo.
    previos = leer_skus_previos(args.salida / "mapa_1_productos.csv", combos, tecnicas)
    if previos:
        print(f"Hoja anterior: se conservan {len(previos)} SKU ya revisados")

    productos, reglas, setups = [], [], {}
    for k, fs in combos.items():
        tid, pid, alcance, a_de, a_a, unidad = k
        tec = tecnicas.get(tid, {})
        code_t = TEC.get(tec.get("x_code", ""), slug(tec.get("x_code", "")))
        prov_nom = fs[0]["x_proveedor_id"][1]
        code_p = PROV.get(prov_nom, slug(prov_nom))
        # El área va aparte y con marcador: 'máximo 603' y 'mayor a 603' llevan
        # el mismo número y son tarifas DISTINTAS. H=hasta, D=desde.
        area = f"-H{int(a_a)}" if a_a else (f"-D{int(a_de)}" if a_de else "")
        ya = {str(int(x)) for x in (a_a, a_de) if x}
        suf = slug(alcance, omitir=ya) if alcance else "GEN"
        suf = f"{suf}{area}"
        if unidad == "lote":
            suf = f"{suf}-LOTE"
        llave = f"{tid}|{pid}|{alcance}|{a_de:g}|{a_a:g}|{unidad}"
        sku = previos.get(llave) or f"PERS-{code_t}-{code_p}-{suf}"

        primera = fs[0]
        markup = primera["x_markup"] or 1.275

        # (B) El nombre lleva la BASE DEL PRECIO cuando no es por pieza. Es el
        # único aviso que no se puede descartar: se ve en la línea, en pantalla
        # y en el PDF que recibe el cliente. Los 11 casos de lote-por-tinta son
        # el error caro del diseño — cotizar 1 tinta cuando eran 2 es creíble,
        # silencioso y se come el margen entero.
        if unidad == "lote":
            base = " POR TINTA" if primera["x_escala_por_tinta"] else " POR LOTE"
        else:
            base = ""
        nombre = (f"{tec.get('x_name','?')}{base} · {alcance or 'General'} · "
                  f"{PROV_NOMBRE.get(prov_nom, prov_nom.title())}")
        if a_a:
            nombre += f" ≤{int(a_a)} cm²"
        if unidad == "lote":
            tope = f"≤{int(primera['x_qty_to']):,}" if primera["x_qty_to"] else "sin tope"
            desde = int(primera["x_qty_from"])
            rango = f"{desde:,}–{int(primera['x_qty_to']):,}" if desde > 1 and primera["x_qty_to"] else tope
            nombre += f" (lote {rango} pzas)"

        productos.append({
            "llave": llave,
            "sku": sku,
            "nombre": nombre,
            "descripcion_venta": descripcion(fs, tec.get("x_name", "")),
            "tecnica": tec.get("x_name", ""),
            "proveedor": prov_nom,
            "alcance": alcance,
            "area_hasta_cm2": int(a_a) if a_a else "",
            "unidad_cobro": unidad,
            "escala_por_tinta": "sí" if primera["x_escala_por_tinta"] else "",
            "qty_minima": int(primera["x_qty_from"]),
            "costo_1er_tramo": round(primera["x_costo_unit"], 4),
            "markup": markup,
            "list_price": round(primera["x_costo_unit"] * markup, 2),
            "standard_price": round(primera["x_costo_unit"], 4),
            "num_tramos": len(fs),
            "vigente_hasta": primera["x_fecha_vigencia"] or "",
            "aviso_en_la_linea": aviso(fs),
            "notas_matriz": (primera["x_notas"] or "").strip()[:120],
        })

        prev = primera["x_costo_unit"]
        for f in fs[1:]:
            if f["x_costo_unit"] == prev:      # tramo redundante: mismo precio
                continue
            reglas.append({
                "sku": sku, "nombre_producto": nombre,
                "min_quantity": int(f["x_qty_from"]),
                "costo": round(f["x_costo_unit"], 4),
                "fixed_price": round(f["x_costo_unit"] * (f["x_markup"] or markup), 2),
                "vigente_hasta": f["x_fecha_vigencia"] or "",
            })
            prev = f["x_costo_unit"]

        if primera["x_costo_setup"]:
            sk = f"PERS-SETUP-{code_t}-{code_p}"
            # Hay setups CONDICIONALES: bordado INN cobra ponchado hasta 200 pzas
            # y de ahí en adelante no. Eso no cabe en el producto, así que se
            # anota para que el vendedor sepa cuándo NO agregar la línea.
            gratis = [f for f in fs if not f["x_costo_setup"]]
            nota = (f"NO se cobra a partir de {int(gratis[0]['x_qty_from']):,} pzas"
                    if gratis else "")
            setups.setdefault(sk, {
                "sku": sk,
                "nombre": f"Setup / preparación · {tec.get('x_name','?')} · "
                        f"{PROV_NOMBRE.get(prov_nom, prov_nom.title())}",
                "costo": round(primera["x_costo_setup"], 2),
                "markup": markup,
                "list_price": round(primera["x_costo_setup"] * markup, 2),
                "condicion": nota,
                "aplica_a": [],
            })
            setups[sk]["aplica_a"].append(sku)

    for s in setups.values():
        s["aplica_a"] = " · ".join(s["aplica_a"])

    # El SKU es la llave del diseño entero: si dos combinaciones distintas caen
    # en el mismo código, la carga pisaría una con otra y los precios saldrían
    # mal. Se falla aquí, ruidosamente, antes de que nadie revise la hoja.
    from collections import Counter
    choques = {k: v for k, v in Counter(p["sku"] for p in productos).items() if v > 1}
    if choques:
        print("\n✗ SKUs DUPLICADOS — hay que desambiguar el alcance antes de seguir:")
        for sku, n in choques.items():
            print(f"    {sku}  ({n} combinaciones):")
            for p in productos:
                if p["sku"] == sku:
                    print(f"        {p['alcance']!r}  área≤{p['area_hasta_cm2'] or '—'}")
        return 1

    args.salida.mkdir(parents=True, exist_ok=True)

    def escribir(nombre: str, datos: list[dict]) -> Path:
        p = args.salida / nombre
        if datos:
            # utf-8-sig para que Excel en Windows respete los acentos.
            with p.open("w", newline="", encoding="utf-8-sig") as fh:
                w = csv.DictWriter(fh, fieldnames=list(datos[0].keys()))
                w.writeheader()
                w.writerows(datos)
        return p

    p1 = escribir("mapa_1_productos.csv", productos)
    p2 = escribir("mapa_2_reglas_precio.csv", reglas)
    p3 = escribir("mapa_3_setups.csv", list(setups.values()))

    print(f"\n{'-'*76}")
    print(f"  {len(productos):>3} productos de servicio      → {p1.name}")
    print(f"  {len(reglas):>3} reglas de lista de precios → {p2.name}")
    print(f"  {len(setups):>3} productos de setup         → {p3.name}")
    print(f"\n  Carpeta: {args.salida}")

    lote = [p for p in productos if p["unidad_cobro"] == "lote"]
    conmin = [p for p in productos if p["qty_minima"] > 1 and p["unidad_cobro"] != "lote"]
    print(f"\n  Ojo al revisar:")
    print(f"    · {len(lote)} productos se cobran POR LOTE "
          f"({sum(1 for p in lote if p['escala_por_tinta'])} de ellos con cantidad = nº de tintas)")
    print(f"    · {len(conmin)} productos tienen cantidad MÍNIMA > 1")
    print(f"    · {len([p for p in productos if p['num_tramos']>1])} tienen curva de cantidad")
    print("\n  Nada de esto existe todavía en Odoo. Es una propuesta para revisar.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
