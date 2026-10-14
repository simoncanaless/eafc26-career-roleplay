"""
Encontrar la partida de carrera jugador mas reciente y leerla.

Se lee el archivo entero a memoria con una sola lectura y nunca se escribe:
el guardado del juego no se toca. Si el juego lo estaba escribiendo justo en
ese momento, la validacion falla y se reintenta una vez.
"""

import os
import time
from datetime import datetime
from pathlib import Path
from typing import Optional

from roleplay import ajustes
from roleplay.partida.carrera import Carrera, construir
from roleplay.partida.formato import FormatoDesconocido

# EAFC_FC26_GUARDADOS manda (las pruebas apuntan a una carpeta vacia)
CARPETA_GUARDADOS = Path(
    os.environ.get("EAFC_FC26_GUARDADOS")
    or Path(os.environ.get("LOCALAPPDATA") or Path.home() / "AppData" / "Local") / "EA SPORTS FC 26" / "settings"
)
PREFIJO_CARRERA_JUGADOR = "CmPlr"

_cache: dict = {}  # (ruta, fecha de modificacion, tamano) -> Carrera (solo la ultima)


def guardados(carpeta: Optional[Path] = None) -> list[Path]:
    """Partidas de carrera jugador, la mas reciente primero."""
    carpeta = carpeta or CARPETA_GUARDADOS
    if not carpeta.is_dir():
        return []
    archivos = [p for p in carpeta.glob(f"{PREFIJO_CARRERA_JUGADOR}*") if p.is_file()]
    return sorted(archivos, key=lambda p: p.stat().st_mtime, reverse=True)


def guardado_elegido(carpeta: Optional[Path] = None) -> Optional[Path]:
    """El que la persona eligio en Ajustes, o el mas reciente."""
    elegido = ajustes.leer().get("partida")
    if elegido and Path(elegido).is_file():
        return Path(elegido)
    lista = guardados(carpeta)
    return lista[0] if lista else None


def leer(ruta: Path) -> Carrera:
    estado = ruta.stat()
    clave = (str(ruta), estado.st_mtime, estado.st_size)
    if clave in _cache:
        return _cache[clave]
    for intento in range(2):
        try:
            datos = ruta.read_bytes()
            carrera = construir(datos, str(ruta), datetime.fromtimestamp(estado.st_mtime))
            break
        except FormatoDesconocido:
            if intento:
                raise
            time.sleep(1.0)  # quizas el juego lo estaba escribiendo
    _cache.clear()
    _cache[clave] = carrera
    return carrera


def carrera_actual(carpeta: Optional[Path] = None) -> Optional[Carrera]:
    """La carrera del guardado elegido, o None si no hay ninguno."""
    ruta = guardado_elegido(carpeta)
    return leer(ruta) if ruta else None
