"""Reacciones a un post de Instagram del jugador (comentarios, likes y
cuantos seguidores gana o pierde) y el post sugerido con su voz. Los numeros
los decide el codigo: el evaluador lexico lee el post (servicios/lexico.py).
Los comentarios: la IA hibrida (servicios/ia.py) si esta, contestando al
post textual; si no, el motor narrativo (roleplay/datos/corpus_redes.json)."""

import random

from pydantic import BaseModel

from roleplay.models import PlayerProfile
from roleplay.servicios import ia, lexico
from roleplay.servicios.narrador import narrador

TASA_LIKES = 0.05  # un post normal: ~5% de los seguidores, mas con reputacion
MAXIMO_COLEGAS = 2
PROBABILIDAD_FAMOSA = 0.3
MAXIMO_LIKES_VERIFICADOS = 3
CATEGORIAS_QUE_COMENTAN = {"deportista"}  # (ademas de los futbolistas y de su pareja)


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
    dichos = _comentarios_con_ia(perfil, texto_post, crecimiento, polemico) or dichos
    if perfil.id:
        from roleplay import database
        from roleplay.servicios import ecosistema

        fama = ecosistema.calcular_fama_jugador(perfil.id)["fama"]
        dichos += comentarios_del_ambiente(perfil, fama, database.get_estado_amor(perfil.id), random.Random())
    return InstagramReaccionIA(
        comentarios=[ComentarioIA(**c) for c in dichos],
        likes_estimados=max(0, round(seguidores_actuales * tasa)),
        crecimiento_seguidores=crecimiento,
    )


