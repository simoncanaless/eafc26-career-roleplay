"""Instagram vivo: el feed global de las paginas de futbol y los comentarios
(y likes verificados) de colegas y celebridades en los posts del jugador."""

import random
import unittest
from unittest import mock

import ayuda  # noqa: F401  (antes que todo: arma el entorno de las pruebas)
import fabrica_partida as f
from datos_ecosistema import CELEBRIDADES, ConEcosistema
from roleplay import database
from roleplay.partida.carrera import construir
from roleplay.servicios import feed, hinchada, instagram


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


    def test_las_paginas_hablan_en_tercera_persona_y_una_cita_no_va_a_la_de_chismes(self):
        # Simon, 2026-10-21: "@goalglobal ... 3 goles tuyos" y @tmz_tv publicando una cita de conferencia
        eventos = [hinchada.EventoHinchada("partido", "2027-03-03", "Ipswich 0-4 Man Utd · 3 goles tuyos", "", 500,
                                           "Ipswich 0-4 Man Utd · 3 goles de Canales"),
                   hinchada.EventoHinchada("noticia", "2027-03-03", "«Todos asumimos nuestra culpa», promete Canales",
                                           "Noticia sobre el (positiva): ... Dijo que su pareja lo banca.", 100)]
        carrera = construir(f.construir_bytes())
        with mock.patch.object(feed, "PROBABILIDAD_POST", 1.0), mock.patch.object(feed, "PROBABILIDAD_RUMOR", 0.0):
            posts = feed.actualizar(self.perfil, eventos, [], 1_000_000, 90, carrera)
        self.assertEqual(len(posts), 2)
        for post in posts:
            self.assertNotIn("tuyo", post["texto"])
            self.assertNotEqual(post["usuario_ig"], "@chismes")
        self.assertTrue(any("3 goles de Canales" in p["texto"] for p in posts))

class TestComentariosDelAmbiente(ConEcosistema):
    def test_colegas_famosas_y_likes_verificados(self):
        tonos, autores = set(), set()
        for semilla in range(12):
            for c in instagram.comentarios_del_ambiente(self.perfil, 99, {}, random.Random(semilla)):
                tonos.add(c["tono"])
                autores.add(c["autor"])
                self.assertNotRegex(c["texto"], r"[{}]|#\w+#")
        self.assertIn("@colega", autores)  # fama 99 supera lo que pide para comentar
        self.assertIn("like", tonos)  # likes verificados
        self.assertFalse(instagram.comentarios_del_ambiente(self.perfil, 10, {}, random.Random(1))
                         and any(c["autor"] == "@colega" for c in
                                 instagram.comentarios_del_ambiente(self.perfil, 10, {}, random.Random(1))))

    def test_la_pareja_secreta_deja_un_guino_y_los_hinchas_lo_notan(self):
        estado = {"estado": "secreto", "pareja": {"nombre": "Actriz Conocida", "usuario_ig": "@actriz"}}
        dichos = instagram.comentarios_del_ambiente(self.perfil, 70, estado, random.Random(2))
        guino = next(c for c in dichos if c["autor"] == "@actriz")
        self.assertLessEqual(len(guino["texto"]), 4)  # un emoji, nada mas
        self.assertTrue(any("@actriz" in c["texto"] for c in dichos))  # "ojo que @actriz..."

    def test_solo_comentan_famosos_del_deporte(self):
        """Una cantante o una actriz sin relacion con el futbol no aparece en sus posts (si un deportista)."""
        from roleplay.servicios import ecosistema

        deportista = {"nombre": "Tenista Top", "usuario_ig": "@tenista", "categoria": "deportista", "exigencia": 10}
        with mock.patch.object(ecosistema, "celebridades", return_value=CELEBRIDADES + [deportista]):
            autores = {c["autor"] for semilla in range(40)
                       for c in instagram.comentarios_del_ambiente(self.perfil, 99, {}, random.Random(semilla))}
        self.assertIn("@tenista", autores)
        self.assertFalse(autores & {c["usuario_ig"] for c in CELEBRIDADES})

    def test_el_post_con_la_pareja(self):
        texto = instagram.post_con_pareja(self.perfil, "Actriz Conocida")
        self.assertIn("Actriz Conocida", texto)
        self.assertIn("Actriz Conocida", instagram.post_con_pareja(self.perfil, "Actriz Conocida", boda=True))
        comun = instagram.generar_reaccion_post(self.perfil, texto, 70, 100_000)
        with mock.patch.object(instagram, "generar_reaccion_post", return_value=comun.model_copy(deep=True)):
            famosa = instagram.reaccion_post_con_pareja(self.perfil, texto, 70, 100_000, famosa=True)
        self.assertEqual(famosa.crecimiento_seguidores, round(abs(comun.crecimiento_seguidores) * 4))


