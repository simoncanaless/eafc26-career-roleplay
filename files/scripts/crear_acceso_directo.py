"""
Crea lo necesario para abrir la app con doble click:

1. roleplay/ui/iconos/app.ico   el icono (una carta estilo FUT con "RP"),
                                dibujado con Qt en varios tamanos.
2. EAFC Roleplay.exe            lanzador chiquito (scripts/lanzador/Lanzador.cs)
                                compilado con el csc.exe que trae Windows.
3. Los dos iconos del escritorio: "EA FC 26" (el juego normal) y
   "EA FC 26 + Roleplay" (el juego igual + la app). Ver servicios/accesos.py.

    .venv\\Scripts\\python.exe scripts\\crear_acceso_directo.py
    .venv\\Scripts\\python.exe scripts\\crear_acceso_directo.py --sin-escritorio

Volver a correrlo es seguro: reemplaza los tres.
"""

import argparse
import os
import struct
import subprocess
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

ICONO = RAIZ / "roleplay" / "ui" / "iconos" / "app.ico"
FUENTE_CS = RAIZ / "scripts" / "lanzador" / "Lanzador.cs"
EXE = RAIZ / "EAFC Roleplay.exe"
TAMANOS = (16, 24, 32, 48, 64, 128, 256)


def _png_icono(tamano: int) -> bytes:
    from PySide6.QtCore import QBuffer, QByteArray, QIODevice, QPointF, QRectF, Qt
    from PySide6.QtGui import QColor, QImage, QLinearGradient, QPainter, QPainterPath, QPen

    from roleplay.ui import estilos
    from roleplay.ui.componentes import _forma_carta
    from roleplay.ui.estilos import fuente_titulo

    imagen = QImage(tamano, tamano, QImage.Format.Format_ARGB32)
    imagen.fill(Qt.GlobalColor.transparent)
    p = QPainter(imagen)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.setRenderHint(QPainter.RenderHint.TextAntialiasing)

    escala = tamano / 256
    rect = QRectF(34 * escala, 8 * escala, 188 * escala, 240 * escala)
    forma = _forma_carta(rect, 34 * escala, 26 * escala)
    degradado = QLinearGradient(rect.topLeft(), rect.bottomRight())
    degradado.setColorAt(0, QColor(estilos.ACENTO_HOVER))
    degradado.setColorAt(1, QColor("#0B6E3D"))
    p.fillPath(forma, degradado)

    p.save()
    p.setClipPath(forma)
    brillo = QPainterPath(QPointF(rect.left(), rect.top()))
    brillo.lineTo(rect.left() + rect.width() * 0.75, rect.top())
    brillo.lineTo(rect.left(), rect.top() + rect.height() * 0.65)
    brillo.closeSubpath()
    p.fillPath(brillo, QColor(255, 255, 255, 45))
    p.restore()

    if tamano >= 32:
        interior = QColor("#E6FFF1")
        interior.setAlpha(150)
        p.setPen(QPen(interior, max(1.0, 3 * escala)))
        p.drawPath(_forma_carta(rect.adjusted(14 * escala, 14 * escala, -14 * escala, -14 * escala), 24 * escala, 16 * escala))

    p.setPen(QColor(estilos.TEXTO_SOBRE_ACENTO))
    p.setFont(fuente_titulo(max(8, int(132 * escala)), 0))
    p.drawText(rect.adjusted(0, 10 * escala, 0, 0), Qt.AlignmentFlag.AlignCenter, "RP")
    p.end()

    datos = QByteArray()
    buffer = QBuffer(datos)
    buffer.open(QIODevice.OpenModeFlag.WriteOnly)
    imagen.save(buffer, "PNG")
    return bytes(datos)


def crear_icono() -> None:
    """ICO con PNG adentro (Windows Vista en adelante), un tamano por entrada."""
    from PySide6.QtGui import QGuiApplication

    _app = QGuiApplication.instance() or QGuiApplication([])  # noqa: F841 - Qt necesita una app para las fuentes
    imagenes = [(tamano, _png_icono(tamano)) for tamano in TAMANOS]

    cabecera = struct.pack("<HHH", 0, 1, len(imagenes))
    entradas = b""
    desplazamiento = 6 + 16 * len(imagenes)
    for tamano, png in imagenes:
        lado = 0 if tamano >= 256 else tamano  # 0 significa 256 en el formato ICO
        entradas += struct.pack("<BBBBHHII", lado, lado, 0, 0, 1, 32, len(png), desplazamiento)
        desplazamiento += len(png)
    ICONO.write_bytes(cabecera + entradas + b"".join(png for _, png in imagenes))
    print(f"Icono:   {ICONO.relative_to(RAIZ)}")


def _csc() -> Path:
    windir = Path(os.environ.get("WINDIR", r"C:\Windows"))
    for carpeta in ("Framework64", "Framework"):
        candidato = windir / "Microsoft.NET" / carpeta / "v4.0.30319" / "csc.exe"
        if candidato.exists():
            return candidato
    raise SystemExit("No encontre csc.exe (.NET Framework 4). Viene con Windows 10/11.")


def compilar_lanzador() -> None:
    resultado = subprocess.run(
        [
            str(_csc()),
            "/nologo",
            "/target:winexe",
            "/optimize+",
            f"/win32icon:{ICONO}",
            f"/out:{EXE}",
            "/r:System.Windows.Forms.dll",
            "/r:System.Core.dll",
            str(FUENTE_CS),
        ],
        capture_output=True,
        text=True,
    )
    if resultado.returncode != 0:
        raise SystemExit(f"No se pudo compilar el lanzador:\n{resultado.stdout}{resultado.stderr}")
    print(f"Lanzador: {EXE.name} ({EXE.stat().st_size // 1024} KB)")


def crear_iconos_del_escritorio() -> None:
    from roleplay.servicios.accesos import crear_accesos
    from roleplay.servicios.juego import juego_configurado

    juego = juego_configurado()
    if juego is None:
        print("No encontre EA FC 26: solo se crea el icono de roleplay (al abrirlo pide elegir el juego).")
    for ruta in crear_accesos(juego):
        print(f"Icono: {ruta}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Icono, lanzador .exe y acceso directo")
    parser.add_argument("--sin-escritorio", action="store_true", help="no crear el acceso directo")
    args = parser.parse_args()

    crear_icono()
    compilar_lanzador()
    if not args.sin_escritorio:
        crear_iconos_del_escritorio()


if __name__ == "__main__":
    main()
