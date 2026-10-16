"""
Lo que la app hace con la partida de FC 26:

- el ultimo partido del usuario, listo para la sala de prensa (marcador,
  rival, sus goles, nota y minutos; asistencias, tarjetas y figura salen
  comparando con la lectura anterior, porque el juego solo guarda totales);
- los hechos destacados del mundo (hat-tricks, goleadas, choques de punta)
  para la prensa: "City gano 3-1 con 3 goles de Haaland".

Que es noticia lo decide el codigo (puntajes); el motor narrativo redacta y la base local pone
nombres a los jugadores (identificar.py, con cache en la base).
"""

from collections import defaultdict
from dataclasses import dataclass, field, replace
from datetime import date, timedelta
from typing import Optional

from roleplay import database
from roleplay.models import MatchInterviewRecord, PlayerProfile
from roleplay.partida.carrera import Carrera, Partido
from roleplay.servicios.identificar import identificar_competiciones, identificar_jugadores
from roleplay.servicios import mercado
from roleplay.servicios.prensa import MAXIMO_NOTICIAS_MUNDO, revisar_prensa
from roleplay.servicios.vision import MatchStats

CAMPOS_TOTALES = ("partidos", "goles", "asistencias", "amarillas", "rojas", "figura")
DIAS_SIN_LECTURA_ANTERIOR = 7  # la primera vez, hechos de la ultima semana del juego


def clave_partido(partido: Partido) -> str:
    return f"{partido.fecha.isoformat()}|{partido.competicion}|{partido.local}|{partido.visita}"


def cantidad(numero: int, singular: str, plural: str) -> str:
    return f"{numero} {singular if numero == 1 else plural}"


def fecha_corta(dia: date) -> str:
    return dia.strftime("%d-%m-%Y")


def marcador(carrera: Carrera, partido: Partido) -> str:
    centro = f"{partido.goles_local}-{partido.goles_visita}" if partido.jugado else "vs"
    return f"{carrera.equipo(partido.local)} {centro} {carrera.equipo(partido.visita)}"


# ---- el ultimo partido del usuario ----


def totales_usuario(carrera: Carrera) -> dict[str, dict]:
    """{competicion: totales} del jugador del usuario (sumando equipos, por
    si cambio de club en la temporada). Claves str: va a estado_json."""
    totales: dict[str, dict] = {}
    for estadistica in carrera.estadisticas_de(carrera.usuario_id) if carrera.usuario_id is not None else []:
        fila = totales.setdefault(str(estadistica.competicion), dict.fromkeys(CAMPOS_TOTALES, 0))
        for campo in CAMPOS_TOTALES:
            fila[campo] += getattr(estadistica, campo)
    return totales


@dataclass
class UltimoPartido:
    clave: str
    partido: Partido
    equipo: int
    resumen: str  # "Man Utd 5-3 Sunderland · Premier League · 16-01-2027"
    stats: MatchStats
    exacto: bool  # asistencias/tarjetas/figura salieron de comparar lecturas
    estado: dict = field(default_factory=dict)  # lo que hay que guardar como "lectura anterior"


def ultimo_partido(carrera: Carrera, anterior: Optional[dict] = None) -> Optional[UltimoPartido]:
    """El ultimo partido jugado por el club del usuario. `anterior` es lo
    guardado la vez pasada (database.get_estado_partida)."""
    anterior = anterior or {}
    equipo = carrera.equipo_usuario()
    if equipo is None:
        return None
    partido = carrera.ultimo_partido_de(equipo)
    if partido is None:
        return None

    clave = clave_partido(partido)
    totales = totales_usuario(carrera)
    if anterior.get("ultimo_partido") == clave:
        detalle = anterior.get("detalle", {})  # ya se cargo antes: lo mismo de esa vez
    else:
        ahora = totales.get(str(partido.competicion))
        antes = anterior.get("totales", {}).get(str(partido.competicion))
        exacto = bool(ahora and antes and ahora["partidos"] - antes["partidos"] == 1)
        detalle = {campo: ahora[campo] - antes[campo] for campo in CAMPOS_TOTALES} if exacto else {}
        detalle["exacto"] = exacto

    actuacion = next((a for a in carrera.actuaciones_en(partido) if a.jugador == carrera.usuario_id), None)
    stats = MatchStats(
        goles_equipo=partido.goles_de(equipo),
        goles_rival=partido.goles_contra(equipo),
        equipo_rival=carrera.equipo(partido.rival(equipo)),
        goles_jugador=actuacion.goles if actuacion else 0,
        asistencias_jugador=max(0, detalle.get("asistencias", 0)),
        rating_jugador=min(10.0, actuacion.nota or 0.0) if actuacion else 0.0,
        minutos_jugados=actuacion.minutos if actuacion else 0,
        tarjeta_amarilla=detalle.get("amarillas", 0) > 0,
        tarjeta_roja=detalle.get("rojas", 0) > 0,
        hombre_del_partido=detalle.get("figura", 0) > 0,
    )
    return UltimoPartido(
        clave=clave,
        partido=partido,
        equipo=equipo,
        resumen=f"{marcador(carrera, partido)} · {carrera.competicion(partido.competicion)} · {fecha_corta(partido.fecha)}",
        stats=stats,
        exacto=bool(detalle.get("exacto")),
        estado={"ultimo_partido": clave, "totales": totales, "detalle": detalle, "archivo": carrera.archivo},
    )


