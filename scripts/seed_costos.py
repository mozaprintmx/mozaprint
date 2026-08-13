#!/usr/bin/env python3
"""
Carga (seed) de costos de personalización en x_costo_personalizacion.

Lee un CSV de costos (uno por proveedor+técnica+alcance+cantidad+área) y los
inserta/actualiza vía JSON-2 API. IDEMPOTENTE: busca por la combinación
(x_tecnica_id, x_proveedor_id, x_alcance_producto, x_qty_from, x_qty_to,
x_area_from_cm2, x_area_to_cm2, x_tintas) — si existe, actualiza (write); si
no, crea (create). Re-correr NO duplica.

DRY-RUN por defecto: sin --apply solo imprime qué haría, sin escribir en Odoo.

Uso:
    python seed_costos.py                    # dry-run (no escribe)
    python seed_costos.py --apply            # ejecuta los cambios
    python seed_costos.py --csv analysis/costos-personalizacion/costos_seed.csv --apply

Entrada (CSV, columnas): tecnica_code, proveedor_nombre, alcance_producto,
qty_from, qty_to, area_from_cm2, area_to_cm2, tintas, escala_por_tinta,
posiciones, unidad_cobro, costo_unit, costo_setup, markup, activa, notas

'markup' es OPCIONAL (factor costo -> precio de venta; default DEFAULT_MARKUP = 1.275).
El precio de venta NO se carga: x_precio_venta y x_precio_setup son campos CALCULADOS en
Odoo (costo x markup) y editables si se quiere un precio manual para una fila concreta.

Resolución de relaciones (cacheada, 1 búsqueda por valor distinto):
    tecnica_code      -> x_tecnica_id   (busca x_tecnica_personalizacion por x_code)
    proveedor_nombre  -> x_proveedor_id (busca res.partner por name EXACTO, igual
                                          que el sync; ABORTA si no matchea exactamente 1)

x_name se arma automáticamente: "{proveedor} - {técnica} - {alcance} - qty {from}-{to}"

Variables de entorno (desde .env):
    ODOO_URL, ODOO_API_KEY, ODOO_DATABASE (opcional)
"""

import argparse
import csv
import os
import sys
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

from odoo_client import OdooClient

MODEL = 'x_costo_personalizacion'
TECNICA_MODEL = 'x_tecnica_personalizacion'
DEFAULT_CSV = 'analysis/costos-personalizacion/costos_seed.csv'
# Factor costo -> precio de venta cuando el CSV no trae columna 'markup'.
# x_precio_venta / x_precio_setup se CALCULAN en Odoo (campos computed) a partir de
# x_costo_unit / x_costo_setup y este factor; el script solo carga costo + markup.
DEFAULT_MARKUP = 1.275
REQUIRED_COLUMNS = (
    'tecnica_code', 'proveedor_nombre', 'qty_from', 'unidad_cobro', 'costo_unit',
)
VALID_UNIDAD_COBRO = ('pieza', 'lote')
# Campos que forman la llave natural de idempotencia (ver docstring).
MATCH_FIELDS = (
    'x_tecnica_id', 'x_proveedor_id', 'x_alcance_producto',
    'x_qty_from', 'x_qty_to', 'x_area_from_cm2', 'x_area_to_cm2', 'x_tintas',
)


def load_rows(csv_path: Path) -> list[dict[str, str]]:
    """Lee el CSV (tolera BOM) y valida columnas requeridas."""
    with open(csv_path, encoding='utf-8-sig', newline='') as f:
        reader = csv.DictReader(f)
        missing = [c for c in REQUIRED_COLUMNS if c not in (reader.fieldnames or [])]
        if missing:
            raise ValueError(
                f"CSV sin columnas requeridas {missing}. "
                f"Encontradas: {reader.fieldnames}"
            )
        return [row for row in reader]


def _int_or_none(raw: str) -> int | None:
    raw = (raw or '').strip()
    return int(raw) if raw else None


def _float_or_none(raw: str) -> float | None:
    raw = (raw or '').strip()
    return float(raw) if raw else None


def _bool(raw: str, default: bool = False) -> bool:
    raw = (raw or '').strip().lower()
    if raw in ('true', '1', 'si', 'sí', 'yes'):
        return True
    if raw in ('false', '0', 'no'):
        return False
    return default


