"""
Punto de entrada unico de EAFC 26 Career Roleplay.

    .venv\\Scripts\\python.exe app.py               menu con todos los modulos
    .venv\\Scripts\\python.exe app.py personaje     solo el asistente de personaje
    .venv\\Scripts\\python.exe app.py entrevistas   solo la sala de prensa
    .venv\\Scripts\\python.exe app.py instagram     solo Instagram
    .venv\\Scripts\\python.exe app.py --jugar       abre EA FC 26 y la app en la sala de prensa
    .venv\\Scripts\\python.exe app.py --diagnostico revisa que todo este en su lugar y sale

Con doble click se abre desde "EAFC Roleplay.exe" o los iconos del
escritorio ("EA FC 26 + Roleplay" es esta app con --jugar).
"""

import argparse
import sys
import traceback
from datetime import datetime

from roleplay import config

MODULOS = ["menu", "personaje", "entrevistas", "instagram"]


def _avisar_error(tipo, valor, rastro) -> None:
    """Abierta con doble click no hay consola: un error sin atrapar no se
    veria en ningun lado. Se anota en errores.log y se muestra."""
    detalle = "".join(traceback.format_exception(tipo, valor, rastro))
    try:
        with config.REGISTRO_ERRORES.open("a", encoding="utf-8") as registro:
            registro.write(f"\n--- {datetime.now().isoformat(timespec='seconds')} ---\n{detalle}")
    except OSError:
        pass
    if sys.stderr is not None:
        sys.__excepthook__(tipo, valor, rastro)

    from PySide6.QtWidgets import QApplication, QMessageBox

    if QApplication.instance() is not None:
        QMessageBox.critical(
            None,
            "Algo fallo",
            f"{valor}\n\nEl detalle quedo en {config.REGISTRO_ERRORES}.",
        )


def _identificar_en_windows() -> None:
    """Sin esto, Windows agrupa la ventana con python.exe y la barra de
    tareas muestra el icono de Python en vez del de la app."""
    if sys.platform == "win32":
        import ctypes

        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("EAFC26.CareerRoleplay")


def _crear_ventana(modulo: str, jugar: bool = False):
    if modulo == "personaje":
        from roleplay.ui.personaje import CharacterWizard

        return CharacterWizard()

    if modulo in ("entrevistas", "instagram"):
        from PySide6.QtWidgets import QVBoxLayout

        from roleplay.ui.comun import con_scroll
        from roleplay.ui.componentes import FondoEstadio

        if modulo == "entrevistas":
            from roleplay.ui.entrevista import InterviewWindow as Pagina
        else:
            from roleplay.ui.instagram import InstagramWindow as Pagina
        pagina = Pagina()
        ventana = FondoEstadio()
        layout = QVBoxLayout(ventana)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(con_scroll(pagina))
        ventana.setWindowTitle(pagina.windowTitle())
        ventana.resize(1000, 820)
        return ventana

    from roleplay.ui.menu import MainMenuWindow

    # jugando, lo que se usa es la sala de prensa al terminar cada partido
    return MainMenuWindow(MainMenuWindow.PAGINA_ENTREVISTAS if jugar else MainMenuWindow.PAGINA_RESUMEN)


def _diagnostico() -> int:
    from roleplay.diagnostico import como_texto, revisar

    resultados = revisar()
    texto = como_texto(resultados)
    (config.CARPETA_DATOS / "diagnostico.txt").write_text(texto + "\n", encoding="utf-8")
    if sys.stdout is not None:
        print(texto)
    return 0 if all(ok for ok, _ in resultados) else 1


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="EAFC 26 Career Roleplay")
    parser.add_argument("modulo", nargs="?", default="menu", choices=MODULOS)
    parser.add_argument("--jugar", action="store_true", help="abre EA FC 26 (sin modificarlo) y la app")
    parser.add_argument("--diagnostico", action="store_true", help="revisa la instalacion y sale")
    args = parser.parse_args(argv)

    sys.excepthook = _avisar_error
    if args.diagnostico:
        return _diagnostico()
    _identificar_en_windows()

    from PySide6.QtCore import Qt
    from PySide6.QtGui import QIcon
    from PySide6.QtWidgets import QApplication

    from roleplay.database import init_db
    from roleplay.ui.ajustes import abrir_juego_o_preguntar
    from roleplay.ui.estilos import aplicar_estilo

    init_db()
    # el navegador del configurador (QtWebEngine) lo necesita antes de crear la
    # aplicacion; QtWebEngine en si se importa recien al abrir el configurador
    QApplication.setAttribute(Qt.ApplicationAttribute.AA_ShareOpenGLContexts)
    app = QApplication(sys.argv[:1])
    app.setApplicationName("EAFC 26 Roleplay")
    if config.ICONO_APP.exists():
        app.setWindowIcon(QIcon(str(config.ICONO_APP)))
    aplicar_estilo(app)

    if args.jugar:
        abrir_juego_o_preguntar(None)  # primero el juego: Steam tarda en levantarlo

    ventana = _crear_ventana(args.modulo, jugar=args.jugar)
    ventana.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
