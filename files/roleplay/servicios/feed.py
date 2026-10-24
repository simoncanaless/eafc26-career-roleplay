"""
Feed global de Instagram: las paginas de futbol de ecosistema_ig.json
(datos de Simon: @433, @fabrizioromano, @elchiringuitotv, @tmz_tv...)
publican solas sobre el jugador cuando el juego avanza (cada revision de la
hinchada): sus partidos, las noticias sobre el (la cita de su entrevista, sus
compras, su vida privada) y, si es famoso, rumores de traspaso.

Que pagina publica y sobre que lo decide el codigo (el tipo de pagina segun
lo que paso); el texto, el motor narrativo (corpus_redes.json, feed_<tipo>).
Sin el archivo de Simon no hay feed (lista vacia). Queda en
estado_json.hinchada.feed (el mas nuevo primero).
"""

import random
from typing import Optional

from roleplay.models import PlayerProfile
from roleplay.servicios import ecosistema
from roleplay.servicios.narrador import narrador

MAXIMO_FEED = 30
PROBABILIDAD_POST = 0.6  # por evento
PROBABILIDAD_RUMOR = 0.15  # por revision, si es famoso
FAMA_RUMOR = 60
LIKES = {"viral": (150_000, 2_500_000), "mercado": (80_000, 900_000), "polemica": (20_000, 250_000),
         "farandula": (40_000, 600_000), "medio": (15_000, 200_000)}
PALABRAS_FARANDULA = ("pareja", "romance", "novia", "cena", "alfombra", "visto", "rumor", "boda", "casamiento", "secreto",
                      "fiesta", "noche", "boliche", "yate", "chisme", "captura")
PALABRAS_LUJO = ("compro", "estrena", "llego", "mansion", "yate", "jet", "reloj", "auto")


def _tipo(evento) -> str:
    """Que clase de pagina publica sobre el evento. Se mira el TITULO (de que se trata):
    el cuerpo de una noticia nombra de paso a la pareja o una noche de fiesta y una cita
    de conferencia terminaba en la pagina de chismes (Simon, 2026-10-21)."""
    titulo = evento.titulo.lower()
    if evento.tipo == "partido":
        return "viral" if "gol" in titulo else "medio"
    if evento.tipo == "amor" or any(p in titulo for p in PALABRAS_FARANDULA):
        return "farandula"
    if "«" in evento.titulo or "«" in evento.detalle[:200] or "entrevista" in titulo or "conferencia" in titulo:
        return "polemica" if evento.crecimiento < 0 else "medio"
    if any(p in titulo for p in PALABRAS_LUJO):
        return "viral"
    return "polemica" if evento.crecimiento < 0 else "medio"


# si no hay una pagina de ese tipo, la que mas se le parece (nunca la de chismes para una cita)
PARECIDAS = {"polemica": ("medio", "viral"), "medio": ("polemica", "viral"), "viral": ("medio",),
             "mercado": ("medio",), "farandula": ("viral",)}


def _pagina(paginas: list[dict], tipo: str, dado: random.Random) -> dict:
    for buscado in (tipo, *PARECIDAS.get(tipo, ())):
        del_tipo = [p for p in paginas if p.get("tipo") == buscado]
        if del_tipo:
            return dado.choice(del_tipo)
    return dado.choice(paginas)


def _likes(tipo: str, fama: int, dado: random.Random) -> int:
    minimo, maximo = LIKES.get(tipo, LIKES["medio"])
    return round(minimo + (maximo - minimo) * (fama / 100) * dado.uniform(0.6, 1.0))


def _interesado(carrera, dado: random.Random) -> Optional[str]:
    """Un gigante (tier 1) que no es su club, para el rumor."""
    if carrera is None:
        return None
    propio = ecosistema.club_del_usuario(carrera)
    gigantes = sorted(e for e, t in ecosistema._tiers(carrera).items() if t == 1 and e != propio)
    return carrera.equipo(dado.choice(gigantes)) if gigantes else None


