"""El configurador oficial nativo (servicios/configurador.py): opciones, precio, garage, reventa, renders y la
pantalla. Con un catalogo chico de mentira y sin salir a internet."""

import json
import os
import tempfile
from datetime import date
from pathlib import Path
from unittest import mock

import ayuda
from roleplay.servicios import autos, configurador, economia
from roleplay.servicios.autos import Configuracion


def op(id_, nombre, seccion, categoria, precio=0, hex_="", seleccionada=False, grupo="", estandar=False, miniatura=""):
    return {"id": id_, "nombre": nombre, "seccion": seccion, "categoria": categoria, "grupo": grupo, "grupo_id": "",
            "hex": hex_, "precio": precio, "estandar": estandar, "seleccionada": seleccionada, "miniatura": miniatura,
            "descripcion": "Forjadas.<br />Con <b>tuerca</b> central &amp; tapas GT3."}


COLOR, LLANTAS, PAQUETES = "section-exterior-color", "section-wheels", "section-individualization-packages"
EXTERIOR = "section-individualization-exterior"
GT3 = {
    "codigo": "992812", "modelo": "911 GT3", "anio": 2027, "moneda": "GBP", "base": 159700, "marca": "Porsche",
    "pais": "GB", "modelo_app": "porsche_911_gt3", "render": ["0Q", "R1", "XX", "LED"],
    "camaras": {"exterior-front-south_west": "ext-low-front-left", "exterior-side-west-wheel": "ext-low-front-left-wheel",
                "interior-dashboard": "int-front-dashboard"},
    "vistas_seccion": {COLOR: ["exterior-front-south_west"], LLANTAS: ["exterior-side-west-wheel"]},
    "opciones": [
        op("0Q", "White", COLOR, "Exterior colours", 0, "#F5F6F7", True),
        op("S9", "Shark Blue", COLOR, "Exterior colours", 2905, "#1B6FB5"),
        op("PT", "Paint to Sample Gulf Blue", COLOR, "Paint to Sample", 11000, "#6FA8DC"),
        op("R1", "20/21-inch GT3 wheels", LLANTAS, "Wheels", 0, seleccionada=True, estandar=True,
           miniatura="/assets/2027/992812/studio_R1.jpg?h=1"),
        op("R2", "Forged wheels in Satin Platinum", LLANTAS, "Painted wheels", 1500, miniatura="/assets/studio_R2.jpg"),
        op("WI", "Winter wheels", LLANTAS, "Winter wheel-and-tyre sets", 3000),
        op("WP", "Weissach Package", PAQUETES, "Equipment packages", 18000),
        op("LED", "Matrix LED headlights", EXTERIOR, "Lights & vision", 0, seleccionada=True, estandar=True),
        op("DEC", "Side decals", EXTERIOR, "Lettering and decals", 800),
        op("XX", "Something not shown", "section-vehicle-accessories", "Covers", 500, seleccionada=True),
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

    def test_pestanas_en_el_orden_de_la_pagina_y_sin_lo_que_no_se_ve(self):
        secciones = configurador.opciones_por_seccion(GT3)
        self.assertEqual(list(secciones), [COLOR, LLANTAS, PAQUETES, EXTERIOR])
        self.assertNotIn("Winter wheel-and-tyre sets", secciones[LLANTAS])  # neumaticos de invierno: no se ven
        eleccion = configurador.de_fabrica(GT3)
        self.assertEqual(sorted(eleccion.ids()), ["0Q", "LED", "R1"])
        self.assertEqual(configurador.precio_total(GT3, eleccion), 159700)

    def test_una_pintura_una_llanta_con_su_pintura_y_el_resto_son_casillas(self):
        eleccion = configurador.de_fabrica(GT3)
        self.assertTrue(configurador.elegir(GT3, eleccion, "PT"))  # otra categoria, la misma seccion: reemplaza
        self.assertTrue(configurador.elegir(GT3, eleccion, "R2"))  # la pintura de la llanta se suma al modelo
        self.assertTrue(configurador.elegir(GT3, eleccion, "WP"))
        self.assertTrue(configurador.elegir(GT3, eleccion, "DEC"))
        self.assertEqual(sorted(eleccion.ids()), ["DEC", "LED", "PT", "R1", "R2", "WP"])
        self.assertEqual(configurador.precio_total(GT3, eleccion), 159700 + 11000 + 1500 + 18000 + 800)
        self.assertTrue(configurador.elegir(GT3, eleccion, "WP"))  # la casilla se apaga
        self.assertFalse(configurador.elegir(GT3, eleccion, "LED"))  # lo de serie no se saca
        self.assertFalse(configurador.elegir(GT3, eleccion, "PT"))  # la pintura ya elegida no cambia nada
        self.assertEqual(sorted(eleccion.ids()), ["DEC", "LED", "PT", "R1", "R2"])

    def test_el_render_lleva_lo_elegido_y_lo_de_fabrica_que_no_se_maneja(self):
        eleccion = configurador.de_fabrica(GT3)
        configurador.elegir(GT3, eleccion, "PT")
        configurador.elegir(GT3, eleccion, "R2")
        self.assertEqual(configurador._ids_de_render(GT3, eleccion), ["LED", "PT", "R1", "R2", "XX"])

    def test_la_descripcion_en_texto_y_las_vistas(self):
        self.assertEqual(configurador.descripcion(GT3["opciones"][0]), "Forjadas.\nCon tuerca central & tapas GT3.")
        self.assertEqual(configurador.camara_de_seccion(GT3, LLANTAS), "ext-low-front-left-wheel")
        self.assertIsNone(configurador.camara_de_seccion(GT3, PAQUETES))
        self.assertEqual([c for c, _ in configurador.vistas_extra(GT3)], ["ext-low-front-left-wheel", "int-front-dashboard"])


class TestGarageYReventa(ConCatalogo):
    def ficha(self, *ids):
        eleccion = configurador.de_fabrica(GT3)
        for i in ids:
            configurador.elegir(GT3, eleccion, i)
        return configurador.ficha(GT3, eleccion)

    def test_el_nombre_para_la_prensa_y_la_descripcion(self):
        ficha = self.ficha("S9", "WP")
        self.assertEqual(configurador.nombre_de_configuracion("Porsche 911 GT3", ficha),
                         "Porsche 911 GT3 en Shark Blue con Weissach Package")
        texto = autos.describir(Configuracion(modelo="porsche_911_gt3", oficial=ficha))
        self.assertIn("en Shark Blue", texto)
        self.assertIn("Weissach Package", texto)

    def test_el_pedido_cobra_el_precio_oficial_y_el_garage_guarda_la_ficha(self):
        ficha = self.ficha("WP")
        config = Configuracion(modelo="porsche_911_gt3", oficial=ficha)
        self.assertEqual(autos.precio(config), round((159700 + 18000) / autos.REDONDEO) * autos.REDONDEO)
        e = economia.pedir_auto({"saldo": 1_000_000}, config, date(2026, 8, 1))
        self.assertEqual(e["saldo"], 1_000_000 - autos.precio(config))
        e, llegaron = economia.entregar_pedidos(e, date(2027, 1, 1))
        guardada = Configuracion.desde_dict(llegaron[0]["config"])
        self.assertIn("Weissach Package", [o["nombre"] for o in guardada.oficial["opciones"]])
        self.assertEqual(guardada.oficial["total"], 159700 + 18000)

    def test_la_reventa_sube_con_lo_de_prestigio(self):
        comun, prestigio = self.ficha("S9"), self.ficha("PT", "WP")
        self.assertEqual(configurador.bonus_de_reventa(comun), 0)
        self.assertEqual(configurador.bonus_de_reventa(prestigio), round((11000 + 18000) * configurador.REVENTA_PRESTIGIO))
        posesion = {"articulo": "auto:porsche_911_gt3", "precio": 200000, "config": {"oficial": prestigio}}
        self.assertEqual(economia.valor_de_venta(posesion), round(200000 * economia.VENTA) + configurador.bonus_de_reventa(prestigio))
        self.assertEqual(economia.valor_de_venta({"articulo": "auto:porsche_911_gt3", "precio": 200000, "config": {}}),
                         round(200000 * economia.VENTA))


class Respuesta:
    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False

    def read(self):
        return b"\xff\xd8 jpeg falso"


class TestImagenes(ConCatalogo):
    def test_cada_vista_se_pide_una_vez(self):
        with mock.patch.object(configurador.urllib.request, "urlopen", return_value=Respuesta()) as urlopen:
            ruta = configurador.render(GT3, configurador.de_fabrica(GT3))
            self.assertEqual(configurador.render(GT3, configurador.de_fabrica(GT3)), ruta)
            otra = configurador.render(GT3, configurador.de_fabrica(GT3), "ext-low-rear", "Oasis", noche=True)
        self.assertNotEqual(ruta, otra)
        self.assertEqual(urlopen.call_count, 2)
        self.assertTrue(ruta.is_relative_to(self.renders))
        self.assertIn("prs.porsche.com/iod/image/GB/992812/1/", urlopen.call_args_list[0][0][0].full_url)

    def test_las_fotos_de_las_opciones(self):
        with mock.patch.object(configurador.urllib.request, "urlopen", return_value=Respuesta()) as urlopen:
            rutas = configurador.miniaturas(GT3, ["R1", "R2", "WP"])  # WP no tiene foto
            configurador.miniaturas(GT3, ["R1"])
        self.assertEqual(sorted(rutas), ["R1", "R2"])
        self.assertEqual(urlopen.call_count, 2)
        self.assertEqual(urlopen.call_args_list[0][0][0].full_url,
                         "https://configurator.porsche.com/assets/2027/992812/studio_R1.jpg?h=1")

    def test_sin_internet_devuelve_none(self):
        with mock.patch.object(configurador.urllib.request, "urlopen", side_effect=OSError("sin red")):
            self.assertIsNone(configurador.render(GT3, configurador.de_fabrica(GT3)))
            self.assertEqual(configurador.miniaturas(GT3, ["R1"]), {})


class TestPantalla(ayuda.PruebaDeInterfaz, ConCatalogo):
    def abrir(self, saldo=500_000):
        from roleplay.ui.configurador_oficial import DialogoConfiguradorOficial

        dialogo = DialogoConfiguradorOficial(autos.POR_ID["porsche_911_gt3"], GT3, saldo, "GBP")
        self.addCleanup(dialogo.deleteLater)
        return dialogo

    def test_elegir_cambia_el_precio_la_descripcion_y_entrega_la_configuracion(self):
        with mock.patch.object(configurador, "render", return_value=None), \
                mock.patch.object(configurador, "miniaturas", return_value={}):
            dialogo = self.abrir()
            dialogo._elegir("WP")
            pobre = self.abrir(saldo=1000)
            ayuda.esperar_tareas()
        self.assertIn("Weissach Package", dialogo.detalle.text())
        self.assertIn("tuerca central", dialogo.detalle.text())
        self.assertIn(str(18), dialogo.precio_label.text().replace(".", ""))
        self.assertTrue(dialogo.encargar_btn.isEnabled())
        self.assertEqual(dialogo.configuracion().oficial["total"], 159700 + 18000)
        self.assertFalse(pobre.encargar_btn.isEnabled())

    def test_girar_y_las_vistas_de_cada_seccion(self):
        pedidas = []

        def render(modelo, eleccion, camara="", entorno="", noche=False):
            pedidas.append((camara, entorno, noche))
            return None

        with mock.patch.object(configurador, "render", render), \
                mock.patch.object(configurador, "miniaturas", return_value={}):
            dialogo = self.abrir()
            ayuda.esperar_tareas()
            self.assertEqual(pedidas[-1][0], "ext-low-front-left")  # la pintura: adelante a la izquierda
            dialogo._girar(1)
            dialogo.escenario.girar.emit(1)  # arrastrar
            ayuda.esperar_tareas()
            self.assertEqual(pedidas[-1][0], "ext-low-rear-left")
            dialogo._girar(-4)  # pasa por el frente y vuelve a la ultima: adelante a la derecha (espejo)
            self.assertEqual(dialogo._camara(), ("ext-low-front-left", True))
            dialogo.pestanas.setCurrentIndex(1)  # llantas -> la vista de la llanta, como la pagina
            ayuda.esperar_tareas()
            self.assertEqual(pedidas[-1][0], "ext-low-front-left-wheel")
            dialogo._cambiar_entorno("Oasis")
            dialogo._cambiar_noche()
            ayuda.esperar_tareas()
        self.assertEqual(pedidas[-1], ("ext-low-front-left-wheel", "Oasis", True))
        self.assertTrue(dialogo._botones_vista["ext-low-front-left-wheel"].isChecked())
