"""
Eventos inesperados: lo que le pasa al jugador fuera de la cancha, bueno y
malo (una multa por exceso de velocidad, una gripe, una campana
publicitaria, un video viral...). Salen solos a medida que pasan las
semanas del juego: el modo en vivo revisa en cada autoguardado
(ui/vida.py:acreditar_con).

Tienen reglas: una multa o un choque solo si tiene auto, un robo solo si
tiene casa, la fiesta filtrada solo si tiene yate; la polemica es mas
probable si el personaje es polemico y casi imposible si es humilde; el
premio de los hinchas solo en buena racha; y nunca se repite un evento de
los ultimos.

Como en la economia, lo que provocan lo decide el codigo (reputacion,
seguidores, plata) y la IA solo escribe la noticia y los comentarios.
Algunos traen un reto de roleplay (ej. arrancar el proximo partido en el
banco): la app no toca el juego, asi que es una propuesta para jugar la
historia, no una regla.

El sorteo es reproducible: cada semana del juego tira su propio dado
(semilla: jugador + semana), asi revisar dos veces la misma partida no
hace aparecer eventos distintos.

Estado en estado_json.eventos:
{"hasta": dia del juego hasta donde se sorteo,
 "historial": [{"id", "evento", "fecha", "titulo", "tono", "reputacion",
                "seguidores", "dinero", "reto"}]}  (el mas nuevo primero)
"""

import copy
import random
import uuid
from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Optional

from pydantic import BaseModel

from roleplay.gemini import generar_json
from roleplay.models import ActividadInstagram, NoticiaPrensa, PlayerProfile
from roleplay.partida.carrera import Carrera
from roleplay.servicios import economia
from roleplay.servicios.contexto import ficha_jugador

PROBABILIDAD_POR_SEMANA = 0.3  # ~ un evento por mes de juego
HISTORIAL_GUARDADO = 20
SIN_REPETIR = 4  # un evento no vuelve hasta que pasen otros tantos


@dataclass(frozen=True)
class TipoEvento:
    id: str
    titulo: str  # el titular corto; {auto}, {casa} se completan con lo que tiene
    detalle: str  # lo que pasa, para la IA (tercera persona)
    tono: str  # positiva | negativa | mixta | neutral
    reputacion: int
    seguidores: float  # veces la escala de la hinchada (la misma que mueve los partidos)
    semanas: float = 0.0  # plata: semanas de sueldo neto (+ cobra, - paga)
    requiere: str = ""  # "" | auto | casa | yate | mala_racha | buena_racha | reputacion:N
    pesos: dict = field(default_factory=dict)  # personalidad -> cuanto mas (o menos) probable
    reto: str = ""  # propuesta de roleplay para el proximo partido


TIPOS = [
    # ---- malos ----
    TipoEvento("multa_velocidad", "Multa por exceso de velocidad con su {auto}",
               "lo pararon a mas de 200 km/h en la autopista con su {auto}",
               "negativa", -2, 0.4, -0.3, "auto", {"polemico": 2.0, "humilde": 0.4}),
    TipoEvento("choque_leve", "Choque leve con su {auto}",
               "choco su {auto} contra un poste saliendo del entrenamiento; no hubo heridos",
               "mixta", -1, 0.6, -1.0, "auto"),
    TipoEvento("robo_casa", "Le robaron en su casa",
               "entraron a robar a su {casa} mientras el jugaba de visitante",
               "negativa", 0, 0.5, -2.0, "casa"),
    TipoEvento("fiesta_yate", "Se filtran fotos de una fiesta en su yate",
               "se filtraron fotos de una fiesta hasta la madrugada en su yate, a mitad de temporada",
               "mixta", -2, 1.5, 0, "yate", {"polemico": 2.0, "humilde": 0.3, "reservado": 0.5}),
    TipoEvento("gripe", "Una gripe lo deja en cama",
               "una gripe fuerte lo tuvo dos dias en cama y llega justo al proximo partido",
               "neutral", 0, 0.1, reto="Arranca el proximo partido en el banco (o pedi el cambio en el entretiempo)."),
    TipoEvento("molestia", "Molestias musculares en el entrenamiento",
               "sintio una molestia en el isquiotibial en el entrenamiento y el cuerpo medico lo cuida",
               "neutral", 0, 0.1, reto="No juegues el proximo partido: simulalo, como si te hubieran dado descanso."),
    TipoEvento("llegada_tarde", "Multa del club por llegar tarde al entrenamiento",
               "llego tarde al entrenamiento y el tecnico le puso una multa interna",
               "negativa", -1, 0.2, -0.5, "", {"polemico": 1.5, "humilde": 0.3},
               reto="El tecnico te sienta: el proximo partido lo empezas en el banco."),
    TipoEvento("polemica_redes", "Una respuesta suya en redes se hace viral... para mal",
               "le contesto mal a un hincha rival en redes y se armo una polemica",
               "negativa", -3, 1.2, 0, "", {"polemico": 3.0, "humilde": 0.2, "reservado": 0.4}),
    TipoEvento("increpado", "Hinchas lo increpan en un restaurante",
               "en plena mala racha del equipo, un grupo de hinchas lo increpo mientras cenaba",
               "negativa", -1, 0.2, 0, "mala_racha"),
    # ---- buenos ----
    TipoEvento("campana", "Una marca deportiva lo elige para su nueva campana",
               "firmo para ser la cara de la nueva campana de una marca deportiva",
               "positiva", 2, 1.5, 4.0, "reputacion:55", {"carismatico": 2.0}),
    TipoEvento("video_viral", "Su golazo en el entrenamiento se hace viral",
               "un video suyo clavando un golazo de chilena en el entrenamiento se hizo viral",
               "positiva", 1, 2.0, 0, "", {"carismatico": 1.5}),
    TipoEvento("visita_hospital", "Visita sorpresa a un hospital de ninos",
               "fue sin avisar a un hospital de ninos y paso la tarde jugando con ellos",
               "positiva", 3, 0.6, 0, "", {"humilde": 2.0, "carismatico": 1.5}),
    TipoEvento("programa_tv", "Invitado estrella en un programa de TV",
               "fue el invitado estrella de un programa de TV en horario central",
               "positiva", 1, 1.2, 0.5, "", {"carismatico": 2.5, "reservado": 0.3}),
    TipoEvento("premio_hinchas", "Los hinchas lo eligen el jugador del mes",
               "en la encuesta de la web del club, los hinchas lo votaron el mejor del mes",
               "positiva", 2, 0.8, 0, "buena_racha"),
    TipoEvento("camiseta_nene", "Le regala su camiseta a un nene que lloraba en la tribuna",
               "despues del partido le regalo su camiseta a un nene que lloraba en la tribuna",
               "positiva", 2, 1.0, 0, "", {"humilde": 1.5, "carismatico": 1.5}),
]
POR_ID = {t.id: t for t in TIPOS}