def ya_entrevistado(partido: UltimoPartido, historial: list[MatchInterviewRecord]) -> bool:
    return any(
        r.origen == "partida" and r.fecha_juego == partido.partido.fecha.isoformat()
        and r.equipo_rival == partido.stats.equipo_rival
        for r in historial
    )


# ---- nombres (base local + lo ya conocido) ----


def nombres_de_jugadores(carrera: Carrera, ids) -> dict[int, str]:
    """{id: nombre} de los que se conocen: los editados en la partida y la base
    local de nombres (servicios/identificar.py). Los demas se describen, nunca
    se inventan. (La tabla nombre_conocido, de cuando los adivinaba la IA, ya
    no se usa: medido contra la partida, 8 de 20 estaban mal.)"""
    ids = {i for i in ids if i is not None}
    nombres = {i: carrera.nombre_editado(i) for i in ids if carrera.nombre_editado(i)}
    resto = ids - set(nombres)
    if resto:
        locales = identificar_jugadores([carrera.ficha(i) for i in sorted(resto)])
        nombres.update({i: nombre for i, (nombre, _) in locales.items() if nombre})
    return nombres


def nombrar_competiciones(carrera: Carrera, ids) -> None:
    """Pone nombre a las copas que la partida no nombra (en la propia carrera)."""
    sin_nombre = sorted(i for i in ids if i in carrera.competiciones and not carrera.competiciones[i].nombre)
    conocidas = {i: n for i, (n, _) in identificar_competiciones([{"id": i} for i in sin_nombre]).items() if n}
    for i, nombre in conocidas.items():
        carrera.competiciones[i] = replace(carrera.competiciones[i], nombre=nombre)


def competiciones_del_usuario(carrera: Carrera) -> list[int]:
    equipo = carrera.equipo_usuario()
    if equipo is None:
        return []
    return sorted({p.competicion for p in carrera.partidos if p.participa(equipo)})


def describir_jugador(carrera: Carrera, jugador: int, nombres: dict[int, str]) -> str:
    if jugador in nombres:
        return nombres[jugador]
    ficha = carrera.ficha(jugador)
    posicion = ficha.get("posicion", "jugador")
    return f"el {posicion} del {ficha['club']}" if "club" in ficha else f"un {posicion}"


# ---- hechos destacados del mundo ----


@dataclass(frozen=True)
class Hecho:
    clave: str
    puntaje: float
    partido: Partido
    figura: Optional[int] = None  # jugador protagonista (hat-trick)
    goles_figura: int = 0
    nota_figura: Optional[float] = None


