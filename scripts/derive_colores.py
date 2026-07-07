#!/usr/bin/env python3
"""
Derivación de swatches (html_color) para el atributo "Color" de Odoo Online 19.0.

El sync de proveedores crea los product.attribute.value del atributo Color por
string exacto y SIN html_color (ver analysis/supplier-sync/AUDITORIA_COLORES.md),
así que el swatch es 100% derivado. Este script puebla html_color a partir de un
motor de reglas base+modificador, con un seed curado de colores lexicalizados.

FUENTE (read-only): data/colores_seed.csv, data/colores_modifiers.csv y las
constantes STRIP_TOKENS / NON_COLOR / MATERIAL_APROX (fuente: data/colores_noncolor.md).
DESTINO (write, solo --apply): product.attribute.value.html_color — NADA MÁS.

Espejo arquitectónico de scripts/derive_tecnicas.py: normalize() idéntica, DRY-RUN
por defecto, escritura agrupada e idempotente, reporte JSON+MD.

MOTOR resolve(name) -> (hex|None, tipo, fuente, detalle). Cascada (primer match gana):
    1. LEX          match exacto normalizado contra seed clase=lex (hex curado).
    2. BICOLOR      el crudo tiene '/' o token 'con' -> especial (patrón, sin hex).
    3. NON_COLOR    normalizado en NON_COLOR -> flag (contaminación, sin hex).
    4. MATERIAL     normalizado en MATERIAL_APROX -> hex aproximado.
    5. STRIP        quita tokens de talla/género; re-matchea el remanente
                    (lex / material / base+modificador).
    6. BASE+MOD     1 color base (seed clase=base) + 0..n modificadores; deltas HLS
                    en cadena vía colorsys (stdlib). fuerza_tipo sobrescribe el tipo.
    7. sin_base     -> flag.

Los "sin html_color" caen en dos cubetas:
    - especial : intencional (transparente/multicolor/bicolor/patrón). NO es error.
    - flag     : contaminación (no-color, talla/basura, token desconocido). Inventario.

Uso:
    python derive_colores.py                 # dry-run (imprime name->hex, tipo, fuente)
    python derive_colores.py --apply         # escribe html_color en Odoo
    python derive_colores.py --limit 50      # acota para pruebas
    python derive_colores.py --report-only   # solo genera el reporte (sin verbose)
    python derive_colores.py --self-check    # corre el motor OFFLINE sobre el CSV dump

Variables de entorno (desde .env; no aplican a --self-check):
    ODOO_URL, ODOO_API_KEY, ODOO_DATABASE (opcional)

────────────────────────────────────────────────────────────────────────────────
HOOK POST-SYNC (documentación; este script NO modifica el sync)
────────────────────────────────────────────────────────────────────────────────
Igual que derive_tecnicas, auto_sync debe invocar este script como subproceso tras
una corrida EXITOSA, con barrido completo (son ~204 valores; NO usa --since). El
subproceso NO debe heredar las credenciales de Odoo del proceso padre: se le pasa un
entorno limpio con solo las vars que necesita.

Config en .env (análoga a la de técnicas):
    DERIVE_COLORES_ENABLED=true
    DERIVE_COLORES_SCRIPT_PATH=D:/MozaPrint/Odoo/Proyectos/mozaprint/scripts/derive_colores.py
    DERIVE_COLORES_PYTHON_PATH=C:/Users/.../Python312/python.exe

Snippet para copiar a analysis/supplier-sync/ (env limpio, sin heredar Odoo):

    import os, subprocess, sys
    if os.environ.get("DERIVE_COLORES_ENABLED", "").lower() in ("1", "true", "yes"):
        script = os.environ["DERIVE_COLORES_SCRIPT_PATH"]
        python = os.environ.get("DERIVE_COLORES_PYTHON_PATH", sys.executable)
        # Entorno mínimo: solo lo que derive_colores necesita, NADA de credenciales
        # heredadas del sync. Las de Odoo salen del .env del repo mozaprint (load_dotenv).
        child_env = {
            "PATH": os.environ.get("PATH", ""),
            "SYSTEMROOT": os.environ.get("SYSTEMROOT", ""),  # requerido en Windows
        }
        subprocess.run(
            [python, script, "--apply"],
            cwd=os.path.dirname(os.path.dirname(script)),  # raíz del repo (para .env y reports/)
            env=child_env,
            check=False,
        )
"""

