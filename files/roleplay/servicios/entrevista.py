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

IA hibrida (servicios/ia.py, opcional): con todo lo anterior ya calculado,
la IA reescribe las preguntas con los mismos temas y hechos, y escribe la
reaccion contestando a lo que dijo el jugador (sus deltas, acotados). Si no
hay IA, queda lo del motor local tal cual.
"""

from dataclasses import replace
from typing import Optional

from pydantic import BaseModel

from roleplay.models import MatchInterviewRecord, PlayerProfile
from roleplay.servicios import cruce, ia, lexico
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


# ---- las 8 tematicas y los periodistas ----

TEMAS = {
    "vestuario": "companeros y vestuario (el nivel de un companero, liderazgos, internas)",
    "mercado": "el mercado de pases del club (los que se fueron, los que llegaron, su futuro)",
    "tactica": "tactica y relacion con el DT",
    "racha": "racha goleadora o sequia, estadisticas y metas",
    "arbitraje": "polemicas arbitrales y cruces con rivales",
    "vida_privada": "vida privada, redes, lo que publican las paginas de futbol y los rumores",
    "contratos": "contratos, patrocinios con marcas y futuro",
    "hinchada": "la presion de la hinchada",
}
# que estilos de periodista (ecosistema_ig.json, datos de Simon) preguntan cada tema
ESTILO_DE_TEMA = {"tactica": ("tactico",), "racha": ("tactico",), "mercado": ("mercado",), "contratos": ("mercado",),
                  "vestuario": ("vestuario",), "hinchada": ("vestuario", "emocional"), "arbitraje": ("polemico",),
                  "vida_privada": ("polemico", "emocional")}
# sin los datos de Simon, los tres de siempre
PROPIOS_POR_ESTILO = {"tactico": PERIODISTAS[0], "vestuario": PERIODISTAS[1], "mercado": PERIODISTAS[1],
                      "polemico": PERIODISTAS[2]}
PREGUNTAS_POR_CONFERENCIA = 3
OBLIGATORIO_DESDE = 7  # una pregunta tan jugosa (hat-trick, roja, sequia, el auto y la mala nota...) no se sortea
TIPOS_VIDA = ("compra_mal", "compra_bien", "pareja_real", "pareja_famosa", "rumor", "rumor_secreto", "crisis",
              "evento_malo", "evento_bueno")
TIPOS_HINCHADA = ("hinchada_contra", "idolo", "ex_club_traidor", "ex_club_idolo", "ex_club_mala")
TIPOS_METAS = ("meta_cerca", "meta_tabla")


def periodista_para(tema: str, usados: set, dado) -> tuple[str, str]:
    """(quien, medio) de un periodista del estilo del tema que no pregunto todavia.
    Los reales firman con su @usuario: "Nombre @usuario". (`usados`: los nombres.)"""
    from roleplay.servicios import ecosistema

    estilos = ESTILO_DE_TEMA.get(tema, ("vestuario",))
    reales = [p for p in ecosistema.periodistas() if str(p.get("nombre", "")).strip() and p["nombre"] not in usados]
    if reales:
        elegido = dado.choice([p for p in reales if p.get("estilo") in estilos] or reales)
        medio = str(elegido.get("medio") or "prensa").replace(":", " -").replace("(", "").replace(")", "")
        usuario = str(elegido.get("usuario_ig") or "").strip()
        quien = str(elegido["nombre"]).strip() + (f" {usuario}" if usuario.startswith("@") else "")
        return quien, medio
    propio = PROPIOS_POR_ESTILO.get(estilos[0], PERIODISTAS[0])
    if propio[0] in usados:
        propio = next((p for p in PERIODISTAS if p[0] not in usados), propio)
    return propio


DEL_PARTIDO = ("tactica", "racha")  # siempre va al menos una pregunta sobre el partido


def _sortear_temas(candidatos: dict, pesos: dict, escritor) -> list[str]:
    """Los obligatorios (lo mas jugoso) y el resto por sorteo ponderado por el
    contexto; si no salio ninguna sobre el partido, la ultima sorteada se cambia."""
    prioridad = {}
    for tema, lista in candidatos.items():
        escribibles = [p for p, s, d in lista if escritor.puede(s, **d)]
        if escribibles:
            prioridad[tema] = max(escribibles)
    elegidos = sorted((t for t, p in prioridad.items() if p >= OBLIGATORIO_DESDE), key=lambda t: -prioridad[t])
    elegidos = elegidos[:PREGUNTAS_POR_CONFERENCIA]
    resto = [t for t in prioridad if t not in elegidos]
    obligatorios = len(elegidos)
    while len(elegidos) < PREGUNTAS_POR_CONFERENCIA and resto:
        tema = escritor.dado.choices(resto, weights=[pesos.get(t, 1.0) for t in resto])[0]
        elegidos.append(tema)
        resto.remove(tema)
    del_partido = [t for t in DEL_PARTIDO if t in prioridad]
    if del_partido and not any(t in elegidos for t in DEL_PARTIDO) and len(elegidos) > obligatorios:
        elegidos[-1] = max(del_partido, key=lambda t: (prioridad[t], pesos.get(t, 1.0)))
    return elegidos


def armar_conferencia(perfil: PlayerProfile, candidatos: dict, pesos: dict, contexto: str, cruces) -> list[str]:
    """Tres preguntas de tres periodistas distintos sobre tres temas distintos
    (y, si hay IA, reescritas sobre los mismos temas y hechos)."""
    preguntas, usados = [], set()
    with narrador(perfil.id, "entrevista") as escritor:
        temas = _sortear_temas(candidatos, pesos, escritor)
        for tema in temas:
            simbolo, datos = _elegir(candidatos[tema], escritor, candidatos[tema])
            nombre, medio = periodista_para(tema, usados, escritor.dado)
            usados.add(nombre.split(" @")[0])
            preguntas.append(f"{nombre} ({medio}): {escritor.decir(simbolo, **datos)}")
    return preguntas_con_ia(perfil, contexto, preguntas, cruces, temas) or preguntas


def contexto_de_club(perfil: PlayerProfile) -> dict:
    """Lo del club que no esta en el partido: el ultimo movimiento del mercado
    que toco al club y la marca con la que tiene contrato."""
    if not perfil.id:
        return {}
    from roleplay import database

    extra = {}
    movimientos = [m for m in database.get_estado_prensa(perfil.id).get("mercado", []) if m.get("club") and m.get("texto")]
    if movimientos:
        extra["movimiento"] = movimientos[0]["texto"].strip().rstrip(".")
    contratos = (database.get_economia(perfil.id).get("patrocinios") or {}).get("contratos") or []
    if contratos:
        extra["marca"] = contratos[-1]["nombre"]
    return extra


def temas_comunes(perfil: PlayerProfile, base: dict, cruces, extra: dict) -> tuple[dict, dict]:
    """Los candidatos y pesos que valen igual antes y despues del partido."""
    candidatos = {t: [] for t in TEMAS}
    pesos = {t: 1.0 for t in TEMAS}
    candidatos["vestuario"].append((2, "tema_vestuario", base))
    candidatos["hinchada"].append((1.5, "tema_hinchada", base))
    candidatos["arbitraje"].append((2, "tema_arbitraje", base))
    candidatos["vida_privada"] += [(1, "pic_generico", base), (1, "tema_vida", base)]
    candidatos["mercado"].append((1, "tema_mercado_futuro", base))
    candidatos["contratos"].append((1, "tema_contratos", base))
    candidatos["tactica"].append((2, "tema_tactica", base))
    if perfil.personalidad == "polemico":
        candidatos["arbitraje"].append((3, "pic_polemico", base))
        pesos["arbitraje"] += 1
        pesos["vida_privada"] += 1
    if extra.get("movimiento"):
        candidatos["mercado"].append((6, "tema_mercado", {**base, "movimiento": extra["movimiento"]}))
        pesos["mercado"] += 3
    if extra.get("marca"):
        candidatos["contratos"].append((5, "tema_patrocinio", {**base, "marca": extra["marca"]}))
        pesos["contratos"] += 1.5
    for c in cruces:
        datos = {**base, **c.datos}
        if c.tipo in TIPOS_VIDA:
            candidatos["vida_privada"].append((c.peso - 0.5, f"pic_{c.tipo}", datos))
            pesos["vida_privada"] += 2
        if c.tipo in TIPOS_HINCHADA:
            candidatos["hinchada"] += [(c.peso, f"ves_{c.tipo}", datos), (c.peso - 0.5, f"pic_{c.tipo}", datos)]
            pesos["hinchada"] += 2
    return candidatos, pesos


def generar_entrevista(perfil: PlayerProfile, stats: MatchStats) -> list[str]:
    """Tres preguntas de tres periodistas, sobre tres de las 8 tematicas:
    lo mas jugoso del partido y de su vida va si o si; el resto se sortea
    con pesos segun el contexto (roja, derrota, mercado, rumores...)."""
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
    tabla = _tabla(carrera, stats)
    candidatos, pesos = temas_comunes(perfil, base, cruces, contexto_de_club(perfil))

    candidatos["tactica"].append((1, f"tac_{resultado}" if resultado != "victoria" else "tac_victoria_sin_gol", base))
    candidatos["vestuario"] += [(1, f"ves_{resultado}", base), (0.5, "ves_generico", base)]
    racha = candidatos["racha"]
    if resultado == "victoria" and stats.goles_jugador:
        racha.append((1, "tac_victoria_gol", base))
    if stats.goles_jugador >= 3:
        racha.append((9, "tac_hat_trick", base))
    if "sequia_rota" in memoria:
        racha.append((8, "tac_sequia_rota", {**base, "partidos_sin_gol": memoria["sequia_rota"]}))
    if "caida" in memoria:
        racha.append((8, "tac_caida", {**base, "promedio_antes": memoria["caida"]}))
    if "mismo_rival" in memoria:
        racha.append((6, "tac_mismo_rival", {**base, "marcador_antes": memoria["mismo_rival"]}))
    if tabla:
        racha.append((7, "tac_tabla_sube" if tabla["sube"] else "tac_tabla_baja", {**base, **tabla}))
    if "racha" in memoria:
        racha.append((6, "tac_racha", {**base, "racha": memoria["racha"]}))
    for c in cruces:
        if c.tipo in TIPOS_METAS:
            racha.append((c.peso, f"ves_{c.tipo}", {**base, **c.datos}))
    if any(k in memoria for k in ("sequia_rota", "caida", "racha")) or stats.goles_jugador >= 3:
        pesos["racha"] += 3
    if stats.hombre_del_partido:
        candidatos["tactica"].append((5, "tac_figura", base))
    if 0 < stats.minutos_jugados < 45:
        candidatos["tactica"].append((4, "tac_pocos_minutos", base))
        pesos["tactica"] += 2
    if stats.tarjeta_roja:
        candidatos["arbitraje"].append((9, "tac_roja", base))
    if "contradiccion" in memoria:
        cita, rival_anterior = memoria["contradiccion"]
        candidatos["arbitraje"].append((10, "pic_contradiccion",
                                        {**base, "cita_anterior": cita, "rival_anterior": rival_anterior}))
    if resultado != "victoria":
        pesos["arbitraje"] += 1.5
        pesos["hinchada"] += 2
    contexto = [f"Partido de hoy: {describir_partido(stats)}"]
    if memoria:
        contexto.append(f"Memoria de partidos anteriores: {memoria}")
    if tabla:
        contexto.append(f"Tabla de {tabla['liga']}: paso del {tabla['posicion_antes']} al {tabla['posicion']}")
    if historial and historial[0].respuestas_jugador:
        anterior = zip(historial[0].preguntas_entrevista, historial[0].respuestas_jugador)
        contexto.append("Su entrevista anterior (vs " + (historial[0].equipo_rival or "?") + "): "
                        + " | ".join(f"P: {p[:160]} R: {r[:200]}" for p, r in anterior))
    return armar_conferencia(perfil, candidatos, pesos, "\n".join(contexto), cruces)


# ---- la IA hibrida (opcional) ----

ESTILOS = {
    "Pizarra Tactica": "tactico y de numeros: el partido, la tabla, las rachas",
    "Radio Tribuna": "del vestuario: el grupo, la hinchada, las metas, los ex clubes",
    "El Picante": "picante: lo de afuera de la cancha, la vida privada, las contradicciones",
}
SISTEMA_PREGUNTAS = (
    "Sos el editor de una conferencia de prensa de futbol en un juego de roleplay. Tres periodistas le hacen "
    "una pregunta cada uno al jugador. Reescribi la pregunta de cada periodista con su estilo, sobre EL MISMO "
    "tema que ya se eligio, con variedad y gancho (1 a 2 oraciones, tuteando al jugador), con el tono del "
    "periodismo deportivo actual (streaming, debates, zona mixta): directo y picante. Usa los hechos dados "
    "tal cual. Devolve las preguntas en el mismo orden, sin el nombre del periodista adelante."
)
SISTEMA_REACCION = (
    "Sos la prensa deportiva que cubre la conferencia de un futbolista en un juego de roleplay. "
    "`reaccion_prensa`: 3 a 4 oraciones en tono periodistico, en tercera persona, que analicen y contesten "
    "ESPECIFICAMENTE lo que dijo el jugador (sus argumentos, quejas, chistes o detalles; podes citarlo textual "
    "entre «»), conectandolo con el partido y, si aplica, con lo primero de su vida. Tono del periodismo deportivo "
    "actual (streaming, debates, zona mixta): si pone excusas o dice algo fuerte, la prensa le contesta con polemica. "
    "`delta_reputacion`: entero (cuanto le suma o resta a su reputacion; parti del sugerido por el sistema). "
    "`delta_carino`: entero de -6 a 6 (la hinchada de su club). `cita`: su frase mas jugosa COPIADA TEXTUAL de "
    "sus respuestas, o vacio. `nuevo_gancho_narrativo`: una trama que deja abierta (promesa, desafio), o vacio."
)


def preguntas_con_ia(perfil: PlayerProfile, contexto: str, preguntas: list[str], cruces,
                     temas: Optional[list[str]] = None) -> Optional[list[str]]:
    """Las mismas preguntas (mismo periodista, mismo tema) reescritas por la IA, o None."""
    partes = [p.split(": ", 1) for p in preguntas]
    temas = list(temas or [])
    lista = "\n".join(
        f"{i + 1}. {quien} - "
        + (f"tema: {TEMAS.get(temas[i], temas[i])}" if i < len(temas) else
           f"estilo {next((e for m, e in ESTILOS.items() if m in quien), 'general')}")
        + f". Pregunta base: {base}" for i, (quien, base) in enumerate(partes)
    )
    datos = ia.pedir_json(
        SISTEMA_PREGUNTAS,
        f"{ia.ficha(perfil)}\n{contexto}\nLo que pasa en su vida:\n{ia.describir_cruces(cruces)}\n\n"
        f"Las preguntas base:\n{lista}",
        {"preguntas": [f"pregunta {i + 1}" for i in range(len(partes))]},
    )
    nuevas = datos.get("preguntas") if datos else None
    if not isinstance(nuevas, list) or len(nuevas) != len(partes):
        return None
    limpias = []
    for (quien, _), pregunta in zip(partes, nuevas):
        pregunta = ia.texto(pregunta, 400)
        nombre = quien.split(" (")[0].split(" @")[0]
        if pregunta.startswith(nombre) and ": " in pregunta[:120]:
            pregunta = pregunta.split(": ", 1)[1]
        if not pregunta:
            return None
        limpias.append(f"{quien}: {pregunta}")
    return limpias


def reaccion_con_ia(perfil: PlayerProfile, contexto: str, respuestas: list[tuple[str, str]], cruces,
                    lectura: lexico.Lectura, delta: int, carino: int, tope: int,
                    con_titular: bool = False) -> Optional[dict]:
    """La reaccion escrita por la IA contestando a lo que dijo, o None.
    Devuelve reaccion, delta (acotado a tope), carino (+-6), cita (solo si
    es textual; si no, la del lexico), gancho y, si se pide, titular."""
    pares = "\n".join(f"P: {p}\nR: {r}" for p, r in respuestas)
    esquema = {"reaccion_prensa": "...", "delta_reputacion": 0, "delta_carino": 0, "cita": "...",
               "nuevo_gancho_narrativo": "..."}
    sistema = SISTEMA_REACCION + f" El delta de reputacion va de -{tope} a {tope}."
    if con_titular:
        esquema = {"titular": "...", **esquema}
        sistema += " `titular`: titular de diario con gancho (si hay cita, entre «»)."
    datos = ia.pedir_json(
        sistema,
        f"{ia.ficha(perfil)}\n{contexto}\nLo que pasa en su vida:\n{ia.describir_cruces(cruces)}\n\n"
        f"La conferencia (preguntas y respuestas textuales del jugador):\n{pares}\n\n"
        f"Lectura del sistema: tono dominante {lectura.eje}, delta de reputacion sugerido {delta}, "
        f"carino de la hinchada sugerido {carino}.",
        esquema,
    )
    reaccion = ia.texto(datos.get("reaccion_prensa"), 1000) if datos else ""
    if not reaccion:
        return None
    textos = [r for _, r in respuestas]
    resultado = {
        "reaccion": reaccion,
        "delta": ia.entero(datos.get("delta_reputacion"), tope, delta),
        "carino": ia.entero(datos.get("delta_carino"), 6, carino),
        "cita": ia.cita_literal(datos.get("cita"), textos) or (lectura.cita if lectura.palabras >= PALABRAS_SECAS else ""),
        "gancho": ia.texto(datos.get("nuevo_gancho_narrativo"), 200),
    }
    if con_titular:
        resultado["titular"] = ia.texto(datos.get("titular"), 160)
    return resultado


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
    cita = lectura.cita if lectura.palabras >= PALABRAS_SECAS else ""
    carino = _carino(lectura, resultado)
    hibrida = reaccion_con_ia(perfil, f"Partido: {describir_partido(stats)}", respuestas, cruces, lectura, delta,
                              carino, DELTA_REPUTACION_MAXIMO)
    if hibrida:
        texto, delta, carino, cita = hibrida["reaccion"], hibrida["delta"], hibrida["carino"], hibrida["cita"]
        nuevo_gancho = hibrida["gancho"] or nuevo_gancho
    return ReaccionPrensa(
        reaccion_prensa=texto, delta_reputacion=delta, nuevo_gancho_narrativo=nuevo_gancho, eje=lectura.eje,
        cita=cita, delta_carino=carino, tono=tono_de(delta),
    )
