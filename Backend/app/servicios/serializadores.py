"""Convierte modelos ORM en diccionarios JSON con etiquetas en español."""
import json
from datetime import datetime

from app.catalogos import (
    ESTADOS_INCIDENTE,
    ESTADOS_RECURSO,
    PRIORIDADES,
    TIPOS_INCIDENTE,
    TIPOS_RECURSO,
)
from app.geografia import (
    DEPARTAMENTOS,
    MUNICIPIOS,
    es_zona_capital,
    etiqueta_nodo,
    etiqueta_ubicacion,
    municipio_de_nodo,
    nodos,
)
from app.models import AssignmentModel, IncidentEventModel, IncidentModel, ResourceModel, UserModel
from app.permisos import ROLES, efectivos, personalizado


def iso(fecha: datetime | None) -> str | None:
    return fecha.isoformat(timespec="seconds") if fecha else None


def minutos_entre(inicio: datetime | None, fin: datetime | None) -> float | None:
    if inicio is None or fin is None:
        return None
    return round((fin - inicio).total_seconds() / 60.0, 1)


def leer_json(texto: str | None, defecto):
    try:
        return json.loads(texto) if texto else defecto
    except (TypeError, ValueError):
        return defecto


def ubicacion_incidente(inc: IncidentModel) -> dict:
    return {
        "department_code": inc.department_code,
        "department_name": DEPARTAMENTOS.get(inc.department_code, {}).get("nombre", ""),
        "municipality_code": inc.municipality_code,
        "municipality_name": MUNICIPIOS.get(inc.municipality_code, {}).get("nombre", ""),
        "zone": inc.zone,
        "place_id": inc.place_id,
        "place_name": inc.place_name,
        "node": inc.node,
        "location_label": etiqueta_ubicacion(inc.department_code, inc.municipality_code, inc.zone, inc.place_name),
        "location_source": inc.location_source,
    }


def nodo(n: int) -> dict:
    info = nodos().get(n, {})
    return {"node": n, "label": etiqueta_nodo(n), "name": info.get("nombre", ""),
            "municipality_code": municipio_de_nodo(n), "department_code": info.get("departamento")}


def asignacion(a: AssignmentModel) -> dict:
    r = a.resource
    return {
        "id": a.id,
        "incident_id": a.incident_id,
        "resource_code": a.resource_code,
        "resource_type": r.type if r else None,
        "resource_type_label": TIPOS_RECURSO.get(r.type, r.type) if r else None,
        "resource_name": r.name if r else None,
        "resource_status": r.status if r else None,
        "origin_node": a.origin_node,
        "origin_label": etiqueta_nodo(a.origin_node),
        "distance_km": a.distance_km,
        "eta_min": a.eta_min,
        "route": leer_json(a.route, []),
        "method": a.method,
        "active": a.active,
        "assigned_at": iso(a.assigned_at),
        "released_at": iso(a.released_at),
    }


def evento(e: IncidentEventModel) -> dict:
    return {
        "id": e.id,
        "timestamp": iso(e.timestamp),
        "event": e.event,
        "detail": e.detail,
        "username": e.username,
        "public": e.public,
    }


def incidente(inc: IncidentModel, detalle: bool = False) -> dict:
    activas = [a for a in inc.assignments if a.active]
    datos = {
        "id": inc.id,
        "type": inc.type,
        "type_label": TIPOS_INCIDENTE.get(inc.type, inc.type),
        "priority": inc.priority,
        "priority_label": PRIORIDADES.get(inc.priority, str(inc.priority)),
        **ubicacion_incidente(inc),
        "latitude": inc.latitude,
        "longitude": inc.longitude,
        "address": inc.address,
        "description": inc.description,
        "reporter_name": inc.reporter_name,
        "reporter_phone": inc.reporter_phone,
        "source": inc.source,
        "status": inc.status,
        "status_label": ESTADOS_INCIDENTE.get(inc.status, inc.status),
        "pending_requirements": leer_json(inc.pending_requirements, {}),
        "reported_at": iso(inc.reported_at),
        "dispatched_at": iso(inc.dispatched_at),
        "arrived_at": iso(inc.arrived_at),
        "resolved_at": iso(inc.resolved_at),
        "dispatch_time_min": minutos_entre(inc.reported_at, inc.dispatched_at),
        "response_time_min": minutos_entre(inc.reported_at, inc.arrived_at),
        "active_units": [a.resource_code for a in activas],
    }
    if detalle:
        datos["assignments"] = [asignacion(a) for a in inc.assignments]
        datos["events"] = [evento(e) for e in inc.events]
    return datos


def incidente_publico(inc: IncidentModel) -> dict:
    """Información que puede ver el ciudadano (sin datos internos ni personales)."""
    activas = [a for a in inc.assignments if a.active]
    return {
        "id": inc.id,
        "type_label": TIPOS_INCIDENTE.get(inc.type, inc.type),
        "priority": inc.priority,
        "priority_label": PRIORIDADES.get(inc.priority, str(inc.priority)),
        "location_label": etiqueta_ubicacion(inc.department_code, inc.municipality_code, inc.zone, inc.place_name),
        "status": inc.status,
        "status_label": ESTADOS_INCIDENTE.get(inc.status, inc.status),
        "reported_at": iso(inc.reported_at),
        "dispatched_at": iso(inc.dispatched_at),
        "arrived_at": iso(inc.arrived_at),
        "resolved_at": iso(inc.resolved_at),
        "units": [
            {
                "code": a.resource_code,
                "type_label": TIPOS_RECURSO.get(a.resource.type, a.resource.type) if a.resource else "",
                "eta_min": a.eta_min,
                "distance_km": a.distance_km,
                "assigned_at": iso(a.assigned_at),
            }
            for a in activas
        ],
        "waiting_for": {
            TIPOS_RECURSO.get(t, t): n for t, n in leer_json(inc.pending_requirements, {}).items()
        },
        "events": [
            {"timestamp": iso(e.timestamp), "detail": e.detail}
            for e in inc.events if e.public
        ],
    }


def recurso(r: ResourceModel, incidente_activo: str | None = None) -> dict:
    return {
        "code": r.code,
        "type": r.type,
        "type_label": TIPOS_RECURSO.get(r.type, r.type),
        "name": r.name,
        "base_node": r.base_node,
        "base_label": etiqueta_nodo(r.base_node),
        "base_municipality_code": municipio_de_nodo(r.base_node),
        "base_department_code": nodos().get(r.base_node, {}).get("departamento"),
        "base_zone": r.base_node if es_zona_capital(r.base_node) else None,
        "current_node": r.current_node,
        "current_label": etiqueta_nodo(r.current_node),
        "department_code": nodos().get(r.current_node, {}).get("departamento"),
        "status": r.status,
        "status_label": ESTADOS_RECURSO.get(r.status, r.status),
        "incident_id": incidente_activo,
        "updated_at": iso(r.updated_at),
    }


def usuario(u: UserModel) -> dict:
    return {
        "id": u.id,
        "username": u.username,
        "full_name": u.full_name,
        "role": u.role,
        "role_label": ROLES[u.role]["nombre"] if u.role in ROLES else u.role,
        # Permisos efectivos por módulo: 0 sin acceso, 1 ver, 2 editar.
        "permissions": efectivos(u),
        "custom_permissions": personalizado(u),
        "is_active": u.is_active,
        "created_at": iso(u.created_at),
    }
