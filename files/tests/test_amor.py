"""Vida sentimental: arranque, sorteo, decisiones y la tarjeta en Vida."""

import os
import tempfile
from datetime import date, timedelta
from pathlib import Path
from unittest import mock

import ayuda
import fabrica_partida as f
from roleplay import database
from roleplay.models import PlayerProfile
from roleplay.partida import lector
from roleplay.partida.carrera import construir
from roleplay.servicios import amor, economia, eventos, hinchada, partida_real

HOY = date(2027, 1, 16)


def perfil(relacion="novia_real", pareja="Denisse"):
    return PlayerProfile(id=7, nombre_jugador="Simon Canales", estado_relacion=relacion, nombre_pareja=pareja)


def plata():
    return economia.acreditar(None, HOY, f.SUELDO)


def con_momentos(*ids):
    return mock.patch.object(amor, "MOMENTOS", [amor.POR_ID[i] for i in ids])


class TestArranque(ayuda.PruebaConBase):
    def test_con_novia_real(self):
        estado, _, sucesos = amor.revisar(perfil(), {}, plata(), HOY)
        self.assertEqual((estado["estado"], sucesos), ("pareja", []))
        self.assertEqual(estado["pareja"]["nombre"], "Denisse")
        self.assertTrue(estado["pareja"]["real"])

    def test_soltero(self):
        estado, _, _ = amor.revisar(perfil("celebridad", ""), {}, plata(), HOY)
        self.assertEqual((estado["estado"], estado["pareja"]), ("soltero", None))
        self.assertEqual(amor.revisar(perfil("novia_real", " "), {}, plata(), HOY)[0]["estado"], "soltero")


class TestConLaNoviaReal(ayuda.PruebaConBase):
    def setUp(self):
        super().setUp()
        self.estado = amor.inicial(perfil(), HOY)

    def test_nunca_le_toca_la_prensa_del_corazon(self):
        posibles = {m.id for m, _ in amor.posibles(perfil(), self.estado, date(2027, 7, 1))}
        self.assertIn("vacaciones", posibles)
        self.assertFalse(posibles & {"alfombra", "rumores_crisis", "entrevista_famosa", "lo_ven", "rumores"})
        self.assertNotIn("vacaciones", {m.id for m, _ in amor.posibles(perfil(), self.estado, HOY)})  # solo en verano

    def test_una_cena_mejora_la_relacion(self):
        with mock.patch.object(amor, "PROBABILIDAD_POR_SEMANA", 1), con_momentos("cena"):
            estado, _, (suceso,) = amor.revisar(perfil(), self.estado, plata(), HOY + timedelta(days=7))
        self.assertEqual(suceso.titulo, "Cena romantica con Denisse")
        self.assertEqual(estado["pareja"]["relacion"], amor.RELACION_INICIAL + 5)
        self.assertEqual(suceso.clave, "amor:cena")

    def test_proponer_casamiento_y_la_boda(self):
        self.estado["pareja"].update(relacion=85, desde="2026-01-01")
        with mock.patch.object(amor, "PROBABILIDAD_POR_SEMANA", 0):
            estado, _, _ = amor.revisar(perfil(), self.estado, plata(), HOY + timedelta(days=7))
        decision, nombre = amor.decision_pendiente(estado)
        self.assertEqual(decision.titulo.format(pareja=nombre), "Le propones casamiento a Denisse?")
        e = plata()
        estado, nueva, suceso = amor.elegir(estado, e, "anillo", HOY)
        self.assertEqual(estado["estado"], "comprometido")
        self.assertEqual(nueva["saldo"], e["saldo"] - round(6 * f.SUELDO * economia.NETO))  # el anillo
        self.assertEqual(suceso.detalle, "le propuso casamiento a Denisse")
        with mock.patch.object(amor, "PROBABILIDAD_POR_SEMANA", 0):
            estado, _, _ = amor.revisar(perfil(), estado, nueva, HOY + timedelta(days=amor.BODA_DESDE_DIAS + 7))
        self.assertEqual(estado["decision"]["tipo"], "boda")
        estado, _, _ = amor.elegir(estado, nueva, "intima", HOY + timedelta(days=amor.BODA_DESDE_DIAS + 7))
        self.assertEqual(estado["estado"], "casado")

    def test_decir_todavia_no_vuelve_a_preguntar_enseguida(self):
        self.estado["pareja"].update(relacion=85, desde="2026-01-01")
        with mock.patch.object(amor, "PROBABILIDAD_POR_SEMANA", 0):
            estado, _, _ = amor.revisar(perfil(), self.estado, plata(), HOY + timedelta(days=7))
            estado, _, _ = amor.elegir(estado, plata(), "todavia", HOY + timedelta(days=7))
            estado["pareja"]["relacion"] = 90
            estado, _, _ = amor.revisar(perfil(), estado, plata(), HOY + timedelta(days=14))
        self.assertIsNone(estado["decision"])

    def test_terminar_con_una_persona_real_no_es_drama(self):
        self.estado["pareja"]["relacion"] = 10
        with mock.patch.object(amor, "PROBABILIDAD_POR_SEMANA", 0):
            estado, _, _ = amor.revisar(perfil(), self.estado, plata(), HOY + timedelta(days=7))
        self.assertEqual(estado["decision"]["tipo"], "crisis")
        estado, _, suceso = amor.elegir(estado, plata(), "terminar", HOY)
        self.assertEqual((estado["estado"], estado["pareja"], suceso.tono), ("soltero", None, "neutral"))


