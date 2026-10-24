"""
El Instagram que se mueve solo: cuando el juego avanza (cada autoguardado
que lee el modo en vivo), los hinchas reaccionan a los partidos nuevos del
jugador y a las noticias sobre el, sin que publique nada.

Cuantos seguidores gana o pierde lo decide el codigo (resultado, sus goles,
su nota, el tono de la noticia, escalado por sus seguidores y reputacion), y
los comentarios tambien: servicios/narrador.py con roleplay/datos/corpus_redes.json
(autores inventados, el tono sigue lo que paso), o la IA hibrida si esta
(servicios/ia.py: una sola llamada para todos los eventos, hablando del
marcador y del titular exactos).
"""

import re
from dataclasses import dataclass
from typing import Optional

from roleplay.models import ActividadInstagram, NoticiaPrensa, PlayerProfile
from roleplay.partida.carrera import Carrera
from roleplay.servicios.narrador import narrador
from roleplay.servicios.partida_real import cantidad, clave_partido, fecha_corta, marcador

# la base de seguidores segun el club (servicios/ecosistema.tier_club): en un gigante se
# arranca con cientos de miles; en un club chico, crecer depende de los goles y los titulos
SEGUIDORES_BASE = {1: 400_000, 2: 25_000, 3: 2_000}
# cuanto multiplica la exposicion: el tier del club y un promedio de gol absurdo
MULTIPLICADOR_TIER = {1: 2.5, 2: 1.0, 3: 0.5}
PROMEDIO_NORMAL = 0.4  # goles por partido desde los que el ruido crece
# (era 40: con 5 goles por partido en un gigante cada evento sumaba varias veces la cuenta
# entera y Simon paso de 600.000 a 52 millones en un mes del juego, 2026-10-21)
TOPE_EXPOSICION = 2.5
MAXIMO_EVENTOS = 5  # por revision: si la app estuvo cerrada mucho tiempo, solo lo ultimo
ESCALA = 0.004  # un partido "normal" mueve ~0,4% de los seguidores...
# ...y cuanto mas cerca del techo de su reputacion, menos (una curva en S, no una bola de nieve).
# Techo con reputacion 100: 40 millones, lo de Haaland o Bellingham; con 80, ~20 M; con 60, ~9 M.
TECHO_MAXIMO = 40_000_000
FRENO_MINIMO = 0.05  # en el techo todavia se mueve un poquito
MINIMO_ESCALA = 40  # ...y con pocos seguidores, al menos esto
FACTOR_RESULTADO = {"victoria": 1.0, "empate": 0.3, "derrota": -0.6}
FACTOR_TONO = {"positiva": 1.5, "mixta": 0.3, "neutral": 0.2, "negativa": -1.2}


@dataclass
class EventoHinchada:
    tipo: str  # "partido" | "noticia"
    fecha_juego: str  # iso
    titulo: str  # lo que se muestra
    detalle: str  # lo que paso, en una oracion
    crecimiento: int
    # como lo cuenta una pagina de afuera (el feed global): en tercera persona. El `titulo`
    # es para el jugador ("3 goles tuyos"); una pagina no le habla a el (Simon, 2026-10-21)
    titular: str = ""


def techo_de_seguidores(reputacion: int) -> int:
    """Hasta donde llega la cuenta con esa reputacion (ahi se frena)."""
    return round(TECHO_MAXIMO * (max(0, min(100, reputacion)) / 100) ** 3 + 20_000)


def _escala(seguidores: int, reputacion: int) -> float:
    """Cuanto mueve un evento: mas seguidores y mas reputacion, mas gente
    mirando (y mas gente que se va si las cosas salen mal), frenado cerca del
    techo de su reputacion: crecer de 30 a 40 millones cuesta mucho mas que de
    300.000 a 400.000."""
    freno = max(FRENO_MINIMO, 1 - seguidores / techo_de_seguidores(reputacion))
    return max(MINIMO_ESCALA, seguidores * ESCALA) * (0.5 + reputacion / 100) * freno


def base_de_seguidores(tier: int, reputacion: int) -> int:
    return round(SEGUIDORES_BASE.get(tier, SEGUIDORES_BASE[2]) * (0.5 + reputacion / 100))


def exposicion(tier: int, goles: int, partidos: int, premios: int = 0) -> float:
    """Cuanto multiplica todo lo que mueve seguidores. 80 goles en 40 partidos
    en un gigante, con premios: una estrella mundial."""
    promedio = goles / max(partidos, 1)
    rendimiento = 1 + max(0.0, promedio - PROMEDIO_NORMAL) * 3
    valor = MULTIPLICADOR_TIER.get(tier, 1.0) * rendimiento * (1 + 0.25 * min(premios, 8))
    return min(TOPE_EXPOSICION, valor)


