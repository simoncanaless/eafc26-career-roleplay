"""El Instagram que se mueve solo y la prensa en cada autoguardado."""

import os
import tempfile
import time
from pathlib import Path
from unittest import mock

import ayuda
import fabrica_partida as f
from roleplay import config, database
from roleplay.models import NoticiaPrensa, PlayerProfile
from roleplay.partida import lector
from roleplay.partida.carrera import construir
from roleplay.servicios import hinchada, partida_real

# un dia despues del ultimo partido del usuario, juegan otros
OTRO_DIA = [(20270119, f.LIGA, f.LIVERPOOL, f.ARSENAL, 1, 1, True)]


class TestCuantoSeMueve(ayuda.PruebaConBase):
    def test_lo_decide_el_resultado_y_lo_que_hizo(self):
        mover = lambda **k: hinchada.crecimiento_por_partido(10_000, 50, **k)  # noqa: E731
        hat_trick = mover(resultado="victoria", jugo=True, goles=3, nota=9.0)
        victoria = mover(resultado="victoria", jugo=True, goles=0, nota=7.0)
        empate = mover(resultado="empate", jugo=True, goles=0, nota=7.0)
        derrota = mover(resultado="derrota", jugo=True, goles=0, nota=5.5)
        sin_jugar = mover(resultado="victoria", jugo=False)
        self.assertGreater(hat_trick, victoria)
        self.assertGreater(victoria, empate)
        self.assertGreater(empate, 0)
        self.assertLess(derrota, 0)
        self.assertLess(sin_jugar, victoria)
        self.assertEqual(victoria, 100)  # 1% de 10.000 con reputacion 50

    def test_con_pocos_seguidores_igual_se_mueve(self):
        self.assertGreater(hinchada.crecimiento_por_partido(0, 50, "victoria", True), 0)
        self.assertLess(hinchada.crecimiento_por_noticia(1_000, 50, "negativa"), 0)


class TestEventos(ayuda.PruebaConBase):
    def setUp(self):
        super().setUp()
        self.c = construir(f.construir_bytes())

    def test_la_primera_vez_solo_el_ultimo_partido(self):
        eventos, estado = hinchada.eventos_nuevos(self.c, [], None, 10_000, 50)
        self.assertEqual([e.titulo for e in eventos], ["Man Utd 5-3 Sunderland · 5 goles tuyos"])
        self.assertIn("marco 5 goles, nota 10.0", eventos[0].detalle)
        self.assertGreater(eventos[0].crecimiento, 0)
        self.assertEqual(estado["hasta"], "2027-01-16")
        self.assertEqual(estado["noticia"], 0)
        # nada nuevo: nada que decir
        self.assertEqual(hinchada.eventos_nuevos(self.c, [], estado, 10_000, 50)[0], [])

    def test_un_partido_nuevo(self):
        _, estado = hinchada.eventos_nuevos(self.c, [], None, 10_000, 50)
        despues = construir(f.construir_bytes(partido_nuevo=True))
        eventos, estado = hinchada.eventos_nuevos(despues, [], estado, 10_000, 50)
        self.assertEqual([e.titulo for e in eventos], ["Man Utd 2-1 Arsenal · 2 goles tuyos"])
        self.assertEqual(estado["hasta"], "2027-01-23")

    def test_las_noticias_sobre_el(self):
        vieja = NoticiaPrensa(id=3, categoria="jugador", tono="positiva", titular="Vieja")
        _, estado = hinchada.eventos_nuevos(self.c, [vieja], None, 10_000, 50)
        self.assertEqual(estado["noticia"], 3)  # las de antes no se reaccionan
        nuevas = [
            NoticiaPrensa(id=5, categoria="jugador", tono="negativa", titular="Canales, en el ojo de la tormenta"),
            NoticiaPrensa(id=4, categoria="general", tono="neutral", titular="Del mundo"),
            vieja,
        ]
        eventos, estado = hinchada.eventos_nuevos(self.c, nuevas, estado, 10_000, 50)
        self.assertEqual([(e.tipo, e.titulo) for e in eventos], [("noticia", "Canales, en el ojo de la tormenta")])
        self.assertLess(eventos[0].crecimiento, 0)
        self.assertEqual(estado["noticia"], 5)

    def test_procesar_comenta_con_el_corpus(self):
        perfil = PlayerProfile(nombre_jugador="Simon Canales", club_actual="Man Utd")
        perfil.id = database.save_profile(perfil)
        actividad, _ = hinchada.procesar(perfil, self.c, [], None, 10_000, 50)
        self.assertEqual(actividad[0].fecha_juego, "2027-01-16")
        self.assertGreater(actividad[0].crecimiento_seguidores, 0)
        comentarios = actividad[0].comentarios
        self.assertGreaterEqual(len(comentarios), 2)
        self.assertEqual((comentarios[0]["tono"], comentarios[0]["autor"][:1]), ("positivo", "@"))
        for c in comentarios:  # todo resuelto: ni variables ni simbolos sin expandir
            self.assertNotRegex(c["texto"] + c["autor"], r"[{}]|#\w+#")  # (un #hashtag suelto si vale)

    def test_los_comentarios_no_se_repiten_entre_partidos(self):
        perfil = PlayerProfile(nombre_jugador="Simon Canales", club_actual="Man Utd")
        perfil.id = database.save_profile(perfil)
        evento = hinchada.EventoHinchada("partido", "2027-01-16", "Victoria", "Gano", 300)
        textos = [c["texto"] for _ in range(4) for c in hinchada.comentar_eventos(perfil, [evento])[0]
                  if c["tono"] == "positivo"]
        self.assertEqual(len(textos), len(set(textos)), textos)


