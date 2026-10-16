"""Pruebas sin red. Las filas de ejemplo copian el formato real de datos.gov.co (oct-2026)."""
from __future__ import annotations

import json
from datetime import date, datetime
from pathlib import Path

import pytest

from tasasco import actualizar, almacen, construir, fuentes


class SodaFalsa:
    """Responde según el dataset; registra las consultas para revisarlas."""

    def __init__(self, respuestas: dict[str, list[dict]]):
        self.respuestas = respuestas
        self.consultas: list[tuple[str, dict]] = []

    def consultar(self, dataset, params, reintentos=3):
        self.consultas.append((dataset, params))
        if "max(fecha_corte)" in params.get("$select", ""):
            return [{"b": "2026-07-31T00:00:00.000"}]
        if "min(fecha_corte)" in params.get("$select", ""):
            return [{"a": "2026-07-03T00:00:00.000"}]
        return self.respuestas.get(dataset, [])

    def paginar(self, dataset, params, pagina=50000):
        return self.consultar(dataset, params)


CDT_REAL = [
    {"fechacorte": "2026-10-14T00:00:00.000", "tipoentidad": "1", "codigoentidad": "1", "nombreentidad": "Banco de Bogotá S.A.",
     "subcuenta": "130", "tasa": "12.84", "monto": "218458415"},
    {"fechacorte": "2026-10-14T00:00:00.000", "tipoentidad": "1", "codigoentidad": "60", "nombreentidad": "Banco Pichincha S.A.",
     "subcuenta": "130", "tasa": "13.39", "monto": "4787519.98"},
    {"fechacorte": "2026-10-14T00:00:00.000", "tipoentidad": "4", "codigoentidad": "117", "nombreentidad": "Credifamilia",
     "subcuenta": "70", "tasa": "9", "monto": "7822.21"},
    {"fechacorte": "2026-10-14T00:00:00.000", "tipoentidad": "1", "codigoentidad": "1", "nombreentidad": "Banco de Bogotá S.A.",
     "subcuenta": "130", "tasa": "0", "monto": "0"},  # tasa 0: se descarta
]

CREDITO_REAL = [
    {"fecha_corte": "2026-10-02T00:00:00.000", "tipo_entidad": "1", "codigo_entidad": "7", "nombre_entidad": "Bancolombia S.A.",
     "tipo_de_cr_dito": "Consumo", "producto_de_cr_dito": "Libre inversión", "monto": "1000", "creditos": "10",
     "tasa_x_monto": "22000"},
]


def test_descargar_cdt_normaliza():
    soda = SodaFalsa({fuentes.CDT_DATASET: CDT_REAL})
    filas = fuentes.descargar_cdt(soda, date(2026, 10, 14), date(2026, 10, 14))
    assert len(filas) == 3
    assert filas[0] == {"fecha": "2026-10-14", "tipo_entidad": "Banco", "codigo_entidad": "1-1",
                        "entidad": "Banco de Bogotá", "plazo_dias": 360, "tasa_ea": 12.84, "monto": 218458415.0}
    where = soda.consultas[0][1]["$where"]
    assert "uca = 1" in where and "fechacorte < '2026-10-15T00:00:00'" in where


def test_descargar_credito_pondera_en_servidor():
    soda = SodaFalsa({fuentes.CREDITO_RECIENTE: CREDITO_REAL})
    filas = fuentes.descargar_credito(soda, fuentes.CREDITO_RECIENTE, date(2026, 10, 1), date(2026, 10, 2))
    assert filas[0]["tasa_ea"] == 22.0 and filas[0]["entidad"] == "Bancolombia"
    p = soda.consultas[0][1]
    assert "sum(tasa_efectiva_promedio * montos_desembolsados)" in p["$select"] and "$group" in p


def test_tibc_y_usura():
    soda = SodaFalsa({fuentes.TIBC_DATASET: [
        {"resolucion": "1968", "vigencia_desde": "2026-10-01T00:00:00.000", "vigencia_hasta": "2026-10-31T00:00:00.000",
         "interes_bancario_corriente": "17,10%", "modalidad": "Consumo y ordinario"}]})
    f = fuentes.descargar_tibc(soda)[0]
    assert f["ibc_ea"] == 17.1 and f["usura_ea"] == 25.65 and f["modalidad"] == "CONSUMO Y ORDINARIO"


