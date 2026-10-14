"""
Economia y estilo de vida. El sueldo real del jugador (la partida de FC 26
lo guarda, por semana) se acredita a medida que pasan los dias del juego, y
con eso se compran casas, autos, relojes, un yate o un jet, o se dona.

Lo que cuesta y lo que provoca lo decide el codigo: cuantos seguidores
gana, si la reputacion sube o baja (una donacion suma; presumir un jet en
plena mala racha resta, y mas si el personaje es humilde), y si es noticia.
La IA solo redacta la noticia y los comentarios de los hinchas.

El dinero vive en estado_json.economia:
{"saldo", "hasta" (dia del juego hasta donde se cobro), "sueldo",
 "posesiones": [{"id", "articulo", "precio", "desde"}],
 "movimientos": [{"fecha", "concepto", "monto"}]}  (el mas nuevo primero)
"""

import copy
import uuid
from dataclasses import dataclass
from datetime import date
from typing import Optional

from pydantic import BaseModel

from roleplay.gemini import generar_json
from roleplay.models import ActividadInstagram, NoticiaPrensa, PlayerProfile
from roleplay.partida.carrera import Carrera
from roleplay.servicios.contexto import ficha_jugador

NETO = 0.55  # lo que queda del sueldo despues de impuestos y la comision del agente
VENTA = 0.70  # lo que se recupera al vender algo
MOVIMIENTOS_GUARDADOS = 60
SEMANAS_PARA_SER_NOTICIA = 26  # algo que cuesta medio anio de sueldo es noticia aunque sea discreto


@dataclass(frozen=True)
class Articulo:
    id: str
    categoria: str  # casa | auto | reloj | moda | yate | avion | donacion
    nombre: str
    precio: int
    mantenimiento: int = 0  # por semana
    ostentoso: bool = False

    @property
    def es_donacion(self) -> bool:
        return self.categoria == "donacion"


CATEGORIAS = {
    "casa": "Casas",
    "auto": "Autos",
    "reloj": "Relojes y joyas",
    "moda": "Moda",
    "yate": "Yates",
    "avion": "Aviones",
}

# Sin marcas: el roleplay no necesita nombres reales y asi nada parece publicidad.
CATALOGO = [
    Articulo("depto", "casa", "Departamento en el centro", 650_000, 1_500),
    Articulo("casa_jardin", "casa", "Casa con jardin en las afueras", 2_500_000, 4_000),
    Articulo("mansion", "casa", "Mansion con pileta y cine", 9_000_000, 15_000, ostentoso=True),
    Articulo("villa_mar", "casa", "Villa frente al mar", 22_000_000, 30_000, ostentoso=True),
    Articulo("auto_aleman", "auto", "Deportivo aleman", 180_000, 1_000),
    Articulo("superdeportivo", "auto", "Superdeportivo italiano", 450_000, 2_500, ostentoso=True),
    Articulo("hiperdeportivo", "auto", "Hiperdeportivo de edicion limitada", 2_800_000, 8_000, ostentoso=True),
    Articulo("reloj_suizo", "reloj", "Reloj suizo", 60_000),
    Articulo("cadena", "reloj", "Cadena de oro y diamantes", 250_000, ostentoso=True),
    Articulo("reloj_diamantes", "reloj", "Reloj de alta relojeria con diamantes", 900_000, ostentoso=True),
    Articulo("guardarropa", "moda", "Guardarropa de disenador", 80_000, 500),
    Articulo("coleccion_moda", "moda", "Coleccion de alta costura", 400_000, 1_500, ostentoso=True),
    Articulo("yate", "yate", "Yate de 30 metros", 12_000_000, 40_000, ostentoso=True),
    Articulo("jet", "avion", "Jet privado", 45_000_000, 90_000, ostentoso=True),
    Articulo("hospital", "donacion", "Donar a un hospital de ninos", 500_000),
    Articulo("damnificados", "donacion", "Ayudar a los damnificados de una catastrofe", 250_000),
    Articulo("escuela", "donacion", "Financiar una escuela de futbol en tu barrio de origen", 1_500_000),
    Articulo("fundacion", "donacion", "Crear tu propia fundacion", 5_000_000),
]
POR_ID = {a.id: a for a in CATALOGO}

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
    e["saldo"] += ingreso - gastos
    _movimiento(e, hoy, f"Sueldo de {dias} dias (neto)", ingreso)
    if gastos:
        _movimiento(e, hoy, "Mantenimiento de lo que tenes", -gastos)
    e["hasta"] = hoy.isoformat()
    return e


def mantenimiento_semanal(economia: dict) -> int:
    return sum(POR_ID[p["articulo"]].mantenimiento for p in economia.get("posesiones", []) if p["articulo"] in POR_ID)


def patrimonio(economia: dict) -> int:
    """Lo que vale lo que tiene (lo que se recuperaria vendiendo)."""
    return round(sum(p["precio"] * VENTA for p in economia.get("posesiones", [])))


def tiene(economia: dict, articulo_id: str) -> bool:
    return any(p["articulo"] == articulo_id for p in economia.get("posesiones", []))


