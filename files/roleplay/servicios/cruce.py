"""
Inyeccion de estado cruzado: lo que pasa en el resto de la vida del jugador
y que la prensa, los periodistas y los hinchas tienen que tener presente.

Lee estado_json (economia, amor, metas, clubes, eventos) y devuelve los
"cruces" que valen la pena, con un peso para elegir el mas jugoso:
- compro algo caro hace poco y jugo mal -> se lo reprochan (modelo y precio);
- esta en pareja (o lo vieron con una famosa) -> el palco, la dedicatoria;
- esta cerca de cumplir (o de fallar) una meta -> la cuenta regresiva;
- juega contra un ex club donde se fue como idolo o como traidor -> el morbo;
- le paso algo hace poco (una multa, la fiesta del yate, la visita al hospital).

Solo lee: quien escribe decide que hacer con cada cruce.
"""

from dataclasses import dataclass, field
from datetime import date
from typing import Optional

from roleplay import database
from roleplay.servicios import clubes, economia

DIAS_COMPRA_RECIENTE = 45
DIAS_EVENTO_RECIENTE = 21
PRECIO_QUE_LLAMA_LA_ATENCION = 150_000
RATING_FLOJO = 6.2
RATING_ALTO = 8.0
EVENTOS_MALOS = {"multa_velocidad", "choque_leve", "fiesta_yate", "polemica_redes", "increpado", "llegada_tarde"}


@dataclass
class Cruce:
    tipo: str  # compra_mal | compra_bien | pareja_real | pareja_famosa | rumor | crisis | meta_cerca | meta_tabla |
    #            ex_club_traidor | ex_club_idolo | ex_club_mala | evento_malo | evento_bueno | hinchada_contra | idolo
    peso: float
    datos: dict = field(default_factory=dict)


def _hoy(e: dict, carrera) -> Optional[date]:
    if carrera is not None and carrera.fecha_actual() is not None:
        return carrera.fecha_actual()
    for valor in (e.get("hasta"),):
        if valor:
            return date.fromisoformat(valor)
    return None


def _dias(desde: str, hoy: Optional[date]) -> int:
    if not desde or hoy is None:
        return 10_000
    return (hoy - date.fromisoformat(desde)).days


def _compra(e: dict, hoy, rating: Optional[float], moneda: str) -> Optional[Cruce]:
    recientes = [p for p in e.get("posesiones", []) if _dias(p.get("desde", ""), hoy) <= DIAS_COMPRA_RECIENTE]
    recientes = [p for p in recientes if p.get("precio", 0) >= PRECIO_QUE_LLAMA_LA_ATENCION]
    if not recientes:
        return None
    posesion = max(recientes, key=lambda p: (p.get("desde", ""), p.get("precio", 0)))
    articulo = economia.articulo_de_posesion(posesion)
    if articulo is None:
        return None
    datos = {"articulo": articulo.nombre, "precio": economia.dinero(posesion["precio"], moneda)}
    if rating is not None and rating < RATING_FLOJO:
        return Cruce("compra_mal", 9, datos)
    if rating is not None and rating >= RATING_ALTO:
        return Cruce("compra_bien", 4, datos)
    return Cruce("compra_bien", 2, datos)


def _amor(estado: dict) -> Optional[Cruce]:
    pareja = estado.get("pareja")
    if not pareja:
        return None
    datos = {"pareja": pareja["nombre"], "oficio": pareja.get("oficio", "")}
    if estado.get("estado") == "conociendo":
        return Cruce("rumor", 6, datos)
    if pareja.get("real"):
        return Cruce("pareja_real", 4, datos)  # una persona real: con respeto, nada de crisis
    if pareja.get("relacion", 50) < 25:
        return Cruce("crisis", 7, datos)
    return Cruce("pareja_famosa", 5, datos)


