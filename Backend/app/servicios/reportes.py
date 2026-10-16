"""Generación del reporte ejecutivo en PDF con ReportLab."""
from __future__ import annotations

from datetime import datetime
from io import BytesIO

from reportlab.graphics.charts.barcharts import HorizontalBarChart
from reportlab.graphics.shapes import Drawing
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

EQUIPO = [
    "Naomy De León Salguero (3590-23-7248)",
    "Cristian Lorenzo Hernández de Paz (3590-24-709)",
    "Kennet Andersson Baten Rojas (3590-25-28916)",
]

AZUL = colors.HexColor("#1e3a5f")
GRIS = colors.HexColor("#f1f5f9")
BORDE = colors.HexColor("#cbd5e1")


def _fmt(valor, sufijo: str = "") -> str:
    return "—" if valor is None else f"{valor}{sufijo}"


def _tabla(datos: list[list], anchos: list[float], encabezado: bool = True) -> Table:
    t = Table(datos, colWidths=anchos, repeatRows=1 if encabezado else 0)
    estilo = [
        ("FONTNAME", (0, 0), (-1, -1), "Helvetica"),
        ("FONTSIZE", (0, 0), (-1, -1), 8.5),
        ("GRID", (0, 0), (-1, -1), 0.4, BORDE),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, GRIS]),
    ]
    if encabezado:
        estilo += [
            ("BACKGROUND", (0, 0), (-1, 0), AZUL),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ]
    t.setStyle(TableStyle(estilo))
    return t


def _grafica_tipos(por_tipo: list[dict]) -> Drawing:
    datos = [d for d in por_tipo if d["count"] > 0] or por_tipo
    datos = list(reversed(datos))  # el mayor arriba
    alto = 30 + 22 * len(datos)
    dibujo = Drawing(16 * cm, alto)
    g = HorizontalBarChart()
    g.x, g.y = 5.2 * cm, 10
    g.width, g.height = 9.5 * cm, alto - 25
    g.data = [[d["count"] for d in datos]]
    g.categoryAxis.categoryNames = [d["label"] for d in datos]
    g.categoryAxis.labels.fontSize = 8
    g.categoryAxis.labels.fontName = "Helvetica"
    g.valueAxis.labels.fontName = "Helvetica"
    g.barLabels.fontName = "Helvetica"
    g.categoryAxis.labels.boxAnchor = "e"
    g.valueAxis.valueMin = 0
    g.valueAxis.labels.fontSize = 7
    g.bars[0].fillColor = AZUL
    g.bars[0].strokeColor = None
    g.barLabelFormat = "%d"
    g.barLabels.fontSize = 7
    g.barLabels.nudge = 8
    dibujo.add(g)
    return dibujo


