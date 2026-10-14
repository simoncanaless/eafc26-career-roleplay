"""
Pagina Temporada: la competicion vista desde tu partida de FC 26. Tabla de
posiciones (en las ligas), goleadores, tus resultados y proximos partidos,
y la ultima fecha. Arriba se elige la competicion. Abajo, los ultimos
traspasos que detecto la prensa (servicios/mercado.py).

Todo sale de la partida (servicios/temporada.py), que se lee en un hilo.
"""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QButtonGroup, QComboBox, QFrame, QGridLayout, QHBoxLayout, QLabel, QVBoxLayout, QWidget

from roleplay.database import get_estado_prensa, load_latest_profile
from roleplay.servicios.temporada import leer_temporada
from roleplay.ui import estilos
from roleplay.ui.comun import ejecutar_en_hilo, esc
from roleplay.ui.componentes import (
    Tarjeta,
    chip,
    chip_alternable,
    etiqueta_campo,
    fila,
    limpiar_layout,
    subtitulo,
    texto_suave,
    titulo_pagina,
)
from roleplay.ui.estilos import fuente_titulo

COLUMNAS_TABLA = ("#", "Equipo", "PJ", "G", "E", "P", "GF", "GC", "DIF", "PTS")
COLORES_RESULTADO = {"G": estilos.POSITIVO, "E": estilos.MIXTO, "P": estilos.NEGATIVO}


def _celda(texto, alinear=Qt.AlignmentFlag.AlignCenter, color: str | None = None, negrita=False) -> QLabel:
    label = QLabel(esc(texto))
    label.setAlignment(alinear | Qt.AlignmentFlag.AlignVCenter)
    estilo = "background: transparent;"
    if color:
        estilo += f" color: {color};"
    if negrita:
        estilo += " font-weight: 700;"
    label.setStyleSheet(estilo)
    return label


def _resaltado() -> QFrame:
    """El fondo verde de la fila del club del usuario (va debajo de sus celdas)."""
    marco = QFrame()
    marco.setObjectName("filaUsuario")
    marco.setStyleSheet(
        f"QFrame#filaUsuario {{ background-color: rgba(31, 224, 127, 0.13); border-left: 3px solid {estilos.ACENTO};"
        " border-radius: 4px; }"
    )
    return marco


