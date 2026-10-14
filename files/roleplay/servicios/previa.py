"""
Conferencia de prensa PREVIA al proximo partido del club. Los datos salen
de la partida de FC 26 (rival, tabla, rachas, si ya se enfrentaron, el
goleador del rival) y los elige el codigo; la IA solo hace las preguntas y
evalua las respuestas, como en la entrevista post-partido.

No se guarda como partido (no suma partidos ni goles): deja una noticia
con el titular de la conferencia y mueve la reputacion.
"""

from dataclasses import dataclass, field
from typing import Optional

from pydantic import BaseModel

from roleplay.gemini import generar_json
from roleplay.models import NoticiaPrensa, PlayerProfile
from roleplay.partida.carrera import Carrera
from roleplay.servicios.contexto import ficha_jugador
from roleplay.servicios.partida_real import (
    clave_partido,
    describir_jugador,
    fecha_corta,
    marcador,
    nombres_de_jugadores,
)

DELTA_REPUTACION_MAXIMO = 10  # una previa pesa menos que lo que pasa en la cancha
RACHA = 5
LETRAS = {"victoria": "G", "empate": "E", "derrota": "P"}
TONOS = ("positiva", "negativa", "mixta", "neutral")


@dataclass
class PreviaPartido:
    clave: str  # clave_partido del proximo partido: para saber si ya se hizo
    club: str
    rival: str
    de_local: bool
    competicion: str
    fecha: str
    datos: list[str] = field(default_factory=list)  # hechos reales para el prompt y la pantalla
    ya_hecha: bool = False

    @property
    def resumen(self) -> str:
        condicion = "de local" if self.de_local else "de visita"
        return f"vs {self.rival} ({condicion}) · {self.competicion} · {self.fecha}"

    def describir(self) -> str:
        condicion = "de local" if self.de_local else "de visita"
        lineas = [f"Proximo partido: {self.club} ante {self.rival}, {condicion}, por {self.competicion} ({self.fecha})."]
        lineas += [f"- {dato}" for dato in self.datos]
        return "\n".join(lineas)


def _racha(carrera: Carrera, equipo: int) -> str:
    ultimos = carrera.partidos_de(equipo, jugados=True)[-RACHA:]
    return " ".join(LETRAS[p.resultado_para(equipo)] for p in ultimos)


def previa_del_proximo(
    carrera: Carrera, nombres: Optional[dict] = None, estado_partida: Optional[dict] = None
) -> Optional[PreviaPartido]:
    """La previa del proximo partido del club del usuario, o None si no hay
    club o no le queda ningun partido por jugar. Sin `nombres`, usa los ya
    conocidos (no consulta a la IA)."""
    equipo = carrera.equipo_usuario()
    if equipo is None:
        return None
    proximo = carrera.proximo_partido_de(equipo)
    if proximo is None:
        return None
    rival = proximo.rival(equipo)
    club, nombre_rival = carrera.equipo(equipo), carrera.equipo(rival)
    competicion = carrera.competiciones.get(proximo.competicion)
    datos = []

    if competicion and competicion.es_liga:
        tabla = carrera.tabla(proximo.competicion)
        puestos = {f.equipo: (n, f) for n, f in enumerate(tabla, start=1)}
        if equipo in puestos and rival in puestos:
            (p_club, f_club), (p_rival, f_rival) = puestos[equipo], puestos[rival]
            datos.append(
                f"En la tabla: {club} {p_club}° con {f_club.pts} pts, {nombre_rival} {p_rival}° con "
                f"{f_rival.pts} pts (de {len(tabla)} equipos)."
            )

    for nombre, id_equipo in ((club, equipo), (nombre_rival, rival)):
        racha = _racha(carrera, id_equipo)
        if racha:
            datos.append(f"Racha de {nombre} (ultimos partidos, el mas reciente al final): {racha}.")

    ultimo_rival = carrera.ultimo_partido_de(rival)
    if ultimo_rival is not None and not ultimo_rival.participa(equipo):
        datos.append(
            f"Ultimo partido de {nombre_rival}: {marcador(carrera, ultimo_rival)} "
            f"({carrera.competicion(ultimo_rival.competicion)})."
        )

    cruces = [p for p in carrera.partidos_de(equipo, jugados=True) if p.participa(rival)]
    if cruces:
        datos.append(
            "Ya se enfrentaron esta temporada: "
            + "; ".join(f"{marcador(carrera, p)} ({carrera.competicion(p.competicion)}, {fecha_corta(p.fecha)})" for p in cruces)
            + "."
        )

    goleador = next((e for e in carrera.goleadores(proximo.competicion, 200) if e.equipo == rival), None)
    if goleador is not None:
        if nombres is None:
            nombres = nombres_de_jugadores(carrera, {goleador.jugador}, preguntar=False)
        datos.append(
            f"Goleador de {nombre_rival} ({carrera.competicion(proximo.competicion)}): "
            f"{describir_jugador(carrera, goleador.jugador, nombres)} con {goleador.goles} goles."
        )

    clave = clave_partido(proximo)
    return PreviaPartido(
        clave=clave,
        club=club,
        rival=nombre_rival,
        de_local=proximo.local == equipo,
        competicion=carrera.competicion(proximo.competicion),
        fecha=fecha_corta(proximo.fecha),
        datos=datos,
        ya_hecha=(estado_partida or {}).get("previa") == clave,
    )


