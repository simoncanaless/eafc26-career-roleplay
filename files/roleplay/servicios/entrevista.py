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
from roleplay.servicios.memoria import anotar_dichos
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
    if stats.equipo_propio:
        partes.append(f"jugando para la seleccion de {stats.equipo_propio}")
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


PENALIDAD_RECIENTE = 0.1  # una pregunta (simbolo) de las ultimas conferencias pesa 10 veces menos


def _elegir(candidatas: list[tuple[float, str, dict]], escritor, reserva: list,
            recientes=(), la_mejor: bool = False) -> tuple[str, dict]:
    """Lo obligatorio (prioridad >= OBLIGATORIO_DESDE: el hat-trick, la roja) va si o si; lo demas se
    sortea por prioridad, y lo que se pregunto hace poco (`recientes`, los simbolos) casi no sale."""
    posibles = [(p, s, d) for p, s, d in candidatas if escritor.puede(s, **d)]
    posibles = posibles or [(p, s, d) for p, s, d in reserva if escritor.puede(s, **d)]
    tope = max(p for p, _, _ in posibles)
    if la_mejor:  # la pregunta del partido: la de mas datos que no se hizo hace poco
        orden = sorted(posibles, key=lambda c: -c[0])
        _, simbolo, datos = next((c for c in orden if c[1] not in recientes), orden[0])
        return simbolo, datos
    if tope >= OBLIGATORIO_DESDE:
        mejores = [c for c in posibles if c[0] == tope]
        frescas = [c for c in mejores if c[1] not in recientes]
        _, simbolo, datos = escritor.dado.choice(frescas or mejores)
        return simbolo, datos
    pesos = [max(p, 0.2) * (PENALIDAD_RECIENTE if s in recientes else 1) for p, s, _ in posibles]
    _, simbolo, datos = escritor.dado.choices(posibles, weights=pesos)[0]
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


def _sortear_temas(candidatos: dict, pesos: dict, escritor, temas_recientes=()) -> list[str]:
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
        # los temas de la conferencia anterior pesan menos: que no sean siempre los mismos tres
        tema = escritor.dado.choices(resto, weights=[pesos.get(t, 1.0) * (0.4 if t in temas_recientes else 1)
                                                     for t in resto])[0]
        elegidos.append(tema)
        resto.remove(tema)
    del_partido = [t for t in DEL_PARTIDO if t in prioridad]
    if del_partido and not any(t in elegidos for t in DEL_PARTIDO) and len(elegidos) > obligatorios:
        elegidos[-1] = max(del_partido, key=lambda t: (prioridad[t], pesos.get(t, 1.0)))
    return elegidos


def armar_conferencia(perfil: PlayerProfile, candidatos: dict, pesos: dict, contexto: str, cruces) -> list[str]:
    """Tres preguntas de tres periodistas distintos sobre tres temas distintos
    (y, si hay IA, reescritas sobre los mismos temas y hechos)."""
    from roleplay import database

    memoria = database.get_memoria_conferencias(perfil.id) if perfil.id else {}
    recientes = set(memoria.get("simbolos", []))
    temas_recientes = set((memoria.get("temas") or [[]])[0])
    preguntas, usados, simbolos = [], set(), []
    with narrador(perfil.id, "entrevista") as escritor:
        temas = _sortear_temas(candidatos, pesos, escritor, temas_recientes)
        del_partido = next((t for t in temas if t in DEL_PARTIDO), None)  # una pregunta siempre con datos reales
        for tema in temas:
            simbolo, datos = _elegir(candidatos[tema], escritor, candidatos[tema], recientes, la_mejor=tema == del_partido)
            simbolos.append(simbolo)
            nombre, medio = periodista_para(tema, usados, escritor.dado)
            usados.add(nombre.split(" @")[0])
            preguntas.append(f"{nombre} ({medio}): {escritor.decir(simbolo, **datos)}")
    finales = preguntas_con_ia(perfil, contexto, preguntas, cruces, temas, memoria.get("preguntas", [])) or preguntas
    if perfil.id:
        database.set_memoria_conferencias(perfil.id, {
            **memoria,  # (los dichos, de servicios/memoria.py)
            "simbolos": (simbolos + memoria.get("simbolos", []))[:MEMORIA_SIMBOLOS],
            "temas": ([temas] + memoria.get("temas", []))[:MEMORIA_CONFERENCIAS],
            "preguntas": ([p.split(": ", 1)[-1] for p in finales] + memoria.get("preguntas", []))[:MEMORIA_PREGUNTAS],
        })
    return finales


