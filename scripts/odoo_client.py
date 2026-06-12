"""
Cliente JSON-2 de Odoo — módulo compartido.

Importar desde otros scripts en este mismo directorio:
    from odoo_client import OdooClient

Variables de entorno necesarias:
    ODOO_URL       https://mozaprint.odoo.com
    ODOO_API_KEY   ...
    ODOO_DATABASE  mozaprint-prod  (opcional)
"""

from typing import Any

import requests


class OdooClient:
    """Cliente mínimo para la JSON-2 API de Odoo."""

    def __init__(self, url: str, api_key: str, database: str | None = None):
        self.url = url.rstrip('/')
        self.headers = {
            'Authorization': f'Bearer {api_key}',
            'Content-Type': 'application/json',
        }
        if database:
            self.headers['DATABASE'] = database

    def _post(self, model: str, method: str, payload: dict[str, Any]) -> Any:
        """
        POST a /json/2/{model}/{method} y devuelve el resultado CRUDO.

        La JSON-2 API devuelve directamente el valor de retorno del método
        (una lista en search_read, un dict en fields_get, etc.), NO envuelto
        en {"result": ...}. Los errores llegan como status HTTP no-2xx, que
        raise_for_status() convierte en excepción.
        """
        response = requests.post(
            f'{self.url}/json/2/{model}/{method}',
            headers=self.headers,
            json=payload,
            timeout=60,
        )
        response.raise_for_status()
        data = response.json()
        # Respaldo: si la instancia envolviera un error en un 200.
        if isinstance(data, dict) and isinstance(data.get('error'), dict):
            raise RuntimeError(f'Odoo error en {model}/{method}: {data["error"]}')
        return data

    def call(
        self,
        model: str,
        method: str,
        payload: dict[str, Any] | None = None,
    ) -> Any:
        """Llamada genérica a /json/2/{model}/{method}."""
        return self._post(model, method, payload or {})

    def fields_get(
        self,
        model: str,
        attributes: list[str] | None = None,
    ) -> dict[str, Any]:
        """Devuelve metadatos de campos del modelo vía fields_get."""
        payload: dict[str, Any] = {}
        if attributes:
            payload['attributes'] = attributes
        return self.call(model, 'fields_get', payload)

    def search_read(
        self,
        model: str,
        domain: list | None = None,
        fields: list[str] | None = None,
        limit: int | None = None,
        offset: int = 0,
        context: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        """Llama a search_read y devuelve la lista de resultados."""
        payload: dict[str, Any] = {
            'domain': domain or [],
            'fields': fields or [],
            'offset': offset,
        }
        if limit is not None:
            payload['limit'] = limit
        if context:
            payload['context'] = context

        data = self._post(model, 'search_read', payload)
        return data if isinstance(data, list) else data.get('records', data)

    def search_read_all(
        self,
        model: str,
        domain: list | None = None,
        fields: list[str] | None = None,
        batch_size: int = 500,
        context: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        """Paginación automática hasta traer todos los registros."""
        results = []
        offset = 0
        while True:
            batch = self.search_read(model, domain, fields, batch_size, offset, context)
            results.extend(batch)
            if len(batch) < batch_size:
                break
            offset += batch_size
        return results

    # --- Escritura (usar con cuidado; los scripts deben ser idempotentes) ---

    def create(self, model: str, vals: dict[str, Any]) -> int:
        """
        Crea un registro y devuelve su id.

        JSON-2 / Odoo 19 usa model_create_multi: el método es create(vals_list)
        y devuelve la lista de ids creados. Verificado contra Odoo 2026-06-12.
        """
        result = self._post(model, 'create', {'vals_list': [vals]})
        # Devuelve lista de ids (p. ej. [42]); tolerar int o dict por robustez.
        if isinstance(result, list) and result:
            first = result[0]
            return first['id'] if isinstance(first, dict) else first
        if isinstance(result, int):
            return result
        if isinstance(result, dict) and 'id' in result:
            return result['id']
        raise RuntimeError(f'Respuesta inesperada de create({model}): {result!r}')

    def write(self, model: str, ids: list[int], vals: dict[str, Any]) -> bool:
        """Actualiza registros existentes. JSON-2: write(ids, vals)."""
        return self._post(model, 'write', {'ids': ids, 'vals': vals})

    def unlink(self, model: str, ids: list[int]) -> bool:
        """Elimina registros. JSON-2: unlink(ids)."""
        return self._post(model, 'unlink', {'ids': ids})
