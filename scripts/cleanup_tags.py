#!/usr/bin/env python3
"""
Limpieza de product.tag en Odoo Online 19.0 — borra los tags que ya NO se quieren
(material, técnicas coladas, basura, huérfanos) tras poner en producción el fix del
sync que elimina la generación de tags de material.

CONSERVA (lista blanca) los tags que el sync legítimamente regenera:
  - Proveedor : 4P, PO, INN
  - Gama-tipo : Normal, Promo, Unico, Outlet
  - Gama-precio: Economico, Premium

Borra por REGLA: todo product.tag cuyo nombre normalizado NO esté en la lista blanca.

PRERREQUISITO CRÍTICO: el fix del sync (no generar material) debe estar YA en producción.
Si se borra antes, el sync regenera los tags de material en la siguiente corrida. Este
script no puede verificarlo solo → exige --confirmar-fix-en-produccion para --apply.

Solo toca product.tag (unlink). NUNCA escribe product.template / product.product /
product.attribute*. Borrar un product.tag solo elimina la etiqueta y sus relaciones m2m;
NO borra productos ni variantes.

Uso:
    python cleanup_tags.py                                          # DRY-RUN (no borra)
    python cleanup_tags.py --apply --confirmar-fix-en-produccion    # borra la lista B

Variables de entorno (desde .env):
    ODOO_URL, ODOO_API_KEY, ODOO_DATABASE (opcional)
"""

import argparse
import os
import sys
import unicodedata
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv

from odoo_client import OdooClient

TAG_MODEL = 'product.tag'

# Modelos sobre los que este script tiene PROHIBIDO cualquier escritura/borrado.
FORBIDDEN_MODELS = {'product.template', 'product.product',
                    'product.attribute', 'product.attribute.value',
                    'product.template.attribute.line'}

# Lista blanca (normalizada): tags que el sync regenera y que NO se borran.
WHITELIST = {
    '4p', 'po', 'inn',                       # proveedor
    'normal', 'promo', 'unico', 'outlet',    # gama-tipo
    'economico', 'premium',                  # gama-precio
}

DEFAULT_THRESHOLD = 160     # aborta si intentara borrar más que esto (protección)
_UNLINK_BATCH = 50


def _norm(s: str) -> str:
    """minúsculas + sin acentos + trim + espacios colapsados."""
    s = unicodedata.normalize('NFKD', s or '')
    s = ''.join(c for c in s if not unicodedata.combining(c))
    return ' '.join(s.lower().split())


# ─── Escritura guardada ──────────────────────────────────────────────────────

def _safe_unlink(client: OdooClient, model: str, ids: list[int]) -> None:
    if model != TAG_MODEL:
        raise RuntimeError(f'PROHIBIDO unlink sobre {model} (solo {TAG_MODEL})')
    if model in FORBIDDEN_MODELS:
        raise RuntimeError(f'PROHIBIDO: {model} en lista negra')
    if not ids:
        return
    client.unlink(model, ids)


# ─── Recolección ─────────────────────────────────────────────────────────────

def _usage_by_tag(client: OdooClient, model: str) -> dict[int, int]:
    """Cuenta registros de `model` que usan cada tag (vía product_tag_ids)."""
    recs = client.search_read_all(
        model, domain=[('active', 'in', [True, False])],
        fields=['id', 'product_tag_ids'], context={'active_test': False},
    )
    count: dict[int, int] = {}
    for r in recs:
        for tid in (r.get('product_tag_ids') or []):
            count[tid] = count.get(tid, 0) + 1
    return count


def load_tags(client: OdooClient) -> list[dict]:
    """
    Todos los product.tag con conteo de templates y variantes.

    Los conteos se calculan escaneando product.template / product.product (como
    audit_tags.py); leer los m2m inversos de product.tag da 500 en esta instancia.
    """
    # product.tag NO tiene campo `active` en esta instancia → dominio vacío.
    tags = client.search_read_all(
        TAG_MODEL,
        domain=[],
        fields=['id', 'name'],
    )
    tmpl_usage = _usage_by_tag(client, 'product.template')
    var_usage = _usage_by_tag(client, 'product.product')
    for t in tags:
        t['n_templates'] = tmpl_usage.get(t['id'], 0)
        t['n_variants'] = var_usage.get(t['id'], 0)
        t['norm'] = _norm(t.get('name', ''))
        t['huerfano'] = t['n_templates'] == 0 and t['n_variants'] == 0
    return tags


