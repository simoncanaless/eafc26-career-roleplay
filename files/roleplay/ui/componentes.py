"""
Piezas visuales reusables, con el estilo de los menus de EA FC: titulos en
mayuscula, tarjetas oscuras, mosaicos de estadisticas, chips de tono, la
carta del jugador (estilo FUT) y el fondo con brillo de estadio.
"""

from dataclasses import dataclass

from PySide6.QtCore import QByteArray, QPointF, QRectF, QSize, Qt
from PySide6.QtGui import (
    QColor,
    QFontMetrics,
    QIcon,
    QLinearGradient,
    QPainter,
    QPainterPath,
    QPen,
    QPixmap,
    QRadialGradient,
)
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QLayout,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from roleplay.ui import estilos
from roleplay.ui.comun import esc, fecha_corta
from roleplay.ui.estilos import fuente_titulo

# ---- Iconos (trazos propios, 24x24) ----

_TRAZOS = {
    "inicio": '<path d="M3 10.5 12 3l9 7.5V20a1 1 0 0 1-1 1h-5v-6H9v6H4a1 1 0 0 1-1-1z"/>',
    "microfono": '<rect x="9" y="3" width="6" height="11" rx="3"/><path d="M5 11a7 7 0 0 0 14 0M12 18v3M8 21h8"/>',
    "camara": '<rect x="3" y="3" width="18" height="18" rx="5"/><circle cx="12" cy="12" r="4"/>'
    '<circle cx="17.5" cy="6.5" r="0.9" fill="{color}"/>',
    "captura": '<path d="M4 8V5a1 1 0 0 1 1-1h3M16 4h3a1 1 0 0 1 1 1v3M20 16v3a1 1 0 0 1-1 1h-3'
    'M8 20H5a1 1 0 0 1-1-1v-3"/><circle cx="12" cy="12" r="3"/>',
    "chispa": '<path d="M11 3l1.9 5.1L18 10l-5.1 1.9L11 17l-1.9-5.1L4 10l5.1-1.9z"/>'
    '<path d="M19 14.5l.7 1.8 1.8.7-1.8.7-.7 1.8-.7-1.8-1.8-.7 1.8-.7z"/>',
    "enviar": '<path d="M21 3 10 14M21 3l-7 18-4-7-7-4z"/>',
    "prensa": '<path d="M4 5h12v14H6a2 2 0 0 1-2-2zM16 9h4v8a2 2 0 0 1-2 2h-2M7 9h6M7 12h6M7 15h4"/>',
    "nuevo": '<circle cx="10" cy="8" r="4"/><path d="M3 20a7 7 0 0 1 14 0M19 7v6M16 10h6"/>',
    "detener": '<rect x="7" y="7" width="10" height="10" rx="1.5" fill="{color}"/>',
    "escudo": '<path d="M12 3l7 3v5c0 5-3.5 8.5-7 10-3.5-1.5-7-5-7-10V6z"/>',
    "corazon": '<path d="M12 20s-7-4.4-7-10a4 4 0 0 1 7-2.6A4 4 0 0 1 19 10c0 5.6-7 10-7 10z"/>',
    "jugar": '<path d="M7 8h10a4.5 4.5 0 0 1 4.4 5.5l-.7 3a2 2 0 0 1-3.3 1L15.3 16H8.7l-2.1 1.5a2 2 0 0 1-3.3-1l-.7-3'
    'A4.5 4.5 0 0 1 7 8z"/><path d="M8 10.5v3M6.5 12h3"/><circle cx="15.5" cy="11" r=".6" fill="{color}"/>'
    '<circle cx="17.3" cy="13" r=".6" fill="{color}"/>',
    "engranaje": '<circle cx="12" cy="12" r="3.2"/><path d="M12 2.5v3M12 18.5v3M2.5 12h3M18.5 12h3'
    'M5.3 5.3l2.1 2.1M16.6 16.6l2.1 2.1M5.3 18.7l2.1-2.1M16.6 7.4l2.1-2.1"/>',
    "mas": '<path d="M12 5v14M5 12h14"/>',
    "trofeo": '<path d="M7.5 4h9v5a4.5 4.5 0 0 1-9 0z"/><path d="M7.5 6H4.5v1.5A3 3 0 0 0 7.8 10.5'
    'M16.5 6h3v1.5a3 3 0 0 1-3.3 3M12 13.5V17M8.5 20.5h7M9.5 17h5v3.5h-5z"/>',
}


