"""
Vida sentimental: la pareja del jugador y lo que pasa con ella a medida que
pasan las semanas del juego, con decisiones que toma el usuario.

Arranca de lo que se eligio al crear el personaje (models.ESTADOS_RELACION):
- "novia_real": en pareja con su novia de la vida real (`nombre_pareja`).
  Es una persona real: con ella solo pasan cosas lindas o roces leves
  (una cena, la tribuna, una discusion por tantos viajes), nunca escandalos,
  rumores ni infidelidades. La prensa la trata con respeto.
- "celebridad": soltero, y es probable que lo vean con una famosa.
- "soltero": soltero; una famosa es posible, pero menos.

Las famosas son INVENTADAS (nombre, apellido y oficio se arman con listas
propias): nunca una persona real. Con ellas si hay prensa del corazon:
rumores, alfombras rojas, crisis.

El estado de la relacion (0-100) se mueve con lo que pasa, y cuando la
historia lo pide aparece una decision: hacer oficial el romance con la
famosa o negarlo, proponer casamiento (con anillo: cuesta), la boda (a lo
grande o intima) y que hacer en una crisis (darle prioridad o terminar).
Lo que provoca (relacion, seguidores, reputacion, plata) lo decide el
codigo; la noticia y los comentarios, el motor narrativo (eventos.contar).

Como los eventos inesperados, se sortea una vez por semana del juego con
una semilla propia (jugador + semana), a lo sumo una cosa por revision.

Estado en estado_json.amor:
{"estado": soltero | conociendo | pareja | comprometido | casado,
 "pareja": {"nombre", "real": bool, "oficio", "desde", "relacion"} o None,
 "hasta": dia del juego hasta donde se sorteo,
 "decision": {"tipo", "fecha"} o None,
 "historial": [{"id", "fecha", "titulo", "tono", "relacion", "seguidores", "dinero", "reputacion"}]}
"""

import copy
import random
import uuid
from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Optional

from roleplay.models import PlayerProfile
from roleplay.servicios import economia

PROBABILIDAD_POR_SEMANA = 0.25
HISTORIAL_GUARDADO = 20
SIN_REPETIR = 3
RELACION_INICIAL = 70
CRISIS = 25
PROPONER_DESDE_RELACION, PROPONER_DESDE_DIAS = 80, 180
BODA_DESDE_DIAS = 120

NOMBRES = ["Valentina", "Camila", "Lucia", "Martina", "Renata", "Julieta", "Emilia", "Antonella", "Catalina",
           "Florencia", "Agustina", "Paloma", "Bianca", "Alma", "Ines", "Olivia"]
APELLIDOS = ["Roca", "Ferrer", "Montiel", "Duarte", "Valdes", "Ibarra", "Quiroga", "Lagos", "Arriaga", "Belmonte",
             "Cisneros", "Solano", "Varela", "Zamora", "Prado", "Linares"]
OFICIOS = ["cantante pop", "actriz de series", "modelo", "influencer de moda", "conductora de TV", "tenista",
           "cantante de reggaeton", "actriz de cine"]


def rotulo(relacion: int) -> str:
    if relacion >= 75:
        return "Muy bien"
    if relacion >= 50:
        return "Bien"
    if relacion >= CRISIS:
        return "Con altibajos"
    return "En crisis"


@dataclass(frozen=True)
class Momento:
    """Algo que pasa con la pareja (o con una famosa)."""

    id: str
    titulo: str  # {pareja}, {oficio}
    detalle: str  # para la prensa (tercera persona, despues del nombre del jugador)
    tono: str
    relacion: int
    seguidores: float  # veces la escala de la hinchada
    semanas: float = 0.0  # plata: semanas de sueldo neto (- paga)
    para: tuple = ("pareja",)  # pareja | pareja_famosa | soltero | conociendo
    meses: tuple = ()  # solo en esos meses (las vacaciones, en el verano europeo)
    reputacion: int = 0


