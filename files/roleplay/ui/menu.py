"""
Menu principal: barra lateral + una pagina por modulo (Resumen,
Entrevistas, Instagram). Cada pagina va dentro de un scroll.
"""

from PySide6.QtWidgets import (
    QFrame,
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
from roleplay.ui.comun import con_scroll, esc, miles
from roleplay.ui.entrevista import InterviewWindow
from roleplay.ui.estilos import marcar_subtitulo, marcar_titulo
from roleplay.ui.instagram import InstagramWindow
from roleplay.ui.personaje import CharacterWizard


class PaginaResumen(QWidget):
    """Vistazo rapido del personaje actual: club, reputacion, seguidores,
    numeros de la carrera y ultimas noticias."""

    def __init__(self, on_crear_personaje):
        super().__init__()

        layout = QVBoxLayout()
        layout.setContentsMargins(28, 28, 28, 28)
        layout.setSpacing(10)

        self.titulo_label = QLabel()
        self.titulo_label.setWordWrap(True)
        marcar_titulo(self.titulo_label)
        layout.addWidget(self.titulo_label)

        self.stats_label = QLabel()
        self.stats_label.setWordWrap(True)
        layout.addWidget(self.stats_label)

        self.carrera_label = QLabel()
        self.carrera_label.setWordWrap(True)
        layout.addWidget(self.carrera_label)

        self.backstory_label = QLabel()
        self.backstory_label.setWordWrap(True)
        layout.addWidget(self.backstory_label)

        self.crear_btn = QPushButton("Crear nuevo personaje")
        self.crear_btn.clicked.connect(on_crear_personaje)
        layout.addWidget(self.crear_btn)

        noticias_titulo = QLabel("Ultimas noticias")
        marcar_subtitulo(noticias_titulo)
        layout.addSpacing(12)
        layout.addWidget(noticias_titulo)

        self.noticias_label = QLabel()
        self.noticias_label.setWordWrap(True)
        layout.addWidget(self.noticias_label)

        layout.addStretch()
        self.setLayout(layout)

    def actualizar(self):
        perfil = load_latest_profile()

        if perfil is None:
            self.titulo_label.setText("Todavia no creaste ningun personaje")
            for label in (self.stats_label, self.carrera_label, self.backstory_label, self.noticias_label):
                label.setText("")
            return

        self.titulo_label.setText(esc(perfil.nombre_jugador))

        club = perfil.club_actual or "sin club definido"
        self.stats_label.setText(
            f"<b>{esc(club)}</b> · Reputacion {get_reputacion_actual(perfil.id)}/100 · "
            f"{miles(get_seguidores(perfil.id))} seguidores en Instagram"
        )

        carrera = calcular_estadisticas_acumuladas(load_match_interviews(perfil.id))
        if carrera["partidos_jugados"]:
            self.carrera_label.setText(
                f"{carrera['partidos_jugados']} partidos · {carrera['goles_totales']} goles · "
                f"{carrera['asistencias_totales']} asistencias · "
                f"rating promedio {carrera['rating_promedio']:.1f}"
            )
        else:
            self.carrera_label.setText("Todavia no registraste ningun partido.")

        self.backstory_label.setText(
            esc(perfil.backstory_generado) if perfil.backstory_generado else "(sin backstory todavia)"
        )

        noticias = load_noticias_prensa(perfil.id, limite=3)
        if noticias:
            self.noticias_label.setText(
                "<br><br>".join(f"<b>{esc(n.titular)}</b><br>{esc(n.cuerpo)}" for n in noticias)
            )
        else:
            self.noticias_label.setText("Todavia no hay noticias.")


class MainMenuWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("EAFC 26 Roleplay")
        self.setMinimumSize(900, 680)

        # ---- barra lateral ----
        sidebar = QFrame()
        sidebar.setObjectName("sidebar")
        sidebar.setFixedWidth(210)
        sidebar_layout = QVBoxLayout()
        sidebar_layout.setContentsMargins(14, 24, 14, 24)
        sidebar_layout.setSpacing(6)

        titulo = QLabel("EAFC 26\nRoleplay")
        marcar_titulo(titulo)
        sidebar_layout.addWidget(titulo)
        sidebar_layout.addSpacing(20)

        # ---- paginas: (texto del boton, pagina) ----
        self.pagina_resumen = PaginaResumen(self._abrir_wizard_personaje)
        self.pagina_entrevistas = InterviewWindow()
        self.pagina_instagram = InstagramWindow()
        self._paginas = [
            ("🏠  Resumen", self.pagina_resumen),
            ("🎙️  Entrevistas", self.pagina_entrevistas),
            ("📸  Instagram", self.pagina_instagram),
        ]

        self.stack = QStackedWidget()
        self._botones_nav = []
        for indice, (texto, pagina) in enumerate(self._paginas):
            self.stack.addWidget(con_scroll(pagina))
            boton = QPushButton(texto)
            boton.setObjectName("navBtn")
            boton.setCheckable(True)
            boton.clicked.connect(lambda _=False, i=indice: self._ir_a(i))
            sidebar_layout.addWidget(boton)
            self._botones_nav.append(boton)

        sidebar_layout.addStretch()
        sidebar.setLayout(sidebar_layout)

        contenedor = QWidget()
        layout_principal = QHBoxLayout()
        layout_principal.setContentsMargins(0, 0, 0, 0)
        layout_principal.setSpacing(0)
        layout_principal.addWidget(sidebar)
        layout_principal.addWidget(self.stack, 1)
        contenedor.setLayout(layout_principal)
        self.setCentralWidget(contenedor)

        self._ir_a(0)

    def _ir_a(self, indice: int):
        self.stack.setCurrentIndex(indice)
        for i, boton in enumerate(self._botones_nav):
            boton.setChecked(i == indice)
        self._paginas[indice][1].actualizar()

    def _abrir_wizard_personaje(self):
        wizard = CharacterWizard(self)
        if wizard.exec():
            self._ir_a(0)
        wizard.deleteLater()
