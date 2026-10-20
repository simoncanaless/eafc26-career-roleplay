"""El concesionario: autos configurables, pedido y entrega con los dias del juego."""

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
from roleplay.servicios import amor, autos, economia, eventos, hinchada, partida_real
from roleplay.servicios.autos import Configuracion

HOY = date(2027, 1, 16)
# la partida dos semanas despues: el 911 (14 dias) ya llego
DOS_SEMANAS = [(20270131, f.LIGA, f.CITY, f.LIVERPOOL, 1, 0, True)]


class TestPrecioYDescripcion(ayuda.PruebaConBase):
    def test_el_precio_suma_las_opciones(self):
        self.assertEqual(autos.precio(Configuracion("porsche_911")), 95_000)
        completo = Configuracion("porsche_911", acabado="metalizado", llantas="forjadas", extras=["carbono"],
                                 patente="SC 9")
        # 95.000 x (1 + 2% + 3% + 8%) + 25.000 de la patente, redondeado a 100
        self.assertEqual(autos.precio(completo), 132_400)

    def test_la_descripcion(self):
        config = Configuracion("ferrari_296", color="amarillo", acabado="mate", pinzas="rojas", franja="lateral",
                               color_franja="negro", interior="tostado", extras=["escape"], patente="SC 9")
        self.assertEqual(
            autos.describir(config),
            'amarillo mate, pinzas rojas, franja lateral negro, interior de cuero tostado, escape deportivo, patente "SC 9"',
        )
        self.assertEqual(autos.describir(Configuracion("ferrari_296")), "rojo brillante")

    def test_patente_y_guardado(self):
        self.assertEqual(autos.limpiar_patente("sc-9 !!"), "SC9")
        self.assertEqual(autos.limpiar_patente("simon canales"), "SIMON CA")
        config = Configuracion("lambo_urus", extras=["carbono"], patente="X 1")
        self.assertEqual(Configuracion.desde_dict(config.a_dict()), config)
        self.assertEqual(Configuracion.desde_dict({"modelo": "lambo_urus", "algo_viejo": 1}).modelo, "lambo_urus")

    def test_cada_modelo_tiene_su_dibujo(self):
        from roleplay.ui.configurador import SILUETAS

        self.assertTrue(all(m.carroceria in SILUETAS for m in autos.MODELOS))
        self.assertEqual(len({m.id for m in autos.MODELOS}), len(autos.MODELOS))


