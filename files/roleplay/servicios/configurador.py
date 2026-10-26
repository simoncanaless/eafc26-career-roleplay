"""
El configurador oficial nativo (pedido de Simon, 2026-10-26; SOLO para su PC: la app no se publica).

Las opciones reales de cada modelo (pinturas con su hex, llantas, interiores, paquetes, con su nombre, precio
oficial en libras, la foto de cada opcion y su descripcion) salen de la pagina del configurador de la marca:
`scripts/extraer_configuradores.py` las lee con el mismo motor del navegador de la app (QtWebEngine) de los datos
que la pagina ya trae, y las guarda en `roleplay/datos/configuradores_oficiales.json`, con las camaras de cada vista
y los fondos (tunel de viento, oasis, estudio). Las imagenes las pide `render()` / `miniatura()` al servicio de la
marca y quedan en `roleplay/datos/img_configurador/` (una vez por combinacion: nunca se pide dos veces la misma).
Hoy: Porsche (`prs.porsche.com/iod`, la combinacion va comprimida con lz-string).

Los dos (el JSON y las imagenes) son de las marcas: van en .gitignore y el paquete de los amigos NO los lleva.
Sin el JSON, el concesionario sigue con el configurador de siempre (la web oficial adentro de la app o el dibujo).
"""

import hashlib
import html
import json
import os
import re
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

CARPETA = Path(__file__).resolve().parent.parent / "datos"
ARCHIVO = CARPETA / "configuradores_oficiales.json"
CARPETA_RENDERS = CARPETA / "img_configurador"
SITIO = "https://configurator.porsche.com"
CABECERAS = {"User-Agent": "Mozilla/5.0", "Referer": SITIO + "/"}

# las pestanas de la pantalla, en el orden de la pagina (lo demas queda como viene de fabrica)
SECCIONES = {
    "section-exterior-color": "Color",
    "section-wheels": "Llantas",
    "section-interior-color": "Interior",
    "section-interior-seats": "Asientos",
    "section-individualization-packages": "Paquetes",
    "section-individualization-exterior": "Exterior",
    "section-individualization-interior": "Personalizar interior",
    "section-individualization-technology": "Tecnologia",
}
# lo que no se ve en el auto ni cambia el render: neumaticos, juegos de invierno, accesorios de llantas
CATEGORIAS_OCULTAS = ("tyres", "winter", "wheel sets", "accessor")
# secciones donde se elige UNA sola cosa aunque venga en varias categorias (la pintura, aunque Paint to Sample venga
# aparte), y donde se elige una por categoria (llantas: el modelo en "Wheels" y su pintura en "Painted wheels");
# en las demas cada opcion se prende y se apaga, como las casillas de la pagina
UNA_POR_SECCION = {"section-exterior-color", "section-interior-color", "section-interior-seats"}
UNA_POR_CATEGORIA = {"section-wheels"}
# las de mas prestigio: suben el valor de reventa (se buscan en la categoria, el grupo o el nombre)
PRESTIGIO = ("paint to sample", "exclusive", "manufaktur", "weissach", "carbono", "carbon", "tailor", "ad personam",
             "mso", "assetto")
REVENTA_PRESTIGIO = 0.25  # de lo invertido en opcionales de prestigio, cuanto suma a la reventa

# girar el auto: las camaras de afuera en orden alrededor del auto. La de adelante a la derecha no existe en el
# servicio: es la de adelante a la izquierda dada vuelta (espejo=True)
GIRO = [("ext-low-front", False), ("ext-low-front-left", False), ("ext-low-side-left", False),
        ("ext-low-rear-left", False), ("ext-low-rear", False), ("ext-low-rear-right", False),
        ("ext-low-side-right", False), ("ext-low-front-left", True)]
# las otras vistas de la pagina (si el modelo las trae)
VISTAS = {"ext-low-front-left-wheel": "Llanta", "ext-high-rear-left": "Desde arriba", "int-front-dashboard": "Tablero",
          "int-front-seats": "Asientos", "int-rear-seats": "Atras"}
ENTORNOS = {"WindTunnel": "Tunel de viento", "Oasis": "Oasis", "Whiteroom Porsche": "Estudio"}


def ruta_archivo() -> Path:
    return Path(os.environ.get("EAFC_CONFIGURADORES", ARCHIVO))


_CACHE: dict = {}


def catalogo() -> dict:
    """{codigo de modelo: {...}} o {} sin el archivo (nunca falla). Se lee una vez por version del archivo."""
    ruta = ruta_archivo()
    try:
        firma = (str(ruta), ruta.stat().st_mtime_ns)
        if _CACHE.get("firma") != firma:
            _CACHE.update(firma=firma, modelos=json.loads(ruta.read_text(encoding="utf-8")).get("modelos", {}))
        return _CACHE["modelos"]
    except (OSError, ValueError):
        return {}


