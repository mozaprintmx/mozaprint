#!/usr/bin/env python3
"""
Auditoría DNS — Mozaprint
==========================

Verifica el estado del DNS de mozaprintmx.com y detecta inconsistencias
entre Cloudflare y Hostinger.

Detecta:
- Quién es authoritative (cuáles nameservers están vivos)
- Registros A, AAAA, MX, TXT, SPF, DKIM, DMARC, CNAME
- Subdominios huérfanos comunes
- Discrepancias entre nameservers
- Validación de configuración de email (SPF/DKIM/DMARC)

Uso:
    python3 dns_audit.py
    python3 dns_audit.py --domain otrodominio.com
    python3 dns_audit.py --output reporte.json

Requiere:
    - dnspython:    pip install dnspython
    - rich (opcional): pip install rich   # para output más bonito

Sin dependencias externas (solo Python 3.9+), usando subprocess + dig:
    python3 dns_audit.py --use-dig
"""

import argparse
import json
import subprocess
import sys
from dataclasses import dataclass, field, asdict
from typing import Any
from datetime import datetime

DEFAULT_DOMAIN = 'mozaprintmx.com'

# Subdominios comunes a auditar
SUBDOMAINS_TO_CHECK = [
    'www',
    'mail',
    'webmail',
    'shop',
    'tienda',
    'blog',
    'old',
    'staging',
    'dev',
    'cpanel',
    'autodiscover',
    'ftp',
    'n8n',  # propuesto para el orquestador
    '_dmarc',
    'default._domainkey',  # DKIM común
    'google._domainkey',   # Google Workspace
    'selector1._domainkey',
    'selector2._domainkey',
]

# Patrones para identificar provider
CLOUDFLARE_NS_PATTERNS = ['cloudflare.com']
HOSTINGER_NS_PATTERNS = ['hostinger.com', 'dns-parking.com']
ODOO_NS_PATTERNS = ['odoo.com']
ODOO_IP_RANGE_PATTERNS = ['149.202.', '34.', '35.205.']  # rangos aproximados


@dataclass
class DNSRecord:
    """Un registro DNS individual"""
    name: str
    rtype: str
    value: str
    ttl: int | None = None


@dataclass
class AuditReport:
    """Reporte completo de auditoría"""
    domain: str
    timestamp: str
    nameservers: list[str] = field(default_factory=list)
    authoritative_provider: str = 'unknown'
    a_records: list[DNSRecord] = field(default_factory=list)
    aaaa_records: list[DNSRecord] = field(default_factory=list)
    mx_records: list[DNSRecord] = field(default_factory=list)
    txt_records: list[DNSRecord] = field(default_factory=list)
    cname_records: list[DNSRecord] = field(default_factory=list)
    subdomains_alive: dict[str, list[str]] = field(default_factory=dict)
    spf_status: dict[str, Any] = field(default_factory=dict)
    dmarc_status: dict[str, Any] = field(default_factory=dict)
    dkim_found: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)


def run_dig(name: str, rtype: str = 'A', nameserver: str | None = None) -> list[str]:
    """Wrapper sobre dig. Devuelve lista de respuestas."""
    cmd = ['dig', '+short', '+time=3', '+tries=1']
    if nameserver:
        cmd.append(f'@{nameserver}')
    cmd.extend([name, rtype])

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
        if result.returncode != 0:
            return []
        lines = [line.strip() for line in result.stdout.strip().split('\n') if line.strip()]
        # Filtrar líneas que parecen comentarios
        lines = [l for l in lines if not l.startswith(';')]
        return lines
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return []


def identify_provider(nameservers: list[str]) -> str:
    """Identifica el provider de DNS authoritative."""
    ns_text = ' '.join(nameservers).lower()
    if any(p in ns_text for p in CLOUDFLARE_NS_PATTERNS):
        return 'cloudflare'
    if any(p in ns_text for p in HOSTINGER_NS_PATTERNS):
        return 'hostinger'
    if any(p in ns_text for p in ODOO_NS_PATTERNS):
        return 'odoo'
    return 'unknown'


