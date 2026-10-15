"""
Evaluador lexico de respuestas (entrevistas, previas, posts): Python puro,
sin IA y al instante.

Tokeniza el texto (sin tildes, en minusculas), busca las palabras y frases
de cada eje de roleplay/datos/lexico.json y suma sus pesos. Una negacion
("no", "nunca", "jamas", "sin"...) en las 2 palabras de antes invierte el
peso: "no fue culpa del arbitro" resta a la excusa en vez de sumar.

Ejes: humildad_equipo, amor_hinchada, ego_confianza, excusa_polemica y
ambicion_foco. El dominante decide como cae lo que dijo; la frase con mas
peso es la cita que sale en la prensa entre «».
"""

import re
import unicodedata
from dataclasses import dataclass, field
from functools import lru_cache

from roleplay.servicios.narrador import corpus

EJES = ("humildad_equipo", "amor_hinchada", "ego_confianza", "excusa_polemica", "ambicion_foco")
NEUTRO = "neutro"
UMBRAL_EJE = 1.5  # menos que esto en todos los ejes: respuestas de cajon
VENTANA_NEGACION = 2
LARGO_CITA = 150


def normalizar(texto: str) -> str:
    sin_tildes = "".join(c for c in unicodedata.normalize("NFD", texto.lower()) if unicodedata.category(c) != "Mn")
    return re.sub(r"[^a-z0-9 ]+", " ", sin_tildes)


def tokens(texto: str) -> list[str]:
    return normalizar(texto).split()


@lru_cache(maxsize=None)
def _diccionario() -> tuple[dict, frozenset, tuple]:
    datos = corpus("lexico")
    ejes = {eje: {tuple(tokens(frase)): peso for frase, peso in palabras.items()} for eje, palabras in datos["ejes"].items()}
    promesas = tuple(tuple(tokens(p)) for p in datos["promesas"])
    return ejes, frozenset(datos["negaciones"]), promesas


def _aparece(frase: tuple, palabras: list[str]) -> list[int]:
    largo = len(frase)
    return [i for i in range(len(palabras) - largo + 1) if tuple(palabras[i:i + largo]) == frase]


def puntuar(texto: str) -> dict[str, float]:
    """Cuanto pesa cada eje en `texto` (puede ser negativo si se lo niega)."""
    ejes, negaciones, _ = _diccionario()
    palabras = tokens(texto)
    puntajes = {eje: 0.0 for eje in EJES}
    for eje, frases in ejes.items():
        for frase, peso in frases.items():
            for i in _aparece(frase, palabras):
                negada = any(p in negaciones for p in palabras[max(0, i - VENTANA_NEGACION):i])
                puntajes[eje] += -peso if negada else peso
    return puntajes


def promesa(texto: str) -> bool:
    _, _, promesas = _diccionario()
    palabras = tokens(texto)
    return any(_aparece(p, palabras) for p in promesas)


def _oraciones(texto: str) -> list[str]:
    return [o.strip(" -\"'«»") for o in re.split(r"(?<=[.!?…])\s+|\n+", texto) if o.strip(" -\"'«»")]


def _recortar(frase: str) -> str:
    frase = frase.rstrip(".")
    if len(frase) <= LARGO_CITA:
        return frase
    corte = frase[:LARGO_CITA].rsplit(" ", 1)[0]
    return corte.rstrip(",;:") + "..."


@dataclass
class Lectura:
    """Lo que dijo el jugador, leido."""

    puntajes: dict[str, float] = field(default_factory=dict)
    eje: str = NEUTRO
    intensidad: float = 0.0  # el puntaje del eje dominante
    cita: str = ""  # su frase mas jugosa (para «...»)
    promesa: str = ""  # una frase con una promesa ("les prometo un gol"), si la hay
    palabras: int = 0


def leer(respuestas: list[str]) -> Lectura:
    texto = " ".join(r for r in respuestas if r)
    puntajes = puntuar(texto)
    eje = max(EJES, key=lambda e: puntajes[e])
    intensidad = puntajes[eje]
    if intensidad < UMBRAL_EJE:
        eje = NEUTRO
    oraciones = [o for r in respuestas for o in _oraciones(r)]

    def peso(oracion: str) -> float:
        p = puntuar(oracion)
        largo = len(tokens(oracion))
        base = (p.get(eje, 0) * 2 if eje != NEUTRO else 0) + sum(max(v, 0) for v in p.values())
        return base + (1.0 if 5 <= largo <= 28 else 0.0)

    cita = _recortar(max(oraciones, key=peso)) if oraciones else ""
    prometida = next((_recortar(o) for o in oraciones if promesa(o)), "")
    return Lectura(puntajes, eje, round(max(intensidad, 0.0), 2), cita, prometida, len(tokens(texto)))
