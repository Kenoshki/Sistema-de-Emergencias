"""
Analítica con Pandas. Las funciones reciben listas de diccionarios (no
dependen de la base de datos), lo que permite probarlas por separado.

Indicadores:
- Tiempo de respuesta  = llegada a escena - hora del reporte.
- Tiempo de despacho   = primera unidad asignada - hora del reporte.
- Cumplimiento         = % de incidentes atendidos dentro del tiempo objetivo
                         de su prioridad.
- Índice de riesgo     = suma ponderada de incidentes por lugar (zona de la
                         capital o municipio) y por departamento
                         (crítico pesa 8, alto 4, medio 2, bajo 1).
- Utilización de flota = unidades ocupadas / unidades operativas.
"""
from __future__ import annotations

from datetime import datetime, timedelta

import pandas as pd

from app.catalogos import ESTADOS_ACTIVOS, PRIORIDADES, TIPOS_INCIDENTE
from app.geografia import DEPARTAMENTOS, etiqueta_nodo

PESO_PRIORIDAD = {1: 1, 2: 2, 3: 4, 4: 8}
TIEMPO_OBJETIVO_MIN = {4: 7, 3: 9, 2: 12, 1: 15}

COLUMNAS = ["id", "type", "priority", "node", "department_code", "status",
            "reported_at", "dispatched_at", "arrived_at", "resolved_at"]


def _redondear(valor, decimales: int = 1):
    if valor is None or pd.isna(valor):
        return None
    return round(float(valor), decimales)


def preparar(incidentes: list[dict]) -> pd.DataFrame:
    df = pd.DataFrame(incidentes, columns=COLUMNAS)
    for col in ("reported_at", "dispatched_at", "arrived_at", "resolved_at"):
        df[col] = pd.to_datetime(df[col])
    df["priority"] = df["priority"].astype("Int64")
    df["node"] = df["node"].astype("Int64")
    df["respuesta_min"] = (df["arrived_at"] - df["reported_at"]).dt.total_seconds() / 60
    df["despacho_min"] = (df["dispatched_at"] - df["reported_at"]).dt.total_seconds() / 60
    df["peso"] = df["priority"].map(PESO_PRIORIDAD).fillna(1)
    df["objetivo_min"] = df["priority"].map(TIEMPO_OBJETIVO_MIN)
    return df


def _ventana(df: pd.DataFrame, inicio: datetime, fin: datetime) -> pd.DataFrame:
    return df[(df["reported_at"] >= inicio) & (df["reported_at"] < fin)]


def _metricas_tiempo(df: pd.DataFrame) -> dict:
    atendidos = df.dropna(subset=["respuesta_min"])
    cumplimiento = None
    if not atendidos.empty:
        cumplimiento = (atendidos["respuesta_min"] <= atendidos["objetivo_min"]).mean() * 100
    return {
        "promedio": _redondear(atendidos["respuesta_min"].mean()) if not atendidos.empty else None,
        "p90": _redondear(atendidos["respuesta_min"].quantile(0.9)) if not atendidos.empty else None,
        "despacho": _redondear(df["despacho_min"].dropna().mean()) if df["despacho_min"].notna().any() else None,
        "cumplimiento": _redondear(cumplimiento),
        "atendidos": int(len(atendidos)),
    }


def _variacion_pct(actual, anterior):
    if actual is None or anterior in (None, 0):
        return None
    return round((actual - anterior) / anterior * 100, 1)


def ranking_riesgo(df: pd.DataFrame, limite: int = 5) -> list[dict]:
    if df.empty:
        return []
    agrupado = (
        df.groupby("node")
        .agg(incidentes=("id", "count"), indice=("peso", "sum"), criticos=("priority", lambda s: int((s == 4).sum())))
        .sort_values(["indice", "criticos", "incidentes"], ascending=False)
        .head(limite)
        .reset_index()
    )
    return [
        {
            "node": int(f.node),
            "label": etiqueta_nodo(int(f.node)),
            "incidents": int(f.incidentes),
            "critical": int(f.criticos),
            "risk_index": int(f.indice),
        }
        for f in agrupado.itertuples()
    ]


def calcular_kpis(incidentes: list[dict], recursos: list[dict], dias: int = 30, ahora: datetime | None = None) -> dict:
    ahora = ahora or datetime.now()
    df = preparar(incidentes)
    inicio = ahora - timedelta(days=dias)
    actual = _ventana(df, inicio, ahora + timedelta(seconds=1))
    anterior = _ventana(df, inicio - timedelta(days=dias), inicio)

    m_actual = _metricas_tiempo(actual)
    m_anterior = _metricas_tiempo(anterior)

    # Flota
    estados = pd.Series([r["status"] for r in recursos], dtype="object")
    total = int(len(estados))
    mantenimiento = int((estados == "maintenance").sum())
    ocupadas = int(estados.isin(["dispatched", "on_scene"]).sum())
    operativas = total - mantenimiento
    utilizacion = round(ocupadas / operativas * 100, 1) if operativas else 0.0

    riesgo = ranking_riesgo(actual)
    activos = df[df["status"].isin(ESTADOS_ACTIVOS)]
    hoy = df[df["reported_at"] >= ahora.replace(hour=0, minute=0, second=0, microsecond=0)]

    return {
        "window_days": dias,
        "total_incidents": int(len(actual)),
        "previous_total_incidents": int(len(anterior)),
        "incidents_change_pct": _variacion_pct(len(actual), len(anterior)),
        "active_incidents": int(len(activos)),
        "critical_active": int((activos["priority"] == 4).sum()),
        "incidents_today": int(len(hoy)),
        "avg_response_time_min": m_actual["promedio"],
        "previous_avg_response_time_min": m_anterior["promedio"],
        "response_time_change_pct": _variacion_pct(m_actual["promedio"], m_anterior["promedio"]),
        "p90_response_time_min": m_actual["p90"],
        "avg_dispatch_time_min": m_actual["despacho"],
        "target_compliance_pct": m_actual["cumplimiento"],
        "attended_incidents": m_actual["atendidos"],
        "highest_risk_node": riesgo[0]["node"] if riesgo else None,
        "highest_risk_label": riesgo[0]["label"] if riesgo else None,
        "risk_ranking": riesgo,
        "fleet_total": total,
        "fleet_busy": ocupadas,
        "fleet_available": int((estados == "available").sum()),
        "fleet_maintenance": mantenimiento,
        "fleet_utilization_pct": utilizacion,
    }


