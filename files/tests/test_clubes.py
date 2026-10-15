"""Tu hinchada: el carino de cada club, los traspasos y las decisiones."""

import tempfile
from datetime import date
from pathlib import Path
from unittest import mock

import ayuda
import fabrica_partida as f
from roleplay import database
from roleplay.models import PlayerProfile
from roleplay.partida import lector
from roleplay.partida.carrera import construir
from roleplay.servicios import clubes, hinchada, partida_real

HOY = date(2027, 1, 16)


def partida(**kwargs):
    return construir(f.construir_bytes(**kwargs))


def con_carino(carino: int, club: int = f.MAN_UTD) -> dict:
    estado, _ = clubes.actualizar({}, partida(fichajes={f.USUARIO: club}) if club != f.MAN_UTD else partida(), 50)
    estado["clubes"][str(club)]["carino"] = carino
    return estado


class TestCarino(ayuda.PruebaConBase):
    def test_la_primera_vez_solo_registra_el_club(self):
        estado, hitos = clubes.actualizar({}, partida(), 50)
        self.assertEqual(hitos, [])
        self.assertEqual(estado["actual"], str(f.MAN_UTD))
        self.assertEqual(estado["hasta"], "2027-01-16")  # los partidos viejos no cuentan
        club = estado["clubes"][str(f.MAN_UTD)]
        self.assertEqual((club["nombre"], club["carino"], club["liga"]), ("Man Utd", 50, 13))

    def test_un_partido_nuevo_lo_mueve(self):
        estado, _ = clubes.actualizar({}, partida(), 50)
        estado, hitos = clubes.actualizar(estado, partida(partido_nuevo=True), 50)
        # victoria (+1), dos goles (+4) y un 8,8 (+2)
        self.assertEqual(estado["clubes"][str(f.MAN_UTD)]["carino"], 57)
        self.assertEqual(hitos, [])
        self.assertEqual(clubes.actualizar(estado, partida(partido_nuevo=True), 50)[0], estado)  # no cuenta dos veces

    def test_por_partido(self):
        self.assertEqual(clubes.carino_por_partido("derrota", False, 0, None), -1)
        self.assertEqual(clubes.carino_por_partido("derrota", True, 0, 5.5), -3)
        self.assertEqual(clubes.carino_por_partido("victoria", True, 5, 10.0), 1 + 6 + 2)  # los goles topean en 6

    def test_los_rotulos(self):
        self.assertEqual([clubes.rotulo(c) for c in (90, 70, 50, 30, 10)],
                         ["Idolo", "Querido", "Respetado", "Cuestionado", "En contra"])


class TestTraspasos(ayuda.PruebaConBase):
    def test_idolo_que_se_va_a_un_rival_de_liga(self):
        estado, hitos = clubes.actualizar(con_carino(80), partida(fichajes={f.USUARIO: f.CITY}), 50)
        self.assertEqual([h.tipo for h in hitos], ["salida", "traicion", "llegada"])
        viejo = estado["clubes"][str(f.MAN_UTD)]
        self.assertEqual((viejo["salida"], viejo["carino"], viejo["hasta"]), ("idolo", 50, "2027-01-16"))
        self.assertEqual((estado["actual"], estado["clubes"][str(f.CITY)]["carino"]), (str(f.CITY), 50))
        self.assertIn("traidor", hitos[1].titulo)
        self.assertEqual(hitos[1].reputacion, -2)

    def test_a_otra_liga_no_es_traicion(self):
        _, hitos = clubes.actualizar(con_carino(80), partida(fichajes={f.USUARIO: f.NAPOLI}), 50)
        self.assertEqual([h.tipo for h in hitos], ["salida", "llegada"])

    def test_por_la_puerta_de_atras(self):
        estado, hitos = clubes.actualizar(con_carino(20), partida(fichajes={f.USUARIO: f.NAPOLI}), 50)
        self.assertEqual((hitos[0].tipo, hitos[0].tono), ("salida", "negativa"))
        self.assertEqual(estado["clubes"][str(f.MAN_UTD)]["salida"], "mala")

    def test_vuelve_el_idolo(self):
        estado, _ = clubes.actualizar(con_carino(75), partida(fichajes={f.USUARIO: f.NAPOLI}), 50)
        estado, hitos = clubes.actualizar(estado, partida(), 50)
        self.assertEqual(hitos[-1].tipo, "regreso")
        self.assertIn("Vuelve el idolo", hitos[-1].titulo)
        self.assertEqual(estado["clubes"][str(f.MAN_UTD)]["carino"], 85)  # +10 por como se fue
        self.assertIsNone(estado["clubes"][str(f.MAN_UTD)]["hasta"])

    def test_la_decision_del_club_de_antes_se_cae(self):
        estado = con_carino(15)
        estado, _ = clubes.actualizar(estado, partida(partido_nuevo=True), 50)  # +7: sigue en contra
        self.assertIsNotNone(estado["decision"])
        estado, _ = clubes.actualizar(estado, partida(fichajes={f.USUARIO: f.NAPOLI}), 50)
        self.assertIsNone(estado["decision"])


