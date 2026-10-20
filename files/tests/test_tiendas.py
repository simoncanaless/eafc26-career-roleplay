"""La tienda real (ui/tienda.py): la web oficial adentro de la app, como el
configurador de autos, y la compra en Vida con su web y su foto."""

import tempfile
import unittest
from pathlib import Path
from unittest import mock

import ayuda
import fabrica_partida as f
from roleplay import config, database
from roleplay.models import PlayerProfile
from roleplay.servicios import tiendas


class TestDialogoTiendaReal(ayuda.PruebaDeInterfaz):
    def _dialogo(self, categoria="reloj", saldo=100_000):
        from roleplay.ui.tienda import DialogoTiendaReal

        dialogo = DialogoTiendaReal(categoria, saldo, "£")
        self.addCleanup(dialogo.deleteLater)
        return dialogo

    def test_las_tiendas_de_la_categoria_y_comprar_solo_si_alcanza(self):
        dialogo = self._dialogo()
        self.assertEqual([b.text() for b in dialogo.botones_tienda], [t.nombre.upper() for t in tiendas.TIENDAS["reloj"]]
                         if dialogo.botones_tienda[0].text().isupper() else [t.nombre for t in tiendas.TIENDAS["reloj"]])
        self.assertIsNone(dialogo.navegador)  # sin pantalla: el formulario y "abrir en tu navegador"
        self.assertFalse(dialogo.comprar_btn.isEnabled())
        dialogo.nombre_edit.setText("Rolex Daytona de oro")
        dialogo.precio_spin.setValue(150_000)
        self.assertFalse(dialogo.comprar_btn.isEnabled())  # no alcanza
        self.assertIn("te faltan", dialogo.saldo_label.text())
        nivel = next(b for b in dialogo.findChildren(type(dialogo.comprar_btn)) if b.property("nivel") == 60_000)
        nivel.click()
        self.assertEqual(dialogo.precio_spin.value(), 60_000)
        self.assertTrue(dialogo.comprar_btn.isEnabled())
        articulo = dialogo.articulo()
        self.assertEqual((articulo.id, articulo.nombre, articulo.precio, articulo.tienda),
                         ("libre:reloj", "Rolex Daytona de oro", 60_000, "Rolex"))

    def test_leer_de_la_pagina_pasa_a_la_moneda_del_juego(self):
        dialogo = self._dialogo("moda")
        dialogo.on_metadatos({"ofertas": [{"nombre": "Zapatillas Nike By You", "precio": "200", "moneda": "EUR"}]})
        self.assertEqual(dialogo.nombre_edit.text(), "Zapatillas Nike By You")
        self.assertEqual(dialogo.precio_spin.value(), tiendas.convertir(200, "EUR", "£"))
        dialogo.on_metadatos({})
        self.assertIn("no dice el precio", dialogo.lectura_label.text())


class TestCompraEnVida(ayuda.PruebaDeInterfaz):
    def setUp(self):
        super().setUp()
        from roleplay.partida import lector
        from roleplay.servicios import amor, eventos, hinchada, partida_real

        guardados = Path(tempfile.mkdtemp(prefix="eafc_tienda_partida_"))
        (guardados / "CmPlr1").write_bytes(f.construir_bytes())
        for parche in (mock.patch.object(lector, "CARPETA_GUARDADOS", guardados),
                       mock.patch.object(partida_real, "identificar_jugadores", return_value={}),
                       mock.patch.object(partida_real, "identificar_competiciones", return_value={}),
                       mock.patch.object(hinchada, "comentar_eventos", return_value={}),
                       mock.patch.object(eventos, "PROBABILIDAD_POR_SEMANA", 0),
                       mock.patch.object(amor, "PROBABILIDAD_POR_SEMANA", 0),
                       mock.patch.object(config, "CARPETA_COMPRAS", Path(tempfile.mkdtemp()) / "compras")):
            parche.start()
            self.addCleanup(parche.stop)
        self.pid = database.save_profile(PlayerProfile(nombre_jugador="Simon Canales", club_actual="Man Utd"))
        from roleplay.ui.vida import PaginaVida

        self.pagina = PaginaVida()
        self.pagina.actualizar()
        ayuda.esperar_tareas()

    def test_el_boton_de_las_webs_oficiales_en_relojes_y_ropa(self):
        from PySide6.QtWidgets import QPushButton

        for categoria in ("reloj", "moda"):
            self.pagina._elegir_categoria(categoria)
            botones = [b for b in self.pagina.findChildren(QPushButton) if b.property("tienda_real") == categoria
                       and b.isVisibleTo(self.pagina)]
            self.assertEqual(len(botones), 1, categoria)

    def test_la_compra_guarda_su_web_y_su_foto(self):
        from PySide6.QtGui import QColor, QImage

        from roleplay.servicios import economia

        foto = QImage(400, 200, QImage.Format.Format_RGB32)
        foto.fill(QColor("gold"))
        articulo = economia.articulo_libre("reloj", "Rolex Daytona de oro", 60_000, "Rolex")
        self.pagina.comprar_de_tienda(articulo, "https://www.rolex.com/es/watches/configure", foto)
        ayuda.esperar_tareas()
        posesion = database.get_economia(self.pid)["posesiones"][-1]
        self.assertEqual((posesion["articulo"], posesion["nombre"], posesion["tienda"]),
                         ("libre:reloj", "Rolex Daytona de oro", "Rolex"))
        self.assertEqual(posesion["url"], "https://www.rolex.com/es/watches/configure")
        self.assertTrue((config.CARPETA_COMPRAS / posesion["foto"]).exists())
        self.assertIn("Rolex Daytona de oro", self.pagina.resultado_label.text())


