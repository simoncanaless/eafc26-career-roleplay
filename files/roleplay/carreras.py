"""
Perfiles de carrera: tener mas de una carrera en la app (la principal, la de
prueba de scripts/partida_de_prueba.py, o un segundo modo carrera de FC 26) y
cambiar entre ellas sin mezclarlas.

Cada carrera es una carpeta de datos propia (su base, sus ajustes -con la
partida de FC 26 que lee-, sus fotos y su navegador). La principal es la
carpeta de siempre (la del proyecto, o %APPDATA%\\EAFC26 Roleplay
empaquetada); las demas viven en <principal>/carreras/<id>/. La lista y cual
esta activa van en <principal>/carreras.json.

Como roleplay.config fija la carpeta de datos al importarse, app.py llama a
`preparar_entorno()` ANTES de importar nada mas: si la activa no es la
principal, pone EAFC_ROLEPLAY_DATOS (y EAFC_FC26_GUARDADOS / EAFC_DM_SIN_ESPERA
si la carrera los trae, como la de prueba). Cambiar de carrera = activarla y
reiniciar la app. Si EAFC_ROLEPLAY_DATOS ya viene en el entorno (las pruebas,
el script de prueba), no se toca nada.

Este modulo NO importa roleplay.config (justamente se usa antes).
"""

import json
import os
import re
import sys
from pathlib import Path
from typing import Optional

PRINCIPAL = "principal"
ARCHIVO = "carreras.json"


def carpeta_principal() -> Path:
    """La carpeta de datos de siempre (la misma regla que config.carpeta_datos, sin el override)."""
    if os.environ.get("EAFC_ROLEPLAY_BASE"):
        return Path(os.environ["EAFC_ROLEPLAY_BASE"])
    if getattr(sys, "frozen", False):
        return Path(os.environ.get("APPDATA") or Path.home()) / "EAFC26 Roleplay"
    return Path(__file__).resolve().parent.parent


def _leer() -> dict:
    try:
        datos = json.loads((carpeta_principal() / ARCHIVO).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return datos if isinstance(datos, dict) else {}


def _guardar(datos: dict) -> None:
    carpeta_principal().mkdir(parents=True, exist_ok=True)
    (carpeta_principal() / ARCHIVO).write_text(json.dumps(datos, ensure_ascii=False, indent=2), encoding="utf-8")


def listar() -> list[dict]:
    """Todas, la principal primero: {"id", "nombre", "carpeta", ("guardados", "dm_sin_espera")}."""
    principal = {"id": PRINCIPAL, "nombre": "Carrera principal", "carpeta": str(carpeta_principal())}
    otras = [c for c in _leer().get("carreras", []) if isinstance(c, dict) and c.get("id") and c.get("carpeta")]
    return [principal] + [c for c in otras if c["id"] != PRINCIPAL]


def activa_id() -> str:
    activa = _leer().get("activa", PRINCIPAL)
    return activa if any(c["id"] == activa for c in listar()) else PRINCIPAL


def activa() -> dict:
    return next(c for c in listar() if c["id"] == activa_id())


def _id_para(nombre: str) -> str:
    base = re.sub(r"[^a-z0-9]+", "_", nombre.lower()).strip("_") or "carrera"
    usados = {c["id"] for c in listar()}
    candidato, n = base, 2
    while candidato in usados:
        candidato, n = f"{base}_{n}", n + 1
    return candidato


def crear(nombre: str, partida: str = "", carpeta: Optional[str] = None, guardados: str = "",
          dm_sin_espera: bool = False, id_: Optional[str] = None) -> dict:
    """Agrega una carrera (o actualiza la del mismo id). `partida`: el guardado CmPlr* de FC 26 que
    lee (vacio: el mas reciente). Le copia a la nueva las claves de IA de la principal."""
    nombre = nombre.strip() or "Otra carrera"
    datos = _leer()
    carreras = [c for c in datos.get("carreras", []) if isinstance(c, dict)]
    id_ = id_ or _id_para(nombre)
    carpeta = Path(carpeta) if carpeta else carpeta_principal() / "carreras" / id_
    carpeta.mkdir(parents=True, exist_ok=True)
    ajustes_nuevos = carpeta / "ajustes.json"
    if not ajustes_nuevos.exists():
        try:
            principales = json.loads((carpeta_principal() / "ajustes.json").read_text(encoding="utf-8"))
        except (OSError, ValueError):
            principales = {}
        iniciales = {k: principales[k] for k in ("groq_api_key", "gemini_api_key", "sin_ia") if principales.get(k)}
        if partida:
            iniciales["partida"] = partida
        ajustes_nuevos.write_text(json.dumps(iniciales, ensure_ascii=False, indent=2), encoding="utf-8")
    carrera = {"id": id_, "nombre": nombre, "carpeta": str(carpeta)}
    if guardados:
        carrera["guardados"] = str(guardados)
    if dm_sin_espera:
        carrera["dm_sin_espera"] = True
    datos["carreras"] = [c for c in carreras if c.get("id") != id_] + [carrera]
    _guardar(datos)
    return carrera


def activar(id_: str) -> dict:
    if not any(c["id"] == id_ for c in listar()):
        raise ValueError(f"No existe la carrera {id_}")
    datos = _leer()
    datos["activa"] = id_
    _guardar(datos)
    return activa()


def entorno_de(carrera: dict) -> dict:
    """Las variables de entorno que hacen que la app use esa carrera."""
    if carrera["id"] == PRINCIPAL:
        return {}
    entorno = {"EAFC_ROLEPLAY_DATOS": carrera["carpeta"]}
    if carrera.get("guardados"):
        entorno["EAFC_FC26_GUARDADOS"] = carrera["guardados"]
    if carrera.get("dm_sin_espera"):
        entorno["EAFC_DM_SIN_ESPERA"] = "1"
    return entorno


def actual() -> dict:
    """La carrera que usa este proceso (por su carpeta de datos)."""
    carpeta = os.environ.get("EAFC_ROLEPLAY_DATOS")
    if not carpeta:
        return listar()[0]
    destino = Path(carpeta).resolve()
    return next((c for c in listar() if Path(c["carpeta"]).resolve() == destino),
                {"id": "externa", "nombre": f"Carrera en {destino.name}", "carpeta": carpeta})


VARIABLES = ("EAFC_ROLEPLAY_DATOS", "EAFC_FC26_GUARDADOS", "EAFC_DM_SIN_ESPERA")


def entorno_para_reiniciar() -> dict:
    """El entorno sin las variables de la carrera: al reiniciar, manda carreras.json."""
    return {k: v for k, v in os.environ.items() if k not in VARIABLES}


def preparar_entorno() -> dict:
    """Lo llama app.py antes de importar roleplay.config. Devuelve la carrera activa."""
    if os.environ.get("EAFC_ROLEPLAY_DATOS"):
        return {"id": "externa", "nombre": "Carrera (carpeta elegida a mano)", "carpeta": os.environ["EAFC_ROLEPLAY_DATOS"]}
    carrera = activa()
    os.environ.update(entorno_de(carrera))
    return carrera