class TestDecisiones(ayuda.PruebaConBase):
    def test_la_hinchada_en_contra_y_pedir_que_te_vendan(self):
        estado, _ = clubes.actualizar(con_carino(20), partida(), 50)
        decision, club = clubes.decision_pendiente(estado)
        self.assertEqual(decision.titulo.format(club=club), "La hinchada de Man Utd esta en tu contra")
        estado, hito, carino = clubes.elegir(estado, "salir", HOY)
        self.assertEqual((carino, estado["clubes"][str(f.MAN_UTD)]["carino"]), (-15, 5))
        self.assertIsNone(estado["decision"])
        self.assertEqual(estado["decisiones"][0]["eleccion"], "salir")
        self.assertIn("pedi el traspaso", hito.reto)
        self.assertEqual(hito.descripcion, "le pidio a Man Utd que lo venda")
        estado, _ = clubes.actualizar(estado, partida(), 50)
        self.assertIsNone(estado["decision"])  # no vuelve enseguida aunque siga en contra

    def test_despues_de_una_polemica(self):
        estado = clubes.por_evento(con_carino(60), "polemica_redes", HOY)
        self.assertEqual(estado["clubes"][str(f.MAN_UTD)]["carino"], 56)
        self.assertEqual(estado["decision"]["tipo"], "polemica")
        estado, hito, _ = clubes.elegir(estado, "disculpas", HOY)
        self.assertEqual((hito.reputacion, hito.tono), (2, "positiva"))
        self.assertIsNone(clubes.por_evento(con_carino(60), "gripe", HOY).get("decision"))

    def test_un_grande_pregunta_por_el_idolo(self):
        self.assertIsNone(clubes.actualizar(con_carino(90), partida(), 60)[0].get("decision"))  # sin reputacion, no
        estado, _ = clubes.actualizar(con_carino(90), partida(), 75)
        self.assertEqual(estado["decision"]["tipo"], "tentado")


class TestTarjetaEnElResumen(ayuda.PruebaDeInterfaz):
    def setUp(self):
        super().setUp()
        carpeta = Path(self.enterContext(tempfile.TemporaryDirectory()))
        (carpeta / "CmPlr1").write_bytes(f.construir_bytes())
        mock.patch.object(lector, "CARPETA_GUARDADOS", carpeta).start()
        mock.patch.object(partida_real, "identificar_jugadores", return_value={}).start()
        mock.patch.object(partida_real, "identificar_competiciones", return_value={}).start()
        mock.patch.object(hinchada, "comentar_eventos", return_value={}).start()
        self.addCleanup(mock.patch.stopall)
        self.addCleanup(ayuda.esperar_tareas)  # (antes de borrar la carpeta: la lectura de la partida corre en un hilo)
        self.pid = database.save_profile(PlayerProfile(nombre_jugador="Simon Canales", club_actual="Man Utd"))
        from roleplay.ui.menu import PaginaResumen

        self.pagina = PaginaResumen(lambda: None)
        self.avisos = []
        self.pagina.decision_pendiente.connect(self.avisos.append)

    def test_con_el_guardado_aparece_la_decision_y_se_contesta(self):
        estado, _ = clubes.actualizar({}, partida(), 50)
        estado["clubes"][str(f.MAN_UTD)]["carino"] = 20
        database.set_estado_clubes(self.pid, estado)
        self.pagina.actualizar()
        self.pagina.actualizar_hinchada(partida())
        ayuda.esperar_tareas()
        self.assertEqual(self.avisos, ["La hinchada de Man Utd esta en tu contra"])
        self.assertFalse(self.pagina.hinchada.isHidden())
        self.assertIn("En contra", self.pagina.hinchada_label.text())
        self.assertFalse(self.pagina.decision.isHidden())
        reputacion = database.get_reputacion_actual(self.pid)
        self.pagina.elegir("salir")
        ayuda.esperar_tareas()
        self.assertTrue(self.pagina.decision.isHidden())
        self.assertEqual(database.get_reputacion_actual(self.pid), reputacion - 1)
        self.assertIn("Reto:", self.pagina.eleccion_label.text())
        self.assertEqual(database.load_noticias_prensa(self.pid)[0].hitos, ["hinchada:eleccion"])
        self.assertEqual([a.tipo for a in database.load_actividad_instagram(self.pid)], ["hinchada"])
        self.assertEqual(database.get_estado_clubes(self.pid)["clubes"][str(f.MAN_UTD)]["carino"], 5)

    def test_sin_partida_leida_no_hay_tarjeta(self):
        self.pagina.actualizar()
        self.assertTrue(self.pagina.hinchada.isHidden())
