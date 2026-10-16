"""
Sala de prensa flotante: un panel semitransparente siempre encima del
juego (con FC 26 en "ventana sin bordes"), para hacer la entrevista sin
salir del partido. Se abre y se cierra con el atajo global (ui/atajo.py),
desde el icono de la bandeja, o sola al terminar un partido (modo en vivo).

No tiene logica propia: es un espejo de la sala de prensa. Muestra lo que
la sala tiene (partido, preguntas, respuestas, reaccion, noticias) y sus
botones llaman a los de la sala. Asi hay una sola entrevista, que se puede
seguir en cualquiera de las dos.

Dos modos (bimodal):
- HUD pasivo: deja pasar mouse y teclado al juego (WindowTransparentForInput)
  y no le saca el foco; muestra los avisos (partido nuevo, noticias, el auto
  que llego...) y "[Ctrl+Shift+F12] Interactuar". Si estaba escondida, un
  aviso la muestra compacta (solo el aviso) y se vuelve a esconder sola.
- Interactivo: el atajo le quita el "pasar los clicks", toma el foco para
  escribir y, al volver a apretarlo (o "Volver al juego"), vuelve al HUD y le
  devuelve el foco a la ventana que estaba al frente (el juego) con
  SetForegroundWindow.
Sin el atajo (otra app lo tomo) nunca deja pasar los clicks: si no, no
habria como volver a usarla.
"""

import ctypes
import sys

from PySide6.QtCore import QPoint, QRectF, Qt, QTimer
from PySide6.QtGui import QColor, QGuiApplication, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import QLabel, QPlainTextEdit, QPushButton, QVBoxLayout, QWidget

from roleplay.ui import estilos
from roleplay.ui.atajo import ATAJO_TEXTO
from roleplay.ui.comun import esc
from roleplay.ui.componentes import boton, chip_alternable, fila, icono, limpiar_layout, texto_suave
from roleplay.ui.estilos import fuente_titulo

ANCHO = 440
MARGEN_PANTALLA = 24
AVISO_MS = 9000  # cuanto dura un aviso en el HUD


def _es_windows() -> bool:
    return sys.platform == "win32" and QGuiApplication.platformName() == "windows"


def _ventana_al_frente() -> int:
    return int(ctypes.windll.user32.GetForegroundWindow() or 0) if _es_windows() else 0


