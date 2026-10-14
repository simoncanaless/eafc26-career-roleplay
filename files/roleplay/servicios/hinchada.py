"""
El Instagram que se mueve solo: cuando el juego avanza (cada autoguardado
que lee el modo en vivo), los hinchas reaccionan a los partidos nuevos del
jugador y a las noticias sobre el, sin que publique nada.

Cuantos seguidores gana o pierde lo decide el codigo (resultado, sus goles,
su nota, el tono de la noticia, escalado por sus seguidores y reputacion);
la IA solo escribe los comentarios. Sin IA, los seguidores se mueven igual
y la actividad sale sin comentarios.
"""

from dataclasses import dataclass
from typing import Optional

from pydantic import BaseModel

from roleplay.gemini import generar_json
from roleplay.models import ActividadInstagram, NoticiaPrensa, PlayerProfile
from roleplay.partida.carrera import Carrera
from roleplay.servicios.contexto import ficha_jugador
from roleplay.servicios.instagram import ComentarioIA
from roleplay.servicios.partida_real import cantidad, clave_partido, fecha_corta, marcador

MAXIMO_EVENTOS = 5  # por revision: si la app estuvo cerrada mucho tiempo, solo lo ultimo
ESCALA = 0.01  # un partido "normal" mueve ~1% de los seguidores
MINIMO_ESCALA = 40  # ...y con pocos seguidores, al menos esto
FACTOR_RESULTADO = {"victoria": 1.0, "empate": 0.3, "derrota": -0.6}
FACTOR_TONO = {"positiva": 1.5, "mixta": 0.3, "neutral": 0.2, "negativa": -1.2}


@dataclass
class EventoHinchada:
    tipo: str  # "partido" | "noticia"
    fecha_juego: str  # iso
    titulo: str  # lo que se muestra
    detalle: str  # lo que lee la IA
    crecimiento: int


def _escala(seguidores: int, reputacion: int) -> float:
    """Cuanto mueve un evento: mas seguidores y mas reputacion, mas gente
    mirando (y mas gente que se va si las cosas salen mal)."""
    return max(MINIMO_ESCALA, seguidores * ESCALA) * (0.5 + reputacion / 100)


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
) -> tuple[list[EventoHinchada], dict]:
    """Los partidos del jugador y las noticias sobre el que todavia no
    tuvieron reaccion. `estado` (estado_json.hinchada) dice hasta donde se
    llego: la primera vez solo se reacciona al ultimo partido y las
    noticias viejas quedan como estan. `noticias`: del mas nuevo al mas
    viejo, como las devuelve la base."""
    estado = dict(estado or {})
    eventos: list[EventoHinchada] = []
    equipo, usuario = carrera.equipo_usuario(), carrera.usuario_id
    nombre = carrera.nombre_editado(usuario) or "el jugador"

    if equipo is not None:
        jugados = carrera.partidos_de(equipo, jugados=True)
        hasta = estado.get("hasta")
        nuevos = [p for p in jugados if p.fecha.isoformat() > hasta] if hasta else jugados[-1:]
        for p in nuevos[-MAXIMO_EVENTOS:]:
            suya = next((a for a in carrera.actuaciones_en(p) if a.jugador == usuario), None)
            goles = suya.goles if suya else 0
            nota = suya.nota if suya else None
            titulo = marcador(carrera, p) + (f" · {cantidad(goles, 'gol tuyo', 'goles tuyos')}" if goles else "")
            if suya is None:
                rendimiento = f"{nombre} no jugo"
            else:
                rendimiento = f"{nombre} jugo {suya.minutos} minutos, marco {cantidad(goles, 'gol', 'goles')}"
                rendimiento += f", nota {nota:.1f}" if nota is not None else ""
            eventos.append(EventoHinchada(
                "partido", p.fecha.isoformat(), titulo,
                f"Partido: {marcador(carrera, p)} ({carrera.competicion(p.competicion)}, {fecha_corta(p.fecha)}). "
                f"Resultado para su club: {p.resultado_para(equipo)}. {rendimiento}.",
                crecimiento_por_partido(seguidores, reputacion, p.resultado_para(equipo), suya is not None, goles, nota),
            ))
        if jugados:
            estado["hasta"] = max(estado.get("hasta") or "", jugados[-1].fecha.isoformat())
            estado["ultimo"] = clave_partido(jugados[-1])

    sobre_el = [n for n in noticias if n.categoria == "jugador" and n.id is not None]
    ultima = estado.get("noticia")
    if ultima is not None:
        hoy = carrera.fecha_actual()
        for n in reversed([n for n in sobre_el if n.id > ultima][:MAXIMO_EVENTOS]):  # del mas viejo al mas nuevo
            eventos.append(EventoHinchada(
                "noticia", hoy.isoformat() if hoy else "", n.titular,
                f"Noticia sobre el ({n.tono}): {n.titular}. {n.cuerpo}",
                crecimiento_por_noticia(seguidores, reputacion, n.tono),
            ))
    if sobre_el:
        estado["noticia"] = max([n.id for n in sobre_el] + ([ultima] if ultima is not None else []))
    elif ultima is None:
        estado["noticia"] = 0
    return eventos, estado


