#!/usr/bin/env python3
"""
Anonimiza exports de WhatsApp Business app para análisis seguro.

Reemplaza nombres, teléfonos, emails, RFCs y direcciones con placeholders
mientras conserva el contenido de la conversación para análisis de patrones.

Uso:
    python anonymize_whatsapp.py input.txt [-o output.txt]
    python anonymize_whatsapp.py "exports/*.txt" --output-dir anonymized/

Input esperado: formato estándar de WhatsApp export
    [DD/MM/YY HH:MM:SS] Nombre: mensaje

Output: mismo formato pero con datos sensibles reemplazados.
"""

import argparse
import re
import sys
from pathlib import Path
from collections import defaultdict


# Patrones de detección
PATRONES = {
    # Teléfonos México (con o sin código país, con o sin espacios/guiones)
    'phone': re.compile(
        r'\+?52[\s\-]?(?:1[\s\-]?)?\d{2}[\s\-]?\d{4}[\s\-]?\d{4}'
        r'|\b\d{10}\b'
        r'|\b\d{2}[\s\-]?\d{4}[\s\-]?\d{4}\b'
    ),
    # Emails
    'email': re.compile(r'\b[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}\b'),
    # RFC México (13 chars para PF, 12 para PM)
    'rfc': re.compile(r'\b[A-Z&Ñ]{3,4}\d{6}[A-Z0-9]{3}\b'),
    # CURP (18 chars)
    'curp': re.compile(r'\b[A-Z]{4}\d{6}[HM][A-Z]{5}[A-Z0-9]{2}\b'),
    # URLs (preservar dominio público, anonimizar paths con info)
    'url': re.compile(r'https?://[^\s]+'),
    # Códigos postales México (5 dígitos consecutivos)
    'cp': re.compile(r'\bC\.?P\.?\s*:?\s*(\d{5})\b'),
    # Tarjetas (no deberían estar pero por si)
    'card': re.compile(r'\b(?:\d{4}[\s\-]?){3}\d{4}\b'),
}


class Anonimizador:
    """Mantiene mapping de original → placeholder para consistencia
    dentro de una misma conversación.
    """

    def __init__(self):
        self.nombres = {}
        self.telefonos = {}
        self.emails = {}
        self.empresas = {}
        self.counter = defaultdict(int)

    def _get_placeholder(self, tipo, original):
        """Devuelve el mismo placeholder si ya se vio, o genera uno nuevo."""
        store = getattr(self, f'{tipo}s', None)
        if store is None:
            self.counter[tipo] += 1
            return f"[{tipo.upper()}_{self.counter[tipo]:03d}]"

        if original not in store:
            self.counter[tipo] += 1
            store[original] = f"[{tipo.upper()}_{self.counter[tipo]:03d}]"
        return store[original]

    def anonimizar_telefono(self, match):
        return self._get_placeholder('telefono', match.group(0))

    def anonimizar_email(self, match):
        # Conserva dominio para que el patrón de cliente corporativo vs personal
        # siga siendo analizable. Ej: "j***@gmail.com" vs "j***@empresa.com"
        email = match.group(0)
        local, _, dominio = email.partition('@')
        return f"{local[0]}***@{dominio}"

    def anonimizar_nombre(self, nombre):
        """Aplica al campo 'autor' de cada línea, no al body del mensaje."""
        nombre = nombre.strip()
        # Si es un número, asume teléfono no agregado a contactos
        if re.match(r'^\+?\d', nombre):
            return self._get_placeholder('contacto_sin_nombre', nombre)
        return self._get_placeholder('contacto', nombre)

    def anonimizar_body(self, body):
        """Reemplaza patrones sensibles dentro del cuerpo del mensaje."""
        body = PATRONES['phone'].sub(self.anonimizar_telefono, body)
        body = PATRONES['email'].sub(self.anonimizar_email, body)
        body = PATRONES['rfc'].sub('[RFC_REDACTADO]', body)
        body = PATRONES['curp'].sub('[CURP_REDACTADO]', body)
        body = PATRONES['card'].sub('[TARJETA_REDACTADA]', body)
        # CP: conservar formato pero ofuscar últimos 3 dígitos
        body = PATRONES['cp'].sub(lambda m: f"CP {m.group(1)[:2]}***", body)
        # URLs: preservar dominio, ofuscar path si tiene info
        body = PATRONES['url'].sub(self._anonimizar_url, body)
        return body

    def _anonimizar_url(self, match):
        url = match.group(0)
        # Si es URL de Mozaprint o público conocido, mantener
        if 'mozaprintmx' in url or 'odoo.com' in url:
            return url
        # Si tiene path con query params (potencial info), ofuscar path
        m = re.match(r'(https?://[^/]+)(/.+)?', url)
        if m and m.group(2):
            return f"{m.group(1)}/[REDACTED_PATH]"
        return url


