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
    """Que clase de pagina publica sobre el evento."""
    texto = f"{evento.titulo} {evento.detalle}".lower()
    if evento.tipo == "partido":
        return "viral" if "gol" in evento.titulo.lower() else "medio"
    if any(p in texto for p in PALABRAS_FARANDULA):
        return "farandula"
    if "«" in evento.detalle or "entrevista" in texto or "conferencia" in texto:
        return "polemica" if evento.crecimiento < 0 else "medio"
    if any(p in texto for p in PALABRAS_LUJO):
        return "viral"
    return "polemica" if evento.crecimiento < 0 else "medio"


def _pagina(paginas: list[dict], tipo: str, dado: random.Random) -> dict:
    del_tipo = [p for p in paginas if p.get("tipo") == tipo]
    return dado.choice(del_tipo or paginas)


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
            texto = escritor.decir(f"feed_{tipo}", **base, titulo=evento.titulo)
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
    return (list(reversed(nuevos)) + anterior)[:MAXIMO_FEED]
