"""Gestión de incidentes (requiere sesión)."""
from typing import Optional

from fastapi import APIRouter, Body, Depends, Query
from sqlalchemy import or_
from sqlalchemy.orm import Session, selectinload

from app.catalogos import ESTADOS_ACTIVOS
from app.database import escapar_like, get_db
from app.models import IncidentModel, UserModel
from app.schemas import IncidentCreate, IncidentUpdate, NotaIncidente
from app.permisos import EDITAR
from app.security import requiere
from app.servicios import operaciones as ops
from app.servicios import serializadores as ser

router = APIRouter(prefix="/api/admin/incidents", tags=["Incidentes"])


@router.get("")
def listar(
    status: Optional[str] = Query(None, description="pending, dispatched, on_scene, resolved, cancelled o 'active'"),
    type: Optional[str] = None,
    department: Optional[str] = None,
    municipality: Optional[str] = None,
    zone: Optional[int] = None,
    priority: Optional[int] = None,
    q: Optional[str] = Query(None, description="Buscar por código o descripción"),
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    _: UserModel = Depends(requiere("incidentes", "despacho", "panel")),
):
    consulta = db.query(IncidentModel).options(selectinload(IncidentModel.assignments))
    if status == "active":
        consulta = consulta.filter(IncidentModel.status.in_(ESTADOS_ACTIVOS))
    elif status:
        consulta = consulta.filter(IncidentModel.status == status)
    if type:
        consulta = consulta.filter(IncidentModel.type == type)
    if department:
        consulta = consulta.filter(IncidentModel.department_code == department)
    if municipality:
        consulta = consulta.filter(IncidentModel.municipality_code == municipality)
    if zone:
        consulta = consulta.filter(IncidentModel.zone == zone)
    if priority:
        consulta = consulta.filter(IncidentModel.priority == priority)
    if q:
        patron = f"%{escapar_like(q.strip()[:80])}%"
        consulta = consulta.filter(or_(*(c.like(patron, escape="\\") for c in (
            IncidentModel.id, IncidentModel.description, IncidentModel.address, IncidentModel.place_name))))
    total = consulta.count()
    filas = (
        consulta.order_by(IncidentModel.reported_at.desc())
        .offset(offset).limit(limit).all()
    )
    return {"total": total, "items": [ser.incidente(i) for i in filas]}


@router.post("", status_code=201)
def crear(datos: IncidentCreate, db: Session = Depends(get_db),
          user: UserModel = Depends(requiere("incidentes", "despacho", nivel=EDITAR))):  # despacho: simulacros
    """Registro hecho por un operador (por ejemplo, desde una llamada telefónica)."""
    inc = ops.crear_incidente(db, datos, source="operator", username=user.username)
    db.commit()
    db.refresh(inc)
    return ser.incidente(inc, detalle=True)


@router.get("/{incident_id}")
def detalle(incident_id: str, db: Session = Depends(get_db), _: UserModel = Depends(requiere("incidentes", "despacho", "panel"))):
    return ser.incidente(ops.obtener_incidente(db, incident_id), detalle=True)


@router.patch("/{incident_id}")
def actualizar(incident_id: str, cambios: IncidentUpdate, db: Session = Depends(get_db),
               user: UserModel = Depends(requiere("incidentes", nivel=EDITAR))):
    inc = ops.obtener_incidente(db, incident_id)
    ops.actualizar_incidente(db, inc, cambios.model_dump(exclude_unset=True), user.username)
    db.commit()
    db.refresh(inc)
    return ser.incidente(inc, detalle=True)


@router.post("/{incident_id}/notes")
def agregar_nota(incident_id: str, nota: NotaIncidente, db: Session = Depends(get_db),
                 user: UserModel = Depends(requiere("incidentes", nivel=EDITAR))):
    inc = ops.obtener_incidente(db, incident_id)
    ops.registrar_evento(db, inc.id, "note", nota.detalle, user.username, public=False)
    db.commit()
    db.refresh(inc)
    return ser.incidente(inc, detalle=True)


@router.post("/{incident_id}/dispatch")
def despachar(incident_id: str, db: Session = Depends(get_db), user: UserModel = Depends(requiere("incidentes", "despacho", nivel=EDITAR))):
    inc = ops.obtener_incidente(db, incident_id)
    plan = ops.despachar_incidente(db, inc, user.username)
    db.commit()
    db.refresh(inc)
    return {
        "assigned": [c.a_dict() for c in plan.asignaciones],
        "missing": plan.faltantes,
        "incident": ser.incidente(inc, detalle=True),
    }


@router.get("/{incident_id}/dispatch-preview")
def previsualizar(incident_id: str, db: Session = Depends(get_db), _: UserModel = Depends(requiere("incidentes", "despacho", "panel"))):
    """Muestra cómo el algoritmo ordena las unidades candidatas (no asigna nada)."""
    inc = ops.obtener_incidente(db, incident_id)
    plan = ops.previsualizar_despacho(db, inc)
    return {
        "incident_node": inc.node,
        "ranking": {tipo: [c.a_dict() for c in lista] for tipo, lista in plan.ranking.items()},
        "would_assign": [c.codigo for c in plan.asignaciones],
        "missing": plan.faltantes,
    }


@router.post("/{incident_id}/arrive")
def llegada(incident_id: str, db: Session = Depends(get_db), user: UserModel = Depends(requiere("incidentes", nivel=EDITAR))):
    inc = ops.obtener_incidente(db, incident_id)
    ops.marcar_en_escena(db, inc, user.username)
    db.commit()
    db.refresh(inc)
    return ser.incidente(inc, detalle=True)


@router.post("/{incident_id}/resolve")
def resolver(incident_id: str, nota: Optional[str] = Body(None, embed=True), db: Session = Depends(get_db),
             user: UserModel = Depends(requiere("incidentes", nivel=EDITAR))):
    inc = ops.obtener_incidente(db, incident_id)
    reasignados = ops.resolver_incidente(db, inc, user.username, nota)
    db.commit()
    db.refresh(inc)
    return {"incident": ser.incidente(inc, detalle=True), "queue_dispatched": reasignados}


@router.post("/{incident_id}/cancel")
def cancelar(incident_id: str, motivo: Optional[str] = Body(None, embed=True), db: Session = Depends(get_db),
             user: UserModel = Depends(requiere("incidentes", nivel=EDITAR))):
    inc = ops.obtener_incidente(db, incident_id)
    reasignados = ops.cancelar_incidente(db, inc, user.username, motivo)
    db.commit()
    db.refresh(inc)
    return {"incident": ser.incidente(inc, detalle=True), "queue_dispatched": reasignados}
