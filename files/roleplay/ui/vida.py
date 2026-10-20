"""
Pagina Vida: la plata del jugador -su sueldo real de la partida de FC 26,
que se cobra a medida que pasan las semanas del juego- y en que la gasta:
casas, autos, relojes, moda, un yate, un jet, o donaciones.

Cada compra mueve seguidores y reputacion (lo decide servicios/economia.py)
al instante; despues, en un hilo, la prensa escribe la noticia (si es
noticia) y los hinchas la comentan en Instagram.

Los autos van por el concesionario (marcas reales, servicios/autos.py): se
configuran (ui/configurador.py), se pagan al pedir y llegan dias despues en
el juego; lo que provocan pasa cuando llegan (acreditar_con los entrega).

Con los dias del juego tambien pasan cosas sin que uno las compre: los
eventos inesperados (servicios/eventos.py), en la tarjeta "Lo que te paso",
y la vida sentimental (servicios/amor.py), con sus decisiones: si esta
soltero, puede buscar en el catalogo de famosas de Simon y mandar un DM
(segun su fama: servicios/ecosistema.py), y un romance puede ser secreto.

En cada categoria con tiendas oficiales (relojes, ropa, casas...), "COMPRAR EN
LAS WEBS OFICIALES" abre la tienda real (ui/tienda.py: la web adentro de la
app, como el configurador de autos); lo comprado guarda su web y su foto.

Ademas: los patrocinios (servicios/patrocinios.py: ofertas de marcas que
pagan por semana con el sueldo) y el marketplace de autos de culto
(servicios/marketplace.py, categoria "Usados y de culto" de la tienda).
"""

from datetime import date
from typing import Optional

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QButtonGroup,
    QComboBox,
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QProgressBar,
    QVBoxLayout,
    QWidget,
)

from roleplay.database import (
    get_economia,
    get_estado_amor,
    get_estado_clubes,
    get_estado_eventos,
    get_reputacion_actual,
    get_seguidores,
    load_latest_profile,
    save_actividad_instagram,
    save_noticia_prensa,
    set_economia,
    set_estado_amor,
    set_estado_clubes,
    set_estado_eventos,
    sumar_reputacion_y_seguidores,
)
from roleplay import config as config_app
from roleplay.servicios import amor, autos, clubes, economia, ecosistema, eventos, marketplace, patrocinios, tiendas
from roleplay.servicios.hinchada import _escala
from roleplay.servicios.economia import CATALOGO, CATEGORIAS, POR_ID, dinero
from roleplay.ui import estilos
from roleplay.ui.comun import ejecutar_en_hilo, esc, miles
from roleplay.ui.configurador import Configurador, guardar_foto, miniatura, miniatura_de_archivo
from roleplay.ui.componentes import (
    Mosaico,
    Tarjeta,
    boton,
    chip_alternable,
    etiqueta_campo,
    fila,
    limpiar_layout,
    subtitulo,
    texto_suave,
    titulo_pagina,
)

MOVIMIENTOS_VISIBLES = 12


def _fila_ancha(texto: QLabel, *derecha, foto=None) -> QHBoxLayout:
    """[foto] texto (ocupa todo el ancho, si no se parte en una columna angosta) [botones]."""
    linea = QHBoxLayout()
    linea.setSpacing(12)
    if foto is not None:
        linea.addWidget(foto)
    linea.addWidget(texto, 1)
    for widget in derecha:
        linea.addWidget(widget)
    return linea
EVENTOS_VISIBLES = 6
RESULTADOS_DM = 15


def _con_signo(numero: int) -> str:
    return f"{'+' if numero >= 0 else ''}{numero:,}".replace(",", ".")


