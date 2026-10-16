"""Autenticación con JWT."""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import UserModel
from app.schemas import LoginRequest
from app.security import crear_token, get_current_user, verify_password
from app.servicios import serializadores as ser

router = APIRouter(prefix="/api/auth", tags=["Autenticación"])


@router.post("/login")
def login(credenciales: LoginRequest, db: Session = Depends(get_db)):
    user = db.query(UserModel).filter(UserModel.username == credenciales.username).first()
    if user is None or not verify_password(credenciales.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Credenciales incorrectas. Verifique usuario y contraseña.",
        )
    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="El usuario está desactivado.")
    return {
        "access_token": crear_token(user),
        "token_type": "bearer",
        "user": ser.usuario(user),
    }


@router.get("/me")
def yo(user: UserModel = Depends(get_current_user)):
    return ser.usuario(user)
