import unittest
from unittest import mock

import ayuda
from roleplay import database
from roleplay.models import MatchInterviewRecord, PlayerProfile
from roleplay.servicios import prensa


def partidos(*goles_y_rating) -> list[MatchInterviewRecord]:
    """partidos((1, 8.0), (0, 6.5)) -> historial, el PRIMERO es el mas reciente."""
    return [MatchInterviewRecord(goles_jugador=g, rating_jugador=r) for g, r in goles_y_rating]


def hitos_de(historial, estado=None):
    stats = prensa.calcular_estadisticas_acumuladas(historial)
    return prensa.detectar_nuevos_hitos(stats, estado or {})


class TestHitos(unittest.TestCase):
    def test_sin_partidos_no_sale_ninguna_noticia(self):
        # El bug que ya le paso a Simon: con 0 partidos el promedio daba 0.0
        # y salia "su rating promedio cayo a 5.0 o menos".
        hitos, _ = hitos_de([])
        self.assertEqual(hitos, [])

    def test_con_menos_de_5_partidos_no_se_juzga_el_rating(self):
        hitos, _ = hitos_de(partidos((0, 4.0), (0, 4.5)))
        self.assertNotIn("mal_momento", [h["tipo"] for h in hitos])

    def test_cinco_partidos_malos_si_son_mal_momento(self):
        hitos, estado = hitos_de(partidos(*[(1, 4.0)] * 5))
        self.assertIn({"tipo": "mal_momento", "valor": 5.0}, hitos)
        self.assertEqual(estado["rating_bajo_min_reportado"], 5.0)

    def test_lo_que_siembra_el_script_de_prueba(self):
        hitos, _ = hitos_de(partidos(*[(1, 8.0)] * 5))
        self.assertCountEqual(
            hitos,
            [
                {"tipo": "hito_goles_totales", "valor": 5},
                {"tipo": "racha_goleadora", "valor": 5},
                {"tipo": "buen_momento", "valor": 8.0},
            ],
        )

    def test_un_hito_ya_reportado_no_se_repite(self):
        historial = partidos(*[(1, 7.0)] * 3)
        hitos, estado = hitos_de(historial)
        self.assertIn({"tipo": "racha_goleadora", "valor": 3}, hitos)
        hitos, _ = hitos_de(historial, estado)
        self.assertEqual(hitos, [])

    def test_la_racha_se_reinicia_al_cortarse_y_puede_volver_a_salir(self):
        _, estado = hitos_de(partidos(*[(1, 7.0)] * 3))
        sin_gol = partidos((0, 6.0), *[(1, 7.0)] * 3)
        _, estado = hitos_de(sin_gol, estado)
        self.assertEqual(estado["racha_goleadora_max_reportada"], 0)
        hitos, _ = hitos_de(partidos(*[(1, 7.0)] * 3) + sin_gol, estado)
        self.assertIn({"tipo": "racha_goleadora", "valor": 3}, hitos)

    def test_estadisticas_de_la_carrera(self):
        historial = partidos((2, 9.0), (0, 6.0))
        historial[0].asistencias_jugador = 1
        stats = prensa.calcular_estadisticas_acumuladas(historial)
        self.assertEqual(
            (stats["partidos_jugados"], stats["goles_totales"], stats["asistencias_totales"]), (2, 2, 1)
        )
        self.assertAlmostEqual(stats["rating_promedio"], 7.5)
        self.assertEqual((stats["racha_goleadora"], stats["racha_sin_gol"]), (1, 0))


class TestRevisarPrensa(ayuda.PruebaConBase):
    """Las noticias las arma el motor narrativo: no fallan ni esperan."""

    def setUp(self):
        super().setUp()
        self.perfil = PlayerProfile(nombre_jugador="Simon Canales", club_actual="Palermo")
        self.perfil.id = database.save_profile(self.perfil)

    def _revisar(self, historial, estado=None, azar=0.99):
        with mock.patch.object(prensa.random, "random", return_value=azar):
            return prensa.revisar_prensa(self.perfil, historial, estado or {})

    def test_la_noticia_del_jugador(self):
        resultado = self._revisar(partidos(*[(1, 7.0)] * 3))
        (noticia,) = resultado["noticias"]  # azar alto: sin la de ambiente
        self.assertEqual((noticia.categoria, noticia.tono, noticia.player_id), ("jugador", "positiva", self.perfil.id))
        self.assertEqual(noticia.hitos, ["racha_goleadora:3"])
        self.assertIn("Canales", noticia.titular)
        self.assertIn("3", noticia.titular + noticia.cuerpo)
        self.assertNotRegex(noticia.titular + noticia.cuerpo, r"[{}]|#\w+#")
        self.assertEqual(noticia.cuerpo[0], noticia.cuerpo[0].upper())

    def test_las_dos_noticias(self):
        resultado = self._revisar(partidos(*[(1, 7.0)] * 3), azar=0.0)
        self.assertEqual([n.categoria for n in resultado["noticias"]], ["jugador", "general"])
        ambiente = resultado["noticias"][1]
        self.assertNotRegex(ambiente.titular + ambiente.cuerpo, r"[{}]|#\w+#")  # los #clubes# ficticios se expanden

    def test_sin_hitos_solo_la_de_ambiente_si_toca(self):
        self.assertEqual(self._revisar([])["noticias"], [])
        self.assertEqual([n.categoria for n in self._revisar([], azar=0.0)["noticias"]], ["general"])

    def test_los_titulares_de_ambiente_no_se_repiten(self):
        titulares = [self._revisar([], azar=0.0)["noticias"][0].titular for _ in range(6)]
        self.assertEqual(len(set(titulares)), 6, titulares)
        self.assertTrue(database.get_narrador_usados(self.perfil.id)["textos"])

    def test_la_entrevista_sale_con_su_cita(self):
        registro = MatchInterviewRecord(
            goles_equipo=2, goles_rival=1, equipo_rival="Inter", goles_jugador=1, rating_jugador=7.5,
            respuestas_jugador=["Fue un triunfo de todo el equipo, el grupo trabajo muchisimo toda la semana."],
            reaccion_prensa="La prensa valoro su humildad.", delta_reputacion=3,
        )
        registro.player_id = self.perfil.id
        registro.id = database.save_match_interview(registro)
        resultado = self._revisar([registro])
        (nota,) = [n for n in resultado["noticias"] if n.hitos == [f"entrevista:{registro.id}"]]
        self.assertIn("«", nota.titular)
        self.assertIn("todo el equipo", nota.titular)
        self.assertIn("La prensa valoro su humildad.", nota.cuerpo)
        self.assertEqual(nota.tono, "positiva")
        self.assertEqual(resultado["estado_prensa"]["entrevista_reportada"], registro.id)
        otra_vez = self._revisar([registro], resultado["estado_prensa"])
        self.assertFalse([n for n in otra_vez["noticias"] if n.hitos == [f"entrevista:{registro.id}"]])

    def test_una_respuesta_corta_no_se_cita(self):
        registro = MatchInterviewRecord(respuestas_jugador=["Bien."], equipo_rival="Inter")
        registro.player_id = self.perfil.id
        registro.id = database.save_match_interview(registro)
        self.assertEqual(self._revisar([registro])["noticias"], [])


if __name__ == "__main__":
    unittest.main()
