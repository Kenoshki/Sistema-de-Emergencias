"""
Simulación de historial de incidentes (función pura, sin base de datos).

El historial se genera con los MISMOS algoritmos del sistema (Dijkstra para
elegir la unidad más cercana), así los tiempos son coherentes con la red vial.
"""
from __future__ import annotations

import random
from datetime import datetime, timedelta

from app.algoritmos.despacho import RecursoDisponible, planificar_despacho
from app.algoritmos.grafo import RedVial
from app.catalogos import ZONAS_CAPITAL, requerimientos
from app.geografia import DEPARTAMENTOS, MUNICIPIOS, nodos

# Flota de la capital: (código, tipo, nodo base = zona)
RECURSOS_CAPITAL: list[tuple[str, str, int]] = [
    ("AMB-01", "ambulance", 1), ("AMB-02", "ambulance", 9), ("AMB-03", "ambulance", 12),
    ("AMB-04", "ambulance", 18), ("AMB-05", "ambulance", 7), ("AMB-06", "ambulance", 16),
    ("BOM-01", "firefighters", 1), ("BOM-02", "firefighters", 4), ("BOM-03", "firefighters", 11),
    ("BOM-04", "firefighters", 18), ("BOM-05", "firefighters", 14),
    ("POL-01", "police", 1), ("POL-02", "police", 10), ("POL-03", "police", 7),
    ("POL-04", "police", 6), ("POL-05", "police", 21),
    ("RES-01", "rescue", 4), ("RES-02", "rescue", 13), ("RES-03", "rescue", 17), ("RES-04", "rescue", 19),
]

# Abreviaturas de departamento para los códigos de unidad (AMB-QZ, BOM-PE...).
ABREVIATURA = {"01": "GU", "02": "PR", "03": "SA", "04": "CM", "05": "ES", "06": "SR", "07": "SO", "08": "TO",
               "09": "QZ", "10": "SU", "11": "RE", "12": "SM", "13": "HU", "14": "QC", "15": "BV", "16": "AV",
               "17": "PE", "18": "IZ", "19": "ZA", "20": "CQ", "21": "JA", "22": "JU"}
# Departamentos con base regional de rescate.
RESCATE_REGIONAL = {"05", "09", "10", "13", "16", "17", "18", "19"}
# Municipios del área metropolitana con unidades propias.
METROPOLITANOS = {"Mixco": "MIX", "Villa Nueva": "VNU", "San Miguel Petapa": "SMP", "Amatitlán": "AMA"}


def _cabecera(depto: str) -> int:
    return int(next(m["codigo"] for m in MUNICIPIOS.values() if m["departamento"] == depto and m["cabecera_departamental"]))


def flota_inicial() -> list[tuple[str, str, int]]:
    """(código, tipo, nodo base) de toda la flota nacional."""
    flota = list(RECURSOS_CAPITAL)
    for nombre, abrev in METROPOLITANOS.items():
        cod = next(m["codigo"] for m in MUNICIPIOS.values() if m["departamento"] == "01" and m["nombre"] == nombre)
        flota += [(f"AMB-{abrev}", "ambulance", int(cod)), (f"POL-{abrev}", "police", int(cod))]
    for depto in DEPARTAMENTOS:
        if depto == "01":
            continue
        nodo = _cabecera(depto)
        ab = ABREVIATURA[depto]
        flota += [(f"AMB-{ab}", "ambulance", nodo), (f"BOM-{ab}", "firefighters", nodo), (f"POL-{ab}", "police", nodo)]
        if depto in RESCATE_REGIONAL:
            flota.append((f"RES-{ab}", "rescue", nodo))
    return flota


RECURSOS_INICIALES = flota_inicial()

# Pesos para que la simulación tenga patrones (lugares y horas con más incidentes).
PESO_ZONA = {18: 15, 1: 11, 12: 8, 7: 6, 21: 8, 6: 5, 3: 4, 11: 4, 5: 4, 19: 4, 25: 4, 24: 3,
             2: 3, 4: 3, 8: 3, 17: 3, 9: 2, 10: 2, 13: 2, 14: 1, 15: 1, 16: 2}


def _pesos_nodos() -> dict[int, float]:
    """La capital concentra cerca de la mitad de los reportes; el resto se reparte en el país."""
    pesos: dict[int, float] = {z: p * 1.0 for z, p in PESO_ZONA.items()}
    for n, info in nodos().items():
        if info["tipo"] != "municipio":
            continue
        if info["departamento"] == "01":
            pesos[n] = 5.0
        elif info["cabecera_departamental"]:
            pesos[n] = 3.5
        else:
            pesos[n] = 0.35
    return pesos


