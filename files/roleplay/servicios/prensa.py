"""
Motor de prensa: noticias sobre el jugador, disparadas por hitos de su
historial (rachas, goles totales, rating), y noticias generales del mundo
del futbol, de ambiente.

La deteccion de hitos es deterministica (Python); la IA solo redacta.
"""

import random
from typing import Optional

from pydantic import BaseModel

from roleplay.gemini import generar_json
from roleplay.models import MatchInterviewRecord, NoticiaPrensa, PlayerProfile
from roleplay.servicios.contexto import ficha_jugador

# ---- Umbrales de hitos (ajustables) ----

CHECKPOINTS_GOLES_TOTALES = [5, 10, 25, 50, 100]
CHECKPOINTS_RACHA_GOLEADORA = [3, 5, 8, 12]
CHECKPOINTS_RACHA_SIN_GOL = [3, 5, 8]
CHECKPOINTS_RATING_ALTO = [8.0, 8.5, 9.0]  # promedio ultimos 5, de menos a mas exigente
CHECKPOINTS_RATING_BAJO = [6.0, 5.5, 5.0]  # promedio ultimos 5, de menos a mas grave

# "Promedio de los ultimos 5" solo existe con 5 partidos jugados. Antes,
# con 0 partidos el promedio daba 0.0 y salia una noticia de "mal momento".
PARTIDOS_PARA_RATING = 5

PROBABILIDAD_NOTICIA_GENERAL = 0.5  # chance de que tambien salga una de ambiente

DESCRIPCIONES_HITOS = {
    "hito_goles_totales": "llego a {valor} goles en su carrera con este personaje",
    "racha_goleadora": "anoto en {valor} partidos consecutivos",
    "racha_sin_gol": "lleva {valor} partidos consecutivos sin convertir",
    "buen_momento": "promedia un rating de {valor} o mas en sus ultimos 5 partidos",
    "mal_momento": "su rating promedio de los ultimos 5 partidos cayo a {valor} o menos",
    # hitos reales, de su partida de FC 26 (servicios/partida_real.py)
    "goles_temporada": "ya lleva {valor} goles en la temporada (dato real de su partida)",
    "lider_goleadores": "es el maximo goleador de la {valor}",
    "partidazo": "hizo un partidazo: {valor}",
    "lider_liga": "su equipo paso a liderar la {valor}",
    "perdio_liderato": "su equipo perdio el liderato de la {valor}",
    "campeon": "su equipo salio campeon de la {valor}",
    "maximo_goleador": "termino la temporada como maximo goleador de la {valor}",
    "jugador_del_mes": "fue elegido jugador del mes: {valor}",
}

# Los premios y logros reales tambien mueven la reputacion (la sala de
# prensa aplica la suma cuando guarda las noticias).
BONOS_REPUTACION = {"jugador_del_mes": 5, "campeon": 10, "maximo_goleador": 8}


def _racha(historial: list[MatchInterviewRecord], condicion) -> int:
    racha = 0
    for partido in historial:
        if not condicion(partido):
            break
        racha += 1
    return racha


def calcular_estadisticas_acumuladas(historial: list[MatchInterviewRecord]) -> dict:
    """`historial` va del partido mas reciente al mas viejo (asi lo
    devuelve database.load_match_interviews)."""
    jugados = len(historial)
    ultimos = historial[:PARTIDOS_PARA_RATING]
    return {
        "partidos_jugados": jugados,
        "goles_totales": sum(p.goles_jugador for p in historial),
        "asistencias_totales": sum(p.asistencias_jugador for p in historial),
        "figuras": sum(p.hombre_del_partido for p in historial),
        "rating_promedio": sum(p.rating_jugador for p in historial) / jugados if jugados else 0.0,
        "racha_goleadora": _racha(historial, lambda p: p.goles_jugador > 0),
        "racha_sin_gol": _racha(historial, lambda p: p.goles_jugador == 0),
        "rating_promedio_ultimos_5": (
            sum(p.rating_jugador for p in ultimos) / len(ultimos) if ultimos else 0.0
        ),
    }


def _estado_prensa_default() -> dict:
    return {
        "goles_totales_max_reportado": 0,
        "racha_goleadora_max_reportada": 0,
        "racha_sin_gol_max_reportada": 0,
        "rating_alto_max_reportado": 0.0,
        "rating_bajo_min_reportado": 99.0,
    }


def _mayor_checkpoint_cruzado(valor_actual, checkpoints_asc, max_reportado):
    """El checkpoint mas alto alcanzado que supere al ya reportado, o None."""
    candidatos = [c for c in checkpoints_asc if valor_actual >= c and c > max_reportado]
    return max(candidatos) if candidatos else None


