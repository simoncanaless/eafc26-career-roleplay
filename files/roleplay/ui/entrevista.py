"""
Sala de prensa (entrevista post-partido). Flujo:

1. Capturar la pantalla de fin de partido y leer las stats con Gemini
   Vision, o escribirlas a mano. Quedan editables en los dos casos.
2. Generar las preguntas con Gemini (perfil + partido).
3. El usuario responde escribiendo o por voz (se graba y Gemini lo
   transcribe; el texto queda editable).
4. Gemini evalua las respuestas: reaccion de prensa, cambio de
   reputacion y, a veces, un gancho narrativo nuevo. Se guarda todo y se
   revisa si el partido disparo algun hito de prensa.

Con la partida de FC 26 hay ademas un segundo modo: la conferencia PREVIA
al proximo partido (servicios/previa.py). Mismas preguntas, voz y envio;
no se guarda como partido: deja una noticia y mueve la reputacion.
"""

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtWidgets import (
    QButtonGroup,
    QComboBox,
    QDoubleSpinBox,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from roleplay.database import (
    actualizar_club,
    actualizar_metas,
    agregar_gancho_narrativo,
    aplicar_delta_reputacion,
    get_estado_prensa,
    get_reputacion_actual,
    load_latest_profile,
    load_match_interviews,
    save_match_interview,
    save_noticia_prensa,
    set_estado_partida,
    set_estado_prensa,
)
from roleplay.models import MatchInterviewRecord, PlayerProfile
from roleplay.servicios.audio import MINIMO_SEGUNDOS, GrabadorMicrofono, listar_microfonos, transcribir
from roleplay.servicios.captura import capturar_pantalla
from roleplay.servicios.entrevista import evaluar_respuestas, generar_entrevista
from roleplay.servicios.partida_real import leer_para_entrevista, revisar_prensa_con_partida
from roleplay.servicios.previa import evaluar_previa, generar_previa, noticia_de_previa
from roleplay.servicios.prensa import BONOS_REPUTACION, revisar_prensa
from roleplay.servicios.vision import MatchStats, extraer_stats_partido
from roleplay.ui import estilos
from roleplay.ui.comun import ejecutar_en_hilo, esc
from roleplay.ui.componentes import (
    Mosaico,
    Tarjeta,
    agregar_noticia,
    boton,
    chip,
    chip_alternable,
    etiqueta_campo,
    fila,
    icono,
    limpiar_layout,
    separador,
    subtitulo,
    texto_suave,
    titulo_pagina,
)
from roleplay.ui.estilos import fuente_titulo

TEXTO_CAPTURAR = "Capturar pantalla"
TEXTO_GENERAR = "Generar entrevista con IA"
TEXTO_REGENERAR = "Regenerar entrevista"
TEXTO_GENERAR_PREVIA = "Generar conferencia previa"
TEXTO_REGENERAR_PREVIA = "Regenerar conferencia"
TEXTO_ENVIAR = "Enviar respuestas"
TEXTO_PRENSA = "Revisar prensa ahora"
TEXTO_VOZ = "Responder por voz"


def _capturar_y_leer() -> MatchStats:
    return extraer_stats_partido(capturar_pantalla())


def _repintar(widget: QWidget) -> None:
    """Vuelve a aplicar la hoja de estilos tras cambiar una propiedad."""
    widget.style().unpolish(widget)
    widget.style().polish(widget)


class InterviewWindow(QWidget):
    # algo cambio (preguntas, respuestas, botones, reaccion): la sala
    # flotante (ui/overlay.py) se redibuja con esto
    cambio = Signal()

    def __init__(self):
        super().__init__()
        self.setWindowTitle("EAFC 26 Roleplay - Sala de prensa")

        self.perfil = None
        self._preguntas: list[str] = []
        self._respuesta_edits: list[QTextEdit] = []
        self._botones_voz: list[QPushButton] = []
        # Lo que hay en curso. _evaluando guarda lo que se mando a evaluar
        # (jugador, stats, preguntas y respuestas), para guardar exactamente
        # eso aunque se toque el formulario, o se cree otro personaje,
        # mientras Gemini responde.
        self._capturando = False
        self._generando = False
        self._evaluando: tuple[PlayerProfile, MatchStats, list[tuple[str, str]], str, str] | None = None
        self._prensa_en_curso = False
        self._prensa_manual = False
        self._prensa_player_id: int | None = None
        self.ultimas_noticias: list = []  # las de la ultima revision (la sala flotante las muestra)
        # voz: (grabador, numero de pregunta) y la pregunta que se transcribe
        self._grabacion: tuple[GrabadorMicrofono, int] | None = None
        self._transcribiendo: int | None = None
        self._microfonos_cargados = False
        self._sin_microfono: str | None = None  # el motivo, si no se puede grabar
        # partida de FC 26: lo leido (LecturaPartida) y de donde salieron las
        # stats del formulario ("partida", "captura" o "manual")
        self._lectura = None
        self._leyendo_partida = False
        self._origen = "manual"
        self._fecha_juego = ""
        # "post": entrevista despues del partido; "previa": conferencia antes
        # del proximo (solo con la partida de FC 26)
        self._modo = "post"
        self._reloj = QTimer(self)
        self._reloj.setInterval(200)
        self._reloj.timeout.connect(self._tic_grabacion)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(40, 34, 40, 34)
        layout.setSpacing(18)

        # ---- cabecera ----
        cabecera = QHBoxLayout()
        textos = QVBoxLayout()
        textos.setSpacing(2)
        textos.addWidget(titulo_pagina("Sala de prensa"))
        self.header_label = subtitulo()
        textos.addWidget(self.header_label)
        cabecera.addLayout(textos, 1)
        self.reputacion_mosaico = Mosaico("Reputacion")
        self.reputacion_mosaico.setFixedWidth(130)
        cabecera.addWidget(self.reputacion_mosaico)
        layout.addLayout(cabecera)

        club = Tarjeta()
        self.club_edit = QLineEdit()
        self.club_edit.setPlaceholderText("Ej: Luton Town")
        self.guardar_club_btn = boton("Guardar club", icono_nombre="escudo")
        self.guardar_club_btn.clicked.connect(self._on_guardar_club_clicked)
        club.cuerpo.addLayout(fila(etiqueta_campo("Club actual"), self.club_edit, self.guardar_club_btn, espaciado=14))
        layout.addWidget(club)

        self.tarjeta_partido = self._tarjeta_partido()
        layout.addWidget(self.tarjeta_partido)
        layout.addWidget(self._tarjeta_entrevista())
        layout.addWidget(self._tarjeta_prensa())
        layout.addStretch()

        self.actualizar()

    # ---- armado de la pagina ----

    def _tarjeta_partido(self) -> Tarjeta:
        tarjeta = Tarjeta("1 · El partido", espaciado=14)

        self.partida_label = texto_suave("Buscando tu partida de FC 26...")
        self.cargar_partida_btn = boton("Cargar de mi partida", primario=True, icono_nombre="jugar")
        self.cargar_partida_btn.setToolTip(
            "Lee tu ultimo partido del guardado de la carrera (sin tocar el juego)"
        )
        self.cargar_partida_btn.clicked.connect(self._on_cargar_partida_clicked)
        self.capturar_btn = boton(TEXTO_CAPTURAR, icono_nombre="captura")
        self.capturar_btn.setToolTip("O captura la pantalla de estadisticas al terminar el partido")
        self.capturar_btn.clicked.connect(self._on_capturar_clicked)
        fila_partida = QHBoxLayout()
        fila_partida.setSpacing(10)
        fila_partida.addWidget(self.partida_label, 1)
        fila_partida.addWidget(self.cargar_partida_btn)
        fila_partida.addWidget(self.capturar_btn)
        tarjeta.cuerpo.addLayout(fila_partida)
        self.partida_nota = texto_suave()
        self.partida_nota.hide()
        tarjeta.cuerpo.addWidget(self.partida_nota)

        # marcador
        self.goles_equipo_spin = self._spin_marcador()
        self.goles_rival_spin = self._spin_marcador()
        self.equipo_propio_label = QLabel()
        self.equipo_propio_label.setFont(fuente_titulo(17, 1))
        self.equipo_propio_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.equipo_rival_edit = QLineEdit()
        self.equipo_rival_edit.setPlaceholderText("Equipo rival")
        self.equipo_rival_edit.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.equipo_rival_edit.setFixedWidth(200)
        guion = QLabel("-")
        guion.setFont(fuente_titulo(40))
        guion.setAlignment(Qt.AlignmentFlag.AlignCenter)

        marcador = QGridLayout()
        marcador.setHorizontalSpacing(18)
        marcador.setVerticalSpacing(6)
        marcador.addWidget(self.equipo_propio_label, 0, 0)
        marcador.addWidget(self.equipo_rival_edit, 0, 2)
        marcador.addWidget(self.goles_equipo_spin, 1, 0, Qt.AlignmentFlag.AlignHCenter)
        marcador.addWidget(guion, 1, 1)
        marcador.addWidget(self.goles_rival_spin, 1, 2, Qt.AlignmentFlag.AlignHCenter)
        marcador.setColumnMinimumWidth(0, 200)
        marcador.setColumnMinimumWidth(2, 200)
        contenedor_marcador = QFrame()
        contenedor_marcador.setObjectName("mosaico")
        envoltura = QHBoxLayout(contenedor_marcador)
        envoltura.setContentsMargins(16, 14, 16, 14)
        envoltura.addStretch()
        envoltura.addLayout(marcador)
        envoltura.addStretch()
        tarjeta.cuerpo.addWidget(contenedor_marcador)

        # tus numeros
        self.goles_jugador_spin = self._spin(10)
        self.asistencias_spin = self._spin(10)
        self.rating_spin = QDoubleSpinBox()
        self.rating_spin.setRange(0.0, 10.0)
        self.rating_spin.setSingleStep(0.1)
        self.rating_spin.setDecimals(1)
        self.minutos_spin = self._spin(120)
        numeros = QGridLayout()
        numeros.setHorizontalSpacing(14)
        numeros.setVerticalSpacing(4)
        for columna, (rotulo, campo) in enumerate(
            (
                ("Tus goles", self.goles_jugador_spin),
                ("Asistencias", self.asistencias_spin),
                ("Rating", self.rating_spin),
                ("Minutos", self.minutos_spin),
            )
        ):
            numeros.addWidget(etiqueta_campo(rotulo), 0, columna)
            numeros.addWidget(campo, 1, columna)
        tarjeta.cuerpo.addLayout(numeros)

        self.amarilla_check = chip_alternable("Tarjeta amarilla")
        self.roja_check = chip_alternable("Tarjeta roja")
        self.motm_check = chip_alternable("Figura del partido")
        tarjeta.cuerpo.addLayout(
            fila(self.amarilla_check, self.roja_check, self.motm_check, estirar_al_final=True)
        )
        return tarjeta

    def _tarjeta_entrevista(self) -> Tarjeta:
        tarjeta = Tarjeta("2 · La entrevista", espaciado=14)
        self.titulo_entrevista = tarjeta.cuerpo.itemAt(0).widget()

        self.modo_post_btn = chip_alternable("Despues del partido")
        self.modo_post_btn.setChecked(True)
        self.modo_previa_btn = chip_alternable("Previa del proximo")
        self.modo_previa_btn.setToolTip("Conferencia de prensa antes de tu proximo partido (sale de tu partida de FC 26)")
        self._grupo_modo = QButtonGroup(self)
        self._grupo_modo.setExclusive(True)
        for boton_modo, modo in ((self.modo_post_btn, "post"), (self.modo_previa_btn, "previa")):
            self._grupo_modo.addButton(boton_modo)
            boton_modo.clicked.connect(lambda _=False, m=modo: self._poner_modo(m))
        tarjeta.cuerpo.addLayout(fila(self.modo_post_btn, self.modo_previa_btn, espaciado=8, estirar_al_final=True))
        self.previa_label = texto_suave()
        self.previa_label.hide()
        tarjeta.cuerpo.addWidget(self.previa_label)

        self.generar_entrevista_btn = boton(TEXTO_GENERAR, primario=True, icono_nombre="chispa")
        self.generar_entrevista_btn.clicked.connect(self._on_generar_entrevista_clicked)
        self.microfono_combo = QComboBox()
        self.microfono_combo.setMinimumWidth(260)
        self.microfono_combo.addItem("Predeterminado de Windows", None)
        self.microfono_combo.setToolTip("Microfono para responder por voz")
        tarjeta.cuerpo.addLayout(
            fila(
                self.generar_entrevista_btn,
                None,
                etiqueta_campo("Microfono"),
                self.microfono_combo,
            )
        )

        self.qa_layout = QVBoxLayout()
        self.qa_layout.setSpacing(12)
        tarjeta.cuerpo.addLayout(self.qa_layout)

        self.enviar_respuestas_btn = boton(TEXTO_ENVIAR, primario=True, icono_nombre="enviar")
        self.enviar_respuestas_btn.clicked.connect(self._on_enviar_respuestas_clicked)
        tarjeta.cuerpo.addLayout(fila(None, self.enviar_respuestas_btn))

        self.reaccion_tarjeta = Tarjeta("Reaccion de la prensa", destacada=True)
        self.reaccion_chips = QHBoxLayout()
        self.reaccion_tarjeta.cuerpo.addLayout(self.reaccion_chips)
        self.reaccion_label = QLabel()
        self.reaccion_label.setWordWrap(True)
        self.reaccion_tarjeta.cuerpo.addWidget(self.reaccion_label)
        self.reaccion_tarjeta.hide()
        tarjeta.cuerpo.addWidget(self.reaccion_tarjeta)
        return tarjeta

    def _tarjeta_prensa(self) -> Tarjeta:
        tarjeta = Tarjeta("3 · La prensa", espaciado=10)
        self.titulo_prensa = tarjeta.cuerpo.itemAt(0).widget()
        self.revisar_prensa_btn = boton(TEXTO_PRENSA, icono_nombre="prensa")
        self.revisar_prensa_btn.clicked.connect(self._on_revisar_prensa_clicked)
        tarjeta.cuerpo.addLayout(
            fila(texto_suave("Titulares sobre vos y del mundo del futbol.", ajustar=False), None, self.revisar_prensa_btn)
        )
        self.noticias_layout = QVBoxLayout()
        self.noticias_layout.setSpacing(8)
        tarjeta.cuerpo.addLayout(self.noticias_layout)
        return tarjeta

    @staticmethod
    def _spin(maximo: int) -> QSpinBox:
        spin = QSpinBox()
        spin.setRange(0, maximo)
        return spin

    @staticmethod
    def _spin_marcador() -> QSpinBox:
        spin = QSpinBox()
        spin.setObjectName("marcador")
        spin.setRange(0, 20)
        spin.setAlignment(Qt.AlignmentFlag.AlignCenter)
        spin.setFixedSize(112, 66)
        return spin

    # ---- estado ----

    def actualizar(self):
        """Recarga el perfil (por si se creo uno nuevo) y refresca la pagina."""
        self.perfil = load_latest_profile()
        self._refrescar_botones()

        if self.perfil is None:
            self.header_label.setText(
                "No encontre ningun personaje guardado. Crea uno primero desde el Resumen."
            )
            self.reputacion_mosaico.poner("-")
            self.club_edit.setText("")
            self.equipo_propio_label.setText("TU EQUIPO")
            return

        self.header_label.setText(self._texto_cabecera())
        self.club_edit.setText(self.perfil.club_actual)
        self.equipo_propio_label.setText((self.perfil.club_actual or "Tu equipo").upper())
        self._refrescar_reputacion()
        self._leer_partida()

    def _refrescar_botones(self):
        """Habilita cada boton segun lo que haya en curso. Es el unico lugar
        que lo decide: asi, volver a esta pestana en medio de una evaluacion
        no deja regenerar las preguntas que se estan evaluando."""
        hay_perfil = self.perfil is not None
        con_voz = self._grabacion is not None or self._transcribiendo is not None
        ocupado_con_preguntas = self._generando or self._evaluando is not None or con_voz
        self.guardar_club_btn.setEnabled(hay_perfil)
        self.capturar_btn.setEnabled(hay_perfil and not self._capturando)
        self.generar_entrevista_btn.setEnabled(hay_perfil and not ocupado_con_preguntas)
        self.enviar_respuestas_btn.setEnabled(
            hay_perfil and bool(self._preguntas) and not ocupado_con_preguntas
        )
        self.revisar_prensa_btn.setEnabled(hay_perfil and not self._prensa_en_curso)
        self.cargar_partida_btn.setEnabled(
            hay_perfil and self._lectura is not None and self._lectura.ultimo is not None
        )
        # cambiar de modo descarta las preguntas: no con algo en curso o respuestas escritas
        cambiar = hay_perfil and not self.ocupada()
        self.modo_post_btn.setEnabled(cambiar)
        self.modo_previa_btn.setEnabled(cambiar and self._previa() is not None)

        hay_microfono = self._sin_microfono is None
        self.microfono_combo.setEnabled(hay_microfono and self._grabacion is None)
        for numero, boton_voz in enumerate(self._botones_voz):
            grabando_esta = self._grabacion is not None and self._grabacion[1] == numero
            libre = (
                not self._generando
                and self._evaluando is None
                and self._transcribiendo is None
                and self._grabacion is None
            )
            boton_voz.setEnabled(hay_microfono and (grabando_esta or libre))
        self.cambio.emit()

    def _refrescar_reputacion(self):
        self.reputacion_mosaico.poner(get_reputacion_actual(self.perfil.id))

    def _leer_stats_desde_formulario(self) -> MatchStats:
        return MatchStats(
            goles_equipo=self.goles_equipo_spin.value(),
            goles_rival=self.goles_rival_spin.value(),
            equipo_rival=self.equipo_rival_edit.text().strip(),
            goles_jugador=self.goles_jugador_spin.value(),
            asistencias_jugador=self.asistencias_spin.value(),
            rating_jugador=self.rating_spin.value(),
            minutos_jugados=self.minutos_spin.value(),
            tarjeta_amarilla=self.amarilla_check.isChecked(),
            tarjeta_roja=self.roja_check.isChecked(),
            hombre_del_partido=self.motm_check.isChecked(),
        )

    def _cargar_stats_en_formulario(self, stats: MatchStats):
        self.goles_equipo_spin.setValue(stats.goles_equipo)
        self.goles_rival_spin.setValue(stats.goles_rival)
        self.equipo_rival_edit.setText(stats.equipo_rival)
        self.goles_jugador_spin.setValue(stats.goles_jugador)
        self.asistencias_spin.setValue(stats.asistencias_jugador)
        self.rating_spin.setValue(stats.rating_jugador)
        self.minutos_spin.setValue(stats.minutos_jugados)
        self.amarilla_check.setChecked(stats.tarjeta_amarilla)
        self.roja_check.setChecked(stats.tarjeta_roja)
        self.motm_check.setChecked(stats.hombre_del_partido)

    def _mostrar_preguntas(self, preguntas: list[str]):
        limpiar_layout(self.qa_layout)
        self._preguntas = preguntas
        self._respuesta_edits = []
        self._botones_voz = []
        self._cargar_microfonos()

        for numero, pregunta in enumerate(preguntas):
            caja = QFrame()
            caja.setObjectName("mosaico")
            caja_layout = QVBoxLayout(caja)
            caja_layout.setContentsMargins(16, 14, 16, 14)
            caja_layout.setSpacing(10)

            texto_pregunta = QLabel(esc(pregunta))
            texto_pregunta.setWordWrap(True)
            texto_pregunta.setFont(fuente_titulo(18, 0.2))
            caja_layout.addLayout(fila(chip(f"P{numero + 1}", estilos.ACENTO), texto_pregunta, espaciado=12))

            respuesta_edit = QTextEdit()
            respuesta_edit.setPlaceholderText("Tu respuesta... (escribila o grabala)")
            respuesta_edit.setFixedHeight(76)
            respuesta_edit.textChanged.connect(self._refrescar_botones)  # (emite cambio)
            caja_layout.addWidget(respuesta_edit)

            boton_voz = boton(TEXTO_VOZ, icono_nombre="microfono")
            boton_voz.setObjectName("microfono")
            boton_voz.clicked.connect(lambda _=False, n=numero: self._on_voz_clicked(n))
            caja_layout.addLayout(fila(None, boton_voz))

            self.qa_layout.addWidget(caja)
            self._respuesta_edits.append(respuesta_edit)
            self._botones_voz.append(boton_voz)

    # ---- 1. capturar pantalla ----

    def _on_capturar_clicked(self):
        self._capturando = True
        self._refrescar_botones()
        self.capturar_btn.setText("LEYENDO PANTALLA...")
        ejecutar_en_hilo(
            _capturar_y_leer,
            al_completar=self._on_extraccion_completada,
            al_fallar=self._on_extraccion_error,
        )

    def _on_extraccion_completada(self, stats: MatchStats):
        self._capturando = False
        self._refrescar_botones()
        self.capturar_btn.setText("VOLVER A CAPTURAR")
        self._cargar_stats_en_formulario(stats)
        self._origen, self._fecha_juego = "captura", ""
        self.partida_nota.hide()
        if stats.confianza_baja:
            QMessageBox.information(
                self,
                "Revisa los datos",
                "La IA no estaba muy segura de algunos numeros de la captura. "
                "Revisa los campos antes de generar la entrevista.",
            )

    def _on_extraccion_error(self, mensaje: str):
        self._capturando = False
        self._refrescar_botones()
        self.capturar_btn.setText(TEXTO_CAPTURAR.upper())
        QMessageBox.warning(self, "Error al capturar/leer la pantalla", mensaje)

    # ---- 2. generar preguntas ----

    def _on_generar_entrevista_clicked(self):
        if self._modo == "previa":
            funcion, argumentos = generar_previa, (self.perfil, self._previa(), self._contexto_real())
        else:
            funcion, argumentos = generar_entrevista, (
                self.perfil, self._leer_stats_desde_formulario(), self._contexto_real()
            )
        self._generando = True
        self._refrescar_botones()
        self.generar_entrevista_btn.setText("GENERANDO...")
        self.reaccion_tarjeta.hide()
        ejecutar_en_hilo(
            funcion,
            *argumentos,
            al_completar=self._on_entrevista_completada,
            al_fallar=self._on_entrevista_error,
        )

    def _texto_generar(self) -> str:
        if self._modo == "previa":
            texto = TEXTO_REGENERAR_PREVIA if self._preguntas else TEXTO_GENERAR_PREVIA
        else:
            texto = TEXTO_REGENERAR if self._preguntas else TEXTO_GENERAR
        return texto.upper()

    def _on_entrevista_completada(self, preguntas: list):
        self._generando = False
        self._mostrar_preguntas(preguntas)
        self._refrescar_botones()
        self.generar_entrevista_btn.setText(self._texto_generar())

    def _on_entrevista_error(self, mensaje: str):
        self._generando = False
        self._refrescar_botones()
        self.generar_entrevista_btn.setText(self._texto_generar())
        QMessageBox.warning(self, "Error al generar la entrevista", mensaje)

    # ---- 3a. responder por voz ----

    def _cargar_microfonos(self):
        """La lista de microfonos se arma recien cuando hay preguntas: para
        abrir la app no hace falta cargar la libreria de audio."""
        if self._microfonos_cargados:
            return
        self._microfonos_cargados = True
        try:
            microfonos = listar_microfonos()
        except RuntimeError as exc:
            self._sin_microfono = str(exc)
            self.microfono_combo.clear()
            self.microfono_combo.addItem("Sin microfono disponible", None)
            self.microfono_combo.setToolTip(self._sin_microfono)
            return
        self.microfono_combo.clear()
        for microfono in microfonos:
            self.microfono_combo.addItem(microfono.nombre, microfono.indice)

    def _on_voz_clicked(self, numero: int):
        if self._grabacion is not None:
            self._terminar_grabacion()
            return

        grabador = GrabadorMicrofono(dispositivo=self.microfono_combo.currentData())
        try:
            grabador.iniciar()
        except RuntimeError as exc:
            QMessageBox.warning(self, "No se pudo grabar", str(exc))
            return

        self._grabacion = (grabador, numero)
        boton_voz = self._botones_voz[numero]
        boton_voz.setProperty("grabando", True)
        boton_voz.setIcon(icono("detener", "#FFFFFF"))
        _repintar(boton_voz)
        self._tic_grabacion()
        self._reloj.start()
        self._refrescar_botones()

    def _tic_grabacion(self):
        if self._grabacion is None:
            return
        grabador, numero = self._grabacion
        segundos = int(grabador.segundos)
        self._botones_voz[numero].setText(f"DETENER · {segundos // 60}:{segundos % 60:02d}")
        self.cambio.emit()
        if grabador.lleno:
            self._terminar_grabacion()

    def _terminar_grabacion(self):
        grabador, numero = self._grabacion
        self._grabacion = None
        self._reloj.stop()
        wav = grabador.detener()

        boton_voz = self._botones_voz[numero]
        boton_voz.setProperty("grabando", False)
        boton_voz.setIcon(icono("microfono", estilos.TEXTO))
        _repintar(boton_voz)

        if grabador.segundos < MINIMO_SEGUNDOS:
            boton_voz.setText(TEXTO_VOZ.upper())
            self._refrescar_botones()
            QMessageBox.information(
                self, "Grabacion vacia", "No alcance a grabar nada. Apreta el boton, habla, y apretalo de nuevo."
            )
            return

        self._transcribiendo = numero
        boton_voz.setText("TRANSCRIBIENDO...")
        self._refrescar_botones()
        ejecutar_en_hilo(
            transcribir,
            wav,
            self._preguntas[numero],
            al_completar=self._on_transcripcion,
            al_fallar=self._on_transcripcion_error,
        )

    def _terminar_transcripcion(self) -> int:
        numero = self._transcribiendo
        self._transcribiendo = None
        self._botones_voz[numero].setText(TEXTO_VOZ.upper())
        self._refrescar_botones()
        return numero

    def _on_transcripcion(self, texto: str):
        numero = self._terminar_transcripcion()
        if not texto:
            QMessageBox.information(self, "No se escucho nada", "La grabacion no tenia voz. Proba de nuevo.")
            return
        edit = self._respuesta_edits[numero]
        anterior = edit.toPlainText().strip()
        edit.setPlainText(f"{anterior} {texto}" if anterior else texto)

    def _on_transcripcion_error(self, mensaje: str):
        self._terminar_transcripcion()
        QMessageBox.warning(self, "Error al transcribir", mensaje)

    # ---- 3b. enviar y evaluar ----

    def _on_enviar_respuestas_clicked(self):
        respuestas = [edit.toPlainText().strip() for edit in self._respuesta_edits]
        if not any(respuestas):
            QMessageBox.information(
                self, "Sin respuestas", "Responde al menos una pregunta antes de enviar."
            )
            return

        pares = list(zip(self._preguntas, respuestas))
        if self._modo == "previa":
            # en el lugar de las stats va la previa, y "previa" como origen
            previa = self._previa()
            self._evaluando = (self.perfil, previa, pares, "previa", previa.clave)
            funcion = evaluar_previa
        else:
            stats = self._leer_stats_desde_formulario()
            self._evaluando = (self.perfil, stats, pares, self._origen, self._fecha_juego)
            funcion = evaluar_respuestas
        self._refrescar_botones()
        self.enviar_respuestas_btn.setText("EVALUANDO...")

        ejecutar_en_hilo(
            funcion,
            self.perfil,
            self._evaluando[1],
            pares,
            self._contexto_real(),
            al_completar=self._on_evaluacion_completada,
            al_fallar=self._on_evaluacion_error,
        )

    def _on_evaluacion_completada(self, resultado):
        perfil, stats, pares, origen, fecha_juego = self._evaluando
        self._evaluando = None
        self._refrescar_botones()
        self.enviar_respuestas_btn.setText(TEXTO_ENVIAR.upper())
        if origen == "previa":
            self._registrar_previa(perfil, stats, resultado)
            return

        nueva_reputacion = aplicar_delta_reputacion(
            perfil.id,
            resultado.delta_reputacion,
            motivo=f"Entrevista post-partido vs {stats.equipo_rival or 'rival'}",
        )
        if resultado.nuevo_gancho_narrativo:
            agregar_gancho_narrativo(perfil.id, resultado.nuevo_gancho_narrativo)
            perfil.ganchos_narrativos.append(resultado.nuevo_gancho_narrativo)

        save_match_interview(
            MatchInterviewRecord(
                player_id=perfil.id,
                **stats.model_dump(exclude={"confianza_baja"}),
                preguntas_entrevista=[pregunta for pregunta, _ in pares],
                respuestas_jugador=[respuesta for _, respuesta in pares],
                reaccion_prensa=resultado.reaccion_prensa,
                delta_reputacion=resultado.delta_reputacion,
                origen=origen,
                fecha_juego=fecha_juego,
            )
        )
        if origen == "partida":
            self._leer_partida()  # para que diga "ya lo entrevistaste"

        self._mostrar_reaccion(resultado, nueva_reputacion, esc(resultado.reaccion_prensa))
        if self.perfil is not None and self.perfil.id == perfil.id:
            self._refrescar_reputacion()
            self._iniciar_revision_prensa(manual=False)

    def _mostrar_reaccion(self, resultado, nueva_reputacion: int, texto: str):
        delta = resultado.delta_reputacion
        color = estilos.POSITIVO if delta > 0 else estilos.NEGATIVO if delta < 0 else estilos.NEUTRO
        limpiar_layout(self.reaccion_chips)
        self.reaccion_chips.addWidget(chip(f"{'+' if delta >= 0 else ''}{delta} reputacion", color))
        self.reaccion_chips.addWidget(chip(f"Ahora {nueva_reputacion}/100", estilos.TEXTO_SUAVE))
        self.reaccion_chips.addStretch()
        if resultado.nuevo_gancho_narrativo:
            texto += (
                f"<br><br><span style='color:{estilos.ACENTO}'>Nueva trama:</span> "
                f"{esc(resultado.nuevo_gancho_narrativo)}"
            )
        self.reaccion_label.setText(texto)
        self.reaccion_tarjeta.show()
        self.cambio.emit()

    def _registrar_previa(self, perfil, previa, resultado):
        """La conferencia previa no es un partido: mueve la reputacion, deja
        su noticia y marca la previa como hecha."""
        nueva_reputacion = aplicar_delta_reputacion(
            perfil.id, resultado.delta_reputacion, motivo=f"Conferencia previa vs {previa.rival}"
        )
        if resultado.nuevo_gancho_narrativo:
            agregar_gancho_narrativo(perfil.id, resultado.nuevo_gancho_narrativo)
            perfil.ganchos_narrativos.append(resultado.nuevo_gancho_narrativo)
        noticia = noticia_de_previa(perfil, previa, resultado)
        save_noticia_prensa(noticia)
        set_estado_partida(perfil.id, {"previa": previa.clave})
        previa.ya_hecha = True

        self.ultimas_noticias = [noticia]
        limpiar_layout(self.noticias_layout)
        agregar_noticia(self.noticias_layout, noticia)
        self._mostrar_reaccion(
            resultado, nueva_reputacion, f"<b>{esc(resultado.titular)}</b><br>{esc(resultado.reaccion_prensa)}"
        )
        if self.perfil is not None and self.perfil.id == perfil.id:
            self._refrescar_reputacion()
            self._mostrar_previa()

    def _on_evaluacion_error(self, mensaje: str):
        self._evaluando = None
        self._refrescar_botones()
        self.enviar_respuestas_btn.setText(TEXTO_ENVIAR.upper())
        QMessageBox.warning(self, "Error al evaluar las respuestas", mensaje)

    # ---- partida de FC 26 ----

    def _contexto_real(self) -> str:
        return self._lectura.contexto if self._lectura is not None else ""

    def _leer_partida(self):
        """Lee el guardado mas reciente en otro hilo (la primera vez tarda
        ~1 s; despues, si el archivo no cambio, sale de la cache)."""
        if self._leyendo_partida or self.perfil is None:
            return
        self._leyendo_partida = True
        ejecutar_en_hilo(
            leer_para_entrevista,
            self.perfil.id,
            al_completar=self._on_partida_leida,
            al_fallar=self._on_partida_error,
        )

    def _on_partida_leida(self, lectura):
        self._leyendo_partida = False
        self._lectura = lectura
        if lectura is None:
            self.partida_label.setText(
                "No encontre una partida de Carrera Jugador de FC 26 en este PC. "
                "Captura la pantalla de stats o escribilas a mano."
            )
        elif lectura.ultimo is None:
            self.partida_label.setText(f"Tu partida \"{esc(lectura.carrera.partida)}\" todavia no tiene partidos jugados.")
        else:
            ya = (
                f" · <span style='color:{estilos.ACENTO}'>ya lo entrevistaste</span>"
                if lectura.ya_entrevistado else ""
            )
            self.partida_label.setText(f"<b>Tu ultimo partido:</b> {esc(lectura.ultimo.resumen)}{ya}")
        if self._modo == "previa" and self._previa() is None and not self.ocupada():
            self._poner_modo("post")  # ya no hay proximo partido (fin de temporada)
        self._mostrar_previa()
        self._refrescar_botones()

    def _on_partida_error(self, mensaje: str):
        self._leyendo_partida = False
        self._lectura = None
        self.partida_label.setText(f"No pude leer tu partida de FC 26 ({esc(mensaje)}). Captura la pantalla o escribi las stats.")
        self._refrescar_botones()

    def ocupada(self) -> bool:
        """Hay una entrevista a medio hacer (preguntas con respuestas sin
        enviar, o algo en curso): no se le pisa con un partido nuevo."""
        return bool(
            self._generando or self._evaluando is not None or self._grabacion is not None
            or self._transcribiendo is not None
            or any(edit.toPlainText().strip() for edit in self._respuesta_edits)
        )

    def recibir_partido_nuevo(self, lectura, preparar_preguntas: bool) -> bool:
        """Modo en vivo: el juego guardo un partido nuevo. Si la sala esta
        libre, lo carga y (si se pide) genera las preguntas. Devuelve si lo
        cargo."""
        self._on_partida_leida(lectura)
        if self.perfil is None or self.ocupada() or lectura.ultimo is None:
            return False
        self._poner_modo("post")
        self._on_cargar_partida_clicked()
        if preparar_preguntas:
            self._on_generar_entrevista_clicked()
        return True

    def _on_cargar_partida_clicked(self):
        ultimo = self._lectura.ultimo
        self._cargar_stats_en_formulario(ultimo.stats)
        club = self._lectura.carrera.equipo(ultimo.equipo)
        if club != self.perfil.club_actual:
            actualizar_club(self.perfil.id, club)
            self.perfil.club_actual = club
            self.club_edit.setText(club)
            self.equipo_propio_label.setText(club.upper())
        set_estado_partida(self.perfil.id, ultimo.estado)
        self._origen, self._fecha_juego = "partida", ultimo.partido.fecha.isoformat()
        if ultimo.exacto:
            self.partida_nota.setText("Cargado de tu partida, con asistencias, tarjetas y figura del partido.")
        else:
            self.partida_nota.setText(
                "Cargado de tu partida. Las asistencias, tarjetas y figura de este partido revisalas a mano: "
                "el juego solo guarda los totales, asi que salen solas recien desde el proximo partido que cargues."
            )
        self.partida_nota.show()

    # ---- conferencia previa ----

    def _previa(self):
        return self._lectura.previa if self._lectura is not None else None

    def _texto_cabecera(self) -> str:
        nombre = esc(self.perfil.nombre_jugador) if self.perfil is not None else ""
        if self._modo == "previa":
            return f"Conferencia previa de {nombre}"
        return f"Entrevista post-partido de {nombre}"

    def texto_contexto(self) -> str:
        """Lo que la sala flotante muestra arriba: el partido o la previa."""
        previa = self._previa()
        if self._modo == "previa" and previa is not None:
            return f"<b>Previa:</b> {esc(previa.resumen)}"
        return self.partida_label.text()

    def _mostrar_previa(self):
        previa = self._previa()
        if self._modo != "previa" or previa is None:
            self.previa_label.hide()
            return
        ya = f" · <span style='color:{estilos.ACENTO}'>ya diste esta conferencia</span>" if previa.ya_hecha else ""
        lineas = [f"<b style='color:{estilos.TEXTO}'>Proximo partido:</b> {esc(previa.resumen)}{ya}"]
        lineas += [f"<span style='color:{estilos.ACENTO}'>▸</span> {esc(dato)}" for dato in previa.datos]
        self.previa_label.setText("<br>".join(lineas))
        self.previa_label.show()

    def _poner_modo(self, modo: str):
        if modo == self._modo:
            return
        if self.ocupada() or (modo == "previa" and self._previa() is None):
            # (los botones ya lo impiden; por las dudas, se deja todo como estaba)
            self.modo_post_btn.setChecked(self._modo == "post")
            self.modo_previa_btn.setChecked(self._modo == "previa")
            return
        self._modo = modo
        self.modo_post_btn.setChecked(modo == "post")
        self.modo_previa_btn.setChecked(modo == "previa")
        # las preguntas del otro modo se descartan (sin cargar los microfonos)
        limpiar_layout(self.qa_layout)
        self._preguntas, self._respuesta_edits, self._botones_voz = [], [], []
        self.reaccion_tarjeta.hide()
        self.tarjeta_partido.setVisible(modo == "post")
        # en la previa no esta la tarjeta del partido: se renumera
        self.titulo_entrevista.setText("2 · LA ENTREVISTA" if modo == "post" else "1 · LA CONFERENCIA")
        self.titulo_prensa.setText("3 · LA PRENSA" if modo == "post" else "2 · LA PRENSA")
        if self.perfil is not None:
            self.header_label.setText(self._texto_cabecera())
        self.generar_entrevista_btn.setText(self._texto_generar())
        self._mostrar_previa()
        self._refrescar_botones()

    # ---- club ----

    def _on_guardar_club_clicked(self):
        nuevo_club = self.club_edit.text().strip()
        actualizar_club(self.perfil.id, nuevo_club)
        self.perfil.club_actual = nuevo_club
        self.equipo_propio_label.setText((nuevo_club or "Tu equipo").upper())
        QMessageBox.information(
            self, "Club actualizado", f"Club actual: {nuevo_club or '(sin definir)'}"
        )

    # ---- prensa ----

    def _on_revisar_prensa_clicked(self):
        self._iniciar_revision_prensa(manual=True)

    def _iniciar_revision_prensa(self, manual: bool):
        # Una revision a la vez: dos en paralelo leen el mismo estado de
        # prensa y publican dos veces el mismo hito.
        if self._prensa_en_curso:
            return
        self._prensa_en_curso = True
        self._prensa_manual = manual
        self._prensa_player_id = self.perfil.id
        self._refrescar_botones()
        self.revisar_prensa_btn.setText("REVISANDO...")

        argumentos = [self.perfil, load_match_interviews(self.perfil.id), get_estado_prensa(self.perfil.id)]
        if self._lectura is not None:
            # con la partida: contexto real y noticias de hechos reales
            funcion, argumentos = revisar_prensa_con_partida, [*argumentos, self._lectura.carrera]
        else:
            funcion = revisar_prensa
        ejecutar_en_hilo(
            funcion,
            *argumentos,
            al_completar=self._on_prensa_completada,
            al_fallar=self._on_prensa_error,
        )

    def _terminar_revision_prensa(self):
        self._prensa_en_curso = False
        self._refrescar_botones()
        self.revisar_prensa_btn.setText(TEXTO_PRENSA.upper())

    def _on_prensa_completada(self, resultado: dict):
        self._terminar_revision_prensa()
        set_estado_prensa(self._prensa_player_id, resultado["estado_prensa"])
        actualizar_metas(self._prensa_player_id, resultado.get("metas", {}))
        bono = resultado.get("delta_reputacion", 0)
        if bono:
            premios = ", ".join(h["tipo"] for h in resultado["hitos"] if h["tipo"] in BONOS_REPUTACION)
            aplicar_delta_reputacion(self._prensa_player_id, bono, motivo=f"Premios, metas y logros: {premios}")
            if self.perfil is not None and self.perfil.id == self._prensa_player_id:
                self._refrescar_reputacion()
        for noticia in resultado["noticias"]:
            save_noticia_prensa(noticia)
        if resultado["noticias"]:
            self.ultimas_noticias = list(resultado["noticias"])
            self.cambio.emit()

        if resultado["noticias"]:
            limpiar_layout(self.noticias_layout)
            for i, noticia in enumerate(resultado["noticias"]):
                if i:
                    self.noticias_layout.addWidget(separador())
                agregar_noticia(self.noticias_layout, noticia)
        elif self._prensa_manual:
            limpiar_layout(self.noticias_layout)
            self.noticias_layout.addWidget(texto_suave("Sin novedades de prensa por ahora."))

    def _on_prensa_error(self, mensaje: str):
        self._terminar_revision_prensa()
        # Si fue la revision automatica de despues de la entrevista, se
        # falla en silencio: no vale la pena cortar el flujo por la nota
        # de color.
        if self._prensa_manual:
            QMessageBox.warning(self, "Error al revisar la prensa", mensaje)