class PaginaVida(QWidget):
    compra_hecha = Signal()  # la reputacion cambio: el menu refresca la barra lateral
    auto_entregado = Signal(str)  # llego un auto pedido: el menu avisa en la bandeja
    evento_inesperado = Signal(str, str)  # (titulo, reto): el menu avisa en la bandeja
    decision_pendiente = Signal(str)  # una decision de la vida sentimental: el menu avisa en la bandeja

    def __init__(self):
        super().__init__()
        self.perfil = None
        self._carrera = None
        self._leyendo = False
        self._categoria = "casa"
        self._ultima_compra = None  # la repercusion que llega tarde de otra compra no pisa la tarjeta
        self._botones_categoria = {}
        self._ofertas_nicho: dict[str, dict] = {}
        self._resultados_dm: list[dict] = []

        layout = QVBoxLayout(self)
        layout.setContentsMargins(40, 34, 40, 34)
        layout.setSpacing(18)

        textos = QVBoxLayout()
        textos.setSpacing(2)
        textos.addWidget(titulo_pagina("Vida"))
        self.subtitulo_label = subtitulo("Leyendo tu partida de FC 26...")
        textos.addWidget(self.subtitulo_label)
        layout.addLayout(textos)

        self.vacio = Tarjeta("Tu plata sale de tu partida", destacada=True)
        self.vacio_label = texto_suave(
            "Tu sueldo es el de tu contrato en la Carrera Jugador de FC 26 y se cobra a medida que pasan "
            "las semanas del juego. Juega y guarda (o deja el autoguardado), y vuelve aca."
        )
        self.vacio.cuerpo.addWidget(self.vacio_label)
        self.vacio.hide()
        layout.addWidget(self.vacio)

        self.contenido = QWidget()
        contenido = QVBoxLayout(self.contenido)
        contenido.setContentsMargins(0, 0, 0, 0)
        contenido.setSpacing(18)

        mosaicos = QHBoxLayout()
        mosaicos.setSpacing(10)
        self.mosaico_saldo = Mosaico("Saldo")
        self.mosaico_sueldo = Mosaico("Sueldo neto por semana")
        self.mosaico_gastos = Mosaico("Gastos fijos por semana")
        self.mosaico_patrimonio = Mosaico("Patrimonio")
        for mosaico in (self.mosaico_saldo, self.mosaico_sueldo, self.mosaico_gastos, self.mosaico_patrimonio):
            mosaicos.addWidget(mosaico)
        contenido.addLayout(mosaicos)

        self.resultado = Tarjeta("Repercusion", destacada=True)
        self.resultado_label = QLabel()
        self.resultado_label.setWordWrap(True)
        self.resultado.cuerpo.addWidget(self.resultado_label)
        self.resultado.hide()
        contenido.addWidget(self.resultado)

        self.eventos = Tarjeta("Lo que te paso")
        self.eventos_layout = QVBoxLayout()
        self.eventos_layout.setSpacing(10)
        self.eventos.cuerpo.addLayout(self.eventos_layout)
        self.eventos.hide()
        contenido.addWidget(self.eventos)

        self.amor = Tarjeta("Vida sentimental")
        self.amor_label = QLabel()  # una linea: con ajuste, al lado de la barra se achica a nada
        self.amor_barra = QProgressBar()
        self.amor_barra.setRange(0, 100)
        self.amor_barra.setTextVisible(False)
        self.amor_barra.setFixedWidth(220)
        self.amor.cuerpo.addLayout(fila(self.amor_label, None, self.amor_barra))
        self.amor_decision = QFrame()
        self.amor_decision.setObjectName("decisionAmor")
        self.amor_decision.setStyleSheet(
            f"QFrame#decisionAmor {{ border: 1px solid {estilos.ACENTO}; border-radius: 10px; }}"
        )
        decision = QVBoxLayout(self.amor_decision)
        decision.setContentsMargins(14, 12, 14, 12)
        decision.setSpacing(8)
        self.amor_decision_label = QLabel()
        self.amor_decision_label.setWordWrap(True)
        decision.addWidget(self.amor_decision_label)
        self.amor_botones = QHBoxLayout()
        self.amor_botones.setSpacing(8)
        decision.addLayout(self.amor_botones)
        self.amor_decision.hide()
        self.amor.cuerpo.addWidget(self.amor_decision)
        self.amor_eleccion = QLabel()
        self.amor_eleccion.setWordWrap(True)
        self.amor_eleccion.hide()
        self.amor.cuerpo.addWidget(self.amor_eleccion)
        self.oficializar_btn = boton("Oficializar relacion", primario=True)
        self.oficializar_btn.clicked.connect(self.oficializar_romance)
        self.oficializar_btn.hide()
        self.amor.cuerpo.addLayout(fila(None, self.oficializar_btn))
        # con la pareja, como en BitLife o Los Sims: citas, regalos, fotos, el anillo, la boda o terminar
        self.amor_acciones = QHBoxLayout()
        self.amor_acciones.setSpacing(8)
        self.amor.cuerpo.addLayout(self.amor_acciones)
        self.amor_pasos = QHBoxLayout()
        self.amor_pasos.setSpacing(8)
        self.amor.cuerpo.addLayout(self.amor_pasos)
        self._post_pareja = None
        self.amor_historial = QVBoxLayout()
        self.amor_historial.setSpacing(6)
        self.amor.cuerpo.addLayout(self.amor_historial)
        # soltero: buscar en el catalogo de famosas y mandar un DM (su propia tarjeta)
        self.vip = Tarjeta("Explorar Instagram VIP")
        self.dm = QWidget()
        dm = QVBoxLayout(self.dm)
        dm.setContentsMargins(0, 6, 0, 0)
        dm.setSpacing(8)
        self.dm_fama_label = texto_suave()
        dm.addWidget(self.dm_fama_label)
        self.dm_buscar_edit = QLineEdit()
        self.dm_buscar_edit.setPlaceholderText("Buscar por nombre o @usuario")
        self.dm_buscar_edit.returnPressed.connect(self.buscar_famosas)
        self.dm_categoria = QComboBox()
        buscar = boton("Buscar")
        buscar.clicked.connect(self.buscar_famosas)
        dm.addLayout(fila(self.dm_buscar_edit, self.dm_categoria, buscar, espaciado=8))
        self.dm_resultados = QVBoxLayout()
        self.dm_resultados.setSpacing(6)
        dm.addLayout(self.dm_resultados)
        self.vip.cuerpo.addWidget(self.dm)
        self.vip.hide()
        self.amor.hide()
        contenido.addWidget(self.amor)
        contenido.addWidget(self.vip)

        self.marcas = Tarjeta("Patrocinios")
        self.marcas_layout = QVBoxLayout()
        self.marcas_layout.setSpacing(8)
        self.marcas.cuerpo.addLayout(self.marcas_layout)
        contenido.addWidget(self.marcas)

        tienda = Tarjeta("Tienda")
        self._grupo = QButtonGroup(self)
        self._grupo.setExclusive(True)
        chips = QHBoxLayout()
        chips.setSpacing(8)
        for categoria, rotulo in CATEGORIAS.items():
            boton_categoria = chip_alternable(rotulo)
            boton_categoria.setChecked(categoria == self._categoria)
            boton_categoria.clicked.connect(lambda _=False, c=categoria: self._elegir_categoria(c))
            self._grupo.addButton(boton_categoria)
            self._botones_categoria[categoria] = boton_categoria
            chips.addWidget(boton_categoria)
        chips.addStretch()
        tienda.cuerpo.addLayout(chips)
        self.tienda_layout = QVBoxLayout()
        self.tienda_layout.setSpacing(8)
        tienda.cuerpo.addLayout(self.tienda_layout)
        contenido.addWidget(tienda)

        self.pedidos = Tarjeta("En camino")
        self.pedidos_layout = QVBoxLayout()
        self.pedidos_layout.setSpacing(8)
        self.pedidos.cuerpo.addLayout(self.pedidos_layout)
        self.pedidos.hide()
        contenido.addWidget(self.pedidos)

        self.posesiones = Tarjeta("Lo que tenes")
        self.posesiones_layout = QVBoxLayout()
        self.posesiones_layout.setSpacing(8)
        self.posesiones.cuerpo.addLayout(self.posesiones_layout)
        contenido.addWidget(self.posesiones)

        filantropia = Tarjeta("Filantropia")
        filantropia.cuerpo.addWidget(texto_suave("Donar sube tu reputacion y la prensa lo cuenta."))
        self.donaciones_layout = QVBoxLayout()
        self.donaciones_layout.setSpacing(8)
        filantropia.cuerpo.addLayout(self.donaciones_layout)
        contenido.addWidget(filantropia)

        movimientos = Tarjeta("Movimientos")
        self.movimientos_layout = QVBoxLayout()
        self.movimientos_layout.setSpacing(4)
        movimientos.cuerpo.addLayout(self.movimientos_layout)
        contenido.addWidget(movimientos)

        self.contenido.hide()
        layout.addWidget(self.contenido)
        layout.addStretch()

    # ---- el sueldo ----

    def actualizar(self):
        self.perfil = load_latest_profile()
        if self._leyendo:
            return
        self._leyendo = True
        ejecutar_en_hilo(economia.leer_partida_para_economia, al_completar=self._on_partida, al_fallar=self._on_error)

    def _on_partida(self, carrera):
        self._leyendo = False
        self.acreditar_con(carrera)

    def _on_error(self, _mensaje: str):
        self._leyendo = False
        self.acreditar_con(None)

    def acreditar_con(self, carrera):
        """Cobra lo que corresponde hasta el dia del juego de `carrera` y
        redibuja. El modo en vivo la llama con cada autoguardado."""
        self.perfil = load_latest_profile()
        self._carrera = carrera
        hoy = carrera.fecha_actual() if carrera is not None else None
        entregados = []
        if self.perfil is not None and hoy is not None and carrera.sueldo_usuario:
            e = economia.acreditar(get_economia(self.perfil.id), hoy, carrera.sueldo_usuario)
            e, entregados = economia.entregar_pedidos(e, hoy)
            set_economia(self.perfil.id, e)
        for posesion in entregados:  # se luce cuando llega: ahi es noticia
            articulo = economia.articulo_de_posesion(posesion)
            if articulo is not None:
                self._aplicar_y_repercutir(self.perfil, carrera, articulo, "Te llego tu")
                self.auto_entregado.emit(articulo.nombre)
        if self.perfil is not None and hoy is not None and carrera.sueldo_usuario:
            self._revisar_eventos(carrera, hoy)
            self._revisar_amor(carrera, hoy)
            self._revisar_patrocinios(hoy)
        self._mostrar()

    # ---- dibujo ----

    def _moneda(self) -> str:
        return economia.moneda_de(self._carrera)

    def _mostrar(self):
        e = get_economia(self.perfil.id) if self.perfil is not None else {}
        if self.perfil is None or not e:
            self.vacio_label.setText(
                "Crea un personaje primero, desde el Resumen." if self.perfil is None else
                "Tu sueldo es el de tu contrato en la Carrera Jugador de FC 26 y se cobra a medida que pasan "
                "las semanas del juego. No encontre tu partida: juega y guarda (o deja el autoguardado), y vuelve aca."
            )
            self.subtitulo_label.setText("Sin partida de Carrera Jugador.")
            self.vacio.show()
            self.contenido.hide()
            return
        self.vacio.hide()
        self.contenido.show()
        moneda = self._moneda()
        club = self._carrera.equipo(self._carrera.equipo_usuario()) if self._carrera is not None else ""
        self.subtitulo_label.setText(
            f"Contrato con <b>{esc(club or 'tu club')}</b>: {dinero(e['sueldo'], moneda)} por semana (bruto). "
            f"Se cobra con los dias del juego; al dia {e['hasta'][8:10]}/{e['hasta'][5:7]}/{e['hasta'][:4]}."
        )
        self.mosaico_saldo.poner(dinero(e["saldo"], moneda))
        self.mosaico_saldo.numero.setStyleSheet(f"color: {estilos.NEGATIVO};" if e["saldo"] < 0 else "")
        self.mosaico_sueldo.poner(dinero(e["sueldo"] * economia.NETO, moneda))
        self.mosaico_gastos.poner(dinero(economia.mantenimiento_semanal(e), moneda))
        self.mosaico_patrimonio.poner(dinero(economia.patrimonio(e), moneda))
        self._mostrar_eventos()
        self._mostrar_amor()
        self._mostrar_patrocinios(e)
        self._mostrar_tienda(e)
        self._mostrar_pedidos(e)
        self._mostrar_posesiones(e)
        self._mostrar_donaciones(e)
        self._mostrar_movimientos(e)

    def _elegir_categoria(self, categoria: str):
        self._categoria = categoria
        self._botones_categoria[categoria].setChecked(True)
        if self.perfil is not None:
            self._mostrar_tienda(get_economia(self.perfil.id))

    def _linea_articulo(self, articulo, e: dict, texto_boton: str) -> QHBoxLayout:
        moneda = self._moneda()
        detalle = dinero(articulo.precio, moneda)
        if articulo.mantenimiento:
            detalle += f" · mantenimiento {dinero(articulo.mantenimiento, moneda)}/semana"
        textos = QLabel(f"<b>{esc(articulo.nombre)}</b><br><span style='color:{estilos.TEXTO_SUAVE}'>{esc(detalle)}</span>")
        ya = economia.tiene(e, articulo.id) and not articulo.es_donacion
        accion = boton("Ya lo tenes" if ya else texto_boton, primario=not ya)
        accion.setProperty("articulo", articulo.id)  # (el objectName es el del estilo: "primario")
        accion.setEnabled(not ya and e.get("saldo", 0) >= articulo.precio)
        if not ya and e.get("saldo", 0) < articulo.precio:
            accion.setToolTip(f"Te faltan {dinero(articulo.precio - e.get('saldo', 0), moneda)}")
        accion.clicked.connect(lambda _=False, i=articulo.id: self._on_comprar(i))
        return fila(textos, None, accion)

    def _mostrar_tienda(self, e: dict):
        limpiar_layout(self.tienda_layout)
        if self._categoria == "auto":
            self._mostrar_concesionario()
            return
        if self._categoria == "usados":
            self._mostrar_marketplace(e)
            return
        oficiales = tiendas.TIENDAS.get(self._categoria, [])
        if oficiales:
            nombres = ", ".join(t.nombre for t in oficiales)
            entrar = boton("Comprar en las webs oficiales", primario=True)
            entrar.setProperty("tienda_real", self._categoria)
            entrar.clicked.connect(lambda _=False, c=self._categoria: self.abrir_tienda_real(c))
            self.tienda_layout.addLayout(_fila_ancha(
                texto_suave(f"Elegi algo de verdad en {esc(nombres)}, adentro de la app (como el configurador de autos)."),
                entrar))
        for articulo in CATALOGO:
            if articulo.categoria == self._categoria:
                self.tienda_layout.addLayout(self._linea_articulo(articulo, e, "Comprar"))

    def _mostrar_concesionario(self):
        moneda = self._moneda()
        self.tienda_layout.addWidget(texto_suave(
            "Elegi el modelo y configuralo a tu gusto. Se paga al pedir y llega dias despues en el juego."
        ))
        for marca in autos.MARCAS:
            self.tienda_layout.addSpacing(4)
            self.tienda_layout.addWidget(etiqueta_campo(marca))
            for modelo in (m for m in autos.MODELOS if m.marca == marca):
                textos = QLabel(
                    f"<b>{esc(modelo.nombre_completo)}</b><br><span style='color:{estilos.TEXTO_SUAVE}'>desde "
                    f"{dinero(modelo.precio, moneda)} · llega {modelo.dias_entrega} dias despues de pedirlo</span>"
                )
                configurar = boton("Configurar", primario=True)
                configurar.setProperty("modelo", modelo.id)
                configurar.clicked.connect(lambda _=False, i=modelo.id: self._on_configurar(i))
                self.tienda_layout.addLayout(fila(textos, None, configurar))

    def _hoy(self, e: Optional[dict] = None):
        if self._carrera is not None and self._carrera.fecha_actual() is not None:
            return self._carrera.fecha_actual()
        hasta = (e or {}).get("hasta")
        return date.fromisoformat(hasta) if hasta else None

    def _mostrar_marketplace(self, e: dict):
        hoy = self._hoy(e)
        ofertas = marketplace.ofertas(self.perfil.id, hoy) if hoy is not None and self.perfil is not None else []
        self._ofertas_nicho = {o["id"]: o for o in ofertas}
        if not ofertas:
            self.tienda_layout.addWidget(texto_suave(
                "Sin el catalogo de autos de culto (roleplay/datos/autos_marketplace.json) no hay marketplace."
            ))
            return
        moneda = self._moneda()
        self.tienda_layout.addWidget(texto_suave(
            "Usados y autos de culto: cambian cada semana del juego, se compran al instante y los de coleccion "
            "se valorizan con el tiempo."
        ))
        for oferta in ofertas:
            articulo = marketplace.articulo(oferta)
            nota = f" · {oferta['nota']}" if oferta.get("nota") else ""
            textos = QLabel(
                f"<b>{esc(articulo.nombre)}</b> · {dinero(oferta['precio'], moneda)}<br>"
                f"<span style='color:{estilos.TEXTO_SUAVE}'>{esc(oferta['categoria'])} · rareza {esc(oferta['rareza'])}"
                f" · {esc(articulo.detalle)}{esc(nota)}</span>"
                + (f"<br><span style='color:{estilos.TEXTO_SUAVE}; font-size: 10px'>Foto: {esc(oferta['credito'])}</span>"
                   if oferta.get("credito") else "")
            )
            textos.setWordWrap(True)
            ya = economia.tiene(e, articulo.id)
            comprar = boton("Ya lo tenes" if ya else "Comprar", primario=not ya)
            comprar.setProperty("nicho", oferta["id"])
            comprar.setEnabled(not ya and e.get("saldo", 0) >= oferta["precio"])
            comprar.clicked.connect(lambda _=False, i=oferta["id"]: self._on_comprar_nicho(i))
            foto = miniatura_de_archivo(marketplace.ruta_imagen(oferta.get("imagen", "")))
            self.tienda_layout.addLayout(_fila_ancha(textos, comprar, foto=foto))

    def _on_comprar_nicho(self, oferta_id: str):
        perfil, carrera = self.perfil, self._carrera
        oferta = self._ofertas_nicho.get(oferta_id)
        if perfil is None or carrera is None or carrera.fecha_actual() is None or oferta is None:
            return
        articulo = marketplace.articulo(oferta)
        try:
            nueva = economia.comprar(get_economia(perfil.id), articulo, carrera.fecha_actual(), marketplace.extra_de(oferta))
        except economia.SinPlata as exc:
            QMessageBox.information(self, "No te alcanza", str(exc))
            return
        set_economia(perfil.id, nueva)
        self._aplicar_y_repercutir(perfil, carrera, articulo, "Compraste")
        self._mostrar()

    # ---- patrocinios ----

    def _revisar_patrocinios(self, hoy):
        perfil = self.perfil
        escandalo = patrocinios.hubo_escandalo(get_estado_eventos(perfil.id), hoy)
        e, novedades = patrocinios.revisar(get_economia(perfil.id), perfil.id, get_seguidores(perfil.id),
                                           get_reputacion_actual(perfil.id), hoy, escandalo)
        set_economia(perfil.id, e)
        for novedad in novedades:
            self._contar_marca(perfil, novedad, hoy)

    def _contar_marca(self, perfil, novedad, hoy):
        ejecutar_en_hilo(
            eventos.contar, perfil, novedad.titulo, f"{perfil.nombre_jugador} {novedad.detalle}", novedad.tono, 0,
            hoy.isoformat(), novedad.clave, "patrocinio",
            al_completar=self._on_repercusion_amor, al_fallar=self._on_repercusion_error,
        )

    def _mostrar_patrocinios(self, e: dict):
        limpiar_layout(self.marcas_layout)
        moneda = self._moneda()
        estado = e.get("patrocinios") or {}
        for contrato in estado.get("contratos", []):
            hasta = contrato["hasta"]
            self.marcas_layout.addWidget(QLabel(
                f"<b>{esc(contrato['nombre'])}</b> <span style='color:{estilos.TEXTO_SUAVE}'>· {esc(contrato['rubro'])}"
                f" · {dinero(contrato['semanal'], moneda)} por semana (bruto) · hasta el "
                f"{hasta[8:10]}/{hasta[5:7]}/{hasta[:4]}</span>"
            ))
        oferta = estado.get("oferta")
        if oferta:
            texto = QLabel(
                f"<span style='color:{estilos.ACENTO}'>Te ofrecen un contrato</span><br><b>{esc(oferta['nombre'])}</b>"
                f" ({esc(oferta['rubro'])}): {dinero(oferta['semanal'], moneda)} por semana, por "
                f"{patrocinios.DURACION_DIAS // 365} anios"
            )
            texto.setWordWrap(True)
            firmar = boton("Firmar", primario=True)
            firmar.setProperty("patrocinio", "firmar")
            firmar.clicked.connect(lambda: self.responder_patrocinio(True))
            rechazar = boton("Rechazar")
            rechazar.setProperty("patrocinio", "rechazar")
            rechazar.clicked.connect(lambda: self.responder_patrocinio(False))
            self.marcas_layout.addLayout(_fila_ancha(texto, firmar, rechazar))
        if not estado.get("contratos") and not oferta:
            self.marcas_layout.addWidget(texto_suave(
                "Con mas seguidores y reputacion, las marcas te van a buscar. Un escandalo puede hacer que te dejen."
            ))

    def responder_patrocinio(self, aceptar: bool):
        perfil = self.perfil
        if perfil is None:
            return
        e = get_economia(perfil.id)
        hoy = self._hoy(e)
        if hoy is None:
            return
        e, novedad = patrocinios.responder(e, aceptar, hoy)
        set_economia(perfil.id, e)
        if novedad is not None:
            self._contar_marca(perfil, novedad, hoy)
        self._mostrar()

    def abrir_tienda_real(self, categoria: str):
        from roleplay.ui.tienda import DialogoTiendaReal

        if self.perfil is None or self._carrera is None or self._carrera.fecha_actual() is None:
            return
        dialogo = DialogoTiendaReal(categoria, get_economia(self.perfil.id).get("saldo", 0), self._moneda(), self)
        if dialogo.exec() == QDialog.DialogCode.Accepted:
            self.comprar_de_tienda(dialogo.articulo(), dialogo.url_actual(), dialogo.foto)
        dialogo.deleteLater()

    def comprar_de_tienda(self, articulo, url: str = "", foto=None):
        """Lo elegido en una web oficial: se compra con su web y su foto (compras/)."""
        from roleplay.ui.tienda import guardar_foto_compra

        perfil, carrera = self.perfil, self._carrera
        if perfil is None or carrera is None or carrera.fecha_actual() is None:
            return
        extra = {"url": url} if url else {}
        try:
            nueva = economia.comprar(get_economia(perfil.id), articulo, carrera.fecha_actual(), extra)
        except economia.SinPlata as exc:
            QMessageBox.information(self, "No te alcanza", str(exc))
            return
        if foto is not None and not foto.isNull():
            posesion = nueva["posesiones"][-1]
            posesion["foto"] = guardar_foto_compra(foto, posesion["id"])
        set_economia(perfil.id, nueva)
        self._aplicar_y_repercutir(perfil, carrera, articulo, "Compraste")
        self._mostrar()

    def _mostrar_pedidos(self, e: dict):
        limpiar_layout(self.pedidos_layout)
        moneda = self._moneda()
        hoy = e.get("hasta", "")
        for pedido in e.get("pedidos", []):
            config = autos.Configuracion.desde_dict(pedido["config"])
            vista = miniatura(config, pedido.get("foto", ""))
            entrega = pedido["entrega"]
            faltan = ""
            if hoy:
                from datetime import date

                dias = (date.fromisoformat(entrega) - date.fromisoformat(hoy)).days
                faltan = f" (faltan {dias} dias del juego)" if dias > 0 else " (llega con el proximo guardado)"
            texto = QLabel(
                f"<b>{esc(autos.POR_ID[pedido['modelo']].nombre_completo)}</b> · {dinero(pedido['precio'], moneda)}"
                f"<br><span style='color:{estilos.TEXTO_SUAVE}'>{esc(autos.describir(config))}<br>"
                f"Llega el {entrega[8:10]}/{entrega[5:7]}/{entrega[:4]}{faltan}</span>"
            )
            texto.setWordWrap(True)
            self.pedidos_layout.addLayout(fila(vista, texto, None))
        self.pedidos.setVisible(bool(e.get("pedidos")))

    def _mostrar_donaciones(self, e: dict):
        limpiar_layout(self.donaciones_layout)
        for articulo in CATALOGO:
            if articulo.es_donacion:
                self.donaciones_layout.addLayout(self._linea_articulo(articulo, e, "Donar"))

    def _mostrar_posesiones(self, e: dict):
        limpiar_layout(self.posesiones_layout)
        moneda = self._moneda()
        posesiones = e.get("posesiones", [])
        hoy = self._hoy(e)
        for posesion in posesiones:
            articulo = economia.articulo_de_posesion(posesion)
            nombre = articulo.nombre if articulo else posesion["articulo"]
            vender_btn = boton(f"Vender por {dinero(economia.valor_de_venta(posesion, hoy), moneda)}")
            vender_btn.clicked.connect(lambda _=False, i=posesion["id"]: self._on_vender(i))
            desde = posesion.get("desde", "")
            detalle = f"{esc(articulo.detalle)}<br>" if articulo is not None and articulo.detalle else ""
            texto = QLabel(f"<b>{esc(nombre)}</b><br><span style='color:{estilos.TEXTO_SUAVE}'>{detalle}desde el "
                           f"{desde[8:10]}/{desde[5:7]}/{desde[:4]}</span>")
            texto.setWordWrap(True)
            partes = [texto, None, vender_btn]
            if posesion.get("config"):  # los autos del concesionario, con su foto (o su dibujo)
                partes.insert(0, miniatura(autos.Configuracion.desde_dict(posesion["config"]), posesion.get("foto", "")))
            elif posesion.get("foto") and posesion["articulo"].startswith(economia.LIBRE):  # de una web oficial
                foto = miniatura_de_archivo(str(config_app.CARPETA_COMPRAS / posesion["foto"]))
                if foto is not None:
                    partes.insert(0, foto)
            elif posesion.get("imagen"):  # los del marketplace, con la foto del catalogo
                foto = miniatura_de_archivo(marketplace.ruta_imagen(posesion["imagen"]))
                if foto is not None:
                    partes.insert(0, foto)
            self.posesiones_layout.addLayout(fila(*partes))
        if not posesiones:
            self.posesiones_layout.addWidget(texto_suave("Todavia no te compraste nada."))

    def _mostrar_movimientos(self, e: dict):
        limpiar_layout(self.movimientos_layout)
        moneda = self._moneda()
        for movimiento in e.get("movimientos", [])[:MOVIMIENTOS_VISIBLES]:
            dia = movimiento["fecha"]
            monto = movimiento["monto"]
            color = estilos.POSITIVO if monto > 0 else estilos.NEGATIVO if monto < 0 else estilos.TEXTO_SUAVE
            cifra = QLabel(("+" if monto > 0 else "") + dinero(monto, moneda) if monto else "")
            cifra.setStyleSheet(f"color: {color}; font-weight: 600;")
            fecha = texto_suave(f"{dia[8:10]}/{dia[5:7]}", ajustar=False)
            fecha.setFixedWidth(46)
            self.movimientos_layout.addLayout(fila(fecha, QLabel(esc(movimiento["concepto"])), None, cifra))

    # ---- eventos inesperados ----

    def _revisar_eventos(self, carrera, hoy):
        perfil = self.perfil
        estado, e, ocurridos = eventos.revisar(
            perfil, get_estado_eventos(perfil.id), get_economia(perfil.id), carrera, hoy,
            get_seguidores(perfil.id), get_reputacion_actual(perfil.id),
        )
        set_estado_eventos(perfil.id, estado)
        set_economia(perfil.id, e)
        for ocurrido in ocurridos:
            sumar_reputacion_y_seguidores(perfil.id, ocurrido.reputacion, ocurrido.seguidores, motivo=ocurrido.titulo)
            # tu hinchada tambien se entera (y una polemica abre una decision en el Resumen)
            set_estado_clubes(perfil.id, clubes.por_evento(get_estado_clubes(perfil.id), ocurrido.tipo.id, ocurrido.fecha))
            self.compra_hecha.emit()  # la reputacion cambio
            self.evento_inesperado.emit(ocurrido.titulo, ocurrido.reto)
            ejecutar_en_hilo(
                eventos.repercusion, perfil, ocurrido, self._moneda(),
                al_completar=lambda resultado, i=ocurrido.id: self._on_repercusion_evento(i, resultado),
                al_fallar=self._on_repercusion_error,
            )

    def _on_repercusion_evento(self, evento_id: str, resultado):
        noticia, actividad = resultado
        save_noticia_prensa(noticia)
        save_actividad_instagram(actividad)  # los seguidores ya se sumaron
        if self.perfil is None:
            return
        estado = get_estado_eventos(self.perfil.id)
        for ocurrido in estado.get("historial", []):
            if ocurrido["id"] == evento_id:
                ocurrido["prensa"] = noticia.titular
                set_estado_eventos(self.perfil.id, estado)
                self._mostrar_eventos()
                break

    def _mostrar_eventos(self):
        limpiar_layout(self.eventos_layout)
        historial = get_estado_eventos(self.perfil.id).get("historial", []) if self.perfil is not None else []
        moneda = self._moneda()
        for ocurrido in historial[:EVENTOS_VISIBLES]:
            efectos = []
            if ocurrido["reputacion"]:
                efectos.append(f"reputacion {_con_signo(ocurrido['reputacion'])}")
            if ocurrido["seguidores"]:
                efectos.append(f"{_con_signo(ocurrido['seguidores'])} seguidores")
            if ocurrido["dinero"]:
                efectos.append(("+" if ocurrido["dinero"] > 0 else "") + dinero(ocurrido["dinero"], moneda))
            color = {"positiva": estilos.POSITIVO, "negativa": estilos.NEGATIVO}.get(ocurrido["tono"], estilos.TEXTO_SUAVE)
            dia = ocurrido["fecha"]
            texto = (f"<b>{esc(ocurrido['titulo'])}</b> <span style='color:{estilos.TEXTO_SUAVE}'>"
                     f"· {dia[8:10]}/{dia[5:7]}</span>")
            if efectos:
                texto += f"<br><span style='color:{color}'>{esc(' · '.join(efectos))}</span>"
            if ocurrido.get("reto"):
                texto += f"<br><span style='color:{estilos.ACENTO}'>Reto:</span> {esc(ocurrido['reto'])}"
            if ocurrido.get("prensa"):
                texto += f"<br><span style='color:{estilos.TEXTO_SUAVE}'>En la prensa: {esc(ocurrido['prensa'])}</span>"
            etiqueta = QLabel(texto)
            etiqueta.setWordWrap(True)
            self.eventos_layout.addWidget(etiqueta)
        self.eventos.setVisible(bool(historial))

    # ---- vida sentimental ----

    def _revisar_amor(self, carrera, hoy):
        perfil = self.perfil
        antes = get_estado_amor(perfil.id)
        fama = ecosistema.calcular_fama_jugador(perfil.id, carrera)["fama"]
        estado, e, sucesos = amor.revisar(perfil, antes, get_economia(perfil.id), hoy, fama)
        set_estado_amor(perfil.id, estado)
        set_economia(perfil.id, e)
        for suceso in sucesos:
            self._contar_amor(perfil, suceso, estado)
        nueva = estado.get("decision")
        if nueva and nueva != antes.get("decision"):
            decision, pareja = amor.decision_pendiente(estado)
            self.decision_pendiente.emit(decision.titulo.format(pareja=pareja))

    def _contar_amor(self, perfil, suceso, estado: dict) -> int:
        if suceso.privado:  # un secreto (o un DM sin respuesta): queda en su historial, sin prensa
            return 0
        seguidores = round(_escala(get_seguidores(perfil.id), get_reputacion_actual(perfil.id)) * suceso.seguidores)
        sumar_reputacion_y_seguidores(perfil.id, suceso.reputacion, seguidores, motivo=suceso.titulo)
        self.compra_hecha.emit()
        descripcion = f"{perfil.nombre_jugador} {suceso.detalle}"  # (con pareja real, amor.py ya no arma crisis)
        apellido = (perfil.nombre_jugador.split() or [""])[-1]
        titular = f"{apellido} {suceso.detalle}" if apellido else suceso.titulo  # lo que paso, con quien
        ejecutar_en_hilo(
            eventos.contar, perfil, titular, descripcion, suceso.tono, seguidores,
            suceso.fecha.isoformat(), suceso.clave, "amor",
            al_completar=self._on_repercusion_amor, al_fallar=self._on_repercusion_error,
        )
        return seguidores

    def _on_repercusion_amor(self, resultado):
        noticia, actividad = resultado
        save_noticia_prensa(noticia)
        save_actividad_instagram(actividad)

    def _mostrar_amor(self):
        estado = get_estado_amor(self.perfil.id) if self.perfil is not None else {}
        if not estado:
            self.amor.hide()
            return
        pareja = estado.get("pareja")
        textos = {
            "pareja": "En pareja con", "comprometido": "Comprometido con", "casado": "Casado con",
            "conociendo": "Conociendo a", "secreto": "En secreto con",
        }
        if pareja and estado["estado"] in textos:
            quien = f"<b>{esc(pareja['nombre'])}</b>" + (f", {esc(pareja['oficio'])}" if pareja.get("oficio") else "")
            texto = f"{textos[estado['estado']]} {quien}"
            if estado["estado"] != "conociendo":
                desde = pareja.get("desde", "")
                texto += (f" <span style='color:{estilos.TEXTO_SUAVE}'>· {amor.rotulo(pareja['relacion'])}"
                          + (f" · desde el {desde[8:10]}/{desde[5:7]}/{desde[:4]}" if desde else "") + "</span>")
            self.amor_label.setText(texto)
            mostrar_barra = estado["estado"] != "conociendo"
            self.amor_barra.setVisible(mostrar_barra)
            if mostrar_barra:
                self.amor_barra.setValue(pareja["relacion"])
                color = (estilos.NEGATIVO if pareja["relacion"] < amor.CRISIS else
                         estilos.MIXTO if pareja["relacion"] < 50 else estilos.ACENTO)
                self.amor_barra.setStyleSheet(f"QProgressBar::chunk {{ background-color: {color}; border-radius: 3px; }}")
        else:
            self.amor_label.setText("<b>Soltero</b> <span style='color:" + estilos.TEXTO_SUAVE + "'>· lo que pase, "
                                    "pasa con las semanas del juego</span>")
            self.amor_barra.hide()
        limpiar_layout(self.amor_botones)
        pendiente = amor.decision_pendiente(estado)
        if pendiente is not None:
            decision, nombre = pendiente
            self.amor_decision_label.setText(
                f"<span style='color:{estilos.ACENTO}'>Tenes que decidir</span><br>"
                f"<b>{esc(decision.titulo.format(pareja=nombre))}</b><br>{esc(decision.pregunta)}"
            )
            for i, opcion in enumerate(decision.opciones):
                eleccion = boton(opcion.texto, primario=i == 0)
                eleccion.setProperty("opcion", opcion.id)
                eleccion.clicked.connect(lambda _=False, o=opcion.id: self.elegir_amor(o))
                self.amor_botones.addWidget(eleccion)
            self.amor_botones.addStretch()
        self.amor_decision.setVisible(pendiente is not None)
        limpiar_layout(self.amor_historial)
        moneda = self._moneda()
        for h in estado.get("historial", [])[:4]:
            efectos = []
            if h.get("relacion"):
                efectos.append(f"relacion {_con_signo(h['relacion'])}")
            if h.get("dinero"):
                efectos.append(dinero(h["dinero"], moneda))
            dia = h["fecha"]
            linea = QLabel(f"<span style='color:{estilos.TEXTO_SUAVE}'>{dia[8:10]}/{dia[5:7]}</span>&nbsp; "
                           f"{esc(h['titulo'])}" + (f" <span style='color:{estilos.TEXTO_SUAVE}'>· "
                                                     f"{esc(' · '.join(efectos))}</span>" if efectos else ""))
            linea.setWordWrap(True)
            self.amor_historial.addWidget(linea)
        self.oficializar_btn.setVisible(estado.get("estado") == "secreto" and bool(estado.get("pareja")))
        self._mostrar_acciones_amor(estado)
        self._mostrar_dm(estado)
        self.amor.show()

    # ---- mandar un DM (soltero, con el catalogo de famosas) ----

    def _fama(self) -> int:
        return ecosistema.calcular_fama_jugador(self.perfil.id, self._carrera, leer_partida=False)["fama"]

    def _mostrar_dm(self, estado: dict):
        hay_catalogo = bool(ecosistema.celebridades())
        soltero = estado.get("estado", "soltero") == "soltero" and not estado.get("decision")
        self.vip.setVisible(hay_catalogo and soltero)
        if not (hay_catalogo and soltero):
            return
        if self.dm_categoria.count() == 0:
            self.dm_categoria.addItem("Todas", "")
            for categoria in amor.categorias():
                self.dm_categoria.addItem(categoria.capitalize(), categoria)
        hoy = self._hoy(get_economia(self.perfil.id))
        puede = hoy is not None and amor.puede_mandar_dm(estado, hoy)
        self.dm_fama_label.setText(
            f"Tu fama: <b>{self._fama()}</b>/100 (reputacion, tu club, tus goles y premios). "
            + ("Podes mandar un DM esta semana." if puede else "Ya mandaste un DM esta semana del juego.")
        )
        self._dibujar_resultados(puede)

    def buscar_famosas(self):
        self._resultados_dm = amor.buscar(self.dm_buscar_edit.text(), self.dm_categoria.currentData() or "",
                                          RESULTADOS_DM)
        estado = get_estado_amor(self.perfil.id) if self.perfil is not None else {}
        hoy = self._hoy(get_economia(self.perfil.id)) if self.perfil is not None else None
        self._dibujar_resultados(hoy is not None and amor.puede_mandar_dm(estado, hoy))

    def _dibujar_resultados(self, puede: bool):
        limpiar_layout(self.dm_resultados)
        fama = self._fama() if self.perfil is not None else 0
        for indice, celebridad in enumerate(self._resultados_dm):
            exigencia = amor.exigencia(celebridad)
            chance = amor.probabilidad_de_exito(fama, exigencia)
            color = estilos.TEXTO if exigencia <= fama else estilos.TEXTO_SUAVE
            color_chance = estilos.POSITIVO if chance >= 0.6 else estilos.MIXTO if chance >= 0.25 else estilos.NEGATIVO
            texto = QLabel(
                f"<span style='color:{color}'><b>{esc(celebridad.get('nombre', ''))}</b></span> "
                f"<span style='color:{estilos.TEXTO_SUAVE}'>· {esc(celebridad.get('oficio', ''))} · "
                f"{esc(celebridad.get('usuario_ig', ''))} · exigencia {exigencia}</span> "
                f"<span style='color:{color_chance}'><b>{round(chance * 100)}% de chance</b></span>"
                + (f" <span style='color:{estilos.TEXTO_SUAVE}'>· si te clava el visto, "
                   f"{round(amor.probabilidad_de_filtracion(fama, exigencia) * 100)}% de que se filtre</span>"
                   if amor.probabilidad_de_filtracion(fama, exigencia) else "")
            )
            texto.setWordWrap(True)
            mandar = boton("Enviar DM", primario=exigencia <= fama)
            mandar.setProperty("dm", indice)
            mandar.setEnabled(puede)
            mandar.clicked.connect(lambda _=False, i=indice: self.mandar_dm(i))
            self.dm_resultados.addLayout(_fila_ancha(texto, mandar))

    def oficializar_romance(self):
        perfil = self.perfil
        estado = get_estado_amor(perfil.id) if perfil is not None else {}
        hoy = self._hoy(get_economia(perfil.id)) if perfil is not None else None
        if perfil is None or hoy is None or estado.get("estado") != "secreto":
            return
        estado, e, suceso = amor.oficializar(estado, get_economia(perfil.id), hoy)
        set_estado_amor(perfil.id, estado)
        set_economia(perfil.id, e)
        seguidores = self._contar_amor(perfil, suceso, estado)
        self.amor_eleccion.setText(f"<b>Lo hiciste oficial</b> · {_con_signo(seguidores)} seguidores"
                                   f"<br><span style='color:{estilos.TEXTO_SUAVE}'>La prensa ya se entero...</span>")
        self.amor_eleccion.show()
        self._mostrar()

    # ---- con la pareja ----

    def _mostrar_acciones_amor(self, estado: dict):
        limpiar_layout(self.amor_acciones)
        limpiar_layout(self.amor_pasos)
        if estado.get("estado") not in amor.PAREJA_ACTIVA + ("conociendo",) or not estado.get("pareja"):
            return
        e = get_economia(self.perfil.id)
        hoy = self._hoy(e)
        if hoy is None:
            return
        moneda = self._moneda()
        if estado["estado"] != "conociendo":
            for accion in amor.ACCIONES.values():
                if accion.solo_casados and estado["estado"] != "casado":
                    continue
                puede, motivo = amor.puede_interactuar(estado, accion.id, hoy)
                costo = amor.costo_de(accion.id, e)
                if puede and costo > e.get("saldo", 0):
                    puede, motivo = False, "No te alcanza la plata."
                b = boton(accion.texto)
                b.setProperty("accion_amor", accion.id)
                b.setEnabled(puede)
                b.setToolTip(motivo or (f"Relacion +{accion.relacion}" + (f" · {dinero(costo, moneda)}" if costo else "")))
                b.clicked.connect(lambda _=False, a=accion.id: self.interactuar_amor(a))
                self.amor_acciones.addWidget(b)
            self.amor_acciones.addStretch()
        if estado["estado"] == "pareja":
            puede, motivo = amor.puede_proponer(estado, hoy)
            b = boton("Proponer casamiento", primario=puede)
            b.setProperty("paso_amor", "proponer")
            b.setEnabled(puede)
            b.setToolTip(motivo or "El anillo cuesta 6 semanas de sueldo")
            b.clicked.connect(self.proponer_casamiento)
            self.amor_pasos.addWidget(b)
        elif estado["estado"] == "comprometido":
            puede, motivo = amor.puede_casarse(estado, hoy)
            for grande, texto in ((True, "Boda a lo grande"), (False, "Boda intima")):
                b = boton(texto, primario=puede and grande)
                b.setProperty("paso_amor", "boda_grande" if grande else "boda_intima")
                b.setEnabled(puede)
                b.setToolTip(motivo or ("25 semanas de sueldo, y todo el mundo se entera" if grande else
                                        "5 semanas de sueldo, solo la familia"))
                b.clicked.connect(lambda _=False, g=grande: self.casarse(g))
                self.amor_pasos.addWidget(b)
        self.amor_pasos.addStretch()
        fin = boton("Divorciarse" if estado["estado"] == "casado" else "Terminar la relacion")
        fin.setProperty("paso_amor", "terminar")
        fin.clicked.connect(self.terminar_relacion)
        self.amor_pasos.addWidget(fin)

    def _aplicar_amor(self, perfil, estado: dict, e: dict, suceso) -> int:
        set_estado_amor(perfil.id, estado)
        set_economia(perfil.id, e)
        return self._contar_amor(perfil, suceso, estado)

    def _resultado_amor(self, suceso, seguidores: int):
        partes = [f"<b>{esc(suceso.titulo)}</b>"]
        if suceso.relacion:
            partes.append(f"relacion {_con_signo(suceso.relacion)}")
        if seguidores:
            partes.append(f"{_con_signo(seguidores)} seguidores")
        if suceso.dinero:
            partes.append(dinero(suceso.dinero, self._moneda()))
        self.amor_eleccion.setText(" · ".join(partes))
        self.amor_eleccion.show()
        self._mostrar()

    def _texto_del_post(self, sugerido: str) -> Optional[str]:
        """El post queda editable antes de publicarse (None: cancelado)."""
        from PySide6.QtWidgets import QInputDialog

        texto, ok = QInputDialog.getMultiLineText(self, "Publicar en Instagram", "Tu post:", sugerido)
        return texto.strip() if ok and texto.strip() else None

    def _confirmar(self, titulo: str, texto: str) -> bool:
        return QMessageBox.question(self, titulo, texto) == QMessageBox.StandardButton.Yes

    def interactuar_amor(self, accion_id: str):
        perfil = self.perfil
        if perfil is None:
            return
        estado, e = get_estado_amor(perfil.id), get_economia(perfil.id)
        hoy = self._hoy(e)
        if hoy is None:
            return
        accion = amor.ACCIONES[accion_id]
        texto = ""
        if accion.publica:
            from roleplay.servicios import instagram

            texto = self._texto_del_post(instagram.post_con_pareja(perfil, estado["pareja"]["nombre"],
                                                                    boda=accion.solo_casados))
            if texto is None:
                return
        try:
            estado, e, suceso = amor.interactuar(estado, e, accion_id, hoy)
        except ValueError as exc:
            QMessageBox.information(self, "Ahora no", str(exc))
            return
        if not accion.publica:
            self._resultado_amor(suceso, self._aplicar_amor(perfil, estado, e, suceso))
            return
        # la foto: un post de verdad en su Instagram (los comentarios y los seguidores, de la reaccion)
        set_estado_amor(perfil.id, estado)
        set_economia(perfil.id, e)
        from roleplay.servicios import instagram

        self._post_pareja = (perfil, texto, suceso)
        ejecutar_en_hilo(
            instagram.reaccion_post_con_pareja, perfil, texto, get_reputacion_actual(perfil.id),
            get_seguidores(perfil.id), not estado["pareja"].get("real"),
            al_completar=self._on_post_pareja, al_fallar=self._on_repercusion_error,
        )
        self.amor_eleccion.setText(f"<b>{esc(suceso.titulo)}</b> · publicando...")
        self.amor_eleccion.show()
        self._mostrar()

    def _on_post_pareja(self, reaccion):
        from roleplay.database import save_instagram_post, sumar_seguidores
        from roleplay.models import InstagramPost

        if self._post_pareja is None:
            return
        perfil, texto, suceso = self._post_pareja
        self._post_pareja = None
        sumar_seguidores(perfil.id, reaccion.crecimiento_seguidores)
        save_instagram_post(InstagramPost(
            player_id=perfil.id, texto=texto, likes=reaccion.likes_estimados,
            crecimiento_seguidores=reaccion.crecimiento_seguidores,
            comentarios=[c.model_dump() for c in reaccion.comentarios],
        ))
        self.compra_hecha.emit()
        if self.perfil is not None and self.perfil.id == perfil.id:
            self.amor_eleccion.setText(
                f"<b>{esc(suceso.titulo)}</b> · {miles(reaccion.likes_estimados)} likes · "
                f"{_con_signo(reaccion.crecimiento_seguidores)} seguidores"
                f"<br><span style='color:{estilos.TEXTO_SUAVE}'>Esta en tu Instagram, con los comentarios.</span>")
            self.amor_eleccion.show()

    def proponer_casamiento(self):
        perfil = self.perfil
        if perfil is None:
            return
        e = get_economia(perfil.id)
        hoy = self._hoy(e)
        try:
            estado, e, suceso = amor.proponer(get_estado_amor(perfil.id), e, hoy)
        except (ValueError, TypeError) as exc:
            QMessageBox.information(self, "Todavia no", str(exc))
            return
        self._resultado_amor(suceso, self._aplicar_amor(perfil, estado, e, suceso))

    def casarse(self, a_lo_grande: bool = True):
        perfil = self.perfil
        if perfil is None:
            return
        e = get_economia(perfil.id)
        hoy = self._hoy(e)
        try:
            estado, e, suceso = amor.casarse(get_estado_amor(perfil.id), e, hoy, a_lo_grande)
        except (ValueError, TypeError) as exc:
            QMessageBox.information(self, "Todavia no", str(exc))
            return
        self._resultado_amor(suceso, self._aplicar_amor(perfil, estado, e, suceso))

    def terminar_relacion(self):
        perfil = self.perfil
        estado = get_estado_amor(perfil.id) if perfil is not None else {}
        pareja = (estado or {}).get("pareja")
        if not pareja:
            return
        divorcio = estado.get("estado") == "casado"
        pregunta = (f"Seguro que te queres divorciar de {pareja['nombre']}? Te cuesta 10 semanas de sueldo."
                    if divorcio else f"Seguro que queres terminar con {pareja['nombre']}?")
        if not self._confirmar("Divorciarse" if divorcio else "Terminar la relacion", pregunta):
            return
        e = get_economia(perfil.id)
        hoy = self._hoy(e)
        if hoy is None:
            return
        estado, e, suceso = amor.terminar(estado, e, hoy)
        self._resultado_amor(suceso, self._aplicar_amor(perfil, estado, e, suceso))

    def mandar_dm(self, indice: int):
        perfil = self.perfil
        if perfil is None or indice >= len(self._resultados_dm):
            return
        e = get_economia(perfil.id)
        hoy = self._hoy(e)
        if hoy is None:
            return
        try:
            estado, e, suceso = amor.intentar(get_estado_amor(perfil.id), e, self._resultados_dm[indice],
                                              self._fama(), hoy)
        except ValueError as exc:
            QMessageBox.information(self, "Ahora no", str(exc))
            return
        set_estado_amor(perfil.id, estado)
        set_economia(perfil.id, e)
        self._contar_amor(perfil, suceso, estado)
        self.amor_eleccion.setText(f"<b>{esc(suceso.titulo)}</b>" + (
            f"<br><span style='color:{estilos.TEXTO_SUAVE}'>La captura ya circula...</span>" if not suceso.privado else ""))
        self.amor_eleccion.show()
        self._resultados_dm = []
        self._mostrar()

    def elegir_amor(self, opcion_id: str):
        perfil = self.perfil
        estado = get_estado_amor(perfil.id) if perfil is not None else {}
        if perfil is None or not estado.get("decision"):
            return
        from datetime import date

        hoy = self._carrera.fecha_actual() if self._carrera is not None and self._carrera.fecha_actual() else \
            date.fromisoformat(estado["hasta"])
        estado, e, suceso = amor.elegir(estado, get_economia(perfil.id), opcion_id, hoy)
        set_estado_amor(perfil.id, estado)
        set_economia(perfil.id, e)
        seguidores = self._contar_amor(perfil, suceso, estado)
        partes = [f"<b>{esc(suceso.titulo)}</b>"]
        if seguidores:
            partes.append(f"{_con_signo(seguidores)} seguidores")
        if suceso.dinero:
            partes.append(dinero(suceso.dinero, self._moneda()))
        self.amor_eleccion.setText(" · ".join(partes) + f"<br><span style='color:{estilos.TEXTO_SUAVE}'>"
                                   "La prensa ya se entero...</span>")
        self.amor_eleccion.show()
        self._mostrar()

    # ---- comprar y vender ----

    def _on_comprar(self, articulo_id: str):
        perfil, carrera = self.perfil, self._carrera
        if perfil is None or carrera is None or carrera.fecha_actual() is None:
            return
        articulo = POR_ID[articulo_id]
        hoy = carrera.fecha_actual()
        try:
            nueva = economia.comprar(get_economia(perfil.id), articulo, hoy)
        except economia.SinPlata as exc:
            QMessageBox.information(self, "No te alcanza", str(exc))
            return
        set_economia(perfil.id, nueva)
        self._aplicar_y_repercutir(perfil, carrera, articulo, "Donaste" if articulo.es_donacion else "Compraste")
        self._mostrar()

    def _aplicar_y_repercutir(self, perfil, carrera, articulo, accion: str):
        """Aplica lo que provoca (seguidores, reputacion), lo muestra y lanza
        en un hilo la noticia y los comentarios de los hinchas."""
        hoy = carrera.fecha_actual()
        efecto = economia.efecto(
            articulo, perfil, get_seguidores(perfil.id), get_reputacion_actual(perfil.id),
            get_economia(perfil.id).get("sueldo", 0), economia.mala_racha(carrera),
        )
        sumar_reputacion_y_seguidores(perfil.id, efecto.reputacion, efecto.seguidores, motivo=f"{accion}: {articulo.nombre}")

        partes = [f"<b>{accion}: {esc(articulo.nombre)}</b>", f"{_con_signo(efecto.seguidores)} seguidores"]
        if efecto.reputacion:
            partes.append(f"reputacion {_con_signo(efecto.reputacion)}")
        texto = " · ".join(partes)
        if articulo.detalle:
            texto += f"<br><span style='color:{estilos.TEXTO_SUAVE}'>{esc(autos.primera_mayuscula(articulo.detalle))}.</span>"
        if efecto.motivo:
            texto += f"<br><span style='color:{estilos.TEXTO_SUAVE}'>{esc(efecto.motivo[0].upper() + efecto.motivo[1:])}.</span>"
        texto += f"<br><span style='color:{estilos.TEXTO_SUAVE}'>Los hinchas estan comentando"
        texto += " y la prensa ya se entero...</span>" if efecto.es_noticia else "...</span>"
        self.resultado_label.setText(texto)
        self.resultado.show()
        self._ultima_compra = articulo.nombre
        self.compra_hecha.emit()
        ejecutar_en_hilo(
            economia.repercusion, perfil, articulo, efecto, self._moneda(), hoy.isoformat(),
            al_completar=self._on_repercusion, al_fallar=self._on_repercusion_error,
        )

    # ---- el concesionario ----

    def _on_configurar(self, modelo_id: str):
        if self.perfil is None:
            return
        dialogo = Configurador(autos.POR_ID[modelo_id], get_economia(self.perfil.id).get("saldo", 0), self._moneda(), self)
        if dialogo.exec() == QDialog.DialogCode.Accepted:
            self.pedir(dialogo.configuracion(), dialogo.foto)
        dialogo.deleteLater()

    def pedir(self, config: autos.Configuracion, foto=None):
        perfil, carrera = self.perfil, self._carrera
        if perfil is None or carrera is None or carrera.fecha_actual() is None:
            return
        try:
            nueva = economia.pedir_auto(get_economia(perfil.id), config, carrera.fecha_actual())
        except economia.SinPlata as exc:
            QMessageBox.information(self, "No te alcanza", str(exc))
            return
        pedido = nueva["pedidos"][-1]
        if foto is not None and not foto.isNull():
            pedido["foto"] = guardar_foto(foto, pedido["id"])
        set_economia(perfil.id, nueva)
        modelo = autos.POR_ID[config.modelo]
        entrega = pedido["entrega"]
        self._ultima_compra = None
        self.resultado_label.setText(
            f"<b>Pediste tu {esc(modelo.nombre_completo)}</b> · {dinero(pedido['precio'], self._moneda())}"
            f"<br><span style='color:{estilos.TEXTO_SUAVE}'>{esc(autos.primera_mayuscula(autos.describir(config)))}.<br>"
            f"Llega el {entrega[8:10]}/{entrega[5:7]}/{entrega[:4]} ({modelo.dias_entrega} dias del juego). "
            "Cuando llegue, la prensa y tus hinchas lo van a ver.</span>"
        )
        self.resultado.show()
        self._mostrar()

    def _on_repercusion(self, resultado):
        noticia, actividad = resultado
        if noticia is not None:
            save_noticia_prensa(noticia)
        save_actividad_instagram(actividad)  # los seguidores ya se sumaron al comprar
        if noticia is not None and not self.resultado.isHidden() and actividad.titulo == self._ultima_compra:
            self.resultado_label.setText(
                self.resultado_label.text().rsplit("<br>", 1)[0]
                + f"<br><span style='color:{estilos.ACENTO}'>En la prensa:</span> {esc(noticia.titular)}"
            )

    def _on_repercusion_error(self, _mensaje: str):
        pass  # los numeros ya se aplicaron; la nota de color no vale un cartel de error

    def _on_vender(self, posesion_id: str):
        if self.perfil is None or self._carrera is None or self._carrera.fecha_actual() is None:
            return
        nueva, recuperado = economia.vender(get_economia(self.perfil.id), posesion_id, self._carrera.fecha_actual())
        set_economia(self.perfil.id, nueva)
        self._ultima_compra = None
        self.resultado_label.setText(f"<b>Vendido</b> · recuperaste {dinero(recuperado, self._moneda())}")
        self.resultado.show()
        self._mostrar()
