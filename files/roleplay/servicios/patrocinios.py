"""
Contratos con marcas (patrocinios). Segun los seguidores de Instagram y la
reputacion, las marcas le ofrecen al jugador un contrato con un pago fijo
por semana, que se cobra junto con el sueldo (economia.acreditar, neto). Las
marcas son reales, solo como nombre en texto (como los autos: decision de
Simon, la app es entre amigos).

- Una oferta por vez, a lo sumo una por semana del juego (semilla propia), de
  la mejor marca para la que le da el nivel y de un rubro que no tenga.
- Si la reputacion cae muy por debajo de lo que pide la marca, o hay un
  escandalo reciente (un evento inesperado negativo), la marca puede
  rescindir; con escandalo, ademas lo multa (semanas del pago).
- Cada contrato dura DURACION_DIAS; al vencer, si sigue dandole el nivel,
  la marca puede volver a ofrecer.

Todo en estado_json.economia.patrocinios:
{"contratos": [{"id", "marca", "nombre", "rubro", "semanal", "desde", "hasta"}],
 "oferta": {"marca", "nombre", "rubro", "semanal", "fecha"} o None,
 "rechazadas": {marca: fecha}, "hasta": dia del juego hasta donde se sorteo}
"""

import copy
import random
import uuid
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Optional

MAXIMO_CONTRATOS = 3
DURACION_DIAS = 730
PROBABILIDAD_OFERTA = 0.4  # por semana, si alguna marca lo quiere
NO_INSISTE_DIAS = 120  # una marca rechazada no vuelve antes
MARGEN_RESCISION = 12  # puntos de reputacion por debajo de lo que pide la marca
PROBABILIDAD_RESCISION_ESCANDALO = 0.5
MULTA_SEMANAS = 2
FACTOR_MAXIMO = 3.0  # cuanto mas paga una marca a un jugador muy por encima de su minimo


@dataclass(frozen=True)
class Marca:
    id: str
    nombre: str
    rubro: str
    seguidores: int  # minimo
    reputacion: int  # minima
    semanal: int  # pago base por semana


MARCAS = [
    Marca("local", "una marca deportiva local", "indumentaria", 3_000, 40, 2_500),
    Marca("bebida", "una bebida isotonica", "bebidas", 20_000, 50, 8_000),
    Marca("puma", "Puma", "botines", 80_000, 55, 25_000),
    Marca("adidas", "Adidas", "botines", 300_000, 65, 55_000),
    Marca("nike", "Nike", "botines", 400_000, 68, 65_000),
    Marca("samsung", "Samsung", "smartphones", 800_000, 70, 70_000),
    Marca("apple", "Apple", "smartphones", 1_500_000, 75, 90_000),
    Marca("rolex", "Rolex", "relojes", 1_000_000, 78, 80_000),
    Marca("gucci", "Gucci", "moda de lujo", 2_000_000, 72, 100_000),
]
POR_ID = {m.id: m for m in MARCAS}


@dataclass
class Novedad:
    """Algo que paso con una marca, listo para la prensa (economia/eventos.contar)."""

    titulo: str
    detalle: str  # tercera persona, despues del nombre del jugador
    tono: str
    dinero: int = 0
    clave: str = ""


def _estado(e: dict) -> dict:
    return e.setdefault("patrocinios", {"contratos": [], "oferta": None, "rechazadas": {}})


def ingreso_semanal(e: Optional[dict], hoy: Optional[date] = None) -> int:
    """Lo que pagan por semana los contratos vigentes (bruto)."""
    contratos = ((e or {}).get("patrocinios") or {}).get("contratos", [])
    return sum(c["semanal"] for c in contratos if hoy is None or c["hasta"] >= hoy.isoformat())


def pago_para(marca: Marca, seguidores: int) -> int:
    factor = min(FACTOR_MAXIMO, max(1.0, seguidores / max(marca.seguidores, 1)) ** 0.5)
    return round(marca.semanal * factor, -2)


def candidatas(e: dict, seguidores: int, reputacion: int, hoy: date) -> list[Marca]:
    estado = _estado(e)
    rubros = {c["rubro"] for c in estado["contratos"]}
    contratadas = {c["marca"] for c in estado["contratos"]}
    rechazadas = estado.get("rechazadas", {})
    resultado = []
    for marca in MARCAS:
        rechazo = rechazadas.get(marca.id)
        if rechazo and (hoy - date.fromisoformat(rechazo)).days < NO_INSISTE_DIAS:
            continue
        if marca.id in contratadas or marca.rubro in rubros:
            continue
        if seguidores >= marca.seguidores and reputacion >= marca.reputacion:
            resultado.append(marca)
    return sorted(resultado, key=lambda m: m.semanal, reverse=True)


