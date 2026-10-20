"""El ecosistema de Simon (famosas, paginas, periodistas, futbolistas y autos
de nicho; datos de prueba propios), la fama del jugador, los seguidores por
tier, los patrocinios, el marketplace, los hiperautos, las parejas del
catalogo con romance secreto, las 8 tematicas de la conferencia y el feed global."""

import json
import os
import random
import tempfile
from datetime import date
from pathlib import Path
from unittest import mock

import ayuda
import fabrica_partida as f
from roleplay import database
from roleplay.models import PlayerProfile
from roleplay.partida.carrera import construir
from roleplay.servicios import (
    amor, autos, cruce, economia, ecosistema, entrevista, feed, hinchada, marketplace, patrocinios,
)
from roleplay.servicios.vision import MatchStats

from datos_ecosistema import AUTOS, CELEBRIDADES, ECOSISTEMA, ConEcosistema


class TestEcosistema(ConEcosistema):
    def test_lee_los_datos_y_sin_archivos_queda_vacio(self):
        self.assertEqual(len(ecosistema.celebridades()), 3)
        self.assertEqual(len(ecosistema.periodistas()), 9)
        self.assertEqual(len(ecosistema.autos_nicho()), 15)
        with mock.patch.dict(os.environ, {"EAFC_ECOSISTEMA": tempfile.mkdtemp()}):
            self.assertEqual(ecosistema.celebridades(), [])
            self.assertEqual(ecosistema.autos_nicho(), [])

    def test_la_fama_premia_al_gigante_y_los_goles(self):
        chico = ecosistema.fama_jugador(50, 3)
        gigante = ecosistema.fama_jugador(50, 1)
        self.assertGreater(gigante, chico + 15)
        self.assertGreater(ecosistema.fama_jugador(50, 1, goles_temporada=30, premios=2), gigante)
        self.assertEqual(ecosistema.fama_jugador(100, 1, 200, 10), 100)

    def test_tier_del_club_con_la_partida(self):
        carrera = construir(f.construir_bytes())
        club = ecosistema.club_del_usuario(carrera)
        self.assertIn(ecosistema.tier_club(carrera, club), (1, 2, 3))
        self.assertEqual(ecosistema.tier_club(None, None), 2)


