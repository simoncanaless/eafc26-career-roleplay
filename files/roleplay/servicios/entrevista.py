"""
Entrevista post-partido, sin IA y al instante.

Preguntas: tres periodistas, cada uno con su estilo:
1. el tactico (Pizarra Tactica): el partido y los numeros, con memoria de
   los ultimos partidos (sequia goleadora rota, racha, caida de rendimiento,
   el cruce anterior con el mismo rival, como se movio la tabla);
2. el del vestuario (Radio Tribuna): el grupo, la hinchada, las metas (con
   la cuenta regresiva exacta) y los reencuentros con un ex club;
3. el picante (El Picante): lo de afuera de la cancha (el auto que se
   compro si jugo mal, la pareja, la multa de la semana) o lo que dijo la
   fecha pasada si hoy no le dio la razon.
Las arma servicios/narrador.py con roleplay/datos/corpus_entrevista.json, sin
repetir bloques recientes, cruzando el partido con el resto de su vida
(servicios/cruce.py).

Evaluacion: servicios/lexico.py lee las respuestas (5 ejes, con negaciones),
y el eje dominante, cruzado con el resultado, la nota y la personalidad,
decide el delta de reputacion (tope +-15), el carino de la hinchada y la
reaccion de la prensa, con la frase del jugador entre «».
"""

from dataclasses import replace
from typing import Optional

from pydantic import BaseModel

from roleplay.models import MatchInterviewRecord, PlayerProfile
from roleplay.servicios import cruce, lexico
from roleplay.servicios.narrador import narrador, unir
from roleplay.servicios.vision import MatchStats

DELTA_REPUTACION_MAXIMO = 15  # cuanto puede mover la reputacion una sola entrevista
HISTORIAL_QUE_SE_MIRA = 10
SEQUIA = 3  # partidos sin gol para que cortarla sea noticia
RACHA = 3
RATING_CAIDA_ANTES, RATING_CAIDA_AHORA = 7.3, 6.3
PALABRAS_SECAS = 8

# los tres periodistas: (nombre, medio)
PERIODISTAS = (
    ("Ignacio Ferrada", "Pizarra Tactica"),
    ("Valentina Aros", "Radio Tribuna"),
    ("Rocco Salinas", "El Picante"),
)

# cuanto suma o resta cada eje segun el resultado (antes de la intensidad)
BASE = {
    "humildad_equipo": {"victoria": 3, "empate": 2, "derrota": 2},
    "amor_hinchada": {"victoria": 3, "empate": 2, "derrota": 2},
    "ambicion_foco": {"victoria": 3, "empate": 1, "derrota": 0},
    "ego_confianza": {"victoria": 2, "empate": -2, "derrota": -6},
    "excusa_polemica": {"victoria": -2, "empate": -4, "derrota": -6},
    lexico.NEUTRO: {"victoria": 0, "empate": 0, "derrota": 0},
}
CARINO = {"humildad_equipo": 1, "amor_hinchada": 3, "ambicion_foco": 1, "excusa_polemica": -2, lexico.NEUTRO: 0}
CLAVE_EJE = {"humildad_equipo": "humildad", "amor_hinchada": "hinchada", "ego_confianza": "ego",
             "excusa_polemica": "excusa", "ambicion_foco": "ambicion"}
PERSONALIDAD_CALZA = {
    "humilde": {"humildad_equipo", "amor_hinchada"},
    "carismatico": {"amor_hinchada", "ego_confianza"},
    "polemico": {"excusa_polemica", "ego_confianza"},
    "reservado": {lexico.NEUTRO, "humildad_equipo"},
}


class ReaccionPrensa(BaseModel):
    reaccion_prensa: str
    delta_reputacion: int
    nuevo_gancho_narrativo: str = ""  # vacio si no surgio ninguno
    eje: str = lexico.NEUTRO  # lo que dominaron sus respuestas
    cita: str = ""  # la frase que sale en la prensa entre «»
    delta_carino: int = 0  # para la hinchada de su club (servicios/clubes.py)
    tono: str = "neutral"


def resultado_de(stats: MatchStats) -> str:
    if stats.goles_equipo > stats.goles_rival:
        return "victoria"
    if stats.goles_equipo < stats.goles_rival:
        return "derrota"
    return "empate"


