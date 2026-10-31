"""
Prueba de punta a punta de la API (usa una base SQLite temporal, no toca MySQL).

Ejecutar desde la carpeta Backend, con el entorno virtual activo:
    python -m pytest -v
"""
import os
import tempfile

# La configuración se lee al importar la app, así que se define ANTES.
_tmp = tempfile.mkdtemp()
os.environ["DATABASE_URL"] = "sqlite:///" + os.path.join(_tmp, "prueba.db").replace("\\", "/")
os.environ["SEED_DEMO_DATA"] = "False"
os.environ["AUTO_DISPATCH"] = "True"
os.environ["DEFAULT_ADMIN_USER"] = "admin"
os.environ["DEFAULT_ADMIN_PASS"] = "1234password"
os.environ["JWT_SECRET"] = "clave-de-prueba-con-mas-de-treinta-y-dos-caracteres"
os.environ["DEBUG_MODE"] = "True"
os.environ["RATE_LIMIT_ENABLED"] = "False"
os.environ["DEFAULT_ADMIN_EMAIL"] = "admin@ejemplo.test"

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.simulacion import RECURSOS_INICIALES  # noqa: E402
from main import app  # noqa: E402


def _base_capital(zona: int) -> dict:
    return {"base_department_code": "01", "base_municipality_code": "0101", "base_zone": zona}


def capital(zona: int) -> dict:
    """Ubicación en la Ciudad de Guatemala."""
    return {"department_code": "01", "municipality_code": "0101", "zone": zona}


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:  # "with" ejecuta el arranque (tablas + flota)
        yield c


@pytest.fixture(scope="module")
def auth(client):
    r = client.post("/api/auth/login", json={"username": "admin", "password": "1234password"})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def test_salud(client):
    assert client.get("/api/health").json()["status"] == "ok"


def test_catalogos(client):
    datos = client.get("/api/public/catalogs").json()
    assert len(datos["departments"]) == 22
    assert len(datos["municipalities"]) == 340
    capital_ = next(m for m in datos["municipalities"] if m["value"] == "0101")
    assert len(capital_["zones"]) == 22
    assert {t["value"] for t in datos["incident_types"]} >= {"fire", "accident", "medical"}


def test_ubicar_por_gps(client):
    r = client.get("/api/public/locate?lat=14.58&lon=-90.523").json()
    assert r["inside"] and r["municipality_code"] == "0101" and r["zone"] == 13
    assert client.get("/api/public/locate?lat=19.43&lon=-99.13").json() == {"inside": False}


def test_ubicacion_obligatoria(client):
    base = {"type": "medical", "priority": 2}
    # Sin ubicación
    r = client.post("/api/public/incidents", json=base)
    assert r.status_code == 422 and "Indique la ubicación" in r.json()["detail"]
    # Capital sin zona
    r = client.post("/api/public/incidents", json={**base, "department_code": "01", "municipality_code": "0101"})
    assert r.status_code == 422 and "zona" in r.json()["detail"]
    # Zona que no existe
    r = client.post("/api/public/incidents", json={**base, **capital(20)})
    assert r.status_code == 422 and "no existe" in r.json()["detail"]
    # Municipio de otro departamento
    r = client.post("/api/public/incidents", json={**base, "department_code": "09", "municipality_code": "0101", "zone": 1})
    assert r.status_code == 422 and "no pertenece" in r.json()["detail"]
    # GPS fuera del país
    r = client.post("/api/public/incidents", json={**base, "latitude": 19.43, "longitude": -99.13})
    assert r.status_code == 422


def test_login_incorrecto(client):
    r = client.post("/api/auth/login", json={"username": "admin", "password": "mala"})
    assert r.status_code == 401


def test_admin_requiere_token(client):
    assert client.get("/api/admin/incidents").status_code == 401
    assert client.get("/api/admin/analytics/kpis").status_code == 401
    r = client.get("/api/admin/incidents", headers={"Authorization": "Bearer token-falso"})
    assert r.status_code == 401


def test_me(client, auth):
    assert client.get("/api/auth/me", headers=auth).json()["role"] == "admin"


