"""
Encontrar EA FC 26 en el PC y abrirlo.

El juego se abre SIEMPRE por su plataforma (Steam, EA app o Epic), igual
que con su propio icono: la app nunca toca los archivos ni la memoria del
juego. Por eso no lo puede romper, una actualizacion del juego no la
rompe a ella, y el anticheat no tiene nada que ver.

Orden: lo que la persona eligio a mano (ajustes.json) > Steam > EA app > Epic.
"""

import os
import re
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Callable, Optional

from roleplay import ajustes

STEAM_APPID_FC26 = "3405690"
NOMBRE_JUEGO = re.compile(r"FC\W*26", re.IGNORECASE)
EPIC_MANIFIESTOS = Path(os.environ.get("PROGRAMDATA", r"C:\ProgramData")) / "Epic" / "EpicGamesLauncher" / "Data" / "Manifests"

# leer_registro(raiz, ruta, valor) -> str | None ; raiz: "HKCU" o "HKLM"
LectorRegistro = Callable[[str, str, str], Optional[str]]
# subclaves(raiz, ruta) -> lista de nombres de subclaves
ListadorRegistro = Callable[[str, str], list]


@dataclass(frozen=True)
class Juego:
    plataforma: str  # "steam" | "ea" | "epic" | "manual"
    comando: str  # URL (steam://...) o ruta de un .exe/.lnk/.url
    icono: str = ""  # el .exe del juego, para el icono del acceso directo
    nombre: str = "EA SPORTS FC 26"

    @property
    def es_url(self) -> bool:
        return "://" in self.comando

    def describir(self) -> str:
        donde = {"steam": "Steam", "ea": "EA app", "epic": "Epic Games", "manual": "elegido a mano"}
        return f"{self.nombre} ({donde.get(self.plataforma, self.plataforma)})"


# ---- registro de Windows (inyectable para las pruebas) ----


def _leer_registro(raiz: str, ruta: str, valor: str) -> Optional[str]:
    try:
        import winreg
    except ImportError:
        return None
    try:
        with winreg.OpenKey(getattr(winreg, f"HKEY_{'CURRENT_USER' if raiz == 'HKCU' else 'LOCAL_MACHINE'}"), ruta) as clave:
            return str(winreg.QueryValueEx(clave, valor)[0])
    except OSError:
        return None


def _subclaves(raiz: str, ruta: str) -> list:
    try:
        import winreg
    except ImportError:
        return []
    nombres = []
    try:
        with winreg.OpenKey(getattr(winreg, f"HKEY_{'CURRENT_USER' if raiz == 'HKCU' else 'LOCAL_MACHINE'}"), ruta) as clave:
            while True:
                try:
                    nombres.append(winreg.EnumKey(clave, len(nombres)))
                except OSError:
                    return nombres
    except OSError:
        return []


def _exe_del_juego(carpeta: Path) -> str:
    """El .exe principal (FC26.exe), para tomarle el icono."""
    if not carpeta.is_dir():
        return ""
    candidatos = sorted(carpeta.glob("FC*.exe")) or sorted(carpeta.glob("*.exe"))
    return str(candidatos[0]) if candidatos else ""


# ---- plataformas ----


def buscar_en_steam(leer: LectorRegistro = _leer_registro) -> Optional[Juego]:
    steam = leer("HKCU", r"Software\Valve\Steam", "SteamPath")
    if not steam:
        return None
    steam = Path(steam)
    bibliotecas = {steam}
    indice = steam / "steamapps" / "libraryfolders.vdf"
    if indice.exists():
        texto = indice.read_text(encoding="utf-8", errors="ignore")
        bibliotecas |= {Path(ruta.replace("\\\\", "\\")) for ruta in re.findall(r'"path"\s+"([^"]+)"', texto)}

    for biblioteca in bibliotecas:
        for manifiesto in (biblioteca / "steamapps").glob("appmanifest_*.acf"):
            texto = manifiesto.read_text(encoding="utf-8", errors="ignore")
            appid = re.search(r'"appid"\s+"(\d+)"', texto)
            nombre = re.search(r'"name"\s+"([^"]+)"', texto)
            carpeta = re.search(r'"installdir"\s+"([^"]+)"', texto)
            if not appid or not (appid.group(1) == STEAM_APPID_FC26 or (nombre and NOMBRE_JUEGO.search(nombre.group(1)))):
                continue
            exe = _exe_del_juego(biblioteca / "steamapps" / "common" / carpeta.group(1)) if carpeta else ""
            return Juego("steam", f"steam://rungameid/{appid.group(1)}", exe)
    return None


def buscar_en_ea(leer: LectorRegistro = _leer_registro, subclaves: ListadorRegistro = _subclaves) -> Optional[Juego]:
    for base in (r"SOFTWARE\EA Games", r"SOFTWARE\WOW6432Node\EA Games"):
        for nombre in subclaves("HKLM", base):
            if not NOMBRE_JUEGO.search(nombre):
                continue
            carpeta = leer("HKLM", f"{base}\\{nombre}", "Install Dir")
            exe = _exe_del_juego(Path(carpeta)) if carpeta else ""
            if exe:
                # abrir el .exe de un juego de la EA app lo abre a traves de la EA app
                return Juego("ea", exe, exe, nombre)
    return None


def buscar_en_epic(carpeta_manifiestos: Path = EPIC_MANIFIESTOS) -> Optional[Juego]:
    import json

    if not carpeta_manifiestos.is_dir():
        return None
    for item in carpeta_manifiestos.glob("*.item"):
        try:
            datos = json.loads(item.read_text(encoding="utf-8", errors="ignore"))
        except ValueError:
            continue
        if not NOMBRE_JUEGO.search(datos.get("DisplayName", "")):
            continue
        url = (
            "com.epicgames.launcher://apps/"
            f"{datos['CatalogNamespace']}%3A{datos['CatalogItemId']}%3A{datos['AppName']}"
            "?action=launch&silent=true"
        )
        exe = str(Path(datos.get("InstallLocation", "")) / datos.get("LaunchExecutable", ""))
        return Juego("epic", url, exe if Path(exe).is_file() else "", datos["DisplayName"])
    return None


def detectar_juego() -> Optional[Juego]:
    return buscar_en_steam() or buscar_en_ea() or buscar_en_epic()


# ---- lo que usa la app ----


def juego_configurado() -> Optional[Juego]:
    """El elegido a mano si lo hay; si no, el que se detecta."""
    guardado = ajustes.leer().get("juego")
    if guardado:
        try:
            return Juego(**guardado)
        except TypeError:
            pass  # ajustes de una version vieja: se vuelve a detectar
    return detectar_juego()


def elegir_a_mano(ruta: str) -> Juego:
    """La persona eligio el .exe del juego, o un acceso directo (.lnk/.url)."""
    camino = Path(ruta)
    if not camino.is_file():
        raise ValueError(f"No existe el archivo {ruta}")
    juego = Juego("manual", str(camino), str(camino) if camino.suffix.lower() == ".exe" else "", camino.stem)
    ajustes.guardar(juego=asdict(juego))
    return juego


def olvidar_eleccion() -> None:
    ajustes.guardar(juego=None)


def abrir_juego(juego: Juego) -> None:
    """Abre el juego como su propio icono: por la plataforma."""
    if not juego.es_url and not Path(juego.comando).exists():
        raise RuntimeError(
            f"No encontre {juego.comando}. Elegi de nuevo como abrir el juego en Ajustes."
        )
    os.startfile(juego.comando)  # noqa: S606 - es justo lo que se quiere
