#!/usr/bin/env python3
"""
Columna de Imagen en el PDF de cotización, como vistas PROPIAS que sobreviven a
las actualizaciones de Odoo.

El problema que resuelve
-----------------------
La columna se agregó con Studio editando **en sitio** la plantilla del módulo:
`sale.report_saleorder_document` (id 1025), cuyo `ir.model.data` es del módulo
`sale` con `noupdate=False`. Cada actualización recarga los datos XML del módulo
y **reescribe `arch_db`** — la personalización desaparece sin error ni traza. Ya
pasó en el salto a saas~19.2 (test, 2026-08-07) y volverá a pasar.

La solución: mover la columna a vistas heredadas propias, que el upgrade no
reescribe. Si algún día un anclaje deja de resolver, Odoo **desactiva** la vista
(fallo ruidoso y detectable) en vez de perderla en silencio.

Cómo se agrega una columna sin descuadrar el resto
--------------------------------------------------
La tabla de líneas tiene cinco tipos de fila y no todas se ajustan solas:

    tr_product        fila normal        → aquí va la imagen
    tr_section        sección            → `td_section_name` con colspan
    tr_section_group  resumen agrupado   → celdas sueltas, sin colspan
    tr_combo          combo              → estructura distinta en 19.0 y 19.2
    tr_note           nota               → colspan="99", inmune

En vez de recalcular colspans (frágil: la fórmula y hasta la estructura cambian
entre versiones), la regla es **una celda vacía por fila**. Cero aritmética, y
funciona igual en 19.0 y en saas~19.2 — verificado contra ambas bases.

La proforma mexicana
--------------------
`l10n_mx_edi_sale.report_saleorder_document_proforma` agrega DOS columnas
(Product code, Unit code) al encabezado y a la fila de producto, y nunca ajusta
las demás filas: la proforma se descuadra 2 columnas **de fábrica**, sin que
nuestra columna tenga nada que ver. La segunda vista lo corrige, aparte a
propósito: si Odoo arregla su bug, se borra esa vista y ya.

    DRY-RUN POR DEFECTO. Sin --apply no escribe nada.

Uso:
    python scripts/deploy_reporte_cotizacion.py --target test            # simulacro
    python scripts/deploy_reporte_cotizacion.py --target test --apply
    python scripts/deploy_reporte_cotizacion.py --target test --verificar   # solo lectura
    python scripts/deploy_reporte_cotizacion.py --target prod --apply --si-produccion \
        --limpiar-base                                   # además quita la edición de Studio
    python scripts/deploy_reporte_cotizacion.py --target test --rollback --apply

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
import xml.etree.ElementTree as ET
import xmlrpc.client
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv

# La consola de Windows (cp1252) no puede imprimir '→', 'ó', etc. El chequeo de
# encoding evita re-envolver si otro script ya lo hizo (audit_post_upgrade importa
# `cuadre_columnas` de aquí): dos wrappers sobre el mismo buffer pierden salida.
if hasattr(sys.stdout, "buffer") and (sys.stdout.encoding or "").lower() != "utf-8":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

REPO = Path(__file__).resolve().parent.parent
BACKUP_DIR = REPO / "backups"

KEY_BASE = "sale.report_saleorder_document"
KEY_PROFORMA = "l10n_mx_edi_sale.report_saleorder_document_proforma"
KEY_IMAGEN = "mozaprint.report_saleorder_imagen"
KEY_MX = "mozaprint.report_saleorder_proforma_columnas"

# Anclajes por nombre de celda. Se comprueban ANTES de escribir: si un upgrade se
# lleva uno, el script se detiene con un mensaje claro en vez de crear una vista
# que Odoo desactivaría después.
ANCLAS_BASE = ["th_description", "td_product_name", "td_section_name",
               "td_combo_name", "td_section_group_name"]
ANCLAS_MX = ["td_combo_price", "td_section_group_name", "td_section_group_discount"]

# Celdas que Studio dejó incrustadas en la plantilla del módulo (--limpiar-base).
CELDAS_STUDIO = ["th_name", "td_image"]

ARCH_IMAGEN = """<data>
    <!-- Encabezado: <th>, no <td> (Studio lo había puesto como td). -->
    <th name="th_description" position="before">
        <th name="th_image" class="text-start" style="width:70px;">Imagen</th>
    </th>

    <!-- Fila de producto: la imagen. max-* en vez de width/height fijos, que
         deformaban las imágenes no cuadradas. image_128 basta a 60px impresos. -->
    <td name="td_product_name" position="before">
        <td name="td_image" class="align-top">
            <img t-if="line.product_id.image_128"
                 t-att-src="image_data_uri(line.product_id.image_128)"
                 style="max-width:60px; max-height:60px;"/>
        </td>
    </td>

    <!-- Las demás filas: una celda vacía cada una. Sin tocar ningún colspan. -->
    <td name="td_section_name" position="before">
        <td name="td_image_section"/>
    </td>
    <td name="td_combo_name" position="before">
        <td name="td_image_combo"/>
    </td>
    <td name="td_section_group_name" position="before">
        <td name="td_image_section_group"/>
    </td>
