"""
Catálogos del dominio: tipos de incidente, tipos de recurso, estados y zonas.

Todo lo que el sistema "sabe" del mundo real está concentrado aquí para que
sea fácil de ajustar sin tocar la lógica de los algoritmos.

NOTA: Las coordenadas de las zonas son APROXIMADAS (centroide aproximado de
cada zona de la Ciudad de Guatemala) y sirven solo para la simulación.
"""

# --------------------------------------------------------------------------
# Tipos de incidente
# --------------------------------------------------------------------------
TIPOS_INCIDENTE: dict[str, str] = {
    "fire": "Incendio estructural / forestal",
    "accident": "Accidente de tránsito",
    "collapse": "Colapso estructural / sismo",
    "landslide": "Deslave / inundación",
    "medical": "Emergencia médica",
    "robbery": "Robo / asalto en proceso",
}

# --------------------------------------------------------------------------
# Tipos de recurso (unidades de respuesta)
# --------------------------------------------------------------------------
TIPOS_RECURSO: dict[str, str] = {
    "ambulance": "Ambulancia",
    "firefighters": "Bomberos",
    "police": "Policía",
    "rescue": "Rescate",
}

# Velocidad promedio en ciudad (km/h) usada para estimar el tiempo de llegada.
VELOCIDAD_KMH: dict[str, float] = {
    "ambulance": 45.0,
    "firefighters": 38.0,
    "police": 50.0,
    "rescue": 40.0,
}

# --------------------------------------------------------------------------
# Prioridades
# --------------------------------------------------------------------------
PRIORIDADES: dict[int, str] = {
    4: "Crítico",
    3: "Alto",
    2: "Medio",
    1: "Bajo",
}

# --------------------------------------------------------------------------
# Estados
# --------------------------------------------------------------------------
ESTADOS_INCIDENTE: dict[str, str] = {
    "pending": "Pendiente (sin unidades)",
    "dispatched": "Unidades en camino",
    "on_scene": "Unidades en escena",
    "resolved": "Resuelto",
    "cancelled": "Cancelado",
}
ESTADOS_ACTIVOS = ("pending", "dispatched", "on_scene")
ESTADOS_CERRADOS = ("resolved", "cancelled")

ESTADOS_RECURSO: dict[str, str] = {
    "available": "Disponible",
    "dispatched": "En camino",
    "on_scene": "En escena",
    "maintenance": "Mantenimiento",
}

# Roles y permisos: ver app/permisos.py

# --------------------------------------------------------------------------
# Zonas de la Ciudad de Guatemala (coordenadas aproximadas)
# La ciudad no tiene zonas 20, 22 ni 23. Cada zona es un nodo del grafo;
# el resto del país usa un nodo por municipio (ver app/geografia.py).
# --------------------------------------------------------------------------
ZONAS_CAPITAL: dict[int, dict] = {
    1: {"nombre": "Centro Histórico", "lat": 14.6420, "lon": -90.5130},
    2: {"nombre": "Hipódromo del Norte", "lat": 14.6560, "lon": -90.5150},
    3: {"nombre": "Cementerio General / El Gallito", "lat": 14.6340, "lon": -90.5260},
    4: {"nombre": "Centro Cívico", "lat": 14.6250, "lon": -90.5160},
    5: {"nombre": "Estadio / Palomo", "lat": 14.6280, "lon": -90.4950},
    6: {"nombre": "Los Álamos / Cipresales", "lat": 14.6560, "lon": -90.4970},
    7: {"nombre": "Kaminal Juyú / Tikal", "lat": 14.6260, "lon": -90.5530},
    8: {"nombre": "El Trébol", "lat": 14.6170, "lon": -90.5290},
    9: {"nombre": "Plaza España", "lat": 14.6080, "lon": -90.5180},
    10: {"nombre": "Zona Viva", "lat": 14.6000, "lon": -90.5060},
    11: {"nombre": "Roosevelt / Mariscal", "lat": 14.6060, "lon": -90.5480},
    12: {"nombre": "Ciudad Universitaria", "lat": 14.5850, "lon": -90.5360},
    13: {"nombre": "Aeropuerto La Aurora", "lat": 14.5800, "lon": -90.5230},
    14: {"nombre": "Las Américas", "lat": 14.5850, "lon": -90.5020},
    15: {"nombre": "Vista Hermosa", "lat": 14.5960, "lon": -90.4860},
    16: {"nombre": "Cayalá / Las Lomas", "lat": 14.6100, "lon": -90.4700},
    17: {"nombre": "Lavarreda", "lat": 14.6450, "lon": -90.4680},
    18: {"nombre": "Atlántida / El Paraíso", "lat": 14.6650, "lon": -90.4720},
    19: {"nombre": "La Florida", "lat": 14.6050, "lon": -90.5650},
    21: {"nombre": "Justo Rufino Barrios", "lat": 14.5650, "lon": -90.5370},
    24: {"nombre": "Canalitos", "lat": 14.6300, "lon": -90.4500},
    25: {"nombre": "Lo de Rodríguez", "lat": 14.6800, "lon": -90.4450},
}