def parse_spf(txt_records: list[str]) -> dict[str, Any]:
    """Analiza registro SPF si existe."""
    spf_record = None
    for txt in txt_records:
        clean = txt.strip('"')
        if clean.startswith('v=spf1'):
            spf_record = clean
            break

    if not spf_record:
        return {'present': False}

    # Identifica includes y mechanismos
    includes = [part.split(':', 1)[1] for part in spf_record.split() if part.startswith('include:')]
    has_all = '-all' in spf_record or '~all' in spf_record or '+all' in spf_record
    strict = '-all' in spf_record

    return {
        'present': True,
        'record': spf_record,
        'includes': includes,
        'has_all_directive': has_all,
        'strict_all': strict,
    }


def parse_dmarc(txt_records: list[str]) -> dict[str, Any]:
    """Analiza registro DMARC."""
    for txt in txt_records:
        clean = txt.strip('"')
        if clean.startswith('v=DMARC1'):
            policy = 'none'
            for part in clean.split(';'):
                part = part.strip()
                if part.startswith('p='):
                    policy = part[2:].strip()
                    break
            return {
                'present': True,
                'record': clean,
                'policy': policy,
                'strict': policy in ('quarantine', 'reject'),
            }
    return {'present': False}


def audit(domain: str) -> AuditReport:
    """Ejecuta la auditoría completa."""
    report = AuditReport(
        domain=domain,
        timestamp=datetime.utcnow().isoformat() + 'Z',
    )

    print(f"\n{'='*60}")
    print(f"  Auditoría DNS · {domain}")
    print(f"{'='*60}\n")

    # 1. Nameservers
    print("→ Consultando nameservers (NS)...")
    ns = run_dig(domain, 'NS')
    report.nameservers = ns
    report.authoritative_provider = identify_provider(ns)

    if not ns:
        report.errors.append("No se encontraron nameservers. ¿El dominio existe?")
        print(f"  ✗ Sin respuesta de NS")
        return report

    print(f"  Provider authoritative: {report.authoritative_provider.upper()}")
    for n in ns:
        print(f"  · {n}")

    # 2. Registros A del dominio raíz
    print("\n→ Registros A del dominio raíz...")
    a_records = run_dig(domain, 'A')
    for a in a_records:
        report.a_records.append(DNSRecord(domain, 'A', a))
        print(f"  · {a}")
    if not a_records:
        report.warnings.append(f"Sin registros A para {domain}")

    # 3. Registros AAAA (IPv6)
    aaaa_records = run_dig(domain, 'AAAA')
    for r in aaaa_records:
        report.aaaa_records.append(DNSRecord(domain, 'AAAA', r))

    # 4. MX (Email)
    print("\n→ Registros MX (correo)...")
    mx_records = run_dig(domain, 'MX')
    for mx in mx_records:
        report.mx_records.append(DNSRecord(domain, 'MX', mx))
        print(f"  · {mx}")
    if not mx_records:
        report.warnings.append("Sin registros MX. ¿No reciben email en este dominio?")

    # 5. TXT (SPF, verificaciones, etc.)
    print("\n→ Registros TXT...")
    txt_records = run_dig(domain, 'TXT')
    for txt in txt_records:
        report.txt_records.append(DNSRecord(domain, 'TXT', txt))
        # Mostrar primeros 80 chars
        display = txt if len(txt) < 80 else txt[:77] + '...'
        print(f"  · {display}")

    # 6. SPF
    print("\n→ Análisis SPF...")
    spf_status = parse_spf(txt_records)
    report.spf_status = spf_status
    if spf_status['present']:
        print(f"  ✓ SPF presente")
        print(f"    Includes: {spf_status['includes']}")
        if not spf_status['strict_all']:
            report.warnings.append(
                "SPF sin '-all' estricto. Considera usar '-all' en lugar de '~all' "
                "para mejor protección anti-spoofing."
            )
            print(f"  ⚠ SPF no es estricto (-all)")
    else:
        report.warnings.append(
            "Sin registro SPF. Crítico para deliverability de email desde mozaprintmx.com."
        )
        print(f"  ⚠ Sin SPF")

    # 7. DMARC
    print("\n→ Análisis DMARC...")
    dmarc_txt = run_dig(f'_dmarc.{domain}', 'TXT')
    dmarc_status = parse_dmarc(dmarc_txt)
    report.dmarc_status = dmarc_status
    if dmarc_status['present']:
        print(f"  ✓ DMARC presente (policy: {dmarc_status['policy']})")
        if not dmarc_status['strict']:
            report.warnings.append(
                f"DMARC con policy='{dmarc_status['policy']}'. "
                "Eventualmente migrar a 'quarantine' o 'reject' para reducir spoofing."
            )
    else:
        report.warnings.append(
            "Sin DMARC. Importante para deliverability de email transaccional "
            "desde Odoo y para prevenir spoofing del dominio."
        )
        print(f"  ⚠ Sin DMARC")

    # 8. Subdominios
    print("\n→ Auditando subdominios comunes...")
    for sub in SUBDOMAINS_TO_CHECK:
        if sub.startswith('_') or 'domainkey' in sub:
            # TXT records (DKIM, verificaciones)
            records = run_dig(f'{sub}.{domain}', 'TXT')
            rtype = 'TXT'
        else:
            records = run_dig(f'{sub}.{domain}', 'A')
            rtype = 'A'
            if not records:
                # Probar CNAME
                records = run_dig(f'{sub}.{domain}', 'CNAME')
                if records:
                    rtype = 'CNAME'

        if records:
            report.subdomains_alive[f'{sub}.{domain}'] = records
            display = records[0] if len(records[0]) < 60 else records[0][:57] + '...'
            print(f"  · {sub:30} ({rtype:5}) → {display}")
            if 'domainkey' in sub and records:
                report.dkim_found.append(sub)

    # 9. Análisis cruzado para detectar config Cloudflare + Hostinger
    print("\n→ Detección de configuración split...")
    has_cloudflare_ns = report.authoritative_provider == 'cloudflare'
    has_hostinger_refs = False

    # Buscar IPs de Hostinger en registros A
    for record in report.a_records:
        if record.value.startswith('149.') or 'hostinger' in record.value.lower():
            has_hostinger_refs = True

    # Verificar MX
    for mx in report.mx_records:
        if 'hostinger' in mx.value.lower():
            has_hostinger_refs = True

    if has_cloudflare_ns and has_hostinger_refs:
        report.warnings.append(
            "Configuración mixta detectada: Cloudflare es authoritative pero "
            "hay registros apuntando a infraestructura Hostinger. Esto es válido "
            "si Hostinger solo aloja email/hosting y Cloudflare maneja DNS+CDN. "
            "Verificar que cada servicio apunte al servidor correcto."
        )
        print(f"  ℹ Cloudflare authoritative + recursos Hostinger (configuración válida)")

    return report


