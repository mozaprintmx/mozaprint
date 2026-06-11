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

    def call(
        self,
        model: str,
        method: str,
        payload: dict[str, Any] | None = None,
    ) -> Any:
        """Llamada genérica a /json2/{model}/{method}."""
        response = requests.post(
            f'{self.url}/json2/{model}/{method}',
            headers=self.headers,
            json=payload or {},
            timeout=60,
        )
        response.raise_for_status()
        data = response.json()
        if 'error' in data:
            raise RuntimeError(f'Odoo error en {model}/{method}: {data["error"]}')
        return data.get('result', data)

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

        response = requests.post(
            f'{self.url}/json2/{model}/search_read',
            headers=self.headers,
            json=payload,
            timeout=60,
        )
        response.raise_for_status()
        data = response.json()
        if 'error' in data:
            raise RuntimeError(f'Odoo error en {model}/search_read: {data["error"]}')
        return data.get('result', [])

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
