"""Perfiles de carrera (roleplay/carreras.py): mas de una carrera, cada una con su carpeta, y cambiar entre ellas."""

import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import ayuda
from roleplay import carreras


class ConBase(unittest.TestCase):
    def setUp(self):
        self.base = Path(tempfile.mkdtemp(prefix="eafc_base_"))
        (self.base / "ajustes.json").write_text(json.dumps({"groq_api_key": "clave", "juego": "x"}), encoding="utf-8")
        parche = mock.patch.dict(os.environ, {"EAFC_ROLEPLAY_BASE": str(self.base)})
        parche.start()
        self.addCleanup(parche.stop)


class TestCarreras(ConBase):
    def test_la_principal_siempre_esta_y_esta_activa(self):
        self.assertEqual([c["id"] for c in carreras.listar()], [carreras.PRINCIPAL])
        self.assertEqual(carreras.activa_id(), carreras.PRINCIPAL)
        self.assertEqual(carreras.entorno_de(carreras.activa()), {})

    def test_crear_una_carrera_con_su_partida(self):
        nueva = carreras.crear("Mi segundo modo carrera", partida="C:/saves/CmPlr7")
        self.assertEqual(nueva["id"], "mi_segundo_modo_carrera")
        carpeta = Path(nueva["carpeta"])
        self.assertEqual(carpeta.parent, self.base / "carreras")
        ajustes_nuevos = json.loads((carpeta / "ajustes.json").read_text(encoding="utf-8"))
        self.assertEqual(ajustes_nuevos, {"groq_api_key": "clave", "partida": "C:/saves/CmPlr7"})  # IA si, juego no
        self.assertEqual(carreras.crear("Mi segundo modo carrera")["id"], "mi_segundo_modo_carrera_2")

    def test_activar_y_el_entorno_al_arrancar(self):
        prueba = carreras.crear("Prueba", carpeta=str(self.base / "prueba"), guardados=str(self.base / "g"),
                                dm_sin_espera=True, id_="prueba")
        carreras.activar("prueba")
        self.assertEqual(carreras.activa_id(), "prueba")
        with mock.patch.dict(os.environ, {}, clear=False):
            for variable in carreras.VARIABLES:
                os.environ.pop(variable, None)
            carreras.preparar_entorno()
            self.assertEqual(os.environ["EAFC_ROLEPLAY_DATOS"], prueba["carpeta"])
            self.assertEqual(os.environ["EAFC_FC26_GUARDADOS"], str(self.base / "g"))
            self.assertEqual(os.environ["EAFC_DM_SIN_ESPERA"], "1")
            self.assertEqual(carreras.actual()["id"], "prueba")
            self.assertNotIn("EAFC_ROLEPLAY_DATOS", carreras.entorno_para_reiniciar())
        with self.assertRaises(ValueError):
            carreras.activar("no_existe")

    def test_si_la_carpeta_viene_en_el_entorno_no_se_toca(self):
        with mock.patch.dict(os.environ, {"EAFC_ROLEPLAY_DATOS": str(self.base / "otra")}):
            self.assertEqual(carreras.preparar_entorno()["id"], "externa")
            self.assertEqual(os.environ["EAFC_ROLEPLAY_DATOS"], str(self.base / "otra"))


class TestTusCarrerasEnAjustes(ayuda.PruebaDeInterfaz):
    def setUp(self):
        super().setUp()
        self.base = Path(tempfile.mkdtemp(prefix="eafc_base_ui_"))
        parche = mock.patch.dict(os.environ, {"EAFC_ROLEPLAY_BASE": str(self.base)})
        parche.start()
        self.addCleanup(parche.stop)

    def test_nueva_carrera_y_cambiar_reinicia(self):
        from PySide6.QtWidgets import QPushButton

        from roleplay.ui import ajustes as modulo

        dialogo = modulo.DialogoAjustes()
        self.addCleanup(dialogo.deleteLater)
        with mock.patch.object(modulo.QInputDialog, "getText", return_value=("Carrera en Italia", True)), \
                mock.patch.object(modulo.QFileDialog, "getOpenFileName", return_value=("C:/saves/CmPlr2", "")):
            dialogo._on_nueva_carrera()
        botones = {b.property("carrera"): b for b in dialogo.findChildren(QPushButton)
                   if b.property("carrera") and b.isVisibleTo(dialogo)}
        self.assertIn("carrera_en_italia", botones)
        with mock.patch.object(modulo, "reiniciar_app") as reiniciar:
            botones["carrera_en_italia"].click()
        reiniciar.assert_called_once()
        self.assertEqual(carreras.activa_id(), "carrera_en_italia")


if __name__ == "__main__":
    unittest.main()
