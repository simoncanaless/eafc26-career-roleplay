"""El motor narrativo local: la gramatica, la cola anti-repeticion, el
evaluador lexico, los cruces con el resto de la vida, la memoria de las
entrevistas y el backstory. Y la IA hibrida (servicios/ia.py) con la red mockeada: la
cascada Groq -> Gemini -> None y la caida limpia al motor local."""

import json
import random
import re
import unittest
from unittest import mock

import ayuda
import fabrica_partida as f
from roleplay import database
from roleplay.models import MatchInterviewRecord, PlayerProfile
from roleplay.partida.carrera import construir
from roleplay.servicios import backstory, cruce, entrevista, lexico, narrador
from roleplay.servicios.narrador import MEMORIA, Narrador, limpiar
from roleplay.servicios.vision import MatchStats

SIN_EXPANDIR = r"[{}]|#\w+#"


def con_gramatica(gramatica: dict, **opciones) -> Narrador:
    escritor = Narrador(dado=random.Random(7), **opciones)
    escritor.gramatica = gramatica
    return escritor


class TestGramatica(unittest.TestCase):
    def test_expande_simbolos_y_variables(self):
        escritor = con_gramatica({"saludo": ["#hola# {nombre}, #pregunta#"], "hola": ["hola"],
                                  "pregunta": ["#como# estas?"], "como": ["como"]})
        self.assertEqual(escritor.decir("saludo", nombre="Simon"), "Hola Simon, como estas?")

    def test_una_alternativa_sin_sus_datos_no_entra(self):
        escritor = con_gramatica({"auto": ["el {modelo} de {precio}", "su auto nuevo"], "solo": ["{precio}"]})
        self.assertEqual({escritor.elegir("auto") for _ in range(10)}, {"Su auto nuevo"})
        self.assertTrue(escritor.puede("auto"))
        self.assertFalse(escritor.puede("solo"))
        self.assertEqual(escritor.decir("solo"), "")
        self.assertIn(escritor.elegir("auto", modelo="911", precio="£95.000"), ("El 911 de £95.000", "Su auto nuevo"))

    def test_un_simbolo_que_no_existe_descarta_la_alternativa(self):
        escritor = con_gramatica({"x": ["#no_existe# hola", "chao"]})
        self.assertEqual(escritor.decir("x"), "Chao")

    def test_ricas_prefiere_la_que_usa_mas_datos(self):
        escritor = con_gramatica({"origen": ["nacio en algun lado", "nacio en {ciudad}", "nacio en {ciudad} en {anio}"]},
                                 ricas=True)
        self.assertEqual(escritor.elegir("origen", ciudad="Quillota", anio="2003"), "Nacio en Quillota en 2003")
        self.assertEqual(escritor.elegir("origen", ciudad="Quillota"), "Nacio en Quillota")

    def test_limpiar(self):
        self.assertEqual(limpiar("tras perder ,  la gente . se fue  .. ¿ por que ?"), "Tras perder, la gente. Se fue. ¿Por que?")
        self.assertEqual(limpiar("« hola »"), "«Hola»")


class TestLimpiar(unittest.TestCase):
    def test_no_toca_un_usuario_al_principio(self):
        self.assertEqual(limpiar("@actriz en los comentarios. ojo"), "@actriz en los comentarios. Ojo")
        self.assertEqual(limpiar("ojo que @actriz comento"), "Ojo que @actriz comento")


class TestNoRepetir(unittest.TestCase):
    def test_no_se_repite_un_bloque_hasta_usar_los_demas(self):
        escritor = con_gramatica({"x": [f"opcion {i}" for i in range(5)]})
        self.assertEqual(len({escritor.decir("x") for _ in range(5)}), 5)

    def test_nunca_bloquea_todas(self):
        # con dos opciones se alternan: la recien usada queda bloqueada, la otra no
        escritor = con_gramatica({"x": ["a", "b"]})
        textos = [escritor.elegir("x") for _ in range(4)]
        self.assertNotEqual(textos[0], textos[1])
        self.assertEqual(textos, textos[:2] * 2)
        self.assertEqual(escritor.usados["bloques"]["x"], [1 if textos[-1] == "B" else 0])

    def test_la_cola_recuerda_hasta_40(self):
        escritor = con_gramatica({"x": [f"texto {i}" for i in range(100)]})
        vistos = [escritor.decir("x") for _ in range(100)]
        self.assertEqual(len(escritor.usados["textos"]), MEMORIA)
        self.assertEqual(len(escritor.usados["bloques"]["x"]), MEMORIA)
        for i in range(len(vistos) - MEMORIA):  # en cada ventana de 40 seguidos, ninguno repetido
            self.assertEqual(len(set(vistos[i:i + MEMORIA])), MEMORIA)

    def test_un_texto_reciente_se_vuelve_a_armar(self):
        # dos piezas de tres opciones: sin el sorteo del reintento, rotan en
        # fila y se repiten los mismos tres textos de los nueve posibles
        escritor = con_gramatica({"x": ["#a# #b#"], "a": ["uno", "dos", "tres"], "b": ["cuatro", "cinco", "seis"]})
        textos = [escritor.decir("x") for _ in range(6)]
        self.assertEqual(len(set(textos)), 6, textos)