MEMORIA_SIMBOLOS = 12  # las preguntas (simbolos) de las ultimas ~4 conferencias
MEMORIA_CONFERENCIAS = 4
MEMORIA_PREGUNTAS = 15  # los textos, para que la IA no las repita


# la linea de cada posicion (carrera.POSICIONES): un fichaje solo le toca al jugador si es de su linea
LINEA = {
    "arquero": "arco", "libero": "defensa", "carrilero derecho": "defensa", "lateral derecho": "defensa",
    "defensa central": "defensa", "lateral izquierdo": "defensa", "carrilero izquierdo": "defensa",
    "mediocentro defensivo": "medio", "volante derecho": "medio", "mediocentro": "medio", "volante izquierdo": "medio",
    "mediapunta": "medio", "segundo delantero": "ataque", "extremo derecho": "ataque", "delantero centro": "ataque",
    "extremo izquierdo": "ataque",
}


def posicion_del_usuario(carrera) -> str:
    if carrera is None or carrera.usuario_id is None:
        return ""
    return carrera.ficha(carrera.usuario_id).get("posicion", "")


def contexto_de_club(perfil: PlayerProfile, carrera=None) -> dict:
    """Lo del club que no esta en el partido: el ultimo movimiento del mercado
    del club que es DE SU LINEA (un lateral que llega no le toca a un delantero
    centro; uno de su mismo puesto es competencia) y la marca con la que tiene
    contrato. Sin saber su posicion (o la del otro), no se pregunta por fichajes."""
    if not perfil.id:
        return {}
    from roleplay import database

    extra = {}
    carrera = carrera if carrera is not None else _carrera()
    propia = posicion_del_usuario(carrera)
    if propia:
        extra["posicion"] = propia
    for m in database.get_estado_prensa(perfil.id).get("mercado", []):
        if not (m.get("club") and m.get("texto") and m.get("posicion") and propia):
            continue
        if LINEA.get(m["posicion"]) != LINEA.get(propia) or m.get("jugador") == getattr(carrera, "usuario_id", None):
            continue
        extra.update(movimiento=m["texto"].strip().rstrip("."), llega=bool(m.get("llega")),
                     posicion_fichaje=m["posicion"])
        if m["posicion"] == propia:
            extra["puesto_compartido"] = propia
        break
    contratos = (database.get_economia(perfil.id).get("patrocinios") or {}).get("contratos") or []
    if contratos:
        from roleplay.servicios import patrocinios

        extra["marca"] = patrocinios.nombre_de(contratos[-1])  # el nombre de hoy (no "una bebida isotonica")
        extra["marca_campanas"] = contratos[-1].get("cumplidas", 0) > 0  # ya hizo promos: "te vimos en la campana"
    return extra


# preguntas que solo tienen sentido DESPUES del partido: en la previa van sus versiones pv_pic_*
SOLO_DESPUES_DEL_PARTIDO = {"pareja_real", "pareja_famosa", "compra_bien", "compra_mal"}


def temas_comunes(perfil: PlayerProfile, base: dict, cruces, extra: dict,
                  previa: bool = False, carrera=None) -> tuple[dict, dict]:
    """Los candidatos y pesos que valen igual antes y despues del partido (`previa`: sin preguntar
    por lo que paso en un partido que todavia no se jugo)."""
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
        datos_mercado = {**base, "movimiento": extra["movimiento"], "posicion_fichaje": extra["posicion_fichaje"]}
        if extra.get("puesto_compartido"):
            datos_mercado["puesto_compartido"] = extra["puesto_compartido"]
        simbolo = "tema_mercado_llega" if extra.get("llega") else "tema_mercado_sale"
        candidatos["mercado"].append((6, simbolo, datos_mercado))
        pesos["mercado"] += 3
    if extra.get("marca"):
        candidatos["contratos"].append((5, "tema_patrocinio", {**base, "marca": extra["marca"]}))
        if extra.get("marca_campanas"):
            candidatos["contratos"].append((5, "tema_patrocinio_campanas", {**base, "marca": extra["marca"]}))
        pesos["contratos"] += 1.5
    for tema, prioridad, simbolo, datos in temas_de_los_datos(perfil, carrera, base) + repregunta(perfil, base):
        candidatos[tema].append((prioridad, simbolo, datos))
        pesos[tema] += 0.5
    for c in cruces:
        datos = {**base, **c.datos}
        if c.tipo in TIPOS_VIDA:
            simbolo = f"pv_pic_{c.tipo}" if previa and c.tipo in SOLO_DESPUES_DEL_PARTIDO else f"pic_{c.tipo}"
            candidatos["vida_privada"].append((c.peso - 0.5, simbolo, datos))
            pesos["vida_privada"] += 2
        if c.tipo in TIPOS_HINCHADA:
            candidatos["hinchada"] += [(c.peso, f"ves_{c.tipo}", datos), (c.peso - 0.5, f"pic_{c.tipo}", datos)]
            pesos["hinchada"] += 2
    return candidatos, pesos


