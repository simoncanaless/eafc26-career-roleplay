"""
El computador, como en GTA (pedido de Simon, 2026-10-26): un escritorio con los iconos de los sitios donde se
compra todo lo de la app, y un navegador que los abre con su direccion (se puede escribir la direccion o volver
atras). Los sitios son INVENTADOS (nombre, dominio, colores: nada de marcas reales en el logo ni el diseno),
como Legendary Motorsport o Dynasty 8 en GTA; lo que venden si es lo de la app: el concesionario con las marcas
reales en texto y el configurador oficial, el marketplace de culto, las casas, yates, aviones, relojes, ropa,
muebles y tecnologia del catalogo (con el boton a las webs oficiales de ui/tienda.py), las donaciones y el banco
(saldo, bienes para vender, pedidos y movimientos).

No tiene logica propia de compras: cada boton llama a la PaginaVida (la misma plata, prensa e hinchas), y cuando
Vida se redibuja (`PaginaVida.mostrada`) el sitio abierto se vuelve a armar.
"""

from dataclasses import dataclass
from typing import Optional

from PySide6.QtCore import QRectF, QSize, Qt
from PySide6.QtGui import QColor, QFont, QLinearGradient, QPainter, QPixmap
from PySide6.QtWidgets import (
    QFrame, QGridLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton, QScrollArea, QStackedWidget, QToolButton,
    QVBoxLayout, QWidget,
)

from roleplay.database import get_economia
from roleplay.servicios import autos, configurador, economia, marketplace, tiendas
from roleplay.servicios.economia import CATALOGO, dinero
from roleplay.ui import estilos
from roleplay.ui.comun import ejecutar_en_hilo, esc
from roleplay.ui.componentes import boton, chip_alternable, limpiar_layout, texto_suave
from roleplay.ui.estilos import fuente_titulo

ALTO_PANTALLA = 820
FOTO_TARJETA = QSize(300, 169)
COLUMNAS = 4
BORDE = "#2A3340"


@dataclass(frozen=True)
class Sitio:
    id: str
    nombre: str
    dominio: str
    lema: str
    color: str  # el de su marca (inventada)
    tipo: str  # inicio | autos | usados | tienda | donar | banco
    categorias: tuple = ()
    sigla: str = ""


SITIOS = [
    Sitio("inicio", "FutNet", "www.futnet.com", "Todo lo que se puede comprar un crack, en un solo lugar", "#00C389",
          "inicio", sigla="FN"),
    Sitio("elite", "Elite Motors", "www.elitemotors.net", "Autos nuevos de las marcas que soñabas de chico", "#C9A227",
          "autos", sigla="EM"),
    Sitio("culto", "Culto & Clasicos", "www.cultoyclasicos.com", "Usados, JDM y autos de coleccion: cambian cada semana",
          "#E8772E", "usados", sigla="C&C"),
    Sitio("horizonte", "Horizonte Propiedades", "www.horizonteprop.com", "Tu proxima casa, con vista a lo que quieras",
          "#2E9E6B", "tienda", ("casa",), "HP"),
    Sitio("altamar", "Altamar Yachts", "www.altamaryachts.com", "El mar es tuyo", "#1F7AE0", "tienda", ("yate",), "AY"),
    Sitio("cielo", "Cielo Privado", "www.cieloprivado.aero", "Volar sin escalas ni filas", "#5BB8E8", "tienda",
          ("avion",), "CP"),
    Sitio("vitrina", "La Vitrina", "www.lavitrina.luxe", "Relojes y joyas para la muñeca de un campeon", "#B8892B",
          "tienda", ("reloj",), "LV"),
    Sitio("pasarela", "Pasarela", "www.pasarela.fashion", "La ropa que vas a lucir en la alfombra roja", "#E0527E",
          "tienda", ("moda",), "P"),
    Sitio("casabella", "Casa Bella", "www.casabella.home", "Muebles y diseño para tu casa nueva", "#A8643A", "tienda",
          ("muebles",), "CB"),
    Sitio("pixel", "Pixel Store", "www.pixelstore.tech", "Tecnologia para jugar, entrenar y descansar", "#7A63E8",
          "tienda", ("tecnologia",), "PX"),
    Sitio("corazon", "Corazon Solidario", "www.corazonsolidario.org", "Devolver un poco de lo que te dio el futbol",
          "#E85D5D", "donar", ("donacion",), "CS"),
    Sitio("banco", "Banco Crack", "www.bancocrack.com", "Tu sueldo, tus bienes y tus movimientos", "#12A37F", "banco",
          sigla="BC"),
]
POR_ID = {s.id: s for s in SITIOS}


