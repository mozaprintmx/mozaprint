#!/usr/bin/env python3
"""
Crea/actualiza los product.template de servicio de personalización, uno por
cada técnica ACTIVA en x_tecnica_personalizacion (lee el catálogo en vivo de
Odoo, no un CSV — si se agregan técnicas después, re-correr solo crea las
nuevas).

IDEMPOTENTE: busca por x_tecnica_servicio_id (la técnica que representa
el servicio) — si existe, actualiza (write); si no, crea (create). Re-correr
NO duplica.

DRY-RUN por defecto: sin --apply solo imprime qué haría, sin escribir en Odoo.

Prerequisitos en Odoo (ver docs/guia-creacion-servicios-personalizacion.md):
    1. Categoría de producto "Servicios de Personalización" ya creada.
    2. Campos x_es_servicio_personalizacion (boolean) y
       x_tecnica_servicio_id (many2one -> x_tecnica_personalizacion)
       ya creados en product.template.

Uso:
    python seed_servicios_personalizacion.py            # dry-run
    python seed_servicios_personalizacion.py --apply    # ejecuta
    python seed_servicios_personalizacion.py --categoria "Otra Categoría" --apply

Variables de entorno (desde .env):
    ODOO_URL, ODOO_API_KEY, ODOO_DATABASE (opcional)
"""

import argparse
import os
import sys
from typing import Any

from dotenv import load_dotenv

from odoo_client import OdooClient

MODEL = 'product.template'
TECNICA_MODEL = 'x_tecnica_personalizacion'
CATEGORY_MODEL = 'product.category'
DEFAULT_CATEGORIA = 'Servicios de Personalización'


def resolve_categoria(client: OdooClient, nombre: str) -> int:
    """Busca la categoría de producto por nombre EXACTO. Aborta si no existe
    o si hay más de una (no la crea — es una decisión contable, no del script)."""
    found = client.search_read(
        CATEGORY_MODEL, domain=[('name', '=', nombre)], fields=['id', 'name'],
    )
    if len(found) == 1:
        return found[0]['id']
    plural = 'ninguna' if not found else f"{len(found)}"
    raise RuntimeError(
        f"Categoría de producto '{nombre}': se esperaba 1, se encontraron {plural}. "
        f"Créala primero en Ventas → Configuración → Categorías de producto "
        f"(ver docs/guia-creacion-servicios-personalizacion.md paso 1)."
    )


def load_tecnicas(client: OdooClient) -> list[dict[str, Any]]:
    """Trae todas las técnicas activas del catálogo en vivo."""
    return client.search_read(
        TECNICA_MODEL,
        domain=[('x_activa', '=', True)],
        fields=['id', 'x_code', 'x_name'],
    )


def build_records(tecnicas: list[dict[str, Any]], categoria_id: int) -> list[dict[str, Any]]:
    records = []
    for t in tecnicas:
        records.append({
            '_tecnica_code': t['x_code'],
            'name': f"Servicio de {t['x_name']}",
            'type': 'service',
            'sale_ok': True,
            'purchase_ok': False,
            'invoice_policy': 'order',
            'list_price': 0.0,
            'categ_id': categoria_id,
            'x_es_servicio_personalizacion': True,
            'x_tecnica_servicio_id': t['id'],
        })
    return records


def seed(client: OdooClient, records: list[dict[str, Any]], apply: bool) -> int:
    mode = 'APPLY' if apply else 'DRY-RUN'
    print(f"\n=== {mode} — {len(records)} servicios de personalización ===\n")

    created = updated = failed = 0

    for rec in records:
        try:
            existing = client.search_read(
                MODEL,
                domain=[('x_tecnica_servicio_id', '=', rec['x_tecnica_servicio_id'])],
                fields=['id', 'name'],
            )
        except Exception as exc:
            print(f"  ✗ [{rec['name']}] error buscando: {exc}")
            failed += 1
            continue

        vals = {k: v for k, v in rec.items() if not k.startswith('_')}

        if existing:
            rec_id = existing[0]['id']
            if apply:
                try:
                    client.write(MODEL, [rec_id], vals)
                    print(f"  ↻ UPDATE id={rec_id} · {rec['name']}")
                    updated += 1
                except Exception as exc:
                    print(f"  ✗ UPDATE id={rec_id} falló: {exc}")
                    failed += 1
            else:
                print(f"  ↻ UPDATE id={rec_id} · {rec['name']}")
                updated += 1
        else:
            if apply:
                try:
                    new_id = client.create(MODEL, vals)
                    print(f"  + CREATE id={new_id} · {rec['name']}")
                    created += 1
                except Exception as exc:
                    print(f"  ✗ CREATE falló: {exc}")
                    failed += 1
            else:
                print(f"  + CREATE · {rec['name']}")
                created += 1

    verb = "aplicados" if apply else "(simulado, sin escribir)"
    print(f"\nResumen {verb}: {created} a crear, {updated} a actualizar, {failed} con error")
    if not apply:
        print("Dry-run: NO se escribió nada en Odoo. Re-corre con --apply para ejecutar.")
    return failed


def main() -> int:
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass

    load_dotenv()

    parser = argparse.ArgumentParser(description='Seed de servicios de personalización en Odoo (idempotente)')
    parser.add_argument('--categoria', default=DEFAULT_CATEGORIA,
                         help=f'Nombre exacto de la categoría de producto (default "{DEFAULT_CATEGORIA}")')
    parser.add_argument('--apply', action='store_true',
                         help='Ejecuta los cambios. Sin este flag es dry-run.')
    args = parser.parse_args()

    odoo_url = os.environ.get('ODOO_URL')
    api_key = os.environ.get('ODOO_API_KEY')
    database = os.environ.get('ODOO_DATABASE')
    if not odoo_url or not api_key:
        print('✗ Falta ODOO_URL o ODOO_API_KEY en variables de entorno', file=sys.stderr)
        return 1

    print(f"Seed servicios de personalización → {MODEL}")
    print(f"Categoría: {args.categoria}")
    print(f"Odoo: {odoo_url}")

    client = OdooClient(odoo_url, api_key, database)

    try:
        categoria_id = resolve_categoria(client, args.categoria)
    except RuntimeError as exc:
        print(f"\n✗ {exc}", file=sys.stderr)
        return 1

    tecnicas = load_tecnicas(client)
    if not tecnicas:
        print(f"\n✗ No se encontraron técnicas activas en {TECNICA_MODEL}.", file=sys.stderr)
        return 1
    print(f"Técnicas activas encontradas: {len(tecnicas)}")

    records = build_records(tecnicas, categoria_id)
    failed = seed(client, records, apply=args.apply)
    return 1 if failed else 0


if __name__ == '__main__':
    sys.exit(main())
