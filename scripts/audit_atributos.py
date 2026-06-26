#!/usr/bin/env python3
"""
Auditoría de SOLO LECTURA de los atributos de producto en Odoo.

Fotografía product.attribute, product.attribute.value y
product.template.attribute.line para decidir qué filtros de /shop quitar,
consolidar o limpiar. No escribe NADA en Odoo.

Uso:
    python audit_atributos.py
    python audit_atributos.py --output reports/mi_audit.json

Variables de entorno (cargadas desde .env en la raíz del proyecto):
    ODOO_URL       https://mozaprint.odoo.com
    ODOO_API_KEY   ...
    ODOO_DATABASE  mozaprint-prod  (opcional)
"""

import argparse
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

# ─── Constantes ──────────────────────────────────────────────────────────────

N_POCOS = 3                 # <= productos → "usado por pocos" (candidato a quitar)
UMBRAL_VALORES_GRANDE = 50  # atributos con más valores → revisar limpieza
TOP_N = 10                  # top valores por nº de productos

# Campos candidatos para "visible en website" (se usa el que exista en la instancia)
VISIBILITY_FIELD_CANDIDATES = ['visibility', 'is_published', 'website_published']

# Incluir archivados aunque el API ignore el context
DOMAIN_ALL_ACTIVE = [('active', 'in', [True, False])]


# ─── Utilidades ──────────────────────────────────────────────────────────────

def safe_call(fn, *args, fallback=None, label='', errors=None, **kwargs):
    """Ejecuta fn(*args, **kwargs); si falla registra el error y retorna fallback."""
    try:
        return fn(*args, **kwargs)
    except Exception as exc:
        msg = f'[{label}] {exc}' if label else str(exc)
        print(f'  ⚠ {msg}')
        if errors is not None:
            errors.append({'label': label, 'error': str(exc)})
        return fallback


def _norm(s: str) -> str:
    """Normaliza para comparar nombres: minúsculas, sin acentos, espacios colapsados."""
    s = unicodedata.normalize('NFKD', s or '')
    s = ''.join(c for c in s if not unicodedata.combining(c))
    return ' '.join(s.lower().split())


def _m2o_id(val: Any) -> int | None:
    """Extrae el id de un campo many2one [id, name] (o None)."""
    return val[0] if isinstance(val, (list, tuple)) and val else None


# ─── Recolección ──────────────────────────────────────────────────────────────

def detect_visibility_field(client: OdooClient, errors: list) -> str | None:
    """Descubre cuál campo de visibilidad existe en product.attribute (no asume)."""
    meta = safe_call(
        client.fields_get, 'product.attribute', ['string', 'type'],
        label='fields_get(product.attribute)', errors=errors,
    ) or {}
    for cand in VISIBILITY_FIELD_CANDIDATES:
        if cand in meta:
            return cand
    return None


def collect(client: OdooClient, errors: list) -> dict[str, Any]:
    """Lee attributes, values y attribute.line (ptal) en bloque."""
    print('→ product.attribute...')
    vis_field = detect_visibility_field(client, errors)
    attr_fields = ['id', 'name', 'display_name', 'display_type', 'create_variant', 'active']
    if vis_field:
        attr_fields.append(vis_field)

    attributes = safe_call(
        client.search_read_all, 'product.attribute',
        domain=DOMAIN_ALL_ACTIVE, fields=attr_fields, context={'active_test': False},
        label='product.attribute', errors=errors,
    ) or []

    print('→ product.attribute.value...')
    values = safe_call(
        client.search_read_all, 'product.attribute.value',
        domain=DOMAIN_ALL_ACTIVE,
        fields=['id', 'name', 'attribute_id', 'active'],
        context={'active_test': False},
        label='product.attribute.value', errors=errors,
    ) or []

    print('→ product.template.attribute.line...')
    ptal = safe_call(
        client.search_read_all, 'product.template.attribute.line',
        domain=DOMAIN_ALL_ACTIVE,
        fields=['id', 'attribute_id', 'product_tmpl_id', 'value_ids'],
        context={'active_test': False},
        label='product.template.attribute.line', errors=errors,
    ) or []

    return {
        'visibility_field': vis_field,
        'attributes': attributes,
        'values': values,
        'ptal': ptal,
    }