class TestCorpus(unittest.TestCase):
    """Los archivos de roleplay/datos: que todo lo que se nombra exista."""

    def test_todos_los_simbolos_existen(self):
        for ruta in sorted(narrador.CARPETA_DATOS.glob("corpus_*.json")):
            gramatica = narrador.corpus(ruta.stem.removeprefix("corpus_"))
            for simbolo, alternativas in gramatica.items():
                self.assertIsInstance(alternativas, list, (ruta.name, simbolo))
                self.assertTrue(alternativas, (ruta.name, simbolo))
                for alternativa in alternativas:
                    for usado in re.findall(r"#(\w+)#", alternativa):
                        self.assertIn(usado, gramatica, f"{ruta.name}: {simbolo} usa #{usado}# que no existe")

    def test_sin_tildes_como_el_resto_de_la_app(self):
        for ruta in sorted(narrador.CARPETA_DATOS.glob("corpus_*.json")):
            texto = ruta.read_text(encoding="utf-8")
            self.assertFalse(re.search(r"[áéíóúñÁÉÍÓÚÑü]", texto), ruta.name)
            json.loads(texto)

    def test_el_lexico_trae_los_cinco_ejes(self):
        datos = narrador.corpus("lexico")
        self.assertEqual(set(datos["ejes"]), set(lexico.EJES))
        self.assertTrue({"no", "nunca", "jamas", "sin"} <= set(datos["negaciones"]))


class TestPersistencia(ayuda.PruebaConBase):
    def setUp(self):
        super().setUp()
        self.perfil = PlayerProfile(nombre_jugador="Simon Canales", club_actual="Man Utd")
        self.perfil.id = database.save_profile(self.perfil)

    def test_la_memoria_queda_en_estado_json(self):
        with narrador.narrador(self.perfil.id, "entrevista") as escritor:
            texto = escritor.decir("ves_generico", club="Man Utd", rival="Arsenal", apellido="Canales")
        usados = database.get_narrador_usados(self.perfil.id)
        self.assertIn(narrador.huella(texto), usados["textos"])
        self.assertTrue(usados["bloques"]["ves_generico"])
        with narrador.narrador(self.perfil.id, "entrevista") as escritor:
            self.assertTrue(escritor.reciente(texto))  # la proxima vez lo recuerda

    def test_un_perfil_que_no_existe_no_rompe_nada(self):
        with narrador.narrador(99_999, "prensa") as escritor:
            self.assertTrue(escritor.decir("c_mercado"))

    def test_dos_entrevistas_seguidas_no_repiten_preguntas(self):
        stats = MatchStats(goles_equipo=2, goles_rival=0, equipo_rival="Arsenal", goles_jugador=1, rating_jugador=7.8,
                           minutos_jugados=90)
        with mock.patch.object(entrevista, "_carrera", return_value=None):
            primera = entrevista.generar_entrevista(self.perfil, stats)
            segunda = entrevista.generar_entrevista(self.perfil, stats)
        self.assertEqual(len(primera), 3)
        for antes, despues in zip(primera, segunda):
            self.assertNotEqual(antes.split(": ", 1)[1], despues.split(": ", 1)[1])
        self.assertNotRegex(" ".join(primera + segunda), SIN_EXPANDIR)


