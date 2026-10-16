"""Almacenamiento en CSV particionado, pensado para git.

- Una partición por mes (CDT, diario) o por año (crédito, semanal).
- Las filas se reemplazan por fecha: si llega de nuevo un día, se sustituye completo (la fuente a veces corrige).
- Orden estable: el diff de cada commit muestra solo las filas nuevas o corregidas.
"""
from __future__ import annotations

import csv
from collections import defaultdict
from pathlib import Path
from typing import Any, Iterable


def particion(fecha: str, granularidad: str) -> str:
    return fecha[:7] if granularidad == "mes" else fecha[:4]


def leer(ruta: Path) -> list[dict[str, str]]:
    if not ruta.exists():
        return []
    with ruta.open(encoding="utf-8", newline="") as fh:
        return list(csv.DictReader(fh))


def leer_carpeta(carpeta: Path) -> list[dict[str, str]]:
    filas: list[dict[str, str]] = []
    for ruta in sorted(carpeta.glob("*.csv")):
        filas.extend(leer(ruta))
    return filas


def escribir(ruta: Path, filas: Iterable[dict[str, Any]], campos: list[str], orden: list[str]) -> None:
    filas = sorted(filas, key=lambda f: tuple(str(f.get(c, "")) for c in orden))
    ruta.parent.mkdir(parents=True, exist_ok=True)
    with ruta.open("w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=campos, extrasaction="ignore", lineterminator="\n")
        w.writeheader()
        w.writerows(filas)


def fusionar(carpeta: Path, nuevas: list[dict[str, Any]], campos: list[str], orden: list[str],
             granularidad: str = "mes") -> int:
    """Inserta `nuevas` reemplazando por completo las fechas que traen. Devuelve filas escritas."""
    if not nuevas:
        return 0
    por_part: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for f in nuevas:
        por_part[particion(f["fecha"], granularidad)].append(f)
    total = 0
    for part, filas in por_part.items():
        ruta = carpeta / f"{part}.csv"
        fechas = {f["fecha"] for f in filas}
        existentes = [f for f in leer(ruta) if f["fecha"] not in fechas]
        escribir(ruta, existentes + filas, campos, orden)
        total += len(filas)
    return total


def max_fecha(carpeta: Path) -> str | None:
    archivos = sorted(carpeta.glob("*.csv"))
    for ruta in reversed(archivos):
        filas = leer(ruta)
        if filas:
            return max(f["fecha"] for f in filas)
    return None
