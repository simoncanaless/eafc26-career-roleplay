"""Sala flotante (encima del juego) y atajo global."""

import ctypes
import sys
import unittest
from unittest import mock

import ayuda
from roleplay import ajustes, config, database
from roleplay.models import NoticiaPrensa, PlayerProfile
from roleplay.servicios.entrevista import ReaccionPrensa


class TestSalaFlotante(ayuda.PruebaDeInterfaz):
    def setUp(self):
        super().setUp()
        database.save_profile(PlayerProfile(nombre_jugador="Simon Canales", club_actual="Man Utd"))
        from roleplay.ui import entrevista
        from roleplay.ui.overlay import SalaFlotante

        self.modulo = entrevista
        self.sala = entrevista.InterviewWindow()
        ayuda.esperar_tareas()
        self.flotante = SalaFlotante(self.sala)

    def _con_preguntas(self, preguntas=("P1 <difícil>?", "P2?")):
        with mock.patch.object(self.modulo, "generar_entrevista", return_value=list(preguntas)):
            self.flotante.generar_btn.click()  # el boton del panel usa la sala
            ayuda.esperar_tareas()

    def test_refleja_las_preguntas_y_comparte_las_respuestas(self):
        self.assertFalse(self.flotante.enviar_btn.isVisibleTo(self.flotante))
        self._con_preguntas()
        self.assertEqual(len(self.flotante._edits), 2)
        self.assertTrue(self.flotante.enviar_btn.isVisibleTo(self.flotante))
        texto_pregunta = self.flotante._textos[0].text()
        self.assertIn("P1 &lt;difícil&gt;?", texto_pregunta)  # escapado

        self.flotante._edits[0].setPlainText("desde el panel")
        self.assertEqual(self.sala._respuesta_edits[0].toPlainText(), "desde el panel")
        self.sala._respuesta_edits[1].setPlainText("desde la sala")
        self.assertEqual(self.flotante._edits[1].toPlainText(), "desde la sala")

    def test_enviar_desde_el_panel_y_ver_la_reaccion_y_las_noticias(self):
        self._con_preguntas(("P1?",))
        self.flotante._edits[0].setPlainText("Contento")
        reaccion = ReaccionPrensa(reaccion_prensa="Cayo muy bien", delta_reputacion=4)
        noticias = {"noticias": [NoticiaPrensa(titular="Canales, figura")], "hitos": [], "estado_prensa": {}}
        with mock.patch.object(self.modulo, "evaluar_respuestas", return_value=reaccion), \
                mock.patch.object(self.modulo, "revisar_prensa", return_value=noticias):
            self.flotante.enviar_btn.click()
            ayuda.esperar_tareas()
            ayuda.esperar_tareas()
        self.assertTrue(self.flotante.reaccion_label.isVisibleTo(self.flotante))
        self.assertIn("Cayo muy bien", self.flotante.reaccion_label.text())
        self.assertIn("Canales, figura", self.flotante.noticias_label.text())

    def test_se_muestra_arriba_a_la_derecha_y_se_alterna(self):
        self.flotante.alternar()
        self.assertTrue(self.flotante.isVisible())
        self.flotante.alternar()
        self.assertFalse(self.flotante.isVisible())


class TestMenuConSalaFlotante(ayuda.PruebaDeInterfaz):
    def _ventana_y_lectura(self):
        import fabrica_partida as f
        from roleplay.partida.carrera import construir
        from roleplay.servicios import partida_real
        from roleplay.ui.menu import MainMenuWindow

        database.save_profile(PlayerProfile(nombre_jugador="Simon Canales", club_actual="Man Utd"))
        ventana = MainMenuWindow()
        ventana.vigilante.detener()
        ayuda.esperar_tareas()
        carrera = construir(f.construir_bytes(partido_nuevo=True))
        lectura = partida_real.LecturaPartida(carrera, partida_real.ultimo_partido(carrera, {}), "", False)
        return ventana, lectura

    def test_aparece_sola_al_terminar_un_partido(self):
        ventana, lectura = self._ventana_y_lectura()
        with mock.patch.object(ventana.pagina_entrevistas, "recibir_partido_nuevo", return_value=True), \
                mock.patch.object(ventana.pagina_entrevistas, "_iniciar_revision_prensa"):
            ventana._on_partido_nuevo(lectura)
        self.assertTrue(ventana.sala_flotante.isVisible())
        ventana.close()
        self.assertFalse(ventana.sala_flotante.isVisible())

    def test_no_aparece_si_se_apago(self):
        ventana, lectura = self._ventana_y_lectura()
        archivo = config.DB_PATH.parent / "ajustes.json"
        with mock.patch.object(config, "ARCHIVO_AJUSTES", archivo), \
                mock.patch.object(ventana.pagina_entrevistas, "recibir_partido_nuevo", return_value=True), \
                mock.patch.object(ventana.pagina_entrevistas, "_iniciar_revision_prensa"):
            ajustes.guardar(en_vivo={"flotante": False})
            ventana._on_partido_nuevo(lectura)
        self.assertFalse(ventana.sala_flotante.isVisible())
        ventana.close()


@unittest.skipUnless(sys.platform == "win32", "el atajo global es de Windows")
class TestAtajoGlobal(unittest.TestCase):
    def test_el_atajo_llega_a_la_app(self):
        ayuda.qapp()
        from roleplay.ui.atajo import ID_ATAJO, WM_HOTKEY, AtajoGlobal

        # las ventanas de otras pruebas (mismo hilo) pudieron quedarse con la combinacion
        ctypes.windll.user32.UnregisterHotKey(None, ID_ATAJO)
        atajo = AtajoGlobal()
        if not atajo.registrar():
            self.skipTest("La combinacion ya esta tomada (¿la app esta abierta?)")
        self.addCleanup(atajo.liberar)
        veces = []
        atajo.presionado.connect(lambda: veces.append(1))
        ctypes.windll.user32.PostThreadMessageW(ctypes.windll.kernel32.GetCurrentThreadId(), WM_HOTKEY, ID_ATAJO, 0)
        for _ in range(5):
            ayuda.qapp().processEvents()
        self.assertEqual(veces, [1])
        atajo.liberar()
        self.assertFalse(atajo.activo)


if __name__ == "__main__":
    unittest.main()