class TestLexico(unittest.TestCase):
    def test_los_ejes(self):
        casos = {
            "Fue un triunfo de todo el equipo, mis companeros dejaron la vida": "humildad_equipo",
            "Esto es para la hinchada, la gente nos empujo todo el partido": "amor_hinchada",
            "Soy el mejor, yo solo gane el partido, soy imparable": "ego_confianza",
            "El arbitro nos robo, fue un escandalo y una injusticia": "excusa_polemica",
            "Queremos el titulo, vamos a ser campeones de la liga": "ambicion_foco",
            "Bien, seguimos": lexico.NEUTRO,
        }
        for respuesta, eje in casos.items():
            self.assertEqual(lexico.leer([respuesta]).eje, eje, respuesta)

    def test_la_negacion_invierte_el_peso(self):
        self.assertGreater(lexico.puntuar("soy el mejor")["ego_confianza"], 0)
        self.assertLess(lexico.puntuar("no soy el mejor")["ego_confianza"], 0)
        self.assertLess(lexico.puntuar("jamas hubo robo")["excusa_polemica"], 0)
        self.assertNotEqual(lexico.leer(["No soy el mejor, nunca fui un crack"]).eje, "ego_confianza")
        # solo cuentan las dos palabras de antes: mas lejos, ya no niega
        self.assertGreater(lexico.puntuar("no creo que el arbitro")["excusa_polemica"], 0)

    def test_tildes_y_mayusculas_dan_lo_mismo(self):
        self.assertEqual(lexico.puntuar("ÁRBITRO, Afición"), lexico.puntuar("arbitro, aficion"))

    def test_la_cita_es_la_frase_mas_jugosa(self):
        lectura = lexico.leer(["Si.", "La hinchada nos empujo todo el partido, esto es para ellos."])
        self.assertEqual(lectura.cita, "La hinchada nos empujo todo el partido, esto es para ellos")
        larga = lexico.leer(["La hinchada " + "y la gente de este club " * 20 + "es lo mejor."])
        self.assertLessEqual(len(larga.cita), lexico.LARGO_CITA + 3)
        self.assertTrue(larga.cita.endswith("..."))

    def test_las_promesas(self):
        self.assertIn("vamos a ganar", lexico.leer(["Gracias. Les prometo que vamos a ganar el clasico."]).promesa)
        self.assertEqual(lexico.leer(["Gracias a todos."]).promesa, "")


class TestCruces(ayuda.PruebaConBase):
    def setUp(self):
        super().setUp()
        self.pid = database.save_profile(PlayerProfile(nombre_jugador="Simon Canales", club_actual="Man Utd"))

    def _con_auto(self, precio=200_000, desde="2027-01-10"):
        database.set_economia(self.pid, {"hasta": "2027-01-16", "saldo": 0, "sueldo": f.SUELDO, "posesiones": [
            {"id": "a1", "articulo": "auto:porsche_911", "precio": precio, "desde": desde,
             "config": {"modelo": "porsche_911"}}]})

    def test_compra_cara_y_partido_flojo_es_reproche(self):
        self._con_auto()
        (primero, *_) = cruce.cruces(self.pid, rating=5.8)
        self.assertEqual(primero.tipo, "compra_mal")
        self.assertEqual(primero.datos["articulo"], "Porsche 911 Carrera")
        self.assertIn("200.000", primero.datos["precio"])
        self.assertEqual(cruce.cruces(self.pid, rating=8.5)[0].tipo, "compra_bien")

    def test_lo_barato_o_lo_viejo_no_es_noticia(self):
        self._con_auto(precio=90_000)
        self.assertEqual(cruce.cruces(self.pid, rating=5.8), [])
        self._con_auto(desde="2026-09-01")
        self.assertEqual(cruce.cruces(self.pid, rating=5.8), [])

    def test_la_pareja(self):
        database.set_estado_amor(self.pid, {"estado": "pareja", "pareja": {"nombre": "Javiera", "real": True}})
        (c,) = cruce.cruces(self.pid)
        self.assertEqual((c.tipo, c.datos["pareja"]), ("pareja_real", "Javiera"))

    def test_el_ex_club_traicionado(self):
        database.set_estado_clubes(self.pid, {"actual": "1", "clubes": {
            "1": {"nombre": "Man Utd", "carino": 50, "desde": "2026-07-01"},
            "2": {"nombre": "Arsenal", "carino": 20, "desde": "2024-07-01", "hasta": "2026-06-30", "traicion": True}}})
        tipos = [c.tipo for c in cruce.cruces(self.pid, rival="Arsenal")]
        self.assertEqual(tipos[0], "ex_club_traidor")
        self.assertNotIn("ex_club_traidor", [c.tipo for c in cruce.cruces(self.pid, rival="Liverpool")])

    def test_el_mas_jugoso_primero(self):
        self._con_auto()
        database.set_estado_amor(self.pid, {"estado": "pareja", "pareja": {"nombre": "Javiera", "real": True}})
        pesos = [c.peso for c in cruce.cruces(self.pid, rating=5.8)]
        self.assertEqual(pesos, sorted(pesos, reverse=True))

    def test_el_reproche_llega_a_la_pregunta(self):
        self._con_auto()
        perfil = database.load_profile(self.pid)
        stats = MatchStats(goles_equipo=0, goles_rival=2, equipo_rival="Arsenal", rating_jugador=5.8, minutos_jugados=90)
        with mock.patch.object(entrevista, "_carrera", return_value=None):
            preguntas = entrevista.generar_entrevista(perfil, stats)
        picante = next(p for p in preguntas if "Porsche 911 Carrera" in p)  # obligatoria: auto caro y mala nota
        self.assertTrue(picante.startswith("Rocco Salinas (El Picante): "))  # la vida privada: el polemico