def buscar_sitio(texto: str) -> Optional[Sitio]:
    """Lo que se escribe en la barra de direcciones: el dominio (con o sin www/https), el nombre o el id."""
    limpio = texto.strip().lower().removeprefix("https://").removeprefix("http://").removeprefix("www.").rstrip("/")
    for sitio in SITIOS:
        if limpio in (sitio.dominio.removeprefix("www."), sitio.nombre.lower(), sitio.id):
            return sitio
    return None


def logo(sitio: Sitio, lado: int = 64) -> QPixmap:
    """El icono del sitio: un cuadrado redondeado de su color con su sigla."""
    imagen = QPixmap(lado, lado)
    imagen.fill(Qt.GlobalColor.transparent)
    pintor = QPainter(imagen)
    pintor.setRenderHint(QPainter.RenderHint.Antialiasing)
    degradado = QLinearGradient(0, 0, lado, lado)
    degradado.setColorAt(0, QColor(sitio.color).lighter(125))
    degradado.setColorAt(1, QColor(sitio.color).darker(140))
    pintor.setBrush(degradado)
    pintor.setPen(Qt.PenStyle.NoPen)
    pintor.drawRoundedRect(QRectF(2, 2, lado - 4, lado - 4), lado * 0.22, lado * 0.22)
    letra = QFont(fuente_titulo(int(lado * (0.42 if len(sitio.sigla) < 3 else 0.32))))
    pintor.setFont(letra)
    pintor.setPen(QColor("white"))
    pintor.drawText(QRectF(0, 0, lado, lado), Qt.AlignmentFlag.AlignCenter, sitio.sigla)
    pintor.end()
    return imagen


def _foto(ruta, tamano: QSize = FOTO_TARJETA) -> Optional[QLabel]:
    """La foto recortada al centro para llenar el cuadro (como las tarjetas de una web)."""
    imagen = QPixmap(str(ruta)) if ruta else QPixmap()
    if imagen.isNull():
        return None
    imagen = imagen.scaled(tamano, Qt.AspectRatioMode.KeepAspectRatioByExpanding, Qt.TransformationMode.SmoothTransformation)
    x, y = (imagen.width() - tamano.width()) // 2, (imagen.height() - tamano.height()) // 2
    etiqueta = QLabel()
    etiqueta.setPixmap(imagen.copy(x, y, tamano.width(), tamano.height()))
    return etiqueta


def _portadas(modelos: list) -> dict:
    """{id del modelo: render oficial de fabrica} de los que tienen configurador oficial (en un hilo, una vez)."""
    salida = {}
    for modelo in modelos:
        catalogo = configurador.de_modelo(modelo)
        if catalogo:
            ruta = configurador.render(catalogo, configurador.de_fabrica(catalogo))
            if ruta:
                salida[modelo.id] = ruta
    return salida


