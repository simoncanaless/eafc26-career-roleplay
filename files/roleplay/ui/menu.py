"""
Menu principal: barra lateral + una pagina por modulo (Resumen,
Entrevistas, Instagram), sobre el fondo de estadio. Cada pagina va dentro
de un scroll.
"""

from PySide6.QtCore import QSize, Qt
from PySide6.QtWidgets import (
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QPushButton,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from roleplay.database import (
    get_reputacion_actual,
    get_seguidores,
    load_latest_profile,
    load_match_interviews,
    load_noticias_prensa,
)
from roleplay.servicios.prensa import calcular_estadisticas_acumuladas
from roleplay.ui import estilos
from roleplay.ui.comun import con_scroll, esc, miles
from roleplay.ui.componentes import (
    CartaJugador,
    FondoEstadio,
    Mosaico,
    Tarjeta,
    agregar_noticia,
    boton,
    compacto,
    icono,
    limpiar_layout,
    nivel_carta,
    separador,
    subtitulo,
    texto_suave,
    titulo_pagina,
)
from roleplay.ui.entrevista import InterviewWindow
from roleplay.ui.estilos import fuente_titulo
from roleplay.ui.instagram import InstagramWindow
from roleplay.ui.ajustes import DialogoAjustes, abrir_juego_o_preguntar
from roleplay.ui.personaje import CharacterWizard

NOTICIAS_EN_RESUMEN = 5


class PaginaResumen(QWidget):
    """Vistazo del personaje: su carta, los numeros de la carrera, la
    historia, las tramas abiertas y las ultimas noticias."""

    def __init__(self, on_crear_personaje):
        super().__init__()
        self._on_crear_personaje = on_crear_personaje

        layout = QVBoxLayout(self)
        layout.setContentsMargins(40, 34, 40, 34)
        layout.setSpacing(18)

        # ---- cabecera ----
        cabecera = QHBoxLayout()
        textos = QVBoxLayout()
        textos.setSpacing(2)
        self.titulo_label = titulo_pagina()
        self.stats_label = subtitulo()
        textos.addWidget(self.titulo_label)
        textos.addWidget(self.stats_label)
        cabecera.addLayout(textos, 1)
        self.crear_btn = boton("Nuevo personaje", icono_nombre="nuevo")
        self.crear_btn.clicked.connect(self._on_crear_personaje)
        cabecera.addWidget(self.crear_btn, 0, Qt.AlignmentFlag.AlignTop)
        layout.addLayout(cabecera)

        # ---- sin personaje ----
        self.vacio = Tarjeta("Arranca tu carrera", destacada=True)
        self.vacio.cuerpo.addWidget(
            texto_suave(
                "Crea tu jugador: de donde viene, como es frente a la prensa y que lo mueve. "
                "Con eso se escribe su historia y empiezan las entrevistas, la prensa y su Instagram."
            )
        )
        crear_grande = boton("Crear personaje", primario=True, icono_nombre="nuevo")
        crear_grande.clicked.connect(self._on_crear_personaje)
        self.vacio.cuerpo.addWidget(crear_grande, 0, Qt.AlignmentFlag.AlignLeft)
        layout.addWidget(self.vacio)

        # ---- carta + numeros ----
        self.contenido = QWidget()
        contenido = QVBoxLayout(self.contenido)
        contenido.setContentsMargins(0, 0, 0, 0)
        contenido.setSpacing(18)

        arriba = QHBoxLayout()
        arriba.setSpacing(22)
        self.carta = CartaJugador()
        arriba.addWidget(self.carta, 0, Qt.AlignmentFlag.AlignTop)

        derecha = QVBoxLayout()
        derecha.setSpacing(14)
        grilla = QGridLayout()
        grilla.setSpacing(10)
        self.mosaicos = {}
        for i, (clave, rotulo) in enumerate(
            (
                ("partidos", "Partidos"),
                ("goles", "Goles"),
                ("asistencias", "Asistencias"),
                ("rating", "Rating prom."),
                ("figuras", "Figura del partido"),
                ("seguidores", "Seguidores"),
            )
        ):
            self.mosaicos[clave] = Mosaico(rotulo)
            grilla.addWidget(self.mosaicos[clave], i // 3, i % 3)
        derecha.addLayout(grilla)

        historia = Tarjeta("Su historia")
        self.backstory_label = texto_suave()
        historia.cuerpo.addWidget(self.backstory_label)
        derecha.addWidget(historia)
        derecha.addStretch()
        arriba.addLayout(derecha, 1)
        contenido.addLayout(arriba)

        self.tramas = Tarjeta("Tramas abiertas")
        self.tramas_layout = QVBoxLayout()
        self.tramas_layout.setSpacing(6)
        self.tramas.cuerpo.addLayout(self.tramas_layout)
        contenido.addWidget(self.tramas)

        noticias = Tarjeta("Central de noticias", espaciado=8)
        self.noticias_layout = QVBoxLayout()
        self.noticias_layout.setSpacing(8)
        noticias.cuerpo.addLayout(self.noticias_layout)
        contenido.addWidget(noticias)

        layout.addWidget(self.contenido)
        layout.addStretch()

    def actualizar(self):
        perfil = load_latest_profile()
        self.vacio.setVisible(perfil is None)
        self.contenido.setVisible(perfil is not None)
        self.crear_btn.setVisible(perfil is not None)

        if perfil is None:
            self.titulo_label.setText("BIENVENIDO")
            self.stats_label.setText("Todavia no creaste ningun personaje.")
            return

        reputacion = get_reputacion_actual(perfil.id)
        seguidores = get_seguidores(perfil.id)
        club = perfil.club_actual or "sin club definido"
        carrera = calcular_estadisticas_acumuladas(load_match_interviews(perfil.id))

        self.titulo_label.setText(esc(perfil.nombre_jugador.upper()))
        self.stats_label.setText(
            f"<b>{esc(club)}</b> · Reputacion {reputacion}/100 · {miles(seguidores)} seguidores en Instagram"
        )

        rating = f"{carrera['rating_promedio']:.1f}" if carrera["partidos_jugados"] else "-"
        self.carta.mostrar(
            perfil.nombre_jugador,
            perfil.club_actual,
            reputacion,
            [
                ("PJ", str(carrera["partidos_jugados"])),
                ("GOL", str(carrera["goles_totales"])),
                ("AST", str(carrera["asistencias_totales"])),
                ("RAT", rating),
                ("FIG", str(carrera["figuras"])),
                ("SEG", compacto(seguidores)),
            ],
        )
        self.carta.setToolTip(
            f"Carta {nivel_carta(reputacion).nombre.lower()}: el color sube con la reputacion "
            "(bronce, plata desde 45, oro desde 70, elite desde 85)."
        )
        self.mosaicos["partidos"].poner(carrera["partidos_jugados"])
        self.mosaicos["goles"].poner(carrera["goles_totales"])
        self.mosaicos["asistencias"].poner(carrera["asistencias_totales"])
        self.mosaicos["rating"].poner(rating)
        self.mosaicos["figuras"].poner(carrera["figuras"])
        self.mosaicos["seguidores"].poner(miles(seguidores))

        self.backstory_label.setText(esc(perfil.backstory_generado) or "(sin historia todavia)")

        limpiar_layout(self.tramas_layout)
        for gancho in perfil.ganchos_narrativos:
            trama = QLabel(f"<span style='color:{estilos.ACENTO}'>▸</span>&nbsp; {esc(gancho)}")
            trama.setWordWrap(True)
            self.tramas_layout.addWidget(trama)
        self.tramas.setVisible(bool(perfil.ganchos_narrativos))

        limpiar_layout(self.noticias_layout)
        noticias = load_noticias_prensa(perfil.id, limite=NOTICIAS_EN_RESUMEN)
        if not noticias:
            self.noticias_layout.addWidget(
                texto_suave("Todavia no hay noticias. Salen solas despues de las entrevistas.")
            )
        for i, noticia in enumerate(noticias):
            if i:
                self.noticias_layout.addSpacing(6)
                self.noticias_layout.addWidget(separador())
                self.noticias_layout.addSpacing(6)
            agregar_noticia(self.noticias_layout, noticia)


class MainMenuWindow(QMainWindow):
    PAGINA_RESUMEN, PAGINA_ENTREVISTAS, PAGINA_INSTAGRAM = range(3)

    def __init__(self, pagina_inicial: int = 0):
        super().__init__()
        self.setWindowTitle("EAFC 26 Roleplay")
        self.setMinimumSize(1100, 720)

        # ---- barra lateral ----
        lateral = QFrame()
        lateral.setObjectName("lateral")
        lateral.setFixedWidth(230)
        lateral_layout = QVBoxLayout(lateral)
        lateral_layout.setContentsMargins(0, 30, 0, 24)
        lateral_layout.setSpacing(4)

        marca = QLabel("EAFC 26")
        marca.setFont(fuente_titulo(15, 4))
        marca.setStyleSheet(f"color: {estilos.ACENTO}; padding-left: 24px;")
        lateral_layout.addWidget(marca)
        nombre_app = QLabel("ROLEPLAY")
        nombre_app.setFont(fuente_titulo(36, 1.5))
        nombre_app.setStyleSheet("padding-left: 22px;")
        lateral_layout.addWidget(nombre_app)
        lateral_layout.addSpacing(28)

        # ---- paginas: (texto, icono, pagina) ----
        self.pagina_resumen = PaginaResumen(self._abrir_wizard_personaje)
        self.pagina_entrevistas = InterviewWindow()
        self.pagina_instagram = InstagramWindow()
        self._paginas = [
            ("Resumen", "inicio", self.pagina_resumen),
            ("Entrevistas", "microfono", self.pagina_entrevistas),
            ("Instagram", "camara", self.pagina_instagram),
        ]

        self.stack = QStackedWidget()
        self._botones_nav: list[QPushButton] = []
        for indice, (texto, nombre_icono, pagina) in enumerate(self._paginas):
            self.stack.addWidget(con_scroll(pagina))
            boton_nav = QPushButton(f"  {texto.upper()}")
            boton_nav.setObjectName("navBtn")
            boton_nav.setCheckable(True)
            boton_nav.setIcon(icono(nombre_icono, estilos.TEXTO_SUAVE, estilos.TEXTO))
            boton_nav.setIconSize(QSize(20, 20))
            boton_nav.setCursor(Qt.CursorShape.PointingHandCursor)
            boton_nav.clicked.connect(lambda _=False, i=indice: self._ir_a(i))
            lateral_layout.addWidget(boton_nav)
            self._botones_nav.append(boton_nav)

        lateral_layout.addStretch()

        self.jugar_btn = boton("Jugar FC 26", primario=True, icono_nombre="jugar")
        self.jugar_btn.setToolTip("Abre EA FC 26 por su plataforma (Steam, EA app o Epic), sin modificarlo")
        self.jugar_btn.clicked.connect(lambda: abrir_juego_o_preguntar(self))
        self.ajustes_btn = QPushButton("  AJUSTES")
        self.ajustes_btn.setObjectName("navBtn")
        self.ajustes_btn.setIcon(icono("engranaje", estilos.TEXTO_SUAVE))
        self.ajustes_btn.setIconSize(QSize(20, 20))
        self.ajustes_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.ajustes_btn.clicked.connect(self._abrir_ajustes)
        envoltura_jugar = QHBoxLayout()
        envoltura_jugar.setContentsMargins(18, 0, 18, 6)
        envoltura_jugar.addWidget(self.jugar_btn)
        lateral_layout.addLayout(envoltura_jugar)
        lateral_layout.addWidget(self.ajustes_btn)
        lateral_layout.addSpacing(14)

        self.jugador_label = QLabel()
        self.jugador_label.setWordWrap(True)
        self.jugador_label.setStyleSheet(f"color: {estilos.TEXTO_SUAVE}; padding: 0px 24px;")
        lateral_layout.addWidget(self.jugador_label)

        fondo = FondoEstadio()
        fondo_layout = QVBoxLayout(fondo)
        fondo_layout.setContentsMargins(0, 0, 0, 0)
        fondo_layout.addWidget(self.stack)

        contenedor = QWidget()
        layout_principal = QHBoxLayout(contenedor)
        layout_principal.setContentsMargins(0, 0, 0, 0)
        layout_principal.setSpacing(0)
        layout_principal.addWidget(lateral)
        layout_principal.addWidget(fondo, 1)
        self.setCentralWidget(contenedor)

        self._ir_a(pagina_inicial)

    def _ir_a(self, indice: int):
        self.stack.setCurrentIndex(indice)
        for i, boton_nav in enumerate(self._botones_nav):
            boton_nav.setChecked(i == indice)
        self._paginas[indice][2].actualizar()
        self._refrescar_jugador()

    def _refrescar_jugador(self):
        perfil = load_latest_profile()
        if perfil is None:
            self.jugador_label.setText("Sin personaje")
            return
        reputacion = get_reputacion_actual(perfil.id)
        self.jugador_label.setText(
            f"<span style='color:{estilos.TEXTO}'><b>{esc(perfil.nombre_jugador)}</b></span><br>"
            f"{esc(perfil.club_actual or 'Sin club')} · REP {reputacion} · {nivel_carta(reputacion).nombre}"
        )

    def _abrir_ajustes(self):
        dialogo = DialogoAjustes(self)
        dialogo.exec()
        dialogo.deleteLater()

    def _abrir_wizard_personaje(self):
        wizard = CharacterWizard(self)
        if wizard.exec():
            self._ir_a(0)
        wizard.deleteLater()
