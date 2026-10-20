"""
El mando (PS5, PS4, Xbox...) en el overlay completo (pedido de Simon, 2026-10-20:
juega con un mando de PS5 y con el overlay abierto el mando le seguia hablando
al juego).

Mientras el overlay esta abierto:
- stick izquierdo: mueve el cursor (la cruceta, despacio, para apuntar fino)
- X (cruz; A en Xbox): apretar (un click, y mantenerlo es arrastrar)
- circulo (B en Xbox): volver al juego
- stick derecho: subir y bajar (la rueda)
- L1 / R1: la seccion anterior / siguiente del menu

El mando se lee con SDL (pysdl2 + pysdl2-dll, la misma libreria que usan Steam
y los emuladores), solo con el overlay abierto, y sin el modo "mejorado" del
DualSense (asi el juego lo sigue viendo igual). No se toca el juego: el cursor y
los clicks se mandan SOLO si el overlay es la ventana del frente. El juego puede
seguir leyendo el mando por su cuenta mientras tanto (eso lo decide el juego).

`ajustes.overlay.mando` (por defecto True) lo apaga; `EAFC_SIN_MANDO=1` tambien (las pruebas).
"""

import ctypes
import os
import sys
import time
from dataclasses import dataclass, field
from typing import Optional

from PySide6.QtCore import QObject, QTimer

from roleplay import ajustes

INTERVALO_MS = 16
ZONA_MUERTA = 0.18
VELOCIDAD = 1600  # pixeles por segundo con el stick a fondo
VELOCIDAD_CRUCETA = 350
RUEDA_POR_SEGUNDO = 14  # muescas de la rueda con el stick derecho a fondo
REVISAR_MANDO_S = 1.0  # sin mando, cada cuanto se busca uno

# botones y ejes de SDL_GameController (el mismo orden para PS5, PS4 y Xbox)
CRUZ, CIRCULO, L1, R1 = 0, 1, 9, 10
ARRIBA, ABAJO, IZQUIERDA, DERECHA = 11, 12, 13, 14
BOTONES = (CRUZ, CIRCULO, L1, R1, ARRIBA, ABAJO, IZQUIERDA, DERECHA)
EJE_X, EJE_Y, EJE_DER_Y = 0, 1, 3


@dataclass
class EstadoMando:
    ejes: tuple = (0.0,) * 6  # -1..1
    botones: frozenset = field(default_factory=frozenset)


def usar_mando() -> bool:
    if os.environ.get("EAFC_SIN_MANDO"):  # (las pruebas: nunca el mando de verdad)
        return False
    return bool(ajustes.leer().get("overlay", {}).get("mando", True))


def _eje(valor: float) -> float:
    """Zona muerta y curva: chico = preciso, a fondo = rapido."""
    if abs(valor) < ZONA_MUERTA:
        return 0.0
    fuerza = (abs(valor) - ZONA_MUERTA) / (1 - ZONA_MUERTA)
    return (fuerza ** 2) * (1 if valor > 0 else -1)


class Traductor:
    """Del estado del mando a acciones: ("mover", dx, dy), ("apretar",),
    ("soltar",), ("rueda", muescas; + es para arriba), ("volver",), ("seccion", +-1)."""

    def __init__(self):
        self._antes: frozenset = frozenset()
        self._resto = [0.0, 0.0, 0.0]  # x, y, rueda (lo que no llego a un pixel o una muesca)

    def soltar_todo(self) -> list:
        apretado = CRUZ in self._antes
        self._antes = frozenset()
        self._resto = [0.0, 0.0, 0.0]
        return [("soltar",)] if apretado else []

    def traducir(self, estado: EstadoMando, dt: float) -> list:
        acciones = []
        botones = estado.botones
        cruceta_x = (DERECHA in botones) - (IZQUIERDA in botones)
        cruceta_y = (ABAJO in botones) - (ARRIBA in botones)
        self._resto[0] += _eje(estado.ejes[EJE_X]) * VELOCIDAD * dt + cruceta_x * VELOCIDAD_CRUCETA * dt
        self._resto[1] += _eje(estado.ejes[EJE_Y]) * VELOCIDAD * dt + cruceta_y * VELOCIDAD_CRUCETA * dt
        self._resto[2] += -_eje(estado.ejes[EJE_DER_Y]) * RUEDA_POR_SEGUNDO * dt
        dx, dy, muescas = (int(v) for v in self._resto)
        self._resto = [self._resto[0] - dx, self._resto[1] - dy, self._resto[2] - muescas]
        if dx or dy:
            acciones.append(("mover", dx, dy))
        nuevos, soltados = botones - self._antes, self._antes - botones
        if CRUZ in nuevos:
            acciones.append(("apretar",))
        if CRUZ in soltados:
            acciones.append(("soltar",))
        if muescas:
            acciones.append(("rueda", muescas))
        if L1 in nuevos:
            acciones.append(("seccion", -1))
        if R1 in nuevos:
            acciones.append(("seccion", 1))
        if CIRCULO in nuevos:
            acciones.append(("volver",))
        self._antes = botones
        return acciones


