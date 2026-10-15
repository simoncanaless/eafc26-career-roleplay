"""
Arma el paquete para los amigos: una carpeta con "EAFC Roleplay.exe" que
no necesita Python instalado, y un .zip listo para compartir.

    .venv\\Scripts\\python.exe -m pip install -r requirements-dev.txt   (una vez)
    .venv\\Scripts\\python.exe scripts\\empaquetar.py

Sale en dist\\:
    dist\\EAFC Roleplay\\                 la carpeta (para probar)
    dist\\EAFC Roleplay (amigos).zip     lo que se comparte

Lo que NO va en el paquete: tu .env (tu clave), tu career_roleplay.db ni
tus ajustes. Cada amigo pone su clave al abrirlo y sus datos quedan en su
%APPDATA%\\EAFC26 Roleplay (ver roleplay/config.py).
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
NO_VA = (".env", "career_roleplay.db", "ajustes.json", "errores.log")
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
        # dxcam carga sus procesadores con import_module: el analisis no los ve
        "--collect-submodules", "dxcam",
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

    podar_chromium(carpeta)
    colados = [ruta for ruta in carpeta.rglob("*") if ruta.name in NO_VA]
    if colados:
        raise SystemExit(f"Se colaron datos personales en el paquete: {colados}")
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
