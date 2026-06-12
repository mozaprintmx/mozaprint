#!/usr/bin/env python3
"""
Auditoría de SOLO LECTURA del catálogo Mozaprint en Odoo.

Fotografía el estado actual para preparar Fase 2. No escribe nada en Odoo.

Uso:
    python audit_catalog.py
    python audit_catalog.py --output reports/mi_audit.json

Variables de entorno (cargadas desde .env en la raíz del proyecto):
    ODOO_URL       https://mozaprint.odoo.com
    ODOO_API_KEY   ...
    ODOO_DATABASE  mozaprint-prod  (opcional)
"""

import argparse
import json
import os
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

from odoo_client import OdooClient

# ─── Constantes ──────────────────────────────────────────────────────────────

# Campos custom esperados según specs/data-model.md
SPEC_TEMPLATE_FIELDS: list[tuple[str, str]] = [
    ('x_tecnica_default_id', 'many2one'),
    ('x_tecnicas_compatibles_ids', 'many2many'),
    ('x_costo_personalizacion', 'many2one'),
    ('x_area_max_cm2', 'float'),
    ('x_area_dimensiones', 'char'),
    ('x_tiempo_produccion_dias', 'integer'),
    ('x_requiere_cotizacion', 'boolean'),
    ('x_proveedor_id', 'many2one'),
    ('x_proveedor_sku', 'char'),
    # Nombre alternativo que usa backup_catalog.py — puede existir con otro prefijo
    ('x_tecnica_default', 'char'),
]

TECNICA_KEYWORDS = frozenset({
    'técnica', 'tecnica', 'impresión', 'impresion',
    'personaliz', 'technique', 'print', 'marcado',
})

# Señal fuerte de "método de marcado" (no de área/dimensiones), para priorizar
# el campo correcto cuando hay varios candidatos (p.ej. x_area_impresion vs
# x_tecnica_impresion, donde ambos contienen "impresion").
TECNICA_STRONG = frozenset({
    'técnica', 'tecnica', 'personaliz', 'technique', 'marcado',
})

TOP_N = 10  # top valores distintos para el campo técnica

# Domain que fuerza incluir archivados aunque el API ignore el context
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


def _alias_map(partners: list[dict]) -> dict[int, str]:
    """Mapea id → 'Proveedor-N' para ofuscar nombres en el reporte."""
    return {p['id']: f'Proveedor-{i + 1}' for i, p in enumerate(partners)}


def _build_tree(records: list[dict]) -> list[dict]:
    """Convierte lista plana con parent_id en árbol anidado."""
    nodes = {r['id']: {**r, 'children': []} for r in records}
    roots: list[dict] = []
    for node in nodes.values():
        parent = node.get('parent_id')
        parent_id = parent[0] if isinstance(parent, (list, tuple)) else parent
        if parent_id and parent_id in nodes:
            nodes[parent_id]['children'].append(node)
        else:
            roots.append(node)
    return roots


# ─── Secciones de auditoría ───────────────────────────────────────────────────

def audit_field_introspection(client: OdooClient, errors: list) -> dict[str, Any]:
    """Descubre campos x_* reales y los cruza contra specs/data-model.md."""
    print('→ Introspección de campos custom...')
    attrs = ['string', 'type', 'selection', 'relation', 'required', 'readonly']

    def custom_fields(model: str) -> list[dict]:
        meta = safe_call(
            client.fields_get, model, attrs,
            label=f'fields_get({model})', errors=errors,
        ) or {}
        return [
            {
                'name': k,
                'string': v.get('string', ''),
                'type': v.get('type', ''),
                'relation': v.get('relation', ''),
                'selection': v.get('selection', []) if v.get('type') == 'selection' else [],
            }
            for k, v in meta.items()
            if k.startswith('x_')
        ]

    tmpl = custom_fields('product.template')
    prod = custom_fields('product.product')
    tmpl_names = {f['name'] for f in tmpl}

    divergences = []
    for spec_name, spec_type in SPEC_TEMPLATE_FIELDS:
        alt = spec_name.replace('x_', 'x_studio_', 1)
        if spec_name in tmpl_names:
            status, actual = 'ok', spec_name
        elif alt in tmpl_names:
            status, actual = 'found_as_x_studio', alt
        else:
            status, actual = 'missing', None
        divergences.append({
            'spec_name': spec_name,
            'expected_type': spec_type,
            'status': status,
            'actual_name': actual,
        })

    return {
        'product_template_custom_fields': tmpl,
        'product_product_custom_fields': prod,
        'spec_divergences': divergences,
    }