PESO_NODO = _pesos_nodos()
PESO_TIPO = {"accident": 30, "medical": 25, "robbery": 18, "fire": 13, "landslide": 7, "collapse": 7}
PESO_PRIORIDAD = {1: 15, 2: 35, 3: 32, 4: 18}
PESO_HORA = [1, 1, 1, 1, 1, 2, 4, 7, 7, 5, 4, 4, 5, 5, 4, 4, 5, 7, 8, 7, 5, 4, 3, 2]

DESCRIPCIONES = {
    "fire": ["Humo denso saliendo de vivienda", "Incendio en local comercial", "Quema de maleza fuera de control"],
    "accident": ["Choque entre dos vehículos", "Motorista herido tras colisión", "Atropello de peatón"],
    "collapse": ["Muro colapsado sobre la banqueta", "Daños en vivienda tras sismo", "Techo caído en bodega"],
    "landslide": ["Deslave bloquea calle principal", "Inundación en paso a desnivel", "Tierra sobre viviendas por lluvia"],
    "medical": ["Persona inconsciente en la vía pública", "Adulto mayor con dolor de pecho", "Persona con dificultad para respirar"],
    "robbery": ["Asalto a bus urbano", "Robo en tienda de barrio", "Asalto a transeúnte"],
}


def _elegir(rng: random.Random, pesos: dict):
    return rng.choices(list(pesos), weights=list(pesos.values()), k=1)[0]


def generar_historial(dias: int = 60, ahora: datetime | None = None, semilla: int = 2026) -> list[dict]:
    """
    Genera incidentes históricos ya resueltos (función pura, sin BD).
    Los tiempos mejoran ligeramente en los últimos 30 días para que el
    panel muestre una tendencia.
    """
    rng = random.Random(semilla)
    ahora = ahora or datetime.now()
    red = RedVial()
    flota = [RecursoDisponible(c, t, z) for c, t, z in RECURSOS_INICIALES]
    historial: list[dict] = []
    contador_dia: dict[str, int] = {}

    for d in range(dias, 0, -1):
        dia = (ahora - timedelta(days=d)).replace(hour=0, minute=0, second=0, microsecond=0)
        reciente = d <= 30
        for _ in range(rng.randint(5, 10)):
            hora = rng.choices(range(24), weights=PESO_HORA, k=1)[0]
            reportado = dia + timedelta(hours=hora, minutes=rng.randint(0, 59), seconds=rng.randint(0, 59))
            tipo = _elegir(rng, PESO_TIPO)
            prioridad = _elegir(rng, PESO_PRIORIDAD)
            nodo = _elegir(rng, PESO_NODO)
            info = nodos()[nodo]

            plan = planificar_despacho(nodo, prioridad, requerimientos(tipo, prioridad), flota, red)
            if not plan.asignaciones:
                continue

            clave = reportado.strftime("%Y%m%d")
            contador_dia[clave] = contador_dia.get(clave, 0) + 1
            demora_despacho = rng.uniform(0.4, 2.0) if reciente else rng.uniform(0.8, 3.2)
            despachado = reportado + timedelta(minutes=demora_despacho)
            eta_min = min(c.eta_min for c in plan.asignaciones)
            factor_trafico = rng.uniform(0.85, 1.35) if reciente else rng.uniform(0.95, 1.6)
            if rng.random() < (0.12 if reciente else 0.2):  # tráfico pesado / lluvia
                factor_trafico *= rng.uniform(1.6, 2.4)
            llegada = despachado + timedelta(minutes=eta_min * factor_trafico)
            cancelado = rng.random() < 0.04
            cierre = llegada + timedelta(minutes=rng.randint(15, 120))

            historial.append({
                "id": f"INC-{clave}-{contador_dia[clave]:04d}",
                "type": tipo,
                "priority": prioridad,
                "department_code": info["departamento"],
                "municipality_code": info["municipio"],
                "zone": nodo if nodo in ZONAS_CAPITAL else None,
                "node": nodo,
                "latitude": round(info["lat"] + rng.uniform(-0.004, 0.004), 6),
                "longitude": round(info["lon"] + rng.uniform(-0.004, 0.004), 6),
                "description": rng.choice(DESCRIPCIONES[tipo]),
                "source": rng.choice(["public", "public", "operator"]),
                "status": "cancelled" if cancelado else "resolved",
                "reported_at": reportado,
                "dispatched_at": despachado,
                "arrived_at": None if cancelado else llegada,
                "resolved_at": despachado + timedelta(minutes=5) if cancelado else cierre,
                "assignments": [c.a_dict() for c in plan.asignaciones],
            })
    return historial
