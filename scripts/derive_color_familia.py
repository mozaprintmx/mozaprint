#!/usr/bin/env python3
"""
Deriva el atributo no_variant "Color (familia)" en cada product.template a partir
de sus valores reales de "Color", para un filtro limpio de color en /shop.

NO crea variantes (create_variant='no_variant'), NO toca el atributo Color real ni
su create_variant. La familia se calcula con colores_engine.familia() (motor laxo:
agrupa por color base/lex dominante; ver scripts/colores_engine.py).

POR QUÉ ES INCREMENTAL Y NECESITA HOOK
El sync opera por-línea sobre attribute_line_ids (comandos (1,…)/(0,0,…), solo Color
y Talla; nunca (5,0,0)) — auditado en analysis/supplier-sync/AUDITORIA_COLORES.md.
Consecuencia: una línea "Color (familia)" agregada por fuera SOBREVIVE toda corrida
del sync. Por eso:
  - La derivación es INCREMENTAL: solo escribe templates nuevos o cuyo set de Color
    cambió (idempotente + --since por write_date). No hace full en cada corrida.
  - En la ruta de CREACIÓN el sync arma las líneas desde cero, así que un producto
    NUEVO entra SIN familia hasta que corra la derivación → el hook post-sync NO es
    opcional (ver al final del docstring).

QUÉ ESCRIBE (y qué NO)
  - Crea/asegura el atributo 'Color (familia)' (no_variant, display_type=color) y sus
    14 valores desde data/colores_familias.csv (Multicolor sin hex).
  - Escribe/actualiza SOLO la línea 'Color (familia)' de cada template, vía comando
    por-línea (1, line_id, …) o (0, 0, …). Nunca toca otras líneas.
  - PROHIBIDO: create/write sobre product.product; tocar create_variant de cualquier
    atributo; modificar la línea/valores del atributo Color REAL (solo lectura).
  - Aborta si 'Color (familia)' existe con create_variant != 'no_variant'.

Uso:
    python derive_color_familia.py                    # dry-run (no escribe)
    python derive_color_familia.py --apply            # crea atributo/valores + escribe líneas
    python derive_color_familia.py --limit 100        # acota nº de templates
    python derive_color_familia.py --published-only    # solo templates publicados
    python derive_color_familia.py --since 2026-07-01  # solo write_date >= fecha (incremental)
    python derive_color_familia.py --self-check        # familia() OFFLINE sobre el CSV dump

Variables de entorno (desde .env; no aplican a --self-check):
    ODOO_URL, ODOO_API_KEY, ODOO_DATABASE (opcional)

────────────────────────────────────────────────────────────────────────────────
HOOK POST-SYNC (OBLIGATORIO — documentación; este script NO modifica el sync)
────────────────────────────────────────────────────────────────────────────────
Encadenar tras cada sync EXITOSO, incremental con --since = marca de la última corrida
(cubre productos nuevos/cambiados del ciclo). Entorno limpio, sin heredar credenciales.

Config en .env:
    DERIVE_FAMILIA_ENABLED=true
    DERIVE_FAMILIA_SCRIPT_PATH=D:/MozaPrint/Odoo/Proyectos/mozaprint/scripts/derive_color_familia.py
    DERIVE_FAMILIA_PYTHON_PATH=C:/Users/.../Python312/python.exe

Snippet para copiar a analysis/supplier-sync/ (env limpio, sin heredar Odoo):

    import os, subprocess, sys
    from datetime import datetime, timezone
    if os.environ.get("DERIVE_FAMILIA_ENABLED", "").lower() in ("1", "true", "yes"):
        script = os.environ["DERIVE_FAMILIA_SCRIPT_PATH"]
        python = os.environ.get("DERIVE_FAMILIA_PYTHON_PATH", sys.executable)
        # 'desde' = marca del inicio del ciclo de sync (UTC). Reprocesa lo tocado hoy.
        desde = ciclo_inicio_utc.strftime("%Y-%m-%d %H:%M:%S")   # tu marca del ciclo
        child_env = {
            "PATH": os.environ.get("PATH", ""),
            "SYSTEMROOT": os.environ.get("SYSTEMROOT", ""),  # requerido en Windows
        }
        subprocess.run(
            [python, script, "--apply", "--since", desde],
            cwd=os.path.dirname(os.path.dirname(script)),  # raíz del repo (.env + reports/)
            env=child_env,
            check=False,
        )
"""

