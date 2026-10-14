"""
Siembra 5 partidos falsos (con gol, rating 8.0) en el ULTIMO personaje,
para probar la prensa sin jugar 5 partidos de verdad. Ojo: van a la base
real y cuentan para las rachas y los hitos de ese personaje.

    .venv\\Scripts\\python.exe scripts\\seed_test_matches.py           siembra
    .venv\\Scripts\\python.exe scripts\\seed_test_matches.py --borrar  borra los sembrados
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from roleplay.database import conectar, init_db, load_latest_profile, save_match_interview  # noqa: E402
from roleplay.models import MatchInterviewRecord  # noqa: E402

PREFIJO_RIVAL = "Rival de prueba"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.strip().splitlines()[0])
    parser.add_argument("--borrar", action="store_true", help="borra los partidos sembrados")
    args = parser.parse_args()

    init_db()
    perfil = load_latest_profile()
    if perfil is None:
        print("No hay ningun personaje creado todavia. Corre app.py primero.")
        return

    if args.borrar:
        with conectar() as conn:
            borrados = conn.execute(
                "DELETE FROM partido_entrevista WHERE player_id = ? AND equipo_rival LIKE ?",
                (perfil.id, f"{PREFIJO_RIVAL}%"),
            ).rowcount
        print(f"Se borraron {borrados} partidos de prueba de {perfil.nombre_jugador}.")
        return

    for i in range(5):
        save_match_interview(
            MatchInterviewRecord(
                player_id=perfil.id,
                goles_equipo=2,
                goles_rival=1,
                equipo_rival=f"{PREFIJO_RIVAL} {i + 1}",
                goles_jugador=1,
                asistencias_jugador=0,
                rating_jugador=8.0,
                minutos_jugados=90,
            )
        )

    print(f"Se sembraron 5 partidos falsos (con gol) para {perfil.nombre_jugador}.")
    print("Deberian salir en una noticia: racha goleadora de 5, 5 goles en la carrera")
    print("y buen momento (rating 8.0). Abri Entrevistas y apreta 'Revisar prensa ahora'.")
    print("Para sacarlos despues: scripts\\seed_test_matches.py --borrar")


if __name__ == "__main__":
    main()
