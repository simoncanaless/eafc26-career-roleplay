"""Metas de temporada: se siguen con la partida y son noticia."""

from pathlib import Path
from unittest import mock

import ayuda
import fabrica_partida as f
from roleplay import database
from roleplay.models import PlayerProfile
from roleplay.partida import lector
from roleplay.partida.carrera import construir
from roleplay.servicios import metas, partida_real, prensa


def meta(tipo, objetivo, temporada="2026/27"):
    return metas.nueva_meta(tipo, objetivo, temporada)


class TestMetas(ayuda.PruebaConBase):
    def setUp(self):
        super().setUp()
        self.c = construir(f.construir_bytes())

    def test_crear_y_contar(self):
        with self.assertRaises(ValueError):
            metas.nueva_meta("goles", 0, "2026/27")
        with self.assertRaises(ValueError):
            metas.nueva_meta("tarjetas", 3, "2026/27")
        self.assertEqual(metas.texto_meta(meta("goles", 30)), "Marcar 30 goles en la temporada")
        self.assertEqual(metas.texto_meta(meta("top_liga", 1)), "Salir campeon de la liga")
        self.assertEqual(metas.texto_meta(meta("top_liga", 4)), "Terminar entre los 4 primeros de la liga")

    def test_el_progreso_sale_de_la_partida(self):
        self.assertEqual(metas.progreso(self.c, meta("goles", 30)), 8)  # 6 en liga + 2 en Champions
        self.assertEqual(metas.progreso(self.c, meta("goles_liga", 30)), 6)
        self.assertEqual(metas.progreso(self.c, meta("asistencias", 10)), 3)
        self.assertEqual(metas.progreso(self.c, meta("top_liga", 4)), 2)

    def test_una_meta_contable_se_cumple_apenas_se_llega(self):
        lograda, pendiente = meta("goles", 5), meta("goles", 30)
        hitos, cambios = metas.evaluar_metas(self.c, [lograda, pendiente])
        self.assertEqual(hitos, [{"tipo": "meta_cumplida", "valor": "Marcar 5 goles en la temporada"}])
        self.assertEqual(cambios[lograda["id"]], {"actual": 8, "estado": "cumplida"})
        self.assertEqual(cambios[pendiente["id"]], {"actual": 8})

    def test_el_puesto_se_decide_al_terminar_la_liga(self):
        top4, campeon = meta("top_liga", 4), meta("top_liga", 1)
        hitos, cambios = metas.evaluar_metas(self.c, [top4, campeon])
        self.assertEqual(hitos, [])
        self.assertNotIn("estado", cambios[top4["id"]])
        with mock.patch.object(metas, "liga_terminada", return_value=True):
            hitos, cambios = metas.evaluar_metas(self.c, [top4, campeon])
        self.assertEqual(cambios[top4["id"]]["estado"], "cumplida")
        self.assertEqual(cambios[campeon["id"]]["estado"], "fallida")
        self.assertEqual([h["tipo"] for h in hitos], ["meta_cumplida", "meta_fallida"])

    def test_las_de_una_temporada_que_paso_fallan(self):
        vieja = meta("goles", 50, "2025/26")
        ya_cumplida = dict(meta("goles", 5, "2025/26"), estado="cumplida")
        hitos, cambios = metas.evaluar_metas(self.c, [vieja, ya_cumplida])
        self.assertEqual(cambios, {vieja["id"]: {"estado": "fallida"}})
        self.assertEqual(hitos, [{"tipo": "meta_fallida", "valor": "Marcar 50 goles en la temporada (2025/26)"}])


class TestMetasEnLaPrensa(ayuda.PruebaConBase):
    def setUp(self):
        super().setUp()
        self.perfil = PlayerProfile(nombre_jugador="Simon Canales", club_actual="Man Utd")
        self.perfil.id = database.save_profile(self.perfil)
        mock.patch.object(partida_real, "identificar_jugadores", return_value={}).start()
        mock.patch.object(partida_real, "identificar_competiciones", return_value={}).start()
        self.addCleanup(mock.patch.stopall)

    def test_la_prensa_las_evalua_y_las_conoce(self):
        lograda, pendiente = meta("goles", 5), meta("goles", 10)
        database.agregar_meta(self.perfil.id, lograda)
        database.agregar_meta(self.perfil.id, pendiente)
        resultado = partida_real.revisar_prensa_con_partida(self.perfil, [], {}, construir(f.construir_bytes()))
        self.assertIn({"tipo": "meta_cumplida", "valor": "Marcar 5 goles en la temporada"}, resultado["hitos"])
        self.assertEqual(resultado["metas"][lograda["id"]]["estado"], "cumplida")
        texto = ayuda.texto_de_noticias(resultado["noticias"])
        self.assertIn("marcar 5 goles en la temporada", texto.lower())
        self.assertIn("2 goles", texto)  # la pendiente (lleva 8 de 10): el cruce de la meta cerca
        self.assertEqual(resultado["delta_reputacion"], prensa.BONOS_REPUTACION["meta_cumplida"])

    def test_las_entrevistas_tambien(self):
        from roleplay.servicios import entrevista
        from roleplay.servicios.vision import MatchStats

        database.agregar_meta(self.perfil.id, meta("goles", 10))  # lleva 8: esta cerca
        stats = MatchStats(goles_equipo=1, goles_rival=1, equipo_rival="Leeds", rating_jugador=6.9, minutos_jugados=90)
        with mock.patch.object(entrevista, "_carrera", return_value=construir(f.construir_bytes())):
            vestuario = entrevista.generar_entrevista(self.perfil, stats)[1]
        self.assertTrue(vestuario.startswith("Valentina Aros (Radio Tribuna): "))
        self.assertRegex(vestuario, r"2 goles|8 de 10")  # le faltan 2: la cuenta regresiva

    def test_actualizar_no_revive_una_borrada(self):
        m = meta("goles", 30)
        database.agregar_meta(self.perfil.id, m)
        database.quitar_meta(self.perfil.id, m["id"])
        database.actualizar_metas(self.perfil.id, {m["id"]: {"estado": "cumplida"}})
        self.assertEqual(database.get_metas(self.perfil.id), [])


