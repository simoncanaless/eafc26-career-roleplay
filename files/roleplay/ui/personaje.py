"""
Asistente de creacion de personaje (quiz inicial).

Guia por unas paginas de preguntas, arma un PlayerProfile, genera el
backstory (servicios/backstory.py, editable antes de guardar) y lo guarda en SQLite.
"""

from PySide6.QtCore import QDate, Qt
from PySide6.QtWidgets import (
    QButtonGroup,
    QDateEdit,
    QLabel,
    QLineEdit,
    QMessageBox,
    QRadioButton,
    QTextEdit,
    QVBoxLayout,
    QWizard,
    QWizardPage,
)

from roleplay.database import save_profile
from roleplay.models import (
    CONTEXTOS_SOCIOECONOMICOS,
    ESTADOS_RELACION,
    MOTIVACIONES,
    PERSONALIDADES,
    PlayerProfile,
)
from roleplay.servicios.backstory import generar_backstory
from roleplay.ui import estilos
from roleplay.ui.comun import ejecutar_en_hilo, esc
from roleplay.ui.componentes import boton


class PaginaDatosBasicos(QWizardPage):
    def __init__(self):
        super().__init__()
        self.setTitle("Datos basicos")
        self.setSubTitle("Empecemos por lo esencial de tu jugador.")

        layout = QVBoxLayout()
        layout.addWidget(QLabel("Nombre del jugador:"))
        self.nombre_edit = QLineEdit()
        self.nombre_edit.setPlaceholderText("Ej: Simon Rojas")
        self.nombre_edit.textChanged.connect(self.completeChanged)
        layout.addWidget(self.nombre_edit)

        layout.addWidget(QLabel("Fecha de nacimiento:"))
        self.fecha_edit = QDateEdit()
        self.fecha_edit.setCalendarPopup(True)
        self.fecha_edit.setDisplayFormat("yyyy-MM-dd")
        self.fecha_edit.setDate(QDate(2005, 1, 1))
        layout.addWidget(self.fecha_edit)

        self.setLayout(layout)

    def isComplete(self) -> bool:
        return bool(self.nombre_edit.text().strip())


class PaginaOrigen(QWizardPage):
    def __init__(self):
        super().__init__()
        self.setTitle("Origen")
        self.setSubTitle("De donde venis?")

        layout = QVBoxLayout()
        layout.addWidget(QLabel("Pais de origen de tus padres:"))
        self.pais_edit = QLineEdit()
        self.pais_edit.setPlaceholderText("Ej: Chile")
        layout.addWidget(self.pais_edit)

        layout.addWidget(QLabel("Ciudad natal:"))
        self.ciudad_edit = QLineEdit()
        self.ciudad_edit.setPlaceholderText("Ej: Quillota")
        layout.addWidget(self.ciudad_edit)

        self.setLayout(layout)


class RadioPage(QWizardPage):
    """Pagina de opcion unica sobre un catalogo {clave: descripcion}."""

    def __init__(self, titulo: str, subtitulo: str, opciones: dict[str, str]):
        super().__init__()
        self.setTitle(titulo)
        self.setSubTitle(subtitulo)
        self._claves = list(opciones)

        self.layout_pagina = QVBoxLayout()
        self.grupo = QButtonGroup(self)
        for i, descripcion in enumerate(opciones.values()):
            radio = QRadioButton(descripcion)
            radio.setChecked(i == 0)
            self.grupo.addButton(radio, i)
            self.layout_pagina.addWidget(radio)
        self.setLayout(self.layout_pagina)

    def seleccion(self) -> str:
        indice = self.grupo.checkedId()
        return self._claves[indice] if indice >= 0 else self._claves[0]


class PaginaRelacion(RadioPage):
    def __init__(self):
        super().__init__(
            "Vida sentimental", "Cual es tu situacion sentimental inicial?", ESTADOS_RELACION
        )
        self.layout_pagina.addWidget(QLabel("Nombre de tu pareja:"))
        self.nombre_pareja_edit = QLineEdit()
        self.layout_pagina.addWidget(self.nombre_pareja_edit)

        self.grupo.idToggled.connect(self._actualizar_pareja)
        self._actualizar_pareja()

    def _actualizar_pareja(self, *_):
        # el nombre solo tiene sentido con "novia real"
        self.nombre_pareja_edit.setEnabled(self.seleccion() == "novia_real")

    def nombre_pareja(self) -> str:
        if self.seleccion() != "novia_real":
            return ""
        return self.nombre_pareja_edit.text().strip()


