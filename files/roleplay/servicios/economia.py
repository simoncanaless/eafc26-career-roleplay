"""
Economia y estilo de vida. El sueldo real del jugador (la partida de FC 26
lo guarda, por semana) se acredita a medida que pasan los dias del juego, y
con eso se compran casas, autos, relojes, un yate o un jet, o se dona.

Lo que cuesta y lo que provoca lo decide el codigo: cuantos seguidores
gana, si la reputacion sube o baja (una donacion suma; presumir un jet en
plena mala racha resta, y mas si el personaje es humilde), y si es noticia.
La noticia y los comentarios los escribe el motor narrativo (eventos.contar).

Los autos se piden en el concesionario (servicios/autos.py, marcas reales):
se pagan al pedir y llegan dias despues en el juego; lo que provocan
(seguidores, reputacion, noticia) pasa cuando llegan y se muestran.

Los autos de culto (JDM, Euro, Muscle) se compran al instante en el
marketplace (servicios/marketplace.py): articulo "nicho:<id>", se valorizan
con el tiempo segun su rareza y se revenden a ese valor.

Los patrocinios (servicios/patrocinios.py) pagan por semana y se cobran con
el sueldo (estado en economia.patrocinios).

Lo demas tambien se puede comprar de verdad en las webs oficiales
(servicios/tiendas.py, ui/tienda.py): un articulo "libre", con el nombre y
el precio que uno eligio, que se guarda con su tienda y su foto.

El dinero vive en estado_json.economia:
{"saldo", "hasta" (dia del juego hasta donde se cobro), "sueldo",
 "posesiones": [{"id", "articulo", "precio", "desde", ("config"), ("foto"),
                 ("nombre", "tienda", "url": los libres)}],
 "pedidos": [{"id", "modelo", "config", "precio", "pedido", "entrega", ("foto")}],
 "movimientos": [{"fecha", "concepto", "monto"}]}  (el mas nuevo primero)
Un auto en posesiones tiene articulo "auto:<modelo>" (su foto en garage/);
uno libre, "libre:<categoria>" (su foto en compras/).
"""

import copy
import uuid
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Optional

from roleplay.models import ActividadInstagram, NoticiaPrensa, PlayerProfile
from roleplay.partida.carrera import Carrera
from roleplay.servicios import autos

NETO = 0.55  # lo que queda del sueldo despues de impuestos y la comision del agente
VENTA = 0.70  # lo que se recupera al vender algo
MOVIMIENTOS_GUARDADOS = 60
SEMANAS_PARA_SER_NOTICIA = 26  # algo que cuesta medio anio de sueldo es noticia aunque sea discreto


@dataclass(frozen=True)
class Articulo:
    id: str
    categoria: str  # casa | auto | reloj | moda | yate | avion | tecnologia | muebles | donacion
    nombre: str
    precio: int
    mantenimiento: int = 0  # por semana
    ostentoso: bool = False
    detalle: str = ""  # como esta configurado (los autos del concesionario)
    tienda: str = ""  # donde se compro (los libres: la web oficial)

    @property
    def es_donacion(self) -> bool:
        return self.categoria == "donacion"


CATEGORIAS = {
    "casa": "Casas",
    "auto": "Autos",
    "reloj": "Relojes y joyas",
    "moda": "Ropa y moda",
    "yate": "Yates",
    "avion": "Aviones",
    "tecnologia": "Tecnologia",
    "muebles": "Muebles",
    "usados": "Usados y de culto",
}