def hechos_destacados(carrera: Carrera, desde: Optional[date] = None, cantidad: int = 2) -> list[Hecho]:
    """Partidos de otros equipos que son noticia, de las competiciones que
    juega el usuario y posteriores a `desde`. Los elige el codigo:
    hat-trick > goleada > choque entre los 4 primeros de la liga."""
    equipo = carrera.equipo_usuario()
    hoy = carrera.fecha_actual()
    if equipo is None or hoy is None:
        return []
    desde = desde or hoy - timedelta(days=DIAS_SIN_LECTURA_ANTERIOR)
    competiciones = set(competiciones_del_usuario(carrera))
    punteros = {}
    for c in competiciones:
        if carrera.competiciones[c].es_liga:
            punteros[c] = {f.equipo for f in carrera.tabla(c)[:4]}

    hechos = []
    for p in carrera.partidos:
        if not p.jugado or p.fecha <= desde or p.competicion not in competiciones or p.participa(equipo):
            continue
        actuaciones = carrera.actuaciones_en(p)
        mejor = actuaciones[0] if actuaciones else None
        diferencia = abs(p.goles_local - p.goles_visita)
        if mejor and mejor.goles >= 3:
            hechos.append(Hecho(clave_partido(p), 10 + mejor.goles, p, mejor.jugador, mejor.goles, mejor.nota))
        elif diferencia >= 4:
            hechos.append(Hecho(clave_partido(p), 7 + diferencia, p, mejor.jugador if mejor and mejor.goles >= 2 else None,
                                mejor.goles if mejor else 0, mejor.nota if mejor else None))
        elif p.competicion in punteros and {p.local, p.visita} <= punteros[p.competicion]:
            hechos.append(Hecho(clave_partido(p), 6, p, mejor.jugador if mejor and mejor.goles else None,
                                mejor.goles if mejor else 0, mejor.nota if mejor else None))
    return sorted(hechos, key=lambda h: (-h.puntaje, h.partido.fecha))[:cantidad]


def describir_hecho(carrera: Carrera, hecho: Hecho, nombres: dict[int, str]) -> str:
    p = hecho.partido
    texto = f"{marcador(carrera, p)} ({carrera.competicion(p.competicion)}, {fecha_corta(p.fecha)})."
    if hecho.figura is not None:
        nota = f", nota {hecho.nota_figura:.1f}" if hecho.nota_figura else ""
        equipo = next((a.equipo for a in carrera.actuaciones_en(p) if a.jugador == hecho.figura), p.local)
        quien = describir_jugador(carrera, hecho.figura, nombres)
        if carrera.equipo(equipo) not in quien:  # "el delantero del City" ya dice el club; un nombre no
            quien += f" ({carrera.equipo(equipo)})"
        texto += f" {quien} marco {cantidad(hecho.goles_figura, 'gol', 'goles')}{nota}."
    if carrera.competiciones[p.competicion].es_liga:
        for equipo in (p.local, p.visita):
            posicion = carrera.posicion_en(p.competicion, equipo)
            if posicion and posicion <= 6:
                texto += f" {carrera.equipo(equipo)} queda {posicion}° en la tabla."
    return texto


def hecho_para_prensa(carrera: Carrera, hecho: Hecho, nombres: dict[int, str]) -> dict:
    """El hecho con sus datos sueltos, para que la prensa arme el titular."""
    p = hecho.partido
    if hecho.figura is not None and hecho.goles_figura >= 3:
        tipo = "hat_trick"
    elif abs(p.goles_local - p.goles_visita) >= 4:
        tipo = "goleada"
    else:
        tipo = "choque"
    gana_local = p.goles_local >= p.goles_visita
    equipo_figura = next((a.equipo for a in carrera.actuaciones_en(p) if a.jugador == hecho.figura), None)
    perdedor = p.visita if gana_local else p.local
    if equipo_figura is not None:
        perdedor = p.rival(equipo_figura)
    return {
        "tipo": tipo, "texto": describir_hecho(carrera, hecho, nombres), "marcador": marcador(carrera, p),
        "local": carrera.equipo(p.local), "visita": carrera.equipo(p.visita),
        "ganador": carrera.equipo(p.local if gana_local else p.visita), "perdedor": carrera.equipo(perdedor),
        "competicion": carrera.competicion(p.competicion),
        "figura": nombres.get(hecho.figura, "") if hecho.figura is not None else "",
        "goles_figura": hecho.goles_figura or "", "equipo_figura": carrera.equipo(equipo_figura) if equipo_figura else "",
    }


def premio_para_prensa(carrera: Carrera, premio: "PremioMes", nombres: dict[int, str]) -> dict:
    return {
        "tipo": "premio", "texto": describir_premio(carrera, premio, nombres),
        "jugador": describir_jugador(carrera, premio.jugador, nombres), "equipo": carrera.equipo(premio.equipo),
        "mes": premio.mes.split(" de ")[0], "liga": premio.liga, "goles": cantidad(premio.goles, "gol", "goles"),
    }


def mercado_para_prensa(carrera: Carrera, traspasos: list, nombres: dict[int, str]) -> dict:
    movimientos = [mercado.describir_traspaso(carrera, t, nombres) for t in traspasos]
    return {
        "tipo": "mercado", "primero": movimientos[0],
        "texto": " ".join(f"{m[0].upper()}{m[1:]}." for m in movimientos),
    }


