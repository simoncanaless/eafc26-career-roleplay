"""La memoria del roleplay para la IA y la guardia de hechos (numeros inventados)."""

import unittest
from unittest import mock

import ayuda
from roleplay import database
from roleplay.models import MatchInterviewRecord, NoticiaPrensa, PlayerProfile
from roleplay.servicios import ia, memoria


class TestCronica(ayuda.PruebaConBase):
    def setUp(self):
        super().setUp()
        self.perfil = PlayerProfile(nombre_jugador="Simon Canales", club_actual="Man Utd", personalidad="polemico",
                                    motivacion="mejor_del_mundo", backstory_generado="Nacio en La Cruz.",
                                    ganchos_narrativos=["Prometio llegar a la final de la Champions"])
        self.perfil.id = database.save_profile(self.perfil)

    def test_junta_quien_es_lo_que_dijo_y_lo_que_le_paso(self):
        database.save_match_interview(MatchInterviewRecord(
            player_id=self.perfil.id, goles_equipo=6, goles_rival=4, equipo_rival="Villarreal CF", goles_jugador=5,
            rating_jugador=10.0, origen="partida"))
        database.save_noticia_prensa(NoticiaPrensa(player_id=self.perfil.id, titular="Canales hace cinco"))
        memoria.anotar_dichos(self.perfil.id, "previa", "Stoke City", ["Jugar como siempre nada mas."])
        texto = memoria.cronica(self.perfil.id)
        for esperado in ("personalidad polemico, lo mueve mejor del mundo", "Nacio en La Cruz",
                         "6-4 vs Villarreal CF (5 goles suyos", "antes de jugar con Stoke City: «Jugar como siempre",
                         "Prometio llegar a la final", "- Canales hace cinco"):
            self.assertIn(esperado, texto)

    def test_los_dichos_quedan_aunque_se_arme_otra_conferencia(self):
        memoria.anotar_dichos(self.perfil.id, "post", "Arsenal", ["Ganamos bien."])
        database.set_memoria_conferencias(self.perfil.id, {**database.get_memoria_conferencias(self.perfil.id),
                                                           "preguntas": ["x"]})
        self.assertEqual(database.get_memoria_conferencias(self.perfil.id)["dichos"][0]["rival"], "Arsenal")

    def test_sin_perfil_no_hay_memoria(self):
        self.assertEqual(memoria.cronica(None), "")
        self.assertEqual(memoria.cronica(9999), "")