import argparse
import csv
import json
import os
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv

from colores_engine import DATA_DIR, ColorEngine
from derive_colores import _newest_color_values_csv, resolve_color_attribute
from odoo_client import OdooClient

ATTR_MODEL = 'product.attribute'
VALUE_MODEL = 'product.attribute.value'
LINE_MODEL = 'product.template.attribute.line'
TEMPLATE_MODEL = 'product.template'

FAMILIA_ATTR_NAME = 'Color (familia)'
FAMILIAS_CSV = DATA_DIR / 'colores_familias.csv'

# Único modelo sobre el que se permite escribir líneas de atributo.
WRITE_MODEL = TEMPLATE_MODEL


# ─── Carga de familias ───────────────────────────────────────────────────────

def load_familias() -> list[dict]:
    """Lee data/colores_familias.csv (ignora '#'): [{familia, hex, orden, tipo}]."""
    with open(FAMILIAS_CSV, encoding='utf-8') as f:
        lines = [ln for ln in f if not ln.lstrip().startswith('#')]
    filas = list(csv.DictReader(lines))
    return [{
        'familia': r['familia'].strip(),
        'hex': (r['hex'] or '').strip().upper(),
        'orden': int(r['orden']),
        'tipo': r['tipo'].strip(),
    } for r in filas]


# ─── Atributo familia (get_or_create con guardas) ────────────────────────────

def ensure_familia_attribute(
    client: OdooClient, familias: list[dict], apply: bool
) -> tuple[int | None, dict[str, int], bool]:
    """
    Asegura el atributo 'Color (familia)' (no_variant, display_type=color) y sus 14
    valores. Devuelve (attr_id|None, {familia: value_id}, would_create).

    GUARDA DURA: aborta si existe con create_variant != 'no_variant' (cambiar valores
    de una línea con create_variant='always' regeneraría product.product masivamente).
    En dry-run sin el atributo, devuelve (None, {}, True) para proyectar sin escribir.
    """
    cands = client.search_read(
        ATTR_MODEL, [('name', '=', FAMILIA_ATTR_NAME)],
        fields=['id', 'create_variant', 'display_type'],
        context={'active_test': False},
    )
    if cands:
        attr = cands[0]
        cv = attr.get('create_variant')
        if cv != 'no_variant':
            raise SystemExit(
                f"✗ ABORT: '{FAMILIA_ATTR_NAME}' existe con create_variant={cv!r}; "
                f"debe ser 'no_variant'. Cambiar valores regeneraría variantes en miles "
                f"de templates. No se toca create_variant desde este script."
            )
        attr_id = attr['id']
    else:
        if not apply:
            return None, {}, True
        attr_id = client.create(ATTR_MODEL, {
            'name': FAMILIA_ATTR_NAME,
            'create_variant': 'no_variant',
            'display_type': 'color',
        })
        print(f"→ Creado atributo '{FAMILIA_ATTR_NAME}' (no_variant) id={attr_id}")

    # Asegurar los 14 valores (por nombre).
    existing = client.search_read(
        VALUE_MODEL, [('attribute_id', '=', attr_id)],
        fields=['id', 'name'], context={'active_test': False},
    )
    by_name = {v['name']: v['id'] for v in existing}
    val_map: dict[str, int] = {}
    for fam in familias:
        name = fam['familia']
        if name in by_name:
            val_map[name] = by_name[name]
        elif apply:
            vals = {'attribute_id': attr_id, 'name': name, 'sequence': fam['orden']}
            if fam['hex']:
                vals['html_color'] = fam['hex']
            val_map[name] = client.create(VALUE_MODEL, vals)
            print(f"   + valor familia '{name}' id={val_map[name]}")
        # dry-run con atributo existente pero valor faltante: se omite del map.
    return attr_id, val_map, False