@dataclass
class Ocurrido:
    """Un evento que ya paso, con lo que provoca."""

    tipo: TipoEvento
    fecha: date
    titulo: str
    detalle: str
    reputacion: int
    seguidores: int
    dinero: int
    id: str = field(default_factory=lambda: uuid.uuid4().hex[:8])

    @property
    def reto(self) -> str:
        return self.tipo.reto

    def a_dict(self) -> dict:
        return {"id": self.id, "evento": self.tipo.id, "fecha": self.fecha.isoformat(),
                "titulo": self.titulo, "tono": self.tipo.tono, "reputacion": self.reputacion,
                "seguidores": self.seguidores, "dinero": self.dinero, "reto": self.reto}


# ---- que puede pasar ----


def _ultima_posesion(e: dict, categorias: tuple) -> Optional[str]:
    """El nombre de lo ultimo que se compro de esas categorias (para el titular)."""
    for posesion in reversed(e.get("posesiones", [])):
        articulo = economia.articulo_de_posesion(posesion)
        if articulo is not None and articulo.categoria in categorias:
            return articulo.nombre
    return None


def buena_racha(carrera: Optional[Carrera]) -> bool:
    """Dos o mas victorias en los ultimos tres partidos del club."""
    if carrera is None or carrera.equipo_usuario() is None:
        return False
    equipo = carrera.equipo_usuario()
    ultimos = carrera.partidos_de(equipo, jugados=True)[-3:]
    return sum(p.resultado_para(equipo) == "victoria" for p in ultimos) >= 2


def posibles(perfil: PlayerProfile, e: dict, carrera: Optional[Carrera], reputacion: int,
             recientes: list[str]) -> list[tuple[TipoEvento, float, dict]]:
    """(tipo, peso, lo que completa el titular) de los eventos que pueden
    pasar ahora."""
    auto = _ultima_posesion(e, ("auto",))
    casa = _ultima_posesion(e, ("casa",))
    yate = _ultima_posesion(e, ("yate",))
    cumple = {
        "": True,
        "auto": auto is not None,
        "casa": casa is not None,
        "yate": yate is not None,
        "mala_racha": economia.mala_racha(carrera),
        "buena_racha": buena_racha(carrera),
    }
    resultado = []
    for tipo in TIPOS:
        if tipo.id in recientes:
            continue
        if tipo.requiere.startswith("reputacion:"):
            if reputacion < int(tipo.requiere.split(":")[1]):
                continue
        elif not cumple[tipo.requiere]:
            continue
        peso = tipo.pesos.get(perfil.personalidad, 1.0)
        resultado.append((tipo, peso, {"auto": auto or "auto", "casa": (casa or "casa").lower()}))
    return resultado


def _sortear(player_id: int, semana: date, opciones: list) -> Optional[tuple]:
    dado = random.Random(f"{player_id}:{semana.isoformat()}")
    if not opciones or dado.random() >= PROBABILIDAD_POR_SEMANA:
        return None
    return dado.choices(opciones, weights=[peso for _, peso, _ in opciones])[0]


