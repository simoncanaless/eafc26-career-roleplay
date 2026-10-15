import os
import tempfile
import time
import unittest
from datetime import date
from pathlib import Path
from unittest import mock

import ayuda
import fabrica_partida as f
from roleplay import ajustes, config, database
from roleplay.models import MatchInterviewRecord, PlayerProfile
from roleplay.partida import lector
from roleplay.partida.carrera import construir
from roleplay.partida.formato import FormatoDesconocido
from roleplay.servicios import partida_real, prensa


def carrera_falsa():
    return construir(f.construir_bytes(), "falsa")


class TestFormatoYCarrera(unittest.TestCase):
    def setUp(self):
        self.c = carrera_falsa()

    def test_el_mundo_de_la_partida(self):
        c = self.c
        self.assertEqual(c.partida, "Carrera - Prog. de Futbolista 1")
        self.assertEqual(c.equipo(f.MAN_UTD), "Man Utd")  # el id se guarda restando 1
        self.assertEqual((c.usuario_id, c.nombre_editado(f.USUARIO)), (f.USUARIO, "Simon Canales"))
        self.assertEqual(c.nombre_editado(41), "A. Iniesta")  # con apodo, el apodo
        self.assertEqual(c.equipo_usuario(), f.MAN_UTD)
        self.assertEqual(c.fecha_actual(), date(2027, 1, 16))
        self.assertEqual(len(c.partidos), len(f.PARTIDOS))  # la basura entre medio se salta

    def test_competiciones(self):
        liga, champions = self.c.competiciones[f.LIGA], self.c.competiciones[f.CHAMPIONS]
        self.assertEqual((liga.nombre, liga.es_liga, liga.continental), ("Premier League", True, False))
        self.assertEqual((champions.nombre, champions.es_liga, champions.continental), (None, False, True))
        self.assertEqual(self.c.competicion(f.CHAMPIONS), "torneo continental")

    def test_partidos_y_quien_marco(self):
        c = self.c
        ultimo = c.ultimo_partido_de(f.MAN_UTD)
        self.assertEqual((ultimo.local, ultimo.visita, ultimo.goles_local, ultimo.goles_visita), (f.MAN_UTD, f.SUNDERLAND, 5, 3))
        self.assertEqual(ultimo.resultado_para(f.SUNDERLAND), "derrota")
        actuaciones = c.actuaciones_en(ultimo)
        self.assertEqual([(a.jugador, a.goles, a.nota) for a in actuaciones], [(f.USUARIO, 5, 10.0), (f.BRUNO, 0, 7.5)])
        goleada = next(p for p in c.partidos if p.local == f.CITY and p.visita == f.LIVERPOOL)
        self.assertEqual([(a.jugador, a.goles) for a in c.actuaciones_en(goleada)], [(f.HAALAND, 3)])
        proximo = c.proximo_partido_de(f.MAN_UTD)
        self.assertEqual((proximo.local, proximo.jugado, proximo.goles_local), (f.NAPOLI, False, None))

    def test_tabla_calculada_con_los_resultados(self):
        tabla = self.c.tabla(f.LIGA)
        self.assertEqual([(fila.equipo, fila.pts, fila.pj) for fila in tabla[:2]], [(f.CITY, 7, 3), (f.MAN_UTD, 6, 2)])
        self.assertEqual(self.c.posicion_en(f.LIGA, f.MAN_UTD), 2)
        self.assertEqual([e.jugador for e in self.c.goleadores(f.LIGA, 2)], [f.USUARIO, f.HAALAND])

    def test_ficha_para_reconocer_al_jugador(self):
        self.assertEqual(
            self.c.ficha(f.HAALAND),
            {"id": f.HAALAND, "club": "Manchester City", "posicion": "delantero centro", "seleccion": "Noruega",
             "media": 92, "nacimiento": "2000-07-21", "edad": 26, "goles_en_la_temporada": 5},
        )

    def test_club_seleccion_y_agentes_libres(self):
        self.assertEqual(self.c.club_de(f.HAALAND), f.CITY)  # no Noruega
        self.assertTrue(self.c.es_seleccion(f.NORUEGA))
        self.assertTrue(self.c.es_agentes_libres(f.AGENTES_LIBRES))
        self.assertEqual(self.c.club_de(f.JUGADORA), f.ARSENAL_FEM)
        self.assertEqual(self.c.mujeres, {f.JUGADORA})
        self.assertEqual(self.c.medias[f.USUARIO], 79)
        # suplente en el plantel: la ficha usa la posicion que prefiere
        self.assertEqual(self.c.ficha(f.SUPLENTE_CITY)["posicion"], "lateral derecho")

    def test_un_archivo_que_no_es_una_partida(self):
        with self.assertRaises(FormatoDesconocido):
            construir(b"esto no es un guardado")
        datos = f.construir_bytes()
        cortado = datos[: datos.index(b"stndgs")]  # el juego lo estaba escribiendo
        with self.assertRaises(FormatoDesconocido):
            construir(cortado)