@pytest.mark.parametrize("entrada,salida", [
    ("Banco de Bogotá S.A.", "Banco de Bogotá"), ("BANCO CONTACTAR S.A.", "Banco Contactar"),
    ("BBVA COLOMBIA", "BBVA Colombia"), ("IRIS CF.", "Iris CF"), ("Tuya", "Tuya"), ("Nequi C.F.", "Nequi CF"),
    ("Finandina Bic o Banco Finandina Bic o Finandina", "Finandina BIC"), ('"Bold C.F."', "Bold CF"),
    ('BANCO UNIÓN S.A. (en adelante el "Banco" o la "Sociedad")', "Banco Unión"),
    ("BANCO AGRARIO DE COLOMBIA o BANAGRARIO", "Banco Agrario de Colombia"),
    ("Itaú; Banco Itaú", "Itaú"), ("NU Colombia Compañía de Financiamiento", "Nu Colombia CF"),
])
def test_limpiar_entidad(entrada, salida):
    assert fuentes.limpiar_entidad(entrada) == salida


def test_meses_cubre_rango():
    v = list(fuentes.meses(date(2026, 1, 15), date(2026, 3, 2)))
    assert v == [(date(2026, 1, 15), date(2026, 1, 31)), (date(2026, 2, 1), date(2026, 2, 28)),
                 (date(2026, 3, 1), date(2026, 3, 2))]


def test_fusionar_reemplaza_fechas(tmp_path):
    campos, orden = actualizar.CAMPOS_CDT, actualizar.ORDEN_CDT
    base = {"tipo_entidad": "Banco", "codigo_entidad": "1-1", "entidad": "X", "plazo_dias": 90, "monto": 1}
    almacen.fusionar(tmp_path, [dict(base, fecha="2026-10-13", tasa_ea=10), dict(base, fecha="2026-10-14", tasa_ea=11)],
                     campos, orden)
    almacen.fusionar(tmp_path, [dict(base, fecha="2026-10-14", tasa_ea=12)], campos, orden)
    filas = almacen.leer(tmp_path / "2026-10.csv")
    assert [(f["fecha"], f["tasa_ea"]) for f in filas] == [("2026-10-13", "10"), ("2026-10-14", "12")]
    assert almacen.max_fecha(tmp_path) == "2026-10-14"


def test_credito_reciente_y_relleno_hacia_atras(tmp_path):
    soda = SodaFalsa({fuentes.CREDITO_HISTORICO: [], fuentes.CREDITO_RECIENTE: CREDITO_REAL})
    actualizar.actualizar_credito(soda, tmp_path, date(2026, 10, 16))
    agregadas = [(d, p["$where"]) for d, p in soda.consultas if "$group" in p]
    assert agregadas[0][0] == fuentes.CREDITO_RECIENTE                      # primero lo reciente (rápido)
    historicas = [w for d, w in agregadas if d == fuentes.CREDITO_HISTORICO]
    assert historicas and "2026-09-19" in historicas[0]                      # luego semana a semana hacia atrás
    assert all("fecha_corte >= '2026-07" not in w or "2026-07-03" <= w[18:28] for w in historicas)
    assert almacen.max_fecha(tmp_path / "credito") == "2026-10-02"


# --------------------------------------------------------------------------- construir

