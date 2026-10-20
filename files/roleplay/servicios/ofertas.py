"""
Ofertas de otros clubes: en las ventanas de pases (julio-agosto y enero) los
clubes que te quieren te mandan una propuesta de contrato, segun tu nivel.
Recibirlas NO es querer irse (pedido de Simon): las miras sin compromiso.

- Quien ofrece: clubes de la partida cuyo plantel (promedio de sus 16
  mejores, `ecosistema.medias_de_plantel`) esta a tu alcance segun tu media y
  tu fama (con mas fama te buscan los gigantes), de tu tier o uno mas abajo.
  Los mejores clubes pesan mas en el sorteo.
- Que ofrecen: sueldo semanal (segun el tier y tu media, y siempre mas que lo
  que ganas hoy: si no, no te moverias), temporadas y las primas (las mismas
  clausulas de servicios/contratos.py, cerca del techo de ESE club).
- Que podes hacer: rechazar; "usarla para negociar" con tu club (la proxima
  negociacion de primas arranca con mas palanca: `palanca_extra`); o
  aceptarla. Aceptar es roleplay: el traspaso lo hace EL JUEGO (pedi salir o
  acepta la oferta cuando llegue en FC 26). Si en `PLAZO_TRASPASO_DIAS` la
  partida te muestra en ese club, las primas de la oferta pasan a ser tu
  contrato solas; si no, el acuerdo se cae.

Una revision por semana del juego (semilla jugador+semana: la misma partida
da las mismas ofertas). Estado en `economia.ofertas`.
"""

import copy
import os
import random
import uuid
from datetime import date, timedelta
from typing import Optional

from roleplay.servicios import contratos

MESES_DE_VENTANA = (7, 8, 1)
MAXIMO_ABIERTAS = 3
VIGENCIA_DIAS = 14
PLAZO_TRASPASO_DIAS = 60
PALANCA_POR_OFERTA = {1: 0.25, 2: 0.15, 3: 0.08}  # cuanto mas grande el que ofrece, mas fuerza para negociar
SUELDO_TIER_1_MEDIA_80 = 150_000  # por semana: Man Utd/Real Madrid a un 80 de media (85 ~ 240.000, 90 ~ 390.000)
FACTOR_SUELDO_TIER = {1: 1.0, 2: 0.4, 3: 0.12}


def en_ventana(hoy: date) -> bool:
    return hoy.month in MESES_DE_VENTANA


def probabilidad(fama: int) -> float:
    """Chance de una oferta por semana de ventana: con mas fama, mas clubes te llaman."""
    return min(0.65, 0.12 + fama / 200)


def sueldo_de_mercado(tier: int, media: int) -> int:
    return round(SUELDO_TIER_1_MEDIA_80 * FACTOR_SUELDO_TIER.get(tier, 0.4) * 1.1 ** (media - 80))


def interesados(carrera, club_actual: Optional[int], media: int, fama: int) -> list[tuple[int, float, int]]:
    """[(equipo, peso, tier)] de los clubes que pueden ir por vos."""
    from roleplay.servicios import ecosistema

    tier_actual = ecosistema.tier_club(carrera, club_actual)
    alcance = media + fama / 10  # la fama compensa la media (a un 80 con fama 100 lo busca un plantel de 88)
    resultado = []
    for equipo, promedio in ecosistema.medias_de_plantel(carrera).items():
        if equipo == club_actual or equipo not in carrera.clubes:
            continue
        tier = ecosistema.tier_club(carrera, equipo)
        if tier > tier_actual + 1 or promedio > alcance or promedio < media - 12:
            continue
        resultado.append((equipo, max(0.1, promedio - (media - 12)), tier))
    return resultado


def _estado(e: dict) -> dict:
    return e.setdefault("ofertas", {"lista": [], "visto": ""})


def abiertas(e: Optional[dict]) -> list[dict]:
    return [o for o in ((e or {}).get("ofertas") or {}).get("lista", []) if o["estado"] in ("nueva", "aceptada")]


def armar(carrera, equipo: int, tier: int, hoy: date, sueldo_actual: int, media: int, fama: int, posicion: str,
          dado: random.Random) -> dict:
    nombre = carrera.equipo(equipo)
    sueldo = max(sueldo_de_mercado(tier, media) * dado.uniform(0.9, 1.15), (sueldo_actual or 0) * dado.uniform(1.08, 1.35))
    sueldo = round(sueldo, -3) if sueldo >= 10_000 else round(sueldo, -2)
    mesa = contratos.abrir(nombre, tier, fama, hoy, posicion, dado=dado)
    condiciones = {c.id: contratos._redondear(mesa["techo"][c.id] * dado.uniform(0.75, 0.95), c.paso)
                   for c in contratos.CLAUSULAS}
    liga = ""
    for competicion_id, competicion in carrera.competiciones.items():
        if competicion.es_liga and any(p.competicion == competicion_id and equipo in (p.local, p.visita)
                                       for p in carrera.partidos):
            liga = competicion.nombre or ""
            break
    return {
        "id": uuid.uuid4().hex[:8], "equipo": equipo, "club": nombre, "tier": tier, "liga": liga,
        "sueldo": int(sueldo), "temporadas": dado.choice((2, 3, 4, 5)), "condiciones": condiciones,
        "meta_goles": mesa["meta_goles"], "fecha": hoy.isoformat(),
        "vence": (hoy + timedelta(days=VIGENCIA_DIAS)).isoformat(), "estado": "nueva",
    }