MOMENTOS = [
    Momento("cena", "Cena romantica con {pareja}", "salio a cenar con {pareja} y los fotografiaron muy sonrientes",
            "positiva", 5, 0.3),
    Momento("tribuna", "{pareja} en la tribuna: la camara los enfoca",
            "dedico su partido a {pareja}, que lo alentaba desde la tribuna", "positiva", 4, 1.0),
    Momento("vacaciones", "Vacaciones con {pareja}", "se fue de vacaciones con {pareja} antes de la pretemporada",
            "positiva", 8, 1.2, -1.5, meses=(6, 7)),
    Momento("regalo", "Un viaje sorpresa para {pareja}", "le regalo a {pareja} un viaje sorpresa", "positiva", 7, 0.5, -1.0),
    Momento("distancia", "Roces con {pareja} por tantos viajes",
            "tiene roces con {pareja}: entre partidos y concentraciones casi no se ven", "mixta", -8, 0.1),
    Momento("aniversario", "Aniversario con {pareja}", "festejo un aniversario mas con {pareja}", "positiva", 6, 0.8),
    # solo con una famosa (inventada): prensa del corazon
    Momento("alfombra", "Alfombra roja con {pareja}", "fue con {pareja}, {oficio}, a la alfombra roja de un estreno",
            "positiva", 3, 2.0, para=("pareja_famosa",)),
    Momento("rumores_crisis", "Rumores de crisis con {pareja}",
            "esta en boca de todos: dicen que las cosas con {pareja} no andan bien", "mixta", -7, 0.9,
            para=("pareja_famosa",)),
    Momento("entrevista_famosa", "{pareja} habla de el en una entrevista",
            "aparecio en una entrevista de {pareja}, {oficio}, que hablo maravillas de el", "positiva", 5, 1.5,
            para=("pareja_famosa",)),
    # soltero: lo ven con una famosa
    Momento("lo_ven", "Lo ven cenando con {pareja}, {oficio}",
            "fue visto cenando a solas con {pareja}, {oficio}, y estallaron los rumores", "mixta", 0, 1.5,
            para=("soltero",)),
    Momento("rumores", "Mas rumores con {pareja}", "fue visto otra vez con {pareja}, {oficio}", "mixta", 0, 0.8,
            para=("conociendo",)),
]
POR_ID = {m.id: m for m in MOMENTOS}


@dataclass(frozen=True)
class Opcion:
    id: str
    texto: str
    noticia: str  # {pareja}
    tono: str
    relacion: int
    seguidores: float
    semanas: float = 0.0
    reputacion: int = 0
    estado: str = ""  # el estado nuevo ("" = igual)


@dataclass(frozen=True)
class Decision:
    titulo: str
    pregunta: str
    opciones: tuple


DECISIONES = {
    "oficial": Decision(
        "Todos preguntan por vos y {pareja}", "Los rumores no paran. Lo haces oficial?",
        (Opcion("oficializar", "Hacerlo oficial", "confirmo su romance con {pareja}", "positiva", 0, 3.0, estado="pareja"),
         Opcion("negar", "Negarlo todo", "nego cualquier romance con {pareja}", "neutral", 0, 0.3, estado="soltero")),
    ),
    "proponer": Decision(
        "Le propones casamiento a {pareja}?", "Llevan un buen tiempo juntos y todo anda muy bien.",
        (Opcion("anillo", "Si, con anillo y todo", "le propuso casamiento a {pareja}", "positiva", 15, 2.0, -6.0, 1,
                estado="comprometido"),
         Opcion("todavia", "Todavia no", "decidio esperar para dar el paso con {pareja}", "neutral", -5, 0)),
    ),
    "boda": Decision(
        "Llega la boda con {pareja}", "Como la quieren?",
        (Opcion("grande", "A lo grande", "se caso con {pareja} en una fiesta enorme", "positiva", 10, 3.0, -25.0,
                estado="casado"),
         Opcion("intima", "Algo intimo, solo la familia", "se caso con {pareja} en una ceremonia intima", "positiva", 12,
                1.5, -5.0, 1, estado="casado")),
    ),
    "crisis": Decision(
        "Las cosas con {pareja} no andan bien", "La relacion esta en crisis. Que haces?",
        (Opcion("prioridad", "Darle prioridad a la relacion", "dejo todo de lado para recomponer su relacion con {pareja}",
                "positiva", 25, 0.3),
         Opcion("terminar", "Terminar", "termino su relacion con {pareja}", "negativa", 0, 1.0, estado="soltero")),
    ),
}