# ---- prensa con la partida ----


def revisar_prensa_con_partida(
    perfil: PlayerProfile,
    historial: list[MatchInterviewRecord],
    estado_prensa: dict,
    carrera: Carrera,
) -> dict:
    """revisar_prensa con datos reales: el contexto de la temporada para la
    noticia sobre el jugador, y una noticia del mundo sobre un hecho real.
    Corre en un hilo (lee la partida y la base)."""
    nombrar_competiciones(carrera, competiciones_del_usuario(carrera))
    desde = estado_prensa.get("partida_hasta")
    publicados = set(estado_prensa.get("hechos_publicados", []))
    hechos = [
        h for h in hechos_destacados(carrera, date.fromisoformat(desde) if desde else None, cantidad=4)
        if h.clave not in publicados
    ][:1]

    from roleplay.servicios import metas as servicio_metas  # (metas importa este modulo)

    premio, estado_mes = premio_del_mes(carrera, estado_prensa.get("mes"))
    terminada, en_curso = archivar_temporada(carrera, estado_prensa.get("temporada_en_curso"))
    metas = database.get_metas(perfil.id) if perfil.id is not None else []
    hitos_metas, cambios_metas = servicio_metas.evaluar_metas(carrera, metas)
    anteriores = database.get_clubes_vistos(carrera.partida)
    traspasos = mercado.detectar_traspasos(carrera, anteriores)[: mercado.TRASPASOS_EN_LA_NOTICIA]
    propio = mercado.traspaso_del_usuario(carrera, anteriores)
    ids = {h.figura for h in hechos} | ({premio.jugador} if premio else set()) | {t.jugador for t in traspasos}
    for c in competiciones_del_usuario(carrera):
        if carrera.competiciones[c].es_liga:
            ids |= {e.jugador for e in carrera.goleadores(c, 3)}
    nombres = nombres_de_jugadores(carrera, ids)
    hitos_reales, estado_reales = detectar_hitos_reales(carrera, estado_prensa.get("reales"))
    hitos_reales += hitos_metas
    if terminada is not None:
        hitos_reales.append({"tipo": "fin_de_temporada", "valor": describir_temporada(terminada)})
    if propio is not None:
        hitos_reales.append({
            "tipo": "nuevo_club", "valor": f"del {carrera.equipo(propio[0])} al {carrera.equipo(propio[1])}",
        })
    # las noticias del mundo, por importancia: el premio que gano otro, el
    # mercado y el partido destacado (solo las primeras salen)
    hechos_mundo = []
    if premio is not None and premio.es_usuario:
        hitos_reales.append({"tipo": "jugador_del_mes", "valor": premio.detalle})
    elif premio is not None:
        hechos_mundo.append(premio_para_prensa(carrera, premio, nombres))
    if traspasos:
        hechos_mundo.append(mercado_para_prensa(carrera, traspasos, nombres))
    usados_partidos = MAXIMO_NOTICIAS_MUNDO - len(hechos_mundo)
    hechos = hechos[: max(usados_partidos, 0)]
    hechos_mundo += [hecho_para_prensa(carrera, h, nombres) for h in hechos]

    resultado = revisar_prensa(
        perfil,
        historial,
        estado_prensa,
        hechos_reales=hechos_mundo,
        hitos_reales=hitos_reales,
        carrera=carrera,
    )
    resultado["estado_prensa"]["reales"] = estado_reales
    resultado["estado_prensa"]["mes"] = estado_mes
    resultado["metas"] = cambios_metas  # la sala las guarda (database.actualizar_metas)
    vitrina = list(estado_prensa.get("vitrina", []))
    for hito in hitos_reales:
        if hito["tipo"] in PREMIOS_DE_VITRINA:
            vitrina.append({"premio": PREMIOS_DE_VITRINA[hito["tipo"]], "detalle": hito["valor"],
                            "temporada": temporada_de(carrera.fecha_actual())})
    resultado["estado_prensa"]["vitrina"] = vitrina
    if en_curso:
        resultado["estado_prensa"]["temporada_en_curso"] = en_curso
    if terminada is not None:
        terminada["titulos"] = [p["premio"] for p in vitrina if p.get("temporada") == terminada["temporada"]]
        resultado["estado_prensa"]["trayectoria"] = list(estado_prensa.get("trayectoria", [])) + [terminada]
    if traspasos:
        hoy = carrera.fecha_actual()
        nuevos = [
            {"fecha": hoy.isoformat() if hoy else "", "texto": mercado.describir_traspaso(carrera, t, nombres),
             "club": t.toca_al_club}
            for t in traspasos
        ]
        resultado["estado_prensa"]["mercado"] = (nuevos + list(estado_prensa.get("mercado", [])))[: mercado.MERCADO_GUARDADO]
    # la foto de los planteles para la proxima vez
    database.guardar_clubes_vistos(carrera.partida, mercado.clubes_de_jugadores(carrera))
    hoy = carrera.fecha_actual()
    if hoy:
        resultado["estado_prensa"]["partida_hasta"] = hoy.isoformat()
    resultado["estado_prensa"]["hechos_publicados"] = (sorted(publicados | {h.clave for h in hechos}))[-50:]
    return resultado