import argparse
import colorsys
import csv
import glob
import json
import os
import re
import sys
import unicodedata
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import NamedTuple

from dotenv import load_dotenv

from odoo_client import OdooClient

ATTR_MODEL = 'product.attribute'
VALUE_MODEL = 'product.attribute.value'
LINE_MODEL = 'product.template.attribute.line'

# Modelos sobre los que este script tiene PROHIBIDO escribir (guarda dura).
FORBIDDEN_WRITE_MODELS = {'product.product', LINE_MODEL, ATTR_MODEL}

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_ROOT / 'data'
SEED_CSV = DATA_DIR / 'colores_seed.csv'
MODIFIERS_CSV = DATA_DIR / 'colores_modifiers.csv'


# ─── Constantes de reglas (fuente: data/colores_noncolor.md) ─────────────────

# Sufijos de talla/género que el proveedor mezcló en el eje Color. Se remueven
# antes de matchear el color base (ej. NEGRO-SMALL -> negro, PLATA DAMA -> plata).
STRIP_TOKENS = {
    'small', 'medium', 'large', 'xl', 'xs', 'xxl', 'xxxl', 's', 'm', 'l', 'extra',
    'dama', 'caballero', 'unisex',
}

# Valores que NO son color: no reciben html_color y se reportan como contaminación.
NON_COLOR = {
    # Talla pura
    'small', 'medium', 'large', 'xl', 'xs', 'xxl', 'extra large', 'extra small', '7x4cm',
    # Basura / no-color
    'unico', 'volteador', 'pelota', 'cucharon', 'cuchara', 'arnes', 'arbol', 'copo',
    'proyecto especial', 'pride',
    # Material sin color claro
    'rpet', 'pasta', 'marmol', 'mezclilla',
    # Patrón / bicolor (los de '/' o 'con' se atrapan antes, en BICOLOR)
    'tricolor', 'mexico', 'arcoiris', 'blanco con negro',
    'negro/plata', 'negro/gris', 'negro/cafe', 'blanco/negro',
    # Efecto no representable con hex plano
    'tornasol', 'jaspeado',
}

# Materiales con color natural razonable -> hex aproximado (tipo=flat).
MATERIAL_APROX = {
    'carton': '#C8A97E',
    'corcho': '#C6A664',
    'madera': '#A0522D',
    'bambu': '#E3C888',
    'coco': '#8B5A2B',
    'caoba': '#6A342A',
    'cebada': '#D8C89A',
    'cana': '#DAB86A',
    'periodico': '#D9D2C5',
}


# ─── Normalización (idéntica a derive_tecnicas) ──────────────────────────────

def normalize(text: str) -> str:
    """minúsculas + sin acentos + trim + espacios colapsados."""
    if not text:
        return ''
    nfkd = unicodedata.normalize('NFKD', text)
    sin_acentos = ''.join(c for c in nfkd if not unicodedata.combining(c))
    return re.sub(r'\s+', ' ', sin_acentos.lower()).strip()


def _tokenize(norm: str) -> list[str]:
    """Parte en tokens por '-' o espacio (separadores del eje Color contaminado)."""
    return [t for t in re.split(r'[\s\-]+', norm) if t]


# ─── Carga del seed y los modificadores ──────────────────────────────────────

class SeedColor(NamedTuple):
    nombre: str
    hex: str      # '' para especial (transparente/multicolor/bicolor)
    tipo: str     # flat | metalico | especial
    clase: str    # base | lex


class Modifier(NamedTuple):
    nombre: str
    delta_l: float
    delta_s: float
    fuerza_tipo: str  # '' o el tipo forzado (metalico/especial)


def _read_csv_skip_comments(path: Path) -> list[dict]:
    """Lee un CSV ignorando líneas que empiezan con '#' (tras strip)."""
    with open(path, encoding='utf-8') as f:
        lines = [ln for ln in f if not ln.lstrip().startswith('#')]
    return list(csv.DictReader(lines))


