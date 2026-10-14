"""
Entrevista post-partido: preguntas a partir del perfil y del partido, y
evaluacion de las respuestas reales del usuario (reaccion de prensa +
impacto en la reputacion).
"""

from typing import Optional

from pydantic import BaseModel

from roleplay.gemini import generar_json
from roleplay.models import PlayerProfile
from roleplay.servicios.contexto import ficha_jugador
from roleplay.servicios.vision import MatchStats

DELTA_REPUTACION_MAXIMO = 15  # cuanto puede mover la reputacion una sola entrevista


class Entrevista(BaseModel):
    preguntas: list[str]


class ReaccionPrensa(BaseModel):
    reaccion_prensa: str
    delta_reputacion: int
    nuevo_gancho_narrativo: str = ""  # vacio si no surgio ninguno


def describir_partido(stats: MatchStats) -> str:
    marcador = f"{stats.goles_equipo}-{stats.goles_rival}"
    if stats.goles_equipo > stats.goles_rival:
        resultado = f"Victoria {marcador}"
    elif stats.goles_equipo < stats.goles_rival:
        resultado = f"Derrota {marcador}"
    else:
        resultado = f"Empate {marcador}"

    partes = [resultado]
    if stats.equipo_rival:
        partes.append(f"vs {stats.equipo_rival}")
    partes.append(f"{stats.goles_jugador} goles, {stats.asistencias_jugador} asistencias")
    partes.append(f"rating {stats.rating_jugador:.1f}")
    partes.append(f"{stats.minutos_jugados} minutos jugados")
    if stats.hombre_del_partido:
        partes.append("elegido hombre del partido")
    if stats.tarjeta_roja:
        partes.append("expulsado con tarjeta roja")
    elif stats.tarjeta_amarilla:
        partes.append("con tarjeta amarilla")
    return ", ".join(partes)


def _contexto(contexto_real: str) -> str:
    if not contexto_real:
        return ""
    return f"\n{contexto_real}\n(Datos reales de su partida: podes usarlos, no los contradigas.)\n"


def _build_prompt(perfil: PlayerProfile, stats: MatchStats, contexto_real: str = "") -> str:
    return f"""
Sos un periodista deportivo en un modo carrera roleplay de EAFC 26.
Genera 2 a 4 preguntas de entrevista en espanol para el jugador, luego de
este partido.

{ficha_jugador(perfil, backstory=True, ganchos=True)}
Resultado del partido: {describir_partido(stats)}
{_contexto(contexto_real)}
Al menos una pregunta debe referirse al partido (goles, rating, tarjetas,
etc.). Otra puede usar alguno de los ganchos narrativos.
""".strip()


def _build_prompt_evaluacion(
    perfil: PlayerProfile, stats: MatchStats, respuestas: list[tuple[str, str]], contexto_real: str = ""
) -> str:
    qa_texto = "\n\n".join(f"P: {pregunta}\nR: {respuesta}" for pregunta, respuesta in respuestas)

    return f"""
Sos un periodista deportivo que acaba de entrevistar a {perfil.nombre_jugador}
despues de un partido, en un modo carrera roleplay de EAFC 26.

{ficha_jugador(perfil, ganchos=True)}
Resultado del partido: {describir_partido(stats)}
{_contexto(contexto_real)}
Estas son las preguntas que le hiciste y las respuestas reales que dio:

{qa_texto}

Evalua como cayeron estas respuestas ante la prensa y los hinchas.
Genera:
1. Una reaccion de prensa: 2 a 4 frases en espanol, estilo nota
   periodistica o resumen de reacciones en redes sociales, describiendo
   como fueron recibidas sus respuestas (podes describir reacciones
   tipicas de hinchas o colegas sin inventar nombres de personas reales).
2. Un delta_reputacion: un numero entero entre -{DELTA_REPUTACION_MAXIMO} y
   {DELTA_REPUTACION_MAXIMO} que refleje el impacto neto en su reputacion publica
   (positivo si cayeron bien, negativo si generaron polemica o rechazo,
   cercano a 0 si fueron respuestas neutras o de cajon).
3. Si alguna respuesta abre una trama nueva interesante (mas alla de
   los ganchos narrativos que ya existen arriba), un
   nuevo_gancho_narrativo breve. Si no aplica, dejalo como string vacio.
""".strip()


def generar_entrevista(
    perfil: PlayerProfile, stats: MatchStats, contexto_real: str = "", api_key: Optional[str] = None
) -> list[str]:
    entrevista = generar_json(
        _build_prompt(perfil, stats, contexto_real),
        Entrevista,
        "Esperate un poco y apreta 'Generar entrevista' de nuevo.",
        api_key=api_key,
    )
    return [pregunta.strip() for pregunta in entrevista.preguntas if pregunta.strip()]


def evaluar_respuestas(
    perfil: PlayerProfile,
    stats: MatchStats,
    respuestas: list[tuple[str, str]],
    contexto_real: str = "",
    api_key: Optional[str] = None,
) -> ReaccionPrensa:
    """Reaccion de prensa + impacto en reputacion (ya acotado)."""
    resultado = generar_json(
        _build_prompt_evaluacion(perfil, stats, respuestas, contexto_real),
        ReaccionPrensa,
        "Esperate un poco y volve a enviar las respuestas.",
        api_key=api_key,
    )
    resultado.delta_reputacion = max(
        -DELTA_REPUTACION_MAXIMO, min(DELTA_REPUTACION_MAXIMO, resultado.delta_reputacion)
    )
    resultado.nuevo_gancho_narrativo = resultado.nuevo_gancho_narrativo.strip()
    return resultado