def de_modelo(modelo) -> Optional[dict]:
    """El catalogo oficial de un modelo del concesionario (autos.Modelo): por su id (`modelo_app`) o, en los de
    Porsche, por el codigo de su url. None si no hay. Tambien acepta la url sola."""
    url = modelo if isinstance(modelo, str) else modelo.url_configurador
    todos = catalogo()
    if not isinstance(modelo, str):
        for datos in todos.values():
            if datos.get("modelo_app") == modelo.id:
                return datos
    codigo = url.rstrip("/").rsplit("/", 1)[-1] if "/model/" in url else ""
    return todos.get(codigo) if codigo else None


@dataclass
class Eleccion:
    """Lo que eligio el jugador sobre un modelo oficial: clave -> id (`clave_de`)."""
    codigo: str
    opciones: dict = field(default_factory=dict)

    def ids(self) -> list:
        return list(self.opciones.values())


def clave_de(op: dict) -> str:
    """En las secciones de una sola cosa, la seccion (o la categoria); si la opcion es de un grupo donde se elige
    una sola (`exclusivo`: las colecciones obligatorias de Aston Martin), el grupo; en las demas, su casilla."""
    if op["seccion"] in UNA_POR_SECCION:
        return op["seccion"]
    if op.get("exclusivo"):
        return f"{op['seccion']}|g|{op.get('grupo_id') or op['categoria']}"
    if op["seccion"] in UNA_POR_CATEGORIA:
        return f"{op['seccion']}|{op['categoria']}"
    return f"{op['seccion']}|{op['id']}"


def es_casilla(op: dict) -> bool:
    return op["seccion"] not in UNA_POR_SECCION | UNA_POR_CATEGORIA and not op.get("exclusivo")


def visible(op: dict) -> bool:
    return op.get("seccion") in SECCIONES and not any(c in op["categoria"].lower() for c in CATEGORIAS_OCULTAS)


def opciones_por_seccion(modelo: dict) -> dict:
    """{seccion: {categoria: [opciones]}} en el orden de SECCIONES y de la pagina."""
    salida: dict = {s: {} for s in SECCIONES}
    for op in modelo.get("opciones", []):
        if visible(op):
            salida[op["seccion"]].setdefault(op["categoria"], []).append(op)
    return {s: cats for s, cats in salida.items() if cats}


def _por_id(modelo: dict) -> dict:
    return {o["id"]: o for o in modelo.get("opciones", [])}


def de_fabrica(modelo: dict) -> Eleccion:
    """La eleccion inicial: lo que viene seleccionado en el configurador de la marca."""
    eleccion = Eleccion(modelo["codigo"])
    for op in modelo.get("opciones", []):
        if op.get("seleccionada") and visible(op):
            eleccion.opciones[clave_de(op)] = op["id"]
    return eleccion


def bloqueada(op: dict) -> bool:
    """Lo de serie que viene puesto no se saca (en la pagina tampoco)."""
    return bool(op.get("estandar") and op.get("seleccionada"))


def elegir(modelo: dict, eleccion: Eleccion, opcion_id: str) -> bool:
    """Elige una opcion; en las casillas, si ya estaba, la saca. Devuelve si cambio algo."""
    op = _por_id(modelo).get(opcion_id)
    if op is None:
        return False
    clave = clave_de(op)
    if not es_casilla(op):
        if eleccion.opciones.get(clave) == opcion_id:
            return False
        eleccion.opciones[clave] = opcion_id
    elif clave in eleccion.opciones:
        if bloqueada(op):
            return False
        del eleccion.opciones[clave]
    else:
        eleccion.opciones[clave] = opcion_id
    return True


def elegidas(modelo: dict, eleccion: Eleccion) -> list:
    por_id = _por_id(modelo)
    return [por_id[i] for i in eleccion.ids() if i in por_id]


def opcionales(modelo: dict, eleccion: Eleccion) -> int:
    return sum(int(o.get("precio") or 0) for o in elegidas(modelo, eleccion))


def precio_total(modelo: dict, eleccion: Eleccion) -> int:
    """Precio base oficial + la suma de los opcionales elegidos (lo de fabrica cuesta 0)."""
    return int(modelo.get("base") or 0) + opcionales(modelo, eleccion)


def descripcion(op: dict) -> str:
    """La descripcion de la pagina en texto (viene con <br /> y entidades)."""
    texto = re.sub(r"<br\s*/?>", "\n", op.get("descripcion") or "")
    return html.unescape(re.sub(r"<[^>]+>", "", texto)).strip()


