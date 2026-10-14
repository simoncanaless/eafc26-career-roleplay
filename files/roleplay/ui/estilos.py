"""
Estilo visual de toda la app, inspirado en los menus de EA FC: fondo
oscuro, acento verde neon, titulos en mayuscula con tipografia condensada.

La paleta se FUERZA (no depende del tema de Windows): si se deja que Qt
mezcle el tema del sistema con la hoja de estilos, quedan labels o campos
invisibles. Los colores viven aca y en ningun otro lado.
"""

from pathlib import Path

from PySide6.QtGui import QColor, QFont, QPalette
from PySide6.QtWidgets import QApplication

ICONOS = Path(__file__).resolve().parent / "iconos"

# ---- Colores ----
FONDO = "#0A0E14"
FONDO_LATERAL = "#06090D"
PANEL = "#111823"
PANEL_ALTO = "#172130"
CAMPO = "#0C121A"
BORDE = "#212D3D"
BORDE_FUERTE = "#2E3D52"
TEXTO = "#EEF2F7"
TEXTO_SUAVE = "#8D9AAE"
TEXTO_APAGADO = "#4D5A6C"

ACENTO = "#1FE07F"  # verde neon
ACENTO_HOVER = "#4AF09B"
ACENTO_PRESIONADO = "#17B867"
TEXTO_SOBRE_ACENTO = "#03150B"
SECUNDARIO = "#3EC5FF"  # celeste, para "Mundo del futbol" y detalles

POSITIVO = "#2BD67B"
NEGATIVO = "#FF4D5E"
MIXTO = "#FFB547"
NEUTRO = TEXTO_SUAVE

# tono de una noticia / comentario / cambio -> color
COLORES_TONO = {
    "positiva": POSITIVO,
    "positivo": POSITIVO,
    "negativa": NEGATIVO,
    "negativo": NEGATIVO,
    "critico": NEGATIVO,
    "mixta": MIXTO,
    "gracioso": MIXTO,
    "neutral": NEUTRO,
}

# ---- Tipografia ----
FUENTE_TITULOS = "Bahnschrift SemiBold Condensed"  # viene con Windows 10/11
FUENTE_TEXTO = "Segoe UI"


def fuente_titulo(pixeles: int, espaciado: float = 0.6) -> QFont:
    """Fuente de titulos y numeros grandes. El espaciado entre letras no
    se puede poner por hoja de estilos, por eso va por codigo."""
    fuente = QFont(FUENTE_TITULOS)
    fuente.setPixelSize(pixeles)
    fuente.setLetterSpacing(QFont.SpacingType.AbsoluteSpacing, espaciado)
    return fuente


def _url(nombre: str) -> str:
    return f'url("{(ICONOS / nombre).as_posix()}")'