# ─── Análisis ─────────────────────────────────────────────────────────────────

def analyze(raw: dict[str, Any]) -> dict[str, Any]:
    """Cruza atributos/valores/líneas y produce métricas y candidatos."""
    print('→ Analizando...')
    attributes = raw['attributes']
    values = raw['values']
    ptal = raw['ptal']
    vis_field = raw['visibility_field']

    # Valores por atributo y lookup id→info
    values_by_attr: dict[int, list] = defaultdict(list)
    value_attr: dict[int, int] = {}
    value_name: dict[int, str] = {}
    for v in values:
        aid = _m2o_id(v.get('attribute_id'))
        if aid is None:
            continue
        values_by_attr[aid].append(v)
        value_attr[v['id']] = aid
        value_name[v['id']] = v.get('name', '')

    # Cruce con líneas: productos por atributo y productos por valor
    products_by_attr: dict[int, set] = defaultdict(set)
    tmpls_by_value: dict[int, set] = defaultdict(set)
    for line in ptal:
        aid = _m2o_id(line.get('attribute_id'))
        tid = _m2o_id(line.get('product_tmpl_id'))
        if aid is None or tid is None:
            continue
        products_by_attr[aid].add(tid)
        for vid in (line.get('value_ids') or []):
            tmpls_by_value[vid].add(tid)

    # Métricas por atributo
    attr_stats: list[dict] = []
    for a in attributes:
        aid = a['id']
        vlist = values_by_attr.get(aid, [])
        value_count = len(vlist)
        product_count = len(products_by_attr.get(aid, set()))

        # Uso de valores
        per_value = []
        used = orphan = used_by_1 = 0
        for v in vlist:
            n = len(tmpls_by_value.get(v['id'], set()))
            per_value.append({'value_id': v['id'], 'name': v.get('name', ''), 'products': n})
            if n == 0:
                orphan += 1
            else:
                used += 1
                if n == 1:
                    used_by_1 += 1
        per_value.sort(key=lambda x: x['products'], reverse=True)

        stats = {
            'id': aid,
            'name': a.get('name', ''),
            'display_name': a.get('display_name', a.get('name', '')),
            'display_type': a.get('display_type'),
            'create_variant': a.get('create_variant'),
            'visibility': a.get(vis_field) if vis_field else None,
            'active': a.get('active', True),
            'value_count': value_count,
            'product_count': product_count,
            'values_used': used,
            'values_orphan': orphan,
            'values_used_by_1_product': used_by_1,
            'usado_por_1_producto': product_count == 1,
            'usado_por_0_productos': product_count == 0,
            'usado_por_pocos': product_count <= N_POCOS,
            'es_grande': value_count > UMBRAL_VALORES_GRANDE,
            'top_values': per_value[:TOP_N],
            'all_values_usage': per_value,
        }
        attr_stats.append(stats)

    attr_stats.sort(key=lambda s: (s['product_count'], s['value_count']))

    # Duplicados / solapados por nombre
    similar = _find_similar(attributes)

    # Candidatos accionables
    cand_eliminar = [
        {k: s[k] for k in ('id', 'name', 'display_type', 'value_count', 'product_count')}
        for s in attr_stats if s['product_count'] <= 1
    ]
    cand_limpiar = [
        {
            'id': s['id'], 'name': s['name'], 'value_count': s['value_count'],
            'values_used': s['values_used'], 'values_orphan': s['values_orphan'],
            'values_used_by_1_product': s['values_used_by_1_product'],
        }
        for s in attr_stats
        if s['value_count'] > UMBRAL_VALORES_GRANDE or s['values_orphan'] >= 10
    ]
    cand_limpiar.sort(key=lambda x: x['values_orphan'], reverse=True)

    return {
        'visibility_field': vis_field,
        'totals': {
            'attributes': len(attributes),
            'attribute_values': len(values),
            'attribute_lines': len(ptal),
        },
        'attributes': attr_stats,
        'candidatos_eliminar': cand_eliminar,
        'candidatos_consolidar': similar,
        'candidatos_limpiar_valores': cand_limpiar,
    }


