"""
Revision rapida de que todo este en su lugar, para cuando a alguien no le
funciona algo ("mandame el diagnostico"). No graba el microfono. Si toma una captura de prueba, pero no la guarda ni la manda a
ningun lado: solo anota su tamano.

    EAFC Roleplay.exe --diagnostico      lo escribe en diagnostico.txt y sale
"""

import sys
from datetime import datetime

from roleplay import config


def revisar() -> list[tuple[bool, str]]:
    resultados: list[tuple[bool, str]] = []

    def anotar(ok: bool, texto: str) -> None:
        resultados.append((ok, texto))

    modo = "paquete" if config.EMPAQUETADA else "codigo"
    anotar(True, f"Modo: {modo} · Python {sys.version.split()[0]} · datos en {config.CARPETA_DATOS}")

    from roleplay.servicios.narrador import CARPETA_DATOS

    corpus = sorted(r.stem for r in CARPETA_DATOS.glob("*.json"))
    anotar(len(corpus) >= 5, f"Motor narrativo local: {len(corpus)} archivos de datos ({', '.join(corpus)})")
    from roleplay.servicios import ia

    anotar(True, f"IA hibrida (opcional): {ia.estado()}")

    try:
        from roleplay.database import conectar, init_db

        init_db()
        with conectar() as conn:
            perfiles = conn.execute("SELECT COUNT(*) FROM player_profile").fetchone()[0]
            partidos = conn.execute("SELECT COUNT(*) FROM partido_entrevista").fetchone()[0]
        anotar(True, f"Base de datos: {perfiles} personajes, {partidos} partidos")
    except Exception as exc:  # noqa: BLE001
        anotar(False, f"Base de datos: ERROR {exc}")

    from roleplay.servicios.juego import juego_configurado

    juego = juego_configurado()
    anotar(juego is not None, f"Juego: {juego.describir() + ' -> ' + juego.comando if juego else 'NO ENCONTRADO (Ajustes > El juego)'}")

    try:
        from roleplay.partida.lector import carrera_actual

        carrera = carrera_actual()
        if carrera is None:
            anotar(True, "Partida de FC 26: no hay partidas de Carrera Jugador (es opcional)")
        else:
            jugador = carrera.nombre_editado(carrera.usuario_id) if carrera.usuario_id is not None else None
            anotar(
                jugador is not None,
                f"Partida de FC 26: \"{carrera.partida}\" · {len(carrera.partidos)} partidos · "
                f"jugador: {jugador or 'NO ENCONTRADO'} · club: {carrera.equipo(carrera.equipo_usuario())}",
            )
    except Exception as exc:  # noqa: BLE001
        anotar(False, f"Partida de FC 26: no se pudo leer ({exc})")

    try:
        from roleplay.servicios.audio import listar_microfonos

        microfonos = listar_microfonos()
        anotar(len(microfonos) > 1, f"Microfonos: {', '.join(m.nombre for m in microfonos[1:]) or 'ninguno'}")
    except RuntimeError as exc:
        anotar(False, f"Microfonos: {exc}")

    try:
        import dxcam

        monitores = [linea for linea in dxcam.output_info().splitlines() if linea.strip()]
        from PySide6.QtGui import QImage

        from roleplay.servicios.captura import capturar_pantalla

        prueba = QImage.fromData(capturar_pantalla())
        anotar(
            not prueba.isNull(),
            f"Captura de pantalla: {prueba.width()}x{prueba.height()} · {len(monitores)} monitor(es)",
        )
    except Exception as exc:  # noqa: BLE001
        anotar(False, f"Captura de pantalla: {exc}")

    try:  # el navegador del configurador de autos (sin el, queda el dibujo)
        from pathlib import Path

        import PySide6
        import PySide6.QtWebEngineWidgets  # noqa: F401

        proceso = Path(PySide6.__file__).parent / "QtWebEngineProcess.exe"
        recursos = Path(PySide6.__file__).parent / "resources" / "qtwebengine_resources.pak"
        anotar(proceso.exists() and recursos.exists(),
               "Navegador del configurador: " + ("listo" if proceso.exists() and recursos.exists() else
                                                  "INCOMPLETO (se ve el dibujo en lugar de la web de la marca)"))
    except ImportError as exc:
        anotar(False, f"Navegador del configurador: no esta ({exc}); se ve el dibujo en lugar de la web de la marca")

    from roleplay.ui.mando import describir_mando

    anotar(True, f"Mando para el overlay: {describir_mando()}")
    from roleplay.servicios import transcriptor

    anotar(True, f"Voz: {transcriptor.estado()}")
    return resultados


def como_texto(resultados: list[tuple[bool, str]]) -> str:
    lineas = [f"Diagnostico EAFC 26 Roleplay · {datetime.now().isoformat(timespec='seconds')}"]
    lineas += [f"[{'OK' if ok else '!!'}] {texto}" for ok, texto in resultados]
    return "\n".join(lineas)