class TestConTuPareja(ayuda.PruebaConBase):
    """Interactuar como en BitLife: citas, regalos, la foto, el anillo, la boda y terminar."""

    def setUp(self):
        super().setUp()
        self.estado = amor.inicial(perfil(), HOY)
        self.e = plata()

    def test_un_regalo_cuesta_y_mejora_la_relacion_una_vez_por_semana(self):
        saldo = self.e["saldo"]
        estado, e, suceso = amor.interactuar(self.estado, self.e, "regalo", HOY)
        self.assertEqual(estado["pareja"]["relacion"], amor.RELACION_INICIAL + amor.ACCIONES["regalo"].relacion)
        self.assertEqual(e["saldo"], saldo - amor.costo_de("regalo", self.e))
        self.assertLess(suceso.dinero, 0)
        self.assertFalse(amor.puede_interactuar(estado, "regalo", HOY + timedelta(days=3))[0])
        self.assertTrue(amor.puede_interactuar(estado, "regalo", HOY + timedelta(days=7))[0])
        self.assertTrue(amor.puede_interactuar(estado, "cena", HOY)[0])  # cada cosa por su lado

    def test_sin_plata_no_hay_regalo_de_lujo(self):
        with self.assertRaises(ValueError):
            amor.interactuar(self.estado, {**self.e, "saldo": 0}, "regalo_lujo", HOY)

    def test_en_secreto_no_se_publica_la_foto(self):
        estado = {**self.estado, "estado": "secreto"}
        self.assertFalse(amor.puede_interactuar(estado, "foto", HOY)[0])
        _, _, suceso = amor.interactuar(estado, self.e, "cena", HOY)
        self.assertTrue(suceso.privado)

    def test_proponer_y_casarse_cuando_se_cumple(self):
        self.assertFalse(amor.puede_proponer(self.estado, HOY)[0])  # recien empiezan
        estado = {**self.estado, "pareja": {**self.estado["pareja"], "relacion": 90, "desde": "2026-01-01"}}
        estado, e, suceso = amor.proponer(estado, self.e, HOY)
        self.assertEqual(estado["estado"], "comprometido")
        self.assertEqual(suceso.titulo, "Le propuso casamiento a Denisse")
        self.assertFalse(amor.puede_casarse(estado, HOY + timedelta(days=30))[0])
        boda = HOY + timedelta(days=amor.BODA_DESDE_DIAS)
        estado, e, suceso = amor.casarse(estado, e, boda, a_lo_grande=False)
        self.assertEqual(estado["estado"], "casado")
        self.assertIn("ceremonia intima", suceso.detalle)
        self.assertTrue(amor.puede_interactuar(estado, "foto_boda", boda)[0])
        estado, _, _ = amor.interactuar(estado, e, "foto_boda", boda)
        self.assertFalse(amor.puede_interactuar(estado, "foto_boda", boda + timedelta(days=30))[0])  # una vez

    def test_terminar_cuando_quiera(self):
        estado, _, suceso = amor.terminar(self.estado, self.e, HOY)
        self.assertEqual(estado["estado"], "soltero")
        self.assertIsNone(estado["pareja"])
        self.assertEqual(suceso.tono, "neutral")  # una persona real: sin drama
        self.assertEqual(suceso.titulo, "Termino con Denisse")
        with self.assertRaises(ValueError):
            amor.terminar(estado, self.e, HOY)


