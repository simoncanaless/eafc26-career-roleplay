"""Lectura de las estadisticas de fin de partido desde la captura, con
Gemini Vision. Lo que lee queda editable en la pantalla antes de seguir."""

from typing import Optional

from pydantic import BaseModel

from roleplay.gemini import generar_json

PROMPT_EXTRACCION = """
Esta imagen es una captura de pantalla de fin de partido de EAFC 26.
Extrae solo las estadisticas del jugador controlado.
Devuelve JSON con estas claves:
- goles_equipo
- goles_rival
- equipo_rival
- goles_jugador
- asistencias_jugador
- rating_jugador
- minutos_jugados
- tarjeta_amarilla
- tarjeta_roja
- hombre_del_partido
- confianza_baja

Si no se puede leer un dato, usa 0/false/"" y marca confianza_baja como true.
""".strip()


class MatchStats(BaseModel):
    goles_equipo: int = 0
    goles_rival: int = 0
    equipo_rival: str = ""
    goles_jugador: int = 0
    asistencias_jugador: int = 0
    rating_jugador: float = 0.0
    minutos_jugados: int = 0
    tarjeta_amarilla: bool = False
    tarjeta_roja: bool = False
    hombre_del_partido: bool = False
    confianza_baja: bool = False


def extraer_stats_partido(imagen_png: bytes, api_key: Optional[str] = None) -> MatchStats:
    return generar_json(
        PROMPT_EXTRACCION,
        MatchStats,
        "Esperate un poco y volve a capturar la pantalla (o escribi las stats a mano).",
        adjunto=(imagen_png, "image/png"),
        api_key=api_key,
    )
