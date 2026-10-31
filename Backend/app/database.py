"""Conexión a la base de datos (MySQL o SQLite) con SQLAlchemy."""
import logging
import os

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import declarative_base, sessionmaker

from app.config import settings

es_sqlite = settings.DATABASE_URL.startswith("sqlite")

engine = create_engine(
    settings.DATABASE_URL,
    connect_args={"check_same_thread": False} if es_sqlite else {},
    # pool_pre_ping evita el error "MySQL server has gone away" tras inactividad.
    pool_pre_ping=not es_sqlite,
    pool_recycle=3600 if not es_sqlite else -1,
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db():
    """Dependencia de FastAPI: abre una sesión por petición y la cierra al final."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def escapar_like(texto: str) -> str:
    """Escapa % y _ para que el texto del usuario se busque literalmente (usar con escape="\\")."""
    return texto.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def crear_base_si_no_existe() -> None:
    """En MySQL, intenta crear la base de datos de DATABASE_URL si todavía no existe."""
    url = make_url(settings.DATABASE_URL)
    if not url.drivername.startswith("mysql") or not url.database:
        return
    nombre = url.database.replace("`", "")
    try:
        # Conectarse al servidor SIN base de datos (set(database=None) no la quita en SQLAlchemy 2.x)
        servidor = create_engine(url._replace(database=None), pool_pre_ping=True)
        try:
            with servidor.connect() as conn:
                conn.execute(text(
                    f"CREATE DATABASE IF NOT EXISTS `{nombre}` CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci"
                ))
                conn.commit()
        finally:
            servidor.dispose()
    except Exception as exc:  # en hosting administrado (Railway) la base ya existe y puede faltar el permiso
        log.warning("No se pudo verificar/crear la base '%s' (se asume que ya existe): %s", nombre, exc)


log = logging.getLogger("uvicorn.error")

# Columnas agregadas a la tabla de usuarios después de la primera versión (se conservan los usuarios).
COLUMNAS_USUARIOS = {
    "permissions": "TEXT NULL",
    "email": "VARCHAR(120) NULL",
    "token_version": "INTEGER NOT NULL DEFAULT 0",
}


def asegurar_esquema() -> None:
    """
    Crea las tablas que falten y agrega las columnas nuevas de `users`.

    Si la base tiene tablas de una versión anterior incompatible, NO las borra:
    se detiene con un error. Para recrearlas (se pierden incidentes, flota y
    cierres de vías; los usuarios se conservan) arranque una vez con
    RESET_SCHEMA=true.
    """
    from app.models import VERSION_ESQUEMA

    existentes = set(inspect(engine).get_table_names())
    version = None
    if "schema_info" in existentes:
        with engine.connect() as conn:
            version = conn.execute(text("SELECT MAX(version) FROM schema_info")).scalar()

    if existentes & {"incidents", "resources"} and version != VERSION_ESQUEMA:
        if os.getenv("RESET_SCHEMA", "").strip().lower() not in ("1", "true", "yes", "si"):
            raise RuntimeError(
                f"La base tiene un esquema anterior (versión {version}, se esperaba {VERSION_ESQUEMA}). "
                "Por seguridad no se borra nada automáticamente. Haga una copia de seguridad y arranque "
                "con RESET_SCHEMA=true para recrear las tablas de operación (los usuarios se conservan)."
            )
        log.warning("RESET_SCHEMA activo: se recrean las tablas de operación (versión %s).", version)
        a_borrar = [t for t in Base.metadata.sorted_tables if t.name in existentes and t.name not in ("users", "password_resets")]
        Base.metadata.drop_all(bind=engine, tables=a_borrar)

    Base.metadata.create_all(bind=engine)
    columnas = {c["name"] for c in inspect(engine).get_columns("users")}
    for nombre, definicion in COLUMNAS_USUARIOS.items():
        if nombre not in columnas:
            log.warning("Agregando la columna users.%s.", nombre)
            with engine.begin() as conn:
                conn.execute(text(f"ALTER TABLE users ADD COLUMN {nombre} {definicion}"))
    with engine.begin() as conn:
        conn.execute(text("DELETE FROM schema_info"))
        conn.execute(text("INSERT INTO schema_info (id, version) VALUES (1, :v)"), {"v": VERSION_ESQUEMA})


def init_db() -> None:
    # Importar los modelos registra las tablas en Base.metadata
    from app import models  # noqa: F401

    crear_base_si_no_existe()
    asegurar_esquema()
