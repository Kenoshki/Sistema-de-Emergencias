# DWG EMS-05 REV A – Sistema Inteligente de Gestión de Emergencias

Plataforma para coordinar ambulancias, bomberos, policía y equipos de rescate en toda Guatemala
(22 departamentos y 340 municipios). Los ciudadanos reportan emergencias y el sistema asigna
**automáticamente** las unidades más cercanas, calculando la ruta más corta sobre la red vial nacional (Dijkstra). Si no hay unidades libres, el incidente
entra a una **cola de prioridad** y se atiende en cuanto se libera una unidad.

**Equipo DWG EMS-05**

- Naomy De León Salguero (3590-23-7248)
- Cristian Lorenzo Hernández de Paz (3590-24-709)
- Kennet Andersson Baten Rojas (3590-25-28916)

---

> **¿Quiere proponer una mejora o reportar un error?** Lea [CONTRIBUTING.md](CONTRIBUTING.md): se trabaja con
> *issues* y *pull requests*, y GitHub ejecuta las pruebas automáticamente en cada propuesta.

## Qué incluye

| Módulo | Qué hace |
|---|---|
| **Portal ciudadano** | Reporte en 4 pasos. La ubicación es obligatoria: departamento → municipio → zona (si el municipio tiene zonas) → aldea o colonia, o GPS con confirmación. Devuelve un código de seguimiento. |
| **Seguimiento** | El ciudadano ve el estado, las unidades asignadas y el tiempo estimado de llegada. Se actualiza solo. |
| **Panel de control** | Indicadores reales (tiempo de respuesta, cumplimiento, flota ocupada, lugar de mayor riesgo), mapa nacional en vivo con vista de la capital, riesgo por departamento y gráficas. |
| **Incidentes** | Lista con filtros y detalle: ruta en el mapa, unidades candidatas, asignación manual, reclasificación, bitácora, llegada, cierre. |
| **Despacho** | Cola de espera ordenada por prioridad efectiva, tablero de flota y generador de simulacros. |
| **Flota** | 99 unidades: capital, área metropolitana y una base por cabecera departamental. Alta, edición, mantenimiento y regreso a base. |
| **Red vial** | Grafo nacional de 361 puntos sobre un mapa de OpenStreetMap. Calculadora de rutas (Dijkstra paso a paso, verificado con NetworkX), trazado opcional por carretera real (OSRM) y cierre de vías por deslaves o bloqueos. |
| **Reportes** | Reporte ejecutivo en PDF (ReportLab) y exportación CSV (Pandas). |
| **Usuarios y permisos** | Perfiles por función (incidentes, flota, red vial) y permisos por módulo que define el administrador. Contraseñas cifradas e inicio de sesión con JWT. |

## Tecnologías

- **Backend:** Python, FastAPI, SQLAlchemy, Pydantic, Pandas, NetworkX, ReportLab, PyJWT, python-dotenv.
- **Frontend:** React 19 + TypeScript, Vite, Tailwind CSS 4, Lucide React, Axios, Leaflet (mapas de OpenStreetMap).
- **Base de datos:** MySQL (también funciona con SQLite para pruebas rápidas).

---

## Instalación en Windows

### Requisitos

- Python 3.11 o superior
- Node.js 20 o superior
- MySQL 8 (MySQL Workbench o XAMPP)

### 1. Base de datos

En MySQL Workbench abra y ejecute `Backend/sql/crear_base_mysql.sql`, o desde la consola:

```bat
mysql -u root -p < Backend\sql\crear_base_mysql.sql
```

(Opcional: el backend también crea la base automáticamente si no existe.) Las tablas, la flota y los datos de ejemplo se crean solos al arrancar el backend.

> Se usa una base nueva (`sysemerg_v2`) porque la versión anterior guardaba sus tablas en `sysemerg` con otras columnas. Así ambas versiones pueden convivir.

### 2. Backend

```bat
cd Backend
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
```

Abra `.env` y ponga su contraseña de MySQL en `DATABASE_URL`:

```env
DATABASE_URL=mysql+pymysql://root:SU_CONTRASEÑA@localhost:3306/sysemerg_v2?charset=utf8mb4
```

> Si la contraseña tiene caracteres especiales (`@`, `#`, `/`, `:`), escríbalos codificados: `@` → `%40`, `#` → `%23`.

Arranque el servidor:

```bat
uvicorn main:app --reload --reload-dir app --port 8000
```

- API: http://localhost:8000
- Documentación interactiva (probar endpoints): http://localhost:8000/docs

### 3. Frontend

En otra terminal:

```bat
cd Frontend
npm install
copy .env.example .env
npm run dev
```

Abra http://localhost:5173

- **Portal ciudadano:** página principal.
- **Centro de despacho:** botón arriba a la derecha. Usuario `admin`, contraseña `1234password` (definidos en el `.env` del backend).
  Para probar los perfiles también se crean `op.incidentes`, `op.flota` y `op.red`, con contraseña `operador2026` (`DEMO_USERS_PASS`).

