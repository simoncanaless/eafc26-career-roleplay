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
- Marcas de todo lo que rodea al futbol (2026-10-20): botines, bebidas,
  tecnologia, electrodomesticos, videojuegos, auriculares, cuidado personal,
  relojes, moda, autos, aerolineas, bancos y comida. Un contrato por rubro.
- Las PROMOS: cada contrato pide algo cada CADA_DIAS del juego (al firmar, la
  campana de lanzamiento): un post en Instagram, una sesion de fotos, un
  evento, un comercial (`PROMOS_POR_RUBRO`: lo concreto de cada rubro). Hay
  PLAZO_DIAS para cumplir (`cumplir()`: bono de BONO_SEMANAS); si vence, falta,
  y con FALTAS_PARA_RESCINDIR la marca se va y cobra la multa.
- "Buscar marcas" (`buscar()`): el representante sale a buscar, una vez por
  semana del juego (sin espera en la partida de prueba).

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

MAXIMO_CONTRATOS = 8
MAXIMO_OFERTAS = 3  # esperando respuesta a la vez
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


# Marcas metidas en el mundo del futbol (2026-10-20, Simon: botines, deportivas, electrodomesticos con promos...).
# Un contrato por rubro (exclusividad, como en los contratos de verdad). Pagos base por semana, en la moneda del juego.
MARCAS = [
    # botines y ropa deportiva
    Marca("local", "Kelme", "botines", 3_000, 40, 2_500),  # (antes "una marca deportiva local")
    Marca("penalty", "Penalty", "botines", 10_000, 44, 5_000),
    Marca("lotto", "Lotto", "botines", 20_000, 46, 7_000),
    Marca("diadora", "Diadora", "botines", 40_000, 49, 10_000),
    Marca("hummel", "Hummel", "botines", 60_000, 51, 13_000),
    Marca("joma", "Joma", "botines", 30_000, 48, 9_000),
    Marca("umbro", "Umbro", "botines", 50_000, 50, 12_000),
    Marca("puma", "Puma", "botines", 80_000, 55, 25_000),
    Marca("mizuno", "Mizuno", "botines", 120_000, 55, 22_000),
    Marca("new_balance", "New Balance", "botines", 200_000, 60, 35_000),
    Marca("under_armour", "Under Armour", "botines", 250_000, 60, 38_000),
    Marca("adidas", "Adidas", "botines", 300_000, 65, 55_000),
    Marca("nike", "Nike", "botines", 400_000, 68, 65_000),
    # bebidas
    Marca("bebida", "Zuko", "bebidas", 5_000, 42, 3_000),  # (antes "una bebida isotonica")
    Marca("aquarius", "Aquarius", "bebidas", 50_000, 50, 8_000),
    Marca("lucozade", "Lucozade Sport", "bebidas", 80_000, 52, 10_000),
    Marca("monster", "Monster Energy", "bebidas", 300_000, 58, 22_000),
    Marca("prime", "Prime Hydration", "bebidas", 600_000, 62, 35_000),
    Marca("powerade", "Powerade", "bebidas", 150_000, 55, 15_000),
    Marca("gatorade", "Gatorade", "bebidas", 400_000, 62, 30_000),
    Marca("red_bull", "Red Bull", "bebidas", 800_000, 65, 45_000),
    Marca("pepsi", "Pepsi", "bebidas", 2_000_000, 70, 70_000),
    Marca("coca_cola", "Coca-Cola", "bebidas", 3_000_000, 74, 90_000),
    # tecnologia
    Marca("motorola", "Motorola", "tecnologia", 60_000, 50, 9_000),
    Marca("realme", "realme", "tecnologia", 100_000, 52, 12_000),
    Marca("lenovo", "Lenovo", "tecnologia", 200_000, 55, 16_000),
    Marca("xiaomi", "Xiaomi", "tecnologia", 300_000, 58, 25_000),
    Marca("oppo", "OPPO", "tecnologia", 400_000, 60, 28_000),
    Marca("huawei", "Huawei", "tecnologia", 500_000, 60, 30_000),
    Marca("samsung", "Samsung", "tecnologia", 800_000, 70, 70_000),
    Marca("apple", "Apple", "tecnologia", 1_500_000, 75, 90_000),
    # electrodomesticos
    Marca("oster", "Oster", "electrodomesticos", 30_000, 48, 6_000),
    Marca("mabe", "Mabe", "electrodomesticos", 60_000, 50, 8_000),
    Marca("midea", "Midea", "electrodomesticos", 100_000, 52, 10_000),
    Marca("tcl", "TCL", "electrodomesticos", 200_000, 55, 15_000),
    Marca("hisense", "Hisense", "electrodomesticos", 350_000, 58, 22_000),
    Marca("philips", "Philips", "electrodomesticos", 500_000, 62, 28_000),
    Marca("lg", "LG", "electrodomesticos", 700_000, 64, 35_000),
    # videojuegos y auriculares
    Marca("playstation", "PlayStation", "videojuegos", 1_000_000, 66, 50_000),
    Marca("ea_sports", "EA SPORTS FC", "videojuegos", 2_000_000, 72, 80_000),
    Marca("jbl", "JBL", "auriculares", 150_000, 55, 12_000),
    Marca("beats", "Beats by Dre", "auriculares", 1_000_000, 66, 45_000),
    # cuidado personal
    Marca("axe", "Axe", "cuidado personal", 100_000, 52, 10_000),
    Marca("nivea", "Nivea Men", "cuidado personal", 200_000, 56, 15_000),
    Marca("head_shoulders", "Head & Shoulders", "cuidado personal", 500_000, 60, 25_000),
    Marca("gillette", "Gillette", "cuidado personal", 1_000_000, 65, 40_000),
    # relojes
    Marca("casio", "Casio G-Shock", "relojes", 100_000, 52, 10_000),
    Marca("tissot", "Tissot", "relojes", 400_000, 60, 25_000),
    Marca("tag_heuer", "TAG Heuer", "relojes", 800_000, 66, 45_000),
    Marca("hublot", "Hublot", "relojes", 1_500_000, 72, 70_000),
    Marca("rolex", "Rolex", "relojes", 1_000_000, 78, 80_000),
    # moda
    Marca("calvin_klein", "Calvin Klein", "moda", 500_000, 60, 30_000),
    Marca("hugo_boss", "Hugo Boss", "moda", 800_000, 64, 40_000),
    Marca("armani", "Emporio Armani", "moda", 1_200_000, 68, 55_000),
    Marca("gucci", "Gucci", "moda", 2_000_000, 72, 100_000),
    Marca("louis_vuitton", "Louis Vuitton", "moda", 3_000_000, 78, 130_000),
    # autos
    Marca("kia", "Kia", "autos", 200_000, 55, 15_000),
    Marca("hyundai", "Hyundai", "autos", 300_000, 57, 20_000),
    Marca("cupra", "Cupra", "autos", 400_000, 60, 25_000),
    Marca("audi", "Audi", "autos", 800_000, 65, 40_000),
    Marca("bmw", "BMW", "autos", 1_000_000, 67, 50_000),
    Marca("mercedes", "Mercedes-Benz", "autos", 1_500_000, 70, 60_000),
    # aerolineas, tarjetas y comida
    Marca("turkish", "Turkish Airlines", "aerolineas", 500_000, 62, 25_000),
    Marca("qatar", "Qatar Airways", "aerolineas", 1_000_000, 67, 40_000),
    Marca("emirates", "Emirates", "aerolineas", 1_500_000, 70, 55_000),
    Marca("santander", "Santander", "bancos y tarjetas", 300_000, 58, 18_000),
    Marca("visa", "Visa", "bancos y tarjetas", 1_000_000, 66, 40_000),
    Marca("mastercard", "Mastercard", "bancos y tarjetas", 1_200_000, 68, 45_000),
    Marca("pringles", "Pringles", "comida", 100_000, 52, 10_000),
    Marca("lays", "Lay's", "comida", 200_000, 55, 14_000),
    Marca("mcdonalds", "McDonald's", "comida", 800_000, 62, 35_000),
    # telefonia, delivery, suplementos, gaming, gimnasios y musica
    Marca("entel", "Entel", "telefonia", 40_000, 48, 7_000),
    Marca("claro", "Claro", "telefonia", 100_000, 52, 12_000),
    Marca("movistar", "Movistar", "telefonia", 200_000, 55, 18_000),
    Marca("vodafone", "Vodafone", "telefonia", 600_000, 62, 30_000),
    Marca("pedidosya", "PedidosYa", "delivery", 50_000, 50, 8_000),
    Marca("rappi", "Rappi", "delivery", 80_000, 52, 10_000),
    Marca("uber_eats", "Uber Eats", "delivery", 400_000, 60, 25_000),
    Marca("myprotein", "Myprotein", "suplementos", 40_000, 48, 6_000),
    Marca("herbalife", "Herbalife", "suplementos", 300_000, 58, 20_000),
    Marca("dxracer", "DXRacer", "sillas gamer", 30_000, 47, 5_000),
    Marca("secretlab", "Secretlab", "sillas gamer", 150_000, 54, 12_000),
    Marca("smart_fit", "Smart Fit", "gimnasios", 80_000, 50, 9_000),
    Marca("spotify", "Spotify", "musica", 1_500_000, 68, 50_000),
]
POR_ID = {m.id: m for m in MARCAS}

