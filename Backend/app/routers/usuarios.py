"""Administración de usuarios y permisos por módulo (solo administradores)."""
import json

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session

from app import permisos
from app.database import get_db
from app.models import UserModel
from app.schemas import UserCreate, UserUpdate
from app.security import hash_password, require_admin
from app.servicios import serializadores as ser

router = APIRouter(prefix="/api/admin/users", tags=["Usuarios"])


def _guardar_permisos(u: UserModel, ajustes: dict[str, int] | None) -> None:
    """Guarda solo lo que difiere del perfil del rol (así, si cambia el perfil, el resto se actualiza solo)."""
    if u.role == "admin" or not ajustes:
        u.permissions = None
        return
    perfil = permisos.ROLES[u.role]["permisos"]
    diferencias = {m: n for m, n in ajustes.items() if perfil.get(m, permisos.SIN_ACCESO) != n}
    u.permissions = json.dumps(diferencias) if diferencias else None


def _correo_en_uso(db: Session, correo: str, excepto_id: int | None = None) -> bool:
    consulta = db.query(UserModel).filter(func.lower(UserModel.email) == correo.lower())
    if excepto_id is not None:
        consulta = consulta.filter(UserModel.id != excepto_id)
    return consulta.first() is not None


@router.get("/roles")
def roles(_: UserModel = Depends(require_admin)):
    """Perfiles predefinidos, módulos y niveles para la pantalla de usuarios."""
    return permisos.catalogo()


@router.get("")
def listar(db: Session = Depends(get_db), _: UserModel = Depends(require_admin)):
    return [ser.usuario(u) for u in db.query(UserModel).order_by(UserModel.username).all()]


@router.post("", status_code=201)
def crear(datos: UserCreate, db: Session = Depends(get_db), _: UserModel = Depends(require_admin)):
    if db.query(UserModel).filter(UserModel.username == datos.username).first():
        raise HTTPException(status_code=409, detail="Ese nombre de usuario ya existe.")
    if datos.email and _correo_en_uso(db, datos.email):
        raise HTTPException(status_code=409, detail="Ese correo ya está asignado a otro usuario.")
    u = UserModel(username=datos.username, password_hash=hash_password(datos.password),
                  full_name=datos.full_name, email=datos.email, role=datos.role, is_active=True)
    _guardar_permisos(u, datos.permissions)
    db.add(u)
    db.commit()
    db.refresh(u)
    return ser.usuario(u)


@router.patch("/{user_id}")
def actualizar(user_id: int, cambios: UserUpdate, db: Session = Depends(get_db), actual: UserModel = Depends(require_admin)):
    u = db.get(UserModel, user_id)
    if u is None:
        raise HTTPException(status_code=404, detail="Usuario no encontrado.")
    if u.id == actual.id and (cambios.is_active is False or (cambios.role and cambios.role != "admin")):
        raise HTTPException(status_code=400, detail="No puede desactivarse ni quitarse el rol de administrador a sí mismo.")
    if cambios.email is not None:
        if cambios.email and _correo_en_uso(db, cambios.email, u.id):
            raise HTTPException(status_code=409, detail="Ese correo ya está asignado a otro usuario.")
        u.email = cambios.email or None
    if cambios.full_name is not None:
        u.full_name = cambios.full_name
    if cambios.role is not None and cambios.role != u.role:
        u.role = cambios.role
        u.permissions = None  # al cambiar de rol se parte del perfil nuevo
        u.token_version = (u.token_version or 0) + 1  # las sesiones abiertas dejan de valer
    if cambios.reset_permissions:
        u.permissions = None
    elif cambios.permissions is not None:
        _guardar_permisos(u, {**permisos.efectivos(u), **cambios.permissions})
    if cambios.is_active is not None:
        if cambios.is_active != u.is_active:
            u.token_version = (u.token_version or 0) + 1
        u.is_active = cambios.is_active
    if cambios.password:
        u.password_hash = hash_password(cambios.password)
        u.token_version = (u.token_version or 0) + 1
    db.commit()
    db.refresh(u)
    return ser.usuario(u)