class PaginaTemporada(QWidget):
    def __init__(self):
        super().__init__()
        self._competicion: int | None = None  # la elegida; None = la liga del club
        self._leyendo = False
        self._pendiente = False  # se pidio otra competicion mientras se leia
        self._grupo = QButtonGroup(self)
        self._grupo.setExclusive(True)
        self.vista = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(40, 34, 40, 34)
        layout.setSpacing(18)

        textos = QVBoxLayout()
        textos.setSpacing(2)
        self.titulo_label = titulo_pagina("Temporada")
        self.subtitulo_label = subtitulo("Leyendo tu partida de FC 26...")
        textos.addWidget(self.titulo_label)
        textos.addWidget(self.subtitulo_label)
        layout.addLayout(textos)

        self.competiciones_layout = QHBoxLayout()
        self.competiciones_layout.setSpacing(8)
        # el resto del mundo de la partida: otras ligas, copas de otros paises, selecciones
        self.otras_combo = QComboBox()
        self.otras_combo.setMinimumWidth(240)
        self.otras_combo.setToolTip("Las demas competiciones que simula tu partida")
        self.otras_combo.activated.connect(self._on_otra)
        self.otras_combo.hide()
        layout.addLayout(fila(self.competiciones_layout, None, self.otras_combo))

        # ---- sin partida ----
        self.vacio = Tarjeta("Sin partida de Carrera Jugador", destacada=True)
        self.vacio_label = texto_suave(
            "Esta pagina se llena con tu partida de FC 26: la tabla, los goleadores, tus resultados y lo que "
            "viene. Juega Carrera Jugador y guarda, o elige la partida en AJUSTES > Tu partida de FC 26."
        )
        self.vacio.cuerpo.addWidget(self.vacio_label)
        self.vacio.hide()
        layout.addWidget(self.vacio)

        # ---- contenido ----
        self.contenido = QWidget()
        contenido = QVBoxLayout(self.contenido)
        contenido.setContentsMargins(0, 0, 0, 0)
        contenido.setSpacing(18)

        self.tabla_tarjeta = Tarjeta("Tabla de posiciones")
        self.tabla_grilla = QGridLayout()
        self.tabla_grilla.setHorizontalSpacing(0)
        self.tabla_grilla.setVerticalSpacing(0)
        self.tabla_tarjeta.cuerpo.addLayout(self.tabla_grilla)
        contenido.addWidget(self.tabla_tarjeta)

        abajo = QHBoxLayout()
        abajo.setSpacing(18)
        izquierda = QVBoxLayout()
        izquierda.setSpacing(18)
        derecha = QVBoxLayout()
        derecha.setSpacing(18)

        self.goleadores_tarjeta = Tarjeta("Goleadores")
        self.goleadores_grilla = QGridLayout()
        self.goleadores_grilla.setHorizontalSpacing(10)
        self.goleadores_grilla.setVerticalSpacing(6)
        self.goleadores_tarjeta.cuerpo.addLayout(self.goleadores_grilla)
        izquierda.addWidget(self.goleadores_tarjeta)

        self.mercado_tarjeta = Tarjeta("Mercado de fichajes")
        self.mercado_layout = QVBoxLayout()
        self.mercado_layout.setSpacing(6)
        self.mercado_tarjeta.cuerpo.addLayout(self.mercado_layout)
        self.mercado_tarjeta.hide()
        izquierda.addWidget(self.mercado_tarjeta)
        izquierda.addStretch()

        self.club_tarjeta = Tarjeta("Tus partidos", destacada=True)
        self.club_layout = QVBoxLayout()
        self.club_layout.setSpacing(6)
        self.club_tarjeta.cuerpo.addLayout(self.club_layout)
        derecha.addWidget(self.club_tarjeta)

        self.fecha_tarjeta = Tarjeta("Ultima fecha")
        self.fecha_layout = QVBoxLayout()
        self.fecha_layout.setSpacing(6)
        self.fecha_tarjeta.cuerpo.addLayout(self.fecha_layout)
        derecha.addWidget(self.fecha_tarjeta)
        derecha.addStretch()

        abajo.addLayout(izquierda, 1)
        abajo.addLayout(derecha, 1)
        contenido.addLayout(abajo)
        self.contenido.hide()
        layout.addWidget(self.contenido)
        layout.addStretch()

    # ---- lectura ----

    def actualizar(self):
        if self._leyendo:
            self._pendiente = True
            return
        self._leyendo = True
        ejecutar_en_hilo(leer_temporada, self._competicion, al_completar=self._on_vista, al_fallar=self._on_error)

    def _on_otra(self, indice: int):
        competicion = self.otras_combo.itemData(indice)
        if competicion is not None:
            self._elegir(competicion)

    def _elegir(self, competicion: int):
        if competicion != self._competicion:
            self._competicion = competicion
            self.actualizar()

    def _terminar_lectura(self) -> bool:
        """True si hay que volver a leer (se cambio de competicion entretanto)."""
        self._leyendo = False
        if self._pendiente:
            self._pendiente = False
            self.actualizar()
            return True
        return False

    def _on_error(self, mensaje: str):
        if self._terminar_lectura():
            return
        self.vista = None
        self.titulo_label.setText("TEMPORADA")
        self.subtitulo_label.setText("No se pudo leer tu partida de FC 26.")
        self.vacio_label.setText(f"La partida no se pudo leer: {esc(mensaje)}")
        limpiar_layout(self.competiciones_layout)
        self.vacio.show()
        self.contenido.hide()

    def _on_vista(self, vista):
        if self._terminar_lectura():
            return
        self.vista = vista
        if vista is None:
            self.titulo_label.setText("TEMPORADA")
            self.subtitulo_label.setText("Sin partida de Carrera Jugador en este PC.")
            limpiar_layout(self.competiciones_layout)
            self.vacio.show()
            self.contenido.hide()
            return
        self._competicion = vista.competicion
        self.vacio.hide()
        self.contenido.show()
        self.titulo_label.setText(f"TEMPORADA {esc(vista.temporada)}")
        if vista.posicion:
            lugar = f" · {vista.posicion}° en la {esc(vista.nombre_competicion)}"
        elif not vista.es_propia:
            lugar = f" · mirando {esc(vista.nombre_competicion)}"
        else:
            lugar = ""
        self.subtitulo_label.setText(
            f"<b>{esc(vista.club)}</b>{lugar} · partida \"{esc(vista.partida)}\" al {esc(vista.fecha)}"
        )
        self._mostrar_competiciones(vista)
        self._mostrar_tabla(vista)
        self._mostrar_goleadores(vista)
        self._mostrar_partidos(vista)
        self._mostrar_mercado()

    # ---- dibujo ----

    def _mostrar_competiciones(self, vista):
        limpiar_layout(self.competiciones_layout)
        for boton in self._grupo.buttons():
            self._grupo.removeButton(boton)
        # mirando otra competicion, ninguna de las del club queda marcada
        self._grupo.setExclusive(vista.es_propia)
        for competicion, nombre in vista.competiciones:
            boton = chip_alternable(nombre)
            boton.setChecked(competicion == vista.competicion)
            boton.clicked.connect(lambda _=False, c=competicion: self._elegir(c))
            self._grupo.addButton(boton)
            self.competiciones_layout.addWidget(boton)
        self._grupo.setExclusive(True)

        self.otras_combo.clear()
        self.otras_combo.addItem("Otras competiciones...", None)
        for competicion, nombre in vista.otras:
            self.otras_combo.addItem(nombre, competicion)
        self.otras_combo.setCurrentIndex(max(0, self.otras_combo.findData(vista.competicion)))
        self.otras_combo.setVisible(bool(vista.otras))

    def _mostrar_tabla(self, vista):
        limpiar_layout(self.tabla_grilla)
        self.tabla_tarjeta.setVisible(bool(vista.tabla))
        if not vista.tabla:
            return
        izquierda = Qt.AlignmentFlag.AlignLeft
        for columna, rotulo in enumerate(COLUMNAS_TABLA):
            cabeza = etiqueta_campo(rotulo)
            cabeza.setAlignment((izquierda if columna == 1 else Qt.AlignmentFlag.AlignCenter))
            cabeza.setContentsMargins(0, 0, 0, 6)
            self.tabla_grilla.addWidget(cabeza, 0, columna)
        for n, f in enumerate(vista.tabla, start=1):
            if f.es_usuario:
                self.tabla_grilla.addWidget(_resaltado(), n, 0, 1, len(COLUMNAS_TABLA))
            color = estilos.TEXTO if f.es_usuario else None
            dif = f"+{f.dif}" if f.dif > 0 else str(f.dif)
            valores = (f.posicion, f.equipo, f.pj, f.pg, f.pe, f.pp, f.gf, f.gc, dif, f.pts)
            for columna, valor in enumerate(valores):
                celda = _celda(
                    valor,
                    izquierda if columna == 1 else Qt.AlignmentFlag.AlignCenter,
                    color=estilos.ACENTO if (f.es_usuario and columna in (0, 9)) else color,
                    negrita=f.es_usuario or columna == 9,
                )
                celda.setMinimumHeight(30)
                if columna == 1:
                    celda.setContentsMargins(8, 0, 0, 0)
                self.tabla_grilla.addWidget(celda, n, columna)
        self.tabla_grilla.setColumnStretch(1, 1)
        for columna in range(len(COLUMNAS_TABLA)):
            if columna != 1:
                self.tabla_grilla.setColumnMinimumWidth(columna, 44)

    def _mostrar_goleadores(self, vista):
        limpiar_layout(self.goleadores_grilla)
        self.goleadores_tarjeta.setVisible(bool(vista.goleadores))
        for n, g in enumerate(vista.goleadores, start=1):
            puesto = QLabel(str(n))
            puesto.setFont(fuente_titulo(20, 0))
            puesto.setStyleSheet(f"color: {estilos.ACENTO if g.es_usuario else estilos.TEXTO_SUAVE};")
            nombre = QLabel(
                f"<b>{esc(g.nombre)}</b>" + (f" <span style='color:{estilos.ACENTO}'>(vos)</span>" if g.es_usuario else "")
                + f"<br><span style='color:{estilos.TEXTO_SUAVE}'>{esc(g.equipo)} · {g.partidos} PJ</span>"
            )
            nombre.setWordWrap(True)
            goles = QLabel(str(g.goles))
            goles.setFont(fuente_titulo(26, 0.3))
            goles.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            if g.es_usuario:
                goles.setStyleSheet(f"color: {estilos.ACENTO};")
            self.goleadores_grilla.addWidget(puesto, n, 0)
            self.goleadores_grilla.addWidget(nombre, n, 1)
            self.goleadores_grilla.addWidget(goles, n, 2)
        self.goleadores_grilla.setColumnStretch(1, 1)
        self.goleadores_grilla.setColumnMinimumWidth(0, 22)

    def _mostrar_mercado(self):
        limpiar_layout(self.mercado_layout)
        perfil = load_latest_profile()
        movimientos = get_estado_prensa(perfil.id).get("mercado", []) if perfil is not None else []
        for movimiento in movimientos:
            texto = QLabel(esc(movimiento["texto"][:1].upper() + movimiento["texto"][1:]))
            texto.setWordWrap(True)
            partes = [texto, None]
            if movimiento.get("club"):
                partes.append(chip("Tu club", estilos.ACENTO))
            fecha = movimiento.get("fecha", "")
            dia = texto_suave(f"{fecha[8:10]}/{fecha[5:7]}" if len(fecha) >= 10 else "", ajustar=False)
            dia.setFixedWidth(46)
            self.mercado_layout.addLayout(fila(dia, *partes, espaciado=10))
        self.mercado_tarjeta.setVisible(bool(movimientos))

    def _linea_partido(self, p, con_resultado: bool) -> QHBoxLayout:
        fecha = texto_suave(p.fecha, ajustar=False)
        fecha.setFixedWidth(46)
        texto = QLabel(
            f"{esc(p.local)} <b>{esc(p.marcador)}</b> {esc(p.visita)}"
            if p.marcador != "vs" else f"{esc(p.local)} <span style='color:{estilos.TEXTO_SUAVE}'>vs</span> {esc(p.visita)}"
        )
        if p.es_usuario and not con_resultado:
            texto.setStyleSheet(f"color: {estilos.TEXTO}; font-weight: 600;")
        elif not p.es_usuario:
            texto.setStyleSheet(f"color: {estilos.TEXTO_SUAVE};")
        partes = [fecha, texto, None]
        if con_resultado and p.resultado:
            partes.append(chip(p.resultado, COLORES_RESULTADO[p.resultado]))
        return fila(*partes, espaciado=10)

    def _mostrar_partidos(self, vista):
        limpiar_layout(self.club_layout)
        self.club_tarjeta.setVisible(vista.es_propia)
        if vista.resultados:
            self.club_layout.addWidget(etiqueta_campo("Resultados"))
            for p in vista.resultados:
                self.club_layout.addLayout(self._linea_partido(p, con_resultado=True))
        if vista.proximos:
            if vista.resultados:
                self.club_layout.addSpacing(8)
            self.club_layout.addWidget(etiqueta_campo("Lo que viene"))
            for p in vista.proximos:
                self.club_layout.addLayout(self._linea_partido(p, con_resultado=False))
        if not vista.resultados and not vista.proximos:
            self.club_layout.addWidget(texto_suave("Tu club no tiene partidos en esta competicion."))

        limpiar_layout(self.fecha_layout)
        self.fecha_tarjeta.setVisible(bool(vista.ultima_fecha))
        if vista.ultima_fecha:
            self.fecha_layout.addWidget(etiqueta_campo(vista.titulo_ultima_fecha))
            for p in vista.ultima_fecha:
                linea = self._linea_partido(p, con_resultado=False)
                self.fecha_layout.addLayout(linea)
