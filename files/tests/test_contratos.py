"""Las primas del contrato: negociacion con la directiva, firma y cobros."""

import random
import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest import mock

import ayuda
import fabrica_partida as f
from roleplay import database
from roleplay.models import PlayerProfile
from roleplay.partida import lector
from roleplay.servicios import amor, contratos, economia, eventos, hinchada, partida_real

HOY = date(2026, 8, 1)


def mesa(fama=70, tier=2, posicion="delantero centro", carino=50):
    return contratos.abrir("Man Utd", tier, fama, HOY, posicion, carino, dado=random.Random(1))


class TestNegociacion(unittest.TestCase):
    def test_la_primera_oferta_queda_bajo_el_techo(self):
        neg = mesa()
        for c in contratos.CLAUSULAS:
            self.assertLess(neg["oferta"][c.id], neg["techo"][c.id])
        self.assertEqual(neg["meta_goles"], 20)
        self.assertEqual(mesa(posicion="defensa central")["meta_goles"], 5)  # un central no hace 20

    def test_un_gigante_y_un_crack_pagan_mas(self):
        self.assertGreater(mesa(fama=95, tier=1)["techo"]["gol"], mesa(fama=40, tier=3)["techo"]["gol"])
        self.assertLessEqual(mesa(fama=100, tier=1)["techo"]["imagen"], contratos.IMAGEN_MAXIMA)

    def test_pedir_lo_justo_cierra_el_trato(self):
        neg = mesa()
        neg, respuesta = contratos.contraofertar(neg, neg["techo"])
        self.assertEqual(respuesta, "acepta")
        self.assertEqual(neg["oferta"], neg["techo"])
        self.assertEqual(neg["estado"], "acuerdo")

    def test_pasarse_un_poco_sube_y_cansa(self):
        neg = mesa()
        pedido = {**neg["techo"], "gol": neg["techo"]["gol"] * 1.5}
        nueva, respuesta = contratos.contraofertar(neg, pedido)
        self.assertEqual(respuesta, "sube")
        self.assertEqual(nueva["oferta"]["gol"], neg["techo"]["gol"])  # hasta donde puede
        self.assertEqual(nueva["paciencia"], neg["paciencia"] - 1)

    def test_pedir_de_mas_ofende_y_se_rompe(self):
        neg = mesa()
        abuso = {k: v * 3 for k, v in neg["techo"].items()}
        neg, respuesta = contratos.contraofertar(neg, abuso)
        self.assertEqual(respuesta, "ofendida")
        neg, respuesta = contratos.contraofertar(neg, abuso)
        self.assertEqual(respuesta, "rompe")
        self.assertEqual(neg["estado"], "rota")
        with self.assertRaises(ValueError):
            contratos.contraofertar(neg, abuso)

    def test_el_idolo_tiene_mas_paciencia(self):
        self.assertEqual(mesa(carino=90)["paciencia"], contratos.PACIENCIA + 1)

    def test_el_representante(self):
        neg = mesa()
        consejo = contratos.consejo(neg, {**neg["oferta"], "gol": neg["techo"]["gol"] * 2})
        self.assertEqual(consejo["gol"], "pasado")
        self.assertEqual(consejo["firma"], "margen")  # la primera oferta siempre deja margen


class TestCobros(unittest.TestCase):
    def setUp(self):
        neg = mesa()
        neg["oferta"] = {c.id: 0 for c in contratos.CLAUSULAS} | {"firma": 30, "gol": 0.5, "meta_goles": 10, "mes": 1,
                                                                  "titulo": 4, "fidelidad": 5, "imagen": 10}
        self.e, self.cobrado = contratos.firmar({"saldo": 0, "sueldo": 100_000, "hasta": "2026-08-01"}, neg, 3, HOY, fama=70, goles=2)
        self.semana = 100_000 * economia.NETO

    def test_firmar_paga_la_primera_cuota_menos_el_representante(self):
        total = 30 * self.semana
        self.assertEqual(self.cobrado, round(total / 3) - round(total * contratos.COMISION_REPRESENTANTE))
        self.assertEqual(self.e["contrato"]["hasta_temporada"], "2028/29")

    def test_goles_meta_y_premios_una_sola_vez(self):
        vitrina = [{"premio": "Jugador del mes", "detalle": "Agosto", "temporada": "2026/27"},
                   {"premio": "Jugador del mes", "detalle": "Mayo", "temporada": "2025/26"}]  # antes de firmar
        e, cobros = contratos.cobrar(self.e, "Man Utd", date(2026, 9, 1), 12, vitrina)
        conceptos = [c for c, _ in cobros]
        self.assertIn("Prima por 10 goles (neto)", conceptos)  # los 2 de antes de firmar no cuentan
        self.assertNotIn("Prima por llegar a 20 goles (neto)", conceptos)  # 12 goles: todavia no
        self.assertEqual(sum(1 for c in conceptos if "jugador del mes" in c), 1)
        e, cobros = contratos.cobrar(e, "Man Utd", date(2026, 9, 8), 12, vitrina)
        self.assertEqual(cobros, [])
        e, cobros = contratos.cobrar(e, "Man Utd", date(2026, 10, 1), 21, vitrina)
        self.assertIn("Prima por llegar a 20 goles (neto)", [c for c, _ in cobros])

    def test_nueva_temporada_fidelidad_y_cuota(self):
        e, _ = contratos.cobrar(self.e, "Man Utd", date(2027, 3, 1), 5, [])
        e, cobros = contratos.cobrar(e, "Man Utd", date(2027, 7, 10), 0, [])
        conceptos = [c for c, _ in cobros]
        self.assertIn("Prima de fidelidad, temporada 2026/27 (neto)", conceptos)
        self.assertIn("Prima de firma: cuota 2 de 3 (neto)", conceptos)

    def test_si_se_va_del_club_el_contrato_termina(self):
        e, cobros = contratos.cobrar(self.e, "Real Madrid", date(2026, 9, 1), 12, [])
        self.assertNotIn("contrato", e)
        self.assertEqual(cobros, [])

    def test_derechos_de_imagen_con_el_sueldo(self):
        e = economia.acreditar(self.e, date(2026, 8, 8), 100_000)
        self.assertIn("Derechos de imagen de 7 dias (neto)", [m["concepto"] for m in e["movimientos"]])

    def test_balon_de_oro_una_vez_por_temporada(self):
        e, prima = contratos.balon_de_oro(self.e, "Man Utd", date(2026, 12, 1))
        self.assertEqual(prima, 0)  # esta clausula quedo en 0
        with self.assertRaises(ValueError):
            contratos.balon_de_oro(e, "Man Utd", date(2027, 1, 1))

    def test_cuando_se_puede_negociar(self):
        self.assertFalse(contratos.puede_negociar(self.e, "Man Utd", HOY, 70)[0])
        self.assertTrue(contratos.puede_negociar(self.e, "Man Utd", HOY, 70 + contratos.MEJORA_DESDE_FAMA)[0])
        self.assertTrue(contratos.puede_negociar(self.e, "Otro club", HOY, 70)[0])
        bloqueado = {**self.e, "negociacion_rota": {"club": "Otro club", "temporada": "2026/27"}}
        self.assertFalse(contratos.puede_negociar(bloqueado, "Otro club", HOY, 70)[0])
        self.assertTrue(contratos.puede_negociar(bloqueado, "Otro club", date(2027, 8, 1), 70)[0])