class TestDibujo(ayuda.PruebaDeInterfaz):
    def test_el_svg_es_valido_y_refleja_la_configuracion(self):
        from PySide6.QtCore import QByteArray
        from PySide6.QtSvg import QSvgRenderer

        from roleplay.ui.configurador import svg_auto

        for modelo in ("ferrari_296", "ferrari_roma", "lambo_urus"):
            config = Configuracion(modelo, color="azul", franja="doble", color_franja="amarillo",
                                   extras=["carbono", "escape"], patente="SC 9")
            svg = svg_auto(config)
            self.assertTrue(QSvgRenderer(QByteArray(svg.encode())).isValid(), modelo)
            self.assertIn(autos.opcion("color", "amarillo").color, svg)  # la franja
            self.assertIn("#1A1B1E", svg)  # la fibra de carbono
            self.assertIn(">SC 9</text>", svg)
            self.assertNotIn("clip-path", svg)  # Qt no lo dibuja
        self.assertNotIn("<text", svg_auto(Configuracion("ferrari_296")))  # sin patente, sin chapa

    def test_cada_familia_con_lo_suyo(self):
        import re

        from PySide6.QtCore import QByteArray
        from PySide6.QtSvg import QSvgRenderer

        from roleplay.ui.configurador import CROMO, SILUETAS, svg_auto

        for modelo in autos.MODELOS:  # todos se dibujan
            svg = svg_auto(Configuracion(modelo.id))
            self.assertTrue(QSvgRenderer(QByteArray(svg.encode())).isValid(), modelo.id)
            self.assertEqual(svg.count('fill="#0B0C0E"'), 2, modelo.id)  # los dos pasarruedas, tambien en un todoterreno
        self.assertEqual({m.carroceria for m in autos.MODELOS + autos.DESCONTINUADOS}, set(SILUETAS))  # y ninguna familia sobra
        aleron = 'M 318 52'
        self.assertIn(aleron, svg_auto(Configuracion("porsche_gt3rs")))
        self.assertNotIn(aleron, svg_auto(Configuracion("porsche_911")))
        self.assertIn(CROMO, svg_auto(Configuracion("bugatti_tourbillon")))  # la linea en C
        g = SILUETAS["g_real"]  # la rueda de auxilio va colgada detras de la carroceria
        self.assertGreater(max(float(x) for x in re.findall(r"([\d.]+) [\d.]+", g.detalles)), g.cola + 10)

    def test_ningun_auto_se_sale_del_dibujo(self):
        """Un todoterreno es mas alto que ancho a esta escala: se achica, no se corta el techo."""
        from PySide6.QtCore import QByteArray, QRectF
        from PySide6.QtGui import QColor, QImage, QPainter
        from PySide6.QtSvg import QSvgRenderer

        from roleplay.ui.configurador import svg_auto

        for modelo in autos.MODELOS:
            img = QImage(400, 170, QImage.Format.Format_ARGB32)
            img.fill(QColor(0, 0, 0, 0))
            pintor = QPainter(img)
            QSvgRenderer(QByteArray(svg_auto(Configuracion(modelo.id)).encode())).render(pintor, QRectF(0, 0, 400, 170))
            pintor.end()
            bordes = [(x, 0) for x in range(400)] + [(0, y) for y in range(140)] + [(399, y) for y in range(140)]
            self.assertFalse(any(img.pixelColor(x, y).alpha() for x, y in bordes), modelo.id)

    def test_el_parante_no_se_sale_de_la_ventana(self):
        from roleplay.ui.configurador import _ventana_en

        ventana = "M 100 50 L 200 40 L 210 80 L 100 80 Z"
        arriba, abajo = _ventana_en(ventana, 150)
        self.assertAlmostEqual(arriba, 45)
        self.assertAlmostEqual(abajo, 80)
        self.assertIsNone(_ventana_en("M 100 50 C 120 40 180 40 200 50 Z", 150))  # con curvas no adivina


class TestConfigurador(ayuda.PruebaDeInterfaz):
    def test_elegir_cambia_precio_y_dibujo(self):
        from roleplay.ui.configurador import Configurador

        dialogo = Configurador(autos.POR_ID["porsche_911"], saldo=120_000, moneda="£")
        self.assertEqual(dialogo.precio_label.text(), "£95.000")
        self.assertTrue(dialogo.pedir_btn.isEnabled())
        dialogo._botones["acabado"]["mate"].click()
        dialogo._botones["color"]["verde"].click()
        dialogo._extras["carbono"].click()
        dialogo.patente_edit.setText("sc 9")
        config = dialogo.configuracion()
        self.assertEqual((config.acabado, config.color, config.extras, config.patente), ("mate", "verde", ["carbono"], "SC 9"))
        self.assertEqual(dialogo.precio_label.text(), economia.dinero(autos.precio(config), "£"))
        self.assertEqual(dialogo.vista.config.color, "verde")
        self.assertFalse(dialogo.pedir_btn.isEnabled())  # 133.600 > 120.000
        self.assertEqual(dialogo.pedir_btn.text(), "NO TE ALCANZA")
        self.assertFalse(dialogo._botones["color_franja"]["negro"].isVisibleTo(dialogo))  # sin franja, sin su color
        dialogo._botones["franja"]["lateral"].click()
        self.assertTrue(dialogo._botones["color_franja"]["negro"].isVisibleTo(dialogo))


