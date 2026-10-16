"""Cola de espera y asignación manual."""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import UserModel
from app.schemas import ManualAssign
from app.permisos import EDITAR
from app.security import requiere
from app.servicios import operaciones as ops
from app.servicios import serializadores as ser

router = APIRouter(prefix="/api/admin/dispatch", tags=["Despacho"])


@router.get("/queue")
def cola(db: Session = Depends(get_db), _: UserModel = Depends(requiere("despacho"))):
    """Incidentes esperando unidades, en el orden en que se atenderán (montículo)."""
    return ops.cola_de_espera(db)


@router.post("/process-queue")
def procesar(db: Session = Depends(get_db), user: UserModel = Depends(requiere("despacho", "incidentes", nivel=EDITAR))):
    resultados = ops.procesar_cola(db, user.username)
    db.commit()
    return {"dispatched": resultados, "remaining": ops.cola_de_espera(db)}


@router.post("/manual")
def asignar_manual(datos: ManualAssign, db: Session = Depends(get_db), user: UserModel = Depends(requiere("incidentes", "despacho", nivel=EDITAR))):
    inc = ops.obtener_incidente(db, datos.incident_id)
    ops.asignar_manual(db, inc, datos.resource_code, user.username)
    db.commit()
    db.refresh(inc)
    return ser.incidente(inc, detalle=True)
