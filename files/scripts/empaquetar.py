"""
Arma el paquete para los amigos: una carpeta con "EAFC Roleplay.exe" que
no necesita Python instalado, y un .zip listo para compartir.

    .venv\\Scripts\\python.exe -m pip install -r requirements-dev.txt   (una vez)
    .venv\\Scripts\\python.exe scripts\\empaquetar.py

Sale en dist\\:
    dist\\EAFC Roleplay\\                 la carpeta (para probar)
    dist\\EAFC Roleplay (amigos).zip     lo que se comparte

Lo que NO va en el paquete: tu career_roleplay.db, tus ajustes ni las fotos
de tu garage, ni tus claves de IA (la IA es opcional: cada amigo pone la suya
si quiere). Cada amigo la abre y listo, y sus datos quedan en su
%APPDATA%\\EAFC26 Roleplay (ver roleplay/config.py). Lo que SI va:
roleplay/datos (los textos del motor narrativo, las bases de nombres, el
catalogo de EA y los datos del ecosistema con las fotos de los autos).
"""

import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
NOMBRE = "EAFC Roleplay"
DIST = RAIZ / "dist"
TRABAJO = RAIZ / "build"
ZIP = DIST / f"{NOMBRE} (amigos).zip"
ICONOS = RAIZ / "roleplay" / "ui" / "iconos"
DATOS = RAIZ / "roleplay" / "datos"  # corpus del motor narrativo y bases de nombres (servicios/narrador.py)
NO_VA = (".env", "career_roleplay.db", "ajustes.json", "errores.log", "carreras.json")
# El navegador del configurador (QtWebEngine) trae ~125 MB que no se usan:
# los recursos de depuracion, las herramientas de desarrollador y los
# idiomas de Chromium (quedan ingles y espanol). Probado: sin esto la web
# oficial carga igual.
IDIOMAS_CHROMIUM = {"en-US.pak", "es.pak", "es-419.pak"}


def construir() -> Path:
    if not (ICONOS / "app.ico").exists():
        raise SystemExit("Falta app.ico: corre antes scripts\\crear_acceso_directo.py --sin-escritorio")
    comando = [
        sys.executable, "-m", "PyInstaller",
        "--noconfirm", "--clean", "--windowed",
        "--name", NOMBRE,
        "--icon", str(ICONOS / "app.ico"),
        "--add-data", f"{ICONOS}{';'}roleplay/ui/iconos",
        "--add-data", f"{DATOS}{';'}roleplay/datos",
        # dxcam carga sus procesadores con import_module: el analisis no los ve
        "--collect-submodules", "dxcam",
        # el mando del overlay: SDL2.dll viene adentro de sdl2dll (ui/mando.py)
        "--collect-all", "sdl2dll",
        # Whisper local (servicios/transcriptor.py) NO va: ~150 MB de librerias; los amigos usan el de Groq
        "--exclude-module", "faster_whisper", "--exclude-module", "ctranslate2",
        "--exclude-module", "onnxruntime", "--exclude-module", "av",
        "--exclude-module", "cv2",
        "--exclude-module", "tkinter",
        "--distpath", str(DIST),
        "--workpath", str(TRABAJO),
        "--specpath", str(TRABAJO),
        str(RAIZ / "app.py"),
    ]
    subprocess.run(comando, check=True, cwd=RAIZ)
    carpeta = DIST / NOMBRE
    shutil.copy(RAIZ / "scripts" / "LEEME_AMIGOS.txt", carpeta / "LEEME.txt")
    shutil.copy(RAIZ / "scripts" / "COMO_PONER_LA_IA.txt", carpeta / "COMO PONER LA IA.txt")

    podar_chromium(carpeta)
    # el configurador oficial (opciones y renders de las marcas) es solo para tu PC: no va a los amigos
    internos = carpeta / "_internal" / "roleplay" / "datos"
    (internos / "configuradores_oficiales.json").unlink(missing_ok=True)
    shutil.rmtree(internos / "img_configurador", ignore_errors=True)
    colados = [ruta for ruta in carpeta.rglob("*") if ruta.name in NO_VA]
    if colados:
        raise SystemExit(f"Se colaron datos personales en el paquete: {colados}")
    if not (DATOS / "catalogo_ea.json").exists():  # sin el, casi nadie tendria nombre en la prensa
        raise SystemExit("Falta roleplay/datos/catalogo_ea.json: corre scripts/nombres_faltantes.py --catalogo-ea")
    faltan = [r.name for r in DATOS.glob("*.json") if r.name != "configuradores_oficiales.json" and not (carpeta / "_internal" / "roleplay" / "datos" / r.name).exists()]
    if faltan:  # sin los corpus, la app no tendria que decir
        raise SystemExit(f"Faltan los datos del motor narrativo en el paquete: {faltan}")
    if (DATOS / "img_autos").exists() and not any((carpeta / "_internal" / "roleplay" / "datos" / "img_autos").glob("*")):
        raise SystemExit("Faltan las fotos de los autos (roleplay/datos/img_autos) en el paquete")
    if not list(carpeta.rglob("qtbase_es.qm")):  # los botones de los pop-ups en espanol (ui/estilos.py)
        print("OJO: no va la traduccion qtbase_es.qm: los botones de los pop-ups saldrian en ingles")
    return carpeta


def podar_chromium(carpeta: Path) -> None:
    pyside = carpeta / "_internal" / "PySide6"
    sobran = [r for r in (pyside / "resources").glob("*") if ".debug." in r.name or r.name.startswith("qtwebengine_devtools")]
    sobran += [r for r in (pyside / "translations" / "qtwebengine_locales").glob("*.pak") if r.name not in IDIOMAS_CHROMIUM]
    for ruta in sobran:
        ruta.unlink()


def comprimir(carpeta: Path) -> None:
    ZIP.unlink(missing_ok=True)
    with zipfile.ZipFile(ZIP, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as archivo:
        for ruta in sorted(carpeta.rglob("*")):
            if ruta.is_file():
                archivo.write(ruta, Path(NOMBRE) / ruta.relative_to(carpeta))


def main() -> None:
    carpeta = construir()
    comprimir(carpeta)
    tamano = sum(ruta.stat().st_size for ruta in carpeta.rglob("*") if ruta.is_file())
    print(f"\nCarpeta: {carpeta}  ({tamano / 2**20:.0f} MB)")
    print(f"Zip:     {ZIP}  ({ZIP.stat().st_size / 2**20:.0f} MB)")


if __name__ == "__main__":
    main()
