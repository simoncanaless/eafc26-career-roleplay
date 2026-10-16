"""Nombres de los jugadores: el catalogo de EA (solo local), el diccionario
de ids de nombre para regens y el script que baja el catalogo."""

import json
import os
import sys
import tempfile
from pathlib import Path
from unittest import mock

import ayuda
from roleplay.servicios import identificar

sys.path.insert(0, str(ayuda.RAIZ / "scripts"))
import nombres_faltantes  # noqa: E402

HAALAND, VINI, REGEN, OTRO_REGEN, SOLO_APELLIDO = 239085, 238794, 460001, 460002, 460003
CATALOGO = {
    str(HAALAND): {"pila": "Erling", "apellido": "Haaland", "nacimiento": "2000-07-21"},
    str(VINI): {"pila": "Vinicius Jose", "apellido": "Paixao de Oliveira Junior", "comun": "Vini Jr.",
                "nacimiento": "2000-07-12"},
    "100": {"pila": "Erling", "apellido": "Otro", "nacimiento": "1990-01-01"},
}


class ConCatalogo(ayuda.PruebaConBase):
    def setUp(self):
        super().setUp()
        carpeta = Path(tempfile.mkdtemp(prefix="eafc_catalogo_"))
        self.archivo = carpeta / "catalogo_ea.json"
        self.archivo.write_text(json.dumps({"jugadores": CATALOGO}), encoding="utf-8")
        parche = mock.patch.dict(os.environ, {"EAFC_CATALOGO_EA": str(self.archivo)})
        parche.start()
        self.addCleanup(parche.stop)
        identificar._catalogo.cache_clear()
        self.addCleanup(identificar._catalogo.cache_clear)
        # sin la base a mano (ya trae a Haaland y a Vinicius): se prueba el catalogo solo
        parche = mock.patch.object(identificar, "jugadores_conocidos", return_value={})
        parche.start()
        self.addCleanup(parche.stop)


class TestCatalogo(ConCatalogo):
    def test_nombre_con_el_nacimiento_que_calza(self):
        nombres = identificar.identificar_jugadores([
            {"id": HAALAND, "nacimiento": "2000-07-21"},
            {"id": VINI, "nacimiento": "2000-07-12"},
            {"id": 100, "nacimiento": "1995-05-05"},  # el id es de otra persona
        ])
        self.assertEqual(nombres[HAALAND], ("Erling Haaland", True))
        self.assertEqual(nombres[VINI], ("Vini Jr.", True))  # el nombre comun manda
        self.assertEqual(nombres[100], ("", False))

    def test_sin_catalogo_queda_sin_nombre(self):
        self.archivo.unlink()
        identificar._catalogo.cache_clear()
        self.assertEqual(identificar.identificar_jugadores([{"id": HAALAND}])[HAALAND], ("", False))

    def test_la_base_a_mano_manda_sobre_el_catalogo(self):
        with mock.patch.object(identificar, "jugadores_conocidos",
                               return_value={str(HAALAND): {"nombre": "E. Haaland", "nacimiento": "2000-07-21"}}):
            nombre = identificar.identificar_jugadores([{"id": HAALAND, "nacimiento": "2000-07-21"}])[HAALAND]
        self.assertEqual(nombre, ("E. Haaland", True))


