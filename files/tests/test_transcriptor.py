"""La voz con Whisper (como el Transcriptor de clases): local -> Groq -> Windows. Nunca el modelo ni la red de verdad."""

import io
import json
import os
import unittest
import urllib.error
import wave
from unittest import mock

import ayuda  # noqa: F401  (EAFC_SIN_WHISPER=1, EAFC_SIN_IA=1)
import numpy as np

from roleplay.servicios import audio, ia, transcriptor


def wav_de(muestras: np.ndarray) -> bytes:
    salida = io.BytesIO()
    with wave.open(salida, "wb") as archivo:
        archivo.setnchannels(1)
        archivo.setsampwidth(2)
        archivo.setframerate(16000)
        archivo.writeframes((muestras * 32767).astype(np.int16).tobytes())
    return salida.getvalue()


WAV = wav_de(np.zeros(16000, dtype=np.float32))


class TestCascada(unittest.TestCase):
    def test_primero_el_local(self):
        with mock.patch.object(transcriptor, "transcribir_local", return_value="hicimos un gran partido") as local, \
                mock.patch.object(transcriptor, "transcribir_groq") as groq:
            self.assertEqual(audio.transcribir(WAV, "¿Que tal?"), "Hicimos un gran partido")
        local.assert_called_once_with(WAV, "¿Que tal?")
        groq.assert_not_called()

    def test_sin_local_va_groq_y_si_el_local_falla_tambien(self):
        for falla in (transcriptor.NoDisponible("sin modelo"), RuntimeError("cuda")):
            with mock.patch.object(transcriptor, "transcribir_local", side_effect=falla), \
                    mock.patch.object(transcriptor, "transcribir_groq", return_value="desde groq"):
                self.assertEqual(audio.transcribir(WAV), "Desde groq")

    def test_sin_ninguno_queda_windows(self):
        with mock.patch.object(transcriptor, "transcribir_local", side_effect=transcriptor.NoDisponible("x")), \
                mock.patch.object(transcriptor, "transcribir_groq", side_effect=transcriptor.NoDisponible("y")), \
                mock.patch.object(audio, "_transcribir_con_windows", return_value="con windows") as windows:
            self.assertEqual(audio.transcribir(WAV), "con windows")
        windows.assert_called_once()
        self.assertEqual(transcriptor.ultimo["motor"], "Windows")

    def test_en_las_pruebas_esta_apagado(self):
        self.assertFalse(transcriptor.hay_libreria())
        with self.assertRaises(transcriptor.NoDisponible):
            transcriptor.transcribir_local(WAV)
        with self.assertRaises(transcriptor.NoDisponible):
            transcriptor.transcribir_groq(WAV)


class TestAjustesDelTranscriptorDeClases(unittest.TestCase):
    def test_lo_que_whisper_inventa_en_el_silencio(self):
        self.assertTrue(transcriptor.es_inventada("Gracias por ver el video."))
        self.assertTrue(transcriptor.es_inventada("¡Suscríbete al canal!"))
        self.assertFalse(transcriptor.es_inventada("Gracias a la hinchada"))

    def test_sube_el_volumen_sin_saturar_y_nunca_lo_baja(self):
        floja = np.full(1600, 0.01, dtype=np.float32)
        subida = transcriptor.subir_volumen(floja)
        self.assertGreater(float(np.abs(subida).max()), 0.05)
        self.assertLessEqual(float(np.abs(subida).max()), 0.95)
        fuerte = np.full(1600, 0.5, dtype=np.float32)
        self.assertIs(transcriptor.subir_volumen(fuerte), fuerte)

    def test_el_wav_de_la_app_se_lee(self):
        muestras = transcriptor.muestras_de_wav(wav_de(np.full(800, 0.25, dtype=np.float32)))
        self.assertEqual(len(muestras), 800)
        self.assertAlmostEqual(float(muestras[0]), 0.25, places=2)


class TestGroq(unittest.TestCase):
    def setUp(self):
        parche = mock.patch.dict(os.environ, {"EAFC_SIN_WHISPER": ""})
        parche.start()
        self.addCleanup(parche.stop)

    def test_manda_el_audio_y_prueba_la_otra_clave_si_una_no_sirve(self):
        pedidos = []

        class Respuesta(io.BytesIO):
            def __enter__(self):
                return self

            def __exit__(self, *_):
                return False

        def urlopen(pedido, timeout=None):
            pedidos.append(pedido)
            if len(pedidos) == 1:
                raise urllib.error.HTTPError(pedido.full_url, 401, "no", {}, None)
            return Respuesta(json.dumps({"text": " Vamos por mas."}).encode())

        with mock.patch.object(ia, "desactivada", return_value=False), \
                mock.patch.object(ia, "claves", return_value=["mala", "buena"]), \
                mock.patch.object(transcriptor.urllib.request, "urlopen", urlopen):
            self.assertEqual(transcriptor.transcribir_groq(WAV, "¿Como sigue Italia?"), "Vamos por mas.")
        self.assertEqual(len(pedidos), 2)
        cuerpo = pedidos[1].data
        self.assertIn(b"whisper-large-v3-turbo", cuerpo)
        self.assertIn(b"name=\"file\"; filename=\"respuesta.wav\"", cuerpo)
        self.assertIn("¿Como sigue Italia?".encode(), cuerpo)  # la pregunta, de contexto
        self.assertEqual(pedidos[1].headers["Authorization"], "Bearer buena")

    def test_con_solo_motor_local_no_sale_a_internet(self):
        with mock.patch.object(ia, "desactivada", return_value=True), \
                mock.patch.object(transcriptor.urllib.request, "urlopen") as urlopen:
            with self.assertRaises(transcriptor.NoDisponible):
                transcriptor.transcribir_groq(WAV)
        urlopen.assert_not_called()


if __name__ == "__main__":
    unittest.main()
