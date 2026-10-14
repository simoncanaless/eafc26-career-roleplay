"""Modo en vivo: vigilar la partida, avisar partidos nuevos y hitos reales."""

import os
import tempfile
import time
import unittest
from datetime import date
from pathlib import Path
from unittest import mock

import ayuda
import fabrica_partida as f
from roleplay import ajustes, config, database
from roleplay.models import PlayerProfile
from roleplay.partida import lector
from roleplay.partida.carrera import construir
from roleplay.servicios import partida_real


class TestHitosReales(unittest.TestCase):
    def setUp(self):
        self.c = construir(f.construir_bytes())

    def test_cada_hito_sale_una_vez(self):
        hitos, estado = partida_real.detectar_hitos_reales(self.c, None)
        self.assertEqual(
            hitos,
            [
                {"tipo": "goles_temporada", "valor": 5},  # 8 goles: paso los 5
                {"tipo": "lider_goleadores", "valor": "Premier League"},
                {"tipo": "partidazo", "valor": "5 goles en el Man Utd 5-3 Sunderland"},
            ],
        )
        self.assertEqual(partida_real.detectar_hitos_reales(self.c, estado)[0], [])

    def test_liderato_que_se_pierde_y_temporada_nueva(self):
        _, estado = partida_real.detectar_hitos_reales(self.c, None)
        estado["club_lider"] = True  # la vez pasada iba primero; ahora va segundo
        hitos, estado = partida_real.detectar_hitos_reales(self.c, estado)
        self.assertEqual(hitos, [{"tipo": "perdio_liderato", "valor": "Premier League"}])
        estado["temporada"] = "2025/26"  # otra temporada: los goles se cuentan de nuevo
        hitos, _ = partida_real.detectar_hitos_reales(self.c, estado)
        self.assertIn({"tipo": "goles_temporada", "valor": 5}, hitos)

    def test_temporada_de(self):
        self.assertEqual(partida_real.temporada_de(date(2027, 1, 16)), "2026/27")
        self.assertEqual(partida_real.temporada_de(date(2026, 8, 1)), "2026/27")


class ConPartidaEnCarpeta(ayuda.PruebaDeInterfaz):
    def setUp(self):
        super().setUp()
        carpeta = tempfile.TemporaryDirectory()
        self.addCleanup(carpeta.cleanup)
        self.carpeta = Path(carpeta.name)
        for objeto, nombre, valor in (
            (lector, "CARPETA_GUARDADOS", self.carpeta),
            (config, "ARCHIVO_AJUSTES", self.carpeta / "ajustes.json"),
        ):
            parche = mock.patch.object(objeto, nombre, valor)
            parche.start()
            self.addCleanup(parche.stop)
        self.pid = database.save_profile(PlayerProfile(nombre_jugador="Simon Canales", club_actual="Man Utd"))
        self.guardado = self.carpeta / "CmPlr20260101"
        self._guardar(partido_nuevo=False)

    def _guardar(self, partido_nuevo: bool):
        self.guardado.write_bytes(f.construir_bytes(partido_nuevo=partido_nuevo))
        momento = time.time() + (10 if partido_nuevo else 0)
        os.utime(self.guardado, (momento, momento))


