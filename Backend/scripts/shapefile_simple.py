"""Lector mínimo de shapefiles de puntos (.shp + .dbf) y conversión GTM -> WGS84.

No requiere librerías externas. Usado por generar_geografia.py.
"""
import math
import struct


def leer_dbf(datos: bytes) -> list[dict]:
    n_registros, long_cab, long_reg = struct.unpack("<IHH", datos[4:12])
    campos = []
    pos = 32
    while datos[pos] != 0x0D:
        nombre = datos[pos:pos + 11].split(b"\x00")[0].decode("latin-1")
        tipo = chr(datos[pos + 11])
        largo = datos[pos + 16]
        campos.append((nombre, tipo, largo))
        pos += 32
    filas = []
    for i in range(n_registros):
        inicio = long_cab + i * long_reg
        reg = datos[inicio:inicio + long_reg]
        if reg[:1] == b"*":
            continue
        fila, p = {}, 1
        for nombre, tipo, largo in campos:
            crudo = reg[p:p + largo]
            p += largo
            for cod in ("utf-8", "latin-1"):
                try:
                    texto = crudo.decode(cod).strip()
                    break
                except UnicodeDecodeError:
                    continue
            if tipo in "NF" and texto:
                try:
                    texto = float(texto) if "." in texto else int(texto)
                except ValueError:
                    pass
            fila[nombre] = texto
        filas.append(fila)
    return filas


def leer_puntos_shp(datos: bytes) -> list[tuple[float, float]]:
    puntos = []
    pos = 100
    while pos < len(datos):
        _, largo = struct.unpack(">ii", datos[pos:pos + 8])
        tipo = struct.unpack("<i", datos[pos + 8:pos + 12])[0]
        if tipo == 1:
            x, y = struct.unpack("<dd", datos[pos + 12:pos + 28])
            puntos.append((x, y))
        else:
            puntos.append((float("nan"), float("nan")))
        pos += 8 + largo * 2
    return puntos


def gtm_a_wgs84(este: float, norte: float, meridiano=-90.5, k0=0.9998, falso_este=500000.0, falso_norte=0.0):
    """Transversa de Mercator inversa (elipsoide WGS84). Devuelve (lat, lon)."""
    a = 6378137.0
    f = 1 / 298.257223563
    e2 = f * (2 - f)
    ep2 = e2 / (1 - e2)
    x = este - falso_este
    m = (norte - falso_norte) / k0
    mu = m / (a * (1 - e2 / 4 - 3 * e2 ** 2 / 64 - 5 * e2 ** 3 / 256))
    e1 = (1 - math.sqrt(1 - e2)) / (1 + math.sqrt(1 - e2))
    phi1 = (mu + (3 * e1 / 2 - 27 * e1 ** 3 / 32) * math.sin(2 * mu)
            + (21 * e1 ** 2 / 16 - 55 * e1 ** 4 / 32) * math.sin(4 * mu)
            + (151 * e1 ** 3 / 96) * math.sin(6 * mu)
            + (1097 * e1 ** 4 / 512) * math.sin(8 * mu))
    s, c, t = math.sin(phi1), math.cos(phi1), math.tan(phi1)
    n1 = a / math.sqrt(1 - e2 * s * s)
    t1 = t * t
    c1 = ep2 * c * c
    r1 = a * (1 - e2) / (1 - e2 * s * s) ** 1.5
    d = x / (n1 * k0)
    lat = phi1 - (n1 * t / r1) * (d * d / 2 - (5 + 3 * t1 + 10 * c1 - 4 * c1 * c1 - 9 * ep2) * d ** 4 / 24
                                  + (61 + 90 * t1 + 298 * c1 + 45 * t1 * t1 - 252 * ep2 - 3 * c1 * c1) * d ** 6 / 720)
    lon = (d - (1 + 2 * t1 + c1) * d ** 3 / 6
           + (5 - 2 * c1 + 28 * t1 - 3 * c1 * c1 + 8 * ep2 + 24 * t1 * t1) * d ** 5 / 120) / c
    return math.degrees(lat), meridiano + math.degrees(lon)