class TestLector(ayuda.PruebaConBase):
    def setUp(self):
        super().setUp()
        carpeta = tempfile.TemporaryDirectory()
        self.addCleanup(carpeta.cleanup)
        self.carpeta = Path(carpeta.name)
        parche = mock.patch.object(lector, "CARPETA_GUARDADOS", self.carpeta)
        parche.start()
        self.addCleanup(parche.stop)
        parche = mock.patch.object(config, "ARCHIVO_AJUSTES", self.carpeta / "ajustes.json")
        parche.start()
        self.addCleanup(parche.stop)

    def _guardar(self, nombre: str, antiguedad: float = 0) -> Path:
        ruta = self.carpeta / nombre
        ruta.write_bytes(f.construir_bytes(nombre))
        momento = time.time() - antiguedad
        os.utime(ruta, (momento, momento))
        return ruta

    def test_sin_partidas(self):
        self.assertIsNone(lector.carrera_actual())

    def test_usa_la_carrera_jugador_mas_reciente_o_la_elegida(self):
        vieja = self._guardar("CmPlr20260101", antiguedad=500)
        self._guardar("CmPlr20260202")
        self._guardar("CmMgrC20260303")  # carrera entrenador: no
        self.assertEqual(lector.carrera_actual().partida, "CmPlr20260202")
        ajustes.guardar(partida=str(vieja))
        self.assertEqual(lector.carrera_actual().partida, "CmPlr20260101")

    def test_cache_mientras_el_archivo_no_cambie(self):
        ruta = self._guardar("CmPlr1")
        primera = lector.leer(ruta)
        self.assertIs(lector.leer(ruta), primera)
        os.utime(ruta, (time.time() + 5, time.time() + 5))
        self.assertIsNot(lector.leer(ruta), primera)

    def test_la_lectura_no_toca_el_guardado(self):
        ruta = self._guardar("CmPlr1")
        antes = (ruta.read_bytes(), ruta.stat().st_mtime)
        lector.leer(ruta)
        self.assertEqual((ruta.read_bytes(), ruta.stat().st_mtime), antes)


