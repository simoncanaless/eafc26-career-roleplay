"""
El overlay completo, como las apps de Overwolf: la app ENTERA a pantalla
completa encima del juego.

- Ctrl+Shift+F12 (ui/atajo.py) lo abre: se guarda la ventana del frente (el
  juego), el contenido de la app (lateral, paginas, barra) se MUEVE a la capa
  del overlay (`CapaOverlay`: una ventana propia, sin bordes y siempre encima,
  creada una sola vez), que se muestra del tamano de la pantalla del juego con
  un poco de transparencia (`ajustes.overlay.opacidad`) y toma el foco.
- El mismo atajo, Esc o "VOLVER AL JUEGO" lo cierran: la capa se esconde, el
  contenido vuelve a la ventana de siempre (que nunca cambio: ni flags ni
  pantalla completa) y el foco vuelve al juego. Tambien se cierra solo si el
  juego vuelve al frente (alt-tab, un click en el juego) o si se minimiza.

No se toca el juego: es una ventana mas encima (por eso el juego tiene que
estar en "ventana sin bordes"; en pantalla completa EXCLUSIVA ninguna ventana
puede dibujarse encima sin engancharse al render, que es lo que vigila el
anticheat: no se hace). Las llamadas a Windows, solo con la plataforma
"windows" (no en las pruebas, que corren offscreen).

`ajustes.overlay.modo`: "completo" (por defecto) o "sala" (el atajo abre la
sala flotante chica de antes, ui/overlay.py).
"""

import ctypes
from datetime import datetime
from typing import Optional

from PySide6.QtCore import QEvent, QObject, Qt, QTimer, Signal
from PySide6.QtGui import QGuiApplication, QKeySequence, QShortcut
from PySide6.QtWidgets import QVBoxLayout, QWidget

from roleplay import ajustes, config
from roleplay.ui.overlay import _es_windows, _poner_al_frente, _soltar_mouse, _ventana_al_frente

OPACIDAD = 0.95
OPACIDAD_MINIMA = 0.7
REINTENTOS_FOCO = 6  # si el juego no suelta el foco al toque, se insiste cada INTERVALO_FOCO_MS
INTERVALO_FOCO_MS = 120
ESPERA_DESACTIVADA_MS = 300  # al perder el foco, cuanto esperar para ver quien lo tomo
MODOS = ("completo", "sala")
MAXIMO_REGISTRO = 300  # lineas de overlay.log


def anotar(texto: str) -> None:
    """overlay.log en la carpeta de datos: que paso al abrir y cerrar (para
    entender un problema encima del juego, que las pruebas no ven). Nunca falla."""
    try:
        ruta = config.CARPETA_DATOS / "overlay.log"
        lineas = ruta.read_text(encoding="utf-8").splitlines()[-MAXIMO_REGISTRO:] if ruta.exists() else []
        lineas.append(f"{datetime.now().isoformat(timespec='milliseconds')} {texto}")
        ruta.write_text("\n".join(lineas) + "\n", encoding="utf-8")
    except OSError:
        pass


def _describir(hwnd: int) -> str:
    if not hwnd or not _es_windows():
        return str(hwnd)
    titulo = ctypes.create_unicode_buffer(60)
    ctypes.windll.user32.GetWindowTextW(hwnd, titulo, 60)
    return f"{hwnd} {titulo.value!r}"


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


class CapaOverlay(QWidget):
    """La ventana del overlay. Se crea UNA vez, con sus flags definitivos (sin bordes,
    siempre encima, sin boton en la barra de tareas), y despues solo se muestra y se
    esconde: nunca se le cambian los flags ni entra o sale de "pantalla completa".

    Antes la ventana principal se transformaba en overlay y volvia (flags nuevos y
    showFullScreen/showNormal con la ventana a la vista). Qt avisa que cambiar el marco
    de una ventana visible y salir de pantalla completa en Windows la deja deformada,
    y Simon lo vio (2026-10-21). Los overlays que no inyectan nada en el juego
    (electron-overlay-window, el de Awakened PoE Trade) usan una ventana propia que
    nunca se destruye ni se transforma."""

    def __init__(self, al_cerrar):
        super().__init__(None, Qt.WindowType.Tool | Qt.WindowType.FramelessWindowHint
                         | Qt.WindowType.WindowStaysOnTopHint)
        self.setWindowTitle("EAFC 26 Roleplay - Overlay")
        self._al_cerrar = al_cerrar
        capa = QVBoxLayout(self)
        capa.setContentsMargins(0, 0, 0, 0)
        capa.setSpacing(0)

    def closeEvent(self, evento):
        evento.ignore()  # (Alt+F4) = volver al juego; la capa no se destruye nunca
        self._al_cerrar()