class TestConLaWebDeLaMarca(ayuda.PruebaDeInterfaz):
    """El configurador con la web oficial adentro. Sin pantalla Chromium no
    dibuja, asi que aca va un navegador de mentira que devuelve una foto."""

    def setUp(self):
        super().setUp()
        from PySide6.QtGui import QColor, QImage
        from PySide6.QtWidgets import QLabel

        from roleplay.ui import configurador

        self.imagen = QImage(1600, 900, QImage.Format.Format_RGB32)
        self.imagen.fill(QColor("#C8102E"))
        imagen = self.imagen

        class NavegadorFalso(QLabel):
            def foto(self):
                return imagen

        self.urls = []

        def crear(url, parent=None):
            self.urls.append(url)
            return NavegadorFalso("la web", parent)

        mock.patch.object(configurador, "crear_navegador", crear).start()
        self.addCleanup(mock.patch.stopall)
        self.dialogo = configurador.Configurador(autos.POR_ID["porsche_911"], saldo=500_000, moneda="£")

    def test_cada_modelo_tiene_su_web_oficial(self):
        from urllib.parse import urlparse

        dominios = {
            "Ferrari": "ferrari.com", "Porsche": "porsche.com", "Lamborghini": "lamborghini.com",
            "McLaren": "mclaren.com", "Mercedes-AMG": "mercedes-benz.co.uk", "Rolls-Royce": "rolls-roycemotorcars.com",
            "Bentley": "bentleymotors.com", "Aston Martin": "astonmartin.com", "Range Rover": "rangerover.com",
            "Bugatti": "bugatti.com",
        }
        for modelo in autos.MODELOS:
            url = urlparse(modelo.url_configurador)
            self.assertEqual(url.scheme, "https", modelo.id)
            self.assertTrue(url.hostname.endswith(dominios[modelo.marca]), modelo.id)

    def test_sin_pantalla_queda_el_dibujo(self):
        from roleplay.ui import navegador

        self.assertFalse(navegador.disponible())  # (las pruebas corren sin pantalla)

    def test_abre_la_web_y_la_foto_se_saca_sola_al_pedir(self):
        self.assertEqual(self.urls, ["https://configurator.porsche.com/en-WW/mode/model/9921B2"])
        self.assertIsNone(self.dialogo.vista)  # la web en lugar del dibujo
        self.assertEqual(self.dialogo.precio_label.text(), "£95.000")  # el panel del juego sigue igual
        self.dialogo._botones["acabado"]["mate"].click()
        self.assertEqual(self.dialogo.configuracion().acabado, "mate")
        self.dialogo.pedir_btn.click()
        self.assertEqual(self.dialogo.result(), 1)
        self.assertEqual(self.dialogo.foto.size(), self.imagen.size())

    def test_pegar_una_imagen(self):
        from PySide6.QtGui import QColor, QImage
        from PySide6.QtWidgets import QApplication

        QApplication.clipboard().clear()
        self.dialogo._pegar_foto()
        self.avisos.assert_called_once()  # "no hay ninguna imagen copiada"
        self.assertIsNone(self.dialogo.foto)
        copiada = QImage(300, 200, QImage.Format.Format_RGB32)
        copiada.fill(QColor("blue"))
        QApplication.clipboard().setImage(copiada)
        self.dialogo._pegar_foto()
        self.assertEqual(self.dialogo.foto.width(), 300)
        self.assertFalse(self.dialogo.foto_label.pixmap().isNull())

    def test_recortar_el_auto(self):
        from PySide6.QtCore import QRect

        from roleplay.ui.configurador import RecortarFoto

        recorte = RecortarFoto(self.imagen)  # se muestra a 1100 de ancho
        self.assertFalse(recorte.recorte_btn.isEnabled())
        recorte.lienzo.seleccion = QRect(110, 62, 550, 310)
        recorte.lienzo.seleccion_cambiada.emit()
        recorte.recorte_btn.click()
        self.assertEqual(recorte.resultado().size().width(), 800)  # en pixeles de la foto de verdad
        entera = RecortarFoto(self.imagen)
        entera.accept()
        self.assertEqual(entera.resultado().size(), self.imagen.size())


