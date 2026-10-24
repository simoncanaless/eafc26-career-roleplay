"""
Whisper para las respuestas por voz (pedido de Simon, 2026-10-24: "lo de probar
con voz no sirve mucho, ¿no podemos usar lo del transcriptor de clases?").

Cascada (servicios/audio.transcribir):
1. **Whisper local** (faster-whisper, como el "Transcriptor de clases" de Simon,
   con sus mismos ajustes): con tarjeta NVIDIA y las DLL de CUDA, large-v3-turbo
   en la GPU; si no, small en el procesador. Solo si el modelo YA esta en el
   disco (no se baja solo: Ajustes > Voz lo descarga). El modelo queda cargado
   en memoria despues de la primera vez (`precargar()` lo carga en un hilo apenas
   aparecen las preguntas).
2. **Whisper de Groq** (whisper-large-v3-turbo) con la clave de la IA: rapido y
   sin descargar nada, pero el audio sale a internet. No se usa con "solo motor
   local" ni sin clave.
3. El reconocedor de Windows (System.Speech), como antes.

faster-whisper se importa adentro de las funciones (no carga nada al abrir la
app) y no va en el paquete de los amigos (ctranslate2 + onnxruntime + av pesan
~150 MB): ellos usan Groq o Windows. `EAFC_SIN_WHISPER=1` (las pruebas) apaga
el local y el de Groq.
"""

import importlib.util
import io
import json
import os
import sys
import threading
import urllib.error
import urllib.request
import uuid
import wave
from typing import Optional

from roleplay import ajustes

# ---- los ajustes del Transcriptor de clases (Desktop/Transcriptor de reuniones/motor.py) ----
MUESTREO = 16000
CASTIGO_REPETICION = 1.15  # con 1,15 las repeticiones seguidas bajaron de 4 a 1 sin perder palabras
CONDICIONAR_TEXTO_PREVIO = False  # encendido, se engancha en bucles ("Gracias." x5)
DETECTOR_DE_VOZ = {"threshold": 0.30, "min_silence_duration_ms": 700, "speech_pad_ms": 600}
NIVEL_OBJETIVO = 0.08  # RMS al que se sube una grabacion floja (nunca se baja)
INVENTADAS = (  # lo que Whisper "escucha" en el silencio: subtitulos de YouTube
    "gracias por ver el video", "gracias por ver este video", "subtitulos realizados por la comunidad de amara.org",
    "subtitulado por la comunidad de amara.org", "mas informacion www", "subscribete al canal",
    "suscribete al canal", "no olvides suscribirte",
)
MODELOS = ("large-v3-turbo", "large-v3", "medium", "small")  # el orden: el mejor que haya en el disco
TAMANOS_GB = {"small": 0.49, "medium": 1.53, "large-v3-turbo": 1.62, "large-v3": 3.09}
MODELO_GPU, MODELO_CPU = "large-v3-turbo", "small"  # respuestas cortas: turbo en GPU es instantaneo

GROQ_URL = "https://api.groq.com/openai/v1/audio/transcriptions"
GROQ_MODELO = "whisper-large-v3-turbo"
GROQ_TIMEOUT = 20

ultimo = {"motor": "", "detalle": ""}  # con que se transcribio la ultima respuesta (la sala lo muestra)


class NoDisponible(Exception):
    """Este motor no esta (sin la libreria, sin el modelo, sin clave): se pasa al siguiente."""


def apagado() -> bool:
    return bool(os.environ.get("EAFC_SIN_WHISPER"))


# ---- audio ----

def muestras_de_wav(wav: bytes):
    """WAV mono 16 bits -> float32 de -1 a 1 (lo que recibe faster-whisper)."""
    import numpy as np

    with wave.open(io.BytesIO(wav)) as archivo:
        datos = archivo.readframes(archivo.getnframes())
    return np.frombuffer(datos, dtype=np.int16).astype(np.float32) / 32768.0


def subir_volumen(muestras):
    """Sube una grabacion floja hasta un nivel normal sin saturarla (el Transcriptor de clases)."""
    import numpy as np

    if muestras.size == 0:
        return muestras
    rms = float(np.sqrt((muestras.astype(np.float64) ** 2).mean()))
    pico = float(np.abs(muestras).max())
    if rms < 1e-6 or pico < 1e-6:
        return muestras
    ganancia = min(NIVEL_OBJETIVO / rms, 0.95 / pico)
    return (muestras * ganancia).astype(np.float32) if ganancia > 1.0 else muestras


