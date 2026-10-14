"""
Sala de prensa flotante: un panel semitransparente siempre encima del
juego (con FC 26 en "ventana sin bordes"), para hacer la entrevista sin
salir del partido. Se abre y se cierra con el atajo global (ui/atajo.py),
desde el icono de la bandeja, o sola al terminar un partido (modo en vivo).

No tiene logica propia: es un espejo de la sala de prensa. Muestra lo que
la sala tiene (partido, preguntas, respuestas, reaccion, noticias) y sus
botones llaman a los de la sala. Asi hay una sola entrevista, que se puede
seguir en cualquiera de las dos.

Se muestra sin quitarle el foco al juego (WA_ShowWithoutActivating).
"""

from PySide6.QtCore import QPoint, QRectF, Qt
from PySide6.QtGui import QColor, QGuiApplication, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import QLabel, QPlainTextEdit, QPushButton, QVBoxLayout, QWidget

from roleplay.ui import estilos
from roleplay.ui.atajo import ATAJO_TEXTO
from roleplay.ui.comun import esc
from roleplay.ui.componentes import boton, chip, fila, icono, limpiar_layout, texto_suave
from roleplay.ui.estilos import fuente_titulo

ANCHO = 440
MARGEN_PANTALLA = 24


class SalaFlotante(QWidget):
    def __init__(self, sala):
        super().__init__(
            None,
            Qt.WindowType.Tool | Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint,
        )
        self.setWindowTitle("EAFC 26 Roleplay - Sala flotante")
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self.setFixedWidth(ANCHO)
        self.sala = sala
        self._preguntas_mostradas: tuple = ()
        self._edits: list[QPlainTextEdit] = []
        self._voces: list[QPushButton] = []
        self._copiando = False  # evita el eco al copiar texto entre la sala y el panel
        self._arrastre: QPoint | None = None
        self._ubicado = False

        layout = QVBoxLayout(self)
        layout.setContentsMargins(22, 18, 22, 20)
        layout.setSpacing(10)

        titulo = QLabel("SALA DE PRENSA")
        titulo.setFont(fuente_titulo(24, 1))
        cerrar = QPushButton("✕")
        cerrar.setObjectName("cerrarFlotante")
        cerrar.setFixedSize(30, 30)
        cerrar.setToolTip(f"Esconder ({ATAJO_TEXTO})")
        cerrar.setStyleSheet(
            f"QPushButton#cerrarFlotante {{ background: transparent; border: none; color: {estilos.TEXTO_SUAVE};"
            f" font-size: 16px; padding: 0; }} QPushButton#cerrarFlotante:hover {{ color: {estilos.TEXTO}; }}"
        )
        cerrar.clicked.connect(self.hide)
        layout.addLayout(fila(titulo, None, chip(ATAJO_TEXTO, estilos.TEXTO_SUAVE), cerrar))

        self.partido_label = texto_suave()
        layout.addWidget(self.partido_label)

        self.cargar_btn = boton("Cargar partido", primario=True, icono_nombre="jugar")
        self.cargar_btn.clicked.connect(lambda: self.sala._on_cargar_partida_clicked())
        self.generar_btn = boton("Generar entrevista", icono_nombre="chispa")
        self.generar_btn.clicked.connect(lambda: self.sala._on_generar_entrevista_clicked())
        layout.addLayout(fila(self.cargar_btn, self.generar_btn, None))

        self.preguntas_layout = QVBoxLayout()
        self.preguntas_layout.setSpacing(14)
        layout.addLayout(self.preguntas_layout)

        self.enviar_btn = boton("Enviar respuestas", primario=True, icono_nombre="enviar")
        self.enviar_btn.clicked.connect(lambda: self.sala._on_enviar_respuestas_clicked())
        layout.addLayout(fila(None, self.enviar_btn))

        self.reaccion_label = QLabel()
        self.reaccion_label.setWordWrap(True)
        layout.addWidget(self.reaccion_label)

        self.noticias_label = QLabel()
        self.noticias_label.setWordWrap(True)
        layout.addWidget(self.noticias_label)

        sala.cambio.connect(self.refrescar)
        self.refrescar()

    # ---- aspecto y arrastre ----

    def paintEvent(self, _evento):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        forma = QPainterPath()
        forma.addRoundedRect(QRectF(self.rect()).adjusted(1, 1, -1, -1), 14, 14)
        fondo = QColor(estilos.FONDO)
        fondo.setAlpha(232)
        p.fillPath(forma, fondo)
        p.setPen(QPen(QColor(estilos.BORDE_FUERTE), 1))
        p.drawPath(forma)
        p.fillRect(QRectF(1, 18, 3, 40), QColor(estilos.ACENTO))
        p.end()

    def mousePressEvent(self, evento):
        if evento.button() == Qt.MouseButton.LeftButton:
            self._arrastre = evento.globalPosition().toPoint() - self.frameGeometry().topLeft()

    def mouseMoveEvent(self, evento):
        if self._arrastre is not None and evento.buttons() & Qt.MouseButton.LeftButton:
            self.move(evento.globalPosition().toPoint() - self._arrastre)

    def mouseReleaseEvent(self, _evento):
        self._arrastre = None

    def _ubicar(self):
        """La primera vez, arriba a la derecha de la pantalla principal."""
        pantalla = QGuiApplication.primaryScreen()
        if pantalla is not None:
            zona = pantalla.availableGeometry()
            self.move(zona.right() - ANCHO - MARGEN_PANTALLA, zona.top() + MARGEN_PANTALLA)
        self._ubicado = True

    def mostrar(self):
        if not self._ubicado:
            self._ubicar()
        self.refrescar()
        self.show()
        self.raise_()

    def alternar(self):
        if self.isVisible():
            self.hide()
        else:
            self.mostrar()

    # ---- espejo de la sala ----

    def _armar_preguntas(self):
        limpiar_layout(self.preguntas_layout)
        self._edits, self._voces = [], []
        for numero, pregunta in enumerate(self.sala._preguntas):
            texto = QLabel(f"<span style='color:{estilos.ACENTO}'><b>P{numero + 1}</b></span>&nbsp; {esc(pregunta)}")
            texto.setTextFormat(Qt.TextFormat.RichText)
            texto.setWordWrap(True)
            bloque = QVBoxLayout()
            bloque.setSpacing(6)
            bloque.addWidget(texto)

            edit = QPlainTextEdit()
            edit.setPlaceholderText("Tu respuesta...")
            edit.setFixedHeight(66)
            edit.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
            edit.textChanged.connect(lambda n=numero: self._on_texto(n))
            voz = boton("Voz", icono_nombre="microfono")
            voz.setObjectName("microfono")
            voz.clicked.connect(lambda _=False, n=numero: self.sala._on_voz_clicked(n))
            bloque.addLayout(fila(edit, voz, espaciado=8))
            self.preguntas_layout.addLayout(bloque)
            self._edits.append(edit)
            self._voces.append(voz)
        self._preguntas_mostradas = tuple(self.sala._preguntas)

    def _on_texto(self, numero: int):
        if self._copiando or numero >= len(self.sala._respuesta_edits):
            return
        self._copiando = True
        self.sala._respuesta_edits[numero].setPlainText(self._edits[numero].toPlainText())
        self._copiando = False

    def refrescar(self):
        if self._copiando:
            return
        sala = self.sala
        self.partido_label.setText(sala.partida_label.text())
        lectura = sala._lectura
        ya_cargado = (
            lectura is not None and lectura.ultimo is not None and sala._origen == "partida"
            and sala._fecha_juego == lectura.ultimo.partido.fecha.isoformat()
        )
        self.cargar_btn.setVisible(sala.cargar_partida_btn.isEnabled() and not ya_cargado)
        self.generar_btn.setEnabled(sala.generar_entrevista_btn.isEnabled())
        self.generar_btn.setText(sala.generar_entrevista_btn.text())

        if tuple(sala._preguntas) != self._preguntas_mostradas:
            self._armar_preguntas()
        self._copiando = True
        for edit, original in zip(self._edits, sala._respuesta_edits):
            texto = original.toPlainText()
            if edit.toPlainText() != texto and not edit.hasFocus():
                edit.setPlainText(texto)
        self._copiando = False
        for voz, original in zip(self._voces, sala._botones_voz):
            grabando = bool(original.property("grabando"))
            voz.setEnabled(original.isEnabled())
            voz.setText("DETENER" if grabando else ("..." if "TRANSCRIB" in original.text() else "VOZ"))
            if voz.property("grabando") != grabando:
                voz.setProperty("grabando", grabando)
                voz.setIcon(icono("detener" if grabando else "microfono", "#FFFFFF" if grabando else estilos.TEXTO))
                voz.style().unpolish(voz)
                voz.style().polish(voz)

        self.enviar_btn.setVisible(bool(sala._preguntas))
        self.enviar_btn.setEnabled(sala.enviar_respuestas_btn.isEnabled())
        self.enviar_btn.setText(sala.enviar_respuestas_btn.text())

        if sala.reaccion_tarjeta.isVisibleTo(sala):
            self.reaccion_label.setText(
                f"<span style='color:{estilos.ACENTO}'><b>Reaccion:</b></span> {sala.reaccion_label.text()}"
            )
            self.reaccion_label.show()
        else:
            self.reaccion_label.hide()

        if sala.ultimas_noticias:
            self.noticias_label.setText(
                "<br>".join(
                    f"<span style='color:{estilos.SECUNDARIO}'>▸</span> {esc(n.titular)}" for n in sala.ultimas_noticias
                )
            )
            self.noticias_label.show()
        else:
            self.noticias_label.hide()
        self.adjustSize()
