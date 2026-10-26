"""
El configurador oficial nativo (servicios/configurador.py), armado como la pagina de la marca: el auto en grande
con el render oficial (se gira arrastrando o con las flechas, con los fondos de la pagina y de noche), las vistas
de la llanta y del interior, y a la derecha las pestanas de la pagina (color, llantas, interior, asientos,
paquetes...) con la foto de cada opcion, su precio y su descripcion. Abajo, precio base + opcionales = precio final
de encargo. Lo abre Vida en lugar del configurador de siempre cuando hay catalogo oficial del modelo (solo en el PC
de Simon).
"""

from typing import Optional

from PySide6.QtCore import QSize, Qt, Signal
from PySide6.QtGui import QImage, QPixmap
from PySide6.QtWidgets import (
    QDialog, QGridLayout, QHBoxLayout, QLabel, QPushButton, QScrollArea, QStackedWidget, QTabBar, QVBoxLayout,
    QWidget,
)

from roleplay.servicios import autos, configurador
from roleplay.servicios.economia import dinero
from roleplay.ui import estilos
from roleplay.ui.comun import ejecutar_en_hilo, esc
from roleplay.ui.componentes import boton, chip_alternable, etiqueta_campo, fila, texto_suave, titulo_seccion

PASO_GIRO_PX = 70  # cuanto hay que arrastrar para pasar a la vista de al lado
COLUMNAS_COLORES = 9
FOTO_OPCION = QSize(184, 104)
BORDE = "#2A3340"


def _render(token: int, modelo: dict, eleccion: configurador.Eleccion, camara: str, entorno: str, noche: bool):
    return token, configurador.render(modelo, eleccion, camara, entorno, noche)


class Escenario(QLabel):
    """El auto en grande: guarda la imagen original y la escala al tamano; arrastrar de costado lo gira."""
    girar = Signal(int)

    def __init__(self):
        super().__init__("Cargando el render oficial...")
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setMinimumSize(640, 360)
        self.setCursor(Qt.CursorShape.OpenHandCursor)
        self.imagen: Optional[QImage] = None
        self._desde: Optional[int] = None

    def mostrar(self, imagen: QImage):
        self.imagen = imagen
        self._escalar()

    def _escalar(self):
        if self.imagen is not None:
            self.setPixmap(QPixmap.fromImage(self.imagen).scaled(
                self.size(), Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))

    def resizeEvent(self, evento):
        super().resizeEvent(evento)
        self._escalar()

    def mousePressEvent(self, evento):
        self._desde = int(evento.position().x())
        self.setCursor(Qt.CursorShape.ClosedHandCursor)

    def mouseMoveEvent(self, evento):
        if self._desde is None:
            return
        x = int(evento.position().x())
        pasos = int((x - self._desde) / PASO_GIRO_PX)
        if pasos:
            self._desde += pasos * PASO_GIRO_PX
            self.girar.emit(-pasos)  # arrastrar a la izquierda muestra el costado siguiente, como en la pagina

    def mouseReleaseEvent(self, evento):
        self._desde = None
        self.setCursor(Qt.CursorShape.OpenHandCursor)


class Ficha(QPushButton):
    """Una opcion como en la pagina: la foto, el nombre y el precio; con borde de color si esta elegida."""

    def __init__(self, op: dict, precio: str):
        super().__init__()
        con_foto = bool(op.get("miniatura"))  # (Aston Martin no da fotos de las opciones: queda el nombre)
        self.setFixedSize(FOTO_OPCION.width() + 16, (FOTO_OPCION.height() if con_foto else 0) + 74)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        caja = QVBoxLayout(self)
        caja.setContentsMargins(8, 8, 8, 8)
        caja.setSpacing(4)
        self.foto = QLabel("···")
        self.foto.setFixedSize(FOTO_OPCION)
        self.foto.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.foto.setStyleSheet(f"background: {estilos.FONDO}; border-radius: 4px; color: {estilos.TEXTO_SUAVE};")
        nombre = QLabel(op["nombre"])
        nombre.setWordWrap(True)
        nombre.setMaximumHeight(34)
        valor = QLabel(precio)
        valor.setObjectName("suave")
        for etiqueta in (self.foto, nombre, valor):
            etiqueta.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
            caja.addWidget(etiqueta)
        self.foto.setVisible(con_foto)
        caja.addStretch()
        self.setToolTip(op["nombre"])

    def poner_foto(self, ruta):
        imagen = QPixmap(str(ruta))
        if not imagen.isNull():
            self.foto.setPixmap(imagen.scaled(FOTO_OPCION, Qt.AspectRatioMode.KeepAspectRatio,
                                              Qt.TransformationMode.SmoothTransformation))

    def marcar(self, elegida: bool):
        borde = estilos.ACENTO if elegida else BORDE
        self.setStyleSheet(f"QPushButton {{ background: {estilos.PANEL}; border: 2px solid {borde}; border-radius: 6px; }}"
                           f"QPushButton:hover {{ border-color: {estilos.ACENTO}; }}")


