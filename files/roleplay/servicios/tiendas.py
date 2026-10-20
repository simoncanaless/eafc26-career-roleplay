"""
La tienda universal: comprar algo de verdad de las webs oficiales (relojes,
moda, tecnologia, muebles, casas, yates y aviones) con la plata del juego.

- TIENDAS: las webs oficiales de cada categoria (marcas reales, solo el
  nombre como texto; verificadas el 2026-10-15 en el navegador: cargan en esa
  direccion). Se abren adentro de la app (ui/tienda.py) o en el navegador de
  siempre.
- NIVELES: precios de referencia por categoria, para cuando la pagina no dice
  cuanto cuesta (o uno no quiere copiarlo).
- leer_metadatos(): lo que dice la pagina de un producto (JSON-LD de
  schema.org u OpenGraph: nombre, precio y moneda; SCRIPT_METADATOS lo junta
  en el navegador) pasado a la moneda del juego. Si la moneda no se sabe, no
  se adivina el precio.

Lo que provoca la compra (seguidores, reputacion, noticia) lo decide
servicios/economia.py, igual que el resto de la tienda.
"""

import json
import re
from dataclasses import dataclass
from typing import Optional
from urllib.parse import urlparse


@dataclass(frozen=True)
class Tienda:
    nombre: str
    url: str
    que: str  # que se hace ahi, para la pantalla
    adentro: bool = True  # False: bloquea los navegadores de las apps ("Access Denied"); se abre en el de siempre


TIENDAS = {
    "casa": [
        Tienda("JamesEdition", "https://www.jamesedition.com/real_estate", "casas, villas y mansiones en venta"),
    ],
    "reloj": [
        Tienda("Rolex", "https://www.rolex.com/es/watches/configure", "el configurador de relojes"),
        Tienda("Audemars Piguet", "https://www.audemarspiguet.com/es/watch-collection", "las colecciones"),
        Tienda("Cartier", "https://www.cartier.com/es-es/watches/collections", "relojes y joyas"),
    ],
    # (probadas en el navegador de la app el 2026-10-20: Gucci, Louis Vuitton, Dior y Farfetch dan
    # "Access Denied" a cualquier navegador integrado, asi que se abren en el de siempre)
    "moda": [
        Tienda("Nike By You", "https://www.nike.com/es/nike-by-you", "disenar tus zapatillas en 3D"),
        Tienda("Balenciaga", "https://www.balenciaga.com/es-es", "la tienda oficial"),
        Tienda("Prada", "https://www.prada.com/es/es.html", "la tienda oficial"),
        Tienda("Versace", "https://www.versace.com/es/es/", "la tienda oficial"),
        Tienda("Moncler", "https://www.moncler.com/es-es/", "la tienda oficial"),
        Tienda("Palm Angels", "https://www.palmangels.com/es-es", "streetwear de lujo"),
        Tienda("Zara", "https://www.zara.com/es/", "la tienda oficial"),
        Tienda("Gucci", "https://www.gucci.com/es/es/", "la tienda oficial (en tu navegador)", adentro=False),
        Tienda("Louis Vuitton", "https://es.louisvuitton.com/esp-es/homepage", "la tienda oficial (en tu navegador)",
               adentro=False),
        Tienda("Dior", "https://www.dior.com/es_es", "la tienda oficial (en tu navegador)", adentro=False),
        Tienda("Farfetch", "https://www.farfetch.com/es/", "moda de lujo de todas las marcas (en tu navegador)",
               adentro=False),
    ],
    "yate": [
        Tienda("JamesEdition", "https://www.jamesedition.com/yachts", "yates en venta"),
    ],
    "avion": [
        Tienda("JamesEdition", "https://www.jamesedition.com/jets", "jets privados en venta"),
    ],
    "tecnologia": [
        Tienda("Xbox Design Lab", "https://xboxdesignlab.xbox.com/", "disenar tu control en 3D"),
        Tienda("Apple", "https://www.apple.com/es/store", "la tienda oficial"),
        Tienda("Secretlab", "https://secretlab.eu/es", "sillas y escritorios gamer"),
    ],
    "muebles": [
        Tienda("Roche Bobois", "https://www.roche-bobois.com/es-ES/", "muebles de disenador"),
        Tienda("IKEA", "https://www.ikea.com/es/es/planners/", "planificar ambientes en 3D"),
    ],
}