def audit_products(client: OdooClient, errors: list) -> dict[str, Any]:
    """
    Conteos de templates y variantes.
    total = incluye archivados (active_test=False + domain explícito como respaldo).
    active = solo activos.
    """
    print('→ Conteos de productos...')

    # Leer metadata del campo type para obtener selección real
    full_meta = safe_call(
        client.fields_get, 'product.template', ['string', 'type', 'selection'],
        label='fields_get(product.template) para type/is_storable', errors=errors,
    ) or {}
    type_meta = full_meta.get('type', {})
    type_selection = type_meta.get('selection') or []
    type_labels = {v: lbl for v, lbl in type_selection}
    has_is_storable = 'is_storable' in full_meta

    ctx_all = {'active_test': False}
    fields_tmpl = ['id', 'active', 'type', 'is_published']
    if has_is_storable:
        fields_tmpl.append('is_storable')

    # DOMAIN_ALL_ACTIVE como respaldo en caso de que el API ignore context
    all_templates = safe_call(
        client.search_read_all, 'product.template',
        domain=DOMAIN_ALL_ACTIVE,
        fields=fields_tmpl,
        context=ctx_all,
        label='product.template (all)', errors=errors,
    ) or []

    active = [t for t in all_templates if t.get('active', True)]
    by_type_raw: Counter = Counter(t.get('type') for t in active if t.get('type'))
    by_type = {type_labels.get(k, k): v for k, v in by_type_raw.items()}
    website_published = sum(1 for t in active if t.get('is_published'))

    all_variants = safe_call(
        client.search_read_all, 'product.product',
        domain=DOMAIN_ALL_ACTIVE,
        fields=['id', 'active'],
        context=ctx_all,
        label='product.product (all)', errors=errors,
    ) or []
    active_variants = [v for v in all_variants if v.get('active', True)]

    result: dict[str, Any] = {
        'note': 'total incluye archivados (active_test=False + domain explícito); active = solo activos',
        'total_templates': len(all_templates),
        'active_templates': len(active),
        'archived_templates': len(all_templates) - len(active),
        'by_type': by_type,
        'by_type_raw': dict(by_type_raw),
        'type_selection_from_odoo': type_selection,
        'website_published': website_published,
        'total_variants': len(all_variants),
        'active_variants': len(active_variants),
        'archived_variants': len(all_variants) - len(active_variants),
    }
    if has_is_storable:
        storable = sum(1 for t in active if t.get('is_storable'))
        result['storable_count'] = storable
        result['non_storable_count'] = len(active) - storable
    else:
        result['storable_note'] = 'Campo is_storable no encontrado en este modelo'
    return result