def _datos_sinteticos(data: Path) -> None:
    import random
    random.seed(1)
    cdt, cred = [], []
    for d in range(60):
        f = date.fromordinal(date(2026, 8, 17).toordinal() + d)
        if f.weekday() >= 5:
            continue
        for cod, ent, base, monto in (("1-1", "Banco Grande", 11.0, 1000), ("1-2", "Banco Medio", 12.0, 300),
                                       ("4-9", "Financiera Diminuta", 15.0, 0.1)):
            for plazo in (90, 360):
                subida = 0.5 if (cod == "1-2" and d > 40) else 0
                cdt.append({"fecha": f.isoformat(), "tipo_entidad": "Banco", "codigo_entidad": cod, "entidad": ent,
                            "plazo_dias": plazo, "tasa_ea": base + subida + (plazo == 360) + random.random() * 0.05,
                            "monto": monto})
    for w in range(9):
        f = date.fromordinal(date(2026, 8, 7).toordinal() + 7 * w).isoformat()
        for cod, ent, base in (("1-1", "Banco Grande", 22.0), ("1-2", "Banco Medio", 20.0 - 0.2 * w)):
            cred.append({"fecha": f, "tipo_entidad": "Banco", "codigo_entidad": cod, "entidad": ent,
                         "tipo_credito": "Consumo", "producto": "Libre inversión", "tasa_ea": base, "monto": 500,
                         "creditos": 5})
    almacen.fusionar(data / "cdt", cdt, actualizar.CAMPOS_CDT, actualizar.ORDEN_CDT, "mes")
    almacen.fusionar(data / "credito", cred, actualizar.CAMPOS_CREDITO, actualizar.ORDEN_CREDITO, "anio")
    almacen.escribir(data / "trm.csv", [{"fecha": "2025-10-16", "hasta": "2025-10-16", "trm": 4000},
                                         {"fecha": "2026-09-16", "hasta": "2026-09-16", "trm": 3300},
                                         {"fecha": "2026-10-16", "hasta": "2026-10-16", "trm": 3170.46}],
                     ["fecha", "hasta", "trm"], ["fecha"])
    almacen.escribir(data / "tibc.csv", [{"desde": "2026-10-01", "hasta": "2026-10-31", "modalidad": "CONSUMO Y ORDINARIO",
                                          "ibc_ea": 17.1, "usura_ea": 25.65, "resolucion": "1"}],
                     ["desde", "hasta", "modalidad", "ibc_ea", "usura_ea", "resolucion"], ["desde"])


def test_construir_resumen(tmp_path):
    data, salida = tmp_path / "data", tmp_path / "out"
    _datos_sinteticos(data)
    r = construir.construir(data, salida, tmp_path / "MOV.md", ahora=datetime(2026, 10, 16, 9, 0, tzinfo=construir.BOGOTA))

    assert r["trm"]["valor"] == 3170.46 and r["trm"]["var_1a_pct"] == round((3170.46 / 4000 - 1) * 100, 2)
    assert r["usura"]["vigente"]["usura_ea"] == 25.65

    p360 = next(p for p in r["cdt"]["plazos"] if p["plazo_dias"] == 360)
    nombres = [e["entidad"] for e in p360["entidades"]]
    assert "Financiera Diminuta" not in nombres          # volumen irrelevante: fuera del ranking
    assert nombres[0] == "Banco Medio"                    # paga más
    assert p360["entidades"][0]["cambio_pp"] == pytest.approx(0.5, abs=0.1)

    li = r["credito"]["productos"][0]
    assert li["producto"] == "Libre inversión" and li["entidades"][0]["entidad"] == "Banco Medio"  # más barato primero
    assert li["entidades"][0]["cambio_pp"] == pytest.approx(-0.8, abs=0.01)

    assert any(m["entidad"] == "Banco Medio" for m in r["movimientos"]["subidas"])
    assert any(m["entidad"] == "Banco Medio" for m in r["movimientos"]["bajadas"])

    for nombre in ("resumen.json", "cdt_series.json", "credito_series.json", "trm.json", "usura.json"):
        assert json.loads((salida / nombre).read_text(encoding="utf-8")) is not None
    md = (tmp_path / "MOV.md").read_text(encoding="utf-8")
    assert "Banco Medio" in md and "25,65%" in md and "p,p" not in md and "$3.170,46" in md


def test_construir_sin_datos(tmp_path):
    r = construir.construir(tmp_path / "vacio", tmp_path / "out")
    assert r["trm"] is None and r["cdt"]["plazos"] == [] and r["credito"]["productos"] == []


# --------------------------------------------------------------------------- seguridad

def test_nombre_no_inyecta_formulas_csv():
    assert not fuentes.limpiar_entidad('=HYPERLINK("http://x","clic")').startswith("=")
    assert not fuentes.limpiar_entidad("+cmd|' /C calc'!A0").startswith("+")
    assert "\n" not in fuentes.limpiar_entidad("Banco\nFalso")


def test_reporte_md_escapa_markdown():
    txt = construir.md("[clic](http://malo) ![x](http://rastreo.png) <script>|")
    assert "[clic](" not in txt and "![x](" not in txt and "<script>" not in txt and "\\|" in txt
