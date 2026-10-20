"""El overlay completo (como Overwolf): la app entera encima del juego."""

import unittest
from unittest import mock

import ayuda
from roleplay import ajustes, database
from roleplay.models import PlayerProfile


class TestOverlayCompleto(ayuda.PruebaDeInterfaz):
    def setUp(self):
        super().setUp()
        from roleplay.ui import overlay_completo
        from roleplay.ui.menu import MainMenuWindow

        self.modulo = overlay_completo
        ajustes.guardar(overlay={})  # (ajustes.json es el mismo en todas las pruebas)
        database.save_profile(PlayerProfile(nombre_jugador="Simon Canales", club_actual="Man Utd"))
        self.ventana = MainMenuWindow()
        self.ventana.vigilante.detener()
        ayuda.esperar_tareas()
        self.addCleanup(self.ventana.deleteLater)
        self.addCleanup(lambda: self.ventana.overlay.cerrar())

    def test_abrir_la_pone_encima_sin_bordes_y_lista_para_usar(self):
        self.ventana.overlay.abrir()
        flags = self.ventana.windowFlags()
        self.assertTrue(self.ventana.overlay.abierto)
        self.assertTrue(self.ventana.isVisible())
        self.assertTrue(flags & self.modulo.Qt.WindowType.FramelessWindowHint)
        self.assertTrue(flags & self.modulo.Qt.WindowType.WindowStaysOnTopHint)
        self.assertTrue(self.ventana.isFullScreen())
        self.assertFalse(self.ventana.barra_overlay.isHidden())  # "volver al juego"
        self.assertAlmostEqual(self.ventana.windowOpacity(), self.modulo.OPACIDAD, places=2)

    def test_cerrar_la_deja_como_estaba(self):
        flags = self.ventana.windowFlags()
        self.ventana.overlay.abrir()
        self.ventana.volver_al_juego_btn.click()
        self.assertFalse(self.ventana.overlay.abierto)
        self.assertFalse(self.ventana.isVisible())  # estaba escondida: vuelve a estarlo
        self.assertEqual(self.ventana.windowFlags(), flags)
        self.assertTrue(self.ventana.barra_overlay.isHidden())
        self.assertEqual(self.ventana.windowOpacity(), 1.0)

    def test_si_estaba_abierta_vuelve_a_ser_la_ventana_de_siempre(self):
        self.ventana.show()
        self.ventana.overlay.abrir()
        self.ventana.overlay.cerrar()
        self.assertTrue(self.ventana.isVisible())
        self.assertFalse(self.ventana.isFullScreen())

    def test_esc_y_cerrar_la_ventana_vuelven_al_juego(self):
        self.ventana.overlay.abrir()
        self.ventana.overlay._esc.activated.emit()
        self.assertFalse(self.ventana.overlay.abierto)
        self.ventana.overlay.abrir()
        self.ventana.close()  # en el overlay, cerrar no cierra la app
        self.assertFalse(self.ventana.overlay.abierto)

    def test_el_atajo_abre_el_overlay_o_la_sala_segun_ajustes(self):
        self.ventana._on_atajo()
        self.assertTrue(self.ventana.overlay.abierto)
        self.ventana._on_atajo()
        self.assertFalse(self.ventana.overlay.abierto)
        ajustes.guardar(overlay={"modo": "sala"})
        with mock.patch.object(self.ventana.sala_flotante, "atajo_presionado") as sala:
            self.ventana._on_atajo()
        sala.assert_called_once()
        self.assertFalse(self.ventana.overlay.abierto)

    def test_la_configuracion_se_acota(self):
        ajustes.guardar(overlay={"modo": "cualquiera", "opacidad": 0.1})
        self.assertEqual(self.modulo.configuracion(), {"modo": "completo", "opacidad": self.modulo.OPACIDAD_MINIMA})

    def test_ajustes_guarda_el_modo_y_la_transparencia(self):
        from roleplay.ui.ajustes import DialogoAjustes

        dialogo = DialogoAjustes()
        dialogo.overlay_modo.setCurrentIndex(1)
        dialogo.overlay_opacidad.setValue(85)
        self.assertEqual(ajustes.leer()["overlay"], {"modo": "sala", "opacidad": 0.85})
        dialogo.deleteLater()


if __name__ == "__main__":
    unittest.main()
