"""
Menu principal: barra lateral + una pagina por modulo (Resumen,
Temporada, Entrevistas, Instagram, Vida), sobre el fondo de estadio. Cada pagina va dentro
de un scroll.
"""

from PySide6.QtCore import QSize, Qt, Signal
from PySide6.QtGui import QAction, QIcon
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QFrame,
    QMenu,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QProgressBar,
    QPushButton,
    QSpinBox,
    QStackedWidget,
    QSystemTrayIcon,
    QVBoxLayout,
    QWidget,
)

from roleplay.database import (
    actualizar_club,
    agregar_meta,
    get_estado_clubes,
    get_estado_prensa,
    get_metas,
    get_reputacion_actual,
    get_seguidores,
    load_latest_profile,
    load_match_interviews,
    load_noticias_prensa,
    quitar_meta,
    save_actividad_instagram,
    save_noticia_prensa,
    set_estado_clubes,
    sumar_reputacion_y_seguidores,
)
from roleplay import config
from roleplay.servicios import clubes, eventos
from roleplay.servicios.hinchada import _escala
from roleplay.servicios.metas import CONTABLES, TIPOS, nueva_meta, texto_meta
from roleplay.servicios.partida_real import resumen_temporada
from roleplay.servicios.prensa import calcular_estadisticas_acumuladas
from roleplay.ui import estilos
from roleplay.ui.comun import con_scroll, ejecutar_en_hilo, esc, miles
from roleplay.ui.componentes import (
    CartaJugador,
    FondoEstadio,
    Mosaico,
    Tarjeta,
    agregar_noticia,
    boton,
    chip,
    compacto,
    etiqueta_campo,
    fila,
    icono,
    limpiar_layout,
    nivel_carta,
    separador,
    subtitulo,
    texto_suave,
    titulo_pagina,
)
from roleplay.ui.entrevista import InterviewWindow
from roleplay.ui.estilos import fuente_titulo
from roleplay.ui.instagram import InstagramWindow
from roleplay.ui.temporada import PaginaTemporada
from roleplay.ui.vida import PaginaVida
from roleplay.ui.ajustes import DialogoAjustes, abrir_juego_o_preguntar
from roleplay.ui.personaje import CharacterWizard
from roleplay.ui.atajo import ATAJO_TEXTO, AtajoGlobal
from roleplay.ui.overlay import SalaFlotante, _poner_al_frente
from roleplay.ui.overlay_completo import OverlayCompleto, anotar as anotar_overlay, configuracion as configuracion_overlay
from roleplay.ui.mando import MandoOverlay
from roleplay.ui.vigilante import VigilantePartida, mostrar_flotante_sola, preparar_entrevista_sola

NOTICIAS_EN_RESUMEN = 5


