"""
Captura de pantalla de fin de partido, con dxcam (Windows, Desktop
Duplication API). Despues se manda a Gemini Vision (servicios/vision.py).

dxcam y OpenCV se importan recien al capturar: cargarlos al abrir la app
la demoraba ~0,4 s para algo que se usa una vez por partido.
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
        _camara = dxcam.create(output_color="BGR")
    return _camara


def capturar_pantalla(region: Optional[Tuple[int, int, int, int]] = None) -> bytes:
    """Captura la pantalla completa (o `region` = (left, top, right,
    bottom) en pixeles) y la devuelve como PNG.

    Pasarle solo el recuadro de stats ahorra tokens y tiempo, pero depende
    de la resolucion; por eso por defecto va la pantalla completa.
    """
    import cv2

    frame = _obtener_camara().grab(region=region, new_frame_only=False)
    if frame is None:
        raise RuntimeError(
            "dxcam no pudo capturar la pantalla (frame vacio). Proba de nuevo con "
            "el juego en primer plano, o escribi las stats a mano."
        )

    ok, buffer = cv2.imencode(".png", frame)
    if not ok:
        raise RuntimeError("No se pudo codificar la captura como PNG.")
    return buffer.tobytes()