def _pixmap_svg(nombre: str, color: str, tamano: int) -> QPixmap:
    cuerpo = _TRAZOS[nombre].format(color=color)
    svg = (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="{color}" '
        f'stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">{cuerpo}</svg>'
    )
    pixmap = QPixmap(tamano, tamano)
    pixmap.fill(Qt.GlobalColor.transparent)
    pintor = QPainter(pixmap)
    QSvgRenderer(QByteArray(svg.encode())).render(pintor)
    pintor.end()
    return pixmap


def icono(nombre: str, color: str = estilos.TEXTO, color_activo: str | None = None) -> QIcon:
    """Icono de linea en el color pedido. `color_activo` se usa cuando el
    boton esta marcado (ej. la pestana actual de la barra lateral)."""
    resultado = QIcon()
    for tamano in (20, 40, 64):
        resultado.addPixmap(_pixmap_svg(nombre, color, tamano), QIcon.Mode.Normal, QIcon.State.Off)
        resultado.addPixmap(
            _pixmap_svg(nombre, color_activo or color, tamano), QIcon.Mode.Normal, QIcon.State.On
        )
        resultado.addPixmap(_pixmap_svg(nombre, estilos.TEXTO_APAGADO, tamano), QIcon.Mode.Disabled)
    return resultado


# ---- Textos ----


def titulo_pagina(texto: str = "") -> QLabel:
    label = QLabel(texto.upper())
    label.setFont(fuente_titulo(34, 1.0))
    label.setWordWrap(True)
    return label


def subtitulo(texto: str = "") -> QLabel:
    label = QLabel(texto)
    label.setObjectName("subtitulo")
    label.setWordWrap(True)
    return label


def titulo_seccion(texto: str) -> QLabel:
    label = QLabel(texto.upper())
    label.setObjectName("seccion")
    label.setFont(fuente_titulo(17, 1.4))
    return label


def etiqueta_campo(texto: str) -> QLabel:
    label = QLabel(texto.upper())
    label.setObjectName("etiquetaCampo")
    return label


def texto_suave(texto: str = "", ajustar: bool = True) -> QLabel:
    """Texto gris. `ajustar=False` para notas de una linea al lado de un
    boton: con ajuste de linea Qt las parte en dos aunque sobre espacio."""
    label = QLabel(texto)
    label.setObjectName("suave")
    label.setWordWrap(ajustar)
    return label


def chip(texto: str, color: str) -> QLabel:
    """Etiqueta chica con borde del color del tono (positiva, negativa...)."""
    label = QLabel(texto.upper())
    label.setFont(fuente_titulo(12, 1.2))
    label.setStyleSheet(
        f"color: {color}; border: 1px solid {color}; border-radius: 9px; padding: 1px 8px;"
    )
    label.setMaximumHeight(22)
    label.setSizePolicy(QSizePolicy.Policy.Maximum, QSizePolicy.Policy.Fixed)
    return label


def chip_tono(tono: str) -> QLabel:
    tono = (tono or "neutral").lower()
    return chip(tono, estilos.COLORES_TONO.get(tono, estilos.NEUTRO))


def separador() -> QFrame:
    linea = QFrame()
    linea.setObjectName("separador")
    linea.setFixedHeight(1)
    return linea


def boton(texto: str, primario: bool = False, icono_nombre: str | None = None) -> QPushButton:
    resultado = QPushButton(texto.upper())
    if primario:
        resultado.setObjectName("primario")
    if icono_nombre:
        color = estilos.TEXTO_SOBRE_ACENTO if primario else estilos.TEXTO
        resultado.setIcon(icono(icono_nombre, color))
        resultado.setIconSize(QSize(18, 18))
    resultado.setCursor(Qt.CursorShape.PointingHandCursor)
    return resultado


def chip_alternable(texto: str) -> QPushButton:
    """Opcion que se prende y apaga (tarjeta amarilla, figura...)."""
    resultado = QPushButton(texto.upper())
    resultado.setObjectName("chip")
    resultado.setCheckable(True)
    resultado.setCursor(Qt.CursorShape.PointingHandCursor)
    return resultado