# ---- la IA: preguntas y evaluacion ----


class PreguntasPrevia(BaseModel):
    preguntas: list[str]


class ReaccionPrevia(BaseModel):
    titular: str
    reaccion_prensa: str
    tono: str = "neutral"
    delta_reputacion: int
    nuevo_gancho_narrativo: str = ""


def _contexto(contexto_real: str) -> str:
    if not contexto_real:
        return ""
    return f"\n{contexto_real}\n(Datos reales de su partida: podes usarlos, no los contradigas.)\n"


def _prompt_preguntas(perfil: PlayerProfile, previa: PreviaPartido, contexto_real: str) -> str:
    return f"""
Sos un periodista deportivo en la conferencia de prensa PREVIA a un partido,
en un modo carrera roleplay de EAFC 26. Genera 2 a 4 preguntas en espanol
para el jugador.

{ficha_jugador(perfil, backstory=True, ganchos=True)}
{previa.describir()}
{_contexto(contexto_real)}
Las preguntas miran hacia adelante: el rival, lo que esta en juego, la
racha, como llega el jugador. Usa los datos reales de arriba (si ya se
enfrentaron, la tabla, el goleador rival). Si el partido es un clasico o
un derbi conocido, aprovechalo. Una puede tocar alguno de los ganchos
narrativos. No inventes resultados que no esten en los datos.
""".strip()


def _prompt_evaluacion(
    perfil: PlayerProfile, previa: PreviaPartido, respuestas: list[tuple[str, str]], contexto_real: str
) -> str:
    qa_texto = "\n\n".join(f"P: {pregunta}\nR: {respuesta}" for pregunta, respuesta in respuestas)
    return f"""
Sos un periodista deportivo que acaba de estar en la conferencia previa de
{perfil.nombre_jugador}, en un modo carrera roleplay de EAFC 26.

{ficha_jugador(perfil, ganchos=True)}
{previa.describir()}
{_contexto(contexto_real)}
Preguntas y respuestas reales del jugador:

{qa_texto}

Genera:
1. titular: el titular que sale en la prensa con lo mas jugoso de la
   conferencia (puede citar al jugador entre comillas), en espanol.
2. reaccion_prensa: 2 a 4 frases sobre como cayeron sus palabras en la
   prensa y los hinchas de los dos equipos (sin inventar nombres de
   personas reales).
3. tono: uno de {", ".join(TONOS)}.
4. delta_reputacion: entero entre -{DELTA_REPUTACION_MAXIMO} y {DELTA_REPUTACION_MAXIMO}
   (positivo si cayo bien, negativo si genero polemica o rechazo, cerca de
   0 si fueron respuestas de cajon). Una previa pesa menos que un partido.
5. nuevo_gancho_narrativo: si sus palabras abren una trama nueva (ej. una
   promesa de gol, una provocacion al rival), descripta brevemente; si no,
   string vacio.
""".strip()


def generar_previa(
    perfil: PlayerProfile, previa: PreviaPartido, contexto_real: str = "", api_key: Optional[str] = None
) -> list[str]:
    resultado = generar_json(
        _prompt_preguntas(perfil, previa, contexto_real),
        PreguntasPrevia,
        "Esperate un poco y apreta 'Generar conferencia' de nuevo.",
        api_key=api_key,
    )
    return [pregunta.strip() for pregunta in resultado.preguntas if pregunta.strip()]


def evaluar_previa(
    perfil: PlayerProfile,
    previa: PreviaPartido,
    respuestas: list[tuple[str, str]],
    contexto_real: str = "",
    api_key: Optional[str] = None,
) -> ReaccionPrevia:
    resultado = generar_json(
        _prompt_evaluacion(perfil, previa, respuestas, contexto_real),
        ReaccionPrevia,
        "Esperate un poco y volve a enviar las respuestas.",
        api_key=api_key,
    )
    resultado.delta_reputacion = max(-DELTA_REPUTACION_MAXIMO, min(DELTA_REPUTACION_MAXIMO, resultado.delta_reputacion))
    resultado.tono = resultado.tono.strip().lower() if resultado.tono.strip().lower() in TONOS else "neutral"
    resultado.titular = resultado.titular.strip() or f"{perfil.nombre_jugador} palpita el duelo ante {previa.rival}"
    resultado.nuevo_gancho_narrativo = resultado.nuevo_gancho_narrativo.strip()
    return resultado


def noticia_de_previa(perfil: PlayerProfile, previa: PreviaPartido, reaccion: ReaccionPrevia) -> NoticiaPrensa:
    """La conferencia queda en la central de noticias."""
    return NoticiaPrensa(
        player_id=perfil.id,
        categoria="jugador",
        tono=reaccion.tono,
        titular=reaccion.titular,
        cuerpo=reaccion.reaccion_prensa,
        hitos=[f"previa:{previa.clave}"],
    )