def load_seed() -> tuple[dict[str, SeedColor], dict[str, SeedColor]]:
    """
    Devuelve (LEX_EXACT, BASE_BY_TOKEN):
      - LEX_EXACT: alias_normalizada (multi-palabra) -> SeedColor clase=lex
      - BASE_BY_TOKEN: token_normalizado -> SeedColor clase=base
    """
    lex_exact: dict[str, SeedColor] = {}
    base_by_token: dict[str, SeedColor] = {}
    for row in _read_csv_skip_comments(SEED_CSV):
        sc = SeedColor(
            nombre=row['nombre'].strip(),
            hex=(row['hex'] or '').strip().upper(),
            tipo=row['tipo'].strip(),
            clase=row['clase'].strip(),
        )
        for alias in (row['aliases'] or '').split('|'):
            alias_norm = normalize(alias)
            if not alias_norm:
                continue
            if sc.clase == 'lex':
                lex_exact.setdefault(alias_norm, sc)
            elif sc.clase == 'base':
                # Los alias base son de una sola palabra; si alguno fuera multi-palabra
                # se indexa por su primer token (no ocurre con el seed actual).
                base_by_token.setdefault(alias_norm.split()[0], sc)
    return lex_exact, base_by_token


def load_modifiers() -> dict[str, Modifier]:
    """token_normalizado -> Modifier."""
    mods: dict[str, Modifier] = {}
    for row in _read_csv_skip_comments(MODIFIERS_CSV):
        m = Modifier(
            nombre=row['modificador'].strip(),
            delta_l=float(row['delta_l']),
            delta_s=float(row['delta_s']),
            fuerza_tipo=(row['fuerza_tipo'] or '').strip(),
        )
        for alias in (row['aliases'] or '').split('|'):
            alias_norm = normalize(alias)
            if alias_norm:
                mods.setdefault(alias_norm, m)
    return mods


# ─── Transformada de color ───────────────────────────────────────────────────

def _clamp(x: float) -> float:
    return max(0.0, min(1.0, x))


def apply_hls(hex_str: str, delta_l: float, delta_s: float) -> str:
    """Aplica deltas de luminosidad/saturación en espacio HLS. Devuelve #RRGGBB."""
    r = int(hex_str[1:3], 16) / 255.0
    g = int(hex_str[3:5], 16) / 255.0
    b = int(hex_str[5:7], 16) / 255.0
    h, l, s = colorsys.rgb_to_hls(r, g, b)
    l = _clamp(l + delta_l)
    s = _clamp(s + delta_s)
    r, g, b = colorsys.hls_to_rgb(h, l, s)
    return '#{:02X}{:02X}{:02X}'.format(round(r * 255), round(g * 255), round(b * 255))


# ─── Motor de resolución ─────────────────────────────────────────────────────

class Resolucion(NamedTuple):
    hex: str | None      # None = no se escribe html_color
    tipo: str            # flat | metalico | especial | flag
    fuente: str          # lex | material | base | base+mod | especial | bicolor
                         # | non_color | base+desconocido | sin_base | multibase
    detalle: str         # base+modificadores usados, o motivo del flag


