"""
Menu principal: barra lateral + una pagina por modulo (Resumen,
Temporada, Entrevistas, Instagram), sobre el fondo de estadio. Cada pagina va dentro
de un scroll.
"""

from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QAction, QIcon
from PySide6.QtWidgets import (
    QApplication,
    QFrame,
    QMenu,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QPushButton,
    QStackedWidget,
    QSystemTrayIcon,
    QVBoxLayout,
    QWidget,
)

from roleplay.database import (
    actualizar_club,
    get_estado_prensa,
    get_reputacion_actual,
    get_seguidores,
    load_latest_profile,
    load_match_interviews,
    load_noticias_prensa,
)
from roleplay import config
from roleplay.servicios.partida_real import resumen_temporada
from roleplay.servicios.prensa import calcular_estadisticas_acumuladas
from roleplay.ui import estilos
from roleplay.ui.comun import con_scroll, ejecutar_en_hilo, esc, miles
from roleplay.ui.componentes import (
    CartaJugador,
    FondoEstadio,
    Mosaico,
    Tarjeta,
    agregar_noticia,
    boton,
    chip,
    compacto,
    etiqueta_campo,
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
from roleplay.ui.temporada import PaginaTemporada
from roleplay.ui.ajustes import DialogoAjustes, abrir_juego_o_preguntar
from roleplay.ui.personaje import CharacterWizard
from roleplay.ui.atajo import ATAJO_TEXTO, AtajoGlobal
from roleplay.ui.overlay import SalaFlotante
from roleplay.ui.vigilante import VigilantePartida, mostrar_flotante_sola, preparar_entrevista_sola

NOTICIAS_EN_RESUMEN = 5


class PaginaResumen(QWidget):
    """Vistazo del personaje: su carta, los numeros de la carrera, la
    historia, las tramas abiertas y las ultimas noticias."""

    def __init__(self, on_crear_personaje, on_club_cambiado=None):
        super().__init__()
        self._on_crear_personaje = on_crear_personaje
        self._on_club_cambiado = on_club_cambiado  # para que la barra lateral se entere
        self._perfil = None
        self._leyendo_temporada = False

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

        # ---- la temporada real (partida de FC 26) ----
        self.temporada = Tarjeta("Tu temporada en FC 26", destacada=True)
        self.temporada_label = texto_suave()
        self.temporada.cuerpo.addWidget(self.temporada_label)
        self.temporada_competiciones = QVBoxLayout()
        self.temporada_competiciones.setSpacing(4)
        self.temporada.cuerpo.addLayout(self.temporada_competiciones)
        self.temporada_ultimos = QHBoxLayout()
        self.temporada_ultimos.setSpacing(6)
        self.temporada.cuerpo.addLayout(self.temporada_ultimos)
        self.temporada_proximo = texto_suave()
        self.temporada.cuerpo.addWidget(self.temporada_proximo)
        self.temporada.hide()
        contenido.addWidget(self.temporada)

        # ---- premios de verdad (jugador del mes, campeon...) ----
        self.vitrina = Tarjeta("Vitrina")
        self.vitrina_layout = QVBoxLayout()
        self.vitrina_layout.setSpacing(6)
        self.vitrina.cuerpo.addLayout(self.vitrina_layout)
        self.vitrina.hide()
        contenido.addWidget(self.vitrina)

        # ---- las temporadas que ya terminaron ----
        self.trayectoria = Tarjeta("Trayectoria")
        self.trayectoria_grilla = QGridLayout()
        self.trayectoria_grilla.setHorizontalSpacing(18)
        self.trayectoria_grilla.setVerticalSpacing(6)
        self.trayectoria.cuerpo.addLayout(self.trayectoria_grilla)
        self.trayectoria.hide()
        contenido.addWidget(self.trayectoria)

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

        self._perfil = perfil
        reputacion = get_reputacion_actual(perfil.id)
        seguidores = get_seguidores(perfil.id)
        club = perfil.club_actual or "sin club definido"
        carrera = calcular_estadisticas_acumuladas(load_match_interviews(perfil.id))

        self.titulo_label.setText(esc(perfil.nombre_jugador.upper()))
        self.stats_label.setText(
            f"<b>{esc(club)}</b> · Reputacion {reputacion}/100 · {miles(seguidores)} seguidores en Instagram"
        )

        # Mientras no se lea la partida (o si no hay), los numeros son los de
        # los partidos registrados en la app.
        self._mostrar_numeros(
            perfil, reputacion, seguidores,
            partidos=carrera["partidos_jugados"], goles=carrera["goles_totales"],
            asistencias=carrera["asistencias_totales"], figura=carrera["figuras"],
            nota=carrera["rating_promedio"] if carrera["partidos_jugados"] else None,
        )
        self.carta.setToolTip(
            f"Carta {nivel_carta(reputacion).nombre.lower()}: el color sube con la reputacion "
            "(bronce, plata desde 45, oro desde 70, elite desde 85)."
        )
        if not self._leyendo_temporada:
            self._leyendo_temporada = True
            ejecutar_en_hilo(resumen_temporada, al_completar=self._on_temporada, al_fallar=self._on_temporada_error)

        self.backstory_label.setText(esc(perfil.backstory_generado) or "(sin historia todavia)")

        limpiar_layout(self.tramas_layout)
        for gancho in perfil.ganchos_narrativos:
            trama = QLabel(f"<span style='color:{estilos.ACENTO}'>▸</span>&nbsp; {esc(gancho)}")
            trama.setWordWrap(True)
            self.tramas_layout.addWidget(trama)
        self.tramas.setVisible(bool(perfil.ganchos_narrativos))

        estado_prensa = get_estado_prensa(perfil.id)
        self._cargar_vitrina(estado_prensa)
        self._cargar_trayectoria(estado_prensa)
        self._cargar_noticias(perfil)

    def _cargar_trayectoria(self, estado_prensa: dict):
        limpiar_layout(self.trayectoria_grilla)
        temporadas = estado_prensa.get("trayectoria", [])
        if temporadas:
            for columna, rotulo in enumerate(("Temporada", "Club", "PJ", "Goles", "Asist.", "Nota", "Liga", "Titulos")):
                self.trayectoria_grilla.addWidget(etiqueta_campo(rotulo), 0, columna)
        for fila_n, t in enumerate(reversed(temporadas), start=1):  # la ultima arriba
            liga = f"{t['posicion']}° {t['liga']}" if t.get("posicion") else "-"
            valores = (
                t["temporada"], t["club"], t["partidos"], t["goles"], t["asistencias"],
                t["nota"] if t.get("nota") is not None else "-", liga, ", ".join(t.get("titulos", [])) or "-",
            )
            for columna, valor in enumerate(valores):
                celda = QLabel(esc(valor))
                if columna == 0:
                    celda.setStyleSheet(f"color: {estilos.ACENTO}; font-weight: 700;")
                self.trayectoria_grilla.addWidget(celda, fila_n, columna)
        self.trayectoria_grilla.setColumnStretch(7, 1)
        self.trayectoria.setVisible(bool(temporadas))

    def _cargar_vitrina(self, estado_prensa: dict):
        limpiar_layout(self.vitrina_layout)
        premios = estado_prensa.get("vitrina", [])
        for premio in reversed(premios):  # el mas nuevo arriba
            linea = QLabel(
                f"<span style='color:{estilos.MIXTO}'>★</span>&nbsp; <b>{esc(premio['premio'])}</b> · "
                f"<span style='color:{estilos.TEXTO_SUAVE}'>{esc(premio['detalle'])} ({esc(premio.get('temporada', ''))})</span>"
            )
            linea.setWordWrap(True)
            self.vitrina_layout.addWidget(linea)
        self.vitrina.setVisible(bool(premios))

    def _mostrar_numeros(self, perfil, reputacion, seguidores, partidos, goles, asistencias, figura, nota):
        rating = f"{nota:.1f}" if nota is not None else "-"
        self.carta.mostrar(
            perfil.nombre_jugador,
            perfil.club_actual,
            reputacion,
            [
                ("PJ", str(partidos)),
                ("GOL", str(goles)),
                ("AST", str(asistencias)),
                ("RAT", rating),
                ("FIG", str(figura)),
                ("SEG", compacto(seguidores)),
            ],
        )
        self.mosaicos["partidos"].poner(partidos)
        self.mosaicos["goles"].poner(goles)
        self.mosaicos["asistencias"].poner(asistencias)
        self.mosaicos["rating"].poner(rating)
        self.mosaicos["figuras"].poner(figura)
        self.mosaicos["seguidores"].poner(miles(seguidores))

    def _on_temporada(self, resumen):
        self._leyendo_temporada = False
        if resumen is None or self._perfil is None:
            self.temporada.hide()
            return
        perfil = self._perfil
        if resumen.club != perfil.club_actual:
            # el club de la partida es el de verdad (cambia con los traspasos)
            actualizar_club(perfil.id, resumen.club)
            perfil.club_actual = resumen.club
            if self._on_club_cambiado:
                self._on_club_cambiado()
            self.stats_label.setText(
                f"<b>{esc(resumen.club)}</b> · Reputacion {get_reputacion_actual(perfil.id)}/100 · "
                f"{miles(get_seguidores(perfil.id))} seguidores en Instagram"
            )
        totales = resumen.totales
        self._mostrar_numeros(
            perfil, get_reputacion_actual(perfil.id), get_seguidores(perfil.id),
            partidos=totales["partidos"], goles=totales["goles"], asistencias=totales["asistencias"],
            figura=totales["figura"], nota=totales["nota"],
        )
        self.carta.setToolTip(self.carta.toolTip() + "\nNumeros de tu partida de FC 26.")
        self.temporada_label.setText(
            f"<b>{esc(resumen.club)}</b> · {esc(resumen.posicion) or 'sin liga'} · "
            f"partida \"{esc(resumen.partida)}\" al {resumen.fecha}"
        )
        limpiar_layout(self.temporada_competiciones)
        for nombre, partidos, goles, asistencias, nota in resumen.por_competicion:
            linea = QLabel(
                f"<span style='color:{estilos.ACENTO}'>▸</span>&nbsp; <b>{esc(nombre)}</b> · {partidos} PJ · "
                f"{goles} goles · {asistencias} asist." + (f" · nota {nota}" if nota is not None else "")
            )
            self.temporada_competiciones.addWidget(linea)
        limpiar_layout(self.temporada_ultimos)
        colores = {"G": estilos.POSITIVO, "E": estilos.MIXTO, "P": estilos.NEGATIVO}
        for letra, marcador_texto, competicion in resumen.ultimos:
            ficha = chip(letra, colores[letra])
            ficha.setToolTip(f"{marcador_texto} ({competicion})")
            self.temporada_ultimos.addWidget(ficha)
        if resumen.ultimos:
            ultimo = texto_suave(f"Ultimo: {esc(resumen.ultimos[-1][1])}", ajustar=False)
            self.temporada_ultimos.addWidget(ultimo)
        self.temporada_ultimos.addStretch()
        self.temporada_proximo.setText(f"Proximo partido: {esc(resumen.proximo)}" if resumen.proximo else "")
        self.temporada.show()

    def _on_temporada_error(self, _mensaje: str):
        # sin la partida el Resumen funciona igual, con los numeros de la app
        self._leyendo_temporada = False
        self.temporada.hide()

    def _cargar_noticias(self, perfil):
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
    PAGINA_RESUMEN, PAGINA_TEMPORADA, PAGINA_ENTREVISTAS, PAGINA_INSTAGRAM = range(4)

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
        self.pagina_resumen = PaginaResumen(self._abrir_wizard_personaje, self._refrescar_jugador)
        self.pagina_temporada = PaginaTemporada()
        self.pagina_entrevistas = InterviewWindow()
        self.pagina_instagram = InstagramWindow()
        self._paginas = [
            ("Resumen", "inicio", self.pagina_resumen),
            ("Temporada", "trofeo", self.pagina_temporada),
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

        # ---- sala flotante (encima del juego) y su atajo global ----
        self.sala_flotante = SalaFlotante(self.pagina_entrevistas)
        self.atajo = AtajoGlobal(self)
        if self.atajo.registrar():
            self.atajo.presionado.connect(self.sala_flotante.alternar)

        # ---- modo en vivo: avisos de partidos nuevos ----
        self.bandeja = None
        if QSystemTrayIcon.isSystemTrayAvailable():
            self.bandeja = QSystemTrayIcon(QIcon(str(config.ICONO_APP)), self)
            self.bandeja.setToolTip("EAFC 26 Roleplay")
            self.bandeja.messageClicked.connect(self._abrir_sala_de_prensa)
            self.bandeja.activated.connect(self._on_bandeja_activada)
            menu = QMenu(self)
            for texto, accion in (
                (f"Sala flotante ({ATAJO_TEXTO})", self.sala_flotante.alternar),
                ("Abrir la app", self._traer_al_frente),
                ("Salir", QApplication.quit),
            ):
                item = QAction(texto, menu)
                item.triggered.connect(accion)
                menu.addAction(item)
            self.bandeja.setContextMenu(menu)
            self.bandeja.show()
        self.vigilante = VigilantePartida(self)
        self.vigilante.partido_nuevo.connect(self._on_partido_nuevo)
        self.vigilante.partida_actualizada.connect(self._on_partida_actualizada)
        self.vigilante.iniciar()

        self._ir_a(pagina_inicial)

    def _ir_a(self, indice: int):
        if indice == self.PAGINA_ENTREVISTAS:
            self._marcar_entrevistas(False)
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

    # ---- modo en vivo ----

    def _marcar_entrevistas(self, pendiente: bool):
        texto = self._paginas[self.PAGINA_ENTREVISTAS][0].upper()
        self._botones_nav[self.PAGINA_ENTREVISTAS].setText(f"  {texto}" + ("   ●" if pendiente else ""))

    def _on_bandeja_activada(self, motivo):
        if motivo == QSystemTrayIcon.ActivationReason.Trigger:  # click izquierdo
            self._traer_al_frente()

    def closeEvent(self, evento):
        self.atajo.liberar()
        self.sala_flotante.close()
        if self.bandeja is not None:
            self.bandeja.hide()
        super().closeEvent(evento)

    def _traer_al_frente(self):
        self.showNormal()
        self.raise_()
        self.activateWindow()

    def _abrir_sala_de_prensa(self):
        self._traer_al_frente()
        self._ir_a(self.PAGINA_ENTREVISTAS)

    def _on_partido_nuevo(self, lectura):
        sala = self.pagina_entrevistas
        cargado = sala.recibir_partido_nuevo(lectura, preparar_entrevista_sola())
        if sala.perfil is not None:
            sala._iniciar_revision_prensa(manual=False)  # la prensa reacciona al partido
        if self.stack.currentIndex() != self.PAGINA_ENTREVISTAS:
            self._marcar_entrevistas(True)
        if mostrar_flotante_sola():
            self.sala_flotante.mostrar()  # encima del juego, sin quitarle el foco
        mensaje = lectura.ultimo.resumen + (". Tu entrevista te espera." if cargado else ".")
        if self.bandeja is not None:
            self.bandeja.showMessage("Partido nuevo", mensaje, QSystemTrayIcon.MessageIcon.Information, 10000)
        QApplication.alert(self)

    def _on_partida_actualizada(self, _lectura):
        if self.stack.currentIndex() == self.PAGINA_RESUMEN:
            self.pagina_resumen.actualizar()
        elif self.stack.currentIndex() == self.PAGINA_TEMPORADA:
            self.pagina_temporada.actualizar()
        self._refrescar_jugador()

    def _abrir_ajustes(self):
        dialogo = DialogoAjustes(self)
        dialogo.exec()
        dialogo.deleteLater()

    def _abrir_wizard_personaje(self):
        wizard = CharacterWizard(self)
        if wizard.exec():
            self._ir_a(0)
        wizard.deleteLater()
