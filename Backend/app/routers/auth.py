"""Autenticación con JWT y recuperación de contraseña."""
import secrets
from datetime import datetime, timedelta

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request, status
from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.models import PasswordResetModel, UserModel
from app.ratelimit import FALLOS_LOGIN, INTENTOS_RESTABLECER, SOLICITUDES_RECUPERACION, ip_cliente
from app.schemas import LoginRequest, OlvideContrasena, RestablecerContrasena
from app.security import (
    HASH_RELLENO,
    crear_token,
    get_current_user,
    hash_password,
    hash_token,
    hay_que_rotar_hash,
    verify_password,
)
from app.servicios import serializadores as ser
from app.servicios.correo import enviar_recuperacion

router = APIRouter(prefix="/api/auth", tags=["Autenticación"])

MENSAJE_RECUPERACION = ("Si la cuenta existe y tiene un correo registrado, enviamos un enlace para "
                        "restablecer la contraseña. Revise también la carpeta de spam.")


def _credenciales_incorrectas() -> HTTPException:
    return HTTPException(status.HTTP_401_UNAUTHORIZED, "Credenciales incorrectas. Verifique usuario y contraseña.")


@router.post("/login")
def login(credenciales: LoginRequest, request: Request, db: Session = Depends(get_db)):
    ip = ip_cliente(request)
    nombre = credenciales.username.strip().lower()
    claves = (f"ip:{ip}", f"user:{nombre}")
    if any(FALLOS_LOGIN.bloqueado(k) for k in claves):
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS,
                            "Demasiados intentos fallidos. Espere unos minutos e intente de nuevo.",
                            headers={"Retry-After": str(settings.LOGIN_VENTANA_MIN * 60)})

    user = db.query(UserModel).filter(func.lower(UserModel.username) == nombre).first()
    # Siempre se calcula el hash (aunque el usuario no exista) para no revelar usuarios por el tiempo de respuesta.
    correcta = verify_password(credenciales.password, user.password_hash if user else HASH_RELLENO)
    # Un usuario desactivado recibe el mismo error genérico: no se confirma que la contraseña era válida.
    if user is None or not correcta or not user.is_active:
        for k in claves:
            FALLOS_LOGIN.registrar(k)
        raise _credenciales_incorrectas()

    for k in claves:
        FALLOS_LOGIN.olvidar(k)
    if hay_que_rotar_hash(user.password_hash):  # sube las iteraciones de hashes antiguos
        user.password_hash = hash_password(credenciales.password)
        db.commit()
    return {
        "access_token": crear_token(user),
        "token_type": "bearer",
        "user": ser.usuario(user),
    }


@router.get("/me")
def yo(user: UserModel = Depends(get_current_user)):
    return ser.usuario(user)


# ------------------------------------------------- recuperación de contraseña
@router.post("/forgot-password")
def olvide_contrasena(datos: OlvideContrasena, request: Request, tareas: BackgroundTasks,
                      db: Session = Depends(get_db)):
    """
    Envía un enlace de un solo uso al correo de la cuenta. La respuesta es SIEMPRE la
    misma, exista o no la cuenta, para no revelar qué usuarios o correos hay registrados.
    """
    identificador = datos.identificador.strip().lower()
    SOLICITUDES_RECUPERACION.exigir(f"ip:{ip_cliente(request)}")
    SOLICITUDES_RECUPERACION.exigir(f"id:{identificador}")

    user = (
        db.query(UserModel)
        .filter(or_(func.lower(UserModel.username) == identificador, func.lower(UserModel.email) == identificador))
        .first()
    )
    if user is not None and user.is_active and user.email:
        token = secrets.token_urlsafe(32)
        ahora = datetime.now()
        # Un solo enlace vigente por usuario: los anteriores quedan inservibles.
        db.query(PasswordResetModel).filter(
            PasswordResetModel.user_id == user.id, PasswordResetModel.used_at.is_(None)
        ).update({"used_at": ahora})
        db.add(PasswordResetModel(
            user_id=user.id, token_hash=hash_token(token),
            expires_at=ahora + timedelta(minutes=settings.RESET_TOKEN_MINUTES),
        ))
        db.commit()
        enlace = f"{settings.FRONTEND_URL}/#/admin/restablecer/{token}"
        tareas.add_task(enviar_recuperacion, user.email, user.full_name, enlace, settings.RESET_TOKEN_MINUTES)
    return {"message": MENSAJE_RECUPERACION}


@router.post("/reset-password")
def restablecer_contrasena(datos: RestablecerContrasena, request: Request, db: Session = Depends(get_db)):
    INTENTOS_RESTABLECER.exigir(f"ip:{ip_cliente(request)}")
    ahora = datetime.now()
    registro = db.query(PasswordResetModel).filter(PasswordResetModel.token_hash == hash_token(datos.token)).first()
    invalido = HTTPException(status.HTTP_400_BAD_REQUEST,
                             "El enlace no es válido o ya venció. Solicite uno nuevo desde «¿Olvidó su contraseña?».")
    if registro is None or registro.used_at is not None or registro.expires_at < ahora:
        raise invalido
    user = db.get(UserModel, registro.user_id)
    if user is None or not user.is_active:
        raise invalido

    user.password_hash = hash_password(datos.password)
    user.token_version = (user.token_version or 0) + 1  # cierra todas las sesiones abiertas
    db.query(PasswordResetModel).filter(
        PasswordResetModel.user_id == user.id, PasswordResetModel.used_at.is_(None)
    ).update({"used_at": ahora})
    db.commit()
    FALLOS_LOGIN.olvidar(f"user:{user.username.lower()}")
    return {"message": "Contraseña actualizada. Ya puede iniciar sesión."}