class TestMemoriaDeLaEntrevista(ayuda.PruebaConBase):
    def setUp(self):
        super().setUp()
        self.perfil = PlayerProfile(nombre_jugador="Simon Canales", club_actual="Man Utd")
        self.perfil.id = database.save_profile(self.perfil)
        mock.patch.object(entrevista, "_carrera", return_value=None).start()
        self.addCleanup(mock.patch.stopall)

    def _jugado(self, rival="Everton", goles=0, rating=6.8, respuestas=(), gf=1, gc=1):
        """Guarda un partido (los primeros que se guardan son los mas viejos)."""
        database.save_match_interview(MatchInterviewRecord(
            player_id=self.perfil.id, equipo_rival=rival, goles_jugador=goles, rating_jugador=rating,
            goles_equipo=gf, goles_rival=gc, respuestas_jugador=list(respuestas), origen="manual"))

    def _preguntas(self, **stats):
        return entrevista.generar_entrevista(self.perfil, MatchStats(minutos_jugados=90, **stats))

    def test_la_sequia_que_se_corta(self):
        for rival in ("Everton", "Fulham", "Brentford"):
            self._jugado(rival)
        preguntas = self._preguntas(goles_equipo=1, goles_rival=0, equipo_rival="Leeds", goles_jugador=1, rating_jugador=7.4)
        tactica = next(p for p in preguntas if p.startswith("Ignacio Ferrada (Pizarra Tactica): "))  # la racha
        self.assertIn("3", tactica)
        self.assertRegex(tactica.lower(), r"sequia|sin gol|sin convertir|en blanco|volviste")

    def test_el_mismo_rival_de_antes(self):
        self._jugado("Liverpool", gf=2, gc=1)
        with mock.patch.object(entrevista, "OBLIGATORIO_DESDE", 6):  # (con 6 no es obligatoria: sale a veces)
            preguntas = self._preguntas(goles_equipo=0, goles_rival=0, equipo_rival="Liverpool", rating_jugador=6.9)
        self.assertTrue(any("2-1" in p for p in preguntas), preguntas)

    def test_la_caida_despues_de_una_buena_racha(self):
        for rival in ("Everton", "Fulham", "Brentford"):
            self._jugado(rival, rating=8.2)
        memoria = entrevista._memoria(MatchStats(rating_jugador=5.9, equipo_rival="Leeds"), entrevista._historial(self.perfil))
        self.assertEqual(memoria["caida"], 8.2)
        tactica = self._preguntas(goles_equipo=0, goles_rival=1, equipo_rival="Leeds", rating_jugador=5.9)[0]
        self.assertIn("5.9", tactica)

    def test_la_contradiccion_con_la_entrevista_anterior(self):
        self._jugado("Arsenal", goles=2, rating=8.5, gf=3, gc=0,
                     respuestas=["Soy el mejor de la liga, yo solo gano los partidos, soy imparable."])
        preguntas = self._preguntas(goles_equipo=0, goles_rival=3, equipo_rival="Chelsea", rating_jugador=5.5)
        self.assertTrue(any("Soy el mejor de la liga" in p for p in preguntas), preguntas)
        # si ganan, no hay contradiccion que sacarle en cara
        memoria = entrevista._memoria(MatchStats(goles_equipo=2, goles_rival=0, equipo_rival="Chelsea"),
                                      entrevista._historial(self.perfil))
        self.assertNotIn("contradiccion", memoria)

    def test_la_tabla_que_cambia(self):
        # con un 3-0 de Liverpool antes, Man Utd venia 3°: el 5-3 lo sube a 2°
        carrera = construir(f.construir_bytes(otros_partidos=[(20270110, f.LIGA, f.LIVERPOOL, f.ARSENAL, 3, 0, True)]), "x")
        stats = MatchStats(goles_equipo=5, goles_rival=3, equipo_rival="Sunderland", rating_jugador=7.0)
        self.assertEqual(entrevista._tabla(carrera, stats),
                         {"posicion": "2°", "posicion_antes": "3°", "liga": "Premier League", "sube": True})
        with mock.patch.object(entrevista, "_carrera", return_value=carrera):
            tactica = entrevista.generar_entrevista(self.perfil, stats)[0]
        self.assertIn("2°", tactica)


