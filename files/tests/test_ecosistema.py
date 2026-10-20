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

CELEBRIDADES = [
    {"nombre": "Estrella Mundial", "usuario_ig": "@estrella", "oficio": "cantante global", "categoria": "cantante",
     "anio_nacimiento": 1995, "exigencia": 95},
    {"nombre": "Actriz Conocida", "usuario_ig": "@actriz", "oficio": "actriz de series", "categoria": "actriz",
     "anio_nacimiento": 1998, "exigencia": 60},
    {"nombre": "Influencer Local", "usuario_ig": "@influ", "oficio": "influencer", "categoria": "influencer",
     "anio_nacimiento": 2001, "exigencia": 20},
]
ECOSISTEMA = {
    "paginas_futbol": [{"nombre": "433", "usuario_ig": "@433", "tipo": "viral"},
                       {"nombre": "Mercado", "usuario_ig": "@mercado", "tipo": "mercado"},
                       {"nombre": "Chismes", "usuario_ig": "@chismes", "tipo": "farandula"}],
    "periodistas": [{"nombre": f"Periodista {estilo} {i}", "usuario_ig": f"@p{estilo}{i}", "medio": f"Medio {i}",
                     "estilo": estilo} for estilo in ("mercado", "tactico", "polemico", "vestuario") for i in range(2)],
    "futbolistas_ig": [{"nombre": "Colega Top", "usuario_ig": "@colega", "rol": "futbolista",
                        "fama_minima_para_comentar": 35}],
}
AUTOS = [{"marca": "Marca", "modelo": f"Modelo {i}", "anio": 1995 + i, "categoria": "JDM Culto",
          "precio_base": 40_000 + 1_000 * i, "rareza": ("Extrema", "Alta", "Media")[i % 3], "nota": "",
          "imagen_local": ""} for i in range(15)]


class ConEcosistema(ayuda.PruebaConBase):
    def setUp(self):
        super().setUp()
        carpeta = Path(tempfile.mkdtemp(prefix="eafc_eco_"))
        (carpeta / "famosas_ig.json").write_text(json.dumps({"celebridades": CELEBRIDADES}), encoding="utf-8")
        (carpeta / "ecosistema_ig.json").write_text(json.dumps(ECOSISTEMA), encoding="utf-8")
        (carpeta / "autos_marketplace.json").write_text(json.dumps({"autos_nicho": AUTOS}), encoding="utf-8")
        parche = mock.patch.dict(os.environ, {"EAFC_ECOSISTEMA": str(carpeta)})
        parche.start()
        self.addCleanup(parche.stop)
        ecosistema._leer.cache_clear()
        self.addCleanup(ecosistema._leer.cache_clear)
        self.perfil = PlayerProfile(nombre_jugador="Simon Canales", club_actual="Man Utd")
        self.perfil.id = database.save_profile(self.perfil)


class TestEcosistema(ConEcosistema):
    def test_lee_los_datos_y_sin_archivos_queda_vacio(self):
        self.assertEqual(len(ecosistema.celebridades()), 3)
        self.assertEqual(len(ecosistema.periodistas()), 8)
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


class TestSeguidores(ayuda.PruebaConBase):
    def test_la_base_y_la_exposicion_segun_el_club_y_los_goles(self):
        self.assertGreater(hinchada.base_de_seguidores(1, 60), 100 * hinchada.base_de_seguidores(3, 60))
        normal = hinchada.exposicion(3, 10, 30)
        estrella = hinchada.exposicion(1, 80, 40, premios=3)
        self.assertGreater(estrella, 20 * normal)  # 80 goles en 40 partidos en un gigante: explota
        self.assertLessEqual(hinchada.exposicion(1, 500, 10, 99), hinchada.TOPE_EXPOSICION)


class TestPatrocinios(ayuda.PruebaConBase):
    def test_oferta_firma_y_cobra_con_el_sueldo(self):
        hoy = date(2026, 10, 1)
        e = economia.acreditar(None, hoy, 100_000)
        with mock.patch.object(patrocinios, "PROBABILIDAD_OFERTA", 1.0):
            e, _ = patrocinios.revisar(e, 1, seguidores=500_000, reputacion=70, hoy=hoy)
        oferta = e["patrocinios"]["oferta"]
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


