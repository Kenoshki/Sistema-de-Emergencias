"""
Carga de datos de muestra: 100 incidentes recientes (ya cerrados, con sus unidades y bitácora)
y 3 usuarios de perfiles distintos. Es idempotente: si los usuarios ya existen, no hace nada.

Se activa con CARGAR_MUESTRA=True (al arrancar) o con `python scripts/cargar_muestra.py`.
Los incidentes se generan con los mismos algoritmos del sistema (ver app/simulacion.py).
"""
from __future__ import annotations

import secrets
from datetime import datetime

from sqlalchemy.orm import Session

from app.config import settings
from app.models import IncidentModel, UserModel
from app.security import hash_password
from app.seed import insertar_historial
from app.servicios.operaciones import _ALFABETO_CODIGO
from app.simulacion import generar_historial

# (usuario, nombre, perfil)
USUARIOS_MUESTRA = [
    ("muestra.incidentes", "Operador de incidentes (muestra)", "incidentes"),
    ("muestra.flota", "Operador de flota (muestra)", "flota"),
    ("muestra.red", "Operador de red vial (muestra)", "red_vial"),
]


def cargar_muestra(db: Session, cantidad: int | None = None, password: str | None = None) -> dict:
    cantidad = cantidad or settings.MUESTRA_CANTIDAD
    password = password or settings.MUESTRA_PASS
    if db.query(UserModel).filter(UserModel.username == USUARIOS_MUESTRA[0][0]).first():
        return {"incidentes": 0, "usuarios": 0, "omitido": True}
    if len(password) < 10:
        raise RuntimeError("MUESTRA_PASS debe tener al menos 10 caracteres.")

    # Los más recientes de un historial de 30 días; el sufijo aleatorio evita choques de código.
    historial = generar_historial(dias=30, ahora=datetime.now(), semilla=2027)[-cantidad:]
    existentes = {i for (i,) in db.query(IncidentModel.id).all()}
    for h in historial:
        h["id"] = f"{h['id']}-{''.join(secrets.choice(_ALFABETO_CODIGO) for _ in range(4))}"
        while h["id"] in existentes:
            h["id"] = f"{h['id'][:-4]}{''.join(secrets.choice(_ALFABETO_CODIGO) for _ in range(4))}"
    insertados = insertar_historial(db, historial)

    for usuario, nombre, rol in USUARIOS_MUESTRA:
        db.add(UserModel(username=usuario, password_hash=hash_password(password),
                         full_name=nombre, role=rol, is_active=True))
    db.commit()
    return {"incidentes": insertados, "usuarios": len(USUARIOS_MUESTRA), "omitido": False}
