# Despliegue en Railway

Se crean **3 servicios** en un mismo proyecto de Railway: **MySQL**, **Backend** y **Frontend**.
El repositorio ya trae `railway.json` en `Backend/` y `Frontend/`.

## 1. Base de datos
1. En el proyecto: **New → Database → MySQL**.
2. No hace falta ejecutar `crear_base_mysql.sql`: Railway ya crea la base y el backend crea las tablas al arrancar.

## 2. Backend
1. **New → GitHub Repo →** este repositorio. En **Settings → Root Directory** escriba `Backend`.
2. En **Variables** agregue (use *Reference* para la base de datos):

| Variable | Valor |
|---|---|
| `DATABASE_URL` | `${{MySQL.MYSQL_URL}}` (el backend convierte `mysql://` en `mysql+pymysql://`) |
| `JWT_SECRET` | cadena aleatoria de 32+ caracteres: `python -c "import secrets; print(secrets.token_urlsafe(48))"` |
| `DEFAULT_ADMIN_USER` | `admin` (o el que prefiera) |
| `DEFAULT_ADMIN_PASS` | contraseña propia de 10+ caracteres (solo se usa al crear el admin la primera vez) |
| `DEFAULT_ADMIN_EMAIL` | correo real del administrador (lo usa «¿Olvidó su contraseña?») |
| `CORS_ORIGINS` | URL pública del frontend, sin `/` final: `https://su-frontend.up.railway.app` |
| `FRONTEND_URL` | la misma URL del frontend (va en el enlace del correo) |
| `DEBUG_MODE` | `False` (o no la defina) |
| `SEED_DEMO_DATA` | `False` en producción real; `True` solo para una demostración (y defina `DEMO_USERS_PASS`) |
| `MAIL_FROM` | `Emergencias <no-reply@su-dominio.com>` |
| `RESEND_API_KEY` | clave de [Resend](https://resend.com) (ver más abajo) |

3. **Settings → Networking → Generate Domain** para obtener la URL pública del backend.
4. Con `DEBUG_MODE=False` el backend **no arranca** si `JWT_SECRET` o `DEFAULT_ADMIN_PASS` son los de ejemplo: es intencional.
   Compruebe `https://su-backend.up.railway.app/api/health`.

> Mantenga **una sola réplica** del backend: el límite anti-abuso (login, reportes públicos) vive en memoria del proceso.

## 3. Frontend
1. **New → GitHub Repo →** el mismo repositorio, **Root Directory** `Frontend` (usa el `Dockerfile` con nginx).
2. Variable (se incrusta al compilar, así que defínala **antes** del primer despliegue o vuelva a desplegar):
   - `VITE_API_URL` = `https://su-backend.up.railway.app/api`
   - `VITE_OSRM_URL` = servidor OSRM propio (vea `osrm/LEEME.md`); vacío usa el público de demostración.
3. **Generate Domain**, copie la URL y colóquela en `CORS_ORIGINS` y `FRONTEND_URL` del backend.

## 4. Correo para «¿Olvidó su contraseña?»
Railway **bloquea SMTP** en los planes Free/Hobby, por eso el backend usa por defecto la API HTTPS de **Resend**:
1. Cree cuenta en Resend, verifique su dominio y genere una *API key* → `RESEND_API_KEY`.
2. `MAIL_FROM` debe usar ese dominio verificado.
3. Alternativa en planes de pago: `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASSWORD`.

Sin proveedor configurado el enlace **no se envía** (queda un aviso en los logs). Un administrador siempre puede
restablecer una contraseña desde *Usuarios y permisos*.

## 5. Después del primer despliegue
- Inicie sesión con el administrador y cambie la contraseña desde *Usuarios y permisos*.
- Pruebe «¿Olvidó su contraseña?» con su propio correo.
- Revise que `/docs` responda 404 (la documentación interactiva se oculta en producción; `ENABLE_DOCS=true` la activa).
- Haga copias de seguridad del MySQL (Railway: pestaña *Backups*).

## Cargar datos de muestra (100 incidentes y 3 usuarios)
1. En las variables del **backend** agregue `CARGAR_MUESTRA=True` y `MUESTRA_PASS=<contraseña propia de 10+ caracteres>`.
2. Espere a que se despliegue. Se crean 100 incidentes recientes (con unidades y bitácora) y 3 usuarios:
   `muestra.incidentes` (perfil incidentes), `muestra.flota` (perfil flota) y `muestra.red` (perfil red vial), todos con `MUESTRA_PASS`.
3. **Quite `CARGAR_MUESTRA`** (los datos quedan guardados). Si se deja, no duplica nada: detecta que la muestra ya existe.

También se puede cargar desde su computadora: `python scripts/cargar_muestra.py` con `DATABASE_URL` apuntando a la base.

## Actualizar un esquema anterior
Si una base existente tiene un esquema viejo, el backend se detiene en lugar de borrar datos. Haga una copia de seguridad
y arranque una vez con `RESET_SCHEMA=true` (se pierden incidentes y flota; los usuarios se conservan), luego quite la variable.