class TestPedidoYEntrega(ayuda.PruebaConBase):
    def setUp(self):
        super().setUp()
        self.e = economia.acreditar(None, HOY, f.SUELDO)  # ~£2,3 M

    def test_se_paga_al_pedir_y_llega_despues(self):
        config = Configuracion("porsche_911", color="gris", llantas="deportivas")
        pedido = economia.pedir_auto(self.e, config, HOY)
        total = autos.precio(config)
        self.assertEqual(pedido["saldo"], self.e["saldo"] - total)
        self.assertEqual(pedido["pedidos"][0]["entrega"], "2027-01-30")
        self.assertEqual(economia.entregar_pedidos(pedido, date(2027, 1, 29)), (pedido, []))
        llego, entregados = economia.entregar_pedidos(pedido, date(2027, 1, 30))
        self.assertEqual(llego["pedidos"], [])
        self.assertEqual(entregados[0]["articulo"], "auto:porsche_911")
        articulo = economia.articulo_de_posesion(entregados[0])
        self.assertEqual((articulo.nombre, articulo.precio, articulo.ostentoso), ("Porsche 911 Carrera", total, False))
        self.assertEqual(articulo.detalle, "gris brillante, llantas deportivas")
        self.assertEqual(economia.mantenimiento_semanal(llego), autos.mantenimiento(total))
        vendido, recuperado = economia.vender(llego, entregados[0]["id"], date(2027, 2, 1))
        self.assertEqual(recuperado, round(total * economia.VENTA))
        self.assertEqual(vendido["movimientos"][0]["concepto"], "Venta: Porsche 911 Carrera")

    def test_sin_plata_no_se_pide(self):
        with self.assertRaises(economia.SinPlata):
            economia.pedir_auto(self.e, Configuracion("bugatti_tourbillon"), HOY)

    def test_un_superdeportivo_es_ostentoso_y_noticia(self):
        self.e["saldo"] = 1_000_000
        pedido = economia.pedir_auto(self.e, Configuracion("ferrari_296"), HOY)
        _, entregados = economia.entregar_pedidos(pedido, date(2027, 3, 1))
        articulo = economia.articulo_de_posesion(entregados[0])
        efecto = economia.efecto(articulo, PlayerProfile(personalidad="carismatico"), 10_000, 50, f.SUELDO, False)
        self.assertTrue(articulo.ostentoso)
        self.assertTrue(efecto.es_noticia)
        perfil = PlayerProfile(nombre_jugador="Simon Canales")
        perfil.id = database.save_profile(perfil)
        with mock.patch.object(hinchada, "comentar_eventos", return_value={}):
            noticia, actividad = economia.repercusion(perfil, articulo, efecto, "£", "2027-03-01")
        self.assertIn("ferrari 296 gtb", noticia.titular.lower())
        self.assertIn("Simon Canales recibio su nuevo Ferrari 296 GTB (rojo brillante; £245.000)", noticia.cuerpo)
        self.assertIn("a sus seguidores les encanta el show", noticia.cuerpo)
        self.assertEqual(actividad.tipo, "entrega")


