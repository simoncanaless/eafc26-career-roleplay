"""
El puente con el navegador de la app (QtWebEngine) para las marcas que solo le contestan a su propia pagina
(Ferrari: a un pedido que no sale de su pagina le devuelve el HTML, tambien las imagenes). Abre una pagina de la
marca sin ventana y corre ahi el mismo `fetch` que hace su configurador: un navegador de verdad pidiendo lo que
la pagina pide, sin falsear cabeceras ni esquivar nada.

`runJavaScript` no espera promesas: cada pedido guarda su resultado en `window.__r[id]` y un QTimer los recoge.
Se importa recien al usarlo (QtWebEngine no se carga al abrir la app: TestArranque).
"""

import itertools
import json
import time
from typing import Callable, Optional

from PySide6.QtCore import QObject, QTimer, QUrl
from PySide6.QtWebEngineCore import QWebEnginePage

ESPERA_MAXIMA_S = 240  # Ferrari dibuja la imagen en el momento: puede tardar
RECOGER = ("(() => { const r = window.__r || {}; const salida = {}; for (const k of Object.keys(r)) { salida[k] = r[k]; "
           "delete r[k]; } return JSON.stringify(salida); })()")


class PuenteWeb(QObject):
    """Una pagina de la marca sin ventana; `ejecutar(cuerpo, al_terminar)` corre el cuerpo de una funcion async ahi
    y llama a `al_terminar(valor)` (None si fallo o tardo demasiado)."""

    def __init__(self, url: str, parent: Optional[QObject] = None):
        super().__init__(parent)
        self.listo = False
        self._ids = itertools.count(1)
        self._pendientes: dict = {}  # id -> (al_terminar, desde)
        self._cola: list = []
        self.pagina = QWebEnginePage(self)
        self.pagina.loadFinished.connect(self._cargo)
        self._reloj = QTimer(self)
        self._reloj.setInterval(300)
        self._reloj.timeout.connect(self._revisar)
        self.pagina.load(QUrl(url))

    def ejecutar(self, cuerpo: str, al_terminar: Callable):
        if not self.listo:
            self._cola.append((cuerpo, al_terminar))
            return
        pedido = next(self._ids)
        self._pendientes[pedido] = (al_terminar, time.time())
        self.pagina.runJavaScript(
            f"window.__r = window.__r || {{}}; (async () => {{ {cuerpo} }})()"
            f".then(v => {{ window.__r[{pedido}] = {{ok: v}}; }}).catch(e => {{ window.__r[{pedido}] = {{error: String(e)}}; }}); 1", 0)
        self._reloj.start()

    def _cargo(self, _bien: bool):
        self.listo = True
        for cuerpo, al_terminar in self._cola:
            self.ejecutar(cuerpo, al_terminar)
        self._cola = []

    def _revisar(self):
        if not self._pendientes:
            self._reloj.stop()
            return
        self.pagina.runJavaScript(RECOGER, 0, self._recibir)
        ahora = time.time()
        for pedido, (al_terminar, desde) in list(self._pendientes.items()):
            if ahora - desde > ESPERA_MAXIMA_S:
                del self._pendientes[pedido]
                _avisar(al_terminar, None)

    def _recibir(self, texto):
        try:
            resultados = json.loads(texto or "{}")
        except ValueError:
            return
        for pedido, resultado in resultados.items():
            al_terminar, _ = self._pendientes.pop(int(pedido), (None, 0))
            if al_terminar is not None:
                _avisar(al_terminar, resultado.get("ok"))


def _avisar(al_terminar: Callable, valor):
    try:
        al_terminar(valor)
    except RuntimeError:
        pass  # la ventana que lo pidio ya se cerro


_PUENTES: dict = {}


def puente(url: str) -> PuenteWeb:
    """Uno por sitio, para toda la app (la pagina se carga una vez)."""
    if url not in _PUENTES:
        _PUENTES[url] = PuenteWeb(url)
    return _PUENTES[url]