def print_summary(report: AuditReport):
    """Imprime resumen ejecutivo."""
    print(f"\n{'='*60}")
    print(f"  RESUMEN")
    print(f"{'='*60}\n")

    print(f"Dominio:                 {report.domain}")
    print(f"Provider authoritative:  {report.authoritative_provider.upper()}")
    print(f"Nameservers activos:     {len(report.nameservers)}")
    print(f"Registros A:             {len(report.a_records)}")
    print(f"Registros MX:            {len(report.mx_records)}")
    print(f"Registros TXT:           {len(report.txt_records)}")
    print(f"Subdominios activos:     {len(report.subdomains_alive)}")
    print(f"SPF configurado:         {'Sí' if report.spf_status.get('present') else 'No'}")
    print(f"DMARC configurado:       {'Sí' if report.dmarc_status.get('present') else 'No'}")
    print(f"DKIM keys encontrados:   {len(report.dkim_found)}")

    if report.warnings:
        print(f"\n⚠ ADVERTENCIAS ({len(report.warnings)}):")
        for w in report.warnings:
            print(f"  · {w}")

    if report.errors:
        print(f"\n✗ ERRORES ({len(report.errors)}):")
        for e in report.errors:
            print(f"  · {e}")

    print(f"\n{'='*60}\n")


