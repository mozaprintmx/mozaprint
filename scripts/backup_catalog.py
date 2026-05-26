#!/usr/bin/env python3
"""
Backup del catálogo de productos desde Odoo via JSON-2 API.

Genera un snapshot JSON del estado actual de:
- product.template
- product.product (variants)
- product.attribute + product.attribute.value
- product.public.category
- product.pricelist + reglas

Útil antes de sync masivo o como respaldo periódico.

Uso:
    python backup_catalog.py
    python backup_catalog.py --output backups/2026-05-23.json
    python backup_catalog.py --supplier "Innovation Line"  # solo de un proveedor

Variables de entorno necesarias:
    ODOO_URL=https://mozaprint.odoo.com
    ODOO_API_KEY=...
    ODOO_DATABASE=mozaprint-prod  (opcional)
"""

import argparse
import json
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

import requests


class OdooClient:
    """Cliente mínimo para JSON-2 API de Odoo."""

    def __init__(self, url: str, api_key: str, database: str | None = None):
        self.url = url.rstrip('/')
        self.headers = {
            'Authorization': f'Bearer {api_key}',
            'Content-Type': 'application/json',
        }
        if database:
            self.headers['DATABASE'] = database

    def search_read(
        self,
        model: str,
        domain: list | None = None,
        fields: list | None = None,
        limit: int | None = None,
        offset: int = 0,
    ) -> list[dict[str, Any]]:
        """Llama a search_read y devuelve la lista de resultados."""
        payload = {
            'domain': domain or [],
            'fields': fields or [],
            'offset': offset,
        }
        if limit:
            payload['limit'] = limit

        response = requests.post(
            f'{self.url}/json2/{model}/search_read',
            headers=self.headers,
            json=payload,
            timeout=60,
        )
        response.raise_for_status()
        return response.json().get('result', [])

    def search_read_all(
        self,
        model: str,
        domain: list | None = None,
        fields: list | None = None,
        batch_size: int = 500,
    ) -> list[dict[str, Any]]:
        """Paginación automática hasta traer todo."""
        results = []
        offset = 0
        while True:
            batch = self.search_read(model, domain, fields, batch_size, offset)
            results.extend(batch)
            if len(batch) < batch_size:
                break
            offset += batch_size
        return results


