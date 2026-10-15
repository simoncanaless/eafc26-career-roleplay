"""Eventos inesperados: reglas, sorteo reproducible, lo que provocan y la tarjeta en Vida."""

import tempfile
from datetime import date, timedelta
from pathlib import Path
from unittest import mock

import ayuda
import fabrica_partida as f
from roleplay import database
from roleplay.models import PlayerProfile
from roleplay.partida import lector
from roleplay.partida.carrera import construir
from roleplay.servicios import economia, eventos, hinchada, partida_real

HOY = date(2027, 1, 16)
NETO_SEMANAL = round(f.SUELDO * economia.NETO)


def perfil(personalidad="reservado"):
    return PlayerProfile(id=7, nombre_jugador="Simon Canales", personalidad=personalidad)


def con_auto():
    e = economia.acreditar(None, HOY, f.SUELDO)
    e["posesiones"].append({"id": "a1", "articulo": "auto:porsche_911", "precio": 95_000, "desde": HOY.isoformat(),
                            "config": {"modelo": "porsche_911"}})
    return e


def ids(opciones):
    return {tipo.id for tipo, _, _ in opciones}


class TestQuePuedePasar(ayuda.PruebaConBase):
    def test_sin_auto_no_hay_multa_ni_choque(self):
        opciones = eventos.posibles(perfil(), economia.acreditar(None, HOY, f.SUELDO), None, 50, [])
        self.assertNotIn("multa_velocidad", ids(opciones))
        self.assertNotIn("robo_casa", ids(opciones))
        self.assertIn("gripe", ids(opciones))

    def test_con_auto_el_titular_lo_nombra(self):
        opciones = eventos.posibles(perfil(), con_auto(), None, 50, [])
        tipo, _, datos = next(o for o in opciones if o[0].id == "multa_velocidad")
        self.assertEqual(tipo.titulo.format(**datos), "Multa por exceso de velocidad con su Porsche 911 Carrera")

    def test_la_personalidad_cambia_lo_probable(self):
        def peso(personalidad, evento):
            return next(p for t, p, _ in eventos.posibles(perfil(personalidad), {}, None, 50, []) if t.id == evento)

        self.assertGreater(peso("polemico", "polemica_redes"), peso("reservado", "polemica_redes"))
        self.assertLess(peso("humilde", "polemica_redes"), peso("reservado", "polemica_redes"))
        self.assertGreater(peso("humilde", "visita_hospital"), peso("reservado", "visita_hospital"))

    def test_lo_que_pide_reputacion_o_racha(self):
        self.assertNotIn("campana", ids(eventos.posibles(perfil(), {}, None, 40, [])))
        self.assertIn("campana", ids(eventos.posibles(perfil(), {}, None, 70, [])))
        self.assertNotIn("premio_hinchas", ids(eventos.posibles(perfil(), {}, None, 50, [])))
        with mock.patch.object(eventos, "buena_racha", return_value=True):
            self.assertIn("premio_hinchas", ids(eventos.posibles(perfil(), {}, None, 50, [])))
        with mock.patch.object(economia, "mala_racha", return_value=True):
            self.assertIn("increpado", ids(eventos.posibles(perfil(), {}, None, 50, [])))

    def test_lo_reciente_no_se_repite(self):
        self.assertNotIn("gripe", ids(eventos.posibles(perfil(), {}, None, 50, ["gripe"])))


