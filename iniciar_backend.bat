@echo off
REM Inicia el backend (ejecutar desde la carpeta Incidentes_v2)
cd /d "%~dp0Backend"
if not exist .env (
  copy .env.example .env >nul
  echo.
  echo Se creo Backend\.env. Escriba su contrasena de MySQL en DATABASE_URL,
  echo guarde el archivo y vuelva a ejecutar este script.
  notepad .env
  pause
  exit /b
)
findstr /c:"tu_password" .env >/dev/null && (
  echo.
  echo Backend\.env todavia tiene "tu_password". Cambielo por su contrasena de MySQL.
  notepad .env
  pause
  exit /b
)
if not exist .venv (
  echo Creando entorno virtual e instalando dependencias...
  python -m venv .venv
  call .venv\Scripts\activate
  pip install -r requirements.txt
) else (
  call .venv\Scripts\activate
)
uvicorn main:app --reload --reload-dir app --port 8000
pause
