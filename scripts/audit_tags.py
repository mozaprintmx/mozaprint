#!/usr/bin/env python3
"""
Auditoría de SOLO LECTURA de los Product Tags (product.tag) en Odoo Online 19.0.

Fotografía el estado de los tags ANTES de agregar tags de familia de color:
campos reales, uso por templates y variantes, huérfanos, duplicados por nombre
normalizado, agrupaciones por prefijo, y colisiones con las 14 familias de color.
No escribe NADA en Odoo. Sin PII: solo nombres de tag y conteos.

Uso:
    python audit_tags.py
    python audit_tags.py --output reports/mi_audit.json

Variables de entorno (desde .env):
    ODOO_URL, ODOO_API_KEY, ODOO_DATABASE (opcional)
"""

import argparse
import csv
import json
import os
import sys
import unicodedata
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

from odoo_client import OdooClient

TAG_MODEL = 'product.tag'
TEMPLATE_MODEL = 'product.template'
VARIANT_MODEL = 'product.product'
FAMILIAS_CSV = Path(__file__).resolve().parent.parent / 'data' / 'colores_familias.csv'

# Campos candidatos (no se asume; se usa el que exista vía fields_get)
COLOR_FIELD_CANDIDATES = ['color', 'html_color']
VISIBLE_FIELD_CANDIDATES = ['visible_to_customers', 'is_published', 'website_published']

# Tags que el sync pone en VARIANTES (no en templates): proveedor y precio.
PROVEEDOR_TAGS = {'4p', 'po', 'inn'}
PRECIO_TAGS = {'economico', 'premium'}


def safe_call(fn, *args, fallback=None, label='', errors=None, **kwargs):
    try:
        return fn(*args, **kwargs)
    except Exception as exc:
        print(f'  ⚠ [{label}] {exc}')
        if errors is not None:
            errors.append({'label': label, 'error': str(exc)})
        return fallback


def _norm(s: str) -> str:
    s = unicodedata.normalize('NFKD', s or '')
    s = ''.join(c for c in s if not unicodedata.combining(c))
    return ' '.join(s.lower().split())


def _load_familias() -> set[str]:
    if not FAMILIAS_CSV.exists():
        return set()
    with open(FAMILIAS_CSV, encoding='utf-8') as f:
        lines = [ln for ln in f if not ln.lstrip().startswith('#')]
    return {_norm(r['familia']) for r in csv.DictReader(lines)}


# ─── Recolección ─────────────────────────────────────────────────────────────

def detect_field(meta: dict, candidates: list[str]) -> str | None:
    for c in candidates:
        if c in meta:
            return c
    return None


def _tag_usage(client: OdooClient, model: str, errors: list) -> dict[int, int]:
    """Cuenta cuántos registros de `model` usan cada tag (vía product_tag_ids)."""
    recs = safe_call(
        client.search_read_all, model,
        domain=[('active', 'in', [True, False])],
        fields=['id', 'product_tag_ids'], context={'active_test': False},
        label=f'{model}.product_tag_ids', errors=errors,
    ) or []
    count: dict[int, int] = defaultdict(int)
    for r in recs:
        for tid in (r.get('product_tag_ids') or []):
            count[tid] += 1
    return dict(count)


def collect(client: OdooClient, errors: list) -> dict[str, Any]:
    print('→ fields_get(product.tag)...')
    meta = safe_call(client.fields_get, TAG_MODEL, ['string', 'type'],
                     label='fields_get(product.tag)', errors=errors) or {}
    color_field = detect_field(meta, COLOR_FIELD_CANDIDATES)
    visible_field = detect_field(meta, VISIBLE_FIELD_CANDIDATES)

    fields = ['id', 'name']
    for f in (color_field, visible_field):
        if f:
            fields.append(f)
    if 'active' in meta:
        fields.append('active')

    print('→ product.tag...')
    tags = safe_call(
        client.search_read_all, TAG_MODEL,
        domain=[('active', 'in', [True, False])] if 'active' in meta else [],
        fields=fields, context={'active_test': False},
        label='product.tag', errors=errors,
    ) or []

    print('→ uso por templates...')
    tmpl_usage = _tag_usage(client, TEMPLATE_MODEL, errors)
    print('→ uso por variantes...')
    var_usage = _tag_usage(client, VARIANT_MODEL, errors)

    return {
        'fields_meta': {k: {'string': v.get('string'), 'type': v.get('type')}
                        for k, v in meta.items()},
        'color_field': color_field,
        'visible_field': visible_field,
        'tags': tags,
        'tmpl_usage': tmpl_usage,
        'var_usage': var_usage,
    }


# ─── Análisis ────────────────────────────────────────────────────────────────