class TestFamilia(ayuda.PruebaConBase):
    """Armar una familia: si, todavia no (su carrera) o nunca; el parto y los hijos."""

    def setUp(self):
        super().setUp()
        self.estado = amor.inicial(perfil(), HOY)
        self.e = plata()

    def test_dice_que_si_y_nace_el_bebe(self):
        estado, e, suceso = amor.hablar_de_hijos(self.estado, self.e, HOY, dado=_dado(0.99, 0.5))
        self.assertTrue(suceso.privado)  # la charla no es noticia
        self.assertTrue(estado["embarazo"])
        self.assertFalse(amor.puede_hablar_de_hijos(estado, HOY)[0])  # ya viene uno
        self.assertFalse(amor.puede_nacer(estado, HOY + timedelta(days=100)))
        dia = HOY + timedelta(days=amor.EMBARAZO_DIAS)
        estado, e, suceso = amor.parto(estado, e, dia, lambda sexo, sugerido: "Ramon")
        self.assertEqual([h["nombre"] for h in amor.hijos(estado)], ["Ramon"])
        self.assertNotIn("embarazo", estado)
        self.assertIn("Ramon", suceso.detalle)
        self.assertFalse(suceso.privado)  # el nacimiento si sale
        self.assertLess(suceso.dinero, 0)
        self.assertTrue(amor.puede_interactuar(estado, "foto_familia", dia)[0])

    def test_todavia_no_o_nunca(self):
        estado, _, suceso = amor.hablar_de_hijos(self.estado, self.e, HOY, dado=_dado(amor.chance_de_no(self.estado)[1] + 0.01))
        self.assertNotIn("embarazo", estado)
        self.assertEqual(suceso.clave, "amor:hijos:todavia")
        self.assertFalse(amor.puede_hablar_de_hijos(estado, HOY + timedelta(days=30))[0])
        self.assertTrue(amor.puede_hablar_de_hijos(estado, HOY + timedelta(days=amor.HIJOS_VOLVER_A_HABLAR_DIAS))[0])
        estado, _, suceso = amor.hablar_de_hijos(self.estado, self.e, HOY, dado=_dado(0.0))
        self.assertEqual(suceso.clave, "amor:hijos:nunca")
        self.assertFalse(amor.puede_hablar_de_hijos(estado, HOY + timedelta(days=999))[0])  # nunca es nunca

    def test_una_famosa_piensa_mas_en_su_carrera(self):
        famosa = {**self.estado, "pareja": {**self.estado["pareja"], "real": False}}
        self.assertGreater(sum(amor.chance_de_no(famosa)), sum(amor.chance_de_no(self.estado)))
        self.assertLess(sum(amor.chance_de_no(famosa)), 0.5)  # no muy alta

    def test_los_hijos_quedan_aunque_terminen(self):
        estado, e, _ = amor.hablar_de_hijos(self.estado, self.e, HOY, dado=_dado(0.99, 0.0))  # mellizos
        estado, e, _ = amor.terminar(estado, e, HOY)
        estado, _, suceso = amor.parto(estado, e, HOY + timedelta(days=amor.EMBARAZO_DIAS))
        self.assertEqual(len(amor.hijos(estado)), 2)
        self.assertIn("mellizos", suceso.detalle)
        self.assertEqual(estado["estado"], "soltero")


