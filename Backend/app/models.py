"""
Modelos ORM (tablas). Todas las columnas de texto tienen longitud explícita
porque MySQL lo exige para VARCHAR.

Ubicación: departamento -> municipio -> (zona) -> lugar poblado (aldea, colonia...).
"Nodo" es el punto de la red vial usado para calcular rutas (ver app/geografia.py).
"""
from datetime import datetime

from sqlalchemy import Boolean, Column, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship

from app.database import Base

# Versión del esquema: si cambia, la base de demostración se recrea al arrancar.
VERSION_ESQUEMA = 2


class SchemaInfoModel(Base):
    __tablename__ = "schema_info"

    id = Column(Integer, primary_key=True)
    version = Column(Integer, nullable=False)


class UserModel(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    username = Column(String(50), unique=True, index=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    # Correo para recuperar la contraseña (en minúsculas; la unicidad se valida en la API).
    email = Column(String(120), nullable=True, index=True)
    # Sube cada vez que cambia la contraseña, el rol o el estado: invalida los tokens anteriores.
    token_version = Column(Integer, nullable=False, default=0, server_default="0")
    full_name = Column(String(100), nullable=False, default="")
    role = Column(String(20), nullable=False, default="operator")  # ver app/permisos.py → ROLES
    # Ajustes del administrador sobre el perfil del rol: JSON {"modulo": 0|1|2}. Vacío = perfil del rol.
    permissions = Column(Text, nullable=True)
    is_active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime, nullable=False, default=datetime.now)


class PasswordResetModel(Base):
    """Enlace de recuperación de contraseña. Solo se guarda el hash del token."""
    __tablename__ = "password_resets"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    token_hash = Column(String(64), unique=True, nullable=False)  # SHA-256 en hexadecimal
    expires_at = Column(DateTime, nullable=False)
    used_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.now)


# ---------------------------------------------------------------- geografía
class DepartmentModel(Base):
    __tablename__ = "departments"

    code = Column(String(2), primary_key=True)          # 01 .. 22 (INE)
    name = Column(String(60), nullable=False)
    head_town = Column(String(80), nullable=False)      # cabecera departamental
    latitude = Column(Float, nullable=False)
    longitude = Column(Float, nullable=False)

    municipalities = relationship("MunicipalityModel", back_populates="department")


class MunicipalityModel(Base):
    __tablename__ = "municipalities"

    code = Column(String(4), primary_key=True)          # DDMM
    department_code = Column(String(2), ForeignKey("departments.code"), nullable=False, index=True)
    name = Column(String(80), nullable=False, index=True)
    latitude = Column(Float, nullable=False)             # cabecera municipal
    longitude = Column(Float, nullable=False)
    is_department_head = Column(Boolean, nullable=False, default=False)
    approximate = Column(Boolean, nullable=False, default=False)
    zones = Column(String(120), nullable=True)           # "1,2,3" si el municipio usa zonas

    department = relationship("DepartmentModel", back_populates="municipalities")


class PlaceModel(Base):
    """Lugar poblado: aldea, caserío, colonia, cantón, finca... (se importa desde CSV)."""
    __tablename__ = "places"

    id = Column(Integer, primary_key=True, autoincrement=True)
    municipality_code = Column(String(4), ForeignKey("municipalities.code"), nullable=False, index=True)
    name = Column(String(150), nullable=False, index=True)
    category = Column(String(40), nullable=False, default="")
    latitude = Column(Float, nullable=True)
    longitude = Column(Float, nullable=True)
    source = Column(String(60), nullable=False, default="")