class TestEvaluacion(ayuda.PruebaConBase):
    def setUp(self):
        super().setUp()
        self.perfil = PlayerProfile(nombre_jugador="Simon Canales", club_actual="Man Utd", personalidad="humilde")
        self.perfil.id = database.save_profile(self.perfil)
        mock.patch.object(entrevista, "_carrera", return_value=None).start()
        self.addCleanup(mock.patch.stopall)
        self.victoria = MatchStats(goles_equipo=2, goles_rival=0, equipo_rival="Arsenal", goles_jugador=1, rating_jugador=7.8)
        self.derrota = MatchStats(goles_equipo=0, goles_rival=2, equipo_rival="Arsenal", rating_jugador=6.0)

    def _evaluar(self, stats, respuesta):
        return entrevista.evaluar_respuestas(self.perfil, stats, [("P?", respuesta)])

    def test_humildad_en_la_victoria(self):
        r = self._evaluar(self.victoria, "Fue un triunfo de todo el equipo, mis companeros dejaron la vida en la cancha.")
        self.assertEqual((r.eje, r.tono), ("humildad_equipo", "positiva"))
        self.assertTrue(0 < r.delta_reputacion <= entrevista.DELTA_REPUTACION_MAXIMO)
        self.assertGreater(r.delta_carino, 0)
        self.assertIn("todo el equipo", r.cita)
        self.assertNotRegex(r.reaccion_prensa, SIN_EXPANDIR)

    def test_ego_en_la_derrota(self):
        r = self._evaluar(self.derrota, "Yo solo soy el mejor de este equipo, soy imparable, los demas no me siguen.")
        self.assertEqual(r.eje, "ego_confianza")
        self.assertLess(r.delta_reputacion, 0)
        self.assertEqual(r.delta_carino, -3)
        self.assertEqual(r.tono, "negativa")

    def test_el_tope(self):
        excusas = "El arbitro nos robo, una injusticia, un escandalo, el arbitraje fue un robo. " * 15
        r = self._evaluar(self.derrota, excusas)
        self.assertEqual(r.delta_reputacion, -entrevista.DELTA_REPUTACION_MAXIMO)
        humilde = "El equipo, el grupo, mis companeros, entre todos, juntos, el plantel. " * 15
        r = self._evaluar(self.victoria, humilde)
        self.assertLessEqual(r.delta_reputacion, entrevista.DELTA_REPUTACION_MAXIMO)

    def test_una_promesa_queda_de_gancho(self):
        r = self._evaluar(self.victoria, "Gracias al equipo. Les prometo que vamos a ganar el clasico del domingo.")
        self.assertIn("vamos a ganar el clasico", r.nuevo_gancho_narrativo)

    def test_respuestas_secas(self):
        r = self._evaluar(self.victoria, "Bien.")
        self.assertEqual((r.eje, r.cita), (lexico.NEUTRO, ""))
        self.assertTrue(r.reaccion_prensa)


class TestBackstory(unittest.TestCase):
    def perfil(self, **cambios):
        datos = dict(nombre_jugador="Simon Canales", ciudad_natal="Quillota", fecha_nacimiento="2003-05-02",
                     contexto_socioeconomico="humilde", personalidad="carismatico", motivacion="legado",
                     anecdota_personal="Rompio la ventana del vecino con un tiro libre")
        datos.update(cambios)
        return PlayerProfile(**datos)

    def test_tres_parrafos_y_sus_ganchos(self):
        resultado = backstory.generar_backstory(self.perfil(), dado=random.Random(3))
        parrafos = resultado.backstory.split("\n\n")
        self.assertEqual(len(parrafos), 3)
        self.assertIn("Simon Canales", resultado.backstory)
        self.assertIn("Quillota", resultado.backstory)
        self.assertIn("ventana del vecino", resultado.backstory)
        self.assertTrue(3 <= len(resultado.ganchos_narrativos) <= backstory.GANCHOS)
        self.assertTrue(all(resultado.ganchos_narrativos))
        self.assertEqual(len(set(resultado.ganchos_narrativos)), len(resultado.ganchos_narrativos))
        self.assertNotRegex(resultado.backstory + " ".join(resultado.ganchos_narrativos), SIN_EXPANDIR)

    def test_la_pareja_real_se_nombra(self):
        resultado = backstory.generar_backstory(self.perfil(estado_relacion="novia_real", nombre_pareja="Javiera"),
                                                dado=random.Random(1))
        self.assertIn("Javiera", resultado.backstory)

    def test_reproducible_con_la_misma_semilla(self):
        uno = backstory.generar_backstory(self.perfil(), dado=random.Random(5))
        otro = backstory.generar_backstory(self.perfil(), dado=random.Random(5))
        self.assertEqual(uno, otro)
        distintos = {backstory.generar_backstory(self.perfil(), dado=random.Random(s)).backstory for s in range(6)}
        self.assertGreater(len(distintos), 1)

    def test_con_lo_minimo_igual_sale(self):
        resultado = backstory.generar_backstory(PlayerProfile(nombre_jugador="Simon"), dado=random.Random(2))
        self.assertTrue(resultado.backstory)
        self.assertGreaterEqual(len(resultado.ganchos_narrativos), 3)


