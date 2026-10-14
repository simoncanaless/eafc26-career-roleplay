"""
Poner nombre a lo que la partida de FC 26 trae solo como numero: jugadores
(la partida no guarda los nombres de los actuales) y copas.

La partida si trae de cada jugador su club, posicion, seleccion y fecha de
nacimiento: con eso la IA lo reconoce ("Manchester City, delantero centro,
Noruega, 2000-07-21" -> Erling Haaland). Si no esta segura, devuelve el
nombre vacio y quien escribe la noticia lo describe en vez de inventar.
Lo reconocido se guarda (database.nombre_conocido): se pregunta una vez.
"""

import json
from typing import Optional

from pydantic import BaseModel

from roleplay.gemini import generar_json

MAXIMO_POR_CONSULTA = 25


class Identificado(BaseModel):
    id: int
    nombre: str
    seguro: bool


class Identificaciones(BaseModel):
    identificados: list[Identificado]


def _consultar(prompt: str, api_key: Optional[str]) -> dict[int, tuple[str, bool]]:
    respuesta = generar_json(
        prompt, Identificaciones, "No se pudieron reconocer los nombres esta vez.", api_key=api_key
    )
    return {i.id: (i.nombre.strip() if i.seguro else "", i.seguro) for i in respuesta.identificados}


def identificar_jugadores(fichas: list[dict], api_key: Optional[str] = None) -> dict[int, tuple[str, bool]]:
    """fichas: Carrera.ficha(jugador). Devuelve {id: (nombre, seguro)}."""
    resultado: dict[int, tuple[str, bool]] = {}
    for desde in range(0, len(fichas), MAXIMO_POR_CONSULTA):
        tanda = fichas[desde: desde + MAXIMO_POR_CONSULTA]
        prompt = f"""
Estas son fichas de futbolistas reales tomadas de la base de datos de
EA SPORTS FC 26 (modo carrera). El campo "id" es el id de EA del jugador
(el mismo de sofifa). Para cada ficha, deci como se llama el jugador, con
el nombre con el que es conocido (ej. "Erling Haaland", "Vinicius Jr.").

Reglas:
- Usa todas las pistas: club, posicion, seleccion, fecha de nacimiento y
  "media" (su valoracion general en FC 26).
- El club puede no ser el de la vida real: en el modo carrera hubo
  traspasos ("Agentes libres" = sin club). Si el club no calza, guiate por
  el id, la fecha de nacimiento, la seleccion y la posicion.
- Si no lo reconoces con seguridad, devolve nombre "" y seguro=false.
  Es mucho peor un nombre equivocado que uno vacio: no adivines.
- Devolve un elemento por cada id.

Fichas:
{json.dumps(tanda, ensure_ascii=False, indent=1)}
""".strip()
        resultado.update(_consultar(prompt, api_key))
    return resultado


def identificar_competiciones(fichas: list[dict], api_key: Optional[str] = None) -> dict[int, tuple[str, bool]]:
    """fichas: {"id", "codigo", "continental", "equipos": [...]}: el nombre
    sale de quienes la juegan (con Napoli, Galatasaray y Real Madrid en una
    fase de 36 equipos es la Champions)."""
    if not fichas:
        return {}
    prompt = f"""
Estas son competiciones de un modo carrera de EA SPORTS FC 26 que el
guardado no nombra. De cada una tenes su codigo interno, si es continental
y algunos de los equipos que la juegan. Deci el nombre de la competicion
real en espanol (ej. "Champions League", "FA Cup", "Carabao Cup").

Si no estas seguro, nombre "" y seguro=false. No adivines.

{json.dumps(fichas, ensure_ascii=False, indent=1)}
""".strip()
    return _consultar(prompt, api_key)
