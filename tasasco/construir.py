"""Convierte data/ en los JSON del sitio (site/public/data) y en MOVIMIENTOS.md.

Criterios (documentados también en el README):
- Tasas efectivas anuales (E.A.) tal como las reporta la Superfinanciera.
- Promedios ponderados por monto: un CDT de $10.000 millones pesa más que uno de $1 millón.
- CDT por entidad: ventana de 7 días para suavizar el ruido diario.
- Rankings solo con entidades de volumen relevante (participación mínima en el monto del plazo o producto),
  para que un CDT aislado con tasa atípica no aparezca como "el mejor".
- Cambios: últimas 4 semanas, en puntos porcentuales (p.p.).
"""
from __future__ import annotations

import json
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import pandas as pd

from .fuentes import limpiar_entidad

BOGOTA = timezone(timedelta(hours=-5))
PLAZOS_CDT = [30, 60, 90, 180, 360, 361]
PLAZO_NOMBRE = {30: "30 días", 60: "60 días", 90: "90 días", 120: "120 días", 180: "180 días",
                360: "360 días", 361: "Más de 360 días"}
# Productos que interesan a una persona natural, en el orden en que se muestran
PRODUCTOS = [
    ("Consumo", "Tarjeta de crédito para ingresos superiores a 2 SMMLV", "Tarjeta de crédito (ingresos > 2 SMMLV)"),
    ("Consumo", "Tarjeta de crédito para ingresos hasta 2 SMMLV", "Tarjeta de crédito (ingresos ≤ 2 SMMLV)"),
    ("Consumo", "Libre inversión", "Libre inversión"),
    ("Consumo", "Libranza otros", "Libranza"),
    ("Consumo", "Vehículo", "Vehículo"),
    ("Consumo", "Crédito rotativo", "Crédito rotativo"),
    ("Consumo", "Créditos de consumo de bajo monto", "Consumo de bajo monto"),
]
PARTICIPACION_MIN = 0.003   # 0,3% del monto del plazo/producto para entrar a rankings
SEMANAS_CAMBIO = 4


# --------------------------------------------------------------------------- carga

def cargar(data: Path) -> dict[str, pd.DataFrame]:
    def carpeta(nombre: str) -> pd.DataFrame:
        archivos = sorted((data / nombre).glob("*.csv"))
        if not archivos:
            return pd.DataFrame()
        df = pd.concat((pd.read_csv(a, dtype={"codigo_entidad": str}) for a in archivos), ignore_index=True)
        df["fecha"] = pd.to_datetime(df["fecha"])
        df["entidad"] = df["entidad"].map(limpiar_entidad)  # aplica reglas de nombre nuevas a datos ya guardados
        return df

    def archivo(nombre: str, fechas: list[str]) -> pd.DataFrame:
        ruta = data / nombre
        if not ruta.exists():
            return pd.DataFrame()
        df = pd.read_csv(ruta)
        for c in fechas:
            df[c] = pd.to_datetime(df[c], errors="coerce")
        return df

    return {"cdt": carpeta("cdt"), "credito": carpeta("credito"),
            "trm": archivo("trm.csv", ["fecha", "hasta"]), "tibc": archivo("tibc.csv", ["desde", "hasta"])}


def ponderado(df: pd.DataFrame, por: list[str]) -> pd.DataFrame:
    """Tasa promedio ponderada por monto."""
    if df.empty:
        return pd.DataFrame(columns=por + ["tasa_ea", "monto"])
    g = df.assign(_tm=df["tasa_ea"] * df["monto"]).groupby(por, as_index=False)[["_tm", "monto"]].sum()
    g = g[g["monto"] > 0]
    g["tasa_ea"] = g["_tm"] / g["monto"]
    return g.drop(columns="_tm")


def r2(x: Any) -> float | None:
    return None if x is None or pd.isna(x) else round(float(x), 2)


# --------------------------------------------------------------------------- TRM

