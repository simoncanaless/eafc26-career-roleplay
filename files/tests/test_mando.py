"""El mando de PS5 en el overlay: stick = cursor, X = apretar, circulo = volver al juego."""

import os
import unittest
from unittest import mock

import ayuda
from roleplay import ajustes, database
from roleplay.models import PlayerProfile
from roleplay.ui import mando
from roleplay.ui.mando import CIRCULO, CRUZ, L1, R1, DERECHA, EstadoMando, Traductor


def estado(x=0.0, y=0.0, der_y=0.0, botones=()):
    return EstadoMando((x, y, 0.0, der_y, 0.0, 0.0), frozenset(botones))


class TestTraductor(unittest.TestCase):
    def test_el_stick_mueve_el_cursor_y_la_zona_muerta_no(self):
        t = Traductor()
        self.assertEqual(t.traducir(estado(x=0.1, y=-0.1), 0.016), [])  # el stick suelto tiembla un poco
        accion = t.traducir(estado(x=1.0), 0.016)[0]
        self.assertEqual(accion[0], "mover")
        self.assertGreater(accion[1], 20)  # a fondo, rapido
        self.assertEqual(accion[2], 0)
        despacio = sum(a[1] for _ in range(10) for a in t.traducir(estado(x=0.3), 0.016) if a[0] == "mover")
        self.assertLess(despacio, 25)  # poquito, preciso

    def test_x_aprieta_y_suelta_una_vez(self):
        t = Traductor()
        self.assertEqual(t.traducir(estado(botones=[CRUZ]), 0.016), [("apretar",)])
        self.assertEqual(t.traducir(estado(botones=[CRUZ]), 0.016), [])  # mantenido: no repite
        self.assertEqual(t.traducir(estado(), 0.016), [("soltar",)])

    def test_circulo_vuelve_al_juego_y_l1_r1_cambian_de_seccion(self):
        t = Traductor()
        self.assertEqual(t.traducir(estado(botones=[CIRCULO]), 0.016), [("volver",)])
        self.assertEqual(t.traducir(estado(botones=[L1]), 0.016), [("seccion", -1)])
        self.assertEqual(t.traducir(estado(botones=[R1]), 0.016), [("seccion", 1)])

    def test_el_stick_derecho_es_la_rueda_y_la_cruceta_apunta_fino(self):
        t = Traductor()
        muescas = sum(a[1] for _ in range(30) for a in t.traducir(estado(der_y=1.0), 0.016) if a[0] == "rueda")
        self.assertLess(muescas, 0)  # para abajo
        t = Traductor()
        pixeles = sum(a[1] for _ in range(10) for a in t.traducir(estado(botones=[DERECHA]), 0.016) if a[0] == "mover")
        self.assertTrue(40 <= pixeles <= 70)

    def test_al_cerrar_no_queda_el_click_apretado(self):
        t = Traductor()
        t.traducir(estado(botones=[CRUZ]), 0.016)
        self.assertEqual(t.soltar_todo(), [("soltar",)])
        self.assertEqual(t.soltar_todo(), [])


class LectorFalso:
    def __init__(self):
        self.estados = []
        self.abierto = False

    def abrir(self):
        self.abierto = True
        return True

    def leer(self):
        return self.estados.pop(0) if self.estados else estado()

    def cerrar(self):
        self.abierto = False


class TestMandoEnElOverlay(ayuda.PruebaDeInterfaz):
    def setUp(self):
        super().setUp()
        from roleplay.ui.menu import MainMenuWindow

        ajustes.guardar(overlay={})
        database.save_profile(PlayerProfile(nombre_jugador="Simon Canales", club_actual="Man Utd"))
        self.ventana = MainMenuWindow()
        self.ventana.vigilante.detener()
        ayuda.esperar_tareas()
        self.addCleanup(self.ventana.deleteLater)
        self.addCleanup(lambda: self.ventana.overlay.cerrar())
        self.lector = LectorFalso()
        self.raton = mock.Mock()
        self.ventana.mando.lector = self.lector
        self.ventana.mando.raton = self.raton

    def test_se_prende_con_el_overlay_y_circulo_vuelve_al_juego(self):
        with mock.patch.dict(os.environ, {"EAFC_SIN_MANDO": ""}):
            self.ventana.overlay.abrir()
        self.assertTrue(self.lector.abierto)
        self.lector.estados = [estado(x=1.0), estado(botones=[CRUZ]), estado(), estado(botones=[R1]),
                               estado(), estado(botones=[CIRCULO])]
        for _ in range(6):
            self.ventana.mando._ultimo -= 0.016  # (un cuadro de 16 ms entre lecturas)
            self.ventana.mando._leer()
        hechas = [c.args[0][0] for c in self.raton.hacer.call_args_list]
        self.assertEqual(hechas, ["mover", "apretar", "soltar"])
        self.assertEqual(self.ventana.stack.currentIndex(), 1)  # R1: la seccion siguiente
        self.assertFalse(self.ventana.overlay.abierto)  # circulo
        self.assertFalse(self.lector.abierto)  # y el mando se suelta

    def test_apagado_en_ajustes_no_lee_el_mando(self):
        ajustes.guardar(overlay={"mando": False})
        with mock.patch.dict(os.environ, {"EAFC_SIN_MANDO": ""}):
            self.ventana.overlay.abrir()
        self.assertFalse(self.lector.abierto)

    def test_el_raton_no_hace_nada_si_el_overlay_no_esta_al_frente(self):
        raton = mando.RatonDeWindows(lambda: 123)
        with mock.patch.object(raton, "_boton") as boton:
            raton.hacer(("apretar",))  # offscreen / otra ventana al frente: nada
        boton.assert_not_called()


if __name__ == "__main__":
    unittest.main()