# ─── Escritura guardada de la línea familia ──────────────────────────────────

def _guard_line_command(cmd: tuple, familia_attr_id: int) -> None:
    """Valida un comando One2many para attribute_line_ids antes de escribir."""
    op = cmd[0]
    if op not in (0, 1):
        raise RuntimeError(f'Comando de línea no permitido: {op} (solo (0,0,…)/(1,…))')
    payload = cmd[2] if len(cmd) > 2 else {}
    if 'create_variant' in payload:
        raise RuntimeError('PROHIBIDO tocar create_variant')
    if op == 0 and payload.get('attribute_id') != familia_attr_id:
        raise RuntimeError('ADD de línea solo permitido para el atributo familia')
    # value_ids debe ser un reemplazo (6,0,[…]) de valores familia.
    for vcmd in payload.get('value_ids', []):
        if vcmd[0] != 6:
            raise RuntimeError(f'value_ids solo admite (6,0,…); llegó {vcmd[0]}')


def _write_familia_line(
    client: OdooClient, tmpl_ids: list[int], cmd: tuple, familia_attr_id: int
) -> None:
    """Único punto de escritura. Solo product.template.attribute_line_ids con (0,0)/(1,…)."""
    if WRITE_MODEL != TEMPLATE_MODEL:
        raise RuntimeError('WRITE_MODEL inesperado')
    _guard_line_command(cmd, familia_attr_id)
    vals = {'attribute_line_ids': [cmd]}
    if set(vals) != {'attribute_line_ids'}:
        raise RuntimeError(f'Escritura no permitida: vals={list(vals)}')
    client.write(TEMPLATE_MODEL, tmpl_ids, vals)


# ─── Lectura del estado en Odoo ──────────────────────────────────────────────

def _tid(rec_field) -> int | None:
    """product_tmpl_id llega como [id, name] o id."""
    if isinstance(rec_field, (list, tuple)):
        return rec_field[0] if rec_field else None
    return rec_field or None


def read_color_state(
    client: OdooClient, color_attr_id: int, since: str | None, published_only: bool,
) -> tuple[dict[int, set[int]], dict[int, str]]:
    """
    Devuelve (tmpl_color_vals, vid_name):
      - tmpl_color_vals: template_id -> set(color value_ids) (product.attribute.value)
      - vid_name: color value_id -> name
    Aplica filtros --since (write_date) y --published-only a nivel template.
    """
    color_lines = client.search_read_all(
        LINE_MODEL, domain=[('attribute_id', '=', color_attr_id)],
        fields=['product_tmpl_id', 'value_ids'],
    )
    tmpl_color_vals: dict[int, set[int]] = defaultdict(set)
    for l in color_lines:
        tid = _tid(l.get('product_tmpl_id'))
        if tid is None:
            continue
        tmpl_color_vals[tid].update(l.get('value_ids') or [])

    # Filtros a nivel template
    if since or published_only:
        domain: list = [('id', 'in', list(tmpl_color_vals))]
        if since:
            domain.append(('write_date', '>=', since))
        if published_only:
            domain.append(('is_published', '=', True))
        kept = {t['id'] for t in client.search_read_all(
            TEMPLATE_MODEL, domain=domain, fields=['id'])}
        tmpl_color_vals = {tid: v for tid, v in tmpl_color_vals.items() if tid in kept}

    # Nombres de los valores de Color usados
    all_vids = set().union(*tmpl_color_vals.values()) if tmpl_color_vals else set()
    vid_name: dict[int, str] = {}
    if all_vids:
        for v in client.search_read_all(
            VALUE_MODEL, domain=[('id', 'in', list(all_vids))],
            fields=['id', 'name'], context={'active_test': False},
        ):
            vid_name[v['id']] = v['name']
    return dict(tmpl_color_vals), vid_name