class TestGuardiaDeHechos(unittest.TestCase):
    def test_un_texto_con_un_numero_que_no_se_le_paso_queda_vacio(self):
        permitidos = ia._numeros_de("Man Utd 7-0 Stoke City, nota 8.4, 1.888.150 seguidores")
        respuesta = {"titular": "Golea 7-0", "cuerpo": "Ya lleva 25 goles", "lista": [{"texto": "8.4 de nota"}],
                     "seguidores": "1888150", "delta": 3}
        limpia = ia._sin_numeros_inventados(respuesta, permitidos)
        self.assertEqual(limpia["titular"], "Golea 7-0")
        self.assertEqual(limpia["cuerpo"], "")  # 25: inventado
        self.assertEqual(limpia["lista"][0]["texto"], "8.4 de nota")
        self.assertEqual(limpia["seguidores"], "1888150")
        self.assertEqual(limpia["delta"], 3)  # los numeros sueltos los acota el que llama

    def test_nombres_lugares_y_hechos_inventados(self):
        # 2026-10-23, Simon: "Old Trafford" en un partido de visitante, "la sensacion del entrenamiento",
        # "el uruguayo de La Cruz" (es chileno)
        fuente = ia.preparar_fuente("Partido: Manchester City 1-3 Man Utd (Premier League). Man Utd jugo de "
                                    "visitante. Simon Canales, de La Cruz, raices chilenas, marco 3 goles.")
        self.assertEqual(ia.nombres_inventados("Canales enciende el Old Trafford contra el City", fuente), ["trafford"])
        self.assertTrue(ia.nombres_inventados("Canales es la sensacion del entrenamiento", fuente))
        self.assertTrue(ia.nombres_inventados("el uruguayo de La Cruz no perdona", fuente))
        for bien in ("Tres goles en cancha del City, los Red Devils festejan", "¡Que noche de Canales!",
                     "el chileno no perdona", "Vamos United 🔥"):
            self.assertEqual(ia.nombres_inventados(bien, fuente), [], bien)
        respuesta = {"comentarios": [{"autor": "@Old_Trafford_Fan", "texto": "Canales en Anfield, increible", "tono": "positivo"}]}
        limpia = ia._sin_numeros_inventados(respuesta, set(), fuente)
        self.assertEqual(limpia["comentarios"][0]["texto"], "")  # Anfield no esta en el pedido
        self.assertEqual(limpia["comentarios"][0]["autor"], "@Old_Trafford_Fan")  # el @ inventado no se revisa

    def test_el_pedido_lleva_la_memoria_y_la_voz(self):
        visto = {}

        def llamar(clave, modelo, sistema, usuario, timeout):
            visto.update(sistema=sistema, usuario=usuario)
            return {"texto": "Le contesto al toque, como la semana pasada."}

        with mock.patch.object(ia, "desactivada", return_value=False), \
                mock.patch.object(ia, "claves", side_effect=lambda p: ["k"] if p == "groq" else []), \
                mock.patch.object(ia, "PROVEEDORES", (("groq", ("m",), llamar),)), \
                mock.patch("roleplay.servicios.memoria.cronica", return_value="Dijo: «vamos por la final»"):
            datos = ia.pedir_json("Sos la prensa.", "Lo de hoy.", {"texto": "..."}, jugador=7)
        self.assertEqual(datos["texto"], "Le contesto al toque, como la semana pasada.")
        self.assertIn("MEMORIA DEL ROLEPLAY", visto["usuario"])
        self.assertIn("vamos por la final", visto["usuario"])
        self.assertIn("roleplay VIVO", visto["sistema"])



class TestLaIAEnLoQueEraGuion(ayuda.PruebaConBase):
    def setUp(self):
        super().setUp()
        self.perfil = PlayerProfile(nombre_jugador="Simon Canales", club_actual="Man Utd")
        self.perfil.id = database.save_profile(self.perfil)

    def test_la_prensa_cuenta_las_notas_con_su_voz_y_la_de_la_entrevista_no_se_toca(self):
        from roleplay.servicios import prensa

        notas = [NoticiaPrensa(titular="Canales llega a 20 goles", cuerpo="Hizo 20 goles.", hitos=["goles:20"]),
                 NoticiaPrensa(titular="La cita", cuerpo="Dijo algo.", hitos=["entrevista:3"])]
        respuesta = {"notas": [{"indice": 0, "titular": "Veinte y contando", "cuerpo": "Canales ya suma 20."},
                               {"indice": 1, "titular": "No", "cuerpo": "No."}]}
        with mock.patch.object(ia, "pedir_json", return_value=respuesta) as pedir:
            nuevas = prensa.reescribir_con_ia(self.perfil, notas)
        self.assertEqual((nuevas[0].titular, nuevas[0].hitos), ("Veinte y contando", ["goles:20"]))
        self.assertEqual(nuevas[1].titular, "La cita")
        self.assertEqual(pedir.call_args.kwargs["jugador"], self.perfil.id)
        with mock.patch.object(ia, "pedir_json", return_value=None):  # sin IA: las del motor
            self.assertEqual(prensa.reescribir_con_ia(self.perfil, notas), notas)

    def test_la_directiva_habla_con_su_voz(self):
        from roleplay.servicios import contratos

        with mock.patch.object(ia, "pedir_json", return_value={"frase": "Aca nadie es mas grande que el club."}):
            self.assertEqual(contratos.frase_con_ia(self.perfil.id, "Man Utd", "neg_ofendida", 4),
                             ("Aca nadie es mas grande que el club.", 4))
        self.assertEqual(contratos.frase_con_ia(self.perfil.id, "Man Utd", "neg_inventado", 1), ("", 1))


if __name__ == "__main__":
    unittest.main()
