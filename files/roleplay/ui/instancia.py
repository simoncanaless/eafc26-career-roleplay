"""
Una sola app abierta a la vez.

Con dos abiertas (paso: una vieja seguia en la bandeja y se abrio otra), solo
la primera se queda con el atajo Ctrl+Shift+F12 y el overlay que se abre es el
de ESA, con el codigo viejo. La segunda le avisa a la primera que se muestre y
se cierra. Al reiniciar (cambiar de carrera), la nueva espera a que la vieja
termine de cerrarse (`EAFC_REINICIO`).
"""

import getpass
import os
import sys
import time

from PySide6.QtCore import QObject, Signal
from PySide6.QtNetwork import QLocalServer, QLocalSocket

NOMBRE = f"EAFC26Roleplay-{getpass.getuser()}"
VARIABLE_REINICIO = "EAFC_REINICIO"
ESPERA_REINICIO_S = 10


def _hay_otra(nombre: str, avisar: bool = True) -> bool:
    """Si hay otra abierta devuelve True y, con `avisar`, le pide que se muestre."""
    socket = QLocalSocket()
    socket.connectToServer(nombre)
    if not socket.waitForConnected(300):
        return False
    if avisar:
        if sys.platform == "win32":  # esta la abrio el usuario: le presta el permiso de pasar al frente
            import ctypes

            ctypes.windll.user32.AllowSetForegroundWindow(-1)  # ASFW_ANY
        socket.write(b"mostrar")
        socket.waitForBytesWritten(300)
    socket.disconnectFromServer()
    return True


class UnaSola(QObject):
    """Ser la unica abierta. `tomar()` False = ya habia otra (y se le aviso)."""

    mostrar = Signal()

    def __init__(self, nombre: str = NOMBRE, parent=None):
        super().__init__(parent)
        self.nombre = nombre
        self._servidor = QLocalServer(self)
        self._servidor.newConnection.connect(self._on_conexion)

    def tomar(self) -> bool:
        if os.environ.pop(VARIABLE_REINICIO, None):  # la vieja se esta cerrando: esperarla
            fin = time.monotonic() + ESPERA_REINICIO_S
            while time.monotonic() < fin and _hay_otra(self.nombre, avisar=False):
                time.sleep(0.3)
        elif _hay_otra(self.nombre):
            return False
        QLocalServer.removeServer(self.nombre)
        return self._servidor.listen(self.nombre)

    def _on_conexion(self):
        while self._servidor.hasPendingConnections():
            self._servidor.nextPendingConnection().deleteLater()
        self.mostrar.emit()
