"""Economia y estilo de vida: sueldo real, compras, donaciones y su repercusion."""

import tempfile
from datetime import date
from pathlib import Path
from unittest import mock

import ayuda
import fabrica_partida as f
from roleplay import database
from roleplay.models import PlayerProfile
from roleplay.partida import lector
from roleplay.partida.carrera import Partido, construir
from roleplay.servicios import amor, economia, eventos, hinchada, partida_real
from roleplay.servicios.economia import POR_ID

HOY = date(2027, 1, 16)
NETO_SEMANAL = round(f.SUELDO * economia.NETO)  # 79.750


class TestDinero(ayuda.PruebaConBase):
    def test_formato(self):
        self.assertEqual(economia.dinero(145_000, "£"), "£145.000")
        self.assertEqual(economia.dinero(4_200_000, "£"), "£4,2 M")
        self.assertEqual(economia.dinero(45_000_000, "€"), "€45 M")
        self.assertEqual(economia.dinero(-1_500, "£"), "-£1.500")

    def test_moneda_segun_la_liga_del_club(self):
        self.assertEqual(economia.moneda_de(construir(f.construir_bytes())), "£")  # Premier League
        self.assertEqual(economia.moneda_de(None), "€")

    def test_el_sueldo_sale_de_la_partida(self):
        self.assertEqual(construir(f.construir_bytes()).sueldo_usuario, 145_000)


class TestSueldo(ayuda.PruebaConBase):
    def test_la_primera_vez_lo_cobrado_en_la_temporada(self):
        e = economia.acreditar(None, HOY, f.SUELDO)
        semanas = (HOY - date(2026, 7, 1)).days / 7
        self.assertEqual(e["saldo"], round(f.SUELDO * economia.NETO * semanas))
        self.assertEqual(e["hasta"], "2027-01-16")
        self.assertEqual(e["movimientos"][0]["concepto"], "Lo cobrado en lo que va de la temporada")

    def test_se_cobra_con_los_dias_del_juego_y_una_sola_vez(self):
        e = economia.acreditar(None, HOY, f.SUELDO)
        saldo = e["saldo"]
        self.assertEqual(economia.acreditar(e, HOY, f.SUELDO)["saldo"], saldo)  # mismo dia: nada
        una_semana = economia.acreditar(e, date(2027, 1, 23), f.SUELDO)
        self.assertEqual(una_semana["saldo"], saldo + NETO_SEMANAL)
        self.assertEqual(e["saldo"], saldo)  # no toca el original

    def test_el_mantenimiento_se_descuenta(self):
        e = economia.acreditar(None, HOY, f.SUELDO)
        e["saldo"] = 20_000_000
        e = economia.comprar(e, POR_ID["mansion"], HOY)
        self.assertEqual(economia.mantenimiento_semanal(e), 15_000)
        despues = economia.acreditar(e, date(2027, 1, 23), f.SUELDO)
        self.assertEqual(despues["saldo"], e["saldo"] + NETO_SEMANAL - 15_000)
        self.assertEqual(despues["movimientos"][0]["concepto"], "Mantenimiento de lo que tenes")

    def test_contrato_nuevo_y_partida_anterior(self):
        e = economia.acreditar(None, HOY, f.SUELDO)
        nuevo = economia.acreditar(e, HOY, 200_000)
        self.assertEqual(nuevo["sueldo"], 200_000)
        self.assertIn("Contrato nuevo", nuevo["movimientos"][0]["concepto"])
        atras = economia.acreditar(e, date(2027, 1, 1), f.SUELDO)  # se cargo un guardado anterior
        self.assertEqual((atras["saldo"], atras["hasta"]), (e["saldo"], "2027-01-01"))


class TestComprarYVender(ayuda.PruebaConBase):
    def setUp(self):
        super().setUp()
        self.e = economia.acreditar(None, HOY, f.SUELDO)  # ~£2,3 M

    def test_sin_plata_no_se_compra(self):
        with self.assertRaises(economia.SinPlata):
            economia.comprar(self.e, POR_ID["jet"], HOY)

    def test_compra_donacion_y_venta(self):
        con_auto = economia.comprar(self.e, POR_ID["auto_aleman"], HOY)
        self.assertEqual(con_auto["saldo"], self.e["saldo"] - 180_000)
        self.assertTrue(economia.tiene(con_auto, "auto_aleman"))
        self.assertEqual(economia.patrimonio(con_auto), round(180_000 * economia.VENTA))
        donado = economia.comprar(con_auto, POR_ID["hospital"], HOY)
        self.assertEqual(len(donado["posesiones"]), 1)  # donar no deja nada
        vendido, recuperado = economia.vender(donado, donado["posesiones"][0]["id"], HOY)
        self.assertEqual(recuperado, 126_000)
        self.assertEqual(vendido["posesiones"], [])
        self.assertEqual(vendido["movimientos"][0]["concepto"], "Venta: Deportivo aleman")