class Escritorio(QWidget):
    """El fondo de pantalla (pintado) con los iconos de los sitios."""

    def __init__(self, abrir):
        super().__init__()
        grilla = QGridLayout(self)
        grilla.setContentsMargins(28, 28, 28, 28)
        grilla.setHorizontalSpacing(18)
        grilla.setVerticalSpacing(14)
        for n, sitio in enumerate(SITIOS):
            icono = QToolButton()
            icono.setObjectName("iconoEscritorio")
            icono.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextUnderIcon)
            icono.setIcon(logo(sitio, 96))
            icono.setIconSize(QSize(56, 56))
            icono.setText(sitio.nombre.replace("&", "&&"))  # (un & solo es un atajo de teclado para Qt)
            icono.setFixedSize(136, 104)
            icono.setCursor(Qt.CursorShape.PointingHandCursor)
            icono.setProperty("sitio", sitio.id)
            icono.setStyleSheet("QToolButton#iconoEscritorio { background: transparent; border: none; color: white; "
                                "border-radius: 8px; } QToolButton#iconoEscritorio:hover { background: rgba(255,255,255,0.12); }")
            icono.clicked.connect(lambda _=False, s=sitio.id: abrir(s))
            grilla.addWidget(icono, n % 6, n // 6, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
        grilla.setColumnStretch(10, 1)
        grilla.setRowStretch(10, 1)

    def paintEvent(self, _evento):
        pintor = QPainter(self)
        fondo = QLinearGradient(0, 0, self.width(), self.height())
        fondo.setColorAt(0, QColor("#0B1F3A"))
        fondo.setColorAt(0.55, QColor("#13294B"))
        fondo.setColorAt(1, QColor("#3B1D5A"))
        pintor.fillRect(self.rect(), fondo)
        pintor.setPen(QColor(255, 255, 255, 22))
        pintor.setFont(fuente_titulo(min(140, max(48, self.width() // 9)), 6))
        pintor.drawText(self.rect().adjusted(0, 0, -40, -30), Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignBottom,
                        "CRACK OS")
        pintor.end()


class PaginaComputador(QWidget):
    def __init__(self, vida):
        super().__init__()
        self.vida = vida
        self.sitio: Optional[Sitio] = None
        self.historial: list = []
        self.marca = ""  # el filtro de Elite Motors
        self._portadas: Optional[dict] = None  # None: todavia no se pidieron
        vida.mostrada.connect(self._refrescar)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(40, 34, 40, 34)
        pantalla = QFrame()
        pantalla.setObjectName("pantallaPC")
        pantalla.setStyleSheet(f"QFrame#pantallaPC {{ background: {estilos.FONDO}; border: 2px solid #1C2430; "
                               "border-radius: 12px; }")
        pantalla.setFixedHeight(ALTO_PANTALLA)
        caja = QVBoxLayout(pantalla)
        caja.setContentsMargins(0, 0, 0, 0)
        caja.setSpacing(0)
        self.stack = QStackedWidget()
        self.escritorio = Escritorio(self.abrir)
        self.stack.addWidget(self.escritorio)
        self.stack.addWidget(self._navegador())
        caja.addWidget(self.stack, 1)
        caja.addWidget(self._barra_de_tareas())
        layout.addWidget(pantalla)
        layout.addStretch()

    # ---- el marco ----

    def _navegador(self) -> QWidget:
        ventana = QWidget()
        caja = QVBoxLayout(ventana)
        caja.setContentsMargins(0, 0, 0, 0)
        caja.setSpacing(0)
        barra = QFrame()
        barra.setStyleSheet(f"background: {estilos.PANEL}; border-bottom: 1px solid {BORDE};")
        fila_barra = QHBoxLayout(barra)
        fila_barra.setContentsMargins(10, 8, 10, 8)
        self.atras_btn = boton("Atras")
        self.atras_btn.clicked.connect(self.atras)
        inicio = boton("FutNet")
        inicio.setToolTip("La pagina de inicio, con todos los sitios")
        inicio.clicked.connect(lambda: self.abrir("inicio"))
        self.direccion = QLineEdit()
        self.direccion.setToolTip("Escribi la direccion de un sitio (por ejemplo www.elitemotors.net)")
        self.direccion.returnPressed.connect(self.ir_a_direccion)
        cerrar = boton("Cerrar")
        cerrar.setToolTip("Cerrar el navegador y volver al escritorio")
        cerrar.clicked.connect(self.cerrar)
        fila_barra.addWidget(self.atras_btn)
        fila_barra.addWidget(inicio)
        fila_barra.addWidget(self.direccion, 1)
        fila_barra.addWidget(cerrar)
        caja.addWidget(barra)
        self.aviso = QLabel()
        self.aviso.setWordWrap(True)
        self.aviso.setStyleSheet(f"background: {estilos.PANEL}; border-left: 4px solid {estilos.ACENTO}; padding: 10px;")
        self.aviso.hide()
        caja.addWidget(self.aviso)
        self.desplazable = QScrollArea()
        self.desplazable.setWidgetResizable(True)
        self.desplazable.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.cuerpo = QWidget()
        self.cuerpo_layout = QVBoxLayout(self.cuerpo)
        self.cuerpo_layout.setContentsMargins(0, 0, 0, 24)
        self.cuerpo_layout.setSpacing(16)
        self.desplazable.setWidget(self.cuerpo)
        caja.addWidget(self.desplazable, 1)
        return ventana

    def _barra_de_tareas(self) -> QWidget:
        barra = QFrame()
        barra.setStyleSheet("background: #080C12; border-top: 1px solid #1C2430;")
        fila_barra = QHBoxLayout(barra)
        fila_barra.setContentsMargins(12, 6, 16, 6)
        self.inicio_btn = QPushButton("  CRACK OS")
        self.inicio_btn.setFont(fuente_titulo(14, 2))
        self.inicio_btn.setStyleSheet(f"color: {estilos.ACENTO}; background: transparent; border: none;")
        self.inicio_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.inicio_btn.setToolTip("Volver al escritorio")
        self.inicio_btn.clicked.connect(self.cerrar)
        self.tarea = QLabel()
        self.reloj = QLabel()
        self.reloj.setStyleSheet(f"color: {estilos.TEXTO_SUAVE};")
        fila_barra.addWidget(self.inicio_btn)
        fila_barra.addSpacing(16)
        fila_barra.addWidget(self.tarea)
        fila_barra.addStretch()
        fila_barra.addWidget(self.reloj)
        return barra

    # ---- navegar ----

    def actualizar(self):
        """El menu la llama al entrar: Vida lee la partida (cobra el sueldo) y al redibujarse refresca el sitio."""
        self.vida.actualizar()
        self._refrescar()

    def abrir(self, sitio_id: str, recordar: bool = True):
        if recordar and self.sitio is not None and self.sitio.id != sitio_id and self.stack.currentIndex() == 1:
            self.historial.append(self.sitio.id)
        self.sitio = POR_ID[sitio_id]
        self.aviso.hide()
        self.stack.setCurrentIndex(1)
        self._dibujar_sitio()
        self.desplazable.verticalScrollBar().setValue(0)

    def atras(self):
        if self.historial:
            self.abrir(self.historial.pop(), recordar=False)
        else:
            self.cerrar()

    def cerrar(self):
        self.stack.setCurrentIndex(0)
        self.sitio, self.historial = None, []
        self._barra()

    def ir_a_direccion(self):
        sitio = buscar_sitio(self.direccion.text())
        if sitio is not None:
            self.abrir(sitio.id)
            return
        self.aviso.setText(f"<b>No se encontro el sitio</b> «{esc(self.direccion.text())}». Proba con alguno de FutNet.")
        self.aviso.show()

    def _refrescar(self):
        if self.sitio is not None and self.stack.currentIndex() == 1:
            posicion = self.desplazable.verticalScrollBar().value()
            self._dibujar_sitio()
            self.desplazable.verticalScrollBar().setValue(posicion)
        self._barra()

    # ---- los datos (los de Vida) ----

    def _datos(self) -> tuple:
        perfil = self.vida.perfil
        e = get_economia(perfil.id) if perfil is not None else {}
        return perfil, e or {}, self.vida._moneda(), self.vida._hoy(e) if e else None

    def _barra(self):
        _, e, moneda, hoy = self._datos()
        self.tarea.setText(f"🌐  {self.sitio.nombre}" if self.sitio is not None and self.stack.currentIndex() == 1 else "")
        fecha = hoy.strftime("%d/%m/%Y") if hoy is not None else "sin partida"
        saldo = dinero(e.get("saldo", 0), moneda) if e else "-"
        self.reloj.setText(f"Saldo {saldo}   ·   {fecha}")

    def _accion(self, funcion, *args):
        """Una compra o venta en Vida; lo que Vida cuenta (seguidores, reputacion) sale arriba del sitio."""
        antes = self.vida.resultado_label.text()
        funcion(*args)
        despues = self.vida.resultado_label.text()
        if despues and despues != antes:
            self.aviso.setText(despues)
            self.aviso.show()

    # ---- los sitios ----

    def _dibujar_sitio(self):
        sitio = self.sitio
        self.direccion.setText(f"https://{sitio.dominio}")
        self.atras_btn.setEnabled(bool(self.historial))
        limpiar_layout(self.cuerpo_layout)
        self.cuerpo_layout.addWidget(self._cabecera(sitio))
        perfil, e, moneda, hoy = self._datos()
        contenido = QVBoxLayout()
        contenido.setContentsMargins(28, 0, 28, 0)
        contenido.setSpacing(14)
        self.cuerpo_layout.addLayout(contenido)
        if sitio.tipo != "inicio" and not e:
            contenido.addWidget(texto_suave("Tu plata sale de tu sueldo en la Carrera Jugador de FC 26: crea tu personaje "
                                            "y juega (o deja el autoguardado) para tener saldo."))
        dibujar = {"inicio": self._inicio, "autos": self._autos, "usados": self._usados, "tienda": self._tienda,
                   "donar": self._tienda, "banco": self._banco}[sitio.tipo]
        dibujar(contenido, sitio, perfil, e, moneda, hoy)
        self.cuerpo_layout.addStretch()
        self._barra()

    def _cabecera(self, sitio: Sitio) -> QWidget:
        banda = QFrame()
        banda.setObjectName("cabeceraSitio")
        claro, oscuro = QColor(sitio.color).darker(115).name(), QColor(sitio.color).darker(260).name()
        banda.setStyleSheet(f"QFrame#cabeceraSitio {{ background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 {claro}, "
                            f"stop:1 {oscuro}); }} QLabel {{ background: transparent; color: white; }}")
        fila_banda = QHBoxLayout(banda)
        fila_banda.setContentsMargins(28, 22, 28, 22)
        imagen = QLabel()
        imagen.setPixmap(logo(sitio, 72))
        textos = QVBoxLayout()
        nombre = QLabel(sitio.nombre.upper())
        nombre.setFont(fuente_titulo(34, 3))
        lema = QLabel(sitio.lema)
        textos.addWidget(nombre)
        textos.addWidget(lema)
        fila_banda.addWidget(imagen)
        fila_banda.addSpacing(10)
        fila_banda.addLayout(textos)
        fila_banda.addStretch()
        return banda

    def _tarjeta(self, foto: Optional[QWidget], titulo: str, detalle: str, accion: Optional[QPushButton]) -> QFrame:
        tarjeta = QFrame()
        tarjeta.setObjectName("tarjetaSitio")
        tarjeta.setStyleSheet(f"QFrame#tarjetaSitio {{ background: {estilos.PANEL}; border: 1px solid {BORDE}; "
                              "border-radius: 10px; }")
        tarjeta.setFixedWidth(FOTO_TARJETA.width() + 24)
        caja = QVBoxLayout(tarjeta)
        caja.setContentsMargins(12, 12, 12, 12)
        caja.setSpacing(6)
        if foto is not None:
            caja.addWidget(foto, 0, Qt.AlignmentFlag.AlignHCenter)
        nombre = QLabel(f"<b>{esc(titulo)}</b>")
        nombre.setWordWrap(True)
        texto = QLabel(detalle)
        texto.setWordWrap(True)
        texto.setObjectName("suave")
        caja.addWidget(nombre)
        caja.addWidget(texto)
        caja.addStretch()
        if accion is not None:
            caja.addWidget(accion)
        return tarjeta

    def _grilla(self, contenido: QVBoxLayout, tarjetas: list):
        grilla = QGridLayout()
        grilla.setSpacing(14)
        for n, tarjeta in enumerate(tarjetas):
            grilla.addWidget(tarjeta, n // COLUMNAS, n % COLUMNAS, Qt.AlignmentFlag.AlignTop)
        grilla.setColumnStretch(COLUMNAS, 1)
        contenido.addLayout(grilla)

    def _boton_comprar(self, e: dict, precio: int, ya: bool, texto: str = "Comprar") -> QPushButton:
        accion = boton("Ya lo tenes" if ya else texto, primario=not ya)
        accion.setEnabled(bool(e) and not ya and e.get("saldo", 0) >= precio)
        if e and not ya and e.get("saldo", 0) < precio:
            accion.setToolTip(f"Te faltan {dinero(precio - e.get('saldo', 0), self.vida._moneda())}")
        return accion

    def _inicio(self, contenido, _sitio, _perfil, _e, _moneda, _hoy):
        contenido.addWidget(texto_suave("Los sitios de tu computador. Tambien podes escribir la direccion arriba."))
        tarjetas = []
        for sitio in SITIOS[1:]:
            entrar = boton("Entrar", primario=True)
            entrar.setProperty("sitio", sitio.id)
            entrar.clicked.connect(lambda _=False, s=sitio.id: self.abrir(s))
            imagen = QLabel()
            imagen.setPixmap(logo(sitio, 64))
            tarjetas.append(self._tarjeta(imagen, sitio.nombre, f"{esc(sitio.lema)}<br>{esc(sitio.dominio)}", entrar))
        self._grilla(contenido, tarjetas)

    def _tienda(self, contenido, sitio, _perfil, e, moneda, _hoy):
        for categoria in sitio.categorias:
            oficiales = tiendas.TIENDAS.get(categoria, [])
            if oficiales and e:
                webs = boton("Ver en las webs oficiales")
                webs.setProperty("tienda_real", categoria)
                webs.clicked.connect(lambda _=False, c=categoria: self._accion(self.vida.abrir_tienda_real, c))
                fila_webs = QHBoxLayout()
                fila_webs.addWidget(texto_suave(f"Tambien elegis algo de verdad en {esc(', '.join(t.nombre for t in oficiales))}."))
                fila_webs.addWidget(webs)
                contenido.addLayout(fila_webs)
            tarjetas = []
            for articulo in (a for a in CATALOGO if a.categoria == categoria):
                ya = economia.tiene(e, articulo.id) and not articulo.es_donacion
                accion = self._boton_comprar(e, articulo.precio, ya, "Donar" if articulo.es_donacion else "Comprar")
                accion.setProperty("articulo", articulo.id)
                accion.clicked.connect(lambda _=False, i=articulo.id: self._accion(self.vida._on_comprar, i))
                detalle = f"<span style='color:{estilos.ACENTO}; font-size: 15px'><b>{dinero(articulo.precio, moneda)}</b></span>"
                if articulo.mantenimiento:
                    detalle += f"<br>Mantenimiento {dinero(articulo.mantenimiento, moneda)} por semana"
                if articulo.ostentoso:
                    detalle += "<br>Exclusivo: la prensa lo va a ver"
                tarjetas.append(self._tarjeta(None, articulo.nombre, detalle, accion))
            self._grilla(contenido, tarjetas)

    def _autos(self, contenido, _sitio, _perfil, e, moneda, _hoy):
        if self._portadas is None:  # el render oficial de fabrica de cada modelo con configurador oficial (una vez)
            self._portadas = {}
            con_oficial = [m for m in autos.MODELOS if configurador.de_modelo(m)]
            if con_oficial:
                ejecutar_en_hilo(_portadas, con_oficial, al_completar=self._on_portadas, al_fallar=self._sin_portadas)
        filtros = QHBoxLayout()
        filtros.setSpacing(6)
        for marca in [""] + list(autos.MARCAS):
            chip = chip_alternable(marca or "Todas")
            chip.setChecked(marca == self.marca)
            chip.clicked.connect(lambda _=False, m=marca: self._filtrar_marca(m))
            filtros.addWidget(chip)
        filtros.addStretch()
        contenido.addLayout(filtros)
        contenido.addWidget(texto_suave("Se configura a tu gusto, se paga al encargarlo y llega dias despues en el juego."))
        tarjetas = []
        for modelo in (m for m in autos.MODELOS if not self.marca or m.marca == self.marca):
            oficial = configurador.de_modelo(modelo) is not None
            configurar = boton("Configurar", primario=True)
            configurar.setProperty("modelo", modelo.id)
            configurar.setEnabled(bool(e))
            configurar.clicked.connect(lambda _=False, i=modelo.id: self._accion(self.vida._on_configurar, i))
            foto = _foto(self._portadas.get(modelo.id)) if self._portadas else None
            if foto is None:
                from roleplay.ui.configurador import miniatura

                foto = miniatura(autos.Configuracion(modelo=modelo.id))
            detalle = (f"<span style='color:{estilos.ACENTO}; font-size: 15px'><b>desde {dinero(modelo.precio, moneda)}"
                       f"</b></span><br>Llega {modelo.dias_entrega} dias despues de encargarlo"
                       + ("<br>Configurador oficial de la marca" if oficial else ""))
            tarjetas.append(self._tarjeta(foto, modelo.nombre_completo, detalle, configurar))
        self._grilla(contenido, tarjetas)

    def _filtrar_marca(self, marca: str):
        self.marca = marca
        self._refrescar()

    def _on_portadas(self, portadas: dict):
        self._portadas = portadas
        if self.sitio is not None and self.sitio.tipo == "autos":
            self._refrescar()

    def _sin_portadas(self, _mensaje: str):
        pass  # sin internet quedan los dibujos

    def _usados(self, contenido, _sitio, perfil, e, moneda, hoy):
        ofertas = marketplace.ofertas(perfil.id, hoy) if perfil is not None and hoy is not None else []
        if not ofertas:
            contenido.addWidget(texto_suave("No hay autos publicados esta semana (sin el catalogo de autos de culto "
                                            "o sin partida)."))
            return
        contenido.addWidget(texto_suave("Las publicaciones cambian cada semana del juego. Se compran al instante y los "
                                        "de coleccion se valorizan con el tiempo."))
        tarjetas = []
        for oferta in ofertas:
            articulo = marketplace.articulo(oferta)
            comprar = self._boton_comprar(e, oferta["precio"], economia.tiene(e, articulo.id))
            comprar.setProperty("nicho", oferta["id"])
            comprar.clicked.connect(lambda _=False, o=oferta: self._accion(self.vida.comprar_nicho, o))
            nota = f" · {esc(oferta['nota'])}" if oferta.get("nota") else ""
            detalle = (f"<span style='color:{estilos.ACENTO}; font-size: 15px'><b>{dinero(oferta['precio'], moneda)}</b>"
                       f"</span><br>{esc(oferta['categoria'])} · rareza {esc(oferta['rareza'])}<br>{esc(articulo.detalle)}{nota}"
                       + (f"<br><span style='font-size: 10px'>Foto: {esc(oferta['credito'])}</span>" if oferta.get("credito") else ""))
            tarjetas.append(self._tarjeta(_foto(marketplace.ruta_imagen(oferta.get("imagen", ""))), articulo.nombre,
                                          detalle, comprar))
        self._grilla(contenido, tarjetas)

    def _banco(self, contenido, _sitio, _perfil, e, moneda, hoy):
        if not e:
            return
        cifras = QHBoxLayout()
        for titulo, monto in (("Saldo", e.get("saldo", 0)), ("Sueldo neto por semana", e.get("sueldo", 0) * economia.NETO),
                              ("Gastos fijos por semana", economia.mantenimiento_semanal(e)),
                              ("Patrimonio", economia.patrimonio(e))):
            caja = QLabel(f"<span style='color:{estilos.TEXTO_SUAVE}'>{titulo.upper()}</span><br>"
                          f"<span style='font-size: 22px'><b>{dinero(monto, moneda)}</b></span>")
            caja.setStyleSheet(f"background: {estilos.PANEL}; border: 1px solid {BORDE}; border-radius: 10px; padding: 12px;")
            cifras.addWidget(caja)
        contenido.addLayout(cifras)
        contenido.addWidget(self._titulo("Tus bienes"))
        for posesion in e.get("posesiones", []):
            articulo = economia.articulo_de_posesion(posesion)
            vender = boton(f"Vender por {dinero(economia.valor_de_venta(posesion, hoy), moneda)}")
            vender.setProperty("posesion", posesion["id"])
            vender.clicked.connect(lambda _=False, i=posesion["id"]: self._accion(self.vida._on_vender, i))
            nombre = articulo.nombre if articulo else posesion["articulo"]
            if posesion.get("config"):
                config = autos.Configuracion.desde_dict(posesion["config"])
                nombre = configurador.nombre_de_configuracion(autos.POR_ID[config.modelo].nombre_completo, config.oficial) \
                    if config.modelo in autos.POR_ID else nombre
            linea = QHBoxLayout()
            linea.addWidget(QLabel(f"<b>{esc(nombre)}</b> · <span style='color:{estilos.TEXTO_SUAVE}'>desde el "
                                   f"{posesion.get('desde', '')[8:10]}/{posesion.get('desde', '')[5:7]}</span>"), 1)
            linea.addWidget(vender)
            contenido.addLayout(linea)
        if not e.get("posesiones"):
            contenido.addWidget(texto_suave("Todavia no te compraste nada."))
        if e.get("pedidos"):
            contenido.addWidget(self._titulo("En camino"))
            for pedido in e["pedidos"]:
                entrega = pedido["entrega"]
                contenido.addWidget(QLabel(f"<b>{esc(autos.POR_ID[pedido['modelo']].nombre_completo)}</b> · llega el "
                                           f"{entrega[8:10]}/{entrega[5:7]}/{entrega[:4]}"))
        contenido.addWidget(self._titulo("Movimientos"))
        for movimiento in e.get("movimientos", [])[:15]:
            monto = movimiento["monto"]
            color = estilos.POSITIVO if monto > 0 else estilos.NEGATIVO if monto < 0 else estilos.TEXTO_SUAVE
            cifra = QLabel(("+" if monto > 0 else "") + dinero(monto, moneda) if monto else "")
            cifra.setStyleSheet(f"color: {color}; font-weight: 600;")
            dia = movimiento["fecha"]
            linea = QHBoxLayout()
            linea.addWidget(texto_suave(f"{dia[8:10]}/{dia[5:7]}", ajustar=False))
            linea.addWidget(QLabel(esc(movimiento["concepto"])), 1)
            linea.addWidget(cifra)
            contenido.addLayout(linea)

    def _titulo(self, texto: str) -> QLabel:
        etiqueta = QLabel(texto.upper())
        etiqueta.setFont(fuente_titulo(18, 1.5))
        return etiqueta