class TestConUnaFamosa(ayuda.PruebaConBase):
    def test_lo_ven_con_una_famosa_inventada_y_lo_hace_oficial(self):
        estado = amor.inicial(perfil("celebridad", ""), HOY)
        with mock.patch.object(amor, "PROBABILIDAD_POR_SEMANA", 1), con_momentos("lo_ven"):
            estado, _, (suceso,) = amor.revisar(perfil("celebridad", ""), estado, plata(), HOY + timedelta(days=7))
        famosa = estado["pareja"]
        self.assertEqual(estado["estado"], "conociendo")
        self.assertFalse(famosa["real"])
        nombre, apellido = famosa["nombre"].split(" ", 1)
        self.assertIn(nombre, amor.NOMBRES)  # inventada: sale de las listas propias
        self.assertIn(apellido, amor.APELLIDOS)
        self.assertIn(famosa["oficio"], suceso.titulo)
        self.assertEqual(estado["decision"]["tipo"], "oficial")
        estado, _, suceso = amor.elegir(estado, plata(), "oficializar", HOY + timedelta(days=7))
        self.assertEqual((estado["estado"], estado["pareja"]["relacion"]), ("pareja", 60))
        posibles = {m.id for m, _ in amor.posibles(perfil("celebridad", ""), estado, HOY)}
        self.assertIn("alfombra", posibles)  # con una famosa si hay prensa del corazon

    def test_negarlo(self):
        estado = amor.inicial(perfil("soltero", ""), HOY)
        with mock.patch.object(amor, "PROBABILIDAD_POR_SEMANA", 1), con_momentos("lo_ven"):
            estado, _, _ = amor.revisar(perfil("soltero", ""), estado, plata(), HOY + timedelta(days=7))
        estado, _, _ = amor.elegir(estado, plata(), "negar", HOY)
        self.assertEqual((estado["estado"], estado["pareja"]), ("soltero", None))

    def test_la_misma_partida_la_misma_famosa(self):
        def sortear():
            with mock.patch.object(amor, "PROBABILIDAD_POR_SEMANA", 1), con_momentos("lo_ven"):
                return amor.revisar(perfil("celebridad", ""), amor.inicial(perfil("celebridad", ""), HOY), plata(),
                                    HOY + timedelta(days=7))[0]["pareja"]["nombre"]

        self.assertEqual(sortear(), sortear())


