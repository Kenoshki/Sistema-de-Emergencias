"""
Operaciones del ciclo de vida de un incidente (capa que toca la base de datos).

    reportado -> despachado -> en escena -> resuelto
         \\______________________________-> cancelado

Las funciones NO hacen commit: el router que las llama confirma la
transacción al final, así una operación es "todo o nada".
"""
from __future__ import annotations

import json
import secrets
from collections import Counter
from datetime import datetime

from sqlalchemy.orm import Session

from app.algoritmos.cola_prioridad import ColaIncidentes
from app.algoritmos.despacho import (
    PlanDespacho,
    RecursoDisponible,
    estimar_eta_min,
    planificar_despacho,
    restar_necesidades,
)
from app.algoritmos.grafo import INFINITO, RedVial
from app.catalogos import ESTADOS_ACTIVOS, TIPOS_RECURSO, requerimientos
from app.geografia import coordenadas_de, etiqueta_nodo, etiqueta_ubicacion, nodo_de
from app.config import settings
from app.models import (
    AssignmentModel,
    IncidentEventModel,
    IncidentModel,
    PlaceModel,
    ResourceModel,
    RoadClosureModel,
)
from app.schemas import IncidentCreate
from app.servicios.serializadores import leer_json


_ALFABETO_CODIGO = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"  # sin 0/O/1/I para dictarlo por teléfono


class ErrorOperacion(Exception):
    """Error de regla de negocio (se responde como HTTP 400/409)."""

    def __init__(self, mensaje: str, codigo_http: int = 400):
        super().__init__(mensaje)
        self.mensaje = mensaje
        self.codigo_http = codigo_http


# ------------------------------------------------------------------ apoyo
def registrar_evento(
    db: Session, incident_id: str, event: str, detail: str,
    username: str | None = None, public: bool = True, cuando: datetime | None = None,
) -> None:
    db.add(IncidentEventModel(
        incident_id=incident_id, event=event, detail=detail[:255],
        username=username, public=public, timestamp=cuando or datetime.now(),
    ))


def generar_id_incidente(db: Session, fecha: datetime | None = None) -> str:
    """
    Formato INC-AAAAMMDD-NNNN-XXXX: consecutivo por día más 4 caracteres aleatorios.
    El sufijo hace que el código no se pueda adivinar recorriendo la secuencia
    (el seguimiento ciudadano es público) y evita colisiones entre reportes simultáneos.
    """
    fecha = fecha or datetime.now()
    prefijo = f"INC-{fecha:%Y%m%d}-"
    ultimo = (
        db.query(IncidentModel.id)
        .filter(IncidentModel.id.like(prefijo + "%"))
        .order_by(IncidentModel.id.desc())
        .first()
    )
    siguiente = int(ultimo[0].split("-")[2]) + 1 if ultimo else 1
    sufijo = "".join(secrets.choice(_ALFABETO_CODIGO) for _ in range(4))
    return f"{prefijo}{siguiente:04d}-{sufijo}"


def construir_red(db: Session) -> RedVial:
    cierres = db.query(RoadClosureModel).all()
    return RedVial(vias_cerradas={(c.node_a, c.node_b) for c in cierres})


def obtener_incidente(db: Session, incident_id: str) -> IncidentModel:
    inc = db.get(IncidentModel, incident_id)
    if inc is None:
        raise ErrorOperacion(f"No existe el incidente {incident_id}.", 404)
    return inc


def _unidades_activas_por_tipo(inc: IncidentModel) -> dict[str, int]:
    return dict(Counter(a.resource.type for a in inc.assignments if a.active and a.resource))


def _describir_faltantes(faltantes: dict[str, int]) -> str:
    return ", ".join(f"{n} {TIPOS_RECURSO.get(t, t)}" for t, n in faltantes.items())


def _liberar_unidades(db: Session, inc: IncidentModel, mover_al_lugar: bool) -> list[str]:
    ahora = datetime.now()
    liberadas = []
    for a in inc.assignments:
        if not a.active:
            continue
        a.active = False
        a.released_at = ahora
        if a.resource:
            a.resource.status = "available"
            if mover_al_lugar:
                a.resource.current_node = inc.node
            liberadas.append(a.resource_code)
    return liberadas


