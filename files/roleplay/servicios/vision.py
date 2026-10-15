"""Las estadisticas de un partido del jugador (MatchStats).

Antes se leian de una captura de la pantalla de fin de partido con IA. Sin
IA no hay forma confiable de leer esa pantalla (cambia con cada modo y cada
idioma), asi que el partido sale del guardado de la carrera
(roleplay/partida/, "Cargar de mi partida") o se escribe a mano."""

from pydantic import BaseModel


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


def extraer_stats_partido(_imagen_png: bytes) -> MatchStats:
    """(Sin IA no se lee la captura: queda para quien la llame, con el aviso de que hacer.)"""
    raise RuntimeError(
        "Leer la captura de pantalla necesitaba IA y la app ya no la usa. "
        "Usa 'Cargar de mi partida' o escribi los numeros a mano."
    )