class TestTarjetaEnVida(ayuda.PruebaDeInterfaz):
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
        self.addCleanup(ayuda.esperar_tareas)
        self.pid = database.save_profile(PlayerProfile(nombre_jugador="Simon Canales", club_actual="Man Utd",
                                                       estado_relacion="novia_real", nombre_pareja="Denisse"))
        from roleplay.ui.vida import PaginaVida

        self.pagina = PaginaVida()
        self.avisos = []
        self.pagina.decision_pendiente.connect(self.avisos.append)
        self.pagina.actualizar()
        ayuda.esperar_tareas()

    def test_muestra_la_pareja(self):
        self.assertFalse(self.pagina.amor.isHidden())
        self.assertIn("En pareja con <b>Denisse</b>", self.pagina.amor_label.text())
        self.assertTrue(self.pagina.amor_decision.isHidden())

    def test_la_propuesta(self):
        estado = database.get_estado_amor(self.pid)
        estado["pareja"].update(relacion=90, desde="2026-01-01")
        database.set_estado_amor(self.pid, estado)
        una_semana_despues = construir(f.construir_bytes(otros_partidos=[(20270123, f.LIGA, f.CITY, f.LIVERPOOL, 1, 0, True)]))
        self.pagina.acreditar_con(una_semana_despues)
        self.assertEqual(self.avisos, ["Le propones casamiento a Denisse?"])
        self.assertFalse(self.pagina.amor_decision.isHidden())
        seguidores = database.get_seguidores(self.pid)
        self.pagina.elegir_amor("anillo")
        ayuda.esperar_tareas()
        self.assertEqual(database.get_estado_amor(self.pid)["estado"], "comprometido")
        self.assertIn("Comprometido con", self.pagina.amor_label.text())
        self.assertGreater(database.get_seguidores(self.pid), seguidores)
        noticia = database.load_noticias_prensa(self.pid)[0]
        self.assertEqual(noticia.hitos, ["amor:proponer:anillo"])
        self.assertEqual([a.tipo for a in database.load_actividad_instagram(self.pid)], ["amor"])

    def test_botones_con_la_pareja(self):
        botones = {b.property("accion_amor"): b for b in self.pagina.findChildren(type(self.pagina.oficializar_btn))
                   if b.property("accion_amor")}
        self.assertEqual(set(botones), {"cena", "regalo", "regalo_lujo", "escapada", "foto"})
        botones["cena"].click()
        ayuda.esperar_tareas()
        self.assertEqual(database.load_noticias_prensa(self.pid)[0].hitos, ["amor:cena"])
        self.assertIn("Canales salio a cenar con Denisse", database.load_noticias_prensa(self.pid)[0].titular)

    def test_la_foto_juntos_va_a_su_instagram(self):
        with mock.patch.object(type(self.pagina), "_texto_del_post", return_value="Con Denisse ❤️"):
            self.pagina.interactuar_amor("foto")
            ayuda.esperar_tareas()
        post = database.load_instagram_posts(self.pid)[0]
        self.assertEqual(post.texto, "Con Denisse ❤️")
        self.assertGreater(post.crecimiento_seguidores, 0)

    def test_terminar_pide_confirmacion(self):
        with mock.patch.object(type(self.pagina), "_confirmar", return_value=False):
            self.pagina.terminar_relacion()
        self.assertEqual(database.get_estado_amor(self.pid)["estado"], "pareja")
        with mock.patch.object(type(self.pagina), "_confirmar", return_value=True):
            self.pagina.terminar_relacion()
            ayuda.esperar_tareas()
        self.assertEqual(database.get_estado_amor(self.pid)["estado"], "soltero")
        self.assertIn("<b>Soltero</b>", self.pagina.amor_label.text())

    def test_armar_una_familia_y_el_parto(self):
        from roleplay.ui.vida import PaginaVida

        estado = database.get_estado_amor(self.pid)
        estado["embarazo"] = {"desde": "2020-01-01", "con": "Denisse", "real": True, "gemelos": False}
        database.set_estado_amor(self.pid, estado)
        self.pagina.actualizar()
        ayuda.esperar_tareas()
        with mock.patch.object(PaginaVida, "_nombre_del_bebe", return_value="Ramon"):
            self.pagina.ir_al_hospital()
            ayuda.esperar_tareas()
        self.assertEqual(amor.hijos(database.get_estado_amor(self.pid))[0]["nombre"], "Ramon")
        self.assertEqual(database.load_noticias_prensa(self.pid)[0].hitos, ["amor:nacimiento"])
        botones = {b.property("paso_amor") for b in self.pagina.findChildren(type(self.pagina.oficializar_btn))
                   if b.isVisibleTo(self.pagina)}
        self.assertIn("hijos", botones)


# ---- parejas del catalogo, DMs y romance secreto (datos de prueba: tests/datos_ecosistema.py) ----

import random  # noqa: E402

from datos_ecosistema import CELEBRIDADES, ConEcosistema  # noqa: E402
from roleplay.servicios import cruce  # noqa: E402


def _dado(*valores):
    """Un dado que devuelve `valores` en orden (para que el DM no dependa del azar)."""
    return mock.Mock(random=mock.Mock(side_effect=list(valores)))


