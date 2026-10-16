"""Configuración leída desde variables de entorno (archivo .env)."""
import os

from dotenv import load_dotenv

load_dotenv()


def _bool(nombre: str, defecto: bool) -> bool:
    valor = os.getenv(nombre)
    if valor is None:
        return defecto
    return valor.strip().lower() in ("1", "true", "si", "sí", "yes", "on")


class Settings:
    DATABASE_URL: str = os.getenv("DATABASE_URL", "sqlite:///./emergencias.db")

    JWT_SECRET: str = os.getenv("JWT_SECRET", "cambie-esta-clave-secreta-en-el-env")
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRE_MINUTES: int = int(os.getenv("JWT_EXPIRE_MINUTES", "480"))

    DEFAULT_ADMIN_USER: str = os.getenv("DEFAULT_ADMIN_USER", "admin")
    DEFAULT_ADMIN_PASS: str = os.getenv("DEFAULT_ADMIN_PASS", "1234password")

    CORS_ORIGINS: list[str] = [
        o.strip() for o in os.getenv("CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173").split(",") if o.strip()
    ]

    # Despachar unidades automáticamente al recibir un reporte ciudadano.
    AUTO_DISPATCH: bool = _bool("AUTO_DISPATCH", True)
    # Cargar unidades y un historial de incidentes de ejemplo si la BD está vacía.
    SEED_DEMO_DATA: bool = _bool("SEED_DEMO_DATA", True)
    # Contraseña de los operadores de demostración (incidentes, flota, red vial).
    DEMO_USERS_PASS: str = os.getenv("DEMO_USERS_PASS", "operador2026")

    DEBUG_MODE: bool = _bool("DEBUG_MODE", True)


settings = Settings()
