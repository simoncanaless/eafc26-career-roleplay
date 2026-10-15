"""
Tu hinchada: el carino de la hinchada de cada club en el que jugaste, y
las decisiones que te toca tomar.

El carino (0-100) arranca en 50 al llegar a un club y se mueve con lo que
pasa: cada partido del club (ganar suma, perder resta; tus goles y tu nota
pesan mas), y lo que te pasa fuera de la cancha (una polemica resta, la
camiseta al nene suma). Todo lo decide el codigo.

Cuando la partida muestra que cambiaste de club:
- te vas como idolo (carino >= 70), normal, o por la puerta de atras (<= 30);
- si eras idolo y te vas a otro club de LA MISMA LIGA, para tus ex hinchas
  sos un traidor (su carino cae 30 puntos): la partida no guarda rivalidades,
  la liga es lo que se puede saber;
- si volves a un club donde ya jugaste, te reciben segun como te fuiste.
Cada una de esas cosas es noticia (`hitos`).

Las decisiones aparecen solas cuando la historia lo pide y se contestan en
el Resumen: la hinchada en tu contra (carino < 25), una polemica que no para
(despues de una polemica en redes o de la fiesta filtrada), o un grande que
pregunta por vos cuando sos el idolo (carino >= 85 y reputacion >= 70, una
vez por temporada). Cada opcion mueve carino, reputacion y seguidores, puede
traer un reto de roleplay (pedir el traspaso en el juego...) y es noticia.

Estado en estado_json.clubes:
{"actual": "<equipo>", "hasta": ultimo partido contado (iso),
 "clubes": {"<equipo>": {"nombre", "liga", "carino", "desde", "hasta", "salida"}},
 "decision": {"tipo", "club", "fecha"} o None,
 "decisiones": [{"tipo", "club", "fecha", "eleccion"}]}  (la mas nueva primero)
"""

import copy
from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Optional

from roleplay.partida.carrera import Carrera

CARINO_INICIAL = 50
IDOLO, PUERTA_DE_ATRAS = 70, 30
EN_CONTRA = 25
TENTADO_CARINO, TENTADO_REPUTACION = 85, 70
CASTIGO_TRAICION = 30
DIAS_ENTRE_DECISIONES = 60  # la misma decision no vuelve antes
DIAS_ENTRE_TENTACIONES = 300  # un grande pregunta una vez por temporada
DECISIONES_GUARDADAS = 20

# lo que mueve un evento inesperado (servicios/eventos.py) en la hinchada de tu club
POR_EVENTO = {
    "polemica_redes": -4, "fiesta_yate": -5, "increpado": -4, "llegada_tarde": -2, "multa_velocidad": -2,
    "camiseta_nene": 5, "premio_hinchas": 4, "visita_hospital": 2, "video_viral": 1,
}
EVENTOS_POLEMICOS = {"polemica_redes", "fiesta_yate"}


def rotulo(carino: int) -> str:
    if carino >= TENTADO_CARINO:
        return "Idolo"
    if carino >= 65:
        return "Querido"
    if carino >= 45:
        return "Respetado"
    if carino >= EN_CONTRA:
        return "Cuestionado"
    return "En contra"


@dataclass(frozen=True)
class Opcion:
    id: str
    texto: str  # el boton
    noticia: str  # lo que hizo, para la prensa (tercera persona, despues del nombre)
    tono: str
    carino: int
    reputacion: int
    seguidores: float  # veces la escala de la hinchada
    reto: str = ""


@dataclass(frozen=True)
class Decision:
    titulo: str  # {club}
    pregunta: str
    opciones: tuple


DECISIONES = {
    "en_contra": Decision(
        "La hinchada de {club} esta en tu contra",
        "Te silban en cada partido y en las redes piden que te vayas. Que haces?",
        (
            Opcion("pelearla", "Quedarte y ganartelos", "prometio quedarse en {club} y ganarse a la hinchada",
                   "positiva", 8, 0, 0.3, "Marca o asisti en los proximos 2 partidos para dar vuelta la historia."),
            Opcion("carta", "Escribirles una carta abierta", "publico una carta abierta a los hinchas de {club}",
                   "positiva", 5, 1, 0.5),
            Opcion("salir", "Pedir que te vendan", "le pidio a {club} que lo venda", "negativa", -15, -1, 0.8,
                   "En el juego, pedi el traspaso (o ponete transferible) y busca club."),
        ),
    ),
    "polemica": Decision(
        "La polemica no para",
        "Todo el mundo habla de lo que paso. Como respondes?",
        (
            Opcion("disculpas", "Pedir disculpas publicas", "pidio disculpas publicas por la polemica", "positiva", 4, 2, -0.3),
            Opcion("redoblar", "Redoblar la apuesta", "redoblo la apuesta en las redes", "negativa", -4, -2, 1.5),
            Opcion("silencio", "No decir nada", "eligio el silencio despues de la polemica", "neutral", -1, 0, 0),
        ),
    ),
    "tentado": Decision(
        "Un grande de Europa pregunta por vos",
        "Sos el idolo de {club}, pero llega una oferta de las que no se ven seguido. Que haces?",
        (
            Opcion("fiel", "Quedarme: este es mi club", "rechazo una oferta de un grande para quedarse en {club}",
                   "positiva", 10, 2, 0.8),
            Opcion("escuchar", "Escuchar la oferta", "abrio la puerta a dejar {club}", "mixta", -10, 0, 1.0,
                   "En el juego, acepta hablar con los clubes interesados en la proxima ventana de pases."),
        ),
    ),
}