# ─── Reporte ─────────────────────────────────────────────────────────────────

def write_report(path: Path, mode: str, conservar: list[dict], borrar: list[dict],
                 total: int, resultado: dict | None) -> None:
    L: list[str] = []
    L.append(f'# Limpieza de product.tag — {datetime.now().isoformat(timespec="seconds")}  [{mode}]\n')
    L.append(f'- Tags totales: **{total}**')
    L.append(f'- Se CONSERVAN (lista blanca): **{len(conservar)}**')
    L.append(f'- Se BORRAN: **{len(borrar)}**')
    if resultado is not None:
        L.append(f'- Borrados OK: {resultado["ok"]} / {len(borrar)} · '
                 f'Fallidos: {len(resultado["fallidos"])}')
    L.append('')
    L.append('## CONSERVAR (lista blanca)\n')
    L.append('| tag | templates | variants |')
    L.append('|---|---:|---:|')
    for t in sorted(conservar, key=lambda x: x['name'].lower()):
        L.append(f'| {t["name"]} | {t["n_templates"]} | {t["n_variants"]} |')

    L.append('\n## BORRAR\n')
    L.append('| tag | templates | variants | huérfano |')
    L.append('|---|---:|---:|:---:|')
    for t in sorted(borrar, key=lambda x: (not x['huerfano'], -x['n_templates'] - x['n_variants'],
                                           x['name'].lower())):
        L.append(f'| {t["name"]} | {t["n_templates"]} | {t["n_variants"]} | '
                 f'{"sí" if t["huerfano"] else ""} |')

    if resultado and resultado['fallidos']:
        L.append('\n## ⚠ Fallidos\n')
        L.append('| tag_id | name | error |')
        L.append('|---:|---|---|')
        for fid, fname, err in resultado['fallidos']:
            L.append(f'| {fid} | {fname} | {err} |')

    L.append('\n> Nota: los tags de gama/proveedor (lista blanca) NO se tocan; el sync los '
             'regenera. Si tras la próxima corrida del sync REAPARECE algún tag de material, '
             'el fix NO está en producción.')
    with open(path, 'w', encoding='utf-8') as f:
        f.write('\n'.join(L) + '\n')


# ─── Borrado por lotes con tolerancia a fallos ───────────────────────────────

def unlink_tags(client: OdooClient, tags: list[dict]) -> dict:
    """Borra en lotes (huérfanos primero); aísla fallos por-tag. Devuelve resultado."""
    # Huérfanos primero (cero riesgo), luego el resto.
    ordenados = sorted(tags, key=lambda t: (not t['huerfano'],))
    ok = 0
    fallidos: list[tuple] = []
    lote_num = 0
    for i in range(0, len(ordenados), _UNLINK_BATCH):
        lote = ordenados[i:i + _UNLINK_BATCH]
        lote_num += 1
        ids = [t['id'] for t in lote]
        try:
            _safe_unlink(client, TAG_MODEL, ids)
            ok += len(ids)
            print(f'  lote {lote_num}: {len(ids)} borrados '
                  f'({"huérfanos" if all(t["huerfano"] for t in lote) else "mixto"})')
        except Exception:
            # aislar por-tag
            for t in lote:
                try:
                    _safe_unlink(client, TAG_MODEL, [t['id']])
                    ok += 1
                except Exception as exc:
                    fallidos.append((t['id'], t.get('name', ''), str(exc)[:140]))
                    print(f'  ✗ tag {t["id"]} ({t.get("name","")!r}): {str(exc)[:100]}')
    return {'ok': ok, 'fallidos': fallidos}


# ─── Main ────────────────────────────────────────────────────────────────────