class TestEnVida(ayuda.PruebaDeInterfaz):
    def setUp(self):
        super().setUp()
        carpeta = Path(self.enterContext(tempfile.TemporaryDirectory()))
        (carpeta / "CmPlr1").write_bytes(f.construir_bytes())
        mock.patch.object(lector, "CARPETA_GUARDADOS", carpeta).start()
        mock.patch.object(partida_real, "identificar_jugadores", return_value={}).start()
        mock.patch.object(partida_real, "identificar_competiciones", return_value={}).start()
        mock.patch.object(hinchada, "comentar_eventos", return_value={}).start()
        mock.patch.object(eventos, "PROBABILIDAD_POR_SEMANA", 0).start()
        mock.patch.object(amor, "PROBABILIDAD_POR_SEMANA", 0).start()
        self.addCleanup(mock.patch.stopall)
        self.addCleanup(ayuda.esperar_tareas)
        self.pid = database.save_profile(PlayerProfile(nombre_jugador="Simon Canales", club_actual="Man Utd"))
        from roleplay.ui.vida import PaginaVida

        self.pagina = PaginaVida()
        self.pagina.actualizar()
        ayuda.esperar_tareas()

    def _negociar(self, que_hace):
        from roleplay.ui.contrato import DialogoNegociacion

        def exec_(dialogo):
            que_hace(dialogo)
            return 0

        with mock.patch.object(DialogoNegociacion, "exec", exec_):
            self.pagina.negociar_contrato()
            ayuda.esperar_tareas()

    def test_negociar_y_firmar(self):
        self.assertFalse(self.pagina.contrato.isHidden())
        self.assertTrue(self.pagina.negociar_btn.isEnabled())
        saldo = database.get_economia(self.pid)["saldo"]

        def firmar(dialogo):
            dialogo.contraofertar()  # pide lo mismo que le ofrecen: acepta
            dialogo.firmar()

        self._negociar(firmar)
        e = database.get_economia(self.pid)
        self.assertIn("contrato", e)
        self.assertGreater(e["saldo"], saldo)
        self.assertEqual(database.load_noticias_prensa(self.pid)[0].hitos, ["contrato:firma"])
        self.assertFalse(self.pagina.negociar_btn.isEnabled())  # hasta que suba su fama
        self.assertIn("Prima por gol", self.pagina.contrato_label.text())

    def test_pensarlo_guarda_la_negociacion(self):
        def pensarlo(dialogo):
            dialogo.pedidos["gol"].setValue(dialogo.negociacion["techo"]["gol"] * 1.5)
            dialogo.contraofertar()

        self._negociar(pensarlo)
        guardada = database.get_economia(self.pid)["negociacion"]
        self.assertEqual(guardada["ronda"], 1)
        self.assertEqual(guardada["paciencia"], guardada["paciencia_inicial"] - 1)

    def test_levantarse_rompe_hasta_la_temporada_que_viene(self):
        self._negociar(lambda dialogo: dialogo.levantarse())
        self.assertIn("negociacion_rota", database.get_economia(self.pid))
        self.assertFalse(self.pagina.negociar_btn.isEnabled())
        self.assertEqual(database.load_noticias_prensa(self.pid)[0].hitos, ["contrato:rota"])

    def test_balon_de_oro(self):
        reputacion = database.get_reputacion_actual(self.pid)
        with mock.patch.object(type(self.pagina), "_confirmar", return_value=True):
            self.pagina.anotar_balon_de_oro()
            ayuda.esperar_tareas()
        self.assertGreater(database.get_reputacion_actual(self.pid), reputacion)
        self.assertFalse(self.pagina.balon_btn.isEnabled())


if __name__ == "__main__":
    unittest.main()
