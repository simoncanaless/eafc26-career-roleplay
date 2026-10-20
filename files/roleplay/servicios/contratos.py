"""
Las primas del contrato: lo que FC 26 no tiene y si tiene cualquier contrato
de verdad. El SUELDO base es el de la partida (se negocia en el juego y la
app lo cobra, servicios/economia.py); aca se negocia con la directiva el resto
del paquete, como en los contratos que se filtraron (Football Leaks):

- prima de firma (se paga en cuotas, una por temporada),
- prima por gol y por llegar a una cantidad de goles en la temporada (la meta
  depende de la posicion: un 9 no es un central),
- jugador del mes, titulo de liga y Balon de Oro (Ronaldo, Di Maria, Kroos y
  Yamal tenian clausula de Balon de Oro),
- prima de fidelidad por cada temporada completa en el club,
- derechos de imagen: un pago semanal aparte, como porcentaje del sueldo.

Los techos se calibraron con lo que se filtro: la prima por gol de Martial en
el United (3 cuotas de 7,2 M de libras por cada 25 goles), Balon de Oro de 1 a
4 M (Ronaldo, Di Maria) y la mitad de los derechos de imagen para el club
(Kroos). Todo se mide en SEMANAS de sueldo (asi escala con el club) salvo la imagen
(porcentaje). La negociacion: la directiva tiene un techo por clausula
(escondido: depende del tier del club y de la fama/palanca del jugador) y
abre con 55-75% de el. El jugador contraoferta; si todo esta bajo el techo,
firma; si se pasa un poco, la directiva sube hasta donde puede y pierde
paciencia; si se pasa mucho, se ofende. Sin paciencia, se levanta de la mesa
(hasta la temporada que viene). El representante da pistas (como uno de
verdad: "hay margen", "te estas pasando").

El juego no guarda el Balon de Oro de forma legible: lo declara el usuario
(una vez por temporada). Jugador del mes y titulo salen de la vitrina
(estado_prensa, servicios/partida_real.py); los goles, de la partida.
Estado en `economia.contrato` y `economia.negociacion`.
"""

import copy
import random
from dataclasses import dataclass
from datetime import date
from typing import Optional

from roleplay.servicios import economia


@dataclass(frozen=True)
class Clausula:
    id: str
    nombre: str
    unidad: str  # "semanas" (de sueldo) o "%"
    techo: float  # para un jugador de palanca 1 en un club de tier 2
    paso: float  # de a cuanto se pide
    que: str  # explicacion corta


CLAUSULAS = [
    Clausula("firma", "Prima de firma", "semanas", 26, 1, "Se paga en cuotas: una por temporada de contrato"),
    Clausula("gol", "Prima por gol", "semanas", 0.35, 0.05, "Por cada gol que hagas en la temporada"),
    Clausula("meta_goles", "Meta de goles", "semanas", 10, 1, "Una vez por temporada, al llegar a la meta"),
    Clausula("mes", "Jugador del mes", "semanas", 1, 0.5, "Cada vez que ganes el premio"),
    Clausula("titulo", "Titulo de liga", "semanas", 4, 0.5, "Si salen campeones"),
    Clausula("balon_oro", "Balon de Oro", "semanas", 12, 1, "Si ganas el Balon de Oro jugando en el club"),
    Clausula("fidelidad", "Prima de fidelidad", "semanas", 5, 1, "Por cada temporada completa en el club"),
    Clausula("imagen", "Derechos de imagen", "%", 10, 1, "Pago semanal aparte, en % del sueldo"),
]
POR_ID = {c.id: c for c in CLAUSULAS}
FACTOR_TIER = {1: 1.35, 2: 1.0, 3: 0.65}  # un gigante paga mas (y tiene mas para repartir)
META_GOLES = {"arco": 1, "defensa": 5, "medio": 10, "ataque": 20}
PACIENCIA = 3
IMAGEN_MAXIMA = 20  # % del sueldo: mas que eso ya no es "aparte"
TEMPORADAS = (1, 2, 3, 4, 5)
CEDE_UN_POCO = 0.25  # hasta 25% sobre el techo: contraoferta
COMISION_REPRESENTANTE = 0.10  # de la prima de firma
MEJORA_DESDE_FAMA = 10  # para pedir mejorar el contrato antes de que venza


def palanca(fama: int, carino: int = 50, goles: int = 0, partidos: int = 0) -> float:
    """Cuanto puede pedir: la fama manda; ser idolo de la hinchada y el ritmo de goles suman."""
    base = 0.5 + fama / 100  # fama 50 -> 1.0, fama 100 -> 1.5
    if carino >= 80:
        base += 0.1
    if partidos >= 5 and goles / partidos >= 0.6:
        base += 0.1
    return max(0.5, min(1.7, base))