def main() -> int:
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass

    parser = argparse.ArgumentParser(description='Limpieza de product.tag (material/técnicas/huérfanos)')
    parser.add_argument('--apply', action='store_true', help='Borra los tags de la lista B. Sin esto, dry-run.')
    parser.add_argument('--confirmar-fix-en-produccion', action='store_true',
                        help='OBLIGATORIO con --apply: confirma que el fix del sync ya está en producción.')
    parser.add_argument('--threshold', type=int, default=DEFAULT_THRESHOLD,
                        help=f'Máximo de tags a borrar antes de abortar (default {DEFAULT_THRESHOLD})')
    parser.add_argument('--output', '-o', help='Ruta del reporte .md')
    args = parser.parse_args()

    # Guarda dura: --apply exige la confirmación explícita del prerrequisito.
    if args.apply and not args.confirmar_fix_en_produccion:
        print('✗ ABORT: --apply requiere --confirmar-fix-en-produccion.\n'
              '  Borrar los tags ANTES de que el fix del sync esté en producción hace que el\n'
              '  sync REGENERE los tags de material en la siguiente corrida. Confírmalo y reintenta.',
              file=sys.stderr)
        return 2

    load_dotenv()
    odoo_url = os.environ.get('ODOO_URL')
    api_key = os.environ.get('ODOO_API_KEY')
    database = os.environ.get('ODOO_DATABASE')
    if not odoo_url or not api_key:
        print('✗ Falta ODOO_URL o ODOO_API_KEY en variables de entorno', file=sys.stderr)
        return 1

    today = datetime.now().strftime('%Y%m%d')
    Path('reports').mkdir(exist_ok=True)
    out_path = Path(args.output) if args.output else Path(f'reports/cleanup_tags_{today}.md')

    mode = 'APPLY' if args.apply else 'DRY-RUN'
    print(f'Limpieza de product.tag  [{mode}]')
    print(f'Odoo: {odoo_url}')

    client = OdooClient(odoo_url, api_key, database)

    # 1. Cargar y clasificar
    tags = load_tags(client)
    total = len(tags)
    conservar = [t for t in tags if t['norm'] in WHITELIST]
    borrar = [t for t in tags if t['norm'] not in WHITELIST]
    print(f'→ {total} tags | conservar {len(conservar)} | borrar {len(borrar)}')

    # 2. Salvaguarda: cada entrada de la lista blanca debe existir en Odoo
    encontrados = {t['norm'] for t in conservar}
    faltantes = WHITELIST - encontrados
    if faltantes:
        print(f'✗ ABORT: la lista blanca no matchea Odoo. Faltan tags para: '
              f'{sorted(faltantes)}.\n  Puede haber cambiado la grafía de un tag de '
              f'proveedor/gama. Revisa antes de borrar (no se borró nada).', file=sys.stderr)
        return 3

    # 3. Salvaguarda: umbral de seguridad
    if len(borrar) > args.threshold:
        print(f'✗ ABORT: se intentarían borrar {len(borrar)} tags (> umbral {args.threshold}). '
              f'Algo está mal; no se borró nada. Sube --threshold si es intencional.',
              file=sys.stderr)
        return 4

    # 4. Imprimir SIEMPRE ambas listas antes de cualquier borrado
    print('\n=== CONSERVAR (lista blanca) ===')
    for t in sorted(conservar, key=lambda x: x['name'].lower()):
        print(f'  ✔ {t["name"]:<18} templates={t["n_templates"]:>4} variants={t["n_variants"]:>5}')

    print(f'\n=== BORRAR ({len(borrar)}) ===')
    n_huerfanos = sum(1 for t in borrar if t['huerfano'])
    for t in sorted(borrar, key=lambda x: (not x['huerfano'],
                                           -x['n_templates'] - x['n_variants'], x['name'].lower())):
        flag = ' (huérfano)' if t['huerfano'] else ''
        print(f'  ✗ {t["name"]:<22} templates={t["n_templates"]:>4} '
              f'variants={t["n_variants"]:>5}{flag}')
    print(f'\n  ({n_huerfanos} huérfanos, {len(borrar) - n_huerfanos} en uso)')

    # 5. Reporte SIEMPRE (antes de borrar)
    resultado = None
    if args.apply:
        print(f'\n→ Borrando {len(borrar)} tags (huérfanos primero)...')
        resultado = unlink_tags(client, borrar)

    write_report(out_path, mode, conservar, borrar, total, resultado)

    # 6. Resumen
    print(f'\n=== Resumen [{mode}] ===')
    print(f'  Total: {total} | Conservados: {len(conservar)} | A borrar: {len(borrar)}')
    if args.apply:
        print(f'  Borrados OK: {resultado["ok"]} / {len(borrar)} | '
              f'Fallidos: {len(resultado["fallidos"])}')
    else:
        print(f'  DRY-RUN: no se borró nada. Re-ejecuta con '
              f'--apply --confirmar-fix-en-produccion.')
    print(f'  Reporte: {out_path}')
    print('  Nota: gama/proveedor NO se tocan (el sync los regenera). Si tras la próxima '
          'corrida reaparece un tag de material, el fix NO está en producción.')
    return 1 if (resultado and resultado['fallidos']) else 0


if __name__ == '__main__':
    sys.exit(main())