def test_flota_inicial(client, auth):
    flota = client.get("/api/admin/resources", headers=auth).json()
    assert len(flota) == len(RECURSOS_INICIALES) == 99   # flota nacional
    assert all(r["status"] == "available" for r in flota)


def test_validacion_en_espanol(client):
    r = client.post("/api/public/incidents", json={"type": "volcan", "priority": 9})
    assert r.status_code == 422
    assert "Tipo inválido" in r.json()["detail"]


def test_reporte_publico_despacha_automaticamente(client, auth):
    r = client.post("/api/public/incidents", json={
        "type": "fire", "priority": 4, **capital(1), "description": "Incendio de prueba",
        "reporter_name": "Prueba", "reporter_phone": "5555-1234",
    })
    assert r.status_code == 201, r.text
    datos = r.json()["data"]
    assert datos["id"].startswith("INC-")
    assert datos["status"] == "dispatched"
    tipos = sorted(u["type_label"] for u in datos["units"])
    assert tipos == ["Ambulancia", "Bomberos", "Bomberos"]
    # La unidad de bomberos de la zona 1 (BOM-01) debe ser la primera elegida
    assert "BOM-01" in [u["code"] for u in datos["units"]]

    seguimiento = client.get(f"/api/public/incidents/{datos['id'].lower()}")
    assert seguimiento.status_code == 200
    assert seguimiento.json()["status"] == "dispatched"

    detalle = client.get(f"/api/admin/incidents/{datos['id']}", headers=auth).json()
    assert detalle["reporter_phone"] == "55551234"
    assert len(detalle["assignments"]) == 3
    assert detalle["assignments"][0]["route"][-1] == 1


def test_ubicacion_por_coordenadas(client):
    r = client.post("/api/public/incidents", json={"type": "medical", "priority": 2,
                                                   "latitude": 14.5801, "longitude": -90.5231})
    assert r.status_code == 201
    assert r.json()["data"]["location_label"].startswith("Zona 13")


def test_reporte_en_el_interior(client, auth):
    cat = client.get("/api/public/catalogs").json()
    coban = next(m for m in cat["municipalities"] if m["label"] == "Cobán")
    r = client.post("/api/public/incidents", json={
        "type": "landslide", "priority": 3, "department_code": "16", "municipality_code": coban["value"],
        "place_name": "Aldea de prueba"})
    assert r.status_code == 201, r.text
    datos = r.json()["data"]
    assert datos["location_label"] == "Aldea de prueba, Cobán, Alta Verapaz"
    # La base departamental de Alta Verapaz es la más cercana
    assert any(u["code"].endswith("-AV") for u in datos["units"])


def test_seguimiento_inexistente(client):
    assert client.get("/api/public/incidents/INC-00000000-0000").status_code == 404


def test_cola_de_espera_y_liberacion(client, auth):
    # Se dejan solo 3 patrullas libres: el 2º robo (pide 2) queda esperando 1.
    patrullas = [r for r in client.get("/api/admin/resources?type=police&status=available", headers=auth).json()]
    for r in patrullas[3:]:
        assert client.patch(f"/api/admin/resources/{r['code']}", headers=auth, json={"status": "maintenance"}).status_code == 200
    ids = []
    for zona in (10, 7):
        r = client.post("/api/admin/incidents", headers=auth,
                        json={"type": "robbery", "priority": 3, **capital(zona)})
        assert r.status_code == 201, r.text
        ids.append(r.json()["id"])

    segundo = client.get(f"/api/admin/incidents/{ids[1]}", headers=auth).json()
    assert segundo["pending_requirements"] == {"police": 1}
    ids.append(ids[1])

    cola = client.get("/api/admin/dispatch/queue", headers=auth).json()
    assert ids[2] in [c["incidente_id"] for c in cola]

    # Al resolver el primero se liberan 2 patrullas y la cola se atiende sola.
    r = client.post(f"/api/admin/incidents/{ids[0]}/resolve", headers=auth, json={"nota": "Sospechoso detenido"})
    assert r.status_code == 200, r.text
    assert any(x["incidente_id"] == ids[2] for x in r.json()["queue_dispatched"])

    tercero = client.get(f"/api/admin/incidents/{ids[2]}", headers=auth).json()
    assert tercero["pending_requirements"] == {}
    assert len(tercero["active_units"]) == 2
    for r in patrullas[3:]:
        client.patch(f"/api/admin/resources/{r['code']}", headers=auth, json={"status": "available"})


