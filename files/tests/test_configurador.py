"""El configurador oficial nativo (servicios/configurador.py): opciones, precio, garage, reventa y renders.
Con un catalogo chico de mentira y sin salir a internet."""

import json
import os
import tempfile
from datetime import date
from pathlib import Path
from unittest import mock

import ayuda
from roleplay.servicios import autos, configurador, economia
from roleplay.servicios.autos import Configuracion


def op(id_, nombre, seccion, categoria, precio=0, hex_="", seleccionada=False, grupo=""):
    return {"id": id_, "nombre": nombre, "seccion": seccion, "categoria": categoria, "grupo": grupo, "hex": hex_,
            "precio": precio, "estandar": False, "seleccionada": seleccionada}


GT3 = {
    "codigo": "992812", "modelo": "911 GT3", "anio": 2027, "moneda": "GBP", "base": 159700, "marca": "Porsche",
    "pais": "GB", "modelo_app": "porsche_911_gt3", "render": ["0Q", "R1", "XX"],
    "opciones": [
        op("0Q", "White", "section-exterior-color", "Exterior colours", 0, "#F5F6F7", True),
        op("S9", "Shark Blue", "section-exterior-color", "Exterior colours", 2905, "#1B6FB5"),
        op("PT", "Paint to Sample Gulf Blue", "section-exterior-color", "Paint to Sample", 11000, "#6FA8DC"),
        op("R1", "20/21-inch GT3 wheels", "section-wheels", "Wheels", 0, seleccionada=True),
        op("R2", "Forged wheels in Satin Platinum", "section-wheels", "Painted wheels", 1500),
        op("WP", "Weissach Package", "section-individualization-packages", "Equipment packages", 18000),
        op("XX", "Something not shown", "section-individualization-technology", "Infotainment", 500, seleccionada=True),
    ],
}


class ConCatalogo(ayuda.PruebaConBase):
    def setUp(self):
        super().setUp()
        carpeta = tempfile.mkdtemp()
        archivo = Path(carpeta) / "configuradores_oficiales.json"
        archivo.write_text(json.dumps({"modelos": {"992812": GT3}}), encoding="utf-8")
        for parche in (mock.patch.dict(os.environ, {"EAFC_CONFIGURADORES": str(archivo)}),
                       mock.patch.object(configurador, "CARPETA_RENDERS", Path(carpeta) / "renders")):
            parche.start()
            self.addCleanup(parche.stop)
        self.renders = Path(carpeta) / "renders"


class TestOpciones(ConCatalogo):
    def test_sin_el_archivo_no_hay_catalogo(self):
        with mock.patch.dict(os.environ, {"EAFC_CONFIGURADORES": str(Path(tempfile.gettempdir()) / "no_existe.json")}):
            self.assertEqual(configurador.catalogo(), {})
            self.assertIsNone(configurador.de_modelo("https://configurator.porsche.com/en-WW/mode/model/992812"))

    def test_se_encuentra_por_la_url_del_concesionario(self):
        self.assertEqual(configurador.de_modelo("https://configurator.porsche.com/es-CL/mode/model/992812")["base"], 159700)
        self.assertIsNone(configurador.de_modelo("https://configurator.porsche.com/en-WW/"))

    def test_solo_las_secciones_que_se_eligen_y_de_fabrica_lo_seleccionado(self):
        categorias = configurador.opciones_por_categoria(GT3)
        self.assertNotIn(("section-individualization-technology", "Infotainment"), categorias)
        eleccion = configurador.de_fabrica(GT3)
        self.assertEqual(eleccion.opciones["section-exterior-color|Exterior colours"], "0Q")
        self.assertEqual(configurador.precio_total(GT3, eleccion), 159700)

    def test_precio_base_mas_opcionales(self):
        eleccion = configurador.de_fabrica(GT3)
        configurador.elegir(eleccion, "section-exterior-color|Exterior colours", "S9")
        configurador.elegir(eleccion, "section-individualization-packages|Equipment packages", "WP")
        self.assertEqual(configurador.opcionales(GT3, eleccion), 2905 + 18000)
        self.assertEqual(configurador.precio_total(GT3, eleccion), 159700 + 2905 + 18000)
        configurador.elegir(eleccion, "section-individualization-packages|Equipment packages", "")
        self.assertEqual(configurador.precio_total(GT3, eleccion), 159700 + 2905)

    def test_una_sola_pintura_y_unas_solas_llantas(self):
        eleccion = configurador.de_fabrica(GT3)
        configurador.elegir(eleccion, "section-exterior-color|Paint to Sample", "PT")
        configurador.elegir(eleccion, "section-wheels|Painted wheels", "R2")
        self.assertEqual(sorted(eleccion.ids()), ["PT", "R2"])
        # en el render, la pintura y las llantas de fabrica se cambian por las elegidas; lo demas queda
        self.assertEqual(configurador._ids_de_render(GT3, eleccion), ["PT", "R2", "XX"])