# ---- todo junto, para la sala de prensa (corre en un hilo) ----


@dataclass
class LecturaPartida:
    carrera: Carrera
    ultimo: Optional[UltimoPartido]
    ya_entrevistado: bool
    previa: object = None  # PreviaPartido del proximo partido (servicios/previa.py), si hay


def leer_para_entrevista(player_id: int) -> Optional[LecturaPartida]:
    """La partida mas reciente, el ultimo partido del usuario y la previa
    del proximo. None si no hay partidas de carrera jugador en el PC."""
    from roleplay.partida.lector import carrera_actual

    carrera = carrera_actual()
    if carrera is None:
        return None
    from roleplay.servicios.previa import previa_del_proximo  # (previa importa este modulo)

    estado = database.get_estado_partida(player_id)
    ultimo = ultimo_partido(carrera, estado)
    nombrar_competiciones(carrera, competiciones_del_usuario(carrera))  # una vez; despues, cache
    historial = database.load_match_interviews(player_id)
    return LecturaPartida(
        carrera=carrera,
        ultimo=ultimo,
        ya_entrevistado=bool(ultimo and ya_entrevistado(ultimo, historial)),
        previa=previa_del_proximo(carrera, estado_partida=estado),
    )


# ---- para el Resumen ----


@dataclass
class ResumenTemporada:
    partida: str
    club: str
    fecha: str
    totales: dict  # partidos, goles, asistencias, figura, nota (promedio)
    por_competicion: list  # (nombre, partidos, goles, asistencias, nota)
    posicion: str  # "2° en la Premier League con 55 pts (lider: Manchester City, 56)"
    ultimos: list  # (letra G/E/P, "Man Utd 5-3 Sunderland", competicion), del mas viejo al ultimo
    proximo: str
    temporada: str = ""
    progreso_metas: dict = field(default_factory=dict)  # id de meta -> lo que lleva (o el puesto)


def resumen_temporada(metas: Optional[list] = None) -> Optional[ResumenTemporada]:
    """Lo que el Resumen muestra de la partida (y cuanto llevan `metas`).
    None si no hay partida o no se encuentra al jugador del usuario. Corre
    en un hilo."""
    from roleplay.partida.lector import carrera_actual
    from roleplay.servicios.metas import progreso

    carrera = carrera_actual()
    if carrera is None or carrera.usuario_id is None or carrera.equipo_usuario() is None:
        return None
    nombrar_competiciones(carrera, competiciones_del_usuario(carrera))  # una vez; despues, cache
    equipo = carrera.equipo_usuario()
    estadisticas = carrera.estadisticas_de(carrera.usuario_id)

    por_competicion, suma = [], dict.fromkeys(("partidos", "goles", "asistencias", "figura", "nota_total"), 0)
    for competicion, totales in sorted(totales_usuario(carrera).items(), key=lambda kv: -kv[1]["partidos"]):
        nota_total = sum(e.nota_total for e in estadisticas if str(e.competicion) == competicion)
        por_competicion.append(
            (carrera.competicion(int(competicion)), totales["partidos"], totales["goles"], totales["asistencias"],
             round(nota_total / totales["partidos"] / 10, 1) if totales["partidos"] else None)
        )
        for campo in ("partidos", "goles", "asistencias", "figura"):
            suma[campo] += totales[campo]
        suma["nota_total"] += nota_total

    posicion = ""
    for competicion in competiciones_del_usuario(carrera):
        if carrera.competiciones[competicion].es_liga and (puesto := carrera.posicion_en(competicion, equipo)):
            tabla = carrera.tabla(competicion)
            posicion = f"{puesto}° en la {carrera.competicion(competicion)} con {tabla[puesto - 1].pts} pts"
            if puesto > 1:
                posicion += f" (lider: {carrera.equipo(tabla[0].equipo)}, {tabla[0].pts})"
            break

    letras = {"victoria": "G", "empate": "E", "derrota": "P"}
    ultimos = [
        (letras[p.resultado_para(equipo)], marcador(carrera, p), carrera.competicion(p.competicion))
        for p in carrera.partidos_de(equipo, jugados=True)[-5:]
    ]
    proximo = carrera.proximo_partido_de(equipo)
    hoy = carrera.fecha_actual()
    return ResumenTemporada(
        partida=carrera.partida,
        club=carrera.equipo(equipo),
        fecha=fecha_corta(hoy) if hoy else "",
        totales={
            "partidos": suma["partidos"], "goles": suma["goles"], "asistencias": suma["asistencias"],
            "figura": suma["figura"],
            "nota": round(suma["nota_total"] / suma["partidos"] / 10, 1) if suma["partidos"] else None,
        },
        por_competicion=por_competicion,
        posicion=posicion,
        ultimos=ultimos,
        proximo=(
            f"{carrera.equipo(proximo.rival(equipo))} ({'local' if proximo.local == equipo else 'visita'}) · "
            f"{carrera.competicion(proximo.competicion)} · {fecha_corta(proximo.fecha)}"
            if proximo else ""
        ),
        temporada=temporada_de(hoy) if hoy else "",
        progreso_metas={m["id"]: progreso(carrera, m) for m in (metas or []) if m.get("estado") == "en_curso"},
    )


