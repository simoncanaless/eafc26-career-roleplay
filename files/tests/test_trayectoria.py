"""La trayectoria: cada temporada de la partida, archivada al terminar."""

from datetime import date
from unittest import mock

import ayuda
import fabrica_partida as f
from roleplay import database
from roleplay.models import PlayerProfile
from roleplay.partida.carrera import Partido, construir
from roleplay.servicios import partida_real, prensa
from roleplay.servicios.partida_real import archivar_temporada, describir_temporada, resumen_de_la_temporada


def carrera_en_la_temporada_siguiente():
    """La partida falsa con un partido jugado en agosto de 2027: el juego ya
    paso a la 2027/28."""
    c = construir(f.construir_bytes())
    c.partidos.append(Partido(date(2027, 8, 14), f.LIGA, f.MAN_UTD, f.LIVERPOOL, 1, 0, True))
    return c


class TestArchivarTemporada(ayuda.PruebaConBase):
    def test_el_resumen_de_la_temporada_en_curso(self):
        r = resumen_de_la_temporada(construir(f.construir_bytes()))
        self.assertEqual(
            {k: r[k] for k in ("temporada", "club", "partidos", "goles", "asistencias", "nota", "liga", "posicion", "hasta")},
            {"temporada": "2026/27", "club": "Man Utd", "partidos": 3, "goles": 8, "asistencias": 3, "nota": 9.2,
             "liga": "Premier League", "posicion": 2, "hasta": "2027-01-16"},
        )
        self.assertEqual(
            describir_temporada(r),
            "temporada 2026/27 con Man Utd: 3 partidos, 8 goles, 3 asistencias, nota media 9.2; "
            "su club termino 2° en la Premier League",
        )

    def test_misma_temporada_solo_actualiza(self):
        c = construir(f.construir_bytes())
        terminada, en_curso = archivar_temporada(c, {"temporada": "2026/27", "goles": 1})
        self.assertIsNone(terminada)
        self.assertEqual(en_curso["goles"], 8)

    def test_al_cambiar_de_temporada_se_archiva_lo_ultimo_visto(self):
        visto = resumen_de_la_temporada(construir(f.construir_bytes()))
        terminada, en_curso = archivar_temporada(carrera_en_la_temporada_siguiente(), visto)
        self.assertEqual(terminada, visto)
        self.assertEqual(en_curso["temporada"], "2027/28")

    def test_la_primera_vez_no_hay_nada_que_archivar(self):
        terminada, en_curso = archivar_temporada(construir(f.construir_bytes()), None)
        self.assertIsNone(terminada)
        self.assertEqual(en_curso["temporada"], "2026/27")


class TestBalanceEnLaPrensa(ayuda.PruebaConBase):
    def setUp(self):
        super().setUp()
        self.perfil = PlayerProfile(nombre_jugador="Simon Canales", club_actual="Man Utd")
        self.perfil.id = database.save_profile(self.perfil)
        mock.patch.object(partida_real, "identificar_jugadores", return_value={}).start()
        mock.patch.object(partida_real, "identificar_competiciones", return_value={}).start()
        self.prompts = []

        def redactar(prompt, _api_key):
            self.prompts.append(prompt)
            return prensa.NoticiaIA(titular="T", cuerpo="C", tono="positiva")

        mock.patch.object(prensa, "_redactar", redactar).start()
        self.addCleanup(mock.patch.stopall)

    def test_el_balance_y_la_trayectoria(self):
        primera = partida_real.revisar_prensa_con_partida(self.perfil, [], {}, construir(f.construir_bytes()))
        estado = primera["estado_prensa"]
        self.assertEqual(estado["temporada_en_curso"]["goles"], 8)
        self.assertNotIn("trayectoria", estado)
        estado["vitrina"] = [{"premio": "Jugador del mes", "detalle": "x", "temporada": "2026/27"}]

        segunda = partida_real.revisar_prensa_con_partida(self.perfil, [], estado, carrera_en_la_temporada_siguiente())
        tipos = [h["tipo"] for h in segunda["hitos"]]
        self.assertIn("fin_de_temporada", tipos)
        self.assertTrue(any("termino la temporada 2026/27 con Man Utd" in p for p in self.prompts))
        trayectoria = segunda["estado_prensa"]["trayectoria"]
        self.assertEqual([t["temporada"] for t in trayectoria], ["2026/27"])
        self.assertEqual(trayectoria[0]["titulos"], ["Jugador del mes"])
        self.assertEqual(segunda["estado_prensa"]["temporada_en_curso"]["temporada"], "2027/28")


class TestTarjetaTrayectoria(ayuda.PruebaDeInterfaz):
    def test_el_resumen_muestra_las_temporadas(self):
        pid = database.save_profile(PlayerProfile(nombre_jugador="Simon Canales", club_actual="Man Utd"))
        database.set_estado_prensa(pid, {"trayectoria": [
            {"temporada": "2025/26", "club": "Palermo", "partidos": 30, "goles": 21, "asistencias": 7, "nota": 8.1,
             "liga": "Serie BKT", "posicion": 1, "titulos": ["Campeon"]},
            {"temporada": "2026/27", "club": "Man Utd", "partidos": 34, "goles": 102, "asistencias": 20, "nota": 9.4,
             "liga": "Premier League", "posicion": 2, "titulos": []},
        ]})
        from roleplay.ui.menu import PaginaResumen

        pagina = PaginaResumen(lambda: None)
        with mock.patch("roleplay.ui.menu.resumen_temporada", return_value=None):
            pagina.actualizar()
            ayuda.esperar_tareas()
        self.assertTrue(pagina.trayectoria.isVisibleTo(pagina))
        grilla = pagina.trayectoria_grilla

        def fila(n):
            return [grilla.itemAtPosition(n, c).widget().text() for c in range(8)]

        self.assertEqual(fila(1), ["2026/27", "Man Utd", "34", "102", "20", "9.4", "2° Premier League", "-"])
        self.assertEqual(fila(2), ["2025/26", "Palermo", "30", "21", "7", "8.1", "1° Serie BKT", "Campeon"])
