"""
Motor de prensa: noticias sobre el jugador, disparadas por hitos de su
historial (rachas, goles totales, rating), y noticias del mundo sobre hechos
reales de la partida (partidos, premios, mercado). Nada inventado: si no
paso nada, no hay noticia.

La deteccion de hitos es deterministica (Python), y la redaccion tambien:
servicios/narrador.py con roleplay/datos/corpus_prensa.json, cruzando con el
resto de su vida (servicios/cruce.py). Despues de cada entrevista sale una
nota con su frase mas jugosa entre «».
"""

from typing import Optional

from roleplay.models import MatchInterviewRecord, NoticiaPrensa, PlayerProfile
from roleplay.servicios import cruce, lexico
from roleplay.servicios.narrador import narrador, unir

# ---- Umbrales de hitos (ajustables) ----

CHECKPOINTS_GOLES_TOTALES = [5, 10, 25, 50, 100]
CHECKPOINTS_RACHA_GOLEADORA = [3, 5, 8, 12]
CHECKPOINTS_RACHA_SIN_GOL = [3, 5, 8]
CHECKPOINTS_RATING_ALTO = [8.0, 8.5, 9.0]  # promedio ultimos 5, de menos a mas exigente
CHECKPOINTS_RATING_BAJO = [6.0, 5.5, 5.0]  # promedio ultimos 5, de menos a mas grave

# "Promedio de los ultimos 5" solo existe con 5 partidos jugados. Antes,
# con 0 partidos el promedio daba 0.0 y salia una noticia de "mal momento".
PARTIDOS_PARA_RATING = 5

MAXIMO_NOTICIAS_MUNDO = 2  # con la partida: noticias del mundo sobre hechos reales por revision

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
    "premio_global": "gano el {valor} (la votacion de la temporada, con los numeros reales de su partida)",
    "candidato_premio": "quedo en el podio del {valor}",
    "nuevo_club": "fue transferido {valor} (dato real de su partida: es su nuevo club)",
    "fin_de_temporada": "termino la {valor}. Escribi el balance de su temporada",
    "meta_cumplida": "cumplio la meta que se habia propuesto publicamente: {valor}",
    "meta_fallida": "NO cumplio la meta que se habia propuesto publicamente: {valor}",
}

# Los premios y logros reales tambien mueven la reputacion (la sala de
# prensa aplica la suma cuando guarda las noticias).
BONOS_REPUTACION = {
    "jugador_del_mes": 5, "premio_global": 6, "candidato_premio": 2, "campeon": 10, "maximo_goleador": 8, "meta_cumplida": 4, "meta_fallida": -4,
}


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


TONO_HITO = {
    "hito_goles_totales": "positiva", "racha_goleadora": "positiva", "buen_momento": "positiva",
    "goles_temporada": "positiva", "lider_goleadores": "positiva", "partidazo": "positiva", "lider_liga": "positiva",
    "premio_global": "positiva", "candidato_premio": "positiva", "campeon": "positiva", "maximo_goleador": "positiva", "jugador_del_mes": "positiva", "meta_cumplida": "positiva",
    "racha_sin_gol": "negativa", "mal_momento": "negativa", "perdio_liderato": "negativa", "meta_fallida": "negativa",
}
# el titular sale del hito mas importante
PRIORIDAD_HITOS = (
    "premio_global", "campeon", "maximo_goleador", "candidato_premio", "jugador_del_mes", "nuevo_club", "fin_de_temporada", "meta_cumplida", "meta_fallida",
    "partidazo", "lider_goleadores", "hito_goles_totales", "racha_goleadora", "lider_liga", "perdio_liderato",
    "goles_temporada", "buen_momento", "racha_sin_gol", "mal_momento",
)
NUCLEOS_POR_NOTICIA = 3
PALABRAS_PARA_CITAR = 8


def _describir_hitos(hitos: list[dict]) -> str:
    return "\n".join(
        "- " + DESCRIPCIONES_HITOS.get(hito["tipo"], "{tipo}: {valor}").format(**hito)
        for hito in hitos
    )


def tono_de_hitos(hitos: list[dict]) -> str:
    tonos = {TONO_HITO.get(h["tipo"], "neutral") for h in hitos} - {"neutral"}
    return "mixta" if len(tonos) > 1 else tonos.pop() if tonos else "neutral"


