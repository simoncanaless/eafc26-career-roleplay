"""
Instagram del jugador: vos escribis el post y Gemini genera los
comentarios, los likes y cuanto suben o bajan tus seguidores.

Y se mueve solo (servicios/hinchada.py): con la partida de FC 26, los
hinchas reaccionan a tus partidos y a las noticias sobre vos aunque no
publiques nada. Lo dispara el modo en vivo en cada autoguardado
(revisar_hinchada) y tambien abrir esta pagina.
"""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QMessageBox, QTextEdit, QVBoxLayout, QWidget

from roleplay.database import (
    get_reputacion_actual,
    get_seguidores,
    load_actividad_instagram,
    load_instagram_posts,
    load_latest_profile,
    load_match_interviews,
    save_actividad_instagram,
    save_instagram_post,
    set_estado_hinchada,
    sumar_seguidores,
)
from roleplay.models import InstagramPost, PlayerProfile
from roleplay.servicios import hinchada
from roleplay.servicios.instagram import generar_reaccion_post, sugerir_post
from roleplay.servicios.partida_real import leer_para_entrevista
from roleplay.ui import estilos
from roleplay.ui.comun import ejecutar_en_hilo, esc, fecha_corta, miles
from roleplay.ui.componentes import (
    Avatar,
    Mosaico,
    Tarjeta,
    boton,
    chip,
    fila,
    limpiar_layout,
    subtitulo,
    texto_suave,
)
from roleplay.ui.estilos import fuente_titulo

TEXTO_PUBLICAR = "Publicar"
POSTS_EN_FEED = 20
ACTIVIDAD_VISIBLE = 8


def _usuario(perfil: PlayerProfile) -> str:
    return "@" + perfil.nombre_jugador.replace(" ", "").lower()


def _crecimiento(numero: int) -> str:
    return f"{'+' if numero >= 0 else ''}{miles(numero)}"


def _comentarios_html(comentarios) -> str:
    """comentarios: dicts {"autor", "texto", "tono"} o ComentarioIA."""
    lineas = []
    for comentario in comentarios:
        autor = comentario["autor"] if isinstance(comentario, dict) else comentario.autor
        texto = comentario["texto"] if isinstance(comentario, dict) else comentario.texto
        lineas.append(f"<b>{esc(autor)}</b>&nbsp; {esc(texto)}")
    return "<br>".join(lineas)


class InstagramWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("EAFC 26 Roleplay - Instagram")

        self.perfil = None
        # (jugador, texto) del post que se esta publicando
        self._publicando: tuple[PlayerProfile, str] | None = None
        self._lectura = None  # la partida de FC 26, si hay (para el contexto real)
        self._leyendo_partida = False
        self._sugiriendo = False
        # los hinchas: una revision a la vez; si se pide otra mientras corre,
        # se hace al terminar (puede haber llegado una noticia nueva)
        self._hinchada_en_curso: int | None = None  # el jugador que se esta revisando
        self._hinchada_pendiente = False

        layout = QVBoxLayout(self)
        layout.setContentsMargins(40, 34, 40, 34)
        layout.setSpacing(18)

        # ---- perfil ----
        perfil_layout = QHBoxLayout()
        perfil_layout.setSpacing(22)
        self.avatar = Avatar(92)
        perfil_layout.addWidget(self.avatar)
        textos = QVBoxLayout()
        textos.setSpacing(2)
        self.header_label = QLabel()
        self.header_label.setFont(fuente_titulo(30, 0.6))
        self.sub_label = subtitulo()
        textos.addStretch()
        textos.addWidget(self.header_label)
        textos.addWidget(self.sub_label)
        textos.addStretch()
        perfil_layout.addLayout(textos, 1)
        self.mosaico_posts = Mosaico("Posts")
        self.mosaico_seguidores = Mosaico("Seguidores")
        self.mosaico_reputacion = Mosaico("Reputacion")
        for mosaico in (self.mosaico_posts, self.mosaico_seguidores, self.mosaico_reputacion):
            mosaico.setFixedWidth(130)
            perfil_layout.addWidget(mosaico)
        layout.addLayout(perfil_layout)

        # ---- nuevo post ----
        nuevo = Tarjeta("Nuevo post")
        self.post_edit = QTextEdit()
        self.post_edit.setPlaceholderText("Ej: Feliz por la victoria de hoy, vamos por mas 💪")
        self.post_edit.setFixedHeight(96)
        nuevo.cuerpo.addWidget(self.post_edit)
        self.publicar_btn = boton(TEXTO_PUBLICAR, primario=True, icono_nombre="enviar")
        self.publicar_btn.clicked.connect(self._on_publicar_clicked)
        self.sugerir_btn = boton("Sugerir post", icono_nombre="chispa")
        self.sugerir_btn.setToolTip("Escribe un post con tu personalidad sobre tu ultimo partido (lo podes editar)")
        self.sugerir_btn.clicked.connect(self._on_sugerir_clicked)
        nuevo.cuerpo.addLayout(
            fila(
                texto_suave("Los comentarios dependen de tu reputacion y de tu temporada.", ajustar=False),
                None, self.sugerir_btn, self.publicar_btn,
            )
        )
        layout.addWidget(nuevo)

        # ---- resultado del ultimo post ----
        self.resultado_tarjeta = Tarjeta("Como le fue a tu post", destacada=True)
        self.resultado_label = QLabel()
        self.resultado_label.setWordWrap(True)
        self.resultado_tarjeta.cuerpo.addWidget(self.resultado_label)
        self.resultado_tarjeta.hide()
        layout.addWidget(self.resultado_tarjeta)

        # ---- lo que pasa sin publicar: los hinchas ----
        self.actividad_tarjeta = Tarjeta("Tus hinchas", espaciado=10)
        self.actividad_tarjeta.cuerpo.addWidget(texto_suave(
            "Reaccionan solos a tus partidos y a las noticias sobre vos, cada vez que el juego guarda."
        ))
        self.actividad_layout = QVBoxLayout()
        self.actividad_layout.setSpacing(12)
        self.actividad_tarjeta.cuerpo.addLayout(self.actividad_layout)
        self.actividad_tarjeta.hide()
        layout.addWidget(self.actividad_tarjeta)

        # ---- feed ----
        feed = Tarjeta("Tu feed", espaciado=12)
        self.feed_layout = QVBoxLayout()
        self.feed_layout.setSpacing(12)
        feed.cuerpo.addLayout(self.feed_layout)
        layout.addWidget(feed)
        layout.addStretch()

        self.actualizar()

    def actualizar(self):
        """Recarga el perfil y refresca la cabecera y el feed."""
        self.perfil = load_latest_profile()

        if self.perfil is None:
            self.header_label.setText("INSTAGRAM")
            self.sub_label.setText("No encontre ningun personaje guardado. Crea uno primero desde el Resumen.")
            self.publicar_btn.setEnabled(False)
            self.sugerir_btn.setEnabled(False)
            limpiar_layout(self.feed_layout)
            return

        self._refrescar_cabecera()
        self.publicar_btn.setEnabled(self._publicando is None)
        self.sugerir_btn.setEnabled(not self._sugiriendo)
        self._cargar_feed()
        self._cargar_actividad()
        self.revisar_hinchada()
        if not self._leyendo_partida:
            self._leyendo_partida = True
            ejecutar_en_hilo(
                leer_para_entrevista, self.perfil.id,
                al_completar=self._on_partida_leida, al_fallar=self._on_partida_error,
            )

    def _on_partida_leida(self, lectura):
        self._leyendo_partida = False
        self._lectura = lectura

    def _on_partida_error(self, _mensaje: str):
        self._leyendo_partida = False  # sin partida, Instagram funciona igual

    def _contexto_real(self) -> str:
        return self._lectura.contexto if self._lectura is not None else ""

    def _ultimo_partido(self) -> str:
        """El ultimo partido, de la partida de FC 26 o de las entrevistas."""
        if self._lectura is not None and self._lectura.ultimo is not None:
            s = self._lectura.ultimo.stats
            return f"{self._lectura.ultimo.resumen}; el marco {s.goles_jugador} goles, nota {s.rating_jugador:.1f}"
        historial = load_match_interviews(self.perfil.id)
        if not historial:
            return ""
        p = historial[0]
        return (
            f"{self.perfil.club_actual or 'su equipo'} {p.goles_equipo}-{p.goles_rival} {p.equipo_rival or 'rival'}; "
            f"el marco {p.goles_jugador} goles, rating {p.rating_jugador:.1f}"
        )

    def _on_sugerir_clicked(self):
        self._sugiriendo = True
        self.sugerir_btn.setEnabled(False)
        self.sugerir_btn.setText("ESCRIBIENDO...")
        ejecutar_en_hilo(
            sugerir_post, self.perfil, self._contexto_real(), self._ultimo_partido(),
            al_completar=self._on_sugerido, al_fallar=self._on_sugerir_error,
        )

    def _terminar_sugerencia(self):
        self._sugiriendo = False
        self.sugerir_btn.setEnabled(self.perfil is not None)
        self.sugerir_btn.setText("SUGERIR POST")

    def _on_sugerido(self, texto: str):
        self._terminar_sugerencia()
        self.post_edit.setPlainText(texto)
        self.post_edit.setFocus()

    def _on_sugerir_error(self, mensaje: str):
        self._terminar_sugerencia()
        QMessageBox.warning(self, "No se pudo sugerir el post", mensaje)

    def _refrescar_cabecera(self):
        reputacion = get_reputacion_actual(self.perfil.id)
        seguidores = get_seguidores(self.perfil.id)
        self.avatar.poner(self.perfil.nombre_jugador)
        self.header_label.setText(esc(_usuario(self.perfil)))
        self.sub_label.setText(
            f"{esc(self.perfil.nombre_jugador)} · {esc(self.perfil.club_actual or 'sin club definido')}"
        )
        self.mosaico_seguidores.poner(miles(seguidores))
        self.mosaico_reputacion.poner(reputacion)

    def _cargar_feed(self):
        posts = load_instagram_posts(self.perfil.id, limite=POSTS_EN_FEED)
        self.mosaico_posts.poner(len(posts) if len(posts) < POSTS_EN_FEED else f"{POSTS_EN_FEED}+")
        limpiar_layout(self.feed_layout)
        if not posts:
            self.feed_layout.addWidget(texto_suave("Todavia no publicaste nada."))
            return

        for post in posts:
            caja = QFrame()
            caja.setObjectName("mosaico")
            caja_layout = QVBoxLayout(caja)
            caja_layout.setContentsMargins(16, 14, 16, 14)
            caja_layout.setSpacing(8)

            color = estilos.POSITIVO if post.crecimiento_seguidores >= 0 else estilos.NEGATIVO
            caja_layout.addLayout(
                fila(
                    chip(f"♥ {miles(post.likes)}", "#FF5A8A"),
                    chip(f"{_crecimiento(post.crecimiento_seguidores)} seguidores", color),
                    None,
                    texto_suave(fecha_corta(post.fecha), ajustar=False),
                )
            )
            texto = QLabel(esc(post.texto))
            texto.setWordWrap(True)
            texto.setFont(fuente_titulo(19, 0.2))
            caja_layout.addWidget(texto)
            if post.comentarios:
                comentarios = texto_suave(_comentarios_html(post.comentarios))
                comentarios.setTextFormat(Qt.TextFormat.RichText)
                caja_layout.addWidget(comentarios)
            self.feed_layout.addWidget(caja)

    def _on_publicar_clicked(self):
        texto = self.post_edit.toPlainText().strip()
        if not texto:
            QMessageBox.information(self, "Post vacio", "Escribi algo antes de publicar.")
            return

        self._publicando = (self.perfil, texto)
        self.publicar_btn.setEnabled(False)
        self.publicar_btn.setText("PUBLICANDO...")

        ejecutar_en_hilo(
            generar_reaccion_post,
            self.perfil,
            texto,
            get_reputacion_actual(self.perfil.id),
            get_seguidores(self.perfil.id),
            self._contexto_real(),
            al_completar=self._on_publicar_completado,
            al_fallar=self._on_publicar_error,
        )

    def _terminar_publicacion(self):
        self._publicando = None
        self.publicar_btn.setEnabled(self.perfil is not None)
        self.publicar_btn.setText(TEXTO_PUBLICAR.upper())

    def _on_publicar_completado(self, resultado):
        perfil, texto = self._publicando
        self._terminar_publicacion()

        nuevo_total = sumar_seguidores(perfil.id, resultado.crecimiento_seguidores)
        save_instagram_post(
            InstagramPost(
                player_id=perfil.id,
                texto=texto,
                likes=resultado.likes_estimados,
                crecimiento_seguidores=resultado.crecimiento_seguidores,
                comentarios=[comentario.model_dump() for comentario in resultado.comentarios],
            )
        )

        self.resultado_label.setText(
            f"<span style='font-size:16px'><b>♥ {miles(resultado.likes_estimados)} likes</b> · "
            f"{_crecimiento(resultado.crecimiento_seguidores)} seguidores "
            f"(ahora: {miles(nuevo_total)} en total)</span><br><br>"
            + _comentarios_html(resultado.comentarios)
        )
        self.resultado_tarjeta.show()

        self.post_edit.setPlainText("")
        if self.perfil is not None and self.perfil.id == perfil.id:
            self._refrescar_cabecera()
            self._cargar_feed()

    # ---- los hinchas ----

    def revisar_hinchada(self):
        """Los hinchas reaccionan a lo nuevo de la partida (en un hilo)."""
        perfil = load_latest_profile()
        if perfil is None:
            return
        if self._hinchada_en_curso is not None:
            self._hinchada_pendiente = True
            return
        self._hinchada_en_curso = perfil.id
        ejecutar_en_hilo(
            hinchada.revisar_hinchada, perfil.id,
            al_completar=self._on_hinchada, al_fallar=self._on_hinchada_error,
        )

    def _terminar_hinchada(self):
        self._hinchada_en_curso = None
        if self._hinchada_pendiente:
            self._hinchada_pendiente = False
            self.revisar_hinchada()

    def _on_hinchada(self, resultado):
        player_id = self._hinchada_en_curso
        if resultado is not None:
            actividad, estado = resultado
            for item in actividad:
                save_actividad_instagram(item)
            total = sum(item.crecimiento_seguidores for item in actividad)
            if total:
                sumar_seguidores(player_id, total)
            set_estado_hinchada(player_id, estado)
            if actividad and self.perfil is not None and self.perfil.id == player_id:
                self._refrescar_cabecera()
                self._cargar_actividad()
        self._terminar_hinchada()

    def _on_hinchada_error(self, _mensaje: str):
        self._terminar_hinchada()  # sin partida legible, Instagram sigue como siempre

    def _cargar_actividad(self):
        limpiar_layout(self.actividad_layout)
        actividad = load_actividad_instagram(self.perfil.id, limite=ACTIVIDAD_VISIBLE)
        for item in actividad:
            color = estilos.POSITIVO if item.crecimiento_seguidores >= 0 else estilos.NEGATIVO
            dia = item.fecha_juego
            fecha = texto_suave(f"{dia[8:10]}/{dia[5:7]}" if len(dia) >= 10 else "", ajustar=False)
            icono_tipo = {"partido": "⚽", "noticia": "📰", "compra": "🛍️", "donacion": "💚"}.get(item.tipo, "•")
            titulo = QLabel(f"{icono_tipo}&nbsp; <b>{esc(item.titulo)}</b>")
            titulo.setWordWrap(True)
            linea = QHBoxLayout()
            linea.setSpacing(10)
            linea.addWidget(chip(f"{_crecimiento(item.crecimiento_seguidores)} seguidores", color))
            linea.addWidget(titulo, 1)  # el titulo ocupa el ancho (si no, se parte en tres lineas)
            linea.addWidget(fecha)
            self.actividad_layout.addLayout(linea)
            if item.comentarios:
                comentarios = texto_suave(_comentarios_html(item.comentarios))
                comentarios.setTextFormat(Qt.TextFormat.RichText)
                comentarios.setContentsMargins(4, 0, 0, 6)
                self.actividad_layout.addWidget(comentarios)
        self.actividad_tarjeta.setVisible(bool(actividad))

    def _on_publicar_error(self, mensaje: str):
        self._terminar_publicacion()
        QMessageBox.warning(self, "Error al publicar", mensaje)
