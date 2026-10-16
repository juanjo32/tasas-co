"""Descarga y normaliza las fuentes oficiales (Superintendencia Financiera vía datos.gov.co).

Todas las funciones devuelven listas de dicts con nombres de campo propios, estables y en español.
"""
from __future__ import annotations

from datetime import date, timedelta
from typing import Any, Iterable

from .soda import Soda

# Datasets en datos.gov.co (todos publicados por la Superintendencia Financiera)
CDT_DATASET = "axk9-g2nh"            # Tasas de captación y operaciones del mercado monetario (diario)
CREDITO_HISTORICO = "w9zh-vetq"      # Tasas activas por tipo de crédito – Histórico (semanal, desde jul-2022)
CREDITO_RECIENTE = "qzsc-9esp"       # Tasas activas por tipo de crédito – Últimos dos meses
TRM_DATASET = "32sa-8pi3"            # TRM diaria desde 1991
TIBC_DATASET = "pare-7x5i"           # Tasa de interés bancario corriente (base de la usura)

# CDT: unidad de captura 1 = emisiones de CDT. Subcuentas con plazo exacto.
CDT_PLAZOS = {10: 30, 50: 60, 70: 90, 90: 120, 110: 180, 130: 360, 140: 361}  # 361 = más de 360 días

TIPOS_ENTIDAD = {
    1: "Banco",
    2: "Corporación financiera",
    4: "Compañía de financiamiento",
    22: "Institución oficial especial",
    32: "Cooperativa financiera",
}


def _num(v: Any) -> float | None:
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _fecha(v: Any) -> str:
    return str(v or "")[:10]


def _lit(v: str) -> str:
    return "'" + str(v).replace("'", "''") + "'"


def _lim(d: date) -> str:
    return d.strftime("%Y-%m-%dT00:00:00")


# --------------------------------------------------------------------------- CDT

def descargar_cdt(soda: Soda, desde: date, hasta: date) -> list[dict[str, Any]]:
    """Tasa efectiva anual y monto de los CDT emitidos cada día, por entidad y plazo."""
    subcuentas = ", ".join(str(s) for s in CDT_PLAZOS)
    params = {
        "$select": "fechacorte, tipoentidad, codigoentidad, nombreentidad, subcuenta, tasa, monto",
        "$where": (f"uca = 1 AND subcuenta in ({subcuentas}) AND fechacorte >= {_lit(_lim(desde))} "
                   f"AND fechacorte < {_lit(_lim(hasta + timedelta(days=1)))}"),
        "$order": "fechacorte, codigoentidad, subcuenta",
    }
    salida = []
    for r in soda.paginar(CDT_DATASET, params):
        tasa, monto = _num(r.get("tasa")), _num(r.get("monto"))
        if tasa is None or tasa <= 0:
            continue
        tipo = int(_num(r.get("tipoentidad")) or 0)
        salida.append({
            "fecha": _fecha(r.get("fechacorte")),
            "tipo_entidad": TIPOS_ENTIDAD.get(tipo, f"Tipo {tipo}"),
            "codigo_entidad": f"{tipo}-{int(_num(r.get('codigoentidad')) or 0)}",
            "entidad": limpiar_entidad(r.get("nombreentidad")),
            "plazo_dias": CDT_PLAZOS[int(_num(r.get("subcuenta")) or 0)],
            "tasa_ea": round(tasa, 4),
            "monto": round(monto or 0.0, 2),
        })
    return salida


# --------------------------------------------------------------------------- Crédito

def descargar_credito(soda: Soda, dataset: str, desde: date, hasta: date) -> list[dict[str, Any]]:
    """Tasa efectiva anual promedio ponderada por monto desembolsado, por semana, entidad y producto.

    El dataset original trae ~900.000 filas por semana (por sexo, municipio, CIIU, etc.).
    La agregación se hace en el servidor para bajar ~1.000 filas por semana.
    """
    params = {
        "$select": ("fecha_corte, tipo_entidad, codigo_entidad, nombre_entidad, tipo_de_cr_dito, producto_de_cr_dito, "
                    "sum(montos_desembolsados) as monto, sum(numero_de_creditos) as creditos, "
                    "sum(tasa_efectiva_promedio * montos_desembolsados) as tasa_x_monto"),
        "$where": (f"fecha_corte >= {_lit(_lim(desde))} AND fecha_corte < {_lit(_lim(hasta + timedelta(days=1)))} "
                   "AND montos_desembolsados > 0"),
        "$group": "fecha_corte, tipo_entidad, codigo_entidad, nombre_entidad, tipo_de_cr_dito, producto_de_cr_dito",
        "$order": "fecha_corte, codigo_entidad",
    }
    salida = []
    for r in soda.paginar(dataset, params):
        monto, txm = _num(r.get("monto")), _num(r.get("tasa_x_monto"))
        if not monto or txm is None:
            continue
        tipo = int(_num(r.get("tipo_entidad")) or 0)
        salida.append({
            "fecha": _fecha(r.get("fecha_corte")),
            "tipo_entidad": TIPOS_ENTIDAD.get(tipo, f"Tipo {tipo}"),
            "codigo_entidad": f"{tipo}-{int(_num(r.get('codigo_entidad')) or 0)}",
            "entidad": limpiar_entidad(r.get("nombre_entidad")),
            "tipo_credito": str(r.get("tipo_de_cr_dito") or "").strip(),
            "producto": str(r.get("producto_de_cr_dito") or "").strip(),
            "tasa_ea": round(txm / monto, 4),
            "monto": round(monto, 2),
            "creditos": int(_num(r.get("creditos")) or 0),
        })
    return salida


