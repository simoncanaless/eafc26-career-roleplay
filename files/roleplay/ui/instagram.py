"""
Pagina de Instagram del jugador: vos escribis el post y Gemini genera los
comentarios, los likes y cuanto suben o bajan tus seguidores.
"""

from PySide6.QtWidgets import QLabel, QMessageBox, QPushButton, QTextEdit, QVBoxLayout, QWidget

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
from roleplay.ui.comun import ejecutar_en_hilo, esc, fecha_corta, miles
from roleplay.ui.estilos import marcar_subtitulo, marcar_titulo

TEXTO_PUBLICAR = "Publicar"


def _usuario(perfil: PlayerProfile) -> str:
    return "@" + perfil.nombre_jugador.replace(" ", "").lower()


class InstagramWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("EAFC 26 Roleplay - Instagram")

        self.perfil = None
        # (jugador, texto) del post que se esta publicando
        self._publicando: tuple[PlayerProfile, str] | None = None

        layout = QVBoxLayout()
        layout.setContentsMargins(28, 28, 28, 28)
        layout.setSpacing(8)

        self.header_label = QLabel()
        self.header_label.setWordWrap(True)
        marcar_titulo(self.header_label)
        layout.addWidget(self.header_label)

        layout.addWidget(QLabel("Escribi tu post:"))
        self.post_edit = QTextEdit()
        self.post_edit.setPlaceholderText("Ej: Feliz por la victoria de hoy, vamos por mas 💪")
        self.post_edit.setMaximumHeight(90)
        layout.addWidget(self.post_edit)

        self.publicar_btn = QPushButton(TEXTO_PUBLICAR)
        self.publicar_btn.clicked.connect(self._on_publicar_clicked)
        layout.addWidget(self.publicar_btn)

        resultado_titulo = QLabel("Resultado del ultimo post")
        marcar_subtitulo(resultado_titulo)
        layout.addSpacing(8)
        layout.addWidget(resultado_titulo)
        self.resultado_label = QLabel()
        self.resultado_label.setWordWrap(True)
        layout.addWidget(self.resultado_label)

        historial_titulo = QLabel("Posts anteriores")
        marcar_subtitulo(historial_titulo)
        layout.addSpacing(8)
        layout.addWidget(historial_titulo)
        self.historial_edit = QTextEdit()
        self.historial_edit.setReadOnly(True)
        self.historial_edit.setMinimumHeight(260)
        layout.addWidget(self.historial_edit, 1)

        self.setLayout(layout)
        self.actualizar()

    def actualizar(self):
        """Recarga el perfil y refresca el encabezado y el historial."""
        self.perfil = load_latest_profile()

        if self.perfil is None:
            self.header_label.setText(
                "No encontre ningun personaje guardado. Crea uno primero desde la pestana de Resumen."
            )
            self.publicar_btn.setEnabled(False)
            self.historial_edit.setPlainText("")
            return

        self._refrescar_header()
        self.publicar_btn.setEnabled(self._publicando is None)
        self._cargar_historial()

    def _refrescar_header(self):
        reputacion = get_reputacion_actual(self.perfil.id)
        seguidores = get_seguidores(self.perfil.id)
        club = self.perfil.club_actual or "sin club definido"
        self.header_label.setText(
            f"<b>{esc(_usuario(self.perfil))}</b> · {esc(club)} · Reputacion {reputacion}/100 · "
            f"<b>{miles(seguidores)} seguidores</b>"
        )

    def _cargar_historial(self):
        posts = load_instagram_posts(self.perfil.id)
        if not posts:
            self.historial_edit.setPlainText("Todavia no publicaste nada.")
            return

        bloques = []
        for post in posts:
            signo = "+" if post.crecimiento_seguidores >= 0 else ""
            bloque = (
                f"📅 {fecha_corta(post.fecha)}\n"
                f'"{post.texto}"\n'
                f"❤️ {miles(post.likes)} likes · {signo}{miles(post.crecimiento_seguidores)} seguidores\n"
            )
            for comentario in post.comentarios:
                bloque += f"  💬 {comentario.get('autor', '?')}: {comentario.get('texto', '')}\n"
            bloques.append(bloque)
        self.historial_edit.setPlainText("\n".join(bloques))

    def _on_publicar_clicked(self):
        texto = self.post_edit.toPlainText().strip()
        if not texto:
            QMessageBox.information(self, "Post vacio", "Escribi algo antes de publicar.")
            return

        self._publicando = (self.perfil, texto)
        self.publicar_btn.setEnabled(False)
        self.publicar_btn.setText("Publicando...")

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
        self.publicar_btn.setText(TEXTO_PUBLICAR)

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

        signo = "+" if resultado.crecimiento_seguidores >= 0 else ""
        texto_resultado = (
            f"❤️ {miles(resultado.likes_estimados)} likes · "
            f"{signo}{miles(resultado.crecimiento_seguidores)} seguidores "
            f"(ahora: {miles(nuevo_total)} en total)<br><br>"
        )
        for comentario in resultado.comentarios:
            texto_resultado += f"💬 <b>{esc(comentario.autor)}:</b> {esc(comentario.texto)}<br>"
        self.resultado_label.setText(texto_resultado)

        self.post_edit.setPlainText("")
        if self.perfil is not None and self.perfil.id == perfil.id:
            self._refrescar_header()
            self._cargar_historial()

    def _on_publicar_error(self, mensaje: str):
        self._terminar_publicacion()
        QMessageBox.warning(self, "Error al publicar", mensaje)
