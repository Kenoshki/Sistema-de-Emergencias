"""
Geografía de Guatemala: 22 departamentos, 340 municipios y zonas.

NODOS DE LA RED (enteros):
- 1 a 25        -> zonas de la Ciudad de Guatemala (municipio 0101).
- 102 a 2217    -> resto de municipios; el número es el código del municipio
                   (0106 Mixco -> nodo 106, 0901 Quetzaltenango -> nodo 901).
El municipio 0101 no es un nodo propio: está representado por sus zonas.

Los datos vienen de app/datos/geografia_gt.json (ver scripts/generar_geografia.py).
"""
from __future__ import annotations

import json
import math
import unicodedata
from functools import lru_cache
from pathlib import Path

from app.catalogos import ZONAS_CAPITAL

_DATOS = json.loads((Path(__file__).parent / "datos" / "geografia_gt.json").read_text(encoding="utf-8"))

DEPARTAMENTOS: dict[str, dict] = {d["codigo"]: d for d in _DATOS["departamentos"]}
MUNICIPIOS: dict[str, dict] = {m["codigo"]: m for m in _DATOS["municipios"]}
MUNICIPIO_CAPITAL = "0101"

# Límites aproximados del territorio (para validar coordenadas GPS).
LIMITES_GT = {"lat_min": 13.6, "lat_max": 17.9, "lon_min": -92.35, "lon_max": -88.15}


def normalizar(texto: str) -> str:
    texto = unicodedata.normalize("NFKD", texto or "").encode("ascii", "ignore").decode().lower()
    return " ".join(texto.replace("-", " ").split())


def _codigo_por_nombre(depto: str, nombre: str) -> str:
    for m in MUNICIPIOS.values():
        if m["departamento"] == depto and normalizar(m["nombre"]) == normalizar(nombre):
            return m["codigo"]
    raise KeyError(f"{nombre} ({depto})")


# --------------------------------------------------------------------------
# Municipios divididos en zonas. Si un municipio aparece aquí, la zona es
# OBLIGATORIA al reportar y debe estar en la lista.
# La capital usa sus zonas oficiales. Los demás rangos son los de uso común:
# verifíquelos con la municipalidad y ajústelos si es necesario.
# --------------------------------------------------------------------------
ZONAS_POR_MUNICIPIO: dict[str, list[int]] = {
    MUNICIPIO_CAPITAL: sorted(ZONAS_CAPITAL),
    _codigo_por_nombre("01", "Mixco"): list(range(1, 12)),
    _codigo_por_nombre("01", "Villa Nueva"): list(range(1, 15)),
    _codigo_por_nombre("09", "Quetzaltenango"): list(range(1, 12)),
}


def zonas_de(municipio: str) -> list[int] | None:
    return ZONAS_POR_MUNICIPIO.get(municipio)


# --------------------------------------------------------------------------
# Nodos
# --------------------------------------------------------------------------
def nodo_de(municipio: str, zona: int | None = None) -> int:
    """Nodo de la red que corresponde a una ubicación."""
    if municipio == MUNICIPIO_CAPITAL:
        if zona not in ZONAS_CAPITAL:
            raise ValueError("En la Ciudad de Guatemala la zona es obligatoria.")
        return int(zona)
    if municipio not in MUNICIPIOS:
        raise ValueError(f"Municipio {municipio} no existe.")
    return int(municipio)


def es_zona_capital(nodo: int) -> bool:
    return nodo in ZONAS_CAPITAL


def municipio_de_nodo(nodo: int) -> str:
    return MUNICIPIO_CAPITAL if es_zona_capital(nodo) else f"{nodo:04d}"


@lru_cache(maxsize=None)
def nodos() -> dict[int, dict]:
    """Todos los nodos de la red con nombre, coordenadas y a qué municipio pertenecen."""
    resultado: dict[int, dict] = {}
    cap = MUNICIPIOS[MUNICIPIO_CAPITAL]
    for z, d in ZONAS_CAPITAL.items():
        resultado[z] = {
            "nodo": z, "tipo": "zona", "nombre": f"Zona {z}", "detalle": d["nombre"],
            "etiqueta": f"Zona {z}, {cap['nombre']}", "lat": d["lat"], "lon": d["lon"],
            "municipio": MUNICIPIO_CAPITAL, "departamento": cap["departamento"], "cabecera_departamental": z == 1,
        }
    for m in MUNICIPIOS.values():
        if m["codigo"] == MUNICIPIO_CAPITAL:
            continue
        depto = DEPARTAMENTOS[m["departamento"]]["nombre"]
        n = int(m["codigo"])
        resultado[n] = {
            "nodo": n, "tipo": "municipio", "nombre": m["nombre"], "detalle": depto,
            "etiqueta": f"{m['nombre']}, {depto}", "lat": m["lat"], "lon": m["lon"],
            "municipio": m["codigo"], "departamento": m["departamento"],
            "cabecera_departamental": m["cabecera_departamental"],
        }
    return resultado


