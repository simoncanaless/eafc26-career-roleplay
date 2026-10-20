"""
El overlay completo, como las apps de Overwolf: la app ENTERA a pantalla
completa encima del juego.

- Ctrl+Shift+F12 (ui/atajo.py) lo abre: se guarda la ventana del frente (el
  juego), la ventana de la app pasa a ser sin bordes, siempre encima y a
  pantalla completa EN EL MONITOR DEL JUEGO, con un poco de transparencia
  (`ajustes.overlay.opacidad`), y toma el foco: se usa al toque.
- El mismo atajo, Esc o "VOLVER AL JUEGO" lo cierran: la ventana se esconde,
  vuelve a ser la de siempre (sus bordes, su tamano) y el foco vuelve al juego.
  Tambien se cierra solo si el juego vuelve al frente (alt-tab, un click en
  el juego) o si la ventana se minimiza: si no, quedaba "abierto" a medias, con
  la barra del overlay en la ventana de siempre.

No se toca el juego: es una ventana mas encima (por eso el juego tiene que
estar en "ventana sin bordes"; en pantalla completa EXCLUSIVA ninguna ventana
puede dibujarse encima sin engancharse al render, que es lo que vigila el
anticheat: no se hace). Las llamadas a Windows, solo con la plataforma
"windows" (no en las pruebas, que corren offscreen).

`ajustes.overlay.modo`: "completo" (por defecto) o "sala" (el atajo abre la
sala flotante chica de antes, ui/overlay.py).
"""

import ctypes
from typing import Optional

from PySide6.QtCore import QEvent, QObject, Qt, QTimer, Signal
from PySide6.QtGui import QGuiApplication, QKeySequence, QShortcut

from roleplay import ajustes
from roleplay.ui.overlay import _es_windows, _poner_al_frente, _soltar_mouse, _ventana_al_frente

OPACIDAD = 0.95
OPACIDAD_MINIMA = 0.7
REINTENTOS_FOCO = 6  # si el juego no suelta el foco al toque, se insiste cada INTERVALO_FOCO_MS
INTERVALO_FOCO_MS = 120
ESPERA_DESACTIVADA_MS = 300  # al perder el foco, cuanto esperar para ver quien lo tomo
MODOS = ("completo", "sala")


def configuracion() -> dict:
    leido = ajustes.leer().get("overlay", {})
    modo = leido.get("modo", "completo")
    try:
        opacidad = float(leido.get("opacidad", OPACIDAD))
    except (TypeError, ValueError):
        opacidad = OPACIDAD
    return {"modo": modo if modo in MODOS else "completo", "opacidad": max(OPACIDAD_MINIMA, min(1.0, opacidad))}


def pantalla_de_la_ventana(hwnd: int):
    """La pantalla (QScreen) donde esta la ventana `hwnd` (el juego); None si no se sabe."""
    if not hwnd or not _es_windows():
        return None
    try:
        from ctypes import wintypes

        class MONITORINFOEX(ctypes.Structure):
            _fields_ = [("cbSize", wintypes.DWORD), ("rcMonitor", wintypes.RECT), ("rcWork", wintypes.RECT),
                        ("dwFlags", wintypes.DWORD), ("szDevice", wintypes.WCHAR * 32)]

        user32 = ctypes.windll.user32
        user32.MonitorFromWindow.restype = wintypes.HANDLE
        monitor = user32.MonitorFromWindow(wintypes.HWND(hwnd), 2)  # MONITOR_DEFAULTTONEAREST
        info = MONITORINFOEX()
        info.cbSize = ctypes.sizeof(MONITORINFOEX)
        if not user32.GetMonitorInfoW(monitor, ctypes.byref(info)):
            return None
        monitor_rect = info.rcMonitor
        for pantalla in QGuiApplication.screens():
            # Qt 6 nombra las pantallas con el nombre del monitor ("VG27AQ5A"), no
            # con el de Windows (DISPLAY1): se compara la esquina y el ancho
            g, escala = pantalla.geometry(), pantalla.devicePixelRatio()
            if pantalla.name() == info.szDevice or (
                    (g.x(), g.y()) == (monitor_rect.left, monitor_rect.top)
                    and round(g.width() * escala) == monitor_rect.right - monitor_rect.left):
                return pantalla
        return None
    except (OSError, AttributeError, ValueError):
        return None


