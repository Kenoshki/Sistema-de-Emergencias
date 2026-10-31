"""
Evita reportes duplicados cuando el teléfono reintenta un envío (mala señal): el cliente manda un
`client_request_id` único y, si ya se registró, se devuelve el mismo incidente en lugar de crear otro.

Memoria por proceso con caducidad (suficiente con una sola réplica, como en Railway).
"""
import threading
import time

_TTL_SEG = 3600
_vistos: dict[str, tuple[float, str]] = {}
_lock = threading.Lock()


def _purgar(ahora: float) -> None:
    for k in [k for k, (t, _) in _vistos.items() if ahora - t > _TTL_SEG]:
        del _vistos[k]


def buscar(clave: str | None) -> str | None:
    """Devuelve el id de incidente ya creado para esa clave, o None."""
    if not clave:
        return None
    with _lock:
        _purgar(time.monotonic())
        hallado = _vistos.get(clave)
        return hallado[1] if hallado else None


def recordar(clave: str | None, incidente_id: str) -> None:
    if clave:
        with _lock:
            _vistos[clave] = (time.monotonic(), incidente_id)


def reiniciar() -> None:
    with _lock:
        _vistos.clear()