# ---- las promos: lo que pide cada marca (cada CADA_DIAS del juego, con PLAZO_DIAS para cumplir) ----
CADA_DIAS = 30
PLAZO_DIAS = 21
FALTAS_PARA_RESCINDIR = 2
BONO_SEMANAS = 1  # cumplir paga una semana extra del contrato
PROMOS = {  # tipo -> (lo que hay que hacer, peso). "post" se cumple publicando en Instagram
    "post": ("Publicar un post en Instagram con {marca}", 3),
    "sesion": ("Sesion de fotos para la campana de {marca}", 2),
    "evento": ("Ir al lanzamiento de {marca}", 1),
    "comercial": ("Grabar un comercial para la tele de {marca}", 1),
}
PROMOS_POR_RUBRO = {  # lo que pide cada rubro, mas concreto
    "electrodomesticos": {"evento": "Hacer la promo de {marca} en una tienda de electrodomesticos"},
    "botines": {"sesion": "Sesion de fotos con los botines nuevos de {marca}",
                "evento": "Presentar los botines de {marca} en una tienda"},
    "bebidas": {"comercial": "Grabar el comercial de {marca} en el estadio"},
    "videojuegos": {"evento": "Jugar una partida con fans en un evento de {marca}",
                    "sesion": "Sesion de captura de movimientos para {marca}"},
    "autos": {"evento": "Recibir el auto de {marca} en un evento para la prensa"},
    "aerolineas": {"sesion": "Sesion de fotos en un avion de {marca}"},
    "comida": {"evento": "Inaugurar un local de {marca} con los hinchas"},
}