class TestVigilante(ConPartidaEnCarpeta):
    def _vigilante(self):
        from roleplay.ui.vigilante import VigilantePartida

        vigilante = VigilantePartida(intervalo_ms=60_000)
        self.nuevos, self.actualizaciones = [], []
        vigilante.partido_nuevo.connect(self.nuevos.append)
        vigilante.partida_actualizada.connect(self.actualizaciones.append)
        return vigilante

    def _dos_vueltas(self, vigilante):
        vigilante.revisar()  # ve el cambio
        vigilante.revisar()  # sigue igual: lo lee
        ayuda.esperar_tareas()

    def test_avisa_solo_los_partidos_nuevos(self):
        vigilante = self._vigilante()
        self._dos_vueltas(vigilante)
        self.assertEqual(len(self.actualizaciones), 1)
        self.assertEqual(self.nuevos, [])  # la primera lectura solo marca donde estamos
        self.assertEqual(database.get_estado_partida(self.pid)["avisado"], "2027-01-16|808|11|106")

        self._dos_vueltas(vigilante)  # nada cambio: ni siquiera se vuelve a leer
        self.assertEqual(len(self.actualizaciones), 1)

        self._guardar(partido_nuevo=True)  # el juego guardo despues de un partido
        vigilante.revisar()
        ayuda.esperar_tareas()
        self.assertEqual(self.nuevos, [])  # todavia puede estar escribiendo: espera una vuelta
        vigilante.revisar()
        ayuda.esperar_tareas()
        self.assertEqual(len(self.nuevos), 1)
        self.assertEqual(self.nuevos[0].ultimo.resumen, "Man Utd 2-1 Arsenal · Premier League · 23-01-2027")

    def test_apagado_no_lee_nada(self):
        ajustes.guardar(en_vivo={"vigilar": False})
        vigilante = self._vigilante()
        self._dos_vueltas(vigilante)
        self.assertEqual(self.actualizaciones, [])

    def test_una_partida_rota_se_reintenta(self):
        self.guardado.write_bytes(b"FBCHUNKS a medio escribir")
        vigilante = self._vigilante()
        self._dos_vueltas(vigilante)
        self.assertEqual(self.actualizaciones, [])
        self._guardar(partido_nuevo=False)
        self._dos_vueltas(vigilante)
        self.assertEqual(len(self.actualizaciones), 1)


class TestSalaEnVivo(ConPartidaEnCarpeta):
    def setUp(self):
        super().setUp()
        from roleplay.ui import entrevista

        self.modulo = entrevista
        self.pagina = entrevista.InterviewWindow()
        ayuda.esperar_tareas()
        self._guardar(partido_nuevo=True)
        self.lectura = partida_real.leer_para_entrevista(self.pid)

    def test_libre_carga_el_partido_y_prepara_las_preguntas(self):
        with mock.patch.object(self.modulo, "generar_entrevista", return_value=["P1?"]) as generar:
            self.assertTrue(self.pagina.recibir_partido_nuevo(self.lectura, preparar_preguntas=True))
            ayuda.esperar_tareas()
        stats = self.pagina._leer_stats_desde_formulario()
        self.assertEqual((stats.equipo_rival, stats.goles_equipo, stats.goles_rival, stats.goles_jugador), ("Arsenal", 2, 1, 2))
        generar.assert_called_once()
        self.assertEqual(self.pagina._preguntas, ["P1?"])

    def test_ocupada_no_se_le_pisa_la_entrevista(self):
        with mock.patch.object(self.modulo, "generar_entrevista", return_value=["P1?"]):
            self.pagina.generar_entrevista_btn.click()
            ayuda.esperar_tareas()
        self.pagina._respuesta_edits[0].setPlainText("a medio responder")
        with mock.patch.object(self.modulo, "generar_entrevista") as generar:
            self.assertFalse(self.pagina.recibir_partido_nuevo(self.lectura, preparar_preguntas=True))
        generar.assert_not_called()
        self.assertEqual(self.pagina._respuesta_edits[0].toPlainText(), "a medio responder")
        self.assertIn("Man Utd 2-1 Arsenal", self.pagina.partida_label.text())  # pero avisa


class TestMenuEnVivo(ConPartidaEnCarpeta):
    def test_un_partido_nuevo_marca_la_sala_y_mueve_la_prensa(self):
        from roleplay.ui.menu import MainMenuWindow

        ventana = MainMenuWindow()
        ventana.vigilante.detener()
        ayuda.esperar_tareas()
        self._guardar(partido_nuevo=True)
        lectura = partida_real.leer_para_entrevista(self.pid)
        sala = ventana.pagina_entrevistas
        with mock.patch.object(sala, "recibir_partido_nuevo", return_value=True) as recibir, \
                mock.patch.object(sala, "_iniciar_revision_prensa") as prensa:
            ventana._on_partido_nuevo(lectura)
        recibir.assert_called_once()
        prensa.assert_called_once_with(manual=False)
        self.assertIn("●", ventana._botones_nav[ventana.PAGINA_ENTREVISTAS].text())
        ventana._ir_a(ventana.PAGINA_ENTREVISTAS)
        self.assertNotIn("●", ventana._botones_nav[ventana.PAGINA_ENTREVISTAS].text())


if __name__ == "__main__":
    unittest.main()