# las marcas que no dan el color en hex (Aston Martin, Ferrari): uno aproximado por el nombre, solo para el circulo
# (el render muestra el de verdad). En orden: la palabra mas especifica primero
COLORES = [
    ("canna di fucile", "#4A4E52"), ("gunmetal", "#4A4E52"), ("british racing", "#1F4D2E"), ("racing green", "#1F4D2E"),
    ("navy", "#1C2A4A"), ("midnight", "#1C2440"), ("burgundy", "#6B1F2A"), ("bordeaux", "#6B1F2A"), ("titanium", "#7E8287"),
    ("platinum", "#B9BCBE"), ("champagne", "#D8C7A0"), ("magnetic", "#5E6266"), ("bronze", "#8C6239"), ("copper", "#B26B3D"),
    ("gold", "#C9A227"), ("oro", "#C9A227"), ("silver", "#C0C4C8"), ("argento", "#C0C4C8"), ("grigio", "#7A7F86"),
    ("grey", "#7A7F86"), ("gray", "#7A7F86"), ("nero", "#121212"), ("black", "#121212"), ("onyx", "#151515"),
    ("bianco", "#F2F2F0"), ("white", "#F2F2F0"), ("avorio", "#EFE6D2"), ("ivory", "#EFE6D2"), ("cream", "#EDE3C8"),
    ("crema", "#EDE3C8"), ("rosso", "#C1121F"), ("red", "#C1121F"), ("giallo", "#F2C200"), ("yellow", "#F2C200"),
    ("arancio", "#E8701A"), ("orange", "#E8701A"), ("azzurro", "#4FA3E0"), ("blu", "#1F3A93"), ("blue", "#1F3A93"),
    ("verde", "#2E6B45"), ("green", "#2E6B45"), ("viola", "#5B2A86"), ("purple", "#5B2A86"), ("marrone", "#5B3A29"),
    ("brown", "#5B3A29"), ("tan", "#A0703C"), ("cuoio", "#8B5A2B"), ("beige", "#CDB891"), ("sabbia", "#CDB891"),
    ("sand", "#CDB891"), ("rosa", "#D98BA0"), ("pink", "#D98BA0"),
]


def color_por_nombre(nombre: str) -> str:
    texto = nombre.lower()
    return next((hex_ for palabra, hex_ in COLORES if palabra in texto), "")


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


# ---- las vistas ----

def proveedor(modelo: dict) -> str:
    """De que marca es el catalogo (como se piden las imagenes): porsche (el primero, sin la clave) o aston."""
    return modelo.get("proveedor", "porsche")


def giro(modelo: dict) -> list:
    """[(camara, espejo)] alrededor del auto: las del modelo o las de Porsche."""
    return [tuple(c) for c in modelo["giro"]] if modelo.get("giro") else GIRO


def giro_inicial(modelo: dict) -> int:
    return int(modelo.get("giro_inicial", 1))


def entornos(modelo: dict) -> dict:
    """{id: nombre} de los fondos que se pueden elegir (el primero, el de entrada)."""
    return modelo.get("entornos_ui") or ENTORNOS


def camara_de_seccion(modelo: dict, seccion: str) -> Optional[str]:
    """La camara que la pagina muestra al abrir esa seccion (llantas -> la llanta, interior -> el tablero)."""
    if "camara_seccion" in modelo:
        return modelo["camara_seccion"].get(seccion)
    for vista in (modelo.get("vistas_seccion") or {}).get(seccion) or []:
        camara = (modelo.get("camaras") or {}).get(vista)
        if camara:
            return camara
    return None


def vistas_extra(modelo: dict) -> list:
    """[(camara, nombre)] de las vistas que no son del giro y que el modelo trae."""
    if "vistas" in modelo:
        return list(modelo["vistas"].items())
    tiene = set((modelo.get("camaras") or {}).values())
    return [(c, n) for c, n in VISTAS.items() if c in tiene]


# ---- las imagenes oficiales (con cache) ----

def _ids_de_render(modelo: dict, eleccion: Eleccion) -> list:
    """Los ids que entran al render: lo de fabrica que la pantalla no maneja + lo elegido."""
    controladas = {o["id"] for o in modelo.get("opciones", []) if visible(o)}
    base = [i for i in modelo.get("render", []) if i not in controladas]
    return sorted(set(base) | set(eleccion.ids()))


