"""
Datos iniciales:
- Usuario administrador (desde el .env).
- Operadores de demostración por perfil (si SEED_DEMO_DATA=True).
- Catálogo de 22 departamentos y 340 municipios (app/datos/geografia_gt.json).
- Flota nacional: 20 unidades en la capital, unidades metropolitanas y una base
  en cada cabecera departamental.
- (Opcional, SEED_DEMO_DATA=True) historial simulado de 60 días e
  incidentes activos, para que el panel tenga datos desde el primer uso
  (ver app/simulacion.py).
"""
from __future__ import annotations

import json

from sqlalchemy.orm import Session

from app.catalogos import TIPOS_RECURSO
from app.config import settings
from app.geografia import DEPARTAMENTOS, MUNICIPIOS, ZONAS_POR_MUNICIPIO, etiqueta_nodo
from app.models import (
    AssignmentModel,
    DepartmentModel,
    IncidentEventModel,
    IncidentModel,
    MunicipalityModel,
    ResourceModel,
    UserModel,
)
from app.security import hash_password
from app.simulacion import RECURSOS_INICIALES, generar_historial


def _crear_geografia(db: Session) -> None:
    if db.query(MunicipalityModel).count() == len(MUNICIPIOS):
        return
    existentes_d = {d.code for d in db.query(DepartmentModel).all()}
    for d in DEPARTAMENTOS.values():
        if d["codigo"] not in existentes_d:
            db.add(DepartmentModel(code=d["codigo"], name=d["nombre"], head_town=d["cabecera"],
                                   latitude=d["lat"], longitude=d["lon"]))
    db.flush()
    existentes_m = {m.code for m in db.query(MunicipalityModel).all()}
    for m in MUNICIPIOS.values():
        if m["codigo"] in existentes_m:
            continue
        zonas = ZONAS_POR_MUNICIPIO.get(m["codigo"])
        db.add(MunicipalityModel(
            code=m["codigo"], department_code=m["departamento"], name=m["nombre"],
            latitude=m["lat"], longitude=m["lon"], is_department_head=m["cabecera_departamental"],
            approximate=m["aproximada"], zones=",".join(str(z) for z in zonas) if zonas else None,
        ))
    db.commit()


def _crear_admin(db: Session) -> None:
    existente = db.query(UserModel).filter(UserModel.username == settings.DEFAULT_ADMIN_USER).first()
    if existente:
        if settings.DEFAULT_ADMIN_EMAIL and not existente.email:
            existente.email = settings.DEFAULT_ADMIN_EMAIL  # habilita «Olvidé mi contraseña» en cuentas anteriores
            db.commit()
        return
    db.add(UserModel(
        email=settings.DEFAULT_ADMIN_EMAIL or None,
        username=settings.DEFAULT_ADMIN_USER,
        password_hash=hash_password(settings.DEFAULT_ADMIN_PASS),
        full_name="Administrador del sistema",
        role="admin",
        is_active=True,
    ))
    db.commit()


def _crear_flota(db: Session) -> None:
    if db.query(ResourceModel).count() > 0:
        return
    for codigo, tipo, nodo in RECURSOS_INICIALES:
        db.add(ResourceModel(
            code=codigo, type=tipo,
            name=f"{TIPOS_RECURSO[tipo]} – Base {etiqueta_nodo(nodo)}"[:100],
            base_node=nodo, current_node=nodo, status="available",
        ))
    db.commit()


