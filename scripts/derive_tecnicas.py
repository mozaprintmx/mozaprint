#!/usr/bin/env python3
"""
Derivación de técnica canónica desde x_tecnica_impresion (texto libre) hacia
los campos estructurados x_tecnica_default_id y x_tecnicas_compatibles_ids.

FUENTE (read-only): product.template.x_tecnica_impresion (char, lo pisa el sync
de proveedores; este script NO lo escribe).
DESTINO: x_tecnica_default_id (m2o) y x_tecnicas_compatibles_ids (m2m), ambos a
x_tecnica_personalizacion.

El match raw→canónica usa la columna x_aliases del modelo de técnicas (variantes
crudas del proveedor separadas por " | ").

DRY-RUN por defecto. Con --apply escribe en Odoo. Idempotente: el m2m se escribe
con reemplazo [(6,0,[ids])] y solo se escribe cuando el valor calculado difiere
del actual, así que re-correr no acumula ni reescribe.

Uso:
    python derive_tecnicas.py                 # dry-run (no escribe)
    python derive_tecnicas.py --apply         # ejecuta (con mini-test previo)
    python derive_tecnicas.py --limit 100     # acota para pruebas

Variables de entorno (desde .env):
    ODOO_URL, ODOO_API_KEY, ODOO_DATABASE (opcional)
"""

import argparse
import csv
import os
import re
import sys
import unicodedata
from datetime import datetime
from pathlib import Path
from typing import Any, NamedTuple

from dotenv import load_dotenv

from odoo_client import OdooClient

TECNICA_MODEL = 'x_tecnica_personalizacion'
TEMPLATE_MODEL = 'product.template'

# Valores crudos que se consideran "sin técnica" (normalizados).
NULL_VALUES = {'', 'n/a', 'na', 's/metodo', 's/método', 'sin metodo', 'ninguna'}

# Separadores de combo: - / , +  y la conjunción " y ".
_SEGMENT_SPLIT = re.compile(r'\s+y\s+|[\-/,+]')
_PARENTHETICAL = re.compile(r'\([^)]*\)')

# Palabras de producto → indican nota multi-componente (kit). Normalizadas.
PRODUCT_WORDS = {
    'boligrafo', 'pluma', 'libreta', 'cuaderno', 'agenda', 'llavero',
    'power bank', 'powerbank', 'vaso', 'taza', 'termo', 'mochila', 'bolsa',
    'gorra', 'playera', 'usb', 'memoria', 'paraguas', 'sombrilla', 'mug',
    'botella', 'cilindro', 'maleta', 'cartera', 'mouse', 'audifonos',
}


# ─── Normalización ───────────────────────────────────────────────────────────

def normalize(text: str) -> str:
    """minúsculas + sin acentos + trim + espacios colapsados."""
    if not text:
        return ''
    nfkd = unicodedata.normalize('NFKD', text)
    sin_acentos = ''.join(c for c in nfkd if not unicodedata.combining(c))
    return re.sub(r'\s+', ' ', sin_acentos.lower()).strip()


# ─── Lookup de técnicas ──────────────────────────────────────────────────────

class Tecnica(NamedTuple):
    id: int
    code: str
    name: str


def build_lookup(
    tecnicas: list[dict],
) -> tuple[dict[str, Tecnica], list[tuple[str, Tecnica]]]:
    """
    Construye:
      - exact: dict alias_normalizada -> Tecnica (match exacto)
      - by_len: lista [(alias_normalizada, Tecnica)] ordenada por longitud DESC
                (para el match por substring más largo)
    """
    exact: dict[str, Tecnica] = {}
    aliases: list[tuple[str, Tecnica]] = []

    for t in tecnicas:
        tec = Tecnica(id=t['id'], code=t.get('x_code') or '', name=t.get('x_name') or '')
        raw_aliases = t.get('x_aliases') or ''
        for alias in raw_aliases.split('|'):
            alias_norm = normalize(alias)
            if not alias_norm:
                continue
            aliases.append((alias_norm, tec))
            # El primero gana en exacto; aliases idénticas entre técnicas son improbables.
            exact.setdefault(alias_norm, tec)

    by_len = sorted(aliases, key=lambda x: len(x[0]), reverse=True)
    return exact, by_len


# ─── Derivación por producto ─────────────────────────────────────────────────

class Derivacion(NamedTuple):
    default: Tecnica | None
    compatibles: list[Tecnica]
    status: str          # FULL | PARTIAL | NONE | NULL
    revisar: str         # '' o motivo: multicomponente / partial / none


def _clean_segment(seg: str) -> str:
    """Quita parentéticos y puntuación final, normaliza."""
    seg = _PARENTHETICAL.sub(' ', seg)
    seg = normalize(seg)
    return seg.strip(' .;:·-')


