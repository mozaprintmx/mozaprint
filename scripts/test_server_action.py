#!/usr/bin/env python3
"""
Test runner para Server Actions de Odoo.

Permite simular la ejecución de un Server Action local antes de copiarlo
a Odoo, validando lógica y errores comunes con datos de prueba.

NOTA: Esto NO ejecuta dentro de Odoo. Simula el environment con mocks
básicos para validar que el código Python sandbox no tenga errores
obvios (imports prohibidos, sintaxis, lógica).

Uso:
    python test_server_action.py \
        --action ai_handle_whatsapp_message \
        --input test/messages/sample_new_customer.json

    python test_server_action.py --list  # listar actions disponibles
"""

import argparse
import json
import sys
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock


# Whitelist conservadora de imports permitidos en Odoo Online sandbox
ALLOWED_IMPORTS = {
    'datetime', 'json', 're', 'math', 'time',
    'dateutil', 'dateutil.relativedelta',
    'collections', 'itertools', 'functools',
}


class OdooEnvironmentMock:
    """Mock básico de env de Odoo para test local."""

    def __init__(self, fixtures: dict[str, list[dict]]):
        self._fixtures = fixtures
        self._models = {}

    def __getitem__(self, model_name: str):
        """env['model.name'] devuelve un MockRecordset."""
        if model_name not in self._models:
            self._models[model_name] = MockRecordset(
                model_name,
                self._fixtures.get(model_name, []),
            )
        return self._models[model_name]

    def ref(self, xml_id: str):
        """Mock de env.ref para referencias XML."""
        mock = MagicMock()
        mock.id = hash(xml_id) % 10000
        mock.name = xml_id
        return mock


class MockRecordset:
    """Mock de un recordset de Odoo."""

    def __init__(self, model_name: str, fixtures: list[dict]):
        self.model_name = model_name
        self._fixtures = fixtures
        self._created_records = []

    def search(self, domain: list, limit: int | None = None,
               order: str | None = None) -> 'MockRecordset':
        """Implementación naïve: ignora dominio en mock, devuelve todo."""
        result = MockRecordset(self.model_name, self._fixtures.copy())
        if limit:
            result._fixtures = result._fixtures[:limit]
        return result

    def search_read(self, domain: list, fields: list,
                    limit: int | None = None) -> list[dict]:
        records = self._fixtures.copy()
        if limit:
            records = records[:limit]
        # Filtrar fields
        return [{f: r.get(f) for f in fields} for r in records]

    def create(self, vals: dict | list[dict]):
        """Crea un mock record."""
        if isinstance(vals, dict):
            vals = [vals]
        new_records = []
        for v in vals:
            record = MagicMock()
            record.id = len(self._created_records) + 1000
            for key, value in v.items():
                setattr(record, key, value)
            new_records.append(record)
            self._created_records.append(v)
        return new_records[0] if len(new_records) == 1 else new_records

    def browse(self, ids):
        if isinstance(ids, int):
            ids = [ids]
        records = []
        for record_id in ids:
            for fixture in self._fixtures:
                if fixture.get('id') == record_id:
                    record = MagicMock()
                    for key, value in fixture.items():
                        setattr(record, key, value)
                    records.append(record)
                    break
        return records[0] if len(records) == 1 else records

    def __iter__(self):
        for fixture in self._fixtures:
            record = MagicMock()
            for key, value in fixture.items():
                setattr(record, key, value)
            yield record

    def __len__(self):
        return len(self._fixtures)


def check_sandbox_safety(code: str) -> list[str]:
    """Verifica que el código no usa imports/builtins prohibidos."""
    issues = []
    import ast
    try:
        tree = ast.parse(code)
    except SyntaxError as e:
        return [f"Error de sintaxis: {e}"]

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                base = alias.name.split('.')[0]
                if base not in ALLOWED_IMPORTS:
                    issues.append(
                        f"Import '{alias.name}' NO permitido en sandbox Odoo Online"
                    )
        elif isinstance(node, ast.ImportFrom):
            base = (node.module or '').split('.')[0]
            if base not in ALLOWED_IMPORTS:
                issues.append(
                    f"from {node.module} NO permitido en sandbox Odoo Online"
                )

        # Detectar uso de builtins peligrosos
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
            if node.func.id in ('exec', 'eval', 'compile', '__import__', 'open'):
                issues.append(
                    f"Uso de '{node.func.id}()' NO permitido en sandbox"
                )

    return issues


