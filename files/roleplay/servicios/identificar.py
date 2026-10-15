"""
Poner nombre a lo que la partida de FC 26 trae solo como numero: jugadores
(la partida no guarda los nombres de los actuales) y copas.

Sin IA: los nombres salen de una base local por id de EA
(roleplay/datos/jugadores_fc26.json y competiciones_fc26.json). Si la base
trae la fecha de nacimiento y no coincide con la de la partida, no se da por
seguro. Lo que no esta devuelve el nombre vacio y quien escribe la noticia
describe al jugador ("el delantero del Arsenal") en vez de inventar.
"""

import json
from functools import lru_cache

from roleplay.servicios.narrador import CARPETA_DATOS


@lru_cache(maxsize=None)
def _base(archivo: str, clave: str) -> dict:
    ruta = CARPETA_DATOS / archivo
    if not ruta.exists():
        return {}
    return json.loads(ruta.read_text(encoding="utf-8")).get(clave, {})


def jugadores_conocidos() -> dict[str, object]:
    return _base("jugadores_fc26.json", "jugadores")


def _nombre_de(entrada) -> tuple[str, str]:
    """(nombre, nacimiento) de una entrada: "Nombre" o {"nombre", "nacimiento"}."""
    if isinstance(entrada, dict):
        return entrada.get("nombre", ""), entrada.get("nacimiento", "")
    return str(entrada), ""


def identificar_jugadores(fichas: list[dict]) -> dict[int, tuple[str, bool]]:
    """fichas: Carrera.ficha(jugador). Devuelve {id: (nombre, seguro)}."""
    base = jugadores_conocidos()
    resultado = {}
    for ficha in fichas:
        nombre, nacimiento = _nombre_de(base.get(str(ficha["id"]), ""))
        if nombre and nacimiento and ficha.get("nacimiento") and nacimiento != ficha["nacimiento"]:
            nombre = ""  # el id no calza con la persona: mejor vacio que equivocado
        resultado[ficha["id"]] = (nombre, bool(nombre))
    return resultado


def identificar_competiciones(fichas: list[dict]) -> dict[int, tuple[str, bool]]:
    """fichas: {"id", "codigo", "continental", "equipos": [...]}. Los ids de
    las copas son los mismos en todas las partidas."""
    base = _base("competiciones_fc26.json", "competiciones")
    return {f["id"]: (base.get(str(f["id"]), ""), bool(base.get(str(f["id"])))) for f in fichas}