def _base(perfil: PlayerProfile) -> dict:
    partes = perfil.nombre_jugador.split()
    return {"nombre": perfil.nombre_jugador, "apellido": partes[-1] if partes else "El jugador",
            "club": perfil.club_actual or "su club"}


def _con_valor(base: dict, hito: dict) -> dict:
    valor = str(hito["valor"])
    return {**base, "valor": valor, "valor_min": valor[:1].lower() + valor[1:]}


def noticia_de_hitos(escritor, perfil: PlayerProfile, hitos: list[dict], cruces: list) -> NoticiaPrensa:
    """[apertura] + [lo que paso, un nucleo por hito] + [cruce] + [cierre]."""
    base = _base(perfil)
    orden = sorted(hitos, key=lambda h: PRIORIDAD_HITOS.index(h["tipo"]) if h["tipo"] in PRIORIDAD_HITOS else 99)
    principal = orden[0]
    tono = tono_de_hitos(hitos)
    titular = escritor.decir(f"t_{principal['tipo']}", **_con_valor(base, principal))
    if not titular:
        titular = DESCRIPCIONES_HITOS.get(principal["tipo"], "{valor}").format(**principal)
    nucleos = [escritor.elegir(f"n_{h['tipo']}", **_con_valor(base, h)) for h in orden[:NUCLEOS_POR_NOTICIA]]
    extra = next((escritor.elegir(f"x_{c.tipo}", **{**base, **c.datos}) for c in cruces
                  if escritor.puede(f"x_{c.tipo}", **{**base, **c.datos})), "")
    cuerpo = unir(escritor.elegir(f"c_apertura_{tono}", **base), *nucleos, extra, escritor.elegir(f"c_cierre_{tono}", **base))
    escritor.anotar(cuerpo)
    return NoticiaPrensa(player_id=perfil.id, categoria="jugador", tono=tono, titular=titular, cuerpo=cuerpo,
                         hitos=[f"{h['tipo']}:{h['valor']}" for h in hitos])


def noticia_de_entrevista(escritor, perfil: PlayerProfile, registro: MatchInterviewRecord) -> Optional[NoticiaPrensa]:
    """La nota de la ultima entrevista, con su frase mas jugosa entre «»."""
    lectura = lexico.leer(registro.respuestas_jugador)
    if not lectura.cita or lectura.palabras < PALABRAS_PARA_CITAR:
        return None
    delta = registro.delta_reputacion
    tono = "positiva" if delta >= 2 else "negativa" if delta <= -2 else "mixta" if delta else "neutral"
    datos = {**_base(perfil), "cita": lectura.cita, "rival": registro.equipo_rival or "su rival",
             "marcador": f"{registro.goles_equipo}-{registro.goles_rival}"}
    titular = escritor.decir(f"t_cita_{tono}", **datos)
    cuerpo = unir(escritor.elegir("n_cita", **datos), registro.reaccion_prensa)
    titular, cuerpo = _nota_con_ia(perfil, registro, lectura.cita, tono) or (titular, cuerpo)
    return NoticiaPrensa(player_id=perfil.id, categoria="jugador", tono=tono, titular=titular, cuerpo=cuerpo,
                         hitos=[f"entrevista:{registro.id}"])


SISTEMA_NOTA = (
    "Sos un diario deportivo en un juego de roleplay de futbol. Con la entrevista post-partido de un jugador, "
    "escribi `titular` (con gancho, que incluya su cita entre «») y `cuerpo` (un parrafo periodistico de 4 a 6 "
    "oraciones en tercera persona que desarrolle lo que dijo, textual cuando sirva, y como lo leyo la prensa)."
)


def _nota_con_ia(perfil: PlayerProfile, registro: MatchInterviewRecord, cita: str, tono: str):
    """(titular, cuerpo) de la IA, o None."""
    from roleplay.servicios import ia

    pares = "\n".join(f"P: {p}\nR: {r}" for p, r in zip(registro.preguntas_entrevista, registro.respuestas_jugador))
    datos = ia.pedir_json(
        SISTEMA_NOTA,
        f"{ia.ficha(perfil)}\nPartido: {registro.goles_equipo}-{registro.goles_rival} vs "
        f"{registro.equipo_rival or 'su rival'}, {registro.goles_jugador} goles, nota {registro.rating_jugador:.1f}.\n"
        f"La entrevista:\n{pares}\nLa cita elegida: «{cita}»\nComo la leyo la prensa ({tono}): {registro.reaccion_prensa}",
        {"titular": "...", "cuerpo": "..."},
        jugador=perfil.id,
    )
    if not datos:
        return None
    titular, cuerpo = ia.texto(datos.get("titular"), 180), ia.texto(datos.get("cuerpo"), 1500)
    return (titular, cuerpo) if titular and cuerpo else None