# ---------------------------------------------------------- crear / editar
def crear_incidente(db: Session, data: IncidentCreate, source: str, username: str | None = None) -> IncidentModel:
    # La ubicación ya viene validada por el esquema (departamento, municipio y zona).
    if not (data.department_code and data.municipality_code):
        raise ErrorOperacion("Falta el departamento o el municipio del incidente.", 422)
    municipio, zona = data.municipality_code, data.zone

    lugar_nombre = data.place_name
    lugar_coords = None
    if data.place_id is not None:
        lugar = db.get(PlaceModel, data.place_id)
        if lugar is None or lugar.municipality_code != municipio:
            raise ErrorOperacion("La aldea o colonia seleccionada no pertenece al municipio elegido.", 422)
        lugar_nombre = lugar.name
        if lugar.latitude is not None and lugar.longitude is not None:
            lugar_coords = (lugar.latitude, lugar.longitude)

    if data.latitude is not None and data.longitude is not None:
        lat, lon, origen_ubicacion = data.latitude, data.longitude, "gps"
    elif lugar_coords:
        (lat, lon), origen_ubicacion = lugar_coords, "form"
    else:
        (lat, lon), origen_ubicacion = coordenadas_de(municipio, zona), "form"

    nodo = nodo_de(municipio, zona)
    inc = IncidentModel(
        id=generar_id_incidente(db),
        type=data.type,
        priority=data.priority,
        department_code=data.department_code,
        municipality_code=municipio,
        zone=zona,
        place_id=data.place_id,
        place_name=lugar_nombre,
        node=nodo,
        location_source=origen_ubicacion,
        latitude=lat,
        longitude=lon,
        address=data.address,
        description=data.description,
        reporter_name=data.reporter_name,
        reporter_phone=data.reporter_phone,
        source=source,
        status="pending",
        pending_requirements=json.dumps(requerimientos(data.type, data.priority)),
        reported_at=datetime.now(),
    )
    db.add(inc)
    db.flush()
    origen = "Reporte ciudadano" if source == "public" else f"Registrado por operador {username}"
    ubicacion = etiqueta_ubicacion(data.department_code, municipio, zona, lugar_nombre)
    registrar_evento(db, inc.id, "reported", f"{origen} recibido: {ubicacion}.", username)

    if settings.AUTO_DISPATCH:
        despachar_incidente(db, inc, username or "sistema")
    return inc


def actualizar_incidente(db: Session, inc: IncidentModel, cambios: dict, username: str) -> IncidentModel:
    if inc.status not in ESTADOS_ACTIVOS:
        raise ErrorOperacion("No se puede modificar un incidente cerrado.", 409)
    descripcion_cambios = []
    for campo, valor in cambios.items():
        if valor is None or getattr(inc, campo) == valor:
            continue
        descripcion_cambios.append(f"{campo}: {getattr(inc, campo)} → {valor}")
        setattr(inc, campo, valor)

    if not descripcion_cambios:
        return inc

    registrar_evento(db, inc.id, "updated", "Reclasificado: " + "; ".join(descripcion_cambios), username, public=False)
    # Si cambió tipo o prioridad, se recalculan las unidades que faltan.
    if "priority" in cambios or "type" in cambios:
        faltan = restar_necesidades(requerimientos(inc.type, inc.priority), _unidades_activas_por_tipo(inc))
        inc.pending_requirements = json.dumps(faltan)
        if faltan and settings.AUTO_DISPATCH:
            despachar_incidente(db, inc, username)
    return inc


