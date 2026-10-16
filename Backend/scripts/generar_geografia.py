"""
Genera app/datos/geografia_gt.json: 22 departamentos y 340 municipios con coordenadas.

Fuentes:
- Lista oficial de municipios por departamento: scripts/fuentes/municipios_wikipedia.txt
  (es.wikipedia.org/wiki/Anexo:Municipios_de_Guatemala).
- Coordenadas de las cabeceras municipales: Banco Mundial, "Guatemala - Municipalities
  head offices" (CC BY 4.0), shapefile en proyección GTM.
  https://datacatalog.worldbank.org/search/dataset/0039799

Uso (desde la carpeta Backend):
    python scripts/generar_geografia.py ruta/cabeceras_municipales_gtm_0.zip

Los municipios creados después de 2017 no están en el shapefile; usan coordenadas
aproximadas (campo "aproximada": true) definidas abajo.
"""
import collections
import json
import math
import re
import sys
import unicodedata
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from shapefile_simple import gtm_a_wgs84, leer_dbf, leer_puntos_shp  # noqa: E402

BASE = Path(__file__).resolve().parent.parent
SALIDA = BASE / "app" / "datos" / "geografia_gt.json"
LISTA = Path(__file__).parent / "fuentes" / "municipios_wikipedia.txt"

# Códigos de departamento del INE
DEPARTAMENTOS = [
    ("01", "Guatemala", "Ciudad de Guatemala"), ("02", "El Progreso", "Guastatoya"),
    ("03", "Sacatepéquez", "La Antigua Guatemala"), ("04", "Chimaltenango", "Chimaltenango"),
    ("05", "Escuintla", "Escuintla"), ("06", "Santa Rosa", "Cuilapa"), ("07", "Sololá", "Sololá"),
    ("08", "Totonicapán", "Totonicapán"), ("09", "Quetzaltenango", "Quetzaltenango"),
    ("10", "Suchitepéquez", "Mazatenango"), ("11", "Retalhuleu", "Retalhuleu"),
    ("12", "San Marcos", "San Marcos"), ("13", "Huehuetenango", "Huehuetenango"),
    ("14", "Quiché", "Santa Cruz del Quiché"), ("15", "Baja Verapaz", "Salamá"),
    ("16", "Alta Verapaz", "Cobán"), ("17", "Petén", "Flores"), ("18", "Izabal", "Puerto Barrios"),
    ("19", "Zacapa", "Zacapa"), ("20", "Chiquimula", "Chiquimula"), ("21", "Jalapa", "Jalapa"),
    ("22", "Jutiapa", "Jutiapa"),
]

# Nombre en el shapefile -> nombre oficial
ALIAS = {
    "ANTIGUA GUATEMALA": "LA ANTIGUA GUATEMALA", "BARILLAS": "SANTA CRUZ BARILLAS",
    "CHICHICASTENANGO": "SANTO TOMAS CHICHICASTENANGO", "COLOMBA": "COLOMBA COSTA CUCA",
    "COMALAPA": "SAN JUAN COMALAPA", "CAHABON": "SANTA MARIA CAHABON", "EL CHOL": "SANTA CRUZ EL CHOL",
    "EL RODEO": "SAN JOSE EL RODEO", "GUATEMALA": "CIUDAD DE GUATEMALA",
    "IXTAHUACAN": "SAN ILDEFONSO IXTAHUACAN", "OSTUNCALCO": "SAN JUAN OSTUNCALCO",
    "PETAPA": "SAN MIGUEL PETAPA", "PUEBLO NUEVO TIQUISATE": "TIQUISATE", "PLAYA GRANDE": "IXCAN",
    "QUEZALTEPEQUE": "QUETZALTEPEQUE", "SAN RAIMUNDO": "SAN RAYMUNDO", "SOLOMA": "SAN PEDRO SOLOMA",
    "SANTA CATARINA LA TINTA": "SANTA CATALINA LA TINTA", "TECPAN GUATEMALA": "TECPAN",
}

# Municipios recientes (no están en el shapefile de 2017): coordenadas aproximadas.
APROXIMADOS = {
    ("16", "RAXRUHA"): (15.866, -90.042), ("05", "SIPACATE"): (13.935, -91.145),
    ("13", "PETATAN"): (15.640, -91.700), ("13", "UNION CANTINIL"): (15.520, -91.680),
    ("17", "EL CHAL"): (16.640, -89.650), ("17", "LAS CRUCES"): (16.620, -90.240),
    ("12", "LA BLANCA"): (14.578, -92.142), ("10", "SAN JOSE LA MAQUINA"): (14.320, -91.600),
    ("19", "SAN JORGE"): (14.930, -89.590),
}


