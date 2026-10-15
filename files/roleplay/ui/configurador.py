"""
Configurador de autos. A la izquierda, la web oficial de la marca adentro
de la app (ui/navegador.py): el auto real se arma en 3D ahi. A la derecha,
lo que cuesta en el juego (pintura, llantas, pinzas, franjas, interior,
extras, patente) y el boton de pedir; el precio sale de servicios/autos.py.

La foto del auto para el garage se saca del navegador (con recorte), se
pega del portapapeles, o se saca sola al pedir. Sin navegador (sin
QtWebEngine, o en las pruebas) queda el dibujo propio: siluetas calcadas de
fotos reales por carroceria, pintadas con lo que se elige; tambien es la
miniatura del garage de los autos sin foto.
"""

from dataclasses import dataclass
from typing import Optional

from PySide6.QtCore import QByteArray, QPoint, QRect, QRectF, QSize, Qt, Signal
from PySide6.QtGui import QGuiApplication, QImage, QPainter, QPixmap
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtWidgets import (
    QApplication,
    QButtonGroup,
    QDialog,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QRubberBand,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from roleplay import config as config_app
from roleplay.servicios import autos
from roleplay.servicios.autos import Configuracion
from roleplay.ui import estilos
from roleplay.ui.comun import con_scroll, esc
from roleplay.ui.componentes import boton, chip_alternable, etiqueta_campo, fila, texto_suave
from roleplay.ui.estilos import fuente_titulo

# ---- el dibujo ----

@dataclass(frozen=True)
class Silueta:
    """Una carroceria, de costado (viewBox 400 x 170, mirando a la izquierda).
    Calcada a mano de una foto real de perfil con scripts/trazar_silueta.py:
    el contorno, nunca el logo ni la marca dibujada."""

    cuerpo: str  # el contorno de la carroceria
    ventana: str
    ruedas: tuple  # ((x, y, radio), ...)
    techo: float  # y del punto mas alto (arriba del degradado de la pintura)
    base_ventana: float
    asiento: tuple  # (x, y) del respaldo que se ve por la ventana
    parantes: tuple = ()  # x de los parantes de la ventana
    puertas: tuple = ()  # x de las lineas de puerta
    faro: str = '<ellipse cx="40" cy="96" rx="11" ry="3" fill="#F4F6F8"/>'
    luz: str = '<rect x="374" y="88" width="9" height="4.5" rx="1.5" fill="#E0242F"/>'
    detalles: str = ""  # tomas de aire, linea en C, rueda de auxilio ({vidrio}, {oscuro}, {cromo})
    cola: float = 384  # x de la parte de atras, abajo (el escape)
    aleron: str = ""  # si el modelo lo lleva
    piso: float = 118  # la parte de abajo de la carroceria (el zocalo)
    arcos: tuple = ()  # ((x, y, radio), ...) de los arcos de rueda: ahi va el pasarruedas oscuro

    def bandas(self, franja: str, color_franja: str, carbono: bool) -> list:
        """Franjas a media altura del costado y la fibra en el zocalo."""
        medio = self.base_ventana + (self.piso - self.base_ventana) * 0.5
        bandas = [(medio + desde, medio + hasta, color_franja)
                  for desde, hasta in {"lateral": ((-3, 3),), "doble": ((-4.5, -1.5), (1.5, 4.5))}.get(franja, ())]
        if carbono:
            bandas.append((self.piso - 6, self.piso, "#1A1B1E"))
        return bandas


# El renderizador SVG de Qt no hace clip-path: lo que va "adentro" de la
# carroceria (franjas, fibra de carbono) va en el degradado de la pintura, y
# los parantes se dibujan solo entre el techo y la base de la ventana.
SILUETAS = {
    # Mercedes-AMG G 63, Commons: Mercedes-AMG_G_63,_GIMS_2018,_Le_Grand-Saconnex_(1X7A0541).jpg
    "g_real": Silueta(
        "M 41.5 96.4 C 42.0 94.7 43.8 89.4 44.4 85.9 C 45.0 82.4 44.8 78.0 45.4 75.4 C 46.0 72.8 46.7 71.7 48"
        ".3 70.4 C 49.9 69.1 53.2 68.8 54.8 67.5 C 56.3 66.2 56.2 63.6 57.6 62.5 C 59.0 61.4 59.0 61.6 63.3 6"
        "1.0 C 67.6 60.4 75.2 59.3 83.2 58.6 C 91.2 57.9 103.5 57.4 111.6 56.9 C 119.6 56.4 127.8 56.3 131.5 "
        "55.9 C 135.2 55.5 129.9 60.1 133.7 54.5 C 137.5 48.9 150.2 28.9 154.3 22.3 C 158.4 15.7 155.5 16.9 1"
        "58.2 15.0 C 160.9 13.1 166.6 12.0 170.3 10.9 C 174.0 9.8 173.6 8.9 180.5 8.3 C 187.4 7.7 197.9 7.4 2"
        "11.9 7.1 C 225.9 6.8 246.9 6.8 264.3 6.6 C 281.8 6.4 306.4 6.0 316.6 6.0 C 326.9 6.0 323.9 6.0 325.8"
        " 6.4 C 327.7 6.8 327.4 7.5 327.8 8.5 C 328.2 9.5 328.3 11.8 328.4 12.4 L 331.1 32.5 L 333.1 46.0 L 3"
        "34.5 59.4 L 335.5 82.8 L 335.5 91.4 L 342.5 91.3 L 343.2 93.1 L 343.2 110.4 L 337.6 111.1 L 322.9 11"
        "2.2 L 322.6 114.5 A 36.1 36.1 0 0 0 250.4 114.5 L 126.4 114.5 A 36.1 36.1 0 0 0 54.2 114.5 L 57.5 11"
        "7.7 L 44.4 116.0 L 41.8 112.1 Z",
        "M 198.6 23.0 L 196.7 21.3 L 159.6 21.7 L 157.5 23.4 L 141.8 54.5 L 143.3 55.5 L 196.7 54.9 L 198.6 53.1 Z",
        ((90.3, 115.9, 27.1), (286.5, 115.9, 27.1)), 6.0, 55.2, (185.7, 31.7),
        puertas=(262.2, 205.4, 132.1),
        faro='<path d="M 53.3 71.7 L 49.1 71.7 L 48.6 91.1 L 52.7 91.1 Z" fill="#F4F6F8"/><path d="M 67.9 66.8 L 62.7 64.2 L 58.5 65.9 L 60.1 68.5 L 67.4 68.9 Z" fill="#F4F6F8"/>',
        luz='<path d="M 339.7 83.0 L 335.5 83.0 L 335.5 91.4 L 339.7 91.4 Z" fill="#E0242F"/>',
        detalles='<path d="M 256.2 21.6 L 254.6 20.0 L 214.3 20.5 L 212.6 22.0 L 212.6 52.4 L 214.3 54.0 L 254.6 53.5 L 256.2 51.9 Z" fill="{vidrio}"/><path d="M 323.7 19.5 L 322.1 18.0 L 270.3 18.5 L 268.7 20.1 L 268.7 51.3 L 270.3 52.8 L 322.1 52.3 L 323.7 50.7 Z" fill="{vidrio}"/><path d="M 332.3 59.5 L 60.1 62.4 L 60.1 63.5 L 332.3 60.5 Z" fill="{oscuro}"/><path d="M 327.1 70.5 L 268.2 71.2 L 268.2 72.8 L 327.1 72.1 Z" fill="{cromo}"/><path d="M 256.4 71.3 L 211.9 71.8 L 211.9 73.4 L 256.4 72.9 Z" fill="{cromo}"/><path d="M 196.2 72.0 L 138.6 72.6 L 138.6 74.2 L 196.2 73.5 Z" fill="{cromo}"/><path d="M 120.3 72.8 L 61.4 73.4 L 61.4 75.0 L 120.3 74.4 Z" fill="{cromo}"/><path d="M 249.9 107.8 L 122.9 109.1 L 122.9 114.9 L 249.9 113.5 Z" fill="#15171A"/><path d="M 249.9 107.0 L 122.9 108.4 L 122.9 109.4 L 249.9 108.0 Z" fill="{cromo}"/><path d="M 358.5 32.8 L 355.4 29.7 L 338.9 29.8 L 335.7 33.0 L 335.7 77.5 L 338.9 80.9 L 355.4 80.7 L 358.5 77.3 Z" fill="#15171A"/><path d="M 50.1 98.9 L 41.8 98.5 L 41.8 112.1 L 49.6 112.6 Z" fill="#15171A"/>',
        piso=114.5,
        arcos=((90.3, 115.9, 36.1), (286.5, 115.9, 36.1)),
        cola=343.2,
    ),
    # Rolls-Royce Spectre, Commons: 2023_Rolls-Royce_Spectre_EV_-_102kWh_(585PS)_Electric_-_Wittering_Blue_-_06-2024,_Side.jpg
    "gt_rolls": Silueta(
        "M 17.8 95.6 C 17.9 93.9 18.0 88.3 18.6 85.6 C 19.2 82.8 20.9 80.6 21.7 79.1 C 22.5 77.6 20.4 78.2 23"
        ".2 76.8 C 26.0 75.4 33.3 72.4 38.3 70.8 C 43.3 69.2 48.3 68.3 53.3 67.4 C 58.3 66.5 62.2 66.1 68.4 6"
        "5.5 C 74.7 64.9 83.3 64.2 90.8 63.7 C 98.3 63.2 107.5 62.6 113.5 62.2 C 119.5 61.8 123.7 61.6 127.0 "
        "61.3 C 130.3 61.0 130.9 61.5 133.4 60.3 C 135.9 59.0 137.8 56.7 142.1 53.8 C 146.4 50.9 153.4 45.8 1"
        "59.1 42.7 C 164.8 39.6 170.3 36.9 176.0 35.0 C 181.7 33.1 187.4 32.1 193.1 31.2 C 198.8 30.3 204.3 3"
        "0.0 210.0 29.6 C 215.7 29.2 221.2 28.8 227.0 29.1 C 232.8 29.4 239.1 30.8 244.9 31.4 C 250.7 32.0 25"
        "6.3 32.3 262.0 33.0 C 267.7 33.7 273.2 34.6 278.9 35.6 C 284.5 36.6 290.2 38.0 295.9 39.3 C 301.6 40"
        ".6 307.3 41.8 313.0 43.3 C 318.7 44.8 324.5 46.4 330.0 48.4 C 335.5 50.4 340.5 53.4 345.9 55.1 C 351"
        ".3 56.8 357.9 57.7 362.3 58.4 C 366.7 59.1 369.7 59.0 372.0 59.5 C 374.3 60.0 375.2 60.8 375.9 61.1 "
        "L 377.0 69.3 L 378.6 80.2 L 379.1 85.6 L 378.6 91.1 L 379.7 95.5 L 383.0 97.7 L 383.0 102.1 L 380.8 "
        "106.9 L 374.3 110.7 L 356.8 111.8 L 337.2 112.5 L 331.8 126.9 A 32.3 32.3 0 1 0 272.8 126.9 L 103.8 "
        "126.9 A 32.5 32.5 0 1 0 42.6 126.9 L 41.3 126.5 L 24.7 125.7 L 19.4 122.7 L 20.2 119.7 L 18.0 109.2 "
        "L 17.2 100.1 Z",
        "M 144.6 62.3 L 157.3 52.9 L 172.6 42.7 L 188.0 38.5 L 210.0 38.0 L 242.5 39.3 L 261.8 44.1 L 275.4 50.9 L 285.8 56.9 L 284.3 58.3 L 249.0 58.7 L 155.5 58.9 Z",
        ((73.2, 115.1, 27.9), (302.3, 114.9, 28.1)), 29.1, 60.6, (216.9, 43.5),
        parantes=(243.3,),
        puertas=(146.6, 245.8),
        faro='<path d="M 22.6 82.8 L 31.4 80.8 L 31.4 82.4 L 22.6 84.4 Z" fill="#F4F6F8"/>',
        luz='<path d="M 362.9 68.4 L 369.4 67.6 L 375.8 80.4 L 371.4 82.8 Z" fill="#E0242F"/>',
        detalles='<path d="M 17.4 82.0 L 20.6 81.6 L 20.2 98.9 L 17.0 99.7 Z" fill="{cromo}"/><path d="M 137.8 72.4 L 178.7 71.2 L 179.5 73.2 L 138.6 74.8 Z" fill="{cromo}"/><path d="M 106.5 120.1 L 269.0 118.9 L 269.0 120.9 L 106.5 122.1 Z" fill="{cromo}"/><path d="M 249.0 59.1 L 285.9 57.1 L 289.1 58.7 L 249.0 59.9 Z" fill="{cromo}"/><path d="M 21.8 88.4 L 29.0 87.6 L 29.0 93.2 L 22.2 94.0 Z" fill="#15171A"/>',
        piso=126.9,
        arcos=((73.2, 116.0, 32.5), (302.3, 113.8, 32.3)),
    ),
    # McLaren MP4-12C (misma linea que el 570S/Artura/750S), Commons: McLaren_MP4-12C_–_Seitenansicht,_30._August_2012,_Düsseldorf.jpg
    "super_real": Silueta(
        "M 17.0 107.5 C 17.2 106.9 17.4 105.2 18.0 104.1 C 18.6 103.0 19.3 102.0 20.6 100.8 C 21.9 99.6 23.9 "
        "98.2 25.8 96.9 C 27.8 95.6 29.9 94.3 32.3 93.0 C 34.7 91.7 37.5 90.2 40.1 89.1 C 42.7 88.0 44.9 87.5"
        " 47.9 86.5 C 50.9 85.5 54.8 84.3 58.3 83.3 C 61.8 82.3 64.8 81.4 68.7 80.4 C 72.6 79.4 77.4 78.3 81."
        "7 77.4 C 86.0 76.5 90.4 75.7 94.7 74.9 C 99.0 74.1 102.7 73.7 107.4 72.7 C 112.1 71.7 118.2 70.3 122"
        ".9 68.7 C 127.6 67.1 130.8 65.3 135.5 63.2 C 140.2 61.1 146.0 58.6 151.2 56.2 C 156.4 53.8 163.2 50."
        "7 166.9 49.0 C 170.6 47.3 170.8 46.7 173.3 46.0 C 175.8 45.3 178.5 45.0 181.7 44.7 C 184.9 44.4 188."
        "8 44.5 192.4 44.3 C 196.0 44.1 199.5 43.5 203.0 43.4 C 206.5 43.2 210.8 43.4 213.6 43.4 C 216.4 43.4"
        " 216.5 43.5 220.0 43.6 C 223.5 43.8 230.6 43.9 234.8 44.3 C 239.0 44.7 241.9 45.4 245.4 46.0 C 248.9"
        " 46.6 252.4 47.2 256.0 47.7 C 259.6 48.2 263.1 48.6 266.7 49.2 C 270.2 49.8 273.8 50.8 277.3 51.5 C "
        "280.8 52.2 284.4 52.8 287.9 53.6 C 291.4 54.4 296.0 55.6 298.5 56.2 C 301.0 56.8 301.0 56.7 302.8 57"
        ".0 C 304.6 57.3 307.1 57.5 309.1 58.1 C 311.1 58.7 312.5 59.7 314.6 60.4 C 316.7 61.1 318.2 62.0 321"
        ".9 62.5 C 325.6 63.0 332.1 63.2 336.7 63.4 C 341.3 63.5 346.0 63.4 349.5 63.4 C 353.0 63.4 354.7 63."
        "4 357.9 63.2 C 361.1 63.0 365.6 62.2 368.6 62.1 C 371.6 62.0 374.7 62.2 376.0 62.5 C 377.3 62.8 376."
        "5 63.6 376.6 63.8 L 378.1 69.3 L 379.7 76.8 L 380.2 81.0 L 382.4 85.3 L 382.9 88.4 L 381.8 96.9 L 37"
        "9.8 106.3 L 378.3 114.7 L 374.1 119.9 L 367.8 122.5 L 361.5 123.3 L 355.3 129.6 A 33.3 33.3 0 1 0 29"
        "7.5 129.6 L 128.7 129.6 A 33.5 33.5 0 1 0 67.7 129.6 L 65.0 132.6 L 55.7 132.9 L 40.1 131.6 L 29.7 1"
        "28.8 L 24.5 125.5 L 20.0 122.3 L 16.7 119.7 L 18.0 117.7 L 17.4 111.9 Z",
        "M 284.9 60.8 L 277.3 56.6 L 268.8 53.2 L 258.6 50.2 L 226.3 49.0 L 200.8 48.7 L 175.4 49.4 L 171.1 50.7 L 160.1 59.6 L 149.9 69.3 L 149.0 72.7 L 158.4 74.0 L 209.3 68.9 L 234.8 68.1 L 260.3 64.7 L 277.3 63.0 Z",
        ((98.2, 115.4, 27.6), (326.4, 113.5, 29.5)), 43.4, 73.3, (205.1, 53.2),
        parantes=(228.9,),
        puertas=(226.3, 126.5),
        faro='<path d="M 59.9 83.3 L 45.9 86.7 L 36.1 93.1 L 39.5 94.4 L 51.4 89.7 Z" fill="#F4F6F8"/>',
        luz='<path d="M 380.0 69.3 L 373.2 67.6 L 373.2 69.3 L 380.0 71.0 Z" fill="#E0242F"/>',
        detalles='<path d="M 277.3 74.9 L 241.6 75.7 L 238.6 86.3 L 230.6 99.1 L 215.3 114.8 L 234.8 112.6 L 251.8 108.4 L 263.3 99.9 L 272.2 86.3 Z" fill="{oscuro}"/><path d="M 377.9 71.0 L 368.1 65.9 L 369.8 81.2 L 379.6 81.2 Z" fill="#15171A"/><path d="M 32.7 105.8 L 17.4 108.4 L 17.4 117.7 L 29.3 118.6 Z" fill="#15171A"/><path d="M 73.9 94.0 L 62.4 96.1 L 61.2 99.1 L 72.2 97.4 Z" fill="{oscuro}"/>',
        piso=129.6,
        arcos=((98.2, 115.8, 33.5), (326.4, 113.1, 33.3)),
    ),
    # Lamborghini Aventador LP700-4, Commons: 2015_Lamborghini_Aventador_LP700-4_Pirelli_Edition_6.5_Side.jpg
    "cuna_real": Silueta(
        "M 17.0 95.1 C 17.4 94.5 18.2 93.1 19.6 91.8 C 21.0 90.5 23.1 88.6 25.3 87.2 C 27.5 85.8 30.1 84.7 32"
        ".9 83.5 C 35.7 82.3 39.1 81.2 42.3 80.3 C 45.4 79.4 48.6 78.7 51.8 77.9 C 55.0 77.1 57.5 76.6 61.3 7"
        "5.4 C 65.1 74.2 70.3 72.3 74.8 71.0 C 79.3 69.7 83.5 68.5 88.1 67.4 C 92.7 66.3 98.0 65.5 102.2 64.6"
        " C 106.4 63.7 108.9 62.9 113.1 61.9 C 117.3 60.9 123.2 59.6 127.3 58.5 C 131.3 57.4 134.0 56.4 137.4"
        " 55.4 C 140.8 54.4 144.1 53.8 147.5 52.8 C 150.9 51.8 154.2 50.4 157.6 49.7 C 161.0 49.0 164.3 49.1 "
        "167.7 48.5 C 171.1 47.9 173.2 46.6 177.8 46.0 C 182.4 45.4 189.5 45.1 195.2 44.9 C 200.9 44.7 206.4 "
        "44.7 212.1 44.9 C 217.8 45.1 223.4 45.5 229.1 46.0 C 234.8 46.5 240.7 47.0 246.5 47.7 C 252.3 48.4 2"
        "58.1 49.3 263.8 50.2 C 269.5 51.1 275.8 52.0 280.8 53.1 C 285.8 54.2 288.9 55.5 293.9 56.7 C 298.9 5"
        "7.9 305.1 59.1 310.7 60.2 C 316.3 61.3 321.8 62.3 327.3 63.3 C 332.8 64.3 338.1 64.8 343.8 66.0 C 34"
        "9.5 67.2 356.3 69.1 361.3 70.2 C 366.3 71.3 370.5 71.8 373.7 72.6 C 376.9 73.4 379.2 74.5 380.3 74.9"
        " L 379.4 77.2 L 377.2 81.5 L 374.2 85.9 L 373.7 91.1 L 373.7 95.2 L 379.9 99.3 L 383.0 101.8 L 382.6"
        " 104.4 L 379.0 110.6 L 379.0 114.6 L 376.4 118.0 L 370.2 121.0 L 362.2 123.5 L 356.9 127.0 L 353.5 1"
        "31.2 L 350.1 133.0 A 31.5 31.5 0 1 0 297.1 133.0 L 123.9 133.0 A 31.5 31.5 0 1 0 70.9 133.0 L 65.9 1"
        "27.4 L 38.4 124.6 L 29.5 124.4 L 18.2 120.2 L 17.8 113.7 L 24.3 107.8 L 20.6 101.7 L 18.2 98.8 Z",
        "M 252.1 68.2 L 246.5 57.2 L 243.2 55.9 L 225.5 54.7 L 200.0 54.0 L 179.8 55.2 L 159.6 58.4 L 139.4 64.2 L 123.2 72.0 L 123.2 73.8 L 139.4 77.7 L 159.6 77.6 L 189.9 77.1 L 225.5 72.6 L 246.9 69.9 Z",
        ((97.4, 115.9, 27.1), (323.6, 115.9, 27.1)), 44.9, 77.7, (210.1, 58.4),
        parantes=(228.3,),
        puertas=(232.3,),
        faro='<path d="M 41.6 91.1 L 19.8 92.0 L 18.6 95.2 L 39.2 94.7 Z" fill="#F4F6F8"/>',
        luz='<path d="M 379.8 75.9 L 375.3 79.8 L 374.1 84.7 L 378.2 80.7 Z" fill="#E0242F"/>',
        detalles='<path d="M 265.4 82.9 L 241.2 76.9 L 226.7 115.0 L 248.5 115.0 Z" fill="#1B1D20"/><path d="M 262.6 65.1 L 247.7 56.8 L 251.7 68.2 L 264.6 69.2 Z" fill="#15171A"/><path d="M 379.0 110.6 L 356.7 116.7 L 355.1 127.2 L 376.1 117.8 Z" fill="#15171A"/>',
        piso=133.0,
        arcos=((97.4, 115.9, 31.5), (323.6, 115.9, 31.5)),
    ),
    # Hiperdeportivo (Bugatti Veyron): "Bugatti Veyron 16.4 - Seitenansicht, 5. April 2012, Duesseldorf.jpg", Wikimedia Commons
    "hiper_real": Silueta(
        "M 17.0 113.6 C 17.2 111.7 16.2 106.0 18.1 102.3 C 20.0 98.6 22.8 94.6 28.3 91.6 C 33.8 88.6 41.8 86."
        "9 50.9 84.3 C 60.0 81.7 72.6 78.4 83.1 75.8 C 93.6 73.2 106.3 70.9 114.1 68.4 C 121.9 66.0 124.5 63."
        "6 130.0 61.1 C 135.5 58.6 140.9 55.4 146.9 53.2 C 152.9 51.0 157.9 49.5 166.1 48.1 C 174.3 46.7 185."
        "8 45.6 196.0 44.7 C 206.2 43.9 218.2 43.4 227.1 43.0 C 236.0 42.6 241.7 42.4 249.7 42.5 C 257.7 42.6"
        " 267.1 42.9 275.1 43.6 C 283.1 44.4 290.2 45.6 297.7 47.0 C 305.2 48.4 312.8 50.0 320.3 52.1 C 327.8"
        " 54.2 335.8 56.9 342.9 59.4 C 350.0 61.9 357.1 64.7 362.7 67.3 C 368.2 69.9 373.0 72.4 376.2 75.2 C "
        "379.4 78.0 380.8 81.3 381.9 84.3 C 383.0 87.3 382.8 91.8 383.0 93.3 L 383.0 110.8 L 375.1 129.4 L 35"
        "5.8 131.7 A 32.2 32.2 0 1 0 301.8 131.7 L 115.8 131.7 A 31.1 31.1 0 1 0 61.6 131.7 L 23.8 131.7 Z",
        "M 125.4 70.1 L 141.3 57.7 L 163.9 51.5 L 198.9 49.2 L 233.9 50.4 L 237.3 69.6 L 165.0 71.8 Z",
        ((88.7, 115.9, 27.1), (328.8, 114.8, 28.2)), 42.5, 70.9, (204.5, 54.9),
        faro='<path d="M 29.4 95.6 L 45.2 89.9 L 52.0 92.2 L 36.2 98.9 Z" fill="#F4F6F8"/>',
        luz='<path d="M 381.9 94.4 L 367.2 95.6 L 367.2 98.9 L 381.9 98.4 Z" fill="#E0242F"/>',
        detalles='<path d="M 151.4 71.8 L 152.6 61.7 L 166.1 61.1 L 167.8 69.6 Z" fill="{oscuro}"/><path d="M 232 74 C 262 74 276 85 276 98 C 276 111 262 122 232 122 L 232 116 C 257 116 269 108 269 98 C 269 88 257 80 232 80 Z" fill="{cromo}"/>',
        piso=131.7,
        arcos=((88.7, 116.5, 31.1), (328.8, 114.2, 32.2)),
    ),
    # GT ingles (Aston Martin DB11, la base del DB12): "2018 Aston Martin DB11 V8 Automatic 4.0 Side.jpg", Wikimedia Commons
    "gt_aston": Silueta(
        "M 17.0 92.7 C 17.0 91.9 16.6 89.0 17.0 87.8 C 17.4 86.6 17.7 86.4 19.5 85.3 C 21.3 84.2 24.2 82.8 27"
        ".8 81.1 C 31.4 79.4 36.0 77.5 41.0 75.3 C 46.0 73.1 52.1 70.0 57.6 67.9 C 63.1 65.8 68.6 64.0 74.1 6"
        "2.6 C 79.6 61.2 85.2 60.3 90.7 59.6 C 96.2 58.9 101.8 58.5 107.3 58.3 C 112.8 58.1 118.9 58.3 123.9 "
        "58.3 C 128.9 58.2 134.4 58.5 137.4 58.0 C 140.4 57.5 138.9 56.5 142.2 55.0 C 145.5 53.5 151.7 51.4 1"
        "57.1 49.2 C 162.5 47.0 170.0 43.5 174.4 41.7 C 178.8 39.9 180.2 39.3 183.3 38.2 C 186.4 37.1 189.8 3"
        "6.1 193.1 35.3 C 196.4 34.4 199.6 33.7 202.9 33.1 C 206.2 32.5 209.4 32.1 212.7 31.8 C 216.0 31.5 21"
        "9.3 31.2 222.6 31.1 C 225.9 31.0 229.1 31.0 232.4 31.0 C 235.7 31.0 238.9 31.0 242.2 31.1 C 245.5 31"
        ".2 248.8 31.5 252.0 31.8 C 255.2 32.1 256.8 32.3 261.1 32.9 C 265.4 33.5 272.2 34.3 277.7 35.3 C 283"
        ".2 36.3 289.9 37.6 294.2 38.7 C 298.5 39.8 300.5 40.7 303.3 41.7 C 306.1 42.8 308.3 44.0 310.8 45.0 "
        "C 313.3 46.0 315.6 47.0 318.4 47.7 C 321.2 48.5 323.8 48.8 327.4 49.5 C 331.0 50.2 336.7 51.1 340.2 "
        "51.9 C 343.7 52.7 344.2 53.4 348.2 54.3 C 352.2 55.2 359.5 56.4 364.0 57.5 C 368.5 58.6 372.5 59.8 3"
        "75.1 60.7 C 377.7 61.6 379.0 62.7 379.8 63.1 L 379.0 71.7 L 382.2 76.5 L 383.0 86.0 L 382.2 92.3 L 3"
        "80.6 97.1 L 379.0 103.4 L 373.5 111.3 L 362.4 116.1 L 354.0 118.3 L 354.8 118.9 A 34.1 34.1 0 1 0 28"
        "8.0 118.9 L 113.9 118.9 A 34.1 34.1 0 1 0 46.9 118.9 L 46.9 122.5 L 32.8 122.6 L 17.8 119.2 L 17.0 1"
        "15.9 L 20.3 104.3 L 19.5 96.0 Z",
        "M 302.7 51.1 L 286.1 43.7 L 267.1 39.9 L 252.0 36.8 L 212.8 37.1 L 202.9 39.3 L 193.2 43.2 L 183.3 48.0 L 174.5 51.9 L 177.2 59.2 L 182.7 61.3 L 212.8 61.3 L 252.0 61.4 L 261.1 61.9 L 279.2 59.2 L 294.2 55.2 Z",
        ((80.4, 112.2, 30.8), (321.4, 112.2, 30.8)), 31.0, 61.6, (224.9, 44.1),
        parantes=(262.0,),
        puertas=(259.6, 143.5),
        faro='<path d="M 59.0 74.2 L 43.9 77.3 L 27.3 83.3 L 22.2 88.7 L 31.9 87.8 L 46.9 82.7 Z" fill="#F4F6F8"/>',
        luz='<path d="M 379.6 63.7 L 365.1 65.8 L 358.5 68.2 L 360.6 71.8 L 377.2 71.2 Z" fill="#E0242F"/>',
        detalles='<path d="M 138.9 77.3 L 98.2 78.8 L 96.7 80.9 L 137.4 82.7 Z" fill="{oscuro}"/><path d="M 252.3 73.9 L 237.5 73.6 L 237.5 75.7 L 252.3 76.0 Z" fill="{cromo}"/><path d="M 381.7 98.4 L 369.6 104.4 L 354.6 113.4 L 354.0 118.3 L 362.4 116.1 L 373.6 111.3 L 379.0 103.2 Z" fill="#15171A"/>',
        piso=118.9,
        arcos=((80.4, 112.8, 34.1), (321.4, 112.2, 34.1)),
    ),
    # GT de lujo (Continental GT 2019): "2019 Bentley Continental GT Coupe 6.0 Side.jpg", Wikimedia Commons
    "gt_lujo": Silueta(
        "M 17.0 98.4 C 17.1 96.5 16.3 90.5 17.5 87.0 C 18.7 83.5 20.8 80.4 24.3 77.7 C 27.9 75.0 32.1 73.0 38"
        ".8 70.9 C 45.5 68.8 55.2 66.7 64.7 65.2 C 74.2 63.7 85.0 63.0 95.8 62.1 C 106.6 61.2 121.7 61.4 129."
        "5 60.1 C 137.3 58.8 137.8 57.0 142.5 54.4 C 147.2 51.8 152.4 47.6 158.0 44.5 C 163.6 41.4 169.3 37.7"
        " 176.2 35.7 C 183.1 33.7 190.4 33.3 199.5 32.6 C 208.6 31.9 221.1 31.3 230.6 31.5 C 240.1 31.7 249.2"
        " 32.6 256.5 33.6 C 263.9 34.6 268.2 35.9 274.7 37.8 C 281.2 39.7 288.1 42.7 295.4 45.0 C 302.7 47.3 "
        "310.9 50.0 318.7 51.8 C 326.5 53.6 334.6 54.7 342.0 55.9 C 349.4 57.1 357.2 58.0 362.8 59.0 C 368.4 "
        "60.0 372.7 60.6 375.7 62.1 C 378.7 63.6 379.7 65.7 380.9 68.3 C 382.1 70.9 382.6 76.1 383.0 77.7 L 3"
        "83.0 101.0 L 379.9 116.6 L 370.6 120.2 L 339.8 122.3 A 33.2 33.2 0 1 0 276.8 122.3 L 106.9 122.3 A 3"
        "3.2 33.2 0 1 0 43.3 122.3 L 20.6 123.3 Z",
        "M 141.4 62.1 L 155.4 49.7 L 176.2 38.8 L 209.8 36.2 L 243.5 37.2 L 269.5 41.4 L 288.6 54.9 L 251.3 59.0 L 178.7 62.1 Z",
        ((75.1, 112.9, 30.1), (308.3, 112.9, 30.1)), 31.5, 62.1, (215.0, 42.4),
        parantes=(245.1,),
        puertas=(130.0, 247.2),
        faro='<path d="M 20.1 83.9 L 28.4 80.8 L 33.6 86.0 L 25.3 92.2 Z" fill="#F4F6F8"/>',
        luz='<path d="M 382.0 67.3 L 371.6 66.3 L 370.6 74.6 L 380.9 75.6 Z" fill="#E0242F"/>',
        detalles='<path d="M 154.9 66.3 L 155.9 52.8 L 169.4 51.8 L 171.5 63.2 Z" fill="{oscuro}"/><path d="M 131.1 108.8 L 113.4 106.7 L 116.5 117.1 L 130.0 118.1 Z" fill="{vidrio}"/><path d="M 272.1 108.8 L 132.1 112.9 L 132.1 115.5 L 272.1 111.4 Z" fill="{cromo}"/>',
        piso=122.3,
        arcos=((75.1, 112.9, 33.2), (308.3, 111.9, 33.2)),
    ),
    # SUV de lujo (Range Rover L460): "2023 Land Rover Range Rover SV Automatic 4.4 Side.jpg", Wikimedia Commons
    "suv_lujo_real": Silueta(
        "M 17.0 90.9 C 17.3 88.8 17.5 82.1 19.0 78.1 C 20.5 74.1 22.1 69.9 26.2 66.8 C 30.3 63.6 35.6 61.2 43"
        ".6 59.2 C 51.6 57.2 64.1 55.8 74.3 54.6 C 84.5 53.4 95.7 53.0 104.9 52.0 C 114.1 51.0 122.5 51.7 129"
        ".5 48.9 C 136.5 46.1 141.1 39.8 146.8 35.1 C 152.5 30.4 158.6 24.7 163.7 20.8 C 168.8 16.9 171.1 13."
        "6 177.5 11.6 C 183.9 9.6 190.2 9.7 202.0 9.1 C 213.8 8.5 231.9 8.3 248.1 8.1 C 264.3 7.9 283.9 8.0 2"
        "99.2 8.1 C 314.5 8.2 330.9 8.0 340.1 8.6 C 349.3 9.2 350.1 8.7 354.4 11.6 C 358.6 14.5 362.4 21.3 36"
        "5.6 25.9 C 368.8 30.5 371.4 35.5 373.8 39.2 C 376.2 43.0 378.4 43.6 379.9 48.4 C 381.4 53.2 382.5 64"
        ".7 383.0 67.9 L 382.0 96.0 L 377.9 104.7 L 339.3 123.1 A 35.8 35.8 0 1 0 271.3 123.1 L 105.7 123.1 A"
        " 35.8 35.8 0 1 0 37.7 123.1 L 19.0 118.0 Z",
        "M 136.6 48.4 L 151.9 31.1 L 167.3 17.8 L 181.6 12.1 L 237.8 11.1 L 299.2 10.6 L 340.1 11.6 L 352.3 16.7 L 366.6 41.3 L 242.9 45.4 Z",
        ((71.7, 111.8, 31.2), (305.3, 111.8, 31.2)), 8.1, 46.9, (199.5, 27.0),
        parantes=(219.9, 296.6),
        puertas=(128.4, 217.4, 299.2),
        faro='<path d="M 23.1 73.0 L 56.4 64.8 L 58.9 67.9 L 25.7 76.0 Z" fill="#F4F6F8"/>',
        luz='<path d="M 377.9 48.4 L 382.5 48.4 L 383.0 78.1 L 378.9 78.1 Z" fill="#E0242F"/>',
        detalles='<path d="M 126.4 58.7 L 139.7 57.6 L 140.7 100.6 L 127.4 101.6 Z" fill="#16181B"/><path d="M 170.4 48.4 L 168.8 35.1 L 150.9 35.1 L 148.9 46.4 Z" fill="#16181B"/><path d="M 108.0 123.1 L 272.6 123.1 L 272.6 110.8 L 108.0 109.8 Z" fill="#16181B"/><path d="M 338.0 122.0 L 377.9 105.7 L 382.0 96.5 L 340.1 108.8 Z" fill="#16181B"/>',
        piso=123.1,
        arcos=((71.7, 111.8, 35.8), (305.3, 111.8, 35.8)),
    ),
    # SUV deportivo (Urus): "Lamborghini Urus, Knightsbridge - geograph.org.uk - 5892143.jpg", Wikimedia Commons (perspectiva rectificada)
    "suv_deportivo": Silueta(
        "M 17.0 83.1 C 17.2 81.1 16.4 75.1 18.0 71.3 C 19.6 67.5 22.4 63.4 26.9 60.2 C 31.4 57.0 37.4 54.3 45"
        ".0 51.9 C 52.6 49.5 62.2 47.6 72.3 45.9 C 82.4 44.1 96.3 42.5 105.5 41.4 C 114.7 40.3 120.7 41.4 127"
        ".5 39.1 C 134.3 36.9 139.8 31.6 146.6 27.9 C 153.4 24.2 159.8 19.7 168.2 16.9 C 176.6 14.1 185.5 12."
        "6 197.1 11.3 C 208.7 10.0 225.0 9.4 237.7 9.2 C 250.4 9.0 261.9 9.1 273.5 10.0 C 285.1 10.9 298.8 12"
        ".9 307.4 14.4 C 316.0 15.9 319.2 16.9 325.4 19.2 C 331.6 21.5 338.4 24.9 344.6 28.4 C 350.8 31.9 357"
        ".4 36.6 362.7 40.1 C 368.0 43.6 372.8 45.3 376.2 49.1 C 379.6 52.9 381.9 60.4 383.0 62.7 L 382.1 87."
        "9 L 379.6 110.2 L 369.4 118.6 L 366.8 115.7 A 36.0 36.0 0 1 0 295.0 115.7 L 134.8 115.7 A 35.1 35.1 "
        "0 1 0 64.8 115.7 L 20.9 109.8 Z",
        "M 134.6 46.6 L 152.7 31.6 L 168.2 20.1 L 203.7 15.1 L 259.0 14.4 L 295.9 17.3 L 314.4 28.5 L 280.9 44.0 L 203.7 46.0 Z",
        ((99.8, 112.7, 30.3), (330.9, 112.7, 30.3)), 9.2, 46.3, (203.7, 22.3),
        parantes=(227.3,),
        puertas=(137.0, 227.3),
        faro='<path d="M 35.9 66.2 L 56.5 63.8 L 68.1 65.9 L 41.0 70.9 Z" fill="#F4F6F8"/>',
        luz='<path d="M 382.1 49.2 L 367.7 47.6 L 366.9 53.5 L 381.3 55.2 Z" fill="#E0242F"/>',
        detalles='<path d="M 23.4 77.7 L 46.1 80.3 L 55.4 98.2 L 46.1 111.5 L 22.9 108.8 Z" fill="{vidrio}"/><path d="M 150.2 48.0 L 152.0 36.6 L 173.2 35.4 L 175.8 45.7 Z" fill="{oscuro}"/>',
        piso=115.7,
        arcos=((99.8, 112.7, 35.1), (330.9, 112.7, 36.0)),
    ),
    # GT de motor delantero (California T): "Ferrari California T right side.jpg", Wikimedia Commons
    "gt_ferrari": Silueta(
        "M 17.0 93.3 C 17.4 91.5 17.6 85.4 19.3 82.2 C 21.1 79.0 24.0 76.3 27.5 74.0 C 31.0 71.7 32.4 70.5 40"
        ".4 68.2 C 48.4 65.9 62.8 62.0 75.5 60.0 C 88.2 58.0 104.7 57.3 116.4 56.5 C 128.1 55.7 138.3 56.3 14"
        "5.6 55.3 C 152.9 54.3 154.8 52.8 160.2 50.6 C 165.6 48.5 171.5 45.1 177.8 42.4 C 184.1 39.7 190.9 36"
        ".3 198.2 34.3 C 205.5 32.3 213.8 31.1 221.6 30.2 C 229.4 29.3 237.7 29.0 245.0 29.0 C 252.3 29.0 259"
        ".2 29.2 265.5 30.2 C 271.8 31.2 276.7 32.8 283.0 34.8 C 289.3 36.8 296.2 40.1 303.5 42.4 C 310.8 44."
        "6 319.1 46.6 326.9 48.3 C 334.7 50.0 343.5 51.2 350.3 52.4 C 357.1 53.6 363.3 54.0 367.8 55.3 C 372."
        "3 56.6 374.9 57.5 377.2 60.0 C 379.5 62.5 381.0 68.8 381.8 70.5 L 383.0 90.4 L 380.7 113.8 L 370.1 1"
        "27.8 L 337.6 130.1 A 33.3 33.3 0 1 0 281.0 130.1 L 101.7 130.1 A 32.7 32.7 0 1 0 51.5 130.1 L 21.7 1"
        "14.9 Z",
        "M 162.0 60.0 L 177.8 47.1 L 193.6 38.9 L 218.7 35.4 L 250.9 34.8 L 269.6 37.8 L 285.9 50.6 L 250.9 58.8 L 198.2 61.1 Z",
        ((76.6, 114.9, 28.1), (309.3, 113.8, 29.2)), 29.0, 60.5, (239.2, 43.6),
        parantes=(263.7,),
        puertas=(146.8, 267.2),
        faro='<path d="M 24.0 81.0 L 40.4 74.0 L 47.4 76.3 L 31.0 83.4 Z" fill="#F4F6F8"/>',
        luz='<path d="M 381.8 63.5 L 371.3 62.3 L 370.1 68.2 L 380.7 69.3 Z" fill="#E0242F"/>',
        detalles='<path d="M 101.2 74.0 L 117.6 78.7 L 118.7 82.2 L 102.4 77.5 Z" fill="{vidrio}"/><path d="M 178.4 64.7 L 177.2 54.1 L 191.2 53.0 L 192.4 62.3 Z" fill="{oscuro}"/><path d="M 380.7 116.1 L 365.5 118.4 L 367.8 127.8 L 378.3 126.6 Z" fill="#15171A"/>',
        piso=130.1,
        arcos=((76.6, 109.1, 32.7), (309.3, 112.6, 33.3)),
    ),
    # Sedan electrico (Taycan GTS): "Porsche Taycan GTS (side view) (taken in 2022) (Kyoto, Japan).jpg", Wikimedia Commons
    "sedan_real": Silueta(
        "M 17.0 101.8 C 17.1 100.2 16.8 94.8 17.5 91.9 C 18.2 89.0 19.2 86.4 21.4 84.2 C 23.6 82.0 25.9 80.5 "
        "30.7 78.7 C 35.5 76.9 41.3 75.3 50.0 73.2 C 58.7 71.1 72.4 68.7 82.9 66.1 C 93.4 63.5 105.0 60.5 113"
        ".2 57.8 C 121.5 55.1 125.5 53.0 132.4 50.1 C 139.3 47.2 147.1 43.3 154.4 40.2 C 161.7 37.1 168.2 33."
        "8 176.4 31.4 C 184.6 29.0 194.7 27.1 203.8 25.9 C 213.0 24.7 222.1 24.3 231.3 24.3 C 240.5 24.3 249."
        "6 24.9 258.8 25.9 C 268.0 26.9 277.1 28.3 286.3 30.3 C 295.5 32.3 305.1 35.2 313.8 38.0 C 322.5 40.8"
        " 330.7 43.9 338.5 46.8 C 346.3 49.7 354.6 53.2 360.5 55.6 C 366.4 58.0 370.8 59.5 374.2 61.1 C 377.6"
        " 62.8 379.3 63.3 380.8 65.5 C 382.3 67.7 382.6 72.8 383.0 74.3 L 381.9 106.2 L 373.1 121.6 L 349.5 1"
        "27.1 A 33.0 33.0 0 1 0 289.1 127.1 L 99.4 127.1 A 33.0 33.0 0 1 0 39.0 127.1 L 21.4 123.8 Z",
        "M 142.3 62.2 L 159.9 46.8 L 173.6 37.5 L 209.3 31.4 L 253.3 31.4 L 280.8 34.7 L 303.9 44.6 L 275.3 61.1 L 209.3 64.4 Z",
        ((69.2, 114.4, 28.6), (319.3, 114.4, 28.6)), 24.3, 63.3, (187.4, 44.1),
        parantes=(215.9,),
        puertas=(115.9, 214.8, 307.2),
        faro='<path d="M 19.2 79.8 L 33.5 73.8 L 39.0 77.1 L 23.6 83.1 Z" fill="#F4F6F8"/>',
        luz='<path d="M 383.0 64.4 L 363.2 62.2 L 363.2 64.4 L 382.5 67.2 Z" fill="#E0242F"/>',
        detalles='<path d="M 133.5 69.9 L 136.8 60.6 L 150.0 60.0 L 151.1 67.7 Z" fill="{oscuro}"/><path d="M 33.5 111.7 L 18.1 107.3 L 19.2 122.7 L 30.7 123.8 Z" fill="{vidrio}"/><path d="M 381.9 111.7 L 368.7 113.9 L 369.8 121.6 L 377.5 121.6 Z" fill="#15171A"/>',
        piso=127.1,
        arcos=((69.2, 113.9, 33.0), (319.3, 113.9, 33.0)),
    ),
    # Ferrari de motor central (458 Italia): "Ferrari 458 Italia berlinetta - port profile.jpg", Wikimedia Commons
    "ferrari_super": Silueta(
        "M 17.0 109.6 C 17.4 108.1 17.8 103.4 19.1 100.8 C 20.4 98.2 22.3 96.3 24.7 94.2 C 27.1 92.1 28.7 90."
        "3 33.4 88.0 C 38.1 85.7 45.5 82.5 53.0 80.3 C 60.5 78.1 71.0 75.9 78.7 74.6 C 86.4 73.3 93.2 73.4 99"
        ".2 72.6 C 105.2 71.8 109.6 71.8 114.7 70.0 C 119.8 68.2 124.5 64.7 130.1 61.8 C 135.7 58.9 142.1 55."
        "2 148.1 52.5 C 154.1 49.8 159.7 47.1 166.1 45.3 C 172.5 43.5 178.9 42.5 186.6 41.7 C 194.3 40.9 204."
        "6 40.6 212.3 40.7 C 220.0 40.8 226.0 41.2 232.9 42.2 C 239.8 43.2 246.7 44.9 253.5 46.4 C 260.4 47.9"
        " 266.3 49.5 274.0 51.5 C 281.7 53.5 291.1 56.3 299.7 58.2 C 308.3 60.1 317.7 61.7 325.4 62.8 C 333.1"
        " 63.9 339.1 64.5 346.0 64.9 C 352.9 65.3 361.8 65.1 366.6 65.4 C 371.4 65.7 372.8 66.0 374.8 66.9 C "
        "376.9 67.8 377.5 68.2 378.9 71.0 C 380.3 73.8 382.3 81.8 383.0 83.9 L 382.0 112.2 L 374.8 128.6 L 35"
        "4.1 130.7 A 31.9 31.9 0 1 0 298.9 130.7 L 123.7 130.7 A 30.8 30.8 0 1 0 69.7 130.7 L 19.6 129.1 Z",
        "M 142.9 71.0 L 166.1 53.6 L 186.6 45.8 L 238.0 45.8 L 258.6 51.5 L 268.9 58.7 L 232.9 64.9 L 166.1 71.0 Z",
        ((96.7, 116.3, 26.7), (326.5, 114.7, 28.3)), 40.7, 71.0, (217.5, 50.5),
        puertas=(245.8,),
        faro='<path d="M 27.3 92.6 L 53.0 83.9 L 59.2 85.4 L 32.4 94.7 Z" fill="#F4F6F8"/>',
        luz='<path d="M 370.7 67.9 L 379.9 70.0 L 380.9 74.1 L 371.7 72.6 Z" fill="#E0242F"/>',
        detalles='<path d="M 252.4 101.9 L 279.2 82.3 L 290.5 86.5 L 268.9 103.9 Z" fill="{oscuro}"/><path d="M 20.1 126.6 L 21.1 113.2 L 32.4 115.2 L 34.5 127.6 Z" fill="{vidrio}"/><path d="M 362.4 126.6 L 382.0 117.3 L 380.9 128.6 L 371.7 130.7 Z" fill="#15171A"/><path d="M 149.6 77.2 L 151.7 67.9 L 165.0 66.9 L 166.1 73.1 Z" fill="{oscuro}"/>',
        piso=130.7,
        arcos=((96.7, 115.8, 30.8), (326.5, 114.7, 31.9)),
    ),
    # Porsche 911 (991 Turbo S): "Porsche 991 Turbo S Seitenansicht.JPG", Wikimedia Commons (marcado a mano:
    # auto negro sobre fondo oscuro). Lo comparten Carrera, Turbo S y GT3 RS (este con aleron)
    "911_real": Silueta(
        "M 17 133 L 17 114.4 C 17.4 112.2 17.9 105.1 19.7 101.1 C 21.5 97.1 23.6 93.4 27.6 90.5 C 31.6 87.6 38.2 85.4 "
        "43.5 83.6 C 48.8 81.8 54.1 80.6 59.4 79.4 C 64.7 78.2 69.1 77.4 75.3 76.7 C 81.5 76.0 89.5 75.7 96.6 75.1 "
        "C 103.7 74.5 109.4 74.6 117.8 73.0 C 126.2 71.4 138.2 68.6 147.0 65.6 C 155.8 62.6 162.9 58.4 170.8 55.0 "
        "C 178.8 51.6 186.7 47.6 194.7 45.4 C 202.7 43.2 211.1 42.2 218.6 41.7 C 226.1 41.2 232.7 41.8 239.8 42.2 "
        "C 246.9 42.6 254.8 43.2 261.0 44.3 C 267.2 45.4 271.6 46.8 276.9 48.6 C 282.2 50.4 287.5 52.8 292.8 54.9 "
        "C 298.1 57.0 302.5 59.5 308.7 61.3 C 314.9 63.1 322.8 64.5 329.9 65.6 C 337.0 66.7 345.4 67.0 351.2 67.7 "
        "C 356.9 68.4 360.0 68.2 364.4 69.8 C 368.8 71.4 374.6 73.8 377.7 77.2 C 380.8 80.7 382.1 88.3 383.0 90.5 "
        "L 382.4 119.7 L 377.7 132.9 L 334.5 133 A 33 33 0 1 0 278.7 133 L 112.3 133 A 33 33 0 1 0 56.5 133 "
        "L 18.1 132.9 Z",
        "M 150.7 67.7 L 197.3 46.5 L 261 46.5 L 287.5 55 L 290 64 L 152 71 Z",
        ((84.4, 115.4, 27.6), (306.6, 115.4, 27.6)), 41.7, 68, (214, 52), parantes=(241,), puertas=(254,),
        faro='<ellipse cx="43" cy="85" rx="8" ry="4" fill="#F4F6F8"/>',
        luz='<rect x="358" y="80" width="25" height="4" rx="1.5" fill="#E0242F"/>',
        detalles='<path d="M 262 93 Q 264 80 279 77 L 281 95 Z" fill="{vidrio}"/>'
                 '<path d="M 18 126 L 20 112 L 34 113 L 36 125 Z" fill="{vidrio}"/>'
                 '<path d="M 362 116 L 383 114 L 382 130 L 366 132 Z" fill="#15171A"/>'
                 '<path d="M 156 72 L 158 64 L 170 63 L 171 69 Z" fill="{oscuro}"/>',
        aleron='<path d="M 332 66 L 334 53 M 360 69 L 362 53" stroke="{oscuro}" stroke-width="3"/>'
               '<path d="M 318 52 L 376 49 L 378 55 L 320 58 Z" fill="{oscuro}"/>',
        piso=133, arcos=((84.4, 115.4, 33), (306.6, 115.4, 33)),
    ),
    # Lamborghini Huracan: "Green huracan (20744807015).jpg", Wikimedia Commons
    "huracan": Silueta(
        "M 17.0 126.2 L 17.0 105.2 L 28.4 97.4 L 39.8 94.5 L 44.7 87.5 L 52.8 83.3 L 78.9 73.9 L 109.9 67.6 L"
        " 139.2 56.3 L 178.3 44.2 L 196.2 42.6 L 240.2 43.3 L 300.5 51.6 L 354.2 62.5 L 372.1 64.8 L 383.0 67"
        ".8 L 383.0 122.8 L 372.1 126.8 L 365.5 126.8 A 37.3 37.3 0 1 0 295.9 126.8 L 130.2 126.8 A 32.7 32.7"
        " 0 1 0 73.0 126.8 L 69.1 127.3 L 17.0 126.2 Z",
        "M 121.3 67.0 L 173.4 48.9 L 188.1 46.9 L 240.2 47.1 L 282.5 53.3 L 282.5 62.3 L 121.3 77.1 Z",
        ((101.6, 112.2, 30.8), (330.7, 112.2, 30.8)), 42.6, 69.7, (196, 56), puertas=(252,),
        faro='<path d="M 37 100 L 64 88 L 66 91 L 40 102 Z" fill="#F4F6F8"/>',
        luz='<path d="M 366 69 L 383 71 L 383 75 L 368 74 Z" fill="#E0242F"/>',
        detalles='<path d="M 18 120 L 40 111 L 53 113 L 41 124 L 18 124 Z" fill="{vidrio}"/>'
                 '<path d="M 254 117 L 276 104 L 279 118 Z" fill="{vidrio}"/>'
                 '<path d="M 366 114 L 383 110 L 383 123 L 372 127 Z" fill="#15171A"/>'
                 '<path d="M 149 66 L 156 56 L 171 55 L 173 62 L 160 66 Z" fill="{oscuro}"/>',
        piso=126.8, arcos=((101.6, 111.0, 32.7), (330.7, 113.4, 37.3)),
    ),
}
PISO = 118  # la parte de abajo de la carroceria
INTERIOR = {"negro": "#1C1C1E", "tostado": "#A0703C", "rojo": "#9E1B22", "blanco": "#E8E2D6"}
VIDRIO = "#0E141B"
CROMO = "#D9DCE0"


def _mezclar(color: str, con: str, cuanto: float) -> str:
    a = [int(color[i:i + 2], 16) for i in (1, 3, 5)]
    b = [int(con[i:i + 2], 16) for i in (1, 3, 5)]
    return "#" + "".join(f"{round(x + (y - x) * cuanto):02X}" for x, y in zip(a, b))


def _color_en(stops: list, y: float) -> str:
    for (y0, c0), (y1, c1) in zip(stops, stops[1:]):
        if y0 <= y <= y1:
            return _mezclar(c0, c1, (y - y0) / (y1 - y0) if y1 > y0 else 0)
    return stops[-1][1] if y > stops[-1][0] else stops[0][1]


def _pintura(base: str, acabado: str, techo: float, piso: float, bandas: list) -> str:
    """El degradado de la pintura (en coordenadas de la carroceria) con las
    bandas -franjas, fibra de carbono- metidas como cortes de color."""
    if acabado == "mate":
        stops = [(techo, _mezclar(base, "#000000", 0.08)), (piso, _mezclar(base, "#000000", 0.18))]
    elif acabado == "metalizado":
        stops = [(techo, _mezclar(base, "#FFFFFF", 0.45)), ((techo + piso) / 2, base),
                 (piso, _mezclar(base, "#000000", 0.45))]
    else:
        stops = [(techo, _mezclar(base, "#FFFFFF", 0.22)), (piso, _mezclar(base, "#000000", 0.25))]
    puntos = list(stops)
    for desde, hasta, color in bandas:  # un borde neto: dos puntos casi en el mismo lugar
        puntos += [(desde - 0.01, _color_en(stops, desde)), (desde, color), (hasta, color),
                   (hasta + 0.01, _color_en(stops, hasta))]
    puntos.sort(key=lambda punto: punto[0])
    largo = piso - techo
    stops_svg = "".join(
        f'<stop offset="{max(0.0, min(1.0, (y - techo) / largo)):.4f}" stop-color="{color}"/>' for y, color in puntos
    )
    return (f'<linearGradient id="pintura" gradientUnits="userSpaceOnUse" x1="0" y1="{techo}" x2="0" y2="{piso}">'
            f'{stops_svg}</linearGradient>')


def _rueda(x: int, y: int, r: int, llanta: str, color_llanta: str, color_pinza: str) -> str:
    aro = r * 0.64
    partes = [
        f'<circle cx="{x}" cy="{y}" r="{r}" fill="#121315"/>',
        f'<circle cx="{x}" cy="{y}" r="{aro:.1f}" fill="{_mezclar(color_llanta, "#000000", 0.55)}"/>',
        # la pinza del freno, detras de los rayos
        f'<path d="M {x - aro * 0.75:.1f} {y - aro * 0.35:.1f} A {aro * 0.8:.1f} {aro * 0.8:.1f} 0 0 1 '
        f'{x + aro * 0.1:.1f} {y - aro * 0.8:.1f}" stroke="{color_pinza}" stroke-width="{aro * 0.32:.1f}" '
        f'fill="none" stroke-linecap="round"/>',
    ]
    rayos = {"estandar": 5, "deportivas": 7, "forjadas": 10, "doradas": 6}[llanta]
    grosor = {"estandar": 3.4, "deportivas": 2.2, "forjadas": 1.6, "doradas": 2.8}[llanta]
    for n in range(rayos):
        partes.append(
            f'<line x1="{x}" y1="{y}" x2="{x}" y2="{y - aro:.1f}" stroke="{color_llanta}" stroke-width="{grosor}" '
            f'stroke-linecap="round" transform="rotate({360 * n / rayos:.1f} {x} {y})"/>'
        )
    partes += [
        f'<circle cx="{x}" cy="{y}" r="{aro:.1f}" fill="none" stroke="{color_llanta}" stroke-width="2"/>',
        f'<circle cx="{x}" cy="{y}" r="{aro * 0.22:.1f}" fill="{color_llanta}"/>',
    ]
    return "".join(partes)


def _ventana_en(ventana: str, x: float):
    """Donde corta la vertical x al borde de la ventana (arriba, abajo), si la
    ventana es un poligono (M ... L ... Z); None si tiene curvas."""
    if any(c in ventana for c in "CQAS"):
        return None
    numeros = [float(n) for n in ventana.replace("M", " ").replace("L", " ").replace("Z", " ").split()]
    puntos = list(zip(numeros[::2], numeros[1::2]))
    cortes = []
    for (x1, y1), (x2, y2) in zip(puntos, puntos[1:] + puntos[:1]):
        if x1 != x2 and min(x1, x2) <= x <= max(x1, x2):
            cortes.append(y1 + (y2 - y1) * (x - x1) / (x2 - x1))
    return (min(cortes), max(cortes)) if len(cortes) >= 2 else None


def svg_auto(config: Configuracion) -> str:
    """El auto configurado, de costado, como SVG (400 x 170)."""
    modelo = autos.POR_ID[config.modelo]
    forma = SILUETAS[modelo.carroceria]
    base = autos.opcion("color", config.color).color
    colores = {"vidrio": VIDRIO, "oscuro": _mezclar(base, "#000000", 0.45), "cromo": CROMO}
    bandas = forma.bandas(config.franja, autos.opcion("color", config.color_franja).color, "carbono" in config.extras)
    linea = _mezclar(base, "#000000", 0.5)
    partes = [
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 400 170">',
        f'<defs>{_pintura(base, config.acabado, forma.techo, forma.piso, bandas)}</defs>',
        '<ellipse cx="200" cy="145" rx="185" ry="7" fill="#000000" fill-opacity="0.45"/>',
    ]
    if modelo.aleron and forma.aleron:
        partes.append(forma.aleron.format(**colores))
    # el pasarruedas: oscuro, se ve entre la rueda y el arco (el mismo circulo del arco)
    for x, y, arco in forma.arcos or tuple((x, y, r * 1.25) for x, y, r in forma.ruedas):
        alto = forma.piso - y  # negativo en un todoterreno: el zocalo queda sobre el eje
        if abs(alto) < arco:
            dx = (arco * arco - alto * alto) ** 0.5
            partes.append(f'<path d="M {x - dx:.1f} {forma.piso} A {arco:.1f} {arco:.1f} 0 {1 if alto > 0 else 0} 1 '
                          f'{x + dx:.1f} {forma.piso} Z" fill="#0B0C0E"/>')
    partes += [
        f'<path d="{forma.cuerpo}" fill="url(#pintura)" stroke="{linea}" stroke-width="1.2"/>',
        f'<path d="{forma.ventana}" fill="{VIDRIO}" stroke="{linea}" stroke-width="1"/>',
        # el respaldo se ve por la ventana: el color del interior
        f'<rect x="{forma.asiento[0]}" y="{forma.asiento[1]}" width="11" height="14" rx="3" '
        f'fill="{INTERIOR.get(config.interior, "#1C1C1E")}"/>',
    ]
    for x in forma.parantes:  # solo dentro de la ventana
        arriba, abajo = _ventana_en(forma.ventana, x) or (forma.techo + 5, forma.base_ventana - 1)
        partes.append(f'<line x1="{x}" y1="{arriba:.1f}" x2="{x - 3}" y2="{abajo:.1f}" '
                      f'stroke="{_mezclar(base, "#000000", 0.35)}" stroke-width="5"/>')
    for x in forma.puertas:
        partes.append(f'<line x1="{x - 4}" y1="{forma.base_ventana + 4}" x2="{x - 1}" y2="{forma.piso - 4}" '
                      f'stroke="{linea}" stroke-width="1"/>')
    partes += [forma.detalles.format(**colores), forma.faro, forma.luz]
    if "escape" in config.extras:
        x = forma.cola - 8
        partes += [f'<rect x="{x}" y="111" width="12" height="4" rx="2" fill="#6B6E73"/>',
                   f'<rect x="{x}" y="105" width="12" height="4" rx="2" fill="#6B6E73"/>']
    llanta = autos.opcion("llantas", config.llantas)
    pinza = autos.opcion("pinzas", config.pinzas)
    for x, y, r in forma.ruedas:
        partes.append(_rueda(x, y, r, llanta.id, llanta.color, pinza.color))
    if config.patente:
        partes.append('<rect x="290" y="152" width="96" height="16" rx="3" fill="#F1F1EE" stroke="#1C1C1C"/>')
        partes.append(f'<text x="338" y="164.5" font-family="Arial" font-size="12" font-weight="bold" '
                      f'text-anchor="middle" fill="#111111">{esc(config.patente)}</text>')
    partes.append("</svg>")
    return "".join(partes)


class VistaAuto(QWidget):
    """Dibuja svg_auto(config), manteniendo las proporciones."""

    def __init__(self, config: Configuracion, alto: int = 200):
        super().__init__()
        self.config = config
        self.setMinimumSize(QSize(round(alto * 400 / 170), alto))
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

    def poner(self, config: Configuracion) -> None:
        self.config = config
        self.update()

    def paintEvent(self, _evento):
        renderizador = QSvgRenderer(QByteArray(svg_auto(self.config).encode()))
        alto = self.height()
        ancho = min(self.width(), round(alto * 400 / 170))
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        renderizador.render(p, QRectF((self.width() - ancho) / 2, 0, ancho, alto))
        p.end()


# ---- la foto del garage ----

ANCHO_FOTO = 960  # se guarda achicada: alcanza para la miniatura y la tarjeta
MINIATURA = QSize(132, 74)


def guardar_foto(imagen: QImage, nombre: str) -> str:
    """Guarda la foto en la carpeta del garage y devuelve el nombre del archivo."""
    config_app.CARPETA_GARAGE.mkdir(parents=True, exist_ok=True)
    if imagen.width() > ANCHO_FOTO:
        imagen = imagen.scaledToWidth(ANCHO_FOTO, Qt.TransformationMode.SmoothTransformation)
    archivo = f"{nombre}.jpg"
    imagen.save(str(config_app.CARPETA_GARAGE / archivo), "JPG", 88)
    return archivo


def _nitida(imagen: QImage, tamano: QSize, cubrir: bool = False) -> QPixmap:
    """La imagen achicada a `tamano` (en puntos de pantalla) con los pixeles
    de la pantalla: al 300% se ve nitida, no estirada. `cubrir`: llena todo
    el tamano y recorta lo que sobra al centro."""
    escala = QGuiApplication.instance().devicePixelRatio()
    destino = tamano * escala
    pixmap = QPixmap.fromImage(imagen).scaled(
        destino, Qt.AspectRatioMode.KeepAspectRatioByExpanding if cubrir else Qt.AspectRatioMode.KeepAspectRatio,
        Qt.TransformationMode.SmoothTransformation)
    if cubrir:
        x, y = (pixmap.width() - destino.width()) // 2, (pixmap.height() - destino.height()) // 2
        pixmap = pixmap.copy(x, y, destino.width(), destino.height())
    pixmap.setDevicePixelRatio(escala)
    return pixmap


def miniatura(config: Configuracion, foto: str = "") -> QWidget:
    """La foto del auto (recortada al centro) si la hay; si no, el dibujo."""
    ruta = config_app.CARPETA_GARAGE / foto if foto else None
    if ruta is not None and ruta.exists():
        etiqueta = QLabel()
        etiqueta.setObjectName("fotoAuto")
        etiqueta.setPixmap(_nitida(QImage(str(ruta)), MINIATURA, cubrir=True))
        etiqueta.setFixedSize(MINIATURA)
        return etiqueta
    vista = VistaAuto(config, alto=56)
    vista.setFixedWidth(MINIATURA.width())
    return vista


class _Lienzo(QLabel):
    """La foto achicada para que entre; se arrastra un rectangulo encima."""

    seleccion_cambiada = Signal()

    def __init__(self, pixmap: QPixmap):
        super().__init__()
        self.setPixmap(pixmap)
        self.setFixedSize(pixmap.size())
        self.setCursor(Qt.CursorShape.CrossCursor)
        self._banda = QRubberBand(QRubberBand.Shape.Rectangle, self)
        self._origen: Optional[QPoint] = None
        self.seleccion = QRect()

    def mousePressEvent(self, evento):
        self._origen = evento.position().toPoint()
        self._banda.setGeometry(QRect(self._origen, QSize()))
        self._banda.show()

    def mouseMoveEvent(self, evento):
        if self._origen is not None:
            self._banda.setGeometry(QRect(self._origen, evento.position().toPoint()).normalized() & self.rect())

    def mouseReleaseEvent(self, _evento):
        self._origen = None
        self.seleccion = self._banda.geometry()
        self.seleccion_cambiada.emit()


class RecortarFoto(QDialog):
    """La foto que se saco del navegador: se usa entera o se recorta el auto."""

    MAXIMO = QSize(1100, 620)

    def __init__(self, imagen: QImage, parent=None):
        super().__init__(parent)
        self.setWindowTitle("La foto de tu auto")
        self.imagen = imagen
        self._recortar = False
        pixmap = QPixmap.fromImage(imagen)
        if pixmap.width() > self.MAXIMO.width() or pixmap.height() > self.MAXIMO.height():
            pixmap = pixmap.scaled(self.MAXIMO, Qt.AspectRatioMode.KeepAspectRatio,
                                   Qt.TransformationMode.SmoothTransformation)
        self._escala = imagen.width() / max(pixmap.width(), 1)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(22, 20, 22, 18)
        layout.setSpacing(12)
        layout.addWidget(texto_suave("Arrastra un rectangulo sobre el auto para recortarlo, o usa la foto entera."))
        self.lienzo = _Lienzo(pixmap)
        layout.addWidget(self.lienzo, 0, Qt.AlignmentFlag.AlignCenter)
        cancelar = boton("Cancelar")
        cancelar.clicked.connect(self.reject)
        entera = boton("Usar la foto entera")
        entera.clicked.connect(self.accept)
        self.recorte_btn = boton("Usar el recorte", primario=True)
        self.recorte_btn.setEnabled(False)
        self.recorte_btn.clicked.connect(self._usar_recorte)
        self.lienzo.seleccion_cambiada.connect(
            lambda: self.recorte_btn.setEnabled(self.lienzo.seleccion.width() > 20 and self.lienzo.seleccion.height() > 20)
        )
        layout.addLayout(fila(None, cancelar, entera, self.recorte_btn))

    def _usar_recorte(self):
        self._recortar = True
        self.accept()

    def resultado(self) -> QImage:
        if not self._recortar:
            return self.imagen
        r = self.lienzo.seleccion
        e = self._escala
        return self.imagen.copy(QRect(round(r.x() * e), round(r.y() * e), round(r.width() * e), round(r.height() * e)))


def crear_navegador(url: str, parent=None) -> Optional[QWidget]:
    """La web oficial de la marca, o None si no se puede (y queda el dibujo)."""
    from roleplay.ui import navegador

    if not url or not navegador.disponible():
        return None
    return navegador.Navegador(url, parent)


# ---- la ventana ----


def _muestra_de_color(color: str, nombre: str) -> QPushButton:
    muestra = QPushButton()
    muestra.setObjectName("muestraColor")
    muestra.setCheckable(True)
    muestra.setFixedSize(28, 28)
    muestra.setToolTip(nombre)
    muestra.setCursor(Qt.CursorShape.PointingHandCursor)
    muestra.setStyleSheet(
        f"QPushButton#muestraColor {{ background-color: {color}; border: 2px solid {estilos.BORDE_FUERTE};"
        f" border-radius: 14px; padding: 0; }}"
        f"QPushButton#muestraColor:checked {{ border: 3px solid {estilos.ACENTO}; }}"
    )
    return muestra


class Configurador(QDialog):
    def __init__(self, modelo: autos.Modelo, saldo: int, moneda: str, parent=None):
        super().__init__(parent)
        from roleplay.servicios.economia import dinero

        self._dinero = lambda monto: dinero(monto, moneda)
        self.modelo = modelo
        self.saldo = saldo
        self.config = Configuracion(modelo.id)
        self._botones: dict[str, dict[str, QPushButton]] = {}
        self.foto: Optional[QImage] = None  # la del garage
        self.setWindowTitle(f"Configurador · {modelo.nombre_completo}")
        self.navegador = crear_navegador(modelo.configurador, self)
        con_web = self.navegador is not None

        layout = QHBoxLayout(self)
        layout.setContentsMargins(26, 24, 26, 22)
        layout.setSpacing(26)

        izquierda = QVBoxLayout()
        izquierda.setSpacing(10)
        marca = QLabel(modelo.marca.upper())
        marca.setFont(fuente_titulo(15, 3))
        marca.setStyleSheet(f"color: {estilos.ACENTO};")
        nombre = QLabel(modelo.nombre.upper())
        nombre.setFont(fuente_titulo(24 if con_web else 34, 1))
        izquierda.addWidget(marca)
        izquierda.addWidget(nombre)
        self.resumen_label = texto_suave()
        self.precio_label = QLabel()
        self.precio_label.setFont(fuente_titulo(30, 0.4))
        base = texto_suave(
            f"Precio base {self._dinero(modelo.precio)} · llega {modelo.dias_entrega} dias despues de pedirlo (en el juego) · "
            f"tenes {self._dinero(saldo)}"
        )
        if con_web:
            self.setWindowFlag(Qt.WindowType.WindowMaximizeButtonHint)
            pantalla = (parent.screen() if parent is not None else QGuiApplication.primaryScreen()).availableGeometry()
            self.resize(round(pantalla.width() * 0.92), round(pantalla.height() * 0.9))
            self.vista = None
            izquierda.addWidget(texto_suave(
                f"La web oficial de {modelo.marca}: armalo en 3D como lo quieras. Cuando te guste como se ve, sacale "
                "la foto para tu garage (si no, se saca sola al pedir)."
            ))
            izquierda.addWidget(self.navegador, 1)
            sacar = boton("Sacar foto", primario=True)
            sacar.clicked.connect(self._sacar_foto)
            pegar = boton("Pegar imagen")
            pegar.setToolTip("Una imagen copiada (por ejemplo, con la captura de Windows: Win+Shift+S)")
            pegar.clicked.connect(self._pegar_foto)
            izquierda.addLayout(fila(sacar, pegar, None))
            layout.addLayout(izquierda, 1)
        else:
            self.setMinimumWidth(980)
            self.vista = VistaAuto(self.config, alto=220)
            izquierda.addWidget(self.vista)
            izquierda.addWidget(self.resumen_label)
            izquierda.addWidget(self.precio_label)
            izquierda.addWidget(base)
            izquierda.addStretch()
            layout.addLayout(izquierda, 3)

        panel = QWidget()
        derecha = QVBoxLayout(panel)
        derecha.setContentsMargins(0, 0, 8, 0)
        derecha.setSpacing(8)
        derecha.addWidget(etiqueta_campo("Pintura"))
        derecha.addLayout(self._muestras("color", autos.COLORES))
        derecha.addLayout(self._grupo_de_chips("acabado", autos.ACABADOS))
        derecha.addWidget(etiqueta_campo("Llantas"))
        derecha.addLayout(self._grupo_de_chips("llantas", autos.LLANTAS))
        derecha.addWidget(etiqueta_campo("Pinzas de freno"))
        derecha.addLayout(self._grupo_de_chips("pinzas", autos.PINZAS))
        derecha.addWidget(etiqueta_campo("Franjas"))
        derecha.addLayout(self._grupo_de_chips("franja", autos.FRANJAS))
        self._colores_franja = self._muestras("color_franja", autos.COLORES)
        derecha.addLayout(self._colores_franja)
        derecha.addWidget(etiqueta_campo("Interior"))
        derecha.addLayout(self._grupo_de_chips("interior", autos.INTERIORES))
        derecha.addWidget(etiqueta_campo("Extras"))
        self._extras: dict[str, QPushButton] = {}
        fila_extras = QHBoxLayout()
        fila_extras.setSpacing(8)
        for extra in autos.EXTRAS:
            chip_extra = chip_alternable(f"{extra.nombre} +{extra.recargo:.0%}")
            chip_extra.clicked.connect(self._cambio)
            self._extras[extra.id] = chip_extra
            fila_extras.addWidget(chip_extra)
        fila_extras.addStretch()
        derecha.addLayout(fila_extras)
        derecha.addWidget(etiqueta_campo(f"Patente personalizada (+{self._dinero(autos.PATENTE_PERSONALIZADA)})"))
        self.patente_edit = QLineEdit()
        self.patente_edit.setPlaceholderText("Ej: SC 9")
        self.patente_edit.setMaxLength(autos.LARGO_PATENTE)
        self.patente_edit.textChanged.connect(self._cambio)
        derecha.addWidget(self.patente_edit)
        if con_web:
            derecha.addWidget(etiqueta_campo("La foto para tu garage"))
            self.foto_label = QLabel("Sin foto todavia: sacala de la web (o se saca sola al pedir).")
            self.foto_label.setObjectName("fotoGarage")
            self.foto_label.setWordWrap(True)
            self.foto_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.foto_label.setFixedSize(400, 225)
            self.foto_label.setStyleSheet(
                f"QLabel#fotoGarage {{ border: 1px dashed {estilos.BORDE_FUERTE}; border-radius: 8px; "
                f"color: {estilos.TEXTO_SUAVE}; padding: 12px; }}"
            )
            derecha.addWidget(self.foto_label)
            derecha.addSpacing(6)
            derecha.addWidget(self.resumen_label)
            derecha.addWidget(self.precio_label)
            derecha.addWidget(base)
        derecha.addStretch()
        self.pedir_btn = boton("Pedir", primario=True, icono_nombre="enviar")
        self.pedir_btn.clicked.connect(self.accept)
        cancelar = boton("Cancelar")
        cancelar.clicked.connect(self.reject)
        derecha.addLayout(fila(None, cancelar, self.pedir_btn))
        if con_web:
            area = con_scroll(panel)
            area.setFixedWidth(460)
            layout.addWidget(area)
        else:
            layout.addWidget(panel, 2)

        self._marcar_actual()
        self._cambio()

    # ---- armado ----

    def _muestras(self, grupo: str, opciones) -> QGridLayout:
        grilla = QGridLayout()
        grilla.setSpacing(8)
        botones = QButtonGroup(self)
        botones.setExclusive(True)
        self._botones[grupo] = {}
        for n, opcion in enumerate(opciones):
            muestra = _muestra_de_color(opcion.color, opcion.nombre)
            muestra.clicked.connect(lambda _=False, g=grupo, o=opcion.id: self._elegir(g, o))
            botones.addButton(muestra)
            self._botones[grupo][opcion.id] = muestra
            grilla.addWidget(muestra, 0, n)
        grilla.setColumnStretch(len(opciones), 1)
        return grilla

    def _grupo_de_chips(self, grupo: str, opciones) -> QHBoxLayout:
        layout = QHBoxLayout()
        layout.setSpacing(8)
        botones = QButtonGroup(self)
        botones.setExclusive(True)
        self._botones[grupo] = {}
        for opcion in opciones:
            texto = opcion.nombre + (f" +{opcion.recargo:.1%}".replace(".0%", "%") if opcion.recargo else "")
            chip_opcion = chip_alternable(texto)
            chip_opcion.clicked.connect(lambda _=False, g=grupo, o=opcion.id: self._elegir(g, o))
            botones.addButton(chip_opcion)
            self._botones[grupo][opcion.id] = chip_opcion
            layout.addWidget(chip_opcion)
        layout.addStretch()
        return layout

    def _marcar_actual(self):
        for grupo, botones in self._botones.items():
            botones[getattr(self.config, grupo)].setChecked(True)

    # ---- cambios ----

    def _elegir(self, grupo: str, opcion_id: str):
        setattr(self.config, grupo, opcion_id)
        self._botones[grupo][opcion_id].setChecked(True)
        self._cambio()

    def _cambio(self):
        self.config.extras = [e for e, chip_extra in self._extras.items() if chip_extra.isChecked()]
        self.config.patente = autos.limpiar_patente(self.patente_edit.text())
        for muestra in self._botones["color_franja"].values():
            muestra.setVisible(self.config.franja != "ninguna")
        total = autos.precio(self.config)
        if self.vista is not None:
            self.vista.poner(self.config)
        self.resumen_label.setText(esc(autos.primera_mayuscula(autos.describir(self.config))))
        self.precio_label.setText(self._dinero(total))
        alcanza = self.saldo >= total
        self.precio_label.setStyleSheet("" if alcanza else f"color: {estilos.NEGATIVO};")
        self.pedir_btn.setEnabled(alcanza)
        self.pedir_btn.setText(f"PEDIR · {self._dinero(total)}" if alcanza else "NO TE ALCANZA")

    def configuracion(self) -> Configuracion:
        return Configuracion.desde_dict(self.config.a_dict())

    # ---- la foto del garage ----

    def _sacar_foto(self):
        recorte = RecortarFoto(self.navegador.foto(), self)
        if recorte.exec() == QDialog.DialogCode.Accepted:
            self._poner_foto(recorte.resultado())
        recorte.deleteLater()

    def _pegar_foto(self):
        imagen = QApplication.clipboard().image()
        if imagen.isNull():
            QMessageBox.information(self, "No hay ninguna imagen copiada",
                                    "Copia una imagen (por ejemplo con Win+Shift+S) y volve a apretar.")
            return
        self._poner_foto(imagen)

    def _poner_foto(self, imagen: QImage):
        imagen.setDevicePixelRatio(1.0)
        self.foto = imagen
        self.foto_label.setPixmap(_nitida(imagen, self.foto_label.size()))

    def accept(self):
        if self.navegador is not None and self.foto is None:
            self.foto = self.navegador.foto()  # al pedir, la foto se saca sola
        super().accept()
