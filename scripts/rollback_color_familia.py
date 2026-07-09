#!/usr/bin/env python3
"""
Rollback SEGURO del atributo no_variant "Color (familia)" (creado por
derive_color_familia.py) en Odoo Online 19.0.

Un atributo no_variant se renderiza como selector en la ficha de producto
(comportamiento nativo), duplicando el selector del Color REAL. Este script quita
ese selector eliminando el atributo 'Color (familia)' y TODAS sus líneas.

Por ser no_variant, el atributo NUNCA creó product.product: eliminarlo solo borra
líneas informativas → es seguro y no afecta ninguna variante.

NO toca el atributo Color REAL (create_variant='always'), ni sus valores/líneas, ni
ninguna variante. Guardas duras abortan si algo no cuadra.

Elimina, en orden (solo con --apply):
    a) product.template.attribute.line con attribute_id = 'Color (familia)'  (limpia fichas)
    b) product.attribute.value del atributo (los 14 de familia)
    c) product.attribute 'Color (familia)'  (unlink; o --archive-only => active=False)

Uso:
    python rollback_color_familia.py                 # dry-run (no borra)
    python rollback_color_familia.py --apply         # ejecuta el borrado
    python rollback_color_familia.py --apply --archive-only   # archiva el atributo en vez de borrarlo

Variables de entorno (desde .env):
    ODOO_URL, ODOO_API_KEY, ODOO_DATABASE (opcional)
"""

import argparse
import os
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv

from odoo_client import OdooClient

ATTR_MODEL = 'product.attribute'
VALUE_MODEL = 'product.attribute.value'
LINE_MODEL = 'product.template.attribute.line'

FAMILIA_ATTR_NAME = 'Color (familia)'
COLOR_ATTR_NAME = 'Color'

# Guardas de modelo
FORBIDDEN_MODELS = {'product.product'}
ALLOWED_UNLINK_MODELS = {LINE_MODEL, VALUE_MODEL, ATTR_MODEL}

_UNLINK_BATCH = 200


def _tid(rec_field) -> int | None:
    if isinstance(rec_field, (list, tuple)):
        return rec_field[0] if rec_field else None
    return rec_field or None


def _find_attr(client: OdooClient, name: str) -> list[dict]:
    return client.search_read(
        ATTR_MODEL, [('name', '=', name)],
        fields=['id', 'name', 'create_variant', 'active'],
        context={'active_test': False},
    )


# ─── Guardas de escritura ────────────────────────────────────────────────────

def _safe_unlink(client: OdooClient, model: str, ids: list[int]) -> None:
    if model in FORBIDDEN_MODELS:
        raise RuntimeError(f'PROHIBIDO unlink sobre {model}')
    if model not in ALLOWED_UNLINK_MODELS:
        raise RuntimeError(f'unlink no permitido sobre {model}')
    if not ids:
        return
    client.unlink(model, ids)


def _safe_archive_attr(client: OdooClient, attr_id: int, target_id: int) -> None:
    if attr_id != target_id:
        raise RuntimeError('archive solo permitido sobre el atributo objetivo')
    vals = {'active': False}
    if set(vals) != {'active'}:
        raise RuntimeError(f'archive: vals no permitido {list(vals)}')
    client.write(ATTR_MODEL, [attr_id], vals)


# ─── Resolución con guardas duras ────────────────────────────────────────────

