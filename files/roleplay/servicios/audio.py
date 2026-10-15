"""
Respuestas por voz: grabar del microfono y transcribir con el reconocedor
de voz de Windows (System.Speech, el de "Reconocimiento de voz"), sin
internet ni IA. Se le pasa el WAV por PowerShell; no hace falta instalar nada
si Windows tiene el reconocedor en espanol (Configuracion > Hora e idioma >
Voz). Si no lo tiene, se avisa y se responde escribiendo.

La grabacion es WAV mono de 16 kHz (lo que se necesita para voz: 2 minutos
pesan ~3,8 MB). `sounddevice` se importa recien al usar el microfono, igual
que dxcam: no hace falta para abrir la app.
"""

import io
import os
import subprocess
import tempfile
import threading
import wave
from dataclasses import dataclass
from typing import Callable, Optional

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


# El reconocedor de Windows, por PowerShell: carga System.Speech, busca un
# reconocedor en espanol (el que haya: es-ES, es-MX...), dicta el WAV entero y
# devuelve el texto. Sale con codigo 3 si no hay ningun reconocedor en espanol.
GUION_RECONOCER = r"""
$ErrorActionPreference = 'Stop'
[Console]::OutputEncoding = [Text.Encoding]::UTF8
Add-Type -AssemblyName System.Speech
$info = [System.Speech.Recognition.SpeechRecognitionEngine]::InstalledRecognizers() |
    Where-Object { $_.Culture.Name -like 'es-*' } | Select-Object -First 1
if ($null -eq $info) { exit 3 }
$motor = New-Object System.Speech.Recognition.SpeechRecognitionEngine($info)
$motor.LoadGrammar((New-Object System.Speech.Recognition.DictationGrammar))
$motor.SetInputToWaveFile($env:EAFC_WAV)
$partes = @()
while ($true) { $r = $motor.Recognize(); if ($null -eq $r) { break }; $partes += $r.Text }
$motor.Dispose()
[Console]::Out.Write(($partes -join ' '))
"""
SIN_RECONOCEDOR = (
    "Windows no tiene el reconocimiento de voz en espanol. Agregalo en Configuracion > Hora e idioma > "
    "Idioma y region > Espanol > Opciones > Voz, o escribi la respuesta."
)
SEGUNDOS_RECONOCER = 120


def transcribir(wav: bytes, pregunta: str = "") -> str:
    """El texto de la respuesta grabada (vacio si no se entendio nada)."""
    archivo = tempfile.NamedTemporaryFile(prefix="eafc_voz_", suffix=".wav", delete=False)
    try:
        archivo.write(wav)
        archivo.close()
        try:
            proceso = subprocess.run(
                ["powershell", "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass", "-Command", GUION_RECONOCER],
                capture_output=True, timeout=SEGUNDOS_RECONOCER, env={**os.environ, "EAFC_WAV": archivo.name},
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise RuntimeError(f"No se pudo usar el reconocedor de voz de Windows ({exc}). Escribi la respuesta.") from exc
        if proceso.returncode == 3:
            raise RuntimeError(SIN_RECONOCEDOR)
        if proceso.returncode != 0:
            detalle = proceso.stderr.decode("utf-8", "replace").strip().splitlines()[-1:] or [""]
            raise RuntimeError(f"El reconocedor de voz de Windows fallo ({detalle[0]}). Escribi la respuesta.")
        texto = proceso.stdout.decode("utf-8", "replace").strip()
        return texto[:1].upper() + texto[1:] if texto else ""
    finally:
        try:
            os.unlink(archivo.name)
        except OSError:
            pass