def _match_segment(
    seg: str,
    exact: dict[str, Tecnica],
    by_len: list[tuple[str, Tecnica]],
) -> Tecnica | None:
    """Match de un segmento: exacto primero, luego substring más largo."""
    if not seg:
        return None
    if seg in exact:
        return exact[seg]
    # Substring más largo contenido en el segmento (by_len ya está ordenado desc).
    for alias_norm, tec in by_len:
        if alias_norm in seg:
            return tec
    return None


def derive(
    raw: str,
    exact: dict[str, Tecnica],
    by_len: list[tuple[str, Tecnica]],
) -> Derivacion:
    """Deriva técnicas de un valor crudo de x_tecnica_impresion."""
    if normalize(raw) in NULL_VALUES:
        return Derivacion(None, [], 'NULL', '')

    segmentos = [_clean_segment(s) for s in _SEGMENT_SPLIT.split(raw)]
    segmentos = [s for s in segmentos if s]
    if not segmentos:
        return Derivacion(None, [], 'NULL', '')

    matched: list[Tecnica] = []
    sin_match = 0
    for seg in segmentos:
        tec = _match_segment(seg, exact, by_len)
        if tec:
            matched.append(tec)
        else:
            sin_match += 1

    # Dedup preservando orden del crudo.
    vistos: set[int] = set()
    compatibles: list[Tecnica] = []
    for tec in matched:
        if tec.id not in vistos:
            vistos.add(tec.id)
            compatibles.append(tec)

    # Multi-componente: alguna palabra de producto en el crudo normalizado.
    # Con límite de palabra (\b) para no confundir 'termo' dentro de 'termograbado'.
    raw_norm = normalize(raw)
    es_multi = any(
        re.search(rf'\b{re.escape(pw)}\b', raw_norm) for pw in PRODUCT_WORDS
    )

    if not compatibles:
        status = 'NONE'
    elif sin_match == 0:
        status = 'FULL'
    else:
        status = 'PARTIAL'

    motivos = []
    if es_multi:
        motivos.append('multicomponente')
    if status == 'PARTIAL':
        motivos.append('partial')
    elif status == 'NONE':
        motivos.append('none')

    default = compatibles[0] if compatibles else None
    return Derivacion(default, compatibles, status, '+'.join(motivos))


# ─── Idempotencia ────────────────────────────────────────────────────────────

def _current_default_id(tmpl: dict) -> int | None:
    val = tmpl.get('x_tecnica_default_id')
    if isinstance(val, (list, tuple)) and val:
        return val[0]
    return val or None


def _needs_write(tmpl: dict, d: Derivacion) -> bool:
    """True si los valores destino actuales difieren de los derivados."""
    new_default = d.default.id if d.default else None
    if _current_default_id(tmpl) != new_default:
        return True
    actuales = set(tmpl.get('x_tecnicas_compatibles_ids') or [])
    nuevos = {t.id for t in d.compatibles}
    return actuales != nuevos


# ─── Main ────────────────────────────────────────────────────────────────────

def _smoke_test_m2m(client: OdooClient, tecnicas: list[dict]) -> None:
    """
    Mini-test del contrato de escritura m2m vía JSON-2 antes del lote.
    Escribe default+compatibles en 1 template, verifica, y RESTAURA el valor
    original. Aborta si el contrato no se comporta como se espera.
    """
    print('→ Mini-test de escritura m2m (1 template, auto-restaurado)...')
    sample = client.search_read(
        TEMPLATE_MODEL,
        domain=[('x_tecnica_impresion', '!=', False)],
        fields=['id', 'x_tecnica_default_id', 'x_tecnicas_compatibles_ids'],
        limit=1,
    )
    if not sample:
        print('  ⚠ Sin templates para el mini-test; se omite.')
        return
    t = sample[0]
    tid = t['id']
    orig_default = _current_default_id(t)
    orig_compat = list(t.get('x_tecnicas_compatibles_ids') or [])
    test_tec = tecnicas[0]['id']

    try:
        client.write(TEMPLATE_MODEL, [tid], {
            'x_tecnica_default_id': test_tec,
            'x_tecnicas_compatibles_ids': [(6, 0, [test_tec])],
        })
        check = client.search_read(
            TEMPLATE_MODEL, domain=[('id', '=', tid)],
            fields=['x_tecnica_default_id', 'x_tecnicas_compatibles_ids'],
        )[0]
        ok = (_current_default_id(check) == test_tec
              and set(check.get('x_tecnicas_compatibles_ids') or []) == {test_tec})
        if not ok:
            raise RuntimeError(f'el write m2m no reflejó el valor esperado: {check}')
        print('  ✓ Contrato m2m OK.')
    finally:
        # Restaurar SIEMPRE el valor original.
        client.write(TEMPLATE_MODEL, [tid], {
            'x_tecnica_default_id': orig_default or False,
            'x_tecnicas_compatibles_ids': [(6, 0, orig_compat)],
        })
        print(f'  ↩ Template {tid} restaurado a su valor original.')