def _compacto(n: int) -> str:
    return f"{n / 1_000_000:.1f} millones".replace(".0 ", " ").replace(".", ",") if n >= 1_000_000 else f"{n // 1000} mil"


def temas_de_los_datos(perfil: PlayerProfile, carrera, base: dict) -> list[tuple[str, float, str, dict]]:
    """Preguntas sobre lo que la app sabe de verdad: goles de la temporada y de la carrera, asistencias,
    racha sin perder del club, el ultimo premio, ofertas de clubes que se filtraron, las primas (firmadas o
    la negociacion rota), un hijo o una boda recientes y los seguidores. [(tema, prioridad, simbolo, datos)]."""
    if not perfil.id:
        return []
    from datetime import date

    from roleplay import database
    from roleplay.servicios import ecosistema
    from roleplay.servicios.partida_real import temporada_de

    resultado = []
    hoy = (carrera.fecha_actual() if carrera is not None else None) or date.today()

    def dias(fecha: str) -> int:
        try:
            return (hoy - date.fromisoformat(fecha[:10])).days
        except (TypeError, ValueError):
            return 9999

    if carrera is not None and carrera.usuario_id is not None:
        goles = ecosistema.goles_de_la_temporada(carrera)
        if goles >= 5:
            resultado.append(("racha", 3, "tac_goles_temporada", {**base, "goles_temporada": goles}))
        asistencias = ecosistema.asistencias_de_la_temporada(carrera)
        if asistencias >= 5:
            resultado.append(("tactica", 2.5, "tac_asistencias", {**base, "asistencias": asistencias}))
        goles_carrera = sum(e.goles for e in carrera.etapas)
        if goles_carrera >= 20:
            resultado.append(("racha", 2.5, "tac_goles_carrera", {
                **base, "goles_carrera": goles_carrera, "partidos_carrera": sum(e.partidos for e in carrera.etapas)}))
        equipo = carrera.equipo_usuario()
        invicto = 0
        for partido in reversed(carrera.partidos_de(equipo, jugados=True) if equipo is not None else []):
            if partido.resultado_para(equipo) == "derrota":
                break
            invicto += 1
        if invicto >= 5:
            resultado.append(("tactica", 3.5, "tac_invicto", {**base, "invicto": invicto}))
    temporada = temporada_de(hoy)
    vitrina = [p for p in database.get_estado_prensa(perfil.id).get("vitrina", []) if p.get("temporada") == temporada]
    if vitrina:
        resultado.append(("racha", 4, "pic_premio_reciente", {**base, "premio": vitrina[-1]["premio"]}))
    e = database.get_economia(perfil.id)
    for oferta in ((e.get("ofertas") or {}).get("lista") or [])[:3]:
        if oferta.get("tier", 3) <= 2 and dias(oferta.get("fecha", "")) <= 30:  # la de un grande se filtra
            resultado.append(("mercado", 6, "tema_oferta_filtrada", {**base, "club_oferta": oferta["club"]}))
            break
    contrato = e.get("contrato") or {}
    if contrato and dias(contrato.get("desde", "")) <= 60:
        resultado.append(("contratos", 4, "tema_primas", base))
    if (e.get("negociacion_rota") or {}).get("temporada") == temporada:
        resultado.append(("contratos", 5, "tema_negociacion_rota", base))
    amor = database.get_estado_amor(perfil.id)
    bebe = next((h for h in reversed(amor.get("hijos") or []) if dias(h.get("nacimiento", "")) <= 90), None)
    if bebe:
        resultado.append(("vida_privada", 6, "pic_hijo", {**base, "bebe": bebe["nombre"]}))
    if amor.get("estado") == "casado" and amor.get("pareja") and dias(amor.get("casados", "")) <= 90:
        resultado.append(("vida_privada", 5, "pic_boda", {**base, "pareja": amor["pareja"]["nombre"]}))
    seguidores = database.get_seguidores(perfil.id)
    if seguidores >= 100_000:
        resultado.append(("vida_privada", 1.5, "pic_seguidores", {**base, "seguidores": _compacto(seguidores)}))
    return resultado


