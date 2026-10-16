"""
Pruebas de analítica (Pandas), simulación y PDF (ReportLab).
No requieren base de datos.
"""
import unittest
from datetime import datetime, timedelta

from app.geografia import nodos
from app.servicios.analitica import a_dataframe_exportable, calcular_kpis, calcular_resumen
from app.servicios.reportes import generar_pdf
from app.simulacion import RECURSOS_INICIALES, generar_historial

AHORA = datetime(2026, 10, 14, 12, 0)


def _incidentes():
    return generar_historial(dias=60, ahora=AHORA)


def _recursos(ocupadas=5, mantenimiento=2):
    estados = ["dispatched"] * ocupadas + ["maintenance"] * mantenimiento
    estados += ["available"] * (len(RECURSOS_INICIALES) - len(estados))
    return [{"code": c, "type": t, "status": s} for (c, t, _z), s in zip(RECURSOS_INICIALES, estados)]


class TestSimulacion(unittest.TestCase):
    def test_historial_coherente(self):
        h = _incidentes()
        self.assertGreater(len(h), 100)
        ids = [i["id"] for i in h]
        self.assertEqual(len(ids), len(set(ids)), "IDs repetidos")
        for i in h:
            self.assertIn(i["node"], nodos())
            self.assertLessEqual(i["reported_at"], i["dispatched_at"])
            if i["arrived_at"]:
                self.assertLess(i["dispatched_at"], i["arrived_at"])
                self.assertLess(i["arrived_at"], i["resolved_at"])

    def test_reproducible(self):
        self.assertEqual(_incidentes()[0]["id"], _incidentes()[0]["id"])


class TestAnalitica(unittest.TestCase):
    def test_kpis_con_datos(self):
        k = calcular_kpis(_incidentes(), _recursos(), dias=30, ahora=AHORA)
        self.assertGreater(k["total_incidents"], 0)
        self.assertIsNotNone(k["avg_response_time_min"])
        self.assertGreater(k["avg_response_time_min"], 1)
        self.assertIn(k["highest_risk_node"], nodos())
        # 5 ocupadas; 2 en mantenimiento no cuentan como operativas
        self.assertEqual(k["fleet_utilization_pct"], round(5 / (len(RECURSOS_INICIALES) - 2) * 100, 1))
        # La simulación mejora en los últimos 30 días
        self.assertLess(k["avg_response_time_min"], k["previous_avg_response_time_min"])
        self.assertTrue(0 <= k["target_compliance_pct"] <= 100)

    def test_kpis_sin_datos(self):
        k = calcular_kpis([], [], ahora=AHORA)
        self.assertEqual(k["total_incidents"], 0)
        self.assertIsNone(k["avg_response_time_min"])
        self.assertIsNone(k["highest_risk_node"])
        self.assertEqual(k["fleet_utilization_pct"], 0.0)

    def test_respuesta_manual(self):
        base = AHORA - timedelta(days=1)
        datos = [
            {"id": "A", "type": "fire", "priority": 4, "node": 1, "department_code": "01", "status": "resolved",
             "reported_at": base, "dispatched_at": base + timedelta(minutes=1),
             "arrived_at": base + timedelta(minutes=6), "resolved_at": base + timedelta(minutes=60)},
            {"id": "B", "type": "medical", "priority": 2, "node": 1, "department_code": "01", "status": "resolved",
             "reported_at": base, "dispatched_at": base + timedelta(minutes=3),
             "arrived_at": base + timedelta(minutes=24), "resolved_at": base + timedelta(minutes=60)},
        ]
        k = calcular_kpis(datos, [], ahora=AHORA)
        self.assertEqual(k["avg_response_time_min"], 15.0)      # (6 + 24) / 2
        self.assertEqual(k["avg_dispatch_time_min"], 2.0)       # (1 + 3) / 2
        self.assertEqual(k["target_compliance_pct"], 50.0)      # A cumple (6<=7), B no (24>12)
        self.assertEqual(k["risk_ranking"][0]["risk_index"], 10)  # 8 + 2

    def test_resumen(self):
        r = calcular_resumen(_incidentes(), dias=30, ahora=AHORA)
        self.assertEqual(len(r["daily_trend"]), 30)
        self.assertEqual(len(r["by_hour"]), 24)
        self.assertEqual(len(r["by_priority"]), 4)
        self.assertEqual(sum(t["count"] for t in r["by_type"]), sum(d["total"] for d in r["daily_trend"]))

    def test_resumen_vacio(self):
        r = calcular_resumen([], dias=7, ahora=AHORA)
        self.assertEqual(len(r["daily_trend"]), 7)
        self.assertEqual(r["by_location"], [])
        self.assertEqual(r["by_department"], [])

    def test_exportable(self):
        df = a_dataframe_exportable(_incidentes())
        self.assertIn("Min. respuesta", df.columns)


class TestReporte(unittest.TestCase):
    def test_pdf(self):
        inc = _incidentes()
        kpis = calcular_kpis(inc, _recursos(), ahora=AHORA)
        resumen = calcular_resumen(inc, ahora=AHORA)
        recientes = [{
            "id": i["id"], "type_label": i["type"], "priority": i["priority"], "location_label": str(i["node"]),
            "status_label": i["status"], "response_time_min": 7.5,
        } for i in inc[-10:]]
        recursos = [{"code": c, "type_label": t, "name": f"Unidad {c}", "current_label": str(z), "status_label": "Disponible"}
                    for c, t, z in RECURSOS_INICIALES]
        pdf = generar_pdf(kpis, resumen, recientes, recursos, "prueba", ahora=AHORA)
        self.assertTrue(pdf.startswith(b"%PDF"))
        self.assertGreater(len(pdf), 5000)

    def test_pdf_vacio(self):
        pdf = generar_pdf(calcular_kpis([], [], ahora=AHORA), calcular_resumen([], ahora=AHORA), [], [], "prueba", ahora=AHORA)
        self.assertTrue(pdf.startswith(b"%PDF"))


if __name__ == "__main__":
    unittest.main()