def audit_suppliers(
    client: OdooClient,
    tmpl_fields: list[dict],
    errors: list,
) -> dict[str, Any]:
    """Analiza vinculación de templates con proveedores (supplierinfo + campo custom)."""
    print('→ Proveedores...')

    suppliers = safe_call(
        client.search_read_all, 'res.partner',
        domain=[('supplier_rank', '>', 0)],
        fields=['id', 'supplier_rank'],
        label='res.partner suppliers', errors=errors,
    ) or []
    alias_map = _alias_map(suppliers)

    supplierinfo = safe_call(
        client.search_read_all, 'product.supplierinfo',
        fields=['id', 'partner_id', 'product_tmpl_id'],
        label='product.supplierinfo', errors=errors,
    ) or []
    tmpl_with_si = {
        r['product_tmpl_id'][0]
        for r in supplierinfo
        if isinstance(r.get('product_tmpl_id'), (list, tuple))
    }
    count_by_sup_si: Counter = Counter(
        r['partner_id'][0]
        for r in supplierinfo
        if isinstance(r.get('partner_id'), (list, tuple))
    )

    tmpl_field_names = {f['name'] for f in tmpl_fields}
    custom_field = next(
        (c for c in ('x_proveedor_id', 'x_studio_proveedor_id') if c in tmpl_field_names),
        None,
    )

    count_by_sup_custom: Counter = Counter()
    tmpl_with_custom: set[int] = set()
    if custom_field:
        rows = safe_call(
            client.search_read_all, 'product.template',
            domain=[(custom_field, '!=', False)],
            fields=['id', custom_field],
            label=f'templates con {custom_field}', errors=errors,
        ) or []
        for r in rows:
            val = r.get(custom_field)
            if isinstance(val, (list, tuple)):
                count_by_sup_custom[val[0]] += 1
                tmpl_with_custom.add(r['id'])

    # Universo = templates ACTIVOS (search sin active_test => solo activos).
    all_tmpl_ids = {
        r['id']
        for r in (
            safe_call(
                client.search_read_all, 'product.template',
                fields=['id'],
                label='tmpl ids activos (supplier gap)', errors=errors,
            ) or []
        )
    }

    # Restringir al universo activo: supplierinfo puede referir templates archivados.
    tmpl_with_si_active = tmpl_with_si & all_tmpl_ids
    tmpl_with_custom_active = tmpl_with_custom & all_tmpl_ids
    covered = tmpl_with_si_active | tmpl_with_custom_active

    # supplierinfo atribuido a partners SIN supplier_rank>0 (hallazgo de higiene).
    known_supplier_ids = {p['id'] for p in suppliers}
    si_to_known = sum(count_by_sup_si.get(i, 0) for i in known_supplier_ids)
    si_to_other = len(supplierinfo) - si_to_known

    return {
        'known_suppliers_count': len(suppliers),
        'known_suppliers': [
            {
                'alias': alias_map[p['id']],
                'supplier_rank': p['supplier_rank'],
                'product_count_supplierinfo': count_by_sup_si.get(p['id'], 0),
                'product_count_custom_field': count_by_sup_custom.get(p['id'], 0),
            }
            for p in suppliers
        ],
        'custom_proveedor_field': custom_field,
        'total_supplierinfo_records': len(supplierinfo),
        'supplierinfo_to_known_suppliers': si_to_known,
        'supplierinfo_to_other_partners': si_to_other,
        'templates_with_supplierinfo': len(tmpl_with_si_active),
        'templates_with_supplierinfo_incl_archived': len(tmpl_with_si),
        'templates_with_custom_field': len(tmpl_with_custom_active),
        'templates_without_any_supplier': len(all_tmpl_ids - covered),
        'total_active_templates_checked': len(all_tmpl_ids),
        'supplierinfo_coverage_pct': round(
            len(tmpl_with_si_active) / max(len(all_tmpl_ids), 1) * 100, 1
        ),
    }


def audit_tecnica_field(
    client: OdooClient,
    tmpl_fields: list[dict],
    errors: list,
) -> dict[str, Any]:
    """Busca cualquier campo en product.template relacionado con técnica/impresión."""
    print('→ Campo técnica de impresión...')

    candidates = [
        f for f in tmpl_fields
        if any(kw in (f['name'] + ' ' + f['string']).lower() for kw in TECNICA_KEYWORDS)
    ]

    # Priorizar el campo de "método" (técnica/personalización) sobre el de área.
    def _priority(f: dict) -> int:
        text = (f['name'] + ' ' + f['string']).lower()
        return 0 if any(k in text for k in TECNICA_STRONG) else 1

    candidates = sorted(candidates, key=_priority)

    # Verificar si el modelo custom x_tecnica_personalizacion ya existe
    tecnica_model_exists = False
    try:
        client.call('x_tecnica_personalizacion', 'search_read',
                    {'domain': [], 'fields': ['id'], 'limit': 1})
        tecnica_model_exists = True
    except Exception:
        pass

    if not candidates:
        return {
            'found': False,
            'candidates': [],
            'tecnica_model_exists': tecnica_model_exists,
            'top_values': [],
        }

    primary = candidates[0]['name']
    rows = safe_call(
        client.search_read_all, 'product.template',
        domain=[(primary, '!=', False)],
        fields=['id', primary],
        label=f'values de {primary}', errors=errors,
    ) or []

    counts: Counter = Counter()
    for r in rows:
        val = r.get(primary)
        if val:
            label = val[1] if (isinstance(val, (list, tuple)) and len(val) > 1) else str(val)
            counts[label] += 1

    return {
        'found': True,
        'candidates': candidates,
        'primary_field': primary,
        'tecnica_model_exists': tecnica_model_exists,
        'top_values': [{'value': v, 'count': c} for v, c in counts.most_common(TOP_N)],
        'distinct_values_total': len(counts),
        'products_with_value': len(rows),
    }