class ColorEngine:
    """Motor de derivación de swatches. Sin estado de Odoo (testeable offline)."""

    def __init__(self) -> None:
        self.lex_exact, self.base_by_token = load_seed()
        self.mods = load_modifiers()

    # -- resolución de un remanente ya tokenizado (usado por STRIP y BASE+MOD) --
    def _base_mod(self, tokens: list[str], via_strip: bool) -> Resolucion:
        bases: list[SeedColor] = []
        applied: list[tuple[str, Modifier]] = []
        unknown: list[str] = []
        for t in tokens:
            if t in self.base_by_token:
                bases.append(self.base_by_token[t])
            elif t in self.mods:
                applied.append((t, self.mods[t]))
            else:
                unknown.append(t)

        if unknown:
            return Resolucion(None, 'flag', 'base+desconocido', unknown[0])
        if not bases:
            return Resolucion(None, 'flag', 'sin_base', ' '.join(tokens))
        if len(bases) > 1:
            return Resolucion(None, 'flag', 'multibase',
                              ','.join(b.nombre for b in bases))

        base = bases[0]
        suf = '+strip' if via_strip else ''
        if base.tipo == 'especial':
            # transparente / multicolor / bicolor: sin hex plano.
            return Resolucion(None, 'especial', 'base' + suf, base.nombre)

        hex_val = base.hex
        tipo = base.tipo
        for _name, m in applied:
            hex_val = apply_hls(hex_val, m.delta_l, m.delta_s)
            if m.fuerza_tipo:
                tipo = m.fuerza_tipo
        fuente = ('base+mod' if applied else 'base') + suf
        detalle = base.nombre + (('+' + '+'.join(n for n, _ in applied)) if applied else '')
        return Resolucion(hex_val, tipo, fuente, detalle)

    def resolve(self, name: str) -> Resolucion:
        raw = name or ''
        norm = normalize(raw)
        if not norm:
            return Resolucion(None, 'flag', 'sin_base', 'vacio')

        # 1. LEX exacto
        if norm in self.lex_exact:
            sc = self.lex_exact[norm]
            if sc.tipo == 'especial':
                return Resolucion(None, 'especial', 'lex', sc.nombre)
            return Resolucion(sc.hex, sc.tipo, 'lex', sc.nombre)

        # 2. BICOLOR (patrón de dos tonos)
        if '/' in raw or 'con' in norm.split():
            return Resolucion(None, 'especial', 'bicolor', raw.strip())

        # 3. NON_COLOR (contaminación)
        if norm in NON_COLOR:
            return Resolucion(None, 'flag', 'non_color', norm)

        # 4. MATERIAL_APROX
        if norm in MATERIAL_APROX:
            return Resolucion(MATERIAL_APROX[norm], 'flat', 'material', norm)

        # 5. STRIP talla/género y re-match del remanente
        tokens = _tokenize(norm)
        core = [t for t in tokens if t not in STRIP_TOKENS]
        via_strip = len(core) != len(tokens)
        if via_strip:
            core_norm = ' '.join(core)
            if not core_norm:
                return Resolucion(None, 'flag', 'sin_base', 'solo talla/genero')
            if core_norm in self.lex_exact:
                sc = self.lex_exact[core_norm]
                if sc.tipo == 'especial':
                    return Resolucion(None, 'especial', 'lex+strip', sc.nombre)
                return Resolucion(sc.hex, sc.tipo, 'lex+strip', sc.nombre)
            if core_norm in MATERIAL_APROX:
                return Resolucion(MATERIAL_APROX[core_norm], 'flat', 'material+strip', core_norm)

        # 6. BASE + MODIFICADOR (sobre el remanente ya sin talla/género)
        return self._base_mod(core, via_strip)


# ─── Buckets de reporte ──────────────────────────────────────────────────────

def fuente_bucket(fuente: str) -> str:
    """Colapsa la fuente detallada a la cubeta de reporte."""
    base = fuente.replace('+strip', '')
    if base == 'lex':
        return 'lex'
    if base == 'material':
        return 'material'
    if base == 'base+mod':
        return 'regla'          # base + modificador (transformada HLS)
    if base == 'base':
        return 'base'
    if base in ('especial', 'bicolor'):
        return 'especial'
    return 'flag'               # non_color / base+desconocido / sin_base / multibase


# ─── Escritura guardada ──────────────────────────────────────────────────────

def _write_html_color(client: OdooClient, value_ids: list[int], hex_val: str) -> None:
    """
    Único punto de escritura del script. Guardas duras:
      - solo product.attribute.value (nunca product.product / .attribute.line / .attribute)
      - solo el campo html_color (ninguna otra clave, jamás create_variant ni variantes)
    """
    if VALUE_MODEL in FORBIDDEN_WRITE_MODELS:  # defensa de constante
        raise RuntimeError('VALUE_MODEL no puede estar en FORBIDDEN_WRITE_MODELS')
    vals = {'html_color': hex_val}
    if set(vals) != {'html_color'}:
        raise RuntimeError(f'Escritura no permitida: vals={list(vals)}')
    client.write(VALUE_MODEL, value_ids, vals)


# ─── Resolución del atributo Color (idéntica a dump_color_values) ────────────

def resolve_color_attribute(client: OdooClient) -> dict:
    cands = client.search_read(
        ATTR_MODEL, [('name', '=', 'Color')],
        fields=['id', 'name', 'create_variant'],
        context={'active_test': False},
    )
    if not cands:
        raise SystemExit("✗ No existe ningún product.attribute con name='Color'")
    for c in cands:
        vals = client.search_read(
            VALUE_MODEL, [('attribute_id', '=', c['id'])], fields=['id'],
            context={'active_test': False},
        )
        c['value_count'] = len(vals)
    if len(cands) > 1:
        print(f'⚠ AMBIGÜEDAD: {len(cands)} atributos llamados "Color":')
        for c in cands:
            print(f'    id={c["id"]} create_variant={c.get("create_variant")!r} '
                  f'valores={c["value_count"]}')
        # Solo abortamos si tras el criterio de desempate siguen empatados.
    chosen = sorted(
        cands,
        key=lambda c: (c.get('create_variant') == 'always', c['value_count']),
        reverse=True,
    )[0]
    empatados = [c for c in cands
                 if (c.get('create_variant') == 'always', c['value_count'])
                 == (chosen.get('create_variant') == 'always', chosen['value_count'])]
    if len(empatados) > 1:
        raise SystemExit('✗ Atributo Color ambiguo tras el desempate; abortando.')
    print(f'→ Atributo Color: id={chosen["id"]} '
          f'create_variant={chosen.get("create_variant")!r} valores={chosen["value_count"]}')
    return chosen