class TestParejas(ConEcosistema):
    def _soltero(self):
        return {"estado": "soltero", "pareja": None, "hasta": "2026-10-01", "decision": None, "historial": []}

    def test_buscar_y_el_dm_segun_la_fama(self):
        self.assertEqual([c["nombre"] for c in amor.buscar(categoria="actriz")], ["Actriz Conocida"])
        self.assertEqual(len(amor.buscar("@influ")), 1)
        hoy = date(2026, 10, 1)
        estado, _, si = amor.intentar(self._soltero(), {}, CELEBRIDADES[1], fama=70, hoy=hoy, dado=_dado(0.0))
        self.assertEqual(estado["estado"], "conociendo")
        self.assertEqual(estado["decision"]["tipo"], "como_seguir")
        self.assertTrue(si.privado)
        with self.assertRaises(ValueError):  # un DM por semana (y ya no esta soltero)
            amor.intentar(estado, {}, CELEBRIDADES[2], 70, hoy)

        # muy lejos de su nivel: visto y la captura llega a los portales de chismes
        _, _, visto = amor.intentar(self._soltero(), {}, CELEBRIDADES[0], fama=50, hoy=hoy, dado=_dado(0.99, 0.0))
        self.assertFalse(visto.privado)
        self.assertEqual((visto.tono, visto.reputacion), ("negativa", -1))
        self.assertIn("chismes", visto.detalle)
        _, _, nada = amor.intentar(self._soltero(), {}, CELEBRIDADES[0], fama=50, hoy=hoy, dado=_dado(0.99, 0.99))
        self.assertTrue(nada.privado)  # visto, pero no se filtro

    def test_la_chance_y_la_filtracion(self):
        self.assertAlmostEqual(amor.probabilidad_de_exito(70, 70), amor.EXITO_AL_ALCANZAR)
        self.assertEqual(amor.probabilidad_de_exito(100, 60), amor.EXITO_MAXIMO)  # casi seguro, nunca 100%
        self.assertEqual(amor.probabilidad_de_exito(40, 95), amor.EXITO_MINIMO)  # una megaestrella: casi imposible
        self.assertLess(amor.probabilidad_de_exito(60, 70), amor.probabilidad_de_exito(70, 70))
        self.assertEqual(amor.probabilidad_de_filtracion(60, 65), 0)  # cerca de su nivel: no es noticia
        self.assertGreater(amor.probabilidad_de_filtracion(40, 95), amor.probabilidad_de_filtracion(50, 75))

    def test_oficializar_un_romance_secreto_cuando_quiera(self):
        hoy = date(2026, 10, 1)
        estado, e, _ = amor.intentar(self._soltero(), {}, CELEBRIDADES[1], 70, hoy, dado=_dado(0.0))
        estado, e, _ = amor.elegir(estado, e, "secreto", hoy)
        estado, e, suceso = amor.oficializar(estado, e, date(2026, 10, 3))  # sin esperar el mes
        self.assertEqual(estado["estado"], "pareja")
        self.assertFalse(suceso.privado)
        self.assertGreater(suceso.seguidores, 0)  # boom de seguidores
        with self.assertRaises(ValueError):
            amor.oficializar(estado, e, hoy)

    def test_romance_secreto_y_despues_publico(self):
        hoy = date(2026, 10, 1)
        estado, e, _ = amor.intentar(self._soltero(), {}, CELEBRIDADES[1], 70, hoy, dado=_dado(0.0))
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


class TestPartidaDePrueba(ayuda.PruebaConBase):
    """scripts/partida_de_prueba.py: su propia carpeta, soltero, y sin espera entre DMs."""

    def test_arma_su_carpeta_sin_tocar_la_real(self):
        import subprocess
        import sys

        carpeta = Path(tempfile.mkdtemp(prefix="eafc_prueba_parejas_")) / "prueba"
        resultado = subprocess.run(
            [sys.executable, str(ayuda.RAIZ / "scripts" / "partida_de_prueba.py"), "--sin-abrir", "--reputacion", "90",
             "--carpeta", str(carpeta)], capture_output=True, text=True, timeout=120,
        )
        self.assertEqual(resultado.returncode, 0, resultado.stderr)
        self.assertTrue((carpeta / "career_roleplay.db").exists())
        self.assertTrue((carpeta / "guardados" / "CmPlr1").exists())
        import sqlite3

        with sqlite3.connect(carpeta / "career_roleplay.db") as conn:
            nombre, relacion, reputacion = conn.execute(
                "SELECT nombre_jugador, estado_relacion, reputacion_inicial FROM player_profile").fetchone()
        self.assertEqual((nombre, relacion, reputacion), ("Tomas Ferreyra", "soltero", 90))

    def test_en_la_de_prueba_no_hay_espera_entre_dms(self):
        estado = {"estado": "soltero", "ultimo_dm": "2026-10-01", "decision": None}
        self.assertFalse(amor.puede_mandar_dm(estado, date(2026, 10, 2)))
        with mock.patch.dict(os.environ, {"EAFC_DM_SIN_ESPERA": "1"}):
            self.assertTrue(amor.puede_mandar_dm(estado, date(2026, 10, 2)))