def resolve_target(client: OdooClient) -> dict | None:
    """
    Resuelve y VALIDA el atributo 'Color (familia)'. Devuelve el dict del atributo,
    o None si no existe (idempotente). Aborta (SystemExit) si alguna guarda falla.
    """
    fam = _find_attr(client, FAMILIA_ATTR_NAME)
    if not fam:
        print(f"✓ No existe '{FAMILIA_ATTR_NAME}'. Nada que revertir (idempotente).")
        return None
    if len(fam) > 1:
        print(f"✗ ABORT: {len(fam)} atributos llamados '{FAMILIA_ATTR_NAME}':")
        for a in fam:
            print(f"    id={a['id']} create_variant={a.get('create_variant')!r} active={a.get('active')}")
        raise SystemExit('Desambigúa manualmente antes de correr el rollback.')

    target = fam[0]
    cv = target.get('create_variant')
    # GUARDA CRÍTICA: el objetivo DEBE ser no_variant.
    if cv != 'no_variant':
        raise SystemExit(
            f"✗ ABORT: '{FAMILIA_ATTR_NAME}' tiene create_variant={cv!r} (esperado 'no_variant'). "
            f"Protección contra tocar un atributo que genera variantes. No se elimina nada."
        )

    # GUARDA: el id del objetivo NUNCA debe coincidir con el del Color REAL (always).
    color = _find_attr(client, COLOR_ATTR_NAME)
    color_real_ids = {c['id'] for c in color if c.get('create_variant') == 'always'}
    if target['id'] in color_real_ids:
        raise SystemExit(
            f"✗ ABORT: el id objetivo {target['id']} coincide con el atributo Color REAL. Abortando."
        )
    print(f"→ Objetivo: '{FAMILIA_ATTR_NAME}' id={target['id']} "
          f"create_variant={cv!r} active={target.get('active')}")
    if color_real_ids:
        print(f"→ Color REAL (intacto): ids={sorted(color_real_ids)} create_variant='always'")
    return target


# ─── Unlink de líneas con tolerancia a fallos ────────────────────────────────

def unlink_lines(
    client: OdooClient, line_ids: list[int], apply: bool
) -> tuple[int, list[tuple[int, str]]]:
    """Elimina líneas en lotes; si un lote falla, aísla por-línea. Devuelve (ok, fallidas)."""
    if not apply:
        return 0, []
    ok = 0
    fallidas: list[tuple[int, str]] = []
    for i in range(0, len(line_ids), _UNLINK_BATCH):
        chunk = line_ids[i:i + _UNLINK_BATCH]
        try:
            _safe_unlink(client, LINE_MODEL, chunk)
            ok += len(chunk)
        except Exception:
            # Aislar la línea problemática (ej. referencia inesperada) sin abortar todo.
            for lid in chunk:
                try:
                    _safe_unlink(client, LINE_MODEL, [lid])
                    ok += 1
                except Exception as exc:
                    fallidas.append((lid, str(exc)[:160]))
    return ok, fallidas


# ─── Reporte ─────────────────────────────────────────────────────────────────

def write_report(path: Path, mode: str, target: dict, n_lines: int, n_tmpls: int,
                 values: list[dict], archive_only: bool,
                 result: dict | None) -> None:
    L: list[str] = []
    L.append(f'# Rollback de "{FAMILIA_ATTR_NAME}" — {datetime.now().isoformat(timespec="seconds")}  [{mode}]\n')
    L.append(f'- Atributo objetivo: id={target["id"]} create_variant=no_variant '
             f'active={target.get("active")}')
    L.append(f'- Líneas a eliminar (a): **{n_lines}** en **{n_tmpls}** templates')
    L.append(f'- Valores a eliminar (b): **{len(values)}**')
    accion_c = 'archivar (active=False)' if archive_only else 'eliminar (unlink)'
    L.append(f'- Atributo (c): {accion_c}\n')
    L.append('## Valores del atributo\n')
    L.append('| id | name |')
    L.append('|---:|---|')
    for v in values:
        L.append(f'| {v["id"]} | {v["name"]} |')
    if result is not None:
        L.append('\n## Resultado [APPLY]\n')
        L.append(f'- Líneas eliminadas: {result["lines_ok"]} / {n_lines} esperadas')
        L.append(f'- Valores eliminados: {result["values_ok"]} / {len(values)} esperados')
        L.append(f'- Atributo: {result["attr_action"]}')
        if result['lines_fail']:
            L.append(f'\n### ⚠ Líneas que fallaron ({len(result["lines_fail"])})\n')
            L.append('| line_id | error |')
            L.append('|---:|---|')
            for lid, err in result['lines_fail']:
                L.append(f'| {lid} | {err} |')
    with open(path, 'w', encoding='utf-8') as f:
        f.write('\n'.join(L) + '\n')


# ─── Main ────────────────────────────────────────────────────────────────────

