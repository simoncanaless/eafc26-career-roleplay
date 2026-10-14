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

    colados = [ruta for ruta in carpeta.rglob("*") if ruta.name in NO_VA]
    if colados:
        raise SystemExit(f"Se colaron datos personales en el paquete: {colados}")
    return carpeta


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
