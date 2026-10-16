"""Inventario de la flota (ambulancias, bomberos, policía, rescate)."""
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import AssignmentModel, ResourceModel, UserModel
from app.schemas import ResourceCreate, ResourceUpdate
from app.permisos import EDITAR
from app.security import requiere
from app.servicios import serializadores as ser
from app.servicios.operaciones import incidente_activo_de_recurso, procesar_cola

router = APIRouter(prefix="/api/admin/resources", tags=["Recursos"])


def _obtener(db: Session, code: str) -> ResourceModel:
    r = db.get(ResourceModel, code)
    if r is None:
        raise HTTPException(status_code=404, detail=f"No existe la unidad {code}.")
    return r


@router.get("")
def listar(type: Optional[str] = None, status: Optional[str] = None, department: Optional[str] = None,
           db: Session = Depends(get_db), _: UserModel = Depends(requiere("flota", "despacho", "incidentes", "panel"))):
    consulta = db.query(ResourceModel)
    if type:
        consulta = consulta.filter(ResourceModel.type == type)
    if status:
        consulta = consulta.filter(ResourceModel.status == status)
    activos = incidente_activo_de_recurso(db)
    datos = [ser.recurso(r, activos.get(r.code)) for r in consulta.order_by(ResourceModel.code).all()]
    if department:
        datos = [d for d in datos if d["department_code"] == department]
    return datos


@router.post("", status_code=201)
def crear(datos: ResourceCreate, db: Session = Depends(get_db), user: UserModel = Depends(requiere("flota", nivel=EDITAR))):
    if db.get(ResourceModel, datos.code):
        raise HTTPException(status_code=409, detail=f"Ya existe una unidad con el código {datos.code}.")
    nodo = datos.nodo_base()
    r = ResourceModel(code=datos.code, type=datos.type, name=datos.name,
                      base_node=nodo, current_node=nodo, status="available")
    db.add(r)
    db.flush()
    procesar_cola(db, user.username)  # una unidad nueva puede atender la cola de espera
    db.commit()
    db.refresh(r)
    return ser.recurso(r, incidente_activo_de_recurso(db).get(r.code))


@router.patch("/{code}")
def actualizar(code: str, cambios: ResourceUpdate, db: Session = Depends(get_db),
               user: UserModel = Depends(requiere("flota", nivel=EDITAR))):
    r = _obtener(db, code)
    datos = cambios.model_dump(exclude_unset=True)
    if "status" in datos and datos["status"] is not None:
        if r.status in ("dispatched", "on_scene"):
            raise HTTPException(status_code=409, detail="La unidad está atendiendo un incidente; libérela primero.")
        r.status = datos["status"]
    if datos.get("name"):
        r.name = datos["name"]
    nodo = cambios.nodo_base()
    if nodo is not None:
        r.base_node = nodo
    db.flush()
    if r.status == "available":
        procesar_cola(db, user.username)
    db.commit()
    db.refresh(r)
    return ser.recurso(r, incidente_activo_de_recurso(db).get(r.code))


@router.post("/{code}/return-base")
def retornar_a_base(code: str, db: Session = Depends(get_db), _: UserModel = Depends(requiere("flota", nivel=EDITAR))):
    r = _obtener(db, code)
    if r.status != "available":
        raise HTTPException(status_code=409, detail="Solo una unidad disponible puede regresar a su base.")
    r.current_node = r.base_node
    db.commit()
    db.refresh(r)
    return ser.recurso(r)


@router.delete("/{code}", status_code=204)
def eliminar(code: str, db: Session = Depends(get_db), _: UserModel = Depends(requiere("flota", nivel=EDITAR))):
    r = _obtener(db, code)
    if r.status in ("dispatched", "on_scene"):
        raise HTTPException(status_code=409, detail="No se puede eliminar una unidad que está atendiendo un incidente.")
    if db.query(AssignmentModel).filter(AssignmentModel.resource_code == code).count() > 0:
        raise HTTPException(status_code=409, detail="La unidad tiene historial de despachos. Póngala en mantenimiento en lugar de eliminarla.")
    db.delete(r)
    db.commit()