> También puede usar `iniciar_backend.bat` e `iniciar_frontend.bat` después de la primera instalación.

### 4. Pruebas automáticas

```bat
cd Backend
.venv\Scripts\activate
python -m pytest -v
```

- `tests/test_algoritmos.py`: catálogo geográfico, reglas de ubicación obligatoria, Dijkstra propio contra NetworkX desde los 361 puntos, despacho y cola de prioridad.
- `tests/test_analitica.py`: indicadores, simulación y generación del PDF.
- `tests/test_api.py`: flujo completo de la API con una base SQLite temporal (no toca MySQL), incluidos los permisos de cada perfil.

---

## Estructura

```
Backend/
  main.py                    Aplicación FastAPI (arranque, CORS, manejo de errores)
  app/
    config.py                Variables de entorno
    database.py              Conexión SQLAlchemy
    models.py                Tablas: departments, municipalities, places, users, incidents, resources,
                             assignments, incident_events, road_closures, schema_info
    schemas.py               Validación de entrada (Pydantic), incluida la ubicación obligatoria
    security.py              Contraseñas PBKDF2 + JWT + verificación de permisos por endpoint
    permisos.py              Perfiles (roles) y permisos por módulo
    catalogos.py             Tipos, zonas de la capital y reglas de unidades por incidente
    geografia.py             Departamentos, municipios, zonas, nodos de la red y localización por GPS
    datos/geografia_gt.json  22 departamentos y 340 municipios con coordenadas
    algoritmos/
      grafo.py               Red vial nacional (k vecinos + árbol de expansión mínima de Prim), Dijkstra + NetworkX
      despacho.py            Asignación voraz de unidades más cercanas
      cola_prioridad.py      Montículo con envejecimiento (anti-inanición)
    servicios/
      operaciones.py         Ciclo de vida del incidente (crear, despachar, llegada, resolver, cola)
      analitica.py           Indicadores con Pandas
      reportes.py            PDF con ReportLab
      serializadores.py      Respuestas JSON
    routers/                 Endpoints por módulo
    seed.py / simulacion.py  Datos iniciales e historial simulado
  scripts/
    importar_lugares.py      Carga aldeas, caseríos y colonias desde un CSV
    generar_geografia.py     Regenera el catálogo de municipios desde el shapefile del Banco Mundial
    fuentes/                 Lista oficial de municipios y plantilla CSV de lugares
  sql/crear_base_mysql.sql
  tests/
Frontend/
  src/
    lib/                     API, sesión, enrutador, tipos, formatos
    components/              Mapa de la red, selector de ubicación en cascada, gráficas, controles
    pages/public/            Portal ciudadano y seguimiento
    pages/admin/             Panel, incidentes, despacho, flota, red vial, reportes, usuarios
osrm/                        Servidor propio de rutas por carretera (Docker)
DOCUMENTACION_ALGORITMOS.md  Explicación de los algoritmos para la presentación
```

## Ubicación: departamentos, municipios, zonas y aldeas

- **Catálogo incluido:** 22 departamentos y 340 municipios con las coordenadas de su cabecera.
  Coordenadas del Banco Mundial, *Guatemala – Municipalities head offices* (CC BY 4.0). Nueve
  municipios creados después de 2017 usan coordenadas aproximadas (campo `approximate`).
- **Zonas:** la zona es obligatoria en los municipios divididos en zonas. La Ciudad de Guatemala
  usa sus 22 zonas oficiales (no existen la 20, 22 ni 23). También están configurados Mixco (1–11),
  Villa Nueva (1–14) y Quetzaltenango (1–11). **Verifique esos rangos** con cada municipalidad y
  ajústelos en `ZONAS_POR_MUNICIPIO` (`Backend/app/geografia.py`).
- **Reglas que valida el backend:** departamento obligatorio, municipio obligatorio y del mismo
  departamento, y zona obligatoria y válida cuando aplica. Si solo llega GPS, debe estar dentro de
  Guatemala y el sistema deduce el municipio. El formulario aplica las mismas reglas antes de enviar.
- **Aldeas, caseríos y colonias:** son miles, así que se cargan desde un CSV
  (por ejemplo, el listado de lugares poblados del Censo 2018 del INE). Mientras no haya catálogo,
  el ciudadano puede escribir el nombre.

  ```bat
  cd Backend
  .venv\Scripts\activate
  python scripts\importar_lugares.py C:\ruta\lugares.csv
  ```

  Columnas: `departamento`, `municipio`, `nombre` y, opcionales, `categoria`, `latitud` y `longitud`.
  Vea `scripts/fuentes/plantilla_lugares.csv`. El municipio se busca por nombre.

> **Cambio de esquema:** al arrancar, si la base tiene tablas de la versión anterior (solo con zonas),
> el backend las vuelve a crear con las columnas nuevas. Se conservan los usuarios. Los incidentes y la
> flota de demostración se generan de nuevo.

## Usuarios, perfiles y permisos