class TestEfecto(ayuda.PruebaConBase):
    def perfil(self, personalidad="reservado"):
        return PlayerProfile(id=1, nombre_jugador="Simon Canales", personalidad=personalidad)

    def test_donar_siempre_suma(self):
        e = economia.efecto(POR_ID["fundacion"], self.perfil(), 10_000, 50, f.SUELDO, en_mala_racha=True)
        self.assertGreater(e.reputacion, 0)
        self.assertGreater(e.seguidores, 0)
        self.assertEqual((e.es_noticia, e.tono), (True, "positiva"))
        chica = economia.efecto(POR_ID["damnificados"], self.perfil(), 10_000, 50, f.SUELDO, False)
        self.assertLess(chica.reputacion, e.reputacion)

    def test_presumir_en_mala_racha_resta(self):
        humilde = economia.efecto(POR_ID["jet"], self.perfil("humilde"), 10_000, 50, f.SUELDO, en_mala_racha=True)
        self.assertEqual((humilde.reputacion, humilde.tono, humilde.es_noticia), (-4, "negativa", True))
        self.assertIn("mala racha", humilde.motivo)
        show = economia.efecto(POR_ID["jet"], self.perfil("carismatico"), 10_000, 50, f.SUELDO, en_mala_racha=False)
        self.assertEqual((show.reputacion, show.tono), (0, "mixta"))
        self.assertGreater(show.seguidores, economia.efecto(
            POR_ID["jet"], self.perfil("reservado"), 10_000, 50, f.SUELDO, False).seguidores)

    def test_algo_discreto_no_es_noticia(self):
        e = economia.efecto(POR_ID["reloj_suizo"], self.perfil(), 10_000, 50, f.SUELDO, False)
        self.assertEqual((e.es_noticia, e.reputacion, e.tono), (False, 0, "neutral"))

    def test_mala_racha(self):
        c = construir(f.construir_bytes())
        self.assertFalse(economia.mala_racha(c))  # G E G
        c.partidos += [
            Partido(date(2027, 1, 20), f.LIGA, f.LIVERPOOL, f.MAN_UTD, 2, 0, True),
            Partido(date(2027, 1, 24), f.LIGA, f.CITY, f.MAN_UTD, 3, 1, True),
        ]
        self.assertTrue(economia.mala_racha(c))


class TestRepercusion(ayuda.PruebaConBase):
    def setUp(self):
        super().setUp()
        self.perfil = PlayerProfile(nombre_jugador="Simon Canales")
        self.perfil.id = database.save_profile(self.perfil)
        self.efecto = economia.Efecto(120, -3, True, "negativa", "en plena mala racha del equipo")

    def test_la_noticia_la_escribe_el_motor(self):
        noticia, actividad = economia.repercusion(self.perfil, POR_ID["jet"], self.efecto, "£", "2027-01-16")
        self.assertIn("jet privado", noticia.titular.lower())
        self.assertIn("en plena mala racha del equipo", noticia.cuerpo)
        self.assertIn("£45 M", noticia.cuerpo)
        self.assertEqual((noticia.tono, noticia.categoria, noticia.hitos), ("negativa", "jugador", ["compra:jet"]))
        self.assertEqual((actividad.tipo, actividad.titulo, actividad.crecimiento_seguidores), ("compra", "Jet privado", 120))
        self.assertTrue(actividad.comentarios)
        self.assertTrue(all(c["autor"] and c["texto"] and c["tono"] for c in actividad.comentarios))

    def test_lo_discreto_solo_lo_comentan_los_hinchas(self):
        discreto = economia.Efecto(10, 0, False, "neutral", "")
        noticia, actividad = economia.repercusion(self.perfil, POR_ID["reloj_suizo"], discreto, "£", "2027-01-16")
        self.assertIsNone(noticia)
        self.assertEqual(actividad.titulo, "Reloj suizo")
        self.assertTrue(actividad.comentarios)


