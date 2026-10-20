"""
Mide que tan variadas salen las conferencias: simula N conferencias seguidas
del mismo jugador con el mismo tipo de partido (lo peor para la variedad) y
cuenta preguntas distintas, cuantas se repiten dentro de las ultimas 10 y que
temas salen. Usa una carpeta de datos temporal y sin IA: no toca nada tuyo.

    .venv\\Scripts\\python.exe scripts\\medir_variedad.py [N]
"""

import os
import sys
import tempfile
from collections import Counter, deque
from pathlib import Path

os.environ["EAFC_ROLEPLAY_DATOS"] = tempfile.mkdtemp(prefix="eafc_variedad_")
os.environ["EAFC_SIN_IA"] = "1"
os.environ["EAFC_FC26_GUARDADOS"] = tempfile.mkdtemp(prefix="eafc_variedad_partidas_")
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from roleplay import database  # noqa: E402
from roleplay.models import MatchInterviewRecord, PlayerProfile  # noqa: E402
from roleplay.servicios import entrevista  # noqa: E402
from roleplay.servicios.vision import MatchStats  # noqa: E402


def _aperturas() -> list[str]:
    import json

    corpus = json.loads((Path(entrevista.__file__).resolve().parent.parent / "datos" / "corpus_entrevista.json")
                        .read_text(encoding="utf-8"))
    return sorted((a for k, v in corpus.items() if k.startswith("a_") and isinstance(v, list) for a in v),
                  key=len, reverse=True)


def nucleo(texto: str, aperturas: list[str]) -> str:
    """La pregunta sin la frase de entrada ("Del vestuario:", "Mirando los numeros,"): lo que se siente repetido."""
    for apertura in aperturas:
        if texto.startswith(apertura):
            texto = texto[len(apertura):]
            break
    texto = texto.strip(" :,")
    return texto[:1].lower() + texto[1:]


def medir(conferencias: int = 40) -> dict:
    database.init_db()
    aperturas = _aperturas()
    nucleos, recientes, nucleo_repetido = Counter(), deque(maxlen=9), 0
    perfil = PlayerProfile(nombre_jugador="Simon Canales", club_actual="Man Utd", personalidad="carismatico")
    perfil.id = database.save_profile(perfil)
    vistas, ultimas, repetidas = Counter(), deque(maxlen=30), 0
    for i in range(conferencias):
        stats = MatchStats(goles_equipo=2, goles_rival=1, goles_jugador=1, rating_jugador=7.8, minutos_jugados=90,
                           equipo_rival="Arsenal")
        preguntas = entrevista.generar_entrevista(perfil, stats)
        for pregunta in preguntas:
            texto = pregunta.split(": ", 1)[1]
            repetidas += texto in ultimas
            ultimas.append(texto)
            vistas[texto] += 1
            n = nucleo(texto, aperturas)
            nucleo_repetido += n in recientes
            recientes.append(n)
            nucleos[n] += 1
        respuestas = ["Contento por el equipo, la gente nos banco toda la tarde.",
                      "El arbitro se equivoco, pero nosotros seguimos.", "Vamos por el titulo, sin dudas."]
        database.save_match_interview(MatchInterviewRecord(
            player_id=perfil.id, goles_equipo=2, goles_rival=1, equipo_rival="Arsenal", goles_jugador=1,
            rating_jugador=7.8, minutos_jugados=90, preguntas_entrevista=preguntas, respuestas_jugador=respuestas))
    total = conferencias * entrevista.PREGUNTAS_POR_CONFERENCIA
    return {"preguntas": total, "textos_distintos": len(vistas), "preguntas_distintas": len(nucleos),
            "repetidas_en_las_ultimas_3_conferencias": nucleo_repetido, "la_mas_repetida": nucleos.most_common(1)[0]}


if __name__ == "__main__":
    print(medir(int(sys.argv[1]) if len(sys.argv) > 1 else 40))