def _find_similar(attributes: list[dict]) -> list[dict]:
    """Señala pares de atributos con nombres parecidos (posible consolidación)."""
    norm = {a['id']: _norm(a['name']) for a in attributes}
    pairs: list[dict] = []
    items = list(attributes)
    for i in range(len(items)):
        for j in range(i + 1, len(items)):
            a, b = items[i], items[j]
            na, nb = norm[a['id']], norm[b['id']]
            if not na or not nb:
                continue
            reason = None
            if na == nb:
                reason = 'nombre idéntico (normalizado)'
            elif (na in nb or nb in na) and min(len(na), len(nb)) >= 3:
                reason = 'uno contiene al otro'
            else:
                ta, tb = na.split(), nb.split()
                if ta and tb and ta[0] == tb[0] and len(ta[0]) >= 4:
                    reason = f"comparten primera palabra '{ta[0]}'"
            if reason:
                pairs.append({
                    'a': a.get('name', ''), 'b': b.get('name', ''),
                    'a_id': a['id'], 'b_id': b['id'], 'reason': reason,
                })
    return pairs


# ─── Reporte Markdown ─────────────────────────────────────────────────────────

def render_markdown(data: dict[str, Any]) -> str:
    ts = data['meta']['timestamp'][:10]
    an = data['analysis']
    t = an['totals']
    errs = data['meta'].get('errors', [])
    vis = an['visibility_field'] or '(no detectado)'

    lines: list[str] = [
        f'# Auditoría de Atributos de Producto — {ts}',
        '',
        'Fotografía de `product.attribute` para limpiar los filtros de /shop. SOLO LECTURA.',
        '',
        '## Resumen',
        '',
        f'- Atributos: **{t["attributes"]}**',
        f'- Valores de atributo (total): **{t["attribute_values"]}**',
        f'- Líneas atributo↔producto (ptal): {t["attribute_lines"]}',
        f'- Campo de visibilidad detectado en product.attribute: `{vis}`',
        '',
        '## Todos los atributos',
        '',
        '| Atributo | Tipo | Variante | Visible | # valores | # productos | huérfanos | Bandera |',
        '|---|---|---|---|---|---|---|---|',
    ]
    for s in an['attributes']:
        if s['usado_por_0_productos']:
            flag = '🔴 0 productos'
        elif s['usado_por_1_producto']:
            flag = '🟠 1 producto'
        elif s['usado_por_pocos']:
            flag = f'🟡 ≤{N_POCOS}'
        else:
            flag = ''
        lines.append(
            f'| {s["name"]} | {s["display_type"]} | {s["create_variant"]} | '
            f'{s["visibility"]} | {s["value_count"]} | {s["product_count"]} | '
            f'{s["values_orphan"]} | {flag} |'
        )

    # ── Candidatos a ELIMINAR / OCULTAR ──
    lines += [
        '',
        '## ⛔ Candidatos a ELIMINAR / ocultar del filtro (≤1 producto)',
        '',
    ]
    if an['candidatos_eliminar']:
        lines += [
            '| Atributo | Tipo | # valores | # productos |',
            '|---|---|---|---|',
            *[
                f'| {c["name"]} | {c["display_type"]} | {c["value_count"]} | {c["product_count"]} |'
                for c in an['candidatos_eliminar']
            ],
        ]
    else:
        lines.append('_Ninguno._')

    # ── Candidatos a CONSOLIDAR ──
    lines += [
        '',
        '## 🔗 Candidatos a CONSOLIDAR (nombres similares — solo señalados)',
        '',
    ]
    if an['candidatos_consolidar']:
        lines += [
            '| Atributo A | Atributo B | Motivo |',
            '|---|---|---|',
            *[
                f'| {p["a"]} | {p["b"]} | {p["reason"]} |'
                for p in an['candidatos_consolidar']
            ],
        ]
    else:
        lines.append('_Ninguno._')

    # ── Candidatos a LIMPIAR VALORES ──
    lines += [
        '',
        f'## 🧹 Candidatos a LIMPIAR valores (>{UMBRAL_VALORES_GRANDE} valores o ≥10 huérfanos)',
        '',
    ]
    if an['candidatos_limpiar_valores']:
        lines += [
            '| Atributo | # valores | en uso | huérfanos | usados por 1 prod |',
            '|---|---|---|---|---|',
            *[
                f'| {c["name"]} | {c["value_count"]} | {c["values_used"]} | '
                f'{c["values_orphan"]} | {c["values_used_by_1_product"]} |'
                for c in an['candidatos_limpiar_valores']
            ],
        ]
    else:
        lines.append('_Ninguno._')

    # ── Top valores de atributos grandes ──
    grandes = [s for s in an['attributes'] if s['es_grande']]
    if grandes:
        lines += ['', f'## Top {TOP_N} valores de atributos grandes (>{UMBRAL_VALORES_GRANDE} valores)', '']
        for s in grandes:
            lines += [
                f'### {s["name"]} — {s["value_count"]} valores '
                f'({s["values_used"]} en uso, {s["values_orphan"]} huérfanos)',
                '',
                '| Valor | # productos |',
                '|---|---|',
                *[f'| {v["name"]} | {v["products"]} |' for v in s['top_values']],
                '',
            ]

    if errs:
        lines += ['', '## Errores/advertencias durante la auditoría', '']
        for e in errs:
            lines.append(f'- `{e.get("label")}`: {e.get("error")}')

    lines += ['', f'_Generado: {data["meta"]["timestamp"]}_', '']
    return '\n'.join(lines)


