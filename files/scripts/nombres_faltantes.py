"""
Los jugadores de tu partida que salen en la prensa (los goleadores de tus
competiciones) y todavia no tienen nombre: la partida de FC 26 no guarda los
nombres de los jugadores actuales, asi que se suman a mano a
roleplay/datos/jugadores_fc26.json.

    .venv\\Scripts\\python.exe scripts\\nombres_faltantes.py                     la lista
    .venv\\Scripts\\python.exe scripts\\nombres_faltantes.py --agregar ID "Nombre"
    .venv\\Scripts\\python.exe scripts\\nombres_faltantes.py --catalogo-ea       baja el catalogo de EA
    .venv\\Scripts\\python.exe scripts\\nombres_faltantes.py --cobertura         cuantos se nombran

--catalogo-ea baja el catalogo oficial de ratings de EA FC (drop-api.ea.com,
~18.000 jugadores de todas las ligas, con su id de EA = el de la partida y su
nacimiento) a roleplay/datos/catalogo_ea.json. Ese archivo queda SOLO en el
PC (.gitignore: el repo es publico) y va en el paquete de los amigos.

La lista trae id, club, posicion, seleccion y nacimiento: con eso (y sofifa,
donde el id es el mismo) se sabe quien es. --agregar guarda el nombre CON la
fecha de nacimiento de la partida: si algun dia ese id es otra persona, no
calza y queda sin nombre. Solo lee la partida. Si no estas seguro de quien es,
no lo agregues: sin nombre, la prensa lo describe ("el delantero del Arsenal").
"""

import argparse
import http.client
import json
import sys
import time
import urllib.request
from datetime import date, datetime
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

from roleplay.partida.lector import carrera_actual  # noqa: E402
from roleplay.servicios import identificar  # noqa: E402
from roleplay.servicios.partida_real import (  # noqa: E402
    competiciones_del_usuario,
    nombrar_competiciones,
    nombres_de_jugadores,
)

ARCHIVO = RAIZ / "roleplay" / "datos" / "jugadores_fc26.json"
CATALOGO = RAIZ / "roleplay" / "datos" / "catalogo_ea.json"
API_EA = "https://drop-api.ea.com/rating/ea-sports-fc?locale=en&limit={limite}&offset={desde}{filtro}"
POR_PAGINA = 100  # la API no acepta mas
# el orden de la API no es estable: con todo junto se saltea siempre a los mismos ~660
# (De Bruyne, Dybala...). Recorrerla tambien por genero cambia el orden y los trae.
FILTROS = ("", "&gender=0", "&gender=1")
REINTENTOS = 3  # a veces corta una respuesta a la mitad
GOLEADORES_POR_COMPETICION = 15


def sin_nombre(carrera) -> list[dict]:
    """Las fichas de los goleadores de las competiciones del usuario que ni la
    partida (editados) ni la base local nombran."""
    fichas, vistos = [], set()
    for competicion in competiciones_del_usuario(carrera):
        goleadores = carrera.goleadores(competicion, GOLEADORES_POR_COMPETICION)
        nombrados = nombres_de_jugadores(carrera, {g.jugador for g in goleadores})
        for goleador in goleadores:
            jugador = goleador.jugador
            if jugador in vistos or jugador in nombrados:
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


def _nacimiento_ea(texto: str) -> str:
    """"6/15/1992 12:00:00 AM" -> "1992-06-15" ("" si no se entiende)."""
    try:
        return datetime.strptime((texto or "").split(" ")[0], "%m/%d/%Y").date().isoformat()
    except ValueError:
        return ""


def entrada_del_catalogo(item: dict) -> dict:
    entrada = {"pila": (item.get("firstName") or "").strip(), "apellido": (item.get("lastName") or "").strip(),
               "nacimiento": _nacimiento_ea(item.get("birthdate"))}
    if (item.get("commonName") or "").strip():
        entrada["comun"] = item["commonName"].strip()
    return entrada


def _pagina(abrir, desde: int, filtro: str) -> dict:
    pedido = urllib.request.Request(API_EA.format(limite=POR_PAGINA, desde=desde, filtro=filtro),
                                    headers={"User-Agent": "Mozilla/5.0", "Accept": "application/json"})
    for intento in range(REINTENTOS):
        try:
            with abrir(pedido, timeout=30) as respuesta:
                return json.loads(respuesta.read().decode("utf-8"))
        except (OSError, ValueError, http.client.HTTPException):
            if intento == REINTENTOS - 1:
                raise
            time.sleep(2)