class TestPartidaReal(ayuda.PruebaConBase):
    def setUp(self):
        super().setUp()
        self.c = carrera_falsa()

    def test_ultimo_partido_la_primera_vez(self):
        ultimo = partida_real.ultimo_partido(self.c, {})
        s = ultimo.stats
        self.assertEqual(
            (s.goles_equipo, s.goles_rival, s.equipo_rival, s.goles_jugador, s.rating_jugador, s.minutos_jugados),
            (5, 3, "Sunderland", 5, 10.0, 90),
        )
        self.assertFalse(ultimo.exacto)  # sin lectura anterior no se saben las asistencias
        self.assertEqual(s.asistencias_jugador, 0)
        self.assertEqual(ultimo.resumen, "Man Utd 5-3 Sunderland · Premier League · 16-01-2027")

    def test_asistencias_tarjetas_y_figura_comparando_con_la_lectura_anterior(self):
        anterior = {"ultimo_partido": "otro", "totales": {str(f.LIGA): {
            "partidos": 1, "goles": 1, "asistencias": 0, "amarillas": 0, "rojas": 0, "figura": 1}}}
        ultimo = partida_real.ultimo_partido(self.c, anterior)
        self.assertTrue(ultimo.exacto)
        self.assertEqual((ultimo.stats.asistencias_jugador, ultimo.stats.hombre_del_partido), (2, True))
        # volver a cargarlo da lo mismo, aunque los totales ya esten al dia
        otra_vez = partida_real.ultimo_partido(self.c, ultimo.estado)
        self.assertEqual((otra_vez.exacto, otra_vez.stats.asistencias_jugador), (True, 2))

    def test_si_se_saltaron_partidos_no_se_inventa(self):
        anterior = {"totales": {str(f.LIGA): dict.fromkeys(partida_real.CAMPOS_TOTALES, 0)}}
        self.assertFalse(partida_real.ultimo_partido(self.c, anterior).exacto)  # 2 partidos de diferencia

    def test_hechos_del_mundo(self):
        hechos = partida_real.hechos_destacados(self.c, desde=date(2027, 1, 1), cantidad=3)
        self.assertEqual(hechos[0].figura, f.HAALAND)  # hat-trick primero
        self.assertEqual(hechos[0].goles_figura, 3)
        self.assertTrue(all(not h.partido.participa(f.MAN_UTD) for h in hechos))  # los del usuario no
        self.assertEqual(partida_real.hechos_destacados(self.c, desde=date(2027, 1, 16)), [])
        texto = partida_real.describir_hecho(self.c, hechos[0], {f.HAALAND: "Erling Haaland"})
        self.assertIn("Manchester City 4-0 Liverpool", texto)
        self.assertIn("Erling Haaland (Manchester City) marco 3 goles, nota 9.6", texto)
        sin_nombre = partida_real.describir_hecho(self.c, hechos[0], {})
        self.assertIn("el delantero centro del Manchester City", sin_nombre)

    def test_los_nombres_salen_de_la_base_local(self):
        locales = {f.HAALAND: ("Erling Haaland", True), f.DELANTERO_ARSENAL: ("", False)}
        with mock.patch.object(partida_real, "identificar_jugadores", side_effect=lambda fichas: {
                ficha["id"]: locales[ficha["id"]] for ficha in fichas}):
            nombres = partida_real.nombres_de_jugadores(self.c, {f.HAALAND, f.USUARIO, f.DELANTERO_ARSENAL})
            self.assertEqual(nombres, {f.HAALAND: "Erling Haaland", f.USUARIO: "Simon Canales"})  # el editado, de la partida
            # lo que adivino la IA en versiones viejas (tabla nombre_conocido) ya no se usa
            database.guardar_nombres_conocidos("jugador", {f.DELANTERO_ARSENAL: ("Adivinado por la IA", True)})
            self.assertEqual(partida_real.nombres_de_jugadores(self.c, {f.DELANTERO_ARSENAL}), {})
        self.assertEqual(database.get_nombres_conocidos("jugador", {f.HAALAND}), {})  # leer no guarda nada

    def test_la_base_local_no_inventa(self):
        from roleplay.servicios import identificar

        base = {"jugadores": {str(f.HAALAND): {"nombre": "Erling Haaland", "nacimiento": "2000-07-21"}}}
        ficha = {"id": f.HAALAND, "nacimiento": "1999-01-01"}
        with mock.patch.object(identificar, "jugadores_conocidos", return_value=base["jugadores"]):
            self.assertEqual(identificar.identificar_jugadores([ficha]), {f.HAALAND: ("", False)})  # otra persona
            ficha["nacimiento"] = "2000-07-21"
            self.assertEqual(identificar.identificar_jugadores([ficha]), {f.HAALAND: ("Erling Haaland", True)})
            self.assertEqual(identificar.identificar_jugadores([{"id": 99999}]), {99999: ("", False)})

    def test_la_base_de_nombres_trae_el_nacimiento_de_cada_uno(self):
        # sin el nacimiento no hay como saber si el id es la persona: la IA vieja
        # habia puesto a Haaland en el id de Vinicius Jr (nacidos con 9 dias de diferencia)
        from roleplay.servicios import identificar

        base = identificar.jugadores_conocidos()
        self.assertTrue(base)
        for ident, entrada in base.items():
            self.assertRegex(entrada["nacimiento"], r"^\d{4}-\d{2}-\d{2}$", ident)
            self.assertTrue(entrada["nombre"].strip(), ident)
        nombres = [entrada["nombre"] for entrada in base.values()]
        self.assertEqual(len(nombres), len(set(nombres)), "un mismo jugador con dos ids")

    def test_nombres_faltantes_y_agregar_uno(self):
        import importlib.util
        import json

        ruta = Path(__file__).resolve().parent.parent / "scripts" / "nombres_faltantes.py"
        especificacion = importlib.util.spec_from_file_location("nombres_faltantes", ruta)
        script = importlib.util.module_from_spec(especificacion)
        especificacion.loader.exec_module(script)
        with mock.patch.object(script.identificar, "jugadores_conocidos", return_value={}):
            faltan = {ficha["id"] for ficha in script.sin_nombre(self.c)}
        self.assertIn(f.HAALAND, faltan)
        self.assertNotIn(f.USUARIO, faltan)  # el editado en la partida ya tiene nombre
        archivo = Path(self.enterContext(tempfile.TemporaryDirectory())) / "jugadores.json"
        archivo.write_text('{"_que_es": "x", "jugadores": {}}', encoding="utf-8")
        entrada = script.agregar(self.c, f.HAALAND, " Erling Haaland ", archivo)
        self.assertEqual(entrada, {"nombre": "Erling Haaland", "nacimiento": self.c.ficha(f.HAALAND)["nacimiento"]})
        self.assertEqual(json.loads(archivo.read_text(encoding="utf-8"))["jugadores"], {str(f.HAALAND): entrada})

    def test_la_prensa_escribe_sobre_un_hecho_real(self):
        perfil = PlayerProfile(id=1, nombre_jugador="Simon Canales")
        hechos = []
        original = prensa.noticia_del_mundo

        def espiar(escritor, perfil_, hecho):
            hechos.append(hecho)
            return original(escritor, perfil_, hecho)

        def de_partidos():
            return [h for h in hechos if h["tipo"] in ("hat_trick", "goleada", "choque")]

        with mock.patch.object(prensa, "noticia_del_mundo", espiar), \
                mock.patch.object(partida_real, "identificar_jugadores", side_effect=lambda fichas: {
                    ficha["id"]: ("Erling Haaland", True) if ficha["id"] == f.HAALAND else ("", False) for ficha in fichas}), \
                mock.patch.object(partida_real, "identificar_competiciones", return_value={f.CHAMPIONS: ("Champions League", True)}):
            resultado = partida_real.revisar_prensa_con_partida(perfil, [], {"partida_hasta": "2027-01-01"}, self.c)
            (hecho,) = de_partidos()
            self.assertEqual((hecho["tipo"], hecho["figura"]), ("hat_trick", "Erling Haaland"))
            self.assertIn("Erling Haaland (Manchester City) marco 3 goles", hecho["texto"])
            self.assertEqual(self.c.competiciones[f.CHAMPIONS].nombre, "Champions League")  # la copa quedo con nombre
            noticia = resultado["noticias"][-1]
            self.assertEqual(noticia.categoria, "general")
            self.assertIn("Haaland", noticia.titular)
            self.assertIn(hecho["texto"], noticia.cuerpo)
            estado = resultado["estado_prensa"]
            self.assertEqual(estado["partida_hasta"], "2027-01-16")
            # el mismo hecho no sale dos veces
            hechos.clear()
            partida_real.revisar_prensa_con_partida(perfil, [], estado, self.c)
        self.assertEqual(de_partidos(), [])

    def test_la_primera_vez_solo_la_ultima_semana_del_juego(self):
        hechos = partida_real.hechos_destacados(self.c)  # hoy en el juego: 16-01-2027
        self.assertTrue(hechos)
        self.assertTrue(all(h.partido.fecha > date(2027, 1, 9) for h in hechos))

    def test_ya_entrevistado(self):
        ultimo = partida_real.ultimo_partido(self.c, {})
        historial = [MatchInterviewRecord(equipo_rival="Sunderland", origen="partida", fecha_juego="2027-01-16")]
        self.assertTrue(partida_real.ya_entrevistado(ultimo, historial))
        self.assertFalse(partida_real.ya_entrevistado(ultimo, [MatchInterviewRecord(equipo_rival="Sunderland")]))