def test_transiciones_de_estado(client, auth):
    r = client.post("/api/admin/incidents", headers=auth, json={"type": "medical", "priority": 3, **capital(9)})
    inc_id = r.json()["id"]
    assert r.json()["status"] == "dispatched"

    r = client.post(f"/api/admin/incidents/{inc_id}/arrive", headers=auth)
    assert r.status_code == 200 and r.json()["status"] == "on_scene"
    assert r.json()["response_time_min"] is not None

    # No se puede marcar llegada dos veces
    assert client.post(f"/api/admin/incidents/{inc_id}/arrive", headers=auth).status_code == 409

    r = client.post(f"/api/admin/incidents/{inc_id}/resolve", headers=auth)
    assert r.json()["incident"]["status"] == "resolved"
    assert client.post(f"/api/admin/incidents/{inc_id}/cancel", headers=auth).status_code == 409

    # La ambulancia quedó libre en el lugar del incidente
    unidad = r.json()["incident"]["assignments"][0]["resource_code"]
    recurso = next(x for x in client.get("/api/admin/resources", headers=auth).json() if x["code"] == unidad)
    assert recurso["status"] == "available"
    assert recurso["current_node"] == 9


def test_reclasificar_prioridad_pide_mas_unidades(client, auth):
    r = client.post("/api/admin/incidents", headers=auth, json={"type": "collapse", "priority": 2, **capital(13)})
    inc_id = r.json()["id"]
    antes = len(r.json()["active_units"])
    r = client.patch(f"/api/admin/incidents/{inc_id}", headers=auth, json={"priority": 4})
    assert r.status_code == 200
    assert len(r.json()["active_units"]) > antes


def test_asignacion_manual(client, auth):
    r = client.post("/api/admin/incidents", headers=auth, json={"type": "medical", "priority": 1, **capital(15)})
    inc_id = r.json()["id"]
    libre = next(x for x in client.get("/api/admin/resources?status=available", headers=auth).json() if x["type"] == "rescue")
    r = client.post("/api/admin/dispatch/manual", headers=auth,
                    json={"incident_id": inc_id, "resource_code": libre["code"]})
    assert r.status_code == 200, r.text
    assert libre["code"] in r.json()["active_units"]
    # La misma unidad ya no está disponible
    r = client.post("/api/admin/dispatch/manual", headers=auth,
                    json={"incident_id": inc_id, "resource_code": libre["code"]})
    assert r.status_code == 409


def test_vista_previa_despacho(client, auth):
    r = client.post("/api/admin/incidents", headers=auth, json={"type": "accident", "priority": 2, **capital(14)})
    preview = client.get(f"/api/admin/incidents/{r.json()['id']}/dispatch-preview", headers=auth).json()
    assert "ambulance" in preview["ranking"] or preview["missing"]


def test_red_vial_y_cierres(client, auth):
    red = client.get("/api/admin/network", headers=auth).json()
    assert len(red["nodes"]) == 22 + 339 and red["connected"] is True

    ruta = client.get("/api/admin/network/route?origen=1&destino=2", headers=auth).json()
    assert ruta["camino"] == [1, 2]
    assert ruta["verificacion_networkx"]["coincide"] is True

    r = client.post("/api/admin/network/closures", headers=auth, json={"node_a": 2, "node_b": 1, "reason": "Deslave"})
    assert r.status_code == 201
    cierre_id = r.json()["id"]
    ruta = client.get("/api/admin/network/route?origen=1&destino=2", headers=auth).json()
    assert ruta["camino"] != [1, 2]
    assert ruta["verificacion_networkx"]["coincide"] is True

    # Conexión inexistente
    assert client.post("/api/admin/network/closures", headers=auth, json={"node_a": 1, "node_b": 25}).status_code == 400
    assert client.delete(f"/api/admin/network/closures/{cierre_id}", headers=auth).status_code == 204