def exposicion_en(carrera: Carrera, premios: int = 0) -> tuple[int, float]:
    """(tier del club del usuario, multiplicador de exposicion) con la partida."""
    from roleplay.servicios import ecosistema

    tier = ecosistema.tier_club(carrera, ecosistema.club_del_usuario(carrera))
    estadisticas = carrera.estadisticas_de(carrera.usuario_id) if carrera.usuario_id is not None else []
    goles = sum(e.goles for e in estadisticas)
    partidos = sum(e.partidos for e in estadisticas)
    return tier, exposicion(tier, goles, partidos, premios)


def crecimiento_por_partido(
    seguidores: int, reputacion: int, resultado: str, jugo: bool, goles: int = 0, nota: Optional[float] = None
) -> int:
    factor = FACTOR_RESULTADO[resultado]
    if not jugo:
        factor *= 0.3  # sin jugar, el resultado del club pesa poco en SU cuenta
    else:
        factor += 0.6 * goles
        if goles >= 3:
            factor += 2.0  # un hat-trick se comparte
        if nota is not None and nota >= 8.5:
            factor += 0.8
        elif nota is not None and nota < 6.0:
            factor -= 0.8
    return round(_escala(seguidores, reputacion) * factor)


def crecimiento_por_noticia(seguidores: int, reputacion: int, tono: str) -> int:
    return round(_escala(seguidores, reputacion) * FACTOR_TONO.get(tono, 0.2))


def eventos_nuevos(
    carrera: Carrera,
    noticias: list[NoticiaPrensa],
    estado: Optional[dict],
    seguidores: int,
    reputacion: int,
    multiplicador: float = 1.0,
) -> tuple[list[EventoHinchada], dict]:
    """Los partidos del jugador y las noticias sobre el que todavia no
    tuvieron reaccion (los seguidores, por `multiplicador`: la exposicion). `estado` (estado_json.hinchada) dice hasta donde se
    llego: la primera vez solo se reacciona al ultimo partido y las
    noticias viejas quedan como estan. `noticias`: del mas nuevo al mas
    viejo, como las devuelve la base."""
    estado = dict(estado or {})
    eventos: list[EventoHinchada] = []
    equipo, usuario = carrera.equipo_usuario(), carrera.usuario_id
    nombre = carrera.nombre_editado(usuario) or "el jugador"

    if equipo is not None:
        # su club y, si juega con ella, su seleccion (sus partidos tambien mueven el Instagram)
        seleccion = carrera.seleccion_del_usuario()
        de_la_seleccion = [p for p in (carrera.partidos_de(seleccion, jugados=True) if seleccion is not None else [])
                           if any(a.jugador == usuario for a in carrera.actuaciones_en(p))]
        jugados = sorted(carrera.partidos_de(equipo, jugados=True) + de_la_seleccion, key=lambda p: p.fecha)
        hasta = estado.get("hasta")
        nuevos = [p for p in jugados if p.fecha.isoformat() > hasta] if hasta else jugados[-1:]
        for p in nuevos[-MAXIMO_EVENTOS:]:
            suyo = seleccion if p in de_la_seleccion else equipo
            suya = next((a for a in carrera.actuaciones_en(p) if a.jugador == usuario), None)
            goles = suya.goles if suya else 0
            nota = suya.nota if suya else None
            if suya is None:
                rendimiento = f"{nombre} no jugo"
            else:
                rendimiento = f"{nombre} jugo {suya.minutos} minutos, marco {cantidad(goles, 'gol', 'goles')}"
                rendimiento += f", nota {nota:.1f}" if nota is not None else ""
            apellido = nombre.split()[-1] if nombre.split() else nombre
            # en tercera persona: lo ve el jugador, pero tambien es lo que leen los hinchas y la IA
            # ("5 goles tuyos" se colaba en los comentarios y en el feed; Simon, 2026-10-23)
            titulo = marcador(carrera, p) + (f" · {cantidad(goles, 'gol', 'goles')} de {apellido}" if goles else "")
            de_local = p.local == suyo
            eventos.append(EventoHinchada(
                "partido", p.fecha.isoformat(), titulo,
                f"Partido: {marcador(carrera, p)} ({carrera.competicion(p.competicion)}, {fecha_corta(p.fecha)}). "
                f"{carrera.equipo(suyo)} ({'su seleccion' if suyo == seleccion else 'su club'}) jugo de "
                f"{'local' if de_local else 'visitante'} y {p.resultado_para(suyo).replace('victoria', 'gano').replace('derrota', 'perdio').replace('empate', 'empato')}. "
                f"{rendimiento}. No se sabe el estadio ni como fueron los goles.",
                round(crecimiento_por_partido(seguidores, reputacion, p.resultado_para(suyo), suya is not None, goles,
                                              nota) * multiplicador),
                titulo,
            ))
        if jugados:
            estado["hasta"] = max(estado.get("hasta") or "", jugados[-1].fecha.isoformat())
            estado["ultimo"] = clave_partido(jugados[-1])

    from roleplay.servicios.eventos import tiene_reaccion_propia

    sobre_el = [n for n in noticias if n.categoria == "jugador" and n.id is not None]
    ultima = estado.get("noticia")
    if ultima is not None:
        hoy = carrera.fecha_actual()
        nuevas = [n for n in sobre_el if n.id > ultima and not tiene_reaccion_propia(n)]  # (esas ya tienen la suya)
        for n in reversed(nuevas[:MAXIMO_EVENTOS]):  # del mas viejo al mas nuevo
            eventos.append(EventoHinchada(
                "noticia", hoy.isoformat() if hoy else "", n.titular,
                f"Noticia sobre el ({n.tono}): {n.titular}. {n.cuerpo}",
                round(crecimiento_por_noticia(seguidores, reputacion, n.tono) * multiplicador),
            ))
    if sobre_el:
        estado["noticia"] = max([n.id for n in sobre_el] + ([ultima] if ultima is not None else []))
    elif ultima is None:
        estado["noticia"] = 0
    return eventos, estado