# Casas, ropa y muebles sin marca; los relojes y joyas de alta gama, con la marca
# como texto (como los autos: decision de Simon, la app es entre amigos).
# Precios aproximados de la vida real, en la moneda del club.
CATALOGO = [
    Articulo("depto", "casa", "Departamento en el centro", 650_000, 1_500),
    Articulo("loft", "casa", "Loft de diseno en un barrio de moda", 1_400_000, 2_500),
    Articulo("casa_jardin", "casa", "Casa con jardin en las afueras", 2_500_000, 4_000),
    Articulo("penthouse", "casa", "Penthouse con vista a toda la ciudad", 6_500_000, 9_000, ostentoso=True),
    Articulo("mansion", "casa", "Mansion con pileta y cine", 9_000_000, 15_000, ostentoso=True),
    Articulo("mansion_colinas", "casa", "Mansion en las colinas con cancha propia", 18_000_000, 25_000, ostentoso=True),
    Articulo("villa_mar", "casa", "Villa frente al mar", 22_000_000, 30_000, ostentoso=True),
    Articulo("reloj_suizo", "reloj", "Reloj suizo", 60_000),
    Articulo("rolex_submariner", "reloj", "Rolex Submariner", 14_000),
    Articulo("cartier_love", "reloj", "Pulsera Cartier Love de oro", 9_000),
    Articulo("rolex_daytona", "reloj", "Rolex Daytona de oro", 55_000),
    Articulo("ap_royal_oak", "reloj", "Audemars Piguet Royal Oak", 75_000),
    Articulo("ap_royal_oak_diamantes", "reloj", "Audemars Piguet Royal Oak con diamantes", 320_000, ostentoso=True),
    Articulo("cadena", "reloj", "Cadena de oro y diamantes", 250_000, ostentoso=True),
    Articulo("anillo_diamantes", "reloj", "Anillo de diamantes", 120_000),
    Articulo("collar_diamantes", "reloj", "Collar de diamantes a medida", 450_000, ostentoso=True),
    Articulo("reloj_diamantes", "reloj", "Reloj de alta relojeria con diamantes", 900_000, ostentoso=True),
    Articulo("zapatillas", "moda", "Zapatillas de edicion limitada", 6_000),
    Articulo("outfit_alfombra", "moda", "Outfit de disenador para la alfombra roja", 25_000),
    Articulo("abrigo_costura", "moda", "Abrigo de alta costura", 45_000),
    Articulo("guardarropa", "moda", "Guardarropa de disenador", 80_000, 500),
    Articulo("coleccion_moda", "moda", "Coleccion de alta costura", 400_000, 1_500, ostentoso=True),
    Articulo("yate", "yate", "Yate de 30 metros", 12_000_000, 40_000, ostentoso=True),
    Articulo("jet", "avion", "Jet privado", 45_000_000, 90_000, ostentoso=True),
    Articulo("setup_gamer", "tecnologia", "Setup gamer de alta gama", 25_000),
    Articulo("home_cinema", "tecnologia", "Sala de cine en casa", 150_000, 500),
    Articulo("simulador", "tecnologia", "Simulador de carreras profesional", 400_000, 1_000, ostentoso=True),
    Articulo("living", "muebles", "Living de disenador", 60_000),
    Articulo("sofa_italiano", "muebles", "Sofa de disenador italiano", 35_000),
    Articulo("comedor_marmol", "muebles", "Comedor de marmol para doce", 90_000),
    Articulo("bodega", "muebles", "Bodega de vinos climatizada", 250_000, 500, ostentoso=True),
    Articulo("cocina", "muebles", "Cocina a medida", 180_000),
    Articulo("arte", "muebles", "Coleccion de arte para la casa", 1_200_000, 2_000, ostentoso=True),
    Articulo("hospital", "donacion", "Donar a un hospital de ninos", 500_000),
    Articulo("damnificados", "donacion", "Ayudar a los damnificados de una catastrofe", 250_000),
    Articulo("escuela", "donacion", "Financiar una escuela de futbol en tu barrio de origen", 1_500_000),
    Articulo("fundacion", "donacion", "Crear tu propia fundacion", 5_000_000),
]
# los autos genericos de la primera version: ya no se venden (ahora esta el
# concesionario), pero si alguien los compro siguen en su garage
ANTERIORES = [
    Articulo("auto_aleman", "auto", "Deportivo aleman", 180_000, 1_000),
    Articulo("superdeportivo", "auto", "Superdeportivo italiano", 450_000, 2_500, ostentoso=True),
    Articulo("hiperdeportivo", "auto", "Hiperdeportivo de edicion limitada", 2_800_000, 8_000, ostentoso=True),
]
POR_ID = {a.id: a for a in CATALOGO + ANTERIORES}

# lo libre (de una web oficial): desde cuanto es ostentoso y cuanto cuesta
# mantenerlo por semana (una parte del precio), segun la categoria
OSTENTOSO_LIBRE = {"casa": 5_000_000, "reloj": 100_000, "moda": 150_000, "yate": 0, "avion": 0,
                   "tecnologia": 100_000, "muebles": 300_000}
