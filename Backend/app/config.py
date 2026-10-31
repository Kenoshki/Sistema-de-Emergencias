"""Configuración leída desde variables de entorno (archivo .env)."""
import logging
import os

from dotenv import load_dotenv

load_dotenv()

log = logging.getLogger("uvicorn.error")

# Valores de ejemplo públicos: nunca deben usarse en producción.
JWT_SECRET_EJEMPLO = ("cambie-esta-clave-secreta-en-el-env", "cambie-esta-clave-por-una-larga-y-aleatoria")
ADMIN_PASS_EJEMPLO = "1234password"
DEMO_PASS_EJEMPLO = "operador2026"


def _bool(nombre: str, defecto: bool) -> bool:
    valor = os.getenv(nombre)
    if valor is None:
        return defecto
    return valor.strip().lower() in ("1", "true", "si", "sí", "yes", "on")


def _url_base_de_datos(url: str) -> str:
    """Railway entrega mysql://...; SQLAlchemy necesita el driver (mysql+pymysql://...)."""
    if url.startswith("mysql://"):
        url = "mysql+pymysql://" + url[len("mysql://"):]
    if url.startswith("mysql+pymysql://") and "charset=" not in url:
        url += ("&" if "?" in url else "?") + "charset=utf8mb4"
    return url


class Settings:
    # Por seguridad el modo depuración está APAGADO salvo que el .env lo active.
    DEBUG_MODE: bool = _bool("DEBUG_MODE", False)

    DATABASE_URL: str = _url_base_de_datos(
        os.getenv("DATABASE_URL") or os.getenv("MYSQL_URL") or "sqlite:///./emergencias.db"
    )

    JWT_SECRET: str = os.getenv("JWT_SECRET", JWT_SECRET_EJEMPLO[0])
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRE_MINUTES: int = int(os.getenv("JWT_EXPIRE_MINUTES", "240"))

    DEFAULT_ADMIN_USER: str = os.getenv("DEFAULT_ADMIN_USER", "admin")
    DEFAULT_ADMIN_PASS: str = os.getenv("DEFAULT_ADMIN_PASS", ADMIN_PASS_EJEMPLO)
    # Correo del administrador inicial (necesario para "Olvidé mi contraseña").
    DEFAULT_ADMIN_EMAIL: str = os.getenv("DEFAULT_ADMIN_EMAIL", "").strip().lower()

    CORS_ORIGINS: list[str] = [
        o.strip().rstrip("/")
        for o in os.getenv("CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173").split(",")
        if o.strip()
    ]

    # Despachar unidades automáticamente al recibir un reporte ciudadano.
    AUTO_DISPATCH: bool = _bool("AUTO_DISPATCH", True)
    # Cargar unidades y un historial de incidentes de ejemplo si la BD está vacía.
    SEED_DEMO_DATA: bool = _bool("SEED_DEMO_DATA", False)
    # Contraseña de los operadores de demostración (incidentes, flota, red vial).
    DEMO_USERS_PASS: str = os.getenv("DEMO_USERS_PASS", DEMO_PASS_EJEMPLO)

    # Carga única de datos de muestra (100 incidentes + 3 usuarios). Vea app/muestra.py.
    CARGAR_MUESTRA: bool = _bool("CARGAR_MUESTRA", False)
    MUESTRA_PASS: str = os.getenv("MUESTRA_PASS", "")
    MUESTRA_CANTIDAD: int = int(os.getenv("MUESTRA_CANTIDAD", "100"))

    # Prioridad máxima que puede declarar un ciudadano (el operador puede reclasificar).
    PUBLIC_MAX_PRIORITY: int = int(os.getenv("PUBLIC_MAX_PRIORITY", "3"))

    # Límites de tasa (en memoria, por proceso).
    RATE_LIMIT_ENABLED: bool = _bool("RATE_LIMIT_ENABLED", True)
    LOGIN_MAX_FALLOS: int = int(os.getenv("LOGIN_MAX_FALLOS", "5"))       # por IP y por usuario
    LOGIN_VENTANA_MIN: int = int(os.getenv("LOGIN_VENTANA_MIN", "15"))
    PUBLIC_MAX_REPORTES: int = int(os.getenv("PUBLIC_MAX_REPORTES", "5"))  # por IP
    PUBLIC_VENTANA_MIN: int = int(os.getenv("PUBLIC_VENTANA_MIN", "10"))

    # Recuperación de contraseña.
    FRONTEND_URL: str = os.getenv("FRONTEND_URL", "http://localhost:5173").rstrip("/")
    RESET_TOKEN_MINUTES: int = int(os.getenv("RESET_TOKEN_MINUTES", "30"))
    # Correo saliente. Railway bloquea SMTP en planes Free/Hobby: use Resend (HTTPS) allí.
    MAIL_FROM: str = os.getenv("MAIL_FROM", "Emergencias <no-reply@localhost>")
    RESEND_API_KEY: str = os.getenv("RESEND_API_KEY", "")
    SMTP_HOST: str = os.getenv("SMTP_HOST", "")
    SMTP_PORT: int = int(os.getenv("SMTP_PORT", "587"))
    SMTP_USER: str = os.getenv("SMTP_USER", "")
    SMTP_PASSWORD: str = os.getenv("SMTP_PASSWORD", "")
    SMTP_TLS: bool = _bool("SMTP_TLS", True)

    # Documentación interactiva (/docs): solo en depuración, salvo que se active.
    ENABLE_DOCS: bool = _bool("ENABLE_DOCS", DEBUG_MODE)

    def validar(self) -> None:
        """
        En producción (DEBUG_MODE=False) el arranque FALLA si se usan secretos de
        ejemplo; en depuración solo se advierte.
        """
        problemas = []
        if self.JWT_SECRET in JWT_SECRET_EJEMPLO or len(self.JWT_SECRET) < 32:
            problemas.append("JWT_SECRET debe ser una cadena aleatoria de al menos 32 caracteres "
                             "(genérela con: python -c \"import secrets; print(secrets.token_urlsafe(48))\").")
        if self.DEFAULT_ADMIN_PASS == ADMIN_PASS_EJEMPLO or len(self.DEFAULT_ADMIN_PASS) < 10:
            problemas.append("DEFAULT_ADMIN_PASS no puede ser la contraseña de ejemplo y debe tener 10 caracteres o más.")
        if self.SEED_DEMO_DATA and self.DEMO_USERS_PASS == DEMO_PASS_EJEMPLO:
            problemas.append("SEED_DEMO_DATA=True crea operadores con contraseña pública; "
                             "desactívelo o cambie DEMO_USERS_PASS.")
        if self.CARGAR_MUESTRA and (len(self.MUESTRA_PASS) < 10 or self.MUESTRA_PASS == DEMO_PASS_EJEMPLO):
            problemas.append("CARGAR_MUESTRA=True requiere MUESTRA_PASS propia de 10 caracteres o más.")
        if not problemas:
            return
        if self.DEBUG_MODE:
            for p in problemas:
                log.warning("Configuración insegura (permitida solo con DEBUG_MODE=True): %s", p)
            return
        raise RuntimeError("Configuración insegura para producción:\n - " + "\n - ".join(problemas))


settings = Settings()
