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

    def test_con_la_seleccion_la_conferencia_es_de_la_seleccion(self):
        # 2026-10-23, Simon: "que tengan mas que ver con lo que esta pasando"
        stats = MatchStats(goles_equipo=5, goles_rival=2, equipo_rival="Hungria", goles_jugador=5, rating_jugador=10,
                           minutos_jugados=90, equipo_propio="Italia")
        temas, contextos = set(), []

        def espiar(*argumentos):
            contextos.append(argumentos[1])
            temas.update(argumentos[4])

        with mock.patch.object(entrevista, "_carrera", return_value=None):
            for _ in range(10):
                with mock.patch.object(entrevista, "preguntas_con_ia", side_effect=espiar):
                    entrevista.generar_entrevista(self.perfil, stats)
        self.assertFalse(temas & {"mercado", "contratos"}, temas)
        self.assertIn("seleccion de Italia", contextos[0])

    def test_si_hizo_goles_no_le_preguntan_por_no_haber_marcado(self):
        stats = MatchStats(goles_equipo=5, goles_rival=2, equipo_rival="Hungria", goles_jugador=5, rating_jugador=10,
                           minutos_jugados=90)
        with mock.patch.object(entrevista, "_carrera", return_value=None):
            for _ in range(15):
                for pregunta in entrevista.generar_entrevista(self.perfil, stats):
                    self.assertNotIn("no te toco marcar", pregunta)
                    self.assertNotIn("sin gol tuyo", pregunta)

    def test_firman_con_su_usuario_y_el_estilo_emocional(self):
        quien, medio = entrevista.periodista_para("tactica", set(), random.Random(1))
        self.assertRegex(quien, r"^Periodista tactico \d @ptactico\d$")
        self.assertEqual(medio[:6], "Medio ")
        emocionales = {entrevista.periodista_para("hinchada", set(), random.Random(i))[0] for i in range(40)}
        self.assertIn("Periodista emocional @pemocional", emocionales)  # el emocional pregunta por la hinchada
        tacticos = {entrevista.periodista_para("tactica", set(), random.Random(i))[0] for i in range(40)}
        self.assertNotIn("Periodista emocional @pemocional", tacticos)


class TestFichajesDeSuLinea(ConEcosistema):
    """Un lateral que llega no le toca a un delantero centro; un extremo o un 9, si."""

    def _carrera(self, posicion="delantero centro"):
        carrera = mock.Mock(usuario_id=1)
        carrera.ficha.return_value = {"posicion": posicion}
        return carrera

    def _mercado(self, *movimientos):
        from roleplay import database

        database.set_estado_prensa(self.perfil.id, {"mercado": [
            {"texto": texto, "club": True, "jugador": 10 + i, "llega": llega, "posicion": posicion}
            for i, (texto, llega, posicion) in enumerate(movimientos)]})

    def test_un_lateral_no_le_toca_a_un_delantero(self):
        self._mercado(("Conor Bradley llega de Brighton", True, "lateral derecho"))
        extra = entrevista.contexto_de_club(self.perfil, self._carrera())
        self.assertNotIn("movimiento", extra)
        self.assertEqual(extra["posicion"], "delantero centro")

    def test_un_extremo_o_un_nueve_si(self):
        self._mercado(("Un lateral llega", True, "lateral izquierdo"), ("Un extremo llega de Napoli", True, "extremo derecho"))
        extra = entrevista.contexto_de_club(self.perfil, self._carrera())
        self.assertEqual(extra["movimiento"], "Un extremo llega de Napoli")
        self.assertNotIn("puesto_compartido", extra)  # misma linea, otro puesto: acomodarse
        self._mercado(("Un nueve llega del Inter", True, "delantero centro"))
        extra = entrevista.contexto_de_club(self.perfil, self._carrera())
        self.assertEqual(extra["puesto_compartido"], "delantero centro")  # competencia directa
        candidatos, _ = entrevista.temas_comunes(self.perfil, {"club": "Man Utd", "rival": "Leeds"}, [], extra)
        self.assertIn("tema_mercado_llega", [s for _, s, _ in candidatos["mercado"]])

    def test_sin_posicion_conocida_no_pregunta_por_fichajes(self):
        self._mercado(("Un nueve llega", True, "delantero centro"), ("Uno viejo sin posicion", True, ""))
        self.assertNotIn("movimiento", entrevista.contexto_de_club(self.perfil, self._carrera("")))


if __name__ == "__main__":
    unittest.main()
