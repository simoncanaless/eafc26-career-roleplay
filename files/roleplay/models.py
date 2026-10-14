"""
Modelos de datos del roleplay: el perfil del personaje y lo que se va
guardando de su carrera (partidos con entrevista, noticias, posts).

Cada dataclass es una tabla de SQLite (ver database.TABLAS): los nombres
de los campos son los nombres de las columnas.
"""

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime
from typing import Optional


def _ahora() -> str:
    return datetime.now().isoformat()


# ---- Catalogos del quiz de personaje (clave -> descripcion) ----

CONTEXTOS_SOCIOECONOMICOS = {
    "humilde": "Crecio en un entorno humilde, con recursos limitados.",
    "clase_media": "Crecio en una familia de clase media, sin grandes lujos ni carencias.",
    "acomodada": "Crecio en una familia acomodada, con acceso a recursos y oportunidades.",
}

PERSONALIDADES = {
    "reservado": "Reservado y de bajo perfil, prefiere que hablen sus actuaciones.",
    "carismatico": "Carismatico y mediatico, disfruta el foco de las camaras.",
    "polemico": "Directo y polemico, no le teme a generar titulares.",
    "humilde": "Humilde y trabajador, valora el esfuerzo por sobre la fama.",
}

MOTIVACIONES = {
    "titulos": "Ganar titulos y trofeos a cualquier costo.",
    "mejor_del_mundo": "Ser reconocido como el mejor jugador del mundo.",
    "familia": "Sacar adelante a su familia y devolverles todo lo que le dieron.",
    "legado": "Dejar un legado en el futbol de su pais.",
}

ESTADOS_RELACION = {
    "novia_real": "En una relacion con su novia de la vida real.",
    "celebridad": "Soltero, pero con posibilidad de iniciar una relacion con una celebridad.",
    "soltero": "Soltero, sin rumbo sentimental definido por ahora.",
}


@dataclass
class PlayerProfile:
    id: Optional[int] = None
    nombre_jugador: str = ""
    pais_padres: str = ""
    ciudad_natal: str = ""
    fecha_nacimiento: str = ""  # YYYY-MM-DD
    contexto_socioeconomico: str = "clase_media"
    personalidad: str = "reservado"
    motivacion: str = "titulos"
    estado_relacion: str = "soltero"
    nombre_pareja: str = ""  # si aplica (novia real)
    anecdota_personal: str = ""
    backstory_generado: str = ""
    ganchos_narrativos: list[str] = field(default_factory=list)
    reputacion_inicial: int = 50  # 0-100, fija desde la creacion
    fecha_creacion: str = field(default_factory=_ahora)
    club_actual: str = ""  # cambia con las transferencias
    # Estado libre de los modulos (reputacion_actual, historial_reputacion,
    # prensa, seguidores_instagram...), para no migrar el esquema por cada
    # sistema nuevo.
    estado_json: dict = field(default_factory=dict)

    def calcular_reputacion_inicial(self) -> int:
        """Reputacion de partida (0-100) segun contexto y personalidad.
        Es deterministica a proposito: no depende de la IA."""
        base = 50

        ajustes_contexto = {"humilde": 10, "clase_media": 0, "acomodada": -5}
        base += ajustes_contexto.get(self.contexto_socioeconomico, 0)

        ajustes_personalidad = {
            "reservado": 5,
            "carismatico": 10,
            "polemico": -10,
            "humilde": 15,
        }
        base += ajustes_personalidad.get(self.personalidad, 0)

        return max(0, min(100, base))

    def to_dict(self) -> dict:
        return asdict(self)

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=2)


@dataclass
class MatchInterviewRecord:
    """Un partido jugado + la entrevista post-partido asociada."""

    id: Optional[int] = None
    player_id: int = 0
    fecha: str = field(default_factory=_ahora)
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
    preguntas_entrevista: list[str] = field(default_factory=list)
    respuestas_jugador: list[str] = field(default_factory=list)  # paralela a preguntas
    reaccion_prensa: str = ""
    delta_reputacion: int = 0
    origen: str = ""  # "partida" (leido del guardado de FC 26), "captura" o "manual"
    fecha_juego: str = ""  # fecha del partido dentro del juego (AAAA-MM-DD), si se sabe


@dataclass
class NoticiaPrensa:
    """Una noticia: sobre el jugador (disparada por un hito, ej. racha
    goleadora) o general del mundo del futbol (inventada, de ambiente)."""

    id: Optional[int] = None
    player_id: int = 0
    fecha: str = field(default_factory=_ahora)
    categoria: str = "jugador"  # "jugador" | "general"
    tono: str = "neutral"  # "positiva" | "negativa" | "mixta" | "neutral"
    titular: str = ""
    cuerpo: str = ""
    hitos: list[str] = field(default_factory=list)  # ej: ["racha_goleadora:5"]


@dataclass
class InstagramPost:
    """Un post de Instagram del jugador, con las reacciones generadas."""

    id: Optional[int] = None
    player_id: int = 0
    fecha: str = field(default_factory=_ahora)
    texto: str = ""
    likes: int = 0
    crecimiento_seguidores: int = 0
    comentarios: list[dict] = field(default_factory=list)  # [{"autor","texto","tono"}]


@dataclass
class ActividadInstagram:
    """Lo que pasa en el Instagram del jugador sin que publique nada: los
    hinchas reaccionan a sus partidos y a las noticias sobre el
    (servicios/hinchada.py). Los seguidores los calcula el codigo; la IA
    solo escribe los comentarios."""

    id: Optional[int] = None
    player_id: int = 0
    fecha: str = field(default_factory=_ahora)
    fecha_juego: str = ""  # dia del juego al que reaccionan
    tipo: str = "partido"  # "partido" | "noticia"
    titulo: str = ""  # "Man Utd 5-3 Sunderland · 5 goles tuyos" o el titular de la noticia
    crecimiento_seguidores: int = 0
    comentarios: list[dict] = field(default_factory=list)  # [{"autor","texto","tono"}]
