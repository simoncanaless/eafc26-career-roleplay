"""
El ecosistema que arma Simon con sus propios scripts, en roleplay/datos/:
- famosas_ig.json ("celebridades": nombre, usuario_ig, oficio, categoria,
  anio_nacimiento, exigencia),
- ecosistema_ig.json ("paginas_futbol", "periodistas", "futbolistas_ig"),
- autos_marketplace.json ("autos_nicho", con fotos en img_autos/).

Los datos son de Simon y quedan bajo su responsabilidad (lo decidio el
2026-10-19): la app solo los LEE, nunca los escribe ni los modifica. No van
al repo publico (.gitignore); si van en el paquete de los amigos. Sin los
archivos, todo lo que los usa sigue andando sin ellos (listas vacias).
EAFC_ECOSISTEMA cambia la carpeta (las pruebas la apuntan a una vacia).

Ademas, dos medidas que usan la hinchada, el amor, los patrocinios, la prensa
y los comentarios de colegas:
- el tier mediatico del club (1 gigante, 2 competitivo, 3 chico): los gigantes
  y los competitivos de siempre por nombre (TIER_1 / TIER_2: un Man United es
  tier 1 aunque ande mal); el resto por la media de su plantel en la partida,
  como mucho tier 2;
- el Player Power Index (fama del jugador, 0-100): reputacion + la base del
  tier (35 / 20 / 8) + goles y asistencias de la temporada + premios y titulos.
"""

import json
import os
import unicodedata
from collections import defaultdict
from functools import lru_cache
from pathlib import Path
from typing import Optional

from roleplay.servicios.narrador import CARPETA_DATOS

# tier mediatico por nombre (normalizado: minusculas y sin tildes); los nombres de la
# partida de FC 26 incluidos (Man Utd, Paris SG, Milano FC = el Milan sin licencia)
TIER_1 = {"real madrid", "man utd", "manchester united", "fc barcelona", "barcelona", "manchester city", "man city",
          "fc bayern munchen", "bayern munchen", "bayern", "paris sg", "paris saint-germain", "psg", "liverpool",
          "arsenal", "chelsea", "juventus"}
TIER_2 = {"psv", "psv eindhoven", "sl benfica", "benfica", "borussia dortmund", "dortmund", "ac milan", "milan",
          "milano fc", "atletico de madrid", "atletico madrid", "inter", "lombardia fc", "ssc napoli", "napoli",
          "fc porto", "porto", "ajax", "spurs", "tottenham", "newcastle utd", "sporting cp", "as roma", "roma",
          "rb leipzig", "leverkusen", "aston villa", "olympique de marseille", "om", "galatasaray", "fenerbahce",
          "boca juniors", "river plate", "flamengo", "palmeiras", "al nassr", "al hilal", "inter miami"}
# el resto: por la media de los 16 mejores del plantel (calibrado con la partida de Simon, 2026-10-20)
TIER_2_DESDE = 74.0
JUGADORES_DEL_PLANTEL = 16
BASE_FAMA = {1: 35, 2: 20, 3: 8}


def carpeta() -> Path:
    return Path(os.environ.get("EAFC_ECOSISTEMA") or CARPETA_DATOS)


