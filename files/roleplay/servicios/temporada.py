"""
Los datos de la pagina Temporada: tabla, goleadores, los partidos del club
del usuario y la ultima fecha de una competicion, sacados de la partida de
FC 26. Todo calculado; la IA solo pone nombre a los goleadores que la
partida no trae (una vez, con cache).
"""

from dataclasses import dataclass, field
from typing import Optional

from roleplay.partida.carrera import Carrera, Partido
from roleplay.servicios.partida_real import (
    competiciones_del_usuario,
    describir_jugador,
    fecha_corta,
    nombrar_competiciones,
    nombres_de_jugadores,
    temporada_de,
)

GOLEADORES = 10
RESULTADOS = 6  # ultimos partidos jugados del club en la competicion
PROXIMOS = 4
DIAS_DE_UNA_FECHA = 3  # una "fecha" de liga se juega en varios dias seguidos


@dataclass
class FilaTablaVista:
    posicion: int
    equipo: str
    pj: int
    pg: int
    pe: int
    pp: int
    gf: int
    gc: int
    pts: int
    es_usuario: bool

    @property
    def dif(self) -> int:
        return self.gf - self.gc


@dataclass
class GoleadorVista:
    nombre: str
    equipo: str
    goles: int
    partidos: int
    es_usuario: bool  # el jugador del usuario


@dataclass
class PartidoVista:
    fecha: str
    local: str
    visita: str
    marcador: str  # "5-3" o "vs"
    resultado: Optional[str] = None  # G/E/P para el club del usuario, si jugo
    es_usuario: bool = False  # juega el club del usuario


@dataclass
class VistaTemporada:
    temporada: str
    partida: str
    club: str
    fecha: str
    competiciones: list  # (id, nombre) de las que juega el club, la liga primero
    competicion: int
    nombre_competicion: str
    es_liga: bool
    posicion: Optional[int] = None  # del club en la tabla, si es liga
    tabla: list = field(default_factory=list)  # FilaTablaVista
    goleadores: list = field(default_factory=list)  # GoleadorVista
    resultados: list = field(default_factory=list)  # PartidoVista, del mas viejo al ultimo
    proximos: list = field(default_factory=list)  # PartidoVista
    ultima_fecha: list = field(default_factory=list)  # PartidoVista
    titulo_ultima_fecha: str = ""


def _dia(dia) -> str:
    return dia.strftime("%d/%m")


def _partido(carrera: Carrera, p: Partido, equipo_usuario: Optional[int]) -> PartidoVista:
    juega = equipo_usuario is not None and p.participa(equipo_usuario)
    resultado = None
    if p.jugado and juega:
        resultado = {"victoria": "G", "empate": "E", "derrota": "P"}[p.resultado_para(equipo_usuario)]
    return PartidoVista(
        fecha=_dia(p.fecha),
        local=carrera.equipo(p.local),
        visita=carrera.equipo(p.visita),
        marcador=f"{p.goles_local}-{p.goles_visita}" if p.jugado else "vs",
        resultado=resultado,
        es_usuario=juega,
    )


def _ordenar_competiciones(carrera: Carrera, propias: list[int]) -> list[int]:
    """La liga primero; despues las demas, la que tiene mas partidos antes."""
    return sorted(
        propias,
        key=lambda c: (
            not carrera.competiciones[c].es_liga,
            -sum(1 for p in carrera.partidos if p.competicion == c),
            c,
        ),
    )


def vista_temporada(
    carrera: Carrera, competicion: Optional[int] = None, preguntar: bool = True
) -> Optional[VistaTemporada]:
    """None si la partida no tiene un club del usuario o no se jugo nada.
    Si `competicion` no es una de las del club, se muestra la primera."""
    equipo = carrera.equipo_usuario()
    hoy = carrera.fecha_actual()
    propias = [c for c in competiciones_del_usuario(carrera) if c in carrera.competiciones]
    if equipo is None or hoy is None or not propias:
        return None
    nombrar_competiciones(carrera, propias, preguntar=preguntar)
    orden = _ordenar_competiciones(carrera, propias)
    if competicion not in orden:
        competicion = orden[0]
    comp = carrera.competiciones[competicion]

    vista = VistaTemporada(
        temporada=temporada_de(hoy),
        partida=carrera.partida,
        club=carrera.equipo(equipo),
        fecha=fecha_corta(hoy),
        competiciones=[(c, carrera.competicion(c)) for c in orden],
        competicion=competicion,
        nombre_competicion=carrera.competicion(competicion),
        es_liga=comp.es_liga,
    )
    if comp.es_liga:
        vista.tabla = [
            FilaTablaVista(n, carrera.equipo(f.equipo), f.pj, f.pg, f.pe, f.pp, f.gf, f.gc, f.pts, f.equipo == equipo)
            for n, f in enumerate(carrera.tabla(competicion), start=1)
        ]
        vista.posicion = next((f.posicion for f in vista.tabla if f.es_usuario), None)

    goleadores = carrera.goleadores(competicion, GOLEADORES)
    nombres = nombres_de_jugadores(carrera, {e.jugador for e in goleadores}, preguntar=preguntar)
    vista.goleadores = [
        GoleadorVista(
            describir_jugador(carrera, e.jugador, nombres), carrera.equipo(e.equipo), e.goles, e.partidos,
            e.jugador == carrera.usuario_id,
        )
        for e in goleadores
    ]

    del_club = [p for p in carrera.partidos_de(equipo) if p.competicion == competicion]
    vista.resultados = [_partido(carrera, p, equipo) for p in del_club if p.jugado][-RESULTADOS:]
    vista.proximos = [_partido(carrera, p, equipo) for p in del_club if not p.jugado][:PROXIMOS]

    jugados = [p for p in carrera.partidos if p.competicion == competicion and p.jugado]
    if jugados:
        ultimo_dia = max(p.fecha for p in jugados)
        recientes = sorted(
            (p for p in jugados if (ultimo_dia - p.fecha).days <= DIAS_DE_UNA_FECHA),
            key=lambda p: (p.fecha, carrera.equipo(p.local)),
        )
        vista.ultima_fecha = [_partido(carrera, p, equipo) for p in recientes]
        primero = recientes[0].fecha
        vista.titulo_ultima_fecha = (
            f"{_dia(primero)} al {_dia(ultimo_dia)}" if primero != ultimo_dia else _dia(ultimo_dia)
        )
    return vista


def leer_temporada(competicion: Optional[int] = None) -> Optional[VistaTemporada]:
    """Para la pagina (corre en un hilo): la partida elegida y su vista.
    None si no hay partida de Carrera Jugador en el PC."""
    from roleplay.partida.lector import carrera_actual

    carrera = carrera_actual()
    return vista_temporada(carrera, competicion) if carrera is not None else None
