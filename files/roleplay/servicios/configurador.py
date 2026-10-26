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


def es_de_interior(camara: str) -> bool:
    """int-front-seats (Porsche), BS_Config_Int_1_LH (Aston Martin), beautyshot_int_trim (Ferrari)."""
    return "int" in camara.lower().replace("-", "_").split("_")


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
            cabeceras = CABECERAS if "porsche.com" in url else {}  # (Porsche: las de su pagina; el resto, ninguna)
            with urllib.request.urlopen(urllib.request.Request(url, headers=cabeceras), timeout=timeout) as respuesta:
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
    tiene esa imagen. Corre en un hilo. Ferrari solo de la cache: se pide por el navegador (`ui/puente_web.py`)."""
    if proveedor(modelo) == "ferrari":
        destino = ruta_ferrari(modelo, eleccion, camara, noche)
        return destino if destino.exists() else None
    if proveedor(modelo) == "bentley":
        return render_bentley(modelo, eleccion, camara)
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


# ---- Bentley (su API cc2 es publica y se recorre sola: cada pieza trae el enlace `add` a la configuracion que
# resulta; el servidor calcula la verificacion del camino `byPRs...`, aplica sus reglas y da las imagenes) ----

BENTLEY = "https://sdl.bentleymotors.com"
GIRO_BENTLEY = [["EXTERIOR_FRONT", False], ["EXTERIOR_3_4_FRONT", False], ["EXTERIOR_SIDE", False],
                ["EXTERIOR_3_4_REAR", False], ["EXTERIOR_REAR", False], ["EXTERIOR_3_4_REAR", True],
                ["EXTERIOR_SIDE", True], ["EXTERIOR_3_4_FRONT", True]]
VISTAS_BENTLEY = {"INTERIOR_DASHBOARD": "Tablero", "INTERIOR_SEATS": "Asientos",
                  "INTERIOR_REAR_SEATS_FACE_ON": "Atras", "INTERIOR_REAR_SEATS_SIDE_ON": "Atras de costado"}


def _json_bentley(camino: str) -> Optional[dict]:
    try:
        with urllib.request.urlopen(BENTLEY + camino, timeout=60) as respuesta:
            return json.loads(respuesta.read())
    except (OSError, ValueError):
        return None


def prs_de_camino(camino: str) -> list:
    """Los codigos de una configuracion de Bentley: van en base64 despues de byPRs + 8 de verificacion."""
    import base64

    codigo = camino.split("byPRs", 1)[1].split("?", 1)[0][8:]
    texto = base64.urlsafe_b64decode(codigo + "=" * (-len(codigo) % 4)).decode("utf-8", "replace")
    return [p for p in texto.split("-") if p]


def _con_parametro(camino: str, clave: str, valor: str) -> str:
    import urllib.parse

    return f"{camino}{'&' if '?' in camino else '?'}{clave}={urllib.parse.quote(valor)}"


def configuracion_bentley(modelo: dict, eleccion: Eleccion) -> Optional[dict]:
    """{vista: url de la imagen} de esa eleccion: desde la de fabrica, agrega (y saca) pieza por pieza con los
    enlaces de su API. Se guarda por eleccion: la misma combinacion no se vuelve a pedir."""
    clave = hashlib.sha1(json.dumps(sorted(eleccion.ids())).encode()).hexdigest()[:16]
    archivo = CARPETA_RENDERS / f"bentley_{modelo['codigo']}" / "configuraciones.json"
    try:
        guardadas = json.loads(archivo.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        guardadas = {}
    if clave in guardadas:
        return guardadas[clave]
    camino = modelo["camino_base"]
    datos = _json_bentley(camino)
    controladas = {o["id"] for o in modelo.get("opciones", []) if visible(o)}
    for op_id in sorted(set(eleccion.ids()) - set(prs_de_camino(camino))):
        nuevo = _json_bentley(_con_parametro(camino, "add", op_id))
        if nuevo is not None:
            camino, datos = nuevo["_links"]["self"]["href"], nuevo
    for op_id in sorted((set(prs_de_camino(camino)) & controladas) - set(eleccion.ids())):
        nuevo = _json_bentley(_con_parametro(camino, "remove", op_id))  # una casilla que se apago
        if nuevo is not None:
            camino, datos = nuevo["_links"]["self"]["href"], nuevo
    if datos is None:
        return None
    vistas = {}
    for grupo in ("cc2:exteriorView", "cc2:interiorView"):
        for vista in datos.get("_embedded", {}).get(grupo, []):
            mayor = max(vista.get("renditions") or [{}], key=lambda r: r.get("width", 0))
            if mayor.get("url"):
                vistas[vista["name"]] = mayor["url"]
    guardadas[clave] = vistas
    archivo.parent.mkdir(parents=True, exist_ok=True)
    archivo.write_text(json.dumps(guardadas), encoding="utf-8")
    return vistas


def render_bentley(modelo: dict, eleccion: Eleccion, camara: str) -> Optional[Path]:
    vistas = configuracion_bentley(modelo, eleccion)
    url = (vistas or {}).get(camara)
    if not url:
        return None
    destino = CARPETA_RENDERS / f"bentley_{modelo['codigo']}" / f"{hashlib.sha1(url.encode()).hexdigest()[:16]}.png"
    return _bajar(url, destino)


# ---- Ferrari (solo le contesta a su pagina: todo pasa por el navegador de la app, ui/puente_web.py) ----

FERRARI = "https://carconfigurator.ferrari.com"
API_FERRARI = "https://api.carconfigurator.ferrari.com"
PAGINA_FERRARI = f"{FERRARI}/en_EN/ferrari_car_configurator"
CUADROS_FERRARI = 18  # el giro de su pagina (los que tienen has2DTurntable)
VISTAS_FERRARI = {"beautyshot_ext_wheel": "Llanta", "beautyshot_ext_rooftop": "Desde arriba",
                  "beautyshot_int_frontseats": "Asientos", "beautyshot_int_steeringwheel": "Volante",
                  "beautyshot_int_frontside": "Cabina", "beautyshot_int_trim": "Detalles"}
# Ferrari no publica precios: estimados por categoria de su arbol (libras); las "especiales" x1,5
PRECIO_FERRARI = {"STANDARD": 0, "ADDITIONAL": 4500, "PAINTWORK": 12000, "LIVERY": 9000, "RIMS": 3500,
                  "CALIPERS": 1400, "CARBON": 4800, "LEATHER": 2500}


def _seccion_ferrari(ruta: list) -> Optional[str]:
    if ruta[0] == "exterior":
        if "paintwork" in ruta:
            return "section-exterior-color"
        if ruta[-1] in ("rims", "calipers"):
            return "section-wheels"
        return "section-individualization-exterior"
    if ruta[0] == "interior":
        if ruta[-1] == "main_area":
            return "section-interior-color"
        if ruta[-1] == "seattype":
            return "section-interior-seats"
        return "section-individualization-interior"
    if ruta[0] == "equipment":
        return "section-individualization-technology"
    return None


def _precio_ferrari(categoria: str, especial: bool) -> int:
    clave = next((c for c in PRECIO_FERRARI if c in categoria), "")
    precio = PRECIO_FERRARI.get(clave, 1500)
    return round(precio * (1.5 if especial else 1))


def normalizar_ferrari(arbol: list, info: dict, modelo_app: str, base: int) -> dict:
    """El catalogo de un Ferrari (su tree-00.json y su linea de models.json) con la forma de los demas."""
    opciones, vistos, camaras = [], set(), set()

    def recorrer(nodo: dict, ruta: list):
        camaras.update(c for c in nodo.get("cameraShot") or [] if c)
        seccion = _seccion_ferrari(ruta)
        for spec in nodo.get("optspec") or []:
            validas = [o for o in spec.get("options") or [] if o.get("selectable")]
            for op in validas:
                if op["id"] in vistos or seccion is None:
                    continue
                vistos.add(op["id"])
                nombre = " ".join(op["name"].split()).title()
                categoria = ("Pinzas" if ruta[-1] == "calipers" else "Llantas") if seccion == "section-wheels" else \
                    (spec.get("description") or ruta[-1]).capitalize()
                opciones.append({
                    "id": op["id"], "nombre": nombre, "seccion": seccion, "categoria": categoria,
                    "grupo": categoria, "grupo_id": spec["id"],
                    "hex": color_por_nombre(nombre) if seccion in ("section-exterior-color", "section-interior-color") else "",
                    "precio": _precio_ferrari(op.get("category") or spec.get("category") or "", bool(op.get("isSpecial"))),
                    "estandar": False, "seleccionada": False, "miniatura": "", "descripcion": "",
                    "exclusivo": len(validas) > 1, "valores": op.get("values") or [],
                })
        for hijo in nodo.get("subConfig") or []:
            recorrer(hijo, ruta + [hijo["id"]])

    for raiz in arbol:
        recorrer(raiz, [raiz["id"]])
    pinturas = [o for o in opciones if o["seccion"] == "section-exterior-color"]
    de_fabrica = next((o for o in pinturas if "Rosso Corsa" in o["nombre"]), pinturas[0] if pinturas else None)
    if de_fabrica is not None:  # sin opciones dibuja el auto base; el color de fabrica, el Rosso Corsa
        de_fabrica.update(seleccionada=True, estandar=True, precio=0)
    giro_18 = bool(info.get("has2DTurntable"))
    giro = [[f"turntable-{n}", False] for n in range(CUADROS_FERRARI)] if giro_18 else [
        ["beautyshot_ext_frontleft", False], ["beautyshot_ext_side", False], ["beautyshot_ext_backleft", False],
        ["beautyshot_ext_backleft", True], ["beautyshot_ext_side", True], ["beautyshot_ext_frontleft", True]]
    vistas = {c: n for c, n in VISTAS_FERRARI.items() if c in camaras}
    if giro_18:
        vistas = {"beautyshot_ext_frontleft": "Presentacion", **vistas}
    return {
        "proveedor": "ferrari", "marca": "Ferrari", "codigo": info["id"], "codigo_ferrari": info.get("code", ""),
        "modelo": info.get("name", ""), "anio": None, "moneda": "GBP", "base": base, "pais": "GB",
        "modelo_app": modelo_app, "precios_estimados": True, "opciones": opciones, "render": [],
        "giro": giro, "giro_inicial": 0, "vistas": vistas, "entornos_ui": {"Blackroom": "Estudio"},
        "camara_seccion": {"section-wheels": "beautyshot_ext_wheel", "section-interior-color": "beautyshot_int_frontseats",
                           "section-interior-seats": "beautyshot_int_frontseats"},
    }


def pedido_ferrari(modelo: dict, eleccion: Eleccion, camara: str, noche: bool) -> dict:
    """Lo que su pagina le manda a la API de imagenes (las opciones con su optionId/variantId)."""
    por_id = _por_id(modelo)
    opciones = [v for i in sorted(eleccion.ids()) if i in por_id for v in por_id[i].get("valores", [])]
    giro = camara.startswith("turntable-")
    return {"daytime": "Night" if noche else "Day", "options": opciones, "scenario": "Blackroom",
            "cameras": [] if giro else [camara], "frames": list(range(CUADROS_FERRARI)) if giro else []}


def ruta_ferrari(modelo: dict, eleccion: Eleccion, camara: str, noche: bool) -> Path:
    pedido = pedido_ferrari(modelo, eleccion, camara, noche)
    clave = hashlib.sha1(json.dumps([pedido["options"], pedido["daytime"], camara], sort_keys=True).encode()).hexdigest()[:16]
    return CARPETA_RENDERS / f"ferrari_{modelo['codigo']}" / f"{clave}.jpg"


def js_imagen_ferrari(modelo: dict, eleccion: Eleccion, camara: str, noche: bool) -> str:
    """El cuerpo (async) que corre en su pagina: pide la imagen como su configurador y la devuelve en base64."""
    pedido = pedido_ferrari(modelo, eleccion, camara, noche)
    cuadro = camara.split("-", 1)[1] if camara.startswith("turntable-") else ""
    return (
        f"const r = await fetch('{API_FERRARI}/vehicle/{modelo['codigo']}/default/images', {{method: 'POST', "
        f"headers: {{'content-type': 'application/json'}}, body: {json.dumps(json.dumps(pedido))}}}).then(x => x.json());"
        f"const url = {json.dumps(cuadro)} ? '{FERRARI}/' + r.prefix + r.trunk + '-Blackroom-{pedido['daytime']}-turntable-"
        f"{cuadro}.jpg' : (r.filenames || []).find(f => f.includes({json.dumps(camara)}));"
        "if (!url) return null;"
        "const imagen = await fetch(url);"
        "if (!imagen.ok || !(imagen.headers.get('content-type') || '').includes('image')) return null;"
        "const blob = await imagen.blob();"
        "return await new Promise(ok => { const f = new FileReader(); f.onload = () => ok(String(f.result).split(',')[1]); "
        "f.readAsDataURL(blob); });"
    )


def guardar_imagen_ferrari(modelo: dict, eleccion: Eleccion, camara: str, noche: bool, base64_jpg) -> Optional[Path]:
    import base64

    if not base64_jpg:
        return None
    destino = ruta_ferrari(modelo, eleccion, camara, noche)
    destino.parent.mkdir(parents=True, exist_ok=True)
    destino.write_bytes(base64.b64decode(base64_jpg))
    return destino


def miniaturas(modelo: dict, ids: list) -> dict:
    """{id: ruta} de las que se pudieron bajar (en un hilo, para una pestana entera)."""
    por_id = _por_id(modelo)
    salida = {}
    for i in ids:
        ruta = miniatura(por_id[i]) if i in por_id else None
        if ruta:
            salida[i] = ruta
    return salida