# ---- hitos reales: lo que la partida dice del jugador ----

CHECKPOINTS_GOLES_TEMPORADA = [5, 10, 25, 50, 75, 100, 150, 200, 300]


def temporada_de(dia: date) -> str:
    """Las temporadas empiezan en julio: 2027-01-16 -> "2026/27"."""
    inicio = dia.year if dia.month >= 7 else dia.year - 1
    return f"{inicio}/{str(inicio + 1)[-2:]}"


def liga_terminada(carrera: Carrera, liga: int) -> bool:
    """Sin partidos pendientes y con al menos una rueda completa jugada por
    todos (si la partida trajera un fixture a medias, no se da por cerrada)."""
    if any(p.competicion == liga and not p.jugado for p in carrera.partidos):
        return False
    tabla = carrera.tabla(liga)
    return bool(tabla) and min(f.pj for f in tabla) >= len(tabla) - 1


def detectar_hitos_reales(carrera: Carrera, estado: Optional[dict] = None) -> tuple[list[dict], dict]:
    """Hitos del jugador que salen de la partida (no de las entrevistas):
    goles de la temporada, maximo goleador de la liga, partidazo (3+ goles),
    su club pasa a liderar o pierde el liderato, campeon. `estado` es lo ya
    reportado (estado_prensa["reales"]): cada hito sale una vez, y los de
    goles se reinician al empezar otra temporada."""
    estado = dict(estado or {})
    hoy = carrera.fecha_actual()
    equipo = carrera.equipo_usuario()
    if hoy is None or equipo is None or carrera.usuario_id is None:
        return [], estado
    temporada = temporada_de(hoy)
    if estado.get("temporada") != temporada:
        estado = {"temporada": temporada}
    hitos = []

    goles = sum(t["goles"] for t in totales_usuario(carrera).values())
    alcanzados = [c for c in CHECKPOINTS_GOLES_TEMPORADA if goles >= c and c > estado.get("goles", 0)]
    if alcanzados:
        hitos.append({"tipo": "goles_temporada", "valor": max(alcanzados)})
        estado["goles"] = max(alcanzados)

    ligas = [c for c in competiciones_del_usuario(carrera) if carrera.competiciones[c].es_liga]
    for liga in ligas[:1]:
        nombre = carrera.competicion(liga)
        goleadores = carrera.goleadores(liga, 1)
        es_lider = bool(goleadores) and goleadores[0].jugador == carrera.usuario_id
        if es_lider and not estado.get("lider_goleadores"):
            hitos.append({"tipo": "lider_goleadores", "valor": nombre})
        estado["lider_goleadores"] = es_lider

        posicion = carrera.posicion_en(liga, equipo)
        era_lider = estado.get("club_lider")
        if posicion == 1 and era_lider is False:
            hitos.append({"tipo": "lider_liga", "valor": nombre})
        elif posicion and posicion > 1 and era_lider:
            hitos.append({"tipo": "perdio_liderato", "valor": nombre})
        estado["club_lider"] = posicion == 1

        terminada = liga_terminada(carrera, liga)
        if posicion == 1 and terminada and not estado.get("campeon"):
            hitos.append({"tipo": "campeon", "valor": nombre})
            estado["campeon"] = True
        if es_lider and terminada and not estado.get("maximo_goleador"):
            hitos.append({"tipo": "maximo_goleador", "valor": nombre})
            estado["maximo_goleador"] = True

    partido = carrera.ultimo_partido_de(equipo)
    if partido is not None:
        clave = clave_partido(partido)
        suya = next((a for a in carrera.actuaciones_en(partido) if a.jugador == carrera.usuario_id), None)
        if suya and suya.goles >= 3 and estado.get("partidazo") != clave:
            hitos.append({
                "tipo": "partidazo",
                "valor": f"{cantidad(suya.goles, 'gol', 'goles')} en el {marcador(carrera, partido)}",
            })
            estado["partidazo"] = clave
    return hitos, estado