class TestPaginaVida(ayuda.PruebaDeInterfaz):
    def setUp(self):
        super().setUp()
        carpeta = Path(self.enterContext(tempfile.TemporaryDirectory()))
        (carpeta / "CmPlr1").write_bytes(f.construir_bytes())
        mock.patch.object(lector, "CARPETA_GUARDADOS", carpeta).start()
        mock.patch.object(partida_real, "identificar_jugadores", return_value={}).start()
        mock.patch.object(partida_real, "identificar_competiciones", return_value={}).start()
        mock.patch.object(hinchada, "comentar_eventos", return_value={}).start()
        mock.patch.object(eventos, "PROBABILIDAD_POR_SEMANA", 0).start()  # sin eventos inesperados: aca se prueba la plata
        mock.patch.object(amor, "PROBABILIDAD_POR_SEMANA", 0).start()  # ni la vida sentimental
        self.addCleanup(mock.patch.stopall)
        self.pid = database.save_profile(
            PlayerProfile(nombre_jugador="Simon Canales", club_actual="Man Utd", personalidad="humilde")
        )
        from roleplay.ui.vida import PaginaVida

        self.pagina = PaginaVida()
        self.pagina.actualizar()
        ayuda.esperar_tareas()

    def _boton(self, layout, nombre):
        from PySide6.QtWidgets import QPushButton

        for i in range(layout.count()):
            fila = layout.itemAt(i).layout()
            for j in range(fila.count() if fila else 0):
                widget = fila.itemAt(j).widget()
                if isinstance(widget, QPushButton) and f"comprar_{widget.property('articulo')}" == nombre:
                    return widget
        raise AssertionError(f"no esta el boton {nombre}")

    def test_cobra_al_abrir(self):
        self.assertTrue(self.pagina.contenido.isVisibleTo(self.pagina))
        e = database.get_economia(self.pid)
        self.assertEqual((e["sueldo"], e["hasta"]), (145_000, "2027-01-16"))
        self.assertEqual(self.pagina.mosaico_saldo.numero.text(), economia.dinero(e["saldo"], "£"))
        self.assertIn("£145.000 por semana", self.pagina.subtitulo_label.text())

    def test_comprar_mueve_seguidores_y_deja_la_repercusion(self):
        seguidores = database.get_seguidores(self.pid)
        saldo = database.get_economia(self.pid)["saldo"]
        self.pagina._elegir_categoria("moda")
        self._boton(self.pagina.tienda_layout, "comprar_coleccion_moda").click()
        ayuda.esperar_tareas()
        e = database.get_economia(self.pid)
        self.assertEqual(e["saldo"], saldo - 400_000)
        self.assertGreater(database.get_seguidores(self.pid), seguidores)
        self.assertEqual(database.get_reputacion_actual(self.pid), 50 - 1)  # humilde y ostentoso
        self.assertEqual([a.tipo for a in database.load_actividad_instagram(self.pid)], ["compra"])
        self.assertIn("coleccion de alta costura", database.load_noticias_prensa(self.pid)[0].titular.lower())
        self.assertIn("Compraste: Coleccion de alta costura", self.pagina.resultado_label.text())
        self.assertFalse(self._boton(self.pagina.tienda_layout, "comprar_coleccion_moda").isEnabled())  # ya lo tiene
        self.assertTrue(self.pagina._botones_categoria["moda"].isChecked())
        self.assertIn("En la prensa:", self.pagina.resultado_label.text())

    def test_la_noticia_de_una_compra_anterior_no_pisa_la_tarjeta(self):
        self.pagina._elegir_categoria("reloj")
        self._boton(self.pagina.tienda_layout, "comprar_cadena").click()  # su noticia llega despues...
        self._boton(self.pagina.donaciones_layout, "comprar_damnificados").click()
        ayuda.esperar_tareas()
        self.assertIn("Donaste", self.pagina.resultado_label.text())
        self.assertEqual(self.pagina.resultado_label.text().count("En la prensa:"), 1)

    def test_los_botones_de_comprar_tienen_el_estilo_primario(self):
        self.pagina._elegir_categoria("reloj")
        self.assertEqual(self._boton(self.pagina.tienda_layout, "comprar_reloj_suizo").objectName(), "primario")

    def test_lo_que_no_alcanza_no_se_puede_comprar(self):
        self.pagina._elegir_categoria("avion")
        jet = self._boton(self.pagina.tienda_layout, "comprar_jet")
        self.assertFalse(jet.isEnabled())
        self.assertIn("Te faltan", jet.toolTip())

    def test_donar_sube_la_reputacion(self):
        self._boton(self.pagina.donaciones_layout, "comprar_hospital").click()
        ayuda.esperar_tareas()
        self.assertGreater(database.get_reputacion_actual(self.pid), 50)
        self.assertEqual(database.get_economia(self.pid)["posesiones"], [])

    def test_vender(self):
        self.pagina._elegir_categoria("reloj")
        self._boton(self.pagina.tienda_layout, "comprar_reloj_suizo").click()
        ayuda.esperar_tareas()
        posesion = database.get_economia(self.pid)["posesiones"][0]
        self.pagina._on_vender(posesion["id"])
        self.assertEqual(database.get_economia(self.pid)["posesiones"], [])
        self.assertIn("recuperaste £42.000", self.pagina.resultado_label.text())

    def test_en_vivo_se_cobra_con_cada_autoguardado(self):
        saldo = database.get_economia(self.pid)["saldo"]
        una_semana_despues = construir(f.construir_bytes(otros_partidos=[(20270123, f.LIGA, f.CITY, f.LIVERPOOL, 1, 0, True)]))
        self.pagina.acreditar_con(una_semana_despues)
        self.assertEqual(database.get_economia(self.pid)["saldo"], saldo + NETO_SEMANAL)