# --------------------------------------------------------------- despacho
def despachar_incidente(db: Session, inc: IncidentModel, username: str) -> PlanDespacho:
    """Asigna automáticamente las unidades más cercanas que aún falten."""
    if inc.status not in ESTADOS_ACTIVOS:
        raise ErrorOperacion("El incidente ya está cerrado.", 409)

    necesidades = restar_necesidades(requerimientos(inc.type, inc.priority), _unidades_activas_por_tipo(inc))
    if not necesidades:
        inc.pending_requirements = "{}"
        return PlanDespacho()

    disponibles = (
        db.query(ResourceModel)
        .filter(ResourceModel.status == "available", ResourceModel.type.in_(list(necesidades)))
        .with_for_update()  # bloquea las filas en MySQL para evitar asignar dos veces la misma unidad
        .all()
    )
    plan = planificar_despacho(
        inc.node, inc.priority, necesidades,
        [RecursoDisponible(r.code, r.type, r.current_node) for r in disponibles],
        construir_red(db),
    )

    por_codigo = {r.code: r for r in disponibles}
    ahora = datetime.now()
    for c in plan.asignaciones:
        r = por_codigo[c.codigo]
        r.status = "dispatched"
        db.add(AssignmentModel(
            incident_id=inc.id, resource_code=r.code, origin_node=c.nodo_origen,
            distance_km=c.distancia_km, eta_min=c.eta_min, route=json.dumps(c.ruta),
            method="auto", active=True, assigned_at=ahora,
        ))
        registrar_evento(
            db, inc.id, "unit_dispatched",
            f"{TIPOS_RECURSO.get(r.type, r.type)} {r.code} en camino desde {etiqueta_nodo(c.nodo_origen)} "
            f"({c.distancia_km} km, llegada estimada {c.eta_min} min).",
            username,
        )

    if plan.asignaciones:
        inc.dispatched_at = inc.dispatched_at or ahora
        if inc.status == "pending":
            inc.status = "dispatched"

    inc.pending_requirements = json.dumps(plan.faltantes)
    if plan.faltantes:
        registrar_evento(
            db, inc.id, "units_missing",
            f"Sin unidades disponibles por ahora: {_describir_faltantes(plan.faltantes)}. "
            "El incidente queda en cola de espera.",
            username,
        )
    db.flush()
    db.refresh(inc)
    return plan


def asignar_manual(db: Session, inc: IncidentModel, codigo_recurso: str, username: str) -> AssignmentModel:
    if inc.status not in ESTADOS_ACTIVOS:
        raise ErrorOperacion("El incidente ya está cerrado.", 409)
    r = db.get(ResourceModel, codigo_recurso)
    if r is None:
        raise ErrorOperacion(f"No existe la unidad {codigo_recurso}.", 404)
    if r.status != "available":
        raise ErrorOperacion(f"La unidad {r.code} no está disponible ({r.status}).", 409)

    distancia, ruta = construir_red(db).ruta(r.current_node, inc.node)
    if distancia == INFINITO:
        raise ErrorOperacion("No hay ruta disponible: el lugar está aislado por vías cerradas.", 409)

    ahora = datetime.now()
    eta = estimar_eta_min(distancia, r.type, inc.priority)
    asignacion = AssignmentModel(
        incident_id=inc.id, resource_code=r.code, origin_node=r.current_node,
        distance_km=round(distancia, 2), eta_min=eta, route=json.dumps(ruta),
        method="manual", active=True, assigned_at=ahora,
    )
    db.add(asignacion)
    r.status = "on_scene" if inc.status == "on_scene" and r.current_node == inc.node else "dispatched"
    inc.dispatched_at = inc.dispatched_at or ahora
    if inc.status == "pending":
        inc.status = "dispatched"
    db.flush()
    db.refresh(inc)

    faltan = restar_necesidades(requerimientos(inc.type, inc.priority), _unidades_activas_por_tipo(inc))
    inc.pending_requirements = json.dumps(faltan)
    registrar_evento(
        db, inc.id, "unit_dispatched",
        f"{TIPOS_RECURSO.get(r.type, r.type)} {r.code} asignada manualmente "
        f"({round(distancia, 2)} km, llegada estimada {eta} min).",
        username,
    )
    return asignacion


def previsualizar_despacho(db: Session, inc: IncidentModel) -> PlanDespacho:
    """Ranking de TODAS las unidades disponibles para cada tipo (sin asignar nada)."""
    necesidades = requerimientos(inc.type, inc.priority)
    disponibles = db.query(ResourceModel).filter(
        ResourceModel.status == "available", ResourceModel.type.in_(list(necesidades))
    ).all()
    return planificar_despacho(
        inc.node, inc.priority,
        restar_necesidades(necesidades, _unidades_activas_por_tipo(inc)) or necesidades,
        [RecursoDisponible(r.code, r.type, r.current_node) for r in disponibles],
        construir_red(db),
    )


def _incidentes_en_espera(db: Session) -> list[IncidentModel]:
    activos = db.query(IncidentModel).filter(IncidentModel.status.in_(ESTADOS_ACTIVOS)).all()
    return [i for i in activos if leer_json(i.pending_requirements, {})]