class LectorMando:
    """El primer mando conectado, por SDL. Nada falla: sin SDL o sin mando, `leer()` da None."""

    def __init__(self):
        self._sdl = None
        self._mando = None
        self._buscado = 0.0
        self.nombre = ""

    def abrir(self) -> bool:
        if self._sdl is not None:
            return True
        try:
            import sdl2dll

            os.environ.setdefault("PYSDL2_DLL_PATH", sdl2dll.get_dllpath())
            import sdl2
        except Exception:  # noqa: BLE001 (sin la libreria, no hay mando; la app sigue)
            return False
        sdl2.SDL_SetHint(b"SDL_JOYSTICK_ALLOW_BACKGROUND_EVENTS", b"1")
        sdl2.SDL_SetHint(b"SDL_JOYSTICK_HIDAPI_PS5_RUMBLE", b"0")  # sin el modo mejorado del DualSense
        sdl2.SDL_SetHint(b"SDL_JOYSTICK_HIDAPI_PS4_RUMBLE", b"0")
        if sdl2.SDL_Init(sdl2.SDL_INIT_GAMECONTROLLER) != 0:
            return False
        self._sdl = sdl2
        self._buscado = 0.0
        return True

    def _buscar(self) -> None:
        sdl2 = self._sdl
        ahora = time.monotonic()
        if ahora - self._buscado < REVISAR_MANDO_S:
            return
        self._buscado = ahora
        sdl2.SDL_PumpEvents()  # (para ver los mandos que se conectan despues)
        for indice in range(sdl2.SDL_NumJoysticks()):
            if sdl2.SDL_IsGameController(indice):
                self._mando = sdl2.SDL_GameControllerOpen(indice)
                if self._mando:
                    self.nombre = (sdl2.SDL_GameControllerName(self._mando) or b"").decode("utf-8", "replace")
                    return

    def leer(self) -> Optional[EstadoMando]:
        sdl2 = self._sdl
        if sdl2 is None:
            return None
        if self._mando and not sdl2.SDL_GameControllerGetAttached(self._mando):
            sdl2.SDL_GameControllerClose(self._mando)
            self._mando, self.nombre = None, ""
        if not self._mando:
            self._buscar()
            if not self._mando:
                return None
        sdl2.SDL_GameControllerUpdate()
        ejes = tuple(sdl2.SDL_GameControllerGetAxis(self._mando, eje) / 32767 for eje in range(6))
        botones = frozenset(b for b in BOTONES if sdl2.SDL_GameControllerGetButton(self._mando, b))
        return EstadoMando(ejes, botones)

    def cerrar(self) -> None:
        if self._sdl is None:
            return
        if self._mando:
            self._sdl.SDL_GameControllerClose(self._mando)
        self._sdl.SDL_QuitSubSystem(self._sdl.SDL_INIT_GAMECONTROLLER)
        self._sdl, self._mando, self.nombre = None, None, ""


def describir_mando() -> str:
    """Para el diagnostico: que mando hay (sin abrir el overlay)."""
    lector = LectorMando()
    if not lector.abrir():
        return "no se pudo cargar SDL (pysdl2-dll): el overlay se usa con el mouse"
    try:
        lector.leer()
        return f"{lector.nombre} conectado" if lector.nombre else "ninguno conectado (se busca al abrir el overlay)"
    finally:
        lector.cerrar()


