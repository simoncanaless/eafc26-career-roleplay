import sqlite3
import unittest

import ayuda
from roleplay import config, database
from roleplay.models import InstagramPost, MatchInterviewRecord, NoticiaPrensa, PlayerProfile


class TestDatabase(ayuda.PruebaConBase):
    def _perfil(self, **campos) -> int:
        return database.save_profile(PlayerProfile(nombre_jugador="Simon", **campos))

    def test_cada_modelo_vuelve_igual_de_la_base(self):
        perfil = PlayerProfile(
            nombre_jugador="Simon Canales",
            ganchos_narrativos=["comprarle una casa a la mama", "rivalidad con el 9 titular"],
            estado_json={"reputacion_actual": 61, "prensa": {"x": 1}},
            club_actual="Union, La Calera",
            reputacion_inicial=65,
        )
        perfil.id = database.save_profile(perfil)
        self.assertEqual(database.load_profile(perfil.id), perfil)

        partido = MatchInterviewRecord(
            player_id=perfil.id,
            goles_jugador=2,
            rating_jugador=8.7,
            tarjeta_roja=True,
            preguntas_entrevista=["P1", "P2"],
            respuestas_jugador=["R1", ""],
            delta_reputacion=-3,
        )
        partido.id = database.save_match_interview(partido)
        self.assertEqual(database.load_match_interviews(perfil.id), [partido])

        noticia = NoticiaPrensa(player_id=perfil.id, titular="T", hitos=["racha_goleadora:5"])
        noticia.id = database.save_noticia_prensa(noticia)
        self.assertEqual(database.load_noticias_prensa(perfil.id), [noticia])

        post = InstagramPost(
            player_id=perfil.id, texto="vamos <3", likes=10,
            comentarios=[{"autor": "fan", "texto": "crack", "tono": "positivo"}],
        )
        post.id = database.save_instagram_post(post)
        self.assertEqual(database.load_instagram_posts(perfil.id), [post])

    def test_lo_que_viene_null_toma_el_valor_por_defecto(self):
        with database.conectar() as conn:
            conn.execute("INSERT INTO player_profile (nombre_jugador) VALUES ('Viejo')")
        perfil = database.load_latest_profile()
        self.assertEqual(perfil.ganchos_narrativos, [])
        self.assertEqual(perfil.estado_json, {})
        self.assertEqual(perfil.reputacion_inicial, 50)
        self.assertEqual(perfil.club_actual, "")

    def test_una_base_vieja_sin_club_actual_se_migra_sin_perder_datos(self):
        config.DB_PATH.unlink()
        conn = sqlite3.connect(config.DB_PATH)
        conn.execute(
            "CREATE TABLE player_profile (id INTEGER PRIMARY KEY AUTOINCREMENT, "
            "nombre_jugador TEXT NOT NULL, estado_json TEXT, reputacion_inicial INTEGER)"
        )
        conn.execute("INSERT INTO player_profile (nombre_jugador, reputacion_inicial) VALUES ('Simon', 40)")
        conn.commit()
        conn.close()

        database.init_db()
        perfil = database.load_latest_profile()
        self.assertEqual((perfil.nombre_jugador, perfil.reputacion_inicial, perfil.club_actual), ("Simon", 40, ""))
        database.actualizar_club(perfil.id, "Palermo")
        self.assertEqual(database.load_profile(perfil.id).club_actual, "Palermo")

    def test_la_tabla_de_partidos_de_la_primera_version_se_completa(self):
        # la base real de Simon: partido_entrevista sin respuestas, reaccion ni delta
        # (guardar una entrevista daba "has no column named respuestas_jugador")
        pid = self._perfil()
        with database.conectar() as conn:
            conn.execute("DROP TABLE partido_entrevista")
            conn.execute(
                "CREATE TABLE partido_entrevista (id INTEGER PRIMARY KEY AUTOINCREMENT, player_id INTEGER NOT NULL, "
                "fecha TEXT, goles_equipo INTEGER, goles_rival INTEGER, equipo_rival TEXT, goles_jugador INTEGER, "
                "asistencias_jugador INTEGER, rating_jugador REAL, minutos_jugados INTEGER, tarjeta_amarilla INTEGER, "
                "tarjeta_roja INTEGER, hombre_del_partido INTEGER, preguntas_entrevista TEXT)"
            )
        database.init_db()
        registro = MatchInterviewRecord(player_id=pid, equipo_rival="Arsenal", preguntas_entrevista=["P?"],
                                        respuestas_jugador=["R"], reaccion_prensa="Bien", delta_reputacion=4,
                                        origen="partida", fecha_juego="2027-01-16")
        registro.id = database.save_match_interview(registro)
        self.assertEqual(database.load_match_interviews(pid), [registro])
        database.init_db()  # otra vez: no agrega nada de nuevo ni falla

    def test_la_reputacion_parte_de_la_inicial_se_acota_y_deja_historial(self):
        pid = self._perfil(reputacion_inicial=40)
        self.assertEqual(database.get_reputacion_actual(pid), 40)
        self.assertEqual(database.aplicar_delta_reputacion(pid, 10, "buena entrevista"), 50)
        self.assertEqual(database.aplicar_delta_reputacion(pid, 500, "exagerado"), 100)
        self.assertEqual(database.aplicar_delta_reputacion(pid, -500, "polemica"), 0)
        historial = database.load_profile(pid).estado_json["historial_reputacion"]
        self.assertEqual([h["reputacion_resultante"] for h in historial], [50, 100, 0])
        self.assertTrue(all("fecha" in h for h in historial))

    def test_seguidores_parten_de_una_base_y_nunca_bajan_de_cero(self):
        pid = self._perfil(reputacion_inicial=40)
        self.assertEqual(database.get_seguidores(pid), 200)  # 40 * 5
        self.assertEqual(database.sumar_seguidores(pid, 55), 255)
        self.assertEqual(database.sumar_seguidores(pid, -1000), 0)
        self.assertEqual(database.get_seguidores(pid), 0)

    def test_cada_modulo_escribe_su_clave_sin_pisar_las_otras(self):
        pid = self._perfil()
        database.aplicar_delta_reputacion(pid, 5, "x")
        database.sumar_seguidores(pid, 7)
        database.set_estado_prensa(pid, {"goles_totales_max_reportado": 5})
        estado = database.load_profile(pid).estado_json
        self.assertEqual(estado["reputacion_actual"], 55)
        self.assertEqual(estado["seguidores_instagram"], 257)
        self.assertEqual(database.get_estado_prensa(pid), {"goles_totales_max_reportado": 5})

    def test_un_gancho_no_se_repite(self):
        pid = self._perfil(ganchos_narrativos=["uno"])
        database.agregar_gancho_narrativo(pid, "dos")
        database.agregar_gancho_narrativo(pid, "  dos ")
        database.agregar_gancho_narrativo(pid, "")
        self.assertEqual(database.load_profile(pid).ganchos_narrativos, ["uno", "dos"])

    def test_los_registros_vienen_del_mas_nuevo_al_mas_viejo_y_respetan_el_limite(self):
        pid = self._perfil()
        for i in range(5):
            database.save_noticia_prensa(NoticiaPrensa(player_id=pid, titular=f"N{i}"))
        self.assertEqual([n.titular for n in database.load_noticias_prensa(pid, limite=3)], ["N4", "N3", "N2"])
        self.assertEqual(len(database.load_noticias_prensa(pid)), 5)

    def test_perfil_inexistente(self):
        self.assertIsNone(database.load_latest_profile())
        self.assertEqual(database.get_reputacion_actual(99), 50)
        self.assertEqual(database.get_estado_prensa(99), {})
        with self.assertRaises(ValueError):
            database.aplicar_delta_reputacion(99, 1, "x")


if __name__ == "__main__":
    unittest.main()