MANTENIMIENTO_LIBRE = {"casa": 0.0017, "yate": 0.0033, "avion": 0.002}
LIBRE = "libre:"


def articulo_libre(categoria: str, nombre: str, precio: int, tienda: str = "") -> Articulo:
    """Lo que se eligio en una web oficial, con el nombre y el precio de ahi."""
    return Articulo(
        f"{LIBRE}{categoria}", categoria, nombre.strip(), int(precio),
        round(precio * MANTENIMIENTO_LIBRE.get(categoria, 0)), precio >= OSTENTOSO_LIBRE.get(categoria, 200_000),
        f"de {tienda}" if tienda else "", tienda,
    )

# moneda segun la liga del club (id de liga + 1, como en la base de EA)
LIGAS_EN_LIBRAS = {13, 14, 50, 60, 61}  # Premier, Championship, Escocia, League One y Two
LIGAS_EN_DOLARES = {39}  # MLS


def moneda_de(carrera: Optional[Carrera]) -> str:
    if carrera is None:
        return "€"
    liga = carrera.ligas_de_equipo.get(carrera.equipo_usuario())
    return "£" if liga in LIGAS_EN_LIBRAS else "$" if liga in LIGAS_EN_DOLARES else "€"


def dinero(monto: float, moneda: str) -> str:
    """145000 -> '£145.000'; 4200000 -> '£4,2 M'."""
    signo = "-" if monto < 0 else ""
    monto = abs(monto)
    if monto >= 1_000_000:
        texto = f"{monto / 1_000_000:.1f}".replace(".", ",").removesuffix(",0") + " M"
    else:
        texto = f"{round(monto):,}".replace(",", ".")
    return f"{signo}{moneda}{texto}"


# ---- el sueldo ----


def _movimiento(economia: dict, dia: date, concepto: str, monto: int) -> None:
    economia.setdefault("movimientos", []).insert(0, {"fecha": dia.isoformat(), "concepto": concepto, "monto": monto})
    del economia["movimientos"][MOVIMIENTOS_GUARDADOS:]


def inicio_de_temporada(dia: date) -> date:
    return date(dia.year if dia.month >= 7 else dia.year - 1, 7, 1)


def acreditar(economia: Optional[dict], hoy: date, sueldo: int) -> dict:
    """La economia al dia `hoy` del juego (una copia). La primera vez, el
    saldo es lo cobrado en lo que va de la temporada. Despues, se suma el
    sueldo neto de los dias que pasaron y se resta el mantenimiento de lo
    que tiene. Llamarla dos veces el mismo dia no cobra dos veces."""
    if not economia:
        semanas = (hoy - inicio_de_temporada(hoy)).days / 7
        nueva = {"saldo": round(sueldo * NETO * semanas), "hasta": hoy.isoformat(), "sueldo": sueldo,
                 "posesiones": [], "movimientos": []}
        _movimiento(nueva, hoy, "Lo cobrado en lo que va de la temporada", nueva["saldo"])
        return nueva
    e = copy.deepcopy(economia)
    if sueldo != e.get("sueldo"):
        e["sueldo"] = sueldo
        _movimiento(e, hoy, f"Contrato nuevo: {sueldo:,} por semana".replace(",", "."), 0)
    dias = (hoy - date.fromisoformat(e["hasta"])).days
    if dias < 0:
        e["hasta"] = hoy.isoformat()  # se cargo una partida anterior: se cobra desde aca
    if dias <= 0:
        return e
    semanas = dias / 7
    ingreso = round(sueldo * NETO * semanas)
    gastos = round(mantenimiento_semanal(e) * semanas)
    from roleplay.servicios import contratos, patrocinios

    marcas = round(patrocinios.ingreso_semanal(e, hoy) * NETO * semanas)
    imagen = round(contratos.ingreso_semanal(e, hoy) * NETO * semanas)
    e["saldo"] += ingreso + marcas + imagen - gastos
    _movimiento(e, hoy, f"Sueldo de {dias} dias (neto)", ingreso)
    if marcas:
        _movimiento(e, hoy, f"Patrocinios de {dias} dias (neto)", marcas)
    if imagen:
        _movimiento(e, hoy, f"Derechos de imagen de {dias} dias (neto)", imagen)
    if gastos:
        _movimiento(e, hoy, "Mantenimiento de lo que tenes", -gastos)
    e["hasta"] = hoy.isoformat()
    return e