def revisar(e: Optional[dict], player_id: Optional[int], seguidores: int, reputacion: int, hoy: date,
            escandalo: bool = False) -> tuple[dict, list[Novedad]]:
    """(economia nueva, novedades) al dia `hoy` del juego: vencimientos,
    rescisiones y, una vez por semana, quizas una oferta."""
    e = copy.deepcopy(e or {})
    estado = _estado(e)
    novedades = []
    vigentes = []
    for contrato in estado["contratos"]:
        marca = POR_ID.get(contrato["marca"])
        if contrato["hasta"] < hoy.isoformat():
            novedades.append(Novedad(f"Termino su contrato con {contrato['nombre']}",
                                     f"cumplio su contrato con {contrato['nombre']} ({contrato['rubro']})", "neutral",
                                     clave=f"patrocinio:fin:{contrato['marca']}"))
            continue
        dado = random.Random(f"rescision:{player_id}:{contrato['id']}:{hoy.isoformat()}")
        cae = marca is not None and reputacion < marca.reputacion - MARGEN_RESCISION
        if cae or (escandalo and dado.random() < PROBABILIDAD_RESCISION_ESCANDALO):
            multa = contrato["semanal"] * MULTA_SEMANAS if escandalo else 0
            motivo = "despues del escandalo" if escandalo else "por su caida de imagen"
            novedades.append(Novedad(
                f"{contrato['nombre']} rescinde su contrato",
                f"perdio su contrato con {contrato['nombre']} {motivo}" + (" y encima tuvo que pagar una multa" if multa else ""),
                "negativa", -multa, clave=f"patrocinio:rescision:{contrato['marca']}",
            ))
            continue
        vigentes.append(contrato)
    estado["contratos"] = vigentes

    desde = date.fromisoformat(estado.get("hasta") or hoy.isoformat())
    semanas = max(0, (hoy - desde).days // 7)
    if "hasta" not in estado:
        estado["hasta"] = hoy.isoformat()
        semanas = 1  # la primera vez ya puede llegar una oferta
    else:
        estado["hasta"] = (desde + timedelta(days=7 * semanas)).isoformat() if semanas else estado["hasta"]
    if not estado.get("oferta") and len(vigentes) < MAXIMO_CONTRATOS:
        for i in range(semanas):
            dado = random.Random(f"patrocinio:{player_id}:{(desde + timedelta(days=7 * i)).isoformat()}")
            posibles = candidatas(e, seguidores, reputacion, hoy)
            if posibles and dado.random() < PROBABILIDAD_OFERTA:
                marca = posibles[0] if dado.random() < 0.6 else dado.choice(posibles)
                estado["oferta"] = {"marca": marca.id, "nombre": marca.nombre, "rubro": marca.rubro,
                                    "semanal": pago_para(marca, seguidores), "fecha": hoy.isoformat()}
                break
    for novedad in novedades:
        if novedad.dinero:
            e["saldo"] = e.get("saldo", 0) + novedad.dinero
            from roleplay.servicios.economia import _movimiento

            _movimiento(e, hoy, novedad.titulo, novedad.dinero)
    return e, novedades


def responder(e: dict, aceptar: bool, hoy: date) -> tuple[dict, Optional[Novedad]]:
    e = copy.deepcopy(e)
    estado = _estado(e)
    oferta = estado.get("oferta")
    if not oferta:
        return e, None
    estado["oferta"] = None
    if not aceptar:
        estado.setdefault("rechazadas", {})[oferta["marca"]] = hoy.isoformat()
        return e, None
    estado["contratos"].append({
        "id": uuid.uuid4().hex[:8], "marca": oferta["marca"], "nombre": oferta["nombre"], "rubro": oferta["rubro"],
        "semanal": oferta["semanal"], "desde": hoy.isoformat(),
        "hasta": (hoy + timedelta(days=DURACION_DIAS)).isoformat(),
    })
    return e, Novedad(f"Firma con {oferta['nombre']}", f"firmo un contrato de patrocinio con {oferta['nombre']} "
                      f"({oferta['rubro']})", "positiva", clave=f"patrocinio:firma:{oferta['marca']}")


def hubo_escandalo(estado_eventos: Optional[dict], hoy: date, dias: int = 14) -> bool:
    """Un evento inesperado negativo en los ultimos `dias` del juego."""
    for ocurrido in (estado_eventos or {}).get("historial", []):
        try:
            fecha = date.fromisoformat(ocurrido.get("fecha", ""))
        except ValueError:
            continue
        if ocurrido.get("tono") == "negativa" and 0 <= (hoy - fecha).days <= dias:
            return True
    return False