def max_fecha_credito(soda: Soda, dataset: str) -> date | None:
    r = soda.consultar(dataset, {"$select": "max(fecha_corte) as b"})
    v = r[0].get("b") if r else None
    return date.fromisoformat(v[:10]) if v else None


def min_fecha_credito(soda: Soda, dataset: str) -> date | None:
    r = soda.consultar(dataset, {"$select": "min(fecha_corte) as a"})
    v = r[0].get("a") if r else None
    return date.fromisoformat(v[:10]) if v else None


# --------------------------------------------------------------------------- TRM y usura

def descargar_trm(soda: Soda, desde: date) -> list[dict[str, Any]]:
    params = {"$select": "valor, vigenciadesde, vigenciahasta",
              "$where": f"vigenciadesde >= {_lit(_lim(desde))}", "$order": "vigenciadesde"}
    salida = []
    for r in soda.paginar(TRM_DATASET, params):
        v = _num(r.get("valor"))
        if v:
            salida.append({"fecha": _fecha(r.get("vigenciadesde")), "hasta": _fecha(r.get("vigenciahasta")),
                           "trm": round(v, 2)})
    return salida


def descargar_tibc(soda: Soda) -> list[dict[str, Any]]:
    """Interés bancario corriente certificado por la Superfinanciera. La usura es 1,5 veces este valor."""
    salida = []
    for r in soda.paginar(TIBC_DATASET, {"$order": "vigencia_desde"}):
        v = _num(str(r.get("interes_bancario_corriente") or "").replace("%", "").replace(",", ".").strip())
        if v is None:
            continue
        salida.append({
            "desde": _fecha(r.get("vigencia_desde")),
            "hasta": _fecha(r.get("vigencia_hasta")),
            "modalidad": str(r.get("modalidad") or "").strip().upper(),
            "ibc_ea": round(v, 4),
            "usura_ea": round(v * 1.5, 4),
            "resolucion": str(r.get("resolucion") or "").strip(),
        })
    return salida


# --------------------------------------------------------------------------- utilidades

_SUFIJOS = (" S.A.S.", " S.A.S", " S.A.", " S.A", " S. A.", " SA")
_SIGLAS = {"BBVA", "GNB", "AV", "CF", "BCSC", "ITAU", "IRIS", "JP", "MIBANCO", "LULO", "NU", "RCI", "GM", "CFA"}
_MENORES = {"DE", "LA", "LAS", "EL", "DEL", "LOS", "Y", "E"}


def limpiar_entidad(nombre: Any) -> str:
    """'Banco de Bogotá S.A.' -> 'Banco de Bogotá'; 'BANCO CONTACTAR S.A.' -> 'Banco Contactar'."""
    n = " ".join(str(nombre or "").split()).strip(" ,")
    for suf in _SUFIJOS:
        if n.upper().endswith(suf):
            n = n[: -len(suf)]
            break
    n = n.strip(" .,")
    if n.isupper():
        palabras = []
        for i, p in enumerate(n.split()):
            limpio = p.strip(".")
            if limpio in _SIGLAS:
                palabras.append(limpio if limpio not in {"MIBANCO", "LULO", "IRIS"} else limpio.capitalize())
            elif i > 0 and limpio in _MENORES:
                palabras.append(limpio.lower())
            else:
                palabras.append(limpio.capitalize())
        n = " ".join(palabras)
    return n


def meses(desde: date, hasta: date) -> Iterable[tuple[date, date]]:
    """Ventanas mensuales [inicio, fin] para descargas largas sin timeouts."""
    actual = date(desde.year, desde.month, 1)
    while actual <= hasta:
        sig = date(actual.year + (actual.month == 12), actual.month % 12 + 1, 1)
        yield max(actual, desde), min(sig - timedelta(days=1), hasta)
        actual = sig
