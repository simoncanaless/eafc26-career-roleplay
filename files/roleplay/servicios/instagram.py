"""Reacciones a un post de Instagram del jugador (comentarios, likes y
cuantos seguidores gana o pierde) y el post sugerido con su voz. Sin IA: el
evaluador lexico lee el post (servicios/lexico.py) y el motor narrativo
escribe (roleplay/datos/corpus_redes.json)."""

from pydantic import BaseModel

from roleplay.models import PlayerProfile
from roleplay.servicios import lexico
from roleplay.servicios.narrador import narrador

TASA_LIKES = 0.05  # un post normal: ~5% de los seguidores, mas con reputacion


class ComentarioIA(BaseModel):  # (el nombre quedo de cuando lo escribia la IA)
    autor: str
    texto: str
    tono: str  # "positivo" | "negativo" | "neutral" | "gracioso"


class InstagramReaccionIA(BaseModel):
    comentarios: list[ComentarioIA]
    likes_estimados: int
    crecimiento_seguidores: int  # puede ser 0 o negativo si el post cayo mal


def generar_reaccion_post(
    perfil: PlayerProfile,
    texto_post: str,
    reputacion_actual: int,
    seguidores_actuales: int,
) -> InstagramReaccionIA:
    from roleplay.servicios.hinchada import _escala, comentarios, datos_de_redes

    lectura = lexico.leer([texto_post])
    polemico = lectura.eje in ("ego_confianza", "excusa_polemica")
    factor = 0.4 if lectura.eje == lexico.NEUTRO else (0.9 if polemico else 1.3)
    if polemico and perfil.personalidad in ("polemico", "carismatico"):
        factor += 0.4  # a sus seguidores les gusta el show
    crecimiento = round(_escala(seguidores_actuales, reputacion_actual) * factor)
    if polemico and reputacion_actual < 40:
        crecimiento = -abs(crecimiento) // 2  # sin reputacion, la polemica resta
    tasa = TASA_LIKES * (0.6 + reputacion_actual / 100) * (1.3 if not polemico and lectura.eje != lexico.NEUTRO else 1)
    datos = datos_de_redes(perfil, texto_post[:40])
    with narrador(perfil.id, "redes") as escritor:
        dichos = comentarios(escritor, "post", crecimiento, datos)
        if polemico:  # un post polemico junta de todo
            dichos += comentarios(escritor, "post", -1, datos)[:2]
        else:
            dichos += comentarios(escritor, "post", 1, datos)[:1]
    return InstagramReaccionIA(
        comentarios=[ComentarioIA(**c) for c in dichos],
        likes_estimados=max(0, round(seguidores_actuales * tasa)),
        crecimiento_seguidores=crecimiento,
    )


def sugerir_post(perfil: PlayerProfile, ultimo_partido: str = "") -> str:
    """Un texto de post con la voz del jugador (su personalidad), sobre su
    ultimo partido. Queda editable antes de publicar."""
    from roleplay.servicios.hinchada import datos_de_redes

    datos = datos_de_redes(perfil)
    situacion = "neutro"
    if perfil.id:
        from roleplay import database

        ultimos = [r for r in database.load_match_interviews(perfil.id) if r.origen != "previa"][:1]
        if ultimos:
            r = ultimos[0]
            situacion = "victoria" if r.goles_equipo > r.goles_rival else "derrota" if r.goles_equipo < r.goles_rival else "empate"
            datos.update(rival=r.equipo_rival or "el rival", marcador=f"{r.goles_equipo}-{r.goles_rival}")
            if r.goles_jugador:
                datos["goles_texto"] = "un gol" if r.goles_jugador == 1 else f"{r.goles_jugador} goles"
                datos["goles_texto_mayus"] = "GOLAZO" if r.goles_jugador == 1 else f"{r.goles_jugador} GOLES"
    personalidad = perfil.personalidad if perfil.personalidad in ("reservado", "carismatico", "polemico", "humilde") else "reservado"
    with narrador(perfil.id, "redes") as escritor:
        return escritor.decir(f"post_{personalidad}_{situacion}", **datos)