@dataclass
class Hito:
    """Algo de la hinchada que es noticia."""

    tipo: str  # llegada | regreso | salida | traicion | eleccion
    titulo: str
    descripcion: str  # para la prensa (tercera persona, despues del nombre)
    tono: str
    seguidores: float = 0.3  # veces la escala de la hinchada
    reputacion: int = 0
    reto: str = ""


# ---- la partida: partidos y traspasos ----


def _club_nuevo(carrera: Carrera, equipo: int, hoy: date, carino: int = CARINO_INICIAL) -> dict:
    return {"nombre": carrera.equipo(equipo), "liga": carrera.ligas_de_equipo.get(equipo), "carino": carino,
            "desde": hoy.isoformat(), "hasta": None, "salida": None}


def _acotar(club: dict, delta: int) -> None:
    club["carino"] = max(0, min(100, club["carino"] + delta))


def carino_por_partido(resultado: str, jugo: bool, goles: int, nota: Optional[float]) -> int:
    delta = {"victoria": 1, "empate": 0, "derrota": -1}[resultado]
    if jugo:
        delta += min(6, 2 * goles)
        if nota is not None and nota >= 8.0:
            delta += 2
        elif nota is not None and nota < 6.0:
            delta -= 2
    return delta


def _cambio_de_club(estado: dict, carrera: Carrera, equipo: int, hoy: date) -> list[Hito]:
    hitos = []
    clubes = estado["clubes"]
    viejo = clubes[estado["actual"]]
    viejo["hasta"] = hoy.isoformat()
    viejo["salida"] = "idolo" if viejo["carino"] >= IDOLO else "mala" if viejo["carino"] <= PUERTA_DE_ATRAS else "normal"
    nuevo_nombre = carrera.equipo(equipo)
    if viejo["salida"] == "idolo":
        hitos.append(Hito("salida", f"Despedida de idolo en {viejo['nombre']}",
                          f"se fue de {viejo['nombre']} despedido como un idolo por sus hinchas", "positiva", 0.8, 1))
    elif viejo["salida"] == "mala":
        hitos.append(Hito("salida", f"Se va de {viejo['nombre']} por la puerta de atras",
                          f"se fue de {viejo['nombre']} entre silbidos de sus propios hinchas", "negativa", 0.2))
    liga_nueva = carrera.ligas_de_equipo.get(equipo)
    if viejo["salida"] == "idolo" and liga_nueva is not None and liga_nueva == viejo.get("liga"):
        _acotar(viejo, -CASTIGO_TRAICION)
        hitos.append(Hito("traicion", f"Los hinchas de {viejo['nombre']} lo tratan de traidor",
                          f"ficho por {nuevo_nombre}, rival de liga de {viejo['nombre']}, y sus ex hinchas no se lo "
                          "perdonan", "negativa", 1.0, -2))
    clave = str(equipo)
    if clave in clubes:  # vuelve
        club = clubes[clave]
        club.update(hasta=None, desde=hoy.isoformat(), nombre=nuevo_nombre)
        if club.get("salida") == "idolo":
            _acotar(club, 10)
            hitos.append(Hito("regreso", f"Vuelve el idolo a {nuevo_nombre}",
                              f"volvio a {nuevo_nombre}, donde lo esperaban como a un idolo", "positiva", 1.2, 2))
        elif club.get("salida") == "mala":
            hitos.append(Hito("regreso", f"Vuelve a {nuevo_nombre}, donde no lo olvidan",
                              f"volvio a {nuevo_nombre}, donde se habia ido por la puerta de atras", "mixta", 0.5))
        else:
            hitos.append(Hito("regreso", f"Vuelve a {nuevo_nombre}", f"volvio a {nuevo_nombre}", "neutral", 0.4))
        club["salida"] = None
    else:
        clubes[clave] = _club_nuevo(carrera, equipo, hoy)
        hitos.append(Hito("llegada", f"Llega a {nuevo_nombre}", f"es nuevo jugador de {nuevo_nombre}", "positiva", 0.6))
    estado["actual"] = clave
    return hitos


def _reciente(estado: dict, tipo: str, hoy: date, dias: int) -> bool:
    return any(d["tipo"] == tipo and (hoy - date.fromisoformat(d["fecha"])).days < dias
               for d in estado.get("decisiones", []))