# Conexiones viales principales entre zonas vecinas de la capital.
CONEXIONES_CAPITAL: list[tuple[int, int]] = [
    (1, 2), (1, 3), (1, 4), (1, 5),
    (2, 6),
    (3, 4), (3, 7), (3, 8),
    (4, 5), (4, 8), (4, 9), (4, 10),
    (5, 6), (5, 10), (5, 16),
    (6, 17), (6, 18),
    (7, 8), (7, 11), (7, 19),
    (8, 9), (8, 11), (8, 12),
    (9, 10), (9, 12), (9, 13),
    (10, 13), (10, 14), (10, 15), (10, 16),
    (11, 12), (11, 19),
    (12, 13), (12, 19), (12, 21),
    (13, 14), (13, 21),
    (14, 15),
    (15, 16),
    (16, 17), (16, 24),
    (17, 18), (17, 24),
    (18, 25),
    (24, 25),
]

# Factor de tortuosidad: las calles no son línea recta, así que la distancia
# por carretera se aproxima como distancia en línea recta * este factor.
FACTOR_TORTUOSIDAD = 1.35          # dentro de la ciudad
FACTOR_TORTUOSIDAD_RURAL = 1.45    # carreteras entre municipios (curvas, montaña)

# Distancia promedio de recorrido cuando la unidad ya está en el mismo nodo.
DISTANCIA_INTRAZONA_KM = 1.5       # misma zona de la capital
DISTANCIA_INTRAMUNICIPAL_KM = 4.0  # mismo municipio (hacia una aldea o colonia)

# Velocidad en carretera para la parte del trayecto fuera del área urbana.
TRAMO_URBANO_KM = 15.0
VELOCIDAD_CARRETERA_KMH = 60.0

# Vecinos más cercanos con los que se conecta cada municipio en la red nacional.
VECINOS_POR_MUNICIPIO = 4


def requerimientos(tipo: str, prioridad: int) -> dict[str, int]:
    """
    Reglas de negocio: qué unidades (y cuántas) necesita un incidente
    según su tipo y prioridad.
    """
    critico = prioridad >= 4
    alto = prioridad >= 3

    reglas: dict[str, int] = {}
    if tipo == "fire":
        reglas["firefighters"] = 2 if alto else 1
        if alto:
            reglas["ambulance"] = 1
    elif tipo == "accident":
        reglas["ambulance"] = 2 if critico else 1
        reglas["police"] = 1
        if critico:
            reglas["rescue"] = 1
    elif tipo == "collapse":
        reglas["rescue"] = 2 if alto else 1
        reglas["ambulance"] = 1
        if alto:
            reglas["firefighters"] = 1
    elif tipo == "landslide":
        reglas["rescue"] = 1
        reglas["firefighters"] = 1
        if alto:
            reglas["ambulance"] = 1
    elif tipo == "medical":
        reglas["ambulance"] = 1
    elif tipo == "robbery":
        reglas["police"] = 2 if alto else 1
        if critico:
            reglas["ambulance"] = 1
    else:
        reglas["police"] = 1
    return reglas