class TestLeerPrecios(unittest.TestCase):
    """Lo que fallaba: runJavaScript devolvia "" (el objeto no se convertia) y un precio
    con 3 decimales se leia por mil. Y sin schema.org, el precio escrito en la pagina."""

    def test_el_script_devuelve_texto_json(self):
        self.assertTrue(tiendas.SCRIPT_METADATOS.startswith("JSON.stringify("))
        self.assertEqual(tiendas.datos_de_script('{"titulo": "X"}'), {"titulo": "X"})
        self.assertIsNone(tiendas.datos_de_script(""))
        self.assertIsNone(tiendas.datos_de_script("no es json"))

    def test_un_precio_numero_con_decimales_no_se_multiplica(self):
        lectura = tiendas.leer_metadatos({"ofertas": [{"nombre": "Solaris 111RS", "precio": 21622823.823,
                                                       "moneda": "USD"}]}, "£")
        self.assertEqual(lectura.precio, tiendas.convertir(21622823.823, "USD", "£"))

    def test_el_precio_escrito_en_la_pagina(self):
        self.assertEqual(tiendas.precio_en_texto("€19,250,000"), (19250000.0, "EUR"))
        self.assertEqual(tiendas.precio_en_texto("12 500 000 EUR"), (12500000.0, "EUR"))
        self.assertEqual(tiendas.precio_en_texto("sin precio"), (None, ""))
        lectura = tiendas.leer_metadatos({"titulo": "Yate | JamesEdition", "precio_texto": "€19,250,000"}, "£")
        self.assertEqual(lectura.precio, tiendas.convertir(19250000, "EUR", "£"))


class TestTiendasQueBloquean(ayuda.PruebaDeInterfaz):
    def test_se_abren_en_el_navegador_de_siempre_y_la_foto_se_pega(self):
        from PySide6.QtGui import QColor, QGuiApplication, QImage

        from roleplay.ui import tienda as modulo

        afuera = [t for t in tiendas.TIENDAS["moda"] if not t.adentro]
        self.assertTrue({"Gucci", "Louis Vuitton"} <= {t.nombre for t in afuera})
        dialogo = modulo.DialogoTiendaReal("moda", 100_000, "£")
        self.addCleanup(dialogo.deleteLater)
        self.assertTrue(dialogo.tienda.adentro)  # arranca en una que se ve adentro
        with mock.patch.object(modulo.QDesktopServices, "openUrl") as abrir:
            dialogo.ir_a(afuera[0])
        abrir.assert_called_once()
        self.assertIn("tu navegador", dialogo.lectura_label.text())
        with mock.patch.object(modulo.QDesktopServices, "openUrl") as abrir:
            dialogo.on_texto_pagina("Access Denied You don't have permission")
        abrir.assert_called_once()
        imagen = QImage(300, 200, QImage.Format.Format_RGB32)
        imagen.fill(QColor("red"))
        QGuiApplication.clipboard().setImage(imagen)
        dialogo.pegar_foto()
        self.assertIsNotNone(dialogo.foto)


if __name__ == "__main__":
    unittest.main()