def audit_categories(client: OdooClient, errors: list) -> dict[str, Any]:
    """Árbol de categorías internas y eCommerce con conteo de productos."""
    print('→ Categorías...')

    internal = safe_call(
        client.search_read_all, 'product.category',
        fields=['id', 'name', 'parent_id', 'complete_name'],
        label='product.category', errors=errors,
    ) or []
    public = safe_call(
        client.search_read_all, 'product.public.category',
        fields=['id', 'name', 'parent_id', 'sequence'],
        label='product.public.category', errors=errors,
    ) or []

    templates = safe_call(
        client.search_read_all, 'product.template',
        fields=['id', 'categ_id', 'public_categ_ids'],
        label='product.template categ_ids', errors=errors,
    ) or []

    internal_count: Counter = Counter(
        t['categ_id'][0]
        for t in templates
        if isinstance(t.get('categ_id'), (list, tuple))
    )
    public_count: Counter = Counter(
        cid
        for t in templates
        for cid in (t.get('public_categ_ids') or [])
    )

    for cat in internal:
        cat['product_count'] = internal_count.get(cat['id'], 0)
    for cat in public:
        cat['product_count'] = public_count.get(cat['id'], 0)

    return {
        'internal_count': len(internal),
        'internal_tree': _build_tree(internal),
        'public_ecommerce_count': len(public),
        'public_ecommerce_tree': _build_tree(public),
    }


def audit_attributes(client: OdooClient, errors: list) -> dict[str, Any]:
    """
    Atributos y sus valores.
    Color: señal principal = display_type == 'color'; respaldo = html_color no vacío.
    """
    print('→ Atributos y variantes...')

    attrs = safe_call(
        client.search_read_all, 'product.attribute',
        fields=['id', 'name', 'display_type', 'create_variant'],
        label='product.attribute', errors=errors,
    ) or []
    values = safe_call(
        client.search_read_all, 'product.attribute.value',
        fields=['id', 'name', 'attribute_id', 'html_color', 'sequence'],
        label='product.attribute.value', errors=errors,
    ) or []

    color_by_type = {a['id'] for a in attrs if a.get('display_type') == 'color'}
    color_by_html = {
        v['attribute_id'][0]
        for v in values
        if v.get('html_color') and isinstance(v.get('attribute_id'), (list, tuple))
    }
    color_ids = color_by_type | color_by_html

    vals_by_attr: dict[int, list] = defaultdict(list)
    for v in values:
        if isinstance(v.get('attribute_id'), (list, tuple)):
            vals_by_attr[v['attribute_id'][0]].append(v)

    color_attrs = [
        {
            'id': a['id'],
            'name': a['name'],
            'display_type': a.get('display_type'),
            'color_detection': (
                'display_type=color' if a['id'] in color_by_type else 'html_color_fallback'
            ),
            'values': [
                {'name': v['name'], 'html_color': v.get('html_color')}
                for v in vals_by_attr.get(a['id'], [])
            ],
        }
        for a in attrs if a['id'] in color_ids
    ]
    non_color_attrs = [
        {
            'id': a['id'],
            'name': a['name'],
            'display_type': a.get('display_type'),
            'create_variant': a.get('create_variant'),
            'value_count': len(vals_by_attr.get(a['id'], [])),
        }
        for a in attrs if a['id'] not in color_ids
    ]

    return {
        'total_attributes': len(attrs),
        'color_attributes': color_attrs,
        'non_color_attributes': non_color_attrs,
    }


