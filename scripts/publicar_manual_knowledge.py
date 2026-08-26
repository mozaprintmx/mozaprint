#!/usr/bin/env python3
"""
Publica un manual del repo como artículo de **Información (Knowledge)** en Odoo.

Por qué existe
--------------
El manual anterior de personalización se publicó a mano una vez y nadie lo volvió
a tocar: acabó describiendo un botón que ya no existía y hubo que archivarlo. El
archivo del repo es la fuente; el artículo es una copia, y una copia que no se
puede regenerar con un comando se queda atrás.

Es idempotente: busca el artículo por título y lo **actualiza** si ya existe.

Los artículos se crean **internos** (`is_published=False`): se ven dentro de Odoo,
no desde el sitio web público.

⚠️ **Revisa el contenido antes de publicar.** El script avisa si detecta
credenciales, correos o nombres de personas, pero no sustituye leerlo: lo que
suba queda visible para todo el equipo.

    DRY-RUN POR DEFECTO. Sin --apply no escribe nada.

Uso:
    python scripts/publicar_manual_knowledge.py --target prod
    python scripts/publicar_manual_knowledge.py --target prod --apply --si-produccion
    python scripts/publicar_manual_knowledge.py --target test --apply \\
        --archivo docs/otro-manual.md --titulo "Otro manual"

Variables de entorno (analysis/supplier-sync/.env):
    ODOO_URL, ODOO_TEST_URL, ODOO_DB, ODOO_USER, ODOO_PASSWORD
"""

from __future__ import annotations

import argparse
import html
import io
import os
import re
import sys
import xmlrpc.client
from pathlib import Path

from dotenv import load_dotenv

if hasattr(sys.stdout, "buffer") and (sys.stdout.encoding or "").lower() not in ("utf-8", "utf8"):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

REPO = Path(__file__).resolve().parent.parent
ARCHIVO_DEF = "docs/manual-admin-precios-personalizacion.md"
TITULO_DEF = "Manual de administrador — Precios de personalización"

SENSIBLE = [
    ("credenciales", r"password|passwd|api[_ ]?key|token|secret|bearer"),
    ("correos", r"[\w.+-]+@[\w-]+\.[\w.]+"),
    ("nombres de personas", r"Juan Carlos|Karina|Rosy|Asomoza|Ponce"),
]


def conectar(url: str, db: str, user: str, pwd: str):
    uid = xmlrpc.client.ServerProxy(f"{url}/xmlrpc/2/common").authenticate(db, user, pwd, {})
    if not uid:
        raise SystemExit(f"✗ Autenticación fallida en {url} (db={db})")
    models = xmlrpc.client.ServerProxy(f"{url}/xmlrpc/2/object")

    def call(model, method, *args, **kw):
        return models.execute_kw(db, uid, pwd, model, method, list(args), kw)

    return call


def uno(r):
    return r[0] if isinstance(r, list) and r else r


def inline(s: str) -> str:
    s = html.escape(s)
    s = re.sub(r"`([^`]+)`", r"<code>\1</code>", s)
    s = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", s)
    s = re.sub(r"(?<!\*)\*([^*]+)\*(?!\*)", r"<em>\1</em>", s)
    # Los enlaces apuntan a archivos del repo, que nadie puede abrir desde Odoo:
    # se deja el texto y se tira el destino.
    return re.sub(r"\[([^\]]+)\]\(([^)]+)\)", r"\1", s)


