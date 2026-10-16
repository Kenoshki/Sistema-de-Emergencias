"""
Red vial de Guatemala modelada como GRAFO PONDERADO NO DIRIGIDO.

- Nodos  : las 22 zonas de la Ciudad de Guatemala + los otros 339 municipios
           (ver app/geografia.py).
- Aristas: 1) conexiones entre zonas vecinas de la capital (definidas a mano);
           2) cada municipio se une con sus K municipios más cercanos (K vecinos);
           3) un ÁRBOL DE EXPANSIÓN MÍNIMA (Prim) garantiza que todo el país
              quede conectado aunque un municipio esté aislado de sus vecinos;
           4) la capital se conecta al resto mediante las zonas más cercanas
              a cada municipio vecino.
- Peso   : distancia estimada por carretera (línea recta × factor de tortuosidad).

Rutas más cortas:
1. `dijkstra()`  -> implementación propia con cola de prioridad (heapq).
2. `ruta_networkx()` -> la misma consulta con NetworkX, para verificar.

Complejidad de Dijkstra con montículo binario: O((V + E) log V).
"""
from __future__ import annotations

import heapq
from dataclasses import dataclass, field
from functools import lru_cache

import networkx as nx

from app.catalogos import (
    CONEXIONES_CAPITAL,
    DISTANCIA_INTRAMUNICIPAL_KM,
    DISTANCIA_INTRAZONA_KM,
    FACTOR_TORTUOSIDAD,
    FACTOR_TORTUOSIDAD_RURAL,
    VECINOS_POR_MUNICIPIO,
    ZONAS_CAPITAL,
)
from app.geografia import MUNICIPIO_CAPITAL, MUNICIPIOS, haversine_km, localizar, nodos

INFINITO = float("inf")


def _normalizar(a: int, b: int) -> tuple[int, int]:
    return (a, b) if a <= b else (b, a)


def _distancia_recta(a: int, b: int) -> float:
    na, nb = nodos()[a], nodos()[b]
    return haversine_km(na["lat"], na["lon"], nb["lat"], nb["lon"])


def peso_arista(a: int, b: int) -> float:
    factor = FACTOR_TORTUOSIDAD if (a in ZONAS_CAPITAL and b in ZONAS_CAPITAL) else FACTOR_TORTUOSIDAD_RURAL
    return round(_distancia_recta(a, b) * factor, 2)


def arbol_expansion_minima_prim(puntos: dict[int, tuple[float, float]]) -> list[tuple[int, int]]:
    """
    Algoritmo de Prim sobre el grafo completo de `puntos` (peso = distancia).
    Devuelve las V-1 aristas del árbol. Complejidad O(V² ) con arreglo de mínimos,
    adecuada para grafos densos como este.
    """
    claves = list(puntos)
    if not claves:
        return []
    en_arbol = {claves[0]}
    mejor = {k: (haversine_km(*puntos[claves[0]], *puntos[k]), claves[0]) for k in claves[1:]}
    aristas = []
    while mejor:
        nodo = min(mejor, key=lambda k: mejor[k][0])
        _, padre = mejor.pop(nodo)
        en_arbol.add(nodo)
        aristas.append((padre, nodo))
        for k in mejor:
            d = haversine_km(*puntos[nodo], *puntos[k])
            if d < mejor[k][0]:
                mejor[k] = (d, nodo)
    return aristas


@lru_cache(maxsize=1)
def conexiones_base() -> tuple[tuple[int, int], ...]:
    """Todas las conexiones de la red (sin cierres). Se calcula una sola vez."""
    aristas: set[tuple[int, int]] = {_normalizar(a, b) for a, b in CONEXIONES_CAPITAL}

    # Puntos de la red nacional: cada municipio + la capital como un solo punto.
    CAPITAL = 0
    puntos: dict[int, tuple[float, float]] = {
        int(c): (m["lat"], m["lon"]) for c, m in MUNICIPIOS.items() if c != MUNICIPIO_CAPITAL
    }
    cap = MUNICIPIOS[MUNICIPIO_CAPITAL]
    puntos[CAPITAL] = (cap["lat"], cap["lon"])

    pares: set[tuple[int, int]] = set()
    # K vecinos más cercanos
    for a, pa in puntos.items():
        cercanos = sorted((haversine_km(*pa, *pb), b) for b, pb in puntos.items() if b != a)
        for _, b in cercanos[:VECINOS_POR_MUNICIPIO]:
            pares.add(_normalizar(a, b))
    # Árbol de expansión mínima: garantiza conectividad
    for a, b in arbol_expansion_minima_prim(puntos):
        pares.add(_normalizar(a, b))

    for a, b in pares:
        if CAPITAL in (a, b):
            municipio = b if a == CAPITAL else a
            lat, lon = puntos[municipio]
            # se une con las 2 zonas de la capital más cercanas a ese municipio
            zonas = sorted(ZONAS_CAPITAL, key=lambda z: haversine_km(lat, lon, ZONAS_CAPITAL[z]["lat"], ZONAS_CAPITAL[z]["lon"]))
            for z in zonas[:2]:
                aristas.add(_normalizar(z, municipio))
        else:
            aristas.add((a, b))
    return tuple(sorted(aristas))