# ─── Reporte ─────────────────────────────────────────────────────────────────

def build_report(filas: list[dict], mode: str, attr_id: int | None,
                 escritos: int, sin_cambio: int, errores: int) -> dict:
    """filas: [{name, products, res: Resolucion, current_hex, escrito(bool|None)}]."""
    total_vals = len(filas)
    total_ph = sum(f['products'] for f in filas)

    por_fuente_vals: dict[str, int] = defaultdict(int)
    por_fuente_ph: dict[str, int] = defaultdict(int)
    con_hex_vals = con_hex_ph = 0
    especial_vals = especial_ph = 0
    flag_vals = flag_ph = 0

    for f in filas:
        res: Resolucion = f['res']
        b = fuente_bucket(res.fuente)
        por_fuente_vals[b] += 1
        por_fuente_ph[b] += f['products']
        if res.hex is not None:
            con_hex_vals += 1
            con_hex_ph += f['products']
        elif res.tipo == 'especial':
            especial_vals += 1
            especial_ph += f['products']
        else:
            flag_vals += 1
            flag_ph += f['products']

    cobertura = (con_hex_ph / total_ph * 100) if total_ph else 0.0

    flagged = sorted(
        ({'name': f['name'], 'products': f['products'],
          'fuente': f['res'].fuente, 'motivo': f['res'].detalle}
         for f in filas if f['res'].hex is None and f['res'].tipo == 'flag'),
        key=lambda x: (-x['products'], x['name']),
    )
    especiales = sorted(
        ({'name': f['name'], 'products': f['products'], 'fuente': f['res'].fuente}
         for f in filas if f['res'].hex is None and f['res'].tipo == 'especial'),
        key=lambda x: (-x['products'], x['name']),
    )

    return {
        'generated': datetime.now().isoformat(timespec='seconds'),
        'mode': mode,
        'attribute_id': attr_id,
        'total_values': total_vals,
        'total_prodhits': total_ph,
        'por_fuente_values': dict(por_fuente_vals),
        'por_fuente_prodhits': dict(por_fuente_ph),
        'con_hex_values': con_hex_vals,
        'con_hex_prodhits': con_hex_ph,
        'especial_values': especial_vals,
        'especial_prodhits': especial_ph,
        'flag_values': flag_vals,
        'flag_prodhits': flag_ph,
        'cobertura_prodhits_pct': round(cobertura, 2),
        'escritos': escritos,
        'sin_cambio': sin_cambio,
        'errores': errores,
        'flagged': flagged,
        'especiales': especiales,
    }


