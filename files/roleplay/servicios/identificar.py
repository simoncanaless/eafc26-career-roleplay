"""
Poner nombre a lo que la partida de FC 26 trae solo como numero: jugadores
(la partida no guarda los nombres de los actuales) y copas.

Los nombres salen de bases locales por id de EA, en este orden:
1. roleplay/datos/jugadores_fc26.json (a mano, scripts/nombres_faltantes.py --agregar);
2. roleplay/datos/catalogo_ea.json: el catalogo oficial de ratings de EA
   (~18.000 jugadores), que baja scripts/nombres_faltantes.py --catalogo-ea.
   Queda SOLO en el PC (.gitignore; si va en el paquete de los amigos);
3. el diccionario de ids de nombre: la partida guarda, para cada jugador
   (tambien regens y juveniles), los ids de su nombre, apellido y nombre comun
   en la tabla de nombres del juego, pero no el texto. Ese texto se aprende de
   los jugadores del catalogo que estan en la partida (el apellido de Haaland
   es el id 14348 -> 14348 = "Haaland"); un id que da dos textos distintos se
   descarta. Asi se nombra a un regen cuyos nombre y apellido ya se vieron
   (o solo por el apellido, si el nombre no).
En 1 y 2, si la fecha de nacimiento no coincide con la de la partida, es
otra persona y queda sin nombre. Lo que no esta devuelve el nombre vacio y
quien escribe la noticia describe al jugador ("el delantero del Arsenal") en
vez de inventar.
"""

import json
import os
from collections import defaultdict
from functools import lru_cache
from pathlib import Path

from roleplay.servicios.narrador import CARPETA_DATOS


def archivo_catalogo() -> Path:
    """EAFC_CATALOGO_EA lo cambia (las pruebas lo apuntan a un archivo que no existe)."""
    return Path(os.environ.get("EAFC_CATALOGO_EA") or CARPETA_DATOS / "catalogo_ea.json")


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


@lru_cache(maxsize=4)
def _catalogo(ruta: str) -> dict:
    try:
        return json.loads(Path(ruta).read_text(encoding="utf-8")).get("jugadores", {})
    except (OSError, ValueError):
        return {}


def catalogo_ea() -> dict[str, dict]:
    """{id: {"pila", "apellido", "comun", "nacimiento"}} ({} si no se bajo)."""
    return _catalogo(str(archivo_catalogo()))


def nombre_del_catalogo(entrada: dict) -> str:
    comun = (entrada.get("comun") or "").strip()
    return comun or " ".join(p for p in ((entrada.get("pila") or "").strip(), (entrada.get("apellido") or "").strip()) if p)


def _calza(nacimiento: str, ficha: dict) -> bool:
    return not (nacimiento and ficha.get("nacimiento") and nacimiento != ficha["nacimiento"])


def diccionario_de_nombres(ids_de_nombre: dict, nacimientos: dict) -> dict[int, str]:
    """{id de nombre del juego: texto}, aprendido de los jugadores de la partida
    que estan en el catalogo (con el nacimiento que calza). nacimientos: {jugador: "aaaa-mm-dd"}."""
    catalogo = catalogo_ea()
    vistos: dict[int, set] = defaultdict(set)
    for jugador, (id_nombre, id_apellido, id_comun) in ids_de_nombre.items():
        entrada = catalogo.get(str(jugador))
        if not entrada or not _calza(entrada.get("nacimiento", ""), {"nacimiento": nacimientos.get(jugador)}):
            continue
        for id_texto, texto in ((id_nombre, entrada.get("pila")), (id_apellido, entrada.get("apellido")),
                                (id_comun, entrada.get("comun"))):
            if id_texto and texto and texto.strip():
                vistos[id_texto].add(texto.strip())
    return {i: next(iter(textos)) for i, textos in vistos.items() if len(textos) == 1}  # dos textos: se descarta


def identificar_jugadores(fichas: list[dict], diccionario: dict | None = None) -> dict[int, tuple[str, bool]]:
    """fichas: Carrera.ficha(jugador) (con "ids_nombre" si la partida los trae).
    diccionario: el de diccionario_de_nombres. Devuelve {id: (nombre, seguro)}."""
    base, catalogo, diccionario = jugadores_conocidos(), catalogo_ea(), diccionario or {}
    resultado = {}
    for ficha in fichas:
        nombre, nacimiento = _nombre_de(base.get(str(ficha["id"]), ""))
        if nombre and not _calza(nacimiento, ficha):
            nombre = ""  # el id no calza con la persona: mejor vacio que equivocado
        entrada = catalogo.get(str(ficha["id"]))
        if not nombre and entrada and _calza(entrada.get("nacimiento", ""), ficha):
            nombre = nombre_del_catalogo(entrada)
        if not nombre and ficha.get("ids_nombre"):
            id_nombre, id_apellido, id_comun = ficha["ids_nombre"]
            if id_comun and id_comun in diccionario:
                nombre = diccionario[id_comun]
            elif id_nombre in diccionario and id_apellido in diccionario:
                nombre = f"{diccionario[id_nombre]} {diccionario[id_apellido]}"
            elif id_apellido in diccionario:
                nombre = diccionario[id_apellido]  # solo el apellido: lo que el juego pone en la camiseta
        resultado[ficha["id"]] = (nombre, bool(nombre))
    return resultado


def identificar_competiciones(fichas: list[dict]) -> dict[int, tuple[str, bool]]:
    """fichas: {"id", "codigo", "continental", "equipos": [...]}. Los ids de
    las copas son los mismos en todas las partidas."""
    base = _base("competiciones_fc26.json", "competiciones")
    return {f["id"]: (base.get(str(f["id"]), ""), bool(base.get(str(f["id"])))) for f in fichas}