def _proponer(estado: dict, tipo: str, hoy: date, dias: int = DIAS_ENTRE_DECISIONES) -> None:
    if estado.get("decision") is None and not _reciente(estado, tipo, hoy, dias):
        estado["decision"] = {"tipo": tipo, "club": estado["actual"], "fecha": hoy.isoformat()}


def actualizar(estado: Optional[dict], carrera: Carrera, reputacion: int) -> tuple[dict, list[Hito]]:
    """El estado al dia de la partida (una copia) y lo que es noticia. La
    primera vez solo registra el club (los partidos viejos no cuentan)."""
    estado = copy.deepcopy(estado or {})
    # el club del contrato: cambia apenas se firma el traspaso (el de los
    # partidos recien cambia cuando juega el primero con el club nuevo)
    equipo, hoy = carrera.club_de(carrera.usuario_id) if carrera.usuario_id else None, carrera.fecha_actual()
    if equipo is None or carrera.es_agentes_libres(equipo):
        equipo = carrera.equipo_usuario()  # sin contrato (o libre): el ultimo club con el que jugo
    if equipo is None or hoy is None:
        return estado, []
    estado.setdefault("clubes", {})
    jugados = carrera.partidos_de(equipo, jugados=True)
    if not estado.get("actual"):
        estado["clubes"][str(equipo)] = _club_nuevo(carrera, equipo, hoy)
        estado["actual"] = str(equipo)
        estado["hasta"] = jugados[-1].fecha.isoformat() if jugados else hoy.isoformat()
        return estado, []
    hitos = []
    if estado["actual"] != str(equipo):
        hitos = _cambio_de_club(estado, carrera, equipo, hoy)
        estado["hasta"] = hoy.isoformat()  # lo que jugo el club nuevo antes de que llegaras no cuenta
        if estado.get("decision") and estado["decision"]["club"] != estado["actual"]:
            estado["decision"] = None  # la decision era sobre el club de antes
    club = estado["clubes"][estado["actual"]]
    hasta = estado.get("hasta") or ""
    for partido in (p for p in jugados if p.fecha.isoformat() > hasta):
        suya = next((a for a in carrera.actuaciones_en(partido) if a.jugador == carrera.usuario_id), None)
        _acotar(club, carino_por_partido(partido.resultado_para(equipo), suya is not None,
                                         suya.goles if suya else 0, suya.nota if suya else None))
    if jugados:
        estado["hasta"] = max(hasta, jugados[-1].fecha.isoformat())
    if club["carino"] < EN_CONTRA:
        _proponer(estado, "en_contra", hoy)
    elif club["carino"] >= TENTADO_CARINO and reputacion >= TENTADO_REPUTACION:
        _proponer(estado, "tentado", hoy, dias=DIAS_ENTRE_TENTACIONES)
    return estado, hitos


def por_evento(estado: Optional[dict], evento_id: str, hoy: date) -> dict:
    """Lo que un evento inesperado le hace al carino de tu hinchada, y si
    abre la decision de la polemica."""
    estado = copy.deepcopy(estado or {})
    if not estado.get("actual"):
        return estado
    _acotar(estado["clubes"][estado["actual"]], POR_EVENTO.get(evento_id, 0))
    if evento_id in EVENTOS_POLEMICOS:
        _proponer(estado, "polemica", hoy)
    return estado


# ---- contestar una decision ----


def decision_pendiente(estado: dict) -> Optional[tuple[Decision, str]]:
    """(la decision, el nombre del club) si hay una esperando respuesta."""
    pendiente = (estado or {}).get("decision")
    if not pendiente:
        return None
    club = estado["clubes"].get(pendiente["club"], {}).get("nombre", "tu club")
    return DECISIONES[pendiente["tipo"]], club


def elegir(estado: dict, opcion_id: str, hoy: date) -> tuple[dict, Hito, int]:
    """(estado nuevo, el hito para la prensa, cuanto cambio el carino)."""
    estado = copy.deepcopy(estado)
    pendiente = estado["decision"]
    decision = DECISIONES[pendiente["tipo"]]
    opcion = next(o for o in decision.opciones if o.id == opcion_id)
    club = estado["clubes"][pendiente["club"]]
    antes = club["carino"]
    _acotar(club, opcion.carino)
    estado["decision"] = None
    estado.setdefault("decisiones", []).insert(
        0, {"tipo": pendiente["tipo"], "club": pendiente["club"], "fecha": hoy.isoformat(), "eleccion": opcion.id})
    del estado["decisiones"][DECISIONES_GUARDADAS:]
    hito = Hito("eleccion", opcion.texto, opcion.noticia.format(club=club["nombre"]), opcion.tono, opcion.seguidores,
                opcion.reputacion, opcion.reto)
    return estado, hito, club["carino"] - antes
