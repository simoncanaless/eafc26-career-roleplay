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