def noticia_del_mundo(escritor, perfil: PlayerProfile, hecho) -> NoticiaPrensa:
    """Un hecho real de la partida (dict de servicios/partida_real.py, o texto suelto)."""
    if isinstance(hecho, str):
        hecho = {"tipo": "texto", "texto": hecho}
    tipo = hecho["tipo"]
    datos = {clave: valor for clave, valor in hecho.items() if valor not in (None, "")}
    if tipo == "hat_trick" and not escritor.puede("t_hat_trick", **datos):
        titular = escritor.decir("t_hat_trick_sin_nombre", **datos)
    elif escritor.tiene(f"t_{tipo}"):
        titular = escritor.decir(f"t_{tipo}", **datos)
    else:
        titular = ""
    if not titular:  # un texto suelto: el titular es su primera oracion
        titular = hecho["texto"].split(". ")[0].split("\n")[0].rstrip(".:")
    cierre = escritor.elegir(f"c_mundo_{tipo}", **datos) or escritor.elegir(f"c_{tipo}", **datos)
    cuerpo = unir(hecho["texto"].replace("\n- ", " ").replace("\n", " "), cierre)
    return NoticiaPrensa(player_id=perfil.id, categoria="general", tono=hecho.get("tono", "neutral"), titular=titular,
                         cuerpo=cuerpo)


def revisar_prensa(
    perfil: PlayerProfile,
    historial: list[MatchInterviewRecord],
    estado_prensa: dict,
    hechos_reales: Optional[list] = None,
    hitos_reales: Optional[list[dict]] = None,
    carrera=None,
) -> dict:
    """Busca hitos nuevos en el historial y escribe sobre lo que paso de
    verdad. Todo sale del motor narrativo: no falla ni espera. Si no paso
    nada real, no hay noticia (nunca se inventa una de ambiente).

    Con la partida de FC 26 (servicios/partida_real.py): si hay
    `hechos_reales` (dicts con "tipo" y "texto"), las noticias del mundo son
    sobre los primeros (hasta MAXIMO_NOTICIAS_MUNDO). `hitos_reales` (los de la partida) se suman a los del
    historial. La ultima entrevista sin nota tiene la suya, con su cita.

    Devuelve {"noticias": list[NoticiaPrensa] (sin guardar),
              "hitos": list[dict],
              "estado_prensa": dict listo para database.set_estado_prensa,
              "delta_reputacion": int (bonos por premios y logros reales)}.
    """
    stats = calcular_estadisticas_acumuladas(historial)
    hitos, nuevo_estado = detectar_nuevos_hitos(stats, estado_prensa)
    hitos = hitos + list(hitos_reales or [])
    noticias: list[NoticiaPrensa] = []
    cruces = cruce.cruces(perfil.id, carrera=carrera) if perfil.id else []

    with narrador(perfil.id, "prensa") as escritor:
        if hitos:
            noticias.append(noticia_de_hitos(escritor, perfil, hitos, cruces))
        entrevistas = [r for r in historial if r.origen != "previa"]
        if entrevistas and entrevistas[0].id is not None and entrevistas[0].id != estado_prensa.get("entrevista_reportada"):
            nota = noticia_de_entrevista(escritor, perfil, entrevistas[0])
            if nota is not None:
                noticias.append(nota)
            nuevo_estado["entrevista_reportada"] = entrevistas[0].id
        if hechos_reales:
            noticias += [noticia_del_mundo(escritor, perfil, h) for h in hechos_reales[:MAXIMO_NOTICIAS_MUNDO]]

    return {
        "noticias": noticias,
        "hitos": hitos,
        "estado_prensa": nuevo_estado,
        "delta_reputacion": sum(BONOS_REPUTACION.get(h["tipo"], 0) for h in hitos),
    }