def describir_partido(stats: MatchStats) -> str:
    marcador = f"{stats.goles_equipo}-{stats.goles_rival}"
    partes = [f"{resultado_de(stats).capitalize()} {marcador}"]
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


def apellido(perfil: PlayerProfile) -> str:
    partes = perfil.nombre_jugador.split()
    return partes[-1] if partes else "El jugador"


def _goles_texto(goles: int) -> str:
    return "un gol" if goles == 1 else f"{goles} goles"


def _historial(perfil: PlayerProfile) -> list[MatchInterviewRecord]:
    if not perfil.id:
        return []
    from roleplay import database

    return [r for r in database.load_match_interviews(perfil.id) if r.origen != "previa"][:HISTORIAL_QUE_SE_MIRA]


def _carrera():
    try:
        from roleplay.partida.lector import carrera_actual

        return carrera_actual()
    except Exception:  # noqa: BLE001  (sin partida, las preguntas salen igual)
        return None


def _tabla(carrera, stats: MatchStats) -> Optional[dict]:
    """Como se movio la tabla de la liga con el ultimo partido (si es este)."""
    if carrera is None:
        return None
    equipo = carrera.equipo_usuario()
    ultimo = carrera.ultimo_partido_de(equipo) if equipo is not None else None
    if ultimo is None or carrera.equipo(ultimo.rival(equipo)) != stats.equipo_rival:
        return None
    competicion = carrera.competiciones.get(ultimo.competicion)
    if competicion is None or not competicion.es_liga:
        return None
    ahora = carrera.posicion_en(ultimo.competicion, equipo)
    antes = replace(carrera, partidos=[p for p in carrera.partidos if p is not ultimo]).posicion_en(ultimo.competicion, equipo)
    if not ahora or not antes or ahora == antes:
        return None
    return {"posicion": f"{ahora}°", "posicion_antes": f"{antes}°", "liga": carrera.competicion(ultimo.competicion),
            "sube": ahora < antes}


def _memoria(stats: MatchStats, historial: list[MatchInterviewRecord]) -> dict:
    """Lo que sale de comparar este partido con los anteriores."""
    memoria = {}
    sin_gol = 0
    for r in historial:
        if r.goles_jugador:
            break
        sin_gol += 1
    con_gol = 0
    for r in historial:
        if not r.goles_jugador:
            break
        con_gol += 1
    if stats.goles_jugador and sin_gol >= SEQUIA:
        memoria["sequia_rota"] = sin_gol
    if stats.goles_jugador and con_gol + 1 >= RACHA:
        memoria["racha"] = con_gol + 1
    ultimos = [r.rating_jugador for r in historial[:3] if r.rating_jugador]
    if len(ultimos) == 3 and 0 < stats.rating_jugador < RATING_CAIDA_AHORA and sum(ultimos) / 3 >= RATING_CAIDA_ANTES:
        memoria["caida"] = round(sum(ultimos) / 3, 1)
    anterior = next((r for r in historial if stats.equipo_rival and r.equipo_rival == stats.equipo_rival), None)
    if anterior is not None:
        memoria["mismo_rival"] = f"{anterior.goles_equipo}-{anterior.goles_rival}"
    if historial and historial[0].respuestas_jugador:
        lectura = lexico.leer(historial[0].respuestas_jugador)
        if lectura.eje == "ego_confianza" and lectura.cita and resultado_de(stats) == "derrota":
            memoria["contradiccion"] = (lectura.cita, historial[0].equipo_rival or "su ultimo rival")
    return memoria


def _elegir(candidatas: list[tuple[float, str, dict]], escritor, reserva: list) -> tuple[str, dict]:
    """La de mas prioridad que el corpus pueda escribir (entre empatadas, al azar)."""
    posibles = [(p, s, d) for p, s, d in candidatas if escritor.puede(s, **d)]
    posibles = posibles or [(p, s, d) for p, s, d in reserva if escritor.puede(s, **d)]
    tope = max(p for p, _, _ in posibles)
    _, simbolo, datos = escritor.dado.choice([c for c in posibles if c[0] == tope])
    return simbolo, datos