def audit_pricelists(client: OdooClient, errors: list) -> dict[str, Any]:
    """Pricelists con items completos (applied_on, vigencias, precios) y loyalty programs."""
    print('→ Pricelists y descuentos...')

    pricelists = safe_call(
        client.search_read_all, 'product.pricelist',
        fields=['id', 'name', 'currency_id', 'active'],
        label='product.pricelist', errors=errors,
    ) or []

    pl_ids = [p['id'] for p in pricelists]
    items: list[dict] = []
    if pl_ids:
        items = safe_call(
            client.search_read_all, 'product.pricelist.item',
            domain=[('pricelist_id', 'in', pl_ids)],
            fields=[
                'id', 'pricelist_id', 'applied_on', 'compute_price',
                'fixed_price', 'percent_price', 'min_quantity',
                'date_start', 'date_end',
                'categ_id', 'product_tmpl_id', 'product_id',
            ],
            label='product.pricelist.item', errors=errors,
        ) or []

    items_by_pl: dict[int, list] = defaultdict(list)
    for item in items:
        if isinstance(item.get('pricelist_id'), (list, tuple)):
            items_by_pl[item['pricelist_id'][0]].append(item)

    loyalty_model_exists = False
    loyalty_programs: list = []
    loyalty_rules: list = []
    loyalty_rewards: list = []
    try:
        loyalty_programs = client.search_read_all(
            'loyalty.program',
            fields=['id', 'name', 'program_type', 'active', 'rule_ids', 'reward_ids'],
        )
        loyalty_model_exists = True
        rule_ids = [r for p in loyalty_programs for r in p.get('rule_ids', [])]
        if rule_ids:
            loyalty_rules = client.search_read(
                'loyalty.rule',
                domain=[('id', 'in', rule_ids)],
                fields=['id', 'program_id', 'minimum_amount', 'minimum_amount_tax_mode'],
            )
        reward_ids = [r for p in loyalty_programs for r in p.get('reward_ids', [])]
        if reward_ids:
            loyalty_rewards = client.search_read(
                'loyalty.reward',
                domain=[('id', 'in', reward_ids)],
                fields=['id', 'program_id', 'reward_type', 'discount', 'discount_mode'],
            )
    except Exception as exc:
        errors.append({'label': 'loyalty.program', 'error': str(exc)})
        print(f'  ⚠ [loyalty.program] {exc}')

    return {
        'pricelists': [
            {
                'id': p['id'],
                'name': p['name'],
                'currency': (
                    p['currency_id'][1]
                    if isinstance(p.get('currency_id'), (list, tuple))
                    else p.get('currency_id')
                ),
                'active': p.get('active', True),
                'item_count': len(items_by_pl.get(p['id'], [])),
                'items': items_by_pl.get(p['id'], []),
            }
            for p in pricelists
        ],
        'loyalty_model_exists': loyalty_model_exists,
        'loyalty_programs_count': len(loyalty_programs),
        'loyalty_programs': loyalty_programs,
        'loyalty_rules': loyalty_rules,
        'loyalty_rewards': loyalty_rewards,
    }


def audit_shop(client: OdooClient, errors: list) -> dict[str, Any]:
    """Estado de /shop: productos publicados y categorías públicas con contenido."""
    print('→ Estado de /shop...')

    published = safe_call(
        client.search_read_all, 'product.template',
        domain=[('is_published', '=', True)],
        fields=['id', 'public_categ_ids'],
        label='templates publicados', errors=errors,
    ) or []
    unpublished = safe_call(
        client.search_read_all, 'product.template',
        domain=[('is_published', '=', False)],
        fields=['id'],
        label='templates no publicados', errors=errors,
    ) or []

    cat_ids_with_published = {
        cid for t in published for cid in (t.get('public_categ_ids') or [])
    }

    return {
        'published_products': len(published),
        'unpublished_products': len(unpublished),
        'public_categories_with_published_products': len(cat_ids_with_published),
    }


def build_quick_flags(
    products: dict,
    suppliers: dict,
    tecnica: dict,
    pricelists: dict,
) -> dict[str, Any]:
    return {
        'total_active_products': products.get('active_templates', 0),
        'total_active_variants': products.get('active_variants', 0),
        'any_product_published': products.get('website_published', 0) > 0,
        'x_proveedor_field_exists': suppliers.get('custom_proveedor_field') is not None,
        'tecnica_field_exists_on_template': tecnica.get('found', False),
        'tecnica_model_exists': tecnica.get('tecnica_model_exists', False),
        'has_loyalty_programs': pricelists.get('loyalty_programs_count', 0) > 0,
        'loyalty_model_exists': pricelists.get('loyalty_model_exists', False),
    }


# ─── Reporte Markdown ─────────────────────────────────────────────────────────

