#!/usr/bin/env python3
"""
Rollback de optimize_category_images.py: restaura `image_1920` de
product.public.category desde un directorio de respaldo.

El respaldo lo genera optimize_category_images.py en
backups/category_images_AAAAMMDD/, con un archivo por categoría nombrado
`<id>_<slug>.webp` (el id es la fuente de verdad; el slug es sólo legibilidad).

Restaurar deja el sitio EXACTAMENTE como estaba, incluidas las miniaturas rotas
que motivaron la optimización — o sea, /shop vuelve a pesar ~5 MB. Úsalo sólo si
la optimización rompió algo visualmente.

DRY-RUN por defecto: sin --apply no escribe nada en Odoo.

Uso:
    python rollback_category_images.py --from backups/category_images_20260807
    python rollback_category_images.py --from backups/category_images_20260807 --apply
    python rollback_category_images.py --from ... --ids 9,108 --apply

Variables de entorno necesarias:
    ODOO_URL, ODOO_API_KEY, ODOO_DATABASE (opcional)
"""

import argparse
import base64
import os
import re
import sys
from pathlib import Path

from dotenv import load_dotenv

from odoo_client import OdooClient

MODEL = 'product.public.category'
REPO = Path(__file__).resolve().parent.parent


def main() -> int:
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass

    load_dotenv()

    p = argparse.ArgumentParser(description='Restaura image_1920 desde un respaldo')
    p.add_argument('--from', dest='origen', required=True,
                   help='Directorio de respaldo (backups/category_images_AAAAMMDD)')
    p.add_argument('--ids', help='Restaurar sólo estos ids, separados por coma.')
    p.add_argument('--apply', action='store_true',
                   help='Ejecuta la restauración. Sin este flag es dry-run.')
    args = p.parse_args()

    odoo_url = os.environ.get('ODOO_URL')
    api_key = os.environ.get('ODOO_API_KEY')
    if not odoo_url or not api_key:
        print('x Falta ODOO_URL o ODOO_API_KEY en variables de entorno', file=sys.stderr)
        return 1

    origen = Path(args.origen)
    if not origen.is_absolute():
        origen = REPO / origen
    if not origen.is_dir():
        print(f'x No existe el directorio de respaldo: {origen}', file=sys.stderr)
        return 1

    solo = {int(x) for x in args.ids.split(',')} if args.ids else None

    archivos = []
    for f in sorted(origen.glob('*.webp')):
        m = re.match(r'^(\d+)_', f.name)
        if not m:
            print(f'  ? se ignora (nombre inesperado): {f.name}')
            continue
        cid = int(m.group(1))
        if solo is None or cid in solo:
            archivos.append((cid, f))

    if not archivos:
        print(f'x No hay archivos que restaurar en {origen}', file=sys.stderr)
        return 1

    print(f'Rollback de imágenes de categoría <- {origen.name}')
    print(f'Odoo: {odoo_url}')
    print(f'Modo: {"APPLY" if args.apply else "DRY-RUN"}\n')
    print(f'=== {len(archivos)} categorías a restaurar ===')

    client = OdooClient(odoo_url, api_key, os.environ.get('ODOO_DATABASE'))
    fallos = 0
    for cid, archivo in archivos:
        raw = archivo.read_bytes()
        etiqueta = f'id={cid:<4} {archivo.name}  ({len(raw)/1024:.1f} KB)'
        if not args.apply:
            print(f'  ~ {etiqueta}')
            continue
        try:
            client.write(MODEL, [cid], {'image_1920': base64.b64encode(raw).decode()})
            print(f'  v {etiqueta}')
        except Exception as exc:
            print(f'  x {etiqueta} — falló: {exc}')
            fallos += 1

    if not args.apply:
        print('\nDry-run: NO se escribió nada en Odoo. Re-corre con --apply para ejecutar.')
    return 1 if fallos else 0


if __name__ == '__main__':
    sys.exit(main())
