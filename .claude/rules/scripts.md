---
paths:
  - "scripts/**"
---

# Scripts ejecutables (Python completo, fuera del sandbox)

A diferencia de los Server Actions, aquí hay **Python completo** (`requests`,
etc.). Dependencias en `requirements.txt` en la raíz.

## Convenciones

- Type hints y docstring con bloques de "Uso" y "Variables de entorno
  necesarias" (ver `scripts/backup_catalog.py` como referencia de estilo).
- Secretos SIEMPRE por variable de entorno (`ODOO_URL`, `ODOO_API_KEY`,
  `ODOO_DATABASE`, ...), nunca hardcodeados, nunca en el repo.
- Cliente Odoo: JSON-2 API con paginación automática (patrón `search_read_all`
  de `backup_catalog.py`).

## Operaciones de riesgo

- **Backup del catálogo (`backup_catalog.py`) ANTES de cualquier sync masivo.**
- Migración de datos: incluir SIEMPRE un script de rollback.
- Cambios masivos de catálogo (> 10 productos): human-in-the-loop obligatorio.
