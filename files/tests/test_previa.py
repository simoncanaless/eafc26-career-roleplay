"""Conferencia de prensa previa al proximo partido."""

import unittest
from unittest import mock

import ayuda
from roleplay.servicios.entrevista import ReaccionPrensa
import fabrica_partida as f
from roleplay import database
from roleplay.models import PlayerProfile
from roleplay.partida.carrera import construir
from roleplay.servicios import entrevista, partida_real, previa
from roleplay.servicios.previa import PreviaPartido, ReaccionPrevia, previa_del_proximo


def carrera_falsa():
    return construir(f.construir_bytes(), "falsa")


class TestPreviaDelProximo(ayuda.PruebaConBase):
    def test_los_datos_salen_de_la_partida(self):
        p = previa_del_proximo(carrera_falsa())
        self.assertEqual((p.club, p.rival, p.de_local, p.fecha), ("Man Utd", "SSC Napoli", False, "20-01-2027"))
        self.assertEqual(p.clave, "2027-01-20|122|48|11")
        self.assertEqual(p.resumen, "vs SSC Napoli (de visita) · torneo continental · 20-01-2027")
        texto = "\n".join(p.datos)
        for esperado in (
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
        # a la IA se le dice quien es quien (una nota lo culpo del goleador del rival y le dio los goles del 7-0)
        from roleplay.servicios import ia, previa

        contexto = previa._contexto(p)
        self.assertIn("El jugador juega en Man Utd; el rival es Manchester City.", contexto)
        self.assertIn("Los marcadores son de los equipos", contexto)
        self.assertIn("lo de un rival (su goleador, su racha, su mal momento) es del rival", ia.REGLAS)

    def test_sin_proximo_partido_no_hay_previa(self):
        c = carrera_falsa()
        c.partidos[:] = [p for p in c.partidos if p.jugado]
        self.assertIsNone(previa_del_proximo(c))

    def test_la_lectura_de_la_sala_trae_la_previa(self):
        c = carrera_falsa()
        with mock.patch("roleplay.partida.lector.carrera_actual", return_value=c):
            lectura = partida_real.leer_para_entrevista(database.save_profile(PlayerProfile(nombre_jugador="Simon")))
        self.assertEqual(lectura.previa.rival, "SSC Napoli")


class TestPreguntasYEvaluacion(ayuda.PruebaConBase):
    def setUp(self):
        super().setUp()
        self.perfil = PlayerProfile(nombre_jugador="Simon Canales", club_actual="Man Utd")
        self.perfil.id = database.save_profile(self.perfil)
        self.previa = PreviaPartido("clave", "Man Utd", "Spurs", True, "Premier League", "24-01-2027",
                                    ["En la tabla: Man Utd 2° con 55 pts, Spurs 8° con 32 pts (de 20 equipos)."],
                                    posicion="2°", posicion_rival="8°", racha_club="G G E", racha_rival="P P G",
                                    puesto=2, puesto_rival=8, puntos=55, puntos_rival=32)

    def test_tres_periodistas_con_los_datos_reales(self):
        preguntas = previa.generar_previa(self.perfil, self.previa)
        self.assertEqual(sorted(p.split(" (")[0] for p in preguntas), sorted(n for n, _ in entrevista.PERIODISTAS))
        for pregunta in preguntas:
            self.assertNotRegex(pregunta, r"[{}]|#\w+#")
        self.assertTrue(any(dato in p for p in preguntas for dato in ("2°", "GGE", "G G E", "Spurs")), preguntas)  # usa la partida

    def test_la_evaluacion_se_acota(self):
        humilde = "El equipo, el grupo, mis companeros, todos juntos, gracias al cuerpo tecnico y al grupo. " * 6
        r = previa.evaluar_previa(self.perfil, self.previa, [("P?", humilde)])
        self.assertEqual((r.eje, r.tono), ("humildad_equipo", "positiva"))
        self.assertTrue(0 < r.delta_reputacion <= previa.DELTA_REPUTACION_MAXIMO)
        self.assertIn("Spurs", r.titular)
        excusas = "El arbitro nos robo, la cancha estaba horrible, el calendario es una verguenza, culpa del arbitro. " * 6
        r = previa.evaluar_previa(self.perfil, self.previa, [("P?", excusas)])
        self.assertEqual(r.eje, "excusa_polemica")
        self.assertTrue(-previa.DELTA_REPUTACION_MAXIMO <= r.delta_reputacion < 0)

    def test_la_nota_de_la_ia_no_trae_al_goleador_del_rival_si_el_no_lo_nombro(self):
        self.previa.goleador = "Robert Bozenik"
        culpa = {"titular": "Canales, en duda", "reaccion_prensa": "Genera dudas tras el bajo rendimiento de Boženík.",
                 "delta_reputacion": -3, "delta_carino": 0, "cita": "", "nuevo_gancho_narrativo": ""}
        bien = dict(culpa, reaccion_prensa="Respondio corto y la sala lo noto.")
        respuestas = [("P?", "Jugar como siempre nada mas, el equipo esta bien y vamos a buscar los tres puntos.")]
        with mock.patch("roleplay.servicios.ia.pedir_json", return_value=culpa):
            r = previa.evaluar_previa(self.perfil, self.previa, respuestas)
        self.assertNotIn("bajo rendimiento", r.reaccion_prensa)  # quedo la del motor local
        with mock.patch("roleplay.servicios.ia.pedir_json", return_value=bien):
            self.assertEqual(previa.evaluar_previa(self.perfil, self.previa, respuestas).reaccion_prensa,
                             "Respondio corto y la sala lo noto.")

    def test_una_respuesta_seca_no_se_cita(self):
        r = previa.evaluar_previa(self.perfil, self.previa, [("P?", "Si.")])
        self.assertEqual(r.cita, "")
        self.assertNotIn("«", r.titular)
        self.assertIn("Spurs", r.titular)


class TestSalaConPrevia(ayuda.PruebaDeInterfaz):
    def setUp(self):
        super().setUp()
        self.pid = database.save_profile(PlayerProfile(nombre_jugador="Simon Canales", club_actual="Man Utd"))
        from roleplay.ui import entrevista

        self.modulo = entrevista
        carrera = carrera_falsa()
        self.lectura = partida_real.LecturaPartida(
            carrera=carrera, ultimo=partida_real.ultimo_partido(carrera, {}),
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

    def test_despues_de_la_entrevista_se_puede_pasar_a_la_previa_y_no_se_repite(self):
        sala = self.sala
        sala._on_cargar_partida_clicked()
        with mock.patch.object(self.modulo, "generar_entrevista", return_value=["P1?"]):
            sala.generar_entrevista_btn.click()
            ayuda.esperar_tareas()
        sala._respuesta_edits[0].setPlainText("Ganamos con el corazon")
        self.assertFalse(sala.modo_previa_btn.isEnabled())  # a medias: no se pisa
        reaccion = ReaccionPrensa(reaccion_prensa="Bien ahi", delta_reputacion=2)
        self.lectura.ya_entrevistado = True  # lo que dira la partida al releerla
        with mock.patch.object(self.modulo, "evaluar_respuestas", return_value=reaccion), \
                mock.patch.object(self.modulo, "revisar_prensa_con_partida", return_value={"noticias": [], "hitos": [], "estado_prensa": {}}):
            sala.enviar_respuestas_btn.click()
            ayuda.esperar_tareas()
            ayuda.esperar_tareas()
        self.assertFalse(sala.ocupada())  # hecha, no a medias
        self.assertTrue(sala._respuesta_edits[0].isReadOnly())
        self.assertFalse(sala.enviar_respuestas_btn.isEnabled())
        self.assertFalse(sala.generar_entrevista_btn.isEnabled())  # ese partido ya tuvo su entrevista
        self.assertEqual(sala.generar_entrevista_btn.text(), self.modulo.TEXTO_YA_HECHA)
        self.assertTrue(sala.modo_previa_btn.isEnabled())

        sala.modo_previa_btn.click()
        self.assertEqual(sala._modo, "previa")
        self.assertTrue(sala.generar_entrevista_btn.isEnabled())
        self.lectura.previa.ya_hecha = True  # la previa ya dada tampoco se repite
        sala._refrescar_botones()
        self.assertFalse(sala.generar_entrevista_btn.isEnabled())
        self.assertEqual(sala.generar_entrevista_btn.text(), self.modulo.TEXTO_YA_HECHA_PREVIA)
        sala.modo_post_btn.click()
        self.assertFalse(sala.generar_entrevista_btn.isEnabled())

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