# ---- la IA hibrida (servicios/ia.py): la red siempre mockeada ----

import os  # noqa: E402
import tempfile  # noqa: E402
import urllib.error  # noqa: E402
from pathlib import Path  # noqa: E402

from roleplay import ajustes, config  # noqa: E402
from roleplay.servicios import hinchada, ia, instagram  # noqa: E402


class _Respuesta:
    def __init__(self, datos):
        self._cuerpo = json.dumps(datos).encode("utf-8")

    def read(self):
        return self._cuerpo

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False


def _groq(contenido):
    return _Respuesta({"choices": [{"message": {"content": json.dumps(contenido)}}]})


def _gemini(contenido):
    return _Respuesta({"candidates": [{"content": {"parts": [{"text": json.dumps(contenido)}]}}]})


def _http(codigo):
    return urllib.error.HTTPError("https://x", codigo, "error", {}, None)


class ConIA(ayuda.PruebaConBase):
    """IA prendida (EAFC_SIN_IA=0), ajustes y .env en una carpeta propia y
    `self.red` en lugar de internet: lista de respuestas o excepciones, en orden."""

    def setUp(self):
        super().setUp()
        carpeta = Path(tempfile.mkdtemp(prefix="eafc_ia_"))
        for parche in (mock.patch.dict(os.environ, {"EAFC_SIN_IA": "0"}),
                       mock.patch.object(config, "ARCHIVO_AJUSTES", carpeta / "ajustes.json"),
                       mock.patch.object(config, "CARPETA_DATOS", carpeta)):
            parche.start()
            self.addCleanup(parche.stop)
        self.carpeta = carpeta
        self.red = []
        self.pedidos = []
        parche = mock.patch.object(ia.urllib.request, "urlopen", side_effect=self._urlopen)
        parche.start()
        self.addCleanup(parche.stop)

    def _urlopen(self, pedido, timeout=None):
        self.pedidos.append((pedido.full_url, json.loads(pedido.data) if pedido.data else None))
        if not self.red:
            raise AssertionError("la IA salio a la red sin que se esperara")
        respuesta = self.red.pop(0)
        if isinstance(respuesta, Exception):
            raise respuesta
        return respuesta


