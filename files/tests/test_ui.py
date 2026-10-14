import threading
import unittest
from unittest import mock

import ayuda
from roleplay import database
from roleplay.models import PlayerProfile
from roleplay.servicios.entrevista import ReaccionPrensa
from roleplay.servicios.instagram import ComentarioIA, InstagramReaccionIA
from roleplay.servicios.vision import MatchStats


class TestHilos(unittest.TestCase):
    """Los dos cierres de la app que se reprodujeron en el codigo original.
    Corren en otro proceso: si vuelven, se cae ese proceso y no la bateria."""

    def _sin_caida(self, codigo: str):
        proceso = ayuda.correr_aislado(codigo)
        self.assertEqual(
            proceso.returncode, 0, f"La app se cerro (codigo {proceso.returncode}).\n{proceso.stderr}"
        )
        self.assertIn("FIN", proceso.stdout)

    def test_cancelar_el_asistente_mientras_genera_el_backstory(self):
        self._sin_caida(
            """
import gc, tempfile, time
from pathlib import Path
from roleplay import config, database
config.DB_PATH = Path(tempfile.mkdtemp()) / "p.db"; database.init_db()
app = ayuda.qapp()
from roleplay.servicios.backstory import BackstoryResult
from roleplay.ui import personaje
personaje.generar_backstory = lambda p: (time.sleep(1), BackstoryResult(backstory="b", ganchos_narrativos=[]))[1]

def abrir_y_cancelar():
    wizard = personaje.CharacterWizard()
    wizard.pagina_basicos.nombre_edit.setText("Simon")
    wizard.pagina_backstory._on_generar_clicked()
    wizard.reject()

abrir_y_cancelar()
gc.collect()
ayuda.esperar_tareas()
print("FIN")
"""
        )

    def test_dos_revisiones_de_prensa_a_la_vez(self):
        self._sin_caida(
            """
import gc, tempfile, time
from pathlib import Path
from unittest import mock
from roleplay import config, database
from roleplay.models import PlayerProfile
config.DB_PATH = Path(tempfile.mkdtemp()) / "p.db"; database.init_db()
database.save_profile(PlayerProfile(nombre_jugador="Simon"))
app = ayuda.qapp()
from roleplay.ui import entrevista
llamadas = []
def revisar_lenta(perfil, historial, estado):
    llamadas.append(1); time.sleep(0.5)
    return {"noticias": [], "hitos": [], "estado_prensa": estado}
entrevista.revisar_prensa = revisar_lenta
pagina = entrevista.InterviewWindow()
pagina._on_revisar_prensa_clicked()
pagina._iniciar_revision_prensa(manual=False)
gc.collect()
ayuda.esperar_tareas()
assert len(llamadas) == 1, llamadas
print("FIN")
"""
        )