def build_records(rows: list[dict[str, str]]) -> list[dict[str, Any]]:
    """
    Construye records intermedios (con códigos SIN resolver todavía) y valida
    tipos/consistencia. Aborta con ValueError si hay filas inválidas.
    """
    records: list[dict[str, Any]] = []
    errors: list[str] = []

    for idx, row in enumerate(rows):
        line_no = idx + 2  # +1 header, +1 base-1

        tecnica_code = (row.get('tecnica_code') or '').strip()
        proveedor_nombre = (row.get('proveedor_nombre') or '').strip()
        unidad_cobro = (row.get('unidad_cobro') or '').strip().lower()

        if not tecnica_code:
            errors.append(f"línea {line_no}: tecnica_code vacío")
            continue
        if not proveedor_nombre:
            errors.append(f"línea {line_no}: proveedor_nombre vacío")
            continue
        if unidad_cobro not in VALID_UNIDAD_COBRO:
            errors.append(
                f"línea {line_no}: unidad_cobro '{unidad_cobro}' inválido "
                f"(debe ser {VALID_UNIDAD_COBRO})"
            )
            continue

        try:
            qty_from = _int_or_none(row.get('qty_from'))
            qty_to = _int_or_none(row.get('qty_to'))
            area_from = _float_or_none(row.get('area_from_cm2'))
            area_to = _float_or_none(row.get('area_to_cm2'))
            tintas = _int_or_none(row.get('tintas')) or 1
            posiciones = _int_or_none(row.get('posiciones')) or 1
            costo_unit = float(row['costo_unit'])
            costo_setup = _float_or_none(row.get('costo_setup')) or 0.0
            # Markup: factor costo -> precio de venta. Columna opcional; si falta o viene
            # vacía se usa el estándar de Mozaprint (DEFAULT_MARKUP).
            markup = _float_or_none(row.get('markup')) or DEFAULT_MARKUP
        except (ValueError, KeyError) as exc:
            errors.append(f"línea {line_no}: valor numérico inválido ({exc})")
            continue

        if qty_from is None:
            errors.append(f"línea {line_no}: qty_from vacío")
            continue
        if qty_to is not None and qty_from > qty_to:
            errors.append(f"línea {line_no}: qty_from ({qty_from}) > qty_to ({qty_to})")
            continue
        if area_from is not None and area_to is not None and area_from > area_to:
            errors.append(f"línea {line_no}: area_from_cm2 ({area_from}) > area_to_cm2 ({area_to})")
            continue

        records.append({
            '_tecnica_code': tecnica_code,
            '_proveedor_nombre': proveedor_nombre,
            '_line_no': line_no,
            'x_alcance_producto': (row.get('alcance_producto') or '').strip(),
            'x_qty_from': qty_from,
            'x_qty_to': qty_to,
            'x_area_from_cm2': area_from,
            'x_area_to_cm2': area_to,
            'x_tintas': tintas,
            'x_escala_por_tinta': _bool(row.get('escala_por_tinta')),
            'x_posiciones': posiciones,
            'x_unidad_cobro': unidad_cobro,
            'x_costo_unit': costo_unit,
            'x_costo_setup': costo_setup,
            'x_markup': markup,
            'x_activa': _bool(row.get('activa'), default=True),
            'x_notas': (row.get('notas') or '').strip(),
        })

    if errors:
        raise ValueError("Validación del CSV falló:\n  " + "\n  ".join(errors))

    return records


def _build_name(tecnica_display: str, proveedor_nombre: str, rec: dict[str, Any]) -> str:
    qty = f"{rec['x_qty_from']}-{rec['x_qty_to']}" if rec['x_qty_to'] else f"{rec['x_qty_from']}+"
    partes = [proveedor_nombre, tecnica_display]
    if rec['x_alcance_producto']:
        partes.append(rec['x_alcance_producto'])
    partes.append(f"qty {qty}")
    return " - ".join(partes)


def resolve_relations(
    client: OdooClient, records: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[str]]:
    """
    Resuelve tecnica_code -> x_tecnica_id y proveedor_nombre -> x_proveedor_id,
    cacheados por valor distinto. Devuelve (records_resueltos, errores).
    """
    errors: list[str] = []
    tecnica_cache: dict[str, tuple[int, str] | None] = {}
    proveedor_cache: dict[str, int | None] = {}

    for code in {r['_tecnica_code'] for r in records}:
        found = client.search_read(
            TECNICA_MODEL, domain=[('x_code', '=', code)], fields=['id', 'x_name'],
        )
        tecnica_cache[code] = (found[0]['id'], found[0]['x_name']) if found else None

    for nombre in {r['_proveedor_nombre'] for r in records}:
        found = client.search_read(
            'res.partner', domain=[('name', '=', nombre)], fields=['id', 'name'],
        )
        if len(found) == 1:
            proveedor_cache[nombre] = found[0]['id']
        else:
            proveedor_cache[nombre] = None
            plural = 'ninguno' if not found else f"{len(found)} ({[f['name'] for f in found]})"
            errors.append(
                f"proveedor_nombre '{nombre}': se esperaba 1 match en res.partner, "
                f"se encontraron {plural}. Ajusta el nombre en el CSV o crea/renombra "
                f"el partner en Odoo."
            )

    for code, val in tecnica_cache.items():
        if val is None:
            errors.append(
                f"tecnica_code '{code}': no existe en {TECNICA_MODEL} (x_code). "
                f"Revisa data/tecnicas_seed.csv."
            )

    if errors:
        return [], errors

    resolved = []
    for rec in records:
        tecnica_id, tecnica_display = tecnica_cache[rec['_tecnica_code']]
        proveedor_id = proveedor_cache[rec['_proveedor_nombre']]
        out = {k: v for k, v in rec.items() if not k.startswith('_')}
        out['x_tecnica_id'] = tecnica_id
        out['x_proveedor_id'] = proveedor_id
        out['x_name'] = _build_name(tecnica_display, rec['_proveedor_nombre'], rec)
        resolved.append(out)
    return resolved, []