class ConPartida(ayuda.PruebaDeInterfaz):
    def setUp(self):
        super().setUp()
        self.carpeta = Path(self.enterContext(tempfile.TemporaryDirectory()))
        mock.patch.object(lector, "CARPETA_GUARDADOS", self.carpeta).start()
        mock.patch.object(config, "ARCHIVO_AJUSTES", self.carpeta / "ajustes.json").start()
        mock.patch.object(partida_real, "identificar_jugadores", return_value={}).start()
        mock.patch.object(partida_real, "identificar_competiciones", return_value={}).start()
        self.addCleanup(mock.patch.stopall)
        self.pid = database.save_profile(PlayerProfile(nombre_jugador="Simon Canales", club_actual="Man Utd"))
        self.guardado = self.carpeta / "CmPlr20260101"
        self._guardar()

    def _guardar(self, segundos=0, **opciones):
        self.guardado.write_bytes(f.construir_bytes(**opciones))
        momento = time.time() + segundos
        os.utime(self.guardado, (momento, momento))


class TestInstagramSeMueveSolo(ConPartida):
    def test_los_hinchas_reaccionan_sin_publicar(self):
        antes = database.get_seguidores(self.pid)
        comentarios = {0: [{"autor": "@redevil", "texto": "Que bestia", "tono": "positivo"}]}
        with mock.patch.object(hinchada, "comentar_eventos", return_value=comentarios):
            from roleplay.ui.instagram import InstagramWindow

            pagina = InstagramWindow()  # abrir la pagina ya revisa
            ayuda.esperar_tareas()
        self.assertTrue(pagina.actividad_tarjeta.isVisibleTo(pagina))
        guardada = database.load_actividad_instagram(self.pid)
        self.assertEqual([a.titulo for a in guardada], ["Man Utd 5-3 Sunderland · 5 goles tuyos"])
        self.assertEqual(database.get_seguidores(self.pid), antes + guardada[0].crecimiento_seguidores)
        self.assertEqual(database.get_estado_hinchada(self.pid)["hasta"], "2027-01-16")
        textos = " ".join(
            pagina.actividad_layout.itemAt(i).widget().text()
            for i in range(pagina.actividad_layout.count()) if pagina.actividad_layout.itemAt(i).widget()
        )
        self.assertIn("Que bestia", textos)

        # otra revision sin nada nuevo: no se repite
        with mock.patch.object(hinchada, "comentar_eventos") as comentar:
            pagina.revisar_hinchada()
            ayuda.esperar_tareas()
        comentar.assert_not_called()
        self.assertEqual(len(database.load_actividad_instagram(self.pid)), 1)

    def test_pedir_otra_mientras_corre_la_hace_despues(self):
        from roleplay.ui.instagram import InstagramWindow

        with mock.patch.object(hinchada, "comentar_eventos", return_value={}):
            pagina = InstagramWindow()
            pagina.revisar_hinchada()  # la primera sigue corriendo: queda pendiente
            self.assertTrue(pagina._hinchada_pendiente)
            ayuda.esperar_tareas()
            ayuda.esperar_tareas()
        self.assertFalse(pagina._hinchada_pendiente)
        self.assertIsNone(pagina._hinchada_en_curso)