class TestEntrevista(ayuda.PruebaDeInterfaz):
    def setUp(self):
        super().setUp()
        self.pid = database.save_profile(
            PlayerProfile(nombre_jugador="Simon", club_actual="Palermo", reputacion_inicial=40)
        )
        from roleplay.ui import entrevista

        self.modulo = entrevista
        self.pagina = entrevista.InterviewWindow()

    def test_se_puede_generar_la_entrevista_sin_capturar_la_pantalla(self):
        self.assertTrue(self.pagina.generar_entrevista_btn.isEnabled())

    def test_flujo_completo_guarda_lo_que_se_evaluo(self):
        p = self.pagina
        p.equipo_rival_edit.setText("Juventus")
        p.goles_jugador_spin.setValue(2)
        p.rating_spin.setValue(8.6)

        with mock.patch.object(self.modulo, "generar_entrevista", return_value=["P1?", "P2?"]):
            p.generar_entrevista_btn.click()
            ayuda.esperar_tareas()
        self.assertEqual(len(p._respuesta_edits), 2)
        p._respuesta_edits[0].setPlainText("Contento por el equipo")

        liberar = threading.Event()

        def gemini_lento(prompt, esquema, que_hacer, api_key=None):
            liberar.wait(5)
            return ReaccionPrensa(
                reaccion_prensa="Cayo bien <3", delta_reputacion=99, nuevo_gancho_narrativo="Lo quiere el Madrid"
            )

        from roleplay.servicios import entrevista as servicio

        prensa = mock.Mock(return_value={"noticias": [], "hitos": [], "estado_prensa": {"ok": 1}})
        with mock.patch.object(servicio, "generar_json", gemini_lento), \
                mock.patch.object(self.modulo, "revisar_prensa", prensa):
            p.enviar_respuestas_btn.click()
            # mientras Gemini evalua: no se puede regenerar, ni aunque se
            # vuelva a la pestana; y tocar el formulario no cambia lo guardado
            self.assertFalse(p.generar_entrevista_btn.isEnabled())
            p.actualizar()
            self.assertFalse(p.generar_entrevista_btn.isEnabled())
            p.equipo_rival_edit.setText("Otro rival")
            p._respuesta_edits[0].setPlainText("Otra respuesta")
            liberar.set()
            ayuda.esperar_tareas()
            ayuda.esperar_tareas()  # la revision de prensa automatica

        partido = database.load_match_interviews(self.pid)[0]
        self.assertEqual((partido.equipo_rival, partido.goles_jugador, partido.rating_jugador), ("Juventus", 2, 8.6))
        self.assertEqual(partido.preguntas_entrevista, ["P1?", "P2?"])
        self.assertEqual(partido.respuestas_jugador, ["Contento por el equipo", ""])
        self.assertEqual(partido.delta_reputacion, 15)  # acotado
        self.assertEqual(database.get_reputacion_actual(self.pid), 55)
        self.assertIn("Lo quiere el Madrid", database.load_profile(self.pid).ganchos_narrativos)
        self.assertIn("Cayo bien <3", ayuda.texto_visible(p.reaccion_label.text()))
        prensa.assert_called_once()
        self.assertEqual(database.get_estado_prensa(self.pid), {"ok": 1})
        self.assertTrue(p.generar_entrevista_btn.isEnabled())

    def test_no_se_envia_sin_ninguna_respuesta(self):
        with mock.patch.object(self.modulo, "generar_entrevista", return_value=["P1?"]):
            self.pagina.generar_entrevista_btn.click()
            ayuda.esperar_tareas()
        with mock.patch.object(self.modulo, "evaluar_respuestas") as evaluar:
            self.pagina.enviar_respuestas_btn.click()
        evaluar.assert_not_called()
        self.avisos.assert_called_once()

    def test_la_captura_carga_las_stats_en_el_formulario(self):
        stats = MatchStats(goles_equipo=3, goles_rival=1, equipo_rival="Inter", rating_jugador=7.9)
        with mock.patch.object(self.modulo, "_capturar_y_leer", return_value=stats):
            self.pagina.capturar_btn.click()
            ayuda.esperar_tareas()
        self.assertEqual(self.pagina._leer_stats_desde_formulario().equipo_rival, "Inter")
        self.assertAlmostEqual(self.pagina.rating_spin.value(), 7.9)

    def test_si_la_captura_falla_se_avisa_y_se_puede_seguir(self):
        with mock.patch.object(self.modulo, "_capturar_y_leer", side_effect=RuntimeError("sin dxcam")):
            self.pagina.capturar_btn.click()
            ayuda.esperar_tareas()
        self.assertIn("sin dxcam", self.avisos.call_args.args[2])
        self.assertTrue(self.pagina.capturar_btn.isEnabled())
        self.assertTrue(self.pagina.generar_entrevista_btn.isEnabled())


class TestInstagram(ayuda.PruebaDeInterfaz):
    def test_un_comentario_con_menor_que_se_ve_entero(self):
        pid = database.save_profile(PlayerProfile(nombre_jugador="Simon Canales", reputacion_inicial=40))
        from roleplay.ui import instagram

        pagina = instagram.InstagramWindow()
        reaccion = InstagramReaccionIA(
            comentarios=[ComentarioIA(autor="fan", texto="te amo crack <3 vamos por mas", tono="positivo")],
            likes_estimados=-4,  # la IA a veces inventa cosas raras
            crecimiento_seguidores=1500,
        )
        pagina.post_edit.setPlainText("Golazo hoy")
        with mock.patch.object(instagram, "generar_reaccion_post", return_value=reaccion):
            pagina.publicar_btn.click()
            ayuda.esperar_tareas()

        visible = ayuda.texto_visible(pagina.resultado_label.text())
        self.assertIn("te amo crack <3 vamos por mas", visible)
        self.assertIn("1.700 en total", visible)  # 200 de base + 1.500
        self.assertEqual(database.get_seguidores(pid), 1700)
        post = database.load_instagram_posts(pid)[0]
        self.assertEqual((post.texto, post.comentarios[0]["autor"]), ("Golazo hoy", "fan"))
        self.assertIn("@simoncanales", pagina.header_label.text())

    def test_likes_negativos_de_la_ia_quedan_en_cero(self):
        from roleplay.servicios import instagram as servicio

        reaccion = InstagramReaccionIA(comentarios=[], likes_estimados=-4, crecimiento_seguidores=0)
        with mock.patch.object(servicio, "generar_json", return_value=reaccion):
            resultado = servicio.generar_reaccion_post(PlayerProfile(nombre_jugador="S"), "x", 50, 100)
        self.assertEqual(resultado.likes_estimados, 0)


