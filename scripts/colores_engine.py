#!/usr/bin/env python3
"""
Motor de color compartido (sin Odoo, testeable offline).

Lo consumen:
  - scripts/derive_colores.py       -> resolve(): deriva html_color (swatch)
  - scripts/derive_color_familia.py -> familia(): deriva la familia de /shop

Expone:
  - normalize(name)          normalización canónica (== derive_tecnicas)
  - resolve(name)  -> Resolucion(hex, tipo, fuente, detalle)   [swatch]
  - familia(name)  -> str | None                                [filtro /shop]
  - ColorEngine    clase con .resolve() y .familia() (carga el seed una vez)

FUENTE (read-only): data/colores_seed.csv (con columna `familia`),
data/colores_modifiers.csv y las constantes STRIP_TOKENS / NON_COLOR /
MATERIAL_APROX / MATERIAL_FAMILIA (fuente documental: data/colores_noncolor.md).

`resolve()` (swatch) exige exactitud: un modificador desconocido -> flag.
`familia()` (filtro) es deliberadamente más laxo: agrupa por el color base/lex
dominante aunque el modificador sea desconocido (ej. ROJO JASPEADO -> Rojo), y
trata tricolor/mexico/arcoiris/surtido como Multicolor. Un filtro tolera "cercano";
el swatch no.
"""

import colorsys
import csv
import re
import unicodedata
from pathlib import Path
from typing import NamedTuple

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

# Valores que NO son color: sin html_color y sin familia; reportados como contaminación.
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

# Materiales con color natural razonable -> hex aproximado para el SWATCH (tipo=flat).
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

# Familia de /shop para cada material (decisión de negocio; ver colores_noncolor.md).
MATERIAL_FAMILIA = {
    'carton': 'Cafe',
    'corcho': 'Cafe',
    'madera': 'Cafe',
    'periodico': 'Cafe',
    'bambu': 'Beige',
    'cebada': 'Beige',
    'cana': 'Beige',
    'coco': 'Blanco',
    'caoba': 'Rojo',   # "tinto" -> familia Rojo (Vino)
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
    hex: str       # '' para especial (transparente/multicolor/bicolor)
    tipo: str      # flat | metalico | especial
    clase: str     # base | lex
    familia: str   # nombre de familia de /shop; '' -> sin familia (Transparente)


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


def load_seed() -> tuple[dict[str, SeedColor], dict[str, SeedColor], set[str]]:
    """
    Devuelve (LEX_EXACT, BASE_BY_TOKEN, MULTI_ALIASES):
      - LEX_EXACT: alias_normalizada (multi-palabra) -> SeedColor clase=lex
      - BASE_BY_TOKEN: token_normalizado -> SeedColor clase=base
      - MULTI_ALIASES: aliases normalizadas de las filas con familia=Multicolor
    """
    lex_exact: dict[str, SeedColor] = {}
    base_by_token: dict[str, SeedColor] = {}
    multi_aliases: set[str] = set()
    for row in _read_csv_skip_comments(SEED_CSV):
        sc = SeedColor(
            nombre=row['nombre'].strip(),
            hex=(row['hex'] or '').strip().upper(),
            tipo=row['tipo'].strip(),
            clase=row['clase'].strip(),
            familia=(row.get('familia') or '').strip(),
        )
        alias_norms = [normalize(a) for a in (row['aliases'] or '').split('|')]
        alias_norms = [a for a in alias_norms if a]
        for alias_norm in alias_norms:
            if sc.clase == 'lex':
                lex_exact.setdefault(alias_norm, sc)
            elif sc.clase == 'base':
                base_by_token.setdefault(alias_norm.split()[0], sc)
        if sc.familia == 'Multicolor':
            multi_aliases.update(alias_norms)
    return lex_exact, base_by_token, multi_aliases


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


# ─── Motor ───────────────────────────────────────────────────────────────────

class Resolucion(NamedTuple):
    hex: str | None      # None = no se escribe html_color
    tipo: str            # flat | metalico | especial | flag
    fuente: str          # lex | material | base | base+mod | especial | bicolor
                         # | non_color | base+desconocido | sin_base | multibase
    detalle: str         # base+modificadores usados, o motivo del flag


class ColorEngine:
    """Carga el seed una vez y resuelve swatch (resolve) y familia (familia)."""

    def __init__(self) -> None:
        self.lex_exact, self.base_by_token, self.multi_aliases = load_seed()
        self.mods = load_modifiers()

    # ---- SWATCH (exacto) ----------------------------------------------------
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

        if norm in self.lex_exact:                      # 1. LEX exacto
            sc = self.lex_exact[norm]
            if sc.tipo == 'especial':
                return Resolucion(None, 'especial', 'lex', sc.nombre)
            return Resolucion(sc.hex, sc.tipo, 'lex', sc.nombre)

        if '/' in raw or 'con' in norm.split():         # 2. BICOLOR
            return Resolucion(None, 'especial', 'bicolor', raw.strip())

        if norm in NON_COLOR:                           # 3. NON_COLOR
            return Resolucion(None, 'flag', 'non_color', norm)

        if norm in MATERIAL_APROX:                      # 4. MATERIAL
            return Resolucion(MATERIAL_APROX[norm], 'flat', 'material', norm)

        tokens = _tokenize(norm)                        # 5. STRIP + re-match
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

        return self._base_mod(core, via_strip)          # 6. BASE + MODIFICADOR

    # ---- FAMILIA (laxo, para el filtro de /shop) ----------------------------
    def familia(self, name: str) -> str | None:
        """
        Familia de /shop para un valor de Color. Más laxo que resolve():
        basta identificar el color base/lex dominante. Devuelve None solo para
        no-color puro (contaminación) y Transparente.
        """
        raw = name or ''
        norm = normalize(raw)
        if not norm:
            return None

        # 1. Patrón de dos tonos y agrupadores multicolor -> Multicolor
        if '/' in raw or 'con' in norm.split():
            return 'Multicolor'
        if norm in self.multi_aliases:              # tricolor/mexico/arcoiris/surtido/...
            return 'Multicolor'

        # 2. No-color puro -> sin familia
        if norm in NON_COLOR:
            return None

        # 3. Material -> familia de material
        if norm in MATERIAL_FAMILIA:
            return MATERIAL_FAMILIA[norm]

        # 4. Quitar talla/género
        core = [t for t in _tokenize(norm) if t not in STRIP_TOKENS]
        if not core:
            return None
        core_norm = ' '.join(core)

        # 5. LEX exacto (incl. compuestos y aliases de una palabra)
        if core_norm in self.lex_exact:
            return self.lex_exact[core_norm].familia or None
        if core_norm in MATERIAL_FAMILIA:
            return MATERIAL_FAMILIA[core_norm]

        # 6. Token base dominante -> su familia (laxo: ignora modificadores desconocidos)
        for t in core:
            if t in self.base_by_token:
                return self.base_by_token[t].familia or None
        # 6b. Token que sea un alias lex de una sola palabra (humo/marino/aqua/…)
        for t in core:
            if t in self.lex_exact:
                return self.lex_exact[t].familia or None

        return None


# ─── Conveniencia a nivel módulo (singleton perezoso) ────────────────────────

_default_engine: ColorEngine | None = None


def _engine() -> ColorEngine:
    global _default_engine
    if _default_engine is None:
        _default_engine = ColorEngine()
    return _default_engine


def resolve(name: str) -> Resolucion:
    return _engine().resolve(name)


def familia(name: str) -> str | None:
    return _engine().familia(name)