class DialogoConfiguradorOficial(QDialog):
    def __init__(self, modelo: autos.Modelo, catalogo: dict, saldo: int, moneda: str, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setWindowTitle(f"EAFC 26 Roleplay - {modelo.nombre_completo}")
        self.modelo, self.catalogo, self.saldo, self.moneda = modelo, catalogo, saldo, moneda
        self.eleccion = configurador.de_fabrica(catalogo)
        self.secciones = configurador.opciones_por_seccion(catalogo)
        self.foto: Optional[QImage] = None  # la del garage: la ultima vista de afuera
        self._giro = configurador.giro(catalogo)  # las camaras alrededor del auto de esta marca
        self.giro, self.camara_extra = configurador.giro_inicial(catalogo), None  # adelante a la izquierda
        self.entorno, self.noche = next(iter(configurador.entornos(catalogo))), False
        self._token = 0
        self._fichas: dict = {}  # id -> Ficha
        self._circulos: dict = {}  # id -> (boton, hex)
        self._paginas: dict = {}  # seccion -> indice en el stack (se arman al abrirlas)

        raiz = QVBoxLayout(self)
        arriba = QHBoxLayout()
        arriba.addWidget(titulo_seccion(f"{modelo.marca} · {catalogo.get('modelo', modelo.nombre)} {catalogo.get('anio') or ''}"))
        arriba.addStretch()
        self._botones_entorno = {}
        for entorno, nombre in configurador.entornos(catalogo).items():
            b = chip_alternable(nombre)
            b.clicked.connect(lambda _=False, e=entorno: self._cambiar_entorno(e))
            self._botones_entorno[entorno] = b
            arriba.addWidget(b)
        self.noche_btn = chip_alternable("Noche")
        self.noche_btn.clicked.connect(self._cambiar_noche)
        arriba.addWidget(self.noche_btn)
        raiz.addLayout(arriba)

        cuerpo = QHBoxLayout()
        izquierda = QVBoxLayout()
        self.escenario = Escenario()
        self.escenario.girar.connect(self._girar)
        izquierda.addWidget(self.escenario, 1)
        vistas = QHBoxLayout()
        anterior, siguiente = boton("‹"), boton("›")
        anterior.clicked.connect(lambda: self._girar(-1))
        siguiente.clicked.connect(lambda: self._girar(1))
        self._botones_vista = {}
        vistas.addWidget(anterior)
        exterior = chip_alternable("Exterior")
        exterior.clicked.connect(lambda: self._ver(None))
        self._botones_vista[None] = exterior
        vistas.addWidget(exterior)
        for camara, nombre in configurador.vistas_extra(catalogo):
            b = chip_alternable(nombre)
            b.clicked.connect(lambda _=False, c=camara: self._ver(c))
            self._botones_vista[camara] = b
            vistas.addWidget(b)
        vistas.addStretch()
        self.estado = texto_suave("", ajustar=False)
        vistas.addWidget(self.estado)
        vistas.addWidget(siguiente)
        izquierda.addLayout(vistas)
        izquierda.addWidget(texto_suave("Arrastra el auto (o usa las flechas) para girarlo."))
        cuerpo.addLayout(izquierda, 1)

        derecha = QVBoxLayout()
        self.pestanas = QTabBar()
        self.pestanas.setExpanding(False)
        self.pestanas.setUsesScrollButtons(True)
        for seccion in self.secciones:
            self.pestanas.addTab(configurador.SECCIONES[seccion].upper())
        derecha.addWidget(self.pestanas)
        self.stack = QStackedWidget()
        derecha.addWidget(self.stack, 1)
        self.detalle = QLabel()
        self.detalle.setWordWrap(True)
        self.detalle.setTextFormat(Qt.TextFormat.RichText)
        self.detalle.setMaximumHeight(150)
        self.detalle.setAlignment(Qt.AlignmentFlag.AlignTop)
        derecha.addWidget(self.detalle)
        panel = QWidget()
        panel.setLayout(derecha)
        panel.setFixedWidth(2 * (FOTO_OPCION.width() + 16) + 60)
        cuerpo.addWidget(panel)
        raiz.addLayout(cuerpo, 1)

        self.precio_label = QLabel()
        self.encargar_btn = boton("Encargar", primario=True)
        self.encargar_btn.clicked.connect(self.accept)
        cancelar = boton("Cancelar")
        cancelar.clicked.connect(self.reject)
        raiz.addLayout(fila(self.precio_label, None, cancelar, self.encargar_btn))
        self.resize(1600, 900)
        self._marcar_botones()
        self._actualizar_precio()
        self.pestanas.currentChanged.connect(self._abrir_seccion)
        self._abrir_seccion(0)
        if self._token == 0:  # la primera seccion no movio la camara: igual hay que mostrar el auto
            self._pedir_render()

    # ---- las opciones ----

    def _dinero(self, monto) -> str:
        return dinero(int(monto or 0), self.moneda) if monto else "De serie"

    def _abrir_seccion(self, indice: int):
        if indice < 0 or indice >= len(self.secciones):
            return
        seccion = list(self.secciones)[indice]
        if seccion not in self._paginas:
            self._paginas[seccion] = self.stack.addWidget(self._pagina(seccion))
        self.stack.setCurrentIndex(self._paginas[seccion])
        camara = configurador.camara_de_seccion(self.catalogo, seccion)  # como la pagina: llantas -> la llanta
        if camara:
            en_el_giro = [i for i, (c, espejo) in enumerate(self._giro) if c == camara and not espejo]
            if en_el_giro:
                self.giro, self.camara_extra = en_el_giro[0], None
            else:
                self.camara_extra = camara
            self._marcar_botones()
            self._pedir_render()

    def _pagina(self, seccion: str) -> QWidget:
        contenido = QWidget()
        caja = QVBoxLayout(contenido)
        con_fotos = []
        for categoria, ops in self.secciones[seccion].items():
            caja.addWidget(etiqueta_campo(categoria))
            grilla = QGridLayout()
            grilla.setSpacing(8)
            if seccion == "section-exterior-color":  # la pintura: circulos con el color real, como la pagina
                for n, op in enumerate(ops):
                    circulo = QPushButton()
                    circulo.setFixedSize(34, 34)
                    circulo.setCursor(Qt.CursorShape.PointingHandCursor)
                    circulo.setToolTip(f"{op['nombre']} · {self._dinero(op['precio'])}")
                    circulo.clicked.connect(lambda _=False, i=op["id"]: self._elegir(i))
                    self._circulos[op["id"]] = (circulo, op["hex"])
                    grilla.addWidget(circulo, n // COLUMNAS_COLORES, n % COLUMNAS_COLORES)
            else:
                for n, op in enumerate(ops):
                    ficha = Ficha(op, self._dinero(op["precio"]))
                    ficha.clicked.connect(lambda _=False, i=op["id"]: self._elegir(i))
                    self._fichas[op["id"]] = ficha
                    grilla.addWidget(ficha, n // 2, n % 2)
                    if op.get("miniatura"):
                        con_fotos.append(op["id"])
            caja.addLayout(grilla)
        caja.addStretch()
        self._marcar_opciones()
        if con_fotos:
            ejecutar_en_hilo(configurador.miniaturas, self.catalogo, con_fotos,
                             al_completar=self._on_miniaturas, al_fallar=self._sin_miniaturas)
        desplazable = QScrollArea()
        desplazable.setWidgetResizable(True)
        desplazable.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        desplazable.setWidget(contenido)
        return desplazable

    def _on_miniaturas(self, rutas: dict):
        for op_id, ruta in rutas.items():
            if op_id in self._fichas:
                self._fichas[op_id].poner_foto(ruta)

    def _sin_miniaturas(self, _mensaje: str):
        pass  # sin internet quedan sin foto; el nombre y el precio estan igual

    def _marcar_opciones(self):
        elegidas = set(self.eleccion.ids())
        for op_id, ficha in self._fichas.items():
            ficha.marcar(op_id in elegidas)
        for op_id, (circulo, hex_) in self._circulos.items():
            borde = estilos.ACENTO if op_id in elegidas else BORDE
            # Paint to Sample no trae un color: el que quieras (un degradado)
            fondo = hex_ or "qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #C0392B, stop:0.5 #F1C40F, stop:1 #2E86C1)"
            circulo.setStyleSheet(f"QPushButton {{ background: {fondo}; border: 3px solid {borde}; border-radius: 17px; }}")

    def _elegir(self, opcion_id: str):
        op = next(o for o in self.catalogo["opciones"] if o["id"] == opcion_id)
        cambio = configurador.elegir(self.catalogo, self.eleccion, opcion_id)
        texto = configurador.descripcion(op)
        if len(texto) > 420:
            texto = texto[:420].rsplit(" ", 1)[0] + "..."
        nota = " · de serie, no se saca" if configurador.bloqueada(op) else ""
        self.detalle.setText(f"<b>{esc(op['nombre'])}</b> · {esc(self._dinero(op['precio']))}{nota}"
                             f"<br><span style='color:{estilos.TEXTO_SUAVE}'>{esc(texto).replace(chr(10), '<br>')}</span>")
        if cambio:
            self._marcar_opciones()
            self._actualizar_precio()
            self._pedir_render()

    def _actualizar_precio(self):
        base, extra = int(self.catalogo.get("base") or 0), configurador.opcionales(self.catalogo, self.eleccion)
        total = base + extra
        alcanza = total <= self.saldo
        self.precio_label.setText(
            f"Precio base {dinero(base, self.moneda)} + opcionales {dinero(extra, self.moneda)} = "
            f"<b style='color:{estilos.ACENTO if alcanza else estilos.NEGATIVO}'>{dinero(total, self.moneda)}</b>"
            f" (precio final de encargo)" + ("" if alcanza else " · No te alcanza con tu saldo.")
            + (f"<br><span style='color:{estilos.TEXTO_SUAVE}'>{esc(self.modelo.marca)} no publica los precios de los "
               "opcionales: son estimados.</span>" if self.catalogo.get("precios_estimados") else ""))
        detalle = configurador.resumen(configurador.ficha(self.catalogo, self.eleccion))
        self.precio_label.setToolTip("\n".join(f"{n}: {self._dinero(p)}" for _, n, p in detalle if p))
        self.encargar_btn.setEnabled(alcanza)

    # ---- el auto ----

    def _camara(self) -> tuple:
        if self.camara_extra:
            return self.camara_extra, False
        return self._giro[self.giro]

    def _girar(self, pasos: int):
        if self.camara_extra is None:
            self.giro = (self.giro + pasos) % len(self._giro)
        self.camara_extra = None
        self._marcar_botones()
        self._pedir_render()

    def _ver(self, camara: Optional[str]):
        self.camara_extra = camara
        self._marcar_botones()
        self._pedir_render()

    def _cambiar_entorno(self, entorno: str):
        self.entorno = entorno
        self._marcar_botones()
        self._pedir_render()

    def _cambiar_noche(self):
        self.noche = not self.noche
        self._marcar_botones()
        self._pedir_render()

    def _marcar_botones(self):
        for entorno, b in self._botones_entorno.items():
            b.setChecked(entorno == self.entorno)
        self.noche_btn.setChecked(self.noche)
        for camara, b in self._botones_vista.items():
            b.setChecked(camara == self.camara_extra)

    def _pedir_render(self):
        self._token += 1
        camara, _ = self._camara()
        self.estado.setText("Cargando...")
        eleccion = configurador.Eleccion(self.eleccion.codigo, dict(self.eleccion.opciones))
        if configurador.proveedor(self.catalogo) == "ferrari":
            self._pedir_a_ferrari(self._token, eleccion, camara)
            return
        ejecutar_en_hilo(_render, self._token, self.catalogo, eleccion, camara, self.entorno, self.noche,
                         al_completar=self._on_render, al_fallar=self._on_render_error)

    def _pedir_a_ferrari(self, token: int, eleccion, camara: str):
        """Ferrari solo le contesta a su pagina: la imagen se pide por el navegador de la app (ui/puente_web.py)."""
        guardada = configurador.render(self.catalogo, eleccion, camara, noche=self.noche)
        if guardada is not None:
            self._on_render((token, guardada))
            return
        from roleplay.ui.puente_web import puente

        noche = self.noche
        self.estado.setText("Ferrari esta dibujando tu auto...")
        puente(configurador.PAGINA_FERRARI).ejecutar(
            configurador.js_imagen_ferrari(self.catalogo, eleccion, camara, noche),
            lambda b64: self._on_render((token, configurador.guardar_imagen_ferrari(
                self.catalogo, eleccion, camara, noche, b64))))

    def _on_render(self, resultado):
        token, ruta = resultado
        if token != self._token:
            return  # llego tarde: ya se pidio otra vista (igual quedo guardada para la proxima)
        if ruta is None:
            self.estado.setText("Esta vista no esta disponible (o no hay internet).")
            return
        self.estado.setText("")
        camara, espejo = self._camara()
        imagen = QImage(str(ruta))
        if espejo:
            imagen = imagen.mirrored(True, False)
        self.escenario.mostrar(imagen)
        if not configurador.es_de_interior(camara) and not espejo:  # la del garage: una de afuera
            self.foto = imagen

    def _on_render_error(self, mensaje: str):
        self.estado.setText(f"No se pudo cargar el render ({mensaje}).")

    def keyPressEvent(self, evento):
        if evento.key() in (Qt.Key.Key_Left, Qt.Key.Key_Right):
            self._girar(-1 if evento.key() == Qt.Key.Key_Left else 1)
        else:
            super().keyPressEvent(evento)

    def configuracion(self) -> autos.Configuracion:
        return autos.Configuracion(modelo=self.modelo.id, oficial=configurador.ficha(self.catalogo, self.eleccion))
