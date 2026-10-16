"""Conexión a la base de datos (MySQL o SQLite) con SQLAlchemy."""
import logging

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


def crear_base_si_no_existe() -> None:
    """En MySQL, crea la base de datos indicada en DATABASE_URL si todavía no existe."""
    url = make_url(settings.DATABASE_URL)
    if not url.drivername.startswith("mysql") or not url.database:
        return
    nombre = url.database.replace("`", "")
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


log = logging.getLogger("uvicorn.error")


def asegurar_esquema() -> None:
    """
    Si la base tiene tablas de una versión anterior del sistema (otras columnas),
    las elimina y las vuelve a crear. Los usuarios se conservan.
    Solo se pierden incidentes, flota y cierres de vías (datos de demostración).
    """
    from app.models import VERSION_ESQUEMA

    existentes = set(inspect(engine).get_table_names())
    version = None
    if "schema_info" in existentes:
        with engine.connect() as conn:
            version = conn.execute(text("SELECT MAX(version) FROM schema_info")).scalar()

    if existentes & {"incidents", "resources"} and version != VERSION_ESQUEMA:
        log.warning("Esquema anterior detectado (versión %s). Se recrean las tablas de operación "
                    "(los usuarios se conservan).", version)
        a_borrar = [t for t in Base.metadata.sorted_tables if t.name in existentes and t.name != "users"]
        Base.metadata.drop_all(bind=engine, tables=a_borrar)

    Base.metadata.create_all(bind=engine)
    # La tabla de usuarios se conserva entre versiones: se agregan las columnas nuevas.
    columnas = {c["name"] for c in inspect(engine).get_columns("users")}
    if "permissions" not in columnas:
        log.warning("Agregando la columna users.permissions (permisos por módulo).")
        with engine.begin() as conn:
            conn.execute(text("ALTER TABLE users ADD COLUMN permissions TEXT NULL"))
    with engine.begin() as conn:
        conn.execute(text("DELETE FROM schema_info"))
        conn.execute(text("INSERT INTO schema_info (id, version) VALUES (1, :v)"), {"v": VERSION_ESQUEMA})


def init_db() -> None:
    # Importar los modelos registra las tablas en Base.metadata
    from app import models  # noqa: F401

    crear_base_si_no_existe()
    asegurar_esquema()
