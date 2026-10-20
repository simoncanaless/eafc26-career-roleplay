"""
Partida imaginaria para probar la vida sentimental (Explorar Instagram VIP,
DMs, romance secreto, oficializar, comentarios de famosas en tus posts) sin
tocar tu carrera real.

Arma (o reusa) la carpeta prueba/ (en .gitignore) con:
- su propia base: un personaje de prueba SOLTERO, con la reputacion y los
  seguidores que digas;
- una partida de FC 26 FALSA (la misma que usan las pruebas: Man Utd, tier 1);
- tus claves de IA si las tenes (para que los comentarios tambien la usen);
y abre la app con esa carpeta (EAFC_ROLEPLAY_DATOS y EAFC_FC26_GUARDADOS):
tu career_roleplay.db y tu partida real ni se leen. Las famosas, paginas y
autos son los de roleplay/datos (tus datos).

    .venv\\Scripts\\python.exe scripts\\partida_de_prueba.py                abre la de prueba (la arma si no esta)
    .venv\\Scripts\\python.exe scripts\\partida_de_prueba.py --reiniciar    la borra y la arma de nuevo
    .venv\\Scripts\\python.exe scripts\\partida_de_prueba.py --reiniciar --reputacion 95 --seguidores 3000000
    --sin-abrir: solo la arma

Con la partida falsa el juego no avanza, asi que la espera de una semana del
juego entre DMs no se cumpliria nunca: en la de prueba no hay espera
(EAFC_DM_SIN_ESPERA=1, solo aca).
"""

import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
CARPETA = RAIZ / "prueba"
NOMBRE = "Prueba Parejas"


def entorno(carpeta: Path) -> dict:
    return {**os.environ, "EAFC_ROLEPLAY_DATOS": str(carpeta), "EAFC_FC26_GUARDADOS": str(carpeta / "guardados"),
            "EAFC_DM_SIN_ESPERA": "1"}


def armar(carpeta: Path, reputacion: int, seguidores: int, personalidad: str) -> None:
    """Corre en un proceso aparte (roleplay.config fija la carpeta de datos al importarse)."""
    codigo = f"""
import json, sys
sys.path[:0] = [{str(RAIZ)!r}, {str(RAIZ / 'tests')!r}]
from pathlib import Path
import fabrica_partida
from roleplay import ajustes, database
from roleplay.models import PlayerProfile

carpeta = Path({str(carpeta)!r})
(carpeta / "guardados").mkdir(parents=True, exist_ok=True)
(carpeta / "guardados" / "CmPlr1").write_bytes(fabrica_partida.construir_bytes(nombre_partida="Partida de prueba (parejas)"))
database.init_db()
perfil = PlayerProfile(nombre_jugador={NOMBRE!r}, club_actual="Man Utd", personalidad={personalidad!r},
                       estado_relacion="soltero", reputacion_inicial={reputacion})
pid = database.save_profile(perfil)
database.sumar_seguidores(pid, {seguidores} - database.get_seguidores(pid))
reales = Path({str(RAIZ / 'ajustes.json')!r})
if reales.exists():  # tus claves de IA, para que la prueba tambien la use (nunca se muestran)
    datos = json.loads(reales.read_text(encoding="utf-8"))
    ajustes.guardar(**{{k: datos[k] for k in ("groq_api_key", "gemini_api_key", "sin_ia") if datos.get(k)}})
print(pid)
"""
    resultado = subprocess.run([sys.executable, "-c", codigo], env=entorno(carpeta), capture_output=True, text=True)
    if resultado.returncode != 0:
        raise SystemExit(f"No se pudo armar la partida de prueba:\n{resultado.stderr}")
    if (RAIZ / ".env").exists():
        shutil.copy2(RAIZ / ".env", carpeta / ".env")  # (la clave vieja de Gemini, si esta)
    # y queda en "Tus carreras" (Ajustes): se puede cambiar a ella desde la app
    sys.path.insert(0, str(RAIZ))
    from roleplay import carreras

    carreras.crear("Partida de prueba (parejas)", carpeta=str(carpeta), guardados=str(carpeta / "guardados"),
                   dm_sin_espera=True, id_="prueba")


def abrir(carpeta: Path) -> None:
    pythonw = Path(sys.executable).with_name("pythonw.exe")
    ejecutable = pythonw if pythonw.exists() else Path(sys.executable)
    banderas = getattr(subprocess, "DETACHED_PROCESS", 0) | getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
    subprocess.Popen([str(ejecutable), str(RAIZ / "app.py")], env=entorno(carpeta), cwd=RAIZ, creationflags=banderas)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Partida imaginaria para probar las parejas")
    parser.add_argument("--reiniciar", action="store_true", help="borra la de prueba y la arma de nuevo")
    parser.add_argument("--reputacion", type=int, default=70)
    parser.add_argument("--seguidores", type=int, default=400_000)
    parser.add_argument("--personalidad", default="carismatico",
                        choices=("reservado", "carismatico", "polemico", "humilde"))
    parser.add_argument("--sin-abrir", action="store_true", help="solo la arma")
    parser.add_argument("--carpeta", type=Path, default=CARPETA, help=argparse.SUPPRESS)  # (las pruebas)
    argumentos = parser.parse_args(argv)
    carpeta = argumentos.carpeta.resolve()
    if carpeta.resolve() == RAIZ.resolve():
        raise SystemExit("La carpeta de prueba no puede ser la del proyecto (ahi esta tu base real).")
    if argumentos.reiniciar and carpeta.exists():
        shutil.rmtree(carpeta)
    if not (carpeta / "career_roleplay.db").exists():
        carpeta.mkdir(parents=True, exist_ok=True)
        armar(carpeta, argumentos.reputacion, argumentos.seguidores, argumentos.personalidad)
        seguidores = f"{argumentos.seguidores:,}".replace(",", ".")
        print(f"Partida de prueba armada en {carpeta} ({NOMBRE}, soltero, reputacion {argumentos.reputacion}, "
              f"{seguidores} seguidores)")
    if not argumentos.sin_abrir:
        abrir(carpeta)
        print("Abriendo la app con la partida de prueba. Anda a Vida > Explorar Instagram VIP.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