class TestGarageYReventa(ConCatalogo):
    def ficha(self, *elegidas):
        eleccion = configurador.de_fabrica(GT3)
        for clave, id_ in elegidas:
            configurador.elegir(eleccion, clave, id_)
        return configurador.ficha(GT3, eleccion)

    def test_el_nombre_para_la_prensa_y_la_descripcion(self):
        ficha = self.ficha(("section-exterior-color|Exterior colours", "S9"),
                           ("section-individualization-packages|Equipment packages", "WP"))
        self.assertEqual(configurador.nombre_de_configuracion("Porsche 911 GT3", ficha),
                         "Porsche 911 GT3 en Shark Blue con Weissach Package")
        texto = autos.describir(Configuracion(modelo="porsche_911_gt3", oficial=ficha))
        self.assertIn("en Shark Blue", texto)
        self.assertIn("Weissach Package", texto)

    def test_el_pedido_cobra_el_precio_oficial_y_el_garage_guarda_la_ficha(self):
        ficha = self.ficha(("section-individualization-packages|Equipment packages", "WP"))
        config = Configuracion(modelo="porsche_911_gt3", oficial=ficha)
        self.assertEqual(autos.precio(config), round((159700 + 18000) / autos.REDONDEO) * autos.REDONDEO)
        e = economia.pedir_auto({"saldo": 1_000_000}, config, date(2026, 8, 1))
        self.assertEqual(e["saldo"], 1_000_000 - autos.precio(config))
        e, llegaron = economia.entregar_pedidos(e, date(2027, 1, 1))
        guardada = Configuracion.desde_dict(llegaron[0]["config"])
        self.assertEqual(guardada.oficial["opciones"][-1]["nombre"], "Weissach Package")
        self.assertEqual(guardada.oficial["total"], 159700 + 18000)

    def test_la_reventa_sube_con_lo_de_prestigio(self):
        comun = self.ficha(("section-exterior-color|Exterior colours", "S9"))
        prestigio = self.ficha(("section-exterior-color|Paint to Sample", "PT"),
                               ("section-individualization-packages|Equipment packages", "WP"))
        self.assertEqual(configurador.bonus_de_reventa(comun), 0)
        self.assertEqual(configurador.bonus_de_reventa(prestigio), round((11000 + 18000) * configurador.REVENTA_PRESTIGIO))
        posesion = {"articulo": "auto:porsche_911_gt3", "precio": 200000, "config": {"oficial": prestigio}}
        self.assertEqual(economia.valor_de_venta(posesion), round(200000 * economia.VENTA) + configurador.bonus_de_reventa(prestigio))
        self.assertEqual(economia.valor_de_venta({"articulo": "auto:porsche_911_gt3", "precio": 200000, "config": {}}),
                         round(200000 * economia.VENTA))


class TestRender(ConCatalogo):
    def test_se_pide_una_vez_por_combinacion(self):
        class Respuesta:
            def __enter__(self):
                return self

            def __exit__(self, *_):
                return False

            def read(self):
                return b"\x89PNG falso"

        eleccion = configurador.de_fabrica(GT3)
        with mock.patch.object(configurador.urllib.request, "urlopen", return_value=Respuesta()) as urlopen:
            ruta = configurador.render(GT3, eleccion)
            self.assertEqual(configurador.render(GT3, configurador.de_fabrica(GT3)), ruta)
        self.assertEqual(urlopen.call_count, 1)
        self.assertTrue(ruta.is_relative_to(self.renders))
        self.assertIn("prs.porsche.com/iod/image/GB/992812/1/", urlopen.call_args[0][0].full_url)

    def test_sin_internet_devuelve_none(self):
        with mock.patch.object(configurador.urllib.request, "urlopen", side_effect=OSError("sin red")):
            self.assertIsNone(configurador.render(GT3, configurador.de_fabrica(GT3)))


class TestPantalla(ayuda.PruebaDeInterfaz, ConCatalogo):
    def test_elegir_cambia_el_precio_y_entrega_la_configuracion(self):
        from roleplay.ui.configurador_oficial import DialogoConfiguradorOficial

        with mock.patch.object(configurador, "render", return_value=None):
            dialogo = DialogoConfiguradorOficial(autos.POR_ID["porsche_911_gt3"], GT3, 500_000, "GBP")
            dialogo._elegir("section-individualization-packages|Equipment packages", "WP")
            pobre = DialogoConfiguradorOficial(autos.POR_ID["porsche_911_gt3"], GT3, 1000, "GBP")
            ayuda.esperar_tareas()
        self.assertIn("Weissach Package", dialogo.precio_label.text())
        self.assertTrue(dialogo.encargar_btn.isEnabled())
        self.assertEqual(dialogo.configuracion().oficial["total"], 159700 + 18000)
        self.assertFalse(pobre.encargar_btn.isEnabled())
        dialogo.deleteLater()
        pobre.deleteLater()
        ayuda.esperar_tareas()
