"""
Estilo visual compartido por toda la app: paleta de colores forzada
(clara, sin depender del tema de Windows) + una hoja de estilos (QSS)
para que los botones, campos y titulos se vean consistentes en todas
las ventanas.
"""

from pathlib import Path

from PySide6.QtGui import QColor, QPalette
from PySide6.QtWidgets import QApplication

ICONOS = Path(__file__).resolve().parent / "iconos"

COLOR_ACENTO = "#1E824C"       # verde cancha
COLOR_ACENTO_HOVER = "#24975A"
COLOR_ACENTO_PRESSED = "#17693C"
COLOR_FONDO = "#F4F6F5"
COLOR_TEXTO = "#141414"
COLOR_BORDE = "#D0D5D2"

STYLESHEET = f"""
QWidget {{
    font-family: 'Segoe UI', 'Helvetica Neue', sans-serif;
    font-size: 13px;
    color: {COLOR_TEXTO};
}}

QMainWindow, QWizard {{
    background-color: {COLOR_FONDO};
}}

QPushButton {{
    background-color: {COLOR_ACENTO};
    color: white;
    border: none;
    border-radius: 6px;
    padding: 9px 16px;
    font-weight: 600;
}}
QPushButton:hover {{
    background-color: {COLOR_ACENTO_HOVER};
}}
QPushButton:pressed {{
    background-color: {COLOR_ACENTO_PRESSED};
}}
QPushButton:disabled {{
    background-color: #C7D0CB;
    color: #F0F3F1;
}}
QPushButton:checked {{
    background-color: {COLOR_ACENTO_PRESSED};
}}

QPushButton#navBtn {{
    background-color: transparent;
    color: {COLOR_TEXTO};
    text-align: left;
    padding: 10px 12px;
    border-radius: 6px;
    font-weight: 600;
}}
QPushButton#navBtn:hover {{
    background-color: #E3E9E5;
}}
QPushButton#navBtn:checked {{
    background-color: {COLOR_ACENTO};
    color: white;
}}

QLineEdit, QTextEdit, QSpinBox, QDoubleSpinBox, QDateEdit {{
    border: 1px solid {COLOR_BORDE};
    border-radius: 5px;
    padding: 6px 8px;
    background-color: white;
    selection-background-color: {COLOR_ACENTO};
}}
QLineEdit:focus, QTextEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus, QDateEdit:focus {{
    border: 1px solid {COLOR_ACENTO};
}}

/* Con la hoja de estilos, Fusion deja los botones de los campos
   numericos sin flecha (solo un marco roto): se dibujan aca. */
QSpinBox, QDoubleSpinBox {{
    padding-right: 26px;
}}
QSpinBox::up-button, QDoubleSpinBox::up-button,
QSpinBox::down-button, QDoubleSpinBox::down-button {{
    subcontrol-origin: padding;
    width: 22px;
    border: none;
    border-left: 1px solid {COLOR_BORDE};
    background-color: white;
}}
QSpinBox::up-button, QDoubleSpinBox::up-button {{
    subcontrol-position: top right;
    border-top-right-radius: 4px;
}}
QSpinBox::down-button, QDoubleSpinBox::down-button {{
    subcontrol-position: bottom right;
    border-bottom-right-radius: 4px;
}}
QSpinBox::up-button:hover, QDoubleSpinBox::up-button:hover,
QSpinBox::down-button:hover, QDoubleSpinBox::down-button:hover {{
    background-color: #E3E9E5;
}}
QSpinBox::up-arrow, QDoubleSpinBox::up-arrow {{
    image: url("{(ICONOS / 'flecha_arriba.svg').as_posix()}");
    width: 10px;
    height: 10px;
}}
QSpinBox::down-arrow, QDoubleSpinBox::down-arrow {{
    image: url("{(ICONOS / 'flecha_abajo.svg').as_posix()}");
    width: 10px;
    height: 10px;
}}

QLabel[heading="true"] {{
    font-size: 20px;
    font-weight: 700;
    color: #14432A;
}}
QLabel[subheading="true"] {{
    font-size: 14px;
    font-weight: 600;
    color: #3A4A42;
}}

QCheckBox, QRadioButton {{
    spacing: 8px;
}}

QFrame#sidebar {{
    background-color: #FFFFFF;
    border-right: 1px solid {COLOR_BORDE};
}}

QFrame#tarjeta {{
    background-color: white;
    border: 1px solid {COLOR_BORDE};
    border-radius: 8px;
}}
"""


def aplicar_estilo(app: QApplication) -> None:
    """Fuerza un estilo y paleta consistentes (claros), sin depender del
    tema de Windows, y aplica la hoja de estilos compartida. Sin esto,
    si Windows esta en modo oscuro, Qt a veces mezcla fondos oscuros con
    texto que no cambia de color (o al reves), dejando labels y campos
    practicamente invisibles."""
    app.setStyle("Fusion")

    paleta = QPalette()
    paleta.setColor(QPalette.ColorRole.Window, QColor(COLOR_FONDO))
    paleta.setColor(QPalette.ColorRole.WindowText, QColor(COLOR_TEXTO))
    paleta.setColor(QPalette.ColorRole.Base, QColor(255, 255, 255))
    paleta.setColor(QPalette.ColorRole.AlternateBase, QColor(245, 245, 245))
    paleta.setColor(QPalette.ColorRole.Text, QColor(COLOR_TEXTO))
    paleta.setColor(QPalette.ColorRole.Button, QColor(240, 240, 240))
    paleta.setColor(QPalette.ColorRole.ButtonText, QColor(COLOR_TEXTO))
    paleta.setColor(QPalette.ColorRole.ToolTipBase, QColor(255, 255, 220))
    paleta.setColor(QPalette.ColorRole.ToolTipText, QColor(COLOR_TEXTO))
    app.setPalette(paleta)

    app.setStyleSheet(STYLESHEET)


def marcar_titulo(label) -> None:
    """Aplica el estilo de titulo grande a un QLabel (heading=true)."""
    label.setProperty("heading", True)
    label.style().unpolish(label)
    label.style().polish(label)


def marcar_subtitulo(label) -> None:
    """Aplica el estilo de subtitulo a un QLabel (subheading=true)."""
    label.setProperty("subheading", True)
    label.style().unpolish(label)
    label.style().polish(label)