def resumen_trm(trm: pd.DataFrame) -> dict[str, Any] | None:
    if trm.empty:
        return None
    t = trm.sort_values("fecha")
    ult = t.iloc[-1]

    def hace(dias: int) -> float | None:
        prev = t[t["fecha"] <= ult["fecha"] - pd.Timedelta(days=dias)]
        return None if prev.empty else float(prev.iloc[-1]["trm"])

    def var(v: float | None) -> float | None:
        return None if not v else r2((ult["trm"] / v - 1) * 100)

    año = t[t["fecha"] > ult["fecha"] - pd.Timedelta(days=365)]
    return {
        "fecha": ult["fecha"].date().isoformat(), "valor": r2(ult["trm"]),
        "var_dia_pct": var(hace(1)), "var_30d_pct": var(hace(30)), "var_1a_pct": var(hace(365)),
        "min_52s": r2(año["trm"].min()), "max_52s": r2(año["trm"].max()),
        "promedio_52s": r2(año["trm"].mean()),
    }


def serie_trm(trm: pd.DataFrame, desde: str = "2015-01-01") -> list[list[Any]]:
    if trm.empty:
        return []
    t = trm[trm["fecha"] >= desde].sort_values("fecha")
    return [[f.date().isoformat(), r2(v)] for f, v in zip(t["fecha"], t["trm"])]


# --------------------------------------------------------------------------- Usura

def usura(tibc: pd.DataFrame, hoy: pd.Timestamp) -> dict[str, Any]:
    """Usura vigente e histórico para las dos modalidades de consumo que usa el sitio."""
    vacio = {"vigente": None, "vigente_bajo_monto": None, "historico": [], "historico_bajo_monto": []}
    if tibc.empty:
        return vacio

    def modalidad(nombre: str) -> tuple[dict[str, Any] | None, list[list[Any]]]:
        d = tibc[tibc["modalidad"] == nombre].sort_values("desde")
        if d.empty:
            return None, []
        vig = d[(d["desde"] <= hoy) & ((d["hasta"] >= hoy) | d["hasta"].isna())]
        v = vig.iloc[-1] if not vig.empty else d.iloc[-1]
        return ({"modalidad": v["modalidad"], "desde": v["desde"].date().isoformat(),
                 "hasta": None if pd.isna(v["hasta"]) else v["hasta"].date().isoformat(),
                 "ibc_ea": r2(v["ibc_ea"]), "usura_ea": r2(v["usura_ea"]), "resolucion": str(v["resolucion"])},
                [[f.date().isoformat(), r2(u)] for f, u in zip(d["desde"], d["usura_ea"]) if f >= pd.Timestamp("2015-01-01")])

    vo, ho = modalidad("CONSUMO Y ORDINARIO")
    vb, hb = modalidad("CONSUMO BAJO MONTO")
    return {"vigente": vo, "vigente_bajo_monto": vb, "historico": ho, "historico_bajo_monto": hb}


# --------------------------------------------------------------------------- CDT

