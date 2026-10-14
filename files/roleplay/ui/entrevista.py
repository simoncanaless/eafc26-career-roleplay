"""
Pagina de entrevistas post-partido. Flujo:

1. Capturar la pantalla de fin de partido y leer las stats con Gemini
   Vision, o escribirlas a mano. Quedan editables en los dos casos.
2. Generar las preguntas con Gemini (perfil + partido).
3. El usuario responde con sus palabras.
4. Gemini evalua las respuestas: reaccion de prensa, cambio de
   reputacion y, a veces, un gancho narrativo nuevo. Se guarda todo y se
   revisa si el partido disparo algun hito de prensa.
"""

from PySide6.QtWidgets import (
    QCheckBox,
    QDoubleSpinBox,
    QFormLayout,
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
    agregar_gancho_narrativo,
    aplicar_delta_reputacion,
    get_estado_prensa,
    get_reputacion_actual,
    load_latest_profile,
    load_match_interviews,
    save_match_interview,
    save_noticia_prensa,
    set_estado_prensa,
)
from roleplay.models import MatchInterviewRecord, PlayerProfile
from roleplay.servicios.captura import capturar_pantalla
from roleplay.servicios.entrevista import evaluar_respuestas, generar_entrevista
from roleplay.servicios.prensa import revisar_prensa
from roleplay.servicios.vision import MatchStats, extraer_stats_partido
from roleplay.ui.comun import ejecutar_en_hilo, esc
from roleplay.ui.estilos import marcar_subtitulo, marcar_titulo

TEXTO_CAPTURAR = "Capturar pantalla de fin de partido"
TEXTO_GENERAR = "Generar entrevista con IA"
TEXTO_REGENERAR = "Regenerar entrevista"
TEXTO_ENVIAR = "Enviar respuestas y ver reaccion de la prensa"
TEXTO_PRENSA = "Revisar prensa ahora"


def _capturar_y_leer() -> MatchStats:
    return extraer_stats_partido(capturar_pantalla())


class InterviewWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("EAFC 26 Roleplay - Entrevista post-partido")

        self.perfil = None
        self._preguntas: list[str] = []
        self._respuesta_edits: list[QTextEdit] = []
        # Lo que hay en curso. _evaluando guarda lo que se mando a evaluar
        # (jugador, stats, preguntas y respuestas), para guardar exactamente
        # eso aunque se toque el formulario, o se cree otro personaje,
        # mientras Gemini responde.
        self._capturando = False
        self._generando = False
        self._evaluando: tuple[PlayerProfile, MatchStats, list[tuple[str, str]]] | None = None
        self._prensa_en_curso = False
        self._prensa_player_id: int | None = None
        self._prensa_manual = False

        layout = QVBoxLayout()
        layout.setContentsMargins(28, 28, 28, 28)
        layout.setSpacing(8)

        self.header_label = QLabel()
        self.header_label.setWordWrap(True)
        marcar_titulo(self.header_label)
        layout.addWidget(self.header_label)

        self.reputacion_label = QLabel()
        layout.addWidget(self.reputacion_label)

        club_layout = QHBoxLayout()
        club_layout.addWidget(QLabel("Club actual:"))
        self.club_edit = QLineEdit()
        self.club_edit.setPlaceholderText("Ej: Luton Town")
        club_layout.addWidget(self.club_edit)
        self.guardar_club_btn = QPushButton("Guardar club")
        self.guardar_club_btn.clicked.connect(self._on_guardar_club_clicked)
        club_layout.addWidget(self.guardar_club_btn)
        layout.addLayout(club_layout)

        # ---- 1. el partido ----
        layout.addSpacing(8)
        layout.addWidget(self._subtitulo("1. El partido"))
        layout.addWidget(QLabel("Captura la pantalla de stats o escribilas a mano:"))

        self.capturar_btn = QPushButton(TEXTO_CAPTURAR)
        self.capturar_btn.clicked.connect(self._on_capturar_clicked)
        layout.addWidget(self.capturar_btn)

        form = QFormLayout()
        self.goles_equipo_spin = self._spin(form, "Goles de tu equipo:", 20)
        self.goles_rival_spin = self._spin(form, "Goles del rival:", 20)
        self.equipo_rival_edit = QLineEdit()
        form.addRow("Equipo rival:", self.equipo_rival_edit)
        self.goles_jugador_spin = self._spin(form, "Tus goles:", 10)
        self.asistencias_spin = self._spin(form, "Tus asistencias:", 10)
        self.rating_spin = QDoubleSpinBox()
        self.rating_spin.setRange(0.0, 10.0)
        self.rating_spin.setSingleStep(0.1)
        self.rating_spin.setDecimals(1)
        form.addRow("Tu rating:", self.rating_spin)
        self.minutos_spin = self._spin(form, "Minutos jugados:", 120)
        layout.addLayout(form)

        checks_layout = QHBoxLayout()
        self.amarilla_check = QCheckBox("Tarjeta amarilla")
        self.roja_check = QCheckBox("Tarjeta roja")
        self.motm_check = QCheckBox("Hombre del partido")
        for check in (self.amarilla_check, self.roja_check, self.motm_check):
            checks_layout.addWidget(check)
        checks_layout.addStretch()
        layout.addLayout(checks_layout)

        # ---- 2. la entrevista ----
        layout.addSpacing(8)
        layout.addWidget(self._subtitulo("2. La entrevista"))

        self.generar_entrevista_btn = QPushButton(TEXTO_GENERAR)
        self.generar_entrevista_btn.clicked.connect(self._on_generar_entrevista_clicked)
        layout.addWidget(self.generar_entrevista_btn)

        self.qa_layout = QVBoxLayout()
        self.qa_layout.setContentsMargins(0, 0, 0, 0)
        layout.addLayout(self.qa_layout)

        self.enviar_respuestas_btn = QPushButton(TEXTO_ENVIAR)
        self.enviar_respuestas_btn.clicked.connect(self._on_enviar_respuestas_clicked)
        layout.addWidget(self.enviar_respuestas_btn)

        self.reaccion_label = QLabel()
        self.reaccion_label.setWordWrap(True)
        layout.addWidget(self.reaccion_label)

        # ---- 3. la prensa ----
        layout.addSpacing(8)
        layout.addWidget(self._subtitulo("3. La prensa"))
        layout.addWidget(QLabel("Titulares sobre vos y del mundo del futbol:"))
        self.noticias_label = QLabel()
        self.noticias_label.setWordWrap(True)
        layout.addWidget(self.noticias_label)

        self.revisar_prensa_btn = QPushButton(TEXTO_PRENSA)
        self.revisar_prensa_btn.clicked.connect(self._on_revisar_prensa_clicked)
        layout.addWidget(self.revisar_prensa_btn)

        layout.addStretch()
        self.setLayout(layout)
        self.actualizar()

    @staticmethod
    def _subtitulo(texto: str) -> QLabel:
        label = QLabel(texto)
        marcar_subtitulo(label)
        return label

    @staticmethod
    def _spin(form: QFormLayout, etiqueta: str, maximo: int) -> QSpinBox:
        spin = QSpinBox()
        spin.setRange(0, maximo)
        form.addRow(etiqueta, spin)
        return spin

    def actualizar(self):
        """Recarga el perfil (por si se creo uno nuevo) y refresca la pagina."""
        self.perfil = load_latest_profile()
        self._refrescar_botones()

        if self.perfil is None:
            self.header_label.setText(
                "No encontre ningun personaje guardado. Crea uno primero desde la pestana de Resumen."
            )
            self.reputacion_label.setText("")
            self.club_edit.setText("")
            return

        self.header_label.setText(f"Entrevista post-partido de {esc(self.perfil.nombre_jugador)}")
        self.club_edit.setText(self.perfil.club_actual)
        self._refrescar_reputacion_label()

    # ---- helpers de estado ----

    def _refrescar_botones(self):
        """Habilita cada boton segun lo que haya en curso. Es el unico lugar
        que lo decide: asi, volver a esta pestana en medio de una evaluacion
        no deja regenerar las preguntas que se estan evaluando."""
        hay_perfil = self.perfil is not None
        ocupado_con_preguntas = self._generando or self._evaluando is not None
        self.guardar_club_btn.setEnabled(hay_perfil)
        self.capturar_btn.setEnabled(hay_perfil and not self._capturando)
        self.generar_entrevista_btn.setEnabled(hay_perfil and not ocupado_con_preguntas)
        self.enviar_respuestas_btn.setEnabled(
            hay_perfil and bool(self._preguntas) and not ocupado_con_preguntas
        )
        self.revisar_prensa_btn.setEnabled(hay_perfil and not self._prensa_en_curso)

    def _refrescar_reputacion_label(self):
        reputacion = get_reputacion_actual(self.perfil.id)
        self.reputacion_label.setText(f"Reputacion actual: {reputacion}/100")

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
        while self.qa_layout.count():
            widget = self.qa_layout.takeAt(0).widget()
            if widget is not None:
                widget.deleteLater()

        self._preguntas = preguntas
        self._respuesta_edits = []
        for i, pregunta in enumerate(preguntas, start=1):
            pregunta_label = QLabel(f"<b>{i}.</b> {esc(pregunta)}")
            pregunta_label.setWordWrap(True)
            self.qa_layout.addWidget(pregunta_label)

            respuesta_edit = QTextEdit()
            respuesta_edit.setPlaceholderText("Tu respuesta...")
            respuesta_edit.setMaximumHeight(70)
            self.qa_layout.addWidget(respuesta_edit)
            self._respuesta_edits.append(respuesta_edit)

    # ---- 1. capturar pantalla ----

    def _on_capturar_clicked(self):
        self._capturando = True
        self._refrescar_botones()
        self.capturar_btn.setText("Capturando y leyendo pantalla...")
        ejecutar_en_hilo(
            _capturar_y_leer,
            al_completar=self._on_extraccion_completada,
            al_fallar=self._on_extraccion_error,
        )

    def _on_extraccion_completada(self, stats: MatchStats):
        self._capturando = False
        self._refrescar_botones()
        self.capturar_btn.setText("Volver a capturar pantalla")
        self._cargar_stats_en_formulario(stats)
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
        self.capturar_btn.setText(TEXTO_CAPTURAR)
        QMessageBox.warning(self, "Error al capturar/leer la pantalla", mensaje)

    # ---- 2. generar preguntas ----

    def _on_generar_entrevista_clicked(self):
        self._generando = True
        self._refrescar_botones()
        self.generar_entrevista_btn.setText("Generando...")
        self.reaccion_label.setText("")
        ejecutar_en_hilo(
            generar_entrevista,
            self.perfil,
            self._leer_stats_desde_formulario(),
            al_completar=self._on_entrevista_completada,
            al_fallar=self._on_entrevista_error,
        )

    def _on_entrevista_completada(self, preguntas: list):
        self._generando = False
        self._mostrar_preguntas(preguntas)
        self._refrescar_botones()
        self.generar_entrevista_btn.setText(TEXTO_REGENERAR)

    def _on_entrevista_error(self, mensaje: str):
        self._generando = False
        self._refrescar_botones()
        self.generar_entrevista_btn.setText(TEXTO_REGENERAR if self._preguntas else TEXTO_GENERAR)
        QMessageBox.warning(self, "Error al generar la entrevista", mensaje)

    # ---- 3. responder y evaluar ----

    def _on_enviar_respuestas_clicked(self):
        respuestas = [edit.toPlainText().strip() for edit in self._respuesta_edits]
        if not any(respuestas):
            QMessageBox.information(
                self, "Sin respuestas", "Responde al menos una pregunta antes de enviar."
            )
            return

        stats = self._leer_stats_desde_formulario()
        pares = list(zip(self._preguntas, respuestas))
        self._evaluando = (self.perfil, stats, pares)
        self._refrescar_botones()
        self.enviar_respuestas_btn.setText("Evaluando reacciones...")

        ejecutar_en_hilo(
            evaluar_respuestas,
            self.perfil,
            stats,
            pares,
            al_completar=self._on_evaluacion_completada,
            al_fallar=self._on_evaluacion_error,
        )

    def _on_evaluacion_completada(self, resultado):
        perfil, stats, pares = self._evaluando
        self._evaluando = None
        self._refrescar_botones()
        self.enviar_respuestas_btn.setText(TEXTO_ENVIAR)

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
            )
        )

        signo = "+" if resultado.delta_reputacion >= 0 else ""
        texto = (
            f"<b>Reaccion de la prensa:</b> {esc(resultado.reaccion_prensa)}<br>"
            f"<b>Impacto en reputacion:</b> {signo}{resultado.delta_reputacion} "
            f"(ahora: {nueva_reputacion}/100)"
        )
        if resultado.nuevo_gancho_narrativo:
            texto += f"<br><b>Nuevo gancho narrativo:</b> {esc(resultado.nuevo_gancho_narrativo)}"
        self.reaccion_label.setText(texto)
        if self.perfil is not None and self.perfil.id == perfil.id:
            self._refrescar_reputacion_label()
            self._iniciar_revision_prensa(manual=False)

    def _on_evaluacion_error(self, mensaje: str):
        self._evaluando = None
        self._refrescar_botones()
        self.enviar_respuestas_btn.setText(TEXTO_ENVIAR)
        QMessageBox.warning(self, "Error al evaluar las respuestas", mensaje)

    # ---- club ----

    def _on_guardar_club_clicked(self):
        nuevo_club = self.club_edit.text().strip()
        actualizar_club(self.perfil.id, nuevo_club)
        self.perfil.club_actual = nuevo_club
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
        self.revisar_prensa_btn.setText("Revisando...")

        ejecutar_en_hilo(
            revisar_prensa,
            self.perfil,
            load_match_interviews(self.perfil.id),
            get_estado_prensa(self.perfil.id),
            al_completar=self._on_prensa_completada,
            al_fallar=self._on_prensa_error,
        )

    def _terminar_revision_prensa(self):
        self._prensa_en_curso = False
        self._refrescar_botones()
        self.revisar_prensa_btn.setText(TEXTO_PRENSA)

    def _on_prensa_completada(self, resultado: dict):
        self._terminar_revision_prensa()
        set_estado_prensa(self._prensa_player_id, resultado["estado_prensa"])
        for noticia in resultado["noticias"]:
            save_noticia_prensa(noticia)

        if resultado["noticias"]:
            bloques = []
            for noticia in resultado["noticias"]:
                etiqueta = "📰 Sobre vos" if noticia.categoria == "jugador" else "🌍 Mundo del futbol"
                bloques.append(f"<b>{etiqueta}: {esc(noticia.titular)}</b><br>{esc(noticia.cuerpo)}")
            self.noticias_label.setText("<br><br>".join(bloques))
        elif self._prensa_manual:
            self.noticias_label.setText("Sin novedades de prensa por ahora.")

    def _on_prensa_error(self, mensaje: str):
        self._terminar_revision_prensa()
        # Si fue la revision automatica de despues de la entrevista, se
        # falla en silencio: no vale la pena cortar el flujo por la nota
        # de color.
        if self._prensa_manual:
            QMessageBox.warning(self, "Error al revisar la prensa", mensaje)