</data>"""

ARCH_MX = """<data>
    <!-- Suma 2 sobre lo que haya calculado el módulo, sin repetir su fórmula:
         así sobrevive a que Odoo la cambie entre versiones. Va después del
         t-set original y antes del que lo fuerza a 99. -->
    <xpath expr="//t[@t-set='section_name_colspan']" position="after">
        <t t-set="section_name_colspan" t-value="section_name_colspan + 2"/>
    </xpath>

    <!-- Resumen agrupado: las celdas van en la misma posición que las de
         l10n_mx (Product code tras la descripción, Unit code tras el descuento). -->
    <td name="td_section_group_name" position="after">
        <td name="td_mx_section_group_code"/>
    </td>
    <td name="td_section_group_discount" position="after">
        <td name="td_mx_section_group_unit"/>
    </td>

    <!-- Combo: la celda de precio es la que va al extremo derecho. -->
    <td name="td_combo_price" position="before">
        <td name="td_mx_combo_code"/>
        <td name="td_mx_combo_unit"/>
    </td>
</data>"""


# ---------------------------------------------------------------- conexión ---
class Odoo:
    """Cliente XML-RPC admin con interruptor de dry-run: en simulacro, toda
    escritura se registra y devuelve un id ficticio, nunca llega a Odoo."""

    def __init__(self, url: str, db: str, user: str, pwd: str, apply: bool):
        self.url, self.db, self.pwd, self.apply = url.rstrip("/"), db, pwd, apply
        self.uid = xmlrpc.client.ServerProxy(f"{self.url}/xmlrpc/2/common").authenticate(
            db, user, pwd, {})
        if not self.uid:
            raise SystemExit(f"✗ Autenticación fallida en {self.url} (db={db})")
        self._m = xmlrpc.client.ServerProxy(f"{self.url}/xmlrpc/2/object")
        self._sim = 0

    def read_call(self, model: str, method: str, *args, **kw):
        return self._m.execute_kw(self.db, self.uid, self.pwd, model, method, list(args), kw)

    def write_call(self, model: str, method: str, *args, **kw):
        if not self.apply:
            self._sim -= 1
            return [self._sim] if method == "create" else True
        return self._m.execute_kw(self.db, self.uid, self.pwd, model, method, list(args), kw)

    def version(self) -> str:
        return xmlrpc.client.ServerProxy(
            f"{self.url}/xmlrpc/2/common").version().get("server_serie", "?")

    def vista(self, key: str) -> dict | None:
        """Busca por key incluyendo ARCHIVADAS: si un upgrade desactivó la vista,
        hay que repararla, no crear un duplicado."""
        r = self.read_call("ir.ui.view", "search_read", [["key", "=", key]],
                           fields=["id", "key", "name", "active", "arch_db", "inherit_id"],
                           context={"active_test": False})
        return r[0] if r else None

    def idiomas(self) -> list[str]:
        """`arch_db` es un campo TRADUCIDO: cada idioma guarda su propio valor.

        Limpiar solo uno dejaría la columna incrustada en el otro, y el reporte
        se renderiza con `t-lang="doc.partner_id.lang"` — saldría duplicada para
        unos clientes y no para otros. `en_US` va siempre: es el valor fuente,
        exista o no como idioma activo.
        """
        activos = [l["code"] for l in
                   self.read_call("res.lang", "search_read", [["active", "=", True]],
                                  fields=["code"])]
        return list(dict.fromkeys(["en_US"] + activos))

    def arch(self, vid: int, lang: str) -> str:
        return self.read_call("ir.ui.view", "read", [vid], fields=["arch_db"],
                              context={"lang": lang})[0]["arch_db"] or ""


# ------------------------------------------------- cuadre de columnas (qweb) ---
def _ev(expr: str, variables: dict):
    """Evalúa una expresión de qweb con las variables conocidas. None si no se puede."""
    try:
        return eval(expr, {"__builtins__": {}}, dict(variables))  # noqa: S307
    except Exception:
        return None


def _ancho(celda: ET.Element, variables: dict) -> int | None:
    """Columnas que ocupa una celda. None = no se renderiza en este escenario."""
    cond = celda.get("t-if")
    if cond is not None:
        v = _ev(cond, variables)
        if v is False:
            return None            # se sabe que NO sale
        # v is None → condición que depende de la línea: se asume que sí sale.
    span = celda.get("colspan") or celda.get("t-att-colspan")
    if span is None:
        return 1
    v = _ev(span, variables)
    return int(v) if isinstance(v, (int, float)) else 1


def _fila(tr: ET.Element, variables: dict) -> int | None:
    """Suma de columnas de una fila. None si es de las que abarcan todo (colspan 99)."""
    v = dict(variables)
    total = 0
    for hijo in tr:
        if hijo.tag == "t":
            if hijo.get("t-set") and hijo.get("t-value") is not None:
                val = _ev(hijo.get("t-value"), v)
                if val is not None:
                    v[hijo.get("t-set")] = val
            # Un <t t-if=...> que no se puede evaluar (depende de la línea) se
            # ignora: es justo el bloque que fuerza colspan=99.
            continue
        if hijo.tag in ("td", "th"):
            a = _ancho(hijo, v)
            if a is None:
                continue
            if a >= 99:
                return None
            total += a
    return total


def cuadre_columnas(arch: str) -> list[str]:
    """Comprueba que TODAS las filas de la tabla sumen las mismas columnas.

    Es el invariante de verdad del reporte: no "existe la columna de imagen",
    sino "ninguna fila queda corta". Se prueba en los cuatro escenarios de
    descuento/impuestos, porque esas dos columnas son condicionales.
    """
    problemas: list[str] = []
    try:
        root = ET.fromstring(arch)
    except ET.ParseError as e:
        return [f"el arch combinado no parsea: {e}"]

    tabla = next((el for el in root.iter("table")
                  if "o_main_table" in (el.get("class") or "")), None)
    if tabla is None:
        return ["no se encontró la tabla de líneas (o_main_table)"]

    for desc in (False, True):
        for imp in (False, True):
            variables = {"display_discount": desc, "display_taxes": imp}
            esperado, escenario = None, f"descuento={desc} impuestos={imp}"
            for tr in tabla.iter("tr"):
                total = _fila(tr, variables)
                if total is None:
                    continue
                nombre = tr.get("name") or "(sin nombre)"
                if esperado is None:      # la primera fila es el encabezado
                    esperado = total
                    continue
                if total != esperado:
                    problemas.append(
                        f"[{escenario}] {nombre}: {total} columnas, el encabezado tiene "
                        f"{esperado} (faltan {esperado - total})")
    return problemas


# ------------------------------------------------------------------ deploy ---
def anclas_presentes(arch: str, nombres: list[str]) -> list[str]:
    return [n for n in nombres if f'name="{n}"' not in arch]


def idiomas_sucios(o: Odoo, base_id: int) -> list[str]:
    """Idiomas cuyo arch todavía trae la columna incrustada por Studio."""
    return [lang for lang in o.idiomas()
            if any(f'name="{c}"' in o.arch(base_id, lang) for c in CELDAS_STUDIO)]


def upsert_vista(o: Odoo, key: str, nombre: str, arch: str, padre_id: int, man: dict) -> int:
    vals = {"name": nombre, "key": key, "type": "qweb", "inherit_id": padre_id,
            "arch": arch, "active": True}
    v = o.vista(key)
    if v:
        nota = "actualizada" if v["active"] else "REACTIVADA (estaba desactivada)"
        o.write_call("ir.ui.view", "write", [v["id"]], vals)
        print(f"  [ ok] {key} (id={v['id']}, {nota})")
        return v["id"]
    nid = o.write_call("ir.ui.view", "create", [vals])
    nid = nid[0] if isinstance(nid, list) else nid
    man["vistas"].append({"key": key, "id": nid})
    print(f"  [NEW] {key} (id={nid}){'' if o.apply else ' (simulado)'}")
    return nid


def _sin_columna_studio(arch: str) -> str:
    """Quita las dos celdas de Studio y devuelve el colspan a su valor de fábrica."""
    nuevo = arch
    for celda in CELDAS_STUDIO:
        nuevo = re.sub(rf'\s*<td name="{celda}"[^>]*>.*?</td>', "", nuevo, flags=re.S)
    # El "4 + (…)" que compensaba la columna vuelve a ser el "3 + (…)" de fábrica.
    return re.sub(r'(<t t-set="section_name_colspan" t-value=")4(\s*\+)', r"\g<1>3\g<2>", nuevo)


def limpiar_base(o: Odoo, base: dict, man: dict) -> bool:
    """Quita de la plantilla del módulo la columna que Studio incrustó ahí.

    Cirugía sobre el texto, no restauración del respaldo de Studio: ese respaldo
    es de agosto 2025 y devolverlo pisaría cualquier corrección que Odoo haya
    hecho a la plantilla desde entonces.

    Se hace IDIOMA POR IDIOMA (ver Odoo.idiomas): dejar uno sucio significaría
    columna duplicada para los clientes que reciban el PDF en ese idioma.
    """
    tocadas, previos = [], {}
    for lang in o.idiomas():
        arch = o.arch(base["id"], lang)
        previos[lang] = arch
        if not any(f'name="{c}"' in arch for c in CELDAS_STUDIO):
            print(f"  [ ok] {lang}: la plantilla ya está limpia")
            continue

        nuevo = _sin_columna_studio(arch)
        try:
            ET.fromstring(nuevo)
        except ET.ParseError as e:
            raise SystemExit(f"✗ [{lang}] la limpieza dejó XML inválido ({e}). No se escribió nada.")
        restantes = [c for c in CELDAS_STUDIO if f'name="{c}"' in nuevo]
        if restantes:
            raise SystemExit(f"✗ [{lang}] quedaron celdas de Studio tras la limpieza: {restantes}")

        print(f"  [FIX] {lang}: se quitan {CELDAS_STUDIO} ({len(arch)} → {len(nuevo)} chars)")
        o.write_call("ir.ui.view", "write", [base["id"]], {"arch_db": nuevo},
                     context={"lang": lang})
        tocadas.append(lang)

    if tocadas:
        man["base_arch_previo"] = {"id": base["id"], "por_idioma": previos}
    return bool(tocadas)


def desplegar(o: Odoo, target: str, limpiar: bool) -> int:
    man = {"target": target, "url": o.url, "db": o.db,
           "ts": datetime.now().isoformat(timespec="seconds"),
           "vistas": [], "base_arch_previo": None}

    base = o.vista(KEY_BASE)
    if not base:
        print(f"✗ No existe {KEY_BASE}. ¿Está instalado el módulo de Ventas?")
        return 1

    print("\n[1] Anclajes en la plantilla base")
    faltan = anclas_presentes(base["arch_db"] or "", ANCLAS_BASE)
    if faltan:
        print(f"  ✗ Faltan anclajes: {faltan}")
        print("    La versión de Odoo cambió la tabla de líneas. Hay que revisar el arch")
        print(f"    de la vista id={base['id']} y actualizar ARCH_IMAGEN antes de seguir.")
        return 1
    print(f"  ✓ los {len(ANCLAS_BASE)} anclajes están presentes")

    print("\n[2] Vistas propias")
    upsert_vista(o, KEY_IMAGEN, "Mozaprint: columna de imagen en cotización",
                 ARCH_IMAGEN, base["id"], man)

    proforma = o.vista(KEY_PROFORMA)
    if not proforma:
        print(f"  · {KEY_PROFORMA} no existe (l10n_mx_edi_sale no instalado): se omite")
    else:
        faltan_mx = anclas_presentes(base["arch_db"] or "", ANCLAS_MX)
        if faltan_mx:
            print(f"  ✗ Faltan anclajes para la proforma: {faltan_mx}. Se omite esa vista.")
        else:
            upsert_vista(o, KEY_MX, "Mozaprint: cuadre de columnas de la proforma MX",
                         ARCH_MX, proforma["id"], man)

    print("\n[3] Plantilla del módulo (edición de Studio)")
    if limpiar:
        limpiar_base(o, base, man)
    else:
        sucios = idiomas_sucios(o, base["id"])
        if sucios:
            print(f"  ⚠ La plantilla TODAVÍA trae la columna incrustada por Studio en: {sucios}")
            print("    Con las dos vistas activas, la columna saldría DUPLICADA.")
            print("    Corre otra vez con --limpiar-base para quitarla.")
        else:
            print("  [ ok] limpia en todos los idiomas")

    if o.apply:
        BACKUP_DIR.mkdir(exist_ok=True)
        p = BACKUP_DIR / f"reporte_cotizacion_{target}_{datetime.now():%Y%m%d_%H%M%S}.json"
        p.write_text(json.dumps(man, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"\n✓ Aplicado. Manifiesto (para --rollback): {p.name}")
        print("  Siguiente: --verificar, y sacar los dos PDFs (cotización y proforma).")
    else:
        print("\n(simulacro) Nada se escribió. Agrega --apply.")
    return 0


# ------------------------------------------------------------- verificación ---
def verificar(o: Odoo) -> int:
    """Salud del reporte. SOLO LECTURA. Devuelve el número de problemas."""
    problemas: list[str] = []
    print("\n=== VERIFICACIÓN (solo lectura, no escribe nada) ===")
    print(f"  Odoo {o.version()}  ·  {o.url}  ·  db={o.db}\n")

    print("[1] Vistas propias")
    for key in (KEY_IMAGEN, KEY_MX):
        v = o.vista(key)
        if not v:
            if key == KEY_MX and not o.vista(KEY_PROFORMA):
                print(f"  · {key}: no aplica (l10n_mx_edi_sale no instalado)")
                continue
            problemas.append(f"falta la vista {key}")
            print(f"  ✗ {key}: NO EXISTE")
        elif not v["active"]:
            problemas.append(f"la vista {key} está DESACTIVADA")
            print(f"  ✗ {key}: existe (id={v['id']}) pero está DESACTIVADA "
                  f"— típico de un upgrade cuyo xpath dejó de resolver")
        else:
            print(f"  ✓ {key}: activa (id={v['id']})")

    print("\n[2] La plantilla del módulo sigue limpia (en todos los idiomas)")
    base = o.vista(KEY_BASE)
    sucios = idiomas_sucios(o, base["id"]) if base else []
    if sucios:
        problemas.append(f"la plantilla del módulo trae celdas de Studio en {sucios}")
        print(f"  ✗ {KEY_BASE} tiene {CELDAS_STUDIO} incrustadas en {sucios} → columna duplicada")
    else:
        print(f"  ✓ {KEY_BASE} sin ediciones in-place ({', '.join(o.idiomas())})")

    print("\n[3] Cuadre de columnas del arch combinado")
    for etiqueta, key in (("cotización", KEY_BASE), ("proforma MX", KEY_PROFORMA)):
        v = o.vista(key)
        if not v:
            print(f"  · {etiqueta}: no aplica")
            continue
        for lang in o.idiomas():
            arch = o.read_call("ir.ui.view", "get_combined_arch", [v["id"]],
                               context={"lang": lang})
            hallazgos = cuadre_columnas(arch)
            img = 'name="td_image"' in arch
            rotulo = f"{etiqueta} [{lang}]"
            if not img:
                problemas.append(f"{rotulo}: el arch combinado no trae la columna de imagen")
            if hallazgos:
                problemas.extend(f"{rotulo}: {h}" for h in hallazgos)
                print(f"  ✗ {rotulo} (id={v['id']}) — imagen={'sí' if img else 'NO'}")
                for h in hallazgos:
                    print(f"      {h}")
            else:
                print(f"  ✓ {rotulo} (id={v['id']}): todas las filas cuadran · "
                      f"imagen={'sí' if img else 'NO'}")

    print("\n" + "-" * 74)
    if problemas:
        print(f"  ✗ {len(problemas)} problema(s):")
        for p in problemas:
            print(f"      - {p}")
    else:
        print("  ✓ El reporte está completo y cuadrado.")
    return len(problemas)


# ---------------------------------------------------------------- rollback ---
def rollback(o: Odoo, target: str) -> int:
    reps = sorted(BACKUP_DIR.glob(f"reporte_cotizacion_{target}_*.json"))
    if not reps:
        print(f"✗ No hay manifiesto para {target} en {BACKUP_DIR}.")
        return 1
    man = json.loads(reps[-1].read_text(encoding="utf-8"))
    print(f"Manifiesto: {reps[-1].name} ({man['ts']})")

    for v in man["vistas"]:
        print(f"  borrar vista {v['key']} (id={v['id']})")
        if o.apply:
            try:
                o.write_call("ir.ui.view", "unlink", [v["id"]])
            except Exception as e:
                print(f"    ⚠ no se pudo borrar: {str(e)[:120]}")

    prev = man.get("base_arch_previo")
    if prev:
        for lang, arch in prev["por_idioma"].items():
            print(f"  restaurar arch de la plantilla id={prev['id']} [{lang}] "
                  f"({len(arch)} chars, con la edición de Studio)")
            if o.apply:
                o.write_call("ir.ui.view", "write", [prev["id"]], {"arch_db": arch},
                             context={"lang": lang})

    if not o.apply:
        print("\n(simulacro) Agrega --apply para revertir.")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--target", choices=["test", "prod"], default="test")
    ap.add_argument("--apply", action="store_true", help="Escribe. Sin esto, simulacro.")
    ap.add_argument("--si-produccion", action="store_true", help="Guardarraíl para --target prod")
    ap.add_argument("--verificar", action="store_true", help="Salud, solo lectura")
    ap.add_argument("--limpiar-base", action="store_true",
                    help="Quita de la plantilla del módulo la columna incrustada por Studio")
    ap.add_argument("--rollback", action="store_true", help="Revierte usando el último manifiesto")
    args = ap.parse_args()

    load_dotenv(REPO / "analysis" / "supplier-sync" / ".env")
    if args.target == "prod":
        url, db = os.environ["ODOO_URL"].rstrip("/"), os.environ["ODOO_DB"]
        if args.apply and not args.verificar and not args.si_produccion:
            print("✗ Para escribir en PRODUCCIÓN agrega --si-produccion (guardarraíl).",
                  file=sys.stderr)
            return 2
    else:
        url = os.environ["ODOO_TEST_URL"].rstrip("/")
        db = url.split("//")[1].split(".")[0]  # el subdominio ES la BD en staging

    o = Odoo(url, db, os.environ["ODOO_USER"], os.environ["ODOO_PASSWORD"], args.apply)

    if args.verificar:
        return 1 if verificar(o) else 0

    modo = "APLICAR" if args.apply else "DRY-RUN (no escribe)"
    print("=" * 74)
    print(f"  REPORTE DE COTIZACIÓN — columna de imagen  [{args.target.upper()}]  ·  {modo}")
    print(f"  {url}  (db={db})  ·  Odoo {o.version()}")
    print("=" * 74)

    if args.rollback:
        return rollback(o, args.target)
    return desplegar(o, args.target, args.limpiar_base)


if __name__ == "__main__":
    sys.exit(main())