def normalizar(texto: str) -> str:
    texto = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode().upper()
    return " ".join(re.sub(r"[^A-Z ]", " ", texto).split())


def distancia(a, b) -> float:
    k = math.cos(math.radians((a[0] + b[0]) / 2))
    return math.hypot(a[0] - b[0], (a[1] - b[1]) * k)


def main(ruta_zip: str) -> None:
    with zipfile.ZipFile(ruta_zip) as z:
        nombres = z.namelist()
        dbf = z.read(next(n for n in nombres if n.lower().endswith(".dbf")))
        shp = z.read(next(n for n in nombres if n.lower().endswith(".shp")))
    filas = leer_dbf(dbf)
    puntos = leer_puntos_shp(shp)

    candidatos = collections.defaultdict(list)  # nombre normalizado -> [(lat, lon)]
    for fila, (x, y) in zip(filas, puntos):
        nombre = normalizar(str(fila.get("nombre", "")))
        nombre = ALIAS.get(nombre, nombre)
        candidatos[nombre].append(tuple(round(v, 6) for v in gtm_a_wgs84(x, y)))

    cod_depto = {nombre: cod for cod, nombre, _ in DEPARTAMENTOS}
    lista = [linea.split("|") for linea in LISTA.read_text(encoding="utf-8").splitlines()
             if linea and not linea.startswith("#")]

    # 1) Nombres únicos -> centroide de cada departamento (para resolver nombres repetidos)
    por_depto = collections.defaultdict(list)
    for depto, muni in lista:
        c = candidatos.get(normalizar(muni), [])
        if len(c) == 1:
            por_depto[cod_depto[depto]].append(c[0])
    centro = {d: (sum(p[0] for p in pts) / len(pts), sum(p[1] for p in pts) / len(pts)) for d, pts in por_depto.items()}

    # 2) Asignar coordenadas
    municipios = []
    for depto, muni in lista:
        d = cod_depto[depto]
        clave = normalizar(muni)
        c = candidatos.get(clave, [])
        aproximada = False
        if len(c) == 1:
            lat, lon = c[0]
        elif len(c) > 1:  # nombre repetido en varios departamentos: el más cercano a este departamento
            lat, lon = min(c, key=lambda p: distancia(p, centro[d]))
        elif (d, clave) in APROXIMADOS:
            lat, lon = APROXIMADOS[(d, clave)]
            aproximada = True
        else:
            raise SystemExit(f"Sin coordenadas: {depto} / {muni}")
        municipios.append({"departamento": d, "nombre": muni, "lat": lat, "lon": lon, "aproximada": aproximada})

    # 3) Códigos: DDMM. La cabecera departamental es 01 y el resto en orden alfabético.
    cabecera = {cod: cab for cod, _, cab in DEPARTAMENTOS}
    salida_munis = []
    for cod, _, _ in DEPARTAMENTOS:
        del_depto = [m for m in municipios if m["departamento"] == cod]
        del_depto.sort(key=lambda m: (m["nombre"] != cabecera[cod], normalizar(m["nombre"])))
        for i, m in enumerate(del_depto, start=1):
            m["codigo"] = f"{cod}{i:02d}"
            m["cabecera_departamental"] = i == 1
            salida_munis.append(m)

    departamentos = []
    for cod, nombre, cab in DEPARTAMENTOS:
        m = next(x for x in salida_munis if x["departamento"] == cod and x["cabecera_departamental"])
        departamentos.append({"codigo": cod, "nombre": nombre, "cabecera": cab, "lat": m["lat"], "lon": m["lon"]})

    datos = {
        "fuente": "Municipios: Wikipedia (Anexo:Municipios de Guatemala). Coordenadas: Banco Mundial, "
                  "Guatemala - Municipalities head offices (CC BY 4.0). Códigos de municipio internos: DD + correlativo.",
        "departamentos": departamentos,
        "municipios": [{k: m[k] for k in ("codigo", "departamento", "nombre", "lat", "lon", "cabecera_departamental", "aproximada")}
                       for m in salida_munis],
    }
    SALIDA.parent.mkdir(parents=True, exist_ok=True)
    SALIDA.write_text(json.dumps(datos, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"{len(departamentos)} departamentos, {len(salida_munis)} municipios "
          f"({sum(m['aproximada'] for m in salida_munis)} con coordenadas aproximadas) -> {SALIDA}")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit(__doc__)
    main(sys.argv[1])