# ---- seguidores por tier y patrocinios (datos de prueba: tests/datos_ecosistema.py) ----

from roleplay.servicios import patrocinios  # noqa: E402


class TestSeguidores(ayuda.PruebaConBase):
    def test_la_base_y_la_exposicion_segun_el_club_y_los_goles(self):
        self.assertGreater(hinchada.base_de_seguidores(1, 60), 100 * hinchada.base_de_seguidores(3, 60))
        normal = hinchada.exposicion(3, 10, 30)
        estrella = hinchada.exposicion(1, 80, 40, premios=3)
        self.assertGreater(estrella, 4 * normal)  # 80 goles en 40 partidos en un gigante: mucho mas ruido, pero acotado
        self.assertLessEqual(hinchada.exposicion(1, 500, 10, 99), hinchada.TOPE_EXPOSICION)


class TestPatrocinios(ayuda.PruebaConBase):
    def test_oferta_firma_y_cobra_con_el_sueldo(self):
        hoy = date(2026, 10, 1)
        e = economia.acreditar(None, hoy, 100_000)
        with mock.patch.object(patrocinios, "PROBABILIDAD_OFERTA", 1.0):
            e, _ = patrocinios.revisar(e, 1, seguidores=500_000, reputacion=70, hoy=hoy)
        oferta = patrocinios.pendientes(e)[0]
        self.assertIn(oferta["marca"], {m.id for m in patrocinios.candidatas(e, 500_000, 70, hoy)})
        self.assertNotIn(oferta["marca"], {"apple", "rolex", "gucci", "samsung"})  # no le da el nivel
        e, novedad = patrocinios.responder(e, True, hoy)
        self.assertEqual(novedad.tono, "positiva")
        self.assertIn(oferta["nombre"], novedad.titulo)
        saldo = e["saldo"]
        e2 = economia.acreditar(e, date(2026, 10, 8), 100_000)
        semanal = e["patrocinios"]["contratos"][0]["semanal"]
        self.assertEqual(e2["saldo"] - saldo, round(100_000 * economia.NETO) + round(semanal * economia.NETO))
        self.assertTrue(any("Patrocinios" in m["concepto"] for m in e2["movimientos"]))

    def test_rescinden_por_imagen_o_escandalo(self):
        hoy = date(2026, 10, 1)
        e = {"saldo": 1_000_000, "patrocinios": {"contratos": [
            {"id": "a", "marca": "nike", "nombre": "Nike", "rubro": "botines", "semanal": 50_000,
             "desde": "2026-01-01", "hasta": "2027-12-31"}], "oferta": None, "rechazadas": {}}}
        caida, novedades = patrocinios.revisar(e, 1, 500_000, reputacion=40, hoy=hoy)  # muy debajo de lo que pide
        self.assertEqual(caida["patrocinios"]["contratos"], [])
        self.assertEqual(novedades[0].tono, "negativa")
        with mock.patch.object(patrocinios, "PROBABILIDAD_RESCISION_ESCANDALO", 1.0):
            multado, novedades = patrocinios.revisar(e, 1, 500_000, reputacion=80, hoy=hoy, escandalo=True)
        self.assertEqual(multado["saldo"], 1_000_000 - 50_000 * patrocinios.MULTA_SEMANAS)
        self.assertTrue(patrocinios.hubo_escandalo({"historial": [{"fecha": "2026-09-25", "tono": "negativa"}]}, hoy))
