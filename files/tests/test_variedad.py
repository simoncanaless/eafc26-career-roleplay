"""Conferencias variadas: piezas combinables, temas con los datos reales, sorteo con memoria, repreguntas y la IA."""

import json
import random
import unittest
from datetime import date
from unittest import mock

import ayuda
import fabrica_partida as f
from roleplay import database
from roleplay.models import MatchInterviewRecord, PlayerProfile
from roleplay.partida.carrera import construir
from roleplay.servicios import entrevista, ia
from roleplay.servicios.narrador import narrador
from roleplay.servicios.vision import MatchStats


def stats():
    return MatchStats(goles_equipo=2, goles_rival=1, goles_jugador=1, rating_jugador=7.8, minutos_jugados=90,
                      equipo_rival="Arsenal")


class ConPerfil(ayuda.PruebaConBase):
    def setUp(self):
        super().setUp()
        self.perfil = PlayerProfile(nombre_jugador="Simon Canales", club_actual="Man Utd")
        self.perfil.id = database.save_profile(self.perfil)
        mock.patch.object(entrevista, "_carrera", return_value=None).start()
        self.addCleanup(mock.patch.stopall)


class TestElegir(ConPerfil):
    def test_lo_obligatorio_va_si_o_si(self):
        with narrador(self.perfil.id, "entrevista") as escritor:
            for _ in range(20):
                simbolo, _ = entrevista._elegir([(9, "tac_hat_trick", {"goles_texto": "3 goles"}),
                                                 (2, "tema_tactica", {"rival": "x"})], escritor, [])
                self.assertEqual(simbolo, "tac_hat_trick")

    def test_lo_que_se_pregunto_hace_poco_casi_no_sale(self):
        candidatas = [(5, "tema_vestuario", {"club": "Man Utd"}), (4, "tema_hinchada", {"club": "Man Utd"})]
        with narrador(self.perfil.id, "entrevista", dado=random.Random(3)) as escritor:
            elegidos = [entrevista._elegir(candidatas, escritor, [], {"tema_vestuario"})[0] for _ in range(60)]
        self.assertGreater(elegidos.count("tema_hinchada"), 45)


class TestMemoria(ConPerfil):
    def test_la_conferencia_queda_anotada_y_cambia_la_siguiente(self):
        entrevista.generar_entrevista(self.perfil, stats())
        memoria = database.get_memoria_conferencias(self.perfil.id)
        self.assertEqual(len(memoria["simbolos"]), 3)
        self.assertEqual(len(memoria["temas"][0]), 3)
        self.assertEqual(len(memoria["preguntas"]), 3)

    def test_en_muchas_conferencias_casi_no_se_repite(self):
        nucleos = []
        for _ in range(15):
            preguntas = entrevista.generar_entrevista(self.perfil, stats())
            nucleos += [p.split(": ", 1)[1] for p in preguntas]
        self.assertGreaterEqual(len(set(nucleos)), 42)  # de 45


class TestDatosReales(ConPerfil):
    def test_ofertas_premios_familia_y_carrera(self):
        e = database.get_economia(self.perfil.id)
        e["ofertas"] = {"lista": [{"club": "Real Madrid", "tier": 1, "fecha": "2027-01-10", "estado": "nueva"}]}
        database.set_economia(self.perfil.id, e)
        estado = database.get_estado_prensa(self.perfil.id)
        estado["vitrina"] = [{"premio": "Jugador del Mes de la Premier League", "temporada": "2026/27"}]
        database.set_estado_prensa(self.perfil.id, estado)
        database.set_estado_amor(self.perfil.id, {"estado": "casado", "casados": "2026-12-20",
                                                  "pareja": {"nombre": "Denisse"},
                                                  "hijos": [{"nombre": "Ramon", "nacimiento": "2027-01-01"}]})
        carrera = construir(f.construir_bytes(etapas=True))
        temas = {s: (t, d) for t, _, s, d in entrevista.temas_de_los_datos(self.perfil, carrera, {"club": "Man Utd"})}
        self.assertEqual(temas["tema_oferta_filtrada"][1]["club_oferta"], "Real Madrid")
        self.assertEqual(temas["pic_premio_reciente"][1]["premio"], "Jugador del Mes de la Premier League")
        self.assertEqual(temas["pic_hijo"][1]["bebe"], "Ramon")
        self.assertIn("pic_boda", temas)
        self.assertEqual(temas["tac_goles_carrera"][1]["goles_carrera"], 264)
        with narrador(self.perfil.id, "entrevista") as escritor:  # el corpus las puede escribir
            for simbolo, (_, datos) in temas.items():
                self.assertTrue(escritor.puede(simbolo, **datos), simbolo)

    def test_una_oferta_de_un_club_chico_no_se_filtra(self):
        e = database.get_economia(self.perfil.id)
        e["ofertas"] = {"lista": [{"club": "Chico FC", "tier": 3, "fecha": date.today().isoformat()}]}
        database.set_economia(self.perfil.id, e)
        simbolos = [s for _, _, s, _ in entrevista.temas_de_los_datos(self.perfil, None, {})]
        self.assertNotIn("tema_oferta_filtrada", simbolos)


class TestRepregunta(ConPerfil):
    def _anterior(self, respuestas):
        database.save_match_interview(MatchInterviewRecord(
            player_id=self.perfil.id, equipo_rival="Liverpool", preguntas_entrevista=["a", "b", "c"],
            respuestas_jugador=respuestas))

    def test_lo_que_dijo_la_vez_pasada(self):
        self._anterior(["El arbitro nos robo el partido, fue un escandalo lo que cobro.", "Nada", "Nada"])
        (tema, _, simbolo, datos), = entrevista.repregunta(self.perfil, {})
        self.assertEqual((tema, simbolo), ("arbitraje", "rep_excusa_polemica"))
        self.assertEqual(datos["rival_anterior"], "Liverpool")
        with narrador(self.perfil.id, "entrevista") as escritor:
            texto = escritor.decir(simbolo, **datos)
        self.assertIn("«", texto)
        self.assertIn("Liverpool", texto)

    def test_sin_conferencia_anterior_no_hay_repregunta(self):
        self.assertEqual(entrevista.repregunta(self.perfil, {}), [])


class TestIA(ConPerfil):
    def test_la_ia_recibe_las_preguntas_recientes_para_no_repetirlas(self):
        pedidos = []

        def pedir(sistema, usuario, esquema, **_):
            pedidos.append(usuario)
            return None

        with mock.patch.object(ia, "pedir_json", side_effect=pedir):
            entrevista.preguntas_con_ia(self.perfil, "", ["A (B): ¿x?"], [], ["tactica"], ["¿Como esta el grupo?"])
        self.assertIn("NO las repitas", pedidos[0])
        self.assertIn("¿Como esta el grupo?", pedidos[0])


class TestCorpus(unittest.TestCase):
    def test_las_piezas_combinables_existen(self):
        from pathlib import Path

        corpus = json.loads((Path(entrevista.__file__).resolve().parent.parent / "datos" / "corpus_entrevista.json")
                            .read_text(encoding="utf-8"))
        for simbolo in ("q_tactica", "q_vestuario", "q_hinchada", "q_arbitraje", "q_vida", "q_victoria"):
            self.assertGreaterEqual(len(corpus[simbolo]), 5, simbolo)
        self.assertIn("#a_tac# #ctx_tactica# #q_tactica#", corpus["tema_tactica"])


if __name__ == "__main__":
    unittest.main()
