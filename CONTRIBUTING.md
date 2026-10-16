# Cómo colaborar

Guía para que el equipo revise el sistema y proponga mejoras sin pisarse el trabajo.

## Reglas del equipo

1. **Nadie sube cambios directo a `main`.** Cada cambio va en una rama y entra por *pull request* (PR).
2. **Cada PR lo revisa al menos otra persona** del equipo antes de unirlo.
3. **Las pruebas deben pasar.** GitHub las ejecuta solo en cada PR (pestaña *Actions*); si hay una ✗ roja, se corrige antes de unir.
4. **Nunca se sube el archivo `.env`** (tiene la contraseña de MySQL). Si agrega una variable nueva, añádala a `.env.example`.

## ¿Tiene una idea o encontró un error?

Abra un **Issue** (pestaña *Issues* → *New issue*) y elija la plantilla:

- **Propuesta de mejora:** qué cambiaría y por qué.
- **Reporte de error:** qué hizo, qué esperaba y qué pasó.

Así queda registrado y el equipo puede comentar antes de programar.

## Flujo para proponer un cambio

```bat
:: 1. Traer lo último de main
git checkout main
git pull

:: 2. Crear una rama con un nombre descriptivo
git checkout -b mejora/filtro-por-fecha

:: 3. Programar y probar (vea abajo)

:: 4. Guardar y subir la rama
git add .
git commit -m "Agrega filtro por fecha en la lista de incidentes"
git push -u origin mejora/filtro-por-fecha
```

5. En GitHub aparece el botón **Compare & pull request**. Describa el cambio (la plantilla lo guía),
   enlace el issue (`Cierra #12`) y asigne a un compañero como revisor.
6. El revisor comenta en las líneas del código, aprueba o pide cambios. Para corregir, haga más
   commits en la misma rama: el PR se actualiza solo.
7. Con la aprobación y las pruebas en verde, se pulsa **Merge**.

Nombres de rama sugeridos: `mejora/...`, `error/...`, `docs/...`.

## Probar antes de subir

```bat
:: Backend (desde la carpeta Backend, con el entorno virtual activo)
python -m pytest -q

:: Frontend (desde la carpeta Frontend)
npm run build
```

## Dónde está cada cosa

- Algoritmos (Dijkstra, despacho voraz, cola de prioridad): `Backend/app/algoritmos/` y `DOCUMENTACION_ALGORITMOS.md`.
- Endpoints de la API: `Backend/app/routers/`. Documentación interactiva en http://localhost:8000/docs.
- Perfiles y permisos por módulo: `Backend/app/permisos.py`.
- Pantallas: `Frontend/src/pages/`. Componentes compartidos: `Frontend/src/components/`.