class TestAutos(ConEcosistema):
    def test_hiperautos_nuevos_y_descontinuados_en_el_garage(self):
        ids = {m.id for m in autos.MODELOS}
        self.assertTrue({"ferrari_f80", "mclaren_w1", "porsche_mission_x"} <= ids)
        self.assertEqual(autos.POR_ID["ferrari_f80"].precio, 3_735_000)
        self.assertNotIn("ferrari_sf90", ids)
        self.assertIn("ferrari_sf90", autos.POR_ID)  # el que lo tenga lo sigue viendo

    def test_marketplace_rota_por_semana_y_se_valoriza(self):
        hoy = date(2026, 10, 7)
        ofertas = marketplace.ofertas(self.perfil.id, hoy)
        self.assertTrue(marketplace.MINIMO_OFERTAS <= len(ofertas) <= marketplace.MAXIMO_OFERTAS)
        self.assertEqual(ofertas, marketplace.ofertas(self.perfil.id, date(2026, 10, 9)))  # la misma semana
        self.assertNotEqual([o["id"] for o in ofertas], [o["id"] for o in marketplace.ofertas(self.perfil.id, date(2026, 10, 20))])
        oferta = ofertas[0]  # (todas las rarezas de los datos se valorizan)
        e = economia.comprar({"saldo": 10_000_000}, marketplace.articulo(oferta), hoy, marketplace.extra_de(oferta))
        posesion = e["posesiones"][0]
        self.assertTrue(posesion["articulo"].startswith(marketplace.PREFIJO))
        self.assertEqual(economia.articulo_de_posesion(posesion).nombre, marketplace.nombre(oferta))
        dos_anios = date(2028, 10, 7)
        self.assertGreater(economia.valor_de_venta(posesion, dos_anios), oferta["precio"])  # subio de valor
        vendido, recuperado = economia.vender(e, posesion["id"], dos_anios)
        self.assertEqual(recuperado, marketplace.valor_de_reventa(posesion, dos_anios))


class TestParejas(ConEcosistema):
    def _soltero(self):
        return {"estado": "soltero", "pareja": None, "hasta": "2026-10-01", "decision": None, "historial": []}

    def test_buscar_y_el_dm_segun_la_fama(self):
        self.assertEqual([c["nombre"] for c in amor.buscar(categoria="actriz")], ["Actriz Conocida"])
        self.assertEqual(len(amor.buscar("@influ")), 1)
        hoy = date(2026, 10, 1)
        estado, _, si = amor.intentar(self._soltero(), {}, CELEBRIDADES[1], fama=70, hoy=hoy)
        self.assertEqual(estado["estado"], "conociendo")
        self.assertEqual(estado["decision"]["tipo"], "como_seguir")
        self.assertTrue(si.privado)
        with self.assertRaises(ValueError):  # un DM por semana (y ya no esta soltero)
            amor.intentar(estado, {}, CELEBRIDADES[2], 70, hoy)

        _, _, visto = amor.intentar(self._soltero(), {}, CELEBRIDADES[0], fama=50, hoy=hoy)
        self.assertFalse(visto.privado)  # muy lejos de su nivel: la captura se filtra
        self.assertEqual((visto.tono, visto.reputacion), ("negativa", -1))
        _, _, nada = amor.intentar(self._soltero(), {}, CELEBRIDADES[1], fama=50, hoy=hoy)
        self.assertTrue(nada.privado)

    def test_romance_secreto_y_despues_publico(self):
        hoy = date(2026, 10, 1)
        estado, e, _ = amor.intentar(self._soltero(), {}, CELEBRIDADES[1], 70, hoy)
        estado, e, suceso = amor.elegir(estado, e, "secreto", hoy)
        self.assertEqual(estado["estado"], "secreto")
        self.assertTrue(suceso.privado)
        database.set_estado_amor(self.perfil.id, estado)
        tipos = [c.tipo for c in cruce.cruces(self.perfil.id)]
        self.assertIn("rumor_secreto", tipos)  # la prensa pregunta por los rumores, sin nombre
        estado["hasta"] = hoy.isoformat()
        estado, e, _ = amor.revisar(self.perfil, estado, e, date(2026, 11, 5), fama=70)
        self.assertEqual(estado["decision"]["tipo"], "salir_a_la_luz")
        estado, e, publico = amor.elegir(estado, e, "publico", date(2026, 11, 5))
        self.assertEqual(estado["estado"], "pareja")
        self.assertFalse(publico.privado)

    def test_lo_ven_con_alguien_de_su_nivel(self):
        dado = random.Random(3)
        for _ in range(10):
            self.assertLessEqual(amor.famosa_para(30, dado)["exigencia"], 30)


