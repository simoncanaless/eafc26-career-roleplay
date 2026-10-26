"""
El configurador oficial nativo (pedido de Simon, 2026-10-26; SOLO para su PC: la app no se publica).

Las opciones reales de cada modelo (pinturas con su hex, llantas, interiores, paquetes, con su nombre y precio
oficial en libras) salen de la pagina del configurador de la marca: `scripts/extraer_configuradores.py` las lee
con el mismo motor del navegador de la app (QtWebEngine) de los datos que la pagina ya trae, y las guarda en
`roleplay/datos/configuradores_oficiales.json`. El render de cada combinacion lo pide `render()` al servicio de
imagenes de la marca y lo guarda en `roleplay/datos/img_configurador/` (una vez por combinacion: nunca se pide
dos veces la misma). Hoy: Porsche (`prs.porsche.com/iod`, la combinacion va comprimida con lz-string).

Los dos (el JSON y las imagenes) son de las marcas: van en .gitignore y el paquete de los amigos NO los lleva.
Sin el JSON, el concesionario sigue con el configurador de siempre (la web oficial adentro de la app o el dibujo).
"""

import hashlib
import json
import os
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

CARPETA = Path(__file__).resolve().parent.parent / "datos"
ARCHIVO = CARPETA / "configuradores_oficiales.json"
CARPETA_RENDERS = CARPETA / "img_configurador"

# lo que se elige en la pantalla (el resto del equipamiento queda como viene de fabrica)
SECCIONES = {
    "section-exterior-color": "Color exterior",
    "section-wheels": "Llantas",
    "section-interior-color": "Interior",
    "section-interior-seats": "Asientos",
    "section-individualization-packages": "Paquetes",
    "section-individualization-exterior": "Exterior",
}
# lo que no se ve en el auto ni cambia el render: neumaticos, juegos de invierno, accesorios de llantas
CATEGORIAS_OCULTAS = ("tyres", "winter", "wheel sets", "accessor")
# secciones donde se elige UNA sola cosa aunque venga en varias categorias (llantas "Wheels" y "Painted wheels")
UNA_POR_SECCION = {"section-exterior-color", "section-wheels", "section-interior-color", "section-interior-seats"}
# las de mas prestigio: suben el valor de reventa (se buscan en la categoria o el grupo)
PRESTIGIO = ("paint to sample", "exclusive", "manufaktur", "weissach", "carbono", "carbon", "tailor", "ad personam",
             "mso", "assetto")
REVENTA_PRESTIGIO = 0.25  # de lo invertido en opcionales de prestigio, cuanto suma a la reventa


def ruta_archivo() -> Path:
    return Path(os.environ.get("EAFC_CONFIGURADORES", ARCHIVO))


def catalogo() -> dict:
    """{codigo de modelo: {...}} o {} sin el archivo (nunca falla)."""
    try:
        return json.loads(ruta_archivo().read_text(encoding="utf-8")).get("modelos", {})
    except (OSError, ValueError):
        return {}


def de_modelo(url_configurador: str) -> Optional[dict]:
    """El catalogo oficial de un modelo del concesionario (por el codigo de su url), o None."""
    codigo = url_configurador.rstrip("/").rsplit("/", 1)[-1] if "/model/" in url_configurador else ""
    return catalogo().get(codigo) if codigo else None


@dataclass
class Eleccion:
    """Lo que eligio el jugador sobre un modelo oficial."""
    codigo: str
    opciones: dict = field(default_factory=dict)  # seccion|categoria -> id de la opcion

    def ids(self) -> list:
        return list(self.opciones.values())


def opciones_por_categoria(modelo: dict) -> dict:
    """{(seccion, categoria): [opciones]} solo de las SECCIONES que se eligen."""
    grupos: dict = {}
    for op in modelo.get("opciones", []):
        if op.get("seccion") in SECCIONES and not any(c in op["categoria"].lower() for c in CATEGORIAS_OCULTAS):
            grupos.setdefault((op["seccion"], op["categoria"]), []).append(op)
    return grupos


def de_fabrica(modelo: dict) -> Eleccion:
    """La eleccion inicial: lo que viene seleccionado en el configurador de la marca."""
    eleccion = Eleccion(modelo["codigo"])
    for (seccion, categoria), ops in opciones_por_categoria(modelo).items():
        elegida = next((o for o in ops if o.get("seleccionada")), None)
        if elegida is not None:
            eleccion.opciones[f"{seccion}|{categoria}"] = elegida["id"]
    return eleccion


def elegir(eleccion: Eleccion, clave: str, opcion_id: str) -> None:
    """Elige (o con "" vuelve a lo de fabrica) en una categoria "seccion|categoria"."""
    seccion = clave.split("|", 1)[0]
    if opcion_id and seccion in UNA_POR_SECCION:
        for otra in [c for c in eleccion.opciones if c.split("|", 1)[0] == seccion]:
            del eleccion.opciones[otra]
    if opcion_id:
        eleccion.opciones[clave] = opcion_id
    else:
        eleccion.opciones.pop(clave, None)


def _por_id(modelo: dict) -> dict:
    return {o["id"]: o for o in modelo.get("opciones", [])}


def elegidas(modelo: dict, eleccion: Eleccion) -> list:
    por_id = _por_id(modelo)
    return [por_id[i] for i in eleccion.ids() if i in por_id]