def seed(client: OdooClient, records: list[dict[str, Any]], apply: bool) -> int:
    """Ejecuta (o simula) el upsert idempotente. Devuelve nº de errores."""
    mode = 'APPLY' if apply else 'DRY-RUN'
    print(f"\n=== {mode} — {len(records)} filas de costo ===\n")

    created = updated = failed = 0

    for rec in records:
        match_domain = [(f, '=', rec[f]) for f in MATCH_FIELDS if rec[f] is not None]
        match_domain += [(f, '=', False) for f in MATCH_FIELDS if rec[f] is None]

        try:
            existing = client.search_read(MODEL, domain=match_domain, fields=['id'])
        except Exception as exc:
            print(f"  ✗ [{rec['x_name']}] error buscando: {exc}")
            failed += 1
            continue

        vals = {k: v for k, v in rec.items()}

        if existing:
            rec_id = existing[0]['id']
            if len(existing) > 1:
                print(f"  ⚠ [{rec['x_name']}] {len(existing)} filas ya matchean esta llave "
                      f"(ids {[e['id'] for e in existing]}) — actualizando solo la primera.")
            if apply:
                try:
                    client.write(MODEL, [rec_id], vals)
                    print(f"  ↻ UPDATE id={rec_id} · {rec['x_name']}")
                    updated += 1
                except Exception as exc:
                    print(f"  ✗ UPDATE id={rec_id} falló: {exc}")
                    failed += 1
            else:
                print(f"  ↻ UPDATE id={rec_id} · {rec['x_name']}")
                updated += 1
        else:
            if apply:
                try:
                    new_id = client.create(MODEL, vals)
                    print(f"  + CREATE id={new_id} · {rec['x_name']}")
                    created += 1
                except Exception as exc:
                    print(f"  ✗ CREATE falló: {exc}")
                    failed += 1
            else:
                print(f"  + CREATE · {rec['x_name']}")
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

    parser = argparse.ArgumentParser(description='Seed de costos de personalización en Odoo (idempotente)')
    parser.add_argument('--csv', default=DEFAULT_CSV, help=f'CSV de entrada (default {DEFAULT_CSV})')
    parser.add_argument('--apply', action='store_true',
                         help='Ejecuta los cambios. Sin este flag es dry-run.')
    args = parser.parse_args()

    csv_path = Path(args.csv)
    if not csv_path.exists():
        print(f"✗ No existe el CSV: {csv_path}", file=sys.stderr)
        return 1

    odoo_url = os.environ.get('ODOO_URL')
    api_key = os.environ.get('ODOO_API_KEY')
    database = os.environ.get('ODOO_DATABASE')
    if not odoo_url or not api_key:
        print('✗ Falta ODOO_URL o ODOO_API_KEY en variables de entorno', file=sys.stderr)
        return 1

    print(f"Seed costos de personalización → {MODEL}")
    print(f"CSV : {csv_path}")
    print(f"Odoo: {odoo_url}")

    try:
        rows = load_rows(csv_path)
        records = build_records(rows)
    except ValueError as exc:
        print(f"\n✗ {exc}", file=sys.stderr)
        return 1

    client = OdooClient(odoo_url, api_key, database)

    resolved, resolve_errors = resolve_relations(client, records)
    if resolve_errors:
        print("\n✗ No se pudieron resolver todas las relaciones técnica/proveedor:", file=sys.stderr)
        for e in resolve_errors:
            print(f"  - {e}", file=sys.stderr)
        return 1

    failed = seed(client, resolved, apply=args.apply)
    return 1 if failed else 0


if __name__ == '__main__':
    sys.exit(main())
