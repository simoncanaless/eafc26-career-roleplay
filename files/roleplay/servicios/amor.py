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

Las famosas salen del catalogo de Simon (roleplay/datos/famosas_ig.json, via
servicios/ecosistema.py): los datos son suyos y su responsabilidad (lo
decidio el 2026-10-19); la app solo los lee. Sin el archivo, se inventan
(NOMBRES x APELLIDOS x OFICIOS). Con ellas hay prensa del corazon: rumores,
alfombras rojas, crisis.

Fama (ecosistema.calcular_fama_jugador: reputacion + tier del club + goles
+ premios) contra la `exigencia` de cada celebridad:
- soltero, puede buscar en el catalogo y mandar un DM (uno por semana del
  juego). La chance de que conteste (`probabilidad_de_exito`) sale de su fama
  contra la exigencia, con un margen: alcanzarla da ~85%, pasarla casi seguro,
  quedarse corto la baja rapido. Si contesta, elige: mantenerlo en SECRETO
  (nada sale en la prensa, pero los periodistas preguntan por los rumores; se
  puede oficializar cuando quiera con `oficializar`) o hacerlo OFICIAL. Si no,
  visto; y cuanto mas lejos estaba, mas probable que la captura se filtre a
  los portales de chismes (`probabilidad_de_filtracion`: chisme publico,
  reputacion -1 y burlas).
- a los que lo "ven con una famosa" (sorteo semanal), solo les toca alguien
  de su nivel.
- un romance secreto, al mes, pide decidir si sale a la luz.

El estado de la relacion (0-100) se mueve con lo que pasa, y cuando la
historia lo pide aparece una decision: hacer oficial el romance con la
famosa o negarlo, proponer casamiento (con anillo: cuesta), la boda (a lo
grande o intima) y que hacer en una crisis (darle prioridad o terminar).
Lo que provoca (relacion, seguidores, reputacion, plata) lo decide el
codigo; la noticia y los comentarios, el motor narrativo (eventos.contar).

Como los eventos inesperados, se sortea una vez por semana del juego con
una semilla propia (jugador + semana), a lo sumo una cosa por revision.

Estado en estado_json.amor:
{"estado": soltero | conociendo | secreto | pareja | comprometido | casado,
 "pareja": {"nombre", "real": bool, "oficio", "desde", "relacion",
            ("usuario_ig", "categoria", "exigencia": las del catalogo)} o None,
 "ultimo_dm": dia del juego del ultimo DM,
 "hasta": dia del juego hasta donde se sorteo,
 "decision": {"tipo", "fecha"} o None,
 "historial": [{"id", "fecha", "titulo", "tono", "relacion", "seguidores", "dinero", "reputacion"}]}
