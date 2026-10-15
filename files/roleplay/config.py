"""
Rutas compartidas.

- Codigo y recursos (iconos) salen de la carpeta del programa.
- Los datos de cada persona (su carrera, su clave de Gemini, sus ajustes,
  el registro de errores) van en CARPETA_DATOS:
    * corriendo desde el codigo (el PC de Simon): la raiz del proyecto,
      como siempre;
    * empaquetada para los amigos (PyInstaller): %APPDATA%\\EAFC26 Roleplay,
      porque la carpeta del programa puede no tener permiso de escritura y
      porque cada uno tiene su propia carrera y su propia clave;
    * EAFC_ROLEPLAY_DATOS en el entorno manda sobre las dos (pruebas).
"""

import os
import sys
from pathlib import Path

EMPAQUETADA = bool(getattr(sys, "frozen", False))
RAIZ_PROYECTO = Path(__file__).resolve().parent.parent
NOMBRE_CARPETA_DATOS = "EAFC26 Roleplay"


def carpeta_datos(entorno=os.environ, empaquetada: bool = EMPAQUETADA) -> Path:
    if entorno.get("EAFC_ROLEPLAY_DATOS"):
        return Path(entorno["EAFC_ROLEPLAY_DATOS"])
    if empaquetada:
        return Path(entorno.get("APPDATA") or Path.home()) / NOMBRE_CARPETA_DATOS
    return RAIZ_PROYECTO


CARPETA_DATOS = carpeta_datos()
CARPETA_DATOS.mkdir(parents=True, exist_ok=True)

DB_PATH = CARPETA_DATOS / "career_roleplay.db"
ARCHIVO_ENV = CARPETA_DATOS / ".env"
ARCHIVO_AJUSTES = CARPETA_DATOS / "ajustes.json"
REGISTRO_ERRORES = CARPETA_DATOS / "errores.log"
CARPETA_GARAGE = CARPETA_DATOS / "garage"  # las fotos de los autos pedidos (ui/configurador.py)
ICONO_APP = RAIZ_PROYECTO / "roleplay" / "ui" / "iconos" / "app.ico"
