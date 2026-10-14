"""Backstory del personaje + ganchos narrativos (semillas de tramas
futuras), generados a partir de las respuestas del quiz."""

from typing import Optional

from pydantic import BaseModel

from roleplay.gemini import generar_json
from roleplay.models import (
    CONTEXTOS_SOCIOECONOMICOS,
    ESTADOS_RELACION,
    MOTIVACIONES,
    PERSONALIDADES,
    PlayerProfile,
)


class BackstoryResult(BaseModel):
    backstory: str
    ganchos_narrativos: list[str]


def _build_prompt(profile: PlayerProfile) -> str:
    relacion = ESTADOS_RELACION.get(profile.estado_relacion, "")
    if profile.estado_relacion == "novia_real" and profile.nombre_pareja:
        relacion += f" Su pareja se llama {profile.nombre_pareja}."

    return f"""
Genera un backstory de un futbolista para modo carrera con estos datos.
- Nombre: {profile.nombre_jugador}
- Padres de: {profile.pais_padres}
- Ciudad natal: {profile.ciudad_natal}
- Fecha de nacimiento: {profile.fecha_nacimiento}
- Contexto: {CONTEXTOS_SOCIOECONOMICOS.get(profile.contexto_socioeconomico, "")}
- Personalidad: {PERSONALIDADES.get(profile.personalidad, "")}
- Motivacion: {MOTIVACIONES.get(profile.motivacion, "")}
- Situacion sentimental: {relacion}
- Anecdota: {profile.anecdota_personal or "(ninguna)"}

Devuelve JSON con `backstory` y `ganchos_narrativos`.
`backstory`: 120-200 palabras.
`ganchos_narrativos`: lista de 3 a 5 frases breves.
No inventes nombres de personas o jugadores reales.
""".strip()


def generar_backstory(profile: PlayerProfile, api_key: Optional[str] = None) -> BackstoryResult:
    return generar_json(
        _build_prompt(profile),
        BackstoryResult,
        "Esperate un poco y apreta 'Regenerar backstory' de nuevo.",
        api_key=api_key,
    )