def read_familia_lines(
    client: OdooClient, familia_attr_id: int
) -> dict[int, tuple[int, set[int]]]:
    """template_id -> (line_id, set(familia value_ids)) de las líneas 'Color (familia)' actuales."""
    out: dict[int, tuple[int, set[int]]] = {}
    for l in client.search_read_all(
        LINE_MODEL, domain=[('attribute_id', '=', familia_attr_id)],
        fields=['id', 'product_tmpl_id', 'value_ids'],
    ):
        tid = _tid(l.get('product_tmpl_id'))
        if tid is not None:
            out[tid] = (l['id'], set(l.get('value_ids') or []))
    return out


# ─── Reporte ─────────────────────────────────────────────────────────────────

def write_report_files(report: dict, stem: Path) -> tuple[Path, Path]:
    json_path = stem.with_suffix('.json')
    md_path = stem.with_suffix('.md')
    with open(json_path, 'w', encoding='utf-8') as f:
        json.dump(report, f, ensure_ascii=False, indent=2)

    L: list[str] = []
    L.append(f'# Derivación Color (familia) — {report["generated"]}  [{report["mode"]}]\n')
    L.append(f'- Templates procesados: **{report["templates"]}**')
    L.append(f'- Con ≥1 familia: {report["con_familia"]} · Sin ninguna familia: '
             f'{report["sin_familia"]}')
    L.append(f'- Escritos: {report["escritos"]} (crea {report["creados"]} / '
             f'actualiza {report["actualizados"]}) · Sin cambio: {report["sin_cambio"]}')
    if report['obsoletas']:
        L.append(f'- ⚠ Líneas familia obsoletas (color quedó sin familia, revisar): '
                 f'{report["obsoletas"]}')
    L.append('\n## Distribución de familias (nº de templates)\n')
    L.append('| familia | templates |')
    L.append('|---|---:|')
    for fam, n in report['distribucion']:
        L.append(f'| {fam} | {n} |')
    if report['sin_familia_ejemplos']:
        L.append('\n## Templates sin ninguna familia (solo valores no-color) — muestra\n')
        L.append('| template_id | valores de color |')
        L.append('|---:|---|')
        for tid, vals in report['sin_familia_ejemplos']:
            L.append(f'| {tid} | {vals} |')
    with open(md_path, 'w', encoding='utf-8') as f:
        f.write('\n'.join(L) + '\n')
    return json_path, md_path


# ─── Self-check (offline) ────────────────────────────────────────────────────

def run_self_check(engine: ColorEngine) -> int:
    csv_path = _newest_color_values_csv()
    if not csv_path or not csv_path.exists():
        print('✗ No hay reports/color_values_*.csv para el self-check', file=sys.stderr)
        return 1
    print(f'Self-check OFFLINE sobre {csv_path} (no toca Odoo)\n')

    tot = con = 0
    dist: dict[str, int] = defaultdict(int)
    sin: list[str] = []
    with open(csv_path, encoding='utf-8') as f:
        for row in csv.DictReader(f):
            p = int(row.get('products') or 0)
            tot += p
            fam = engine.familia(row['name'])
            if fam:
                con += p
                dist[fam] += p
            else:
                sin.append(row['name'])

    cob = (con / tot * 100) if tot else 0.0
    print(f'  COBERTURA prod-hits: {cob:.2f}%  ({con}/{tot})')
    print(f'  Sin familia        : {len(sin)} valores')
    print('\n  Distribución por familia (prod-hits):')
    for fam, n in sorted(dist.items(), key=lambda x: -x[1]):
        print(f'    {fam:<12}{n}')
    print('\n  Sin familia:', ', '.join(sin))
    return 0


