"""Reacciones a un post de Instagram del jugador: comentarios, likes y
cuantos seguidores gana o pierde."""

from typing import Optional

from pydantic import BaseModel

from roleplay.gemini import generar_json
from roleplay.models import PlayerProfile
from roleplay.servicios.contexto import ficha_jugador


class ComentarioIA(BaseModel):
    autor: str
    texto: str
    tono: str  # "positivo" | "negativo" | "neutral" | "gracioso"


class InstagramReaccionIA(BaseModel):
    comentarios: list[ComentarioIA]
    likes_estimados: int
    crecimiento_seguidores: int  # puede ser 0 o negativo si el post cayo mal


def _contexto(contexto_real: str) -> str:
    if not contexto_real:
        return ""
    return f"\n{contexto_real}\n(Datos reales de su partida: los hinchas los conocen y los comentan.)\n"


class PostSugerido(BaseModel):
    texto: str


def _build_prompt_post(
    perfil: PlayerProfile,
    texto_post: str,
    reputacion_actual: int,
    seguidores_actuales: int,
    contexto_real: str = "",
) -> str:
    return f"""
Sos el/la community manager que simula las redes sociales de
{perfil.nombre_jugador}, un futbolista de EAFC 26 en un modo carrera
roleplay.

{ficha_jugador(perfil)}
Reputacion publica actual: {reputacion_actual}/100.
Seguidores actuales en Instagram: {seguidores_actuales}.
{_contexto(contexto_real)}
{perfil.nombre_jugador} acaba de publicar este post:
"{texto_post}"

Genera:
1. Entre 3 y 6 comentarios realistas reaccionando al post (autor
   inventado: hincha, critico, o algun colega futbolista ficticio,
   mas el texto del comentario y su tono). Varia el tono: mezcla de
   positivos, algun critico/negativo si la reputacion no es muy alta
   o el post se presta para polemica, y algun comentario gracioso. Si
   hay datos reales de su temporada, que algunos comentarios los
   mencionen (un resultado, sus goles, la tabla). NO uses nombres de
   personas reales como autores.
2. likes_estimados: un numero entero coherente con los seguidores
   actuales y la reputacion (mas seguidores/reputacion = mas likes,
   pero un post polemico con mala reputacion puede tener pocos likes y
   muchos comentarios negativos).
3. crecimiento_seguidores: un numero entero (puede ser 0 o negativo si
   el post genero rechazo) de cuantos seguidores nuevos gano o perdio
   con este post especifico.
""".strip()


def generar_reaccion_post(
    perfil: PlayerProfile,
    texto_post: str,
    reputacion_actual: int,
    seguidores_actuales: int,
    contexto_real: str = "",
    api_key: Optional[str] = None,
) -> InstagramReaccionIA:
    reaccion = generar_json(
        _build_prompt_post(perfil, texto_post, reputacion_actual, seguidores_actuales, contexto_real),
        InstagramReaccionIA,
        "Esperate un poco y apreta 'Publicar' de nuevo (el texto del post sigue ahi).",
        api_key=api_key,
    )
    reaccion.likes_estimados = max(0, reaccion.likes_estimados)
    return reaccion


def sugerir_post(perfil: PlayerProfile, contexto_real: str = "", ultimo_partido: str = "",
                 api_key: Optional[str] = None) -> str:
    """Un texto de post escrito con la voz del jugador (su personalidad),
    sobre su ultimo partido o su momento. Queda editable antes de publicar."""
    sugerido = generar_json(
        f"""
Escribi un post de Instagram (1 a 3 frases, en espanol, con 0 a 3 emojis
y hasta 2 hashtags) como si lo escribiera {perfil.nombre_jugador}, con su
personalidad.

{ficha_jugador(perfil)}
{_contexto(contexto_real)}
{"Su ultimo partido: " + ultimo_partido if ultimo_partido else ""}

Que suene a futbolista de verdad en sus redes: agradecer, picar al rival,
celebrar un gol o pedir calma segun como le fue y segun su personalidad.
No inventes resultados ni datos que no esten arriba. Devolve solo el texto.
""".strip(),
        PostSugerido,
        "Esperate un poco y apreta 'Sugerir post' de nuevo.",
        api_key=api_key,
    )
    return sugerido.texto.strip().strip('"')