class PaginaAnecdota(QWizardPage):
    def __init__(self):
        super().__init__()
        self.setTitle("Un dato extra")
        self.setSubTitle("Contanos algo (opcional) que le de sabor a tu historia.")
        layout = QVBoxLayout()
        self.texto_edit = QTextEdit()
        self.texto_edit.setPlaceholderText(
            "Ej: jugaba de arquero improvisado en la calle, "
            "casi deja el futbol por una lesion a los 15, etc."
        )
        layout.addWidget(self.texto_edit)
        self.setLayout(layout)


class PaginaBackstory(QWizardPage):
    def __init__(self):
        super().__init__()
        self.setTitle("Backstory")
        self.setSubTitle(
            "Revisa tus respuestas y genera la historia inicial de tu jugador "
            "(o escribila vos)."
        )

        layout = QVBoxLayout()
        self.resumen_label = QLabel()
        self.resumen_label.setWordWrap(True)
        layout.addWidget(self.resumen_label)

        self.generar_btn = boton("Generar backstory", primario=True, icono_nombre="chispa")
        self.generar_btn.clicked.connect(self._on_generar_clicked)
        layout.addWidget(self.generar_btn)

        layout.addWidget(QLabel("Backstory (podes editarlo o borrar lo que no te guste):"))
        self.resultado_edit = QTextEdit()
        self.resultado_edit.setPlaceholderText("Aca va a aparecer el backstory generado...")
        self.resultado_edit.textChanged.connect(self.completeChanged)
        layout.addWidget(self.resultado_edit)

        layout.addWidget(QLabel("Ganchos narrativos (uno por linea, podes editar o borrar):"))
        self.ganchos_edit = QTextEdit()
        self.ganchos_edit.setPlaceholderText("Aca van a aparecer los ganchos narrativos...")
        self.ganchos_edit.setMaximumHeight(120)
        layout.addWidget(self.ganchos_edit)

        self.setLayout(layout)

    def initializePage(self):
        perfil = self.wizard().construir_perfil()
        self.resumen_label.setText(
            f"<b>{esc(perfil.nombre_jugador)}</b> · {perfil.fecha_nacimiento}<br>"
            f"Padres de {esc(perfil.pais_padres)} · nacido en {esc(perfil.ciudad_natal)}<br>"
            f"Contexto: {CONTEXTOS_SOCIOECONOMICOS.get(perfil.contexto_socioeconomico)}<br>"
            f"Personalidad: {PERSONALIDADES.get(perfil.personalidad)}<br>"
            f"Motivacion: {MOTIVACIONES.get(perfil.motivacion)}<br>"
            f"Relacion: {ESTADOS_RELACION.get(perfil.estado_relacion)}<br>"
            f"Reputacion inicial estimada: {perfil.calcular_reputacion_inicial()}/100"
        )

    def _on_generar_clicked(self):
        self.generar_btn.setEnabled(False)
        self.generar_btn.setText("GENERANDO...")
        ejecutar_en_hilo(
            generar_backstory,
            self.wizard().construir_perfil(),
            al_completar=self._on_completado,
            al_fallar=self._on_error,
        )

    def _on_completado(self, resultado):
        self.resultado_edit.setPlainText(resultado.backstory)
        self.ganchos_edit.setPlainText("\n".join(f"- {g}" for g in resultado.ganchos_narrativos))
        self.generar_btn.setEnabled(True)
        self.generar_btn.setText("REGENERAR BACKSTORY")

    def _on_error(self, mensaje: str):
        QMessageBox.warning(self, "Error al generar backstory", mensaje)
        self.generar_btn.setEnabled(True)
        self.generar_btn.setText("GENERAR BACKSTORY")

    def isComplete(self) -> bool:
        # Basta con que haya un backstory, generado o escrito a mano: asi
        # se puede crear el personaje sin generarlo.
        return bool(self.backstory())

    def backstory(self) -> str:
        return self.resultado_edit.toPlainText().strip()

    def ganchos(self) -> list[str]:
        lineas = (linea.strip().lstrip("-").strip() for linea in self.ganchos_edit.toPlainText().splitlines())
        return [linea for linea in lineas if linea]