def es_inventada(texto: str) -> bool:
    limpio = texto.lower().strip(" .,!¡?¿-—\"'")
    for con, sin in (("á", "a"), ("é", "e"), ("í", "i"), ("ó", "o"), ("ú", "u")):
        limpio = limpio.replace(con, sin)
    return any(limpio.startswith(frase) for frase in INVENTADAS)


# ---- Whisper local ----

def _preparar_cuda() -> None:
    """Windows no encuentra solo las DLL de CUDA que instala pip (nvidia-cublas/cudnn)."""
    if not hasattr(os, "add_dll_directory"):
        return
    spec = importlib.util.find_spec("nvidia")
    if spec is None or not spec.submodule_search_locations:
        return
    raiz = list(spec.submodule_search_locations)[0]
    for carpeta in sorted(__import__("pathlib").Path(raiz).glob("*/bin")):
        try:
            os.add_dll_directory(str(carpeta))
        except OSError:
            continue
        os.environ["PATH"] = f"{carpeta}{os.pathsep}{os.environ.get('PATH', '')}"


def hay_libreria() -> bool:
    return not apagado() and importlib.util.find_spec("faster_whisper") is not None


def hay_gpu() -> bool:
    """La tarjeta existe Y se cargan las DLL de CUDA (sin ellas, revienta al cargar el modelo)."""
    if not hay_libreria():
        return False
    try:
        _preparar_cuda()
        import ctranslate2

        if ctranslate2.get_cuda_device_count() <= 0:
            return False
        if sys.platform == "win32":
            import ctypes

            for nombre in ("cublas64_12.dll", "cudnn64_9.dll"):
                ctypes.WinDLL(nombre)
        return True
    except Exception:  # noqa: BLE001
        return False


def modelo_descargado(nombre: str) -> bool:
    if not hay_libreria():
        return False
    try:
        from faster_whisper.utils import download_model

        download_model(nombre, local_files_only=True)
        return True
    except Exception:  # noqa: BLE001
        return False


def modelo_elegido() -> Optional[str]:
    """El de Ajustes (`voz.modelo`) si esta bajado; si no, el sugerido para este PC, o el mejor que haya."""
    if not hay_libreria():
        return None
    pedido = (ajustes.leer().get("voz") or {}).get("modelo", "auto")
    if pedido in MODELOS and modelo_descargado(pedido):
        return pedido
    sugerido = MODELO_GPU if hay_gpu() else MODELO_CPU
    if modelo_descargado(sugerido):
        return sugerido
    return next((m for m in MODELOS if modelo_descargado(m)), None)


