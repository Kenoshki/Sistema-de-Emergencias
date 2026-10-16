"""Red vial nacional: grafo de zonas y municipios, cálculo de rutas y cierre de vías."""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.algoritmos.grafo import INFINITO, RedVial
from app.geografia import etiqueta_nodo, nodos
from app.database import get_db
from app.models import RoadClosureModel, UserModel
from app.schemas import RoadClosureCreate
from app.permisos import EDITAR
from app.security import get_current_user, requiere
from app.servicios.operaciones import construir_red, procesar_cola
from app.servicios.serializadores import iso

router = APIRouter(prefix="/api/admin/network", tags=["Red vial"])


def _cierre(c: RoadClosureModel) -> dict:
    return {"id": c.id, "node_a": c.node_a, "node_b": c.node_b,
            "label_a": etiqueta_nodo(c.node_a), "label_b": etiqueta_nodo(c.node_b), "reason": c.reason,
            "created_by": c.created_by, "created_at": iso(c.created_at)}


@router.get("")
def grafo(db: Session = Depends(get_db), _: UserModel = Depends(get_current_user)):
    red = construir_red(db)
    return {
        "nodes": [
            {"node": n, "kind": d["tipo"], "name": d["nombre"], "detail": d["detalle"], "label": d["etiqueta"],
             "lat": d["lat"], "lon": d["lon"], "municipality_code": d["municipio"], "department_code": d["departamento"],
             "department_head": d["cabecera_departamental"]}
            for n, d in nodos().items()
        ],
        "edges": red.aristas(),
        "closures": [_cierre(c) for c in db.query(RoadClosureModel).order_by(RoadClosureModel.created_at.desc()).all()],
        "connected": red.es_conexo(),
    }


@router.get("/route")
def ruta(origen: int = Query(..., description="Nodo de origen"), destino: int = Query(..., description="Nodo destino"),
         db: Session = Depends(get_db), _: UserModel = Depends(requiere("red"))):
    if origen not in nodos() or destino not in nodos():
        raise HTTPException(status_code=400, detail="Origen o destino inválido.")
    red = construir_red(db)
    resultado = red.dijkstra(origen)
    distancia, camino = red.ruta(origen, destino)
    distancia_nx, camino_nx = red.ruta_networkx(origen, destino)
    tramos = [
        {"desde": a, "hasta": b, "desde_label": etiqueta_nodo(a), "hasta_label": etiqueta_nodo(b),
         "distancia_km": red.adyacencia[a][b]}
        for a, b in zip(camino, camino[1:])
    ]
    return {
        "origen": origen,
        "destino": destino,
        "alcanzable": distancia != INFINITO,
        "distancia_km": None if distancia == INFINITO else distancia,
        "camino": camino,
        "tramos": tramos,
        "origen_label": etiqueta_nodo(origen),
        "destino_label": etiqueta_nodo(destino),
        # Pasos del algoritmo: en qué orden Dijkstra "fijó" cada nodo
        "orden_visita": resultado.orden_visita,
        "distancias_desde_origen": {z: (None if d == INFINITO else d) for z, d in resultado.distancias.items()},
        "verificacion_networkx": {
            "distancia_km": None if distancia_nx == INFINITO else distancia_nx,
            "camino": camino_nx,
            "coincide": abs((distancia if distancia != INFINITO else -1) - (distancia_nx if distancia_nx != INFINITO else -1)) < 0.05,
        },
    }


@router.post("/closures", status_code=201)
def cerrar_via(datos: RoadClosureCreate, db: Session = Depends(get_db), user: UserModel = Depends(requiere("red", nivel=EDITAR))):
    a, b = sorted((datos.node_a, datos.node_b))
    if not RedVial.existe_conexion(a, b):
        raise HTTPException(status_code=400, detail=f"No existe una conexión directa entre {etiqueta_nodo(a)} y {etiqueta_nodo(b)}.")
    if db.query(RoadClosureModel).filter(RoadClosureModel.node_a == a, RoadClosureModel.node_b == b).first():
        raise HTTPException(status_code=409, detail="Esa vía ya está cerrada.")
    c = RoadClosureModel(node_a=a, node_b=b, reason=datos.reason, created_by=user.username)
    db.add(c)
    db.commit()
    db.refresh(c)
    return _cierre(c)


@router.delete("/closures/{closure_id}", status_code=204)
def reabrir_via(closure_id: int, db: Session = Depends(get_db), user: UserModel = Depends(requiere("red", nivel=EDITAR))):
    c = db.get(RoadClosureModel, closure_id)
    if c is None:
        raise HTTPException(status_code=404, detail="Cierre no encontrado.")
    db.delete(c)
    db.flush()
    procesar_cola(db, user.username)  # una vía reabierta puede conectar unidades con incidentes en espera
    db.commit()
