"""
El navegador integrado del configurador: abre la web oficial de la marca
adentro de la app (QtWebEngine, el Chromium de Qt) para configurar el auto
real en 3D, y saca la foto de lo que se ve para el garage.

- QtWebEngine se importa recien al abrir el configurador: pesa y demora, y
  abrir la app tiene que seguir siendo rapido (tests/test_ui.py::TestArranque).
- La web se carga como pagina principal, no dentro de un iframe: los
  encabezados X-Frame-Options / frame-ancestors (que solo frenan iframes)
  no aplican, y no se toca ningun encabezado de seguridad.
- Perfil propio y persistente (carpeta "navegador" en los datos de la app):
  el aviso de cookies de cada marca se contesta una sola vez.
- Los enlaces que abren otra ventana se abren en la misma.
- Sin pantalla (Qt "offscreen", las pruebas) no se crea: Chromium no dibuja
  y la foto saldria en blanco. Tampoco si falta QtWebEngine en la instalacion:
  el configurador vuelve al dibujo propio.
"""

from PySide6.QtCore import QUrl
from PySide6.QtGui import QDesktopServices, QGuiApplication, QImage
from PySide6.QtWidgets import QApplication, QHBoxLayout, QLabel, QProgressBar, QVBoxLayout, QWidget

from roleplay import config
from roleplay.ui import estilos
from roleplay.ui.componentes import boton

_perfil = None


def disponible() -> bool:
    if QGuiApplication.platformName() == "offscreen":
        return False
    try:
        import PySide6.QtWebEngineWidgets  # noqa: F401
    except ImportError:
        return False
    return True


def _perfil_persistente():
    global _perfil
    if _perfil is None:
        from PySide6.QtWebEngineCore import QWebEngineProfile

        carpeta = config.CARPETA_DATOS / "navegador"
        _perfil = QWebEngineProfile("configuradores", QApplication.instance())
        _perfil.setPersistentStoragePath(str(carpeta))
        _perfil.setCachePath(str(carpeta / "cache"))
        _perfil.setPersistentCookiesPolicy(QWebEngineProfile.PersistentCookiesPolicy.AllowPersistentCookies)
    return _perfil


class Navegador(QWidget):
    """La web oficial, con una barra minima: atras, recargar, la direccion y
    abrirla en el navegador de siempre."""

    def __init__(self, url: str, parent=None):
        super().__init__(parent)
        from PySide6.QtWebEngineCore import QWebEnginePage
        from PySide6.QtWebEngineWidgets import QWebEngineView

        class Pagina(QWebEnginePage):
            def createWindow(self, _tipo):  # "abrir en otra pestana": en la misma
                return self

        self._inicio = QUrl(url)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        barra = QHBoxLayout()
        barra.setSpacing(6)
        self.atras_btn = boton("Atras")
        self.recargar_btn = boton("Recargar")
        self.direccion = QLabel()
        self.direccion.setStyleSheet(f"color: {estilos.TEXTO_SUAVE};")
        afuera = boton("Abrir en tu navegador")
        afuera.setToolTip("Si la web no anda bien aca adentro, abrila en Chrome o Edge")
        afuera.clicked.connect(lambda: QDesktopServices.openUrl(self.vista.url()))
        for widget in (self.atras_btn, self.recargar_btn):
            barra.addWidget(widget)
        barra.addWidget(self.direccion, 1)
        barra.addWidget(afuera)
        layout.addLayout(barra)

        self.progreso = QProgressBar()
        self.progreso.setRange(0, 100)
        self.progreso.setTextVisible(False)
        self.progreso.setFixedHeight(3)
        layout.addWidget(self.progreso)

        self.vista = QWebEngineView(self)
        self.vista.setPage(Pagina(_perfil_persistente(), self.vista))
        layout.addWidget(self.vista, 1)

        self.atras_btn.clicked.connect(self.vista.back)
        self.recargar_btn.clicked.connect(self.vista.reload)
        self.vista.urlChanged.connect(lambda u: self.direccion.setText(u.host()))
        self.vista.loadProgress.connect(self.progreso.setValue)
        self.vista.loadFinished.connect(lambda _ok: self.progreso.setValue(100))
        self.vista.load(self._inicio)

    def foto(self) -> QImage:
        """Lo que se ve ahora de la web (sin la barra de arriba), en pixeles de
        verdad: con la pantalla al 300% la captura sale 3 veces mas grande, y
        se la trata como una imagen comun (si no, se dibuja a un tercio)."""
        imagen = self.vista.grab().toImage()
        imagen.setDevicePixelRatio(1.0)
        return imagen