def analyze(raw: dict[str, Any]) -> dict[str, Any]:
    print('→ Analizando...')
    tags = raw['tags']
    tmpl_usage = raw['tmpl_usage']
    var_usage = raw['var_usage']
    color_field = raw['color_field']
    visible_field = raw['visible_field']
    familias = _load_familias()

    stats: list[dict] = []
    for t in tags:
        tid = t['id']
        tmpls = tmpl_usage.get(tid, 0)
        vars_ = var_usage.get(tid, 0)
        nombre = t.get('name', '')
        n = _norm(nombre)
        if n in familias:
            tipo = 'color'
        elif n in PROVEEDOR_TAGS:
            tipo = 'proveedor'
        elif n in PRECIO_TAGS:
            tipo = 'precio'
        else:
            tipo = 'material/otros'
        stats.append({
            'id': tid,
            'name': nombre,
            'name_norm': n,
            'color': t.get(color_field) if color_field else None,
            'visible': t.get(visible_field) if visible_field else None,
            'active': t.get('active', True),
            'templates': tmpls,
            'variants': vars_,
            'tipo_inferido': tipo,
            'huerfano': tmpls == 0 and vars_ == 0,
            'un_solo_template': tmpls == 1,
        })
    stats.sort(key=lambda s: (s['templates'], s['variants']), reverse=True)

    # Duplicados por nombre normalizado
    by_norm: dict[str, list] = defaultdict(list)
    for s in stats:
        by_norm[s['name_norm']].append(s)
    duplicados = [
        {'name_norm': k, 'variantes': [{'id': s['id'], 'name': s['name'],
                                        'templates': s['templates'], 'variants': s['variants']}
                                       for s in v]}
        for k, v in by_norm.items() if len(v) >= 2
    ]

    # Agrupaciones por primera palabra (posible fragmentación de material)
    by_prefix: dict[str, list] = defaultdict(list)
    for s in stats:
        first = s['name_norm'].split()[0] if s['name_norm'] else ''
        if first:
            by_prefix[first].append(s['name'])
    prefijos = sorted(
        ({'prefijo': k, 'n_tags': len(v), 'tags': sorted(v)}
         for k, v in by_prefix.items() if len(v) >= 2),
        key=lambda x: x['n_tags'], reverse=True,
    )

    # Colisiones con las 14 familias de color
    colisiones = [{'familia': s['name'], 'tag_id': s['id'],
                   'templates': s['templates'], 'variants': s['variants']}
                  for s in stats if s['name_norm'] in familias]

    # Distribución por tipo inferido
    dist_tipo: dict[str, int] = defaultdict(int)
    for s in stats:
        dist_tipo[s['tipo_inferido']] += 1

    huerfanos = [s for s in stats if s['huerfano']]
    un_prod = [s for s in stats if s['un_solo_template'] and s['variants'] == 0]

    return {
        'color_field': color_field,
        'visible_field': visible_field,
        'totales': {
            'tags': len(stats),
            'huerfanos': len(huerfanos),
            'un_solo_template_sin_variantes': len(un_prod),
            'duplicados_norm': len(duplicados),
        },
        'distribucion_por_tipo': dict(dist_tipo),
        'tags': stats,
        'huerfanos': [{'id': s['id'], 'name': s['name']} for s in huerfanos],
        'un_solo_producto': [{'id': s['id'], 'name': s['name'], 'templates': s['templates']}
                             for s in un_prod],
        'duplicados': duplicados,
        'prefijos': prefijos,
        'colisiones_familia_color': colisiones,
        'familias_referencia': sorted(_load_familias()),
    }


# ─── Reporte ─────────────────────────────────────────────────────────────────