def insertar_historial(db: Session, historial: list[dict]) -> int:
    """Guarda incidentes ya resueltos/cancelados (con sus asignaciones y bitácora). Devuelve cuántos."""
    for h in historial:
        db.add(IncidentModel(
            id=h["id"], type=h["type"], priority=h["priority"],
            department_code=h["department_code"], municipality_code=h["municipality_code"],
            zone=h["zone"], node=h["node"], location_source="form",
            latitude=h["latitude"], longitude=h["longitude"], description=h["description"],
            source=h["source"], status=h["status"], pending_requirements="{}",
            reported_at=h["reported_at"], dispatched_at=h["dispatched_at"],
            arrived_at=h["arrived_at"], resolved_at=h["resolved_at"],
        ))
        eventos = [(h["reported_at"], "reported", f"Reporte recibido: {etiqueta_nodo(h['node'])}.")]
        for a in h["assignments"]:
            db.add(AssignmentModel(
                incident_id=h["id"], resource_code=a["codigo"], origin_node=a["nodo_origen"],
                distance_km=a["distancia_km"], eta_min=a["eta_min"], route=json.dumps(a["ruta"]),
                method="auto", active=False, assigned_at=h["dispatched_at"], released_at=h["resolved_at"],
            ))
            eventos.append((h["dispatched_at"], "unit_dispatched",
                            f"{TIPOS_RECURSO[a['tipo']]} {a['codigo']} en camino ({a['distancia_km']} km, ETA {a['eta_min']} min)."))
        if h["arrived_at"]:
            eventos.append((h["arrived_at"], "on_scene", "Las unidades llegaron al lugar del incidente."))
            eventos.append((h["resolved_at"], "resolved", "Incidente resuelto."))
        else:
            eventos.append((h["resolved_at"], "cancelled", "Incidente cancelado (falsa alarma)."))
        for cuando, evento, detalle in eventos:
            db.add(IncidentEventModel(incident_id=h["id"], timestamp=cuando, event=evento, detail=detalle, username="sistema"))
    db.commit()

    return len(historial)


def _crear_historial(db: Session) -> None:
    if db.query(IncidentModel).count() > 0:
        return
    insertar_historial(db, generar_historial())

    # Algunos incidentes activos creados con el flujo real (despacho automático).
    from app.schemas import IncidentCreate
    from app.servicios.operaciones import crear_incidente, despachar_incidente

    activos = [
        IncidentCreate(type="fire", priority=4, department_code="01", municipality_code="0101", zone=18,
                       description="Incendio en vivienda de dos niveles, posibles personas atrapadas",
                       reporter_name="Ana López", reporter_phone="55551234"),
        IncidentCreate(type="accident", priority=3, department_code="01", municipality_code="0101", zone=12,
                       description="Colisión múltiple frente a la USAC", reporter_phone="44448888"),
        IncidentCreate(type="landslide", priority=4, department_code="16", municipality_code="1601",
                       description="Deslave sobre viviendas tras lluvias intensas"),
        IncidentCreate(type="medical", priority=2, department_code="09", municipality_code="0901", zone=3,
                       description="Persona con desmayo en parada de bus"),
    ]
    for datos in activos:
        inc = crear_incidente(db, datos, "public")
        if not settings.AUTO_DISPATCH:
            despachar_incidente(db, inc, "sistema")
    db.commit()


# Un usuario de demostración por perfil, para probar los permisos por módulo.
USUARIOS_DEMO = [
    ("op.incidentes", "Operador de incidentes (demo)", "incidentes"),
    ("op.flota", "Operador de flota (demo)", "flota"),
    ("op.red", "Operador de red vial (demo)", "red_vial"),
]


def _crear_usuarios_demo(db: Session) -> None:
    for usuario, nombre, rol in USUARIOS_DEMO:
        if db.query(UserModel).filter(UserModel.username == usuario).first():
            continue
        db.add(UserModel(username=usuario, password_hash=hash_password(settings.DEMO_USERS_PASS),
                         full_name=nombre, role=rol, is_active=True))
    db.commit()


def sembrar_datos(db: Session) -> None:
    _crear_geografia(db)
    _crear_admin(db)
    _crear_flota(db)
    if settings.CARGAR_MUESTRA:
        from app.muestra import cargar_muestra
        cargar_muestra(db)
    if settings.SEED_DEMO_DATA:
        _crear_usuarios_demo(db)
        _crear_historial(db)
