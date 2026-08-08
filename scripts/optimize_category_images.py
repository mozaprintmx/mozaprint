#!/usr/bin/env python3
"""
Optimiza las imágenes de las categorías de eCommerce (product.public.category)
para desinflar el filmstrip de /shop.

CONTEXTO DEL PROBLEMA (medido y verificado 2026-08-07):
    El filmstrip nativo de website_sale (`o_wsale_categories_filmstrip`) NO sirve
    las imágenes por /web/image/: las incrusta en el HTML de /shop como data URI,
    una por categoría raíz. Al ir dentro del HTML no se cachean, se re-descargan
    en cada visita y bloquean el render.

    Y Odoo NO redimensiona `image_128` cuando `image_1920` se escribe por API:
    la deja byte a byte idéntica (comprobado leyendo de vuelta tras escribir; las
    únicas categorías que tenían miniatura real eran las subidas por el editor
    web). Conclusión operativa: **el peso de /shop es la suma de los
    `image_1920` × 4/3**, así que el único control que tenemos es escribirlas ya
    pequeñas.

    Punto de partida: /shop = 5,041 KB, de los cuales 4,598 KB (91%) eran las 38
    miniaturas, a 121 KB de promedio.

QUÉ HACE:
    1. Descarga `image_1920` de cada categoría y guarda el ORIGINAL en
       backups/category_images_AAAAMMDD/ (backup_catalog.py NO respalda imágenes).
    2. Re-encoda a WebP con el lado mayor <= --max-px, SIEMPRE partiendo del
       original respaldado y nunca de lo que hay en Odoo (evita recomprimir sobre
       recomprimido en corridas sucesivas).
    3. Con --apply re-escribe `image_1920` y verifica leyendo de vuelta.

    NO toca ninguna vista ni snippet: el filmstrip es nativo y se re-renderiza solo.

IDEMPOTENTE: si re-encodar el original da byte a byte lo que ya está en Odoo, la
categoría se salta. Re-correr con los mismos parámetros no escribe nada.

DRY-RUN por defecto: sin --apply no escribe nada en Odoo.

Uso:
    python optimize_category_images.py                    # dry-run, todas
    python optimize_category_images.py --only-broken      # dry-run, solo las rotas
    python optimize_category_images.py --only-broken --apply
    python optimize_category_images.py --ids 9,108,141 --apply
    python optimize_category_images.py --max-px 384 --quality 85 --apply

Rollback:
    python rollback_category_images.py --from backups/category_images_AAAAMMDD --apply

Variables de entorno necesarias:
    ODOO_URL       https://mozaprintmx.odoo.com
    ODOO_API_KEY   ...
    ODOO_DATABASE  (opcional)
"""

import argparse
import base64
import io
import os
import re
import sys
import unicodedata
from datetime import date
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from PIL import Image

from odoo_client import OdooClient

MODEL = 'product.public.category'
REPO = Path(__file__).resolve().parent.parent

# El filmstrip dibuja fichas de ~128 px y Odoo incrusta la imagen tal cual en el
# HTML, así que 256 px da nitidez 2x en pantallas retina al mínimo costo.
# Calibrado sobre los originales (2026-08-07): 256/q82 -> /shop ~912 KB;
# 512/q82 -> ~1,893 KB; 128/q82 -> ~603 KB pero sin margen para retina.
DEFAULT_MAX_PX = 256
DEFAULT_QUALITY = 82


def slug(texto: str) -> str:
    """Nombre de archivo seguro a partir del nombre de la categoría."""
    plano = unicodedata.normalize('NFKD', texto).encode('ascii', 'ignore').decode()
    return re.sub(r'[^a-zA-Z0-9]+', '_', plano).strip('_').lower() or 'sin_nombre'


def dimensiones(raw: bytes) -> tuple[int, int]:
    with Image.open(io.BytesIO(raw)) as im:
        return im.size


def optimizar(raw: bytes, max_px: int, quality: int) -> bytes:
    """Reduce al lado mayor <= max_px y re-encoda a WebP conservando alfa."""
    with Image.open(io.BytesIO(raw)) as im:
        im.load()
        # WebP no soporta paleta ni CMYK; normalizar preservando transparencia.
        if im.mode in ('P', 'LA'):
            im = im.convert('RGBA')
        elif im.mode not in ('RGB', 'RGBA'):
            im = im.convert('RGB')
        im.thumbnail((max_px, max_px), Image.LANCZOS)
        salida = io.BytesIO()
        im.save(salida, format='WEBP', quality=quality, method=6)
        return salida.getvalue()


def cargar_categorias(client: OdooClient, ids: list[int] | None) -> list[dict[str, Any]]:
    """Trae sólo las categorías que tienen imagen (image_1920 es pesado)."""
    domain: list = [('image_1920', '!=', False)]
    if ids:
        domain.append(('id', 'in', ids))
    return client.search_read_all(
        MODEL,
        domain=domain,
        fields=['id', 'name', 'parent_id', 'image_1920', 'image_128'],
        batch_size=5,
    )


