"""Cliente mínimo para la API SODA de datos.gov.co (Socrata)."""
from __future__ import annotations

import os
import time
from typing import Any

import requests

BASE = "https://www.datos.gov.co/resource/{dataset}.json"


class Soda:
    def __init__(self, app_token: str | None = None, timeout: int = 180, pausa: float = 0.5):
        self.s = requests.Session()
        token = app_token if app_token is not None else os.getenv("SOCRATA_APP_TOKEN")
        if token:
            self.s.headers["X-App-Token"] = token
        self.s.headers["User-Agent"] = "tasas-co (+https://github.com/juanjo32/tasas-co)"
        self.timeout = timeout
        self.pausa = pausa

    def consultar(self, dataset: str, params: dict[str, str], reintentos: int = 4) -> list[dict[str, Any]]:
        url = BASE.format(dataset=dataset)
        ultimo: Exception | None = None
        for intento in range(reintentos):
            try:
                r = self.s.get(url, params=params, timeout=self.timeout)
                if r.status_code in (429, 500, 502, 503, 504):
                    raise requests.HTTPError(f"{r.status_code}: {r.text[:200]}")
                r.raise_for_status()
                time.sleep(self.pausa)
                return r.json()
            except (requests.RequestException, ValueError) as e:
                ultimo = e
                time.sleep(5 * (intento + 1))
        raise RuntimeError(f"Fallo consultando {dataset}: {ultimo}")

    def paginar(self, dataset: str, params: dict[str, str], pagina: int = 50000) -> list[dict[str, Any]]:
        filas: list[dict[str, Any]] = []
        offset = 0
        while True:
            p = dict(params, **{"$limit": str(pagina), "$offset": str(offset)})
            lote = self.consultar(dataset, p)
            filas.extend(lote)
            if len(lote) < pagina:
                return filas
            offset += pagina
