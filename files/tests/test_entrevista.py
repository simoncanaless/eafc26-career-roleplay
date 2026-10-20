"""Conferencias: periodistas reales (con su @usuario) y las 8 tematicas."""

import random
import unittest
from unittest import mock

from datos_ecosistema import ConEcosistema
from roleplay.servicios import entrevista
from roleplay.servicios.vision import MatchStats


class TestConferencia(ConEcosistema):
    def test_periodistas_reales_temas_distintos_y_lo_obligatorio(self):
        stats = MatchStats(goles_equipo=0, goles_rival=2, equipo_rival="Arsenal", rating_jugador=5.1,
                           minutos_jugados=70, tarjeta_roja=True)
        with mock.patch.object(entrevista, "_carrera", return_value=None):
            preguntas = entrevista.generar_entrevista(self.perfil, stats)
        self.assertEqual(len(preguntas), 3)
        nombres = [p.split(" (")[0] for p in preguntas]
        self.assertEqual(len(set(nombres)), 3)
        self.assertTrue(all(n.startswith("Periodista ") for n in nombres))  # los de los datos de Simon
        self.assertTrue(any("roja" in p.lower() or "expuls" in p.lower() for p in preguntas), preguntas)
        for pregunta in preguntas:
            self.assertNotRegex(pregunta, r"[{}]|#\w+#")

    def test_los_temas_varian(self):
        stats = MatchStats(goles_equipo=1, goles_rival=1, equipo_rival="Leeds", rating_jugador=6.8, minutos_jugados=90)
        vistos = set()
        with mock.patch.object(entrevista, "_carrera", return_value=None):
            for _ in range(12):
                with mock.patch.object(entrevista, "preguntas_con_ia", side_effect=lambda *a: vistos.update(a[4]) or None):
                    entrevista.generar_entrevista(self.perfil, stats)
        self.assertGreaterEqual(len(vistos), 6)  # de las 8 tematicas

    def test_firman_con_su_usuario_y_el_estilo_emocional(self):
        quien, medio = entrevista.periodista_para("tactica", set(), random.Random(1))
        self.assertRegex(quien, r"^Periodista tactico \d @ptactico\d$")
        self.assertEqual(medio[:6], "Medio ")
        emocionales = {entrevista.periodista_para("hinchada", set(), random.Random(i))[0] for i in range(40)}
        self.assertIn("Periodista emocional @pemocional", emocionales)  # el emocional pregunta por la hinchada
        tacticos = {entrevista.periodista_para("tactica", set(), random.Random(i))[0] for i in range(40)}
        self.assertNotIn("Periodista emocional @pemocional", tacticos)


if __name__ == "__main__":
    unittest.main()