def limpiar_layout(layout: QLayout) -> None:
    while layout.count():
        item = layout.takeAt(0)
        if item.widget() is not None:
            # se esconde ya: deleteLater lo borra recien en la proxima vuelta
            # del bucle de eventos y mientras tanto se veria encima de lo nuevo
            item.widget().hide()
            item.widget().deleteLater()
        elif item.layout() is not None:
            limpiar_layout(item.layout())


# ---- Contenedores ----


class Tarjeta(QFrame):
    """Panel oscuro con borde suave. `destacada` le pone la franja verde."""

    def __init__(self, titulo: str = "", destacada: bool = False, espaciado: int = 10):
        super().__init__()
        self.setObjectName("tarjeta")
        if destacada:
            self.setProperty("destacada", True)
        self.cuerpo = QVBoxLayout(self)
        self.cuerpo.setContentsMargins(20, 18, 20, 18)
        self.cuerpo.setSpacing(espaciado)
        if titulo:
            self.cuerpo.addWidget(titulo_seccion(titulo))


class Mosaico(QFrame):
    """Una estadistica: numero grande arriba, rotulo chico abajo."""

    def __init__(self, rotulo: str):
        super().__init__()
        self.setObjectName("mosaico")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 10, 14, 10)
        layout.setSpacing(0)
        self.numero = QLabel("-")
        self.numero.setFont(fuente_titulo(30, 0.5))
        layout.addWidget(self.numero)
        layout.addWidget(etiqueta_campo(rotulo))

    def poner(self, valor) -> None:
        self.numero.setText(str(valor))


def compacto(numero: int) -> str:
    """1234 -> '1,2K', 3400000 -> '3,4M' (como los contadores de las redes)."""
    for limite, sufijo in ((1_000_000, "M"), (1_000, "K")):
        if abs(numero) >= limite:
            return f"{numero / limite:.1f}".replace(".", ",").replace(",0", "") + sufijo
    return str(numero)


def iniciales(nombre: str) -> str:
    partes = [p for p in nombre.split() if p]
    return "".join(p[0] for p in partes[:2]).upper() or "?"


# ---- Carta del jugador (estilo FUT) ----


@dataclass(frozen=True)
class NivelCarta:
    nombre: str
    claro: str
    oscuro: str
    texto: str
    filo: str


# La reputacion decide el color de la carta, como los niveles de FUT.
NIVELES_CARTA = [
    (85, NivelCarta("ELITE", "#1C6E5B", "#04130F", "#F2FFF8", estilos.ACENTO)),
    (70, NivelCarta("ORO", "#F9E39A", "#B88A2C", "#2B2108", "#FFF4C9")),
    (45, NivelCarta("PLATA", "#EEF2F6", "#8B97A4", "#1B2128", "#FFFFFF")),
    (0, NivelCarta("BRONCE", "#E6AE7E", "#87522D", "#2A1708", "#F8D3AE")),
]


def nivel_carta(reputacion: int) -> NivelCarta:
    for minimo, nivel in NIVELES_CARTA:
        if reputacion >= minimo:
            return nivel
    return NIVELES_CARTA[-1][1]


def _forma_carta(rect: QRectF, chaflan: float, radio: float) -> QPainterPath:
    """Escudo de carta: esquinas de arriba cortadas en diagonal y las de
    abajo redondeadas."""
    x, y, w, h = rect.x(), rect.y(), rect.width(), rect.height()
    forma = QPainterPath(QPointF(x + chaflan, y))
    forma.lineTo(x + w - chaflan, y)
    forma.lineTo(x + w, y + chaflan)
    forma.lineTo(x + w, y + h - radio)
    forma.quadTo(x + w, y + h, x + w - radio, y + h)
    forma.lineTo(x + radio, y + h)
    forma.quadTo(x, y + h, x, y + h - radio)
    forma.lineTo(x, y + chaflan)
    forma.closeSubpath()
    return forma


