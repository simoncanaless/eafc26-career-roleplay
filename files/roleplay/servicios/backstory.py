"""Backstory del personaje + ganchos narrativos (semillas de tramas
futuras), armados a partir de las respuestas del asistente: un parrafo por
lo que contesto (de donde viene, como es, que lo mueve, su vida personal y
su anecdota), con el motor narrativo (roleplay/datos/corpus_vida.json).
Sin IA, al instante, y queda editable."""

import random
from typing import Optional

from pydantic import BaseModel

from roleplay.models import PlayerProfile
from roleplay.servicios.narrador import Narrador, unir

GANCHOS = 4


class BackstoryResult(BaseModel):
    backstory: str
    ganchos_narrativos: list[str]


def generar_backstory(profile: PlayerProfile, dado: Optional[random.Random] = None) -> BackstoryResult:
    escritor = Narrador("vida", dado=dado, ricas=True)
    datos = {
        "nombre": profile.nombre_jugador or "El jugador",
        "ciudad": profile.ciudad_natal.strip(),
        "pais_padres": profile.pais_padres.strip(),
        "anio": profile.fecha_nacimiento[:4] if profile.fecha_nacimiento[:4].isdigit() else "",
        "pareja": profile.nombre_pareja.strip(),
        "anecdota": profile.anecdota_personal.strip().rstrip(".")[:1].lower() + profile.anecdota_personal.strip().rstrip(".")[1:],
        "club": profile.club_actual.strip(),
    }
    relacion = profile.estado_relacion if profile.estado_relacion in ("novia_real", "celebridad", "soltero") else "soltero"
    if relacion == "novia_real" and not datos["pareja"]:
        relacion = "soltero"
    parrafos = [
        escritor.elegir(f"b_origen_{profile.contexto_socioeconomico}", **datos)
        or escritor.elegir("b_origen_clase_media", **datos),
        unir(escritor.elegir(f"b_personalidad_{profile.personalidad}", **datos),
             escritor.elegir(f"b_motivacion_{profile.motivacion}", **datos)),
        unir(escritor.elegir(f"b_relacion_{relacion}", **datos), escritor.elegir("b_anecdota", **datos),
             escritor.elegir("b_cierre", **datos)),
    ]
    origen = {"humilde": "humilde_origen", "acomodada": "acomodada"}.get(profile.contexto_socioeconomico, "")
    fuentes = [f"g_{profile.motivacion}", f"g_{profile.personalidad}", f"g_{relacion}", f"g_{origen}"]
    ganchos = []
    for fuente in fuentes:
        if escritor.tiene(fuente) and escritor.puede(fuente, **datos):
            gancho = escritor.elegir(fuente, **datos)
            if gancho and gancho not in ganchos:
                ganchos.append(gancho)
    while len(ganchos) < 3:  # siempre al menos tres tramas
        extra = escritor.elegir(escritor.dado.choice([f for f in ("g_titulos", "g_legado", "g_familia") if f]), **datos)
        if extra not in ganchos:
            ganchos.append(extra)
    return BackstoryResult(backstory="\n\n".join(p for p in parrafos if p), ganchos_narrativos=ganchos[:GANCHOS])
