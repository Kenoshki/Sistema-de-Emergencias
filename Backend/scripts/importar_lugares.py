"""
Importa aldeas, caseríos, colonias y demás lugares poblados desde un CSV.

Uso (desde la carpeta Backend, con el entorno virtual activo):
    python scripts/importar_lugares.py ruta/lugares.csv
    python scripts/importar_lugares.py ruta/lugares.csv --reemplazar   # borra los lugares importados antes

Columnas reconocidas (no importa el orden ni mayúsculas/tildes):
    departamento   (obligatoria)  nombre o código 01..22
    municipio      (obligatoria)  nombre del municipio
    nombre         (obligatoria)  nombre del lugar. También: lugar, lugar_poblado, localidad
    categoria      (opcional)     aldea, caserío, colonia, cantón, finca, paraje...
    latitud        (opcional)     también: lat, y
    longitud       (opcional)     también: lon, lng, x

El municipio se busca por NOMBRE dentro del departamento (los códigos de municipio
de este sistema son internos y no coinciden con los del INE).
Fuente sugerida: listado de lugares poblados del Censo 2018 del INE (www.ine.gob.gt).
Plantilla: scripts/fuentes/plantilla_lugares.csv
"""
import argparse
import csv
import io
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.database import SessionLocal, init_db  # noqa: E402
from app.geografia import DEPARTAMENTOS, MUNICIPIOS, normalizar  # noqa: E402
from app.models import PlaceModel  # noqa: E402

ALIAS_COLUMNAS = {
    "departamento": {"departamento", "depto", "cod_depto", "codigo_departamento", "departamento_nombre"},
    "municipio": {"municipio", "municipio_nombre", "nombre_municipio", "mun"},
    "nombre": {"nombre", "lugar", "lugar_poblado", "localidad", "nombre_lugar", "comunidad"},
    "categoria": {"categoria", "tipo", "categoria_lugar", "clase"},
    "latitud": {"latitud", "lat", "y"},
    "longitud": {"longitud", "lon", "lng", "long", "x"},
}

CATEGORIAS = {"aldea", "caserio", "colonia", "canton", "finca", "paraje", "barrio", "lotificacion",
              "residencial", "asentamiento", "parcelamiento", "comunidad", "sector", "pueblo", "villa", "ciudad"}


def leer_csv(ruta: Path) -> list[dict]:
    crudo = ruta.read_bytes()
    for codificacion in ("utf-8-sig", "latin-1"):
        try:
            texto = crudo.decode(codificacion)
            break
        except UnicodeDecodeError:
            continue
    try:
        dialecto = csv.Sniffer().sniff(texto[:5000], delimiters=",;\t|")
    except csv.Error:
        dialecto = csv.excel
    filas = list(csv.DictReader(io.StringIO(texto), dialect=dialecto))
    if not filas:
        return []
    mapa = {}
    for col in filas[0]:
        clave = normalizar(col or "").replace(" ", "_")
        for destino, alias in ALIAS_COLUMNAS.items():
            if clave in alias and destino not in mapa:
                mapa[destino] = col
    faltan = [c for c in ("departamento", "municipio", "nombre") if c not in mapa]
    if faltan:
        raise SystemExit(f"Faltan columnas obligatorias: {', '.join(faltan)}. Columnas del archivo: {list(filas[0])}")
    return [{destino: (fila.get(origen) or "").strip() for destino, origen in mapa.items()} for fila in filas]


def numero(valor: str):
    try:
        return float(valor.replace(",", ".")) if valor else None
    except ValueError:
        return None


def main() -> None:
    parser = argparse.ArgumentParser(description="Importa lugares poblados desde CSV")
    parser.add_argument("csv", type=Path)
    parser.add_argument("--reemplazar", action="store_true", help="borra antes los lugares importados")
    args = parser.parse_args()

    deptos = {normalizar(d["nombre"]): c for c, d in DEPARTAMENTOS.items()}
    deptos.update({c: c for c in DEPARTAMENTOS})
    deptos.update({str(int(c)): c for c in DEPARTAMENTOS})
    munis = {(m["departamento"], normalizar(m["nombre"])): c for c, m in MUNICIPIOS.items()}
    munis.update({("01", "guatemala"): "0101"})  # "Guatemala" = Ciudad de Guatemala

    filas = leer_csv(args.csv)
    init_db()
    db = SessionLocal()
    try:
        if args.reemplazar:
            borrados = db.query(PlaceModel).delete()
            print(f"Se eliminaron {borrados} lugares anteriores.")
        existentes = {(p.municipality_code, normalizar(p.name)) for p in db.query(PlaceModel).all()}

        nuevos, sin_municipio, repetidos = 0, [], 0
        for i, f in enumerate(filas, start=2):
            depto = deptos.get(normalizar(f["departamento"])) or deptos.get(f["departamento"].zfill(2))
            muni = munis.get((depto, normalizar(f["municipio"]))) if depto else None
            if not muni:
                sin_municipio.append(f"línea {i}: {f['departamento']} / {f['municipio']}")
                continue
            nombre = f["nombre"]
            if not nombre:
                continue
            clave = (muni, normalizar(nombre))
            if clave in existentes:
                repetidos += 1
                continue
            categoria = normalizar(f.get("categoria", ""))
            lat, lon = numero(f.get("latitud", "")), numero(f.get("longitud", ""))
            if lat is not None and lon is not None and not (13.6 <= lat <= 17.9 and -92.35 <= lon <= -88.15):
                lat = lon = None  # coordenadas fuera de Guatemala: se ignoran
            db.add(PlaceModel(
                municipality_code=muni, name=nombre[:150],
                category=categoria if categoria in CATEGORIAS else (f.get("categoria", "")[:40]),
                latitude=lat, longitude=lon, source=args.csv.name[:60],
            ))
            existentes.add(clave)
            nuevos += 1
            if nuevos % 2000 == 0:
                db.commit()
        db.commit()
    finally:
        db.close()

    print(f"Importados: {nuevos}. Repetidos omitidos: {repetidos}. Sin municipio reconocido: {len(sin_municipio)}.")
    for linea in sin_municipio[:20]:
        print("  -", linea)
    if len(sin_municipio) > 20:
        print(f"  ... y {len(sin_municipio) - 20} más")


if __name__ == "__main__":
    main()