class CartaJugador(QWidget):
    ANCHO, ALTO = 250, 360

    def __init__(self):
        super().__init__()
        self.setFixedSize(self.ANCHO, self.ALTO)
        self.nombre = ""
        self.club = ""
        self.reputacion = 0
        self.stats: list[tuple[str, str]] = []

    def mostrar(self, nombre: str, club: str, reputacion: int, stats: list[tuple[str, str]]) -> None:
        """stats: hasta 6 pares (rotulo, valor), en dos columnas."""
        self.nombre, self.club, self.reputacion, self.stats = nombre, club, reputacion, stats[:6]
        self.update()

    def paintEvent(self, _evento):
        nivel = nivel_carta(self.reputacion)
        texto = QColor(nivel.texto)
        texto_suave = QColor(nivel.texto)
        texto_suave.setAlpha(170)
        w, h = self.width(), self.height()

        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setRenderHint(QPainter.RenderHint.TextAntialiasing)

        forma = _forma_carta(QRectF(1, 1, w - 2, h - 2), 26, 18)
        degradado = QLinearGradient(0, 0, w * 0.35, h)
        degradado.setColorAt(0, QColor(nivel.claro))
        degradado.setColorAt(1, QColor(nivel.oscuro))
        p.fillPath(forma, degradado)

        # brillo diagonal
        p.save()
        p.setClipPath(forma)
        brillo = QPainterPath(QPointF(0, 0))
        brillo.lineTo(w * 0.72, 0)
        brillo.lineTo(w * 0.18, h * 0.62)
        brillo.lineTo(0, h * 0.74)
        brillo.closeSubpath()
        p.fillPath(brillo, QColor(255, 255, 255, 30))
        p.restore()

        # filo exterior e interior
        p.setPen(QPen(QColor(nivel.filo), 2))
        p.drawPath(forma)
        filo_interior = QColor(nivel.filo)
        filo_interior.setAlpha(110)
        p.setPen(QPen(filo_interior, 1))
        p.drawPath(_forma_carta(QRectF(10, 10, w - 20, h - 20), 20, 12))

        # reputacion, como la media de la carta
        p.setPen(texto)
        p.setFont(fuente_titulo(66, 0))
        p.drawText(QRectF(24, 18, 110, 72), Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop, str(self.reputacion))
        p.setFont(fuente_titulo(16, 2))
        p.drawText(QRectF(27, 90, 110, 20), Qt.AlignmentFlag.AlignLeft, "REP")
        p.setPen(texto_suave)
        p.setFont(fuente_titulo(13, 2))
        p.drawText(QRectF(27, 112, 110, 18), Qt.AlignmentFlag.AlignLeft, nivel.nombre)

        # "foto": circulo con las iniciales
        centro = QPointF(w * 0.64, 96)
        circulo = QColor(nivel.texto)
        circulo.setAlpha(26)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(circulo)
        p.drawEllipse(centro, 58, 58)
        p.setPen(texto)
        p.setFont(fuente_titulo(50, 1))
        p.drawText(QRectF(centro.x() - 58, centro.y() - 58, 116, 116), Qt.AlignmentFlag.AlignCenter, iniciales(self.nombre))

        # nombre
        p.setFont(fuente_titulo(27, 1.2))
        metricas = QFontMetrics(p.font())
        nombre = metricas.elidedText(self.nombre.upper(), Qt.TextElideMode.ElideRight, w - 40)
        p.drawText(QRectF(20, 170, w - 40, 36), Qt.AlignmentFlag.AlignCenter, nombre)
        linea = QColor(nivel.texto)
        linea.setAlpha(70)
        p.setPen(QPen(linea, 1))
        p.drawLine(QPointF(40, 212), QPointF(w - 40, 212))

        # estadisticas en dos columnas
        for i, (rotulo, valor) in enumerate(self.stats):
            columna, fila = i // 3, i % 3
            x = 34 if columna == 0 else w / 2 + 14
            y = 224 + fila * 30
            p.setPen(texto)
            p.setFont(fuente_titulo(23, 0.4))
            p.drawText(QRectF(x, y, 56, 28), Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, valor)
            p.setPen(texto_suave)
            p.setFont(fuente_titulo(16, 1.5))
            p.drawText(QRectF(x + 54, y, 50, 28), Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, rotulo)
        p.setPen(QPen(linea, 1))
        p.drawLine(QPointF(w / 2, 228), QPointF(w / 2, 306))

        # club al pie
        p.setPen(texto_suave)
        p.setFont(fuente_titulo(14, 2))
        club = QFontMetrics(p.font()).elidedText(
            (self.club or "SIN CLUB").upper(), Qt.TextElideMode.ElideRight, w - 60
        )
        p.drawText(QRectF(30, h - 46, w - 60, 20), Qt.AlignmentFlag.AlignCenter, club)
        p.end()


