"""
Carga 100 incidentes de muestra y 3 usuarios (incidentes, flota, red vial) en la base de DATABASE_URL.

Uso (desde la carpeta Backend, con el entorno virtual activo):
    MUESTRA_PASS="una-clave-larga-1234" python scripts/cargar_muestra.py        (Linux/Mac/Git Bash)
    $env:MUESTRA_PASS="una-clave-larga-1234"; python scripts/cargar_muestra.py  (PowerShell)

Para Railway: ponga CARGAR_MUESTRA=True y MUESTRA_PASS en las variables del backend, despliegue una vez
y luego quite CARGAR_MUESTRA (los datos quedan guardados).
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.database import SessionLocal, init_db  # noqa: E402
from app.muestra import USUARIOS_MUESTRA, cargar_muestra  # noqa: E402
from app.seed import sembrar_datos  # noqa: E402

if __name__ == "__main__":
    init_db()
    with SessionLocal() as db:
        sembrar_datos(db)  # geografía, administrador y flota (si faltan)
        r = cargar_muestra(db)
    if r["omitido"]:
        print("La muestra ya estaba cargada: no se hizo nada.")
    else:
        print(f"Listo: {r['incidentes']} incidentes y {r['usuarios']} usuarios.")
        print("Usuarios:", ", ".join(u for u, _, _ in USUARIOS_MUESTRA), "(contraseña = MUESTRA_PASS)")
