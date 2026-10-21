"""
La mesa de negociacion con la directiva (servicios/contratos.py): la oferta
del club por clausula, lo que pedis vos, lo que opina tu representante y
cuanta paciencia le queda a la directiva. Se firma la oferta vigente del club
(cuando acepta tu pedido, la oferta pasa a ser tu pedido).

Al cerrar sin firmar, la negociacion queda guardada como esta (con su
paciencia): volver a abrirla no la reinicia.
"""

from typing import Optional

from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDoubleSpinBox,
    QGridLayout,
    QSpinBox,
    QLabel,
    QVBoxLayout,
    QWidget,
)

from roleplay.servicios import contratos
from roleplay.servicios.narrador import narrador
from roleplay.ui import estilos
from roleplay.ui.comun import ejecutar_en_hilo, esc
from roleplay.ui.componentes import boton, etiqueta_campo, fila, texto_suave, titulo_seccion

COLOR_CONSEJO = {"margen": "POSITIVO", "justo": "TEXTO_SUAVE", "pasado": "NEGATIVO"}


class DialogoNegociacion(QDialog):
    def __init__(self, negociacion: dict, sueldo: int, moneda: str, player_id: Optional[int] = None,
                 parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setWindowTitle("EAFC 26 Roleplay - Negociar el contrato")
        self.negociacion, self.sueldo, self.moneda, self.player_id = negociacion, sueldo, moneda, player_id
        self.firmado = False
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 18, 20, 18)
        layout.setSpacing(12)
        layout.addWidget(titulo_seccion(f"Primas con {negociacion['club']}"))
        layout.addWidget(texto_suave(
            "Tu sueldo base es el de tu contrato en FC 26 (eso se negocia en el juego). Aca se negocia lo demas: "
            "lo que el club te paga por firmar, por tus goles y premios, por quedarte y por tu imagen. "
            "Escribi cuanto queres por cada cosa. Los montos son en bruto: se cobra el neto, como el sueldo."
        ))
        self.directiva_label = QLabel()
        self.directiva_label.setWordWrap(True)
        layout.addWidget(self.directiva_label)
        self.paciencia_label = texto_suave()
        layout.addWidget(self.paciencia_label)

        grilla = QGridLayout()
        grilla.setHorizontalSpacing(14)
        grilla.setVerticalSpacing(8)
        for columna, titulo in enumerate(("Clausula", "Oferta del club", "Lo que pedis", "Tu representante")):
            grilla.addWidget(etiqueta_campo(titulo), 0, columna)
        self.ofertas, self.pedidos, self.consejos = {}, {}, {}
        for fila_n, c in enumerate(contratos.CLAUSULAS, start=1):
            nombre = QLabel(f"<b>{esc(c.nombre)}</b><br><span style='color:{estilos.TEXTO_SUAVE}'>{esc(c.que)}</span>")
            nombre.setWordWrap(True)
            grilla.addWidget(nombre, fila_n, 0)
            self.ofertas[c.id] = QLabel()
            self.ofertas[c.id].setWordWrap(True)
            grilla.addWidget(self.ofertas[c.id], fila_n, 1)
            if c.unidad == "%":  # la imagen: en % del sueldo (la plata por semana se ve en la oferta)
                pedido = QDoubleSpinBox()
                pedido.setDecimals(0)
                pedido.setRange(0, 100)
                pedido.setSuffix("% del sueldo")
            else:  # las primas: en plata (por dentro siguen siendo semanas de sueldo)
                pedido = QSpinBox()
                pedido.setRange(0, 2_000_000_000)
                pedido.setGroupSeparatorShown(True)
                pedido.setPrefix(f"{moneda} ")
                pedido.setSingleStep(max(1_000, round(c.paso * sueldo, -3)))
            pedido.setProperty("clausula", c.id)
            pedido.valueChanged.connect(self._aconsejar)
            self.pedidos[c.id] = pedido
            grilla.addWidget(pedido, fila_n, 2)
            self.consejos[c.id] = QLabel()
            self.consejos[c.id].setWordWrap(True)
            grilla.addWidget(self.consejos[c.id], fila_n, 3)
        grilla.setColumnStretch(0, 2)
        grilla.setColumnStretch(1, 2)
        grilla.setColumnStretch(3, 2)
        layout.addLayout(grilla)

        self.temporadas = QComboBox()
        for n in contratos.TEMPORADAS:
            self.temporadas.addItem(f"{n} temporada{'s' if n > 1 else ''}", n)
        self.temporadas.setCurrentIndex(2)
        layout.addLayout(fila(etiqueta_campo("Duracion de las primas"), self.temporadas, None))
        self.levantarse_btn = boton("Levantarse de la mesa")
        self.levantarse_btn.clicked.connect(self.levantarse)
        self.cerrar_btn = boton("Pensarlo")
        self.cerrar_btn.setToolTip("Cerrar y seguir despues (la directiva se acuerda de todo)")
        self.cerrar_btn.clicked.connect(self.reject)
        self.contraofertar_btn = boton("Contraofertar")
        self.contraofertar_btn.clicked.connect(self.contraofertar)
        self.firmar_btn = boton("Firmar la oferta del club", primario=True)
        self.firmar_btn.clicked.connect(self.firmar)
        layout.addLayout(fila(self.levantarse_btn, None, self.cerrar_btn, self.contraofertar_btn, self.firmar_btn))

        self._decir("neg_abre" if negociacion["ronda"] == 0 else "neg_sube")
        self._mostrar(poner_pedidos=True)
        self.setMinimumWidth(980)

    # ---- dibujo ----

    def _decir(self, simbolo: str):
        """La frase del corpus al toque y, si hay IA, la suya cuando llega (si no se dijo otra mientras)."""
        with narrador(self.player_id, "vida") as escritor:
            texto = escritor.decir(simbolo, club=self.negociacion["club"])
        self._poner_frase(texto)
        self._frase_pedida = getattr(self, "_frase_pedida", 0) + 1
        ejecutar_en_hilo(contratos.frase_con_ia, self.player_id, self.negociacion["club"], simbolo,
                         self._frase_pedida, al_completar=self._on_frase_ia, al_fallar=self._on_frase_fallo)

    def _poner_frase(self, texto: str):
        self.directiva_label.setText(f"<span style='font-size:15px'>{esc(texto)}</span>")

    def _on_frase_fallo(self, _error: str):
        pass  # queda la frase del corpus

    def _on_frase_ia(self, resultado):
        texto, pedida = resultado
        if texto and pedida == self._frase_pedida:
            self._poner_frase(texto)

    def _mostrar(self, poner_pedidos: bool = False):
        neg = self.negociacion
        for c in contratos.CLAUSULAS:
            self.ofertas[c.id].setText(contratos.rotulo(c, neg["oferta"][c.id], self.sueldo, self.moneda,
                                                        neg.get("meta_goles", 0)))
            if poner_pedidos:
                self.pedidos[c.id].setValue(neg["oferta"][c.id] if c.unidad == "%" else
                                            contratos.monto(c, neg["oferta"][c.id], self.sueldo))
        abierta = neg["estado"] == "abierta"
        if neg["estado"] == "rota":
            self.paciencia_label.setText("La directiva se levanto de la mesa.")
        elif neg["estado"] == "acuerdo":
            self.paciencia_label.setText("Hay acuerdo: elegi la duracion y firma.")
        else:
            self.paciencia_label.setText(f"Paciencia de la directiva: {'●' * neg['paciencia']}"
                                         f"{'○' * max(0, neg.get('paciencia_inicial', contratos.PACIENCIA) - neg['paciencia'])} "
                                         f"· ronda {neg['ronda'] + 1}")
        for pedido in self.pedidos.values():
            pedido.setEnabled(abierta)
        self.contraofertar_btn.setEnabled(abierta)
        self.levantarse_btn.setEnabled(abierta)
        self.firmar_btn.setEnabled(neg["estado"] in ("abierta", "acuerdo"))
        self._aconsejar()

    def pedido(self) -> dict:
        """Lo que pide, en las unidades de contratos.py (semanas de sueldo; la imagen en %)."""
        resultado = {}
        for c in contratos.CLAUSULAS:
            valor = self.pedidos[c.id].value()
            resultado[c.id] = valor if c.unidad == "%" or not self.sueldo else valor / self.sueldo
        return resultado

    def _aconsejar(self, *_):
        if self.negociacion["estado"] != "abierta":
            for etiqueta in self.consejos.values():
                etiqueta.clear()
            return
        consejos = contratos.consejo(self.negociacion, self.pedido())
        with narrador(None, "vida") as escritor:  # sin memoria: es una pista, no un texto para guardar
            for clausula, opinion in consejos.items():
                color = getattr(estilos, COLOR_CONSEJO[opinion])
                self.consejos[clausula].setText(
                    f"<span style='color:{color}'>{esc(escritor.elegir(f'rep_{opinion}'))}</span>")

    # ---- acciones ----

    def contraofertar(self):
        self.negociacion, respuesta = contratos.contraofertar(self.negociacion, self.pedido())
        self._decir(f"neg_{respuesta}")
        self._mostrar(poner_pedidos=respuesta != "ofendida")

    def levantarse(self):
        self.negociacion = contratos.levantarse(self.negociacion)
        self._decir("neg_te_vas")
        self._mostrar()

    def firmar(self):
        self.firmado = True
        self.accept()

    def duracion(self) -> int:
        return int(self.temporadas.currentData())
