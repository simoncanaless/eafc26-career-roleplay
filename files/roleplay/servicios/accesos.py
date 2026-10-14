"""
Los dos iconos del escritorio:

- "EA FC 26"             abre el juego normal, por su plataforma. Nada mas.
- "EA FC 26 + Roleplay"  abre el juego igual que el otro y ademas la app
                         (en la sala de prensa).

El juego es el mismo en los dos: el roleplay corre aparte, al lado.
Los .lnk se crean con el WScript.Shell de Windows (via PowerShell), para
no depender de pywin32.
"""

import subprocess
import sys
from pathlib import Path
from typing import Optional

from roleplay import config
from roleplay.servicios.juego import Juego

NOMBRE_JUEGO_NORMAL = "EA FC 26"
NOMBRE_JUEGO_ROLEPLAY = "EA FC 26 + Roleplay"
ARGUMENTO_JUGAR = "--jugar"
# El acceso de una version anterior, que abria solo la app
ACCESOS_VIEJOS = ("EAFC 26 Roleplay.lnk",)


def escritorio() -> Path:
    """La carpeta Escritorio real (puede estar en OneDrive)."""
    resultado = subprocess.run(
        ["powershell", "-NoProfile", "-NonInteractive", "-Command", "[Environment]::GetFolderPath('Desktop')"],
        capture_output=True,
        text=True,
    )
    ruta = resultado.stdout.strip()
    return Path(ruta) if ruta else Path.home() / "Desktop"


def lanzador_de_la_app() -> tuple[str, str]:
    """(ejecutable, argumentos) que abren la app, segun como este instalada."""
    if config.EMPAQUETADA:
        return sys.executable, ""  # el paquete es el propio .exe
    exe = config.RAIZ_PROYECTO / "EAFC Roleplay.exe"
    if exe.exists():
        return str(exe), ""
    pythonw = config.RAIZ_PROYECTO / ".venv" / "Scripts" / "pythonw.exe"
    return str(pythonw), f'"{config.RAIZ_PROYECTO / "app.py"}"'


def _comillas_ps(texto: str) -> str:
    return "'" + str(texto).replace("'", "''") + "'"


def crear_lnk(ruta: Path, destino: str, argumentos: str = "", carpeta: str = "", icono: str = "", descripcion: str = "") -> None:
    script = (
        f"$a = (New-Object -ComObject WScript.Shell).CreateShortcut({_comillas_ps(ruta)}); "
        f"$a.TargetPath = {_comillas_ps(destino)}; "
        f"$a.Arguments = {_comillas_ps(argumentos)}; "
        f"$a.WorkingDirectory = {_comillas_ps(carpeta)}; "
        + (f"$a.IconLocation = {_comillas_ps(icono + ',0')}; " if icono else "")
        + f"$a.Description = {_comillas_ps(descripcion)}; "
        "$a.Save()"
    )
    resultado = subprocess.run(
        ["powershell", "-NoProfile", "-NonInteractive", "-Command", script],
        capture_output=True,
        text=True,
    )
    if resultado.returncode != 0 or not ruta.exists():
        raise RuntimeError(f"No se pudo crear el acceso directo {ruta.name}: {resultado.stderr.strip()}")


def crear_url(ruta: Path, url: str, icono: str = "") -> None:
    """Acceso a una URL (steam://...), como los que crea el propio Steam."""
    lineas = ["[InternetShortcut]", f"URL={url}"]
    if icono:
        lineas += [f"IconFile={icono}", "IconIndex=0"]
    # newline: Windows quiere CRLF; escribir "\r\n" en modo texto lo duplica
    ruta.write_text("\n".join(lineas) + "\n", encoding="utf-8", newline="\r\n")


def crear_accesos(juego: Optional[Juego], carpeta: Optional[Path] = None) -> list[Path]:
    """Crea (o reemplaza) los dos iconos en `carpeta` (el escritorio si no
    se dice). Sin juego detectado se crea solo el de roleplay: al abrirlo,
    la app pide elegir el juego."""
    carpeta = carpeta or escritorio()
    creados = []

    if juego is not None:
        if juego.es_url:
            normal = carpeta / f"{NOMBRE_JUEGO_NORMAL}.url"
            crear_url(normal, juego.comando, juego.icono)
        else:
            normal = carpeta / f"{NOMBRE_JUEGO_NORMAL}.lnk"
            crear_lnk(normal, juego.comando, carpeta=str(Path(juego.comando).parent), icono=juego.icono, descripcion=juego.nombre)
        creados.append(normal)

    ejecutable, argumentos = lanzador_de_la_app()
    roleplay = carpeta / f"{NOMBRE_JUEGO_ROLEPLAY}.lnk"
    icono_app = ejecutable if config.EMPAQUETADA else str(config.ICONO_APP)
    crear_lnk(
        roleplay,
        ejecutable,
        f"{argumentos} {ARGUMENTO_JUGAR}".strip(),
        carpeta=str(Path(ejecutable).parent),
        icono=icono_app,
        descripcion="Abre EA FC 26 y el roleplay de la carrera",
    )
    creados.append(roleplay)

    for viejo in ACCESOS_VIEJOS:
        (carpeta / viejo).unlink(missing_ok=True)
    return creados
