"""
La tienda real: comprar algo de las webs oficiales (relojes, ropa, casas,
yates, aviones, tecnologia, muebles) como el configurador de los autos.

- A la IZQUIERDA, la web oficial adentro de la app (ui/navegador.py), con un
  boton por tienda de la categoria (servicios/tiendas.TIENDAS: el
  configurador de Rolex, Nike By You para disenar zapatillas, Gucci...).
- A la DERECHA, lo que se compra en el juego: el nombre, el precio ("LEER DE
  LA PAGINA" corre SCRIPT_METADATOS en la web y tiendas.leer_metadatos lo pasa
  a la moneda del juego; si la pagina no lo dice, un nivel de precio o a
  mano), la foto ("CAPTURAR VISTA", con el recorte del configurador) y COMPRAR.

Sin navegador (sin pantalla o sin QtWebEngine) queda el formulario y un boton
para abrir la tienda en el navegador de siempre. Lo que provoca la compra lo
decide servicios/economia.py (ui/vida.py la hace con `articulo()`).
"""

from typing import Optional

from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QDesktopServices, QImage, QPixmap
from PySide6.QtWidgets import (
    QButtonGroup,
    QDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from roleplay import config as config_app
from roleplay.servicios import economia, tiendas
from roleplay.servicios.economia import dinero
from roleplay.ui import estilos
from roleplay.ui.comun import esc
from roleplay.ui.componentes import boton, chip_alternable, etiqueta_campo, fila, texto_suave, titulo_seccion
from roleplay.ui.configurador import RecortarFoto, crear_navegador

ANCHO_PANEL = 360
ANCHO_FOTO = 960
PRECIO_MAXIMO = 2_000_000_000


def guardar_foto_compra(imagen: QImage, nombre: str) -> str:
    """La foto de una compra en la carpeta compras/; devuelve el nombre del archivo."""
    config_app.CARPETA_COMPRAS.mkdir(parents=True, exist_ok=True)
    if imagen.width() > ANCHO_FOTO:
        imagen = imagen.scaledToWidth(ANCHO_FOTO, Qt.TransformationMode.SmoothTransformation)
    archivo = f"{nombre}.jpg"
    imagen.save(str(config_app.CARPETA_COMPRAS / archivo), "JPG", 88)
    return archivo


class DialogoTiendaReal(QDialog):
    def __init__(self, categoria: str, saldo: int, moneda: str, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setWindowTitle("EAFC 26 Roleplay - Tienda")
        self.categoria, self.saldo, self.moneda = categoria, saldo, moneda
        self.tiendas = tiendas.TIENDAS.get(categoria, [])
        self.tienda = self.tiendas[0] if self.tiendas else None
        self.foto: Optional[QImage] = None

        layout = QHBoxLayout(self)
        layout.setContentsMargins(18, 16, 18, 16)
        layout.setSpacing(16)

        # ---- la web ----
        izquierda = QVBoxLayout()
        izquierda.setSpacing(10)
        self._grupo = QButtonGroup(self)
        self._grupo.setExclusive(True)
        self.botones_tienda = []
        chips = QHBoxLayout()
        chips.setSpacing(8)
        for i, tienda in enumerate(self.tiendas):
            chip = chip_alternable(tienda.nombre)
            chip.setChecked(i == 0)
            chip.setToolTip(tienda.que)
            chip.clicked.connect(lambda _=False, t=tienda: self.ir_a(t))
            self._grupo.addButton(chip)
            self.botones_tienda.append(chip)
            chips.addWidget(chip)
        chips.addStretch()
        izquierda.addLayout(chips)
        self.navegador = crear_navegador(self.tienda.url, self) if self.tienda else None
        if self.navegador is not None:
            izquierda.addWidget(self.navegador, 1)
            self.setMinimumSize(1280, 780)
        else:
            sin = texto_suave("No se puede mostrar la web adentro de la app. Abri la tienda en tu navegador, elegi "
                              "lo que quieras y anota aca el nombre y el precio.")
            afuera = boton("Abrir la tienda en tu navegador", primario=True)
            afuera.clicked.connect(lambda: QDesktopServices.openUrl(QUrl(self.url_actual())))
            izquierda.addWidget(sin)
            izquierda.addLayout(fila(afuera, None))
            izquierda.addStretch()
        layout.addLayout(izquierda, 1)

        # ---- lo que se compra en el juego ----
        panel = QWidget()
        panel.setFixedWidth(ANCHO_PANEL)
        derecha = QVBoxLayout(panel)
        derecha.setContentsMargins(0, 0, 0, 0)
        derecha.setSpacing(10)
        derecha.addWidget(titulo_seccion("Lo que te compras"))
        derecha.addWidget(etiqueta_campo("Que es"))
        self.nombre_edit = QLineEdit()
        self.nombre_edit.setPlaceholderText("Ej: Rolex Daytona de oro")
        self.nombre_edit.setMaxLength(tiendas.LARGO_NOMBRE)
        derecha.addWidget(self.nombre_edit)
        derecha.addWidget(etiqueta_campo("Precio"))
        self.precio_spin = QSpinBox()
        self.precio_spin.setRange(0, PRECIO_MAXIMO)
        self.precio_spin.setSingleStep(1_000)
        self.precio_spin.setGroupSeparatorShown(True)
        self.precio_spin.setPrefix(f"{moneda} ")
        derecha.addWidget(self.precio_spin)
        self.leer_btn = boton("Leer de la pagina")
        self.leer_btn.setEnabled(self.navegador is not None)
        self.leer_btn.clicked.connect(self.leer_pagina)
        derecha.addLayout(fila(self.leer_btn, None))
        self.lectura_label = texto_suave()
        derecha.addWidget(self.lectura_label)
        niveles = QHBoxLayout()
        niveles.setSpacing(6)
        for rotulo, precio in tiendas.NIVELES.get(categoria, []):
            nivel = boton(rotulo)
            nivel.setToolTip(dinero(precio, moneda))
            nivel.setProperty("nivel", precio)
            nivel.clicked.connect(lambda _=False, p=precio: self.precio_spin.setValue(p))
            niveles.addWidget(nivel)
        derecha.addWidget(texto_suave("Si la pagina no dice el precio, un nivel:"))
        derecha.addLayout(niveles)

        derecha.addWidget(etiqueta_campo("La foto"))
        self.foto_label = QLabel()
        self.foto_label.setFixedHeight(150)
        self.foto_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.foto_label.setText(f"<span style='color:{estilos.TEXTO_SUAVE}'>Sin foto</span>")
        derecha.addWidget(self.foto_label)
        self.capturar_btn = boton("Capturar vista")
        self.capturar_btn.setEnabled(self.navegador is not None)
        self.capturar_btn.clicked.connect(self.capturar)
        derecha.addLayout(fila(self.capturar_btn, None))
        derecha.addStretch()
        self.saldo_label = texto_suave(f"Tenes {dinero(saldo, moneda)}")
        derecha.addWidget(self.saldo_label)
        cancelar = boton("Cancelar")
        cancelar.clicked.connect(self.reject)
        self.comprar_btn = boton("Comprar", primario=True)
        self.comprar_btn.clicked.connect(self.accept)
        derecha.addLayout(fila(None, cancelar, self.comprar_btn))
        layout.addWidget(panel)

        self.nombre_edit.textChanged.connect(self._refrescar)
        self.precio_spin.valueChanged.connect(self._refrescar)
        self._refrescar()

    # ---- la web ----

    def ir_a(self, tienda: tiendas.Tienda):
        self.tienda = tienda
        if self.navegador is not None:
            self.navegador.vista.load(QUrl(tienda.url))

    def url_actual(self) -> str:
        if self.navegador is not None:
            return self.navegador.vista.url().toString()
        return self.tienda.url if self.tienda else ""

    def leer_pagina(self):
        if self.navegador is None:
            return
        self.lectura_label.setText("Leyendo la pagina...")
        self.navegador.vista.page().runJavaScript(tiendas.SCRIPT_METADATOS, 0, self.on_metadatos)

    def on_metadatos(self, datos):
        lectura = tiendas.leer_metadatos(datos if isinstance(datos, dict) else None, self.moneda)
        if lectura.nombre and not self.nombre_edit.text().strip():
            self.nombre_edit.setText(lectura.nombre)
        if lectura.precio:
            self.precio_spin.setValue(min(lectura.precio, PRECIO_MAXIMO))
            self.lectura_label.setText(f"La pagina dice {esc(lectura.original)}: {dinero(lectura.precio, self.moneda)}")
        else:
            self.lectura_label.setText("La pagina no dice el precio: elegi un nivel o escribilo.")

    def capturar(self):
        if self.navegador is None:
            return
        recorte = RecortarFoto(self.navegador.foto(), self)
        recorte.setWindowTitle("La foto de tu compra")
        if recorte.exec() == QDialog.DialogCode.Accepted:
            self.poner_foto(recorte.resultado())
        recorte.deleteLater()

    def poner_foto(self, imagen: QImage):
        self.foto = imagen
        self.foto_label.setPixmap(QPixmap.fromImage(imagen).scaled(
            ANCHO_PANEL, 150, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))

    # ---- la compra ----

    def _refrescar(self):
        precio = self.precio_spin.value()
        alcanza = 0 < precio <= self.saldo
        self.comprar_btn.setEnabled(bool(self.nombre_edit.text().strip()) and alcanza)
        if precio > self.saldo:
            self.saldo_label.setText(f"Tenes {dinero(self.saldo, self.moneda)}: te faltan "
                                     f"{dinero(precio - self.saldo, self.moneda)}")
        else:
            self.saldo_label.setText(f"Tenes {dinero(self.saldo, self.moneda)}")

    def articulo(self) -> economia.Articulo:
        return economia.articulo_libre(self.categoria, self.nombre_edit.text(), self.precio_spin.value(),
                                       self.tienda.nombre if self.tienda else "")