class TestSorteo(ayuda.PruebaConBase):
    def revisar(self, estado, hoy, e=None, p=perfil()):
        return eventos.revisar(p, estado, e if e is not None else economia.acreditar(None, HOY, f.SUELDO),
                               None, hoy, 10_000, 50)

    def test_la_primera_vez_solo_marca_desde_donde_contar(self):
        estado, _, ocurridos = self.revisar({}, HOY)
        self.assertEqual((estado["hasta"], ocurridos), ("2027-01-16", []))

    def test_cada_semana_tira_su_dado_y_lo_que_sobra_cuenta_despues(self):
        with mock.patch.object(eventos, "PROBABILIDAD_POR_SEMANA", 0):
            estado, _, ocurridos = self.revisar({"hasta": "2027-01-16"}, HOY + timedelta(days=10))
        self.assertEqual((estado["hasta"], ocurridos), ("2027-01-23", []))  # los 3 dias de mas, para la proxima
        with mock.patch.object(eventos, "PROBABILIDAD_POR_SEMANA", 1):
            _, _, ocurridos = self.revisar({"hasta": "2027-01-16"}, HOY + timedelta(days=3))
        self.assertEqual(ocurridos, [])  # sin una semana entera no se sortea

    def test_a_lo_sumo_uno_por_revision_y_reproducible(self):
        with mock.patch.object(eventos, "PROBABILIDAD_POR_SEMANA", 1):
            estado, _, ocurridos = self.revisar({"hasta": "2027-01-16"}, HOY + timedelta(days=70))
            _, _, otra_vez = self.revisar({"hasta": "2027-01-16"}, HOY + timedelta(days=70))
        self.assertEqual(len(ocurridos), 1)
        self.assertEqual(ocurridos[0].tipo.id, otra_vez[0].tipo.id)  # la misma partida, el mismo evento
        self.assertEqual(ocurridos[0].fecha, date(2027, 1, 23))  # paso en la primera semana
        self.assertEqual(estado["historial"][0]["evento"], ocurridos[0].tipo.id)

    def test_la_plata_entra_en_la_economia(self):
        campana = eventos.POR_ID["campana"]
        with mock.patch.object(eventos, "PROBABILIDAD_POR_SEMANA", 1), mock.patch.object(eventos, "TIPOS", [campana]):
            e = economia.acreditar(None, HOY, f.SUELDO)
            _, nueva, (ocurrido,) = eventos.revisar(perfil(), {"hasta": "2027-01-16"}, e, None, HOY + timedelta(days=7),
                                                    10_000, 70)
        self.assertEqual(ocurrido.dinero, round(4 * f.SUELDO * economia.NETO))
        self.assertEqual(nueva["saldo"], e["saldo"] + ocurrido.dinero)
        self.assertEqual(nueva["movimientos"][0]["concepto"], "Una marca deportiva lo elige para su nueva campana")
        self.assertEqual((ocurrido.reputacion, ocurrido.seguidores > 0), (2, True))
        self.assertEqual(e["saldo"], economia.acreditar(None, HOY, f.SUELDO)["saldo"])  # no toca el original

    def test_no_se_repite_enseguida(self):
        gripe = eventos.POR_ID["gripe"]
        with mock.patch.object(eventos, "PROBABILIDAD_POR_SEMANA", 1), mock.patch.object(eventos, "TIPOS", [gripe]):
            estado, _, primero = self.revisar({"hasta": "2027-01-16"}, HOY + timedelta(days=7))
            _, _, segundo = self.revisar(estado, HOY + timedelta(days=14))
        self.assertEqual((len(primero), segundo), (1, []))
        self.assertIn("banco", primero[0].reto)

    def test_partida_anterior(self):
        estado, _, ocurridos = self.revisar({"hasta": "2027-02-01", "historial": []}, HOY)
        self.assertEqual((estado["hasta"], ocurridos), ("2027-01-16", []))