def render_markdown(data: dict[str, Any]) -> str:
    an = data['analysis']
    ts = data['meta']['timestamp'][:10]
    t = an['totales']
    errs = data['meta'].get('errors', [])
    L: list[str] = [
        f'# Auditoría de Product Tags — {ts}',
        '',
        'Fotografía de `product.tag` ANTES de agregar tags de familia de color. SOLO LECTURA.',
        '',
        '## Campos reales de product.tag (fields_get)',
        '',
        f'- Campo de color detectado: `{an["color_field"]}`',
        f'- Campo de visibilidad al cliente detectado: `{an["visible_field"]}`',
        '',
        '| campo | tipo | label |',
        '|---|---|---|',
    ]
    for k, m in sorted(data['raw_fields'].items()):
        L.append(f'| {k} | {m.get("type")} | {m.get("string")} |')

    L += [
        '',
        '## Resumen',
        '',
        f'- Tags totales: **{t["tags"]}**',
        f'- Huérfanos (0 templates y 0 variantes): **{t["huerfanos"]}**',
        f'- Usado por 1 template (y 0 variantes): **{t["un_solo_template_sin_variantes"]}**',
        f'- Grupos de nombre duplicado (normalizado): **{t["duplicados_norm"]}**',
        f'- Distribución por tipo inferido: `{an["distribucion_por_tipo"]}`',
        '',
        '## Colisiones con las 14 familias de color',
        '',
    ]
    if an['colisiones_familia_color']:
        L += ['| Familia | tag_id | templates | variants |', '|---|---|---|---|',
              *[f'| {c["familia"]} | {c["tag_id"]} | {c["templates"]} | {c["variants"]} |'
                for c in an['colisiones_familia_color']]]
    else:
        L.append(f'_Ninguna. No existe tag cuyo nombre coincida con una familia '
                 f'({", ".join(an["familias_referencia"])})._')

    L += ['', '## Todos los tags (por uso desc)', '',
          '| Tag | tipo inf. | color | visible | templates | variants | bandera |',
          '|---|---|---|---|---|---|---|']
    for s in an['tags']:
        flag = '🔴 huérfano' if s['huerfano'] else ('🟠 1 template' if s['un_solo_template'] else '')
        L.append(f'| {s["name"]} | {s["tipo_inferido"]} | {s["color"]} | {s["visible"]} | '
                 f'{s["templates"]} | {s["variants"]} | {flag} |')

    L += ['', '## 🔴 Huérfanos (0 uso) — candidatos a depurar', '']
    L.append(', '.join(f'{h["name"]}' for h in an['huerfanos']) or '_Ninguno._')

    L += ['', '## 🔗 Duplicados por nombre normalizado', '']
    if an['duplicados']:
        for d in an['duplicados']:
            variantes = '; '.join(f'{v["name"]}(id{v["id"]}, {v["templates"]}t/{v["variants"]}v)'
                                  for v in d['variantes'])
            L.append(f'- `{d["name_norm"]}` → {variantes}')
    else:
        L.append('_Ninguno._')

    L += ['', '## 🧩 Agrupaciones por primera palabra (posible fragmentación de material)', '']
    if an['prefijos']:
        L += ['| Prefijo | # tags | tags |', '|---|---|---|',
              *[f'| {p["prefijo"]} | {p["n_tags"]} | {", ".join(p["tags"])} |'
                for p in an['prefijos']]]
    else:
        L.append('_Ninguna._')

    if errs:
        L += ['', '## Errores/advertencias', '', *[f'- `{e["label"]}`: {e["error"]}' for e in errs]]
    L += ['', f'_Generado: {data["meta"]["timestamp"]}_', '']
    return '\n'.join(L)


# ─── Main ────────────────────────────────────────────────────────────────────

def main() -> int:
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass

    load_dotenv()
    parser = argparse.ArgumentParser(description='Auditoría de solo lectura de product.tag')
    parser.add_argument('--output', '-o', help='Ruta del JSON de salida')
    args = parser.parse_args()

    odoo_url = os.environ.get('ODOO_URL')
    api_key = os.environ.get('ODOO_API_KEY')
    database = os.environ.get('ODOO_DATABASE')
    if not odoo_url or not api_key:
        print('✗ Falta ODOO_URL o ODOO_API_KEY en variables de entorno', file=sys.stderr)
        return 1

    today = datetime.now().strftime('%Y%m%d')
    Path('reports').mkdir(exist_ok=True)
    json_path = Path(args.output) if args.output else Path(f'reports/audit_tags_{today}.json')
    md_path = json_path.with_suffix('.md')

    print(f'Mozaprint — Auditoría de product.tag → {json_path}')
    print(f'Odoo: {odoo_url}\n')

    client = OdooClient(odoo_url, api_key, database)
    errors: list[dict] = []

    raw = collect(client, errors)
    analysis = analyze(raw)

    data: dict[str, Any] = {
        'meta': {
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'odoo_url': odoo_url,
            'script_version': '1.0.0',
            'errors': errors,
        },
        'raw_fields': raw['fields_meta'],
        'analysis': analysis,
    }

    with open(json_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False, default=str)
    with open(md_path, 'w', encoding='utf-8') as f:
        f.write(render_markdown(data))

    print('\n✓ Auditoría completada')
    print(f'  JSON : {json_path}')
    print(f'  MD   : {md_path}')
    print(f'  Tags: {analysis["totales"]["tags"]} | '
          f'Huérfanos: {analysis["totales"]["huerfanos"]} | '
          f'Colisiones familia: {len(analysis["colisiones_familia_color"])} | '
          f'Duplicados: {analysis["totales"]["duplicados_norm"]}')
    if errors:
        print(f'  ⚠ {len(errors)} advertencias — ver meta.errors')
    return 0


if __name__ == '__main__':
    sys.exit(main())
