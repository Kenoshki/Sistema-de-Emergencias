@echo off
REM Inicia el frontend (ejecutar desde la carpeta Incidentes_v2)
cd /d "%~dp0Frontend"
if not exist node_modules call npm install
if not exist .env copy .env.example .env
npm run dev
pause