# (rotulo, precio en la moneda del juego)
NIVELES = {
    "casa": [("Departamento", 650_000), ("Casa", 2_500_000), ("Mansion", 9_000_000), ("Villa", 22_000_000)],
    "reloj": [("Reloj", 15_000), ("Alta relojeria", 60_000), ("Con diamantes", 250_000), ("Pieza unica", 1_000_000)],
    "moda": [("Una prenda", 1_500), ("Un look", 8_000), ("Coleccion", 40_000), ("Alta costura", 400_000)],
    "yate": [("Lancha", 500_000), ("Yate", 5_000_000), ("Superyate", 12_000_000), ("Megayate", 60_000_000)],
    "avion": [("Avion ligero", 3_000_000), ("Jet mediano", 15_000_000), ("Jet grande", 45_000_000)],
    "tecnologia": [("Gadget", 1_500), ("Setup", 8_000), ("Setup de alta gama", 25_000), ("Sala de cine", 150_000)],
    "muebles": [("Un mueble", 3_000), ("Un ambiente", 20_000), ("Living de disenador", 60_000), ("Obra de arte", 500_000)],
}

# cuanto vale cada moneda en euros (aproximado: es para el roleplay) y el euro
# en la moneda del juego (servicios/economia.py:moneda_de)
EN_EUROS = {"EUR": 1.0, "USD": 0.92, "GBP": 1.17, "CHF": 1.05, "CLP": 0.00098, "MXN": 0.05, "AED": 0.25,
            "JPY": 0.0061, "CAD": 0.67, "AUD": 0.6}
EURO_EN = {"€": 1.0, "£": 0.85, "$": 1.09}
SIMBOLOS = {"€": "EUR", "£": "GBP", "US$": "USD", "$": "USD", "USD": "USD", "EUR": "EUR", "GBP": "GBP", "CHF": "CHF",
            "CLP": "CLP"}
# un precio escrito en la pagina: "€19,250,000", "US$ 1.299", "12 500 000 EUR"
PRECIO_EN_TEXTO = re.compile(
    r"(US\$|USD|EUR|GBP|CHF|€|£|\$)\s?(\d[\d.,\s]{2,}\d)|(\d[\d.,\s]{2,}\d)\s?(USD|EUR|GBP|CHF|€|£)")
LARGO_NOMBRE = 80

# lo que corre en la pagina (ui/tienda.py): junta JSON-LD y OpenGraph
SCRIPT_METADATOS = r"""
(() => {
  const meta = (k) => {
    const e = document.querySelector(`meta[property="${k}"], meta[name="${k}"], meta[itemprop="${k}"]`);
    return e ? (e.getAttribute("content") || "") : "";
  };
  const ofertas = [];
  for (const s of document.querySelectorAll('script[type="application/ld+json"]')) {
    let datos;
    try { datos = JSON.parse(s.textContent); } catch (e) { continue; }
    const pila = [datos];
    while (pila.length) {
      const x = pila.pop();
      if (Array.isArray(x)) { pila.push(...x); continue; }
      if (!x || typeof x !== "object") continue;
      if (x["@graph"]) pila.push(x["@graph"]);
      const oferta = [].concat(x.offers || [])[0];
      const spec = (oferta && oferta.priceSpecification) || {};
      const precio = (oferta && (oferta.price || oferta.lowPrice || spec.price)) || x.price;
      if (precio !== undefined && precio !== null && precio !== "") {
        ofertas.push({
          nombre: String(x.name || ""),
          precio: typeof precio === "number" ? precio : String(precio),  // un numero va como numero (21622823.823)
          moneda: String((oferta && (oferta.priceCurrency || spec.priceCurrency)) || x.priceCurrency || ""),
          imagen: String([].concat(x.image || [])[0] || "").trim(),
        });
      }
    }
  }
  return {
    titulo: document.title, url: location.href,
    og_titulo: meta("og:title"), og_imagen: meta("og:image"),
    precio: meta("product:price:amount") || meta("og:price:amount") || meta("price"),
    moneda: meta("product:price:currency") || meta("og:price:currency") || meta("priceCurrency"),
    ofertas: ofertas.slice(0, 5),
    precio_texto: ((document.querySelector("main") || document.body).innerText.slice(0, 20000)
      .match(/(US\$|USD|EUR|GBP|CHF|€|£|\$)\s?\d[\d.,\s]{2,}\d|\d[\d.,\s]{2,}\d\s?(USD|EUR|GBP|CHF|€|£)/) || [""])[0],
  };
})()
"""


# runJavaScript no convierte bien un objeto con listas de objetos (llegaba "" y nunca se leia el
# precio): la pagina devuelve el JSON como texto y datos_de_script lo abre
SCRIPT_METADATOS = "JSON.stringify(" + SCRIPT_METADATOS.strip() + ")"


def datos_de_script(resultado) -> Optional[dict]:
    """Lo que devolvio SCRIPT_METADATOS (texto JSON; o ya un dict) como dict, o None."""
    if isinstance(resultado, dict):
        return resultado
    try:
        datos = json.loads(resultado) if isinstance(resultado, str) and resultado else None
    except ValueError:
        return None
    return datos if isinstance(datos, dict) else None


