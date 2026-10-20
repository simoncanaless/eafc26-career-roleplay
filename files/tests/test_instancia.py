"""Una sola app abierta: la segunda le avisa a la primera y se cierra."""

import os
import time
import unittest
from unittest import mock

import ayuda
from PySide6.QtWidgets import QApplication

from roleplay.ui import instancia


def esperar(condicion, segundos=3.0):
    fin = time.monotonic() + segundos
    while not condicion() and time.monotonic() < fin:
        QApplication.processEvents()
        time.sleep(0.01)


class TestUnaSola(ayuda.PruebaDeInterfaz):
    def setUp(self):
        super().setUp()
        self.nombre = f"EAFC26Roleplay-prueba-{os.getpid()}-{self._testMethodName}"

    def test_la_segunda_le_avisa_a_la_primera_y_no_abre(self):
        primera = instancia.UnaSola(self.nombre)
        self.addCleanup(primera.deleteLater)
        avisos = []
        primera.mostrar.connect(lambda: avisos.append(1))
        self.assertTrue(primera.tomar())
        segunda = instancia.UnaSola(self.nombre)
        self.addCleanup(segunda.deleteLater)
        self.assertFalse(segunda.tomar())
        esperar(lambda: avisos)
        self.assertEqual(avisos, [1])

    def test_al_reiniciar_espera_que_la_vieja_se_cierre(self):
        vieja = instancia.UnaSola(self.nombre)
        self.assertTrue(vieja.tomar())
        nueva = instancia.UnaSola(self.nombre)
        self.addCleanup(nueva.deleteLater)
        vueltas = []

        def cerrar_la_vieja(segundos):
            vueltas.append(segundos)
            vieja._servidor.close()

        with mock.patch.dict(os.environ, {instancia.VARIABLE_REINICIO: "1"}), \
                mock.patch.object(instancia.time, "sleep", cerrar_la_vieja):
            self.assertTrue(nueva.tomar())
            self.assertNotIn(instancia.VARIABLE_REINICIO, os.environ)  # (no pasa a los hijos)
        self.assertEqual(len(vueltas), 1)
        vieja.deleteLater()


if __name__ == "__main__":
    unittest.main()