class OverlayCompleto(QObject):
    cambio = Signal(bool)  # True al abrirse, False al cerrarse

    def __init__(self, ventana):
        super().__init__(ventana)
        self.ventana = ventana
        self.abierto = False
        self._juego = 0
        self._contenido = None  # lo que se mueve de la ventana principal a la capa
        self._ventana_visible = False
        self._intentos = 0
        self.capa = CapaOverlay(self._cerrar_por_la_ventana)
        self.capa.setWindowIcon(ventana.windowIcon())
        self.capa.installEventFilter(self)
        ventana.destroyed.connect(self.capa.deleteLater)
        self._esc = QShortcut(QKeySequence(Qt.Key.Key_Escape), self.capa)
        self._esc.setContext(Qt.ShortcutContext.WindowShortcut)
        self._esc.setEnabled(False)
        self._esc.activated.connect(self._on_esc)

    def hwnd(self) -> int:
        """La ventana donde esta la app ahora (el mando mueve el cursor adentro de esta)."""
        return int(self.capa.winId()) if self.abierto else int(self.ventana.winId())

    def eventFilter(self, objeto, evento):
        if self.abierto and objeto is self.capa:
            if (evento.type() == QEvent.Type.WindowStateChange and self.capa.isMinimized()
                    and not evento.oldState() & Qt.WindowState.WindowMinimized):
                anotar("se minimizo")
                QTimer.singleShot(0, self._cerrar_sin_devolver)
            elif evento.type() == QEvent.Type.WindowDeactivate:
                anotar(f"perdio el foco; al frente: {_describir(_ventana_al_frente())}")
                QTimer.singleShot(ESPERA_DESACTIVADA_MS, self._si_volvio_el_juego)
        return False

    def _si_volvio_el_juego(self):
        if self.abierto and self._juego and _ventana_al_frente() == self._juego:
            anotar("el juego volvio al frente: se cierra")
            self.cerrar(devolver_foco=False)

    def _on_esc(self):
        anotar("Esc")
        self.cerrar()

    def _cerrar_por_la_ventana(self):
        anotar("cerrar la ventana")
        self.cerrar()

    def _cerrar_sin_devolver(self):
        self.cerrar(devolver_foco=False)

    def alternar(self):
        if self.abierto:
            self.cerrar()
        else:
            self.abrir()

    def _lugar(self):
        """Toda la pantalla donde esta el juego (FC 26 en ventana sin bordes la ocupa entera)."""
        pantalla = (pantalla_de_la_ventana(self._juego) or self.ventana.screen()
                    or QGuiApplication.primaryScreen())
        return pantalla.geometry() if pantalla is not None else self.capa.geometry()

    def abrir(self):
        if self.abierto:
            return
        v = self.ventana
        al_frente = _ventana_al_frente()
        if al_frente and al_frente not in (int(v.winId()), int(self.capa.winId())):
            self._juego = al_frente
        anotar(f"abrir: al frente {_describir(al_frente)}, ventana "
               f"{'minimizada' if v.isMinimized() else 'visible' if v.isVisible() else 'escondida'}")
        self._ventana_visible = v.isVisible() and not v.isMinimized()
        self.capa.setGeometry(self._lugar())
        self.capa.setWindowOpacity(configuracion()["opacidad"])
        self._contenido = v.takeCentralWidget()
        if self._contenido is not None:
            self.capa.layout().addWidget(self._contenido)
            self._contenido.show()
        if self._ventana_visible:
            v.hide()  # (vacia; vuelve igual que estaba al cerrar)
        self.abierto = True
        self._esc.setEnabled(True)
        self.capa.show()
        self.capa.raise_()
        self.capa.activateWindow()
        self._intentos = 0
        self._tomar_el_foco()
        self.cambio.emit(True)

    def _tomar_el_foco(self):
        """Sin el foco, el juego se queda con los clicks y el teclado aunque
        el overlay se vea encima: se insiste unas veces."""
        if not self.abierto:
            return
        _soltar_mouse()
        tomado = _poner_al_frente(int(self.capa.winId()))
        anotar(f"tomar el foco (intento {self._intentos + 1}): {'si' if tomado else 'no'}")
        if not tomado and _es_windows():
            self._intentos += 1
            if self._intentos < REINTENTOS_FOCO:
                QTimer.singleShot(INTERVALO_FOCO_MS, self._tomar_el_foco)

    def cerrar(self, devolver_foco: bool = True):
        if not self.abierto:
            return
        v = self.ventana
        anotar(f"cerrar (devolver el foco: {'si' if devolver_foco else 'no'})")
        self.abierto = False
        self._esc.setEnabled(False)
        self.capa.hide()
        if self._contenido is not None:
            self.capa.layout().removeWidget(self._contenido)
            v.setCentralWidget(self._contenido)
            self._contenido = None
        if self._ventana_visible:
            v.show()  # como estaba antes (queda detras del juego)
        if devolver_foco:
            _poner_al_frente(self._juego)
        self.cambio.emit(False)