class TestPersonajeYMenu(ayuda.PruebaDeInterfaz):
    def test_se_puede_crear_el_personaje_escribiendo_el_backstory_a_mano(self):
        from roleplay.ui.personaje import CharacterWizard

        wizard = CharacterWizard()
        wizard.pagina_basicos.nombre_edit.setText("Simon")
        wizard.pagina_relacion.grupo.button(0).setChecked(True)  # novia real
        wizard.pagina_relacion.nombre_pareja_edit.setText("Javiera")
        self.assertFalse(wizard.pagina_backstory.isComplete())
        wizard.pagina_backstory.resultado_edit.setPlainText("Crecio en Quillota.")
        wizard.pagina_backstory.ganchos_edit.setPlainText("- gancho uno\n\n-gancho dos")
        self.assertTrue(wizard.pagina_backstory.isComplete())
        wizard.accept()

        perfil = database.load_latest_profile()
        self.assertEqual(perfil.backstory_generado, "Crecio en Quillota.")
        self.assertEqual(perfil.ganchos_narrativos, ["gancho uno", "gancho dos"])
        self.assertEqual((perfil.estado_relacion, perfil.nombre_pareja), ("novia_real", "Javiera"))

    def test_el_nombre_de_pareja_solo_cuenta_con_novia_real(self):
        from roleplay.ui.personaje import CharacterWizard

        wizard = CharacterWizard()
        wizard.pagina_relacion.nombre_pareja_edit.setText("Javiera")
        wizard.pagina_relacion.grupo.button(2).setChecked(True)  # soltero
        self.assertFalse(wizard.pagina_relacion.nombre_pareja_edit.isEnabled())
        self.assertEqual(wizard.construir_perfil().nombre_pareja, "")

    def test_el_resumen_no_le_cambia_las_comas_al_club(self):
        database.save_profile(
            PlayerProfile(nombre_jugador="Simon", club_actual="Union, La Calera", reputacion_inicial=400)
        )
        from roleplay.ui.menu import PaginaResumen

        pagina = PaginaResumen(lambda: None)
        pagina.actualizar()
        self.assertIn("Union, La Calera", pagina.stats_label.text())
        self.assertIn("2.000 seguidores", pagina.stats_label.text())

    def test_el_menu_navega_y_cada_pagina_va_en_un_scroll(self):
        from PySide6.QtWidgets import QScrollArea

        from roleplay.ui.menu import MainMenuWindow

        ventana = MainMenuWindow()
        for indice in range(3):
            ventana._ir_a(indice)
            self.assertIsInstance(ventana.stack.currentWidget(), QScrollArea)
            self.assertEqual([b.isChecked() for b in ventana._botones_nav], [i == indice for i in range(3)])

    def test_cada_modulo_abre_suelto(self):
        import app

        for modulo in app.MODULOS:
            with self.subTest(modulo=modulo):
                self.assertIsNotNone(app._crear_ventana(modulo))


class TestArranque(unittest.TestCase):
    def test_abrir_la_app_no_carga_gemini_ni_la_captura(self):
        proceso = ayuda.correr_aislado(
            "import sys, roleplay.ui.menu\n"
            "print(sorted(m for m in ('google.genai', 'cv2', 'dxcam') if m in sys.modules))"
        )
        self.assertEqual(proceso.returncode, 0, proceso.stderr)
        self.assertEqual(proceso.stdout.strip(), "[]")


if __name__ == "__main__":
    unittest.main()