class TestRouterIA(ConIA):
    def test_sin_claves_no_sale_a_la_red(self):
        self.assertIsNone(ia.pedir_json("s", "u", {"ok": True}))
        self.assertEqual(self.pedidos, [])

    def test_apagada_no_sale_aunque_haya_claves(self):
        ajustes.guardar(groq_api_key="clave", sin_ia=True)
        self.assertIsNone(ia.pedir_json("s", "u", {"ok": True}))
        with mock.patch.dict(os.environ, {"EAFC_SIN_IA": "1"}):
            ajustes.guardar(sin_ia=None)
            self.assertIsNone(ia.pedir_json("s", "u", {"ok": True}))
        self.assertEqual(self.pedidos, [])

    def test_groq_con_cuota_agotada_rota_al_modelo_chico(self):
        ajustes.guardar(groq_api_key="clave")
        self.red = [_http(429), _groq({"ok": True})]
        self.assertEqual(ia.pedir_json("s", "u", {"ok": True}), {"ok": True})
        modelos = [cuerpo["model"] for _, cuerpo in self.pedidos]
        self.assertEqual(modelos, list(ia.GROQ_MODELOS[:2]))
        self.assertEqual(self.pedidos[0][1]["response_format"], {"type": "json_object"})
        self.assertEqual((ia.ultimo["proveedor"], ia.ultimo["modelo"]), ("groq", ia.GROQ_MODELOS[1]))

    def test_si_groq_dio_de_baja_los_modelos_usa_los_que_tenga(self):
        ajustes.guardar(groq_api_key="clave")
        lista = _Respuesta({"data": [{"id": "whisper-large-v3"}, {"id": "llama-guard-9"}, {"id": "llama-5-70b"},
                                     {"id": ia.GROQ_MODELOS[0]}]})
        self.red = [_http(404)] * len(ia.GROQ_MODELOS) + [lista, _groq({"ok": True})]
        self.assertEqual(ia.pedir_json("s", "u", {"ok": True}), {"ok": True})
        self.assertEqual(self.pedidos[-2][0], ia.GROQ_MODELOS_URL)
        self.assertEqual(ia.ultimo["modelo"], "llama-5-70b")  # ni whisper ni el guard ni uno ya probado

    def test_sin_groq_contesta_gemini(self):
        (self.carpeta / ".env").write_text("GROQ_API_KEYS=mala1, mala2\nGEMINI_API_KEY=buena\n", encoding="utf-8")
        self.assertEqual(ia.claves("groq"), ["mala1", "mala2"])
        self.red = [_http(401), _http(403), _http(500), _gemini({"ok": 1})]
        self.assertEqual(ia.pedir_json("s", "u", {"ok": 1}), {"ok": 1})
        urls = [url for url, _ in self.pedidos]
        self.assertTrue(all("groq" in u for u in urls[:2]))  # una clave mala no prueba el otro modelo
        self.assertIn("gemini-2.5-flash:", urls[2])
        self.assertIn("gemini-2.5-flash-lite:", urls[3])
        self.assertEqual(self.pedidos[3][1]["generationConfig"]["responseMimeType"], "application/json")

    def test_sin_internet_o_basura_cae_al_motor_local_sin_excepcion(self):
        ajustes.guardar(groq_api_key="a", gemini_api_key="b")
        self.red = [urllib.error.URLError("sin red"), _Respuesta({"choices": []}), _groq("no es un objeto"),
                    TimeoutError(), _gemini(["una lista"])]
        self.assertIsNone(ia.pedir_json("s", "u", {"ok": True}))
        self.assertEqual(len(self.pedidos), 5)

    def test_probar_dice_quien_contesto(self):
        self.assertIn("motor local", ia.probar())
        ajustes.guardar(groq_api_key="clave")
        self.red = [_groq({"ok": True})]
        self.assertIn("Groq", ia.probar())

    def test_el_estado_no_muestra_las_claves(self):
        ajustes.guardar(groq_api_key="secreta123")
        self.assertNotIn("secreta123", ia.estado())
        self.assertIn("Groq: 1 clave", ia.estado())


