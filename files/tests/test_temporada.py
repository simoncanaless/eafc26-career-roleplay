"""Pagina Temporada: tabla, goleadores y partidos sacados de la partida."""

import tempfile
from pathlib import Path
from unittest import mock

import ayuda
import fabrica_partida as f
from roleplay import database
from roleplay.partida import lector
from roleplay.partida.carrera import construir
from roleplay.servicios import partida_real
from roleplay.servicios.temporada import vista_temporada


class TestVistaTemporada(ayuda.PruebaConBase):
    def setUp(self):
        super().setUp()
        self.c = construir(f.construir_bytes(), "falsa")
        self.ia_jugadores = mock.patch.object(
            partida_real, "identificar_jugadores", return_value={f.HAALAND: ("Erling Haaland", True)}
        ).start()
        mock.patch.object(
            partida_real, "identificar_competiciones", return_value={f.CHAMPIONS: ("Champions League", True)}
        ).start()
        self.addCleanup(mock.patch.stopall)

    def test_la_liga_del_club_primero(self):
        v = vista_temporada(self.c)
        self.assertEqual((v.temporada, v.club, v.fecha), ("2026/27", "Man Utd", "16-01-2027"))
        self.assertEqual(v.competiciones, [(f.LIGA, "Premier League"), (f.CHAMPIONS, "Champions League")])
        self.assertEqual(v.competicion, f.LIGA)
        self.assertTrue(v.es_liga)

    def test_tabla_con_el_club_marcado(self):
        v = vista_temporada(self.c)
        self.assertEqual([fila.equipo for fila in v.tabla][:2], ["Manchester City", "Man Utd"])
        suya = v.tabla[1]
        self.assertTrue(suya.es_usuario)
        self.assertEqual((suya.posicion, suya.pj, suya.pts, suya.dif), (2, 2, 6, 3))
        self.assertEqual(v.posicion, 2)
        self.assertEqual(sum(fila.es_usuario for fila in v.tabla), 1)

    def test_goleadores_con_nombre_y_el_usuario_marcado(self):
        v = vista_temporada(self.c)
        self.assertEqual(
            [(g.nombre, g.goles, g.es_usuario) for g in v.goleadores][:2],
            [("Simon Canales", 6, True), ("Erling Haaland", 5, False)],
        )
        # el que la IA no reconocio se describe, no se inventa
        self.assertIn("el delantero centro del Arsenal", [g.nombre for g in v.goleadores])

    def test_resultados_proximos_y_ultima_fecha(self):
        v = vista_temporada(self.c)
        self.assertEqual([(p.marcador, p.resultado) for p in v.resultados], [("2-1", "G"), ("5-3", "G")])
        self.assertEqual(v.proximos, [])  # el proximo es de Champions
        self.assertEqual(v.titulo_ultima_fecha, "16/01")
        self.assertEqual(
            [(p.local, p.marcador, p.visita, p.es_usuario) for p in v.ultima_fecha],
            [("Man Utd", "5-3", "Sunderland", True), ("Manchester City", "2-0", "Arsenal", False)],
        )

    def test_una_copa_no_tiene_tabla(self):
        v = vista_temporada(self.c, f.CHAMPIONS)
        self.assertEqual(v.nombre_competicion, "Champions League")
        self.assertFalse(v.es_liga)
        self.assertEqual((v.tabla, v.posicion), ([], None))
        self.assertEqual([(p.marcador, p.resultado) for p in v.resultados], [("3-3", "E")])
        self.assertEqual([(p.local, p.visita, p.marcador) for p in v.proximos], [("SSC Napoli", "Man Utd", "vs")])

    def test_una_competicion_ajena_muestra_la_del_club(self):
        self.assertEqual(vista_temporada(self.c, 99999).competicion, f.LIGA)

    def test_sin_ia_se_ve_igual(self):
        self.ia_jugadores.side_effect = RuntimeError("sin cuota")
        v = vista_temporada(self.c)
        self.assertEqual(len(v.tabla), 5)
        self.assertIn("el delantero centro del Manchester City", [g.nombre for g in v.goleadores])
        self.assertEqual(database.get_nombres_conocidos("jugador", {f.HAALAND}), {})  # se pregunta la proxima


