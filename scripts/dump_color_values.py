#!/usr/bin/env python3
"""
Dump de SOLO LECTURA de los valores del atributo "Color" en Odoo.

Lista todos los product.attribute.value del atributo Color con su html_color,
conteo de productos (templates) que los usan, y una columna name_normalizado que
aplica la MISMA normalización que usará derive_colores (minúsculas + sin acentos +
trim + colapsa espacios), para ver de inmediato qué valores colapsan al mismo
canónico (evidencia de fragmentación). Insumo para reconciliar el seed de swatches.

SOLO LECTURA: no escribe nada en Odoo.

Uso:
    python dump_color_values.py
    python dump_color_values.py --output reports/mi_dump.csv

Variables de entorno (cargadas desde .env en la raíz del proyecto):
    ODOO_URL       https://mozaprintmx.odoo.com
    ODOO_API_KEY   ...
    ODOO_DATABASE  mozaprintmx  (opcional)
"""

import argparse
import csv
import os
import sys
import unicodedata
from collections import defaultdict
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv

from odoo_client import OdooClient

ATTR_MODEL = 'product.attribute'
VALUE_MODEL = 'product.attribute.value'
LINE_MODEL = 'product.template.attribute.line'


def normalize(s: str) -> str:
    """
    Normalización canónica (idéntica a la que usará derive_colores):
    minúsculas + sin acentos + trim + colapsa espacios internos.
    """
    s = unicodedata.normalize('NFKD', s or '')
    s = ''.join(c for c in s if not unicodedata.combining(c))
    return ' '.join(s.lower().split())


def resolve_color_attribute(client: OdooClient) -> dict:
    """
    Resuelve el atributo Color. Si hay varios (duplicados históricos), prioriza
    create_variant='always' y el de más valores; reporta la ambigüedad.
    """
    cands = client.search_read(
        ATTR_MODEL, [('name', '=', 'Color')],
        fields=['id', 'name', 'create_variant'],
        context={'active_test': False},
    )
    if not cands:
        raise SystemExit("✗ No existe ningún product.attribute con name='Color'")

    # nº de valores por candidato (incluye archivados)
    for c in cands:
        vals = client.search_read(
            VALUE_MODEL, [('attribute_id', '=', c['id'])], fields=['id'],
            context={'active_test': False},
        )
        c['value_count'] = len(vals)

    if len(cands) > 1:
        print(f"⚠ AMBIGÜEDAD: {len(cands)} atributos llamados 'Color':")
        for c in cands:
            print(f"    id={c['id']} create_variant={c.get('create_variant')!r} "
                  f"valores={c['value_count']}")

    # Preferir create_variant='always', luego más valores
    chosen = sorted(
        cands,
        key=lambda c: (c.get('create_variant') == 'always', c['value_count']),
        reverse=True,
    )[0]
    print(f"→ Atributo Color elegido: id={chosen['id']} "
          f"create_variant={chosen.get('create_variant')!r} valores={chosen['value_count']}")
    return chosen