def generar_entrevista(perfil: PlayerProfile, stats: MatchStats) -> list[str]:
    """Las tres preguntas (tactico, vestuario, picante)."""
    historial = _historial(perfil)
    carrera = _carrera()
    resultado = resultado_de(stats)
    base = {
        "nombre": perfil.nombre_jugador, "apellido": apellido(perfil), "club": perfil.club_actual or "el equipo",
        "rival": stats.equipo_rival or "el rival", "marcador": f"{stats.goles_equipo}-{stats.goles_rival}",
        "goles": stats.goles_jugador, "goles_texto": _goles_texto(stats.goles_jugador),
        "rating": f"{stats.rating_jugador:.1f}", "minutos": stats.minutos_jugados,
    }
    memoria = _memoria(stats, historial)
    cruces = cruce.cruces(perfil.id, stats.equipo_rival, stats.rating_jugador or None, carrera)
    usados = set()

    tactico = [(1, f"tac_{resultado}" if resultado != "victoria" else
                ("tac_victoria_gol" if stats.goles_jugador else "tac_victoria_sin_gol"), base)]
    if stats.goles_jugador >= 3:
        tactico.append((9, "tac_hat_trick", base))
    if stats.tarjeta_roja:
        tactico.append((9, "tac_roja", base))
    if "sequia_rota" in memoria:
        tactico.append((8, "tac_sequia_rota", {**base, "partidos_sin_gol": memoria["sequia_rota"]}))
    if "caida" in memoria:
        tactico.append((8, "tac_caida", {**base, "promedio_antes": memoria["caida"]}))
    if "mismo_rival" in memoria:
        tactico.append((6, "tac_mismo_rival", {**base, "marcador_antes": memoria["mismo_rival"]}))
    tabla = _tabla(carrera, stats)
    if tabla:
        tactico.append((7, "tac_tabla_sube" if tabla["sube"] else "tac_tabla_baja", {**base, **tabla}))
    if "racha" in memoria:
        tactico.append((6, "tac_racha", {**base, "racha": memoria["racha"]}))
    if stats.hombre_del_partido:
        tactico.append((5, "tac_figura", base))
    if 0 < stats.minutos_jugados < 45:
        tactico.append((4, "tac_pocos_minutos", base))

    vestuario = [(1, f"ves_{resultado}", base), (0.5, "ves_generico", base)]
    for c in cruces:
        if c.tipo in ("meta_cerca", "meta_tabla", "hinchada_contra", "idolo", "ex_club_traidor", "ex_club_idolo",
                      "ex_club_mala"):
            vestuario.append((c.peso, f"ves_{c.tipo}", {**base, **c.datos}))

    picante = [(1, "pic_generico", base)]
    if perfil.personalidad == "polemico":
        picante.append((2, "pic_polemico", base))
    if "contradiccion" in memoria:
        cita, rival_anterior = memoria["contradiccion"]
        picante.append((10, "pic_contradiccion", {**base, "cita_anterior": cita, "rival_anterior": rival_anterior}))
    for c in cruces:
        if c.tipo in ("compra_mal", "compra_bien", "pareja_real", "pareja_famosa", "rumor", "crisis", "evento_malo",
                      "evento_bueno", "ex_club_traidor", "hinchada_contra"):
            picante.append((c.peso - 0.5, f"pic_{c.tipo}", {**base, **c.datos}))

    preguntas = []
    with narrador(perfil.id, "entrevista") as escritor:
        for (nombre, medio), candidatas in zip(PERIODISTAS, (tactico, vestuario, picante)):
            libres = [c for c in candidatas if c[1].split("_", 1)[1] not in usados]
            simbolo, datos = _elegir(libres, escritor, candidatas)
            usados.add(simbolo.split("_", 1)[1])  # el mismo tema no lo pregunta otro periodista
            preguntas.append(f"{nombre} ({medio}): {escritor.decir(simbolo, **datos)}")
    return preguntas


# ---- la evaluacion ----


def _delta(lectura: lexico.Lectura, resultado: str, rating: float, personalidad: str, tope: int) -> int:
    base = BASE[lectura.eje][resultado]
    if lectura.eje == "ego_confianza" and resultado == "victoria" and rating and rating < 7.5:
        base = -2  # sacar pecho sin haber jugado bien
    delta = base * (1 + min(lectura.intensidad, 9) / 6)
    if lectura.eje in PERSONALIDAD_CALZA.get(personalidad, set()):
        delta += 1  # coherente con su imagen
    if rating >= 8.5:
        delta += 1
    elif 0 < rating < 5.5 and lectura.eje == "ego_confianza":
        delta -= 2
    if lectura.palabras < PALABRAS_SECAS and personalidad != "reservado":
        delta -= 1
    if lectura.promesa:
        delta += 1
    return max(-tope, min(tope, round(delta)))