# ---- Windows: el cursor y los clicks, SOLO dentro del overlay ----

class _ENTRADA(ctypes.Structure):
    class _Union(ctypes.Union):
        class _Raton(ctypes.Structure):
            _fields_ = [("dx", ctypes.c_long), ("dy", ctypes.c_long), ("mouseData", ctypes.c_ulong),
                        ("dwFlags", ctypes.c_ulong), ("time", ctypes.c_ulong), ("dwExtraInfo", ctypes.c_size_t)]
        _fields_ = [("mi", _Raton), ("relleno", ctypes.c_byte * 32)]
    _fields_ = [("type", ctypes.c_ulong), ("u", _Union)]


ABAJO_IZQ, ARRIBA_IZQ, RUEDA = 0x0002, 0x0004, 0x0800


class RatonDeWindows:
    """Mueve el cursor y hace los clicks, solo si `hwnd` (el overlay) es la
    ventana del frente y el cursor queda adentro de ella."""

    def __init__(self, hwnd_de):
        self._hwnd_de = hwnd_de  # funcion: el hwnd del overlay ahora

    def _al_frente(self) -> bool:
        return sys.platform == "win32" and ctypes.windll.user32.GetForegroundWindow() == self._hwnd_de()

    def _boton(self, flags: int, datos: int = 0) -> None:
        entrada = _ENTRADA(type=0)
        entrada.u.mi.dwFlags, entrada.u.mi.mouseData = flags, ctypes.c_ulong(datos & 0xFFFFFFFF).value
        ctypes.windll.user32.SendInput(1, ctypes.byref(entrada), ctypes.sizeof(_ENTRADA))

    def hacer(self, accion: tuple) -> None:
        if not self._al_frente():
            return
        from ctypes import wintypes

        user32 = ctypes.windll.user32
        if accion[0] == "mover":
            punto, borde = wintypes.POINT(), wintypes.RECT()
            user32.GetCursorPos(ctypes.byref(punto))
            user32.GetWindowRect(self._hwnd_de(), ctypes.byref(borde))
            x = max(borde.left, min(borde.right - 1, punto.x + accion[1]))
            y = max(borde.top, min(borde.bottom - 1, punto.y + accion[2]))
            user32.SetCursorPos(x, y)
        elif accion[0] == "apretar":
            self._boton(ABAJO_IZQ)
        elif accion[0] == "soltar":
            self._boton(ARRIBA_IZQ)
        elif accion[0] == "rueda":
            self._boton(RUEDA, accion[1] * 120)


class MandoOverlay(QObject):
    """Prende el mando cuando se abre el overlay y lo apaga cuando se cierra."""

    def __init__(self, ventana, overlay, lector=None, raton=None):
        super().__init__(ventana)
        self.ventana = ventana
        self.overlay = overlay
        self.lector = lector or LectorMando()
        self.raton = raton or RatonDeWindows(lambda: int(ventana.winId()))
        self.traductor = Traductor()
        self._ultimo = 0.0
        self._timer = QTimer(self)
        self._timer.setInterval(INTERVALO_MS)
        self._timer.timeout.connect(self._leer)
        overlay.cambio.connect(self._on_overlay)

    def _on_overlay(self, abierto: bool):
        if abierto and usar_mando() and self.lector.abrir():
            self.traductor = Traductor()
            self._ultimo = time.monotonic()
            self._timer.start()
            return
        self._timer.stop()
        for accion in self.traductor.soltar_todo():  # (que no quede el click apretado)
            self.raton.hacer(accion)
        self.lector.cerrar()

    def _leer(self):
        ahora = time.monotonic()
        dt, self._ultimo = min(0.1, ahora - self._ultimo), ahora
        estado = self.lector.leer()
        if estado is None:
            return
        for accion in self.traductor.traducir(estado, dt):
            if accion[0] == "volver":
                for soltar in self.traductor.soltar_todo():
                    self.raton.hacer(soltar)
                self.overlay.cerrar()
                return
            if accion[0] == "seccion":
                self.ventana.cambiar_seccion(accion[1])
            else:
                self.raton.hacer(accion)