# ---- premios: jugador del mes y la vitrina ----

MESES = ("enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto",
         "septiembre", "octubre", "noviembre", "diciembre")
MINIMO_PARTIDOS_MES = 2  # partidos de liga del club en el mes para que haya premio
PREMIOS_DE_VITRINA = {
    "jugador_del_mes": "Jugador del mes",
    "campeon": "Campeon",
    "maximo_goleador": "Maximo goleador",
}


@dataclass
class PremioMes:
    mes: str  # "enero de 2027"
    liga: str
    jugador: int
    equipo: int
    goles: int
    es_usuario: bool

    @property
    def detalle(self) -> str:
        return f"{self.mes} en la {self.liga}, con {cantidad(self.goles, 'gol', 'goles')}"


def _goles_en_liga(carrera: Carrera, liga: int) -> dict[int, int]:
    goles: dict[int, int] = defaultdict(int)
    for e in carrera.estadisticas:
        if e.competicion == liga and e.goles:
            goles[e.jugador] += e.goles
    return goles


def _goles_desde(carrera: Carrera, liga: int, desde: date) -> dict[int, int]:
    """Goles de liga en los partidos desde `desde`, segun los ultimos
    partidos guardados de cada jugador (alcanza para unas pocas fechas)."""
    goles: dict[int, int] = defaultdict(int)
    for a in carrera.actuaciones:
        if a.competicion == liga and a.fecha >= desde and a.goles:
            goles[a.jugador] += a.goles
    return goles


def _restar(a: dict, b: dict) -> dict[int, int]:
    return {j: a.get(j, 0) - b.get(j, 0) for j in set(a) | set(b) if a.get(j, 0) - b.get(j, 0)}


def _mes_siguiente(mes: str) -> str:
    anio, numero = (int(x) for x in mes.split("-"))
    return f"{anio + numero // 12}-{numero % 12 + 1:02d}"


def premio_del_mes(carrera: Carrera, estado: Optional[dict] = None) -> tuple[Optional["PremioMes"], dict]:
    """El jugador del mes de la liga del usuario (el que mas goles hizo),
    cuando el juego pasa al mes siguiente. `estado` (estado_prensa["mes"])
    guarda los goles de cada uno al empezar el mes en curso: el premio es
    la diferencia al cerrarlo. Si la app no vio el mes entero (se salteo
    un mes, cambio la temporada o la liga) no se inventa: se vuelve a
    empezar a contar."""
    estado = dict(estado or {})
    hoy = carrera.fecha_actual()
    equipo = carrera.equipo_usuario()
    ligas = [c for c in competiciones_del_usuario(carrera) if carrera.competiciones[c].es_liga]
    if hoy is None or equipo is None or not ligas:
        return None, estado
    liga = ligas[0]
    mes, inicio_mes = hoy.strftime("%Y-%m"), hoy.replace(day=1)
    if estado.get("mes") == mes and estado.get("liga") == liga:
        return None, estado
    # los goles de cada uno al terminar el mes anterior (= al empezar este)
    al_empezar = {j: g for j, g in _restar(_goles_en_liga(carrera, liga), _goles_desde(carrera, liga, inicio_mes)).items() if g > 0}
    nuevo = {"mes": mes, "liga": liga, "base": {str(j): g for j, g in al_empezar.items()}}

    anterior = estado.get("mes")
    if (
        anterior is None or estado.get("liga") != liga or _mes_siguiente(anterior) != mes
        or temporada_de(date.fromisoformat(f"{anterior}-01")) != temporada_de(inicio_mes)
    ):
        return None, nuevo
    base = {int(j): g for j, g in estado.get("base", {}).items()}
    del_mes = {j: g for j, g in _restar(al_empezar, base).items() if g > 0}
    jugados = [
        p for p in carrera.partidos_de(equipo, jugados=True)
        if p.competicion == liga and p.fecha.strftime("%Y-%m") == anterior
    ]
    if len(jugados) < MINIMO_PARTIDOS_MES or not del_mes:
        return None, nuevo
    # en empate, el que lleva mas goles en la liga; despues, el de id menor (estable)
    ganador = max(del_mes, key=lambda j: (del_mes[j], al_empezar.get(j, 0), -j))
    filas = [e for e in carrera.estadisticas if e.jugador == ganador and e.competicion == liga]
    anio, numero = (int(x) for x in anterior.split("-"))
    return PremioMes(
        mes=f"{MESES[numero - 1]} de {anio}",
        liga=carrera.competicion(liga),
        jugador=ganador,
        equipo=max(filas, key=lambda e: e.partidos).equipo if filas else equipo,
        goles=del_mes[ganador],
        es_usuario=ganador == carrera.usuario_id,
    ), nuevo


