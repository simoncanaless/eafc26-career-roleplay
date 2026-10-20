"""Ofertas de otros clubes: llegan segun tu nivel, y mirarlas no es querer irse."""

import os
import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest import mock

import ayuda
import fabrica_partida as f
from roleplay import database
from roleplay.models import PlayerProfile
from roleplay.partida import lector
from roleplay.partida.carrera import construir
from roleplay.servicios import amor, clubes, contratos, eventos, hinchada, ofertas, partida_real

ENERO = date(2027, 1, 16)


def dado_que_si():
    import random

    dado = random.Random(1)
    dado.random = lambda: 0.0  # siempre hay oferta
    return dado


class ConOfertas(unittest.TestCase):
    def setUp(self):
        super().setUp()
        mock.patch.dict(os.environ, {"EAFC_SIN_OFERTAS": "0"}).start()
        self.addCleanup(mock.patch.stopall)
        self.carrera = construir(f.construir_bytes())
        self.e = {"saldo": 0, "sueldo": f.SUELDO, "hasta": "2027-01-16"}


class TestOfertas(ConOfertas):
    def test_el_sueldo_segun_el_club_y_la_media(self):
        self.assertEqual(ofertas.sueldo_de_mercado(1, 80), 150_000)
        self.assertGreater(ofertas.sueldo_de_mercado(1, 85), 230_000)
        self.assertLess(ofertas.sueldo_de_mercado(3, 80), ofertas.sueldo_de_mercado(2, 80))

    def test_te_buscan_otros_clubes_no_el_tuyo(self):
        equipos = [e for e, _, _ in ofertas.interesados(self.carrera, f.MAN_UTD, 79, 90)]
        self.assertTrue(equipos)
        self.assertNotIn(f.MAN_UTD, equipos)

    def test_solo_en_la_ventana_de_pases(self):
        e, novedades = ofertas.revisar(self.e, self.carrera, 1, date(2027, 3, 10), 90, dado=dado_que_si())
        self.assertEqual(novedades, [])
        e, novedades = ofertas.revisar(self.e, self.carrera, 1, ENERO, 90, dado=dado_que_si())
        oferta = novedades[0]["oferta"]
        self.assertEqual(novedades[0]["tipo"], "nueva")
        self.assertGreater(oferta["sueldo"], f.SUELDO)  # si no paga mas, no te moverias
        self.assertEqual(set(oferta["condiciones"]), {c.id for c in contratos.CLAUSULAS})
        _, otra_vez = ofertas.revisar(e, self.carrera, 1, ENERO, 90, dado=dado_que_si())
        self.assertEqual(otra_vez, [])  # una revision por semana

    def _con_oferta(self):
        e, novedades = ofertas.revisar(self.e, self.carrera, 1, ENERO, 90, dado=dado_que_si())
        return e, novedades[0]["oferta"]

    def test_usarla_para_negociar_da_palanca(self):
        e, oferta = self._con_oferta()
        e, _ = ofertas.responder(e, oferta["id"], "negociar", ENERO)
        self.assertGreater(ofertas.palanca_extra(e, ENERO), 0)
        sin = contratos.abrir("Man Utd", 1, 70, ENERO, dado=__import__("random").Random(1))
        con = contratos.abrir("Man Utd", 1, 70, ENERO, dado=__import__("random").Random(1),
                              extra=ofertas.palanca_extra(e, ENERO))
        self.assertGreater(con["techo"]["gol"], sin["techo"]["gol"])

    def test_aceptar_y_el_traspaso_lo_hace_el_juego(self):
        e, oferta = self._con_oferta()
        e, _ = ofertas.responder(e, oferta["id"], "aceptar", ENERO)
        _, novedades = ofertas.revisar(e, self.carrera, 1, ENERO, 90)
        self.assertEqual(novedades, [])  # sigue en su club: todavia nada
        traspasado = construir(f.construir_bytes(fichajes={f.USUARIO: oferta["equipo"]}))
        e, novedades = ofertas.revisar(e, traspasado, 1, ENERO, 90)
        self.assertEqual(novedades[0]["tipo"], "cumplida")
        self.assertEqual(e["contrato"]["club"], oferta["club"])  # las primas de la oferta son su contrato
        self.assertEqual(e["contrato"]["condiciones"], oferta["condiciones"])

    def test_si_el_traspaso_no_llega_el_acuerdo_se_cae(self):
        e, oferta = self._con_oferta()
        e, _ = ofertas.responder(e, oferta["id"], "aceptar", ENERO)
        _, novedades = ofertas.revisar(e, self.carrera, 1, date(2027, 4, 1), 90)
        self.assertEqual(novedades[0]["tipo"], "caida")

    def test_escuchar_no_es_querer_irse(self):
        opcion = next(o for o in clubes.DECISIONES["tentado"].opciones if o.id == "escuchar")
        self.assertEqual(opcion.carino, 0)
        self.assertNotEqual(opcion.tono, "negativa")


class TestEnVida(ayuda.PruebaDeInterfaz):
    def setUp(self):
        super().setUp()
        mock.patch.dict(os.environ, {"EAFC_SIN_OFERTAS": "0"}).start()
        carpeta = Path(self.enterContext(tempfile.TemporaryDirectory()))
        (carpeta / "CmPlr1").write_bytes(f.construir_bytes())
        mock.patch.object(lector, "CARPETA_GUARDADOS", carpeta).start()
        mock.patch.object(partida_real, "identificar_jugadores", return_value={}).start()
        mock.patch.object(partida_real, "identificar_competiciones", return_value={}).start()
        mock.patch.object(hinchada, "comentar_eventos", return_value={}).start()
        mock.patch.object(eventos, "PROBABILIDAD_POR_SEMANA", 0).start()
        mock.patch.object(amor, "PROBABILIDAD_POR_SEMANA", 0).start()
        mock.patch.object(ofertas, "probabilidad", return_value=1.0).start()
        self.addCleanup(mock.patch.stopall)
        self.addCleanup(ayuda.esperar_tareas)
        self.pid = database.save_profile(PlayerProfile(nombre_jugador="Simon Canales", club_actual="Man Utd"))
        from roleplay.ui.vida import PaginaVida

        self.pagina = PaginaVida()
        self.pagina.actualizar()
        ayuda.esperar_tareas()

    def test_la_oferta_llega_y_se_acepta(self):
        self.assertFalse(self.pagina.ofertas.isHidden())
        oferta = ofertas.abiertas(database.get_economia(self.pid))[0]
        botones = {b.property("oferta"): b for b in self.pagina.findChildren(type(self.pagina.negociar_btn))
                   if b.property("oferta")}
        botones[f"{oferta['id']}:aceptar"].click()
        self.assertEqual(ofertas.abiertas(database.get_economia(self.pid))[0]["estado"], "aceptada")


if __name__ == "__main__":
    unittest.main()
