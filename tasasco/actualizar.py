"""Actualización incremental de los datos en data/.

Primera corrida: descarga el histórico (CDT desde 2022, crédito desde jul-2022, TRM desde 1991).
Corridas siguientes: solo las últimas semanas, reemplazando fechas que la fuente haya corregido.
Escribe después de cada mes descargado, así una corrida interrumpida retoma donde quedó.
"""
from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path

from . import almacen, fuentes
from .soda import Soda

INICIO_CDT = date(2022, 1, 1)
CAMPOS_CDT = ["fecha", "tipo_entidad", "codigo_entidad", "entidad", "plazo_dias", "tasa_ea", "monto"]
ORDEN_CDT = ["fecha", "codigo_entidad", "plazo_dias"]
CAMPOS_CREDITO = ["fecha", "tipo_entidad", "codigo_entidad", "entidad", "tipo_credito", "producto",
                  "tasa_ea", "monto", "creditos"]
ORDEN_CREDITO = ["fecha", "tipo_credito", "producto", "codigo_entidad"]


def log(msg: str) -> None:
    print(msg, flush=True)


def actualizar_cdt(soda: Soda, data: Path, hoy: date) -> None:
    carpeta = data / "cdt"
    ultima = almacen.max_fecha(carpeta)
    desde = date.fromisoformat(ultima) - timedelta(days=10) if ultima else INICIO_CDT
    for a, b in fuentes.meses(desde, hoy):
        filas = fuentes.descargar_cdt(soda, a, b)
        n = almacen.fusionar(carpeta, filas, CAMPOS_CDT, ORDEN_CDT, "mes")
        log(f"CDT {a}..{b}: {n} filas")


def actualizar_credito(soda: Soda, data: Path, hoy: date) -> None:
    carpeta = data / "credito"
    ultima = almacen.max_fecha(carpeta)
    hist_max = fuentes.max_fecha_credito(soda, fuentes.CREDITO_HISTORICO)
    if ultima:
        desde = date.fromisoformat(ultima) - timedelta(days=21)
    else:
        desde = fuentes.min_fecha_credito(soda, fuentes.CREDITO_HISTORICO) or date(2022, 7, 1)
    for a, b in fuentes.meses(desde, hoy):
        # El histórico llega hasta hist_max; lo posterior está en el dataset de los últimos dos meses
        tramos = []
        if hist_max and a <= hist_max:
            tramos.append((fuentes.CREDITO_HISTORICO, a, min(b, hist_max)))
        if not hist_max or b > hist_max:
            tramos.append((fuentes.CREDITO_RECIENTE, max(a, (hist_max or a) + timedelta(days=1)), b))
        for dataset, x, y in tramos:
            if x > y:
                continue
            filas = fuentes.descargar_credito(soda, dataset, x, y)
            n = almacen.fusionar(carpeta, filas, CAMPOS_CREDITO, ORDEN_CREDITO, "anio")
            log(f"Crédito {dataset} {x}..{y}: {n} filas")


def actualizar_trm(soda: Soda, data: Path) -> None:
    ruta = data / "trm.csv"
    existentes = almacen.leer(ruta)
    ultima = max((f["fecha"] for f in existentes), default=None)
    desde = date.fromisoformat(ultima) - timedelta(days=15) if ultima else date(1991, 1, 1)
    nuevas = fuentes.descargar_trm(soda, desde)
    fechas = {f["fecha"] for f in nuevas}
    filas = [f for f in existentes if f["fecha"] not in fechas] + nuevas
    almacen.escribir(ruta, filas, ["fecha", "hasta", "trm"], ["fecha"])
    log(f"TRM: {len(nuevas)} filas nuevas o revisadas, {len(filas)} en total")


def actualizar_tibc(soda: Soda, data: Path) -> None:
    filas = fuentes.descargar_tibc(soda)
    almacen.escribir(data / "tibc.csv", filas, ["desde", "hasta", "modalidad", "ibc_ea", "usura_ea", "resolucion"],
                     ["desde", "modalidad"])
    log(f"Interés bancario corriente: {len(filas)} resoluciones")


def actualizar(data: Path, solo: set[str] | None = None, hoy: date | None = None) -> None:
    hoy = hoy or date.today()
    soda = Soda()
    pasos = {"trm": lambda: actualizar_trm(soda, data), "tibc": lambda: actualizar_tibc(soda, data),
             "cdt": lambda: actualizar_cdt(soda, data, hoy), "credito": lambda: actualizar_credito(soda, data, hoy)}
    errores = []
    for nombre, paso in pasos.items():
        if solo and nombre not in solo:
            continue
        try:
            paso()
        except Exception as e:  # una fuente caída no debe tumbar las demás
            errores.append(f"{nombre}: {e}")
            log(f"::error::Falló {nombre}: {e}")
    if errores:
        raise SystemExit("Fuentes con error: " + "; ".join(errores))

