"""
Captura de pantalla de fin de partido, con dxcam (Windows, Desktop
Duplication API: la misma que usan OBS o Discord para compartir pantalla;
no toca el juego). La usa el diagnostico para probar que se puede capturar.

Se pide la imagen en BGRA, el formato nativo de Windows: asi dxcam no
convierte colores y no necesita OpenCV (~110 MB menos en el paquete para
los amigos). El PNG lo arma Qt. dxcam se importa recien al capturar.
"""

from typing import Optional, Tuple

_camara = None  # se reusa entre capturas


def _obtener_camara():
    global _camara
    if _camara is None:
        try:
            import dxcam
        except ImportError as exc:
            raise RuntimeError(
                "dxcam no esta disponible: es una libreria solo para Windows. "
                "Instalala con: .venv\\Scripts\\python.exe -m pip install -r requirements.txt "
                f"(error original: {exc})"
            ) from exc
        # Monitor principal. Si jugas en otro, pasar output_idx=1, 2...
        _camara = dxcam.create(output_color="BGRA", processor_backend="numpy")
    return _camara


def a_png(frame) -> bytes:
    """Cuadro BGRA de dxcam (alto x ancho x 4) -> PNG. RGB32 ignora el
    canal alfa, que en la captura de escritorio puede venir en 0."""
    from PySide6.QtCore import QBuffer, QIODevice
    from PySide6.QtGui import QImage

    alto, ancho = frame.shape[:2]
    imagen = QImage(frame.data, ancho, alto, frame.strides[0], QImage.Format.Format_RGB32).copy()
    buffer = QBuffer()
    buffer.open(QIODevice.OpenModeFlag.WriteOnly)
    if not imagen.save(buffer, "PNG"):
        raise RuntimeError("No se pudo codificar la captura como PNG.")
    return bytes(buffer.data())


def capturar_pantalla(region: Optional[Tuple[int, int, int, int]] = None) -> bytes:
    """Captura la pantalla completa (o `region` = (left, top, right,
    bottom) en pixeles) y la devuelve como PNG.

    Pasarle solo el recuadro de stats ahorra tokens y tiempo, pero depende
    de la resolucion; por eso por defecto va la pantalla completa.
    """
    frame = _obtener_camara().grab(region=region, new_frame_only=False)
    if frame is None:
        raise RuntimeError(
            "dxcam no pudo capturar la pantalla (frame vacio). Proba de nuevo con "
            "el juego en primer plano, o escribi las stats a mano."
        )
    return a_png(frame)
