import io
import unittest
import wave
from types import SimpleNamespace
from unittest import mock

import numpy as np

import ayuda
from roleplay import database
from roleplay.models import PlayerProfile
from roleplay.servicios import audio


class StreamFalso:
    """Hace de sounddevice.InputStream: al arrancar entrega `bloques` al
    callback, como haria el microfono."""

    def __init__(self, bloques, falla_al_abrir=False):
        self.bloques = bloques
        self.falla_al_abrir = falla_al_abrir
        self.abierto = False

    def __call__(self, device, channels, samplerate, dtype, callback):
        if self.falla_al_abrir:
            raise OSError("Error opening InputStream: Invalid device")
        self.parametros = (device, channels, samplerate, dtype)
        self.callback = callback
        return self

    def start(self):
        self.abierto = True
        for bloque in self.bloques:
            self.callback(bloque, len(bloque), None, None)

    def stop(self):
        pass

    def close(self):
        self.abierto = False


def bloque(muestras: int, valor: int = 1000):
    return np.full((muestras, 1), valor, dtype=np.int16)


def leer_wav(datos: bytes):
    with wave.open(io.BytesIO(datos)) as archivo:
        return archivo.getnchannels(), archivo.getframerate(), archivo.readframes(archivo.getnframes())


class TestGrabador(unittest.TestCase):
    def test_graba_y_entrega_un_wav_mono_de_16khz(self):
        stream = StreamFalso([bloque(8000), bloque(8000, 7)])
        grabador = audio.GrabadorMicrofono(dispositivo=4, crear_stream=stream)
        grabador.iniciar()
        self.assertAlmostEqual(grabador.segundos, 1.0)
        canales, frecuencia, pcm = leer_wav(grabador.detener())
        self.assertEqual((canales, frecuencia), (1, 16000))
        self.assertEqual(len(pcm), 16000 * 2)
        self.assertEqual(stream.parametros, (4, 1, 16000, "int16"))
        self.assertFalse(stream.abierto)

    def test_no_pasa_del_maximo(self):
        stream = StreamFalso([bloque(10000), bloque(10000), bloque(10000)])
        grabador = audio.GrabadorMicrofono(maximo_segundos=1, crear_stream=stream)
        grabador.iniciar()
        self.assertTrue(grabador.lleno)
        _, _, pcm = leer_wav(grabador.detener())
        self.assertEqual(len(pcm), 16000 * 2)

    def test_sin_microfono_explica_que_revisar(self):
        grabador = audio.GrabadorMicrofono(crear_stream=StreamFalso([], falla_al_abrir=True))
        with self.assertRaises(RuntimeError) as ctx:
            grabador.iniciar()
        self.assertIn("Privacidad", str(ctx.exception))

    def test_lista_solo_los_microfonos_de_la_api_por_defecto(self):
        falso = SimpleNamespace(
            default=SimpleNamespace(hostapi=0),
            query_devices=lambda: [
                {"name": "Parlantes", "max_input_channels": 0, "hostapi": 0},
                {"name": "HyperX (MME)", "max_input_channels": 1, "hostapi": 0},
                {"name": "HyperX (WASAPI)", "max_input_channels": 1, "hostapi": 2},
            ],
        )
        with mock.patch.object(audio, "_sounddevice", return_value=falso):
            microfonos = audio.listar_microfonos()
        self.assertEqual(
            microfonos, [audio.Microfono(None, "Predeterminado de Windows"), audio.Microfono(1, "HyperX (MME)")]
        )

    def test_transcribir_manda_el_audio_y_la_pregunta(self):
        with mock.patch.object(audio, "generar_json", return_value=audio.Transcripcion(texto="  Hola  ")) as llamada:
            texto = audio.transcribir(b"RIFF", pregunta="Que sentiste?")
        self.assertEqual(texto, "Hola")
        self.assertEqual(llamada.call_args.kwargs["adjunto"], (b"RIFF", "audio/wav"))
        self.assertIn("Que sentiste?", llamada.call_args.args[0])