class OverlayCompleto(QObject):
    cambio = Signal(bool)  # True al abrirse, False al cerrarse

    def __init__(self, ventana):
        super().__init__(ventana)
        self.ventana = ventana
        self.abierto = False
        self._juego = 0
        self._antes: Optional[dict] = None
        self._intentos = 0
        self._esc = QShortcut(QKeySequence(Qt.Key.Key_Escape), ventana)
        self._esc.setContext(Qt.ShortcutContext.WindowShortcut)
        self._esc.setEnabled(False)
        self._esc.activated.connect(self.cerrar)
        ventana.installEventFilter(self)

    def eventFilter(self, objeto, evento):
        if self.abierto and objeto is self.ventana:
            if (evento.type() == QEvent.Type.WindowStateChange and self.ventana.isMinimized()
                    and not evento.oldState() & Qt.WindowState.WindowMinimized):  # (no al abrirse desde minimizada)
                QTimer.singleShot(0, self._cerrar_sin_devolver)
            elif evento.type() == QEvent.Type.WindowDeactivate:
                QTimer.singleShot(ESPERA_DESACTIVADA_MS, self._si_volvio_el_juego)
        return False

    def _si_volvio_el_juego(self):
        if self.abierto and self._juego and _ventana_al_frente() == self._juego:
            self.cerrar(devolver_foco=False)

    def _cerrar_sin_devolver(self):
        self.cerrar(devolver_foco=False)

    def alternar(self):
        if self.abierto:
            self.cerrar()
        else:
            self.abrir()

    def abrir(self):
        if self.abierto:
            return
        v = self.ventana
        al_frente = _ventana_al_frente()
        if al_frente and al_frente != int(v.winId()):
            self._juego = al_frente
        self._antes = {"visible": v.isVisible() and not v.isMinimized(), "geometria": v.saveGeometry(),
                       "flags": v.windowFlags()}
        pantalla = pantalla_de_la_ventana(self._juego) or v.screen() or QGuiApplication.primaryScreen()
        v.setWindowFlags(self._antes["flags"] | Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint)
        v.setWindowOpacity(configuracion()["opacidad"])
        if pantalla is not None:
            v.setGeometry(pantalla.geometry())
        self.abierto = True
        self._esc.setEnabled(True)
        v.showFullScreen()
        v.raise_()
        v.activateWindow()
        self._intentos = 0
        self._tomar_el_foco()
        self.cambio.emit(True)

    def _tomar_el_foco(self):
        """Sin el foco, el juego se queda con los clicks y el teclado aunque
        el overlay se vea encima: se insiste unas veces."""
        if not self.abierto:
            return
        _soltar_mouse()
        if not _poner_al_frente(int(self.ventana.winId())) and _es_windows():
            self._intentos += 1
            if self._intentos < REINTENTOS_FOCO:
                QTimer.singleShot(INTERVALO_FOCO_MS, self._tomar_el_foco)

    def cerrar(self, devolver_foco: bool = True):
        if not self.abierto:
            return
        v = self.ventana
        antes = self._antes or {}
        self.abierto = False
        self._esc.setEnabled(False)
        v.hide()
        v.setWindowOpacity(1.0)
        v.setWindowFlags(antes.get("flags", v.windowFlags()))
        v.setWindowState(Qt.WindowState.WindowNoState)
        if antes.get("geometria") is not None:
            v.restoreGeometry(antes["geometria"])
        if antes.get("visible"):
            v.showNormal()  # como estaba antes (queda detras del juego)
        if devolver_foco:
            _poner_al_frente(self._juego)
        self.cambio.emit(False)