def cdt(df: pd.DataFrame) -> dict[str, Any]:
    if df.empty:
        return {"fecha": None, "plazos": [], "serie_sistema": {}, "serie_entidades": {}}
    ult = df["fecha"].max()
    ventana = df[df["fecha"] > ult - pd.Timedelta(days=7)]
    antes_fin = ult - pd.Timedelta(weeks=SEMANAS_CAMBIO)
    ventana_antes = df[(df["fecha"] <= antes_fin) & (df["fecha"] > antes_fin - pd.Timedelta(days=7))]

    actual = ponderado(ventana, ["plazo_dias", "codigo_entidad", "entidad", "tipo_entidad"])
    previo = ponderado(ventana_antes, ["plazo_dias", "codigo_entidad"]).rename(columns={"tasa_ea": "tasa_antes"})
    actual = actual.merge(previo[["plazo_dias", "codigo_entidad", "tasa_antes"]], how="left",
                          on=["plazo_dias", "codigo_entidad"])
    sist = ponderado(ventana, ["plazo_dias"]).set_index("plazo_dias")["tasa_ea"]
    sist_antes = ponderado(ventana_antes, ["plazo_dias"]).set_index("plazo_dias")["tasa_ea"]

    plazos = []
    for p in PLAZOS_CDT:
        a = actual[actual["plazo_dias"] == p]
        if a.empty:
            continue
        a = a[a["monto"] >= a["monto"].sum() * PARTICIPACION_MIN].sort_values("tasa_ea", ascending=False)
        plazos.append({
            "plazo_dias": p, "nombre": PLAZO_NOMBRE[p],
            "promedio_sistema": r2(sist.get(p)), "cambio_pp": r2(sist.get(p) - sist_antes.get(p))
            if p in sist_antes.index else None,
            "entidades": [{
                "entidad": e.entidad, "tipo": e.tipo_entidad, "tasa_ea": r2(e.tasa_ea),
                "cambio_pp": r2(e.tasa_ea - e.tasa_antes) if not pd.isna(e.tasa_antes) else None,
                "participacion_pct": r2(e.monto / a["monto"].sum() * 100),
            } for e in a.itertuples()],
        })

    # Series semanales (semana que termina en viernes) para gráficas
    semanal = df.assign(semana=df["fecha"].dt.to_period("W-FRI").dt.end_time.dt.normalize())
    s_sis = ponderado(semanal, ["semana", "plazo_dias"])
    serie_sistema = {str(p): [[w.date().isoformat(), r2(t)] for w, t in
                              zip(g.sort_values("semana")["semana"], g.sort_values("semana")["tasa_ea"])]
                     for p, g in s_sis.groupby("plazo_dias") if p in PLAZOS_CDT}
    # Por entidad: las 12 de mayor monto en el último año, plazos 90 y 360
    ultimo_año = semanal[semanal["fecha"] > ult - pd.Timedelta(days=365)]
    grandes = ultimo_año.groupby("entidad")["monto"].sum().sort_values(ascending=False).head(12).index
    s_ent = ponderado(semanal[semanal["entidad"].isin(grandes) & semanal["plazo_dias"].isin([90, 360])],
                      ["semana", "plazo_dias", "entidad"])
    serie_entidades = {}
    for (p, ent), g in s_ent.groupby(["plazo_dias", "entidad"]):
        g = g.sort_values("semana")
        serie_entidades.setdefault(str(p), {})[ent] = [[w.date().isoformat(), r2(t)] for w, t in
                                                         zip(g["semana"], g["tasa_ea"])]
    return {"fecha": ult.date().isoformat(), "ventana_dias": 7, "plazos": plazos,
            "serie_sistema": serie_sistema, "serie_entidades": serie_entidades}


# --------------------------------------------------------------------------- Crédito

