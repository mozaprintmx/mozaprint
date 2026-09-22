#!/usr/bin/env python3
"""
Corre de una sola vez **todas** las validaciones automáticas del checklist
post-upgrade y resume el resultado en una tabla. Todas son de **solo lectura**.

Por qué existe: cada pieza que entró a producción dejó su propio auditor, y en un
upgrade hay que correrlos todos. Si se corren a mano es fácil olvidar uno — y el
que se olvide es justo el que va a fallar. Este script los encadena y sale con
código 1 si cualquiera encuentra algo.

Qué corre (el mismo orden del checklist):

  a) `audit_post_upgrade.py`        — vistas, sitio web y censo de objetos custom
  b) `deploy_reporte_cotizacion.py` — columna de imagen y cuadre del PDF de cotización
  c) `audit_lineas_facturables.py`  — que no reaparezca código que Odoo factura (ADR 007)
  d) `audit_personalizacion.py`     — matriz, productos y reglas de precio coherentes
  e) `audit_checkout_sin_pago.py`   — que la tienda siga sin cobrar en línea (ADR 010)

Lo que este script NO cubre, y hay que hacer a mano tras un upgrade:

  - `audit_post_upgrade.py --comparar` (test vs prod lado a lado);
  - el checkout en el navegador: `/shop/payment` necesita un carrito con dirección
    y transportista, y eso no se puede simular de forma fiable desde un script;
  - el PDF de cotización a ojo.
  Ver `docs/upgrades/checklist-post-upgrade.md`.

Uso:
    python scripts/checklist_upgrade.py --target test
    python scripts/checklist_upgrade.py --target prod
    python scripts/checklist_upgrade.py --target test --sin-http   # más rápido
    python scripts/checklist_upgrade.py --target test --ver        # salida completa

Variables de entorno (analysis/supplier-sync/.env):
    ODOO_URL, ODOO_TEST_URL, ODOO_DB, ODOO_USER, ODOO_PASSWORD
"""

from __future__ import annotations

import argparse
import io
import subprocess
import sys
import time
from pathlib import Path

if hasattr(sys.stdout, "buffer"):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

REPO = Path(__file__).resolve().parent.parent
SCRIPTS = REPO / "scripts"

# (letra, qué vigila, script, argumentos propios)
VALIDACIONES = [
    ("a", "Vistas, sitio web y censo de objetos custom",
     "audit_post_upgrade.py", []),
    ("b", "PDF de cotización: columna de imagen y cuadre",
     "deploy_reporte_cotizacion.py", ["--verificar"]),
    ("c", "Código que Odoo factura (debe ser 0)",
     "audit_lineas_facturables.py", ["--max-bloques", "0"]),
    ("d", "Personalización: matriz, productos y reglas",
     "audit_personalizacion.py", []),
    ("e", "La tienda sigue SIN cobrar en línea",
     "audit_checkout_sin_pago.py", []),
]

# Solo el primero acepta saltarse el barrido HTTP.
ACEPTAN_SIN_HTTP = {"audit_post_upgrade.py"}


def correr(script: str, args: list[str], ver: bool) -> tuple[int, str, float]:
    """Ejecuta un auditor y devuelve (código, salida, segundos)."""
    inicio = time.monotonic()
    proc = subprocess.run(
        [sys.executable, str(SCRIPTS / script), *args],
        cwd=REPO, capture_output=True, text=True, encoding="utf-8", errors="replace",
    )
    salida = (proc.stdout or "") + (proc.stderr or "")
    if ver:
        print(salida)
    return proc.returncode, salida, time.monotonic() - inicio


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--target", choices=["test", "prod"], default="test")
    ap.add_argument("--sin-http", action="store_true",
                    help="Omite el barrido de rutas públicas (más rápido)")
    ap.add_argument("--ver", action="store_true",
                    help="Muestra la salida completa de cada auditor, no solo el resumen")
    args = ap.parse_args()

    print("=" * 78)
    print(f"  CHECKLIST POST-UPGRADE — {len(VALIDACIONES)} validaciones  "
          f"[{args.target.upper()}]  ·  solo lectura")
    print("=" * 78)

    resultados = []
    for letra, que, script, propios in VALIDACIONES:
        extra = ["--sin-http"] if (args.sin_http and script in ACEPTAN_SIN_HTTP) else []
        cmd = ["--target", args.target, *propios, *extra]
        print(f"\n[{letra}] {que}")
        print(f"    $ python scripts/{script} {' '.join(cmd)}")
        codigo, salida, segs = correr(script, cmd, args.ver)
        resultados.append((letra, que, script, codigo, salida, segs))
        print(f"    {'✓ limpio' if codigo == 0 else f'✗ con hallazgos (código {codigo})'}"
              f"  ·  {segs:.0f}s")
        if codigo != 0 and not args.ver:
            print("    ---- últimas líneas ----")
            for linea in [l for l in salida.splitlines() if l.strip()][-12:]:
                print(f"    {linea}")

    fallidas = [r for r in resultados if r[3] != 0]
    print("\n" + "=" * 78)
    print("  RESUMEN")
    for letra, que, _script, codigo, _s, segs in resultados:
        print(f"   {'✓' if codigo == 0 else '✗'} ({letra}) {que:<48} {segs:>5.0f}s")
    print("=" * 78)

    if fallidas:
        print(f"  ✗ {len(fallidas)} de {len(resultados)} con hallazgos: "
              f"{', '.join(f'({r[0]})' for r in fallidas)}")
        print("  Reprodúcelas una por una con --ver para ver el detalle completo.")
        return 1

    print("  ✓ Las cinco limpias.")
    print("  Falta a mano: `audit_post_upgrade.py --comparar`, el checkout en el navegador")
    print("  y el PDF a ojo. Ver docs/upgrades/checklist-post-upgrade.md")
    return 0


if __name__ == "__main__":
    sys.exit(main())
