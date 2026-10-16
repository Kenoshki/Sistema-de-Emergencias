"""Módulo público: el ciudadano reporta y da seguimiento a su emergencia."""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.catalogos import ESTADOS_INCIDENTE, PRIORIDADES, TIPOS_INCIDENTE, TIPOS_RECURSO, ZONAS_CAPITAL
from app.database import get_db
from app.geografia import DEPARTAMENTOS, MUNICIPIO_CAPITAL, MUNICIPIOS, localizar, normalizar, zonas_de
from app.models import IncidentModel, PlaceModel
from app.schemas import IncidentCreate
from app.servicios import serializadores as ser
from app.servicios.operaciones import crear_incidente

router = APIRouter(prefix="/api/public", tags=["Público"])


def _nombre_zona(municipio: str, z: int) -> str:
    if municipio == MUNICIPIO_CAPITAL and z in ZONAS_CAPITAL:
        return f"Zona {z} – {ZONAS_CAPITAL[z]['nombre']}"
    return f"Zona {z}"


@router.get("/catalogs")
def catalogos(db: Session = Depends(get_db)):
    """Listas para llenar los formularios (tipos, prioridades, departamentos, municipios y zonas)."""
    con_lugares = {c for (c,) in db.query(PlaceModel.municipality_code).distinct().all()}
    return {
        "incident_types": [{"value": k, "label": v} for k, v in TIPOS_INCIDENTE.items()],
        "resource_types": [{"value": k, "label": v} for k, v in TIPOS_RECURSO.items()],
        "priorities": [{"value": k, "label": v} for k, v in PRIORIDADES.items()],
        "statuses": [{"value": k, "label": v} for k, v in ESTADOS_INCIDENTE.items()],
        "departments": [
            {"value": d["codigo"], "label": d["nombre"], "lat": d["lat"], "lon": d["lon"]}
            for d in sorted(DEPARTAMENTOS.values(), key=lambda d: normalizar(d["nombre"]))
        ],
        "municipalities": [
            {
                "value": m["codigo"], "label": m["nombre"], "department": m["departamento"],
                "lat": m["lat"], "lon": m["lon"],
                "zones": [{"value": z, "label": _nombre_zona(m["codigo"], z)} for z in (zonas_de(m["codigo"]) or [])] or None,
                "has_places": m["codigo"] in con_lugares,
            }
            for m in sorted(MUNICIPIOS.values(), key=lambda m: normalizar(m["nombre"]))
        ],
    }


@router.get("/locate")
def ubicar(lat: float = Query(..., ge=-90, le=90), lon: float = Query(..., ge=-180, le=180)):
    """Propone departamento, municipio y zona a partir del GPS (el usuario debe confirmarlos)."""
    punto = localizar(lat, lon)
    if not punto["dentro"]:
        return {"inside": False}
    return {
        "inside": True,
        "department_code": punto["departamento"],
        "municipality_code": punto["municipio"],
        "zone": punto["zona"],
        "label": punto["etiqueta"],
        "distance_km": punto["distancia_km"],
    }


@router.get("/places")
def buscar_lugares(
    municipality: str = Query(..., min_length=4, max_length=4),
    q: str = Query("", max_length=80),
    limit: int = Query(20, ge=1, le=50),
    db: Session = Depends(get_db),
):
    """Aldeas, caseríos y colonias de un municipio (catálogo importado desde CSV)."""
    consulta = db.query(PlaceModel).filter(PlaceModel.municipality_code == municipality)
    texto = q.strip()
    if texto:
        consulta = consulta.filter(func.lower(PlaceModel.name).like(f"%{texto.lower()}%"))
    lugares = consulta.order_by(PlaceModel.name).limit(limit).all()
    return [{"id": p.id, "name": p.name, "category": p.category} for p in lugares]


@router.post("/incidents", status_code=201)
def registrar_incidente_publico(datos: IncidentCreate, db: Session = Depends(get_db)):
    inc = crear_incidente(db, datos, source="public")
    db.commit()
    db.refresh(inc)
    return {
        "message": f"Reporte {inc.id} recibido. Guarde este código para dar seguimiento.",
        "data": ser.incidente_publico(inc),
    }


@router.get("/incidents/{incident_id}")
def seguimiento(incident_id: str, db: Session = Depends(get_db)):
    inc = db.get(IncidentModel, incident_id.strip().upper())
    if inc is None:
        raise HTTPException(status_code=404, detail="No se encontró un reporte con ese código.")
    return ser.incidente_publico(inc)
