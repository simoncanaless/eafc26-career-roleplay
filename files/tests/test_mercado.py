"""Mercado de fichajes: traspasos reales comparando dos lecturas de la partida."""

from unittest import mock

import ayuda
import fabrica_partida as f
from roleplay import database
from roleplay.models import PlayerProfile
from roleplay.partida.carrera import construir
from roleplay.servicios import mercado, partida_real, prensa

FICHAJES = {
    f.BRUNO: f.AGENTES_LIBRES,  # se va del club del usuario, libre
    f.DELANTERO_ARSENAL: f.MAN_UTD,  # llega al club del usuario
    f.HAALAND: f.NAPOLI,  # una estrella cambia de liga
    f.SUPLENTE_CITY: f.SUNDERLAND,  # media 64, fuera del club: no es noticia
    f.JUGADORA: f.CHELSEA_FEM,  # liga femenina: no entra
}


def antes_y_despues(fichajes=FICHAJES):
    return construir(f.construir_bytes()), construir(f.construir_bytes(fichajes=fichajes))


class TestTraspasos(ayuda.PruebaConBase):
    def test_lo_que_es_noticia_y_en_que_orden(self):
        antes, despues = antes_y_despues()
        anteriores = mercado.clubes_de_jugadores(antes)
        self.assertNotIn(f.JUGADORA, anteriores)
        self.assertEqual(anteriores[f.HAALAND], f.CITY)  # el club, no la seleccion
        traspasos = mercado.detectar_traspasos(despues, anteriores)
        self.assertEqual(
            [(t.jugador, t.desde, t.hacia, t.toca_al_club) for t in traspasos],
            [
                (f.BRUNO, f.MAN_UTD, f.AGENTES_LIBRES, True),
                (f.DELANTERO_ARSENAL, f.ARSENAL, f.MAN_UTD, True),
                (f.HAALAND, f.CITY, f.NAPOLI, False),
            ],
        )

    def test_como_se_cuenta_cada_uno(self):
        antes, despues = antes_y_despues()
        traspasos = mercado.detectar_traspasos(despues, mercado.clubes_de_jugadores(antes))
        nombres = {f.HAALAND: "Erling Haaland"}
        textos = [mercado.describir_traspaso(despues, t, nombres) for t in traspasos]
        self.assertEqual(textos[0], "un mediapunta (edad 32, media 86, sin nombre en la partida) quedo libre tras dejar Man Utd")
        self.assertIn("paso de Arsenal a Man Utd", textos[1])
        self.assertEqual(textos[2], "Erling Haaland (media 92) paso de Manchester City a SSC Napoli")
        self.assertEqual(
            mercado.describir_traspaso(despues, traspasos[0], nombres, para_la_ia=False),
            "un mediapunta (edad 32, media 86) quedo libre tras dejar Man Utd",
        )
        hecho = mercado.texto_mercado(despues, traspasos, nombres)
        self.assertTrue(hecho.startswith("Movimientos del mercado de fichajes (club del jugador: Man Utd):"))

    def test_sin_lectura_anterior_no_hay_traspasos(self):
        _, despues = antes_y_despues()
        self.assertEqual(mercado.detectar_traspasos(despues, {}), [])

    def test_el_traspaso_del_usuario(self):
        antes, despues = antes_y_despues({f.USUARIO: f.CITY})
        anteriores = mercado.clubes_de_jugadores(antes)
        self.assertEqual(mercado.traspaso_del_usuario(despues, anteriores), (f.MAN_UTD, f.CITY))
        self.assertEqual(mercado.detectar_traspasos(despues, anteriores), [])  # no va con los del mundo
        self.assertIsNone(mercado.traspaso_del_usuario(antes, anteriores))

    def test_la_foto_se_guarda_por_partida(self):
        antes, _ = antes_y_despues()
        database.guardar_clubes_vistos("otra", {1: 2})
        database.guardar_clubes_vistos(antes.partida, mercado.clubes_de_jugadores(antes))
        self.assertEqual(database.get_clubes_vistos(antes.partida)[f.HAALAND], f.CITY)
        self.assertEqual(database.get_clubes_vistos("otra"), {1: 2})
        database.guardar_clubes_vistos("otra", {3: 4})  # reemplaza
        self.assertEqual(database.get_clubes_vistos("otra"), {3: 4})