def run_action(action_path: Path, input_data: dict, fixtures: dict) -> Any:
    """Carga el código del action y lo ejecuta con mocks."""
    code = action_path.read_text(encoding='utf-8')

    # Validación de sandbox
    issues = check_sandbox_safety(code)
    if issues:
        print("⚠ Issues de sandbox detectados:")
        for issue in issues:
            print(f"  - {issue}")
        print()

    # Preparar environment
    env = OdooEnvironmentMock(fixtures)

    # Mock record para el trigger
    record = MagicMock()
    for key, value in input_data.get('record', {}).items():
        setattr(record, key, value)

    # Logger mock
    _logger = MagicMock()
    _logger.info = lambda msg, *args: print(f"  [INFO] {msg % args if args else msg}")
    _logger.warning = lambda msg, *args: print(f"  [WARN] {msg % args if args else msg}")
    _logger.error = lambda msg, *args: print(f"  [ERROR] {msg % args if args else msg}")

    # Variables disponibles en sandbox Odoo
    sandbox_globals = {
        'env': env,
        'record': record,
        'records': [record],
        'model': env[input_data.get('model', 'mail.message')],
        '_logger': _logger,
        'datetime': __import__('datetime'),
        'json': json,
        're': __import__('re'),
        'math': __import__('math'),
        'time': __import__('time'),
    }

    print(f"→ Ejecutando {action_path.name}...")
    print(f"  Input: {input_data.get('model', 'N/A')} record id={getattr(record, 'id', None)}")
    print()

    try:
        exec(code, sandbox_globals)
        print()
        print("✓ Ejecución completada sin excepciones")

        # Si el action devuelve algo, capturarlo (Odoo expone `action` como var de retorno)
        if 'action' in sandbox_globals:
            print(f"  Retorno: {json.dumps(sandbox_globals['action'], indent=2, default=str)}")

        return sandbox_globals
    except Exception as e:
        print()
        print(f"✗ Error en ejecución: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
        return None


def main():
    parser = argparse.ArgumentParser(description='Test runner de Server Actions')
    parser.add_argument('--action', help='Nombre del archivo .py del action')
    parser.add_argument('--input', help='Archivo JSON con input de prueba')
    parser.add_argument('--fixtures', default='test/fixtures.json',
                        help='Archivo JSON con fixtures de modelos')
    parser.add_argument('--list', action='store_true', help='Listar actions disponibles')
    parser.add_argument('--actions-dir', default='odoo-extensions/server-actions',
                        help='Directorio con Server Actions')
    args = parser.parse_args()

    actions_dir = Path(args.actions_dir)

    if args.list or not args.action:
        print("Server Actions disponibles:")
        if actions_dir.exists():
            for f in sorted(actions_dir.glob('*.py')):
                print(f"  - {f.stem}")
        else:
            print(f"  (directorio {actions_dir} no existe aún)")
        return 0

    # Resolver action
    action_path = actions_dir / f"{args.action}.py"
    if not action_path.exists():
        print(f"✗ Action no encontrado: {action_path}", file=sys.stderr)
        return 1

    # Cargar input
    if args.input:
        input_path = Path(args.input)
        if not input_path.exists():
            print(f"✗ Input no encontrado: {input_path}", file=sys.stderr)
            return 1
        input_data = json.loads(input_path.read_text())
    else:
        input_data = {}

    # Cargar fixtures
    fixtures_path = Path(args.fixtures)
    if fixtures_path.exists():
        fixtures = json.loads(fixtures_path.read_text())
    else:
        print(f"⚠ Sin fixtures ({fixtures_path}), usando vacíos")
        fixtures = {}

    result = run_action(action_path, input_data, fixtures)
    return 0 if result else 1


if __name__ == '__main__':
    sys.exit(main())