def _menor_checkpoint_cruzado(valor_actual, checkpoints_desc, min_reportado):
    """Para umbrales hacia abajo (rating bajo): el mas bajo alcanzado que
    este por debajo del minimo ya reportado, o None."""
    candidatos = [c for c in checkpoints_desc if valor_actual <= c and c < min_reportado]
    return min(candidatos) if candidatos else None


def detectar_nuevos_hitos(stats: dict, estado_prensa: dict) -> tuple[list[dict], dict]:
    """Compara las estadisticas contra los checkpoints ya reportados y
    devuelve (hitos_nuevos, estado_prensa_actualizado).

    Las rachas se reinician solas cuando se cortan, para poder volver a
    dispararse mas adelante en la carrera."""
    estado = {**_estado_prensa_default(), **estado_prensa}
    hitos = []

    def registrar(tipo: str, clave_estado: str, valor) -> None:
        if valor is not None:
            hitos.append({"tipo": tipo, "valor": valor})
            estado[clave_estado] = valor

    registrar(
        "hito_goles_totales",
        "goles_totales_max_reportado",
        _mayor_checkpoint_cruzado(
            stats["goles_totales"], CHECKPOINTS_GOLES_TOTALES, estado["goles_totales_max_reportado"]
        ),
    )

    for tipo, checkpoints in (
        ("racha_goleadora", CHECKPOINTS_RACHA_GOLEADORA),
        ("racha_sin_gol", CHECKPOINTS_RACHA_SIN_GOL),
    ):
        clave = f"{tipo}_max_reportada"
        if stats[tipo] == 0:
            estado[clave] = 0
        else:
            registrar(tipo, clave, _mayor_checkpoint_cruzado(stats[tipo], checkpoints, estado[clave]))

    if stats["partidos_jugados"] >= PARTIDOS_PARA_RATING:
        rating = stats["rating_promedio_ultimos_5"]

        if rating < CHECKPOINTS_RATING_ALTO[0]:
            estado["rating_alto_max_reportado"] = 0.0
        else:
            registrar(
                "buen_momento",
                "rating_alto_max_reportado",
                _mayor_checkpoint_cruzado(
                    rating, CHECKPOINTS_RATING_ALTO, estado["rating_alto_max_reportado"]
                ),
            )

        if rating > CHECKPOINTS_RATING_BAJO[0]:
            estado["rating_bajo_min_reportado"] = 99.0
        else:
            registrar(
                "mal_momento",
                "rating_bajo_min_reportado",
                _menor_checkpoint_cruzado(
                    rating, CHECKPOINTS_RATING_BAJO, estado["rating_bajo_min_reportado"]
                ),
            )

    return hitos, estado


def _describir_hitos(hitos: list[dict]) -> str:
    return "\n".join(
        "- " + DESCRIPCIONES_HITOS.get(hito["tipo"], "{tipo}: {valor}").format(**hito)
        for hito in hitos
    )


class NoticiaIA(BaseModel):
    titular: str
    cuerpo: str
    tono: str  # "positiva" | "negativa" | "mixta" | "neutral"


def _bloque_real(contexto_real: str) -> str:
    if not contexto_real:
        return ""
    return f"\n{contexto_real}\n(Estos datos son reales de su partida: usalos y no los contradigas.)\n"


def _build_prompt_noticia_jugador(
    perfil: PlayerProfile, stats: dict, hitos: list[dict], contexto_real: str = ""
) -> str:
    return f"""
Sos un periodista deportivo escribiendo una noticia espontanea (no una
entrevista) sobre {perfil.nombre_jugador}, en un modo carrera roleplay
de EAFC 26.

{ficha_jugador(perfil, backstory=True)}
{_bloque_real(contexto_real)}
Datos acumulados de su carrera hasta ahora:
- Partidos jugados: {stats['partidos_jugados']}
- Goles totales: {stats['goles_totales']}
- Rating promedio ultimos 5 partidos: {stats['rating_promedio_ultimos_5']:.1f}

Motivo de esta noticia:
{_describir_hitos(hitos)}

Escribi una noticia deportiva corta (titular + 3-5 frases de cuerpo, en
espanol) sobre esto. Si los hitos son positivos (rachas goleadoras, buen
rating, muchos goles), el tono puede incluir comparaciones con leyendas
del futbol o rumores de premios individuales (Balon de Oro, mejor
jugador de la liga) SIN inventar nombres de jugadores reales que
compitan por el premio. Si son negativos (sequia de gol, mal momento),
el tono puede incluir criticas de la prensa o dudas sobre su nivel. Si
hay mezcla, reflejalo con tono mixto.

Clasifica el tono general como "positiva", "negativa" o "mixta".
""".strip()


