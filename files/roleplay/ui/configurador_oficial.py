"""
El configurador oficial nativo (servicios/configurador.py): el render de la marca en grande, las opciones
reales (circulos con el color exacto de cada pintura, llantas, interior, asientos, paquetes) y el desglose
precio base + opcionales = precio final de encargo. Lo abre Vida en lugar del configurador de siempre cuando
hay catalogo oficial del modelo (solo en el PC de Simon).
"""

from typing import Optional

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QImage, QPainter, QPixmap
from PySide6.QtWidgets import (
    QComboBox, QDialog, QGridLayout, QHBoxLayout, QLabel, QPushButton, QScrollArea, QVBoxLayout, QWidget,
)

from roleplay.servicios import autos, configurador
from roleplay.servicios.economia import dinero
from roleplay.ui import estilos
from roleplay.ui.comun import ejecutar_en_hilo, esc
from roleplay.ui.componentes import boton, etiqueta_campo, fila, texto_suave, titulo_seccion

COLUMNAS_COLORES = 8


class DialogoConfiguradorOficial(QDialog):
    def __init__(self, modelo: autos.Modelo, catalogo: dict, saldo: int, moneda: str, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setWindowTitle(f"EAFC 26 Roleplay - {modelo.nombre_completo}")
        self.modelo, self.catalogo, self.saldo, self.moneda = modelo, catalogo, saldo, moneda
        self.eleccion = configurador.de_fabrica(catalogo)
        self.foto: Optional[QImage] = None
        self._pedido_render = 0
        self._botones_color: dict = {}
        self._combos: dict = {}

        raiz = QHBoxLayout(self)
        izquierda = QVBoxLayout()
        izquierda.addWidget(titulo_seccion(f"{modelo.marca} · {catalogo.get('modelo', modelo.nombre)} {catalogo.get('anio', '')}"))
        self.render_label = QLabel("Cargando el render oficial...")
        self.render_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.render_label.setMinimumSize(720, 405)
        izquierda.addWidget(self.render_label, 1)
        self.precio_label = QLabel()
        self.precio_label.setWordWrap(True)
        izquierda.addWidget(self.precio_label)
        raiz.addLayout(izquierda, 3)

        panel = QWidget()
        opciones = QVBoxLayout(panel)
        for (seccion, categoria), ops in configurador.opciones_por_categoria(catalogo).items():
            opciones.addWidget(etiqueta_campo(f"{configurador.SECCIONES[seccion]} · {categoria}"))
            clave = f"{seccion}|{categoria}"
            if seccion == "section-exterior-color":  # la pintura: circulos con el color real de la marca
                grilla = QGridLayout()
                for n, op in enumerate(ops):
                    circulo = QPushButton()
                    circulo.setFixedSize(30, 30)
                    circulo.setToolTip(f"{op['nombre']} · {self._dinero(op['precio'])}")
                    circulo.clicked.connect(lambda _=False, c=clave, i=op["id"]: self._elegir(c, i))
                    self._botones_color.setdefault(clave, []).append((op["id"], op["hex"], circulo))
                    grilla.addWidget(circulo, n // COLUMNAS_COLORES, n % COLUMNAS_COLORES)
                opciones.addLayout(grilla)
                self._pintar_circulos(clave)
            else:
                combo = QComboBox()
                combo.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon)
                combo.setMinimumContentsLength(24)  # los nombres largos de Porsche no ensanchan el panel
                combo.addItem("Como viene de fabrica", "")
                for op in ops:
                    combo.addItem(f"{op['nombre']} · {self._dinero(op['precio'])}", op["id"])
                actual = self.eleccion.opciones.get(clave, "")
                combo.setCurrentIndex(max(0, combo.findData(actual)))
                combo.currentIndexChanged.connect(lambda _=0, c=clave, w=combo: self._elegir(c, w.currentData()))
                self._combos[clave] = combo
                opciones.addWidget(combo)
        opciones.addStretch()
        desplazable = QScrollArea()
        desplazable.setWidgetResizable(True)
        desplazable.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        desplazable.setWidget(panel)
        derecha = QVBoxLayout()
        derecha.addWidget(texto_suave("Las opciones y los precios del configurador oficial de la marca (mercado UK)."))
        derecha.addWidget(desplazable, 1)
        self.encargar_btn = boton("Encargar", primario=True)
        self.encargar_btn.clicked.connect(self._encargar)
        cancelar = boton("Cancelar")
        cancelar.clicked.connect(self.reject)
        derecha.addLayout(fila(None, cancelar, self.encargar_btn))
        raiz.addLayout(derecha, 2)
        self.resize(1500, 860)
        self._actualizar()

    def _dinero(self, monto) -> str:
        return dinero(int(monto or 0), self.moneda) if monto else "de serie"

    def _pintar_circulos(self, clave: str):
        elegido = self.eleccion.opciones.get(clave)
        for op_id, hex_, circulo in self._botones_color.get(clave, []):
            borde = estilos.ACENTO if op_id == elegido else "#3A4452"
            # Paint to Sample no trae un color: el que quieras (un degradado)
            fondo = hex_ or "qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #C0392B, stop:0.5 #F1C40F, stop:1 #2E86C1)"
            circulo.setStyleSheet(f"QPushButton {{ background: {fondo}; border: 3px solid {borde}; border-radius: 15px; }}")

    def _elegir(self, clave: str, opcion_id: str):
        configurador.elegir(self.eleccion, clave, opcion_id)
        for otra in self._botones_color:
            self._pintar_circulos(otra)
        for otra, combo in self._combos.items():  # una sola llanta: la otra lista vuelve a "de fabrica"
            combo.blockSignals(True)
            combo.setCurrentIndex(max(0, combo.findData(self.eleccion.opciones.get(otra, ""))))
            combo.blockSignals(False)
        self._actualizar()

    def _actualizar(self):
        base, extra = int(self.catalogo.get("base") or 0), configurador.opcionales(self.catalogo, self.eleccion)
        total = base + extra
        detalle = "".join(f"<br>· {esc(n)}: {self._dinero(p)}" for _, n, p in
                          configurador.resumen(configurador.ficha(self.catalogo, self.eleccion)) if p)
        alcanza = total <= self.saldo
        self.precio_label.setText(
            f"Precio base {dinero(base, self.moneda)} + opcionales {dinero(extra, self.moneda)} = "
            f"<b style='color:{estilos.ACENTO if alcanza else estilos.NEGATIVO}'>{dinero(total, self.moneda)}</b>"
            f" (precio final de encargo){detalle}" + ("" if alcanza else "<br>No te alcanza con tu saldo."))
        self.encargar_btn.setEnabled(alcanza)
        self._pedido_render += 1
        ejecutar_en_hilo(configurador.render, self.catalogo, configurador.Eleccion(self.eleccion.codigo,
                                                                                   dict(self.eleccion.opciones)),
                         al_completar=self._on_render, al_fallar=self._on_render_error)

    def _on_render(self, ruta):
        if ruta is None:
            self.render_label.setText("Sin internet: el render llega cuando haya conexion.")
            return
        imagen = QImage(str(ruta))
        fondo = QImage(imagen.size(), QImage.Format.Format_RGB32)
        fondo.fill(QColor(estilos.FONDO))
        pintor = QPainter(fondo)
        pintor.drawImage(0, 0, imagen)
        pintor.end()
        self.foto = fondo  # la del garage (sin transparencia)
        self.render_label.setPixmap(QPixmap.fromImage(fondo).scaled(
            self.render_label.size(), Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))

    def _on_render_error(self, mensaje: str):
        self.render_label.setText(f"No se pudo cargar el render ({mensaje}).")

    def _encargar(self):
        self.accept()

    def configuracion(self) -> autos.Configuracion:
        return autos.Configuracion(modelo=self.modelo.id, oficial=configurador.ficha(self.catalogo, self.eleccion))