@dataclass
class Novedad:
    """Algo que paso con una marca, listo para la prensa (economia/eventos.contar)."""

    titulo: str
    detalle: str  # tercera persona, despues del nombre del jugador
    tono: str
    dinero: int = 0
    clave: str = ""


def _estado(e: dict) -> dict:
    estado = e.setdefault("patrocinios", {"contratos": [], "ofertas": [], "rechazadas": {}})
    vieja = estado.pop("oferta", None)  # (antes habia una sola oferta a la vez)
    estado.setdefault("ofertas", [])
    if vieja:
        estado["ofertas"].insert(0, vieja)
    return estado


def pendientes(e: Optional[dict]) -> list[dict]:
    """Las ofertas de marcas esperando respuesta (las mas nuevas primero)."""
    estado = (e or {}).get("patrocinios") or {}
    return ([estado["oferta"]] if estado.get("oferta") else []) + list(estado.get("ofertas", []))


def _oferta(marca: Marca, seguidores: int, hoy: date) -> dict:
    return {"marca": marca.id, "nombre": marca.nombre, "rubro": marca.rubro, "semanal": pago_para(marca, seguidores),
            "fecha": hoy.isoformat()}


def nombre_de(contrato: dict) -> str:
    """El nombre de hoy de la marca (las genericas de antes ahora son marcas de verdad)."""
    marca = POR_ID.get(contrato.get("marca"))
    return marca.nombre if marca else contrato.get("nombre", "")