def generar_pdf(
    kpis: dict,
    resumen: dict,
    incidentes_recientes: list[dict],
    recursos: list[dict],
    generado_por: str,
    ahora: datetime | None = None,
) -> bytes:
    ahora = ahora or datetime.now()
    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer, pagesize=letter, leftMargin=1.8 * cm, rightMargin=1.8 * cm,
        topMargin=1.6 * cm, bottomMargin=1.6 * cm,
        title="Reporte ejecutivo - DWG EMS-05", author="DWG EMS-05",
    )
    estilos = getSampleStyleSheet()
    titulo = ParagraphStyle("titulo", parent=estilos["Title"], textColor=AZUL, fontSize=18, spaceAfter=4)
    sub = ParagraphStyle("sub", parent=estilos["Normal"], alignment=TA_CENTER, textColor=colors.HexColor("#475569"), fontSize=9)
    h2 = ParagraphStyle("h2", parent=estilos["Heading2"], textColor=AZUL, fontSize=12, spaceBefore=12, spaceAfter=6)
    normal = ParagraphStyle("n", parent=estilos["Normal"], fontSize=9, leading=12)

    dias = kpis.get("window_days", 30)
    e: list = [
        Paragraph("Sistema Inteligente de Gestión de Emergencias", titulo),
        Paragraph(f"Reporte ejecutivo · últimos {dias} días · generado el {ahora:%d/%m/%Y %H:%M} por {generado_por}", sub),
        Paragraph("DWG EMS-05 REV A", sub),
        Spacer(1, 10),
    ]

    # Indicadores
    e.append(Paragraph("1. Indicadores clave", h2))
    filas = [
        ["Indicador", "Valor", "Periodo anterior"],
        ["Incidentes registrados", _fmt(kpis.get("total_incidents")), _fmt(kpis.get("previous_total_incidents"))],
        ["Tiempo promedio de respuesta", _fmt(kpis.get("avg_response_time_min"), " min"), _fmt(kpis.get("previous_avg_response_time_min"), " min")],
        ["Tiempo de respuesta percentil 90", _fmt(kpis.get("p90_response_time_min"), " min"), ""],
        ["Tiempo promedio de despacho", _fmt(kpis.get("avg_dispatch_time_min"), " min"), ""],
        ["Cumplimiento del tiempo objetivo", _fmt(kpis.get("target_compliance_pct"), " %"), ""],
        ["Lugar de mayor riesgo", Paragraph(kpis.get("highest_risk_label") or "—", normal), ""],
        ["Utilización actual de la flota", _fmt(kpis.get("fleet_utilization_pct"), " %"), ""],
        ["Incidentes activos ahora", _fmt(kpis.get("active_incidents")), ""],
    ]
    e.append(_tabla(filas, [8 * cm, 5 * cm, 4.4 * cm]))

    # Por tipo
    e.append(Paragraph("2. Incidentes por tipo", h2))
    e.append(_grafica_tipos(resumen.get("by_type", [])))

    # Prioridad
    e.append(Paragraph("3. Tiempo de respuesta por prioridad", h2))
    filas = [["Prioridad", "Incidentes", "Respuesta promedio", "Tiempo objetivo"]]
    for p in resumen.get("by_priority", []):
        filas.append([f"{p['priority']} – {p['label']}", p["count"], _fmt(p["avg_response_min"], " min"), f"{p['target_min']} min"])
    e.append(_tabla(filas, [5 * cm, 3.5 * cm, 4.5 * cm, 4.4 * cm]))

    # Riesgo por lugar y departamento
    e.append(Paragraph("4. Lugares con mayor índice de riesgo", h2))
    e.append(Paragraph("Índice = suma ponderada de incidentes (crítico 8, alto 4, medio 2, bajo 1).", normal))
    e.append(Spacer(1, 4))
    filas = [["Lugar", "Incidentes", "Críticos", "Índice"]]
    for z in kpis.get("risk_ranking", []):
        filas.append([Paragraph(z["label"], normal), z["incidents"], z["critical"], z["risk_index"]])
    if len(filas) == 1:
        filas.append(["Sin datos", "", "", ""])
    e.append(_tabla(filas, [9 * cm, 3 * cm, 2.7 * cm, 2.7 * cm]))
    por_depto = resumen.get("by_department", [])[:8]
    if por_depto:
        e.append(Spacer(1, 6))
        filas = [["Departamento", "Incidentes", "Índice"]]
        for d in por_depto:
            filas.append([d["label"], d["count"], d["risk_index"]])
        e.append(_tabla(filas, [9 * cm, 3 * cm, 5.4 * cm]))

    # Flota
    e.append(Paragraph("5. Estado de la flota", h2))
    filas = [["Código", "Tipo", "Ubicación actual", "Estado"]]
    for r in recursos:
        filas.append([r["code"], r["type_label"], Paragraph(r["current_label"], normal), r["status_label"]])
    e.append(_tabla(filas, [2.6 * cm, 2.8 * cm, 8.4 * cm, 3.6 * cm]))

    # Recientes
    e.append(Paragraph("6. Incidentes recientes", h2))
    filas = [["ID", "Tipo", "Prior.", "Ubicación", "Estado", "Respuesta"]]
    for i in incidentes_recientes[:25]:
        filas.append([i["id"], Paragraph(i["type_label"], normal), i["priority"], Paragraph(i["location_label"], normal), Paragraph(i["status_label"], normal), _fmt(i["response_time_min"], " min")])
    if len(filas) == 1:
        filas.append(["—", "Sin incidentes", "", "", "", ""])
    e.append(_tabla(filas, [3.5 * cm, 3.3 * cm, 1.2 * cm, 4.4 * cm, 3.1 * cm, 1.9 * cm]))

    e.append(Spacer(1, 14))
    e.append(Paragraph("<b>Equipo DWG EMS-05:</b> " + " · ".join(EQUIPO), ParagraphStyle("eq", parent=normal, fontSize=7.5, textColor=colors.HexColor("#64748b"))))

    def pie(canvas, documento):
        canvas.saveState()
        canvas.setFont("Helvetica", 7.5)
        canvas.setFillColor(colors.HexColor("#64748b"))
        canvas.drawString(1.8 * cm, 1 * cm, "DWG EMS-05 REV A · Sistema Inteligente de Gestión de Emergencias")
        canvas.drawRightString(letter[0] - 1.8 * cm, 1 * cm, f"Página {documento.page}")
        canvas.restoreState()

    doc.build(e, onFirstPage=pie, onLaterPages=pie)
    return buffer.getvalue()