def _carino(lectura: lexico.Lectura, resultado: str) -> int:
    if lectura.eje == "ego_confianza":
        return -3 if resultado == "derrota" else 0
    valor = CARINO[lectura.eje]
    return valor * 2 if lectura.intensidad >= 6 else valor


def _bien(lectura: lexico.Lectura, resultado: str, delta: int) -> str:
    if lectura.eje in ("ego_confianza", "excusa_polemica"):
        return "bien" if delta > 0 else "mal"
    return "mal" if resultado == "derrota" else "bien"


def tono_de(delta: int) -> str:
    return "positiva" if delta >= 2 else "negativa" if delta <= -2 else "mixta" if delta else "neutral"


def reaccionar(escritor, perfil: PlayerProfile, lectura: lexico.Lectura, delta: int, apertura: str, datos: dict,
               cruces: list) -> str:
    """La reaccion de la prensa: [apertura] + [lo que dijo] + [cruce] + [cierre]."""
    datos = {**datos, "apellido": apellido(perfil), "cita": lectura.cita}
    if lectura.palabras < PALABRAS_SECAS:
        nucleo = escritor.elegir("r_vacio", **datos)
    elif lectura.eje == lexico.NEUTRO:
        nucleo = escritor.elegir("r_neutro", **datos)
    else:
        nucleo = escritor.elegir(f"r_{CLAVE_EJE[lectura.eje]}_{_bien(lectura, datos.get('resultado', ''), delta)}", **datos)
    extra = next((escritor.elegir(f"r_cruce_{c.tipo}", **{**datos, **c.datos}) for c in cruces
                  if escritor.puede(f"r_cruce_{c.tipo}", **{**datos, **c.datos})), "")
    cierre = escritor.elegir(f"r_cierre_{'positivo' if delta >= 2 else 'negativo' if delta <= -2 else 'neutro'}", **datos)
    inicio = escritor.elegir(apertura, **datos)
    if inicio.endswith(",") and nucleo[:1].isupper() and not nucleo.startswith(datos["apellido"]):
        nucleo = nucleo[0].lower() + nucleo[1:]  # "Tras perder con X, respuestas cortas de..."
    texto = unir(inicio, nucleo, extra, cierre)
    escritor.anotar(texto)
    return texto


def gancho(escritor, lectura: lexico.Lectura) -> str:
    return escritor.elegir("gancho_promesa", promesa=lectura.promesa) if lectura.promesa else ""


def evaluar_respuestas(
    perfil: PlayerProfile, stats: MatchStats, respuestas: list[tuple[str, str]]
) -> ReaccionPrensa:
    """Reaccion de prensa + impacto en reputacion (ya acotado) + carino."""
    lectura = lexico.leer([r for _, r in respuestas])
    resultado = resultado_de(stats)
    delta = _delta(lectura, resultado, stats.rating_jugador, perfil.personalidad, DELTA_REPUTACION_MAXIMO)
    datos = {"rival": stats.equipo_rival or "el rival", "marcador": f"{stats.goles_equipo}-{stats.goles_rival}",
             "club": perfil.club_actual or "el equipo", "resultado": resultado}
    cruces = cruce.cruces(perfil.id, stats.equipo_rival, stats.rating_jugador or None, _carrera())
    with narrador(perfil.id, "entrevista") as escritor:
        texto = reaccionar(escritor, perfil, lectura, delta, f"r_apertura_{resultado}", datos, cruces)
        nuevo_gancho = gancho(escritor, lectura)
    return ReaccionPrensa(
        reaccion_prensa=texto, delta_reputacion=delta, nuevo_gancho_narrativo=nuevo_gancho, eje=lectura.eje,
        cita=lectura.cita if lectura.palabras >= PALABRAS_SECAS else "", delta_carino=_carino(lectura, resultado),
        tono=tono_de(delta),
    )