def ingreso_semanal(e: Optional[dict], hoy: Optional[date] = None) -> int:
    """Lo que pagan por semana los contratos vigentes (bruto)."""
    contratos = ((e or {}).get("patrocinios") or {}).get("contratos", [])
    return sum(c["semanal"] for c in contratos if hoy is None or c["hasta"] >= hoy.isoformat())


def _rubro(contrato: dict) -> str:
    """El rubro de hoy de la marca (los contratos viejos guardaban "smartphones" o "moda de lujo")."""
    marca = POR_ID.get(contrato.get("marca"))
    return marca.rubro if marca else contrato.get("rubro", "")


def _sin_espera() -> bool:
    import os

    return os.environ.get("EAFC_DM_SIN_ESPERA") == "1"  # la partida de prueba: el juego no avanza


def puede_buscar(e: Optional[dict], hoy: date) -> tuple[bool, str]:
    estado = (e or {}).get("patrocinios") or {}
    if len(pendientes(e)) >= MAXIMO_OFERTAS:
        return False, "Ya tenes ofertas esperando respuesta: contestalas primero."
    if len(estado.get("contratos", [])) >= MAXIMO_CONTRATOS:
        return False, f"Ya tenes {MAXIMO_CONTRATOS} contratos: no te da el tiempo para mas."
    ultima = estado.get("busqueda")
    if ultima and not _sin_espera() and (hoy - date.fromisoformat(ultima)).days < 7:
        return False, "Tu representante ya busco esta semana del juego."
    return True, ""


def buscar(e: Optional[dict], player_id: Optional[int], seguidores: int, reputacion: int,
           hoy: date) -> tuple[dict, list[dict], str]:
    """Tu representante sale a buscar marcas (una vez por semana del juego): (economia, ofertas nuevas, mensaje).
    Trae hasta MAXIMO_OFERTAS, de rubros distintos: elegis la que quieras (o varias)."""
    ok, motivo = puede_buscar(e, hoy)
    if not ok:
        return copy.deepcopy(e or {}), [], motivo
    e = copy.deepcopy(e or {})
    estado = _estado(e)
    estado["busqueda"] = hoy.isoformat()
    ofrecidas = {o["rubro"] for o in estado["ofertas"]}
    posibles = [m for m in candidatas(e, seguidores, reputacion, hoy) if m.rubro not in ofrecidas]
    if not posibles:
        siguiente = min((m for m in MARCAS if m.seguidores > seguidores or m.reputacion > reputacion),
                        key=lambda m: (m.seguidores, m.reputacion), default=None)
        mensaje = "Ninguna marca nueva quiere sumarte por ahora."
        if siguiente is not None:
            mensaje += (f" La proxima ({siguiente.nombre}) pide {siguiente.seguidores:,} seguidores y "
                        f"reputacion {siguiente.reputacion}.").replace(",", ".")
        return e, [], mensaje
    dado = random.Random(f"busqueda:{player_id}:{hoy.isoformat()}:{len(estado['contratos'])}")
    nuevas = []
    lugar = MAXIMO_OFERTAS - len(estado["ofertas"])
    while posibles and len(nuevas) < lugar:
        # la que mas paga es la mas probable, pero tambien aparecen las mas chicas
        marca = dado.choices(posibles, weights=[1 + i for i in range(len(posibles), 0, -1)])[0]
        nuevas.append(_oferta(marca, seguidores, hoy))
        posibles = [m for m in posibles if m.rubro != marca.rubro]
    estado["ofertas"] = nuevas + estado["ofertas"]
    nombres = [o["nombre"] for o in nuevas]
    quien = nombres[0] if len(nombres) == 1 else ", ".join(nombres[:-1]) + " y " + nombres[-1]
    return e, nuevas, f"{quien} {'quiere' if len(nombres) == 1 else 'quieren'} hablar con vos."