if __name__ == "__main__":
    unittest.main()


class TestVocesConLosDatosReales(ConEcosistema):
    """2026-10-24 (pedido de Simon): las cuentas verificadas que elige el codigo van en los datos de la IA (y el
    validador las deja pasar), cada una con su registro; una cuenta real que no se eligio, se descarta."""

    def test_el_colega_habla_con_su_voz_y_una_cuenta_real_inventada_se_descarta(self):
        from roleplay.servicios import ia

        ambiente = [{"autor": "@colega", "texto": "texto del corpus", "tono": "positivo"}]
        respuesta = [{"autor": "@colega", "texto": "Maquina 🔥", "tono": "positivo"},
                     {"autor": "@estrella", "texto": "Te amo", "tono": "positivo"},  # real, no elegida
                     {"autor": "@hincha_1", "texto": "Seguimos!", "tono": "positivo"},
                     {"autor": "@hincha_2", "texto": "Vamos", "tono": "gracioso"}]
        with mock.patch.object(instagram, "comentarios_del_ambiente", return_value=ambiente), \
                mock.patch.object(instagram, "_comentarios_con_ia", return_value=respuesta) as pedido:
            reaccion = instagram.generar_reaccion_post(self.perfil, "Seguimos", 60, 10_000)
        self.assertEqual(pedido.call_args.args[4], ("@colega",))  # el codigo eligio quien comenta
        textos = {c.autor: c.texto for c in reaccion.comentarios}
        self.assertEqual(textos["@colega"], "Maquina 🔥")
        self.assertNotIn("@estrella", textos)
        self.assertIn("@hincha_1", textos)

    def test_el_validador_acepta_las_cuentas_que_van_en_los_datos(self):
        from roleplay.servicios import ia

        fuente = ia.preparar_fuente("Cuentas verificadas que comentan este post: @colega (Colega Top)")
        self.assertEqual(ia.nombres_inventados("Grande Colega Top, que golazo", fuente), [])
        self.assertTrue(ia.nombres_inventados("Grande Lionel, que golazo", fuente))

    def test_cada_pagina_con_su_formato_y_los_hechos_iguales(self):
        from roleplay.servicios import ia

        posts = [{"pagina": "433", "usuario_ig": "@433", "tipo": "viral", "texto": "Canales: 3 goles al City", "likes": 1},
                 {"pagina": "Mercado", "usuario_ig": "@mercado", "tipo": "rumor", "texto": "Arsenal mira a Canales", "likes": 1}]
        with mock.patch.object(ia, "pedir_json", return_value={"posts": [
                {"indice": 0, "texto": "3 goles al City 🔥 ¿Es el mejor del momento?"},
                {"indice": 1, "texto": ""}]}) as pedido:
            nuevos = feed.con_formato_de_cada_pagina(self.perfil, posts)
        self.assertIn("pregunta abierta", pedido.call_args.args[1])  # el formato de @433
        self.assertEqual(nuevos[0]["texto"], "3 goles al City 🔥 ¿Es el mejor del momento?")
        self.assertEqual(nuevos[1]["texto"], "Arsenal mira a Canales")  # vacio (guardia): queda el de base