@dataclass
class Suceso:
    """Algo que paso (un momento o una decision), listo para la prensa."""

    titulo: str
    detalle: str  # tercera persona, despues del nombre del jugador
    tono: str
    seguidores: float  # veces la escala
    relacion: int = 0
    dinero: int = 0
    reputacion: int = 0
    fecha: Optional[date] = None
    clave: str = ""  # para el hito de la prensa
    id: str = field(default_factory=lambda: uuid.uuid4().hex[:8])


# ---- el arranque ----


def inicial(perfil: PlayerProfile, hoy: date) -> dict:
    if perfil.estado_relacion == "novia_real" and perfil.nombre_pareja.strip():
        pareja = {"nombre": perfil.nombre_pareja.strip(), "real": True, "oficio": "", "desde": hoy.isoformat(),
                  "relacion": RELACION_INICIAL}
        return {"estado": "pareja", "pareja": pareja, "hasta": hoy.isoformat(), "decision": None, "historial": []}
    return {"estado": "soltero", "pareja": None, "hasta": hoy.isoformat(), "decision": None, "historial": []}


def famosa_inventada(dado: random.Random) -> dict:
    return {"nombre": f"{dado.choice(NOMBRES)} {dado.choice(APELLIDOS)}", "real": False, "oficio": dado.choice(OFICIOS),
            "desde": "", "relacion": 50}


# ---- el sorteo semanal ----


def _clase(estado: dict) -> str:
    if estado["estado"] in ("pareja", "comprometido", "casado"):
        return "pareja_famosa" if not estado["pareja"]["real"] else "pareja"
    return estado["estado"]  # soltero | conociendo


def posibles(perfil: PlayerProfile, estado: dict, semana: date) -> list[tuple[Momento, float]]:
    clase = _clase(estado)
    recientes = [h.get("momento") for h in estado.get("historial", [])[:SIN_REPETIR]]
    resultado = []
    for momento in MOMENTOS:
        aplica = clase in momento.para or (clase == "pareja_famosa" and "pareja" in momento.para)
        if not aplica or momento.id in recientes or (momento.meses and semana.month not in momento.meses):
            continue
        peso = 1.0
        if momento.id == "lo_ven":
            peso = 3.0 if perfil.estado_relacion == "celebridad" else 0.6
        resultado.append((momento, peso))
    return resultado


def _proponer(estado: dict, hoy: date) -> None:
    if estado.get("decision"):
        return
    pareja = estado.get("pareja")
    tipo = None
    if estado["estado"] == "conociendo":
        tipo = "oficial"
    elif pareja and pareja["relacion"] < CRISIS:
        tipo = "crisis"
    elif estado["estado"] == "pareja" and pareja["relacion"] >= PROPONER_DESDE_RELACION and pareja.get("desde") and \
            (hoy - date.fromisoformat(pareja["desde"])).days >= PROPONER_DESDE_DIAS and \
            not any(h.get("decision") == "proponer" and (hoy - date.fromisoformat(h["fecha"])).days < 180
                    for h in estado.get("historial", [])):
        tipo = "proponer"
    elif estado["estado"] == "comprometido" and (hoy - date.fromisoformat(estado.get("comprometidos", hoy.isoformat()))
                                                 ).days >= BODA_DESDE_DIAS:
        tipo = "boda"
    if tipo:
        estado["decision"] = {"tipo": tipo, "fecha": hoy.isoformat()}


def _anotar(estado: dict, suceso: Suceso, extra: dict) -> None:
    historial = estado.setdefault("historial", [])
    historial.insert(0, {"id": suceso.id, "fecha": suceso.fecha.isoformat(), "titulo": suceso.titulo, "tono": suceso.tono,
                         "relacion": suceso.relacion, "dinero": suceso.dinero, "reputacion": suceso.reputacion, **extra})
    del historial[HISTORIAL_GUARDADO:]


def _cobrar(e: dict, suceso: Suceso) -> None:
    if suceso.dinero and e:
        e["saldo"] = e.get("saldo", 0) + suceso.dinero
        economia._movimiento(e, suceso.fecha, suceso.titulo, suceso.dinero)