def backup_catalog(
    client: OdooClient,
    supplier_name: str | None = None,
) -> dict[str, Any]:
    """Construye snapshot completo del catálogo."""
    snapshot = {
        'metadata': {
            'timestamp': datetime.utcnow().isoformat() + 'Z',
            'odoo_url': client.url,
            'supplier_filter': supplier_name,
        },
    }

    # Filtro por proveedor si aplica
    template_domain = []
    if supplier_name:
        suppliers = client.search_read(
            'res.partner',
            domain=[('name', '=', supplier_name), ('supplier_rank', '>', 0)],
            fields=['id'],
        )
        if not suppliers:
            raise ValueError(f"Proveedor '{supplier_name}' no encontrado")
        template_domain = [('x_proveedor_id', '=', suppliers[0]['id'])]

    print(f"→ Descargando product.template...")
    snapshot['product_templates'] = client.search_read_all(
        'product.template',
        domain=template_domain,
        fields=[
            'id', 'name', 'default_code', 'list_price', 'standard_price',
            'type', 'categ_id', 'public_categ_ids',
            'attribute_line_ids', 'optional_product_ids', 'accessory_product_ids',
            'x_proveedor_id', 'x_proveedor_sku',
            'x_tecnica_default', 'x_area_max_cm2', 'x_area_dimensiones',
            'x_tiempo_produccion_dias', 'x_requiere_cotizacion',
            'active', 'write_date',
        ],
    )
    print(f"  {len(snapshot['product_templates'])} templates")

    print(f"→ Descargando product.product (variants)...")
    if template_domain:
        # Filtrar variants por templates
        template_ids = [t['id'] for t in snapshot['product_templates']]
        variant_domain = [('product_tmpl_id', 'in', template_ids)]
    else:
        variant_domain = []

    snapshot['product_variants'] = client.search_read_all(
        'product.product',
        domain=variant_domain,
        fields=[
            'id', 'product_tmpl_id', 'default_code', 'name',
            'lst_price', 'standard_price', 'qty_available',
            'product_template_variant_value_ids',
            'active',
        ],
    )
    print(f"  {len(snapshot['product_variants'])} variants")

    print(f"→ Descargando product.attribute...")
    snapshot['attributes'] = client.search_read_all(
        'product.attribute',
        fields=['id', 'name', 'display_type', 'create_variant'],
    )

    print(f"→ Descargando product.attribute.value...")
    snapshot['attribute_values'] = client.search_read_all(
        'product.attribute.value',
        fields=['id', 'name', 'attribute_id', 'html_color', 'sequence'],
    )

    print(f"→ Descargando categorías eCommerce...")
    snapshot['public_categories'] = client.search_read_all(
        'product.public.category',
        fields=['id', 'name', 'parent_id', 'sequence'],
    )

    print(f"→ Descargando pricelists...")
    snapshot['pricelists'] = client.search_read_all(
        'product.pricelist',
        fields=['id', 'name', 'currency_id', 'active'],
    )

    print(f"→ Descargando programas de loyalty (descuentos)...")
    try:
        snapshot['loyalty_programs'] = client.search_read_all(
            'loyalty.program',
            fields=['id', 'name', 'program_type', 'active', 'rule_ids', 'reward_ids'],
        )
        # Rules
        rule_ids = [r for p in snapshot['loyalty_programs'] for r in p.get('rule_ids', [])]
        if rule_ids:
            snapshot['loyalty_rules'] = client.search_read(
                'loyalty.rule',
                domain=[('id', 'in', rule_ids)],
                fields=['id', 'program_id', 'minimum_amount', 'minimum_amount_tax_mode'],
            )
        # Rewards
        reward_ids = [r for p in snapshot['loyalty_programs'] for r in p.get('reward_ids', [])]
        if reward_ids:
            snapshot['loyalty_rewards'] = client.search_read(
                'loyalty.reward',
                domain=[('id', 'in', reward_ids)],
                fields=['id', 'program_id', 'reward_type', 'discount', 'discount_mode'],
            )
    except Exception as e:
        print(f"  ⚠ No se pudo obtener loyalty: {e}")
        snapshot['loyalty_programs'] = []

    return snapshot


def main():
    parser = argparse.ArgumentParser(description='Backup catálogo Odoo')
    parser.add_argument('--output', '-o', help='Ruta del archivo de salida')
    parser.add_argument('--supplier', help='Filtrar por nombre de proveedor')
    parser.add_argument('--pretty', action='store_true', default=True,
                        help='Indentar el JSON (default: true)')
    args = parser.parse_args()

    # Config desde env
    odoo_url = os.environ.get('ODOO_URL')
    api_key = os.environ.get('ODOO_API_KEY')
    database = os.environ.get('ODOO_DATABASE')

    if not odoo_url or not api_key:
        print('✗ Falta ODOO_URL o ODOO_API_KEY en variables de entorno', file=sys.stderr)
        return 1

    # Output path
    if args.output:
        out_path = Path(args.output)
    else:
        backup_dir = Path('backups')
        backup_dir.mkdir(exist_ok=True)
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        suffix = f"_{args.supplier.lower().replace(' ', '_')}" if args.supplier else ''
        out_path = backup_dir / f'catalog{suffix}_{timestamp}.json'

    print(f"Backup → {out_path}")
    if args.supplier:
        print(f"Filtro: proveedor = {args.supplier}")

    client = OdooClient(odoo_url, api_key, database)

    try:
        snapshot = backup_catalog(client, supplier_name=args.supplier)
    except Exception as e:
        print(f"✗ Error: {e}", file=sys.stderr)
        return 1

    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, 'w', encoding='utf-8') as f:
        if args.pretty:
            json.dump(snapshot, f, indent=2, ensure_ascii=False, default=str)
        else:
            json.dump(snapshot, f, ensure_ascii=False, default=str)

    size_mb = out_path.stat().st_size / 1024 / 1024
    print(f"\n✓ Backup completado")
    print(f"  Tamaño: {size_mb:.2f} MB")
    print(f"  Templates: {len(snapshot.get('product_templates', []))}")
    print(f"  Variants: {len(snapshot.get('product_variants', []))}")
    print(f"  Categorías: {len(snapshot.get('public_categories', []))}")
    print(f"  Programas descuento: {len(snapshot.get('loyalty_programs', []))}")

    return 0


if __name__ == '__main__':
    sys.exit(main())