def credito(df: pd.DataFrame) -> dict[str, Any]:
    if df.empty:
        return {"fecha": None, "productos": [], "serie_sistema": {}}
    ult = df["fecha"].max()
    fechas = sorted(df["fecha"].unique())
    antes = [f for f in fechas if f <= ult - pd.Timedelta(weeks=SEMANAS_CAMBIO)]
    f_antes = antes[-1] if antes else None
    productos, series = [], {}
    for tipo, prod, nombre in PRODUCTOS:
        d = df[(df["tipo_credito"] == tipo) & (df["producto"] == prod)]
        if d.empty:
            continue
        hoy_d = d[d["fecha"] == ult]
        actual = ponderado(hoy_d, ["codigo_entidad", "entidad", "tipo_entidad"])
        previo = ponderado(d[d["fecha"] == f_antes], ["codigo_entidad"]).rename(columns={"tasa_ea": "tasa_antes"}) \
            if f_antes is not None else pd.DataFrame(columns=["codigo_entidad", "tasa_antes"])
        actual = actual.merge(previo[["codigo_entidad", "tasa_antes"]], how="left", on="codigo_entidad")
        total = actual["monto"].sum()
        actual = actual[actual["monto"] >= total * PARTICIPACION_MIN].sort_values("tasa_ea")
        sis = ponderado(hoy_d, ["tipo_credito"])["tasa_ea"]
        sis_antes = ponderado(d[d["fecha"] == f_antes], ["tipo_credito"])["tasa_ea"] if f_antes is not None else []
        prom = float(sis.iloc[0]) if len(sis) else None
        prom_antes = float(sis_antes.iloc[0]) if len(sis_antes) else None
        productos.append({
            "producto": nombre, "producto_fuente": prod, "tipo_credito": tipo,
            "promedio_sistema": r2(prom), "cambio_pp": r2(prom - prom_antes) if prom and prom_antes else None,
            "entidades": [{
                "entidad": e.entidad, "tipo": e.tipo_entidad, "tasa_ea": r2(e.tasa_ea),
                "cambio_pp": r2(e.tasa_ea - e.tasa_antes) if not pd.isna(e.tasa_antes) else None,
                "participacion_pct": r2(e.monto / total * 100),
            } for e in actual.itertuples()],
        })
        s = ponderado(d, ["fecha"]).sort_values("fecha")
        series[nombre] = [[f.date().isoformat(), r2(t)] for f, t in zip(s["fecha"], s["tasa_ea"])]
    return {"fecha": ult.date().isoformat(), "comparado_con": None if f_antes is None else
            pd.Timestamp(f_antes).date().isoformat(), "productos": productos, "serie_sistema": series}


# --------------------------------------------------------------------------- Movimientos

def movimientos(c: dict[str, Any], k: dict[str, Any], n: int = 5) -> dict[str, list[dict[str, Any]]]:
    """Mayores subidas y bajadas de las últimas 4 semanas entre entidades con volumen relevante."""
    filas = []
    for p in c.get("plazos", []):
        if p["plazo_dias"] not in (90, 360):
            continue
        for e in p["entidades"]:
            if e["cambio_pp"] is not None and e["participacion_pct"] >= 1:
                filas.append({"grupo": f"CDT {p['nombre']}", **e})
    for p in k.get("productos", []):
        for e in p["entidades"]:
            if e["cambio_pp"] is not None and e["participacion_pct"] >= 1:
                filas.append({"grupo": p["producto"], **e})
    filas.sort(key=lambda x: x["cambio_pp"])
    return {"bajadas": [f for f in filas if f["cambio_pp"] < 0][:n],
            "subidas": [f for f in reversed(filas) if f["cambio_pp"] > 0][:n]}


# --------------------------------------------------------------------------- Reporte

def _es(x: float, dec: int = 2) -> str:
    """Formato colombiano: punto de miles, coma decimal."""
    return f"{x:,.{dec}f}".replace(",", "_").replace(".", ",").replace("_", ".")


def pp(x: float | None) -> str:
    if x is None:
        return "—"
    return ("+" if x > 0 else "−" if x < 0 else "") + _es(abs(x)) + " p.p."


def pct(x: float | None) -> str:
    return "—" if x is None else f"{_es(x)}%"


def pesos(x: float | None, dec: int = 2) -> str:
    return "—" if x is None else f"${_es(x, dec)}"