def revisar(perfil: PlayerProfile, estado: dict, e: dict, carrera: Optional[Carrera], hoy: date,
            seguidores: int, reputacion: int) -> tuple[dict, dict, list[Ocurrido]]:
    """(estado nuevo, economia nueva, eventos que pasaron) al dia `hoy` del
    juego; no toca la base. La primera vez solo marca desde donde contar.
    A lo sumo un evento por revision: si pasaron meses entre guardados, no
    llueven diez cosas juntas."""
    from roleplay.servicios.hinchada import _escala

    estado, e = copy.deepcopy(estado or {}), copy.deepcopy(e or {})
    if not estado.get("hasta") or hoy < date.fromisoformat(estado["hasta"]):
        estado["hasta"] = hoy.isoformat()  # la primera vez, o se cargo una partida anterior
        return estado, e, []
    desde = date.fromisoformat(estado["hasta"])
    semanas = (hoy - desde).days // 7
    if semanas <= 0:
        return estado, e, []
    estado["hasta"] = (desde + timedelta(days=7 * semanas)).isoformat()  # lo que sobra cuenta para la proxima
    historial = estado.setdefault("historial", [])
    recientes = [h["evento"] for h in historial[:SIN_REPETIR]]
    opciones = posibles(perfil, e, carrera, reputacion, recientes)
    for i in range(semanas):
        semana = desde + timedelta(days=7 * i)
        elegido = _sortear(perfil.id, semana, opciones)
        if elegido is None:
            continue
        tipo, _, datos = elegido
        dia = semana + timedelta(days=7)  # paso en esa semana: se cuenta al cerrarla
        plata = round(tipo.semanas * e.get("sueldo", 0) * economia.NETO)
        ocurrido = Ocurrido(
            tipo=tipo, fecha=min(dia, hoy), titulo=tipo.titulo.format(**datos), detalle=tipo.detalle.format(**datos),
            reputacion=tipo.reputacion, seguidores=round(_escala(seguidores, reputacion) * tipo.seguidores),
            dinero=plata,
        )
        if plata and e:
            e["saldo"] = e.get("saldo", 0) + plata
            economia._movimiento(e, ocurrido.fecha, ocurrido.titulo, plata)
        historial.insert(0, ocurrido.a_dict())
        del historial[HISTORIAL_GUARDADO:]
        return estado, e, [ocurrido]
    return estado, e, []


# ---- la repercusion: noticia y comentarios (la IA) ----


class NoticiaEvento(BaseModel):
    titular: str
    cuerpo: str


def repercusion(perfil: PlayerProfile, ocurrido: Ocurrido, moneda: str, contexto_real: str = ""
                ) -> tuple[NoticiaPrensa, ActividadInstagram]:
    """Corre en un hilo. Sin IA, la noticia sale con el titular del evento y
    los hinchas sin comentarios; los numeros ya se aplicaron igual."""
    from roleplay.servicios.hinchada import EventoHinchada, comentar_eventos

    descripcion = f"{perfil.nombre_jugador} {ocurrido.detalle}"
    if ocurrido.dinero:
        descripcion += f" ({'cobra' if ocurrido.dinero > 0 else 'le cuesta'} {economia.dinero(abs(ocurrido.dinero), moneda)})"
    try:
        redactada = generar_json(
            f"""
Sos un periodista deportivo y de la prensa del corazon. Escribi una noticia
corta (titular + 2 a 4 frases, en espanol) sobre esto que le paso a un
jugador en un modo carrera roleplay de EAFC 26:

{descripcion}.
{ficha_jugador(perfil)}
{contexto_real}
El tono es {ocurrido.tipo.tono} (respetalo). No nombres marcas ni personas
reales (salvo la marca del auto si aparece arriba). No inventes resultados
ni datos que no esten arriba.
""".strip(),
            NoticiaEvento,
            "No se pudo escribir la noticia esta vez.",
        )
        titular, cuerpo = redactada.titular.strip(), redactada.cuerpo.strip()
    except RuntimeError:
        titular, cuerpo = f"{perfil.nombre_jugador}: {ocurrido.titulo[0].lower()}{ocurrido.titulo[1:]}", ""
    noticia = NoticiaPrensa(player_id=perfil.id, categoria="jugador", tono=ocurrido.tipo.tono, titular=titular,
                            cuerpo=cuerpo, hitos=[f"evento:{ocurrido.tipo.id}"])
    evento = EventoHinchada("evento", ocurrido.fecha.isoformat(), ocurrido.titulo, descripcion, ocurrido.seguidores)
    try:
        comentarios = comentar_eventos(perfil, [evento], contexto_real).get(0, [])
    except RuntimeError:
        comentarios = []
    actividad = ActividadInstagram(
        player_id=perfil.id, fecha_juego=ocurrido.fecha.isoformat(), tipo="evento", titulo=ocurrido.titulo,
        crecimiento_seguidores=ocurrido.seguidores, comentarios=comentarios,
    )
    return noticia, actividad
