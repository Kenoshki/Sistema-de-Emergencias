"""
Seguridad: contraseñas con hash (PBKDF2-SHA256) y tokens JWT.

PBKDF2 viene incluido en Python (hashlib), así que no requiere librerías
compiladas. Nunca se guarda la contraseña en texto plano.
"""
import base64
import hashlib
import hmac
import secrets
from datetime import datetime, timedelta, timezone

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.models import UserModel

ITERACIONES = 260_000
_bearer = HTTPBearer(auto_error=False)


# ------------------------------------------------------------- contraseñas
def hash_password(password: str) -> str:
    sal = secrets.token_bytes(16)
    derivada = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), sal, ITERACIONES)
    return "pbkdf2_sha256${}${}${}".format(
        ITERACIONES,
        base64.b64encode(sal).decode(),
        base64.b64encode(derivada).decode(),
    )


def verify_password(password: str, guardado: str) -> bool:
    try:
        algoritmo, iteraciones, sal_b64, hash_b64 = guardado.split("$")
        if algoritmo != "pbkdf2_sha256":
            return False
        sal = base64.b64decode(sal_b64)
        esperado = base64.b64decode(hash_b64)
        calculado = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), sal, int(iteraciones))
        return hmac.compare_digest(calculado, esperado)
    except (ValueError, TypeError):
        return False


# Hash de relleno: el login siempre calcula PBKDF2, exista o no el usuario (evita adivinar usuarios por el tiempo).
HASH_RELLENO = hash_password(secrets.token_urlsafe(16))


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def hay_que_rotar_hash(guardado: str) -> bool:
    return not guardado.startswith(f"pbkdf2_sha256${ITERACIONES}$")


# ------------------------------------------------------------------- JWT
def crear_token(user: UserModel) -> str:
    expira = datetime.now(timezone.utc) + timedelta(minutes=settings.JWT_EXPIRE_MINUTES)
    payload = {"sub": user.username, "role": user.role, "tv": user.token_version or 0, "exp": expira}
    return jwt.encode(payload, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)


def _no_autorizado(detalle: str) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail=detalle,
        headers={"WWW-Authenticate": "Bearer"},
    )


def get_current_user(
    credenciales: HTTPAuthorizationCredentials | None = Depends(_bearer),
    db: Session = Depends(get_db),
) -> UserModel:
    if credenciales is None:
        raise _no_autorizado("Debe iniciar sesión para acceder a este recurso.")
    try:
        payload = jwt.decode(credenciales.credentials, settings.JWT_SECRET, algorithms=[settings.JWT_ALGORITHM])
    except jwt.ExpiredSignatureError:
        raise _no_autorizado("La sesión expiró. Inicie sesión de nuevo.") from None
    except jwt.InvalidTokenError:
        raise _no_autorizado("Token inválido.") from None

    user = db.query(UserModel).filter(UserModel.username == payload.get("sub")).first()
    if user is None or not user.is_active or payload.get("tv", 0) != (user.token_version or 0):
        raise _no_autorizado("Usuario no encontrado o desactivado.")
    return user


def require_admin(user: UserModel = Depends(get_current_user)) -> UserModel:
    if user.role != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Solo un administrador puede realizar esta acción.")
    return user


def requiere(*modulos: str, nivel: int = 1):
    """
    Dependencia de FastAPI: deja pasar si el usuario tiene al menos `nivel`
    (1 ver, 2 editar) en ALGUNO de los módulos indicados.
    Ejemplo: Depends(requiere("flota", nivel=EDITAR)).
    """
    from app.permisos import EDITAR, MODULOS, tiene

    def _verificar(user: UserModel = Depends(get_current_user)) -> UserModel:
        if not tiene(user, modulos, nivel):
            accion = "modificar" if nivel >= EDITAR else "consultar"
            nombres = " o ".join(MODULOS[m]["nombre"] for m in modulos)
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,
                                detail=f"Su usuario no tiene permiso para {accion} {nombres}. Consulte al administrador.")
        return user
    return _verificar