def _poner_al_frente(hwnd: int) -> None:
    if hwnd and _es_windows() and ctypes.windll.user32.IsWindow(hwnd):
        ctypes.windll.user32.SetForegroundWindow(hwnd)


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
        self._textos: list[QLabel] = []
        self._edits: list[QPlainTextEdit] = []
        self._voces: list[QPushButton] = []
        self._copiando = False  # evita el eco al copiar texto entre la sala y el panel
        self._arrastre: QPoint | None = None
        self._ubicado = False
        self.click_a_traves = True  # el menu lo apaga si no pudo registrar el atajo
        self.interactivo = False
        self._ventana_juego = 0  # la que estaba al frente antes de interactuar
        self._solo_aviso = False  # se mostro solo por un aviso: compacta y se esconde sola
        self._timer_aviso = QTimer(self)
        self._timer_aviso.setSingleShot(True)
        self._timer_aviso.timeout.connect(self._fin_aviso)

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
        cerrar.clicked.connect(self._cerrar)
        self.modo_label = QLabel()
        self.modo_label.setStyleSheet(f"color: {estilos.TEXTO_SUAVE};")
        layout.addLayout(fila(titulo, None, self.modo_label, cerrar))

        self.aviso_label = QLabel()
        self.aviso_label.setWordWrap(True)
        self.aviso_label.setTextFormat(Qt.TextFormat.RichText)
        self.aviso_label.hide()
        layout.addWidget(self.aviso_label)

        # todo lo de la entrevista (en un aviso suelto queda escondido)
        self.cuerpo = QWidget()
        principal, layout = layout, QVBoxLayout(self.cuerpo)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)
        principal.addWidget(self.cuerpo)

        # despues del partido / previa del proximo: los mismos modos de la sala
        self.modo_post_btn = chip_alternable("Post-partido")
        self.modo_previa_btn = chip_alternable("Previa")
        self.modo_post_btn.clicked.connect(lambda: self._elegir_modo("post"))
        self.modo_previa_btn.clicked.connect(lambda: self._elegir_modo("previa"))
        layout.addLayout(fila(self.modo_post_btn, self.modo_previa_btn, espaciado=8, estirar_al_final=True))

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

        self.volver_btn = boton("Volver al juego", icono_nombre="jugar")
        self.volver_btn.clicked.connect(self.modo_hud)
        layout.addLayout(fila(None, self.volver_btn))

        sala.cambio.connect(self.refrescar)
        self._aplicar_modo(False)
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

    # ---- los dos modos ----

    def deja_pasar_clicks(self) -> bool:
        return bool(self.windowFlags() & Qt.WindowType.WindowTransparentForInput)

    def _aplicar_modo(self, interactivo: bool):
        self.interactivo = interactivo
        pasar = not interactivo and self.click_a_traves
        if self.deja_pasar_clicks() != pasar:
            visible = self.isVisible()
            self.setWindowFlag(Qt.WindowType.WindowTransparentForInput, pasar)  # (esconde la ventana)
            if visible:
                self.show()
        if not self.click_a_traves:
            self.modo_label.setText("")
        else:
            self.modo_label.setText(f"[{ATAJO_TEXTO}] " + ("Volver al juego" if interactivo else "Interactuar"))
        self.volver_btn.setVisible(interactivo)

    def _preparar(self):
        if not self._ubicado:
            self._ubicar()
        self._solo_aviso = False
        self.cuerpo.show()
        self.refrescar()

    def mostrar(self):
        """En HUD (modo en vivo, al terminar un partido): sin quitarle el foco al juego."""
        if not self.isVisible():
            self._aplicar_modo(False)
        self._preparar()
        self.show()
        self.raise_()

    def modo_interactivo(self):
        if not (self.isVisible() and self.interactivo):
            al_frente = _ventana_al_frente()
            if al_frente and al_frente != int(self.winId()):
                self._ventana_juego = al_frente
        self._aplicar_modo(True)
        self._preparar()
        self.show()
        self.raise_()
        self.activateWindow()
        _poner_al_frente(int(self.winId()))

    def modo_hud(self):
        """Vuelve a dejar pasar los clicks y le devuelve el foco al juego."""
        self._aplicar_modo(False)
        _poner_al_frente(self._ventana_juego)

    def atajo_presionado(self):
        if self.isVisible() and self.interactivo:
            self.modo_hud()
        else:
            self.modo_interactivo()

    def alternar(self):
        """Desde la bandeja: la abre para usarla, o la esconde."""
        if self.isVisible():
            self._cerrar()
        else:
            self.modo_interactivo()

    def _cerrar(self):
        volver = self.interactivo
        self.hide()
        self._aplicar_modo(False)
        if volver:
            _poner_al_frente(self._ventana_juego)

    def avisar(self, titulo: str, texto: str = ""):
        """Un aviso en el HUD. Si estaba escondida, se muestra compacta (solo
        el aviso, sin quitarle el foco al juego) y se esconde sola."""
        self.aviso_label.setText(
            f"<span style='color:{estilos.ACENTO}'><b>{esc(titulo.upper())}</b></span>"
            + (f"<br>{esc(texto)}" if texto else "")
        )
        self.aviso_label.show()
        if not self.isVisible():
            self.mostrar()
            self._solo_aviso = True
            self.cuerpo.hide()
        self.adjustSize()
        self._timer_aviso.start(AVISO_MS)

    def _fin_aviso(self):
        self.aviso_label.hide()
        if self._solo_aviso and not self.interactivo:
            self.hide()
        self._solo_aviso = False
        self.cuerpo.show()
        self.adjustSize()

    # ---- espejo de la sala ----

    def _elegir_modo(self, modo: str):
        boton_sala = self.sala.modo_post_btn if modo == "post" else self.sala.modo_previa_btn
        if boton_sala.isEnabled():
            boton_sala.click()  # la sala decide; el panel se entera por `cambio`
        self.refrescar()

    def _armar_preguntas(self):
        limpiar_layout(self.preguntas_layout)
        self._textos, self._edits, self._voces = [], [], []
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
            self._textos.append(texto)
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
        self.modo_post_btn.setChecked(sala._modo == "post")
        self.modo_previa_btn.setChecked(sala._modo == "previa")
        self.modo_post_btn.setEnabled(sala.modo_post_btn.isEnabled())
        self.modo_previa_btn.setEnabled(sala.modo_previa_btn.isEnabled())
        self.partido_label.setText(sala.texto_contexto())
        lectura = sala._lectura
        ya_cargado = (
            lectura is not None and lectura.ultimo is not None and sala._origen == "partida"
            and sala._fecha_juego == lectura.ultimo.partido.fecha.isoformat()
        )
        self.cargar_btn.setVisible(sala.cargar_partida_btn.isEnabled() and not ya_cargado and sala._modo == "post")
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
