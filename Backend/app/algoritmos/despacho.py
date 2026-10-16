"""
Algoritmo de ASIGNACIÓN AUTOMÁTICA de unidades a un incidente.

Estrategia voraz (greedy) sobre distancias de Dijkstra:

1. Se calculan las reglas de cuántas unidades de cada tipo necesita el
   incidente (ver `catalogos.requerimientos`).
2. Se ejecuta Dijkstra UNA sola vez desde el nodo del incidente. Como el grafo
   es no dirigido, la distancia incidente -> nodo X es igual a X -> incidente,
   así obtenemos la distancia de TODAS las unidades con un solo recorrido.
3. Para cada tipo requerido se ordenan las unidades disponibles por
   (distancia, código) y se eligen las N más cercanas.
4. Si faltan unidades de algún tipo, quedan registradas como "faltantes" y
   el incidente entra a la cola de prioridad hasta que se libere una unidad.

Complejidad: O((V + E) log V) por Dijkstra + O(R log R) por ordenar R unidades.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from app.algoritmos.grafo import INFINITO, RedVial, distancia_interna
from app.catalogos import TRAMO_URBANO_KM, VELOCIDAD_CARRETERA_KMH, VELOCIDAD_KMH

MINUTOS_ALISTAMIENTO = 1.5   # tiempo que tarda una unidad en salir
FACTOR_SIRENA_CRITICO = 1.15  # en prioridad 4 la unidad circula más rápido


@dataclass
class RecursoDisponible:
    codigo: str
    tipo: str
    nodo: int


@dataclass
class Candidato:
    codigo: str
    tipo: str
    nodo_origen: int
    distancia_km: float
    eta_min: float
    ruta: list[int]

    def a_dict(self) -> dict:
        return {
            "codigo": self.codigo,
            "tipo": self.tipo,
            "nodo_origen": self.nodo_origen,
            "distancia_km": self.distancia_km,
            "eta_min": self.eta_min,
            "ruta": self.ruta,
        }


@dataclass
class PlanDespacho:
    asignaciones: list[Candidato] = field(default_factory=list)
    faltantes: dict[str, int] = field(default_factory=dict)
    ranking: dict[str, list[Candidato]] = field(default_factory=dict)

    @property
    def completo(self) -> bool:
        return not self.faltantes


def estimar_eta_min(distancia_km: float, tipo: str, prioridad: int) -> float:
    """Los primeros km se recorren a velocidad urbana; el resto, en carretera."""
    urbana = VELOCIDAD_KMH.get(tipo, 40.0)
    carretera = VELOCIDAD_CARRETERA_KMH
    if prioridad >= 4:
        urbana *= FACTOR_SIRENA_CRITICO
        carretera *= FACTOR_SIRENA_CRITICO
    tramo_urbano = min(distancia_km, TRAMO_URBANO_KM)
    tramo_carretera = max(0.0, distancia_km - TRAMO_URBANO_KM)
    minutos = tramo_urbano / urbana * 60.0 + tramo_carretera / carretera * 60.0
    return round(MINUTOS_ALISTAMIENTO + minutos, 1)


def planificar_despacho(
    nodo_incidente: int,
    prioridad: int,
    necesidades: dict[str, int],
    recursos: list[RecursoDisponible],
    red: RedVial,
) -> PlanDespacho:
    """Calcula qué unidades enviar SIN modificar nada (función pura)."""
    plan = PlanDespacho()
    if not necesidades:
        return plan

    dijkstra = red.dijkstra(nodo_incidente)

    for tipo in sorted(necesidades):
        cantidad = necesidades[tipo]
        if cantidad <= 0:
            continue

        candidatos: list[Candidato] = []
        for r in recursos:
            if r.tipo != tipo:
                continue
            if r.nodo == nodo_incidente:
                distancia, ruta = distancia_interna(nodo_incidente), [nodo_incidente]
            else:
                distancia = dijkstra.distancias.get(r.nodo, INFINITO)
                if distancia == INFINITO:
                    continue  # nodo aislado por vías cerradas
                # El camino va del incidente a la unidad; la unidad lo recorre al revés.
                ruta = list(reversed(dijkstra.camino_hasta(r.nodo)))
            candidatos.append(Candidato(
                codigo=r.codigo,
                tipo=tipo,
                nodo_origen=r.nodo,
                distancia_km=round(distancia, 2),
                eta_min=estimar_eta_min(distancia, tipo, prioridad),
                ruta=ruta,
            ))

        candidatos.sort(key=lambda c: (c.distancia_km, c.codigo))
        plan.ranking[tipo] = candidatos

        elegidos = candidatos[:cantidad]
        plan.asignaciones.extend(elegidos)
        if len(elegidos) < cantidad:
            plan.faltantes[tipo] = cantidad - len(elegidos)

    return plan


def restar_necesidades(necesidades: dict[str, int], ya_asignados: dict[str, int]) -> dict[str, int]:
    """Necesidades que aún faltan cubrir, dadas las unidades ya asignadas."""
    resultado = {}
    for tipo, cantidad in necesidades.items():
        restante = cantidad - ya_asignados.get(tipo, 0)
        if restante > 0:
            resultado[tipo] = restante
    return resultado
