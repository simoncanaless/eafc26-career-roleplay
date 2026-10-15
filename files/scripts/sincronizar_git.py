"""
Sube los cambios a GitHub en un paso: git add -A, revisa que no se cuele nada
privado (claves, la base con tu carrera, respaldos, el paquete), commit y push
a origin main.

    .venv\\Scripts\\python.exe scripts\\sincronizar_git.py "Que cambio"

Si encuentra algo privado en lo que se iba a subir, lo saca del commit (git
reset) y no sube nada: hay que agregarlo al .gitignore. Sin cambios nuevos,
igual hace push (por si quedaron commits sin subir).
"""

import re
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]  # Proyecto Fifa (el repo), no files/
PROHIBIDO = re.compile(
    r"(^|/)(\.env(\.[^/]*)?|ajustes\.json|errores\.log|diagnostico\.txt)$"
    r"|\.(db|db-journal|zip|exe|pyc|pyo)$"
    r"|(^|/)(\.venv|build|dist|navegador|garage|compras|__pycache__)/"
)
CLAVE = re.compile(r"AIza[0-9A-Za-z_\-]{30,}|gsk_[0-9A-Za-z]{20,}|(GEMINI|GROQ)_API_KEYS?\s*=\s*['\"]?[A-Za-z0-9_\-]{12,}")


def git(*argumentos: str) -> subprocess.CompletedProcess:
    return subprocess.run(["git", *argumentos], cwd=REPO, capture_output=True, text=True, encoding="utf-8")


def problemas_en_lo_preparado() -> list[str]:
    """Lo privado que esta por entrar al commit (nombres prohibidos o claves)."""
    archivos = [a for a in git("diff", "--cached", "--name-only", "-z").stdout.split("\0") if a]
    problemas = [f"archivo privado: {a}" for a in archivos if PROHIBIDO.search(a)]
    agregado = [linea[1:] for linea in git("diff", "--cached", "-U0").stdout.splitlines()
                if linea.startswith("+") and not linea.startswith("+++")]
    problemas += [f"parece una clave: {linea.strip()[:60]}..." for linea in agregado if CLAVE.search(linea)]
    return problemas


def main(argumentos: list[str]) -> int:
    mensaje = " ".join(argumentos).strip()
    if not mensaje:
        print('Uso: sincronizar_git.py "Que cambio"')
        return 2
    git("add", "-A")
    problemas = problemas_en_lo_preparado()
    if problemas:
        git("reset")
        print("NO se subio nada. Esto es privado (agregalo al .gitignore):")
        print("\n".join(f"  - {p}" for p in problemas))
        return 1
    if git("diff", "--cached", "--quiet").returncode != 0:
        commit = git("commit", "-m", mensaje)
        if commit.returncode != 0:
            print(commit.stdout + commit.stderr)
            return 1
        print(commit.stdout.splitlines()[0] if commit.stdout else "commit hecho")
    else:
        print("Sin cambios nuevos: solo push.")
    if not git("remote", "get-url", "origin").stdout.strip():
        print("Falta el repositorio remoto: git remote add origin <URL del repo en GitHub>")
        return 1
    push = git("push", "origin", "main")
    print((push.stdout + push.stderr).strip())
    return push.returncode


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