# ---- la IA: los comentarios ----


class ComentariosDeEvento(BaseModel):
    indice: int
    comentarios: list[ComentarioIA]


class ReaccionesDeHinchas(BaseModel):
    eventos: list[ComentariosDeEvento]


def comentar_eventos(
    perfil: PlayerProfile, eventos: list[EventoHinchada], contexto_real: str = "", api_key: Optional[str] = None
) -> dict[int, list[dict]]:
    """{indice del evento: [comentarios]} (una sola consulta para todos)."""
    lista = "\n".join(
        f"{i}. {e.detalle} (seguidores: {'+' if e.crecimiento >= 0 else ''}{e.crecimiento})"
        for i, e in enumerate(eventos)
    )
    contexto = f"\n{contexto_real}\n(Datos reales de su partida: los hinchas los conocen.)\n" if contexto_real else ""
    respuesta = generar_json(
        f"""
Simulas los comentarios que dejan los hinchas en el Instagram de
{perfil.nombre_jugador}, futbolista de un modo carrera roleplay de EAFC 26,
cuando pasan cosas en su temporada (el no publico nada: comentan en su
ultimo post).

{ficha_jugador(perfil)}{contexto}
Lo que paso (con cuantos seguidores gano o perdio por eso):
{lista}

Para cada uno, 2 o 3 comentarios cortos estilo Instagram (en espanol, se
puede mezclar algo de ingles si el club es ingles, con emojis): hinchas de
su club, algun hater o hincha rival, algun comentario gracioso. Que el tono
siga lo que paso (si perdio o una noticia negativa, criticas; si la rompio,
euforia). Autores inventados tipo @usuario, nunca nombres de personas
reales. No inventes datos que no esten arriba.
Devolve "indice" igual al numero de cada uno.
""".strip(),
        ReaccionesDeHinchas,
        "No se pudieron escribir los comentarios esta vez.",
        api_key=api_key,
    )
    return {e.indice: [c.model_dump() for c in e.comentarios] for e in respuesta.eventos}


def procesar(
    perfil: PlayerProfile,
    carrera: Carrera,
    noticias: list[NoticiaPrensa],
    estado: Optional[dict],
    seguidores: int,
    reputacion: int,
    contexto_real: str = "",
) -> tuple[list[ActividadInstagram], dict]:
    """La actividad nueva (sin guardar) y el estado nuevo. Si la IA falla,
    la actividad sale igual, sin comentarios."""
    eventos, nuevo_estado = eventos_nuevos(carrera, noticias, estado, seguidores, reputacion)
    comentarios: dict[int, list[dict]] = {}
    if eventos:
        try:
            comentarios = comentar_eventos(perfil, eventos, contexto_real)
        except RuntimeError:
            comentarios = {}
    actividad = [
        ActividadInstagram(
            player_id=perfil.id, fecha_juego=e.fecha_juego, tipo=e.tipo, titulo=e.titulo,
            crecimiento_seguidores=e.crecimiento, comentarios=comentarios.get(i, []),
        )
        for i, e in enumerate(eventos)
    ]
    return actividad, nuevo_estado


def revisar_hinchada(player_id: int) -> Optional[tuple[list[ActividadInstagram], dict]]:
    """Para la pagina de Instagram (corre en un hilo): la partida elegida y
    lo que los hinchas tienen para decir. None sin partida o sin perfil."""
    from roleplay import database
    from roleplay.partida.lector import carrera_actual
    from roleplay.servicios.partida_real import contexto_temporada

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
        contexto_temporada(carrera),
    )