def reporte_md(r: dict[str, Any]) -> str:
    l = [f"# Movimientos de tasas en Colombia", "",
         f"_Actualizado: {r['generado'][:16].replace('T', ' ')} (hora Colombia). "
         f"Fuente: Superintendencia Financiera vía datos.gov.co._", ""]
    t = r.get("trm")
    if t:
        l += ["## TRM", "", f"**{pesos(t['valor'])}** el {t['fecha']}. Variación en 30 días: {pct(t['var_30d_pct'])}; "
              f"en un año: {pct(t['var_1a_pct'])}. Rango de 52 semanas: {pesos(t['min_52s'], 0)} a {pesos(t['max_52s'], 0)}.", ""]
    u = (r.get("usura") or {}).get("vigente")
    if u:
        l += ["## Tasa de usura (consumo y ordinario)", "",
              f"**{pct(u['usura_ea'])} E.A.** vigente desde {u['desde']} (interés bancario corriente {pct(u['ibc_ea'])}).", ""]
    c = r.get("cdt") or {}
    if c.get("plazos"):
        l += [f"## CDT: mejores tasas (últimos 7 días al {c['fecha']})", "",
              "| Plazo | Promedio del sistema | Cambio 4 sem. | Mejor tasa | Entidad |", "|---|---|---|---|---|"]
        for p in c["plazos"]:
            top = p["entidades"][0] if p["entidades"] else None
            l.append(f"| {p['nombre']} | {pct(p['promedio_sistema'])} | {pp(p['cambio_pp'])} | "
                     f"{pct(top['tasa_ea']) if top else '—'} | {top['entidad'] if top else '—'} |")
        l.append("")
    k = r.get("credito") or {}
    if k.get("productos"):
        l += [f"## Crédito de consumo (semana al {k['fecha']})", "",
              "| Producto | Promedio | Cambio 4 sem. | Más barato | Entidad |", "|---|---|---|---|---|"]
        for p in k["productos"]:
            top = p["entidades"][0] if p["entidades"] else None
            l.append(f"| {p['producto']} | {pct(p['promedio_sistema'])} | {pp(p['cambio_pp'])} | "
                     f"{pct(top['tasa_ea']) if top else '—'} | {top['entidad'] if top else '—'} |")
        l.append("")
    m = r.get("movimientos") or {}
    for titulo, clave in (("Mayores subidas (4 semanas)", "subidas"), ("Mayores bajadas (4 semanas)", "bajadas")):
        if m.get(clave):
            l += [f"## {titulo}", ""] + [f"- **{x['entidad']}**, {x['grupo']}: {pct(x['tasa_ea'])} ({pp(x['cambio_pp'])})"
                                         for x in m[clave]] + [""]
    l += ["---", "Tasas efectivas anuales promedio ponderadas por monto. Rankings solo con entidades con al menos 0,3% "
          "del monto del plazo o producto. No es asesoría financiera."]
    return "\n".join(l) + "\n"


# --------------------------------------------------------------------------- Principal

def construir(data: Path, salida: Path, reporte: Path | None = None, ahora: datetime | None = None) -> dict[str, Any]:
    ahora = ahora or datetime.now(BOGOTA)
    d = cargar(data)
    c, k = cdt(d["cdt"]), credito(d["credito"])
    resumen = {
        "generado": ahora.isoformat(timespec="seconds"),
        "fuente": "Superintendencia Financiera de Colombia vía datos.gov.co",
        "trm": resumen_trm(d["trm"]),
        "usura": usura(d["tibc"], pd.Timestamp(ahora.date())),  # históricos van solo en usura.json
        "cdt": {kk: v for kk, v in c.items() if not kk.startswith("serie")},
        "credito": {kk: v for kk, v in k.items() if not kk.startswith("serie")},
    }
    resumen["movimientos"] = movimientos(c, k)
    historicos_usura = {k2: resumen["usura"].pop(k2) for k2 in ("historico", "historico_bajo_monto")}
    salida.mkdir(parents=True, exist_ok=True)

    def guardar(nombre: str, obj: Any) -> None:
        (salida / nombre).write_text(json.dumps(obj, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")

    guardar("resumen.json", resumen)
    guardar("cdt_series.json", {"sistema": c["serie_sistema"], "entidades": c["serie_entidades"]})
    guardar("credito_series.json", k["serie_sistema"])
    guardar("trm.json", serie_trm(d["trm"]))
    guardar("usura.json", {"consumo_y_ordinario": historicos_usura["historico"],
                           "consumo_bajo_monto": historicos_usura["historico_bajo_monto"]})
    if reporte:
        reporte.write_text(reporte_md(resumen), encoding="utf-8")
    return resumen
