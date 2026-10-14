"""Rutas compartidas. Todas salen de la raiz del proyecto, no del
directorio desde donde se corre la app, para que funcione igual con
`python app.py` que con un acceso directo o desde otra carpeta."""

from pathlib import Path

RAIZ_PROYECTO = Path(__file__).resolve().parent.parent
DB_PATH = RAIZ_PROYECTO / "career_roleplay.db"
ARCHIVO_ENV = RAIZ_PROYECTO / ".env"
