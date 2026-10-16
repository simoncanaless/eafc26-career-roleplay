"""
Ajustes: como se abre el juego, la partida que se lee, el modo en vivo,
el motor narrativo (claves opcionales de la IA hibrida: sin ellas, o con
"solo motor local", la app funciona igual y sin internet), los dos iconos
del escritorio y el diagnostico.
"""

import os

from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QFileDialog,
    QLineEdit,
    QMessageBox,
    QPlainTextEdit,
    QVBoxLayout,
    QWidget,
)

from roleplay import ajustes
from roleplay.partida import lector
from roleplay.ui.atajo import ATAJO_TEXTO
from roleplay.servicios.accesos import crear_accesos
from roleplay.servicios.juego import abrir_juego, elegir_a_mano, juego_configurado, olvidar_eleccion
from roleplay.ui.comun import ejecutar_en_hilo, esc
from roleplay.ui.componentes import Tarjeta, boton, fila, texto_suave, titulo_pagina

FILTRO_JUEGO = "El juego o su acceso directo (*.exe *.lnk *.url)"


def elegir_juego_a_mano(padre: QWidget):
    ruta, _ = QFileDialog.getOpenFileName(
        padre, "Elegi el juego (FC26.exe) o su acceso directo", os.path.expanduser("~/Desktop"), FILTRO_JUEGO
    )
    return elegir_a_mano(ruta) if ruta else None


def abrir_juego_o_preguntar(padre: QWidget) -> bool:
    """Abre EA FC 26 por su plataforma. Si no se encuentra, pide elegirlo
    (una sola vez: queda guardado). Devuelve si se abrio."""
    juego = juego_configurado()
    if juego is None:
        QMessageBox.information(
            padre,
            "No encontre EA FC 26",
            "No encontre el juego en Steam, la EA app ni Epic. Elegi su .exe o su "
            "acceso directo una vez y queda guardado.",
        )
        juego = elegir_juego_a_mano(padre)
        if juego is None:
            return False
    try:
        abrir_juego(juego)
    except (RuntimeError, OSError) as exc:
        QMessageBox.warning(padre, "No se pudo abrir el juego", str(exc))
        return False
    return True


