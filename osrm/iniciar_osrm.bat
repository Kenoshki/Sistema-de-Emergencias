@echo off
setlocal
rem ============================================================
rem  Servidor propio de rutas por carretera (OSRM) para Guatemala
rem  Requiere Docker Desktop. La primera vez descarga el mapa de
rem  Guatemala (unos 125 MB) y prepara la red vial (varios minutos).
rem  Luego atiende en http://localhost:5000
rem ============================================================

set IMAGEN=ghcr.io/project-osrm/osrm-backend:v5.27.1
set PBF_URL=https://download.geofabrik.de/central-america/guatemala-latest.osm.pbf
rem Los datos se guardan fuera de OneDrive para no sincronizar cientos de MB.
set DATOS=%LOCALAPPDATA%\osrm-guatemala

where docker >nul 2>nul
if errorlevel 1 (
  echo No se encontro Docker. Instale Docker Desktop: https://www.docker.com/products/docker-desktop/
  pause
  exit /b 1
)

rem El comando docker existe, pero el motor solo funciona con Docker Desktop abierto.
docker info >nul 2>nul
if errorlevel 1 (
  echo Docker Desktop no esta encendido. Intentando abrirlo...
  if exist "%ProgramFiles%\Docker\Docker\Docker Desktop.exe" (
    start "" "%ProgramFiles%\Docker\Docker\Docker Desktop.exe"
  ) else (
    echo No se encontro Docker Desktop. Abralo manualmente desde el menu Inicio.
  )
  echo Esperando a que Docker termine de arrancar ^(puede tardar 1 o 2 minutos^)...
  for /l %%i in (1,1,60) do (
    docker info >nul 2>nul && goto docker_listo
    timeout /t 5 /nobreak >nul
  )
  echo.
  echo Docker no respondio despues de 5 minutos.
  echo Abra Docker Desktop, espere a que diga "Engine running" y vuelva a ejecutar este archivo.
  pause
  exit /b 1
)
:docker_listo

if not exist "%DATOS%" mkdir "%DATOS%"

if "%1"=="actualizar" (
  echo Se descargara de nuevo el mapa y se volvera a preparar la red vial.
  del /q "%DATOS%\*" >nul 2>nul
)

if not exist "%DATOS%\guatemala-latest.osm.pbf" (
  echo Descargando el mapa de Guatemala desde Geofabrik...
  curl -L --fail -o "%DATOS%\guatemala-latest.osm.pbf" %PBF_URL% || goto error
)

if not exist "%DATOS%\listo.txt" (
  echo Preparando la red vial ^(solo la primera vez^)...
  docker run --rm -t -v "%DATOS%:/data" %IMAGEN% osrm-extract -p /opt/car.lua /data/guatemala-latest.osm.pbf || goto error
  docker run --rm -t -v "%DATOS%:/data" %IMAGEN% osrm-partition /data/guatemala-latest.osrm || goto error
  docker run --rm -t -v "%DATOS%:/data" %IMAGEN% osrm-customize /data/guatemala-latest.osrm || goto error
  echo ok> "%DATOS%\listo.txt"
)

echo.
echo Servidor OSRM en http://localhost:5000  ^(Ctrl+C para detenerlo^)
echo En Frontend\.env ponga:  VITE_OSRM_URL=http://localhost:5000
echo.
docker run --rm -t -p 5000:5000 -v "%DATOS%:/data" %IMAGEN% osrm-routed --algorithm mld --max-viaroute-size 500 /data/guatemala-latest.osrm
exit /b 0

:error
echo.
echo Ocurrio un error. Revise el mensaje de arriba.
pause
exit /b 1
