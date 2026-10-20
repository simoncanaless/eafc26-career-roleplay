"""Los hinchas reaccionan una vez a cada cosa (Simon: "Canales cerro sus primas" salia dos veces)."""

import unittest
from datetime import date

import ayuda  # noqa: F401
import fabrica_partida as f
from roleplay.models import NoticiaPrensa
from roleplay.partida.carrera import construir
from roleplay.servicios import clubes, hinchada, patrocinios


class TestUnaReaccion(unittest.TestCase):
    def test_las_noticias_que_ya_traen_reaccion_no_se_repiten(self):
        carrera = construir(f.construir_bytes())
        noticias = [
            NoticiaPrensa(id=3, player_id=1, categoria="jugador", tono="positiva", titular="Canales cerro sus primas",
                          cuerpo="x", hitos=["contrato:firma"]),
            NoticiaPrensa(id=2, player_id=1, categoria="jugador", tono="positiva", titular="Firma con Zuko",
                          cuerpo="x", hitos=["patrocinio:firma:bebida"]),
            NoticiaPrensa(id=1, player_id=1, categoria="jugador", tono="positiva", titular="Canales ya lleva 25 goles",
                          cuerpo="x", hitos=["goles_temporada:25"]),
        ]
        eventos, estado = hinchada.eventos_nuevos(carrera, noticias, {"noticia": 0, "hasta": "2099-01-01"}, 100_000, 70)
        self.assertEqual([e.titulo for e in eventos], ["Canales ya lleva 25 goles"])  # solo la de la prensa
        self.assertEqual(estado["noticia"], 3)  # igual se marcan como vistas

    def test_la_decision_de_la_hinchada_dice_lo_que_paso(self):
        estado = {"actual": "11", "clubes": {"11": {"nombre": "Man Utd", "carino": 90}},
                  "decision": {"tipo": "tentado", "club": "11", "fecha": "2027-01-01"}}
        _, hito, _ = clubes.elegir(estado, "escuchar", date(2027, 1, 2))
        self.assertNotEqual(hito.titulo, "Escuchar la oferta, sin compromiso")
        self.assertIn("Man Utd", hito.titulo)

    def test_las_marcas_con_su_nombre_de_hoy(self):
        e = {"patrocinios": {"contratos": [{"id": "x", "marca": "bebida", "nombre": "una bebida isotonica",
                                            "rubro": "bebidas", "semanal": 100, "desde": "2027-01-01",
                                            "hasta": "2027-01-10"}]}}
        _, novedades = patrocinios.revisar(e, 1, 1000, 70, date(2027, 2, 1))
        self.assertIn("Zuko", novedades[0].titulo)
        self.assertNotIn("isotonica", novedades[0].detalle)


if __name__ == "__main__":
    unittest.main()
