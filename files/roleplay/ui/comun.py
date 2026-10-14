"""
Piezas que comparten todas las pantallas: correr la IA en un hilo, dar
formato a numeros y textos, y envolver una pagina en un scroll.
"""

import html
from typing import Any, Callable

from PySide6.QtCore import QObject, Qt, QThread, Signal, Slot
from PySide6.QtWidgets import QFrame, QScrollArea, QWidget


class Tarea(QThread):
    """Corre una funcion fuera del hilo de la interfaz. Emite `completado`
    con lo que devuelve o `error` con el mensaje de la excepcion."""

    completado = Signal(object)
    error = Signal(str)

    def __init__(self, funcion: Callable[..., Any], *args, **kwargs):
        super().__init__()
        self._funcion = funcion
        self._args = args
        self._kwargs = kwargs

    def run(self):
        try:
            resultado = self._funcion(*self._args, **self._kwargs)
        except Exception as exc:  # noqa: BLE001 - se le muestra al usuario
            self.error.emit(str(exc))
        else:
            self.completado.emit(resultado)


class _TareasVivas(QObject):
    """Guarda cada Tarea hasta que termina.

    Si la ventana que la lanzo se cierra antes (ej. cancelar el asistente
    mientras Gemini escribe el backstory), nadie mas tiene una referencia
    al QThread, Python lo destruye corriendo y Qt cierra la app entera
    ("QThread: Destroyed while thread is still running"). Con este
    registro el hilo termina tranquilo; la ventana ya cerrada simplemente
    no recibe el resultado (PySide desconecta sus metodos al destruirla).
    """

    def __init__(self):
        super().__init__()
        self._tareas: set[Tarea] = set()

    def agregar(self, tarea: Tarea) -> None:
        self._tareas.add(tarea)
        tarea.finished.connect(self._al_terminar)

    @Slot()
    def _al_terminar(self):
        tarea = self.sender()
        # `finished` se emite justo ANTES de que el hilo termine del todo.
        tarea.wait()
        self._tareas.discard(tarea)

    def cantidad(self) -> int:
        return len(self._tareas)


_registro: _TareasVivas | None = None


def tareas_vivas() -> _TareasVivas:
    global _registro
    if _registro is None:
        _registro = _TareasVivas()
    return _registro


def ejecutar_en_hilo(
    funcion: Callable[..., Any],
    *args,
    al_completar: Callable[[Any], None],
    al_fallar: Callable[[str], None],
    **kwargs,
) -> Tarea:
    """Corre `funcion(*args, **kwargs)` en otro hilo y llama, ya de vuelta
    en el hilo de la interfaz, a `al_completar(resultado)` o a
    `al_fallar(mensaje)`.

    Pasar metodos de la ventana (no lambdas): si la ventana se destruye
    antes de que termine, PySide desconecta sus metodos solo."""
    tarea = Tarea(funcion, *args, **kwargs)
    tarea.completado.connect(al_completar)
    tarea.error.connect(al_fallar)
    tareas_vivas().agregar(tarea)
    tarea.start()
    return tarea


def miles(numero: int) -> str:
    """1234567 -> '1.234.567'."""
    return f"{numero:,}".replace(",", ".")


def esc(texto: Any) -> str:
    """Escapa un texto para meterlo en un QLabel con formato. Sin esto,
    un comentario como 'te amo crack <3 vamos' se ve 'te amo crack ':
    Qt toma el '<' como el comienzo de una etiqueta y se come el resto."""
    return html.escape(str(texto), quote=False)


def fecha_corta(fecha_iso: str) -> str:
    """'2026-08-07T23:13:02.83' -> '2026-08-07 23:13'."""
    return fecha_iso[:16].replace("T", " ")


def con_scroll(pagina: QWidget) -> QScrollArea:
    """Envuelve una pagina en un scroll vertical, para que crezca (ej. con
    las preguntas de la entrevista) sin cortarse ni agrandar la ventana.
    Todo queda transparente: el fondo lo pinta quien la contiene."""
    area = QScrollArea()
    area.setWidgetResizable(True)
    area.setFrameShape(QFrame.Shape.NoFrame)
    area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
    area.setWidget(pagina)
    # setWidget le activa el relleno a la pagina: se apaga para que se vea
    # el fondo de estadio de atras
    pagina.setObjectName("pagina")
    pagina.setAutoFillBackground(False)
    area.viewport().setAutoFillBackground(False)
    return area