# ---- los comentarios (motor narrativo) ----


def datos_de_redes(perfil: PlayerProfile, titulo: str = "") -> dict:
    """Lo que necesitan los comentarios: el apellido, el club y su "tag"."""
    club = perfil.club_actual or "futbol"
    etiqueta = re.sub(r"[^a-z0-9]", "", club.lower()) or "futbol"
    partes = perfil.nombre_jugador.split()
    return {"apellido": partes[-1] if partes else "crack", "club": club, "club_tag": etiqueta,
            "club_tag_mayus": "".join(p.capitalize() for p in re.findall(r"[a-z0-9]+", club.lower())) or "Futbol",
            "titulo": titulo}


def comentarios(escritor, tipo: str, crecimiento: int, datos: dict) -> list[dict]:
    """Dos o tres comentarios: el tono sigue lo que paso (si gano seguidores,
    mas hinchas contentos; si perdio, mas criticas), con algun gracioso."""
    dado = escritor.dado
    lado = "pos" if crecimiento >= 0 else "neg"
    propio = f"com_{tipo}_{lado}" if escritor.puede(f"com_{tipo}_{lado}", **datos) else f"com_{lado}"
    if lado == "pos":
        plan = [("hincha", propio, "positivo"), ("gracioso", "com_grac", "gracioso"),
                dado.choice([("rival", "com_neg", "negativo"), ("neutro", "com_neutro", "neutral")])]
    else:
        plan = [("hincha", propio, "negativo"), ("rival", "com_neg", "negativo"),
                dado.choice([("gracioso", "com_grac", "gracioso"), ("hincha", "com_pos", "positivo")])]
    if dado.random() < 0.3:
        plan = plan[:2]
    resultado = []
    for clase, simbolo, tono in plan:
        con_numero = {**datos, "n": dado.randint(7, 99)}
        resultado.append({"autor": escritor.elegir(f"autor_{clase}", **con_numero),
                          "texto": escritor.decir(simbolo, **con_numero), "tono": tono})
    return resultado


SISTEMA_HINCHAS = (
    "TAREA: sos la seccion de comentarios del Instagram de un futbolista, en un juego de roleplay. Para cada "
    "evento, 2 o 3 comentarios.\n"
    "QUIEN COMENTA: cuentas inventadas (@usuario): hinchas de su equipo, algun rival que chicanea, una cuenta de "
    "memes. Nunca personas reales.\n"
    "DE QUE HABLAN: SOLO del evento: el marcador exacto, sus goles si los hizo, el titular tal cual. Le pueden "
    "hablar a el (\"¡Que partido, Simon!\") o hablar de el (\"Canales esta on fire\").\n"
    "TONO: si gano seguidores, mas contentos; si perdio, mas criticas. `tono`: positivo, negativo, neutral o "
    "gracioso. Pueden llevar emojis y jerga de redes.\n"
    "NO: seguidores ni numeros de la app; estadios, entrenamientos, lesiones o jugadas que no esten en el evento; "
    "exagerar el titular (escuchar una oferta no es irse, firmar con una marca no es cambiar de club); si jugo "
    "con su seleccion, el comentario es de la seleccion, no de su club.\n"
    "EJEMPLO. Evento: \"Manchester City 1-3 Man Utd · 3 goles de Canales\" (Man Utd de visitante).\n"
    "  BIEN: {\"autor\": \"@red_hasta_morir\", \"texto\": \"Tres goles en cancha del City 🔥 no es de este planeta\", "
    "\"tono\": \"positivo\"}\n"
    "  MAL: \"Old Trafford exploto con su hat-trick\" (jugo de visitante y el estadio no esta en el evento)."
)