def articulo_de_posesion(posesion: dict) -> Optional[Articulo]:
    """El articulo de algo que tiene: del catalogo, un auto configurado o algo libre."""
    if posesion["articulo"].startswith("nicho:"):
        from roleplay.servicios import marketplace

        return marketplace.articulo_de_posesion(posesion)
    if posesion["articulo"].startswith(LIBRE):
        return articulo_libre(posesion["articulo"][len(LIBRE):], posesion.get("nombre", "Algo"), posesion["precio"],
                              posesion.get("tienda", ""))
    if posesion["articulo"].startswith("auto:"):
        modelo = autos.POR_ID.get(posesion["articulo"][5:])
        if modelo is None:
            return None
        config = autos.Configuracion.desde_dict(posesion.get("config", {"modelo": modelo.id}))
        return Articulo(
            posesion["articulo"], "auto", modelo.nombre_completo, posesion["precio"],
            autos.mantenimiento(posesion["precio"]), posesion["precio"] >= autos.OSTENTOSO_DESDE, autos.describir(config),
        )
    return POR_ID.get(posesion["articulo"])


def mantenimiento_semanal(economia: dict) -> int:
    return sum(a.mantenimiento for p in economia.get("posesiones", []) if (a := articulo_de_posesion(p)))


def valor_de_venta(posesion: dict, hoy: Optional[date] = None) -> int:
    """Lo que se recupera vendiendolo: el 70%, salvo los autos de culto del
    marketplace, que se revenden a lo que valen hoy (menos la comision)."""
    if posesion["articulo"].startswith("nicho:"):
        from roleplay.servicios import marketplace

        return marketplace.valor_de_reventa(posesion, hoy or date.fromisoformat(posesion.get("desde") or "2000-01-01"))
    from roleplay.servicios import configurador

    # los opcionales de prestigio del configurador oficial (Paint to Sample, Weissach...) se pagan en la reventa
    return round(posesion["precio"] * VENTA) + configurador.bonus_de_reventa((posesion.get("config") or {}).get("oficial"))


def patrimonio(economia: dict) -> int:
    """Lo que vale lo que tiene (lo que se recuperaria vendiendo)."""
    hoy = date.fromisoformat(economia["hasta"]) if economia.get("hasta") else None
    return round(sum(valor_de_venta(p, hoy) for p in economia.get("posesiones", [])))


def tiene(economia: dict, articulo_id: str) -> bool:
    return any(p["articulo"] == articulo_id for p in economia.get("posesiones", []))


# ---- comprar, donar, vender ----


class SinPlata(ValueError):
    pass


def comprar(economia: dict, articulo: Articulo, hoy: date, extra: Optional[dict] = None) -> dict:
    """`extra`: lo que se guarda ademas en la posesion (lo libre: nombre, tienda, url, foto)."""
    if economia.get("saldo", 0) < articulo.precio:
        raise SinPlata(f"No te alcanza: cuesta {articulo.precio:,} y tenes {economia.get('saldo', 0):,}".replace(",", "."))
    e = copy.deepcopy(economia)
    e["saldo"] -= articulo.precio
    if articulo.es_donacion:
        _movimiento(e, hoy, articulo.nombre, -articulo.precio)
    else:
        posesion = {"id": uuid.uuid4().hex[:8], "articulo": articulo.id, "precio": articulo.precio,
                    "desde": hoy.isoformat()}
        if articulo.id.startswith(LIBRE) or articulo.id.startswith("nicho:"):
            posesion.update({"nombre": articulo.nombre, "tienda": articulo.tienda})
        posesion.update(extra or {})
        e.setdefault("posesiones", []).append(posesion)
        _movimiento(e, hoy, f"Compra: {articulo.nombre}", -articulo.precio)
    return e