"""

import copy
import os
import random
import uuid
from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Optional

from roleplay.models import PlayerProfile
from roleplay.servicios import ecosistema, economia

PROBABILIDAD_POR_SEMANA = 0.25
HISTORIAL_GUARDADO = 20
SIN_REPETIR = 3
RELACION_INICIAL = 70
CRISIS = 25
PROPONER_DESDE_RELACION, PROPONER_DESDE_DIAS = 80, 180
BODA_DESDE_DIAS = 120
DM_CADA_DIAS = 7  # un DM por semana del juego
EXITO_AL_ALCANZAR = 0.85  # chance de que conteste si su fama justo alcanza la exigencia
EXITO_POR_PUNTO = 0.03  # cuanto sube (o baja) por cada punto de fama de diferencia
EXITO_MINIMO, EXITO_MAXIMO = 0.03, 0.97
FILTRACION_DESDE = 10  # puntos de diferencia desde los que un visto puede filtrarse
FILTRACION_POR_PUNTO = 1 / 30
FILTRACION_MAXIMA = 0.9
SECRETO_DECIDIR_DIAS = 30

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
    # romance secreto: lo de adentro no sale en la prensa (privado) y lo de afuera son rumores sin nombre
    Momento("escapada", "Escapada secreta con {pareja}", "se escapo unos dias con {pareja} sin que nadie se entere",
            "positiva", 6, 0.0, para=("secreto",)),
    Momento("mensajes", "Mensajes a toda hora con {pareja}", "no suelta el telefono: habla todo el dia con {pareja}",
            "positiva", 4, 0.0, para=("secreto",)),
    Momento("casi_descubiertos", "Casi los descubren", "estuvo a punto de ser fotografiado con alguien famoso: "
            "las redes sospechan de un romance secreto", "mixta", -2, 0.6, para=("secreto",)),
]
PRIVADOS = {"escapada", "mensajes"}  # no salen en la prensa
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
    privado: bool = False  # no sale en la prensa


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
    "como_seguir": Decision(
        "{pareja} te contesto", "Le gustaste. Lo mantienen en secreto o lo hacen oficial?",
        (Opcion("secreto", "Mantenerlo en secreto", "empezo algo en secreto con {pareja}", "positiva", 5, 0,
                estado="secreto", privado=True),
         Opcion("oficial", "Hacerlo oficial", "confirmo su romance con {pareja}", "positiva", 0, 3.0, estado="pareja")),
    ),
    "salir_a_la_luz": Decision(
        "Un mes en secreto con {pareja}", "Lo siguen escondiendo o lo hacen publico?",
        (Opcion("publico", "Hacerlo publico", "hizo publico su romance con {pareja}", "positiva", 5, 3.0, estado="pareja"),
         Opcion("seguir_secreto", "Seguir en secreto", "sigue escondiendo su romance con {pareja}", "neutral", -3, 0,
                estado="secreto", privado=True)),
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
    privado: bool = False  # queda en su historial, sin prensa ni seguidores


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


def de_catalogo(celebridad: dict) -> dict:
    """La pareja que sale de una entrada del catalogo de Simon."""
    return {"nombre": str(celebridad.get("nombre", "")).strip(), "real": False,
            "oficio": str(celebridad.get("oficio", "")).strip(), "usuario_ig": celebridad.get("usuario_ig", ""),
            "categoria": celebridad.get("categoria", ""), "exigencia": exigencia(celebridad), "desde": "",
            "relacion": 50}


def exigencia(celebridad: dict) -> int:
    return ecosistema.numero(celebridad.get("exigencia"), 50)


def famosa_para(fama: int, dado: random.Random) -> dict:
    """Alguien de su nivel (del catalogo; si no hay catalogo, inventada)."""
    alcanzables = [c for c in ecosistema.celebridades() if exigencia(c) <= fama]
    if not alcanzables:
        return famosa_inventada(dado)
    return de_catalogo(dado.choices(alcanzables, weights=[1 + exigencia(c) / 20 for c in alcanzables])[0])


def buscar(texto: str = "", categoria: str = "", limite: int = 40) -> list[dict]:
    """El catalogo filtrado por nombre o @usuario y por categoria (de mas a menos exigente)."""
    texto = texto.strip().lower().lstrip("@")
    encontradas = [
        c for c in ecosistema.celebridades()
        if (not categoria or c.get("categoria") == categoria)
        and (not texto or texto in str(c.get("nombre", "")).lower() or texto in str(c.get("usuario_ig", "")).lower())
    ]
    return sorted(encontradas, key=exigencia, reverse=True)[:limite]


def categorias() -> list[str]:
    return sorted({c.get("categoria") for c in ecosistema.celebridades() if c.get("categoria")})


def puede_mandar_dm(estado: Optional[dict], hoy: date) -> bool:
    estado = estado or {}
    if estado.get("estado", "soltero") != "soltero" or estado.get("decision"):
        return False
    ultimo = estado.get("ultimo_dm")
    if os.environ.get("EAFC_DM_SIN_ESPERA") == "1":
        return True  # solo la partida de prueba (scripts/partida_de_prueba.py): ahi el juego no avanza
    return not ultimo or (hoy - date.fromisoformat(ultimo)).days >= DM_CADA_DIAS


def probabilidad_de_exito(fama: int, exigencia_: int) -> float:
    """La chance de que conteste el DM (0-1): ~85% si la fama justo alcanza."""
    return max(EXITO_MINIMO, min(EXITO_MAXIMO, EXITO_AL_ALCANZAR + EXITO_POR_PUNTO * (fama - exigencia_)))


def probabilidad_de_filtracion(fama: int, exigencia_: int) -> float:
    """Si lo deja en visto: la chance de que la captura llegue a los portales de chismes."""
    return max(0.0, min(FILTRACION_MAXIMA, (exigencia_ - fama - FILTRACION_DESDE) * FILTRACION_POR_PUNTO))


def intentar(estado: dict, e: dict, celebridad: dict, fama: int, hoy: date,
             dado: Optional[random.Random] = None) -> tuple[dict, dict, Suceso]:
    """Mandarle un DM a alguien del catalogo. Con `probabilidad_de_exito`
    contesta (y hay que decidir: secreto u oficial); si no, visto, y quizas la
    captura se filtra (`probabilidad_de_filtracion`)."""
    if not puede_mandar_dm(estado, hoy):
        raise ValueError("Ahora no podes mandar otro DM.")
    estado, e = copy.deepcopy(estado), copy.deepcopy(e or {})
    estado["ultimo_dm"] = hoy.isoformat()
    pareja = de_catalogo(celebridad)
    nombre, oficio = pareja["nombre"], pareja["oficio"] or "celebridad"
    dado = dado or random.Random(f"dm:{nombre}:{hoy.isoformat()}:{fama}")
    if dado.random() < probabilidad_de_exito(fama, pareja["exigencia"]):
        estado["estado"], estado["pareja"] = "conociendo", pareja
        estado["decision"] = {"tipo": "como_seguir", "fecha": hoy.isoformat()}
        suceso = Suceso(f"{nombre} te contesto el DM", f"recibio respuesta de {nombre}, {oficio}", "positiva", 0,
                        fecha=hoy, clave="amor:dm:si", privado=True)
    elif dado.random() < probabilidad_de_filtracion(fama, pareja["exigencia"]):
        suceso = Suceso(f"{nombre} lo dejo en visto", f"le escribio a {nombre}, {oficio}, y lo dejo en visto: "
                        "la captura del chat llego a los portales de chismes y las redes se burlan", "negativa", 0.4,
                        reputacion=-1, fecha=hoy, clave="amor:dm:visto")
    else:
        suceso = Suceso(f"{nombre} no contesto", f"le escribio a {nombre}, {oficio}, y no hubo respuesta", "neutral", 0,
                        fecha=hoy, clave="amor:dm:no", privado=True)
    _anotar(estado, suceso, {"dm": pareja.get("usuario_ig") or nombre})
    return estado, e, suceso


# ---- el sorteo semanal ----


def _clase(estado: dict) -> str:
    if estado["estado"] == "secreto":
        return "secreto"
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
    elif estado["estado"] == "secreto" and pareja.get("desde") and \
            (hoy - date.fromisoformat(pareja["desde"])).days >= SECRETO_DECIDIR_DIAS and \
            (hoy - date.fromisoformat(estado.get("secreto_revisado", pareja["desde"]))).days >= SECRETO_DECIDIR_DIAS:
        tipo = "salir_a_la_luz"
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


def revisar(perfil: PlayerProfile, estado: Optional[dict], e: dict, hoy: date,
            fama: int = 50) -> tuple[dict, dict, list[Suceso]]:
    """(estado nuevo, economia nueva, lo que paso) al dia `hoy` del juego.
    La primera vez arranca del personaje y solo marca desde donde contar.
    `fama`: a quien le puede tocar "lo ven con" (servicios/ecosistema)."""
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
            estado["pareja"] = famosa_para(fama, dado)
            estado["estado"] = "conociendo"
        pareja = estado["pareja"]
        datos = {"pareja": pareja["nombre"], "oficio": pareja.get("oficio", "")}
        suceso = Suceso(momento.titulo.format(**datos), momento.detalle.format(**datos), momento.tono,
                        momento.seguidores, momento.relacion,
                        round(momento.semanas * e.get("sueldo", 0) * economia.NETO), momento.reputacion,
                        fecha=min(semana + timedelta(days=7), hoy), clave=f"amor:{momento.id}",
                        privado=momento.id in PRIVADOS)
        if estado["estado"] in ("pareja", "comprometido", "casado", "secreto"):
            pareja["relacion"] = max(0, min(100, pareja["relacion"] + momento.relacion))
        _cobrar(e, suceso)
        _anotar(estado, suceso, {"momento": momento.id})
        sucesos.append(suceso)
        break  # a lo sumo una cosa por revision
    _proponer(estado, hoy)
    return estado, e, sucesos


def oficializar(estado: dict, e: dict, hoy: date) -> tuple[dict, dict, Suceso]:
    """Hacer publico un romance secreto cuando quiera (no hace falta esperar la decision)."""
    if (estado or {}).get("estado") != "secreto" or not estado.get("pareja"):
        raise ValueError("No hay un romance secreto para oficializar.")
    estado = copy.deepcopy(estado)
    estado["decision"] = {"tipo": "salir_a_la_luz", "fecha": hoy.isoformat()}
    return elegir(estado, e, "publico", hoy)


# ---- interactuar con la pareja (como en BitLife o Los Sims) ----

INTERACCION_CADA_DIAS = 7  # cada cosa, una vez por semana del juego


@dataclass(frozen=True)
class Accion:
    id: str
    texto: str  # el boton
    titulo: str  # para la prensa: {pareja}
    detalle: str  # tercera persona, despues del nombre del jugador
    relacion: int
    semanas: float  # cuanto cuesta, en semanas de sueldo neto
    seguidores: float  # veces la escala de la hinchada (x3 con una pareja famosa)
    publica: bool = False  # se publica en redes: con un romance secreto no se puede
    solo_casados: bool = False  # y una sola vez (la foto de la boda)


ACCIONES = {
    "cena": Accion("cena", "Invitar a cenar", "Cena con {pareja}", "salio a cenar con {pareja}", 4, 0.05, 0.2),
    "regalo": Accion("regalo", "Hacer un regalo", "Un regalo para {pareja}", "le hizo un regalo a {pareja}", 6, 0.3, 0.1),
    "regalo_lujo": Accion("regalo_lujo", "Regalo de lujo", "Una joya para {pareja}", "le regalo una joya a {pareja}", 12,
                          2.0, 0.6),
    "escapada": Accion("escapada", "Escapada de fin de semana", "Escapada con {pareja}",
                       "se escapo un fin de semana con {pareja}", 10, 1.0, 0.8),
    "foto": Accion("foto", "Subir una foto juntos", "{pareja} y el, la foto del dia",
                   "subio una foto con {pareja} y las redes explotaron", 5, 0.0, 2.5, publica=True),
    "foto_boda": Accion("foto_boda", "Subir la boda a Instagram", "Las fotos de la boda con {pareja}",
                        "subio las fotos de su boda con {pareja}", 5, 0.0, 4.0, publica=True, solo_casados=True),
}
PAREJA_ACTIVA = ("pareja", "secreto", "comprometido", "casado")


def _sin_espera() -> bool:
    return os.environ.get("EAFC_DM_SIN_ESPERA") == "1"  # la partida de prueba: el juego no avanza


def _dias_desde(fecha: str, hoy: date) -> int:
    try:
        return (hoy - date.fromisoformat(fecha)).days
    except (TypeError, ValueError):
        return 0


def puede_interactuar(estado: Optional[dict], accion_id: str, hoy: date) -> tuple[bool, str]:
    """(si se puede, por que no)."""
    estado = estado or {}
    accion = ACCIONES[accion_id]
    if estado.get("estado") not in PAREJA_ACTIVA or not estado.get("pareja"):
        return False, "No estas en pareja."
    if accion.publica and estado["estado"] == "secreto":
        return False, "Es un romance secreto: para publicar juntos, primero hacelo oficial."
    ultima = (estado.get("interacciones") or {}).get(accion_id)
    if accion.solo_casados:
        if estado["estado"] != "casado":
            return False, "Primero, la boda."
        if ultima and _dias_desde(ultima, hoy) >= 0 and ultima >= estado.get("casados", ""):
            return False, "Ya subiste las fotos de la boda."
    elif ultima and not _sin_espera() and _dias_desde(ultima, hoy) < INTERACCION_CADA_DIAS:
        return False, "Ya lo hiciste esta semana del juego."
    return True, ""


def interactuar(estado: dict, e: dict, accion_id: str, hoy: date) -> tuple[dict, dict, Suceso]:
    ok, motivo = puede_interactuar(estado, accion_id, hoy)
    if not ok:
        raise ValueError(motivo)
    estado, e = copy.deepcopy(estado), copy.deepcopy(e or {})
    accion = ACCIONES[accion_id]
    costo = round(accion.semanas * e.get("sueldo", 0) * economia.NETO)
    if costo > e.get("saldo", 0):
        raise ValueError("No te alcanza la plata.")
    pareja = estado["pareja"]
    datos = {"pareja": pareja["nombre"]}
    famosa = not pareja.get("real")
    secreto = estado["estado"] == "secreto"
    seguidores = 0 if secreto else accion.seguidores * (3 if famosa and accion.publica else 1)
    suceso = Suceso(accion.titulo.format(**datos), accion.detalle.format(**datos), "positiva", seguidores,
                    accion.relacion, -costo, fecha=hoy,
                    clave=f"amor:{accion_id}", privado=secreto)
    pareja["relacion"] = max(0, min(100, pareja.get("relacion", 50) + accion.relacion))
    estado.setdefault("interacciones", {})[accion_id] = hoy.isoformat()
    _cobrar(e, suceso)
    _anotar(estado, suceso, {"accion": accion_id})
    return estado, e, suceso


def costo_de(accion_id: str, e: Optional[dict]) -> int:
    return round(ACCIONES[accion_id].semanas * (e or {}).get("sueldo", 0) * economia.NETO)


def puede_proponer(estado: Optional[dict], hoy: date) -> tuple[bool, str]:
    estado = estado or {}
    pareja = estado.get("pareja") or {}
    if estado.get("estado") != "pareja" or not pareja:
        return False, "Para proponer casamiento tienen que estar en pareja (y no en secreto)."
    if _sin_espera():
        return True, ""
    if pareja.get("relacion", 0) < PROPONER_DESDE_RELACION:
        return False, f"La relacion tiene que estar en {PROPONER_DESDE_RELACION} o mas."
    if _dias_desde(pareja.get("desde", ""), hoy) < PROPONER_DESDE_DIAS:
        return False, f"Tienen que llevar {PROPONER_DESDE_DIAS} dias juntos."
    return True, ""


def proponer(estado: dict, e: dict, hoy: date) -> tuple[dict, dict, Suceso]:
    ok, motivo = puede_proponer(estado, hoy)
    if not ok:
        raise ValueError(motivo)
    estado = copy.deepcopy(estado)
    estado["decision"] = {"tipo": "proponer", "fecha": hoy.isoformat()}
    return elegir(estado, e, "anillo", hoy)


def puede_casarse(estado: Optional[dict], hoy: date) -> tuple[bool, str]:
    estado = estado or {}
    if estado.get("estado") != "comprometido":
        return False, "Primero, el anillo."
    if not _sin_espera() and _dias_desde(estado.get("comprometidos", ""), hoy) < BODA_DESDE_DIAS:
        return False, f"La boda se organiza: {BODA_DESDE_DIAS} dias despues del compromiso."
    return True, ""


def casarse(estado: dict, e: dict, hoy: date, a_lo_grande: bool = True) -> tuple[dict, dict, Suceso]:
    ok, motivo = puede_casarse(estado, hoy)
    if not ok:
        raise ValueError(motivo)
    estado = copy.deepcopy(estado)
    estado["decision"] = {"tipo": "boda", "fecha": hoy.isoformat()}
    return elegir(estado, e, "grande" if a_lo_grande else "intima", hoy)


def terminar(estado: dict, e: dict, hoy: date) -> tuple[dict, dict, Suceso]:
    """Terminar la relacion cuando quiera (con una persona real, sin drama en la prensa)."""
    if (estado or {}).get("estado") not in PAREJA_ACTIVA + ("conociendo",) or not estado.get("pareja"):
        raise ValueError("No estas en pareja.")
    estado, e = copy.deepcopy(estado), copy.deepcopy(e or {})
    pareja = estado["pareja"]
    divorcio = estado["estado"] == "casado"
    real, secreto = pareja.get("real"), estado["estado"] in ("secreto", "conociendo")
    detalle = (f"se divorcio de {pareja['nombre']}" if divorcio else f"termino su relacion con {pareja['nombre']}")
    suceso = Suceso(("Se divorcio de {p}" if divorcio else "Termino con {p}").format(p=pareja["nombre"]), detalle,
                    "neutral" if real else "mixta", 0 if secreto else 1.0,
                    dinero=-round((10 if divorcio else 0) * e.get("sueldo", 0) * economia.NETO), fecha=hoy,
                    clave="amor:fin", privado=secreto)
    estado.update(estado="soltero", pareja=None, decision=None)
    _cobrar(e, suceso)
    _anotar(estado, suceso, {"fin": True})
    return estado, e, suceso


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
    hecho = opcion.noticia.format(pareja=nombre)
    suceso = Suceso(hecho[:1].upper() + hecho[1:], hecho, opcion.tono, opcion.seguidores, opcion.relacion,
                    round(opcion.semanas * e.get("sueldo", 0) * economia.NETO), opcion.reputacion, fecha=hoy,
                    clave=f"amor:{tipo}:{opcion.id}", privado=opcion.privado)
    pareja["relacion"] = max(0, min(100, pareja["relacion"] + opcion.relacion))
    if pareja["real"] and suceso.tono == "negativa":
        suceso.tono = "neutral"  # con una persona real, nada de drama en la prensa
    if opcion.estado == "soltero":
        estado["pareja"] = None
    elif opcion.estado in ("pareja", "secreto") and estado["estado"] == "conociendo":
        pareja.update(desde=hoy.isoformat(), relacion=60)
    if tipo == "salir_a_la_luz":
        estado["secreto_revisado"] = hoy.isoformat()
    if opcion.estado == "comprometido":
        estado["comprometidos"] = hoy.isoformat()
    if opcion.estado == "casado":
        estado["casados"] = hoy.isoformat()
    if opcion.estado:
        estado["estado"] = opcion.estado
    estado["decision"] = None
    _cobrar(e, suceso)
    _anotar(estado, suceso, {"decision": tipo, "eleccion": opcion.id})
    return estado, e, suceso
