"""
Atajo de teclado global (funciona aunque el juego tenga el foco), con la
API de Windows RegisterHotKey: sin librerias extra. Windows avisa con un
WM_HOTKEY en la cola de mensajes del hilo, y Qt se lo pasa a los filtros
de eventos nativos.

Si otra aplicacion ya uso esa combinacion, registrar() devuelve False y la
app sigue igual (la sala flotante se abre desde el icono de la bandeja).
"""

import ctypes
import sys
from ctypes import wintypes

from PySide6.QtCore import QAbstractNativeEventFilter, QCoreApplication, QObject, Signal

WM_HOTKEY = 0x0312
MOD_ALT, MOD_CONTROL, MOD_SHIFT, MOD_NOREPEAT = 0x0001, 0x0002, 0x0004, 0x4000
VK_F12 = 0x7B
ID_ATAJO = 0x0EAF  # las aplicaciones usan ids entre 0x0000 y 0xBFFF (doc. de RegisterHotKey)

ATAJO_TEXTO = "Ctrl+Shift+F12"
ATAJO = (MOD_CONTROL | MOD_SHIFT | MOD_NOREPEAT, VK_F12)


class _Filtro(QAbstractNativeEventFilter):
    def __init__(self, al_presionar):
        super().__init__()
        self._al_presionar = al_presionar

    def nativeEventFilter(self, tipo, mensaje):
        # Qt entrega el tipo como QByteArray: compararlo con bytes da siempre False
        if bytes(tipo) == b"windows_generic_MSG" and int(mensaje):
            msg = wintypes.MSG.from_address(int(mensaje))
            if msg.message == WM_HOTKEY and msg.wParam == ID_ATAJO:
                self._al_presionar()
                return True, 0
        return False, 0


class AtajoGlobal(QObject):
    presionado = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._filtro = None  # hay que guardarlo: si Python lo borra, Qt se cae
        self.activo = False

    def registrar(self) -> bool:
        if sys.platform != "win32" or self.activo:
            return self.activo
        modificadores, tecla = ATAJO
        if not ctypes.windll.user32.RegisterHotKey(None, ID_ATAJO, modificadores, tecla):
            return False
        self._filtro = _Filtro(self.presionado.emit)
        QCoreApplication.instance().installNativeEventFilter(self._filtro)
        self.activo = True
        return True

    def liberar(self) -> None:
        if not self.activo:
            return
        ctypes.windll.user32.UnregisterHotKey(None, ID_ATAJO)
        QCoreApplication.instance().removeNativeEventFilter(self._filtro)
        self._filtro = None
        self.activo = False