class Avatar(QWidget):
    """Foto de perfil de Instagram: iniciales con el anillo de colores."""

    def __init__(self, tamano: int = 86):
        super().__init__()
        self.setFixedSize(tamano, tamano)
        self.texto = "?"

    def poner(self, nombre: str) -> None:
        self.texto = iniciales(nombre)
        self.update()

    def paintEvent(self, _evento):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        lado = self.width()
        anillo = QLinearGradient(0, lado, lado, 0)
        for posicion, color in ((0, "#FEDA75"), (0.35, "#FA7E1E"), (0.65, "#D62976"), (1, "#4F5BD5")):
            anillo.setColorAt(posicion, QColor(color))
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(anillo)
        p.drawEllipse(QRectF(0, 0, lado, lado))
        p.setBrush(QColor(estilos.FONDO))
        p.drawEllipse(QRectF(4, 4, lado - 8, lado - 8))
        p.setBrush(QColor(estilos.PANEL_ALTO))
        p.drawEllipse(QRectF(7, 7, lado - 14, lado - 14))
        p.setPen(QColor(estilos.TEXTO))
        p.setFont(fuente_titulo(int(lado * 0.36), 1))
        p.drawText(QRectF(0, 0, lado, lado), Qt.AlignmentFlag.AlignCenter, self.texto)
        p.end()


class FondoEstadio(QWidget):
    """Fondo de la zona de contenido: oscuro, con un brillo verde arriba a
    la derecha (como los focos de un estadio) y lineas diagonales tenues."""

    def paintEvent(self, _evento):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()
        p.fillRect(self.rect(), QColor(estilos.FONDO))

        for x, y, radio, color, alfa in (
            (w * 0.92, -h * 0.15, max(w, h) * 0.75, estilos.ACENTO, 34),
            (w * 0.05, h * 1.05, max(w, h) * 0.6, estilos.SECUNDARIO, 18),
        ):
            brillo = QRadialGradient(QPointF(x, y), radio)
            centro = QColor(color)
            centro.setAlpha(alfa)
            borde = QColor(color)
            borde.setAlpha(0)
            brillo.setColorAt(0, centro)
            brillo.setColorAt(1, borde)
            p.fillRect(self.rect(), brillo)

        linea = QColor(255, 255, 255, 7)
        p.setPen(QPen(linea, 1))
        paso = 34
        for x in range(-h, w, paso):
            p.drawLine(QPointF(x, h), QPointF(x + h * 0.6, 0))
        p.end()


def fila(*widgets, espaciado: int = 10, estirar_al_final: bool = False) -> QHBoxLayout:
    """Fila horizontal. Un `None` entre los widgets es un espacio elastico:
    fila(texto, None, boton) deja el boton pegado a la derecha."""
    layout = QHBoxLayout()
    layout.setSpacing(espaciado)
    for widget in widgets:
        if widget is None:
            layout.addStretch()
        elif isinstance(widget, QLayout):
            layout.addLayout(widget)
        else:
            layout.addWidget(widget)
    if estirar_al_final:
        layout.addStretch()
    return layout


def agregar_noticia(layout: QVBoxLayout, noticia) -> None:
    """Agrega una noticia a `layout`: chips de categoria y tono, fecha,
    titular grande y cuerpo."""
    if noticia.categoria == "jugador":
        categoria = chip("Sobre vos", estilos.ACENTO)
    else:
        categoria = chip("Mundo del futbol", estilos.SECUNDARIO)
    fecha = texto_suave(fecha_corta(noticia.fecha), ajustar=False)
    layout.addLayout(fila(categoria, chip_tono(noticia.tono), None, fecha, espaciado=8))

    titular = QLabel(esc(noticia.titular))
    titular.setFont(fuente_titulo(21, 0.3))
    titular.setWordWrap(True)
    layout.addWidget(titular)
    layout.addWidget(texto_suave(esc(noticia.cuerpo)))
