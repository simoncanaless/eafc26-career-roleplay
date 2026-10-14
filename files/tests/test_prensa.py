import unittest
from unittest import mock

import ayuda  # noqa: F401 - prepara el entorno de prueba
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


class TestRevisarPrensa(unittest.TestCase):
    perfil = PlayerProfile(id=7, nombre_jugador="Simon", club_actual="Palermo")

    def _redactor(self, falla_la_general: bool):
        def redactar(prompt, esquema, que_hacer, api_key=None):
            if "GENERAL" in prompt:
                if falla_la_general:
                    raise RuntimeError("Gemini caido.")
                return prensa.NoticiaIA(titular="Ambiente", cuerpo="c", tono="neutral")
            return prensa.NoticiaIA(titular="Sobre Simon", cuerpo="c", tono="positiva")

        return redactar

    def test_si_falla_la_de_ambiente_se_queda_la_del_jugador(self):
        with mock.patch.object(prensa, "generar_json", self._redactor(falla_la_general=True)), \
                mock.patch.object(prensa.random, "random", return_value=0.0):
            resultado = prensa.revisar_prensa(self.perfil, partidos(*[(1, 7.0)] * 3), {})
        self.assertEqual([n.titular for n in resultado["noticias"]], ["Sobre Simon"])
        self.assertEqual(resultado["noticias"][0].player_id, 7)
        self.assertEqual(resultado["noticias"][0].hitos, ["racha_goleadora:3"])

    def test_si_falla_la_de_ambiente_y_no_hay_otra_se_avisa(self):
        with mock.patch.object(prensa, "generar_json", self._redactor(falla_la_general=True)), \
                mock.patch.object(prensa.random, "random", return_value=0.0):
            with self.assertRaises(RuntimeError):
                prensa.revisar_prensa(self.perfil, [], {})

    def test_las_dos_noticias(self):
        with mock.patch.object(prensa, "generar_json", self._redactor(falla_la_general=False)), \
                mock.patch.object(prensa.random, "random", return_value=0.0):
            resultado = prensa.revisar_prensa(self.perfil, partidos(*[(1, 7.0)] * 3), {})
        self.assertEqual([n.categoria for n in resultado["noticias"]], ["jugador", "general"])


if __name__ == "__main__":
    unittest.main()