def vender(economia: dict, posesion_id: str, hoy: date) -> tuple[dict, int]:
    e = copy.deepcopy(economia)
    posesion = next(p for p in e.get("posesiones", []) if p["id"] == posesion_id)
    e["posesiones"].remove(posesion)
    recuperado = valor_de_venta(posesion, hoy)
    e["saldo"] += recuperado
    articulo = articulo_de_posesion(posesion)
    _movimiento(e, hoy, f"Venta: {articulo.nombre if articulo else posesion['articulo']}", recuperado)
    return e, recuperado


# ---- el concesionario: pedir y recibir ----


def pedir_auto(economia: dict, config: autos.Configuracion, hoy: date) -> dict:
    total = autos.precio(config)
    if economia.get("saldo", 0) < total:
        raise SinPlata(f"No te alcanza: cuesta {total:,} y tenes {economia.get('saldo', 0):,}".replace(",", "."))
    modelo = autos.POR_ID[config.modelo]
    e = copy.deepcopy(economia)
    e["saldo"] -= total
    e.setdefault("pedidos", []).append({
        "id": uuid.uuid4().hex[:8], "modelo": modelo.id, "config": config.a_dict(), "precio": total,
        "pedido": hoy.isoformat(), "entrega": (hoy + timedelta(days=modelo.dias_entrega)).isoformat(),
    })
    _movimiento(e, hoy, f"Pedido: {modelo.nombre_completo}", -total)
    return e


def entregar_pedidos(economia: dict, hoy: date) -> tuple[dict, list[dict]]:
    """Los pedidos cuya fecha de entrega ya paso en el juego pasan al
    garage. Devuelve (economia, posesiones nuevas)."""
    listos = [p for p in economia.get("pedidos", []) if p["entrega"] <= hoy.isoformat()]
    if not listos:
        return economia, []
    e = copy.deepcopy(economia)
    entregados = []
    for pedido in listos:
        e["pedidos"] = [p for p in e["pedidos"] if p["id"] != pedido["id"]]
        posesion = {"id": pedido["id"], "articulo": f"auto:{pedido['modelo']}", "precio": pedido["precio"],
                    "desde": hoy.isoformat(), "config": pedido["config"]}
        if pedido.get("foto"):
            posesion["foto"] = pedido["foto"]  # la que se saco en el configurador
        e.setdefault("posesiones", []).append(posesion)
        entregados.append(posesion)
        _movimiento(e, hoy, f"Te llego: {autos.POR_ID[pedido['modelo']].nombre_completo}", 0)
    return e, entregados


# ---- lo que provoca ----


@dataclass
class Efecto:
    seguidores: int
    reputacion: int
    es_noticia: bool
    tono: str  # positiva | negativa | mixta | neutral
    motivo: str  # por que cayo asi (para la pantalla y la noticia)


def mala_racha(carrera: Optional[Carrera]) -> bool:
    """Dos o mas derrotas en los ultimos tres partidos del club."""
    if carrera is None or carrera.equipo_usuario() is None:
        return False
    equipo = carrera.equipo_usuario()
    ultimos = carrera.partidos_de(equipo, jugados=True)[-3:]
    return sum(p.resultado_para(equipo) == "derrota" for p in ultimos) >= 2


def efecto(
    articulo: Articulo, perfil: PlayerProfile, seguidores: int, reputacion: int, sueldo: int, en_mala_racha: bool
) -> Efecto:
    from roleplay.servicios.hinchada import _escala  # la misma escala que mueve los partidos

    escala = _escala(seguidores, reputacion)
    semanas = articulo.precio / max(sueldo * NETO, 1)  # cuantas semanas de sueldo cuesta
    if articulo.es_donacion:
        return Efecto(
            seguidores=round(escala * (1 + min(semanas, 40) / 8)),
            reputacion=max(1, min(8, 1 + round(semanas / 4))),
            es_noticia=True,
            tono="positiva",
            motivo="una donacion siempre cae bien",
        )
    seguidores_ganados = escala * (1.0 if articulo.ostentoso else 0.2) * min(3.0, 1 + semanas / 20)
    reputacion_cambio, tono, motivos = 0, "neutral", []
    if articulo.ostentoso:
        tono = "mixta"
        if en_mala_racha:
            reputacion_cambio -= 3
            tono = "negativa"
            motivos.append("en plena mala racha del equipo")
        if perfil.personalidad in ("humilde", "reservado"):
            reputacion_cambio -= 1
            motivos.append("choca con su imagen de bajo perfil")
        elif perfil.personalidad in ("carismatico", "polemico"):
            seguidores_ganados *= 1.3
            motivos.append("a sus seguidores les encanta el show")
    return Efecto(
        seguidores=round(seguidores_ganados),
        reputacion=reputacion_cambio,
        es_noticia=articulo.ostentoso or semanas >= SEMANAS_PARA_SER_NOTICIA,
        tono=tono,
        motivo="; ".join(motivos),
    )