# Ojo: la hoja de estilos NO pone una fuente para todo QWidget. Si la pone,
# pisa cualquier setFont() hecho por codigo y los titulos grandes salen con
# la letra chica de siempre. La fuente base va con app.setFont().
STYLESHEET = f"""
QWidget {{
    color: {TEXTO};
}}
QMainWindow, QDialog, QWizard, QMessageBox {{
    background-color: {FONDO};
}}
QToolTip {{
    background-color: {PANEL_ALTO};
    color: {TEXTO};
    border: 1px solid {BORDE_FUERTE};
    padding: 6px;
}}

/* ---------- botones ---------- */
QPushButton {{
    background-color: {PANEL_ALTO};
    color: {TEXTO};
    border: 1px solid {BORDE_FUERTE};
    border-radius: 6px;
    padding: 9px 18px;
    font-family: '{FUENTE_TITULOS}';
    font-size: 15px;
}}
QPushButton:hover {{
    border-color: {ACENTO};
}}
QPushButton:pressed {{
    background-color: {PANEL};
}}
QPushButton:disabled {{
    color: {TEXTO_APAGADO};
    border-color: {BORDE};
    background-color: {PANEL};
}}
QPushButton#primario {{
    background-color: {ACENTO};
    color: {TEXTO_SOBRE_ACENTO};
    border: none;
}}
QPushButton#primario:hover {{
    background-color: {ACENTO_HOVER};
}}
QPushButton#primario:pressed {{
    background-color: {ACENTO_PRESIONADO};
}}
QPushButton#primario:disabled {{
    background-color: #173826;
    color: #3F6B54;
}}

/* opciones que se prenden y apagan (tarjetas, figura del partido) */
QPushButton#chip {{
    background-color: {CAMPO};
    border: 1px solid {BORDE_FUERTE};
    border-radius: 16px;
    padding: 6px 14px;
    font-size: 14px;
    color: {TEXTO_SUAVE};
}}
QPushButton#chip:hover {{
    border-color: {TEXTO_SUAVE};
}}
QPushButton#chip:checked {{
    background-color: {PANEL_ALTO};
    border-color: {ACENTO};
    color: {TEXTO};
}}

/* microfono: rojo mientras graba */
QPushButton#microfono[grabando="true"] {{
    background-color: {NEGATIVO};
    border-color: {NEGATIVO};
    color: white;
}}

/* navegacion lateral */
QPushButton#navBtn {{
    background-color: transparent;
    border: none;
    border-left: 3px solid transparent;
    border-radius: 0px;
    color: {TEXTO_SUAVE};
    text-align: left;
    padding: 12px 16px;
    font-size: 17px;
}}
QPushButton#navBtn:hover {{
    color: {TEXTO};
    background-color: {PANEL};
}}
QPushButton#navBtn:checked {{
    color: {TEXTO};
    border-left: 3px solid {ACENTO};
    background-color: qlineargradient(x1:0, y1:0, x2:1, y2:0,
        stop:0 rgba(31, 224, 127, 0.20), stop:1 rgba(31, 224, 127, 0.0));
}}

/* ---------- campos ---------- */
QLineEdit, QTextEdit, QPlainTextEdit, QSpinBox, QDoubleSpinBox, QDateEdit, QComboBox {{
    background-color: {CAMPO};
    border: 1px solid {BORDE_FUERTE};
    border-radius: 6px;
    padding: 7px 10px;
    selection-background-color: {ACENTO};
    selection-color: {TEXTO_SOBRE_ACENTO};
}}
QLineEdit:focus, QTextEdit:focus, QPlainTextEdit:focus, QSpinBox:focus,
QDoubleSpinBox:focus, QDateEdit:focus, QComboBox:focus {{
    border-color: {ACENTO};
}}
QLineEdit:disabled, QTextEdit:disabled, QSpinBox:disabled, QComboBox:disabled {{
    color: {TEXTO_APAGADO};
    border-color: {BORDE};
}}

/* numeros grandes del marcador */
QSpinBox#marcador {{
    font-family: '{FUENTE_TITULOS}';
    font-size: 40px;
    padding: 2px 30px 2px 12px;
}}

/* Con la hoja de estilos, Fusion deja los botones de los campos
   numericos sin flecha (solo un marco roto): se dibujan aca. */
QSpinBox, QDoubleSpinBox, QDateEdit {{
    padding-right: 26px;
}}
QSpinBox::up-button, QDoubleSpinBox::up-button, QDateEdit::up-button,
QSpinBox::down-button, QDoubleSpinBox::down-button, QDateEdit::down-button {{
    subcontrol-origin: padding;
    width: 22px;
    border: none;
    border-left: 1px solid {BORDE};
    background-color: {CAMPO};
}}
QSpinBox::up-button, QDoubleSpinBox::up-button, QDateEdit::up-button {{
    subcontrol-position: top right;
    border-top-right-radius: 4px;
}}
QSpinBox::down-button, QDoubleSpinBox::down-button, QDateEdit::down-button {{
    subcontrol-position: bottom right;
    border-bottom-right-radius: 4px;
}}
QSpinBox::up-button:hover, QDoubleSpinBox::up-button:hover, QDateEdit::up-button:hover,
QSpinBox::down-button:hover, QDoubleSpinBox::down-button:hover, QDateEdit::down-button:hover {{
    background-color: {PANEL_ALTO};
}}
QSpinBox::up-arrow, QDoubleSpinBox::up-arrow, QDateEdit::up-arrow {{
    image: {_url('flecha_arriba.svg')};
    width: 10px;
    height: 10px;
}}
QSpinBox::down-arrow, QDoubleSpinBox::down-arrow, QDateEdit::down-arrow {{
    image: {_url('flecha_abajo.svg')};
    width: 10px;
    height: 10px;
}}

QComboBox::drop-down {{
    border: none;
    width: 26px;
}}
QComboBox::down-arrow {{
    image: {_url('flecha_abajo.svg')};
    width: 10px;
    height: 10px;
}}
QComboBox QAbstractItemView {{
    background-color: {PANEL_ALTO};
    border: 1px solid {BORDE_FUERTE};
    selection-background-color: {ACENTO};
    selection-color: {TEXTO_SOBRE_ACENTO};
    outline: none;
}}

QCheckBox, QRadioButton {{
    spacing: 10px;
    padding: 3px 0px;
}}
QCheckBox::indicator, QRadioButton::indicator {{
    width: 16px;
    height: 16px;
    background-color: {CAMPO};
    border: 1px solid {BORDE_FUERTE};
}}
QCheckBox::indicator {{
    border-radius: 4px;
}}
QRadioButton::indicator {{
    border-radius: 9px;
}}
QCheckBox::indicator:hover, QRadioButton::indicator:hover {{
    border-color: {ACENTO};
}}
QCheckBox::indicator:checked {{
    background-color: {ACENTO};
    border-color: {ACENTO};
    image: {_url('check.svg')};
}}
QRadioButton::indicator:checked {{
    border-color: {ACENTO};
    background-color: qradialgradient(cx:0.5, cy:0.5, radius:0.5, fx:0.5, fy:0.5,
        stop:0 {ACENTO}, stop:0.42 {ACENTO}, stop:0.5 {CAMPO}, stop:1 {CAMPO});
}}

/* ---------- textos ---------- */
QLabel#subtitulo {{
    color: {TEXTO_SUAVE};
    font-size: 14px;
}}
QLabel#seccion {{
    color: {ACENTO};
}}
QLabel#etiquetaCampo {{
    color: {TEXTO_SUAVE};
    font-size: 11px;
    font-weight: 600;
}}
QLabel#suave {{
    color: {TEXTO_SUAVE};
}}

/* ---------- contenedores ---------- */
QFrame#lateral {{
    background-color: {FONDO_LATERAL};
    border-right: 1px solid {BORDE};
}}
QFrame#tarjeta {{
    background-color: rgba(17, 24, 35, 0.94);
    border: 1px solid {BORDE};
    border-radius: 10px;
}}
QFrame#tarjeta[destacada="true"] {{
    border-left: 3px solid {ACENTO};
}}
QFrame#mosaico {{
    background-color: {CAMPO};
    border: 1px solid {BORDE};
    border-radius: 8px;
}}
QFrame#separador {{
    background-color: {BORDE};
    max-height: 1px;
    border: none;
}}

/* Las paginas son transparentes: el fondo lo pinta FondoEstadio. */
QStackedWidget, QScrollArea, QWidget#pagina {{
    background: transparent;
}}

/* avance de una meta */
QProgressBar {{
    background-color: {CAMPO};
    border: 1px solid {BORDE};
    border-radius: 4px;
    max-height: 8px;
    min-height: 8px;
    text-align: center;
}}
QProgressBar::chunk {{
    background-color: {ACENTO};
    border-radius: 3px;
}}

QScrollBar:vertical {{
    background: transparent;
    width: 10px;
    margin: 4px 2px 4px 0px;
}}
QScrollBar::handle:vertical {{
    background: {BORDE_FUERTE};
    border-radius: 4px;
    min-height: 40px;
}}
QScrollBar::handle:vertical:hover {{
    background: {TEXTO_APAGADO};
}}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical,
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{
    height: 0px;
    background: transparent;
}}
"""