# la repregunta: de que tema es lo que dijo la vez pasada (segun el eje del lexico)
TEMA_DE_EJE = {"excusa_polemica": "arbitraje", "ego_confianza": "vida_privada", "amor_hinchada": "hinchada",
               "humildad_equipo": "vestuario", "ambicion_foco": "racha", "promesa": "racha"}


def repregunta(perfil: PlayerProfile, base: dict) -> list[tuple[str, float, str, dict]]:
    """Lo que dijo en la conferencia anterior, de vuelta: "la vez pasada dijiste «...». ¿Lo sostenes?"."""
    if not perfil.id:
        return []
    from roleplay import database

    anterior = next((r for r in database.load_match_interviews(perfil.id) if any(r.respuestas_jugador or [])), None)
    if anterior is None:
        return []
    lectura = lexico.leer(anterior.respuestas_jugador)
    cita = lectura.promesa or lectura.cita
    eje = "promesa" if lectura.promesa else lectura.eje
    if not cita or len(cita) < 15 or eje not in TEMA_DE_EJE:
        return []
    datos = {**base, "cita_anterior": cita.strip().rstrip(".")[:140], "rival_anterior": anterior.equipo_rival or "el rival"}
    return [(TEMA_DE_EJE[eje], 6 if eje == "promesa" else 5, f"rep_{eje}", datos)]


def generar_entrevista(perfil: PlayerProfile, stats: MatchStats) -> list[str]:
    """Tres preguntas de tres periodistas, sobre tres de las 8 tematicas:
    lo mas jugoso del partido y de su vida va si o si; el resto se sortea
    con pesos segun el contexto (roja, derrota, mercado, rumores...)."""
    historial = _historial(perfil)
    carrera = _carrera()
    resultado = resultado_de(stats)
    base = {
        "nombre": perfil.nombre_jugador, "apellido": apellido(perfil),
        "club": stats.equipo_propio or perfil.club_actual or "el equipo",  # (con la seleccion, la seleccion)
        "rival": stats.equipo_rival or "el rival", "marcador": f"{stats.goles_equipo}-{stats.goles_rival}",
        "goles": stats.goles_jugador, "goles_texto": _goles_texto(stats.goles_jugador),
        "rating": f"{stats.rating_jugador:.1f}", "minutos": stats.minutos_jugados,
    }
    memoria = _memoria(stats, historial)
    cruces = cruce.cruces(perfil.id, stats.equipo_rival, stats.rating_jugador or None, carrera)
    tabla = _tabla(carrera, stats)
    extra = contexto_de_club(perfil, carrera)
    candidatos, pesos = temas_comunes(perfil, base, cruces, extra, carrera=carrera)

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
    if extra.get("posicion"):
        contexto.append(f"Posicion del jugador en su club: {extra['posicion']}")
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
    "tal cual: nunca le atribuyas al jugador una posicion, un rol o una zona de la cancha distinta de la que "
    "dicen los datos. Los numeros (la tabla, los puntos, las rachas, los goles) son SOLO los de los datos: no "
    "digas que dos equipos estan cerca en la tabla si los datos dicen lo contrario, ni inventes resultados. Si "
    "la conferencia es PREVIA, el partido todavia no se jugo: no preguntes por como jugo, a quien le dedico el "
    "partido ni quien estaba mirando. Cada periodista tiene su voz y su memoria: si en la memoria del roleplay hay "
    "algo que el jugador dijo antes (una promesa, una frase fuerte, una evasiva) o una trama abierta que toca su "
    "tema, puede retomarlo (\"la otra vez dijiste...\"), citando textual solo lo que esta en la memoria. "
    "Cada periodista le habla AL JUGADOR (por su nombre o sin nombre): nunca pongas el nombre del periodista "
    "dentro de la pregunta. Devolve las preguntas en el mismo orden, sin el nombre del periodista adelante."
)
SISTEMA_REACCION = (
    "Sos la prensa deportiva que cubre la conferencia de un futbolista en un juego de roleplay. "
    "`reaccion_prensa`: 3 a 4 oraciones en tono periodistico, en tercera persona, que analicen y contesten "
    "ESPECIFICAMENTE lo que dijo el jugador (sus argumentos, quejas, chistes o detalles; podes citarlo textual "
    "entre «»), conectandolo con el partido y, si aplica, con lo primero de su vida. Tono del periodismo deportivo "
    "actual (streaming, debates, zona mixta): si pone excusas o dice algo fuerte, la prensa le contesta con polemica. "
    "`delta_reputacion`: entero (cuanto le suma o resta a su reputacion; parti del sugerido por el sistema). "
    "`delta_carino`: entero de -6 a 6 (la hinchada de su club). `cita`: su frase mas jugosa COPIADA TEXTUAL de "
    "sus respuestas, o vacio. `nuevo_gancho_narrativo`: una trama que deja abierta (promesa, desafio), o vacio. "
    "La prensa se acuerda: si hoy cumple, contradice o repite algo de lo que dijo antes (esta en la memoria), "
    "marcalo. Se juzga SOLO lo que respondio: los datos del partido y del rival son contexto, nunca motivo de critica; no "
    "traigas a jugadores del rival si el no los nombro, y no le pongas cargos (capitan, lider del vestuario) que "
    "no esten en los datos."
)