def analizar(cats: list[dict[str, Any]], max_px: int, quality: int,
             backup_dir: Path) -> list[dict[str, Any]]:
    """Descarga, respalda y calcula la versión optimizada de cada categoría."""
    filas = []
    for cat in sorted(cats, key=lambda x: x['name']):
        actual = base64.b64decode(cat['image_1920'])
        thumb = base64.b64decode(cat['image_128']) if cat.get('image_128') else b''
        # Odoo NO regenera image_128 al escribir por API: la deja idéntica a
        # image_1920 (verificado 2026-08-07). Por eso lo que pesa en el HTML es
        # el tamaño de image_1920 tal cual lo escribimos aquí.
        copia_literal = len(thumb) == len(actual) and len(actual) > 0

        # NUNCA sobrescribir: si el archivo ya existe es de una corrida previa y
        # contiene el original de verdad. Re-escribirlo tras un --apply guardaría
        # la versión ya optimizada y dejaría el rollback inservible.
        archivo = backup_dir / f"{cat['id']:03d}_{slug(cat['name'])}.webp"
        if not archivo.exists():
            archivo.write_bytes(actual)

        # Siempre re-encodar DESDE EL ORIGINAL respaldado, nunca desde lo que hay
        # en Odoo: si ya corrimos --apply, eso es una versión comprimida y
        # re-comprimirla degrada la imagen en cada pasada.
        fuente = archivo.read_bytes()

        try:
            w, h = dimensiones(actual)
            nueva = optimizar(fuente, max_px, quality)
            nw, nh = dimensiones(nueva)
            error = None
        except Exception as exc:
            w = h = nw = nh = 0
            nueva = b''
            error = str(exc)

        # Idempotencia exacta: si re-encodar da byte a byte lo que ya está en
        # Odoo, no hay nada que escribir.
        identica = bool(nueva) and nueva == actual
        # Ya está en el objetivo y re-encodar no gana nada: sólo perdería calidad.
        sin_ganancia = (bool(nueva) and len(nueva) >= len(actual)
                        and max(w, h) <= max_px)

        filas.append({
            'id': cat['id'],
            'name': cat['name'],
            'padre': (cat.get('parent_id') or [None, None])[1],
            'copia_literal': copia_literal,
            'bytes_orig': len(actual),
            'bytes_fuente': len(fuente),
            'bytes_thumb': len(thumb),
            'px_orig': (w, h),
            'bytes_nueva': len(nueva),
            'px_nueva': (nw, nh),
            'nueva_b64': base64.b64encode(nueva).decode() if nueva else '',
            'backup': archivo,
            'error': error,
            'saltar': identica or sin_ganancia or bool(error),
            'motivo_salto': ('error' if error else
                             'ya aplicada' if identica else
                             'sin ganancia' if sin_ganancia else ''),
        })
    return filas


def aplicar(client: OdooClient, filas: list[dict[str, Any]], apply: bool) -> int:
    """Escribe image_1920 y verifica que Odoo haya regenerado image_128."""
    fallos = 0
    for f in filas:
        if f['saltar']:
            continue
        etiqueta = f"id={f['id']:<4} {f['name']}"
        if not apply:
            print(f"  ~ {etiqueta}")
            continue
        try:
            client.write(MODEL, [f['id']], {'image_1920': f['nueva_b64']})
        except Exception as exc:
            print(f"  x {etiqueta} — falló el write: {exc}")
            fallos += 1
            continue
        # Verificación: leer de vuelta y confirmar que quedó lo que escribimos.
        # Odoo copia image_1920 en image_128 sin redimensionar, así que lo que
        # se incrusta en el HTML de /shop es exactamente este tamaño.
        try:
            leido = client.search_read(MODEL, [('id', '=', f['id'])],
                                       ['image_1920', 'image_128'])
            n1920 = len(base64.b64decode(leido[0]['image_1920'])) if leido else 0
            n128 = len(base64.b64decode(leido[0]['image_128'])) if leido else 0
            f['bytes_post'] = n1920
            if n1920 != f['bytes_nueva']:
                print(f"  ! {etiqueta} — se escribieron {f['bytes_nueva']/1024:.1f} KB "
                      f"pero Odoo reporta {n1920/1024:.1f} KB")
                fallos += 1
            else:
                print(f"  v {etiqueta} — {f['bytes_orig']/1024:.1f} KB "
                      f"-> {n1920/1024:.1f} KB (en el HTML: {n128/1024:.1f} KB)")
        except Exception as exc:
            print(f"  ? {etiqueta} — escrita pero no se pudo verificar: {exc}")
    return fallos


