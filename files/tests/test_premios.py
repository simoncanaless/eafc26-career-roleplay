"""Premios reales: jugador del mes, campeon y maximo goleador, y la vitrina."""

from datetime import date
from unittest import mock

import ayuda
import fabrica_partida as f
from roleplay import database
from roleplay.models import PlayerProfile
from roleplay.partida.carrera import Partido, construir
from roleplay.servicios import partida_real, prensa
from roleplay.servicios.partida_real import liga_terminada, premio_del_mes


def carrera_en_febrero():
    """La partida falsa (todo en enero) con un partido ya jugado en febrero:
    el juego paso de mes."""
    c = construir(f.construir_bytes(), "falsa")
    c.partidos.append(Partido(date(2027, 2, 1), f.LIGA, f.LIVERPOOL, f.MAN_UTD, 0, 0, True))
    return c


ENERO_DESDE_CERO = {"mes": "2027-01", "liga": f.LIGA, "base": {}}


class TestJugadorDelMes(ayuda.PruebaConBase):
    def test_la_primera_vez_solo_empieza_a_contar(self):
        premio, estado = premio_del_mes(construir(f.construir_bytes()), None)
        self.assertIsNone(premio)
        # todos los goles son de enero: al empezar el mes nadie tenia goles
        self.assertEqual(estado, {"mes": "2027-01", "liga": f.LIGA, "base": {}})

    def test_mismo_mes_no_cambia_nada(self):
        premio, estado = premio_del_mes(construir(f.construir_bytes()), ENERO_DESDE_CERO)
        self.assertIsNone(premio)
        self.assertEqual(estado, ENERO_DESDE_CERO)

    def test_al_pasar_de_mes_gana_el_que_mas_goles_hizo(self):
        premio, estado = premio_del_mes(carrera_en_febrero(), ENERO_DESDE_CERO)
        self.assertEqual((premio.jugador, premio.goles, premio.es_usuario), (f.USUARIO, 6, True))
        self.assertEqual(premio.detalle, "enero de 2027 en la Premier League, con 6 goles")
        self.assertEqual(estado["mes"], "2027-02")
        self.assertEqual(estado["base"][str(f.USUARIO)], 6)  # lo de enero queda como base de febrero

    def test_cuenta_solo_lo_del_mes(self):
        # el usuario ya tenia 3 de antes: en enero hizo 3, Haaland 5
        estado = {"mes": "2027-01", "liga": f.LIGA, "base": {str(f.USUARIO): 3}}
        premio, _ = premio_del_mes(carrera_en_febrero(), estado)
        self.assertEqual((premio.jugador, premio.equipo, premio.goles, premio.es_usuario), (f.HAALAND, f.CITY, 5, False))
        texto = partida_real.describir_premio(carrera_en_febrero(), premio, {f.HAALAND: "Erling Haaland"})
        self.assertEqual(
            texto, "Erling Haaland (Manchester City) fue elegido jugador del mes de enero en la Premier League: "
            "marco 5 goles en el mes."
        )

    def test_sin_ver_el_mes_entero_no_hay_premio(self):
        salteado = {"mes": "2026-12", "liga": f.LIGA, "base": {}}
        premio, estado = premio_del_mes(carrera_en_febrero(), salteado)
        self.assertIsNone(premio)
        self.assertEqual(estado["mes"], "2027-02")  # vuelve a empezar a contar

    def test_con_pocos_partidos_en_el_mes_no_hay_premio(self):
        c = carrera_en_febrero()
        c.partidos[:] = [p for p in c.partidos if not (p.participa(f.MAN_UTD) and p.fecha == date(2027, 1, 2))]
        premio, _ = premio_del_mes(c, ENERO_DESDE_CERO)
        self.assertIsNone(premio)

    def test_el_cambio_de_temporada_no_premia(self):
        self.assertEqual(partida_real._mes_siguiente("2026-12"), "2027-01")
        self.assertEqual(partida_real._mes_siguiente("2027-06"), "2027-07")
        c = construir(f.construir_bytes())
        c.partidos.append(Partido(date(2027, 7, 20), f.LIGA, f.LIVERPOOL, f.MAN_UTD, 0, 0, True))
        premio, _ = premio_del_mes(c, {"mes": "2027-06", "liga": f.LIGA, "base": {}})
        self.assertIsNone(premio)