def test_analitica_y_reportes(client, auth):
    k = client.get("/api/admin/analytics/kpis", headers=auth).json()
    assert k["total_incidents"] >= 5
    assert k["fleet_total"] >= len(RECURSOS_INICIALES)
    assert k["avg_response_time_min"] is not None

    s = client.get("/api/admin/analytics/summary?dias=7", headers=auth).json()
    assert len(s["daily_trend"]) == 7

    pdf = client.get("/api/admin/reports/pdf", headers=auth)
    assert pdf.status_code == 200 and pdf.content.startswith(b"%PDF")

    csv = client.get("/api/admin/reports/csv", headers=auth)
    assert csv.status_code == 200 and "Min. respuesta" in csv.content.decode("utf-8-sig")


def _crear_y_entrar(client, auth, usuario: str, rol: str, permisos: dict | None = None) -> dict:
    datos = {"username": usuario, "password": "Operador2026", "full_name": usuario, "role": rol}
    if permisos is not None:
        datos["permissions"] = permisos
    r = client.post("/api/admin/users", headers=auth, json=datos)
    assert r.status_code == 201, r.text
    token = client.post("/api/auth/login", json={"username": usuario, "password": "Operador2026"}).json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def test_roles_disponibles(client, auth):
    cat = client.get("/api/admin/users/roles", headers=auth).json()
    assert {r["value"] for r in cat["roles"]} == {"admin", "incidentes", "flota", "red_vial", "operator"}
    assert {m["value"] for m in cat["modules"]} == {"panel", "incidentes", "despacho", "flota", "red", "reportes"}


def test_operador_de_incidentes(client, auth):
    op = _crear_y_entrar(client, auth, "op.inc", "incidentes")
    yo = client.get("/api/auth/me", headers=op).json()
    assert yo["permissions"]["incidentes"] == 2 and yo["permissions"]["flota"] == 1
    # Puede registrar incidentes y ver la flota...
    r = client.post("/api/admin/incidents", headers=op, json={"type": "medical", "priority": 2, **capital(1)})
    assert r.status_code == 201, r.text
    assert client.get("/api/admin/resources", headers=op).status_code == 200
    # ...pero no modificar la flota, cerrar vías ni gestionar usuarios.
    assert client.patch("/api/admin/resources/AMB-02", headers=op, json={"status": "maintenance"}).status_code == 403
    assert client.post("/api/admin/network/closures", headers=op, json={"node_a": 1, "node_b": 4}).status_code == 403
    assert client.get("/api/admin/users", headers=op).status_code == 403


def test_operador_de_flota(client, auth):
    op = _crear_y_entrar(client, auth, "op.flo", "flota")
    assert client.get("/api/admin/incidents", headers=op).status_code == 200
    r = client.post("/api/admin/incidents", headers=op, json={"type": "medical", "priority": 2, **capital(1)})
    assert r.status_code == 403 and "permiso" in r.json()["detail"]
    r = client.post("/api/admin/resources", headers=op, json={"code": "RES-98", "type": "rescue", "name": "Prueba", **_base_capital(2)})
    assert r.status_code == 201, r.text


def test_operador_de_red_vial(client, auth):
    op = _crear_y_entrar(client, auth, "op.red", "red_vial")
    assert client.get("/api/admin/dispatch/queue", headers=op).status_code == 403   # sin acceso a Despacho
    r = client.post("/api/admin/network/closures", headers=op, json={"node_a": 1, "node_b": 4, "reason": "Prueba"})
    assert r.status_code == 201, r.text
    assert client.delete(f"/api/admin/network/closures/{r.json()['id']}", headers=op).status_code == 204
    assert client.post("/api/admin/resources/AMB-01/return-base", headers=op).status_code == 403


def test_permisos_ajustados_por_el_administrador(client, auth):
    # Operador de flota al que el administrador le quita el panel y le permite cerrar vías.
    op = _crear_y_entrar(client, auth, "op.mixto", "flota", {"panel": 0, "red": 2})
    yo = client.get("/api/auth/me", headers=op).json()
    assert yo["custom_permissions"] is True
    assert yo["permissions"]["panel"] == 0 and yo["permissions"]["red"] == 2
    assert client.get("/api/admin/analytics/kpis", headers=op).status_code == 200      # reportes: ver
    r = client.post("/api/admin/network/closures", headers=op, json={"node_a": 2, "node_b": 6})
    assert r.status_code == 201, r.text
    client.delete(f"/api/admin/network/closures/{r.json()['id']}", headers=op)
    # Volver al perfil del rol
    uid = yo["id"]
    r = client.patch(f"/api/admin/users/{uid}", headers=auth, json={"reset_permissions": True})
    assert r.json()["custom_permissions"] is False and r.json()["permissions"]["red"] == 1
    assert client.post("/api/admin/network/closures", headers=op, json={"node_a": 2, "node_b": 6}).status_code == 403
    # Nivel inválido
    r = client.patch(f"/api/admin/users/{uid}", headers=auth, json={"permissions": {"flota": 5}})
    assert r.status_code == 422