def opcionales(modelo: dict, eleccion: Eleccion) -> int:
    return sum(int(o.get("precio") or 0) for o in elegidas(modelo, eleccion))


def precio_total(modelo: dict, eleccion: Eleccion) -> int:
    """Precio base oficial + la suma de los opcionales elegidos (lo de fabrica cuesta 0)."""
    return int(modelo.get("base") or 0) + opcionales(modelo, eleccion)


def es_de_prestigio(opcion: dict) -> bool:
    texto = f"{opcion.get('categoria', '')} {opcion.get('grupo', '')} {opcion.get('nombre', '')}".lower()
    return any(p in texto for p in PRESTIGIO)


def bonus_de_reventa(config_oficial: Optional[dict]) -> int:
    """Lo que la configuracion suma a la reventa: una parte de lo invertido en opcionales de prestigio."""
    if not config_oficial:
        return 0
    invertido = sum(int(o.get("precio") or 0) for o in config_oficial.get("opciones", []) if es_de_prestigio(o))
    return round(invertido * REVENTA_PRESTIGIO)


def nombre_de_configuracion(modelo_nombre: str, config_oficial: Optional[dict]) -> str:
    """"Porsche 911 GT3 RS en Shark Blue con Paquete Weissach": para la prensa, Instagram y la memoria."""
    if not config_oficial:
        return modelo_nombre
    ops = config_oficial.get("opciones", [])
    color = next((o["nombre"] for o in ops if o.get("seccion") == "section-exterior-color"), "")
    paquete = next((o["nombre"] for o in ops if o.get("seccion") == "section-individualization-packages"
                    and o.get("precio")), "")
    texto = modelo_nombre + (f" en {color}" if color else "")
    return texto + (f" con {paquete}" if paquete else "")


def ficha(modelo: dict, eleccion: Eleccion) -> dict:
    """La especificacion que se guarda en el pedido y despues en el garage (config["oficial"])."""
    ops = elegidas(modelo, eleccion)
    return {
        "marca": modelo.get("marca", ""), "codigo": modelo["codigo"], "modelo": modelo.get("modelo", ""),
        "anio": modelo.get("anio"), "moneda": modelo.get("moneda", "GBP"), "base": int(modelo.get("base") or 0),
        "opciones": [{k: o.get(k) for k in ("id", "nombre", "seccion", "categoria", "grupo", "hex", "precio")} for o in ops],
        "opcionales": opcionales(modelo, eleccion), "total": precio_total(modelo, eleccion),
    }


def resumen(ficha_oficial: dict) -> list:
    """La spec sheet: [(seccion legible, nombre, precio)]."""
    return [(SECCIONES.get(o.get("seccion"), o.get("categoria", "")), o["nombre"], int(o.get("precio") or 0))
            for o in ficha_oficial.get("opciones", [])]


# ---- el render oficial (con cache) ----

def _ids_de_render(modelo: dict, eleccion: Eleccion) -> list:
    """Los ids que entran al render: los de fabrica, cambiando en cada categoria elegida la de fabrica por la elegida."""
    por_id = _por_id(modelo)

    def grupo(op: dict) -> str:  # lo que se reemplaza: la seccion entera (pintura, llantas) o la categoria
        return op["seccion"] if op["seccion"] in UNA_POR_SECCION else f"{op['seccion']}|{op['categoria']}"

    elegidos = {grupo(por_id[i]): i for i in eleccion.ids() if i in por_id}
    base = []
    for i in modelo.get("render", []):
        op = por_id.get(i)
        if op is None or grupo(op) not in elegidos:
            base.append(i)
    return sorted(set(base) | set(elegidos.values()))


def url_render(modelo: dict, eleccion: Eleccion, camara: str = "ext-low-front-left") -> str:
    import lzstring

    pais = modelo.get("pais", "GB")
    pedido = {"config": {"animations": [], "camera": {"id": camara, "options": {"variant": "desktop"}},
                         "environment": {"id": "WhiteroomAlpha", "options": {}}, "lighting": {"id": "DAY", "options": {}},
                         "product": {"id": modelo["codigo"], "options": {"config": _ids_de_render(modelo, eleccion),
                                                                          "country": pais, "modelYear": modelo.get("anio")}}},
              "settings": {"format": "png", "transparent": True}}
    comprimido = lzstring.LZString().compressToEncodedURIComponent(json.dumps(pedido, separators=(",", ":")))
    return f"https://prs.porsche.com/iod/image/{pais}/{modelo['codigo']}/1/{comprimido}?clientId=icc"


def render(modelo: dict, eleccion: Eleccion, camara: str = "ext-low-front-left") -> Optional[Path]:
    """El render de esa combinacion (de la cache o pedido una vez). None sin internet. Corre en un hilo."""
    clave = hashlib.sha1(json.dumps([modelo["codigo"], _ids_de_render(modelo, eleccion), camara]).encode()).hexdigest()[:16]
    destino = CARPETA_RENDERS / modelo["codigo"] / f"{clave}.png"
    if destino.exists():
        return destino
    try:
        pedido = urllib.request.Request(url_render(modelo, eleccion, camara), headers={
            "User-Agent": "Mozilla/5.0", "Referer": "https://configurator.porsche.com/"})
        with urllib.request.urlopen(pedido, timeout=30) as respuesta:
            datos = respuesta.read()
    except (OSError, ValueError):
        return None
    destino.parent.mkdir(parents=True, exist_ok=True)
    destino.write_bytes(datos)
    return destino