class TestHibrido(ConIA):
    def setUp(self):
        super().setUp()
        ajustes.guardar(groq_api_key="clave")
        self.perfil = database.load_profile(database.save_profile(PlayerProfile(
            nombre_jugador="Simon Canales", club_actual="Man Utd", personalidad="polemico")))
        self.stats = MatchStats(goles_equipo=0, goles_rival=2, equipo_rival="Arsenal", rating_jugador=5.8,
                                minutos_jugados=90)
        self.respuestas = [("P1?", "El arbitro nos robo el partido, no hay otra explicacion."),
                           ("P2?", "Yo hice lo mio, el equipo no me acompano.")]

    def test_la_reaccion_contesta_lo_que_dijo_y_queda_acotada(self):
        self.red = [_groq({"reaccion_prensa": "Canales culpo al arbitro tras el 0-2.", "delta_reputacion": 99,
                           "delta_carino": -40, "cita": "una frase que nunca dijo",
                           "nuevo_gancho_narrativo": "La prensa espera su revancha."})]
        r = entrevista.evaluar_respuestas(self.perfil, self.stats, self.respuestas)
        self.assertEqual(r.reaccion_prensa, "Canales culpo al arbitro tras el 0-2.")
        self.assertEqual(r.delta_reputacion, entrevista.DELTA_REPUTACION_MAXIMO)
        self.assertEqual(r.delta_carino, -6)
        self.assertEqual(r.tono, "positiva")
        self.assertNotIn("nunca dijo", r.cita)  # una cita inventada no vale: queda la del lexico
        self.assertIn(r.cita.lower()[:20], " ".join(t for _, t in self.respuestas).lower())
        self.assertIn("Yo hice lo mio", self.pedidos[0][1]["messages"][1]["content"])  # le llega lo que dijo

    def test_sin_respuesta_de_la_ia_queda_el_motor_local(self):
        self.red = [_http(500)] * len(ia.GROQ_MODELOS)
        r = entrevista.evaluar_respuestas(self.perfil, self.stats, self.respuestas)
        self.assertTrue(r.reaccion_prensa)
        self.assertLessEqual(abs(r.delta_reputacion), entrevista.DELTA_REPUTACION_MAXIMO)
        self.assertNotRegex(r.reaccion_prensa, SIN_EXPANDIR)

    def test_las_preguntas_mantienen_periodista_y_si_falla_quedan_las_locales(self):
        self.red = [_groq({"preguntas": ["Ignacio Ferrada (Pizarra Tactica): ¿Que paso atras?", "¿Y la hinchada?",
                                         "¿Y el auto?"]})]
        orden = iter(entrevista.PERIODISTAS)  # (el orden fijo, solo para esta prueba)
        with mock.patch.object(entrevista, "periodista_para", side_effect=lambda *_: next(orden)):
            preguntas = entrevista.generar_entrevista(self.perfil, self.stats)
        self.assertEqual(preguntas[0], "Ignacio Ferrada (Pizarra Tactica): ¿Que paso atras?")  # sin el nombre repetido
        self.assertTrue(preguntas[2].startswith("Rocco Salinas (El Picante): "))
        self.assertIn("tema:", self.pedidos[0][1]["messages"][1]["content"])  # la IA sabe de que tema es cada una
        self.red = [_groq({"preguntas": ["solo una"]})]  # no calza: las del motor local
        locales = entrevista.generar_entrevista(self.perfil, self.stats)
        self.assertEqual(len(locales), 3)
        self.assertNotIn("solo una", " ".join(locales))

    def test_comentarios_del_post_y_de_la_hinchada(self):
        self.red = [_groq({"comentarios": [{"autor": "hincha_red", "texto": "Ese reloj no ataja penales", "tono": "gracioso"},
                                           {"autor": "@rival", "texto": "Juga y despues presumi", "tono": "negativo"},
                                           {"autor": "@meme", "texto": "jajaja", "tono": "inventado"}]})]
        r = instagram.generar_reaccion_post(self.perfil, "Mi reloj nuevo", 50, 1000)
        self.assertEqual([c.autor for c in r.comentarios], ["@hincha_red", "@rival", "@meme"])
        self.assertEqual(r.comentarios[2].tono, "neutral")
        self.assertIn("Mi reloj nuevo", self.pedidos[0][1]["messages"][1]["content"])

        eventos = [hinchada.EventoHinchada("partido", "2026-01-01", "0-2 vs Arsenal", "Perdio 0-2.", -30),
                   hinchada.EventoHinchada("noticia", "2026-01-01", "Polemica", "...", -10)]
        self.red = [_groq({"eventos": [{"indice": 0, "comentarios": [
            {"autor": "@a", "texto": "Ese 0-2 duele", "tono": "negativo"},
            {"autor": "@b", "texto": "Vamos igual", "tono": "positivo"}]}]})]
        dichos = hinchada.comentar_eventos(self.perfil, eventos)
        self.assertEqual(dichos[0][0]["texto"], "Ese 0-2 duele")
        self.assertTrue(dichos[1])  # el que la IA no comento sale del motor local


class TestAjustesIA(ayuda.PruebaDeInterfaz):
    def setUp(self):
        super().setUp()
        parche = mock.patch.object(config, "ARCHIVO_AJUSTES", config.DB_PATH.parent / "ajustes.json")
        parche.start()
        self.addCleanup(parche.stop)

    def test_guarda_claves_y_modo_local_y_prueba(self):
        from roleplay.ui.ajustes import DialogoAjustes

        dialogo = DialogoAjustes()
        dialogo.groq_edit.setText(" gsk_prueba ")
        dialogo.groq_edit.editingFinished.emit()
        dialogo.sin_ia_check.setChecked(True)
        self.assertEqual(ajustes.leer().get("groq_api_key"), "gsk_prueba")
        self.assertTrue(ajustes.leer().get("sin_ia"))
        with mock.patch.object(ia, "probar", return_value="Respondio Groq en 300 ms."):
            dialogo.probar_btn.click()
            ayuda.esperar_tareas()
        self.assertIn("300 ms", dialogo.prueba_label.text())
        dialogo.sin_ia_check.setChecked(False)
        self.assertNotIn("sin_ia", ajustes.leer())
        dialogo.deleteLater()


if __name__ == "__main__":
    unittest.main()