class TestFinDeLiga(ayuda.PruebaConBase):
    def test_un_fixture_a_medias_no_es_fin_de_liga(self):
        c = construir(f.construir_bytes())
        self.assertFalse(liga_terminada(c, f.LIGA))  # sin pendientes, pero nadie jugo una rueda
        hitos, _ = partida_real.detectar_hitos_reales(c)
        self.assertNotIn("maximo_goleador", [h["tipo"] for h in hitos])

    def test_al_terminar_la_liga_el_goleador_y_el_campeon(self):
        c = construir(f.construir_bytes())
        with mock.patch.object(partida_real, "liga_terminada", return_value=True):
            hitos, estado = partida_real.detectar_hitos_reales(c)
            otra_vez, _ = partida_real.detectar_hitos_reales(c, estado)
        self.assertIn({"tipo": "maximo_goleador", "valor": "Premier League"}, hitos)
        self.assertNotIn("campeon", [h["tipo"] for h in hitos])  # el Man Utd va 2°
        self.assertNotIn("maximo_goleador", [h["tipo"] for h in otra_vez])


class TestPrensaConPremios(ayuda.PruebaConBase):
    def setUp(self):
        super().setUp()
        self.perfil = PlayerProfile(nombre_jugador="Simon Canales", club_actual="Man Utd")
        self.perfil.id = database.save_profile(self.perfil)
        mock.patch.object(partida_real, "identificar_jugadores", return_value={}).start()
        mock.patch.object(partida_real, "identificar_competiciones", return_value={}).start()
        self.addCleanup(mock.patch.stopall)
        self.prompts = []

        def redactar(prompt, _api_key):
            self.prompts.append(prompt)
            return prensa.NoticiaIA(titular="T", cuerpo="C", tono="positiva")

        mock.patch.object(prensa, "_redactar", redactar).start()

    def test_el_jugador_del_mes_es_noticia_bono_y_vitrina(self):
        resultado = partida_real.revisar_prensa_con_partida(
            self.perfil, [], {"mes": ENERO_DESDE_CERO}, carrera_en_febrero()
        )
        self.assertIn({"tipo": "jugador_del_mes", "valor": "enero de 2027 en la Premier League, con 6 goles"},
                      resultado["hitos"])
        self.assertIn("fue elegido jugador del mes: enero de 2027", self.prompts[0])
        self.assertEqual(resultado["delta_reputacion"], prensa.BONOS_REPUTACION["jugador_del_mes"])
        estado = resultado["estado_prensa"]
        self.assertEqual(estado["mes"]["mes"], "2027-02")
        self.assertEqual(estado["vitrina"], [{
            "premio": "Jugador del mes", "detalle": "enero de 2027 en la Premier League, con 6 goles",
            "temporada": "2026/27",
        }])

    def test_si_lo_gana_otro_es_la_noticia_del_mundo(self):
        estado = {"mes": {"mes": "2027-01", "liga": f.LIGA, "base": {str(f.USUARIO): 3}}}
        resultado = partida_real.revisar_prensa_con_partida(self.perfil, [], estado, carrera_en_febrero())
        self.assertNotIn("jugador_del_mes", [h["tipo"] for h in resultado["hitos"]])
        self.assertTrue(any("jugador del mes de enero" in p for p in self.prompts))
        self.assertEqual(resultado["estado_prensa"]["vitrina"], [])
        self.assertEqual(resultado["delta_reputacion"], 0)


class TestVitrinaYBono(ayuda.PruebaDeInterfaz):
    def test_la_sala_aplica_el_bono_y_el_resumen_muestra_la_vitrina(self):
        pid = database.save_profile(PlayerProfile(nombre_jugador="Simon Canales", club_actual="Man Utd"))
        from roleplay.ui import entrevista
        from roleplay.ui.menu import PaginaResumen

        with mock.patch.object(entrevista, "leer_para_entrevista", return_value=None):
            sala = entrevista.InterviewWindow()
            ayuda.esperar_tareas()
        vitrina = [{"premio": "Jugador del mes", "detalle": "enero de 2027 en la Premier League, con 6 goles",
                    "temporada": "2026/27"}]
        resultado = {
            "noticias": [], "hitos": [{"tipo": "jugador_del_mes", "valor": "x"}],
            "estado_prensa": {"vitrina": vitrina}, "delta_reputacion": 5,
        }
        with mock.patch.object(entrevista, "revisar_prensa", return_value=resultado):
            sala._iniciar_revision_prensa(manual=False)
            ayuda.esperar_tareas()
        self.assertEqual(database.get_reputacion_actual(pid), 55)
        self.assertEqual(sala.reputacion_mosaico.numero.text(), "55")

        pagina = PaginaResumen(lambda: None)
        with mock.patch("roleplay.ui.menu.resumen_temporada", return_value=None):
            pagina.actualizar()
            ayuda.esperar_tareas()
        self.assertTrue(pagina.vitrina.isVisibleTo(pagina))
        texto = ayuda.texto_visible(pagina.vitrina_layout.itemAt(0).widget().text())
        self.assertIn("Jugador del mes · enero de 2027 en la Premier League, con 6 goles (2026/27)", texto)