# ---- la repercusion: noticia (si es noticia) y comentarios ----


def _descripcion(perfil: PlayerProfile, articulo: Articulo, efecto_: Efecto, moneda: str) -> str:
    precio = dinero(articulo.precio, moneda)
    if articulo.es_donacion:  # los nombres de las donaciones ya son una accion: "Donar a ..."
        texto = f"{perfil.nombre_jugador} decidio {articulo.nombre[0].lower()}{articulo.nombre[1:]} ({precio})"
    elif articulo.id.startswith("auto:"):
        texto = f"{perfil.nombre_jugador} recibio su nuevo {articulo.nombre} ({articulo.detalle}; {precio})"
    elif articulo.tienda:
        texto = f"{perfil.nombre_jugador} se compro en {articulo.tienda}: {articulo.nombre} ({precio})"
    else:
        texto = f"{perfil.nombre_jugador} se compro: {articulo.nombre} ({precio})"
    return texto + (f", {efecto_.motivo}" if efecto_.motivo else "")


def _titulo(perfil: PlayerProfile, articulo: Articulo) -> str:
    partes = perfil.nombre_jugador.split()
    apellido = partes[-1] if partes else "El jugador"
    if articulo.es_donacion:
        return f"El gesto de {apellido}: {articulo.nombre[0].lower()}{articulo.nombre[1:]}"
    if articulo.id.startswith("auto:"):
        return f"{apellido} estrena su {articulo.nombre}"
    if articulo.tienda:  # el nombre de una web oficial suele empezar con la marca: tal cual
        return f"{apellido} se da un gusto: {articulo.nombre}"
    return f"{apellido} se da un gusto: {articulo.nombre[0].lower()}{articulo.nombre[1:]}"


def repercusion(
    perfil: PlayerProfile, articulo: Articulo, efecto_: Efecto, moneda: str, fecha_juego: str
) -> tuple[Optional[NoticiaPrensa], ActividadInstagram]:
    """La noticia (si es noticia) y lo que dicen los hinchas
    (servicios/eventos.contar). Los numeros ya se aplicaron antes."""
    from roleplay.servicios.eventos import contar
    from roleplay.servicios.hinchada import EventoHinchada, comentar_eventos

    descripcion = _descripcion(perfil, articulo, efecto_, moneda)
    tipo = "donacion" if articulo.es_donacion else "entrega" if articulo.id.startswith("auto:") else "compra"
    if efecto_.es_noticia:
        noticia, actividad = contar(perfil, _titulo(perfil, articulo), descripcion, efecto_.tono, efecto_.seguidores,
                                    fecha_juego, f"{'donacion' if articulo.es_donacion else 'compra'}:{articulo.id}",
                                    tipo)
        actividad.titulo = articulo.nombre
        return noticia, actividad
    evento = EventoHinchada(tipo, fecha_juego, articulo.nombre, descripcion, efecto_.seguidores)
    actividad = ActividadInstagram(
        player_id=perfil.id, fecha_juego=fecha_juego, tipo=tipo, titulo=articulo.nombre,
        crecimiento_seguidores=efecto_.seguidores, comentarios=comentar_eventos(perfil, [evento]).get(0, []),
    )
    return None, actividad


def carpeta_de_foto(posesion: dict) -> str:
    """Donde vive la foto de una posesion (o pedido), relativo a los datos de la app."""
    return "garage" if posesion.get("config") or posesion.get("articulo", "").startswith("auto:") else "compras"


def leer_partida_para_economia() -> Optional[Carrera]:
    """Para la pagina (corre en un hilo)."""
    from roleplay.partida.lector import carrera_actual

    return carrera_actual()