class TestVozEnLaEntrevista(ayuda.PruebaDeInterfaz):
    def setUp(self):
        super().setUp()
        database.save_profile(PlayerProfile(nombre_jugador="Simon"))
        from roleplay.ui import entrevista

        self.modulo = entrevista
        microfonos = [audio.Microfono(None, "Predeterminado de Windows"), audio.Microfono(3, "HyperX")]
        parche = mock.patch.object(entrevista, "listar_microfonos", return_value=microfonos)
        parche.start()
        self.addCleanup(parche.stop)
        self.pagina = entrevista.InterviewWindow()
        with mock.patch.object(entrevista, "generar_entrevista", return_value=["P1?", "P2?"]):
            self.pagina.generar_entrevista_btn.click()
            ayuda.esperar_tareas()

    def _grabador_falso(self, segundos: float):
        bloques = [bloque(int(16000 * segundos))] if segundos else []
        stream = StreamFalso(bloques)
        return lambda dispositivo: audio.GrabadorMicrofono(dispositivo, crear_stream=stream)

    def test_grabar_transcribe_y_agrega_al_texto(self):
        p = self.pagina
        self.assertEqual(p.microfono_combo.count(), 2)
        p.microfono_combo.setCurrentIndex(1)
        p._respuesta_edits[1].setPlainText("Primero:")

        with mock.patch.object(self.modulo, "GrabadorMicrofono", self._grabador_falso(2)) as _, \
                mock.patch.object(self.modulo, "transcribir", return_value="estoy feliz") as transcribir:
            p._botones_voz[1].click()  # empieza
            self.assertEqual(p._grabacion[0].dispositivo, 3)
            # mientras graba no se puede regenerar, enviar ni grabar otra respuesta
            self.assertFalse(p.generar_entrevista_btn.isEnabled())
            self.assertFalse(p.enviar_respuestas_btn.isEnabled())
            self.assertFalse(p._botones_voz[0].isEnabled())
            self.assertTrue(p._botones_voz[1].isEnabled())
            self.assertIn("DETENER", p._botones_voz[1].text())
            p._botones_voz[1].click()  # termina
            ayuda.esperar_tareas()

        self.assertEqual(p._respuesta_edits[1].toPlainText(), "Primero: estoy feliz")
        self.assertEqual(transcribir.call_args.args[1], "P2?")
        self.assertTrue(p.enviar_respuestas_btn.isEnabled())
        self.assertTrue(all(b.isEnabled() for b in p._botones_voz))

    def test_un_click_sin_hablar_no_gasta_una_llamada(self):
        with mock.patch.object(self.modulo, "GrabadorMicrofono", self._grabador_falso(0)), \
                mock.patch.object(self.modulo, "transcribir") as transcribir:
            self.pagina._botones_voz[0].click()
            self.pagina._botones_voz[0].click()
        transcribir.assert_not_called()
        self.avisos.assert_called_once()

    def test_si_falla_el_microfono_se_avisa(self):
        def no_abre(dispositivo):
            return audio.GrabadorMicrofono(dispositivo, crear_stream=StreamFalso([], falla_al_abrir=True))

        with mock.patch.object(self.modulo, "GrabadorMicrofono", no_abre):
            self.pagina._botones_voz[0].click()
        self.assertIsNone(self.pagina._grabacion)
        self.assertIn("Privacidad", self.avisos.call_args.args[2])
        self.assertTrue(self.pagina.generar_entrevista_btn.isEnabled())

    def test_sin_libreria_de_audio_los_botones_quedan_apagados(self):
        from roleplay.ui import entrevista

        with mock.patch.object(entrevista, "listar_microfonos", side_effect=RuntimeError("Falta la libreria")):
            pagina = entrevista.InterviewWindow()
            pagina._mostrar_preguntas(["P1?"])
            pagina._refrescar_botones()
        self.assertFalse(pagina._botones_voz[0].isEnabled())
        self.assertIn("Falta la libreria", pagina.microfono_combo.toolTip())


if __name__ == "__main__":
    unittest.main()
