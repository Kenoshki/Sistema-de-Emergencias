"""Indicadores y series para el panel ejecutivo (Pandas)."""
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import IncidentModel, ResourceModel, UserModel
from app.security import requiere
from app.servicios.analitica import calcular_kpis, calcular_resumen

router = APIRouter(prefix="/api/admin/analytics", tags=["Analítica"])


def cargar_incidentes(db: Session, desde: datetime | None = None) -> list[dict]:
    consulta = db.query(
        IncidentModel.id, IncidentModel.type, IncidentModel.priority, IncidentModel.node, IncidentModel.department_code, IncidentModel.status,
        IncidentModel.reported_at, IncidentModel.dispatched_at, IncidentModel.arrived_at, IncidentModel.resolved_at,
    )
    if desde is not None:
        consulta = consulta.filter(IncidentModel.reported_at >= desde)
    return [dict(f._mapping) for f in consulta.all()]


def cargar_recursos(db: Session) -> list[dict]:
    return [{"code": r.code, "type": r.type, "status": r.status} for r in db.query(ResourceModel).all()]


@router.get("/kpis")
def kpis(dias: int = Query(30, ge=1, le=365), db: Session = Depends(get_db), _: UserModel = Depends(requiere("panel", "reportes"))):
    # Se cargan 2 ventanas (actual y anterior) para calcular la variación.
    desde = datetime.now() - timedelta(days=dias * 2 + 1)
    datos = cargar_incidentes(db, desde)
    # Los incidentes activos se cuentan aunque sean antiguos.
    activos_antiguos = [
        dict(f._mapping) for f in db.query(
            IncidentModel.id, IncidentModel.type, IncidentModel.priority, IncidentModel.node, IncidentModel.department_code, IncidentModel.status,
            IncidentModel.reported_at, IncidentModel.dispatched_at, IncidentModel.arrived_at, IncidentModel.resolved_at,
        ).filter(IncidentModel.reported_at < desde, IncidentModel.status.in_(("pending", "dispatched", "on_scene"))).all()
    ]
    return calcular_kpis(datos + activos_antiguos, cargar_recursos(db), dias=dias)


@router.get("/summary")
def resumen(dias: int = Query(30, ge=1, le=365), db: Session = Depends(get_db), _: UserModel = Depends(requiere("panel", "reportes"))):
    return calcular_resumen(cargar_incidentes(db, datetime.now() - timedelta(days=dias + 1)), dias=dias)