def _meta(lista: list[dict], temporada: Optional[str], carrera=None) -> Optional[Cruce]:
    from roleplay.servicios import metas  # metas -> partida_real -> prensa -> cruce: adentro, no arriba

    mejores = []
    for meta in lista:
        if meta.get("estado") != "en_curso" or (temporada and meta.get("temporada") != temporada):
            continue
        # con la partida, lo que lleva HOY (lo guardado es de la ultima revision de la prensa)
        actual = metas.progreso(carrera, meta) if carrera is not None else meta.get("actual")
        if actual is None:
            continue
        datos = {"meta": metas.texto_meta(meta).lower(), "objetivo": meta["objetivo"], "actual": actual}
        if meta["tipo"] in metas.CONTABLES:
            faltan = meta["objetivo"] - actual
            if 0 < faltan <= max(3, round(meta["objetivo"] * 0.15)):
                unidad = "asistencias" if meta["tipo"] == "asistencias" else "goles"
                if faltan == 1:
                    unidad = unidad[:-1] if unidad == "goles" else "asistencia"
                mejores.append(Cruce("meta_cerca", 8 - faltan * 0.5, {**datos, "faltan": faltan, "unidad": unidad}))
        elif meta["tipo"] == "top_liga" and actual > meta["objetivo"]:
            mejores.append(Cruce("meta_tabla", 6, {**datos, "puesto": actual}))
    return max(mejores, key=lambda c: c.peso) if mejores else None


def _ex_club(estado: dict, rival: str) -> Optional[Cruce]:
    if not rival:
        return None
    actual = estado.get("actual")
    for clave, club in estado.get("clubes", {}).items():
        if clave == actual or club.get("nombre", "").lower() != rival.lower() or not club.get("hasta"):
            continue
        datos = {"ex_club": club["nombre"]}
        if club.get("traicion"):
            return Cruce("ex_club_traidor", 10, datos)
        if club.get("salida") == "idolo":
            return Cruce("ex_club_idolo", 9, datos)
        if club.get("salida") == "mala":
            return Cruce("ex_club_mala", 8, datos)
        return Cruce("ex_club_idolo", 6, datos) if club.get("carino", 50) >= 60 else None
    return None


def _hinchada(estado: dict) -> Optional[Cruce]:
    club = estado.get("clubes", {}).get(estado.get("actual") or "")
    if not club:
        return None
    if club["carino"] < clubes.EN_CONTRA:
        return Cruce("hinchada_contra", 6, {"club": club["nombre"], "carino": club["carino"]})
    if club["carino"] >= clubes.TENTADO_CARINO:
        return Cruce("idolo", 3, {"club": club["nombre"], "carino": club["carino"]})
    return None


def _evento(estado: dict, hoy, rating: Optional[float]) -> Optional[Cruce]:
    historial = estado.get("historial", [])
    if not historial or _dias(historial[0].get("fecha", ""), hoy) > DIAS_EVENTO_RECIENTE:
        return None
    ultimo = historial[0]
    datos = {"evento": ultimo["titulo"][0].lower() + ultimo["titulo"][1:]}
    if ultimo.get("evento") in EVENTOS_MALOS:
        return Cruce("evento_malo", 9 if rating is not None and rating < RATING_FLOJO else 7, datos)
    if ultimo.get("tono") == "positiva":
        return Cruce("evento_bueno", 5, datos)
    return None


def cruces(player_id: Optional[int], rival: str = "", rating: Optional[float] = None, carrera=None,
           temporada: Optional[str] = None) -> list[Cruce]:
    """Los cruces de este momento, del mas jugoso al menos."""
    if not player_id:
        return []
    e = database.get_economia(player_id)
    hoy = _hoy(e, carrera)
    estado_clubes = database.get_estado_clubes(player_id)
    encontrados = [
        _compra(e, hoy, rating, economia.moneda_de(carrera)),
        _amor(database.get_estado_amor(player_id)),
        _meta(database.get_metas(player_id), temporada, carrera),
        _ex_club(estado_clubes, rival),
        _hinchada(estado_clubes),
        _evento(database.get_estado_eventos(player_id), hoy, rating),
    ]
    return sorted((c for c in encontrados if c is not None), key=lambda c: -c.peso)
