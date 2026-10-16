"""Descarga de reportes: PDF (ReportLab) y CSV (Pandas)."""
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, Query
from fastapi.responses import Response
from sqlalchemy.orm import Session, selectinload

from app.database import get_db
from app.models import IncidentModel, ResourceModel, UserModel
from app.routers.analitica import cargar_incidentes, cargar_recursos
from app.security import requiere
from app.servicios import serializadores as ser
from app.servicios.analitica import a_dataframe_exportable, calcular_kpis, calcular_resumen
from app.servicios.operaciones import incidente_activo_de_recurso
from app.servicios.reportes import generar_pdf

router = APIRouter(prefix="/api/admin/reports", tags=["Reportes"])


@router.get("/pdf")
def reporte_pdf(dias: int = Query(30, ge=1, le=365), db: Session = Depends(get_db),
                user: UserModel = Depends(requiere("reportes"))):
    ahora = datetime.now()
    datos = cargar_incidentes(db, ahora - timedelta(days=dias * 2 + 1))
    recientes = (
        db.query(IncidentModel).options(selectinload(IncidentModel.assignments))
        .order_by(IncidentModel.reported_at.desc()).limit(25).all()
    )
    activos = incidente_activo_de_recurso(db)
    recursos = [ser.recurso(r, activos.get(r.code)) for r in db.query(ResourceModel).order_by(ResourceModel.code).all()]
    pdf = generar_pdf(
        calcular_kpis(datos, cargar_recursos(db), dias=dias, ahora=ahora),
        calcular_resumen(datos, dias=dias, ahora=ahora),
        [ser.incidente(i) for i in recientes],
        recursos,
        generado_por=user.full_name or user.username,
        ahora=ahora,
    )
    nombre = f"reporte_emergencias_{ahora:%Y%m%d_%H%M}.pdf"
    return Response(content=pdf, media_type="application/pdf",
                    headers={"Content-Disposition": f'attachment; filename="{nombre}"'})


@router.get("/csv")
def reporte_csv(dias: int = Query(30, ge=1, le=365), db: Session = Depends(get_db),
                _: UserModel = Depends(requiere("reportes"))):
    ahora = datetime.now()
    df = a_dataframe_exportable(cargar_incidentes(db, ahora - timedelta(days=dias)))
    # utf-8-sig para que Excel muestre bien las tildes
    contenido = df.to_csv(index=False).encode("utf-8-sig")
    nombre = f"incidentes_{ahora:%Y%m%d_%H%M}.csv"
    return Response(content=contenido, media_type="text/csv; charset=utf-8",
                    headers={"Content-Disposition": f'attachment; filename="{nombre}"'})
