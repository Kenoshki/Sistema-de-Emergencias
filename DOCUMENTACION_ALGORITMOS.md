# Algoritmos del sistema – DWG EMS-05 REV A

Este documento explica los algoritmos que usa el sistema, dónde están en el código y cómo se comprueba que
funcionan. Sirve como guía para la presentación del curso.

---

## 1. Modelo: Guatemala como grafo ponderado

**Archivos:** `Backend/app/geografia.py`, `Backend/app/algoritmos/grafo.py`

- **Nodos (V = 361):** las 22 zonas de la Ciudad de Guatemala (1–19, 21, 24 y 25) y los otros
  339 municipios del país (un nodo por cabecera municipal). El municipio de Guatemala no tiene nodo
  propio: lo representan sus zonas. Los nodos se numeran 1–25 para zonas y con el código de municipio
  para el resto (Mixco = 106, Quetzaltenango = 901).
- **Aristas (E = 901):** el grafo es **no dirigido** y se construye así:
  1. **Capital:** 45 conexiones entre zonas vecinas, definidas a mano.
  2. **K vecinos más cercanos (K = 4):** cada municipio se une con sus 4 municipios más cercanos.
  3. **Árbol de expansión mínima (Prim):** garantiza que todo el país quede conectado aunque un
     municipio quede lejos de sus vecinos (por ejemplo, en Petén).
  4. **Enlace con la capital:** cada municipio vecino de la capital se une a las 2 zonas más cercanas.
- **Peso:** distancia estimada por carretera, en km:

```
peso(a, b) = haversine(a, b) × 1.35   dentro de la capital
peso(a, b) = haversine(a, b) × 1.45   entre municipios (curvas y montaña)
```

`haversine` da la distancia en línea recta sobre la Tierra; el factor de tortuosidad compensa que las
carreteras no son rectas. Con este modelo, de la zona 10 a Quetzaltenango hay unos 170 km y a Flores
486 km, cerca de las distancias reales por carretera.

### Árbol de expansión mínima con Prim

```
en_árbol = {primer punto}
mejor[v] = distancia(primer punto, v) para todos los demás
mientras queden puntos fuera:
    u = punto fuera del árbol con menor mejor[u]
    agregar arista (padre[u], u) y meter u al árbol
    para cada punto v fuera: si distancia(u, v) < mejor[v], actualizar mejor[v] y padre[v]
```

Con arreglo de mínimos la complejidad es O(V²), adecuada para un grafo completo (denso) de 340 puntos.

Se guarda como **lista de adyacencia** (`dict[zona, dict[vecino, peso]]`), que ocupa O(V + E) memoria.

**Vías cerradas:** al cerrar una vía (deslave, inundación), se reconstruye el grafo sin esa arista. Todas las rutas nuevas
la evitan automáticamente. Si una zona queda aislada, su distancia es ∞ y ninguna unidad puede asignarse hasta reabrir la vía.

---

## 2. Ruta más corta: Dijkstra

**Archivo:** `Backend/app/algoritmos/grafo.py` → `RedVial.dijkstra()`

Implementación propia con un **montículo binario** (`heapq`):

```
dist[v] = ∞ para todo v;  dist[origen] = 0
cola = [(0, origen)]
mientras cola no esté vacía:
    (d, u) = extraer_mínimo(cola)
    si u ya fue visitado: continuar          # entrada obsoleta
    marcar u como visitado
    para cada vecino v de u con peso w:
        si d + w < dist[v]:                  # relajación
            dist[v] = d + w
            previo[v] = u
            insertar(cola, (dist[v], v))
```

El camino se reconstruye siguiendo `previo[]` desde el destino hasta el origen.

- **Complejidad:** O((V + E) log V) tiempo, O(V) memoria adicional.
- **Por qué funciona:** todos los pesos son positivos (distancias), así que cuando un nodo sale de la cola su distancia ya es definitiva.

**Verificación:** el mismo cálculo se hace con NetworkX. La prueba
`test_dijkstra_propio_coincide_con_networkx` ejecuta Dijkstra desde **cada uno de los 361 nodos** y compara
las distancias a todos los destinos (cerca de 130,000 pares) con las de NetworkX.
En la pantalla **Red vial** se muestra el resultado de ambos y el orden en que Dijkstra fijó cada zona.

---

## 3. Asignación automática de unidades (algoritmo voraz)

**Archivo:** `Backend/app/algoritmos/despacho.py` → `planificar_despacho()`

### Reglas: qué necesita cada incidente

`catalogos.requerimientos(tipo, prioridad)` define las unidades. Ejemplos:

| Incidente | Prioridad 1–2 | Prioridad 3 | Prioridad 4 |
|---|---|---|---|
| Incendio | 1 Bomberos | 2 Bomberos + 1 Ambulancia | 2 Bomberos + 1 Ambulancia |
| Accidente | 1 Ambulancia + 1 Policía | igual | 2 Ambulancias + 1 Policía + 1 Rescate |
| Colapso / sismo | 1 Rescate + 1 Ambulancia | 2 Rescate + 1 Ambulancia + 1 Bomberos | igual |
| Robo / asalto | 1 Policía | 2 Policías | 2 Policías + 1 Ambulancia |

### Pasos

1. Se ejecuta Dijkstra **una sola vez** desde la zona del incidente. Como el grafo es no dirigido,
   `dist(incidente → X) = dist(X → incidente)`, así que se obtiene la distancia de **todas** las unidades con un solo recorrido.
