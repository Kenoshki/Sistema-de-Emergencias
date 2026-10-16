"""
Cola de prioridad de incidentes pendientes (montículo binario con heapq).

Cuando no hay unidades suficientes, los incidentes quedan en espera. Cada vez
que una unidad se libera, el sistema atiende primero al incidente más urgente.

Orden de atención:
1. Mayor PRIORIDAD EFECTIVA.
2. A igual prioridad, el que lleva más tiempo esperando (FIFO).

Prioridad efectiva = prioridad + bono por espera (envejecimiento / "aging").
El bono evita la INANICIÓN: un incidente de prioridad baja que lleva mucho
tiempo esperando va subiendo hasta que eventualmente se atiende.

Operaciones: insertar O(log n), extraer O(log n), consultar tope O(1).
"""
from __future__ import annotations

import heapq
import itertools
from dataclasses import dataclass, field
from datetime import datetime

MINUTOS_POR_PUNTO = 30.0   # cada 30 min de espera suma 1 punto
BONO_MAXIMO = 1.0          # el bono por espera nunca supera 1 punto


def prioridad_efectiva(prioridad: int, reportado: datetime, ahora: datetime | None = None) -> float:
    ahora = ahora or datetime.now()
    minutos = max(0.0, (ahora - reportado).total_seconds() / 60.0)
    return round(prioridad + min(BONO_MAXIMO, minutos / MINUTOS_POR_PUNTO), 3)


@dataclass(order=True)
class _Entrada:
    clave: tuple
    incidente_id: str = field(compare=False)
    prioridad: int = field(compare=False)
    efectiva: float = field(compare=False)
    reportado: datetime = field(compare=False)


class ColaIncidentes:
    def __init__(self, ahora: datetime | None = None) -> None:
        self._heap: list[_Entrada] = []
        self._contador = itertools.count()  # desempate estable
        self._ahora = ahora or datetime.now()

    def insertar(self, incidente_id: str, prioridad: int, reportado: datetime) -> None:
        efectiva = prioridad_efectiva(prioridad, reportado, self._ahora)
        # heapq es un montículo de MÍNIMOS, por eso se niega la prioridad.
        clave = (-efectiva, reportado, next(self._contador))
        heapq.heappush(self._heap, _Entrada(clave, incidente_id, prioridad, efectiva, reportado))

    def extraer(self) -> _Entrada:
        if not self._heap:
            raise IndexError("La cola de incidentes está vacía")
        return heapq.heappop(self._heap)

    def tope(self) -> _Entrada | None:
        return self._heap[0] if self._heap else None

    def __len__(self) -> int:
        return len(self._heap)

    def __bool__(self) -> bool:
        return bool(self._heap)

    def en_orden(self) -> list[dict]:
        """Vista ordenada sin modificar la cola (para mostrarla en pantalla)."""
        copia = list(self._heap)
        resultado = []
        posicion = 1
        while copia:
            e = heapq.heappop(copia)
            resultado.append({
                "posicion": posicion,
                "incidente_id": e.incidente_id,
                "prioridad": e.prioridad,
                "prioridad_efectiva": e.efectiva,
                "reportado": e.reportado,
            })
            posicion += 1
        return resultado