class _Motor:
    """El modelo cargado queda en memoria: la primera carga tarda, las siguientes no."""

    def __init__(self):
        self._modelo = None
        self._clave = None
        self._candado = threading.Lock()

    def cargar(self, nombre: str):
        from faster_whisper import WhisperModel

        with self._candado:
            gpu = hay_gpu()
            clave = (nombre, gpu)
            if self._clave == clave and self._modelo is not None:
                return self._modelo, gpu
            self._modelo = None
            try:
                modelo = WhisperModel(nombre, device="cuda" if gpu else "cpu",
                                      compute_type="float16" if gpu else "int8", local_files_only=True)
            except Exception:  # noqa: BLE001 (la GPU no arranco: al procesador)
                if not gpu:
                    raise
                gpu = False
                modelo = WhisperModel(nombre, device="cpu", compute_type="int8", local_files_only=True,
                                      cpu_threads=max(4, (os.cpu_count() or 8) // 2))
            self._modelo, self._clave = modelo, (nombre, gpu)
            return modelo, gpu


_motor = _Motor()


def precargar() -> None:
    """Carga el modelo en un hilo (lo llama la sala al mostrar las preguntas). Nunca falla."""
    def cargar():
        try:
            nombre = modelo_elegido()
            if nombre:
                _motor.cargar(nombre)
        except Exception:  # noqa: BLE001
            pass

    if hay_libreria():
        threading.Thread(target=cargar, daemon=True).start()


def transcribir_local(wav: bytes, pregunta: str = "") -> str:
    nombre = modelo_elegido()
    if nombre is None:
        raise NoDisponible("sin Whisper local")
    modelo, gpu = _motor.cargar(nombre)
    segmentos, _info = modelo.transcribe(
        subir_volumen(muestras_de_wav(wav)),
        language="es",
        beam_size=5 if gpu else 1,
        vad_filter=True,
        vad_parameters=DETECTOR_DE_VOZ,
        condition_on_previous_text=CONDICIONAR_TEXTO_PREVIO,
        repetition_penalty=CASTIGO_REPETICION,
        initial_prompt=(pregunta or "")[:200] or None,  # el contexto ayuda con nombres (rivales, clubes)
    )
    texto = " ".join(s.text.strip() for s in segmentos if s.text.strip() and not es_inventada(s.text))
    ultimo.update(motor="Whisper local", detalle=f"{nombre} en {'la GPU' if gpu else 'el procesador'}")
    return texto.strip()


def descargar_modelo(nombre: str) -> None:
    """Baja el modelo (Ajustes > Voz). Corre en un hilo; puede tardar."""
    if not hay_libreria():
        raise RuntimeError("Esta version de la app no trae Whisper local.")
    from faster_whisper.utils import download_model

    download_model(nombre)


# ---- Whisper de Groq ----

def transcribir_groq(wav: bytes, pregunta: str = "") -> str:
    from roleplay.servicios import ia

    if apagado() or ia.desactivada():
        raise NoDisponible("IA desactivada")
    claves = ia.claves("groq")
    if not claves:
        raise NoDisponible("sin clave de Groq")
    limite = "----eafc" + uuid.uuid4().hex
    campos = {"model": GROQ_MODELO, "language": "es", "response_format": "json", "temperature": "0"}
    if pregunta:
        campos["prompt"] = pregunta[:200]
    cuerpo = b"".join(
        f"--{limite}\r\nContent-Disposition: form-data; name=\"{k}\"\r\n\r\n{v}\r\n".encode("utf-8")
        for k, v in campos.items()
    ) + (f"--{limite}\r\nContent-Disposition: form-data; name=\"file\"; filename=\"respuesta.wav\"\r\n"
         "Content-Type: audio/wav\r\n\r\n").encode("utf-8") + wav + f"\r\n--{limite}--\r\n".encode("utf-8")
    ultimo_error = None
    for clave in claves:
        pedido = urllib.request.Request(GROQ_URL, data=cuerpo, method="POST", headers={
            "Authorization": f"Bearer {clave}", "Content-Type": f"multipart/form-data; boundary={limite}",
            "User-Agent": "EAFC26-Roleplay"})
        try:
            with urllib.request.urlopen(pedido, timeout=GROQ_TIMEOUT) as respuesta:
                texto = json.loads(respuesta.read().decode("utf-8")).get("text", "")
            ultimo.update(motor="Whisper de Groq", detalle=GROQ_MODELO)
            return "" if es_inventada(texto) else texto.strip()
        except urllib.error.HTTPError as error:
            ultimo_error = error  # 401/403: la siguiente clave; 429/5xx: tambien se intenta la siguiente
        except (OSError, ValueError) as error:
            raise NoDisponible(f"Groq no contesto ({type(error).__name__})") from error
    raise NoDisponible(f"Groq no transcribio (HTTP {getattr(ultimo_error, 'code', '?')})")


# ---- para Ajustes y el diagnostico ----

def estado() -> str:
    """Que motor de voz se va a usar, en una linea (nunca muestra claves)."""
    partes = []
    if hay_libreria():
        nombre = modelo_elegido()
        donde = "GPU" if hay_gpu() else "procesador"
        partes.append(f"Whisper local: {nombre} en {'la GPU' if donde == 'GPU' else 'el procesador'}" if nombre else "Whisper local: sin modelo descargado")
    else:
        partes.append("Whisper local: no viene en esta version")
    from roleplay.servicios import ia

    partes.append("Whisper de Groq: " + ("listo" if ia.claves("groq") and not ia.desactivada() else "sin clave"))
    partes.append("Windows: de respaldo")
    return " · ".join(partes)
