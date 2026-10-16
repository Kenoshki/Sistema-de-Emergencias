"""
Pruebas de los algoritmos y de la geografía (no requieren base de datos ni servidor).

Ejecutar desde la carpeta Backend:
    python -m pytest tests/test_algoritmos.py -v
o sin pytest:
    python -m unittest tests.test_algoritmos -v
"""
import unittest
from datetime import datetime, timedelta

import networkx as nx

from app.algoritmos.cola_prioridad import ColaIncidentes, prioridad_efectiva
from app.algoritmos.despacho import RecursoDisponible, estimar_eta_min, planificar_despacho, restar_necesidades
from app.algoritmos.grafo import INFINITO, RedVial, arbol_expansion_minima_prim, conexiones_base, distancia_interna
from app.catalogos import DISTANCIA_INTRAMUNICIPAL_KM, DISTANCIA_INTRAZONA_KM, ZONAS_CAPITAL, requerimientos
from app.geografia import (
    DEPARTAMENTOS,
    MUNICIPIOS,
    localizar,
    nodo_de,
    nodos,
    validar_ubicacion,
    zonas_de,
)

MIXCO = next(c for c, m in MUNICIPIOS.items() if m["nombre"] == "Mixco")
XELA = next(c for c, m in MUNICIPIOS.items() if m["nombre"] == "Quetzaltenango")
FLORES = next(c for c, m in MUNICIPIOS.items() if m["nombre"] == "Flores")
COBAN = next(c for c, m in MUNICIPIOS.items() if m["nombre"] == "Cobán")


class TestGeografia(unittest.TestCase):
    def test_catalogo_completo(self):
        self.assertEqual(len(DEPARTAMENTOS), 22)
        self.assertEqual(len(MUNICIPIOS), 340)
        for d in DEPARTAMENTOS:
            cabeceras = [m for m in MUNICIPIOS.values() if m["departamento"] == d and m["cabecera_departamental"]]
            self.assertEqual(len(cabeceras), 1, d)

    def test_coordenadas_dentro_de_guatemala(self):
        for m in MUNICIPIOS.values():
            self.assertTrue(13.6 <= m["lat"] <= 17.9 and -92.35 <= m["lon"] <= -88.15, m["nombre"])

    def test_nodos(self):
        # 22 zonas de la capital + 339 municipios (la capital se representa por sus zonas)
        self.assertEqual(len(nodos()), 22 + 339)
        self.assertEqual(nodo_de("0101", 10), 10)
        self.assertEqual(nodo_de(MIXCO, 3), int(MIXCO))

    def test_zona_obligatoria_en_la_capital(self):
        with self.assertRaises(ValueError):
            validar_ubicacion("01", "0101", None)
        with self.assertRaises(ValueError):
            validar_ubicacion("01", "0101", 20)  # la zona 20 no existe
        self.assertEqual(validar_ubicacion("01", "0101", 10), ("01", "0101", 10))

    def test_zona_obligatoria_en_municipios_con_zonas(self):
        self.assertIsNotNone(zonas_de(MIXCO))
        with self.assertRaises(ValueError):
            validar_ubicacion("01", MIXCO, None)

    def test_zona_se_ignora_si_el_municipio_no_tiene_zonas(self):
        self.assertEqual(validar_ubicacion("16", COBAN, 5), ("16", COBAN, None))

    def test_municipio_debe_pertenecer_al_departamento(self):
        with self.assertRaises(ValueError):
            validar_ubicacion("09", "0101", 10)

    def test_localizar_por_gps(self):
        z13 = ZONAS_CAPITAL[13]
        p = localizar(z13["lat"], z13["lon"])
        self.assertEqual((p["municipio"], p["zona"]), ("0101", 13))
        x = MUNICIPIOS[XELA]
        self.assertEqual(localizar(x["lat"] + 0.002, x["lon"])["municipio"], XELA)
        self.assertFalse(localizar(19.43, -99.13)["dentro"])  # Ciudad de México


