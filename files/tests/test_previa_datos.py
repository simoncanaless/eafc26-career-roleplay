"""Las preguntas salen de los datos reales (Simon: "con el Stoke tan cerca" cuando el Stoke es ultimo y el, primero)."""

import unittest

import ayuda
from roleplay import database
from roleplay.models import PlayerProfile
from roleplay.servicios import cruce, entrevista, previa


def la_previa(puesto, puesto_rival, puntos, puntos_rival):
    return previa.PreviaPartido(clave="x", club="Man Utd", rival="Stoke City", de_local=False,
                                competicion="Premier League", fecha="10-02-2027", posicion=f"{puesto}°",
                                posicion_rival=f"{puesto_rival}°", puesto=puesto, puesto_rival=puesto_rival,
                                puntos=puntos, puntos_rival=puntos_rival)


class TestLaTabla(unittest.TestCase):
    def test_primero_contra_el_ultimo_es_ser_favorito(self):
        self.assertEqual(previa.como_llegan(la_previa(1, 20, 64, 9)), ("pv_tac_tabla_favorito", 55))

    def test_cerca_en_la_tabla(self):
        self.assertEqual(previa.como_llegan(la_previa(1, 2, 64, 63))[0], "pv_tac_tabla")
        self.assertEqual(previa.como_llegan(la_previa(5, 12, 44, 40))[0], "pv_tac_tabla")  # 4 puntos

    def test_desde_abajo(self):
        self.assertEqual(previa.como_llegan(la_previa(15, 2, 25, 63)), ("pv_tac_tabla_abajo", 38))

    def test_sin_tabla_no_hay_pregunta_de_tabla(self):
        self.assertEqual(previa.como_llegan(la_previa(0, 0, 0, 0))[0], "")


class TestPreguntas(ayuda.PruebaConBase):
    def setUp(self):
        super().setUp()
        self.perfil = PlayerProfile(nombre_jugador="Simon Canales", club_actual="Man Utd",
                                    estado_relacion="novia_real", nombre_pareja="Denisse")
        self.perfil.id = database.save_profile(self.perfil)

    def _simbolos(self, previa_):
        pareja = cruce.Cruce("pareja_real", 6, {"pareja": "Denisse"})
        candidatos, _ = entrevista.temas_comunes(self.perfil, {"club": "Man Utd"}, [pareja], {}, previa=previa_)
        return {s for lista in candidatos.values() for _, s, _ in lista}

    def test_en_la_previa_no_se_pregunta_por_un_partido_que_no_se_jugo(self):
        self.assertIn("pv_pic_pareja_real", self._simbolos(True))
        self.assertNotIn("pic_pareja_real", self._simbolos(True))
        self.assertIn("pic_pareja_real", self._simbolos(False))  # despues del partido, si

    def test_las_preguntas_de_la_previa_no_hablan_en_pasado(self):
        from roleplay.servicios.narrador import narrador

        with narrador(self.perfil.id, "entrevista") as escritor:
            for _ in range(6):
                texto = escritor.decir("pv_pic_pareja_real", pareja="Denisse")
                self.assertNotIn("despues del partido", texto)
                self.assertNotIn("estaba", texto)

    def test_la_marca_con_su_nombre_de_hoy(self):
        e = database.get_economia(self.perfil.id)
        e["patrocinios"] = {"contratos": [{"id": "x", "marca": "bebida", "nombre": "una bebida isotonica",
                                           "rubro": "bebidas", "semanal": 1, "desde": "2027-01-01",
                                           "hasta": "2029-01-01"}]}
        database.set_economia(self.perfil.id, e)
        extra = entrevista.contexto_de_club(self.perfil, None)
        self.assertEqual(extra["marca"], "Zuko")
        self.assertFalse(extra["marca_campanas"])  # todavia no hizo ninguna promo


if __name__ == "__main__":
    unittest.main()