class TestPrensaConMercado(ayuda.PruebaConBase):
    def setUp(self):
        super().setUp()
        self.perfil = PlayerProfile(nombre_jugador="Simon Canales", club_actual="Man Utd")
        self.perfil.id = database.save_profile(self.perfil)
        mock.patch.object(partida_real, "identificar_jugadores", return_value={}).start()
        mock.patch.object(partida_real, "identificar_competiciones", return_value={}).start()
        self.prompts = []

        def redactar(prompt, _api_key):
            self.prompts.append(prompt)
            return prensa.NoticiaIA(titular=f"T{len(self.prompts)}", cuerpo="C", tono="neutral")

        mock.patch.object(prensa, "_redactar", redactar).start()
        self.addCleanup(mock.patch.stopall)

    def _revisar(self, carrera, estado=None):
        return partida_real.revisar_prensa_con_partida(self.perfil, [], estado or {}, carrera)

    def test_la_primera_vez_solo_saca_la_foto(self):
        antes, despues = antes_y_despues()
        resultado = self._revisar(antes)
        self.assertNotIn("mercado", resultado["estado_prensa"])
        self.assertFalse(any("Movimientos del mercado" in p for p in self.prompts))
        self.assertEqual(database.get_clubes_vistos(antes.partida)[f.BRUNO], f.MAN_UTD)

        self.prompts.clear()
        resultado = self._revisar(despues, resultado["estado_prensa"])
        mundo = [p for p in self.prompts if "hecho REAL" in p]
        self.assertTrue(any("Movimientos del mercado" in p for p in mundo))
        self.assertLessEqual(len(mundo), prensa.MAXIMO_NOTICIAS_MUNDO)
        guardado = resultado["estado_prensa"]["mercado"]
        self.assertEqual(len(guardado), 3)
        self.assertTrue(guardado[0]["club"])
        self.assertEqual(guardado[0]["fecha"], "2027-01-16")
        # la foto ya es la nueva: los mismos traspasos no vuelven a salir
        self.assertEqual(database.get_clubes_vistos(antes.partida)[f.BRUNO], f.AGENTES_LIBRES)
        self.prompts.clear()
        self._revisar(despues, resultado["estado_prensa"])
        self.assertFalse(any("Movimientos del mercado" in p for p in self.prompts))

    def test_si_el_usuario_cambia_de_club_es_noticia_suya(self):
        antes, despues = antes_y_despues({f.USUARIO: f.CITY})
        self._revisar(antes)
        resultado = self._revisar(despues)
        self.assertIn({"tipo": "nuevo_club", "valor": "del Man Utd al Manchester City"}, resultado["hitos"])
        self.assertIn("fue transferido del Man Utd al Manchester City", self.prompts[-2] + self.prompts[-1])

    def test_si_la_ia_falla_la_foto_no_avanza(self):
        antes, despues = antes_y_despues()
        self._revisar(antes)
        with mock.patch.object(prensa, "_redactar", side_effect=RuntimeError("sin cuota")):
            with self.assertRaises(RuntimeError):
                self._revisar(despues)
        self.assertEqual(database.get_clubes_vistos(antes.partida)[f.BRUNO], f.MAN_UTD)  # se detectan de nuevo


class TestDosNoticiasDelMundo(ayuda.PruebaConBase):
    def test_hasta_el_maximo(self):
        perfil = PlayerProfile(id=1, nombre_jugador="Simon")
        with mock.patch.object(prensa, "_redactar", return_value=prensa.NoticiaIA(titular="T", cuerpo="C", tono="neutral")) as r:
            resultado = prensa.revisar_prensa(perfil, [], {}, hechos_reales=["uno", "dos", "tres"])
        self.assertEqual(r.call_count, 2)
        self.assertEqual([n.categoria for n in resultado["noticias"]], ["general", "general"])