def etiqueta_nodo(nodo: int | None) -> str:
    if nodo is None:
        return "—"
    info = nodos().get(nodo)
    return info["etiqueta"] if info else f"Nodo {nodo}"


def etiqueta_ubicacion(departamento: str | None, municipio: str | None, zona: int | None = None,
                       lugar: str | None = None) -> str:
    partes = []
    if lugar:
        partes.append(lugar)
    if zona is not None:
        partes.append(f"Zona {zona}")
    if municipio and municipio in MUNICIPIOS:
        partes.append(MUNICIPIOS[municipio]["nombre"])
    if departamento and departamento in DEPARTAMENTOS:
        nombre = DEPARTAMENTOS[departamento]["nombre"]
        if not partes or partes[-1] != nombre:
            partes.append(nombre)
    return ", ".join(partes) or "Sin ubicación"


# --------------------------------------------------------------------------
# Distancias y localización por GPS
# --------------------------------------------------------------------------
def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Distancia en línea recta (km) entre dos coordenadas geográficas."""
    radio_tierra = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * radio_tierra * math.asin(math.sqrt(a))


def dentro_de_guatemala(lat: float, lon: float) -> bool:
    return (LIMITES_GT["lat_min"] <= lat <= LIMITES_GT["lat_max"]
            and LIMITES_GT["lon_min"] <= lon <= LIMITES_GT["lon_max"])


def localizar(lat: float, lon: float) -> dict:
    """
    Ubicación más probable de una coordenada GPS: el nodo más cercano (zona de la
    capital o cabecera municipal). Es una APROXIMACIÓN: el ciudadano debe
    confirmarla o corregirla en el formulario.
    """
    if not dentro_de_guatemala(lat, lon):
        return {"dentro": False}
    todos = nodos()
    nodo = min(todos, key=lambda n: haversine_km(lat, lon, todos[n]["lat"], todos[n]["lon"]))
    info = todos[nodo]
    return {
        "dentro": True,
        "nodo": nodo,
        "departamento": info["departamento"],
        "municipio": info["municipio"],
        "zona": nodo if info["tipo"] == "zona" else None,
        "etiqueta": info["etiqueta"],
        "distancia_km": round(haversine_km(lat, lon, info["lat"], info["lon"]), 2),
    }


def coordenadas_de(municipio: str, zona: int | None) -> tuple[float, float]:
    """Coordenadas de referencia de una ubicación elegida en el formulario."""
    if municipio == MUNICIPIO_CAPITAL and zona in ZONAS_CAPITAL:
        return ZONAS_CAPITAL[zona]["lat"], ZONAS_CAPITAL[zona]["lon"]
    m = MUNICIPIOS[municipio]
    return m["lat"], m["lon"]


def validar_ubicacion(departamento: str | None, municipio: str | None, zona: int | None) -> tuple[str, str, int | None]:
    """
    Reglas obligatorias de ubicación. Devuelve (departamento, municipio, zona) normalizados
    o lanza ValueError con un mensaje claro para el usuario.
    """
    if not municipio:
        raise ValueError("Seleccione el municipio.")
    m = MUNICIPIOS.get(municipio)
    if m is None:
        raise ValueError(f"El municipio {municipio} no existe.")
    if departamento and departamento != m["departamento"]:
        depto = DEPARTAMENTOS.get(departamento, {}).get("nombre", departamento)
        raise ValueError(f"{m['nombre']} no pertenece al departamento de {depto}.")
    zonas = zonas_de(municipio)
    if zonas:
        if zona is None:
            raise ValueError(f"{m['nombre']} está dividido en zonas: seleccione la zona.")
        if zona not in zonas:
            raise ValueError(f"La zona {zona} no existe en {m['nombre']}. Zonas válidas: "
                             + ", ".join(str(z) for z in zonas) + ".")
    else:
        zona = None  # el municipio no usa zonas
    return m["departamento"], municipio, zona