def zona_mas_cercana(lat: float, lon: float) -> int:
    """(Compatibilidad) nodo más cercano a una coordenada."""
    return localizar(lat, lon).get("nodo", 1)


@dataclass
class ResultadoDijkstra:
    origen: int
    distancias: dict[int, float]
    previos: dict[int, int | None]
    orden_visita: list[int] = field(default_factory=list)

    def camino_hasta(self, destino: int) -> list[int]:
        """Reconstruye el camino origen -> destino siguiendo los predecesores."""
        if self.distancias.get(destino, INFINITO) == INFINITO:
            return []
        camino: list[int] = []
        actual: int | None = destino
        while actual is not None:
            camino.append(actual)
            actual = self.previos[actual]
        camino.reverse()
        return camino


def distancia_interna(nodo: int) -> float:
    """Recorrido típico cuando la unidad ya está en el mismo nodo."""
    return DISTANCIA_INTRAZONA_KM if nodo in ZONAS_CAPITAL else DISTANCIA_INTRAMUNICIPAL_KM


class RedVial:
    """Grafo nacional. Permite cerrar vías (p. ej. por un deslave)."""

    def __init__(self, vias_cerradas: set[tuple[int, int]] | None = None) -> None:
        self.vias_cerradas: set[tuple[int, int]] = {_normalizar(a, b) for a, b in (vias_cerradas or set())}
        self.adyacencia: dict[int, dict[int, float]] = {n: {} for n in nodos()}
        self.grafo_nx = nx.Graph()
        self.grafo_nx.add_nodes_from(nodos())
        for a, b in conexiones_base():
            if (a, b) in self.vias_cerradas:
                continue
            peso = peso_arista(a, b)
            self.adyacencia[a][b] = peso
            self.adyacencia[b][a] = peso
            self.grafo_nx.add_edge(a, b, weight=peso)

    @staticmethod
    def existe_conexion(a: int, b: int) -> bool:
        return _normalizar(a, b) in set(conexiones_base())

    def aristas(self) -> list[dict]:
        """Todas las conexiones (incluidas las cerradas) para dibujar el mapa."""
        return [
            {"origen": a, "destino": b, "distancia_km": peso_arista(a, b), "cerrada": (a, b) in self.vias_cerradas}
            for a, b in conexiones_base()
        ]

    # ------------------------------------------------------ Dijkstra propio
    def dijkstra(self, origen: int) -> ResultadoDijkstra:
        """
        Algoritmo de Dijkstra con cola de prioridad (montículo binario).

        1. Todas las distancias inician en infinito, excepto el origen (0).
        2. Se extrae de la cola el nodo con menor distancia conocida.
        3. Se "relajan" sus aristas: si pasar por él mejora la distancia de un
           vecino, se actualiza y se inserta en la cola.
        4. Se repite hasta vaciar la cola.
        """
        if origen not in self.adyacencia:
            raise ValueError(f"El nodo {origen} no existe en la red vial")

        distancias: dict[int, float] = {n: INFINITO for n in self.adyacencia}
        previos: dict[int, int | None] = {n: None for n in self.adyacencia}
        visitados: set[int] = set()
        orden: list[int] = []

        distancias[origen] = 0.0
        cola: list[tuple[float, int]] = [(0.0, origen)]

        while cola:
            dist_actual, nodo = heapq.heappop(cola)
            if nodo in visitados:
                continue  # entrada obsoleta en la cola
            visitados.add(nodo)
            orden.append(nodo)

            for vecino, peso in self.adyacencia[nodo].items():
                nueva = dist_actual + peso
                if nueva < distancias[vecino]:
                    distancias[vecino] = nueva
                    previos[vecino] = nodo
                    heapq.heappush(cola, (nueva, vecino))

        distancias = {n: (round(d, 2) if d != INFINITO else INFINITO) for n, d in distancias.items()}
        return ResultadoDijkstra(origen, distancias, previos, orden)

    def ruta(self, origen: int, destino: int) -> tuple[float, list[int]]:
        """Distancia (km) y camino de nodos usando el Dijkstra propio."""
        if origen == destino:
            return distancia_interna(origen), [origen]
        res = self.dijkstra(origen)
        return res.distancias[destino], res.camino_hasta(destino)

    # ------------------------------------------------------ NetworkX (ref.)
    def ruta_networkx(self, origen: int, destino: int) -> tuple[float, list[int]]:
        """Misma consulta con NetworkX (para verificar el Dijkstra propio)."""
        if origen == destino:
            return distancia_interna(origen), [origen]
        try:
            dist, camino = nx.single_source_dijkstra(self.grafo_nx, origen, destino, weight="weight")
        except nx.NetworkXNoPath:
            return INFINITO, []
        return round(float(dist), 2), list(camino)

    def es_conexo(self) -> bool:
        return nx.is_connected(self.grafo_nx)