class TestPantallas(ayuda.PruebaDeInterfaz):
    """Vida (marketplace, patrocinios, DM) e Instagram (feed global) con la partida de prueba."""

    def setUp(self):
        super().setUp()
        from roleplay.partida import lector
        from roleplay.servicios import eventos, partida_real

        carpeta = Path(tempfile.mkdtemp(prefix="eafc_eco_ui_"))
        (carpeta / "famosas_ig.json").write_text(json.dumps({"celebridades": CELEBRIDADES}), encoding="utf-8")
        (carpeta / "ecosistema_ig.json").write_text(json.dumps(ECOSISTEMA), encoding="utf-8")
        (carpeta / "autos_marketplace.json").write_text(json.dumps({"autos_nicho": AUTOS}), encoding="utf-8")
        guardados = Path(tempfile.mkdtemp(prefix="eafc_eco_partida_"))
        (guardados / "CmPlr1").write_bytes(f.construir_bytes())
        for parche in (mock.patch.dict(os.environ, {"EAFC_ECOSISTEMA": str(carpeta)}),
                       mock.patch.object(lector, "CARPETA_GUARDADOS", guardados),
                       mock.patch.object(partida_real, "identificar_jugadores", return_value={}),
                       mock.patch.object(partida_real, "identificar_competiciones", return_value={}),
                       mock.patch.object(hinchada, "comentar_eventos", return_value={}),
                       mock.patch.object(eventos, "PROBABILIDAD_POR_SEMANA", 0),
                       mock.patch.object(amor, "PROBABILIDAD_POR_SEMANA", 0),
                       mock.patch.object(patrocinios, "PROBABILIDAD_OFERTA", 1.0)):
            parche.start()
            self.addCleanup(parche.stop)
        ecosistema._leer.cache_clear()
        self.addCleanup(ecosistema._leer.cache_clear)
        self.pid = database.save_profile(PlayerProfile(nombre_jugador="Simon Canales", club_actual="Man Utd"))
        database.sumar_seguidores(self.pid, 50_000)  # para que alguna marca lo quiera

    def _vida(self):
        from roleplay.ui.vida import PaginaVida

        pagina = PaginaVida()
        pagina.actualizar()
        ayuda.esperar_tareas()
        return pagina

    def _botones(self, pagina, propiedad):
        from PySide6.QtWidgets import QPushButton

        return [b for b in pagina.findChildren(QPushButton) if b.property(propiedad) is not None and b.isVisibleTo(pagina)]

    def test_marketplace_y_patrocinio(self):
        pagina = self._vida()
        pagina._elegir_categoria("usados")
        comprar = [b for b in self._botones(pagina, "nicho") if b.isEnabled()]
        self.assertTrue(comprar)
        comprar[0].click()
        ayuda.esperar_tareas()
        posesiones = database.get_economia(self.pid)["posesiones"]
        self.assertTrue(posesiones[0]["articulo"].startswith(marketplace.PREFIJO))

        firmar = next(b for b in self._botones(pagina, "patrocinio") if b.property("patrocinio") == "firmar")
        firmar.click()
        ayuda.esperar_tareas()
        contratos = database.get_economia(self.pid)["patrocinios"]["contratos"]
        self.assertEqual(len(contratos), 1)
        self.assertTrue(any(contratos[0]["nombre"] in n.titular for n in database.load_noticias_prensa(self.pid)))

    def test_dm_a_una_famosa_de_su_nivel(self):
        pagina = self._vida()
        self.assertTrue(pagina.dm.isVisibleTo(pagina))
        pagina.dm_buscar_edit.setText("@influ")
        pagina.buscar_famosas()
        self.assertEqual(len(self._botones(pagina, "dm")), 1)
        pagina.mandar_dm(0)
        estado = database.get_estado_amor(self.pid)
        self.assertEqual((estado["estado"], estado["decision"]["tipo"]), ("conociendo", "como_seguir"))
        self.assertFalse(pagina.dm.isVisibleTo(pagina))  # ya no esta soltero: a decidir
        self.assertEqual(database.load_noticias_prensa(self.pid), [])  # el DM es privado

    def test_feed_global_en_instagram(self):
        database.set_estado_hinchada(self.pid, {"feed": [
            {"pagina": "433", "usuario_ig": "@433", "tipo": "viral", "texto": "Canales <otra vez>", "fecha": "2027-01-16",
             "likes": 250_000}]})
        from roleplay.ui.instagram import InstagramWindow

        pagina = InstagramWindow()
        ayuda.esperar_tareas()
        self.assertTrue(pagina.global_tarjeta.isVisibleTo(pagina))
        textos = " ".join(pagina.global_layout.itemAt(i).widget().text() for i in range(pagina.global_layout.count()))
        self.assertIn("@433", textos)
        self.assertIn("&lt;otra vez&gt;", textos)  # escapado
        # (al abrir, la revision de la hinchada ya publico sobre el partido de la partida de prueba)
        self.assertGreaterEqual(len(database.get_estado_hinchada(self.pid)["feed"]), 1)

    def test_panel_vip_con_chance_y_oficializar_el_secreto(self):
        pagina = self._vida()
        self.assertTrue(pagina.vip.isVisibleTo(pagina))  # soltero: el panel aparte
        pagina.dm_buscar_edit.setText("@estrella")
        pagina.buscar_famosas()
        texto = pagina.dm_resultados.itemAt(0).layout().itemAt(0).widget().text()
        self.assertIn("% de chance", texto)
        self.assertIn("% de que se filtre", texto)  # una megaestrella: si te clava el visto, se sabe

        database.set_estado_amor(self.pid, {
            "estado": "secreto", "hasta": "2027-01-16", "decision": None, "historial": [],
            "pareja": {"nombre": "Actriz Conocida", "real": False, "oficio": "actriz", "usuario_ig": "@actriz",
                       "desde": "2027-01-10", "relacion": 60}})
        pagina._mostrar()
        self.assertFalse(pagina.vip.isVisibleTo(pagina))
        self.assertTrue(pagina.oficializar_btn.isVisibleTo(pagina))
        pagina.oficializar_btn.click()
        ayuda.esperar_tareas()
        self.assertEqual(database.get_estado_amor(self.pid)["estado"], "pareja")
        self.assertFalse(pagina.oficializar_btn.isVisibleTo(pagina))
        self.assertTrue(any("Actriz Conocida" in n.cuerpo for n in database.load_noticias_prensa(self.pid)))