def write_report_files(report: dict, stem: Path) -> tuple[Path, Path]:
    json_path = stem.with_suffix('.json')
    md_path = stem.with_suffix('.md')
    with open(json_path, 'w', encoding='utf-8') as f:
        json.dump(report, f, ensure_ascii=False, indent=2)

    lines: list[str] = []
    lines.append(f'# Derivación de swatches (Color) — {report["generated"]}  [{report["mode"]}]\n')
    lines.append(f'- Valores totales: **{report["total_values"]}** '
                 f'(prod-hits {report["total_prodhits"]})')
    lines.append(f'- Con html_color: **{report["con_hex_values"]}** valores / '
                 f'{report["con_hex_prodhits"]} prod-hits')
    lines.append(f'- **Cobertura (prod-hits con swatch): {report["cobertura_prodhits_pct"]}%**')
    lines.append(f'- Especial (sin hex, intencional): {report["especial_values"]} valores / '
                 f'{report["especial_prodhits"]} prod-hits')
    lines.append(f'- Flagged (contaminación): {report["flag_values"]} valores / '
                 f'{report["flag_prodhits"]} prod-hits')
    lines.append(f'- Escritos: {report["escritos"]} · Sin cambio: {report["sin_cambio"]} · '
                 f'Errores: {report["errores"]}\n')

    lines.append('## Resueltos por fuente\n')
    lines.append('| fuente | valores | prod-hits |')
    lines.append('|---|---:|---:|')
    for k in ('lex', 'base', 'regla', 'material', 'especial', 'flag'):
        v = report['por_fuente_values'].get(k, 0)
        ph = report['por_fuente_prodhits'].get(k, 0)
        lines.append(f'| {k} | {v} | {ph} |')

    lines.append('\n## FLAGGED — inventario de contaminación\n')
    lines.append('| valor | prod-hits | fuente | motivo |')
    lines.append('|---|---:|---|---|')
    for r in report['flagged']:
        lines.append(f'| {r["name"]} | {r["products"]} | {r["fuente"]} | {r["motivo"]} |')

    lines.append('\n## ESPECIAL — sin swatch por diseño (transparente/multicolor/bicolor)\n')
    lines.append('| valor | prod-hits | fuente |')
    lines.append('|---|---:|---|')
    for r in report['especiales']:
        lines.append(f'| {r["name"]} | {r["products"]} | {r["fuente"]} |')

    with open(md_path, 'w', encoding='utf-8') as f:
        f.write('\n'.join(lines) + '\n')
    return json_path, md_path


# ─── Self-check (offline, sobre el CSV dump) ─────────────────────────────────

def _newest_color_values_csv() -> Path | None:
    matches = sorted(glob.glob('reports/color_values_*.csv'))
    return Path(matches[-1]) if matches else None


def run_self_check(engine: ColorEngine) -> int:
    csv_path = _newest_color_values_csv()
    if not csv_path or not csv_path.exists():
        print('✗ No hay reports/color_values_*.csv para el self-check', file=sys.stderr)
        return 1
    print(f'Self-check OFFLINE sobre {csv_path} (no toca Odoo)\n')

    filas: list[dict] = []
    with open(csv_path, encoding='utf-8') as f:
        for row in csv.DictReader(f):
            filas.append({
                'name': row['name'],
                'products': int(row.get('products') or 0),
                'res': engine.resolve(row['name']),
                'current_hex': (row.get('html_color') or '').upper(),
                'escrito': None,
            })

    report = build_report(filas, mode='SELF-CHECK', attr_id=None,
                          escritos=0, sin_cambio=0, errores=0)

    print(f'  Valores            : {report["total_values"]} '
          f'(prod-hits {report["total_prodhits"]})')
    print(f'  Con swatch (hex)   : {report["con_hex_values"]} valores / '
          f'{report["con_hex_prodhits"]} prod-hits')
    print(f'  COBERTURA prod-hits: {report["cobertura_prodhits_pct"]}%')
    print(f'  Especial (sin hex) : {report["especial_values"]} valores / '
          f'{report["especial_prodhits"]} prod-hits')
    print(f'  Flagged (contam.)  : {report["flag_values"]} valores / '
          f'{report["flag_prodhits"]} prod-hits')
    print('\n  Por fuente (valores):')
    for k in ('lex', 'base', 'regla', 'material', 'especial', 'flag'):
        print(f'    {k:<10}: {report["por_fuente_values"].get(k, 0)}')

    if report['flagged']:
        print('\n  FLAGGED (top 20 por prod-hits):')
        for r in report['flagged'][:20]:
            print(f'    {r["name"]:<24} {r["products"]:>4}p  {r["fuente"]}:{r["motivo"]}')
    return 0


# ─── Main ────────────────────────────────────────────────────────────────────

