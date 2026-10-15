"""
Metas de temporada: el usuario se propone algo ("30 goles", "terminar entre
los 4 primeros") y la app sigue el avance con los datos reales de la
partida. Cumplirla o no es noticia y mueve la reputacion; la prensa y las
entrevistas las conocen (servicios/cruce.py: la meta que esta cerca).

Solo metas que la partida permite medir: contar goles o asistencias y la
posicion final del club en la liga.
"""

import uuid
from typing import Optional

from roleplay.partida.carrera import Carrera
from roleplay.servicios.partida_real import (
    competiciones_del_usuario,
    liga_terminada,
    temporada_de,
    totales_usuario,
)

# tipo -> (como se elige en la pantalla, como se cuenta la meta)
TIPOS = {
    "goles": ("Goles en la temporada", "Marcar {objetivo} goles en la temporada"),
    "goles_liga": ("Goles en la liga", "Marcar {objetivo} goles en la liga"),
    "asistencias": ("Asistencias en la temporada", "Dar {objetivo} asistencias en la temporada"),
    "top_liga": ("Terminar entre los primeros de la liga", "Terminar entre los {objetivo} primeros de la liga"),
}
CONTABLES = {"goles", "goles_liga", "asistencias"}  # se cumplen apenas se llega


def nueva_meta(tipo: str, objetivo: int, temporada: str) -> dict:
    if tipo not in TIPOS:
        raise ValueError(f"Tipo de meta desconocido: {tipo}")
    if objetivo < 1:
        raise ValueError("El objetivo tiene que ser 1 o mas")
    return {
        "id": uuid.uuid4().hex[:8],
        "tipo": tipo,
        "objetivo": int(objetivo),
        "temporada": temporada,
        "estado": "en_curso",  # | "cumplida" | "fallida"
        "actual": None,
    }


def texto_meta(meta: dict) -> str:
    texto = TIPOS[meta["tipo"]][1].format(objetivo=meta["objetivo"])
    if meta["tipo"] == "top_liga" and meta["objetivo"] == 1:
        texto = "Salir campeon de la liga"
    return texto


def _liga(carrera: Carrera) -> Optional[int]:
    ligas = [c for c in competiciones_del_usuario(carrera) if carrera.competiciones[c].es_liga]
    return ligas[0] if ligas else None


def progreso(carrera: Carrera, meta: dict) -> Optional[int]:
    """Cuanto lleva (goles, asistencias) o en que puesto va el club. None
    si la partida no lo dice (sin club, sin liga)."""
    totales = totales_usuario(carrera)
    if meta["tipo"] == "goles":
        return sum(t["goles"] for t in totales.values())
    if meta["tipo"] == "asistencias":
        return sum(t["asistencias"] for t in totales.values())
    liga = _liga(carrera)
    if liga is None:
        return None
    if meta["tipo"] == "goles_liga":
        return totales.get(str(liga), {}).get("goles", 0)
    equipo = carrera.equipo_usuario()
    return carrera.posicion_en(liga, equipo) if equipo is not None else None


def evaluar_metas(carrera: Carrera, metas: list[dict]) -> tuple[list[dict], dict]:
    """(hitos para la prensa, cambios {id: campos} para guardar). Una meta
    contable se cumple apenas se llega; la del puesto se decide cuando
    termina la liga. Las que quedaron de una temporada anterior sin
    cumplirse, fallan (con lo ultimo que se vio)."""
    hoy = carrera.fecha_actual()
    if hoy is None:
        return [], {}
    temporada = temporada_de(hoy)
    liga = _liga(carrera)
    terminada = liga is not None and liga_terminada(carrera, liga)
    hitos, cambios = [], {}
    for meta in metas:
        if meta.get("estado") != "en_curso":
            continue
        if meta["temporada"] != temporada:
            cambios[meta["id"]] = {"estado": "fallida"}
            hitos.append({"tipo": "meta_fallida", "valor": f"{texto_meta(meta)} ({meta['temporada']})"})
            continue
        actual = progreso(carrera, meta)
        cambio = {"actual": actual}
        if actual is not None:
            if meta["tipo"] in CONTABLES and actual >= meta["objetivo"]:
                cambio["estado"] = "cumplida"
            elif meta["tipo"] == "top_liga" and terminada:
                cambio["estado"] = "cumplida" if actual <= meta["objetivo"] else "fallida"
        if cambio.get("estado") == "cumplida":
            hitos.append({"tipo": "meta_cumplida", "valor": texto_meta(meta)})
        elif cambio.get("estado") == "fallida":
            hitos.append({"tipo": "meta_fallida", "valor": texto_meta(meta)})
        cambios[meta["id"]] = cambio
    return hitos, cambios