def texto_promo(tipo: str, marca: str, rubro: str) -> str:
    return PROMOS_POR_RUBRO.get(rubro, {}).get(tipo, PROMOS[tipo][0]).format(marca=marca)


def _nueva_promo(contrato: dict, hoy: date, dado: random.Random) -> dict:
    tipos = list(PROMOS)
    tipo = dado.choices(tipos, weights=[PROMOS[t][1] for t in tipos])[0]
    return {"id": uuid.uuid4().hex[:8], "tipo": tipo, "texto": texto_promo(tipo, contrato["nombre"], _rubro(contrato)),
            "desde": hoy.isoformat(), "vence": (hoy + timedelta(days=PLAZO_DIAS)).isoformat()}


def promos_pendientes(e: Optional[dict]) -> list[tuple[dict, dict]]:
    """[(contrato, promo)] de lo que hay que cumplir."""
    contratos = ((e or {}).get("patrocinios") or {}).get("contratos", [])
    return [(c, c["promo"]) for c in contratos if c.get("promo")]


def cumplir(e: dict, contrato_id: str, hoy: date) -> tuple[dict, Novedad]:
    """Hizo la promo: la marca paga el bono (una semana mas del contrato)."""
    e = copy.deepcopy(e)
    contrato = next((c for c in _estado(e)["contratos"] if c["id"] == contrato_id and c.get("promo")), None)
    if contrato is None:
        raise ValueError("No hay una promo pendiente con esa marca.")
    promo = contrato.pop("promo")
    contrato["cumplidas"] = contrato.get("cumplidas", 0) + 1
    bono = contrato["semanal"] * BONO_SEMANAS
    from roleplay.servicios.economia import NETO, _movimiento

    neto = round(bono * NETO)
    e["saldo"] = e.get("saldo", 0) + neto
    _movimiento(e, hoy, f"Bono de {contrato['nombre']} por la promo (neto)", neto)
    return e, Novedad(f"{contrato['nombre']} lanza su campana", f"protagonizo la campana de {contrato['nombre']}: "
                      f"{promo['texto'][:1].lower()}{promo['texto'][1:]}", "positiva", neto,
                      clave=f"patrocinio:promo:{contrato['marca']}")


def pago_para(marca: Marca, seguidores: int) -> int:
    factor = min(FACTOR_MAXIMO, max(1.0, seguidores / max(marca.seguidores, 1)) ** 0.5)
    return round(marca.semanal * factor, -2)


