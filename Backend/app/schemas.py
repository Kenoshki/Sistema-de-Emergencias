"""Esquemas Pydantic: validan los datos que ENTRAN a la API."""
from typing import Optional

from pydantic import BaseModel, Field, field_validator, model_validator

from app.catalogos import ESTADOS_RECURSO, TIPOS_INCIDENTE, TIPOS_RECURSO
from app.geografia import dentro_de_guatemala, localizar, nodos, validar_ubicacion
from app.permisos import MODULOS, ROLES, normalizar


class Ubicacion(BaseModel):
    """
    Ubicación obligatoria. Dos formas válidas:
    1. Formulario: departamento + municipio (+ zona si el municipio se divide en zonas).
    2. Solo GPS: latitud y longitud dentro de Guatemala; el sistema deduce el resto.
    Si llegan ambas, manda lo que eligió la persona en el formulario.
    """
    department_code: Optional[str] = Field(None, min_length=2, max_length=2)
    municipality_code: Optional[str] = Field(None, min_length=4, max_length=4)
    zone: Optional[int] = None
    place_id: Optional[int] = None
    place_name: Optional[str] = Field(None, max_length=150)
    latitude: Optional[float] = Field(None, ge=-90, le=90)
    longitude: Optional[float] = Field(None, ge=-180, le=180)

    @model_validator(mode="after")
    def ubicacion_obligatoria(self):
        if (self.latitude is None) != (self.longitude is None):
            raise ValueError("Latitud y longitud deben enviarse juntas.")
        tiene_gps = self.latitude is not None

        if self.municipality_code or self.department_code or self.zone is not None:
            if not self.department_code:
                raise ValueError("Seleccione el departamento.")
            self.department_code, self.municipality_code, self.zone = validar_ubicacion(
                self.department_code, self.municipality_code, self.zone)
        elif tiene_gps:
            assert self.latitude is not None and self.longitude is not None
            if not dentro_de_guatemala(self.latitude, self.longitude):
                raise ValueError("La ubicación GPS está fuera de Guatemala. Seleccione departamento y municipio.")
            punto = localizar(self.latitude, self.longitude)
            self.department_code, self.municipality_code, self.zone = (
                punto["departamento"], punto["municipio"], punto["zona"])
        else:
            raise ValueError("Indique la ubicación: departamento, municipio (y zona si aplica) "
                             "o comparta su ubicación GPS.")
        if self.place_name is not None:
            self.place_name = self.place_name.strip() or None
        return self


class IncidentCreate(Ubicacion):
    type: str = Field(..., description="Tipo de incidente: " + ", ".join(TIPOS_INCIDENTE))
    priority: int = Field(..., ge=1, le=4, description="1 = bajo ... 4 = crítico")
    address: Optional[str] = Field(None, max_length=200)
    description: Optional[str] = Field(None, max_length=1000)
    # Identificador único del envío: permite reintentar sin duplicar el reporte (ver app/idempotencia.py).
    client_request_id: Optional[str] = Field(None, min_length=8, max_length=64, pattern=r"^[A-Za-z0-9_-]+$")
    reporter_name: Optional[str] = Field(None, max_length=100)
    reporter_phone: Optional[str] = Field(None, max_length=20)

    @field_validator("type")
    @classmethod
    def tipo_valido(cls, v: str) -> str:
        if v not in TIPOS_INCIDENTE:
            raise ValueError(f"Tipo inválido. Use uno de: {', '.join(TIPOS_INCIDENTE)}")
        return v

    @field_validator("reporter_phone")
    @classmethod
    def telefono_valido(cls, v: Optional[str]) -> Optional[str]:
        if v is None or v.strip() == "":
            return None
        limpio = v.replace(" ", "").replace("-", "")
        if not limpio.lstrip("+").isdigit() or len(limpio.lstrip("+")) < 8:
            raise ValueError("Teléfono inválido (mínimo 8 dígitos).")
        return limpio



class IncidentUpdate(BaseModel):
    priority: Optional[int] = Field(None, ge=1, le=4)
    type: Optional[str] = None
    description: Optional[str] = Field(None, max_length=1000)
    address: Optional[str] = Field(None, max_length=200)

    @field_validator("type")
    @classmethod
    def tipo_valido(cls, v):
        if v is not None and v not in TIPOS_INCIDENTE:
            raise ValueError("Tipo de incidente inválido.")
        return v


class NotaIncidente(BaseModel):
    detalle: str = Field(..., min_length=1, max_length=255)


def _correo_valido(v: Optional[str]) -> Optional[str]:
    if v is None:
        return None
    v = v.strip().lower()
    if v == "":
        return ""  # en UserUpdate vacío = quitar el correo
    local, _, dominio = v.rpartition("@")
    if not local or "." not in dominio or " " in v or len(v) > 120 or dominio.startswith(".") or dominio.endswith("."):
        raise ValueError("Correo electrónico inválido.")
    return v


class OlvideContrasena(BaseModel):
    identificador: str = Field(..., min_length=3, max_length=120, description="Usuario o correo")