def a_html(texto: str) -> str:
    """Markdown → HTML suficiente para Knowledge.

    Cubre lo que usan estos manuales: encabezados, tablas, bloques de código,
    citas, listas, separadores y énfasis. No pretende ser un conversor general.
    """
    out, i, ln = [], 0, texto.split("\n")
    while i < len(ln):
        linea = ln[i]
        if linea.startswith("```"):
            j, buf = i + 1, []
            while j < len(ln) and not ln[j].startswith("```"):
                buf.append(html.escape(ln[j]))
                j += 1
            out.append("<pre><code>" + "\n".join(buf) + "</code></pre>")
            i = j + 1
            continue
        if (linea.startswith("|") and i + 1 < len(ln)
                and set(ln[i + 1].replace("|", "").strip()) <= set("-: ")):
            cab = [x.strip() for x in linea.strip("|").split("|")]
            j, filas = i + 2, []
            while j < len(ln) and ln[j].startswith("|"):
                filas.append([x.strip() for x in ln[j].strip("|").split("|")])
                j += 1
            t = "<table class='table table-bordered'><thead><tr>"
            t += "".join(f"<th>{inline(x)}</th>" for x in cab) + "</tr></thead><tbody>"
            for f in filas:
                t += "<tr>" + "".join(f"<td>{inline(x)}</td>" for x in f) + "</tr>"
            out.append(t + "</tbody></table>")
            i = j
            continue
        if linea.startswith(">"):
            j, buf = i, []
            while j < len(ln) and ln[j].startswith(">"):
                buf.append(inline(ln[j].lstrip("> ").rstrip()))
                j += 1
            out.append("<blockquote><p>" + "<br/>".join(buf) + "</p></blockquote>")
            i = j
            continue
        if linea.startswith("#"):
            n = min(len(linea) - len(linea.lstrip("#")), 4)
            out.append(f"<h{n}>{inline(linea.lstrip('# '))}</h{n}>")
            i += 1
            continue
        if linea.strip() == "---":
            out.append("<hr/>")
            i += 1
            continue
        if linea.strip().startswith("- "):
            j, buf = i, []
            while j < len(ln) and ln[j].strip().startswith("- "):
                buf.append(f"<li>{inline(ln[j].strip()[2:])}</li>")
                j += 1
            out.append("<ul>" + "".join(buf) + "</ul>")
            i = j
            continue
        if linea.strip():
            out.append(f"<p>{inline(linea)}</p>")
        i += 1
    return "\n".join(out)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--target", choices=["test", "prod"], default="prod")
    ap.add_argument("--archivo", default=ARCHIVO_DEF)
    ap.add_argument("--titulo", default=TITULO_DEF)
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--si-produccion", action="store_true")
    args = ap.parse_args()

    load_dotenv(REPO / "analysis" / "supplier-sync" / ".env")
    if args.target == "prod":
        url, db = os.environ["ODOO_URL"].rstrip("/"), os.environ["ODOO_DB"]
        if args.apply and not args.si_produccion:
            print("✗ Para escribir en PRODUCCIÓN agrega --si-produccion.", file=sys.stderr)
            return 2
    else:
        url = os.environ["ODOO_TEST_URL"].rstrip("/")
        db = url.split("//")[1].split(".")[0]

    ruta = REPO / args.archivo
    if not ruta.exists():
        raise SystemExit(f"✗ No existe {ruta}")
    md = ruta.read_text(encoding="utf-8")
    cuerpo = a_html(md)

    print("=" * 78)
    print(f"  PUBLICAR MANUAL EN INFORMACIÓN  [{args.target.upper()}]  ·  "
          f"{'APLICAR' if args.apply else 'DRY-RUN'}")
    print(f"  {url}  ·  {args.archivo}")
    print("=" * 78)

    print(f"\n[1] Revisión de contenido sensible")
    plano = html.unescape(re.sub(r"<[^>]+>", " ", cuerpo))
    alerta = False
    for etiqueta, pat in SENSIBLE:
        hits = sorted(set(re.findall(pat, plano, re.I)))
        if hits:
            alerta = True
            print(f"  ⚠ {etiqueta}: {hits[:6]}")
        else:
            print(f"  ✓ {etiqueta}: ninguno")
    if alerta:
        print("\n  ⚠ Revisa los avisos: lo que subas lo verá todo el equipo.")

    print(f"\n[2] Conversión")
    print(f"  {len(md):,} caracteres de Markdown → {len(cuerpo):,} de HTML")
    print(f"  {cuerpo.count('<h')} encabezados · {cuerpo.count('<table')} tablas · "
          f"{cuerpo.count('<pre>')} bloques de código")

    call = conectar(url, db, os.environ["ODOO_USER"], os.environ["ODOO_PASSWORD"])
    print(f"\n[3] Artículo «{args.titulo}»")
    ex = call("knowledge.article", "search_read", [["name", "=", args.titulo]],
              fields=["name", "active"], context={"active_test": False})
    if ex:
        print(f"  ~ ACTUALIZAR el existente id={ex[0]['id']}"
              f"{' (estaba archivado, se reactiva)' if not ex[0]['active'] else ''}")
        if args.apply:
            call("knowledge.article", "write", [ex[0]["id"]],
                 {"body": cuerpo, "active": True})
            print(f"     → escrito · {url}/odoo/knowledge/{ex[0]['id']}")
    else:
        print("  + CREAR artículo interno (no visible desde el sitio web)")
        if args.apply:
            aid = uno(call("knowledge.article", "create", [{
                "name": args.titulo, "body": cuerpo,
                "internal_permission": "write",
                "is_article_visible_by_everyone": True,
            }]))
            print(f"     → creado id={aid} · {url}/odoo/knowledge/{aid}")

    print("\n" + "-" * 78)
    if not args.apply:
        print("  (simulacro) Agrega --apply para publicar.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