# ---------------------------------------------------------------- operación
class IncidentModel(Base):
    __tablename__ = "incidents"

    id = Column(String(30), primary_key=True, index=True)  # INC-20261014-0001
    type = Column(String(30), nullable=False, index=True)
    priority = Column(Integer, nullable=False, index=True)  # 1..4

    department_code = Column(String(2), ForeignKey("departments.code"), nullable=False, index=True)
    municipality_code = Column(String(4), ForeignKey("municipalities.code"), nullable=False, index=True)
    zone = Column(Integer, nullable=True)                   # solo en municipios con zonas
    place_id = Column(Integer, ForeignKey("places.id"), nullable=True)
    place_name = Column(String(150), nullable=True)         # aldea/colonia (catálogo o texto)
    node = Column(Integer, nullable=False, index=True)      # nodo de la red vial
    location_source = Column(String(10), nullable=False, default="form")  # form | gps
    latitude = Column(Float, nullable=False)
    longitude = Column(Float, nullable=False)
    address = Column(String(200), nullable=True)

    description = Column(Text, nullable=True)
    reporter_name = Column(String(100), nullable=True)
    reporter_phone = Column(String(20), nullable=True)
    source = Column(String(20), nullable=False, default="public")  # public | operator

    status = Column(String(20), nullable=False, default="pending", index=True)
    # Unidades que aún faltan, en JSON: {"ambulance": 1}
    pending_requirements = Column(Text, nullable=False, default="{}")

    reported_at = Column(DateTime, nullable=False, default=datetime.now, index=True)
    dispatched_at = Column(DateTime, nullable=True)
    arrived_at = Column(DateTime, nullable=True)
    resolved_at = Column(DateTime, nullable=True)

    assignments = relationship(
        "AssignmentModel", back_populates="incident", order_by="AssignmentModel.assigned_at"
    )
    events = relationship(
        "IncidentEventModel", back_populates="incident", order_by="IncidentEventModel.timestamp"
    )


class ResourceModel(Base):
    __tablename__ = "resources"

    code = Column(String(20), primary_key=True, index=True)  # AMB-01, AMB-QZ
    type = Column(String(30), nullable=False, index=True)  # ambulance | firefighters | police | rescue
    name = Column(String(100), nullable=False)
    base_node = Column(Integer, nullable=False)
    current_node = Column(Integer, nullable=False)
    status = Column(String(20), nullable=False, default="available", index=True)
    updated_at = Column(DateTime, nullable=False, default=datetime.now, onupdate=datetime.now)

    assignments = relationship("AssignmentModel", back_populates="resource")


class AssignmentModel(Base):
    """Unidad asignada a un incidente (historial completo de despachos)."""
    __tablename__ = "assignments"

    id = Column(Integer, primary_key=True, autoincrement=True)
    incident_id = Column(String(30), ForeignKey("incidents.id", ondelete="CASCADE"), nullable=False, index=True)
    resource_code = Column(String(20), ForeignKey("resources.code", ondelete="CASCADE"), nullable=False, index=True)
    origin_node = Column(Integer, nullable=False)
    distance_km = Column(Float, nullable=False)
    eta_min = Column(Float, nullable=False)
    route = Column(Text, nullable=False, default="[]")  # JSON: [13, 9, 10]
    method = Column(String(20), nullable=False, default="auto")  # auto | manual
    active = Column(Boolean, nullable=False, default=True, index=True)
    assigned_at = Column(DateTime, nullable=False, default=datetime.now)
    released_at = Column(DateTime, nullable=True)

    incident = relationship("IncidentModel", back_populates="assignments")
    resource = relationship("ResourceModel", back_populates="assignments")


class IncidentEventModel(Base):
    """Bitácora: todo lo que le pasa a un incidente queda registrado."""
    __tablename__ = "incident_events"

    id = Column(Integer, primary_key=True, autoincrement=True)
    incident_id = Column(String(30), ForeignKey("incidents.id", ondelete="CASCADE"), nullable=False, index=True)
    timestamp = Column(DateTime, nullable=False, default=datetime.now)
    event = Column(String(40), nullable=False)
    detail = Column(String(255), nullable=False, default="")
    username = Column(String(50), nullable=True)
    public = Column(Boolean, nullable=False, default=True)  # visible para el ciudadano

    incident = relationship("IncidentModel", back_populates="events")


class RoadClosureModel(Base):
    """Vía cerrada entre dos nodos (deslave, inundación, manifestación...)."""
    __tablename__ = "road_closures"

    id = Column(Integer, primary_key=True, autoincrement=True)
    node_a = Column(Integer, nullable=False)
    node_b = Column(Integer, nullable=False)
    reason = Column(String(200), nullable=False, default="")
    created_by = Column(String(50), nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.now)