Cada usuario tiene, para cada módulo, un nivel: **sin acceso**, **ver** o **editar**. El perfil fija los
niveles iniciales y el administrador puede ajustar cualquier módulo de cualquier usuario en
**Usuarios y permisos**.

| Perfil | Panel | Incidentes | Despacho | Flota | Red vial | Reportes |
|---|---|---|---|---|---|---|
| Administrador (además gestiona usuarios) | Ver | Editar | Editar | Editar | Editar | Ver |
| Operador de incidentes | Ver | **Editar** | **Editar** | Ver | Ver | Ver |
| Operador de flota | Ver | Ver | Ver | **Editar** | Ver | Ver |
| Operador de red vial | Ver | Ver | Sin acceso | Ver | **Editar** | Ver |
| Operador general (centros pequeños) | Ver | Editar | Editar | Editar | Editar | Ver |

- **Incidentes (editar):** registrar, reclasificar, asignar unidades, marcar llegada, resolver y cancelar.
- **Despacho (editar):** procesar la cola de espera y generar simulacros.
- **Flota (editar):** alta, edición, mantenimiento, regreso a base y baja de unidades.
- **Red vial (editar):** cerrar y reabrir vías.

El backend valida el permiso en cada endpoint (responde 403 si falta) y el frontend oculta los
módulos y botones que el usuario no puede usar. Los cambios de permisos se aplican de inmediato.
Los perfiles están en `Backend/app/permisos.py`.

> Al actualizar desde una versión anterior, el backend agrega la columna `users.permissions`. Los
> usuarios que eran "operador" pasan al perfil **Operador general**, con los mismos permisos que tenían.

## Mapas (OpenStreetMap)

- El panel, el detalle del incidente y la red vial muestran el grafo sobre un mapa de
  **OpenStreetMap** con **Leaflet**. Arriba a la derecha del mapa se elige el fondo:
  - **Mapa:** OpenStreetMap. Necesita internet.
  - **Esquema:** el dibujo propio del grafo. Funciona sin internet (útil si falla la red durante la presentación).
- Los puntos y las líneas son los nodos y aristas del grafo: las rutas las sigue calculando Dijkstra.
  OpenStreetMap solo aporta el fondo (calles, ríos, nombres).
- **Dibujar por carretera (OSRM):** con una ruta en pantalla, esta casilla consulta el servidor público de
  [OSRM](https://project-osrm.org/) para trazar la ruta por las carreteras reales, pasando por los mismos
  puntos que eligió Dijkstra, y compara su distancia con la del modelo.
- Las teselas son de `tile.openstreetmap.org` (© colaboradores de OpenStreetMap, ODbL).

### Uso a nivel nacional

El servidor público de OSRM y las teselas de `tile.openstreetmap.org` son de demostración: se saturan y no
admiten el tráfico de un sistema nacional. Ambos se cambian en `Frontend/.env`, sin tocar el código:

| Variable | Para qué sirve |
|---|---|
| `VITE_OSRM_URL` | Servidor OSRM propio, por ejemplo `http://localhost:5000`. Vacía = demostración. |
| `VITE_TILE_URL` | Proveedor o servidor de teselas, con `{z}/{x}/{y}`. Vacía = tile.openstreetmap.org. |

`osrm/iniciar_osrm.bat` monta un OSRM propio con el mapa de Guatemala usando Docker. `osrm/LEEME.md`
explica cómo instalarlo en un servidor y qué opciones hay para las teselas.

## Variables del backend (`.env`)

| Variable | Para qué sirve |
|---|---|
| `DATABASE_URL` | Conexión a MySQL (o `sqlite:///./emergencias.db`) |
| `DEFAULT_ADMIN_USER` / `DEFAULT_ADMIN_PASS` | Administrador que se crea la primera vez |
| `JWT_SECRET` | Clave para firmar las sesiones; cámbiela |
| `CORS_ORIGINS` | Direcciones del frontend permitidas |
| `AUTO_DISPATCH` | `True` para asignar unidades automáticamente al recibir un reporte |
| `SEED_DEMO_DATA` | `True` para cargar 60 días de historial simulado y los operadores de demostración |
| `DEMO_USERS_PASS` | Contraseña de los operadores de demostración (`op.incidentes`, `op.flota`, `op.red`) |

## Problemas comunes

| Síntoma | Solución |
|---|---|
| `Access denied for user 'root'` | Contraseña incorrecta en `DATABASE_URL`. |
| `Unknown database 'sysemerg_v2'` | Ejecute `sql/crear_base_mysql.sql`. |
| `cryptography package is required` | `pip install cryptography` (ya está en requirements.txt). |
| El frontend dice "No hay conexión con el servidor" | El backend no está encendido o `VITE_API_URL` apunta a otro puerto. |
| Error de CORS en la consola del navegador | Agregue la dirección del frontend a `CORS_ORIGINS` y reinicie el backend. |
| Quiero empezar de cero | `DROP DATABASE sysemerg_v2;`, vuelva a ejecutar el script SQL y reinicie el backend. |
