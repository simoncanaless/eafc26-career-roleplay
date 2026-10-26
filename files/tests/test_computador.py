"""El computador estilo GTA (ui/computador.py): escritorio, navegador con direcciones y los sitios, que compran
y venden por la PaginaVida (la misma plata, prensa e hinchas)."""

import tempfile
from pathlib import Path
from unittest import mock

import ayuda
import fabrica_partida as f
from roleplay import database
from roleplay.models import PlayerProfile
from roleplay.partida import lector
from roleplay.servicios import amor, eventos, hinchada, partida_real


class TestDirecciones(ayuda.PruebaConBase):
    def test_se_encuentra_por_dominio_nombre_o_id(self):
        from roleplay.ui.computador import buscar_sitio

        self.assertEqual(buscar_sitio("https://www.elitemotors.net/").id, "elite")
        self.assertEqual(buscar_sitio("elitemotors.net").id, "elite")
        self.assertEqual(buscar_sitio("  Banco Crack ").id, "banco")
        self.assertIsNone(buscar_sitio("www.legendarymotorsport.net"))

    def test_los_sitios_son_inventados_y_cubren_las_categorias_de_la_tienda(self):
        from roleplay.servicios import economia
        from roleplay.ui.computador import SITIOS

        categorias = {c for s in SITIOS for c in s.categorias}
        self.assertTrue(set(economia.CATEGORIAS) - {"auto", "usados"} <= categorias)
        self.assertEqual(len({s.dominio for s in SITIOS}), len(SITIOS))


class TestComputador(ayuda.PruebaDeInterfaz):
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
        self.addCleanup(mock.patch.stopall)
        self.pid = database.save_profile(PlayerProfile(nombre_jugador="Simon Canales", club_actual="Man Utd",
                                                       personalidad="humilde"))
        from roleplay.ui.computador import PaginaComputador
        from roleplay.ui.vida import PaginaVida

        self.vida = PaginaVida()
        self.pc = PaginaComputador(self.vida)
        self.pc.actualizar()
        ayuda.esperar_tareas()

    def botones(self, propiedad: str) -> dict:
        from PySide6.QtWidgets import QPushButton

        return {b.property(propiedad): b for b in self.pc.cuerpo.findChildren(QPushButton)
                if b.property(propiedad) and b.isVisibleTo(self.pc.cuerpo)}  # (los del sitio anterior estan escondidos)

    def test_el_escritorio_abre_los_sitios_y_la_barra_tiene_saldo_y_fecha(self):
        from PySide6.QtWidgets import QToolButton

        self.assertEqual(self.pc.stack.currentIndex(), 0)
        self.assertIn("16/01/2027", self.pc.reloj.text())
        iconos = {b.property("sitio"): b for b in self.pc.escritorio.findChildren(QToolButton)}
        iconos["inicio"].click()
        self.assertEqual(self.pc.stack.currentIndex(), 1)
        self.assertEqual(self.pc.direccion.text(), "https://www.futnet.com")
        self.botones("sitio")["horizonte"].click()
        self.assertEqual(self.pc.direccion.text(), "https://www.horizonteprop.com")
        self.pc.atras()
        self.assertEqual(self.pc.sitio.id, "inicio")
        self.pc.direccion.setText("www.bancocrack.com")
        self.pc.ir_a_direccion()
        self.assertEqual(self.pc.sitio.id, "banco")
        self.pc.direccion.setText("www.noexiste.com")
        self.pc.ir_a_direccion()
        self.assertIn("No se encontro", self.pc.aviso.text())
        self.pc.cerrar()
        self.assertEqual(self.pc.stack.currentIndex(), 0)

    def test_comprar_en_un_sitio_es_comprar_en_vida(self):
        saldo = database.get_economia(self.pid)["saldo"]
        self.pc.abrir("pasarela")
        self.botones("articulo")["coleccion_moda"].click()
        ayuda.esperar_tareas()
        self.assertEqual(database.get_economia(self.pid)["saldo"], saldo - 400_000)
        self.assertIn("Compraste: Coleccion de alta costura", self.pc.aviso.text())
        self.assertEqual(self.botones("articulo")["coleccion_moda"].text(), "YA LO TENES")  # el sitio se rearmo
        self.assertIn("coleccion de alta costura", database.load_noticias_prensa(self.pid)[0].titular.lower())
        self.pc.abrir("banco")
        vender = self.botones("posesion")
        self.assertEqual(len(vender), 1)
        next(iter(vender.values())).click()
        self.assertEqual(database.get_economia(self.pid).get("posesiones"), [])

    def test_sin_plata_no_se_puede_y_cada_sitio_se_arma(self):
        from roleplay.ui.computador import SITIOS

        self.pc.abrir("cielo")
        self.assertFalse(self.botones("articulo")["jet"].isEnabled())
        for sitio in SITIOS:
            self.pc.abrir(sitio.id)
            self.assertIn(sitio.dominio, self.pc.direccion.text())
        self.pc.abrir("elite")
        self.assertIn("porsche_911_gt3", self.botones("modelo"))
        self.pc._filtrar_marca("Ferrari")
        self.assertTrue(all("ferrari" in m for m in self.botones("modelo")))
