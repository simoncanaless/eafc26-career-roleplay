"""La carrera entera de la partida (YMgA/NgwF/cPet), los premios con su nombre y la gala de fin de temporada."""

import unittest
from unittest import mock

import ayuda
import fabrica_partida as f
from roleplay import database
from roleplay.models import PlayerProfile
from roleplay.partida.carrera import construir
from roleplay.servicios import contratos, partida_real, premios


def carrera(**kwargs):
    return construir(f.construir_bytes(etapas=True, **kwargs))


class TestEtapas(unittest.TestCase):
    def test_la_carrera_entera_club_por_club(self):
        c = carrera()
        arsenal, united = c.etapas
        self.assertEqual((arsenal.equipo, united.equipo), (f.ARSENAL, f.MAN_UTD))  # en YMgA vienen corridos en 1
        self.assertEqual(arsenal.liga, "Premier League")
        self.assertEqual(sum(e.partidos for e in c.etapas), 78)
        self.assertEqual(sum(e.goles for e in c.etapas), 264)
        self.assertEqual(sum(e.asistencias for e in c.etapas), 61)
        self.assertEqual((sum(e.ganados for e in c.etapas), sum(e.empatados for e in c.etapas),
                          sum(e.perdidos for e in c.etapas)), (63, 8, 7))
        self.assertEqual(arsenal.titulos, [f.LIGA])
        self.assertEqual(united.titulos, [])
        self.assertEqual(arsenal.nota, 8.8)
        self.assertEqual(arsenal.premios, {"equipo_de_la_semana": 21, "jugador_del_mes": 7})  # el tipo 2, sin confirmar

    def test_sin_las_tablas_no_hay_etapas(self):
        self.assertEqual(construir(f.construir_bytes()).etapas, [])

    def test_el_resumen(self):
        with mock.patch.object(partida_real, "identificar_competiciones", return_value={}):
            completa = partida_real.carrera_completa(carrera())
        self.assertEqual([e["club"] for e in completa], ["Arsenal", "Man Utd"])
        self.assertEqual(completa[0]["titulos"], ["Premier League"])


class TestNombresPorLiga(unittest.TestCase):
    def test_cada_liga_con_su_premio(self):
        self.assertEqual(premios.nombre_premio("maximo_goleador", "LALIGA EA SPORTS"), "Trofeo Pichichi")
        self.assertEqual(premios.nombre_premio("maximo_goleador", "Serie A Enilive"), "Capocannoniere de la Serie A")
        self.assertEqual(premios.nombre_premio("maximo_goleador", "Serie BKT"), "Capocannoniere de la Serie B")
        self.assertEqual(premios.nombre_premio("jugador_del_mes", "Premier League"), "Jugador del Mes de la Premier League")
        self.assertEqual(premios.nombre_premio("campeon", "Serie A"), "Scudetto")
        self.assertEqual(premios.nombre_premio("jugador_del_mes", "Liga Inventada"), "Jugador del Mes de la Liga Inventada")


class TestGala(unittest.TestCase):
    def setUp(self):
        mock.patch.object(premios, "MINIMO_PARTIDOS", 1).start()  # la partida de prueba tiene pocos partidos
        self.addCleanup(mock.patch.stopall)

    def test_los_premios_salen_de_los_numeros_reales(self):
        c = carrera()
        resultados = {r.premio.id: r for r in premios.gala(c)}
        self.assertEqual(resultados["gerd_muller"].ganador.jugador, f.USUARIO)  # 8 goles contra 5 de Haaland
        self.assertEqual(resultados["gerd_muller"].puesto(f.HAALAND), 2)
        self.assertIn("balon_de_oro", resultados)
        self.assertIn("bota_de_oro", resultados)

    def test_la_gala_una_vez_cuando_termina_la_liga(self):
        c = carrera()
        with mock.patch.object(partida_real, "liga_terminada", return_value=False):
            self.assertEqual(partida_real.gala_de_la_temporada(c, None)[0], [])
        with mock.patch.object(partida_real, "liga_terminada", return_value=True):
            hitos, resultados, temporada = partida_real.gala_de_la_temporada(c, None)
            self.assertIn("Trofeo Gerd Muller (France Football)", [h["valor"] for h in hitos])
            self.assertEqual(partida_real.gala_de_la_temporada(c, temporada)[0], [])  # una vez por temporada


