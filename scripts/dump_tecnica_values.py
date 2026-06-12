#!/usr/bin/env python3
"""
Dump de SOLO LECTURA de los valores distintos de x_tecnica_impresion.

Lista completa (no solo el top-N del audit) de los valores de texto libre del
campo `x_tecnica_impresion` en product.template, con conteo de productos por
valor. Insumo para diseñar la normalización de Fase 2 (mapear texto libre →
modelo x_tecnica_personalizacion).

SOLO LECTURA: no escribe nada en Odoo.

Uso:
    python dump_tecnica_values.py
    python dump_tecnica_values.py --output reports/mi_dump.csv

Variables de entorno (cargadas desde .env en la raíz del proyecto):
    ODOO_URL       https://mozaprintmx.odoo.com
    ODOO_API_KEY   ...
    ODOO_DATABASE  mozaprintmx  (opcional)
"""

import argparse
import csv
import os
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv

from odoo_client import OdooClient

TECNICA_FIELD = 'x_tecnica_impresion'
COMBO_SEPARATORS = ('-', '/', ',')


def main() -> int:
    # La consola de Windows (cp1252) no puede imprimir →/✓; forzar UTF-8.
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass

    load_dotenv()

    parser = argparse.ArgumentParser(
        description='Dump de solo lectura de valores de x_tecnica_impresion'
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
    out_path = Path(args.output) if args.output else Path(f'reports/tecnica_values_{today}.csv')

    print(f'Mozaprint — Dump de {TECNICA_FIELD} → {out_path}')
    print(f'Odoo: {odoo_url}')
    print()

    client = OdooClient(odoo_url, api_key, database)

    # product.template activos con valor en el campo (mismo universo que el audit).
    print(f'→ Leyendo product.template con {TECNICA_FIELD} != False...')
    rows = client.search_read_all(
        'product.template',
        domain=[(TECNICA_FIELD, '!=', False)],
        fields=['id', TECNICA_FIELD],
    )

    counts: Counter = Counter()
    for r in rows:
        val = r.get(TECNICA_FIELD)
        if val:
            # Char libre: viene como string. Normalizar a str por robustez.
            counts[str(val)] += 1

    ordered = counts.most_common()  # orden desc por conteo

    with open(out_path, 'w', encoding='utf-8', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(['valor_raw', 'conteo'])
        for valor, conteo in ordered:
            writer.writerow([valor, conteo])

    combo_values = sum(
        1 for valor in counts if any(sep in valor for sep in COMBO_SEPARATORS)
    )
    combo_products = sum(
        c for valor, c in counts.items() if any(sep in valor for sep in COMBO_SEPARATORS)
    )

    print(f'\n✓ Dump completado')
    print(f'  CSV: {out_path}')
    print(f'  Valores distintos          : {len(counts)}')
    print(f'  Productos con valor         : {sum(counts.values())}')
    print(f'  Valores con separador combo : {combo_values} '
          f'(separadores: {", ".join(COMBO_SEPARATORS)})')
    print(f'  Productos en valores combo  : {combo_products}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