def main() -> int:
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass

    load_dotenv()

    parser = argparse.ArgumentParser(
        description='Dump de solo lectura de los valores del atributo Color'
    )
    parser.add_argument('--output', '-o', help='Ruta del CSV de salida')
    args = parser.parse_args()

    odoo_url = os.environ.get('ODOO_URL')
    api_key = os.environ.get('ODOO_API_KEY')
    database = os.environ.get('ODOO_DATABASE')
    if not odoo_url or not api_key:
        print('✗ Falta ODOO_URL o ODOO_API_KEY en variables de entorno', file=sys.stderr)
        return 1

    today = datetime.now().strftime('%Y%m%d')
    Path('reports').mkdir(exist_ok=True)
    out_path = Path(args.output) if args.output else Path(f'reports/color_values_{today}.csv')

    print('Mozaprint — Dump de valores del atributo Color')
    print(f'Odoo: {odoo_url}')
    print()

    client = OdooClient(odoo_url, api_key, database)

    # 1. Resolver atributo Color
    attr = resolve_color_attribute(client)
    attr_id = attr['id']

    # 2. Todos los valores del atributo (incluye archivados)
    print('→ Leyendo product.attribute.value...')
    values = client.search_read_all(
        VALUE_MODEL,
        domain=[('attribute_id', '=', attr_id)],
        fields=['id', 'name', 'html_color', 'sequence', 'active'],
        context={'active_test': False},
    )

    # 3. Conteo de templates por valor vía product.template.attribute.line
    print('→ Leyendo product.template.attribute.line (conteo de productos)...')
    ptal = client.search_read_all(
        LINE_MODEL,
        domain=[('attribute_id', '=', attr_id)],
        fields=['product_tmpl_id', 'value_ids'],
    )
    tmpls_by_value: dict[int, set] = defaultdict(set)
    for line in ptal:
        tmo = line.get('product_tmpl_id')
        tid = tmo[0] if isinstance(tmo, (list, tuple)) else tmo
        if tid is None:
            continue
        for vid in (line.get('value_ids') or []):
            tmpls_by_value[vid].add(tid)

    # 4/5. Armar filas con name_normalizado y ordenar por conteo desc
    filas = []
    for v in values:
        products = len(tmpls_by_value.get(v['id'], set()))
        filas.append({
            'name': v.get('name', ''),
            'name_normalizado': normalize(v.get('name', '')),
            'html_color': v.get('html_color') or '',
            'products': products,
            'active': v.get('active', True),
            'id': v['id'],
        })
    filas.sort(key=lambda r: (r['products'], r['name'].lower()), reverse=True)

    with open(out_path, 'w', encoding='utf-8', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(['name', 'name_normalizado', 'html_color', 'products', 'active', 'id'])
        for r in filas:
            writer.writerow([
                r['name'], r['name_normalizado'], r['html_color'],
                r['products'], r['active'], r['id'],
            ])

    # 6. Resumen en consola
    total = len(filas)
    con_hex = sum(1 for r in filas if r['html_color'])

    # Agrupar por name_normalizado; nombres crudos DISTINTOS por grupo
    grupos: dict[str, set] = defaultdict(set)
    grupo_products: dict[str, int] = defaultdict(int)
    for r in filas:
        grupos[r['name_normalizado']].add(r['name'])
        grupo_products[r['name_normalizado']] += r['products']
    canonicos = len(grupos)
    fragmentados = {k: v for k, v in grupos.items() if len(v) >= 2}

    print(f'\n✓ Dump completado')
    print(f'  CSV: {out_path}')
    print(f'  Valores crudos (raw)            : {total}')
    print(f'  Con html_color (swatch)         : {con_hex}  '
          f'({total - con_hex} sin swatch)')
    print(f'  Canónicos por name_normalizado  : {canonicos}  '
          f'(colapso: {total} → {canonicos})')
    print(f'  Grupos fragmentados (≥2 crudos) : {len(fragmentados)}')

    if fragmentados:
        print('\n  Fragmentación exacta (canónico → variantes crudas [prods]):')
        # ordenar por nº de variantes crudas desc, luego por productos del grupo
        for canon in sorted(
            fragmentados,
            key=lambda k: (len(grupos[k]), grupo_products[k]),
            reverse=True,
        ):
            crudas = sorted(grupos[canon])
            # productos por nombre crudo (para ver a cuál conviene canonizar)
            prods_por_nombre = {
                nm: next((r['products'] for r in filas if r['name'] == nm), 0)
                for nm in crudas
            }
            detalle = ', '.join(f'{nm!r}[{prods_por_nombre[nm]}p]' for nm in crudas)
            print(f'    {canon!r}: {detalle}')

    return 0


if __name__ == '__main__':
    sys.exit(main())
