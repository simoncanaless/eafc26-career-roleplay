import os
import unittest
from unittest import mock

from google.genai import errors
from pydantic import BaseModel

import ayuda  # noqa: F401 - prepara el entorno de prueba
from roleplay import gemini


def error(codigo: int):
    clase = errors.ServerError if codigo >= 500 else errors.ClientError
    return clase(codigo, {"error": {"code": codigo, "message": "x", "status": "X"}})


class Respuesta:
    def __init__(self, texto):
        self.text = texto


class ClientesFalsos:
    """Un cliente falso por key. `respuestas[(key, modelo)]` es lo que
    devuelve (o la excepcion que lanza) cada combinacion; anota el orden."""

    def __init__(self, respuestas):
        self.respuestas = respuestas
        self.llamadas = []

    def __call__(self, key):
        clientes = self

        class Modelos:
            def generate_content(self, model, contents, config):
                clientes.llamadas.append((key, model))
                resultado = clientes.respuestas.get((key, model), error(503))
                if isinstance(resultado, Exception):
                    raise resultado
                return resultado

        cliente = mock.Mock()
        cliente.models = Modelos()
        return cliente


class TestFallback(unittest.TestCase):
    def _correr(self, respuestas, keys="k1,k2"):
        falsos = ClientesFalsos(respuestas)
        # GEMINI_API_KEY vacia: que no se cuele la key real del .env
        with mock.patch.dict(os.environ, {"GEMINI_API_KEYS": keys, "GEMINI_API_KEY": ""}), \
                mock.patch.object(gemini, "_cliente", falsos):
            try:
                return gemini.generate_content_with_fallback("hola", None, models=["m1", "m2"]), falsos.llamadas
            except Exception as exc:  # noqa: BLE001
                return exc, falsos.llamadas

    def test_429_prueba_el_otro_modelo_con_la_misma_key(self):
        resultado, llamadas = self._correr({("k1", "m1"): error(429), ("k1", "m2"): Respuesta("ok")})
        self.assertEqual(resultado.text, "ok")
        self.assertEqual(llamadas, [("k1", "m1"), ("k1", "m2")])

    def test_401_salta_directo_a_la_siguiente_key(self):
        resultado, llamadas = self._correr({("k1", "m1"): error(401), ("k2", "m1"): Respuesta("ok")})
        self.assertEqual(resultado.text, "ok")
        self.assertEqual(llamadas, [("k1", "m1"), ("k2", "m1")])

    def test_503_prueba_el_siguiente_modelo(self):
        resultado, llamadas = self._correr({("k1", "m2"): Respuesta("ok")})
        self.assertEqual(llamadas, [("k1", "m1"), ("k1", "m2")])

    def test_400_falla_de_inmediato(self):
        resultado, llamadas = self._correr({("k1", "m1"): error(400)})
        self.assertIsInstance(resultado, errors.ClientError)
        self.assertEqual(llamadas, [("k1", "m1")])

    def test_si_todo_falla_avisa_con_runtime_error(self):
        resultado, llamadas = self._correr({})
        self.assertIsInstance(resultado, RuntimeError)
        self.assertEqual(len(llamadas), 4)

    def test_sin_keys(self):
        resultado, _ = self._correr({}, keys="")
        self.assertIsInstance(resultado, gemini.FaltaApiKey)

    def test_lista_de_keys(self):
        with mock.patch.dict(os.environ, {"GEMINI_API_KEYS": " a, b;c  d "}):
            self.assertEqual(gemini.get_gemini_api_keys(), ["a", "b", "c", "d"])
        with mock.patch.dict(os.environ, {"GEMINI_API_KEYS": "", "GEMINI_API_KEY": "unica"}):
            self.assertEqual(gemini.get_gemini_api_keys(), ["unica"])

    def test_el_sdk_no_reintenta_la_cuota(self):
        self.assertNotIn(429, gemini.REINTENTOS_SERVIDOR["http_status_codes"])


class Esquema(BaseModel):
    titular: str


class TestGenerarJson(unittest.TestCase):
    QUE_HACER = "Apreta 'Probar' de nuevo."

    def _generar(self, efecto):
        with mock.patch.object(gemini, "generate_content_with_fallback", side_effect=efecto):
            return gemini.generar_json("prompt", Esquema, self.QUE_HACER)

    def test_devuelve_el_esquema_validado(self):
        self.assertEqual(self._generar([Respuesta('{"titular": "Hola"}')]), Esquema(titular="Hola"))

    def test_formato_inesperado_dice_que_hacer(self):
        with self.assertRaises(RuntimeError) as ctx:
            self._generar([Respuesta('{"otra_cosa": 1}')])
        self.assertIn(self.QUE_HACER, str(ctx.exception))

    def test_gemini_caido_dice_que_hacer(self):
        with self.assertRaises(RuntimeError) as ctx:
            self._generar(RuntimeError("Gemini esta rechazando los pedidos."))
        self.assertTrue(str(ctx.exception).endswith(self.QUE_HACER))

    def test_sin_key_no_dice_que_reintentes(self):
        with self.assertRaises(gemini.FaltaApiKey) as ctx:
            self._generar(gemini.FaltaApiKey("Falta GEMINI_API_KEY."))
        self.assertNotIn(self.QUE_HACER, str(ctx.exception))

    def test_la_imagen_viaja_junto_al_prompt(self):
        with mock.patch.object(
            gemini, "generate_content_with_fallback", return_value=Respuesta('{"titular": "x"}')
        ) as llamada:
            gemini.generar_json("prompt", Esquema, self.QUE_HACER, imagen_png=b"\x89PNG")
        contenido = llamada.call_args.args[0]
        self.assertEqual(contenido[0], "prompt")
        self.assertEqual(contenido[1].inline_data.mime_type, "image/png")


if __name__ == "__main__":
    unittest.main()