def main() -> int:
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass

    load_dotenv()

    parser = argparse.ArgumentParser(description='Deriva técnica canónica desde x_tecnica_impresion')
    parser.add_argument('--apply', action='store_true', help='Escribe en Odoo. Sin esto, dry-run.')
    parser.add_argument('--output', '-o', help='Ruta del CSV de salida')
    parser.add_argument('--limit', type=int, default=0, help='Acota nº de templates (0 = todos)')
    args = parser.parse_args()

    odoo_url = os.environ.get('ODOO_URL')
    api_key = os.environ.get('ODOO_API_KEY')
    database = os.environ.get('ODOO_DATABASE')
    if not odoo_url or not api_key:
        print('✗ Falta ODOO_URL o ODOO_API_KEY en variables de entorno', file=sys.stderr)
        return 1

    today = datetime.now().strftime('%Y%m%d')
    Path('reports').mkdir(exist_ok=True)
    out_path = Path(args.output) if args.output else Path(f'reports/tecnica_derivacion_{today}.csv')

    mode = 'APPLY' if args.apply else 'DRY-RUN'
    print(f'Derivación de técnica  [{mode}]')
    print(f'Odoo: {odoo_url}')

    client = OdooClient(odoo_url, api_key, database)

    # 1. Lookup de técnicas
    tecnicas = client.search_read_all(
        TECNICA_MODEL, fields=['id', 'x_code', 'x_name', 'x_aliases'],
    )
    if not tecnicas:
        print('✗ No hay registros en x_tecnica_personalizacion', file=sys.stderr)
        return 1
    exact, by_len = build_lookup(tecnicas)
    print(f'→ {len(tecnicas)} técnicas, {len(by_len)} aliases en el lookup.')

    # 1b. Mini-test del contrato m2m antes de escribir en lote
    if args.apply:
        _smoke_test_m2m(client, tecnicas)

    # 2. Templates con x_tecnica_impresion
    templates = client.search_read_all(
        TEMPLATE_MODEL,
        domain=[('x_tecnica_impresion', '!=', False)],
        fields=['id', 'name', 'x_tecnica_impresion',
                'x_tecnica_default_id', 'x_tecnicas_compatibles_ids'],
    )
    if args.limit:
        templates = templates[:args.limit]
    print(f'→ {len(templates)} templates con x_tecnica_impresion.')

    counts = {'FULL': 0, 'PARTIAL': 0, 'NONE': 0, 'NULL': 0}
    revisar_count = 0
    escritos = 0
    sin_cambio = 0
    errores = 0
    filas: list[dict] = []

    for t in templates:
        try:
            raw = t.get('x_tecnica_impresion') or ''
            d = derive(raw, exact, by_len)
            counts[d.status] += 1
            if d.revisar:
                revisar_count += 1

            if args.apply and d.compatibles and _needs_write(t, d):
                try:
                    client.write(TEMPLATE_MODEL, [t['id']], {
                        'x_tecnica_default_id': d.default.id,
                        'x_tecnicas_compatibles_ids': [(6, 0, [x.id for x in d.compatibles])],
                    })
                    escritos += 1
                except Exception as exc:
                    errores += 1
                    print(f'  ✗ write template {t["id"]} ({t.get("name","")[:40]}): {exc}')
            elif args.apply:
                sin_cambio += 1

            filas.append({
                'template_id': t['id'],
                'name': t.get('name', ''),
                'raw_tecnica': raw,
                'default_code': d.default.code if d.default else '',
                'compatibles_codes': '|'.join(x.code for x in d.compatibles),
                'status': d.status,
                'revisar': d.revisar,
            })
        except Exception as exc:
            errores += 1
            print(f'  ✗ template {t.get("id")} ({t.get("name","")[:40]}): {exc}')

    # 3. CSV
    with open(out_path, 'w', encoding='utf-8', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=[
            'template_id', 'name', 'raw_tecnica', 'default_code',
            'compatibles_codes', 'status', 'revisar',
        ])
        writer.writeheader()
        writer.writerows(filas)

    # 4. Resumen
    print(f'\n=== Resumen [{mode}] ===')
    print(f'  Total procesados : {len(templates)}')
    for st in ('FULL', 'PARTIAL', 'NONE', 'NULL'):
        print(f'  {st:<8}: {counts[st]}')
    print(f'  Marcados para revisión (PARTIAL+NONE+multicomponente): {revisar_count}')
    if args.apply:
        print(f'  Escritos: {escritos} | Sin cambio: {sin_cambio} | Errores: {errores}')
    else:
        escribibles = sum(1 for fila in filas if fila['default_code'])
        print(f'  (dry-run: se escribirían {escribibles} con match; NADA se escribió)')
    print(f'  CSV: {out_path}')
    return 1 if errores else 0


if __name__ == '__main__':
    sys.exit(main())