def actualizar(perfil: PlayerProfile, eventos: list, anterior: list, seguidores: int, reputacion: int,
               carrera=None) -> list[dict]:
    """El feed nuevo: lo que publicaron las paginas sobre `eventos` (EventoHinchada) + lo anterior."""
    paginas = ecosistema.paginas_futbol()
    anterior = list(anterior or [])
    if not paginas or perfil.id is None:
        return anterior
    hoy = carrera.fecha_actual() if carrera is not None else None
    fecha = hoy.isoformat() if hoy else ""
    dado = random.Random(f"feed:{perfil.id}:{fecha}:{len(anterior)}:{len(eventos)}")
    tier = ecosistema.tier_club(carrera, ecosistema.club_del_usuario(carrera))
    fama = ecosistema.fama_jugador(reputacion, tier, ecosistema.goles_de_la_temporada(carrera))
    partes = perfil.nombre_jugador.split()
    base = {"apellido": partes[-1] if partes else "el crack", "nombre": perfil.nombre_jugador,
            "club": perfil.club_actual or "su club"}
    nuevos = []
    with narrador(perfil.id, "redes") as escritor:
        for evento in eventos:
            tipo = _tipo(evento)
            if tipo != "farandula" and dado.random() >= PROBABILIDAD_POST:
                continue  # (la farandula no se pierde un chisme)
            pagina = _pagina(paginas, tipo, dado)
            texto = escritor.decir(f"feed_{tipo}", **base, titulo=getattr(evento, "titular", "") or evento.titulo)
            if texto:
                nuevos.append({"pagina": pagina.get("nombre", ""), "usuario_ig": pagina.get("usuario_ig", ""),
                               "tipo": tipo, "texto": texto, "fecha": evento.fecha_juego or fecha,
                               "likes": _likes(tipo, fama, dado)})
        interesado = _interesado(carrera, dado) if fama >= FAMA_RUMOR else None
        if interesado and dado.random() < PROBABILIDAD_RUMOR:
            pagina = _pagina(paginas, "mercado", dado)
            texto = escritor.decir("feed_rumor", **base, interesado=interesado)
            if texto:
                nuevos.append({"pagina": pagina.get("nombre", ""), "usuario_ig": pagina.get("usuario_ig", ""),
                               "tipo": "rumor", "texto": texto, "fecha": fecha,
                               "likes": _likes("mercado", fama, dado)})
    nuevos = con_formato_de_cada_pagina(perfil, nuevos)
    return (list(reversed(nuevos)) + anterior)[:MAXIMO_FEED]


# ---- el formato de cada pagina (IA; pedido de Simon del 2026-10-24) ----
# Lo que publica cada pagina lo decide el codigo (que pagina, sobre que hecho); la IA solo le da la forma de esa
# cuenta. Los hechos los cuida la guardia de ia.py: un numero o un nombre que no esta en el post de base se descarta
# y queda el texto del corpus.
FORMATOS = {
    "@fabrizioromano": "exclusiva de mercado: arranca con 🚨, frases cortas, cita textual si hay; \"HERE WE GO\" "
                       "SOLO si el dato es un pase cerrado (un interes o un rumor es \"contactos\", \"atentos\").",
    "@433": "cultura de vestuario y viral: corto, emojis, y termina con una pregunta abierta a los seguidores.",
    "@brfootball": "meme y remate: una linea con punchline, tono burlon o epico.",
    "@elchiringuitotv": "debate explosivo de estudio: alguna frase en MAYUSCULAS, exclamaciones, toma partido.",
    "@tmz_tv": "chisme: tono de primicia de farandula, sin afirmar nada que no este en el post.",
}
FORMATO_POR_TIPO = {
    "viral": "viral: corto, con emojis y energia.", "medio": "medio deportivo: informativo pero con gancho.",
    "mercado": "mercado de pases: tono de primicia, sin afirmar un pase que no esta cerrado.",
    "polemica": "debate: toma partido y abre la discusion.", "farandula": "farandula: chisme liviano.",
    "rumor": "rumor de mercado: \"atentos\", \"contactos\", nunca un pase cerrado.",
}
SISTEMA_FEED = (
    "TAREA: las paginas de futbol de Instagram publican sobre un futbolista, en un juego de roleplay. Te paso cada "
    "post de base y el FORMATO de la cuenta que lo publica: reescribilo con ese formato (1 a 3 oraciones), en "
    "tercera persona.\n"
    "LO MAS IMPORTANTE: dice lo MISMO que el post de base: los nombres, los clubes, el marcador, los goles y el "
    "hecho quedan tal cual; no agregues hechos. Un rumor sigue siendo rumor.\n"
    "EJEMPLO. Base: \"Arsenal sigue de cerca a Canales\"; cuenta @fabrizioromano.\n"
    "  BIEN: \"🚨 Arsenal sigue de cerca a Canales. Contactos iniciados, atentos.\"\n"
    "  MAL: \"🚨 HERE WE GO! Canales al Arsenal\" (es un interes, no un pase cerrado)."
)


def con_formato_de_cada_pagina(perfil: PlayerProfile, posts: list[dict]) -> list[dict]:
    """Los mismos posts con la forma de la cuenta que los publica (una llamada para todos), o como estaban."""
    if not posts:
        return posts
    from roleplay.servicios import ia

    lista = "\n".join(
        f"{i}. {p['usuario_ig']} ({p.get('pagina', '')}) - formato: "
        f"{FORMATOS.get(p['usuario_ig'].lower(), FORMATO_POR_TIPO.get(p['tipo'], 'medio deportivo'))}\n"
        f"   Post de base: {p['texto']}" for i, p in enumerate(posts))
    datos = ia.pedir_json(SISTEMA_FEED, f"{ia.ficha(perfil)}\n\nLos posts:\n{lista}",
                          {"posts": [{"indice": 0, "texto": "..."}]})
    resultado = list(posts)
    for item in (datos or {}).get("posts") or []:
        if isinstance(item, dict) and isinstance(item.get("indice"), int) and 0 <= item["indice"] < len(posts):
            texto = ia.texto(item.get("texto"), 400)
            if texto:
                resultado[item["indice"]] = {**posts[item["indice"]], "texto": texto}
    return resultado