class TestResumenConLaPartida(ayuda.PruebaDeInterfaz):
    def test_la_temporada_real_en_el_resumen(self):
        carpeta = tempfile.TemporaryDirectory()
        self.addCleanup(carpeta.cleanup)
        (Path(carpeta.name) / "CmPlr1").write_bytes(f.construir_bytes())
        pid = database.save_profile(PlayerProfile(nombre_jugador="Simon Canales", club_actual="Palermo"))
        from roleplay.ui.menu import PaginaResumen

        with mock.patch.object(lector, "CARPETA_GUARDADOS", Path(carpeta.name)),                 mock.patch.object(partida_real, "identificar_competiciones", return_value={f.CHAMPIONS: ("Champions League", True)}):
            resumen = partida_real.resumen_temporada()
            self.assertEqual([c[0] for c in resumen.por_competicion], ["Premier League", "Champions League"])
            self.assertEqual([u[0] for u in resumen.ultimos], ["G", "E", "G"])  # del mas viejo al ultimo
            self.assertEqual(resumen.ultimos[-1][1], "Man Utd 5-3 Sunderland")
            self.assertEqual(resumen.totales["goles"], 8)
            pagina = PaginaResumen(lambda: None)
            pagina.actualizar()
            ayuda.esperar_tareas()
        self.assertEqual(database.load_profile(pid).club_actual, "Man Utd")  # club sincronizado
        self.assertTrue(pagina.temporada.isVisibleTo(pagina))
        self.assertEqual(pagina.mosaicos["goles"].numero.text(), "8")
        self.assertIn("2° en la Premier League", pagina.temporada_label.text())


