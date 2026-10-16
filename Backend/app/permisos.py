"""
Permisos por módulo.

Cada usuario tiene, para cada módulo del centro de despacho, un nivel:
    0 = sin acceso · 1 = ver · 2 = editar

El rol es un perfil predefinido que fija los niveles iniciales. El administrador
puede ajustar cualquier módulo de cualquier usuario; esos ajustes se guardan en
users.permissions (JSON) y tienen prioridad sobre el perfil.

El administrador tiene siempre acceso total y es el único que gestiona usuarios.

La dependencia de FastAPI que exige un permiso en cada endpoint está en
app/security.py → requiere(). Este módulo no depende de FastAPI.
"""
import json
from typing import Iterable, Protocol


class _Usuario(Protocol):
    role: str
    permissions: str | None


SIN_ACCESO, VER, EDITAR = 0, 1, 2
NIVELES = {SIN_ACCESO: "Sin acceso", VER: "Ver", EDITAR: "Editar"}

# Módulos del centro de despacho (el de usuarios es exclusivo del administrador).
MODULOS: dict[str, dict[str, str]] = {
    "panel":      {"nombre": "Panel de control", "ver": "Indicadores y mapa en vivo", "editar": "—"},
    "incidentes": {"nombre": "Incidentes", "ver": "Lista, detalle y bitácora",
                   "editar": "Registrar, reclasificar, asignar unidades, marcar llegada, resolver y cancelar"},
    "despacho":   {"nombre": "Despacho", "ver": "Cola de espera y tablero de flota",
                   "editar": "Procesar la cola y generar simulacros"},
    "flota":      {"nombre": "Flota", "ver": "Unidades y su estado",
                   "editar": "Alta, edición, mantenimiento, regreso a base y baja de unidades"},
    "red":        {"nombre": "Red vial", "ver": "Mapa y calculadora de rutas",
                   "editar": "Cerrar y reabrir vías"},
    "reportes":   {"nombre": "Reportes", "ver": "Descargar PDF y CSV", "editar": "—"},
}

# Módulos que solo tienen nivel "ver" (no hay nada que editar en ellos).
SOLO_LECTURA = {"panel", "reportes"}

_TODO = {m: (VER if m in SOLO_LECTURA else EDITAR) for m in MODULOS}

ROLES: dict[str, dict] = {
    "admin": {
        "nombre": "Administrador",
        "descripcion": "Acceso total. Gestiona usuarios y define sus permisos por módulo.",
        "permisos": _TODO,
    },
    "incidentes": {
        "nombre": "Operador de incidentes",
        "descripcion": "Vigila el estado de los incidentes: registra, asigna unidades y les da seguimiento hasta el cierre.",
        "permisos": {"panel": VER, "incidentes": EDITAR, "despacho": EDITAR, "flota": VER, "red": VER, "reportes": VER},
    },
    "flota": {
        "nombre": "Operador de flota",
        "descripcion": "Vela por las unidades: altas, mantenimiento, disponibilidad y regreso a base.",
        "permisos": {"panel": VER, "incidentes": VER, "despacho": VER, "flota": EDITAR, "red": VER, "reportes": VER},
    },
    "red_vial": {
        "nombre": "Operador de red vial",
        "descripcion": "Controla la red vial: cierra y reabre vías por deslaves, bloqueos o inundaciones.",
        "permisos": {"panel": VER, "incidentes": VER, "despacho": SIN_ACCESO, "flota": VER, "red": EDITAR, "reportes": VER},
    },
    "operator": {
        "nombre": "Operador general",
        "descripcion": "Para centros pequeños: opera todos los módulos, sin gestionar usuarios.",
        "permisos": _TODO,
    },
}


def normalizar(permisos: dict | None) -> dict[str, int]:
    """Deja solo módulos conocidos y niveles válidos (0, 1 o 2; 1 como máximo en los de solo lectura)."""
    limpio: dict[str, int] = {}
    for modulo, nivel in (permisos or {}).items():
        if modulo not in MODULOS:
            continue
        try:
            n = int(nivel)
        except (TypeError, ValueError):
            continue
        tope = VER if modulo in SOLO_LECTURA else EDITAR
        limpio[modulo] = max(SIN_ACCESO, min(n, tope))
    return limpio


def efectivos(user: _Usuario) -> dict[str, int]:
    """Permisos que realmente aplican: los del perfil, sustituidos por los ajustes del administrador."""
    if user.role == "admin":
        return dict(_TODO)
    base = dict(ROLES.get(user.role, ROLES["operator"])["permisos"])
    if user.permissions:
        try:
            base.update(normalizar(json.loads(user.permissions)))
        except (ValueError, TypeError):
            pass
    return {m: base.get(m, SIN_ACCESO) for m in MODULOS}


def personalizado(user: _Usuario) -> bool:
    """¿Los permisos difieren del perfil de su rol?"""
    if user.role == "admin" or user.role not in ROLES:
        return False
    return efectivos(user) != {m: ROLES[user.role]["permisos"].get(m, SIN_ACCESO) for m in MODULOS}


def tiene(user: _Usuario, modulos: Iterable[str], nivel: int) -> bool:
    p = efectivos(user)
    return any(p.get(m, SIN_ACCESO) >= nivel for m in modulos)


def catalogo() -> dict:
    """Roles y módulos para la pantalla de usuarios."""
    return {
        "modules": [
            {"value": m, "label": d["nombre"], "view": d["ver"], "edit": d["editar"], "read_only": m in SOLO_LECTURA}
            for m, d in MODULOS.items()
        ],
        "roles": [
            {"value": r, "label": d["nombre"], "description": d["descripcion"],
             "permissions": {m: d["permisos"].get(m, SIN_ACCESO) for m in MODULOS}}
            for r, d in ROLES.items()
        ],
        "levels": [{"value": k, "label": v} for k, v in NIVELES.items()],
    }