def revisar(perfil: PlayerProfile, estado: Optional[dict], e: dict, hoy: date) -> tuple[dict, dict, list[Suceso]]:
    """(estado nuevo, economia nueva, lo que paso) al dia `hoy` del juego.
    La primera vez arranca del personaje y solo marca desde donde contar."""
    if not estado:
        return inicial(perfil, hoy), copy.deepcopy(e or {}), []
    estado, e = copy.deepcopy(estado), copy.deepcopy(e or {})
    if hoy < date.fromisoformat(estado["hasta"]):
        estado["hasta"] = hoy.isoformat()  # se cargo una partida anterior
        return estado, e, []
    desde = date.fromisoformat(estado["hasta"])
    semanas = (hoy - desde).days // 7
    if semanas <= 0:
        return estado, e, []
    estado["hasta"] = (desde + timedelta(days=7 * semanas)).isoformat()
    sucesos = []
    for i in range(semanas):
        semana = desde + timedelta(days=7 * i)
        dado = random.Random(f"amor:{perfil.id}:{semana.isoformat()}")
        opciones = posibles(perfil, estado, semana)
        if not opciones or dado.random() >= PROBABILIDAD_POR_SEMANA:
            continue
        momento = dado.choices([m for m, _ in opciones], weights=[p for _, p in opciones])[0]
        if momento.id == "lo_ven":
            estado["pareja"] = famosa_inventada(dado)
            estado["estado"] = "conociendo"
        pareja = estado["pareja"]
        datos = {"pareja": pareja["nombre"], "oficio": pareja.get("oficio", "")}
        suceso = Suceso(momento.titulo.format(**datos), momento.detalle.format(**datos), momento.tono,
                        momento.seguidores, momento.relacion,
                        round(momento.semanas * e.get("sueldo", 0) * economia.NETO), momento.reputacion,
                        fecha=min(semana + timedelta(days=7), hoy), clave=f"amor:{momento.id}")
        if estado["estado"] in ("pareja", "comprometido", "casado"):
            pareja["relacion"] = max(0, min(100, pareja["relacion"] + momento.relacion))
        _cobrar(e, suceso)
        _anotar(estado, suceso, {"momento": momento.id})
        sucesos.append(suceso)
        break  # a lo sumo una cosa por revision
    _proponer(estado, hoy)
    return estado, e, sucesos


# ---- contestar una decision ----


def decision_pendiente(estado: Optional[dict]) -> Optional[tuple[Decision, str]]:
    pendiente = (estado or {}).get("decision")
    if not pendiente:
        return None
    return DECISIONES[pendiente["tipo"]], (estado.get("pareja") or {}).get("nombre", "")


def elegir(estado: dict, e: dict, opcion_id: str, hoy: date) -> tuple[dict, dict, Suceso]:
    estado, e = copy.deepcopy(estado), copy.deepcopy(e or {})
    tipo = estado["decision"]["tipo"]
    decision = DECISIONES[tipo]
    opcion = next(o for o in decision.opciones if o.id == opcion_id)
    pareja = estado["pareja"]
    nombre = pareja["nombre"]
    suceso = Suceso(opcion.texto, opcion.noticia.format(pareja=nombre), opcion.tono, opcion.seguidores, opcion.relacion,
                    round(opcion.semanas * e.get("sueldo", 0) * economia.NETO), opcion.reputacion, fecha=hoy,
                    clave=f"amor:{tipo}:{opcion.id}")
    pareja["relacion"] = max(0, min(100, pareja["relacion"] + opcion.relacion))
    if pareja["real"] and suceso.tono == "negativa":
        suceso.tono = "neutral"  # con una persona real, nada de drama en la prensa
    if opcion.estado == "soltero":
        estado["pareja"] = None
    elif opcion.estado == "pareja" and estado["estado"] == "conociendo":
        pareja.update(desde=hoy.isoformat(), relacion=60)
    if opcion.estado == "comprometido":
        estado["comprometidos"] = hoy.isoformat()
    if opcion.estado:
        estado["estado"] = opcion.estado
    estado["decision"] = None
    _cobrar(e, suceso)
    _anotar(estado, suceso, {"decision": tipo, "eleccion": opcion.id})
    return estado, e, suceso