class TestSalaDePrensaConLaPartida(ayuda.PruebaDeInterfaz):
    def setUp(self):
        super().setUp()
        self.pid = database.save_profile(PlayerProfile(nombre_jugador="Simon Canales", club_actual="Palermo"))
        from roleplay.ui import entrevista

        self.modulo = entrevista
        lectura = partida_real.LecturaPartida(
            carrera=carrera_falsa(), ultimo=None, ya_entrevistado=False
        )
        lectura.ultimo = partida_real.ultimo_partido(lectura.carrera, {})
        parche = mock.patch.object(entrevista, "leer_para_entrevista", return_value=lectura)
        parche.start()
        self.addCleanup(parche.stop)
        self.pagina = entrevista.InterviewWindow()
        ayuda.esperar_tareas()

    def test_cargar_el_ultimo_partido(self):
        p = self.pagina
        self.assertIn("Man Utd 5-3 Sunderland", ayuda.texto_visible(p.partida_label.text()))
        self.assertTrue(p.cargar_partida_btn.isEnabled())
        p.cargar_partida_btn.click()

        stats = p._leer_stats_desde_formulario()
        self.assertEqual((stats.goles_equipo, stats.goles_rival, stats.equipo_rival, stats.goles_jugador, stats.rating_jugador),
                         (5, 3, "Sunderland", 5, 10.0))
        self.assertEqual(database.load_profile(self.pid).club_actual, "Man Utd")  # el club se actualiza
        self.assertIn("revisalas a mano", p.partida_nota.text())  # primera vez: asistencias no se saben
        self.assertEqual(database.get_estado_partida(self.pid)["ultimo_partido"], "2027-01-16|808|11|106")

        with mock.patch.object(self.modulo, "generar_entrevista", return_value=["P1?"]) as generar:
            p.generar_entrevista_btn.click()
            ayuda.esperar_tareas()
        self.assertEqual(generar.call_args.args[1].equipo_rival, "Sunderland")  # las stats de la partida

        p._respuesta_edits[0].setPlainText("Cinco goles, que mas se puede pedir")
        reaccion = self.modulo.evaluar_respuestas.__globals__["ReaccionPrensa"](reaccion_prensa="Bien", delta_reputacion=3)
        with mock.patch.object(self.modulo, "evaluar_respuestas", return_value=reaccion), \
                mock.patch.object(self.modulo, "revisar_prensa_con_partida",
                                  return_value={"noticias": [], "hitos": [], "estado_prensa": {}}) as prensa_real:
            p.enviar_respuestas_btn.click()
            ayuda.esperar_tareas()
            ayuda.esperar_tareas()
        partido = database.load_match_interviews(self.pid)[0]
        self.assertEqual((partido.origen, partido.fecha_juego, partido.goles_jugador), ("partida", "2027-01-16", 5))
        prensa_real.assert_called_once()  # la prensa usa la partida

    def test_sin_partida_se_dice_y_se_puede_seguir(self):
        with mock.patch.object(self.modulo, "leer_para_entrevista", return_value=None):
            pagina = self.modulo.InterviewWindow()
            ayuda.esperar_tareas()
        self.assertIn("No encontre una partida", pagina.partida_label.text())
        self.assertFalse(pagina.cargar_partida_btn.isEnabled())
        self.assertTrue(pagina.generar_entrevista_btn.isEnabled())  # las stats se escriben a mano