class PaginaResumen(QWidget):
    """Vistazo del personaje: su carta, los numeros de la carrera, la
    historia, las tramas abiertas y las ultimas noticias."""

    decision_pendiente = Signal(str)  # el titulo: el menu avisa en la bandeja
    reputacion_cambiada = Signal()  # una decision o un traspaso movio la reputacion

    def __init__(self, on_crear_personaje, on_club_cambiado=None):
        super().__init__()
        self._on_crear_personaje = on_crear_personaje
        self._on_club_cambiado = on_club_cambiado  # para que la barra lateral se entere
        self._perfil = None
        self._leyendo_temporada = False
        self._temporada_actual = ""  # "2026/27", de la partida: a esa temporada van las metas nuevas

        layout = QVBoxLayout(self)
        layout.setContentsMargins(40, 34, 40, 34)
        layout.setSpacing(18)

        # ---- cabecera ----
        cabecera = QHBoxLayout()
        textos = QVBoxLayout()
        textos.setSpacing(2)
        self.titulo_label = titulo_pagina()
        self.stats_label = subtitulo()
        textos.addWidget(self.titulo_label)
        textos.addWidget(self.stats_label)
        cabecera.addLayout(textos, 1)
        self.crear_btn = boton("Nuevo personaje", icono_nombre="nuevo")
        self.crear_btn.clicked.connect(self._on_crear_personaje)
        cabecera.addWidget(self.crear_btn, 0, Qt.AlignmentFlag.AlignTop)
        layout.addLayout(cabecera)

        # ---- sin personaje ----
        self.vacio = Tarjeta("Arranca tu carrera", destacada=True)
        self.vacio.cuerpo.addWidget(
            texto_suave(
                "Crea tu jugador: de donde viene, como es frente a la prensa y que lo mueve. "
                "Con eso se escribe su historia y empiezan las entrevistas, la prensa y su Instagram."
            )
        )
        crear_grande = boton("Crear personaje", primario=True, icono_nombre="nuevo")
        crear_grande.clicked.connect(self._on_crear_personaje)
        self.vacio.cuerpo.addWidget(crear_grande, 0, Qt.AlignmentFlag.AlignLeft)
        layout.addWidget(self.vacio)

        # ---- carta + numeros ----
        self.contenido = QWidget()
        contenido = QVBoxLayout(self.contenido)
        contenido.setContentsMargins(0, 0, 0, 0)
        contenido.setSpacing(18)

        arriba = QHBoxLayout()
        arriba.setSpacing(22)
        self.carta = CartaJugador()
        arriba.addWidget(self.carta, 0, Qt.AlignmentFlag.AlignTop)

        derecha = QVBoxLayout()
        derecha.setSpacing(14)
        grilla = QGridLayout()
        grilla.setSpacing(10)
        self.mosaicos = {}
        for i, (clave, rotulo) in enumerate(
            (
                ("partidos", "Partidos"),
                ("goles", "Goles"),
                ("asistencias", "Asistencias"),
                ("rating", "Rating prom."),
                ("figuras", "Figura del partido"),
                ("seguidores", "Seguidores"),
            )
        ):
            self.mosaicos[clave] = Mosaico(rotulo)
            grilla.addWidget(self.mosaicos[clave], i // 3, i % 3)
        derecha.addLayout(grilla)

        historia = Tarjeta("Su historia")
        self.backstory_label = texto_suave()
        historia.cuerpo.addWidget(self.backstory_label)
        derecha.addWidget(historia)
        derecha.addStretch()
        arriba.addLayout(derecha, 1)
        contenido.addLayout(arriba)

        # ---- la temporada real (partida de FC 26) ----
        self.temporada = Tarjeta("Tu temporada en FC 26", destacada=True)
        self.temporada_label = texto_suave()
        self.temporada.cuerpo.addWidget(self.temporada_label)
        self.temporada_competiciones = QVBoxLayout()
        self.temporada_competiciones.setSpacing(4)
        self.temporada.cuerpo.addLayout(self.temporada_competiciones)
        self.temporada_ultimos = QHBoxLayout()
        self.temporada_ultimos.setSpacing(6)
        self.temporada.cuerpo.addLayout(self.temporada_ultimos)
        self.temporada_proximo = texto_suave()
        self.temporada.cuerpo.addWidget(self.temporada_proximo)
        self.temporada.hide()
        contenido.addWidget(self.temporada)

        # ---- la hinchada de cada club y las decisiones (servicios/clubes.py) ----
        self.hinchada = Tarjeta("Tu hinchada")
        self.hinchada_label = QLabel()
        self.hinchada_barra = QProgressBar()
        self.hinchada_barra.setRange(0, 100)
        self.hinchada_barra.setTextVisible(False)
        self.hinchada_barra.setFixedWidth(220)
        self.hinchada.cuerpo.addLayout(fila(self.hinchada_label, None, self.hinchada_barra))
        self.decision = QFrame()
        self.decision.setObjectName("decision")
        self.decision.setStyleSheet(
            f"QFrame#decision {{ border: 1px solid {estilos.ACENTO}; border-radius: 10px; }}"
        )
        decision = QVBoxLayout(self.decision)
        decision.setContentsMargins(14, 12, 14, 12)
        decision.setSpacing(8)
        self.decision_label = QLabel()
        self.decision_label.setWordWrap(True)
        decision.addWidget(self.decision_label)
        self.decision_botones = QHBoxLayout()
        self.decision_botones.setSpacing(8)
        decision.addLayout(self.decision_botones)
        self.decision.hide()
        self.hinchada.cuerpo.addWidget(self.decision)
        self.eleccion_label = QLabel()
        self.eleccion_label.setWordWrap(True)
        self.eleccion_label.hide()
        self.hinchada.cuerpo.addWidget(self.eleccion_label)
        self.hinchada_antes = texto_suave()
        self.hinchada.cuerpo.addWidget(self.hinchada_antes)
        self.hinchada.hide()
        contenido.addWidget(self.hinchada)

        # ---- metas de la temporada (se siguen con la partida) ----
        self.metas = Tarjeta("Metas de la temporada")
        self.metas.cuerpo.addWidget(texto_suave(
            "Proponete metas: se siguen solas con tu partida, la prensa te pregunta por ellas y "
            "cumplirlas (o no) mueve tu reputacion."
        ))
        self.metas_layout = QVBoxLayout()
        self.metas_layout.setSpacing(8)
        self.metas.cuerpo.addLayout(self.metas_layout)
        self.meta_tipo = QComboBox()
        for tipo, (rotulo, _) in TIPOS.items():
            self.meta_tipo.addItem(rotulo, tipo)
        self.meta_objetivo = QSpinBox()
        self.meta_objetivo.setRange(1, 300)
        self.meta_objetivo.setValue(20)
        self.meta_tipo.currentIndexChanged.connect(self._on_tipo_meta)
        self.meta_agregar_btn = boton("Agregar meta", icono_nombre="mas")
        self.meta_agregar_btn.clicked.connect(self._on_agregar_meta)
        self.metas.cuerpo.addLayout(fila(self.meta_tipo, self.meta_objetivo, self.meta_agregar_btn, None))
        self.metas.hide()
        contenido.addWidget(self.metas)

        # ---- la carrera entera, club por club (de la partida) ----
        self.carrera_completa = Tarjeta("Tu carrera en FC 26")
        self.carrera_label = QLabel()
        self.carrera_label.setWordWrap(True)
        self.carrera_completa.cuerpo.addWidget(self.carrera_label)
        self.carrera_completa.hide()
        contenido.addWidget(self.carrera_completa)

        # ---- premios de verdad (jugador del mes, campeon...) ----
        self.vitrina = Tarjeta("Vitrina")
        self.vitrina_layout = QVBoxLayout()
        self.vitrina_layout.setSpacing(6)
        self.vitrina.cuerpo.addLayout(self.vitrina_layout)
        self.vitrina.hide()
        contenido.addWidget(self.vitrina)

        # ---- las temporadas que ya terminaron ----
        self.trayectoria = Tarjeta("Trayectoria")
        self.trayectoria_grilla = QGridLayout()
        self.trayectoria_grilla.setHorizontalSpacing(18)
        self.trayectoria_grilla.setVerticalSpacing(6)
        self.trayectoria.cuerpo.addLayout(self.trayectoria_grilla)
        self.trayectoria.hide()
        contenido.addWidget(self.trayectoria)

        self.tramas = Tarjeta("Tramas abiertas")
        self.tramas_layout = QVBoxLayout()
        self.tramas_layout.setSpacing(6)
        self.tramas.cuerpo.addLayout(self.tramas_layout)
        contenido.addWidget(self.tramas)

        noticias = Tarjeta("Central de noticias", espaciado=8)
        self.noticias_layout = QVBoxLayout()
        self.noticias_layout.setSpacing(8)
        noticias.cuerpo.addLayout(self.noticias_layout)
        contenido.addWidget(noticias)

        layout.addWidget(self.contenido)
        layout.addStretch()

    def actualizar(self):
        perfil = load_latest_profile()
        self.vacio.setVisible(perfil is None)
        self.contenido.setVisible(perfil is not None)
        self.crear_btn.setVisible(perfil is not None)

        if perfil is None:
            self.titulo_label.setText("BIENVENIDO")
            self.stats_label.setText("Todavia no creaste ningun personaje.")
            return

        self._perfil = perfil
        reputacion = get_reputacion_actual(perfil.id)
        seguidores = get_seguidores(perfil.id)
        club = perfil.club_actual or "sin club definido"
        carrera = calcular_estadisticas_acumuladas(load_match_interviews(perfil.id))

        self.titulo_label.setText(esc(perfil.nombre_jugador.upper()))
        self.stats_label.setText(
            f"<b>{esc(club)}</b> · Reputacion {reputacion}/100 · {miles(seguidores)} seguidores en Instagram"
        )

        # Mientras no se lea la partida (o si no hay), los numeros son los de
        # los partidos registrados en la app.
        self._mostrar_numeros(
            perfil, reputacion, seguidores,
            partidos=carrera["partidos_jugados"], goles=carrera["goles_totales"],
            asistencias=carrera["asistencias_totales"], figura=carrera["figuras"],
            nota=carrera["rating_promedio"] if carrera["partidos_jugados"] else None,
        )
        self.carta.setToolTip(
            f"Carta {nivel_carta(reputacion).nombre.lower()}: el color sube con la reputacion "
            "(bronce, plata desde 45, oro desde 70, elite desde 85)."
        )
        if not self._leyendo_temporada:
            self._leyendo_temporada = True
            ejecutar_en_hilo(
                resumen_temporada, get_metas(perfil.id), al_completar=self._on_temporada, al_fallar=self._on_temporada_error
            )

        self.backstory_label.setText(esc(perfil.backstory_generado) or "(sin historia todavia)")

        limpiar_layout(self.tramas_layout)
        for gancho in perfil.ganchos_narrativos:
            trama = QLabel(f"<span style='color:{estilos.ACENTO}'>▸</span>&nbsp; {esc(gancho)}")
            trama.setWordWrap(True)
            self.tramas_layout.addWidget(trama)
        self.tramas.setVisible(bool(perfil.ganchos_narrativos))

        self._mostrar_hinchada()
        estado_prensa = get_estado_prensa(perfil.id)
        self._cargar_vitrina(estado_prensa)
        self._cargar_trayectoria(estado_prensa)
        self._cargar_noticias(perfil)

    # ---- la hinchada ----

    def actualizar_hinchada(self, carrera):
        """Con cada guardado: los partidos nuevos mueven el carino, un
        traspaso es noticia y, si la historia lo pide, aparece una decision."""
        perfil = load_latest_profile()
        if perfil is None or carrera is None:
            return
        antes = get_estado_clubes(perfil.id)
        estado, hitos = clubes.actualizar(antes, carrera, get_reputacion_actual(perfil.id))
        set_estado_clubes(perfil.id, estado)
        for hito in hitos:
            self._contar(perfil, hito, carrera.fecha_actual().isoformat())
        nueva = estado.get("decision")
        if nueva and nueva != antes.get("decision"):
            self.decision_pendiente.emit(clubes.decision_pendiente(estado)[0].titulo.format(
                club=estado["clubes"][nueva["club"]]["nombre"]))
        self._mostrar_hinchada()

    def _contar(self, perfil, hito, fecha: str):
        """Aplica lo que mueve (reputacion, seguidores) y lanza la noticia."""
        seguidores = round(_escala(get_seguidores(perfil.id), get_reputacion_actual(perfil.id)) * hito.seguidores)
        sumar_reputacion_y_seguidores(perfil.id, hito.reputacion, seguidores, motivo=hito.titulo)
        if hito.reputacion:
            self.reputacion_cambiada.emit()
        ejecutar_en_hilo(
            eventos.contar, perfil, hito.titulo, f"{perfil.nombre_jugador} {hito.descripcion}", hito.tono, seguidores,
            fecha, f"hinchada:{hito.tipo}", "hinchada",
            al_completar=self._on_contado, al_fallar=lambda _mensaje: None,
        )
        return seguidores

    def _on_contado(self, resultado):
        noticia, actividad = resultado
        save_noticia_prensa(noticia)
        save_actividad_instagram(actividad)
        if self._perfil is not None:
            self._cargar_noticias(self._perfil)

    def _mostrar_hinchada(self):
        perfil = self._perfil or load_latest_profile()
        estado = get_estado_clubes(perfil.id) if perfil is not None else {}
        if not estado.get("actual"):
            self.hinchada.hide()
            return
        club = estado["clubes"][estado["actual"]]
        self.hinchada_label.setText(
            f"<b>{esc(club['nombre'])}</b> · {clubes.rotulo(club['carino'])} "
            f"<span style='color:{estilos.TEXTO_SUAVE}'>({club['carino']}/100)</span>"
        )
        self.hinchada_barra.setValue(club["carino"])
        color = estilos.NEGATIVO if club["carino"] < clubes.EN_CONTRA else estilos.MIXTO if club["carino"] < 45 else estilos.ACENTO
        self.hinchada_barra.setStyleSheet(f"QProgressBar::chunk {{ background-color: {color}; border-radius: 3px; }}")
        limpiar_layout(self.decision_botones)
        pendiente = clubes.decision_pendiente(estado)
        if pendiente is not None:
            decision, nombre_club = pendiente
            self.decision_label.setText(
                f"<span style='color:{estilos.ACENTO}'>Tenes que decidir</span><br>"
                f"<b>{esc(decision.titulo.format(club=nombre_club))}</b><br>{esc(decision.pregunta.format(club=nombre_club))}"
            )
            for i, opcion in enumerate(decision.opciones):
                eleccion = boton(opcion.texto, primario=i == 0)
                eleccion.setProperty("opcion", opcion.id)
                eleccion.clicked.connect(lambda _=False, o=opcion.id: self.elegir(o))
                self.decision_botones.addWidget(eleccion)
            self.decision_botones.addStretch()
        self.decision.setVisible(pendiente is not None)
        antes = [c for clave, c in estado["clubes"].items() if clave != estado["actual"] and c.get("hasta")]
        como = {"idolo": "se fue como idolo", "mala": "se fue por la puerta de atras", "normal": "se fue"}
        self.hinchada_antes.setText(
            "Antes: " + " · ".join(f"{esc(c['nombre'])} ({clubes.rotulo(c['carino']).lower()}, "
                                   f"{como.get(c.get('salida'), 'se fue')})" for c in antes) if antes else
            "El carino de los hinchas sube con tus goles y las victorias, y baja con las derrotas y las polemicas."
        )
        self.hinchada.show()

    def elegir(self, opcion_id: str):
        perfil = self._perfil or load_latest_profile()
        estado = get_estado_clubes(perfil.id) if perfil is not None else {}
        if perfil is None or not estado.get("decision"):
            return
        from datetime import date

        fecha = date.fromisoformat(estado["hasta"]) if estado.get("hasta") else date.today()
        estado, hito, carino = clubes.elegir(estado, opcion_id, fecha)
        set_estado_clubes(perfil.id, estado)
        seguidores = self._contar(perfil, hito, fecha.isoformat())
        partes = [f"<b>Elegiste: {esc(hito.titulo)}</b>", f"carino {'+' if carino >= 0 else ''}{carino}"]
        if hito.reputacion:
            partes.append(f"reputacion {'+' if hito.reputacion > 0 else ''}{hito.reputacion}")
        if seguidores:
            partes.append(f"{'+' if seguidores > 0 else ''}{miles(seguidores)} seguidores")
        texto = " · ".join(partes)
        if hito.reto:
            texto += f"<br><span style='color:{estilos.ACENTO}'>Reto:</span> {esc(hito.reto)}"
        texto += f"<br><span style='color:{estilos.TEXTO_SUAVE}'>La prensa ya se entero...</span>"
        self.eleccion_label.setText(texto)
        self.eleccion_label.show()
        self._mostrar_hinchada()

    def _cargar_trayectoria(self, estado_prensa: dict):
        limpiar_layout(self.trayectoria_grilla)
        temporadas = estado_prensa.get("trayectoria", [])
        if temporadas:
            for columna, rotulo in enumerate(("Temporada", "Club", "PJ", "Goles", "Asist.", "Nota", "Liga", "Titulos")):
                self.trayectoria_grilla.addWidget(etiqueta_campo(rotulo), 0, columna)
        for fila_n, t in enumerate(reversed(temporadas), start=1):  # la ultima arriba
            liga = f"{t['posicion']}° {t['liga']}" if t.get("posicion") else "-"
            valores = (
                t["temporada"], t["club"], t["partidos"], t["goles"], t["asistencias"],
                t["nota"] if t.get("nota") is not None else "-", liga, ", ".join(t.get("titulos", [])) or "-",
            )
            for columna, valor in enumerate(valores):
                celda = QLabel(esc(valor))
                if columna == 0:
                    celda.setStyleSheet(f"color: {estilos.ACENTO}; font-weight: 700;")
                self.trayectoria_grilla.addWidget(celda, fila_n, columna)
        self.trayectoria_grilla.setColumnStretch(7, 1)
        self.trayectoria.setVisible(bool(temporadas))

    def _mostrar_carrera(self, etapas: list):
        if not etapas:
            self.carrera_completa.hide()
            return
        suave = estilos.TEXTO_SUAVE
        total = {k: sum(e[k] for e in etapas) for k in ("partidos", "ganados", "empatados", "perdidos", "goles",
                                                         "asistencias", "amarillas")}
        semana = sum(e["premios"].get("equipo_de_la_semana", 0) for e in etapas)
        figura = sum(e.get("figura", 0) for e in etapas)
        mes = sum(e["premios"].get("jugador_del_mes", 0) for e in etapas)
        titulos = [t for e in etapas for t in e["titulos"]]
        lineas = [
            f"<b>{len(etapas)} club{'es' if len(etapas) > 1 else ''}</b> · {total['partidos']} PJ "
            f"({total['ganados']}G {total['empatados']}E {total['perdidos']}P) · <b>{total['goles']} goles</b> · "
            f"{total['asistencias']} asistencias · {total['amarillas']} amarillas",
            f"Titulos: <b>{len(titulos)}</b>" + (f" ({esc(', '.join(titulos))})" if titulos else "")
            + f" · Futbolista del partido: <b>{figura}</b> · Equipo de la semana: <b>{semana}</b> · "
              f"Jugador del mes: <b>{mes}</b>",
        ]
        for e in etapas:
            nota = f" · nota {e['nota']:.1f}" if e.get("nota") else ""
            lineas.append(
                f"<span style='color:{estilos.ACENTO}'>▸</span> <b>{esc(e['club'])}</b>"
                f"<span style='color:{suave}'> ({esc(e['liga'])})</span>: {e['partidos']} PJ, {e['goles']} goles, "
                f"{e['asistencias']} asist.{nota}"
                + (f" · <span style='color:{estilos.MIXTO}'>★ {esc(', '.join(e['titulos']))}</span>" if e["titulos"] else "")
                + f"<span style='color:{suave}'> · figura {e.get('figura', 0)}, "
                  f"equipo de la semana {e['premios'].get('equipo_de_la_semana', 0)}, "
                  f"jugador del mes {e['premios'].get('jugador_del_mes', 0)}</span>"
            )
        self.carrera_label.setText("<br>".join(lineas))
        self.carrera_completa.show()

    def _cargar_vitrina(self, estado_prensa: dict):
        limpiar_layout(self.vitrina_layout)
        premios = estado_prensa.get("vitrina", [])
        for premio in reversed(premios):  # el mas nuevo arriba
            linea = QLabel(
                f"<span style='color:{estilos.MIXTO}'>★</span>&nbsp; <b>{esc(premio['premio'])}</b> · "
                f"<span style='color:{estilos.TEXTO_SUAVE}'>{esc(premio['detalle'])} ({esc(premio.get('temporada', ''))})</span>"
            )
            linea.setWordWrap(True)
            self.vitrina_layout.addWidget(linea)
        self.vitrina.setVisible(bool(premios))

    def _mostrar_numeros(self, perfil, reputacion, seguidores, partidos, goles, asistencias, figura, nota):
        rating = f"{nota:.1f}" if nota is not None else "-"
        self.carta.mostrar(
            perfil.nombre_jugador,
            perfil.club_actual,
            reputacion,
            [
                ("PJ", str(partidos)),
                ("GOL", str(goles)),
                ("AST", str(asistencias)),
                ("RAT", rating),
                ("FIG", str(figura)),
                ("SEG", compacto(seguidores)),
            ],
        )
        self.mosaicos["partidos"].poner(partidos)
        self.mosaicos["goles"].poner(goles)
        self.mosaicos["asistencias"].poner(asistencias)
        self.mosaicos["rating"].poner(rating)
        self.mosaicos["figuras"].poner(figura)
        self.mosaicos["seguidores"].poner(miles(seguidores))

    def _on_temporada(self, resumen):
        self._leyendo_temporada = False
        if resumen is None or self._perfil is None:
            self.temporada.hide()
            self.metas.hide()  # sin partida no hay con que seguirlas
            return
        self._temporada_actual = resumen.temporada
        self._mostrar_carrera(resumen.etapas)
        self._mostrar_metas(resumen.progreso_metas)
        perfil = self._perfil
        if resumen.club != perfil.club_actual:
            # el club de la partida es el de verdad (cambia con los traspasos)
            actualizar_club(perfil.id, resumen.club)
            perfil.club_actual = resumen.club
            if self._on_club_cambiado:
                self._on_club_cambiado()
            self.stats_label.setText(
                f"<b>{esc(resumen.club)}</b> · Reputacion {get_reputacion_actual(perfil.id)}/100 · "
                f"{miles(get_seguidores(perfil.id))} seguidores en Instagram"
            )
        totales = resumen.totales
        self._mostrar_numeros(
            perfil, get_reputacion_actual(perfil.id), get_seguidores(perfil.id),
            partidos=totales["partidos"], goles=totales["goles"], asistencias=totales["asistencias"],
            figura=totales["figura"], nota=totales["nota"],
        )
        self.carta.setToolTip(self.carta.toolTip() + "\nNumeros de tu partida de FC 26.")
        self.temporada_label.setText(
            f"<b>{esc(resumen.club)}</b> · {esc(resumen.posicion) or 'sin liga'} · "
            f"partida \"{esc(resumen.partida)}\" al {resumen.fecha}"
        )
        limpiar_layout(self.temporada_competiciones)
        for nombre, partidos, goles, asistencias, nota in resumen.por_competicion:
            linea = QLabel(
                f"<span style='color:{estilos.ACENTO}'>▸</span>&nbsp; <b>{esc(nombre)}</b> · {partidos} PJ · "
                f"{goles} goles · {asistencias} asist." + (f" · nota {nota}" if nota is not None else "")
            )
            self.temporada_competiciones.addWidget(linea)
        limpiar_layout(self.temporada_ultimos)
        colores = {"G": estilos.POSITIVO, "E": estilos.MIXTO, "P": estilos.NEGATIVO}
        for letra, marcador_texto, competicion in resumen.ultimos:
            ficha = chip(letra, colores[letra])
            ficha.setToolTip(f"{marcador_texto} ({competicion})")
            self.temporada_ultimos.addWidget(ficha)
        if resumen.ultimos:
            ultimo = texto_suave(f"Ultimo: {esc(resumen.ultimos[-1][1])}", ajustar=False)
            self.temporada_ultimos.addWidget(ultimo)
        self.temporada_ultimos.addStretch()
        self.temporada_proximo.setText(f"Proximo partido: {esc(resumen.proximo)}" if resumen.proximo else "")
        self.temporada.show()

    def _on_temporada_error(self, _mensaje: str):
        # sin la partida el Resumen funciona igual, con los numeros de la app
        self._leyendo_temporada = False
        self.temporada.hide()
        self.metas.hide()

    # ---- metas ----

    def _on_tipo_meta(self):
        # un puesto en la tabla se pide chico; goles o asistencias, mas grande
        self.meta_objetivo.setValue(4 if self.meta_tipo.currentData() == "top_liga" else 20)

    def _on_agregar_meta(self):
        if self._perfil is None or not self._temporada_actual:
            return
        agregar_meta(self._perfil.id, nueva_meta(self.meta_tipo.currentData(), self.meta_objetivo.value(), self._temporada_actual))
        self.actualizar()

    def _on_quitar_meta(self, meta_id: str):
        if self._perfil is not None:
            quitar_meta(self._perfil.id, meta_id)
            self.actualizar()

    def _mostrar_metas(self, progreso: dict):
        limpiar_layout(self.metas_layout)
        estados = {
            "en_curso": ("En curso", estilos.SECUNDARIO),
            "cumplida": ("Cumplida", estilos.POSITIVO),
            "fallida": ("Fallida", estilos.NEGATIVO),
        }
        for meta in get_metas(self._perfil.id):
            if meta["temporada"] != self._temporada_actual:
                continue
            actual = progreso.get(meta["id"], meta.get("actual"))
            estado = meta["estado"]
            if estado == "en_curso" and meta["tipo"] in CONTABLES and actual is not None and actual >= meta["objetivo"]:
                estado = "cumplida"  # ya se llego: la prensa lo hace oficial en la proxima revision
            rotulo, color = estados.get(estado, estados["en_curso"])
            partes = [chip(rotulo, color), QLabel(esc(texto_meta(meta))), None]
            if meta["tipo"] == "top_liga":
                if actual:
                    partes.append(texto_suave(f"va {actual}°", ajustar=False))
            elif actual is not None:
                barra = QProgressBar()
                barra.setRange(0, meta["objetivo"])
                barra.setValue(min(actual, meta["objetivo"]))
                barra.setTextVisible(False)
                barra.setFixedWidth(160)
                partes += [barra, texto_suave(f"{actual}/{meta['objetivo']}", ajustar=False)]
            if estado == "en_curso":
                quitar = QPushButton("✕")
                quitar.setObjectName("quitarMeta")
                quitar.setFixedSize(28, 28)
                quitar.setToolTip("Quitar esta meta")
                quitar.setStyleSheet("QPushButton#quitarMeta { padding: 0; font-size: 13px; }")
                quitar.clicked.connect(lambda _=False, i=meta["id"]: self._on_quitar_meta(i))
                partes.append(quitar)
            self.metas_layout.addLayout(fila(*partes, espaciado=10))
        self.metas.show()

    def _cargar_noticias(self, perfil):
        limpiar_layout(self.noticias_layout)
        noticias = load_noticias_prensa(perfil.id, limite=NOTICIAS_EN_RESUMEN)
        if not noticias:
            self.noticias_layout.addWidget(
                texto_suave("Todavia no hay noticias. Salen solas despues de las entrevistas.")
            )
        for i, noticia in enumerate(noticias):
            if i:
                self.noticias_layout.addSpacing(6)
                self.noticias_layout.addWidget(separador())
                self.noticias_layout.addSpacing(6)
            agregar_noticia(self.noticias_layout, noticia)


class MainMenuWindow(QMainWindow):
    PAGINA_RESUMEN, PAGINA_TEMPORADA, PAGINA_ENTREVISTAS, PAGINA_INSTAGRAM, PAGINA_VIDA = range(5)

    def __init__(self, pagina_inicial: int = 0):
        super().__init__()
        from roleplay import carreras

        carrera = carreras.actual()
        self.setWindowTitle("EAFC 26 Roleplay" + ("" if carrera["id"] == carreras.PRINCIPAL else f" - {carrera['nombre']}"))
        self.setMinimumSize(1100, 720)

        # ---- barra lateral ----
        lateral = QFrame()
        lateral.setObjectName("lateral")
        lateral.setFixedWidth(230)
        lateral_layout = QVBoxLayout(lateral)
        lateral_layout.setContentsMargins(0, 30, 0, 24)
        lateral_layout.setSpacing(4)

        marca = QLabel("EAFC 26")
        marca.setFont(fuente_titulo(15, 4))
        marca.setStyleSheet(f"color: {estilos.ACENTO}; padding-left: 24px;")
        lateral_layout.addWidget(marca)
        nombre_app = QLabel("ROLEPLAY")
        nombre_app.setFont(fuente_titulo(36, 1.5))
        nombre_app.setStyleSheet("padding-left: 22px;")
        lateral_layout.addWidget(nombre_app)
        lateral_layout.addSpacing(28)

        # ---- paginas: (texto, icono, pagina) ----
        self.pagina_resumen = PaginaResumen(self._abrir_wizard_personaje, self._refrescar_jugador)
        self.pagina_temporada = PaginaTemporada()
        self.pagina_entrevistas = InterviewWindow()
        self.pagina_instagram = InstagramWindow()
        self.pagina_vida = PaginaVida()
        self.pagina_vida.compra_hecha.connect(self._refrescar_jugador)
        self.pagina_vida.auto_entregado.connect(self._on_auto_entregado)
        self.pagina_vida.evento_inesperado.connect(self._on_evento_inesperado)
        self.pagina_resumen.decision_pendiente.connect(self._on_decision_pendiente)
        self.pagina_vida.decision_pendiente.connect(lambda titulo: self._on_decision_pendiente(titulo, "Vida"))
        self.pagina_resumen.reputacion_cambiada.connect(self._refrescar_jugador)
        self._paginas = [
            ("Resumen", "inicio", self.pagina_resumen),
            ("Temporada", "trofeo", self.pagina_temporada),
            ("Entrevistas", "microfono", self.pagina_entrevistas),
            ("Instagram", "camara", self.pagina_instagram),
            ("Vida", "billetera", self.pagina_vida),
        ]

        self.stack = QStackedWidget()
        self._botones_nav: list[QPushButton] = []
        for indice, (texto, nombre_icono, pagina) in enumerate(self._paginas):
            self.stack.addWidget(con_scroll(pagina))
            boton_nav = QPushButton(f"  {texto.upper()}")
            boton_nav.setObjectName("navBtn")
            boton_nav.setCheckable(True)
            boton_nav.setIcon(icono(nombre_icono, estilos.TEXTO_SUAVE, estilos.TEXTO))
            boton_nav.setIconSize(QSize(20, 20))
            boton_nav.setCursor(Qt.CursorShape.PointingHandCursor)
            boton_nav.clicked.connect(lambda _=False, i=indice: self._ir_a(i))
            lateral_layout.addWidget(boton_nav)
            self._botones_nav.append(boton_nav)

        lateral_layout.addStretch()

        self.jugar_btn = boton("Jugar FC 26", primario=True, icono_nombre="jugar")
        self.jugar_btn.setToolTip("Abre EA FC 26 por su plataforma (Steam, EA app o Epic), sin modificarlo")
        self.jugar_btn.clicked.connect(lambda: abrir_juego_o_preguntar(self._padre()))
        self.ajustes_btn = QPushButton("  AJUSTES")
        self.ajustes_btn.setObjectName("navBtn")
        self.ajustes_btn.setIcon(icono("engranaje", estilos.TEXTO_SUAVE))
        self.ajustes_btn.setIconSize(QSize(20, 20))
        self.ajustes_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.ajustes_btn.clicked.connect(self._abrir_ajustes)
        envoltura_jugar = QHBoxLayout()
        envoltura_jugar.setContentsMargins(18, 0, 18, 6)
        envoltura_jugar.addWidget(self.jugar_btn)
        lateral_layout.addLayout(envoltura_jugar)
        lateral_layout.addWidget(self.ajustes_btn)
        lateral_layout.addSpacing(14)

        self.jugador_label = QLabel()
        self.jugador_label.setWordWrap(True)
        self.jugador_label.setStyleSheet(f"color: {estilos.TEXTO_SUAVE}; padding: 0px 24px;")
        lateral_layout.addWidget(self.jugador_label)

        fondo = FondoEstadio()
        fondo_layout = QVBoxLayout(fondo)
        fondo_layout.setContentsMargins(0, 0, 0, 0)
        fondo_layout.addWidget(self.stack)

        contenedor = QWidget()
        layout_principal = QHBoxLayout(contenedor)
        layout_principal.setContentsMargins(0, 0, 0, 0)
        layout_principal.setSpacing(0)
        layout_principal.addWidget(lateral)
        layout_principal.addWidget(fondo, 1)

        # ---- la barra del overlay completo (solo encima del juego) ----
        self.barra_overlay = QFrame()
        self.barra_overlay.setObjectName("barraOverlay")
        self.barra_overlay.setStyleSheet(
            f"QFrame#barraOverlay {{ background-color: {estilos.ACENTO}; }} "
            f"QFrame#barraOverlay QLabel {{ color: {estilos.FONDO}; font-weight: 700; }}"
        )
        barra = QHBoxLayout(self.barra_overlay)
        barra.setContentsMargins(18, 6, 12, 6)
        barra.addWidget(QLabel(f"EAFC 26 ROLEPLAY · OVERLAY  —  {ATAJO_TEXTO} o ESC para volver al juego"))
        barra.addStretch()
        self.volver_al_juego_btn = boton("Volver al juego")
        barra.addWidget(self.volver_al_juego_btn)
        self.barra_overlay.hide()
        raiz = QWidget()
        layout_raiz = QVBoxLayout(raiz)
        layout_raiz.setContentsMargins(0, 0, 0, 0)
        layout_raiz.setSpacing(0)
        layout_raiz.addWidget(self.barra_overlay)
        layout_raiz.addWidget(contenedor, 1)
        self.setCentralWidget(raiz)

        # ---- sala flotante (encima del juego) y su atajo global ----
        self.sala_flotante = SalaFlotante(self.pagina_entrevistas)
        # el overlay completo (como Overwolf): la app entera encima del juego (ui/overlay_completo.py)
        self.overlay = OverlayCompleto(self)
        self.overlay.cambio.connect(self._on_overlay)
        self.volver_al_juego_btn.clicked.connect(self._on_volver_al_juego)
        self.mando = MandoOverlay(self, self.overlay)  # el mando de PS5/Xbox con el overlay abierto
        self.atajo = AtajoGlobal(self)
        if self.atajo.registrar():  # overlay completo (o la sala flotante, segun Ajustes)
            self.atajo.presionado.connect(self._on_atajo)
        else:
            self.sala_flotante.click_a_traves = False  # sin atajo no habria como volver a usarla

        # ---- modo en vivo: avisos de partidos nuevos ----
        self.bandeja = None
        if QSystemTrayIcon.isSystemTrayAvailable():
            self.bandeja = QSystemTrayIcon(QIcon(str(config.ICONO_APP)), self)
            self.bandeja.setToolTip("EAFC 26 Roleplay")
            self.bandeja.messageClicked.connect(self._abrir_sala_de_prensa)
            self.bandeja.activated.connect(self._on_bandeja_activada)
            menu = QMenu(self)
            for texto, accion in (
                (f"Overlay ({ATAJO_TEXTO})", self.overlay.alternar),
                ("Sala flotante", self.sala_flotante.alternar),
                ("Abrir la app", self._traer_al_frente),
                ("Salir", QApplication.quit),
            ):
                item = QAction(texto, menu)
                item.triggered.connect(accion)
                menu.addAction(item)
            self.bandeja.setContextMenu(menu)
            self.bandeja.show()
        self.vigilante = VigilantePartida(self)
        self.vigilante.partido_nuevo.connect(self._on_partido_nuevo)
        self.vigilante.dia_nuevo.connect(self._on_dia_nuevo)
        self.pagina_entrevistas.noticias_publicadas.connect(self._on_noticias_publicadas)
        self.vigilante.partida_actualizada.connect(self._on_partida_actualizada)
        self.vigilante.iniciar()

        self._ir_a(pagina_inicial)

    # ---- el overlay ----

    def _on_volver_al_juego(self):
        anotar_overlay("boton VOLVER AL JUEGO")
        self.overlay.cerrar()

    def _on_atajo(self):
        anotar_overlay("atajo")
        if configuracion_overlay()["modo"] == "sala":
            self.sala_flotante.atajo_presionado()
        else:
            self.overlay.alternar()

    def _on_overlay(self, abierto: bool):
        self.barra_overlay.setVisible(abierto)
        if abierto:
            if self.sala_flotante.isVisible():
                self.sala_flotante.hide()  # el overlay ya muestra todo
            self._paginas[self.stack.currentIndex()][2].actualizar()

    def cambiar_seccion(self, paso: int):
        """L1 / R1 del mando: la seccion anterior o la siguiente del menu."""
        self._ir_a((self.stack.currentIndex() + paso) % len(self._paginas))

    def _ir_a(self, indice: int):
        if indice == self.PAGINA_ENTREVISTAS:
            self._marcar_entrevistas(False)
        self.stack.setCurrentIndex(indice)
        for i, boton_nav in enumerate(self._botones_nav):
            boton_nav.setChecked(i == indice)
        self._paginas[indice][2].actualizar()
        self._refrescar_jugador()

    def _refrescar_jugador(self):
        perfil = load_latest_profile()
        if perfil is None:
            self.jugador_label.setText("Sin personaje")
            return
        reputacion = get_reputacion_actual(perfil.id)
        self.jugador_label.setText(
            f"<span style='color:{estilos.TEXTO}'><b>{esc(perfil.nombre_jugador)}</b></span><br>"
            f"{esc(perfil.club_actual or 'Sin club')} · REP {reputacion} · {nivel_carta(reputacion).nombre}"
        )

    # ---- modo en vivo ----

    def _marcar_entrevistas(self, pendiente: bool):
        texto = self._paginas[self.PAGINA_ENTREVISTAS][0].upper()
        self._botones_nav[self.PAGINA_ENTREVISTAS].setText(f"  {texto}" + ("   ●" if pendiente else ""))

    def _on_bandeja_activada(self, motivo):
        if motivo == QSystemTrayIcon.ActivationReason.Trigger:  # click izquierdo
            self._traer_al_frente()

    def closeEvent(self, evento):
        if self.overlay.abierto:  # cerrar la ventana en el overlay = volver al juego (la app sigue en la bandeja)
            anotar_overlay("cerrar la ventana")
            evento.ignore()
            self.overlay.cerrar()
            return
        self.atajo.liberar()
        self.sala_flotante.close()
        if self.bandeja is not None:
            self.bandeja.hide()
        super().closeEvent(evento)

    def _padre(self):
        """Para los dialogos: la capa del overlay si esta abierto (si no, quedarian debajo)."""
        return self.overlay.capa if self.overlay.abierto else self

    def _en_la_app(self) -> bool:
        """El usuario esta mirando la app: la ventana de siempre o el overlay."""
        return self.isActiveWindow() or (self.overlay.abierto and self.overlay.capa.isActiveWindow())

    def _traer_al_frente(self):
        """La ventana de siempre al frente (la bandeja, el icono del escritorio): si
        el overlay estaba abierto, primero se cierra (si no, quedaba a medias: la
        ventana normal con la barra del overlay)."""
        if self.overlay.abierto:
            self.overlay.cerrar(devolver_foco=False)
        self.showNormal()
        self.raise_()
        self.activateWindow()
        _poner_al_frente(int(self.winId()))

    def traer_desde_otra(self):
        """Alguien quiso abrir la app de nuevo: se muestra esta (ui/instancia.py)."""
        self._traer_al_frente()

    def _abrir_sala_de_prensa(self):
        self._traer_al_frente()
        self._ir_a(self.PAGINA_ENTREVISTAS)

    def _on_partido_nuevo(self, lectura):
        sala = self.pagina_entrevistas
        cargado = sala.recibir_partido_nuevo(lectura, preparar_entrevista_sola())
        if sala.perfil is not None:
            sala._iniciar_revision_prensa(manual=False)  # la prensa reacciona al partido
        if self.stack.currentIndex() != self.PAGINA_ENTREVISTAS:
            self._marcar_entrevistas(True)
        mensaje = lectura.ultimo.resumen + (". Tu entrevista te espera." if cargado else ".")
        if mostrar_flotante_sola():
            self.sala_flotante.mostrar()  # encima del juego (HUD), sin quitarle el foco
            self.sala_flotante.avisar("Partido nuevo", mensaje)
        self.pagina_instagram.revisar_hinchada()  # los hinchas reaccionan al partido
        if self.bandeja is not None:
            self.bandeja.showMessage("Partido nuevo", mensaje, QSystemTrayIcon.MessageIcon.Information, 10000)
        QApplication.alert(self)

    def _on_dia_nuevo(self, lectura):
        """El juego avanzo (autoguardado) sin partido del usuario: la prensa
        revisa los hechos reales del mundo y el Instagram se mueve."""
        sala = self.pagina_entrevistas
        sala._on_partida_leida(lectura)  # la sala trabaja con la partida al dia
        if sala.perfil is not None:
            sala._iniciar_revision_prensa(manual=False)
        self.pagina_instagram.revisar_hinchada()
        if self.sala_flotante.isVisible():
            self.sala_flotante.avisar("El juego avanzo", "La prensa revisa lo que paso en la fecha.")

    def _avisar_encima(self, titulo: str, texto: str):
        """Un aviso en el HUD encima del juego (si esta prendido y no estas en la app)."""
        if mostrar_flotante_sola() and not self._en_la_app():
            self.sala_flotante.avisar(titulo, texto)

    def _on_auto_entregado(self, nombre: str):
        self._avisar_encima("Te llego tu auto", nombre)
        if self.bandeja is not None and not self._en_la_app():
            self.bandeja.showMessage(
                "Te llego tu auto", f"{nombre}: la prensa y tus hinchas ya lo vieron.",
                QSystemTrayIcon.MessageIcon.Information, 8000,
            )

    def _on_evento_inesperado(self, titulo: str, reto: str):
        self._avisar_encima("Algo te paso", titulo + (f". Reto: {reto}" if reto else ""))
        if self.bandeja is not None and not self._en_la_app():
            self.bandeja.showMessage(
                "Algo te paso", titulo + (f". Reto: {reto}" if reto else ". Mira la pagina Vida."),
                QSystemTrayIcon.MessageIcon.Information, 10000,
            )

    def _on_decision_pendiente(self, titulo: str, pagina: str = "Resumen"):
        if self.bandeja is not None and not self._en_la_app():
            self.bandeja.showMessage(
                "Tenes que decidir algo", f"{titulo}. Contestalo en {pagina}.",
                QSystemTrayIcon.MessageIcon.Information, 10000,
            )

    def _on_noticias_publicadas(self, noticias: list, manual: bool):
        self.pagina_instagram.revisar_hinchada()  # los hinchas reaccionan a las noticias
        if manual or self.bandeja is None or self._en_la_app():
            return
        principal = next((n for n in noticias if n.categoria == "jugador"), noticias[0])
        self._avisar_encima("Prensa", principal.titular)
        self.bandeja.showMessage("Prensa", principal.titular, QSystemTrayIcon.MessageIcon.Information, 8000)

    def _on_partida_actualizada(self, lectura):
        self.pagina_vida.acreditar_con(lectura.carrera)  # el sueldo se cobra con los dias del juego
        self.pagina_resumen.actualizar_hinchada(lectura.carrera)  # el carino de tu hinchada y las decisiones
        if self.stack.currentIndex() == self.PAGINA_RESUMEN:
            self.pagina_resumen.actualizar()
        elif self.stack.currentIndex() == self.PAGINA_TEMPORADA:
            self.pagina_temporada.actualizar()
        self._refrescar_jugador()

    def _abrir_ajustes(self):
        dialogo = DialogoAjustes(self._padre())
        dialogo.exec()
        dialogo.deleteLater()

    def _abrir_wizard_personaje(self):
        wizard = CharacterWizard(self._padre())
        if wizard.exec():
            self._ir_a(0)
        wizard.deleteLater()