class TestTarjetaMetas(ayuda.PruebaDeInterfaz):
    def setUp(self):
        super().setUp()
        self.pid = database.save_profile(PlayerProfile(nombre_jugador="Simon Canales", club_actual="Man Utd"))
        carpeta = self.enterContext(__import__("tempfile").TemporaryDirectory())
        (Path(carpeta) / "CmPlr1").write_bytes(f.construir_bytes())
        mock.patch.object(lector, "CARPETA_GUARDADOS", Path(carpeta)).start()
        mock.patch.object(partida_real, "identificar_competiciones", return_value={}).start()
        self.addCleanup(mock.patch.stopall)
        from roleplay.ui.menu import PaginaResumen

        self.pagina = PaginaResumen(lambda: None)
        self.pagina.actualizar()
        ayuda.esperar_tareas()

    def _filas(self):
        from PySide6.QtWidgets import QLabel

        filas = []
        for i in range(self.pagina.metas_layout.count()):
            layout = self.pagina.metas_layout.itemAt(i).layout()
            filas.append([layout.itemAt(j).widget().text() for j in range(layout.count())
                          if isinstance(layout.itemAt(j).widget(), QLabel)])
        return filas

    def test_agregar_ver_el_avance_y_quitar(self):
        self.assertTrue(self.pagina.metas.isVisibleTo(self.pagina))
        self.assertEqual(self._filas(), [])
        self.pagina.meta_tipo.setCurrentIndex(self.pagina.meta_tipo.findData("goles"))
        self.pagina.meta_objetivo.setValue(30)
        self.pagina.meta_agregar_btn.click()
        ayuda.esperar_tareas()
        self.assertEqual(self._filas(), [["EN CURSO", "Marcar 30 goles en la temporada", "8/30"]])
        self.assertEqual(database.get_metas(self.pid)[0]["temporada"], "2026/27")

        self.pagina.meta_tipo.setCurrentIndex(self.pagina.meta_tipo.findData("top_liga"))
        self.assertEqual(self.pagina.meta_objetivo.value(), 4)
        self.pagina.meta_agregar_btn.click()
        ayuda.esperar_tareas()
        self.assertEqual(self._filas()[1], ["EN CURSO", "Terminar entre los 4 primeros de la liga", "va 2°"])

        # llegar al numero ya la muestra cumplida (sin esperar a la prensa) y no se puede quitar
        self.pagina.meta_tipo.setCurrentIndex(self.pagina.meta_tipo.findData("asistencias"))
        self.pagina.meta_objetivo.setValue(3)
        self.pagina.meta_agregar_btn.click()
        ayuda.esperar_tareas()
        self.assertEqual(self._filas()[2], ["CUMPLIDA", "Dar 3 asistencias en la temporada", "3/3"])

        from PySide6.QtWidgets import QPushButton

        tercera = self.pagina.metas_layout.itemAt(2).layout()
        self.assertFalse(any(isinstance(tercera.itemAt(j).widget(), QPushButton) for j in range(tercera.count())))
        primera = self.pagina.metas_layout.itemAt(0).layout()
        quitar = next(primera.itemAt(j).widget() for j in range(primera.count())
                      if isinstance(primera.itemAt(j).widget(), QPushButton))
        quitar.click()
        ayuda.esperar_tareas()
        self.assertEqual([m["tipo"] for m in database.get_metas(self.pid)], ["top_liga", "asistencias"])

    def test_sin_partida_no_se_muestra(self):
        with mock.patch("roleplay.ui.menu.resumen_temporada", return_value=None):
            self.pagina.actualizar()
            ayuda.esperar_tareas()
        self.assertFalse(self.pagina.metas.isVisibleTo(self.pagina))
