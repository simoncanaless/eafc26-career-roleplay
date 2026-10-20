"""
Marketplace de usados y autos de culto (JDM, Euro, Muscle, Supercars), con
el catalogo de Simon (autos_marketplace.json: marca, modelo, anio, categoria,
precio_base, rareza, nota y foto en img_autos/).

Cada semana del juego rota una seleccion de 8 a 12 autos (semilla: jugador +
semana: la misma partida muestra los mismos), cada uno con kilometraje
simulado, un estado ("Impecable de coleccion", "Importado de Japon",
"Preparado Track/Drift"...) y un precio que varia con la rareza y el estado.
Se compran al instante (sin fabrica de por medio) y van al garage. Los de
culto se valorizan con los anios del juego segun su rareza: al revenderlos
se cobra el valor de hoy menos la comision del marketplace.
"""

import random
import re
from datetime import date, timedelta
from typing import Optional

from roleplay.servicios import autos, ecosistema
from roleplay.servicios.economia import Articulo

PREFIJO = "nicho:"
MINIMO_OFERTAS, MAXIMO_OFERTAS = 8, 12
COMISION = 0.05  # lo que se queda el marketplace al revender
KM_POR_ANIO = (3_000, 14_000)
ESTADOS = [
    ("Impecable de coleccion", 1.25),
    ("Importado de Japon", 1.05),
    ("Preparado Track/Drift", 0.95),
    ("Original y bien cuidado", 1.0),
    ("Con detalles de uso", 0.85),
]
# rareza: (precio minimo, maximo) sobre el base, y cuanto se valoriza por anio
RAREZA = {"Baja": (0.90, 1.05, 0.00), "Media": (0.95, 1.15, 0.03), "Alta": (1.00, 1.25, 0.06),
          "Extrema": (1.05, 1.40, 0.10)}


def _semana(hoy: date) -> date:
    return hoy - timedelta(days=hoy.weekday())


def _slug(texto: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", texto.lower()).strip("_")


def ofertas(player_id: Optional[int], hoy: date) -> list[dict]:
    """Los autos de esta semana del juego (los mismos para la misma partida)."""
    catalogo = ecosistema.autos_nicho()
    if not catalogo:
        return []
    semana = _semana(hoy)
    dado = random.Random(f"marketplace:{player_id}:{semana.isoformat()}")
    elegidos = dado.sample(catalogo, min(len(catalogo), dado.randint(MINIMO_OFERTAS, MAXIMO_OFERTAS)))
    resultado = []
    for auto in elegidos:
        minimo, maximo, _ = RAREZA.get(auto.get("rareza"), RAREZA["Media"])
        estado, factor = dado.choice(ESTADOS)
        anio = ecosistema.numero(auto.get("anio"), hoy.year)
        km = max(500, (hoy.year - anio) * dado.randint(*KM_POR_ANIO)) if anio < hoy.year else dado.randint(100, 3_000)
        precio = round(ecosistema.numero(auto.get("precio_base")) * dado.uniform(minimo, maximo) * factor, -2)
        imagen = ecosistema.imagen_auto(auto)
        resultado.append({
            "id": f"{_slug(auto.get('marca', ''))}_{_slug(auto.get('modelo', ''))}_{anio}_{semana.isoformat()}",
            "marca": auto.get("marca", ""), "modelo": auto.get("modelo", ""), "anio": anio,
            "categoria": auto.get("categoria", ""), "rareza": auto.get("rareza", "Media"), "nota": auto.get("nota", ""),
            "km": km, "estado": estado, "precio": int(max(precio, 1_000)), "imagen": str(imagen) if imagen else "",
        })
    return sorted(resultado, key=lambda o: o["precio"])


def nombre(oferta: dict) -> str:
    return f"{oferta['marca']} {oferta['modelo']} ({oferta['anio']})"


def detalle(oferta: dict) -> str:
    return f"{oferta['km']:,} km · {oferta['estado']}".replace(",", ".")


def articulo(oferta: dict) -> Articulo:
    return Articulo(PREFIJO + oferta["id"], "auto", nombre(oferta), oferta["precio"],
                    autos.mantenimiento(oferta["precio"]), oferta["precio"] >= autos.OSTENTOSO_DESDE, detalle(oferta),
                    "el marketplace")


def extra_de(oferta: dict) -> dict:
    """Lo que se guarda en la posesion, para mostrarla y revenderla."""
    return {"nombre": nombre(oferta), "detalle": detalle(oferta), "rareza": oferta["rareza"],
            "imagen": oferta["imagen"], "categoria": oferta["categoria"]}


def articulo_de_posesion(posesion: dict) -> Articulo:
    precio = posesion["precio"]
    return Articulo(posesion["articulo"], "auto", posesion.get("nombre", "Auto de culto"), precio,
                    autos.mantenimiento(precio), precio >= autos.OSTENTOSO_DESDE, posesion.get("detalle", ""),
                    "el marketplace")


def valor_actual(posesion: dict, hoy: date) -> int:
    """Lo que vale hoy: se valoriza por anio del juego segun la rareza."""
    _, _, por_anio = RAREZA.get(posesion.get("rareza"), RAREZA["Media"])
    try:
        anios = max(0.0, (hoy - date.fromisoformat(posesion.get("desde", hoy.isoformat()))).days / 365)
    except ValueError:
        anios = 0.0
    return round(posesion["precio"] * (1 + por_anio) ** anios)


def valor_de_reventa(posesion: dict, hoy: date) -> int:
    return round(valor_actual(posesion, hoy) * (1 - COMISION))
