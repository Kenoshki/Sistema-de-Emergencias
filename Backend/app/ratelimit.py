"""
Límite de tasa en memoria (ventana deslizante). Protege el login, el reporte
público y la recuperación de contraseña contra abuso.

Es por proceso: con un solo worker (como en Railway) basta; con varios
workers o réplicas habría que moverlo a Redis.
"""
import threading
import time
from collections import defaultdict, deque

from fastapi import HTTPException, Request, status

from app.config import settings


class Limitador:
    def __init__(self, maximo: int, ventana_seg: int, mensaje: str):
        self.maximo = maximo
        self.ventana = ventana_seg
        self.mensaje = mensaje
        self._eventos: dict[str, deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()

    def _purgar(self, clave: str, ahora: float) -> deque[float]:
        cola = self._eventos[clave]
        while cola and ahora - cola[0] > self.ventana:
            cola.popleft()
        if not cola:
            self._eventos.pop(clave, None)
            return self._eventos[clave]
        return cola

    def bloqueado(self, clave: str) -> bool:
        if not settings.RATE_LIMIT_ENABLED:
            return False
        with self._lock:
            return len(self._purgar(clave, time.monotonic())) >= self.maximo

    def registrar(self, clave: str) -> None:
        with self._lock:
            self._purgar(clave, time.monotonic()).append(time.monotonic())

    def olvidar(self, clave: str) -> None:
        with self._lock:
            self._eventos.pop(clave, None)

    def reiniciar(self) -> None:
        with self._lock:
            self._eventos.clear()

    def exigir(self, clave: str) -> None:
        """Cuenta el evento y rechaza con 429 si se superó el máximo."""
        if self.bloqueado(clave):
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=self.mensaje,
                headers={"Retry-After": str(self.ventana)},
            )
        self.registrar(clave)


def ip_cliente(request: Request) -> str:
    """IP del cliente (uvicorn con --proxy-headers ya resuelve X-Forwarded-For detrás de Railway)."""
    return request.client.host if request.client else "desconocida"


# ---- Instancias usadas por los routers -----------------------------------
FALLOS_LOGIN = Limitador(settings.LOGIN_MAX_FALLOS, settings.LOGIN_VENTANA_MIN * 60,
                         "Demasiados intentos fallidos. Espere unos minutos e intente de nuevo.")
REPORTES_PUBLICOS = Limitador(settings.PUBLIC_MAX_REPORTES, settings.PUBLIC_VENTANA_MIN * 60,
                              "Se enviaron demasiados reportes desde esta conexión. Si es una emergencia real, llame al 110 o al 123.")
SOLICITUDES_RECUPERACION = Limitador(5, 3600, "Demasiadas solicitudes de recuperación. Intente más tarde.")
INTENTOS_RESTABLECER = Limitador(10, 900, "Demasiados intentos. Espere unos minutos e intente de nuevo.")
CONSULTAS_SEGUIMIENTO = Limitador(60, 600, "Demasiadas consultas. Espere unos minutos.")