def describir_premio(carrera: Carrera, premio: PremioMes, nombres: dict[int, str]) -> str:
    return (
        f"{describir_jugador(carrera, premio.jugador, nombres)} ({carrera.equipo(premio.equipo)}) fue elegido "
        f"jugador del mes de {premio.mes.split(' de ')[0]} en la {premio.liga}: marco "
        f"{cantidad(premio.goles, 'gol', 'goles')} en el mes."
    )


# ---- la trayectoria: cada temporada, al terminar ----


def resumen_de_la_temporada(carrera: Carrera) -> Optional[dict]:
    """Lo que se archiva de la temporada en curso del usuario (club, sus
    numeros y como va su club en la liga). None sin club o sin partidos."""
    hoy, equipo = carrera.fecha_actual(), carrera.equipo_usuario()
    if hoy is None or equipo is None or carrera.usuario_id is None:
        return None
    totales = totales_usuario(carrera)
    partidos = sum(t["partidos"] for t in totales.values())
    nota_total = sum(e.nota_total for e in carrera.estadisticas_de(carrera.usuario_id))
    resumen = {
        "temporada": temporada_de(hoy),
        "club": carrera.equipo(equipo),
        "partidos": partidos,
        "goles": sum(t["goles"] for t in totales.values()),
        "asistencias": sum(t["asistencias"] for t in totales.values()),
        "figura": sum(t["figura"] for t in totales.values()),
        "nota": round(nota_total / partidos / 10, 1) if partidos else None,
        "liga": "",
        "posicion": None,
        "hasta": hoy.isoformat(),
    }
    ligas = [c for c in competiciones_del_usuario(carrera) if carrera.competiciones[c].es_liga]
    if ligas:
        resumen["liga"] = carrera.competicion(ligas[0])
        resumen["posicion"] = carrera.posicion_en(ligas[0], equipo)
    return resumen


def archivar_temporada(carrera: Carrera, en_curso: Optional[dict]) -> tuple[Optional[dict], Optional[dict]]:
    """(temporada que termino, resumen de la que esta en curso). `en_curso`
    es el resumen guardado la vez anterior (estado_prensa): si el juego ya
    paso a otra temporada, ese es el balance de la que termino (hasta lo
    ultimo que la app alcanzo a ver)."""
    actual = resumen_de_la_temporada(carrera)
    if actual is None:
        return None, en_curso
    if en_curso and en_curso.get("temporada") != actual["temporada"]:
        return dict(en_curso), actual
    return None, actual


def describir_temporada(t: dict) -> str:
    texto = (
        f"temporada {t['temporada']} con {t['club']}: {cantidad(t['partidos'], 'partido', 'partidos')}, "
        f"{cantidad(t['goles'], 'gol', 'goles')}, {cantidad(t['asistencias'], 'asistencia', 'asistencias')}"
    )
    if t.get("nota") is not None:
        texto += f", nota media {t['nota']}"
    if t.get("posicion"):
        texto += f"; su club termino {t['posicion']}° en la {t['liga']}"
    return texto
