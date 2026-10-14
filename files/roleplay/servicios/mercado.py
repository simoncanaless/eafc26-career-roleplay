"""
Mercado de fichajes con datos reales. La partida de FC 26 guarda en que
club esta cada jugador; comparando contra la lectura anterior de la misma
partida (tabla club_visto) los que cambiaron de club son traspasos.

Que es noticia lo decide el codigo: lo que toca al club del usuario, las
estrellas (por su media) de cualquier liga y los buenos jugadores de su
liga. La IA solo redacta. Las jugadoras (ligas femeninas) no entran.
"""

from dataclasses import dataclass
from typing import Optional

from roleplay.partida.carrera import Carrera

MEDIA_ESTRELLA = 82  # un traspaso asi es noticia venga de la liga que venga
MEDIA_EN_TU_LIGA = 75  # ...y asi, si entra o sale de la liga del usuario
TRASPASOS_EN_LA_NOTICIA = 5
MERCADO_GUARDADO = 15  # los ultimos que se muestran en la pagina Temporada


@dataclass(frozen=True)
class Traspaso:
    jugador: int
    desde: int
    hacia: int
    media: int
    puntaje: int
    toca_al_club: bool  # entra o sale del club del usuario


def clubes_de_jugadores(carrera: Carrera) -> dict[int, int]:
    """{jugador: club} de hoy (hombres; con los agentes libres como "club")."""
    clubes = {}
    for jugador in carrera.vinculos:
        if jugador in carrera.mujeres:
            continue
        club = carrera.club_de(jugador)
        if club is not None:
            clubes[jugador] = club
    return clubes


def detectar_traspasos(carrera: Carrera, anteriores: dict[int, int]) -> list[Traspaso]:
    """Los traspasos que son noticia desde la lectura anterior, el mas
    importante primero. Sin lectura anterior no hay con que comparar."""
    if not anteriores or not carrera.ligas_de_equipo:
        return []
    equipo = carrera.equipo_usuario()
    liga_usuario = carrera.ligas_de_equipo.get(equipo)
    traspasos = []
    for jugador, hacia in clubes_de_jugadores(carrera).items():
        desde = anteriores.get(jugador)
        if desde is None or desde == hacia or jugador == carrera.usuario_id:
            continue
        media = carrera.medias.get(jugador, 0)
        toca = equipo is not None and equipo in (desde, hacia)
        en_su_liga = liga_usuario is not None and liga_usuario in (
            carrera.ligas_de_equipo.get(desde), carrera.ligas_de_equipo.get(hacia)
        )
        if toca:
            puntaje = 200 + media
        elif media >= MEDIA_ESTRELLA:
            puntaje = 100 + media
        elif en_su_liga and media >= MEDIA_EN_TU_LIGA:
            puntaje = media
        else:
            continue
        traspasos.append(Traspaso(jugador, desde, hacia, media, puntaje, toca))
    return sorted(traspasos, key=lambda t: (-t.puntaje, t.jugador))


def traspaso_del_usuario(carrera: Carrera, anteriores: dict[int, int]) -> Optional[tuple[int, int]]:
    """(club de antes, club de ahora) si el jugador del usuario cambio de club."""
    if carrera.usuario_id is None:
        return None
    antes, ahora = anteriores.get(carrera.usuario_id), carrera.club_de(carrera.usuario_id)
    if antes is not None and ahora is not None and antes != ahora:
        return antes, ahora
    return None


def _quien(carrera: Carrera, traspaso: Traspaso, nombres: dict[int, str], para_la_ia: bool) -> str:
    if traspaso.jugador in nombres:
        return f"{nombres[traspaso.jugador]} (media {traspaso.media})"
    ficha = carrera.ficha(traspaso.jugador)
    edad = f"edad {ficha['edad']}, " if "edad" in ficha else ""
    aviso = ", sin nombre en la partida" if para_la_ia else ""  # que la IA no le invente uno
    return f"un {ficha.get('posicion', 'jugador')} ({edad}media {traspaso.media}{aviso})"


def describir_traspaso(
    carrera: Carrera, traspaso: Traspaso, nombres: dict[int, str], para_la_ia: bool = True
) -> str:
    quien = _quien(carrera, traspaso, nombres, para_la_ia)
    desde, hacia = carrera.equipo(traspaso.desde), carrera.equipo(traspaso.hacia)
    if carrera.es_agentes_libres(traspaso.hacia):
        return f"{quien} quedo libre tras dejar {desde}"
    if carrera.es_agentes_libres(traspaso.desde):
        return f"{quien} firmo con {hacia} como agente libre"
    return f"{quien} paso de {desde} a {hacia}"


def texto_mercado(carrera: Carrera, traspasos: list[Traspaso], nombres: dict[int, str]) -> str:
    """El hecho para la noticia del mundo: los movimientos, con lo que toca
    al club del usuario primero."""
    club = carrera.equipo(carrera.equipo_usuario())
    lineas = [f"Movimientos del mercado de fichajes (club del jugador: {club}):"]
    lineas += [f"- {describir_traspaso(carrera, t, nombres)}." for t in traspasos]
    return "\n".join(lineas)
