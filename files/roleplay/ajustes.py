"""Ajustes de cada persona (ej. como abrir el juego), en ajustes.json de
su carpeta de datos. Leer nunca falla: un archivo roto o ausente es {}."""

import json

from roleplay import config


def leer() -> dict:
    try:
        return json.loads(config.ARCHIVO_AJUSTES.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def guardar(**cambios) -> dict:
    """Mezcla `cambios` con lo guardado. Un valor None borra la clave."""
    actuales = leer()
    for clave, valor in cambios.items():
        if valor is None:
            actuales.pop(clave, None)
        else:
            actuales[clave] = valor
    config.ARCHIVO_AJUSTES.write_text(json.dumps(actuales, ensure_ascii=False, indent=2), encoding="utf-8")
    return actuales