def render_markdown(data: dict[str, Any]) -> str:
    ts = data['meta']['timestamp'][:10]
    p = data['products']
    s = data['suppliers']
    t = data['tecnica_field']
    pl = data['pricelists']
    sh = data['shop_state']
    qf = data['quick_flags']
    fi = data['field_introspection']
    errs = data['meta'].get('errors', [])

    lines: list[str] = [
        f'# Auditoría de Catálogo Mozaprint — {ts}',
        '',
        '## Quick flags',
        '',
        '| Flag | Valor |',
        '|---|---|',
        *[f'| `{k}` | {v} |' for k, v in qf.items()],
        '',
        '## Productos',
        '',
        f'- Templates totales (incl. archivados): **{p.get("total_templates")}**',
        f'- Templates activos: **{p.get("active_templates")}**',
        f'- Templates archivados: {p.get("archived_templates")}',
        f'- Publicados en /shop: **{p.get("website_published")}**',
        f'- Variantes totales (incl. archivadas): {p.get("total_variants")}',
        f'- Variantes activas: {p.get("active_variants")}',
        '',
        '### Desglose por tipo (selección real de Odoo)',
        '',
    ]
    for lbl, cnt in (p.get('by_type') or {}).items():
        lines.append(f'- {lbl}: {cnt}')
    if 'storable_count' in p:
        lines += [
            f'- is_storable=True (almacenables): {p["storable_count"]}',
            f'- is_storable=False: {p.get("non_storable_count")}',
        ]
    elif 'storable_note' in p:
        lines.append(f'- _{p["storable_note"]}_')

    lines += [
        '',
        '## Proveedores',
        '',
        f'- Proveedores conocidos (supplier_rank>0): {s.get("known_suppliers_count")}',
        f'- Campo custom proveedor en product.template: '
        f'`{s.get("custom_proveedor_field") or "no encontrado"}`',
        f'- Templates activos con supplierinfo: {s.get("templates_with_supplierinfo")} / '
        f'{s.get("total_active_templates_checked")} ({s.get("supplierinfo_coverage_pct")}%)',
        f'- Registros supplierinfo totales: {s.get("total_supplierinfo_records")} '
        f'(a proveedores con rank>0: {s.get("supplierinfo_to_known_suppliers")}; '
        f'**a partners SIN rank de proveedor: {s.get("supplierinfo_to_other_partners")}**)',
        f'- Templates con campo custom proveedor: {s.get("templates_with_custom_field")}',
        f'- **Templates activos sin proveedor (ninguna vinculación): '
        f'{s.get("templates_without_any_supplier")}**',
        '',
    ]
    if s.get('known_suppliers'):
        lines += [
            '| Alias | supplier_rank | Via supplierinfo | Via campo custom |',
            '|---|---|---|---|',
            *[
                f'| {sup["alias"]} | {sup["supplier_rank"]} | '
                f'{sup["product_count_supplierinfo"]} | {sup["product_count_custom_field"]} |'
                for sup in s['known_suppliers']
            ],
        ]

    lines += ['', '## Campo técnica de impresión', '']
    if t.get('found'):
        lines += [
            f'- Campo encontrado: `{t.get("primary_field")}`',
            f'- Productos con valor: {t.get("products_with_value")} '
            f'({t.get("distinct_values_total")} valores distintos)',
            '',
            '### Top valores',
            '',
            *[f'- `{item["value"]}`: {item["count"]}' for item in t.get('top_values', [])],
        ]
    else:
        lines += [
            '- **No se encontró ningún campo** con términos de técnica/impresión/personalización.',
            f'- Modelo `x_tecnica_personalizacion` existe: {t.get("tecnica_model_exists", False)}',
        ]

    active_pl = sum(1 for pl_ in pl.get('pricelists', []) if pl_.get('active'))
    total_items = sum(pl_.get('item_count', 0) for pl_ in pl.get('pricelists', []))
    lines += [
        '',
        '## Pricelists',
        '',
        f'- Pricelists activas: {active_pl}',
        f'- Total items de precio: {total_items}',
        f'- Modelo loyalty.program disponible: {pl.get("loyalty_model_exists")}',
        f'- Loyalty programs: {pl.get("loyalty_programs_count", 0)}',
        '',
    ]
    for pl_ in pl.get('pricelists', []):
        lines.append(
            f'  - **{pl_["name"]}** ({pl_.get("currency")}) — '
            f'{pl_["item_count"]} items — activa: {pl_.get("active")}'
        )

    lines += [
        '',
        '## /shop',
        '',
        f'- Productos publicados: **{sh.get("published_products")}**',
        f'- Productos no publicados: {sh.get("unpublished_products")}',
        f'- Categorías públicas con productos publicados: '
        f'{sh.get("public_categories_with_published_products")}',
        '',
        '## Divergencias del spec (specs/data-model.md vs Odoo real)',
        '',
        '| Campo spec | Tipo esperado | Estado | Nombre real en Odoo |',
        '|---|---|---|---|',
    ]
    status_icons = {
        'ok': '✓ existe',
        'found_as_x_studio': '⚠ prefijo x_studio_',
        'missing': '✗ no existe',
    }
    for d in fi.get('spec_divergences', []):
        icon = status_icons.get(d['status'], d['status'])
        lines.append(
            f'| `{d["spec_name"]}` | {d["expected_type"]} | {icon} | '
            f'`{d.get("actual_name") or "—"}` |'
        )

    lines += ['', '## Hallazgos para Fase 2', '']
    missing = [d for d in fi.get('spec_divergences', []) if d['status'] == 'missing']
    found_as_studio = [d for d in fi.get('spec_divergences', []) if d['status'] == 'found_as_x_studio']
    if missing:
        lines.append(f'- **{len(missing)} campos del spec aún no existen** — crear vía Studio:')
        for d in missing:
            lines.append(f'  - `{d["spec_name"]}` ({d["expected_type"]})')
    else:
        lines.append('- Todos los campos del spec existen en Odoo.')
    if found_as_studio:
        lines.append(f'- {len(found_as_studio)} campo(s) encontrado(s) con prefijo `x_studio_` en lugar de `x_`:')
        for d in found_as_studio:
            lines.append(f'  - spec: `{d["spec_name"]}` → real: `{d["actual_name"]}`')
    if not t.get('found') and not t.get('tecnica_model_exists'):
        lines.append('- El modelo `x_tecnica_personalizacion` **no existe** — crear en Fase 2.')

    if errs:
        lines += ['', '## Errores/advertencias durante la auditoría', '']
        for e in errs:
            lines.append(f'- `{e.get("label")}`: {e.get("error")}')

    lines += ['', f'_Generado: {data["meta"]["timestamp"]}_', '']
    return '\n'.join(lines)