def _pasada(jugadores: dict, abrir, pausa: float, filtro: str = "") -> int:
    """Una vuelta por todas las paginas; suma a `jugadores`. Devuelve cuantos nuevos."""
    antes, desde, total = len(jugadores), 0, 0
    while True:
        pagina = _pagina(abrir, desde, filtro)
        total = max(total, pagina.get("totalItems") or 0)  # la API no siempre dice el mismo total
        items = pagina.get("items") or []
        for item in items:
            if item.get("id"):
                jugadores[str(item["id"])] = entrada_del_catalogo(item)
        desde += len(items)
        print(f"  {desde}/{total} ({len(jugadores)} distintos)", end="\r", flush=True)
        if not items or desde >= total:
            return len(jugadores) - antes
        time.sleep(pausa)


def bajar_catalogo(archivo: Path = CATALOGO, abrir=urllib.request.urlopen, pausa: float = 0.1,
                   pasadas: int = 4) -> int:
    """Baja el catalogo de EA y lo guarda (sumado a lo que ya habia). El orden de la
    API no es estable entre paginas y en cada vuelta se saltea gente: se dan varias
    vueltas hasta que casi no aparecen nuevos. Devuelve cuantos jugadores quedan."""
    try:
        jugadores = json.loads(archivo.read_text(encoding="utf-8")).get("jugadores", {})
    except (OSError, ValueError):
        jugadores = {}
    for numero in range(pasadas):
        nuevos = sum(_pasada(jugadores, abrir, pausa, filtro) for filtro in FILTROS)
        print(f"\n  vuelta {numero + 1}: {nuevos} nuevos")
        if nuevos < 20:
            break
    archivo.write_text(json.dumps({
        "_comentario": "Catalogo oficial de ratings de EA FC 26 (drop-api.ea.com), por id de EA. SOLO local: "
                       "no se sube al repo (.gitignore). Lo genera scripts/nombres_faltantes.py --catalogo-ea.",
        "_descargado": date.today().isoformat(),
        "jugadores": jugadores,
    }, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    return len(jugadores)


def cobertura(carrera) -> dict:
    """Cuantos se nombran: todos los jugadores, los goleadores de cada competicion y los de tu liga."""
    todos = set(carrera.nacimientos)
    nombrados = nombres_de_jugadores(carrera, todos)
    goleadores = {g.jugador for c in carrera.competiciones for g in carrera.goleadores(c, 10_000)}
    return {"jugadores": (len(todos & set(nombrados)), len(todos)),
            "goleadores": (len(goleadores & set(nombrados)), len(goleadores)),
            "goleadores_sin_nombre": sorted(goleadores - set(nombrados))}


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--agregar", nargs=2, metavar=("ID", "NOMBRE"), help="suma un nombre a la base local")
    parser.add_argument("--catalogo-ea", action="store_true", help="baja el catalogo de EA (solo local)")
    parser.add_argument("--cobertura", action="store_true", help="cuantos jugadores de tu partida tienen nombre")
    argumentos = parser.parse_args(argv)
    if argumentos.catalogo_ea:
        print("Bajando el catalogo de EA FC...")
        print(f"\nListo: {bajar_catalogo()} jugadores en {CATALOGO}")
        identificar._catalogo.cache_clear()
    carrera = carrera_actual()
    if carrera is None:
        print("No encontre una partida de Carrera Jugador de FC 26.")
        return 1
    if argumentos.cobertura or argumentos.catalogo_ea:
        datos = cobertura(carrera)
        for clave in ("jugadores", "goleadores"):
            con, total = datos[clave]
            print(f"{clave}: {con}/{total} con nombre ({100 * con / max(total, 1):.1f}%)")
        for jugador in datos["goleadores_sin_nombre"][:40]:
            ficha = carrera.ficha(jugador)
            print(f"  sin nombre: {jugador} | {ficha.get('club', '?')} | {ficha.get('posicion', '?')} | "
                  f"{ficha.get('nacimiento', '?')}")
        return 0
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