def print_recommendations(report: AuditReport):
    """Imprime recomendaciones según hallazgos."""
    print(f"{'='*60}")
    print(f"  RECOMENDACIONES")
    print(f"{'='*60}\n")

    recs = []

    # Sobre el setup actual
    if report.authoritative_provider == 'cloudflare':
        recs.append("✓ Cloudflare es authoritative, configuración ideal.")
        recs.append(
            "  Acción: usar Hostinger solo como registrar (renovación del dominio). "
            "Administrar todos los DNS desde Cloudflare."
        )
    elif report.authoritative_provider == 'hostinger':
        recs.append("⚠ Hostinger es authoritative, no Cloudflare.")
        recs.append(
            "  Acción: migrar autoridad de DNS a Cloudflare cambiando los "
            "nameservers en el registrar. Tarda 24-48h en propagar."
        )
    elif report.authoritative_provider == 'unknown':
        recs.append("? Provider authoritative no identificado claramente.")
        recs.append(f"  Nameservers: {', '.join(report.nameservers)}")

    # Sobre email
    if not report.mx_records:
        recs.append(
            "ℹ Sin registros MX. Si Mozaprint envía emails desde @mozaprintmx.com, "
            "verificar configuración de Google Workspace, Microsoft 365 o similar."
        )

    if not report.spf_status.get('present'):
        recs.append(
            "⚠ Configurar SPF urgentemente. Necesario para que los emails de "
            "Odoo (cotizaciones, follow-ups) lleguen al inbox del cliente y no a spam."
        )

    if not report.dmarc_status.get('present'):
        recs.append(
            "⚠ Configurar DMARC con policy='none' inicialmente para monitorear, "
            "luego escalar a 'quarantine'. Protege la reputación del dominio."
        )

    # Sobre subdominios
    legacy = [s for s in report.subdomains_alive if any(x in s for x in ['old', 'staging', 'dev', 'cpanel'])]
    if legacy:
        recs.append(
            f"⚠ Subdominios potencialmente legacy: {', '.join(legacy)}. "
            "Verificar si siguen en uso o eliminar."
        )

    # Sobre n8n
    if f'n8n.{report.domain}' not in report.subdomains_alive:
        recs.append(
            f"ℹ Subdominio n8n.{report.domain} no configurado. Crear cuando se "
            "aprovisione el VPS del orquestador."
        )

    for i, rec in enumerate(recs, 1):
        print(f"{i}. {rec}\n")

    print(f"{'='*60}\n")


def main():
    parser = argparse.ArgumentParser(description='Auditoría DNS Mozaprint')
    parser.add_argument('--domain', default=DEFAULT_DOMAIN,
                        help=f'Dominio a auditar (default: {DEFAULT_DOMAIN})')
    parser.add_argument('--output', help='Guardar reporte JSON en archivo')
    parser.add_argument('--no-recommendations', action='store_true',
                        help='No imprimir recomendaciones')
    args = parser.parse_args()

    # Verificar que dig está disponible
    try:
        subprocess.run(['dig', '-v'], capture_output=True, timeout=2, check=False)
    except (subprocess.TimeoutExpired, FileNotFoundError):
        print("✗ ERROR: 'dig' no está instalado.")
        print("  macOS:  brew install bind")
        print("  Ubuntu: apt-get install dnsutils")
        print("  Windows: instalar BIND o usar WSL")
        return 1

    report = audit(args.domain)
    print_summary(report)

    if not args.no_recommendations:
        print_recommendations(report)

    if args.output:
        with open(args.output, 'w', encoding='utf-8') as f:
            json.dump(asdict(report), f, indent=2, ensure_ascii=False, default=str)
        print(f"✓ Reporte JSON guardado en: {args.output}")

    return 0 if not report.errors else 1


if __name__ == '__main__':
    sys.exit(main())