class TestRepercusion(ayuda.PruebaConBase):
    def setUp(self):
        super().setUp()
        with mock.patch.object(eventos, "PROBABILIDAD_POR_SEMANA", 1), \
                mock.patch.object(eventos, "TIPOS", [eventos.POR_ID["multa_velocidad"]]):
            _, _, (self.ocurrido,) = eventos.revisar(perfil(), {"hasta": "2027-01-16"}, con_auto(), None,
                                                     HOY + timedelta(days=7), 10_000, 50)

    def test_con_ia(self):
        comentarios = {0: [{"usuario": "hincha", "texto": "Despacio, crack"}]}
        with mock.patch.object(eventos, "generar_json", return_value=eventos.NoticiaEvento(titular="T", cuerpo="C")) as ia, \
                mock.patch.object(hinchada, "comentar_eventos", return_value=comentarios):
            noticia, actividad = eventos.repercusion(perfil(), self.ocurrido, "£")
        self.assertIn("Porsche 911 Carrera", ia.call_args[0][0])
        self.assertIn("le cuesta", ia.call_args[0][0])
        self.assertEqual((noticia.titular, noticia.tono, noticia.hitos), ("T", "negativa", ["evento:multa_velocidad"]))
        self.assertEqual((actividad.tipo, actividad.comentarios), ("evento", comentarios[0]))

    def test_sin_ia_igual_sale(self):
        with mock.patch.object(eventos, "generar_json", side_effect=RuntimeError("sin cuota")), \
                mock.patch.object(hinchada, "comentar_eventos", side_effect=RuntimeError("sin cuota")):
            noticia, actividad = eventos.repercusion(perfil(), self.ocurrido, "£")
        self.assertEqual(noticia.titular, "Simon Canales: multa por exceso de velocidad con su Porsche 911 Carrera")
        self.assertEqual(actividad.comentarios, [])


class TestEnLaPaginaVida(ayuda.PruebaDeInterfaz):
    def setUp(self):
        super().setUp()
        carpeta = Path(self.enterContext(tempfile.TemporaryDirectory()))
        (carpeta / "CmPlr1").write_bytes(f.construir_bytes())
        mock.patch.object(lector, "CARPETA_GUARDADOS", carpeta).start()
        mock.patch.object(partida_real, "identificar_jugadores", return_value={}).start()
        mock.patch.object(partida_real, "identificar_competiciones", return_value={}).start()
        mock.patch.object(hinchada, "comentar_eventos", return_value={}).start()
        mock.patch.object(eventos, "generar_json", return_value=eventos.NoticiaEvento(titular="Gripe", cuerpo="C")).start()
        mock.patch.object(eventos, "PROBABILIDAD_POR_SEMANA", 1).start()
        mock.patch.object(eventos, "TIPOS", [eventos.POR_ID["gripe"]]).start()
        self.addCleanup(mock.patch.stopall)
        self.pid = database.save_profile(PlayerProfile(nombre_jugador="Simon Canales", club_actual="Man Utd"))
        from roleplay.ui.vida import PaginaVida

        self.pagina = PaginaVida()
        self.avisos = []
        self.pagina.evento_inesperado.connect(lambda titulo, reto: self.avisos.append((titulo, reto)))
        self.pagina.actualizar()
        ayuda.esperar_tareas()

    def test_al_abrir_solo_marca_desde_donde_contar(self):
        self.assertEqual(database.get_estado_eventos(self.pid)["hasta"], "2027-01-16")
        self.assertTrue(self.pagina.eventos.isHidden())

    def test_con_el_autoguardado_pasa_y_se_ve(self):
        una_semana_despues = construir(f.construir_bytes(otros_partidos=[(20270123, f.LIGA, f.CITY, f.LIVERPOOL, 1, 0, True)]))
        self.pagina.acreditar_con(una_semana_despues)
        ayuda.esperar_tareas()
        self.assertEqual(self.avisos, [("Una gripe lo deja en cama", eventos.POR_ID["gripe"].reto)])
        self.assertFalse(self.pagina.eventos.isHidden())
        texto = ayuda.texto_visible(self.pagina.eventos_layout.itemAt(0).widget().text())
        self.assertIn("Una gripe lo deja en cama", texto)
        self.assertIn("Reto: Arranca el proximo partido en el banco", texto)
        self.assertIn("En la prensa: Gripe", texto)
        self.assertEqual([a.tipo for a in database.load_actividad_instagram(self.pid)], ["evento"])
        self.assertEqual(database.load_noticias_prensa(self.pid)[0].hitos, ["evento:gripe"])
        self.assertEqual(database.get_economia(self.pid)["saldo"] > 0, True)
