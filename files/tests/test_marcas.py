"""Marcas del mundo del futbol: buscar, firmar, las promos que piden y lo que pasa si no se cumplen."""

import os
import tempfile
import unittest
from datetime import date, timedelta
from pathlib import Path
from unittest import mock

import ayuda
import fabrica_partida as f
from roleplay import database
from roleplay.models import PlayerProfile
from roleplay.partida import lector
from roleplay.servicios import amor, eventos, hinchada, partida_real, patrocinios

HOY = date(2027, 1, 16)


def con_contrato(seguidores=500_000, reputacion=70):
    e, _, _ = patrocinios.buscar({"saldo": 0, "sueldo": 100_000}, 1, seguidores, reputacion, HOY)
    e, novedad = patrocinios.responder(e, True, HOY)
    return e, novedad


class TestMarcas(unittest.TestCase):
    def test_hay_marcas_de_todo_el_mundo_del_futbol(self):
        rubros = {m.rubro for m in patrocinios.MARCAS}
        self.assertLessEqual({"botines", "bebidas", "tecnologia", "electrodomesticos", "videojuegos", "relojes",
                              "moda", "autos", "aerolineas"}, rubros)
        self.assertGreaterEqual(len(patrocinios.MARCAS), 50)

    def test_buscar_trae_una_oferta_de_tu_nivel(self):
        e, nuevas, mensaje = patrocinios.buscar({}, 1, 500_000, 65, HOY)
        self.assertEqual(len(nuevas), patrocinios.MAXIMO_OFERTAS)  # varias para elegir
        self.assertEqual(len({o["rubro"] for o in nuevas}), len(nuevas))  # de rubros distintos
        for oferta in nuevas:
            marca = patrocinios.POR_ID[oferta["marca"]]
            self.assertLessEqual(marca.seguidores, 500_000)
            self.assertLessEqual(marca.reputacion, 65)
            self.assertIn(marca.nombre, mensaje)
        _, nada, mensaje = patrocinios.buscar(e, 1, 500_000, 65, HOY)  # ya hay ofertas esperando
        self.assertEqual(nada, [])

    def test_una_vez_por_semana_y_sin_nivel_te_dice_que_falta(self):
        e, nuevas, _ = patrocinios.buscar({}, 1, 500_000, 65, HOY)
        for oferta in nuevas:
            e, _ = patrocinios.responder(e, False, HOY, oferta["marca"])
        self.assertFalse(patrocinios.puede_buscar(e, HOY + timedelta(days=3))[0])
        with mock.patch.dict(os.environ, {"EAFC_DM_SIN_ESPERA": "1"}):  # la partida de prueba
            self.assertTrue(patrocinios.puede_buscar(e, HOY)[0])
        _, nada, mensaje = patrocinios.buscar({}, 1, 10, 10, HOY)
        self.assertEqual(nada, [])
        self.assertIn("pide", mensaje)

    def test_un_contrato_por_rubro(self):
        e, _ = con_contrato()
        rubro = patrocinios._rubro(e["patrocinios"]["contratos"][0])
        self.assertNotIn(rubro, {m.rubro for m in patrocinios.candidatas(e, 5_000_000, 100, HOY)})

    def test_al_firmar_ya_piden_la_campana_y_cumplir_paga_el_bono(self):
        e, _ = con_contrato()
        (contrato, promo), = patrocinios.promos_pendientes(e)
        self.assertIn(contrato["nombre"], promo["texto"])
        saldo = e["saldo"]
        e, novedad = patrocinios.cumplir(e, contrato["id"], HOY)
        self.assertGreater(e["saldo"], saldo)
        self.assertEqual(novedad.tono, "positiva")
        self.assertEqual(patrocinios.promos_pendientes(e), [])
        with self.assertRaises(ValueError):
            patrocinios.cumplir(e, contrato["id"], HOY)

    def test_no_cumplir_dos_veces_y_la_marca_se_va(self):
        e, _ = con_contrato()
        dia = HOY + timedelta(days=patrocinios.PLAZO_DIAS + 1)
        e, novedades = patrocinios.revisar(e, 1, 500_000, 70, dia)
        self.assertEqual([n.tono for n in novedades], ["mixta"])  # primera falta: se queja
        self.assertEqual(e["patrocinios"]["contratos"][0]["faltas"], 1)
        dia += timedelta(days=patrocinios.CADA_DIAS)
        e, _ = patrocinios.revisar(e, 1, 500_000, 70, dia)  # nueva promo
        self.assertTrue(patrocinios.promos_pendientes(e))
        e, novedades = patrocinios.revisar(e, 1, 500_000, 70, dia + timedelta(days=patrocinios.PLAZO_DIAS + 1))
        self.assertIn("rescinde", novedades[0].titulo)
        self.assertEqual(e["patrocinios"]["contratos"], [])

    def test_lo_concreto_de_cada_rubro(self):
        self.assertIn("tienda de electrodomesticos", patrocinios.texto_promo("evento", "LG", "electrodomesticos"))
        self.assertEqual(patrocinios.texto_promo("post", "Nike", "botines"), "Publicar un post en Instagram con Nike")

    def test_los_contratos_viejos_siguen_andando(self):
        viejo = {"marca": "samsung", "rubro": "smartphones"}
        self.assertEqual(patrocinios._rubro(viejo), "tecnologia")
        generica = {"marca": "bebida", "nombre": "una bebida isotonica"}
        self.assertEqual(patrocinios.nombre_de(generica), "Zuko")  # ahora es una marca de verdad
        e = {"patrocinios": {"contratos": [], "oferta": {"marca": "puma", "rubro": "botines"}}}
        self.assertEqual([o["marca"] for o in patrocinios.pendientes(e)], ["puma"])  # la oferta de antes sigue

    def test_hay_marcas_para_los_que_recien_empiezan(self):
        chicas = [m.nombre for m in patrocinios.MARCAS if m.seguidores <= 50_000]
        self.assertGreaterEqual(len(chicas), 8)
        self.assertNotIn("una", " ".join(m.nombre.lower() for m in patrocinios.MARCAS).split())  # ninguna generica