class TestPaginaTemporada(ayuda.PruebaDeInterfaz):
    def setUp(self):
        super().setUp()
        self.carpeta = tempfile.TemporaryDirectory()
        self.addCleanup(self.carpeta.cleanup)
        mock.patch.object(lector, "CARPETA_GUARDADOS", Path(self.carpeta.name)).start()
        mock.patch.object(partida_real, "identificar_jugadores", return_value={}).start()
        mock.patch.object(
            partida_real, "identificar_competiciones", return_value={f.CHAMPIONS: ("Champions League", True)}
        ).start()
        self.addCleanup(mock.patch.stopall)
        from roleplay.ui.temporada import PaginaTemporada

        self.pagina = PaginaTemporada()

    def _celda(self, fila: int, columna: int) -> str:
        """El texto de una celda de la tabla (la fila del club tiene ademas el
        fondo resaltado en la misma posicion, debajo)."""
        from PySide6.QtWidgets import QLabel

        grilla = self.pagina.tabla_grilla
        for i in range(grilla.count()):
            widget = grilla.itemAt(i).widget()
            if isinstance(widget, QLabel) and grilla.getItemPosition(i)[:2] == (fila, columna):
                return widget.text()
        raise AssertionError(f"sin celda en {fila},{columna}")

    def _con_partida(self):
        (Path(self.carpeta.name) / "CmPlr1").write_bytes(f.construir_bytes())

    def test_sin_partida_lo_explica(self):
        self.pagina.actualizar()
        ayuda.esperar_tareas()
        self.assertTrue(self.pagina.vacio.isVisibleTo(self.pagina))
        self.assertFalse(self.pagina.contenido.isVisibleTo(self.pagina))
        self.assertIn("Sin partida", self.pagina.subtitulo_label.text())

    def test_tabla_y_cambio_de_competicion(self):
        self._con_partida()
        self.pagina.actualizar()
        ayuda.esperar_tareas()
        self.assertTrue(self.pagina.contenido.isVisibleTo(self.pagina))
        self.assertIn("2026/27", self.pagina.titulo_label.text())
        self.assertIn("2° en la Premier League", self.pagina.subtitulo_label.text())
        self.assertTrue(self.pagina.tabla_tarjeta.isVisibleTo(self.pagina))
        self.assertEqual(self.pagina.tabla_grilla.rowCount(), 6)  # encabezado + 5 equipos
        self.assertEqual(self._celda(2, 1), "Man Utd")
        self.assertEqual(self._celda(2, 9), "6")  # puntos

        botones = self.pagina._grupo.buttons()
        self.assertEqual([b.text() for b in botones], ["PREMIER LEAGUE", "CHAMPIONS LEAGUE"])
        self.assertTrue(botones[0].isChecked())
        botones[1].click()
        ayuda.esperar_tareas()
        self.assertEqual(self.pagina.vista.competicion, f.CHAMPIONS)
        self.assertFalse(self.pagina.tabla_tarjeta.isVisibleTo(self.pagina))  # una copa no tiene tabla
        self.assertTrue(self.pagina._grupo.buttons()[1].isChecked())

    def test_cambiar_de_competicion_mientras_lee(self):
        self._con_partida()
        self.pagina.actualizar()
        self.pagina._elegir(f.CHAMPIONS)  # todavia leyendo la liga
        ayuda.esperar_tareas()
        ayuda.esperar_tareas()
        self.assertEqual(self.pagina.vista.competicion, f.CHAMPIONS)

    def test_el_mercado_de_fichajes(self):
        from roleplay.models import PlayerProfile

        pid = database.save_profile(PlayerProfile(nombre_jugador="Simon Canales"))
        database.set_estado_prensa(pid, {"mercado": [
            {"fecha": "2027-01-16", "texto": "un lateral derecho (media 80) paso de Spurs a Man Utd", "club": True},
            {"fecha": "2027-01-15", "texto": "Erling Haaland (media 92) paso de Manchester City a SSC Napoli", "club": False},
        ]})
        self._con_partida()
        self.pagina.actualizar()
        ayuda.esperar_tareas()
        self.assertTrue(self.pagina.mercado_tarjeta.isVisibleTo(self.pagina))
        self.assertEqual(self.pagina.mercado_layout.count(), 2)
        primera = self.pagina.mercado_layout.itemAt(0).layout()
        textos = [primera.itemAt(i).widget().text() for i in range(primera.count()) if primera.itemAt(i).widget()]
        self.assertEqual(textos[0], "16/01")
        self.assertIn("Un lateral derecho (media 80) paso de Spurs a Man Utd", textos)
        self.assertIn("TU CLUB", textos)

    def test_esta_en_el_menu(self):
        from roleplay.ui.menu import MainMenuWindow

        self._con_partida()
        ventana = MainMenuWindow()
        ventana.vigilante.detener()
        ventana._ir_a(ventana.PAGINA_TEMPORADA)
        ayuda.esperar_tareas()
        self.assertIn("TEMPORADA", ventana._botones_nav[ventana.PAGINA_TEMPORADA].text())
        self.assertTrue(ventana._botones_nav[ventana.PAGINA_TEMPORADA].isChecked())
        self.assertIsNotNone(ventana.pagina_temporada.vista)
        ventana.close()