def _build_prompt_noticia_general(perfil: PlayerProfile) -> str:
    return f"""
Sos un periodista deportivo escribiendo una noticia GENERAL del mundo
del futbol (no directamente sobre {perfil.nombre_jugador}), para darle
ambiente al modo carrera roleplay de EAFC 26 en el que juega. Club
actual del jugador (para ambientar, no tiene que ser el protagonista):
{perfil.club_actual or "(desconocido)"}.

Escribi una noticia corta e INVENTADA (titular + 2-4 frases) sobre algo
que este pasando en el mundo del futbol alrededor del jugador: un
rumor de transferencia de otro jugador ficticio, una sorpresa en la
tabla de posiciones, una polemica arbitral, un cambio de tecnico en
otro club, etc. No inventes nombres de jugadores, clubes o personas
reales: todo ficticio, ambientado en el mismo universo del modo
carrera. Clasifica el tono como "positiva", "negativa" o "neutral".
""".strip()


def _build_prompt_noticia_real(perfil: PlayerProfile, hecho: str, contexto_real: str) -> str:
    return f"""
Sos un periodista deportivo. Escribi una noticia corta (titular + 2-4
frases, en espanol) sobre este hecho REAL del modo carrera de EAFC 26 en
el que juega {perfil.nombre_jugador} (no es el protagonista):

{hecho}
{_bloque_real(contexto_real)}
Reglas: los resultados, goles y posiciones son exactamente esos. Nombra
solo a los jugadores que aparecen con nombre en el hecho; si aparece "el
delantero del X", no le inventes un nombre. Podes agregar color (reaccion
de los hinchas, lo que significa para la tabla) sin inventar otros datos.
Clasifica el tono como "positiva", "negativa" o "neutral".
""".strip()


def _redactar(prompt: str, api_key: Optional[str]) -> NoticiaIA:
    return generar_json(
        prompt, NoticiaIA, "No se pudo generar la noticia esta vez.", api_key=api_key
    )


def revisar_prensa(
    perfil: PlayerProfile,
    historial: list[MatchInterviewRecord],
    estado_prensa: dict,
    api_key: Optional[str] = None,
    incluir_general: bool = True,
    contexto_real: str = "",
    hechos_reales: Optional[list[str]] = None,
    hitos_reales: Optional[list[dict]] = None,
) -> dict:
    """Busca hitos nuevos en el historial y, a veces, agrega una noticia
    general de ambiente.

    Con la partida de FC 26 (servicios/partida_real.py): `contexto_real` va
    a la noticia sobre el jugador, y si hay `hechos_reales` la noticia del
    mundo es sobre el primero (siempre), en vez de una inventada al azar.
    `hitos_reales` (los de la partida) se suman a los del historial.

    Devuelve {"noticias": list[NoticiaPrensa] (sin guardar),
              "hitos": list[dict],
              "estado_prensa": dict listo para database.set_estado_prensa,
              "delta_reputacion": int (bonos por premios y logros reales)}.

    Si falla la noticia de ambiente pero ya hay una sobre el jugador, se
    sigue sin la de ambiente: no vale la pena perder la importante.
    """
    stats = calcular_estadisticas_acumuladas(historial)
    hitos, nuevo_estado = detectar_nuevos_hitos(stats, estado_prensa)
    hitos = hitos + list(hitos_reales or [])
    noticias: list[NoticiaPrensa] = []

    if hitos:
        redactada = _redactar(_build_prompt_noticia_jugador(perfil, stats, hitos, contexto_real), api_key)
        noticias.append(
            NoticiaPrensa(
                player_id=perfil.id,
                categoria="jugador",
                tono=redactada.tono,
                titular=redactada.titular,
                cuerpo=redactada.cuerpo,
                hitos=[f"{h['tipo']}:{h['valor']}" for h in hitos],
            )
        )

    if hechos_reales:
        prompt_general = _build_prompt_noticia_real(perfil, hechos_reales[0], contexto_real)
    elif incluir_general and random.random() < PROBABILIDAD_NOTICIA_GENERAL:
        prompt_general = _build_prompt_noticia_general(perfil)
    else:
        prompt_general = None

    if prompt_general:
        try:
            redactada = _redactar(prompt_general, api_key)
        except RuntimeError:
            if not noticias:
                raise
        else:
            noticias.append(
                NoticiaPrensa(
                    player_id=perfil.id,
                    categoria="general",
                    tono=redactada.tono,
                    titular=redactada.titular,
                    cuerpo=redactada.cuerpo,
                )
            )

    return {
        "noticias": noticias,
        "hitos": hitos,
        "estado_prensa": nuevo_estado,
        "delta_reputacion": sum(BONOS_REPUTACION.get(h["tipo"], 0) for h in hitos),
    }