def candidatas(e: dict, seguidores: int, reputacion: int, hoy: date) -> list[Marca]:
    estado = _estado(e)
    rubros = {_rubro(c) for c in estado["contratos"]}
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
        # la promo: si se vencio sin cumplir, falta (con FALTAS_PARA_RESCINDIR, se va y cobra la multa)
        promo = contrato.get("promo")
        if promo and promo["vence"] < hoy.isoformat():
            contrato.pop("promo")
            contrato["faltas"] = contrato.get("faltas", 0) + 1
            if contrato["faltas"] >= FALTAS_PARA_RESCINDIR:
                multa = contrato["semanal"] * MULTA_SEMANAS
                novedades.append(Novedad(
                    f"{contrato['nombre']} rescinde su contrato",
                    f"perdio su contrato con {contrato['nombre']} por no cumplir con las promociones y tuvo que "
                    "pagar una multa", "negativa", -multa, clave=f"patrocinio:rescision:{contrato['marca']}"))
                continue
            novedades.append(Novedad(
                f"{contrato['nombre']}, molesta", f"no cumplio con la promo que le pedia {contrato['nombre']} "
                f"({promo['texto'][:1].lower()}{promo['texto'][1:]}) y en la marca no estan contentos", "mixta",
                clave=f"patrocinio:falta:{contrato['marca']}"))
        ultima = contrato.get("ultima_promo") or contrato["desde"]
        if not contrato.get("promo") and (hoy - date.fromisoformat(ultima)).days >= CADA_DIAS:
            contrato["promo"] = _nueva_promo(contrato, hoy, random.Random(f"promo:{contrato['id']}:{hoy.isoformat()}"))
            contrato["ultima_promo"] = hoy.isoformat()
        vigentes.append(contrato)
    estado["contratos"] = vigentes

    desde = date.fromisoformat(estado.get("hasta") or hoy.isoformat())
    semanas = max(0, (hoy - desde).days // 7)
    if "hasta" not in estado:
        estado["hasta"] = hoy.isoformat()
        semanas = 1  # la primera vez ya puede llegar una oferta
    else:
        estado["hasta"] = (desde + timedelta(days=7 * semanas)).isoformat() if semanas else estado["hasta"]
    if len(estado["ofertas"]) < MAXIMO_OFERTAS and len(vigentes) < MAXIMO_CONTRATOS:
        for i in range(semanas):
            dado = random.Random(f"patrocinio:{player_id}:{(desde + timedelta(days=7 * i)).isoformat()}")
            ofrecidas = {o["rubro"] for o in estado["ofertas"]}
            posibles = [m for m in candidatas(e, seguidores, reputacion, hoy) if m.rubro not in ofrecidas]
            if posibles and dado.random() < PROBABILIDAD_OFERTA:
                marca = posibles[0] if dado.random() < 0.6 else dado.choice(posibles)
                estado["ofertas"].insert(0, _oferta(marca, seguidores, hoy))
                break
    for novedad in novedades:
        if novedad.dinero:
            e["saldo"] = e.get("saldo", 0) + novedad.dinero
            from roleplay.servicios.economia import _movimiento

            _movimiento(e, hoy, novedad.titulo, novedad.dinero)
    return e, novedades


def responder(e: dict, aceptar: bool, hoy: date, marca: Optional[str] = None) -> tuple[dict, Optional[Novedad]]:
    """Contestar una oferta (`marca`: su id; sin el, la primera)."""
    e = copy.deepcopy(e)
    estado = _estado(e)
    oferta = next((o for o in estado["ofertas"] if marca is None or o["marca"] == marca), None)
    if not oferta:
        return e, None
    estado["ofertas"].remove(oferta)
    if aceptar and oferta["rubro"] in {_rubro(c) for c in estado["contratos"]}:
        return e, None  # ya firmo otra del mismo rubro
    if not aceptar:
        estado.setdefault("rechazadas", {})[oferta["marca"]] = hoy.isoformat()
        return e, None
    contrato = {
        "id": uuid.uuid4().hex[:8], "marca": oferta["marca"], "nombre": oferta["nombre"], "rubro": oferta["rubro"],
        "semanal": oferta["semanal"], "desde": hoy.isoformat(),
        "hasta": (hoy + timedelta(days=DURACION_DIAS)).isoformat(), "ultima_promo": hoy.isoformat(),
    }
    contrato["promo"] = _nueva_promo(contrato, hoy, random.Random(f"promo:{contrato['id']}"))  # la campana de lanzamiento
    estado["contratos"].append(contrato)
    # exclusividad: la competencia del mismo rubro ya no puede (Pepsi si firmaste con Coca-Cola)
    estado["ofertas"] = [o for o in estado["ofertas"] if o["rubro"] != oferta["rubro"]]
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
