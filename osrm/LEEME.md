# Servidor propio de rutas (OSRM)

El botón **Dibujar por carretera** del mapa usa [OSRM](https://project-osrm.org/) para trazar una ruta por las
carreteras reales. Por defecto consulta el servidor público de demostración (`router.project-osrm.org`), que es
gratuito pero limitado: cualquiera lo usa, puede saturarse o rechazar consultas y no garantiza disponibilidad.
Para un uso real hay que montar un servidor propio con el mapa de Guatemala. Así no hay límites de consultas,
los datos no salen de la institución y se puede actualizar el mapa cuando se necesite.

## Opción 1: en una computadora con Windows (desarrollo o presentación)

1. Instale [Docker Desktop](https://www.docker.com/products/docker-desktop/) y ábralo.
2. Ejecute `osrm\iniciar_osrm.bat`. La primera vez:
   - descarga el mapa de Guatemala de [Geofabrik](https://download.geofabrik.de/central-america/guatemala.html)
     (unos 125 MB), y
   - prepara la red vial (varios minutos).

   Los datos se guardan en `%LOCALAPPDATA%\osrm-guatemala`, fuera de OneDrive. Las siguientes veces arranca en segundos.
3. En `Frontend\.env` agregue la línea siguiente y reinicie el frontend:

   ```env
   VITE_OSRM_URL=http://localhost:5000
   ```

4. Para descargar un mapa más reciente: `osrm\iniciar_osrm.bat actualizar`.

Prueba rápida (de la zona 10 a Flores):
<http://localhost:5000/route/v1/driving/-90.506,14.600;-89.883,16.928?overview=false>

## Opción 2: en un servidor (uso nacional)

En un servidor Linux con Docker, los mismos pasos:

```bash
mkdir -p /srv/osrm && cd /srv/osrm
wget https://download.geofabrik.de/central-america/guatemala-latest.osm.pbf
IMG=ghcr.io/project-osrm/osrm-backend:v5.27.1
docker run --rm -v "$PWD:/data" $IMG osrm-extract -p /opt/car.lua /data/guatemala-latest.osm.pbf
docker run --rm -v "$PWD:/data" $IMG osrm-partition /data/guatemala-latest.osrm
docker run --rm -v "$PWD:/data" $IMG osrm-customize /data/guatemala-latest.osrm
docker run -d --restart unless-stopped --name osrm -p 5000:5000 -v "$PWD:/data" $IMG \
  osrm-routed --algorithm mld --max-viaroute-size 500 /data/guatemala-latest.osrm
```

Recomendaciones:

- **Capacidad:** Guatemala es un mapa pequeño. Un servidor de 2 núcleos y 4 GB de RAM responde cientos de
  rutas por segundo. Si crece la demanda, se levantan más copias del contenedor detrás de un balanceador.
- **Acceso:** publíquelo detrás de HTTPS (por ejemplo, Nginx) y apunte `VITE_OSRM_URL` a esa dirección.
- **Actualización:** repita los pasos con un mapa nuevo cada semana o cada mes (por ejemplo, con una tarea
  programada), para incluir carreteras nuevas.

## El fondo del mapa (teselas) también tiene límites

Las imágenes del mapa vienen de `tile.openstreetmap.org`. Su
[política de uso](https://operations.osmfoundation.org/policies/tiles/) permite tráfico ligero, pero no un
sistema de uso nacional. Para eso hay dos caminos:

- **Proveedor comercial** de teselas basadas en OpenStreetMap (por ejemplo MapTiler, Stadia Maps o
  Thunderforest), con una clave de acceso.
- **Servidor de teselas propio** con los mismos datos de Geofabrik.

En ambos casos solo cambia una línea en `Frontend\.env`:

```env
VITE_TILE_URL=https://su-proveedor/{z}/{x}/{y}.png?key=SU_CLAVE
```

Respete siempre la atribución "© OpenStreetMap" que muestra el mapa (licencia ODbL).