@lru_cache(maxsize=16)
def _leer(ruta: str) -> dict:
    try:
        datos = json.loads(Path(ruta).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return datos if isinstance(datos, dict) else {}


def _lista(archivo: str, clave: str) -> list[dict]:
    return [x for x in _leer(str(carpeta() / archivo)).get(clave, []) if isinstance(x, dict) and x.get("nombre", x.get("modelo"))]


def celebridades() -> list[dict]:
    return _lista("famosas_ig.json", "celebridades")


def paginas_futbol() -> list[dict]:
    return _lista("ecosistema_ig.json", "paginas_futbol")


def periodistas() -> list[dict]:
    return _lista("ecosistema_ig.json", "periodistas")


def futbolistas_ig() -> list[dict]:
    return _lista("ecosistema_ig.json", "futbolistas_ig")


def autos_nicho() -> list[dict]:
    return _lista("autos_marketplace.json", "autos_nicho")


def imagen_auto(auto: dict) -> Optional[Path]:
    """La foto local del auto (img_autos/ al lado de los datos), si esta."""
    nombre = Path(str(auto.get("imagen_local") or "")).name
    if not nombre:
        return None
    ruta = carpeta() / "img_autos" / nombre
    return ruta if ruta.exists() else None


def numero(valor, defecto: int = 0) -> int:
    try:
        return int(valor)
    except (TypeError, ValueError):
        return defecto


# ---- el tier del club ----


def medias_de_plantel(carrera) -> dict[int, float]:
    """equipo -> promedio de sus 16 mejores jugadores (hombres): que tan bueno es cada club."""
    _tiers(carrera)
    return carrera.memo["medias_de_plantel"]


def _tiers(carrera) -> dict[int, int]:
    if "tiers" not in carrera.memo:
        medias = defaultdict(list)
        for jugador, vinculos in carrera.vinculos.items():
            media = carrera.medias.get(jugador)
            if media is None or jugador in carrera.mujeres:
                continue
            for equipo, _ in vinculos:
                es_club = equipo in carrera.clubes or (
                    equipo in carrera.ligas_de_equipo and not carrera.es_seleccion(equipo))
                if es_club:
                    medias[equipo].append(media)
        tiers, promedios = {}, {}
        for equipo, lista in medias.items():
            mejores = sorted(lista, reverse=True)[:JUGADORES_DEL_PLANTEL]
            promedio = sum(mejores) / len(mejores)
            promedios[equipo] = promedio
            tiers[equipo] = tier_por_nombre(carrera.equipo(equipo)) or (2 if promedio >= TIER_2_DESDE else 3)
        carrera.memo["tiers"] = tiers
        carrera.memo["medias_de_plantel"] = promedios
    return carrera.memo["tiers"]


def normalizar(nombre: str) -> str:
    sin_tildes = unicodedata.normalize("NFKD", str(nombre or "")).encode("ascii", "ignore").decode()
    return " ".join(sin_tildes.lower().split())


def tier_por_nombre(nombre: str) -> Optional[int]:
    clave = normalizar(nombre)
    return 1 if clave in TIER_1 else 2 if clave in TIER_2 else None


def tier_club(carrera, club: Optional[int]) -> int:
    """1 gigante, 2 competitivo, 3 chico (2 si no se sabe)."""
    if carrera is None or club is None:
        return 2
    return _tiers(carrera).get(club) or tier_por_nombre(carrera.equipo(club)) or 2


def club_del_usuario(carrera) -> Optional[int]:
    if carrera is None or carrera.usuario_id is None:
        return None
    return carrera.club_de(carrera.usuario_id) or carrera.equipo_usuario()


def goles_de_la_temporada(carrera) -> int:
    if carrera is None or carrera.usuario_id is None:
        return 0
    return sum(e.goles for e in carrera.estadisticas_de(carrera.usuario_id))


def asistencias_de_la_temporada(carrera) -> int:
    if carrera is None or carrera.usuario_id is None:
        return 0
    return sum(e.asistencias for e in carrera.estadisticas_de(carrera.usuario_id))


# ---- la fama del jugador ----


def fama_jugador(reputacion: int, tier: int, goles_temporada: int = 0, premios: int = 0, asistencias: int = 0) -> int:
    """Player Power Index (0-100). Un tier 1 da una base enorme (35); un club chico, casi nada (8)."""
    valor = (reputacion * 0.45 + BASE_FAMA.get(tier, BASE_FAMA[2]) + min(12, goles_temporada * 0.3)
             + min(5, asistencias * 0.2) + min(10, premios * 3))
    return max(0, min(100, round(valor)))


def premios_del_jugador(player_id: Optional[int]) -> int:
    if not player_id:
        return 0
    from roleplay import database

    return len(database.get_estado_prensa(player_id).get("vitrina", []))


def calcular_fama_jugador(perfil, carrera=None, leer_partida: bool = True) -> dict:
    """{"fama", "tier", "goles", "asistencias", "premios"} del jugador (`perfil`:
    el PlayerProfile o su id). Sin `carrera`, lee la partida (lento: llamarla
    desde un hilo) salvo leer_partida=False. Premios: la vitrina (titulos y
    premios individuales)."""
    from roleplay import database

    player_id = getattr(perfil, "id", perfil)
    if carrera is None and leer_partida:
        try:
            from roleplay.partida.lector import carrera_actual

            carrera = carrera_actual()
        except Exception:  # noqa: BLE001  (sin partida, fama sin club ni goles)
            carrera = None
    reputacion = database.get_reputacion_actual(player_id) if player_id else 50
    tier = tier_club(carrera, club_del_usuario(carrera))
    goles = goles_de_la_temporada(carrera)
    asistencias = asistencias_de_la_temporada(carrera)
    premios = premios_del_jugador(player_id)
    return {"fama": fama_jugador(reputacion, tier, goles, premios, asistencias), "tier": tier, "goles": goles,
            "asistencias": asistencias, "premios": premios}