def linea(posicion: str) -> str:
    from roleplay.servicios import entrevista

    return entrevista.LINEA.get((posicion or "").lower(), "ataque")


# ---- la negociacion ----


def _redondear(valor: float, paso: float) -> float:
    return round(round(valor / paso) * paso, 2)


def abrir(club: str, tier: int, fama: int, hoy: date, posicion: str = "", carino: int = 50, goles: int = 0,
          partidos: int = 0, dado: Optional[random.Random] = None) -> dict:
    """La directiva se sienta a negociar: su techo (escondido) y su primera oferta."""
    dado = dado or random.Random(f"contrato:{club}:{hoy.isoformat()}:{fama}")
    fuerza = palanca(fama, carino, goles, partidos) * FACTOR_TIER.get(tier, 1.0)
    techo, oferta = {}, {}
    for c in CLAUSULAS:
        if c.id == "imagen":
            tope = min(IMAGEN_MAXIMA, c.techo * (0.6 + fama / 100) * FACTOR_TIER.get(tier, 1.0))
        else:
            tope = c.techo * fuerza
        tope *= dado.uniform(0.9, 1.1)  # cada directiva es distinta
        techo[c.id] = _redondear(tope, c.paso)
        oferta[c.id] = min(_redondear(tope * dado.uniform(0.55, 0.75), c.paso), max(0.0, techo[c.id] - c.paso))
    paciencia = PACIENCIA + (1 if carino >= 80 else 0)
    return {"club": club, "fecha": hoy.isoformat(), "techo": techo, "oferta": oferta, "paciencia": paciencia,
            "paciencia_inicial": paciencia,
            "ronda": 0, "meta_goles": META_GOLES[linea(posicion)], "estado": "abierta"}


def exceso(negociacion: dict, pedido: dict) -> float:
    """Cuanto se pasa el pedido del techo (0 = nada), en promedio de las clausulas."""
    techo = negociacion["techo"]
    sobre = [max(0.0, pedido.get(c.id, 0) / techo[c.id] - 1) if techo[c.id] else 0.0 for c in CLAUSULAS]
    return sum(sobre) / len(sobre) * 2  # pasarse mucho en una sola ya pesa


def consejo(negociacion: dict, pedido: dict) -> dict:
    """Lo que dice el representante de cada clausula: "margen", "justo" o "pasado"."""
    resultado = {}
    for c in CLAUSULAS:
        tope, valor = negociacion["techo"][c.id], pedido.get(c.id, 0)
        resultado[c.id] = "pasado" if valor > tope * 1.05 else "margen" if valor < tope * 0.85 else "justo"
    return resultado


def contraofertar(negociacion: dict, pedido: dict) -> tuple[dict, str]:
    """(negociacion nueva, lo que contesta la directiva: "acepta", "sube", "ofendida" o "rompe")."""
    neg = copy.deepcopy(negociacion)
    if neg["estado"] != "abierta":
        raise ValueError("La negociacion ya termino.")
    pedido = {c.id: max(0.0, float(pedido.get(c.id, neg["oferta"][c.id]))) for c in CLAUSULAS}
    neg["ronda"] += 1
    sobre = exceso(neg, pedido)
    if sobre == 0:
        neg["oferta"] = pedido
        neg["estado"] = "acuerdo"
        return neg, "acepta"
    if sobre <= CEDE_UN_POCO:
        neg["paciencia"] -= 1
        # lo que esta dentro de lo posible lo acepta; lo demas, sube hasta su techo
        neg["oferta"] = {c.id: min(pedido[c.id], neg["techo"][c.id]) for c in CLAUSULAS}
        respuesta = "sube"
    else:
        neg["paciencia"] -= 2
        respuesta = "ofendida"
    if neg["paciencia"] <= 0:
        neg["estado"] = "rota"
        return neg, "rompe"
    return neg, respuesta


def levantarse(negociacion: dict) -> dict:
    neg = copy.deepcopy(negociacion)
    neg["estado"] = "rota"
    return neg


# ---- el contrato firmado ----