def _comentarios_con_ia(perfil: PlayerProfile, eventos: list[EventoHinchada]) -> dict[int, list[dict]]:
    from roleplay.servicios import ia

    lista = "\n".join(f"{i}. [{e.tipo}] {e.titulo}. {e.detalle[:400]} (seguidores: {e.crecimiento:+d})"
                      for i, e in enumerate(eventos))
    datos = ia.pedir_json(
        SISTEMA_HINCHAS, f"{ia.ficha(perfil)}\n\nLos eventos:\n{lista}",
        {"eventos": [{"indice": 0, "comentarios": [{"autor": "@usuario", "texto": "...", "tono": "positivo"}]}]},
        jugador=perfil.id,
    )
    resultado = {}
    for item in (datos or {}).get("eventos") or []:
        if isinstance(item, dict) and isinstance(item.get("indice"), int) and 0 <= item["indice"] < len(eventos):
            validos = ia.comentarios_validos(item.get("comentarios"), maximo=3)
            if validos:
                resultado[item["indice"]] = validos
    return resultado


def comentar_eventos(perfil: PlayerProfile, eventos: list[EventoHinchada]) -> dict[int, list[dict]]:
    """{indice del evento: [comentarios]}: los de la IA si esta y, los que
    falten, del motor local (al instante)."""
    with narrador(perfil.id, "redes") as escritor:
        locales = {i: comentarios(escritor, e.tipo, e.crecimiento, datos_de_redes(perfil, e.titulo))
                   for i, e in enumerate(eventos)}
    return {**locales, **(_comentarios_con_ia(perfil, eventos) if eventos else {})}


def procesar(
    perfil: PlayerProfile,
    carrera: Carrera,
    noticias: list[NoticiaPrensa],
    estado: Optional[dict],
    seguidores: int,
    reputacion: int,
    premios: int = 0,
) -> tuple[list[ActividadInstagram], dict]:
    """La actividad nueva (sin guardar) y el estado nuevo. Si el club del
    usuario es de un tier mejor que el ultimo visto (o es la primera vez), los
    seguidores suben a la base de ese club (una actividad "hinchada")."""
    tier, multiplicador = exposicion_en(carrera, premios)
    eventos, nuevo_estado = eventos_nuevos(carrera, noticias, estado, seguidores, reputacion, multiplicador)
    dichos = comentar_eventos(perfil, eventos) if eventos else {}
    actividad = [
        ActividadInstagram(
            player_id=perfil.id, fecha_juego=e.fecha_juego, tipo=e.tipo, titulo=e.titulo,
            crecimiento_seguidores=e.crecimiento, comentarios=dichos.get(i, []),
        )
        for i, e in enumerate(eventos)
    ]
    visto = (estado or {}).get("base_tier")
    if visto is None or tier < visto:
        nuevo_estado["base_tier"] = tier
        base = base_de_seguidores(tier, reputacion)
        if seguidores < base:
            from roleplay.servicios import ecosistema

            club = carrera.equipo(ecosistema.club_del_usuario(carrera)) if ecosistema.club_del_usuario(carrera) else ""
            hoy = carrera.fecha_actual()
            actividad.append(ActividadInstagram(
                player_id=perfil.id, fecha_juego=hoy.isoformat() if hoy else "", tipo="hinchada",
                titulo=f"Jugar en {club or 'tu club'} te pone en la vidriera", crecimiento_seguidores=base - seguidores,
                comentarios=[],
            ))
    from roleplay.servicios import feed

    nuevo_estado["feed"] = feed.actualizar(perfil, eventos, (estado or {}).get("feed", []), seguidores, reputacion,
                                           carrera)
    return actividad, nuevo_estado


def revisar_hinchada(player_id: int) -> Optional[tuple[list[ActividadInstagram], dict]]:
    """Para la pagina de Instagram (corre en un hilo): la partida elegida y
    lo que los hinchas tienen para decir. None sin partida o sin perfil."""
    from roleplay import database
    from roleplay.partida.lector import carrera_actual

    perfil = database.load_profile(player_id)
    carrera = carrera_actual()
    if perfil is None or carrera is None or carrera.equipo_usuario() is None:
        return None
    return procesar(
        perfil,
        carrera,
        database.load_noticias_prensa(player_id, limite=20),
        database.get_estado_hinchada(player_id),
        database.get_seguidores(player_id),
        database.get_reputacion_actual(player_id),
        len(database.get_estado_prensa(player_id).get("vitrina", [])),
    )