2. Para cada tipo requerido se ordenan las unidades disponibles por `(distancia, código)`.
3. Se eligen las N más cercanas (elección voraz).
4. El tiempo estimado de llegada es:

```
ETA (min) = 1.5 min de alistamiento + distancia / velocidad × 60
```

   Los primeros 15 km se recorren a velocidad urbana según el tipo de unidad (ambulancia 45 km/h,
   policía 50, bomberos 38, rescate 40); el resto, en carretera a 60 km/h. En prioridad crítica ambas
   velocidades aumentan 15 %.
5. Si faltan unidades de algún tipo, se registran como **faltantes** y el incidente entra a la cola de prioridad.

- **Complejidad:** O((V + E) log V + R log R), con R = número de unidades.
- **Concurrencia:** al leer las unidades libres se usa `SELECT … FOR UPDATE` en MySQL, para que dos despachos simultáneos no tomen la misma unidad.
- **Por qué voraz:** en emergencias se prioriza la respuesta inmediata al incidente que llega. Una asignación óptima global
  (por ejemplo, el algoritmo húngaro) requeriría conocer los incidentes futuros. Es una buena línea de mejora para discutir.

La pantalla de detalle del incidente muestra el **ranking** de unidades candidatas que produce este algoritmo, y permite
asignar manualmente otra unidad si el operador lo decide.

---

## 4. Ubicación obligatoria y localización por GPS

**Archivos:** `Backend/app/geografia.py` (`validar_ubicacion`, `localizar`), `Backend/app/schemas.py`

- Sin GPS, la ubicación se elige en cascada: departamento → municipio → zona (si el municipio se
  divide en zonas) → aldea o colonia. El backend rechaza un municipio que no pertenece al
  departamento, una zona que no existe y la falta de zona donde es obligatoria.
- Con GPS se busca el **nodo más cercano** (búsqueda lineal, O(V)): una zona de la capital o una cabecera
  municipal. Es una aproximación, porque un punto puede estar más cerca de la cabecera vecina que de la
  suya. Por eso el formulario muestra el lugar detectado y pide confirmarlo o corregirlo.

## 5. Cola de prioridad con envejecimiento

**Archivo:** `Backend/app/algoritmos/cola_prioridad.py` → `ColaIncidentes`

Cuando no hay unidades suficientes, los incidentes esperan en un **montículo binario**. Cada vez que se libera una unidad
(al resolver o cancelar un incidente, al reabrir una vía o al agregar una unidad), `operaciones.procesar_cola()` extrae los
incidentes en orden y vuelve a ejecutar el despacho para cada uno.

**Orden:**

```
prioridad_efectiva = prioridad + min(1, minutos_esperando / 30)
clave del montículo = (−prioridad_efectiva, hora_de_reporte, contador)
```

- `heapq` es un montículo de mínimos, por eso se niega la prioridad.
- A igual prioridad efectiva, se atiende primero al que reportó antes (FIFO).
- El contador garantiza un desempate estable.

**Envejecimiento (aging):** cada 30 minutos de espera se suma 1 punto, con un máximo de +1. Esto evita la **inanición**:
un incidente de prioridad baja que espera mucho termina alcanzando al siguiente nivel, pero nunca supera a uno crítico
reciente (el bono máximo es 1).

- **Complejidad:** insertar O(log n), extraer O(log n), consultar el tope O(1).

Se ve en la pantalla **Despacho**: posición, prioridad original, prioridad efectiva y minutos de espera.

---

## 6. Analítica (Pandas)

**Archivo:** `Backend/app/servicios/analitica.py`

| Indicador | Cálculo |
|---|---|
| Tiempo de respuesta | `llegada − reporte`, promedio y percentil 90 |
| Tiempo de despacho | `primera asignación − reporte` |
| Cumplimiento | % de incidentes cuya respuesta fue ≤ tiempo objetivo (P4: 7 min, P3: 9, P2: 12, P1: 15) |
| Índice de riesgo por lugar y por departamento | Σ pesos por prioridad (crítico 8, alto 4, medio 2, bajo 1) |
| Utilización de flota | unidades ocupadas / (total − en mantenimiento) |
| Variación | Cada indicador se compara con el periodo anterior de igual duración |

También calcula series por día, por tipo, por hora del día y por prioridad para las gráficas del panel.

---

## 7. Datos de demostración

**Archivo:** `Backend/app/simulacion.py`

Si `SEED_DEMO_DATA=True` y la base está vacía, se generan unos 420 incidentes de los últimos 60 días en
todo el país, aproximadamente la mitad en la capital. Cada uno se despacha
con **el mismo algoritmo** del sistema (Dijkstra + voraz), y la llegada se calcula a partir del ETA con un factor de tráfico
aleatorio. La semilla es fija, así que los datos son reproducibles. Los últimos 30 días tienen tiempos un poco mejores para
que el panel muestre una tendencia.

---

## Resumen de complejidades

| Algoritmo | Estructura | Tiempo |
|---|---|---|
| Construcción de la red | K vecinos + Prim | O(V² log V) una sola vez al arrancar |
| Dijkstra | Montículo binario + lista de adyacencia | O((V + E) log V) |
| Despacho voraz | Dijkstra + ordenamiento | O((V + E) log V + R log R) |
| Cola de espera | Montículo binario | O(log n) por operación |
| Lugar más cercano a una coordenada GPS | Búsqueda lineal | O(V) |