def calcular_resumen(incidentes: list[dict], dias: int = 30, ahora: datetime | None = None) -> dict:
    """Series para las gráficas del panel."""
    ahora = ahora or datetime.now()
    # Días calendario completos: hoy y los (dias - 1) días anteriores.
    inicio = ahora.replace(hour=0, minute=0, second=0, microsecond=0) - timedelta(days=dias - 1)
    df = _ventana(preparar(incidentes), inicio, ahora + timedelta(seconds=1))

    # Por tipo (incluye tipos con 0)
    conteo_tipo = df["type"].value_counts()
    por_tipo = [
        {"type": t, "label": etiqueta, "count": int(conteo_tipo.get(t, 0))}
        for t, etiqueta in TIPOS_INCIDENTE.items()
    ]
    por_tipo.sort(key=lambda x: x["count"], reverse=True)

    # Por lugar (zona de la capital o municipio) y por departamento
    por_lugar, por_depto = [], []
    if not df.empty:
        g = df.groupby("node").agg(n=("id", "count"), indice=("peso", "sum")).reset_index()
        por_lugar = [
            {"node": int(f.node), "label": etiqueta_nodo(int(f.node)), "count": int(f.n), "risk_index": int(f.indice)}
            for f in g.itertuples()
        ]
        g = df.groupby("department_code").agg(n=("id", "count"), indice=("peso", "sum")).reset_index()
        por_depto = [
            {"department_code": f.department_code,
             "label": DEPARTAMENTOS.get(f.department_code, {}).get("nombre", f.department_code),
             "count": int(f.n), "risk_index": int(f.indice)}
            for f in g.itertuples()
        ]
    por_lugar.sort(key=lambda x: x["risk_index"], reverse=True)
    por_depto.sort(key=lambda x: x["risk_index"], reverse=True)

    # Tendencia diaria (rellena días sin incidentes con 0)
    dias_rango = pd.date_range(end=pd.Timestamp(ahora).normalize(), periods=dias, freq="D")
    diario = df.assign(dia=df["reported_at"].dt.normalize())
    total_dia = diario.groupby("dia")["id"].count()
    criticos_dia = diario[diario["priority"] >= 3].groupby("dia")["id"].count()
    tendencia = [
        {"date": d.strftime("%Y-%m-%d"), "total": int(total_dia.get(d, 0)), "high_or_critical": int(criticos_dia.get(d, 0))}
        for d in dias_rango
    ]

    # Por prioridad
    por_prioridad = []
    for p in sorted(PRIORIDADES, reverse=True):
        sub = df[df["priority"] == p]
        atendidos = sub.dropna(subset=["respuesta_min"])
        por_prioridad.append({
            "priority": p,
            "label": PRIORIDADES[p],
            "count": int(len(sub)),
            "avg_response_min": _redondear(atendidos["respuesta_min"].mean()) if not atendidos.empty else None,
            "target_min": TIEMPO_OBJETIVO_MIN[p],
        })

    # Por hora del día
    conteo_hora = df["reported_at"].dt.hour.value_counts()
    por_hora = [{"hour": h, "count": int(conteo_hora.get(h, 0))} for h in range(24)]

    return {
        "window_days": dias,
        "by_type": por_tipo,
        "by_location": por_lugar,
        "by_department": por_depto,
        "daily_trend": tendencia,
        "by_priority": por_prioridad,
        "by_hour": por_hora,
    }


def a_dataframe_exportable(incidentes: list[dict]) -> pd.DataFrame:
    """Tabla con columnas en español para exportar a CSV."""
    df = preparar(incidentes)
    df["tipo"] = df["type"].map(TIPOS_INCIDENTE)
    df["prioridad"] = df["priority"].map(PRIORIDADES)
    df["departamento"] = df["department_code"].map(lambda c: DEPARTAMENTOS.get(c, {}).get("nombre", c))
    df["lugar"] = df["node"].map(lambda n: etiqueta_nodo(int(n)) if pd.notna(n) else "")
    salida = df[["id", "tipo", "prioridad", "departamento", "lugar", "status", "reported_at", "dispatched_at",
                 "arrived_at", "resolved_at", "despacho_min", "respuesta_min"]].copy()
    salida.columns = ["ID", "Tipo", "Prioridad", "Departamento", "Lugar", "Estado", "Reportado", "Despachado",
                      "Llegada", "Cierre", "Min. despacho", "Min. respuesta"]
    for col in ("Min. despacho", "Min. respuesta"):
        salida[col] = salida[col].round(1)
    return salida