def firmar(e: dict, negociacion: dict, temporadas: int, hoy: date, fama: int = 0, goles: int = 0) -> tuple[dict, int]:
    """Firma lo que ofrece la directiva (la oferta vigente). Devuelve (economia, cobrado hoy):
    la primera cuota de la prima de firma, menos la comision del representante."""
    if negociacion["estado"] not in ("abierta", "acuerdo"):
        raise ValueError("No hay nada para firmar.")
    e = copy.deepcopy(e or {})
    temporadas = max(1, min(max(TEMPORADAS), int(temporadas)))
    sueldo = e.get("sueldo", 0)
    condiciones = dict(negociacion["oferta"])
    firma_total = round(condiciones["firma"] * sueldo * economia.NETO)
    contrato = {
        "club": negociacion["club"], "desde": hoy.isoformat(), "temporadas": temporadas,
        "hasta_temporada": _temporada_mas(hoy, temporadas - 1), "condiciones": condiciones,
        "meta_goles": negociacion.get("meta_goles", META_GOLES["ataque"]), "fama_al_firmar": fama,
        "cuotas_firma": {"total": firma_total, "pagadas": 0}, "pagado": {},
        "visto": {"temporada": _temporada(hoy), "goles": goles},  # los goles de antes de firmar no cuentan
    }
    e["contrato"] = contrato
    e.pop("negociacion", None)
    cobrado = _cuota_de_firma(e, hoy, [])
    comision = round(firma_total * COMISION_REPRESENTANTE)
    if comision:
        e["saldo"] = e.get("saldo", 0) - comision
        economia._movimiento(e, hoy, "Comision de tu representante (prima de firma)", -comision)
    return e, cobrado - comision


def _temporada_mas(hoy: date, n: int) -> str:
    from roleplay.servicios.partida_real import temporada_de

    inicio = economia.inicio_de_temporada(hoy)
    return temporada_de(date(inicio.year + n, 7, 1))


def _temporada(hoy: date) -> str:
    from roleplay.servicios.partida_real import temporada_de

    return temporada_de(hoy)


def vigente(e: Optional[dict], club: str, hoy: date) -> Optional[dict]:
    contrato = (e or {}).get("contrato")
    if not contrato or contrato.get("club") != club or _temporada(hoy) > contrato["hasta_temporada"]:
        return None
    return contrato


def puede_negociar(e: Optional[dict], club: str, hoy: date, fama: int) -> tuple[bool, str]:
    e = e or {}
    if not club:
        return False, "No se en que club estas."
    bloqueo = e.get("negociacion_rota")
    if bloqueo and bloqueo.get("club") == club and bloqueo.get("temporada") == _temporada(hoy):
        return False, "La directiva se levanto de la mesa: hasta la temporada que viene no hay charla."
    contrato = vigente(e, club, hoy)
    if contrato is None:
        return True, ""
    if contrato.get("mejora_pedida") == _temporada(hoy):
        return False, "Ya pediste mejorar el contrato esta temporada."
    if fama >= contrato.get("fama_al_firmar", 0) + MEJORA_DESDE_FAMA:
        return True, ""
    return False, (f"Tenes contrato hasta la temporada {contrato['hasta_temporada']}. Para pedir una mejora, "
                   f"tu fama tiene que subir {MEJORA_DESDE_FAMA} puntos desde que firmaste.")


def ingreso_semanal(e: Optional[dict], hoy: Optional[date] = None) -> int:
    """Lo que paga el club por derechos de imagen por semana (bruto)."""
    contrato = (e or {}).get("contrato")
    if not contrato or (hoy is not None and _temporada(hoy) > contrato["hasta_temporada"]):
        return 0
    return round(e.get("sueldo", 0) * contrato["condiciones"].get("imagen", 0) / 100)


def _semanas(e: dict, semanas: float) -> int:
    return round(semanas * e.get("sueldo", 0) * economia.NETO)


def _cobrar(e: dict, hoy: date, concepto: str, monto: int, cobros: list) -> None:
    if monto <= 0:
        return
    e["saldo"] = e.get("saldo", 0) + monto
    economia._movimiento(e, hoy, concepto, monto)
    cobros.append((concepto, monto))


def _cuota_de_firma(e: dict, hoy: date, cobros: list) -> int:
    contrato = e["contrato"]
    cuotas = contrato["cuotas_firma"]
    if cuotas["pagadas"] >= contrato["temporadas"] or not cuotas["total"]:
        return 0
    monto = round(cuotas["total"] / contrato["temporadas"])
    cuotas["pagadas"] += 1
    cuotas["ultima"] = _temporada(hoy)
    _cobrar(e, hoy, f"Prima de firma: cuota {cuotas['pagadas']} de {contrato['temporadas']} (neto)", monto, cobros)
    return monto