def cola_de_espera(db: Session) -> list[dict]:
    cola = ColaIncidentes()
    incidentes = {i.id: i for i in _incidentes_en_espera(db)}
    for inc in incidentes.values():
        cola.insertar(inc.id, inc.priority, inc.reported_at)
    vista = cola.en_orden()
    for fila in vista:
        inc = incidentes[fila["incidente_id"]]
        fila["reportado"] = fila["reportado"].isoformat(timespec="seconds")
        fila["tipo"] = inc.type
        fila["nodo"] = inc.node
        fila["ubicacion"] = etiqueta_ubicacion(inc.department_code, inc.municipality_code, inc.zone, inc.place_name)
        fila["estado"] = inc.status
        fila["faltantes"] = leer_json(inc.pending_requirements, {})
        fila["minutos_espera"] = round((datetime.now() - inc.reported_at).total_seconds() / 60, 1)
    return vista


def procesar_cola(db: Session, username: str) -> list[dict]:
    """
    Atiende la cola de espera en orden de prioridad efectiva (montículo).
    Se ejecuta automáticamente cada vez que se libera una unidad.
    """
    cola = ColaIncidentes()
    for inc in _incidentes_en_espera(db):
        cola.insertar(inc.id, inc.priority, inc.reported_at)

    resultados = []
    while cola:
        entrada = cola.extraer()
        inc = db.get(IncidentModel, entrada.incidente_id)
        if inc is None:
            continue
        plan = despachar_incidente(db, inc, username)
        if plan.asignaciones:
            resultados.append({
                "incidente_id": inc.id,
                "asignadas": [c.codigo for c in plan.asignaciones],
                "faltantes": plan.faltantes,
            })
    return resultados


# --------------------------------------------------------- cambio de estado
def marcar_en_escena(db: Session, inc: IncidentModel, username: str) -> IncidentModel:
    if inc.status != "dispatched":
        raise ErrorOperacion("Solo un incidente con unidades en camino puede pasar a 'en escena'.", 409)
    inc.status = "on_scene"
    inc.arrived_at = datetime.now()
    for a in inc.assignments:
        if a.active and a.resource:
            a.resource.status = "on_scene"
            a.resource.current_node = inc.node
    registrar_evento(db, inc.id, "on_scene", "Las unidades llegaron al lugar del incidente.", username)
    return inc


def resolver_incidente(db: Session, inc: IncidentModel, username: str, nota: str | None = None) -> list[dict]:
    if inc.status not in ESTADOS_ACTIVOS:
        raise ErrorOperacion("El incidente ya está cerrado.", 409)
    ahora = datetime.now()
    if inc.arrived_at is None and inc.dispatched_at is not None:
        inc.arrived_at = ahora
    inc.status = "resolved"
    inc.resolved_at = ahora
    inc.pending_requirements = "{}"
    liberadas = _liberar_unidades(db, inc, mover_al_lugar=True)
    detalle = "Incidente resuelto." + (f" {nota}" if nota else "")
    if liberadas:
        detalle += f" Unidades liberadas: {', '.join(liberadas)}."
    registrar_evento(db, inc.id, "resolved", detalle, username)
    db.flush()
    # Al liberar unidades se atiende la cola de espera (algoritmo de prioridad).
    return procesar_cola(db, username) if liberadas else []


def cancelar_incidente(db: Session, inc: IncidentModel, username: str, motivo: str | None = None) -> list[dict]:
    if inc.status not in ESTADOS_ACTIVOS:
        raise ErrorOperacion("El incidente ya está cerrado.", 409)
    inc.status = "cancelled"
    inc.resolved_at = datetime.now()
    inc.pending_requirements = "{}"
    liberadas = _liberar_unidades(db, inc, mover_al_lugar=inc.arrived_at is not None)
    registrar_evento(db, inc.id, "cancelled", "Incidente cancelado." + (f" Motivo: {motivo}" if motivo else ""), username)
    db.flush()
    return procesar_cola(db, username) if liberadas else []


def incidente_activo_de_recurso(db: Session) -> dict[str, str]:
    """Mapa código de unidad -> incidente al que está asignada ahora."""
    filas = db.query(AssignmentModel.resource_code, AssignmentModel.incident_id).filter(AssignmentModel.active.is_(True)).all()
    return {codigo: incidente for codigo, incidente in filas}