def _paleta() -> QPalette:
    paleta = QPalette()
    roles = {
        QPalette.ColorRole.Window: FONDO,
        QPalette.ColorRole.WindowText: TEXTO,
        QPalette.ColorRole.Base: CAMPO,
        QPalette.ColorRole.AlternateBase: PANEL,
        QPalette.ColorRole.Text: TEXTO,
        QPalette.ColorRole.Button: PANEL_ALTO,
        QPalette.ColorRole.ButtonText: TEXTO,
        QPalette.ColorRole.BrightText: "#FFFFFF",
        QPalette.ColorRole.Highlight: ACENTO,
        QPalette.ColorRole.HighlightedText: TEXTO_SOBRE_ACENTO,
        QPalette.ColorRole.ToolTipBase: PANEL_ALTO,
        QPalette.ColorRole.ToolTipText: TEXTO,
        QPalette.ColorRole.PlaceholderText: TEXTO_APAGADO,
        QPalette.ColorRole.Link: SECUNDARIO,
    }
    for rol, color in roles.items():
        paleta.setColor(rol, QColor(color))
    for rol in (QPalette.ColorRole.WindowText, QPalette.ColorRole.Text, QPalette.ColorRole.ButtonText):
        paleta.setColor(QPalette.ColorGroup.Disabled, rol, QColor(TEXTO_APAGADO))
    return paleta


def aplicar_estilo(app: QApplication) -> None:
    """Fusion + paleta oscura forzada + hoja de estilos compartida."""
    app.setStyle("Fusion")
    app.setPalette(_paleta())
    fuente = QFont(FUENTE_TEXTO)
    fuente.setPixelSize(13)
    app.setFont(fuente)
    app.setStyleSheet(STYLESHEET)