class RestablecerContrasena(BaseModel):
    token: str = Field(..., min_length=20, max_length=200)
    password: str = Field(..., min_length=8, max_length=128)


class LoginRequest(BaseModel):
    username: str = Field(..., min_length=1, max_length=50)
    password: str = Field(..., min_length=1, max_length=128)


class BaseUnidad(BaseModel):
    """Base de una unidad: municipio (y zona si aplica)."""
    base_department_code: Optional[str] = Field(None, min_length=2, max_length=2)
    base_municipality_code: Optional[str] = Field(None, min_length=4, max_length=4)
    base_zone: Optional[int] = None

    def nodo_base(self) -> Optional[int]:
        from app.geografia import nodo_de
        if not self.base_municipality_code:
            return None
        return nodo_de(self.base_municipality_code, self.base_zone)

    @model_validator(mode="after")
    def validar_base(self):
        if self.base_municipality_code or self.base_department_code:
            _, self.base_municipality_code, self.base_zone = validar_ubicacion(
                self.base_department_code, self.base_municipality_code, self.base_zone)
        return self


class ResourceCreate(BaseUnidad):
    code: str = Field(..., min_length=2, max_length=20, pattern=r"^[A-Z0-9-]+$")
    type: str
    name: str = Field(..., min_length=2, max_length=100)

    @field_validator("type")
    @classmethod
    def tipo_valido(cls, v):
        if v not in TIPOS_RECURSO:
            raise ValueError(f"Tipo inválido. Use uno de: {', '.join(TIPOS_RECURSO)}")
        return v

    @model_validator(mode="after")
    def base_obligatoria(self):
        if not self.base_municipality_code:
            raise ValueError("Indique el municipio base de la unidad.")
        return self


class ResourceUpdate(BaseUnidad):
    name: Optional[str] = Field(None, min_length=2, max_length=100)
    status: Optional[str] = None

    @field_validator("status")
    @classmethod
    def estado_valido(cls, v):
        # Solo se puede poner/quitar mantenimiento manualmente; el resto lo maneja el despacho.
        if v is not None and v not in ("available", "maintenance"):
            raise ValueError(f"Estado inválido. Valores permitidos manualmente: available, maintenance ({', '.join(ESTADOS_RECURSO)})")
        return v


class ManualAssign(BaseModel):
    incident_id: str
    resource_code: str


class RoadClosureCreate(BaseModel):
    node_a: int
    node_b: int
    reason: str = Field("", max_length=200)

    @field_validator("node_a", "node_b")
    @classmethod
    def nodo_valido(cls, v):
        if v not in nodos():
            raise ValueError(f"El nodo {v} no existe en la red vial.")
        return v


class UserCreate(BaseModel):
    username: str = Field(..., min_length=3, max_length=50, pattern=r"^[a-zA-Z0-9_.-]+$")
    password: str = Field(..., min_length=8, max_length=128)
    full_name: str = Field("", max_length=100)
    email: Optional[str] = None
    role: str = "incidentes"
    # Ajustes por módulo sobre el perfil del rol ({"flota": 2, ...}); None = perfil del rol.
    permissions: Optional[dict[str, int]] = None

    @field_validator("role")
    @classmethod
    def rol_valido(cls, v):
        if v not in ROLES:
            raise ValueError(f"Rol inválido. Use: {', '.join(ROLES)}")
        return v

    @field_validator("email")
    @classmethod
    def correo_valido(cls, v):
        return _correo_valido(v) or None

    @field_validator("permissions")
    @classmethod
    def permisos_validos(cls, v):
        return _validar_permisos(v)


class UserUpdate(BaseModel):
    full_name: Optional[str] = Field(None, max_length=100)
    email: Optional[str] = None  # "" = quitar el correo
    role: Optional[str] = None
    is_active: Optional[bool] = None
    password: Optional[str] = Field(None, min_length=8, max_length=128)
    # {} o None con reset_permissions=True vuelve al perfil del rol.
    permissions: Optional[dict[str, int]] = None
    reset_permissions: bool = False

    @field_validator("role")
    @classmethod
    def rol_valido(cls, v):
        if v is not None and v not in ROLES:
            raise ValueError("Rol inválido.")
        return v

    @field_validator("email")
    @classmethod
    def correo_valido(cls, v):
        return _correo_valido(v)

    @field_validator("permissions")
    @classmethod
    def permisos_validos(cls, v):
        return _validar_permisos(v)


def _validar_permisos(v: Optional[dict]) -> Optional[dict[str, int]]:
    if v is None:
        return None
    desconocidos = [m for m in v if m not in MODULOS]
    if desconocidos:
        raise ValueError(f"Módulos desconocidos: {', '.join(desconocidos)}. Use: {', '.join(MODULOS)}")
    if any(n not in (0, 1, 2) for n in v.values()):
        raise ValueError("Cada nivel debe ser 0 (sin acceso), 1 (ver) o 2 (editar).")
    return normalizar(v)