# ─── Main ─────────────────────────────────────────────────────────────────────

def main() -> int:
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass

    load_dotenv()

    parser = argparse.ArgumentParser(description='Auditoría de solo lectura de atributos de producto')
    parser.add_argument('--output', '-o', help='Ruta del JSON de salida')
    parser.add_argument('--no-pretty', action='store_true', help='JSON sin indentar')
    args = parser.parse_args()

    odoo_url = os.environ.get('ODOO_URL')
    api_key = os.environ.get('ODOO_API_KEY')
    database = os.environ.get('ODOO_DATABASE')

    if not odoo_url or not api_key:
        print('✗ Falta ODOO_URL o ODOO_API_KEY en variables de entorno', file=sys.stderr)
        return 1

    today = datetime.now().strftime('%Y%m%d')
    Path('reports').mkdir(exist_ok=True)
    json_path = Path(args.output) if args.output else Path(f'reports/audit_atributos_{today}.json')
    md_path = json_path.with_suffix('.md')

    print(f'Mozaprint — Auditoría de atributos → {json_path}')
    print(f'Odoo: {odoo_url}')
    print()

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
        'analysis': analysis,
    }

    indent = None if args.no_pretty else 2
    with open(json_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=indent, ensure_ascii=False, default=str)
    with open(md_path, 'w', encoding='utf-8') as f:
        f.write(render_markdown(data))

    size_kb = json_path.stat().st_size / 1024
    print('\n✓ Auditoría completada')
    print(f'  JSON : {json_path} ({size_kb:.1f} KB)')
    print(f'  MD   : {md_path}')
    print(f'  Atributos: {analysis["totals"]["attributes"]} | '
          f'Valores: {analysis["totals"]["attribute_values"]} | '
          f'Candidatos eliminar: {len(analysis["candidatos_eliminar"])}')
    if errors:
        print(f'  ⚠ {len(errors)} advertencias — ver meta.errors en el JSON')
    return 0


if __name__ == '__main__':
    sys.exit(main())