# ─── Main ────────────────────────────────────────────────────────────────────

def main() -> int:
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass

    parser = argparse.ArgumentParser(description="Deriva el atributo no_variant 'Color (familia)'")
    parser.add_argument('--apply', action='store_true', help='Crea atributo/valores y escribe líneas. Sin esto, dry-run.')
    parser.add_argument('--limit', type=int, default=0, help='Acota nº de templates (0 = todos)')
    parser.add_argument('--published-only', action='store_true', help='Solo templates publicados')
    parser.add_argument('--since', help='YYYY-MM-DD o ISO8601: solo templates con write_date >= since')
    parser.add_argument('--self-check', action='store_true', help='familia() OFFLINE sobre el CSV dump; no toca Odoo')
    parser.add_argument('--output', '-o', help='Prefijo de salida del reporte (sin extensión)')
    args = parser.parse_args()

    engine = ColorEngine()

    if args.self_check:
        return run_self_check(engine)

    if args.since:
        try:
            datetime.fromisoformat(args.since)
        except ValueError:
            print(f'✗ --since inválido: {args.since!r} (usa YYYY-MM-DD o ISO8601)', file=sys.stderr)
            return 1

    load_dotenv()
    odoo_url = os.environ.get('ODOO_URL')
    api_key = os.environ.get('ODOO_API_KEY')
    database = os.environ.get('ODOO_DATABASE')
    if not odoo_url or not api_key:
        print('✗ Falta ODOO_URL o ODOO_API_KEY en variables de entorno', file=sys.stderr)
        return 1

    today = datetime.now().strftime('%Y%m%d')
    Path('reports').mkdir(exist_ok=True)
    stem = Path(args.output) if args.output else Path(f'reports/derive_familia_{today}')

    mode = 'APPLY' if args.apply else 'DRY-RUN'
    print(f'Derivación Color (familia)  [{mode}]')
    print(f'Odoo: {odoo_url}')

    client = OdooClient(odoo_url, api_key, database)
    familias = load_familias()

    # 1. Atributo Color REAL (solo lectura) y atributo familia (get_or_create)
    color_attr = resolve_color_attribute(client)
    color_attr_id = color_attr['id']
    familia_attr_id, val_map, would_create = ensure_familia_attribute(client, familias, args.apply)

    # 2. Estado de Color por template + nombres
    tmpl_color_vals, vid_name = read_color_state(
        client, color_attr_id, args.since, args.published_only)
    tids = sorted(tmpl_color_vals)
    if args.limit:
        tids = tids[:args.limit]
    print(f'→ {len(tids)} templates con línea de Color'
          + (f' (filtrados: since={args.since!r} published_only={args.published_only})'
             if (args.since or args.published_only) else ''))

    # 3. Familia deseada por template
    desired: dict[int, set[str]] = {}
    dist_tmpl: dict[str, int] = defaultdict(int)
    sin_fam_tids: list[int] = []
    for tid in tids:
        fams = set()
        for vid in tmpl_color_vals[tid]:
            f = engine.familia(vid_name.get(vid, ''))
            if f:
                fams.add(f)
        desired[tid] = fams
        if fams:
            for f in fams:
                dist_tmpl[f] += 1
        else:
            sin_fam_tids.append(tid)

    con_familia = len(tids) - len(sin_fam_tids)

    # 4. Diff contra las líneas familia existentes (si el atributo ya existe)
    fam_lines = read_familia_lines(client, familia_attr_id) if familia_attr_id else {}
    pending_create: dict[frozenset, list[int]] = defaultdict(list)
    pending_update: list[tuple[int, int, list[int]]] = []
    obsoletas: list[int] = []
    sin_cambio = 0
    unmapped = 0

    if familia_attr_id is None:
        # dry-run sin atributo aún: proyección pura (todo template con familia se escribiría)
        would_write = con_familia
    else:
        for tid in tids:
            fams = desired[tid]
            existing = fam_lines.get(tid)
            if not fams:
                if existing and existing[1]:
                    obsoletas.append(tid)
                continue
            if not all(f in val_map for f in fams):
                unmapped += 1
                continue
            fam_ids = frozenset(val_map[f] for f in fams)
            if existing is None:
                pending_create[fam_ids].append(tid)
            elif existing[1] != set(fam_ids):
                pending_update.append((tid, existing[0], sorted(fam_ids)))
            else:
                sin_cambio += 1
        would_write = sum(len(v) for v in pending_create.values()) + len(pending_update)

    # 5. Escritura (solo --apply)
    escritos = creados = actualizados = 0
    errores = 0
    if args.apply and familia_attr_id is not None:
        for fam_ids, tid_list in pending_create.items():
            cmd = (0, 0, {'attribute_id': familia_attr_id,
                          'value_ids': [(6, 0, sorted(fam_ids))]})
            try:
                _write_familia_line(client, tid_list, cmd, familia_attr_id)
                escritos += len(tid_list)
                creados += len(tid_list)
            except Exception as exc:
                errores += len(tid_list)
                print(f'  ✗ crear familia en {len(tid_list)} templates: {exc}')
        for tid, line_id, fam_ids in pending_update:
            cmd = (1, line_id, {'value_ids': [(6, 0, fam_ids)]})
            try:
                _write_familia_line(client, [tid], cmd, familia_attr_id)
                escritos += 1
                actualizados += 1
            except Exception as exc:
                errores += 1
                print(f'  ✗ actualizar familia template {tid}: {exc}')

    # 6. Reporte
    report = {
        'generated': datetime.now().isoformat(timespec='seconds'),
        'mode': mode,
        'familia_attr_id': familia_attr_id,
        'would_create_attr': would_create,
        'templates': len(tids),
        'con_familia': con_familia,
        'sin_familia': len(sin_fam_tids),
        'distribucion': sorted(dist_tmpl.items(), key=lambda x: -x[1]),
        'escritos': escritos,
        'creados': creados,
        'actualizados': actualizados,
        'sin_cambio': sin_cambio,
        'unmapped': unmapped,
        'obsoletas': len(obsoletas),
        'sin_familia_ejemplos': [
            (tid, ', '.join(sorted(vid_name.get(v, '') for v in tmpl_color_vals[tid])))
            for tid in sin_fam_tids[:25]
        ],
    }
    json_path, md_path = write_report_files(report, stem)

    # 7. Resumen
    print(f'\n=== Resumen [{mode}] ===')
    if would_create:
        print(f"  Atributo '{FAMILIA_ATTR_NAME}': NO existe todavía "
              f"({'se crearía con --apply' if not args.apply else 'creado'})")
    print(f'  Templates procesados : {len(tids)}')
    print(f'  Con ≥1 familia       : {con_familia} · Sin ninguna familia: {len(sin_fam_tids)}')
    print('  Distribución (templates):', {k: v for k, v in report['distribucion']})
    if args.apply and familia_attr_id is not None:
        print(f'  Escritos: {escritos} (crea {creados} / actualiza {actualizados}) | '
              f'Sin cambio: {sin_cambio} | Errores: {errores}')
    else:
        print(f'  Se escribirían: {would_write} templates (NADA se escribió)')
    if unmapped:
        print(f'  ⚠ {unmapped} templates sin mapear (valores familia faltantes; corre --apply)')
    if obsoletas:
        print(f'  ⚠ {len(obsoletas)} líneas familia obsoletas para revisión')
    print(f'  Reporte: {json_path}  ·  {md_path}')
    return 1 if errores else 0


if __name__ == '__main__':
    sys.exit(main())