def revisar(e: Optional[dict], carrera, player_id: Optional[int], hoy: date, fama: int,
            dado: Optional[random.Random] = None) -> tuple[dict, list[dict]]:
    """(economia nueva, novedades [{"tipo": "nueva"|"cumplida"|"caida"|"vencida", "oferta": ...}])."""
    from roleplay.servicios import ecosistema, entrevista

    e = copy.deepcopy(e or {})
    estado = _estado(e)
    novedades = []
    club_actual = ecosistema.club_del_usuario(carrera)
    for oferta in estado["lista"]:
        if oferta["estado"] == "aceptada" and club_actual == oferta["equipo"]:
            oferta["estado"] = "cumplida"  # el juego lo hizo: las primas de la oferta pasan a ser su contrato
            negociacion = {"club": oferta["club"], "oferta": dict(oferta["condiciones"]), "estado": "acuerdo",
                           "meta_goles": oferta.get("meta_goles", 20)}
            e, _ = contratos.firmar(e, negociacion, oferta["temporadas"], hoy, fama,
                                    ecosistema.goles_de_la_temporada(carrera))
            estado = _estado(e)
            novedades.append({"tipo": "cumplida", "oferta": oferta})
        elif oferta["estado"] == "aceptada" and (hoy - date.fromisoformat(oferta["fecha_aceptada"])).days > PLAZO_TRASPASO_DIAS:
            oferta["estado"] = "caida"
            novedades.append({"tipo": "caida", "oferta": oferta})
        elif oferta["estado"] == "nueva" and hoy.isoformat() > oferta["vence"]:
            oferta["estado"] = "vencida"
    semana = (hoy - timedelta(days=hoy.weekday())).isoformat()
    if os.environ.get("EAFC_SIN_OFERTAS") == "1":  # (las pruebas de otros modulos)
        return e, novedades
    if estado.get("visto") == semana or not en_ventana(hoy) or club_actual is None or carrera.usuario_id is None:
        estado["visto"] = semana if en_ventana(hoy) else estado.get("visto", "")
        return e, novedades
    estado["visto"] = semana
    dado = dado or random.Random(f"ofertas:{player_id}:{semana}")
    if len(abiertas(e)) >= MAXIMO_ABIERTAS or any(o["estado"] == "aceptada" for o in estado["lista"]) \
            or dado.random() >= probabilidad(fama):
        return e, novedades
    media = carrera.medias.get(carrera.usuario_id, 70)
    ya = {o["equipo"] for o in abiertas(e)}
    candidatos = [c for c in interesados(carrera, club_actual, media, fama) if c[0] not in ya]
    if not candidatos:
        return e, novedades
    equipo, _, tier = dado.choices(candidatos, weights=[p for _, p, _ in candidatos])[0]
    oferta = armar(carrera, equipo, tier, hoy, e.get("sueldo", 0), media, fama,
                   entrevista.posicion_del_usuario(carrera), dado)
    estado["lista"] = [oferta] + estado["lista"][:19]
    novedades.append({"tipo": "nueva", "oferta": oferta})
    return e, novedades


def responder(e: dict, oferta_id: str, accion: str, hoy: date) -> tuple[dict, dict]:
    """accion: "rechazar", "negociar" (palanca para tu club) o "aceptar" (el traspaso lo hace el juego)."""
    e = copy.deepcopy(e)
    estado = _estado(e)
    oferta = next((o for o in estado["lista"] if o["id"] == oferta_id), None)
    if oferta is None or oferta["estado"] != "nueva":
        raise ValueError("Esa oferta ya no esta.")
    if accion == "rechazar":
        oferta["estado"] = "rechazada"
    elif accion == "negociar":
        oferta["estado"] = "usada"
        e["palanca_extra"] = {"valor": PALANCA_POR_OFERTA.get(oferta["tier"], 0.1), "club": oferta["club"],
                              "hasta": (hoy + timedelta(days=VIGENCIA_DIAS * 2)).isoformat()}
    elif accion == "aceptar":
        oferta["estado"] = "aceptada"
        oferta["fecha_aceptada"] = hoy.isoformat()
        for otra in estado["lista"]:
            if otra is not oferta and otra["estado"] == "nueva":
                otra["estado"] = "descartada"
    else:
        raise ValueError(accion)
    return e, oferta


def palanca_extra(e: Optional[dict], hoy: date) -> float:
    extra = (e or {}).get("palanca_extra")
    return extra["valor"] if extra and hoy.isoformat() <= extra["hasta"] else 0.0