class TestDiaNuevo(ConPartida):
    def _vigilante(self):
        from roleplay.ui.vigilante import VigilantePartida

        vigilante = VigilantePartida(intervalo_ms=60_000)
        self.partidos, self.dias = [], []
        vigilante.partido_nuevo.connect(self.partidos.append)
        vigilante.dia_nuevo.connect(self.dias.append)
        return vigilante

    def _leer(self, vigilante):
        vigilante.revisar()
        vigilante.revisar()
        ayuda.esperar_tareas()

    def test_avanzar_dias_sin_jugar_tambien_se_avisa(self):
        vigilante = self._vigilante()
        self._leer(vigilante)  # la primera: solo marca
        self.assertEqual((self.partidos, self.dias), ([], []))
        self._guardar(segundos=10, otros_partidos=OTRO_DIA)  # simulo dias: jugaron otros
        self._leer(vigilante)
        self.assertEqual(self.partidos, [])
        self.assertEqual(len(self.dias), 1)
        self.assertEqual(database.get_estado_partida(self.pid)["dia_visto"], "2027-01-19")
        self._guardar(segundos=20, otros_partidos=OTRO_DIA, partido_nuevo=True)  # despues juego yo
        self._leer(vigilante)
        self.assertEqual((len(self.partidos), len(self.dias)), (1, 1))  # es partido nuevo, no "dia"

    def test_el_menu_mueve_la_prensa_y_el_instagram(self):
        from roleplay.ui import entrevista
        from roleplay.ui.menu import MainMenuWindow

        with mock.patch.object(hinchada, "comentar_eventos", return_value={}):
            ventana = MainMenuWindow()
            ventana.vigilante.detener()
            ayuda.esperar_tareas()
        carrera = construir(f.construir_bytes(otros_partidos=OTRO_DIA))
        lectura = partida_real.LecturaPartida(carrera, partida_real.ultimo_partido(carrera, {}), "CTX", False)
        noticia = NoticiaPrensa(categoria="general", titular="Liverpool y Arsenal no se sacan diferencias")
        resultado = {"noticias": [noticia], "hitos": [], "estado_prensa": {}}
        with mock.patch.object(entrevista, "revisar_prensa_con_partida", return_value=resultado) as prensa, \
                mock.patch.object(ventana.pagina_instagram, "revisar_hinchada") as hinchas:
            ventana._on_dia_nuevo(lectura)
            ayuda.esperar_tareas()
        self.assertEqual(prensa.call_args.kwargs, {})
        self.assertIs(prensa.call_args.args[3], carrera)  # con la partida al dia
        self.assertGreaterEqual(hinchas.call_count, 2)  # por el dia y por las noticias
        ventana.close()

    def test_aviso_en_la_bandeja_de_noticias_automaticas(self):
        from roleplay.ui.menu import MainMenuWindow

        with mock.patch.object(hinchada, "comentar_eventos", return_value={}):
            ventana = MainMenuWindow()
            ventana.vigilante.detener()
            ayuda.esperar_tareas()
        ventana.bandeja = mock.MagicMock()
        sobre_el = NoticiaPrensa(categoria="jugador", titular="Canales, jugador del mes")
        otra = NoticiaPrensa(categoria="general", titular="Del mundo")
        with mock.patch.object(ventana.pagina_instagram, "revisar_hinchada"):
            ventana._on_noticias_publicadas([otra, sobre_el], False)
            ventana._on_noticias_publicadas([otra], True)  # la pidio el usuario: no se avisa
        ventana.bandeja.showMessage.assert_called_once()
        self.assertEqual(ventana.bandeja.showMessage.call_args.args[1], "Canales, jugador del mes")
        ventana.bandeja = None
        ventana.close()