def cobrar(e: Optional[dict], club: str, hoy: date, goles: int, vitrina: list[dict]) -> tuple[dict, list]:
    """Las primas que tocan al dia `hoy`: (economia nueva, [(concepto, monto)]). Llamarla seguido no cobra dos veces."""
    e = copy.deepcopy(e or {})
    cobros: list = []
    contrato = e.get("contrato")
    if not contrato:
        return e, cobros
    if contrato.get("club") != club:  # se fue (o lo vendieron): el contrato con ese club termina
        e["contrato_anterior"] = contrato
        e.pop("contrato")
        return e, cobros
    temporada = _temporada(hoy)
    condiciones, visto, pagado = contrato["condiciones"], contrato["visto"], contrato["pagado"]
    anterior = visto.get("temporada")
    if anterior and anterior != temporada:  # cambio de temporada
        # fidelidad: la temporada que termino, si estuvo en el club desde el principio
        if anterior <= contrato["hasta_temporada"] and contrato["desde"] <= f"{anterior[:4]}-09-01":
            _cobrar(e, hoy, f"Prima de fidelidad, temporada {anterior} (neto)", _semanas(e, condiciones["fidelidad"]),
                    cobros)
        if temporada <= contrato["hasta_temporada"] and contrato["cuotas_firma"].get("ultima") != temporada:
            _cuota_de_firma(e, hoy, cobros)
        visto.update(temporada=temporada, goles=0)
    if temporada > contrato["hasta_temporada"]:
        return e, cobros
    # goles (los de la partida, en todas las competiciones)
    nuevos = max(0, goles - visto.get("goles", 0))
    if nuevos:
        _cobrar(e, hoy, f"Prima por {nuevos} gol{'es' if nuevos > 1 else ''} (neto)",
                _semanas(e, condiciones["gol"] * nuevos), cobros)
        visto["goles"] = goles
    meta = contrato.get("meta_goles", 20)
    if goles >= meta and pagado.get("meta_goles") != temporada:
        pagado["meta_goles"] = temporada
        _cobrar(e, hoy, f"Prima por llegar a {meta} goles (neto)", _semanas(e, condiciones["meta_goles"]), cobros)
    # premios de la vitrina desde que firmo
    ya = set(pagado.get("premios", []))
    for premio in vitrina:
        clave = f"{premio.get('premio')}:{premio.get('detalle')}:{premio.get('temporada')}"
        if clave in ya or (premio.get("temporada") or "") < _temporada(date.fromisoformat(contrato["desde"])):
            continue
        clausula = {"Jugador del mes": "mes", "Campeon": "titulo"}.get(premio.get("premio"))
        if clausula is None:
            continue
        ya.add(clave)
        nombre = "jugador del mes" if clausula == "mes" else "el titulo de liga"
        _cobrar(e, hoy, f"Prima por {nombre} (neto)", _semanas(e, condiciones[clausula]), cobros)
    pagado["premios"] = sorted(ya)
    return e, cobros


def balon_de_oro(e: Optional[dict], club: str, hoy: date) -> tuple[dict, int]:
    """El usuario lo gano en el juego (la partida no lo guarda de forma legible): una vez por temporada."""
    e = copy.deepcopy(e or {})
    ganados = e.setdefault("balones_de_oro", [])
    temporada = _temporada(hoy)
    if temporada in ganados:
        raise ValueError("Ya anotaste el Balon de Oro de esta temporada.")
    ganados.append(temporada)
    contrato = vigente(e, club, hoy)
    if contrato is None:
        return e, 0
    cobros: list = []
    monto = _semanas(e, contrato["condiciones"]["balon_oro"])
    _cobrar(e, hoy, "Prima por el Balon de Oro (neto)", monto, cobros)
    return e, monto


def rotulo(clausula: Clausula, valor: float, sueldo: int, moneda: str, meta: int = 0) -> str:
    """Como se muestra una clausula: "4 semanas (≈ $120.000)" o "12% del sueldo"."""
    if clausula.unidad == "%":
        return f"{valor:g}% del sueldo ({economia.dinero(round(sueldo * valor / 100), moneda)} por semana)"
    texto = f"{valor:g} semana{'s' if valor != 1 else ''} ({economia.dinero(round(valor * sueldo), moneda)})"
    if clausula.id == "meta_goles" and meta:
        texto += f" al llegar a {meta} goles"
    return texto


def contexto(carrera, player_id: Optional[int]) -> dict:
    """Lo que la directiva mira para negociar, leido de la partida y de la app."""
    from roleplay import database
    from roleplay.servicios import ecosistema, entrevista

    club_id = ecosistema.club_del_usuario(carrera)
    club = carrera.equipo(club_id) if carrera is not None and club_id is not None else ""
    estado_clubes = database.get_estado_clubes(player_id) if player_id else {}
    actual = (estado_clubes.get("clubes") or {}).get(estado_clubes.get("actual") or "", {})
    stats = carrera.estadisticas_de(carrera.usuario_id) if carrera is not None and carrera.usuario_id else []
    return {
        "club": club, "tier": ecosistema.tier_club(carrera, club_id),
        "fama": ecosistema.calcular_fama_jugador(player_id, carrera)["fama"] if player_id else 50,
        "posicion": entrevista.posicion_del_usuario(carrera), "carino": actual.get("carino", 50),
        "goles": sum(s.goles for s in stats), "partidos": sum(s.partidos for s in stats),
    }