class TestConferencia(ConEcosistema):
    def test_periodistas_reales_temas_distintos_y_lo_obligatorio(self):
        stats = MatchStats(goles_equipo=0, goles_rival=2, equipo_rival="Arsenal", rating_jugador=5.1,
                           minutos_jugados=70, tarjeta_roja=True)
        with mock.patch.object(entrevista, "_carrera", return_value=None):
            preguntas = entrevista.generar_entrevista(self.perfil, stats)
        self.assertEqual(len(preguntas), 3)
        nombres = [p.split(" (")[0] for p in preguntas]
        self.assertEqual(len(set(nombres)), 3)
        self.assertTrue(all(n.startswith("Periodista ") for n in nombres))  # los de los datos de Simon
        self.assertTrue(any("roja" in p.lower() or "expuls" in p.lower() for p in preguntas), preguntas)
        for pregunta in preguntas:
            self.assertNotRegex(pregunta, r"[{}]|#\w+#")

    def test_los_temas_varian(self):
        stats = MatchStats(goles_equipo=1, goles_rival=1, equipo_rival="Leeds", rating_jugador=6.8, minutos_jugados=90)
        vistos = set()
        with mock.patch.object(entrevista, "_carrera", return_value=None):
            for _ in range(12):
                with mock.patch.object(entrevista, "preguntas_con_ia", side_effect=lambda *a: vistos.update(a[4]) or None):
                    entrevista.generar_entrevista(self.perfil, stats)
        self.assertGreaterEqual(len(vistos), 6)  # de las 8 tematicas


class TestFeedGlobal(ConEcosistema):
    def test_las_paginas_publican_y_hay_rumores(self):
        eventos = [hinchada.EventoHinchada("partido", "2027-01-16", "Man Utd 5-3 Sunderland · 3 goles tuyos", "", 500),
                   hinchada.EventoHinchada("noticia", "2027-01-16", "Lo ven cenando con Actriz Conocida",
                                           "Noticia sobre el (mixta): romance", 100)]
        carrera = construir(f.construir_bytes())
        with mock.patch.object(feed, "PROBABILIDAD_POST", 1.0), mock.patch.object(feed, "PROBABILIDAD_RUMOR", 1.0), \
                mock.patch.object(feed, "_interesado", return_value="Real Madrid"), \
                mock.patch.object(feed.ecosistema, "fama_jugador", return_value=90):
            posts = feed.actualizar(self.perfil, eventos, [], 1_000_000, 90, carrera)
        tipos = {p["tipo"] for p in posts}
        self.assertTrue({"viral", "farandula", "rumor"} <= tipos, posts)
        self.assertEqual(next(p for p in posts if p["tipo"] == "farandula")["usuario_ig"], "@chismes")
        rumor = next(p for p in posts if p["tipo"] == "rumor")
        self.assertIn("Real Madrid", rumor["texto"])
        self.assertEqual(rumor["usuario_ig"], "@mercado")
        for post in posts:
            self.assertNotRegex(post["texto"], r"[{}]|#\w+#")
            self.assertGreater(post["likes"], 0)


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