def escribir_reporte(filas: list[dict[str, Any]], ruta: Path, apply: bool,
                     max_px: int, quality: int, backup_dir: Path) -> None:
    kb = lambda n: f'{n/1024:.1f}'  # noqa: E731
    tocadas = [f for f in filas if not f['saltar']]
    ahorro = sum(f['bytes_orig'] - f['bytes_nueva'] for f in tocadas)

    lineas = [
        f'# Optimización de imágenes de categorías — {date.today().isoformat()}',
        '',
        f'- Modo: **{"APPLY" if apply else "DRY-RUN"}**',
        f'- Parámetros: `--max-px {max_px} --quality {quality}`',
        f'- Respaldo de originales: `{backup_dir.relative_to(REPO)}/` '
        f'(fuente de todo re-encodado)',
        f'- Categorías con imagen: {len(filas)} · a optimizar: {len(tocadas)}',
        f'- Ahorro en las tocadas: **{kb(ahorro)} KB**',
        '',
        'Odoo no redimensiona `image_128` al escribir por API: la deja idéntica a',
        '`image_1920`. El filmstrip de `/shop` incrusta esa imagen como data URI,',
        'así que el peso de la página es la suma de la columna "KB después" × 4/3.',
        '',
        '## Detalle',
        '',
        '| id | categoría | px antes | KB antes | px después | KB después | acción |',
        '|---:|---|---|---:|---|---:|---|',
    ]
    for f in sorted(filas, key=lambda x: -(x['bytes_orig'] - x['bytes_nueva'])):
        accion = f"salta ({f['motivo_salto']})" if f['saltar'] else 'optimiza'
        lineas.append(
            f"| {f['id']} | {f['name']} "
            f"| {f['px_orig'][0]}x{f['px_orig'][1]} | {kb(f['bytes_orig'])} "
            f"| {f['px_nueva'][0]}x{f['px_nueva'][1]} | {kb(f['bytes_nueva'])} | {accion} |"
        )
    if not apply:
        lineas += ['', '> Dry-run: no se escribió nada en Odoo. '
                       'Re-corre con `--apply` para ejecutar.']
    ruta.write_text('\n'.join(lineas) + '\n', encoding='utf-8')


def main() -> int:
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass

    load_dotenv()

    p = argparse.ArgumentParser(
        description='Optimiza image_1920 de product.public.category (idempotente)')
    p.add_argument('--apply', action='store_true',
                   help='Ejecuta los cambios. Sin este flag es dry-run.')
    p.add_argument('--only-broken', action='store_true',
                   help='Sólo las categorías cuya image_128 es copia literal de '
                        'image_1920 (tras un --apply lo son todas).')
    p.add_argument('--ids', help='Lista de ids separados por coma.')
    p.add_argument('--max-px', type=int, default=DEFAULT_MAX_PX,
                   help=f'Lado mayor máximo (default {DEFAULT_MAX_PX}).')
    p.add_argument('--quality', type=int, default=DEFAULT_QUALITY,
                   help=f'Calidad WebP 1-100 (default {DEFAULT_QUALITY}).')
    args = p.parse_args()

    odoo_url = os.environ.get('ODOO_URL')
    api_key = os.environ.get('ODOO_API_KEY')
    if not odoo_url or not api_key:
        print('x Falta ODOO_URL o ODOO_API_KEY en variables de entorno', file=sys.stderr)
        return 1

    ids = [int(x) for x in args.ids.split(',')] if args.ids else None
    hoy = date.today().strftime('%Y%m%d')
    backup_dir = REPO / 'backups' / f'category_images_{hoy}'
    backup_dir.mkdir(parents=True, exist_ok=True)
    (REPO / 'reports').mkdir(exist_ok=True)

    print(f'Optimización de imágenes de categoría -> {MODEL}')
    print(f'Odoo: {odoo_url}')
    print(f'Modo: {"APPLY" if args.apply else "DRY-RUN"} · max {args.max_px}px · q{args.quality}\n')

    client = OdooClient(odoo_url, api_key, os.environ.get('ODOO_DATABASE'))

    print('-> Descargando imágenes actuales (esto tarda, image_1920 es pesado)...')
    cats = cargar_categorias(client, ids)
    if not cats:
        print('x No se encontraron categorías con imagen.', file=sys.stderr)
        return 1

    filas = analizar(cats, args.max_px, args.quality, backup_dir)
    if args.only_broken:
        filas = [f for f in filas if f['copia_literal']]

    copias = [f for f in filas if f['copia_literal']]
    tocadas = [f for f in filas if not f['saltar']]
    print(f'   {len(filas)} categorías con imagen · '
          f'{len(copias)} con image_128 = copia literal de image_1920')
    print(f'   originales en {backup_dir.relative_to(REPO)}/ (fuente del re-encodado)\n')

    print(f'=== {"APPLY" if args.apply else "DRY-RUN"} — {len(tocadas)} a optimizar ===')
    fallos = aplicar(client, filas, args.apply)

    antes = sum(f['bytes_orig'] for f in tocadas)
    despues = sum(f['bytes_nueva'] for f in tocadas)
    print(f'\nPeso de las tocadas: {antes/1024:.1f} KB -> {despues/1024:.1f} KB '
          f'({(1 - despues/antes)*100:.0f}% menos)' if antes else '\nNada que optimizar.')

    reporte = REPO / 'reports' / f'optimize_category_images_{hoy}.md'
    escribir_reporte(filas, reporte, args.apply, args.max_px, args.quality, backup_dir)
    print(f'Reporte: {reporte.relative_to(REPO)}')

    if not args.apply:
        print('\nDry-run: NO se escribió nada en Odoo. Re-corre con --apply para ejecutar.')
    return 1 if fallos else 0


if __name__ == '__main__':
    sys.exit(main())