class TestGrafo(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.red = RedVial()

    def test_red_nacional_conexa(self):
        self.assertTrue(self.red.es_conexo())

    def test_prim_genera_arbol(self):
        puntos = {i: (14.0 + i * 0.1, -90.0 + (i % 3) * 0.1) for i in range(8)}
        aristas = arbol_expansion_minima_prim(puntos)
        g = nx.Graph(aristas)
        self.assertEqual(len(aristas), len(puntos) - 1)
        self.assertTrue(nx.is_tree(g))

    def test_dijkstra_propio_coincide_con_networkx(self):
        """Desde CADA nodo, las distancias propias = NetworkX para todos los destinos."""
        for origen in nodos():
            propio = self.red.dijkstra(origen).distancias
            ref = nx.single_source_dijkstra_path_length(self.red.grafo_nx, origen, weight="weight")
            for destino, d in ref.items():
                self.assertAlmostEqual(propio[destino], d, places=1, msg=f"{origen}->{destino}")

    def test_camino_es_valido(self):
        distancia, camino = self.red.ruta(19, int(FLORES))
        suma = sum(self.red.adyacencia[x][y] for x, y in zip(camino, camino[1:]))
        self.assertAlmostEqual(suma, distancia, places=1)
        self.assertEqual((camino[0], camino[-1]), (19, int(FLORES)))

    def test_distancias_razonables(self):
        # Por carretera: capital - Xela ~200 km, capital - Flores ~500 km
        self.assertTrue(140 < self.red.ruta(10, int(XELA))[0] < 260)
        self.assertTrue(400 < self.red.ruta(10, int(FLORES))[0] < 620)

    def test_mismo_nodo(self):
        self.assertEqual(self.red.ruta(10, 10), (DISTANCIA_INTRAZONA_KM, [10]))
        self.assertEqual(self.red.ruta(int(COBAN), int(COBAN))[0], DISTANCIA_INTRAMUNICIPAL_KM)

    def test_cerrar_via_cambia_ruta(self):
        d_normal, camino_normal = self.red.ruta(1, 2)
        self.assertEqual(camino_normal, [1, 2])
        red_cerrada = RedVial(vias_cerradas={(2, 1)})
        d_cerrada, camino_cerrado = red_cerrada.ruta(1, 2)
        self.assertGreater(d_cerrada, d_normal)
        self.assertNotEqual(camino_cerrado, [1, 2])

    def test_nodo_aislado(self):
        vecinos = {(a, b) for a, b in conexiones_base() if int(FLORES) in (a, b)}
        red = RedVial(vias_cerradas=vecinos)
        distancia, camino = red.ruta(1, int(FLORES))
        self.assertEqual(distancia, INFINITO)
        self.assertEqual(camino, [])


class TestDespacho(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.red = RedVial()

    def setUp(self):
        self.recursos = [
            RecursoDisponible("AMB-01", "ambulance", 1),
            RecursoDisponible("AMB-02", "ambulance", 13),
            RecursoDisponible("AMB-QZ", "ambulance", int(XELA)),
            RecursoDisponible("BOM-01", "firefighters", 4),
            RecursoDisponible("POL-01", "police", 10),
        ]

    def test_elige_la_unidad_mas_cercana(self):
        plan = planificar_despacho(14, 2, {"ambulance": 1}, self.recursos, self.red)
        self.assertEqual([c.codigo for c in plan.asignaciones], ["AMB-02"])

    def test_en_el_interior_elige_la_base_departamental(self):
        plan = planificar_despacho(int(XELA), 3, {"ambulance": 1}, self.recursos, self.red)
        self.assertEqual(plan.asignaciones[0].codigo, "AMB-QZ")
        self.assertEqual(plan.asignaciones[0].distancia_km, distancia_interna(int(XELA)))

    def test_ranking_ordenado_por_distancia(self):
        plan = planificar_despacho(14, 2, {"ambulance": 1}, self.recursos, self.red)
        distancias = [c.distancia_km for c in plan.ranking["ambulance"]]
        self.assertEqual(distancias, sorted(distancias))
        self.assertEqual(len(distancias), 3)

    def test_ruta_va_de_la_unidad_al_incidente(self):
        plan = planificar_despacho(14, 2, {"ambulance": 1}, self.recursos, self.red)
        ruta = plan.asignaciones[0].ruta
        self.assertEqual((ruta[0], ruta[-1]), (13, 14))

    def test_registra_faltantes(self):
        plan = planificar_despacho(5, 4, {"police": 2, "rescue": 1}, self.recursos, self.red)
        self.assertEqual(len(plan.asignaciones), 1)
        self.assertEqual(plan.faltantes, {"police": 1, "rescue": 1})

    def test_eta_carretera_mas_rapida_que_urbana(self):
        # 100 km no tardan 100/45 h: después de 15 km se va en carretera a 60 km/h
        self.assertLess(estimar_eta_min(100, "ambulance", 2), 1.5 + 100 / 45 * 60)
        self.assertLess(estimar_eta_min(10, "ambulance", 4), estimar_eta_min(10, "ambulance", 2))

    def test_requerimientos(self):
        self.assertEqual(requerimientos("fire", 4), {"firefighters": 2, "ambulance": 1})
        self.assertEqual(requerimientos("medical", 3), {"ambulance": 1})

    def test_restar_necesidades(self):
        self.assertEqual(restar_necesidades({"police": 2, "ambulance": 1}, {"police": 1, "ambulance": 1}), {"police": 1})


class TestColaPrioridad(unittest.TestCase):
    def test_orden_por_prioridad_y_llegada(self):
        ahora = datetime(2026, 10, 1, 12, 0)
        cola = ColaIncidentes(ahora=ahora)
        cola.insertar("A", 2, ahora - timedelta(minutes=1))
        cola.insertar("B", 4, ahora - timedelta(minutes=1))
        cola.insertar("C", 4, ahora - timedelta(minutes=2))
        cola.insertar("D", 1, ahora)
        orden = [cola.extraer().incidente_id for _ in range(len(cola))]
        self.assertEqual(orden, ["C", "B", "A", "D"])

    def test_envejecimiento_evita_inanicion(self):
        ahora = datetime(2026, 10, 1, 12, 0)
        cola = ColaIncidentes(ahora=ahora)
        cola.insertar("VIEJO_P2", 2, ahora - timedelta(minutes=45))
        cola.insertar("NUEVO_P3", 3, ahora)
        self.assertEqual(cola.extraer().incidente_id, "VIEJO_P2")

    def test_bono_maximo(self):
        ahora = datetime(2026, 10, 1, 12, 0)
        self.assertEqual(prioridad_efectiva(1, ahora - timedelta(hours=10), ahora), 2.0)

    def test_extraer_vacia(self):
        with self.assertRaises(IndexError):
            ColaIncidentes().extraer()


if __name__ == "__main__":
    unittest.main()
