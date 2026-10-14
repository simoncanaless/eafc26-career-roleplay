"""
Punto de entrada unico de EAFC 26 Career Roleplay.

    .venv\\Scripts\\python.exe app.py               menu con todos los modulos
    .venv\\Scripts\\python.exe app.py personaje     solo el asistente de personaje
    .venv\\Scripts\\python.exe app.py entrevistas   solo la sala de prensa
    .venv\\Scripts\\python.exe app.py instagram     solo Instagram

Con doble click se abre desde "EAFC Roleplay.exe" (o el acceso directo del
escritorio), que corre esto mismo sin ventana de consola.
"""

import argparse
import sys
import traceback
from datetime import datetime
from pathlib import Path

MODULOS = ["menu", "personaje", "entrevistas", "instagram"]
RAIZ = Path(__file__).resolve().parent
ICONO_APP = RAIZ / "roleplay" / "ui" / "iconos" / "app.ico"
REGISTRO_ERRORES = RAIZ / "errores.log"


def _avisar_error(tipo, valor, rastro) -> None:
    """Abierta con doble click no hay consola: un error sin atrapar no se
    veria en ningun lado. Se anota en errores.log y se muestra."""
    detalle = "".join(traceback.format_exception(tipo, valor, rastro))
    try:
        with REGISTRO_ERRORES.open("a", encoding="utf-8") as registro:
            registro.write(f"\n--- {datetime.now().isoformat(timespec='seconds')} ---\n{detalle}")
    except OSError:
        pass
    sys.__excepthook__(tipo, valor, rastro)

    from PySide6.QtWidgets import QApplication, QMessageBox

    if QApplication.instance() is not None:
        QMessageBox.critical(
            None,
            "Algo fallo",
            f"{valor}\n\nEl detalle quedo en {REGISTRO_ERRORES.name}, en la carpeta del proyecto.",
        )


def _identificar_en_windows() -> None:
    """Sin esto, Windows agrupa la ventana con python.exe y la barra de
    tareas muestra el icono de Python en vez del de la app."""
    if sys.platform == "win32":
        import ctypes

        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("EAFC26.CareerRoleplay")


def _crear_ventana(modulo: str):
    if modulo == "personaje":
        from roleplay.ui.personaje import CharacterWizard

        return CharacterWizard()

    if modulo in ("entrevistas", "instagram"):
        from roleplay.ui.comun import con_scroll
        from roleplay.ui.componentes import FondoEstadio

        if modulo == "entrevistas":
            from roleplay.ui.entrevista import InterviewWindow as Pagina
        else:
            from roleplay.ui.instagram import InstagramWindow as Pagina
        pagina = Pagina()
        ventana = FondoEstadio()
        from PySide6.QtWidgets import QVBoxLayout

        layout = QVBoxLayout(ventana)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(con_scroll(pagina))
        ventana.setWindowTitle(pagina.windowTitle())
        ventana.resize(1000, 820)
        return ventana

    from roleplay.ui.menu import MainMenuWindow

    return MainMenuWindow()


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="EAFC 26 Career Roleplay")
    parser.add_argument("modulo", nargs="?", default="menu", choices=MODULOS)
    args = parser.parse_args(argv)

    sys.excepthook = _avisar_error
    _identificar_en_windows()

    from PySide6.QtGui import QIcon
    from PySide6.QtWidgets import QApplication

    from roleplay.database import init_db
    from roleplay.ui.estilos import aplicar_estilo

    init_db()
    app = QApplication(sys.argv[:1])
    app.setApplicationName("EAFC 26 Roleplay")
    if ICONO_APP.exists():
        app.setWindowIcon(QIcon(str(ICONO_APP)))
    aplicar_estilo(app)
    ventana = _crear_ventana(args.modulo)
    ventana.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