def comentarios_del_ambiente(perfil: PlayerProfile, fama: int, estado_amor: dict, dado: random.Random) -> list[dict]:
    """Lo que dejan en sus posts los futbolistas y las celebridades del catalogo
    de Simon (servicios/ecosistema.py): los colegas, si su fama supera la que
    piden para comentar; su pareja (un guino si es secreto: los hinchas lo
    notan); o alguna celebridad de su nivel. El texto, del corpus."""
    from roleplay.servicios import ecosistema
    from roleplay.servicios.hinchada import datos_de_redes

    datos = datos_de_redes(perfil)
    resultado = []
    with narrador(perfil.id, "redes") as escritor:
        def hincha(simbolo: str, **extra) -> dict:
            return {"autor": escritor.elegir("autor_hincha", **datos, n=dado.randint(7, 99)),
                    "texto": escritor.decir(simbolo, **datos, **extra), "tono": "gracioso"}

        colegas = [c for c in ecosistema.futbolistas_ig() if c.get("usuario_ig")
                   and ecosistema.numero(c.get("fama_minima_para_comentar"), 101) <= fama]
        elegidos = dado.sample(colegas, min(len(colegas), MAXIMO_COLEGAS, dado.randint(0, 1 + fama // 40)))
        for colega in elegidos:
            resultado.append({"autor": colega["usuario_ig"], "texto": escritor.decir("com_colega"), "tono": "positivo"})
        if elegidos and dado.random() < 0.5:
            resultado.append(hincha("com_nota_colega", colega=elegidos[0]["usuario_ig"]))

        estado = (estado_amor or {}).get("estado", "soltero")
        pareja = (estado_amor or {}).get("pareja") or {}
        if pareja.get("usuario_ig") and estado in ("secreto", "pareja", "comprometido", "casado"):
            secreto = estado == "secreto"
            resultado.append({"autor": pareja["usuario_ig"],
                              "texto": escritor.decir("com_pareja_secreta" if secreto else "com_pareja"),
                              "tono": "positivo"})
            if secreto:
                resultado.append(hincha("com_nota_famosa", famosa=pareja["usuario_ig"]))
        elif dado.random() < PROBABILIDAD_FAMOSA:
            # solo deportistas: una cantante de jazz no tiene nada que hacer en los posts de un futbolista
            de_su_nivel = [c for c in ecosistema.celebridades() if c.get("usuario_ig")
                           and c.get("categoria") in CATEGORIAS_QUE_COMENTAN
                           and ecosistema.numero(c.get("exigencia"), 101) <= fama]
            if de_su_nivel:
                famosa = dado.choice(de_su_nivel)
                resultado.append({"autor": famosa["usuario_ig"], "texto": escritor.decir("com_famosa"), "tono": "positivo"})
                resultado.append(hincha("com_nota_famosa", famosa=famosa["usuario_ig"]))

        # likes verificados: colegas y celebridades de su nivel que no comentaron
        ya = {c["autor"] for c in resultado}
        verificados = [c["usuario_ig"] for c in colegas if c["usuario_ig"] not in ya]
        verificados += [c["usuario_ig"] for c in ecosistema.celebridades() if c.get("usuario_ig")
                        and c.get("categoria") in CATEGORIAS_QUE_COMENTAN
                        and c["usuario_ig"] not in ya and ecosistema.numero(c.get("exigencia"), 101) <= fama]
        for usuario in dado.sample(verificados, min(len(verificados), dado.randint(0, MAXIMO_LIKES_VERIFICADOS))):
            resultado.append({"autor": usuario, "texto": "le dio like ❤️ (verificado)", "tono": "like"})
    return resultado


SISTEMA_COMENTARIOS = (
    "Sos la seccion de comentarios del Instagram de un futbolista en un juego de roleplay. Escribi 4 o 5 "
    "comentarios de cuentas inventadas (@usuarios de hinchas fanaticos, rivales, cuentas de memes) que "
    "RESPONDAN DIRECTAMENTE a lo que dice el post, con humor y jerga de redes (pueden llevar emojis). "
    "El tono general sigue a como le cayo el post a la gente. `tono` de cada uno: positivo, negativo, "
    "neutral o gracioso. Las cuentas son inventadas: nunca nombres de personas reales."
)


def _comentarios_con_ia(perfil: PlayerProfile, texto_post: str, crecimiento: int, polemico: bool) -> list[dict]:
    from roleplay.servicios import cruce, entrevista

    ultimo = ""
    if perfil.id:
        from roleplay import database

        r = next((r for r in database.load_match_interviews(perfil.id) if r.origen != "previa"), None)
        if r is not None:
            ultimo = f"Su ultimo partido: {r.goles_equipo}-{r.goles_rival} vs {r.equipo_rival or 'el rival'}, " \
                     f"{r.goles_jugador} goles, nota {r.rating_jugador:.1f}."
    vida = ia.describir_cruces(cruce.cruces(perfil.id, None, None, entrevista._carrera()) if perfil.id else [])
    como = "le cayo bien" if crecimiento > 0 and not polemico else "genero polemica" if polemico else "le cayo mal"
    datos = ia.pedir_json(
        SISTEMA_COMENTARIOS,
        f"{ia.ficha(perfil)}\n{ultimo}\nLo que pasa en su vida:\n{vida}\n\nEl post (textual):\n{texto_post[:1500]}\n\n"
        f"Como cayo: {como}.",
        {"comentarios": [{"autor": "@usuario", "texto": "...", "tono": "positivo"}]},
        jugador=perfil.id,
    )
    return ia.comentarios_validos(datos.get("comentarios") if datos else None, minimo=3)


def post_de_compra(perfil: PlayerProfile, objeto: str, tienda: str = "") -> str:
    """El post para presumir algo que se compro ("PRESUMIR EN INSTAGRAM", en
    Vida), con la voz de su personalidad. Queda editable antes de publicar."""
    from roleplay.servicios.hinchada import datos_de_redes

    datos = {**datos_de_redes(perfil), "objeto": objeto.strip(), "tienda": tienda.strip()}
    personalidad = perfil.personalidad if perfil.personalidad in ("reservado", "carismatico", "polemico", "humilde") else "reservado"
    with narrador(perfil.id, "redes") as escritor:
        return escritor.decir(f"presumir_{personalidad}", **datos)


FACTOR_PAREJA = 2.0  # un post con la pareja mueve mas que uno comun (x2 mas con una famosa)


def post_con_pareja(perfil: PlayerProfile, pareja: str, boda: bool = False, familia: bool = False) -> str:
    """El texto del post con su pareja (o de la boda), con su voz. Queda editable."""
    from roleplay.servicios.hinchada import datos_de_redes

    datos = {**datos_de_redes(perfil), "pareja": pareja.strip()}
    personalidad = perfil.personalidad if perfil.personalidad in ("reservado", "carismatico", "polemico", "humilde") else "reservado"
    with narrador(perfil.id, "redes") as escritor:
        tipo = "boda" if boda else "familia" if familia else "pareja"
        return escritor.decir(f"post_{tipo}_{personalidad}", **datos)


def post_promo(perfil: PlayerProfile, marca: str) -> str:
    """El post de una promo con una marca (servicios/patrocinios.py), con su voz y el #publi. Queda editable."""
    from roleplay.servicios.hinchada import datos_de_redes

    datos = {**datos_de_redes(perfil), "marca": marca.strip()}
    personalidad = perfil.personalidad if perfil.personalidad in ("reservado", "carismatico", "polemico", "humilde") else "reservado"
    with narrador(perfil.id, "redes") as escritor:
        return escritor.decir(f"post_promo_{personalidad}", **datos)


def reaccion_post_con_pareja(perfil: PlayerProfile, texto: str, reputacion: int, seguidores: int,
                             famosa: bool) -> InstagramReaccionIA:
    """Corre en un hilo: la reaccion de un post con la pareja (mas seguidores y likes)."""
    reaccion = generar_reaccion_post(perfil, texto, reputacion, seguidores)
    factor = FACTOR_PAREJA * (2 if famosa else 1)
    reaccion.crecimiento_seguidores = round(abs(reaccion.crecimiento_seguidores) * factor)
    reaccion.likes_estimados = round(reaccion.likes_estimados * factor)
    return reaccion


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
