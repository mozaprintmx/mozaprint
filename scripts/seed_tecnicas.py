#!/usr/bin/env python3
"""
Carga (seed) del catálogo de técnicas de personalización en Odoo.

Lee un CSV de técnicas canónicas y las inserta/actualiza en el modelo
x_tecnica_personalizacion vía JSON-2 API. IDEMPOTENTE: busca por x_code; si
existe actualiza (write), si no crea (create). Re-correr NO duplica.

DRY-RUN por defecto: sin --apply solo imprime qué haría, sin escribir en Odoo.

Uso:
    python seed_tecnicas.py                 # dry-run (no escribe)
    python seed_tecnicas.py --apply         # ejecuta los cambios
    python seed_tecnicas.py --csv data/tecnicas_seed.csv --apply

Entrada (CSV, columnas): code, nombre, x_aliases  (x_orden opcional)
Mapeo a x_tecnica_personalizacion:
    code      -> x_code        (llave de idempotencia; requerido, único)
    nombre    -> x_name
    x_aliases -> x_aliases
    x_orden   -> x_orden        (del CSV si existe; si no, (línea+1)*10)
    (fijos)   -> x_activa=True, x_descripcion=""

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

MODEL = 'x_tecnica_personalizacion'
DEFAULT_CSV = 'data/tecnicas_seed.csv'
REQUIRED_COLUMNS = ('code', 'nombre', 'x_aliases')


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


def build_records(rows: list[dict[str, str]]) -> list[dict[str, Any]]:
    """
    Construye los vals para Odoo y valida x_code (no vacío, único).
    Aborta con ValueError si hay vacíos o duplicados.
    """
    records: list[dict[str, Any]] = []
    seen: dict[str, int] = {}
    empties: list[int] = []
    duplicates: list[str] = []

    for idx, row in enumerate(rows):
        code = (row.get('code') or '').strip()
        line_no = idx + 2  # +1 por header, +1 por base-1 (para mensajes humanos)

        if not code:
            empties.append(line_no)
            continue
        if code in seen:
            duplicates.append(f"'{code}' (líneas {seen[code]} y {line_no})")
            continue
        seen[code] = line_no

        # x_orden: usa el del CSV si es un entero válido; si no, (índice+1)*10.
        raw_orden = (row.get('x_orden') or '').strip()
        try:
            orden = int(raw_orden) if raw_orden else (idx + 1) * 10
        except ValueError:
            orden = (idx + 1) * 10

        records.append({
            'x_code': code,
            'x_name': (row.get('nombre') or '').strip(),
            'x_aliases': (row.get('x_aliases') or '').strip(),
            'x_orden': orden,
            'x_activa': True,
            'x_descripcion': '',
        })

    errors = []
    if empties:
        errors.append(f"x_code vacío en líneas: {empties}")
    if duplicates:
        errors.append(f"x_code duplicado: {'; '.join(duplicates)}")
    if errors:
        raise ValueError("Validación del CSV falló — " + " | ".join(errors))

    return records


def seed(client: OdooClient, records: list[dict[str, Any]], apply: bool) -> int:
    """Ejecuta (o simula) el upsert idempotente. Devuelve nº de errores."""
    mode = 'APPLY' if apply else 'DRY-RUN'
    print(f"\n=== {mode} — {len(records)} técnicas ===\n")

    created = updated = failed = 0

    for rec in records:
        code = rec['x_code']
        try:
            existing = client.search_read(
                MODEL, domain=[('x_code', '=', code)], fields=['id', 'x_code'],
            )
        except Exception as exc:
            print(f"  ✗ [{code}] error buscando: {exc}")
            failed += 1
            continue

        if existing:
            rec_id = existing[0]['id']
            if apply:
                try:
                    client.write(MODEL, [rec_id], rec)
                    print(f"  ↻ UPDATE [{code}] id={rec_id} · {rec['x_name']}")
                    updated += 1
                except Exception as exc:
                    print(f"  ✗ UPDATE [{code}] id={rec_id} falló: {exc}")
                    failed += 1
            else:
                print(f"  ↻ UPDATE [{code}] id={rec_id} · {rec['x_name']}")
                updated += 1
        else:
            if apply:
                try:
                    new_id = client.create(MODEL, rec)
                    print(f"  + CREATE [{code}] id={new_id} · {rec['x_name']}")
                    created += 1
                except Exception as exc:
                    print(f"  ✗ CREATE [{code}] falló: {exc}")
                    failed += 1
            else:
                print(f"  + CREATE [{code}] · {rec['x_name']}")
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

    parser = argparse.ArgumentParser(description='Seed de técnicas en Odoo (idempotente)')
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

    print(f"Seed técnicas → {MODEL}")
    print(f"CSV : {csv_path}")
    print(f"Odoo: {odoo_url}")

    try:
        rows = load_rows(csv_path)
        records = build_records(rows)
    except ValueError as exc:
        print(f"\n✗ {exc}", file=sys.stderr)
        return 1

    client = OdooClient(odoo_url, api_key, database)
    failed = seed(client, records, apply=args.apply)
    return 1 if failed else 0


if __name__ == '__main__':
    sys.exit(main())