def test_crear_y_eliminar_recurso(client, auth):
    r = client.post("/api/admin/resources", headers=auth,
                    json={"code": "AMB-99", "type": "ambulance", "name": "Ambulancia de prueba", **_base_capital(5)})
    assert r.status_code == 201, r.text
    assert client.post("/api/admin/resources", headers=auth,
                       json={"code": "AMB-99", "type": "ambulance", "name": "Repetida", **_base_capital(5)}).status_code == 409
    # Si la unidad nueva atendió la cola, ya no está libre para borrarse; en ese caso se omite.
    estado = next(x for x in client.get("/api/admin/resources", headers=auth).json() if x["code"] == "AMB-99")["status"]
    if estado == "available":
        assert client.delete("/api/admin/resources/AMB-99", headers=auth).status_code == 204


# ---------------------------------------------------- seguridad y recuperación
def _crear_usuario(client, auth, username, email="oper@ejemplo.test", password="clave-inicial-1"):
    r = client.post("/api/admin/users", headers=auth, json={
        "username": username, "password": password, "full_name": "Prueba", "role": "flota", "email": email})
    assert r.status_code == 201, r.text
    return r.json()


def _login(client, username, password):
    return client.post("/api/auth/login", json={"username": username, "password": password})


@pytest.fixture()
def correos(monkeypatch):
    """Captura los correos de recuperación en lugar de enviarlos."""
    enviados = []
    monkeypatch.setattr("app.routers.auth.enviar_recuperacion",
                        lambda destino, nombre, enlace, minutos: enviados.append((destino, enlace)) or True)
    return enviados


def test_recuperar_contrasena_flujo_completo(client, auth, correos):
    _crear_usuario(client, auth, "rec.flujo", "rec.flujo@ejemplo.test")
    token_viejo = _login(client, "rec.flujo", "clave-inicial-1").json()["access_token"]

    r = client.post("/api/auth/forgot-password", json={"identificador": "rec.flujo@ejemplo.test"})
    assert r.status_code == 200
    assert len(correos) == 1 and correos[0][0] == "rec.flujo@ejemplo.test"
    token = correos[0][1].rsplit("/", 1)[1]

    r = client.post("/api/auth/reset-password", json={"token": token, "password": "nueva-clave-segura"})
    assert r.status_code == 200, r.text
    assert _login(client, "rec.flujo", "nueva-clave-segura").status_code == 200
    assert _login(client, "rec.flujo", "clave-inicial-1").status_code == 401
    # el enlace sirve una sola vez y las sesiones anteriores quedan cerradas
    assert client.post("/api/auth/reset-password", json={"token": token, "password": "otra-clave-nueva"}).status_code == 400
    assert client.get("/api/auth/me", headers={"Authorization": f"Bearer {token_viejo}"}).status_code == 401


def test_recuperar_no_revela_si_la_cuenta_existe(client, correos):
    existente = client.post("/api/auth/forgot-password", json={"identificador": "admin"})
    inexistente = client.post("/api/auth/forgot-password", json={"identificador": "no.existe.nadie"})
    assert existente.status_code == inexistente.status_code == 200
    assert existente.json() == inexistente.json()


def test_token_de_recuperacion_invalido_o_vencido(client, auth, correos):
    from datetime import datetime, timedelta

    from app.database import SessionLocal
    from app.models import PasswordResetModel

    assert client.post("/api/auth/reset-password",
                       json={"token": "x" * 40, "password": "nueva-clave-segura"}).status_code == 400
    _crear_usuario(client, auth, "rec.vence", "rec.vence@ejemplo.test")
    client.post("/api/auth/forgot-password", json={"identificador": "rec.vence"})
    token = correos[-1][1].rsplit("/", 1)[1]
    with SessionLocal() as db:
        db.query(PasswordResetModel).update({"expires_at": datetime.now() - timedelta(minutes=1)})
        db.commit()
    assert client.post("/api/auth/reset-password", json={"token": token, "password": "nueva-clave-segura"}).status_code == 400