def main() -> int:
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass

    parser = argparse.ArgumentParser(description='Deriva swatches (html_color) del atributo Color')
    parser.add_argument('--apply', action='store_true', help='Escribe html_color en Odoo. Sin esto, dry-run.')
    parser.add_argument('--limit', type=int, default=0, help='Acota nº de valores (0 = todos)')
    parser.add_argument('--report-only', action='store_true', help='Solo genera el reporte (sin verbose por valor)')
    parser.add_argument('--self-check', action='store_true', help='Corre el motor OFFLINE sobre el CSV dump; no toca Odoo')
    parser.add_argument('--output', '-o', help='Prefijo de salida del reporte (sin extensión)')
    args = parser.parse_args()

    engine = ColorEngine()

    # --self-check no necesita Odoo ni .env
    if args.self_check:
        return run_self_check(engine)

    load_dotenv()
    odoo_url = os.environ.get('ODOO_URL')
    api_key = os.environ.get('ODOO_API_KEY')
    database = os.environ.get('ODOO_DATABASE')
    if not odoo_url or not api_key:
        print('✗ Falta ODOO_URL o ODOO_API_KEY en variables de entorno', file=sys.stderr)
        return 1

    today = datetime.now().strftime('%Y%m%d')
    Path('reports').mkdir(exist_ok=True)
    stem = Path(args.output) if args.output else Path(f'reports/derive_colores_{today}')

    mode = 'APPLY' if args.apply else 'DRY-RUN'
    verbose = not args.report_only
    print(f'Derivación de swatches (Color)  [{mode}]')
    print(f'Odoo: {odoo_url}')

    client = OdooClient(odoo_url, api_key, database)

    # 1. Resolver atributo Color
    attr = resolve_color_attribute(client)
    attr_id = attr['id']

    # 2. Valores del atributo (incluye archivados)
    values = client.search_read_all(
        VALUE_MODEL,
        domain=[('attribute_id', '=', attr_id)],
        fields=['id', 'name', 'html_color'],
        context={'active_test': False},
    )
    if args.limit:
        values = values[:args.limit]

    # 3. Conteo de templates por valor (para el inventario de contaminación)
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

    # 4. Resolver cada valor
    filas: list[dict] = []
    # Agrupar escrituras por hex idéntico (idempotente): hex -> [value_ids]
    pending: dict[str, list[int]] = defaultdict(list)
    for v in values:
        res = engine.resolve(v.get('name', ''))
        current = (v.get('html_color') or '').upper()
        products = len(tmpls_by_value.get(v['id'], set()))
        escrito: bool | None = None
        if res.hex is not None:
            if res.hex.upper() != current:
                pending[res.hex.upper()].append(v['id'])
                escrito = True
            else:
                escrito = False
        filas.append({
            'name': v.get('name', ''), 'products': products, 'res': res,
            'current_hex': current, 'escrito': escrito, 'id': v['id'],
        })
        if verbose:
            hx = res.hex or '—'
            print(f'  {v.get("name",""):<26} {hx:<9} {res.tipo:<9} '
                  f'{res.fuente}:{res.detalle}')

    n_write = sum(len(ids) for ids in pending.values())
    n_groups = len(pending)
    sin_cambio = sum(1 for f in filas if f['escrito'] is False)

    # 5. Escritura agrupada (solo --apply): un write por hex.
    escritos = 0
    errores = 0
    if args.apply:
        for hex_val, ids in pending.items():
            try:
                _write_html_color(client, ids, hex_val)
                escritos += len(ids)
            except Exception as exc:
                errores += len(ids)
                print(f'  ✗ hex {hex_val} ({len(ids)} valores): {exc}')

    # 6. Reporte
    report = build_report(filas, mode, attr_id, escritos, sin_cambio, errores)
    json_path, md_path = write_report_files(report, stem)

    # 7. Resumen
    print(f'\n=== Resumen [{mode}] ===')
    print(f'  Valores procesados : {report["total_values"]} '
          f'(prod-hits {report["total_prodhits"]})')
    print(f'  Con swatch (hex)   : {report["con_hex_values"]} valores / '
          f'{report["con_hex_prodhits"]} prod-hits')
    print(f'  COBERTURA prod-hits: {report["cobertura_prodhits_pct"]}%')
    print(f'  Especial (sin hex) : {report["especial_values"]} valores / '
          f'{report["especial_prodhits"]} prod-hits')
    print(f'  Flagged (contam.)  : {report["flag_values"]} valores / '
          f'{report["flag_prodhits"]} prod-hits')
    if args.apply:
        print(f'  Escritos: {escritos} valores en {n_groups} grupos de hex | '
              f'Sin cambio: {sin_cambio} | Errores: {errores}')
    else:
        print(f'  Se escribirían: {n_write} valores en {n_groups} grupos de hex '
              f'(NADA se escribió)')
    print(f'  Reporte: {json_path}  ·  {md_path}')
    return 1 if errores else 0


if __name__ == '__main__':
    sys.exit(main())