class DialogoAjustes(QDialog):
    def __init__(self, padre: QWidget | None = None):
        super().__init__(padre)
        self.setWindowTitle("EAFC 26 Roleplay - Ajustes")
        self.setMinimumWidth(680)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(30, 28, 30, 24)
        layout.setSpacing(14)
        layout.addWidget(titulo_pagina("Ajustes"))

        juego = Tarjeta("El juego")
        self.juego_label = texto_suave()
        elegir = boton("Elegir a mano...")
        elegir.clicked.connect(self._on_elegir_juego)
        detectar = boton("Detectar de nuevo")
        detectar.clicked.connect(self._on_detectar)
        juego.cuerpo.addWidget(self.juego_label)
        juego.cuerpo.addLayout(fila(None, detectar, elegir))
        layout.addWidget(juego)

        partida = Tarjeta("Tu partida de FC 26")
        partida.cuerpo.addWidget(
            texto_suave(
                "La sala de prensa y el Resumen leen tu partida de Carrera Jugador (resultados, "
                "quien hizo los goles, tus numeros). Solo se lee: el juego no se toca."
            )
        )
        self.partida_label = texto_suave()
        partida.cuerpo.addWidget(self.partida_label)
        reciente = boton("Usar la mas reciente")
        reciente.clicked.connect(self._on_partida_reciente)
        elegir_partida = boton("Elegir otra...")
        elegir_partida.clicked.connect(self._on_elegir_partida)
        partida.cuerpo.addLayout(fila(None, reciente, elegir_partida))
        layout.addWidget(partida)

        en_vivo = Tarjeta("Modo en vivo")
        en_vivo.cuerpo.addWidget(
            texto_suave(
                "Mientras juegas, la app mira tu partida: cuando el juego guarda un partido nuevo, "
                "te avisa y actualiza la prensa."
            )
        )
        actuales = ajustes.leer().get("en_vivo", {})
        self.vigilar_check = QCheckBox("Avisarme cuando juegue un partido nuevo")
        self.vigilar_check.setChecked(actuales.get("vigilar", True))
        self.preguntas_check = QCheckBox("Dejar la entrevista lista (cargar el partido y generar las preguntas)")
        self.preguntas_check.setChecked(actuales.get("preguntas_solas", True))
        self.flotante_check = QCheckBox("Mostrar la sala flotante encima del juego al terminar un partido")
        self.flotante_check.setChecked(actuales.get("flotante", True))
        for casilla in (self.vigilar_check, self.preguntas_check, self.flotante_check):
            casilla.toggled.connect(self._on_en_vivo)
            en_vivo.cuerpo.addWidget(casilla)
        en_vivo.cuerpo.addWidget(
            texto_suave(
                f"La sala flotante se abre y se cierra con {ATAJO_TEXTO}, aunque estes jugando. "
                "Para que se vea encima del juego, usa FC 26 en \"Ventana sin bordes\"."
            )
        )
        layout.addWidget(en_vivo)

        motor = Tarjeta("Motor narrativo e IA hibrida")
        motor.cuerpo.addWidget(
            texto_suave(
                "El motor local escribe todo al instante y sin internet. Con una clave, la IA reescribe las "
                "preguntas, la reaccion de la prensa y los comentarios contestando a lo que vos dijiste "
                "(los numeros y los hechos los sigue poniendo la app). Lo que escribis se manda al proveedor."
            )
        )
        guardados = ajustes.leer()
        self.groq_edit = QLineEdit(guardados.get("groq_api_key", ""))
        self.groq_edit.setPlaceholderText("Clave de Groq (recomendado: gratis y ~0,3 s, en console.groq.com)")
        self.gemini_edit = QLineEdit(guardados.get("gemini_api_key", ""))
        self.gemini_edit.setPlaceholderText("Clave de Gemini (opcional, de respaldo)")
        for edit in (self.groq_edit, self.gemini_edit):
            edit.setEchoMode(QLineEdit.EchoMode.Password)
            edit.editingFinished.connect(self._on_claves)
            motor.cuerpo.addWidget(edit)
        self.sin_ia_check = QCheckBox("Usar solo motor local sin IA (0 ms, offline)")
        self.sin_ia_check.setChecked(bool(guardados.get("sin_ia")))
        self.sin_ia_check.toggled.connect(self._on_sin_ia)
        self.prueba_label = texto_suave()
        self.probar_btn = boton("Probar IA")
        self.probar_btn.clicked.connect(self._on_probar_ia)
        motor.cuerpo.addWidget(self.sin_ia_check)
        motor.cuerpo.addLayout(fila(self.prueba_label, None, self.probar_btn))
        layout.addWidget(motor)

        iconos = Tarjeta("Iconos del escritorio")
        iconos.cuerpo.addWidget(
            texto_suave(
                "Crea dos iconos: \"EA FC 26\" abre el juego normal, y \"EA FC 26 + Roleplay\" "
                "abre el mismo juego y ademas esta app. El juego no se modifica en ninguno de los dos."
            )
        )
        crear = boton("Crear los dos iconos", primario=True)
        crear.clicked.connect(self._on_crear_iconos)
        iconos.cuerpo.addLayout(fila(None, crear))
        layout.addWidget(iconos)

        diagnostico = Tarjeta("Diagnostico")
        self.diagnostico_edit = QPlainTextEdit()
        self.diagnostico_edit.setReadOnly(True)
        self.diagnostico_edit.setFixedHeight(120)
        self.diagnostico_edit.hide()
        revisar = boton("Revisar")
        revisar.clicked.connect(self._on_diagnostico)
        self.copiar_btn = boton("Copiar")
        self.copiar_btn.clicked.connect(
            lambda: QGuiApplication.clipboard().setText(self.diagnostico_edit.toPlainText())
        )
        self.copiar_btn.hide()
        diagnostico.cuerpo.addLayout(
            fila(texto_suave("Si algo no funciona, revisa y manda el resultado.", ajustar=False), None, self.copiar_btn, revisar)
        )
        diagnostico.cuerpo.addWidget(self.diagnostico_edit)
        layout.addWidget(diagnostico)

        cerrar = boton("Cerrar")
        cerrar.clicked.connect(self.accept)
        layout.addLayout(fila(None, cerrar))
        self._refrescar()

    def _refrescar(self):
        elegida = lector.guardado_elegido()
        if elegida is None:
            self.partida_label.setText(
                f"No encontre partidas de Carrera Jugador en {esc(str(lector.CARPETA_GUARDADOS))}."
            )
        else:
            cual = "elegida a mano" if ajustes.leer().get("partida") else "la mas reciente"
            self.partida_label.setText(f"<b>{esc(elegida.name)}</b> ({cual})")
        juego = juego_configurado()
        self.juego_label.setText(
            f"<b>{esc(juego.describir())}</b><br>{esc(juego.comando)}" if juego
            else "No encontre EA FC 26 en Steam, la EA app ni Epic. Elegilo a mano."
        )

    def _on_elegir_juego(self):
        try:
            elegir_juego_a_mano(self)
        except ValueError as exc:
            QMessageBox.warning(self, "No se pudo elegir", str(exc))
        self._refrescar()

    def _on_en_vivo(self, *_):
        ajustes.guardar(en_vivo={
            "vigilar": self.vigilar_check.isChecked(),
            "preguntas_solas": self.preguntas_check.isChecked(),
            "flotante": self.flotante_check.isChecked(),
        })
        self.preguntas_check.setEnabled(self.vigilar_check.isChecked())
        self.flotante_check.setEnabled(self.vigilar_check.isChecked())

    def _on_claves(self):
        ajustes.guardar(groq_api_key=self.groq_edit.text().strip() or None,
                        gemini_api_key=self.gemini_edit.text().strip() or None)

    def _on_sin_ia(self, activado: bool):
        ajustes.guardar(sin_ia=True if activado else None)

    def _on_probar_ia(self):
        from roleplay.servicios import ia

        self._on_claves()
        self.probar_btn.setEnabled(False)
        self.prueba_label.setText("Probando...")
        ejecutar_en_hilo(ia.probar, al_completar=self._on_prueba_ia, al_fallar=self._on_prueba_ia)

    def _on_prueba_ia(self, mensaje):
        self.probar_btn.setEnabled(True)
        self.prueba_label.setText(esc(str(mensaje)))

    def _on_elegir_partida(self):
        ruta, _ = QFileDialog.getOpenFileName(
            self, "Elegi tu partida de Carrera Jugador", str(lector.CARPETA_GUARDADOS), "Carrera jugador (CmPlr*)"
        )
        if ruta:
            ajustes.guardar(partida=ruta)
        self._refrescar()

    def _on_partida_reciente(self):
        ajustes.guardar(partida=None)
        self._refrescar()

    def _on_detectar(self):
        olvidar_eleccion()
        self._refrescar()

    def _on_crear_iconos(self):
        try:
            creados = crear_accesos(juego_configurado())
        except (RuntimeError, OSError) as exc:
            QMessageBox.warning(self, "No se pudieron crear los iconos", str(exc))
            return
        QMessageBox.information(
            self, "Iconos creados", "Listo, en tu escritorio:\n\n" + "\n".join(f"• {ruta.stem}" for ruta in creados)
        )

    def _on_diagnostico(self):
        from roleplay.diagnostico import como_texto, revisar

        self.diagnostico_edit.setPlainText(como_texto(revisar()))
        self.diagnostico_edit.show()
        self.copiar_btn.show()