def procesar_linea(linea, anonimizador):
    """Procesa una línea del export de WhatsApp.

    Formato esperado:
    [DD/MM/YY, HH:MM:SS] Nombre: mensaje
    [DD/MM/YY, HH:MM:SS] Nombre: <Archivo omitido>

    Líneas de continuación no tienen prefijo de timestamp.
    """
    # Match líneas con timestamp
    patron_linea = re.compile(
        r'^\[(\d{1,2}/\d{1,2}/\d{2,4},?\s+\d{1,2}:\d{2}(?::\d{2})?)\]\s+'
        r'([^:]+?):\s*(.*)$'
    )

    match = patron_linea.match(linea)
    if match:
        timestamp, autor, mensaje = match.groups()
        autor_anonimo = anonimizador.anonimizar_nombre(autor)
        mensaje_anonimo = anonimizador.anonimizar_body(mensaje)
        return f"[{timestamp}] {autor_anonimo}: {mensaje_anonimo}\n"
    else:
        # Línea de continuación o sistema, sólo anonimizar contenido
        return anonimizador.anonimizar_body(linea)


def anonimizar_archivo(input_path: Path, output_path: Path):
    """Procesa un archivo completo."""
    anonimizador = Anonimizador()
    
    with open(input_path, 'r', encoding='utf-8') as f_in:
        lineas = f_in.readlines()
    
    lineas_anonimas = [procesar_linea(linea, anonimizador) for linea in lineas]
    
    with open(output_path, 'w', encoding='utf-8') as f_out:
        f_out.writelines(lineas_anonimas)
    
    # Resumen
    print(f"✓ {input_path.name} → {output_path.name}")
    print(f"  Contactos: {len(anonimizador.nombres) + len(anonimizador.empresas)}")
    print(f"  Teléfonos: {len(anonimizador.telefonos)}")
    print(f"  Emails: {len(anonimizador.emails)}")


def main():
    parser = argparse.ArgumentParser(
        description='Anonimiza exports de WhatsApp para análisis seguro',
        epilog='Ejemplo: python anonymize_whatsapp.py "exports/*.txt" -d anonymized/'
    )
    parser.add_argument('input', help='Archivo o glob pattern')
    parser.add_argument('-o', '--output', help='Archivo de salida (un solo input)')
    parser.add_argument('-d', '--output-dir', help='Directorio de salida (múltiples)')
    parser.add_argument('--dry-run', action='store_true', help='Mostrar qué se procesaría')
    
    args = parser.parse_args()
    
    # Resolver inputs
    input_path = Path(args.input)
    if '*' in args.input or '?' in args.input:
        # Glob pattern
        parent = input_path.parent if input_path.parent != Path('.') else Path('.')
        pattern = input_path.name
        files = sorted(parent.glob(pattern))
    else:
        files = [input_path] if input_path.exists() else []
    
    if not files:
        print(f"✗ No se encontraron archivos para: {args.input}", file=sys.stderr)
        return 1
    
    # Determinar output
    if args.output_dir:
        out_dir = Path(args.output_dir)
        out_dir.mkdir(parents=True, exist_ok=True)
    elif args.output:
        if len(files) > 1:
            print("✗ --output sólo aplica para un input. Usa --output-dir para múltiples.",
                  file=sys.stderr)
            return 1
        out_dir = None
    else:
        out_dir = Path('anonymized')
        out_dir.mkdir(exist_ok=True)
    
    if args.dry_run:
        print("DRY RUN — sólo mostrando qué se procesaría:")
        for f in files:
            out = Path(args.output) if args.output else (out_dir / f.name)
            print(f"  {f} → {out}")
        return 0
    
    # Procesar
    for f in files:
        if args.output:
            out = Path(args.output)
        else:
            out = out_dir / f.name
        anonimizar_archivo(f, out)
    
    print(f"\n✓ {len(files)} archivo(s) procesado(s)")
    print("⚠ Revisa manualmente que la anonimización fue completa antes de compartir.")
    return 0


if __name__ == '__main__':
    sys.exit(main())