class TestDiccionarioDeIds(ConCatalogo):
    def test_aprende_de_la_partida_y_nombra_a_los_regens(self):
        ids_de_nombre = {HAALAND: (10973, 14348, 0), VINI: (38072, 40602, 38056), 100: (10973, 999, 0),
                         REGEN: (10973, 40602, 0), OTRO_REGEN: (5, 6, 38056), SOLO_APELLIDO: (777, 14348, 0)}
        nacimientos = {HAALAND: "2000-07-21", VINI: "2000-07-12", 100: "1995-05-05"}  # 100 no calza: no ensena
        diccionario = identificar.diccionario_de_nombres(ids_de_nombre, nacimientos)
        self.assertEqual(diccionario[14348], "Haaland")
        self.assertEqual(diccionario[38056], "Vini Jr.")
        self.assertNotIn(999, diccionario)
        fichas = [{"id": j, "ids_nombre": ids_de_nombre[j]} for j in (REGEN, OTRO_REGEN, SOLO_APELLIDO)]
        nombres = identificar.identificar_jugadores(fichas, diccionario)
        self.assertEqual(nombres[REGEN][0], "Erling Paixao de Oliveira Junior")
        self.assertEqual(nombres[OTRO_REGEN][0], "Vini Jr.")
        self.assertEqual(nombres[SOLO_APELLIDO][0], "Haaland")
        self.assertEqual(identificar.identificar_jugadores([{"id": 7, "ids_nombre": (1, 2, 0)}], diccionario)[7],
                         ("", False))

    def test_un_id_con_dos_textos_se_descarta(self):
        catalogo = {**CATALOGO, "200": {"pila": "Erlin", "apellido": "X", "nacimiento": "2001-01-01"}}
        self.archivo.write_text(json.dumps({"jugadores": catalogo}), encoding="utf-8")
        identificar._catalogo.cache_clear()
        diccionario = identificar.diccionario_de_nombres(
            {HAALAND: (10973, 14348, 0), 200: (10973, 1, 0)}, {HAALAND: "2000-07-21", 200: "2001-01-01"})
        self.assertNotIn(10973, diccionario)  # "Erling" o "Erlin": mejor ninguno
        self.assertEqual(diccionario[14348], "Haaland")


class TestBajarCatalogo(ayuda.PruebaConBase):
    def test_baja_todas_las_paginas_y_guarda_solo_lo_necesario(self):
        paginas = {
            0: {"totalItems": 3, "items": [{"id": 1, "firstName": "Kylian", "lastName": "Mbappe",
                                            "commonName": None, "birthdate": "12/20/1998 12:00:00 AM", "stats": {}}]},
            1: {"totalItems": 3, "items": [{"id": 2, "firstName": "Vinicius", "lastName": "Junior",
                                            "commonName": "Vini Jr.", "birthdate": "7/12/2000 12:00:00 AM"},
                                           {"id": 3, "firstName": "A", "lastName": "B", "birthdate": "raro"}]},
        }

        class Respuesta:
            def __init__(self, datos):
                self.datos = datos

            def read(self):
                return json.dumps(self.datos).encode("utf-8")

            def __enter__(self):
                return self

            def __exit__(self, *_):
                return False

        pedidos = []

        def abrir(pedido, timeout=None):
            if "gender" in pedido.full_url:
                return Respuesta({"totalItems": 0, "items": []})
            desde = int(pedido.full_url.split("offset=")[1])
            pedidos.append(desde)
            return Respuesta(paginas.get(desde, {"totalItems": 3, "items": []}))

        archivo = config_tmp = Path(tempfile.mkdtemp()) / "catalogo_ea.json"
        with mock.patch("builtins.print"):
            cantidad = nombres_faltantes.bajar_catalogo(archivo, abrir=abrir, pausa=0, pasadas=1)
        self.assertEqual(cantidad, 3)
        self.assertEqual(pedidos, [0, 1])
        jugadores = json.loads(config_tmp.read_text(encoding="utf-8"))["jugadores"]
        self.assertEqual(jugadores["1"], {"pila": "Kylian", "apellido": "Mbappe", "nacimiento": "1998-12-20"})
        self.assertEqual(jugadores["2"]["comun"], "Vini Jr.")
        self.assertEqual(jugadores["3"]["nacimiento"], "")
        self.assertNotIn("stats", json.dumps(jugadores))


class TestQueNoSeSuba(ayuda.PruebaConBase):
    def test_el_catalogo_esta_en_gitignore(self):
        reglas = (ayuda.RAIZ.parent / ".gitignore").read_text(encoding="utf-8")
        self.assertIn("files/roleplay/datos/catalogo_ea.json", reglas)