# ---- comprar, donar, vender ----


class SinPlata(ValueError):
    pass


def comprar(economia: dict, articulo: Articulo, hoy: date) -> dict:
    if economia.get("saldo", 0) < articulo.precio:
        raise SinPlata(f"No te alcanza: cuesta {articulo.precio:,} y tenes {economia.get('saldo', 0):,}".replace(",", "."))
    e = copy.deepcopy(economia)
    e["saldo"] -= articulo.precio
    if articulo.es_donacion:
        _movimiento(e, hoy, articulo.nombre, -articulo.precio)
    else:
        e.setdefault("posesiones", []).append(
            {"id": uuid.uuid4().hex[:8], "articulo": articulo.id, "precio": articulo.precio, "desde": hoy.isoformat()}
        )
        _movimiento(e, hoy, f"Compra: {articulo.nombre}", -articulo.precio)
    return e


def vender(economia: dict, posesion_id: str, hoy: date) -> tuple[dict, int]:
    e = copy.deepcopy(economia)
    posesion = next(p for p in e.get("posesiones", []) if p["id"] == posesion_id)
    e["posesiones"].remove(posesion)
    recuperado = round(posesion["precio"] * VENTA)
    e["saldo"] += recuperado
    articulo = POR_ID.get(posesion["articulo"])
    _movimiento(e, hoy, f"Venta: {articulo.nombre if articulo else posesion['articulo']}", recuperado)
    return e, recuperado


# ---- lo que provoca ----


@dataclass
class Efecto:
    seguidores: int
    reputacion: int
    es_noticia: bool
    tono: str  # positiva | negativa | mixta | neutral
    motivo: str  # por que cayo asi (para la pantalla y para la IA)


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


# ---- la repercusion: noticia (si es noticia) y comentarios (la IA) ----


class NoticiaCompra(BaseModel):
    titular: str
    cuerpo: str


def _descripcion(perfil: PlayerProfile, articulo: Articulo, efecto_: Efecto, moneda: str) -> str:
    precio = dinero(articulo.precio, moneda)
    if articulo.es_donacion:  # los nombres de las donaciones ya son una accion: "Donar a ..."
        texto = f"{perfil.nombre_jugador} decidio {articulo.nombre[0].lower()}{articulo.nombre[1:]} ({precio})"
    else:
        texto = f"{perfil.nombre_jugador} se compro: {articulo.nombre} ({precio})"
    return texto + (f"; {efecto_.motivo}" if efecto_.motivo else "")


def repercusion(
    perfil: PlayerProfile, articulo: Articulo, efecto_: Efecto, moneda: str, fecha_juego: str, contexto_real: str = ""
) -> tuple[Optional[NoticiaPrensa], ActividadInstagram]:
    """Corre en un hilo. La noticia (si corresponde) y lo que dicen los
    hinchas. Sin IA: la noticia sale con un titular armado por el codigo y
    los hinchas sin comentarios; los numeros ya se aplicaron igual."""
    from roleplay.servicios.hinchada import EventoHinchada, comentar_eventos

    descripcion = _descripcion(perfil, articulo, efecto_, moneda)
    noticia = None
    if efecto_.es_noticia:
        try:
            redactada = generar_json(
                f"""
Sos un periodista de la prensa del corazon y deportiva. Escribi una noticia
corta (titular + 2 a 4 frases, en espanol) sobre esto, en un modo carrera
roleplay de EAFC 26:

{descripcion}.
{ficha_jugador(perfil)}
{contexto_real}
El tono de la noticia es {efecto_.tono} (respetalo). Sin marcas ni nombres
de personas reales. No inventes resultados ni datos que no esten arriba.
""".strip(),
                NoticiaCompra,
                "No se pudo escribir la noticia esta vez.",
            )
            titular, cuerpo = redactada.titular.strip(), redactada.cuerpo.strip()
        except RuntimeError:
            titular = descripcion[0].upper() + descripcion[1:]
            cuerpo = ""
        noticia = NoticiaPrensa(
            player_id=perfil.id, categoria="jugador", tono=efecto_.tono, titular=titular, cuerpo=cuerpo,
            hitos=[f"{'donacion' if articulo.es_donacion else 'compra'}:{articulo.id}"],
        )

    evento = EventoHinchada(
        "donacion" if articulo.es_donacion else "compra", fecha_juego, articulo.nombre, descripcion, efecto_.seguidores
    )
    try:
        comentarios = comentar_eventos(perfil, [evento], contexto_real).get(0, [])
    except RuntimeError:
        comentarios = []
    actividad = ActividadInstagram(
        player_id=perfil.id, fecha_juego=fecha_juego, tipo=evento.tipo, titulo=articulo.nombre,
        crecimiento_seguidores=efecto_.seguidores, comentarios=comentarios,
    )
    return noticia, actividad


def leer_partida_para_economia() -> Optional[Carrera]:
    """Para la pagina (corre en un hilo)."""
    from roleplay.partida.lector import carrera_actual

    return carrera_actual()
