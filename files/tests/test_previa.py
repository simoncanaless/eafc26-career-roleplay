"""Conferencia de prensa previa al proximo partido."""

import unittest
from unittest import mock

import ayuda
import fabrica_partida as f
from roleplay import database
from roleplay.models import PlayerProfile
from roleplay.partida.carrera import construir
from roleplay.servicios import partida_real, previa
from roleplay.servicios.previa import PreviaPartido, ReaccionPrevia, previa_del_proximo


def carrera_falsa():
    return construir(f.construir_bytes(), "falsa")


class TestPreviaDelProximo(ayuda.PruebaConBase):
    def test_los_datos_salen_de_la_partida(self):
        p = previa_del_proximo(carrera_falsa())
        self.assertEqual((p.club, p.rival, p.de_local, p.fecha), ("Man Utd", "SSC Napoli", False, "20-01-2027"))
        self.assertEqual(p.clave, "2027-01-20|122|48|11")
        texto = p.describir()
        for esperado in (
            "Man Utd ante SSC Napoli, de visita",
            "Racha de Man Utd (ultimos partidos, el mas reciente al final): G E G.",
            "Ya se enfrentaron esta temporada: Man Utd 3-3 SSC Napoli",
        ):
            self.assertIn(esperado, texto)
        self.assertFalse(p.ya_hecha)

    def test_ya_hecha_segun_lo_guardado(self):
        c = carrera_falsa()
        clave = previa_del_proximo(c).clave
        self.assertTrue(previa_del_proximo(c, estado_partida={"previa": clave}).ya_hecha)
        self.assertFalse(previa_del_proximo(c, estado_partida={"previa": "otra"}).ya_hecha)

    def test_en_una_liga_compara_la_tabla_y_nombra_al_goleador_rival(self):
        c = carrera_falsa()
        # el proximo pasa a ser de liga, ante el City
        c.partidos.append(c.partidos[-1].__class__(
            fecha=c.partidos[-1].fecha.replace(day=19), competicion=f.LIGA, local=f.CITY, visita=f.MAN_UTD,
            goles_local=None, goles_visita=None, jugado=False,
        ))
        p = previa_del_proximo(c, nombres={f.HAALAND: "Erling Haaland"})
        self.assertEqual(p.rival, "Manchester City")
        self.assertIn("En la tabla: Man Utd 2° con 6 pts, Manchester City 1° con 7 pts (de 5 equipos).", p.datos)
        self.assertIn("Goleador de Manchester City (Premier League): Erling Haaland con 5 goles.", p.datos)
        self.assertIn("Ultimo partido de Manchester City: Manchester City 2-0 Arsenal (Premier League).", p.datos)

    def test_sin_proximo_partido_no_hay_previa(self):
        c = carrera_falsa()
        c.partidos[:] = [p for p in c.partidos if p.jugado]
        self.assertIsNone(previa_del_proximo(c))

    def test_la_lectura_de_la_sala_trae_la_previa(self):
        c = carrera_falsa()
        with mock.patch("roleplay.partida.lector.carrera_actual", return_value=c):
            lectura = partida_real.leer_para_entrevista(database.save_profile(PlayerProfile(nombre_jugador="Simon")))
        self.assertEqual(lectura.previa.rival, "SSC Napoli")


class TestPromptsYEvaluacion(unittest.TestCase):
    def setUp(self):
        self.perfil = PlayerProfile(id=1, nombre_jugador="Simon Canales", club_actual="Man Utd")
        self.previa = PreviaPartido("clave", "Man Utd", "Spurs", True, "Premier League", "24-01-2027",
                                    ["En la tabla: Man Utd 2° con 55 pts, Spurs 8° con 32 pts (de 20 equipos)."])

    def test_las_preguntas_usan_los_datos_reales(self):
        prompt = previa._prompt_preguntas(self.perfil, self.previa, "CONTEXTO")
        self.assertIn("PREVIA", prompt)
        self.assertIn("Man Utd ante Spurs, de local, por Premier League", prompt)
        self.assertIn("Spurs 8° con 32 pts", prompt)
        self.assertIn("CONTEXTO", prompt)

    def test_la_evaluacion_se_acota(self):
        crudo = ReaccionPrevia(titular=" ", reaccion_prensa="Polemica", tono="Rarisimo", delta_reputacion=40)
        with mock.patch.object(previa, "generar_json", return_value=crudo):
            r = previa.evaluar_previa(self.perfil, self.previa, [("P?", "R")])
        self.assertEqual(r.delta_reputacion, previa.DELTA_REPUTACION_MAXIMO)
        self.assertEqual(r.tono, "neutral")
        self.assertIn("Spurs", r.titular)  # sin titular, uno por defecto


