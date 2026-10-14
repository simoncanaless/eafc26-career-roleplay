"""
Bienvenida (clave de Gemini) y Ajustes: la clave, como se abre el juego,
los dos iconos del escritorio y el diagnostico.
"""

import os

from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QDesktopServices, QGuiApplication
from PySide6.QtWidgets import (
    QDialog,
    QFileDialog,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPlainTextEdit,
    QVBoxLayout,
    QWidget,
)

from roleplay import ajustes
from roleplay.gemini import get_gemini_api_keys, guardar_clave, probar_clave, usa_lista_de_claves
from roleplay.servicios.accesos import crear_accesos
from roleplay.servicios.juego import abrir_juego, elegir_a_mano, juego_configurado, olvidar_eleccion
from roleplay.ui import estilos
from roleplay.ui.comun import ejecutar_en_hilo, esc
from roleplay.ui.componentes import Tarjeta, boton, fila, texto_suave, titulo_pagina

URL_AI_STUDIO = "https://aistudio.google.com/apikey"
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


class DialogoClave(QDialog):
    """Pide la clave de Gemini, la prueba y la guarda. Con `bienvenida`
    es la pantalla del primer arranque y deja seguir sin IA."""

    def __init__(self, padre: QWidget | None = None, bienvenida: bool = False):
        super().__init__(padre)
        self.setWindowTitle("EAFC 26 Roleplay - Clave de Gemini")
        self.setMinimumWidth(620)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(30, 28, 30, 24)
        layout.setSpacing(14)
        layout.addWidget(titulo_pagina("Bienvenido" if bienvenida else "Clave de Gemini"))
        layout.addWidget(
            texto_suave(
                "La IA del roleplay (entrevistas, prensa, Instagram, leer las stats) usa "
                "Gemini de Google. Cada uno usa su propia clave: es gratis y se saca en un minuto."
            )
        )
        pasos = QLabel(
            f"<span style='color:{estilos.ACENTO}'><b>1.</b></span> Abri AI Studio con tu cuenta de Google.<br>"
            f"<span style='color:{estilos.ACENTO}'><b>2.</b></span> Apreta <b>Create API key</b> y copiala.<br>"
            f"<span style='color:{estilos.ACENTO}'><b>3.</b></span> Pegala aca abajo."
        )
        layout.addWidget(pasos)
        abrir = boton("Abrir AI Studio")
        abrir.clicked.connect(lambda: QDesktopServices.openUrl(QUrl(URL_AI_STUDIO)))
        layout.addLayout(fila(abrir, None))

        self.clave_edit = QLineEdit()
        self.clave_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self.clave_edit.setPlaceholderText("Pega tu clave (empieza con AIza...)")
        layout.addWidget(self.clave_edit)

        self.estado_label = QLabel()
        self.estado_label.setWordWrap(True)
        layout.addWidget(self.estado_label)

        self.guardar_btn = boton("Probar y guardar", primario=True)
        self.guardar_btn.clicked.connect(self._on_guardar)
        self.cancelar_btn = boton("Seguir sin IA" if bienvenida else "Cancelar")
        self.cancelar_btn.clicked.connect(self.reject)
        layout.addLayout(fila(None, self.cancelar_btn, self.guardar_btn))

        if usa_lista_de_claves():
            self.clave_edit.setEnabled(False)
            self.guardar_btn.setEnabled(False)
            self._estado("Tu .env usa una lista de claves (GEMINI_API_KEYS): cambialas ahi.", estilos.MIXTO)

    def _estado(self, texto: str, color: str) -> None:
        self.estado_label.setText(f"<span style='color:{color}'>{esc(texto)}</span>")

    def _on_guardar(self):
        clave = self.clave_edit.text().strip()
        if not clave:
            self._estado("Pega la clave primero.", estilos.MIXTO)
            return
        self.guardar_btn.setEnabled(False)
        self._estado("Probando la clave...", estilos.TEXTO_SUAVE)
        ejecutar_en_hilo(probar_clave, clave, al_completar=self._on_clave_ok, al_fallar=self._on_clave_mala)

    def _on_clave_ok(self, _):
        guardar_clave(self.clave_edit.text())
        self.accept()

    def _on_clave_mala(self, mensaje: str):
        self.guardar_btn.setEnabled(True)
        self._estado(mensaje, estilos.NEGATIVO)


def pedir_clave_si_falta() -> None:
    """Primer arranque: si no hay clave y la persona no eligio seguir sin
    IA, se le muestra la bienvenida."""
    if get_gemini_api_keys() or ajustes.leer().get("sin_ia"):
        return
    if DialogoClave(bienvenida=True).exec() != QDialog.DialogCode.Accepted:
        ajustes.guardar(sin_ia=True)  # no volver a preguntar; queda en Ajustes


class DialogoAjustes(QDialog):
    def __init__(self, padre: QWidget | None = None):
        super().__init__(padre)
        self.setWindowTitle("EAFC 26 Roleplay - Ajustes")
        self.setMinimumWidth(680)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(30, 28, 30, 24)
        layout.setSpacing(14)
        layout.addWidget(titulo_pagina("Ajustes"))

        clave = Tarjeta("Clave de Gemini")
        self.clave_label = texto_suave(ajustar=False)
        cambiar = boton("Cambiar clave")
        cambiar.clicked.connect(self._on_cambiar_clave)
        clave.cuerpo.addLayout(fila(self.clave_label, None, cambiar))
        layout.addWidget(clave)

        juego = Tarjeta("El juego")
        self.juego_label = texto_suave()
        elegir = boton("Elegir a mano...")
        elegir.clicked.connect(self._on_elegir_juego)
        detectar = boton("Detectar de nuevo")
        detectar.clicked.connect(self._on_detectar)
        juego.cuerpo.addWidget(self.juego_label)
        juego.cuerpo.addLayout(fila(None, detectar, elegir))
        layout.addWidget(juego)

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
        claves = get_gemini_api_keys()
        if claves:
            self.clave_label.setText(f"Configurada (termina en …{esc(claves[0][-4:])}).")
        else:
            self.clave_label.setText("Sin clave: la IA no funciona hasta que pongas una.")
        juego = juego_configurado()
        self.juego_label.setText(
            f"<b>{esc(juego.describir())}</b><br>{esc(juego.comando)}" if juego
            else "No encontre EA FC 26 en Steam, la EA app ni Epic. Elegilo a mano."
        )

    def _on_cambiar_clave(self):
        if DialogoClave(self).exec() == QDialog.DialogCode.Accepted:
            ajustes.guardar(sin_ia=None)
        self._refrescar()

    def _on_elegir_juego(self):
        try:
            elegir_juego_a_mano(self)
        except ValueError as exc:
            QMessageBox.warning(self, "No se pudo elegir", str(exc))
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