def _nombra_ajenos(texto: str, ajenos, respuestas) -> bool:
    """La IA trajo a un jugador ajeno (el goleador del rival...) que el jugador no nombro."""
    dicho, escrito = lexico.normalizar(" ".join(respuestas)), lexico.normalizar(texto)
    for nombre in ajenos:
        apellido = lexico.normalizar(nombre).split()[-1] if nombre.strip() else ""
        if len(apellido) >= 4 and apellido in escrito and apellido not in dicho:
            return True
    return False


def preguntas_con_ia(perfil: PlayerProfile, contexto: str, preguntas: list[str], cruces,
                     temas: Optional[list[str]] = None, recientes: Optional[list[str]] = None) -> Optional[list[str]]:
    """Las mismas preguntas (mismo periodista, mismo tema) reescritas por la IA, o None. `recientes`: las de
    las ultimas conferencias, que no tiene que repetir ni parafrasear."""
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
        + (f"Preguntas de sus ultimas conferencias (NO las repitas ni las parafrasees, busca otro angulo):\n"
           + "\n".join(f"- {r[:200]}" for r in (recientes or [])[:MEMORIA_PREGUNTAS]) + "\n\n" if recientes else "")
        + f"Las preguntas base:\n{lista}",
        {"preguntas": [f"pregunta {i + 1}" for i in range(len(partes))]},
        jugador=perfil.id,
    )
    nuevas = datos.get("preguntas") if datos else None
    if not isinstance(nuevas, list) or len(nuevas) != len(partes):
        return None
    limpias = []
    for (quien, base), pregunta in zip(partes, nuevas):
        pregunta = ia.texto(pregunta, 400)
        nombre = quien.split(" (")[0].split(" @")[0]
        if pregunta.startswith(nombre) and ": " in pregunta[:120]:
            pregunta = pregunta.split(": ", 1)[1]
        de_pila = nombre.split()[0] if nombre.split() else ""
        if de_pila and pregunta.startswith(de_pila + ","):  # le hablo al periodista en vez de al jugador
            pregunta = (perfil.nombre_jugador.split() or [""])[0] + pregunta[len(de_pila):]
        limpias.append(f"{quien}: {pregunta or base}")  # (vacia = la guardia de hechos la tiro: queda la del motor)
    return limpias


def reaccion_con_ia(perfil: PlayerProfile, contexto: str, respuestas: list[tuple[str, str]], cruces,
                    lectura: lexico.Lectura, delta: int, carino: int, tope: int,
                    con_titular: bool = False, ajenos: tuple = ()) -> Optional[dict]:
    """La reaccion escrita por la IA contestando a lo que dijo, o None.
    Devuelve reaccion, delta (acotado a tope), carino (+-6), cita (solo si
    es textual; si no, la del lexico), gancho y, si se pide, titular.
    `ajenos`: nombres de otros (el goleador del rival) que la nota no puede
    traer si el jugador no los nombro: si los trae, None (queda la del motor
    local; 2026-10-20, una nota lo culpo del "bajo rendimiento" del goleador del rival)."""
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
        jugador=perfil.id,
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
    if _nombra_ajenos(resultado["reaccion"] + " " + resultado.get("titular", ""), ajenos, textos):
        return None
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
             "club": stats.equipo_propio or perfil.club_actual or "el equipo", "resultado": resultado}
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
    anotar_dichos(perfil.id, "post", stats.equipo_rival, [r for _, r in respuestas], cita)
    return ReaccionPrensa(
        reaccion_prensa=texto, delta_reputacion=delta, nuevo_gancho_narrativo=nuevo_gancho, eje=lectura.eje,
        cita=cita, delta_carino=carino, tono=tono_de(delta),
    )