class TestJugadorDelMesDelJuego(ayuda.PruebaConBase):
    def setUp(self):
        super().setUp()
        self.perfil = PlayerProfile(nombre_jugador="Simon Canales", club_actual="Man Utd")
        self.perfil.id = database.save_profile(self.perfil)
        mock.patch.object(partida_real, "identificar_jugadores", return_value={}).start()
        mock.patch.object(partida_real, "identificar_competiciones", return_value={}).start()
        self.addCleanup(mock.patch.stopall)

    def test_la_primera_vez_solo_cuenta_desde_ahi(self):
        hitos, estado = partida_real.premios_del_juego(carrera())
        self.assertEqual(hitos, [])
        self.assertEqual(estado, {"etapa": 2, "equipo_de_la_semana": 15, "jugador_del_mes": 5})

    def test_si_el_contador_sube_lo_gano(self):
        _, estado = partida_real.premios_del_juego(carrera())
        hitos, _ = partida_real.premios_del_juego(carrera(jugador_del_mes=6), estado)
        self.assertEqual(hitos[0]["tipo"], "jugador_del_mes")
        self.assertEqual(hitos[0]["liga"], "Premier League")

    def test_en_la_prensa_y_la_vitrina_con_el_nombre_de_su_liga(self):
        estado = {"premios_juego": {"etapa": 2, "jugador_del_mes": 5, "equipo_de_la_semana": 15}}
        resultado = partida_real.revisar_prensa_con_partida(self.perfil, [], estado, carrera(jugador_del_mes=6))
        vitrina = resultado["estado_prensa"]["vitrina"]
        self.assertEqual([p["premio"] for p in vitrina], ["Jugador del Mes de la Premier League"])
        self.assertEqual(vitrina[0]["tipo"], "jugador_del_mes")
        self.assertEqual(resultado["estado_prensa"]["premios_juego"]["jugador_del_mes"], 6)


class TestPrimasConLaVitrina(unittest.TestCase):
    def test_el_balon_de_oro_de_la_gala_paga_la_prima(self):
        from datetime import date

        neg = contratos.abrir("Man Utd", 1, 80, date(2026, 8, 1), "delantero centro")
        e, _ = contratos.firmar({"saldo": 0, "sueldo": 100_000, "hasta": "2026-08-01"}, neg, 2, date(2026, 8, 1))
        vitrina = [{"tipo": "balon_de_oro", "premio": "Balon de Oro (France Football)", "detalle": "x",
                    "temporada": "2026/27"}]
        e, cobros = contratos.cobrar(e, "Man Utd", date(2027, 5, 30), 0, vitrina)
        self.assertIn("Prima por el Balon de Oro (neto)", [c for c, _ in cobros])
        with self.assertRaises(ValueError):  # ya esta anotado: el boton no lo cobra dos veces
            contratos.balon_de_oro(e, "Man Utd", date(2027, 6, 1))

    def test_sin_contrato_queda_anotado(self):
        from datetime import date

        vitrina = [{"tipo": "balon_de_oro", "premio": "x", "detalle": "x", "temporada": "2026/27"}]
        e, _ = contratos.cobrar({"saldo": 0, "sueldo": 1}, "Man Utd", date(2027, 5, 30), 0, vitrina)
        self.assertEqual(e["balones_de_oro"], ["2026/27"])


class TestResumen(ayuda.PruebaDeInterfaz):
    def test_la_tarjeta_de_la_carrera(self):
        from roleplay.ui.menu import PaginaResumen

        pagina = PaginaResumen(lambda: None)
        with mock.patch.object(partida_real, "identificar_competiciones", return_value={}):
            pagina._mostrar_carrera(partida_real.carrera_completa(carrera()))
        texto = pagina.carrera_label.text()
        self.assertIn("264 goles", texto)
        self.assertIn("Equipo de la semana: <b>36</b>", texto)
        self.assertFalse(pagina.carrera_completa.isHidden())


if __name__ == "__main__":
    unittest.main()
