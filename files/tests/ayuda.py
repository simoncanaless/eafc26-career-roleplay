"""
Lo comun a todas las pruebas:

- Qt sin ventana (QT_QPA_PLATFORM=offscreen).
- Una base SQLite temporal por prueba, dentro de una carpeta de datos
  temporal: nunca se toca career_roleplay.db ni nada del proyecto.
- La memoria anti-repeticion del motor narrativo es la de cada base: cada prueba arranca de cero.
- Dialogos modales mudos (si no, cuelgan la prueba).
"""

import os
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
# Toda la bateria (y los procesos que lanza) usa una carpeta de datos propia:
# nada de lo que se pruebe escribe en la carpeta del proyecto.
os.environ["EAFC_ROLEPLAY_DATOS"] = tempfile.mkdtemp(prefix="eafc_pruebas_")
# ...y la "principal" de los perfiles de carrera (roleplay/carreras.py): carreras.json nunca va al proyecto
os.environ["EAFC_ROLEPLAY_BASE"] = os.environ["EAFC_ROLEPLAY_DATOS"]
# ...y una carpeta de guardados de FC 26 vacia: nunca se lee la partida real
os.environ["EAFC_FC26_GUARDADOS"] = tempfile.mkdtemp(prefix="eafc_guardados_")
# ...y la IA hibrida apagada: las pruebas nunca salen a internet (test_ia.py la prende con mocks)
os.environ["EAFC_SIN_IA"] = "1"
# ...y sin el catalogo de EA del PC (solo local): los nombres dependen de lo que arme cada prueba
# ...y sin los datos del ecosistema de Simon (famosas, paginas, periodistas, autos de nicho)
os.environ["EAFC_ECOSISTEMA"] = tempfile.mkdtemp(prefix="eafc_ecosistema_")
os.environ["EAFC_CATALOGO_EA"] = str(Path(tempfile.gettempdir()) / "eafc_sin_catalogo.json")
RAIZ = Path(__file__).resolve().parent.parent
if str(RAIZ) not in sys.path:
    sys.path.insert(0, str(RAIZ))

from roleplay import config, database  # noqa: E402


def qapp():
    from PySide6.QtWidgets import QApplication

    return QApplication.instance() or QApplication([])


def esperar_tareas(segundos: float = 5.0) -> None:
    """Espera a que terminen los hilos lanzados con ejecutar_en_hilo y
    entrega sus senales (completado / error) en el hilo de la interfaz."""
    from roleplay.ui.comun import tareas_vivas

    app = qapp()
    limite = time.monotonic() + segundos
    while tareas_vivas().cantidad() and time.monotonic() < limite:
        app.processEvents()
        time.sleep(0.01)
    app.processEvents()
    if tareas_vivas().cantidad():
        raise AssertionError("Quedaron hilos corriendo despues de esperar.")


def correr_aislado(codigo: str, segundos: float = 30.0) -> subprocess.CompletedProcess:
    """Corre `codigo` en otro proceso de Python (con tests/ayuda importado).
    Para escenarios que, si fallan, cierran el proceso entero: asi la
    prueba falla con un mensaje en vez de tumbar toda la bateria."""
    preambulo = f"import sys; sys.path.insert(0, {str(RAIZ / 'tests')!r}); import ayuda\n"
    return subprocess.run(
        [sys.executable, "-c", preambulo + codigo],
        cwd=RAIZ,
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=segundos,
        env={**os.environ, "PYTHONIOENCODING": "utf-8"},
    )


class PruebaConBase(unittest.TestCase):
    """Cada prueba arranca con una base vacia en una carpeta temporal."""

    def setUp(self):
        carpeta = tempfile.TemporaryDirectory()
        self.addCleanup(carpeta.cleanup)
        parche = mock.patch.object(config, "DB_PATH", Path(carpeta.name) / "prueba.db")
        parche.start()
        self.addCleanup(parche.stop)
        database.init_db()


class PruebaDeInterfaz(PruebaConBase):
    """Ademas: QApplication y dialogos mudos (quedan grabados para revisar)."""

    def setUp(self):
        super().setUp()
        qapp()
        from PySide6.QtWidgets import QMessageBox

        self.avisos = mock.MagicMock()
        for nombre in ("information", "warning"):
            parche = mock.patch.object(QMessageBox, nombre, self.avisos)
            parche.start()
            self.addCleanup(parche.stop)
        self.addCleanup(esperar_tareas)


def texto_de_noticias(noticias) -> str:
    """Todo lo que dice la prensa (titulares y cuerpos), para buscar en el."""
    return "\n".join(f"{n.titular}\n{n.cuerpo}" for n in noticias)


def texto_visible(html: str) -> str:
    """Lo que de verdad se ve de un texto con formato en un QLabel."""
    from PySide6.QtGui import QTextDocument

    documento = QTextDocument()
    documento.setHtml(html)
    return documento.toPlainText()
