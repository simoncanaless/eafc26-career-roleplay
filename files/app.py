"""
Punto de entrada unico de EAFC 26 Career Roleplay.

    .venv\\Scripts\\python.exe app.py               menu con todos los modulos
    .venv\\Scripts\\python.exe app.py personaje     solo el asistente de personaje
    .venv\\Scripts\\python.exe app.py entrevistas   solo entrevistas post-partido
    .venv\\Scripts\\python.exe app.py instagram     solo Instagram
"""

import argparse
import sys

MODULOS = ["menu", "personaje", "entrevistas", "instagram"]


def _crear_ventana(modulo: str):
    if modulo == "personaje":
        from roleplay.ui.personaje import CharacterWizard

        return CharacterWizard()

    if modulo in ("entrevistas", "instagram"):
        from roleplay.ui.comun import con_scroll

        if modulo == "entrevistas":
            from roleplay.ui.entrevista import InterviewWindow as Pagina
        else:
            from roleplay.ui.instagram import InstagramWindow as Pagina
        pagina = Pagina()
        ventana = con_scroll(pagina)
        ventana.setWindowTitle(pagina.windowTitle())
        ventana.resize(640, 760)
        return ventana

    from roleplay.ui.menu import MainMenuWindow

    return MainMenuWindow()


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="EAFC 26 Career Roleplay")
    parser.add_argument("modulo", nargs="?", default="menu", choices=MODULOS)
    args = parser.parse_args(argv)

    from PySide6.QtWidgets import QApplication

    from roleplay.database import init_db
    from roleplay.ui.estilos import aplicar_estilo

    init_db()
    app = QApplication(sys.argv[:1])
    aplicar_estilo(app)
    ventana = _crear_ventana(args.modulo)
    ventana.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
