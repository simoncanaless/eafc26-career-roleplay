"""
Modo en vivo: vigilar la partida de FC 26 mientras se juega.

Cada pocos segundos se mira (sin abrirlo) el guardado de la carrera. Cuando
el juego lo reescribe, se espera a que deje de cambiar -para no leerlo a
medio escribir- y se lee en otro hilo. Si el club del usuario jugo un
partido nuevo, se emite `partido_nuevo`: la app avisa, prepara la sala de
prensa y actualiza la prensa.

La primera lectura solo marca donde estamos (no avisa del ultimo partido
que ya estaba jugado al abrir la app).
"""

from typing import Optional

from PySide6.QtCore import QObject, QTimer, Signal, Slot

from roleplay import ajustes
from roleplay.database import get_estado_partida, load_latest_profile, set_estado_partida
from roleplay.partida import lector
from roleplay.servicios.partida_real import leer_para_entrevista
from roleplay.ui.comun import ejecutar_en_hilo

INTERVALO_MS = 5000


def en_vivo_activo() -> bool:
    return ajustes.leer().get("en_vivo", {}).get("vigilar", True)


def preparar_entrevista_sola() -> bool:
    return ajustes.leer().get("en_vivo", {}).get("preguntas_solas", True)


def mostrar_flotante_sola() -> bool:
    return ajustes.leer().get("en_vivo", {}).get("flotante", True)


class VigilantePartida(QObject):
    partido_nuevo = Signal(object)  # LecturaPartida con un partido que no se habia avisado
    partida_actualizada = Signal(object)  # LecturaPartida, ante cualquier guardado nuevo

    def __init__(self, parent: Optional[QObject] = None, intervalo_ms: int = INTERVALO_MS):
        super().__init__(parent)
        self._firma_leida = None  # (ruta, fecha, tamano) de lo ultimo que se leyo
        self._firma_vista = None  # la que se vio en la vuelta anterior (para esperar que se asiente)
        self._leyendo = False
        self._reloj = QTimer(self)
        self._reloj.setInterval(intervalo_ms)
        self._reloj.timeout.connect(self.revisar)

    def iniciar(self) -> None:
        self._reloj.start()
        self.revisar()

    def detener(self) -> None:
        self._reloj.stop()

    @Slot()
    def revisar(self) -> None:
        if self._leyendo or not en_vivo_activo():
            return
        ruta = lector.guardado_elegido()
        if ruta is None:
            return
        try:
            estado = ruta.stat()
        except OSError:
            return  # el juego lo esta reemplazando justo ahora
        firma = (str(ruta), estado.st_mtime, estado.st_size)
        if firma == self._firma_leida:
            return
        if firma != self._firma_vista:
            self._firma_vista = firma  # cambio: se lee en la proxima vuelta si sigue igual
            return
        perfil = load_latest_profile()
        if perfil is None:
            return
        self._leyendo = True
        self._firma_leida = firma
        ejecutar_en_hilo(leer_para_entrevista, perfil.id, al_completar=self._on_leida, al_fallar=self._on_fallo)

    def _on_fallo(self, _mensaje: str) -> None:
        # Se reintenta en la proxima vuelta (quizas el juego seguia escribiendo).
        self._leyendo = False
        self._firma_leida = None

    def _on_leida(self, lectura) -> None:
        self._leyendo = False
        if lectura is None:
            return
        self.partida_actualizada.emit(lectura)
        if lectura.ultimo is None:
            return
        perfil = load_latest_profile()
        if perfil is None:
            return
        avisado = get_estado_partida(perfil.id).get("avisado")
        if avisado == lectura.ultimo.clave:
            return
        set_estado_partida(perfil.id, {"avisado": lectura.ultimo.clave})
        if avisado is not None:  # la primera vez solo se marca donde estamos
            self.partido_nuevo.emit(lectura)