class TestPartidaRealDelPC(unittest.TestCase):
    """Con la partida de verdad de este PC, si hay (solo lectura). En el PC
    de los amigos o sin FC 26, se salta."""

    def setUp(self):
        carpeta = Path(os.environ.get("LOCALAPPDATA", "")) / "EA SPORTS FC 26" / "settings"
        self.guardados = lector.guardados(carpeta) if carpeta.is_dir() else []
        if not self.guardados:
            self.skipTest("No hay partidas de Carrera Jugador de FC 26 en este PC")

    def test_se_lee_entera_y_cuadra(self):
        carrera = construir(self.guardados[0].read_bytes(), str(self.guardados[0]))
        self.assertIsNotNone(carrera.usuario_id, "no se encontro al jugador del usuario")
        self.assertIsNotNone(carrera.equipo_usuario())
        jugados = [p for p in carrera.partidos if p.jugado]
        self.assertTrue(jugados)
        revisados = cuadran = 0
        for partido in jugados:
            actuaciones = carrera.actuaciones_en(partido)
            for equipo in (partido.local, partido.visita):
                suyas = [a for a in actuaciones if a.equipo == equipo]
                if suyas:
                    revisados += 1
                    cuadran += sum(a.goles for a in suyas) == partido.goles_de(equipo)
        self.assertGreater(cuadran / revisados, 0.9, f"solo {cuadran}/{revisados} marcadores cuadran")


if __name__ == "__main__":
    unittest.main()