def main() -> int:
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass

    parser = argparse.ArgumentParser(description=f"Rollback seguro de '{FAMILIA_ATTR_NAME}'")
    parser.add_argument('--apply', action='store_true', help='Ejecuta el borrado. Sin esto, dry-run.')
    parser.add_argument('--archive-only', action='store_true',
                        help='Archiva el atributo (active=False) en vez de borrarlo (reversible).')
    parser.add_argument('--output', '-o', help='Ruta del reporte .md')
    args = parser.parse_args()

    load_dotenv()
    odoo_url = os.environ.get('ODOO_URL')
    api_key = os.environ.get('ODOO_API_KEY')
    database = os.environ.get('ODOO_DATABASE')
    if not odoo_url or not api_key:
        print('✗ Falta ODOO_URL o ODOO_API_KEY en variables de entorno', file=sys.stderr)
        return 1

    today = datetime.now().strftime('%Y%m%d')
    Path('reports').mkdir(exist_ok=True)
    out_path = Path(args.output) if args.output else Path(f'reports/rollback_familia_{today}.md')

    mode = 'APPLY' if args.apply else 'DRY-RUN'
    print(f'Rollback Color (familia)  [{mode}]')
    print(f'Odoo: {odoo_url}')

    client = OdooClient(odoo_url, api_key, database)

    # 1. Resolver + guardas duras
    target = resolve_target(client)
    if target is None:
        return 0
    target_id = target['id']

    # 2. Líneas del atributo (a) — lo que ensucia las fichas
    lines = client.search_read_all(
        LINE_MODEL, domain=[('attribute_id', '=', target_id)],
        fields=['id', 'product_tmpl_id'],
    )
    line_ids = [l['id'] for l in lines]
    tmpls = {_tid(l.get('product_tmpl_id')) for l in lines}
    tmpls.discard(None)

    # 3. Valores del atributo (b)
    values = client.search_read_all(
        VALUE_MODEL, domain=[('attribute_id', '=', target_id)],
        fields=['id', 'name'], context={'active_test': False},
    )

    print(f'→ Líneas a eliminar: {len(line_ids)} en {len(tmpls)} templates')
    print(f'→ Valores a eliminar: {len(values)}  ({", ".join(v["name"] for v in values)})')
    accion_c = 'ARCHIVAR (active=False)' if args.archive_only else 'ELIMINAR (unlink)'
    print(f'→ Atributo (c): {accion_c}')

    result: dict | None = None
    if args.apply:
        # a) líneas
        lines_ok, lines_fail = unlink_lines(client, line_ids, apply=True)
        print(f'  a) Líneas eliminadas: {lines_ok}/{len(line_ids)}'
              + (f'  ⚠ fallaron {len(lines_fail)}' if lines_fail else ''))
        # b) valores (solo si no quedaron líneas colgando de esos valores)
        value_ids = [v['id'] for v in values]
        values_ok = 0
        try:
            _safe_unlink(client, VALUE_MODEL, value_ids)
            values_ok = len(value_ids)
        except Exception as exc:
            print(f'  ✗ b) fallo al eliminar valores: {str(exc)[:160]}')
        print(f'  b) Valores eliminados: {values_ok}/{len(value_ids)}')
        # c) atributo
        try:
            if args.archive_only:
                _safe_archive_attr(client, target_id, target_id)
                attr_action = 'archivado (active=False)'
            else:
                _safe_unlink(client, ATTR_MODEL, [target_id])
                attr_action = 'eliminado (unlink)'
        except Exception as exc:
            attr_action = f'FALLÓ: {str(exc)[:160]}'
        print(f'  c) Atributo: {attr_action}')
        result = {
            'lines_ok': lines_ok, 'lines_fail': lines_fail,
            'values_ok': values_ok, 'attr_action': attr_action,
        }

    # 4. Reporte
    write_report(out_path, mode, target, len(line_ids), len(tmpls),
                 values, args.archive_only, result)

    print(f'\n=== {mode} ===')
    if args.apply:
        n_fail = len(result['lines_fail']) if result else 0
        print(f'  Rollback ejecutado. Líneas {result["lines_ok"]}/{len(line_ids)}, '
              f'valores {result["values_ok"]}/{len(values)}, atributo: {result["attr_action"]}')
        print(f'  Reporte: {out_path}')
        return 1 if n_fail else 0
    print(f'  Se eliminarían {len(line_ids)} líneas ({len(tmpls)} templates), '
          f'{len(values)} valores y el atributo (NADA se borró)')
    print(f'  Reporte: {out_path}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
