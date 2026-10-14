"""
Respuestas por voz: grabar del microfono y transcribir con Gemini.

La grabacion es WAV mono de 16 kHz (lo que se necesita para voz: 2 minutos
pesan ~3,8 MB). `sounddevice` se importa recien al usar el microfono, igual
que dxcam: no hace falta para abrir la app.
"""

import io
import threading
import wave
from dataclasses import dataclass
from typing import Callable, Optional

from pydantic import BaseModel

from roleplay.gemini import generar_json

FRECUENCIA = 16000
MAXIMO_SEGUNDOS = 120  # tope por respuesta, para no mandar audios eternos
MINIMO_SEGUNDOS = 0.5  # menos que esto es un click sin querer

AYUDA_PERMISOS = (
    "Revisa que el microfono este conectado y que Windows deje usarlo: "
    "Configuracion > Privacidad y seguridad > Microfono > permitir que las "
    "aplicaciones de escritorio accedan al microfono."
)


def _sounddevice():
    try:
        import sounddevice
    except (ImportError, OSError) as exc:
        raise RuntimeError(
            "Falta la libreria para grabar audio. Instalala con: "
            ".venv\\Scripts\\python.exe -m pip install -r requirements.txt "
            f"(error original: {exc})"
        ) from exc
    return sounddevice


@dataclass(frozen=True)
class Microfono:
    indice: Optional[int]  # None = el predeterminado de Windows
    nombre: str


def listar_microfonos() -> list[Microfono]:
    """Microfonos disponibles. Windows lista cada uno una vez por API de
    audio (MME, DirectSound, WASAPI...): se dejan solo los de la API por
    defecto, para no mostrar el mismo microfono cuatro veces."""
    sd = _sounddevice()
    api_por_defecto = sd.default.hostapi
    microfonos = [Microfono(None, "Predeterminado de Windows")]
    for indice, dispositivo in enumerate(sd.query_devices()):
        if dispositivo["max_input_channels"] > 0 and dispositivo["hostapi"] == api_por_defecto:
            microfonos.append(Microfono(indice, dispositivo["name"]))
    return microfonos


def a_wav(pcm: bytes, frecuencia: int = FRECUENCIA) -> bytes:
    """PCM de 16 bits mono -> archivo WAV en memoria."""
    salida = io.BytesIO()
    with wave.open(salida, "wb") as archivo:
        archivo.setnchannels(1)
        archivo.setsampwidth(2)
        archivo.setframerate(frecuencia)
        archivo.writeframes(pcm)
    return salida.getvalue()


class GrabadorMicrofono:
    """Graba del microfono entre `iniciar()` y `detener()`.

    sounddevice entrega el audio en su propio hilo (el callback); aca solo
    se juntan los bloques. Pasado MAXIMO_SEGUNDOS deja de guardar: la
    interfaz se encarga de detenerlo y avisar.
    """

    def __init__(
        self,
        dispositivo: Optional[int] = None,
        frecuencia: int = FRECUENCIA,
        maximo_segundos: float = MAXIMO_SEGUNDOS,
        crear_stream: Optional[Callable[..., object]] = None,
    ):
        self.dispositivo = dispositivo
        self.frecuencia = frecuencia
        self._maximo_muestras = int(maximo_segundos * frecuencia)
        self._crear_stream = crear_stream  # para las pruebas
        self._bloques: list[bytes] = []
        self._muestras = 0
        self._candado = threading.Lock()
        self._stream = None

    @property
    def segundos(self) -> float:
        with self._candado:
            return self._muestras / self.frecuencia

    @property
    def lleno(self) -> bool:
        with self._candado:
            return self._muestras >= self._maximo_muestras

    def iniciar(self) -> None:
        crear = self._crear_stream or _sounddevice().InputStream
        try:
            self._stream = crear(
                device=self.dispositivo,
                channels=1,
                samplerate=self.frecuencia,
                dtype="int16",
                callback=self._recibir,
            )
            self._stream.start()
        except Exception as exc:  # noqa: BLE001 - PortAudioError y compania
            self._stream = None
            raise RuntimeError(f"No se pudo abrir el microfono ({exc}). {AYUDA_PERMISOS}") from exc

    def _recibir(self, bloque, cuadros, _tiempo, _estado) -> None:
        with self._candado:
            disponibles = self._maximo_muestras - self._muestras
            if disponibles <= 0:
                return
            cuadros = min(cuadros, disponibles)
            self._bloques.append(bloque[:cuadros].tobytes())
            self._muestras += cuadros

    def detener(self) -> bytes:
        """Corta la grabacion y devuelve el WAV (vacio si no grabo nada)."""
        if self._stream is not None:
            self._stream.stop()
            self._stream.close()
            self._stream = None
        with self._candado:
            return a_wav(b"".join(self._bloques), self.frecuencia)


class Transcripcion(BaseModel):
    texto: str


def _build_prompt(pregunta: str) -> str:
    return f"""
Transcribi este audio en espanol, palabra por palabra. Es la respuesta de
un futbolista a esta pregunta de un periodista despues de un partido:
"{pregunta}"

No resumas, no corrijas lo que dice ni agregues nada: solo pone la
puntuacion. Si no se escucha a nadie hablando, devolve el texto vacio.
""".strip()


def transcribir(wav: bytes, pregunta: str = "", api_key: Optional[str] = None) -> str:
    resultado = generar_json(
        _build_prompt(pregunta),
        Transcripcion,
        "Esperate un poco y volve a grabar la respuesta (o escribila).",
        adjunto=(wav, "audio/wav"),
        api_key=api_key,
    )
    return resultado.texto.strip()