class CharacterWizard(QWizard):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("EAFC 26 Roleplay - Creacion de personaje")
        self.setMinimumSize(680, 600)
        # Classic: el estilo por defecto en Windows (Aero) pinta zonas
        # blancas que no respetan la paleta oscura.
        self.setWizardStyle(QWizard.WizardStyle.ClassicStyle)
        for tipo, texto in (
            (QWizard.WizardButton.BackButton, "ATRAS"),
            (QWizard.WizardButton.NextButton, "SIGUIENTE"),
            (QWizard.WizardButton.FinishButton, "CREAR JUGADOR"),
            (QWizard.WizardButton.CancelButton, "CANCELAR"),
        ):
            self.setButtonText(tipo, texto)

        self.pagina_basicos = PaginaDatosBasicos()
        self.pagina_origen = PaginaOrigen()
        self.pagina_contexto = RadioPage(
            "Contexto socioeconomico", "Como fue tu crianza?", CONTEXTOS_SOCIOECONOMICOS
        )
        self.pagina_personalidad = RadioPage(
            "Personalidad publica", "Como te mostras ante la prensa y los hinchas?", PERSONALIDADES
        )
        self.pagina_motivacion = RadioPage("Motivacion", "Que te mueve a triunfar?", MOTIVACIONES)
        self.pagina_relacion = PaginaRelacion()
        self.pagina_anecdota = PaginaAnecdota()
        self.pagina_backstory = PaginaBackstory()

        paginas = (
            self.pagina_basicos,
            self.pagina_origen,
            self.pagina_contexto,
            self.pagina_personalidad,
            self.pagina_motivacion,
            self.pagina_relacion,
            self.pagina_anecdota,
            self.pagina_backstory,
        )
        self.setTitleFormat(Qt.TextFormat.RichText)
        self.setSubTitleFormat(Qt.TextFormat.RichText)
        for numero, pagina in enumerate(paginas, start=1):
            pagina.setTitle(
                f"<span style=\"font-family:'{estilos.FUENTE_TITULOS}'; font-size:30px\">"
                f"{esc(pagina.title().upper())}</span>"
            )
            pagina.setSubTitle(
                f"<span style=\"color:{estilos.ACENTO}; font-family:'{estilos.FUENTE_TITULOS}'; "
                f"font-size:15px\">PASO {numero}/{len(paginas)}</span>&nbsp;&nbsp;"
                f"<span style=\"color:{estilos.TEXTO_SUAVE}\">{esc(pagina.subTitle())}</span>"
            )
            self.addPage(pagina)

        self.profile_id = None  # queda con el id guardado si se acepta

    def construir_perfil(self) -> PlayerProfile:
        perfil = PlayerProfile(
            nombre_jugador=self.pagina_basicos.nombre_edit.text().strip(),
            fecha_nacimiento=self.pagina_basicos.fecha_edit.date().toString("yyyy-MM-dd"),
            pais_padres=self.pagina_origen.pais_edit.text().strip(),
            ciudad_natal=self.pagina_origen.ciudad_edit.text().strip(),
            contexto_socioeconomico=self.pagina_contexto.seleccion(),
            personalidad=self.pagina_personalidad.seleccion(),
            motivacion=self.pagina_motivacion.seleccion(),
            estado_relacion=self.pagina_relacion.seleccion(),
            nombre_pareja=self.pagina_relacion.nombre_pareja(),
            anecdota_personal=self.pagina_anecdota.texto_edit.toPlainText().strip(),
        )
        perfil.reputacion_inicial = perfil.calcular_reputacion_inicial()
        return perfil

    def accept(self):
        perfil = self.construir_perfil()
        perfil.backstory_generado = self.pagina_backstory.backstory()
        perfil.ganchos_narrativos = self.pagina_backstory.ganchos()
        self.profile_id = save_profile(perfil)
        QMessageBox.information(
            self,
            "Personaje guardado",
            f"{perfil.nombre_jugador} ya esta listo. Ahora podes ir a Entrevistas o a Instagram.",
        )
        super().accept()