def test_correo_unico_por_usuario(client, auth):
    _crear_usuario(client, auth, "dup.uno", "duplicado@ejemplo.test")
    r = client.post("/api/admin/users", headers=auth, json={
        "username": "dup.dos", "password": "clave-inicial-1", "role": "flota", "email": "DUPLICADO@ejemplo.test"})
    assert r.status_code == 409


def test_cambiar_contrasena_cierra_sesiones(client, auth):
    u = _crear_usuario(client, auth, "sesion.cierra", None)
    token = _login(client, "sesion.cierra", "clave-inicial-1").json()["access_token"]
    cab = {"Authorization": f"Bearer {token}"}
    assert client.get("/api/auth/me", headers=cab).status_code == 200
    assert client.patch(f"/api/admin/users/{u['id']}", headers=auth, json={"password": "otra-clave-nueva"}).status_code == 200
    assert client.get("/api/auth/me", headers=cab).status_code == 401


def test_login_se_bloquea_tras_varios_fallos(client, auth, monkeypatch):
    from app import ratelimit

    monkeypatch.setattr(ratelimit.settings, "RATE_LIMIT_ENABLED", True)
    ratelimit.FALLOS_LOGIN.reiniciar()
    _crear_usuario(client, auth, "fuerza.bruta", None)
    for _ in range(ratelimit.FALLOS_LOGIN.maximo):
        assert _login(client, "fuerza.bruta", "incorrecta").status_code == 401
    # ya bloqueado: ni siquiera la contraseña correcta pasa
    assert _login(client, "fuerza.bruta", "clave-inicial-1").status_code == 429
    ratelimit.FALLOS_LOGIN.reiniciar()


def test_usuario_desactivado_recibe_error_generico(client, auth):
    u = _crear_usuario(client, auth, "desactivado", None)
    client.patch(f"/api/admin/users/{u['id']}", headers=auth, json={"is_active": False})
    r = _login(client, "desactivado", "clave-inicial-1")
    assert r.status_code == 401
    assert r.json()["detail"] == _login(client, "desactivado", "mala").json()["detail"]


def test_reporte_publico_limita_prioridad_y_tasa(client, auth, monkeypatch):
    from app import ratelimit

    r = client.post("/api/public/incidents", json={"type": "fire", "priority": 4, **capital(2)})
    assert r.status_code == 201
    assert r.json()["data"]["priority"] == 3  # tope para reportes ciudadanos
    assert len(r.json()["data"]["id"].split("-")) == 4  # INC-AAAAMMDD-NNNN-XXXX (no enumerable)

    monkeypatch.setattr(ratelimit.settings, "RATE_LIMIT_ENABLED", True)
    ratelimit.REPORTES_PUBLICOS.reiniciar()
    codigos = [client.post("/api/public/incidents", json={"type": "medical", "priority": 1, **capital(3)}).status_code
               for _ in range(ratelimit.REPORTES_PUBLICOS.maximo + 1)]
    assert codigos[-1] == 429 and codigos[0] == 201
    ratelimit.REPORTES_PUBLICOS.reiniciar()


def test_busqueda_trata_comodines_como_texto(client, auth):
    r = client.get("/api/admin/incidents", headers=auth, params={"q": "%"})
    assert r.status_code == 200
    assert r.json()["total"] == 0


def test_arranque_falla_en_produccion_con_secretos_de_ejemplo():
    from app.config import Settings

    s = Settings()
    s.DEBUG_MODE = False
    s.JWT_SECRET = "cambie-esta-clave-secreta-en-el-env"
    with pytest.raises(RuntimeError):
        s.validar()
    s.JWT_SECRET = "x" * 48
    s.DEFAULT_ADMIN_PASS = "una-contrasena-larga-y-propia"
    s.SEED_DEMO_DATA = False
    s.validar()  # no lanza