def numero(texto) -> Optional[float]:
    """"585000" -> 585000; "1.299,99" -> 1299.99; "1,299.99" -> 1299.99;
    "12.500" -> 12500 (tres cifras despues del punto: son miles). None si no hay numero."""
    if isinstance(texto, (int, float)):
        return float(texto)
    limpio = re.sub(r"[^\d.,]", "", str(texto or ""))
    if not re.search(r"\d", limpio):
        return None
    if "." in limpio and "," in limpio:
        decimal = "." if limpio.rfind(".") > limpio.rfind(",") else ","
        limpio = limpio.replace("," if decimal == "." else ".", "").replace(decimal, ".")
    elif limpio.count(".") > 1 or limpio.count(",") > 1:
        limpio = limpio.replace(".", "").replace(",", "")
    elif "." in limpio or "," in limpio:
        entero, resto = limpio.split("." if "." in limpio else ",")
        limpio = entero + resto if len(resto) == 3 and entero else f"{entero or 0}.{resto}"
    try:
        return float(limpio)
    except ValueError:
        return None


def convertir(monto: float, moneda: str, moneda_juego: str) -> Optional[int]:
    """`monto` en `moneda` (codigo ISO) a la moneda del juego, o None si no se conoce."""
    if moneda.upper() not in EN_EUROS or moneda_juego not in EURO_EN:
        return None
    return round(monto * EN_EUROS[moneda.upper()] * EURO_EN[moneda_juego])


def limpiar_titulo(titulo: str) -> str:
    """"Sillas de gaming | Secretlab TITAN Evo | Secretlab EU" -> lo de antes del primer separador."""
    for parte in re.split(r"\s+[|–—-]\s+", titulo or ""):
        if parte.strip():
            return parte.strip()[:LARGO_NOMBRE]
    return ""


@dataclass
class LecturaPagina:
    nombre: str = ""
    precio: Optional[int] = None  # en la moneda del juego
    original: str = ""  # "USD 585.000", para mostrar de donde salio
    imagen: str = ""


def leer_metadatos(datos: Optional[dict], moneda_juego: str) -> LecturaPagina:
    """`datos` = lo que devuelve SCRIPT_METADATOS. Primero el producto de
    schema.org (trae nombre, precio y moneda juntos), despues OpenGraph."""
    datos = datos or {}
    oferta = next((o for o in datos.get("ofertas", []) if numero(o.get("precio"))), None)
    if oferta is not None:
        nombre = oferta.get("nombre") or limpiar_titulo(datos.get("og_titulo") or datos.get("titulo", ""))
        monto, moneda, imagen = numero(oferta["precio"]), oferta.get("moneda", ""), oferta.get("imagen", "")
    else:
        nombre = limpiar_titulo(datos.get("og_titulo") or datos.get("titulo", ""))
        monto, moneda, imagen = numero(datos.get("precio")), datos.get("moneda", ""), ""
        if not monto:  # ni schema.org ni OpenGraph: el primer precio escrito en la pagina
            monto, moneda = precio_en_texto(datos.get("precio_texto", ""))
    lectura = LecturaPagina(nombre=nombre.strip()[:LARGO_NOMBRE], imagen=(imagen or datos.get("og_imagen", "")).strip())
    if monto:
        moneda = SIMBOLOS.get(moneda.strip(), moneda.strip().upper())
        lectura.original = f"{moneda or '?'} {round(monto):,}".replace(",", ".")
        lectura.precio = convertir(monto, moneda, moneda_juego) if moneda else None
    return lectura


def precio_en_texto(texto: str) -> tuple:
    """"€19,250,000" -> (19250000.0, "EUR"); (None, "") si no hay un precio con su moneda."""
    m = PRECIO_EN_TEXTO.search(texto or "")
    if not m:
        return None, ""
    simbolo = (m.group(1) or m.group(4) or "").strip()
    cifra = (m.group(2) or m.group(3) or "").replace(" ", "").replace("\u202f", "").replace("\xa0", "")
    return numero(cifra), SIMBOLOS.get(simbolo, simbolo)


def _dominio(url: str) -> str:
    """"https://es.louisvuitton.com/esp-es" -> "louisvuitton.com"."""
    return ".".join((urlparse(url).hostname or "").split(".")[-2:])


def tienda_de_url(url: str, categoria: str) -> Tienda:
    """La tienda de la lista a la que pertenece `url` (por el dominio), o una suelta."""
    dominio = _dominio(url)
    candidatas = TIENDAS.get(categoria, []) + [t for lista in TIENDAS.values() for t in lista]
    return next((t for t in candidatas if dominio and _dominio(t.url) == dominio),
                Tienda(dominio or "una tienda", url, ""))