class TestSalaConPrevia(ayuda.PruebaDeInterfaz):
    def setUp(self):
        super().setUp()
        self.pid = database.save_profile(PlayerProfile(nombre_jugador="Simon Canales", club_actual="Man Utd"))
        from roleplay.ui import entrevista

        self.modulo = entrevista
        carrera = carrera_falsa()
        self.lectura = partida_real.LecturaPartida(
            carrera=carrera, ultimo=partida_real.ultimo_partido(carrera, {}), contexto="CONTEXTO REAL",
            ya_entrevistado=False, previa=previa_del_proximo(carrera),
        )
        mock.patch.object(entrevista, "leer_para_entrevista", return_value=self.lectura).start()
        self.addCleanup(mock.patch.stopall)
        self.sala = entrevista.InterviewWindow()
        ayuda.esperar_tareas()

    def _a_la_previa_con_preguntas(self):
        self.sala.modo_previa_btn.click()
        with mock.patch.object(self.modulo, "generar_previa", return_value=["¿Como llegan a Napoles?"]) as generar:
            self.sala.generar_entrevista_btn.click()
            ayuda.esperar_tareas()
        return generar

    def test_cambiar_a_la_previa(self):
        sala = self.sala
        self.assertTrue(sala.modo_previa_btn.isEnabled())
        sala.modo_previa_btn.click()
        self.assertEqual(sala._modo, "previa")
        self.assertFalse(sala.tarjeta_partido.isVisibleTo(sala))  # el formulario del partido no aplica
        self.assertIn("Conferencia previa", sala.header_label.text())
        self.assertIn("vs SSC Napoli", ayuda.texto_visible(sala.previa_label.text()))
        self.assertEqual(sala.generar_entrevista_btn.text(), "GENERAR CONFERENCIA PREVIA")
        self.assertEqual(sala.titulo_entrevista.text(), "1 · LA CONFERENCIA")
        sala.modo_post_btn.click()
        self.assertEqual(sala._modo, "post")
        self.assertTrue(sala.tarjeta_partido.isVisibleTo(sala))
        self.assertFalse(sala.previa_label.isVisibleTo(sala))

    def test_generar_y_enviar_la_previa(self):
        generar = self._a_la_previa_con_preguntas()
        self.assertIs(generar.call_args.args[1], self.lectura.previa)
        self.assertEqual(generar.call_args.args[2], "CONTEXTO REAL")

        sala = self.sala
        sala._respuesta_edits[0].setPlainText("Vamos a ganar alla, no hay otra")
        self.assertFalse(sala.modo_post_btn.isEnabled())  # con respuestas escritas no se cambia de modo
        reaccion = ReaccionPrevia(titular="Canales: \"Vamos a ganar alla\"", reaccion_prensa="Los napolitanos no lo olvidan.",
                                  tono="mixta", delta_reputacion=4, nuevo_gancho_narrativo="Prometio ganar en Napoles")
        with mock.patch.object(self.modulo, "evaluar_previa", return_value=reaccion), \
                mock.patch.object(self.modulo, "revisar_prensa_con_partida") as prensa:
            sala.enviar_respuestas_btn.click()
            ayuda.esperar_tareas()
        prensa.assert_not_called()

        self.assertEqual(database.load_match_interviews(self.pid), [])  # no cuenta como partido
        self.assertEqual(database.get_reputacion_actual(self.pid), 50 + 4)
        noticia = database.load_noticias_prensa(self.pid)[0]
        self.assertEqual((noticia.titular, noticia.tono), ("Canales: \"Vamos a ganar alla\"", "mixta"))
        self.assertEqual(database.get_estado_partida(self.pid)["previa"], self.lectura.previa.clave)
        self.assertIn("Prometio ganar en Napoles", database.load_profile(self.pid).ganchos_narrativos)
        self.assertIn("ya diste esta conferencia", sala.previa_label.text())
        self.assertIn("Vamos a ganar alla", ayuda.texto_visible(sala.reaccion_label.text()))

    def test_la_sala_flotante_muestra_la_previa(self):
        from roleplay.ui.overlay import SalaFlotante

        flotante = SalaFlotante(self.sala)
        self._a_la_previa_con_preguntas()
        self.assertIn("Previa:", flotante.partido_label.text())
        self.assertFalse(flotante.cargar_btn.isVisibleTo(flotante))
        self.assertEqual(len(flotante._edits), 1)

    def test_cambiar_de_modo_desde_la_sala_flotante(self):
        from roleplay.ui.overlay import SalaFlotante

        flotante = SalaFlotante(self.sala)
        self.assertTrue(flotante.modo_post_btn.isChecked())
        flotante.modo_previa_btn.click()
        self.assertEqual(self.sala._modo, "previa")
        self.assertTrue(flotante.modo_previa_btn.isChecked())
        self.assertFalse(flotante.modo_post_btn.isChecked())
        flotante.modo_post_btn.click()
        self.assertEqual(self.sala._modo, "post")

    def test_sin_previa_el_panel_tampoco_la_ofrece(self):
        from roleplay.ui.overlay import SalaFlotante

        self.lectura.previa = None
        self.sala._on_partida_leida(self.lectura)
        flotante = SalaFlotante(self.sala)
        self.assertFalse(flotante.modo_previa_btn.isEnabled())
        flotante.modo_previa_btn.click()  # deshabilitado: no hace nada
        self.assertEqual(self.sala._modo, "post")

    def test_un_partido_nuevo_vuelve_al_post_partido(self):
        self.sala.modo_previa_btn.click()
        self.assertTrue(self.sala.recibir_partido_nuevo(self.lectura, preparar_preguntas=False))
        self.assertEqual(self.sala._modo, "post")
        self.assertEqual(self.sala._origen, "partida")

    def test_sin_previa_no_se_puede_elegir(self):
        self.lectura.previa = None
        self.sala._on_partida_leida(self.lectura)
        self.assertFalse(self.sala.modo_previa_btn.isEnabled())


if __name__ == "__main__":
    unittest.main()