class TestConcesionarioEnLaPagina(ayuda.PruebaDeInterfaz):
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
        self.pid = database.save_profile(PlayerProfile(nombre_jugador="Simon Canales", club_actual="Man Utd"))
        from roleplay.ui.vida import PaginaVida

        self.pagina = PaginaVida()
        self.pagina.actualizar()
        ayuda.esperar_tareas()

    def test_estan_todos_los_modelos(self):
        from PySide6.QtWidgets import QPushButton

        self.pagina._elegir_categoria("auto")
        modelos = []
        for i in range(self.pagina.tienda_layout.count()):
            fila = self.pagina.tienda_layout.itemAt(i).layout()
            for j in range(fila.count() if fila else 0):
                widget = fila.itemAt(j).widget()
                if isinstance(widget, QPushButton) and widget.property("modelo"):
                    modelos.append(widget.property("modelo"))
        self.assertEqual(modelos, [m.id for m in autos.MODELOS])

    def test_configurar_pedir_y_recibir(self):
        from PySide6.QtWidgets import QDialog

        from roleplay.ui import vida

        entregas = []
        self.pagina.auto_entregado.connect(entregas.append)
        seguidores = database.get_seguidores(self.pid)
        with mock.patch.object(vida.Configurador, "exec", return_value=QDialog.DialogCode.Accepted), \
                mock.patch.object(vida.Configurador, "configuracion",
                                  return_value=Configuracion("porsche_911", color="verde", patente="SC 9")):
            self.pagina._on_configurar("porsche_911")
        e = database.get_economia(self.pid)
        self.assertEqual([p["modelo"] for p in e["pedidos"]], ["porsche_911"])
        self.assertTrue(self.pagina.pedidos.isVisibleTo(self.pagina))
        self.assertIn("Pediste tu Porsche 911 Carrera", self.pagina.resultado_label.text())
        self.assertIn("Llega el 30/01/2027", self.pagina.resultado_label.text())
        self.assertEqual(database.get_seguidores(self.pid), seguidores)  # todavia no lo luce

        self.pagina.acreditar_con(construir(f.construir_bytes(otros_partidos=DOS_SEMANAS)))  # autoguardado
        ayuda.esperar_tareas()
        e = database.get_economia(self.pid)
        self.assertEqual(e["pedidos"], [])
        self.assertEqual([p["articulo"] for p in e["posesiones"]], ["auto:porsche_911"])
        self.assertEqual(entregas, ["Porsche 911 Carrera"])
        self.assertIn("Te llego tu: Porsche 911 Carrera", self.pagina.resultado_label.text())
        self.assertGreater(database.get_seguidores(self.pid), seguidores)
        self.assertEqual([a.tipo for a in database.load_actividad_instagram(self.pid)], ["entrega"])
        self.assertFalse(self.pagina.pedidos.isVisibleTo(self.pagina))

    def test_la_foto_llega_al_garage(self):
        from PySide6.QtGui import QColor, QImage
        from PySide6.QtWidgets import QLabel

        from roleplay import config

        foto = QImage(1920, 1080, QImage.Format.Format_RGB32)
        foto.fill(QColor("#1F4FA8"))
        self.pagina.pedir(Configuracion("porsche_911", color="azul"), foto)
        archivo = database.get_economia(self.pid)["pedidos"][0]["foto"]
        self.assertEqual(QImage(str(config.CARPETA_GARAGE / archivo)).width(), 960)  # se guarda achicada
        self.assertEqual(len(self.pagina.pedidos.findChildren(QLabel, "fotoAuto")), 1)
        self.pagina.acreditar_con(construir(f.construir_bytes(otros_partidos=DOS_SEMANAS)))
        ayuda.esperar_tareas()
        self.assertEqual(database.get_economia(self.pid)["posesiones"][0]["foto"], archivo)
        fotos = [f for f in self.pagina.posesiones.findChildren(QLabel, "fotoAuto") if not f.isHidden()]
        self.assertEqual([f.size().width() for f in fotos], [132])

    def test_sin_foto_queda_el_dibujo(self):
        from roleplay.ui.configurador import VistaAuto

        self.pagina.pedir(Configuracion("porsche_911"))
        self.assertNotIn("foto", database.get_economia(self.pid)["pedidos"][0])
        self.assertEqual(len(self.pagina.pedidos.findChildren(VistaAuto)), 1)