# ─── Main ─────────────────────────────────────────────────────────────────────

def main() -> int:
    # La consola de Windows (cp1252) no puede imprimir →/✓/⚠; forzar UTF-8.
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass

    load_dotenv()

    parser = argparse.ArgumentParser(description='Auditoría de solo lectura del catálogo Odoo')
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
    json_path = Path(args.output) if args.output else Path(f'reports/catalog_audit_{today}.json')
    md_path = json_path.with_suffix('.md')

    print(f'Mozaprint — Auditoría de catálogo → {json_path}')
    print(f'Odoo: {odoo_url}')
    print()

    client = OdooClient(odoo_url, api_key, database)
    errors: list[dict] = []

    fi = audit_field_introspection(client, errors)
    tmpl_fields = fi['product_template_custom_fields']

    products = audit_products(client, errors)
    suppliers = audit_suppliers(client, tmpl_fields, errors)
    tecnica = audit_tecnica_field(client, tmpl_fields, errors)
    categories = audit_categories(client, errors)
    attributes = audit_attributes(client, errors)
    pricelists_data = audit_pricelists(client, errors)
    shop = audit_shop(client, errors)
    quick_flags = build_quick_flags(products, suppliers, tecnica, pricelists_data)

    data: dict[str, Any] = {
        'meta': {
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'odoo_url': odoo_url,
            'script_version': '1.0.0',
            'errors': errors,
        },
        'field_introspection': fi,
        'products': products,
        'suppliers': suppliers,
        'tecnica_field': tecnica,
        'categories': categories,
        'attributes': attributes,
        'pricelists': pricelists_data,
        'shop_state': shop,
        'quick_flags': quick_flags,
    }

    indent = None if args.no_pretty else 2
    with open(json_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=indent, ensure_ascii=False, default=str)

    with open(md_path, 'w', encoding='utf-8') as f:
        f.write(render_markdown(data))

    size_kb = json_path.stat().st_size / 1024
    print(f'\n✓ Auditoría completada')
    print(f'  JSON : {json_path} ({size_kb:.1f} KB)')
    print(f'  MD   : {md_path}')
    print(f'  Productos activos  : {quick_flags["total_active_products"]}')
    print(f'  Variantes activas  : {quick_flags["total_active_variants"]}')
    if errors:
        print(f'  ⚠ {len(errors)} advertencias — ver meta.errors en el JSON')
    return 0


if __name__ == '__main__':
    sys.exit(main())
