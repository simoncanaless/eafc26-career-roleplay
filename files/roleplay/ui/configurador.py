"""
Configurador de autos: una ventana con la vista previa del auto (dibujada
por la app: siluetas propias por carroceria, pintadas con lo que se elige)
y las opciones. El precio sale de servicios/autos.py.
"""

from dataclasses import dataclass

from PySide6.QtCore import QByteArray, QRectF, QSize, Qt
from PySide6.QtGui import QPainter
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtWidgets import (
    QButtonGroup,
    QDialog,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from roleplay.servicios import autos
from roleplay.servicios.autos import Configuracion
from roleplay.ui import estilos
from roleplay.ui.comun import esc
from roleplay.ui.componentes import boton, chip_alternable, etiqueta_campo, fila, texto_suave
from roleplay.ui.estilos import fuente_titulo

# ---- el dibujo ----

@dataclass(frozen=True)
class Silueta:
    """Una familia de autos, de costado (viewBox 400 x 170, mirando a la
    izquierda). Dibujos propios que recuerdan la forma de cada tipo, como
    hace GTA: parecidos, nunca copias."""

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


# El renderizador SVG de Qt no hace clip-path: lo que va "adentro" de la
# carroceria (franjas, fibra de carbono) va en el degradado de la pintura, y
# los parantes se dibujan solo entre el techo y la base de la ventana.
SILUETAS = {
    # Lamborghini: cuna baja y angulosa, arcos hexagonales, toma de aire
    "cuna": Silueta(
        "M 14 112 L 16 106 L 60 96 L 132 86 L 186 60 L 236 58 L 330 76 L 380 82 L 386 92 L 384 116 L 330 118 "
        "L 326 98 L 312 91 L 288 91 L 274 98 L 270 118 L 126 118 L 122 98 L 108 91 L 84 91 L 70 98 L 66 118 L 18 118 Z",
        "M 142 84 L 188 63 L 232 61 L 292 75 Z",
        ((96, 121, 23), (300, 121, 23)), 58, 84, (204, 66), puertas=(240,),
        faro='<path d="M 22 105 L 54 98 L 56 101 L 26 108 Z" fill="#F4F6F8"/>',
        luz='<rect x="370" y="86" width="14" height="3" fill="#E0242F"/>',
        detalles='<path d="M 250 99 L 292 88 L 288 108 L 254 108 Z" fill="{vidrio}"/>',
    ),
    # Porsche 911: el techo cae redondeado hasta la cola, faro redondo, barra de luz
    "911": Silueta(
        "M 18 116 L 20 102 Q 24 92 44 90 Q 70 84 116 80 Q 150 56 190 51 Q 236 47 284 62 Q 346 82 382 100 "
        "L 384 118 L 330 118 A 28 28 0 0 0 272 118 L 124 118 A 28 28 0 0 0 68 118 Z",
        "M 130 79 Q 160 59 192 56 Q 236 53 272 64 Z",
        ((96, 121, 23), (301, 121, 23)), 50, 79, (200, 63), parantes=(222,), puertas=(226,),
        faro='<ellipse cx="54" cy="91" rx="9" ry="5" fill="#F4F6F8"/>',
        luz='<path d="M 344 86 L 378 99 L 378 102 L 344 89 Z" fill="#E0242F"/>',
        aleron='<path d="M 326 76 L 328 58 M 350 84 L 352 58" stroke="{oscuro}" stroke-width="3"/>'
               '<path d="M 310 56 L 370 53 L 372 60 L 312 62 Z" fill="{oscuro}"/>',
    ),
    # Ferrari 296/SF90, McLaren: cabina adelantada y toma de aire detras de la puerta
    "super": Silueta(
        "M 16 114 L 18 104 Q 22 96 42 94 L 110 86 Q 150 56 196 52 L 230 52 Q 290 56 336 78 L 378 84 "
        "Q 386 88 384 100 L 382 118 L 328 118 A 28 28 0 0 0 272 118 L 126 118 A 28 28 0 0 0 70 118 Z",
        "M 124 85 Q 156 60 198 56 L 228 56 Q 262 60 286 71 Z",
        ((98, 121, 23), (300, 121, 23)), 52, 85, (194, 64), puertas=(232,),
        faro='<ellipse cx="40" cy="98" rx="12" ry="2.6" fill="#F4F6F8"/>',
        luz='<rect x="374" y="90" width="9" height="4" rx="1.5" fill="#E0242F"/>',
        detalles='<path d="M 246 97 Q 262 85 292 84 L 294 104 Q 270 105 246 97 Z" fill="{vidrio}"/>',
    ),
    # Bugatti: largo y redondo, con la linea en C cromada
    "hiper": Silueta(
        "M 16 112 Q 18 98 40 94 Q 90 84 128 80 Q 166 52 210 48 L 244 48 Q 300 52 342 76 Q 380 84 386 100 "
        "L 384 118 L 328 118 A 29 29 0 0 0 270 118 L 128 118 A 29 29 0 0 0 70 118 Z",
        "M 140 79 Q 172 56 210 52 L 242 52 Q 286 56 318 72 Z",
        ((99, 121, 24), (299, 121, 24)), 48, 79, (212, 60),
        luz='<rect x="366" y="92" width="16" height="3" rx="1.5" fill="#E0242F"/>',
        detalles='<path d="M 264 82 Q 226 82 224 99 Q 226 114 264 114" fill="none" stroke="{cromo}" stroke-width="3"/>',
    ),
    # Aston Martin, Bentley, Roma, Spectre: capo largo, cola corta
    "gt": Silueta(
        "M 16 116 L 18 102 Q 22 92 44 89 L 150 78 Q 188 52 226 48 L 262 48 Q 316 52 350 74 L 380 80 "
        "Q 388 84 386 98 L 384 118 L 334 118 A 28 28 0 0 0 278 118 L 120 118 A 28 28 0 0 0 64 118 Z",
        "M 162 77 Q 194 56 228 52 L 260 52 Q 304 56 336 72 Z",
        ((92, 121, 23), (306, 121, 23)), 48, 77, (224, 60), parantes=(250,), puertas=(252,),
        faro='<ellipse cx="40" cy="95" rx="12" ry="3.2" fill="#F4F6F8"/>',
        luz='<rect x="374" y="86" width="9" height="4.5" rx="1.5" fill="#E0242F"/>',
    ),
    # Taycan, AMG GT 63: cuatro puertas, bajo y liso, barra de luz atras
    "sedan": Silueta(
        "M 16 114 L 18 102 Q 22 94 42 91 L 118 82 Q 156 54 200 49 L 268 48 Q 320 52 354 76 L 380 82 "
        "Q 388 86 386 100 L 384 118 L 332 118 A 28 28 0 0 0 276 118 L 124 118 A 28 28 0 0 0 68 118 Z",
        "M 130 81 Q 162 58 202 54 L 266 53 Q 308 56 340 74 Z",
        ((96, 121, 23), (304, 121, 23)), 48, 81, (188, 62), parantes=(214, 278), puertas=(216, 280),
        luz='<rect x="350" y="84" width="32" height="3" rx="1.5" fill="#E0242F"/>',
    ),
    # Urus, Purosangue, Cayenne: SUV con el techo que cae
    "suv": Silueta(
        "M 16 118 L 16 92 Q 18 80 40 77 L 116 70 Q 146 42 184 38 L 290 38 Q 336 42 360 64 L 380 70 "
        "Q 388 74 386 92 L 384 118 L 334 118 A 30 30 0 0 0 274 118 L 130 118 A 30 30 0 0 0 70 118 Z",
        "M 128 69 Q 152 46 186 43 L 288 43 Q 326 46 346 64 Z",
        ((100, 121, 25), (304, 121, 25)), 38, 69, (194, 50), parantes=(222, 286), puertas=(224, 288),
        faro='<path d="M 18 86 L 42 80 L 44 84 L 20 90 Z" fill="#F4F6F8"/>',
        luz='<rect x="376" y="74" width="9" height="5" rx="1.5" fill="#E0242F"/>',
    ),
    # Cullinan, Range Rover: alto y recto, de frente vertical
    "suv_lujo": Silueta(
        "M 14 118 L 14 84 Q 14 70 30 68 L 100 64 Q 124 36 150 32 L 352 32 Q 368 32 374 46 L 384 64 L 386 118 "
        "L 336 118 A 31 31 0 0 0 274 118 L 132 118 A 31 31 0 0 0 70 118 Z",
        "M 112 63 Q 132 40 154 37 L 348 37 Q 362 38 368 52 L 372 62 Z",
        ((101, 121, 26), (305, 121, 26)), 32, 63, (174, 47), parantes=(206, 290), puertas=(208, 292),
        faro='<rect x="15" y="73" width="18" height="6" rx="2" fill="#F4F6F8"/>',
        luz='<rect x="378" y="68" width="6" height="18" rx="1.5" fill="#E0242F"/>',
        cola=386,
    ),
    # G 63: una caja, parabrisas recto y la rueda de auxilio atras
    "g": Silueta(
        "M 18 118 L 18 76 L 26 70 L 108 68 L 122 34 L 356 34 L 362 40 L 364 118 L 334 118 "
        "A 31 31 0 0 0 274 118 L 132 118 A 31 31 0 0 0 70 118 Z",
        "M 126 66 L 137 40 L 352 40 L 354 64 Z",
        ((101, 121, 26), (305, 121, 26)), 34, 66, (174, 50), parantes=(204, 282), puertas=(206, 284),
        faro='<circle cx="28" cy="80" r="6" fill="#F4F6F8"/>',
        luz='<rect x="356" y="70" width="5" height="12" rx="1" fill="#E0242F"/>',
        detalles='<circle cx="372" cy="84" r="17" fill="#121315"/><circle cx="372" cy="84" r="10" fill="{oscuro}"/>',
        cola=364,
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


def _pintura(base: str, acabado: str, techo: float, bandas: list) -> str:
    """El degradado de la pintura (en coordenadas de la carroceria) con las
    bandas -franjas, fibra de carbono- metidas como cortes de color."""
    if acabado == "mate":
        stops = [(techo, _mezclar(base, "#000000", 0.08)), (PISO, _mezclar(base, "#000000", 0.18))]
    elif acabado == "metalizado":
        stops = [(techo, _mezclar(base, "#FFFFFF", 0.45)), ((techo + PISO) / 2, base),
                 (PISO, _mezclar(base, "#000000", 0.45))]
    else:
        stops = [(techo, _mezclar(base, "#FFFFFF", 0.22)), (PISO, _mezclar(base, "#000000", 0.25))]
    puntos = list(stops)
    for desde, hasta, color in bandas:  # un borde neto: dos puntos casi en el mismo lugar
        puntos += [(desde - 0.01, _color_en(stops, desde)), (desde, color), (hasta, color),
                   (hasta + 0.01, _color_en(stops, hasta))]
    puntos.sort(key=lambda punto: punto[0])
    largo = PISO - techo
    stops_svg = "".join(
        f'<stop offset="{max(0.0, min(1.0, (y - techo) / largo)):.4f}" stop-color="{color}"/>' for y, color in puntos
    )
    return (f'<linearGradient id="pintura" gradientUnits="userSpaceOnUse" x1="0" y1="{techo}" x2="0" y2="{PISO}">'
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


def svg_auto(config: Configuracion) -> str:
    """El auto configurado, de costado, como SVG (400 x 170)."""
    modelo = autos.POR_ID[config.modelo]
    forma = SILUETAS[modelo.carroceria]
    base = autos.opcion("color", config.color).color
    colores = {"vidrio": VIDRIO, "oscuro": _mezclar(base, "#000000", 0.45), "cromo": CROMO}
    color_franja = autos.opcion("color", config.color_franja).color
    bandas = [(y, y + alto, color_franja)
              for y, alto in {"lateral": ((97, 6),), "doble": ((95, 3), (101, 3))}.get(config.franja, ())]
    if "carbono" in config.extras:
        bandas.append((111, PISO, "#1A1B1E"))
    linea = _mezclar(base, "#000000", 0.5)
    partes = [
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 400 170">',
        f'<defs>{_pintura(base, config.acabado, forma.techo, bandas)}</defs>',
        '<ellipse cx="200" cy="145" rx="185" ry="7" fill="#000000" fill-opacity="0.45"/>',
    ]
    if modelo.aleron and forma.aleron:
        partes.append(forma.aleron.format(**colores))
    partes += [
        f'<path d="{forma.cuerpo}" fill="url(#pintura)" stroke="{linea}" stroke-width="1.2"/>',
        f'<path d="{forma.ventana}" fill="{VIDRIO}" stroke="{linea}" stroke-width="1"/>',
        # el respaldo se ve por la ventana: el color del interior
        f'<rect x="{forma.asiento[0]}" y="{forma.asiento[1]}" width="11" height="14" rx="3" '
        f'fill="{INTERIOR.get(config.interior, "#1C1C1E")}"/>',
    ]
    for x in forma.parantes:  # solo dentro de la ventana
        partes.append(f'<line x1="{x}" y1="{forma.techo + 5}" x2="{x - 3}" y2="{forma.base_ventana - 1}" '
                      f'stroke="{_mezclar(base, "#000000", 0.35)}" stroke-width="5"/>')
    for x in forma.puertas:
        partes.append(f'<line x1="{x - 4}" y1="{forma.base_ventana + 4}" x2="{x - 1}" y2="114" '
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
        self.setWindowTitle(f"Configurador · {modelo.nombre_completo}")
        self.setMinimumWidth(980)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(26, 24, 26, 22)
        layout.setSpacing(26)

        izquierda = QVBoxLayout()
        izquierda.setSpacing(10)
        marca = QLabel(modelo.marca.upper())
        marca.setFont(fuente_titulo(15, 3))
        marca.setStyleSheet(f"color: {estilos.ACENTO};")
        nombre = QLabel(modelo.nombre.upper())
        nombre.setFont(fuente_titulo(34, 1))
        izquierda.addWidget(marca)
        izquierda.addWidget(nombre)
        self.vista = VistaAuto(self.config, alto=220)
        izquierda.addWidget(self.vista)
        self.resumen_label = texto_suave()
        izquierda.addWidget(self.resumen_label)
        self.precio_label = QLabel()
        self.precio_label.setFont(fuente_titulo(30, 0.4))
        izquierda.addWidget(self.precio_label)
        izquierda.addWidget(texto_suave(
            f"Precio base {self._dinero(modelo.precio)} · llega {modelo.dias_entrega} dias despues de pedirlo (en el juego) · "
            f"tenes {self._dinero(saldo)}"
        ))
        izquierda.addStretch()
        layout.addLayout(izquierda, 3)

        derecha = QVBoxLayout()
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
        derecha.addStretch()
        self.pedir_btn = boton("Pedir", primario=True, icono_nombre="enviar")
        self.pedir_btn.clicked.connect(self.accept)
        cancelar = boton("Cancelar")
        cancelar.clicked.connect(self.reject)
        derecha.addLayout(fila(None, cancelar, self.pedir_btn))
        layout.addLayout(derecha, 2)

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
        self.vista.poner(self.config)
        self.resumen_label.setText(esc(autos.primera_mayuscula(autos.describir(self.config))))
        self.precio_label.setText(self._dinero(total))
        alcanza = self.saldo >= total
        self.precio_label.setStyleSheet("" if alcanza else f"color: {estilos.NEGATIVO};")
        self.pedir_btn.setEnabled(alcanza)
        self.pedir_btn.setText(f"PEDIR · {self._dinero(total)}" if alcanza else "NO TE ALCANZA")

    def configuracion(self) -> Configuracion:
        return Configuracion.desde_dict(self.config.a_dict())
