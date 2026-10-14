"""
Instagram del jugador: vos escribis el post y Gemini genera los
comentarios, los likes y cuanto suben o bajan tus seguidores.
"""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QMessageBox, QTextEdit, QVBoxLayout, QWidget

from roleplay.database import (
    get_reputacion_actual,
    get_seguidores,
    load_instagram_posts,
    load_latest_profile,
    save_instagram_post,
    sumar_seguidores,
)
from roleplay.models import InstagramPost, PlayerProfile
from roleplay.servicios.instagram import generar_reaccion_post
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
        nuevo.cuerpo.addLayout(
            fila(texto_suave("Los comentarios dependen de tu reputacion.", ajustar=False), None, self.publicar_btn)
        )
        layout.addWidget(nuevo)

        # ---- resultado del ultimo post ----
        self.resultado_tarjeta = Tarjeta("Como le fue a tu post", destacada=True)
        self.resultado_label = QLabel()
        self.resultado_label.setWordWrap(True)
        self.resultado_tarjeta.cuerpo.addWidget(self.resultado_label)
        self.resultado_tarjeta.hide()
        layout.addWidget(self.resultado_tarjeta)

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
            limpiar_layout(self.feed_layout)
            return

        self._refrescar_cabecera()
        self.publicar_btn.setEnabled(self._publicando is None)
        self._cargar_feed()

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

    def _on_publicar_error(self, mensaje: str):
        self._terminar_publicacion()
        QMessageBox.warning(self, "Error al publicar", mensaje)
