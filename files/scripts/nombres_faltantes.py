"""
Los jugadores de tu partida que salen en la prensa (los goleadores de tus
competiciones) y todavia no tienen nombre: la partida de FC 26 no guarda los
nombres de los jugadores actuales, asi que se suman a mano a
roleplay/datos/jugadores_fc26.json.

    .venv\\Scripts\\python.exe scripts\\nombres_faltantes.py                     la lista
    .venv\\Scripts\\python.exe scripts\\nombres_faltantes.py --agregar ID "Nombre"

La lista trae id, club, posicion, seleccion y nacimiento: con eso (y sofifa,
donde el id es el mismo) se sabe quien es. --agregar guarda el nombre CON la
fecha de nacimiento de la partida: si algun dia ese id es otra persona, no
calza y queda sin nombre. Solo lee la partida. Si no estas seguro de quien es,
no lo agregues: sin nombre, la prensa lo describe ("el delantero del Arsenal").
"""

import argparse
import json
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

from roleplay.partida.lector import carrera_actual  # noqa: E402
from roleplay.servicios import identificar  # noqa: E402
from roleplay.servicios.partida_real import competiciones_del_usuario, nombrar_competiciones  # noqa: E402

ARCHIVO = RAIZ / "roleplay" / "datos" / "jugadores_fc26.json"
GOLEADORES_POR_COMPETICION = 15


def sin_nombre(carrera) -> list[dict]:
    """Las fichas de los goleadores de las competiciones del usuario que ni la
    partida (editados) ni la base local nombran."""
    conocidos = identificar.jugadores_conocidos()
    fichas, vistos = [], set()
    for competicion in competiciones_del_usuario(carrera):
        for goleador in carrera.goleadores(competicion, GOLEADORES_POR_COMPETICION):
            jugador = goleador.jugador
            if jugador in vistos or str(jugador) in conocidos or carrera.nombre_editado(jugador):
                continue
            vistos.add(jugador)
            fichas.append({**carrera.ficha(jugador), "goles": goleador.goles,
                           "competicion": carrera.competicion(competicion)})
    return fichas


def agregar(carrera, jugador: int, nombre: str, archivo: Path = ARCHIVO) -> dict:
    """Guarda el nombre con el nacimiento que dice la partida. Devuelve la entrada."""
    contenido = json.loads(archivo.read_text(encoding="utf-8"))
    entrada = {"nombre": nombre.strip()}
    nacimiento = carrera.ficha(jugador).get("nacimiento")
    if nacimiento:
        entrada["nacimiento"] = nacimiento
    jugadores = contenido.setdefault("jugadores", {})
    jugadores[str(jugador)] = entrada
    contenido["jugadores"] = dict(sorted(jugadores.items(), key=lambda par: int(par[0])))
    archivo.write_text(json.dumps(contenido, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    return entrada


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--agregar", nargs=2, metavar=("ID", "NOMBRE"), help="suma un nombre a la base local")
    argumentos = parser.parse_args(argv)
    carrera = carrera_actual()
    if carrera is None:
        print("No encontre una partida de Carrera Jugador de FC 26.")
        return 1
    if argumentos.agregar:
        jugador, nombre = int(argumentos.agregar[0]), argumentos.agregar[1]
        entrada = agregar(carrera, jugador, nombre)
        if "nacimiento" not in entrada:
            print(f"Ojo: el id {jugador} no esta en tu partida; quedo sin fecha de nacimiento para comprobarlo.")
        print(f"Agregado: {jugador} = {entrada}")
        return 0
    nombrar_competiciones(carrera, competiciones_del_usuario(carrera))
    fichas = sin_nombre(carrera)
    if not fichas:
        print("Todos los goleadores de tus competiciones tienen nombre.")
        return 0
    print(f"{len(fichas)} goleadores sin nombre (id | club | posicion | seleccion | nacimiento | goles):")
    for ficha in fichas:
        print(f"  {ficha['id']} | {ficha.get('club', '?')} | {ficha.get('posicion', '?')} | "
              f"{ficha.get('seleccion', '-') or '-'} | {ficha.get('nacimiento', '?')} | "
              f"{ficha['goles']} en {ficha['competicion']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