def _pedido_render(modelo: dict, eleccion: Eleccion, camara: str, entorno: str, noche: bool) -> dict:
    return {"config": {"animations": [], "camera": {"id": camara, "options": {"variant": "desktop"}},
                       "environment": {"id": entorno, "options": {}},
                       "lighting": {"id": "NIGHT" if noche else "DAY", "options": {}},
                       "product": {"id": modelo["codigo"], "options": {"config": _ids_de_render(modelo, eleccion),
                                                                        "country": modelo.get("pais", "GB"),
                                                                        "modelYear": modelo.get("anio")}}},
            "settings": {"format": "jpeg", "transparent": False}}


def valor_aston(op_id: str):
    """Como va una opcion de Aston Martin en el pedido: un codigo ("3132") o, las de una lista (los cueros por
    zona), {"TU": {"TU": "L830"}} (el id es "TU:L830")."""
    if ":" in op_id:
        lista, codigo = op_id.split(":", 1)
        return {lista: {lista: codigo}}
    return op_id


def _url_aston(modelo: dict, eleccion: Eleccion, camara: str, entorno: str, noche: bool) -> str:
    import lzstring

    ids = _ids_de_render(modelo, eleccion)
    valores = [i for i in ids if ":" not in i] + [valor_aston(i) for i in ids if ":" in i]
    pedido = {"animations": [], "camera": {"id": camara, "options": {}},
              "config": {"id": modelo["codigo"], "options": {"config": valores}},
              "environment": {"id": entorno, "options": {"night": noche}}}
    comprimido = lzstring.LZString().compressToEncodedURIComponent(json.dumps(pedido, separators=(",", ":")))
    return f"https://configurator.astonmartin.com/iod/{modelo.get('pais', 'GB')}/{modelo['codigo']}/1920/{comprimido}"


def url_render(modelo: dict, eleccion: Eleccion, camara: str = "ext-low-front-left", entorno: str = "WindTunnel",
               noche: bool = False) -> str:
    import lzstring

    if proveedor(modelo) == "aston":
        return _url_aston(modelo, eleccion, camara, entorno, noche)
    pedido = _pedido_render(modelo, eleccion, camara, entorno, noche)
    comprimido = lzstring.LZString().compressToEncodedURIComponent(json.dumps(pedido, separators=(",", ":")))
    return f"https://prs.porsche.com/iod/image/{modelo.get('pais', 'GB')}/{modelo['codigo']}/1/{comprimido}?clientId=icc"


def _bajar(url: str, destino: Path, intentos: int = 1, timeout: int = 30) -> Optional[Path]:
    """Baja una vez (si ya esta, no pide nada). Con `intentos`, reintenta cuando el servidor todavia esta
    generando la imagen (Aston Martin la dibuja en el momento: 503/504 las primeras veces)."""
    import time
    import urllib.error

    if destino.exists():
        return destino
    for intento in range(intentos):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=CABECERAS), timeout=timeout) as respuesta:
                datos = respuesta.read()
            break
        except urllib.error.HTTPError as error:
            if error.code not in (502, 503, 504) or intento == intentos - 1:
                return None
            time.sleep(3)
        except (OSError, ValueError):
            return None
    destino.parent.mkdir(parents=True, exist_ok=True)
    destino.write_bytes(datos)
    return destino


def render(modelo: dict, eleccion: Eleccion, camara: str = "ext-low-front-left", entorno: str = "WindTunnel",
           noche: bool = False) -> Optional[Path]:
    """El render de esa combinacion y vista (de la cache o pedido una vez). None sin internet o si la marca no
    tiene esa imagen. Corre en un hilo."""
    url = url_render(modelo, eleccion, camara, entorno, noche)
    destino = CARPETA_RENDERS / modelo["codigo"] / f"{hashlib.sha1(url.encode()).hexdigest()[:16]}.jpg"
    if destino.exists():
        return destino
    if proveedor(modelo) == "aston":
        return _bajar(url, destino, intentos=4, timeout=120)
    return _bajar(url, destino)


def miniatura(op: dict) -> Optional[Path]:
    """La foto chica de la opcion (la de la pagina), bajada una vez. None si no tiene o sin internet."""
    ruta = op.get("miniatura") or ""
    if not ruta:
        return None
    url = ruta if ruta.startswith("http") else SITIO + ruta
    nombre = hashlib.sha1(url.split("?", 1)[0].encode()).hexdigest()[:16] + ".jpg"
    return _bajar(url, CARPETA_RENDERS / "miniaturas" / nombre)


def miniaturas(modelo: dict, ids: list) -> dict:
    """{id: ruta} de las que se pudieron bajar (en un hilo, para una pestana entera)."""
    por_id = _por_id(modelo)
    salida = {}
    for i in ids:
        ruta = miniatura(por_id[i]) if i in por_id else None
        if ruta:
            salida[i] = ruta
    return salida