class TestEnVida(ayuda.PruebaDeInterfaz):
    def setUp(self):
        super().setUp()
        carpeta = Path(self.enterContext(tempfile.TemporaryDirectory()))
        (carpeta / "CmPlr1").write_bytes(f.construir_bytes())
        mock.patch.object(lector, "CARPETA_GUARDADOS", carpeta).start()
        mock.patch.object(partida_real, "identificar_jugadores", return_value={}).start()
        mock.patch.object(partida_real, "identificar_competiciones", return_value={}).start()
        mock.patch.object(hinchada, "comentar_eventos", return_value={}).start()
        mock.patch.object(eventos, "PROBABILIDAD_POR_SEMANA", 0).start()
        mock.patch.object(amor, "PROBABILIDAD_POR_SEMANA", 0).start()
        mock.patch.object(patrocinios, "PROBABILIDAD_OFERTA", 0).start()
        self.addCleanup(mock.patch.stopall)
        self.addCleanup(ayuda.esperar_tareas)
        self.pid = database.save_profile(PlayerProfile(nombre_jugador="Simon Canales", club_actual="Man Utd"))
        database.sumar_seguidores(self.pid, 2_000_000)
        from roleplay.ui.vida import PaginaVida

        self.pagina = PaginaVida()
        self.pagina.actualizar()
        ayuda.esperar_tareas()

    def test_buscar_firmar_y_publicar_la_promo(self):
        self.pagina.buscar_marcas_btn.click()
        ofertas = patrocinios.pendientes(database.get_economia(self.pid))
        self.assertEqual(len(ofertas), patrocinios.MAXIMO_OFERTAS)
        for oferta in ofertas:  # firma todas: se puede tener varias marcas a la vez
            self.pagina.responder_patrocinio(True, oferta["marca"])
        self.assertEqual(len(database.get_economia(self.pid)["patrocinios"]["contratos"]), patrocinios.MAXIMO_OFERTAS)
        ayuda.esperar_tareas()
        e = database.get_economia(self.pid)
        contrato, promo = patrocinios.promos_pendientes(e)[0]
        promo["tipo"] = "post"  # que sea un post, para probar Instagram
        database.set_economia(self.pid, e)
        with mock.patch.object(type(self.pagina), "_texto_del_post", return_value="Con la marca #publi"):
            self.pagina.hacer_promo(contrato["id"])
            ayuda.esperar_tareas()
        self.assertEqual(database.load_instagram_posts(self.pid)[0].texto, "Con la marca #publi")
        pendientes = [c["id"] for c, _ in patrocinios.promos_pendientes(database.get_economia(self.pid))]
        self.assertNotIn(contrato["id"], pendientes)  # esa promo quedo cumplida (las otras marcas esperan la suya)

    def test_exclusividad_por_rubro(self):
        e = database.get_economia(self.pid)
        e.setdefault("patrocinios", {})["contratos"] = [{"id": "x", "marca": "coca_cola", "nombre": "Coca-Cola",
                                                         "rubro": "bebidas", "semanal": 1, "desde": "2027-01-01",
                                                         "hasta": "2029-01-01", "ultima_promo": "2027-01-16"}]
        database.set_economia(self.pid, e)
        self.pagina.buscar_marcas_btn.click()
        ofertas = patrocinios.pendientes(database.get_economia(self.pid))
        self.assertNotIn("bebidas", {o["rubro"] for o in ofertas})  # Pepsi no te ofrece si sos de Coca-Cola
        self.assertIn("Exclusividad", self.pagina.marcas_exclusividad.text())


if __name__ == "__main__":
    unittest.main()
