"""
Lee las opciones reales de los configuradores oficiales y las guarda en
roleplay/datos/configuradores_oficiales.json (SOLO para tu PC: va en .gitignore y no va en el paquete).

    .venv\\Scripts\\python.exe scripts\\extraer_configuradores.py [codigo ...]

Abre cada modelo del concesionario con el mismo motor del navegador de la app (QtWebEngine), sin
ventana, y lee los datos que la pagina ya trae (window.__reactRouterDataRouter: el catalogo de
opciones con nombre, hex, precio y categoria, el precio base y los ids que usa el render). Un
modelo a la vez y con pausa: no es una carga para la web. Hoy: Porsche, mercado UK (precios en libras).
"""

import json
import sys
import time
import urllib.request
from pathlib import Path
from typing import Optional

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

from PySide6.QtCore import QEventLoop, QTimer, QUrl  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from roleplay.servicios import autos, configurador  # noqa: E402

MERCADO = "en-GB"
PAUSA_S = 3
SCRIPT = r"""
(() => {
  const c = window.__reactRouterDataRouter?.state?.loaderData?.['customer-configurator'];
  if (!c || !c.views || !c.views.optionsList) return '';
  const ops = [];
  for (const sec of c.views.optionsList) for (const ca of (sec.categories || [])) for (const g of (ca.groups || []))
    for (const it of (g.items || [])) ops.push({id: it.id, nombre: it.title, seccion: sec.id, categoria: ca.title,
      grupo: g.title || '', grupo_id: it.groupId || '', hex: (it.color || [])[0] || '', precio: it.priceNumeric || 0,
      estandar: !!it.isStandardEquipment, seleccionada: !!it.isSelected, miniatura: it.thumbnail || '',
      descripcion: it.description || ''});
  return JSON.stringify({codigo: c.catalog.orderType, modelo: c.catalog.modelName, anio: c.catalog.modelYear,
    moneda: c.market.currency, base: c.configuration.prices.main.base.raw, render: c.prs.optionIds || [],
    opciones: ops, vistas_seccion: Object.fromEntries(c.views.optionsList.map(s => [s.id, s.visualizationViews || []])),
    escenario: ((c.mainStage || {}).stage || []).map(s => ({vista: s.view, url: s.url})),
    entornos: ((c.prs || {}).environments || []).map(e => e.id)});
})()
"""


def camaras(escenario: list) -> dict:
    """{vista de la pagina: id de camara del render}, sacado de las imagenes del escenario (el pedido va en lz-string)."""
    import lzstring

    salida = {}
    for imagen in escenario:
        try:
            comprimido = imagen["url"].split("/1/", 1)[1].split("?", 1)[0]
            pedido = json.loads(lzstring.LZString().decompressFromEncodedURIComponent(comprimido))
            salida[imagen["vista"]] = pedido["config"]["camera"]["id"]
        except (IndexError, KeyError, TypeError, ValueError):
            continue
    return salida


def leer(pagina, url: str) -> dict:
    lazo = QEventLoop()
    pagina.loadFinished.connect(lazo.quit)
    pagina.load(QUrl(url))
    QTimer.singleShot(45000, lazo.quit)
    lazo.exec()
    pagina.loadFinished.disconnect(lazo.quit)
    for _ in range(20):  # los datos llegan despues de la carga (streaming): se espera hasta que esten
        resultado = {}
        lazo = QEventLoop()
        pagina.runJavaScript(SCRIPT, 0, lambda r: (resultado.update(texto=r), lazo.quit()))
        QTimer.singleShot(5000, lazo.quit)
        lazo.exec()
        if resultado.get("texto"):
            return json.loads(resultado["texto"])
        espera = QEventLoop()
        QTimer.singleShot(1000, espera.quit)
        espera.exec()
    return {}


# ---- Aston Martin: todo con pedidos simples (sus datos y sus imagenes responden a cualquiera) ----

ASTON = "https://configurator.astonmartin.com"
# los del concesionario -> el codigo de cada version en su configurador (models/products/CL + sus traducciones)
CODIGOS_ASTON = {
    "aston_vantage": "AM617", "aston_vantage_roadster": "AM647", "aston_vantage_s": "AM662",
    "aston_vantage_s_roadster": "AM682", "aston_db12": "AM576A", "aston_db12_volante": "AM546A",
    "aston_db12_s": "AM578", "aston_db12_s_volante": "AM548", "aston_dbx_gt": "AM810", "aston_dbx_s": "AM842",
    "aston_dbx707": "AM890", "aston_vanquish": "AM374", "aston_vanquish_volante": "AM384",
    "aston_valhalla": "AM003A", "aston_valen": "AM390",
}
GIRO_ASTON = [["BS_Config_Ext_1", False], ["BS_Config_Ext_2", False], ["BS_Config_Ext_3", False],
              ["BS_Config_Ext_8", False], ["BS_Config_Ext_7", False], ["BS_Config_Ext_3", True], ["BS_Config_Ext_2", True]]
VISTAS_ASTON = {"BS_Config_Ext_5": "Llanta", "BS_Config_Ext_Top": "Desde arriba", "BS_Config_Int_1_LH": "Interior 1",
                "BS_Config_Int_2_LH": "Interior 2", "BS_Config_Int_3_LH": "Interior 3", "BS_Config_Int_4_LH": "Interior 4"}
ENTORNOS_ASTON = {"Black_Studio": "Estudio negro", "ShowroomGaydon": "Gaydon", "env_New_York_Lumen": "Nueva York",
                  "env_Amalfi_CoastalRoad_Lumen": "Costa de Amalfi", "Silverstone": "Silverstone"}
# Aston Martin no publica precios de opcionales: estimados por coleccion (libras), "Q by Aston Martin" x2,5
PRECIO_ASTON = {"PAINT": 2400, "WHEELS": 2800, "BRAKE_CALIPERS": 950, "BRAKE_DISC": 9000, "LIVERIES": 3500,
                "GRAPHICS_COLOR": 600, "LOWER_BODY_PACKAGE": 7500, "UPPER_BODY_PACKAGE": 6500, "ROOF": 4000,
                "PROTECTIVE_FILM": 4500, "ENVIRONMENTS": 3000, "SEATING": 3500, "STEERING_WHEEL": 1500,
                "CARBON_FIBRE_INTERIOR_PACKAGE": 5500, "DIFFUSER": 3500, "EXHAUST_SYSTEM": 3000, "AUDIO": 2500}


def _json(url: str):
    with urllib.request.urlopen(url, timeout=60) as respuesta:
        return json.loads(respuesta.read())


def _seccion_aston(ruta: list) -> Optional[str]:
    """De que pestana es cada coleccion del arbol de Aston Martin (None: no se elige, queda de fabrica)."""
    grupo, nombre = ruta[0], ruta[-1]
    if grupo == "EXTERIOR":
        if "PAINT" in ruta:
            return "section-exterior-color"
        if nombre == "WHEELS" or "BRAKES" in ruta:
            return "section-wheels"
        return "section-individualization-exterior"
    if grupo == "INTERIOR":
        return {"ENVIRONMENTS": "section-interior-color", "SEATING": "section-interior-seats"}.get(
            nombre, "section-individualization-interior")
    if grupo == "INTERIOR_OPTIONS":
        return "section-individualization-interior"
    if grupo == "PERSONALISATION":
        return {"PACKAGES": "section-individualization-packages", "EXTERIOR": "section-individualization-exterior"}.get(
            ruta[1] if len(ruta) > 1 else "", "section-individualization-technology")
    return None  # SL, HIDDEN_OPTIONS


def _precio_aston(coleccion: str, codigo: dict, de_fabrica: bool) -> int:
    if de_fabrica:
        return 0
    meta = codigo.get("meta") or {}
    if coleccion in ("PAINT",) or meta.get("family", "").startswith("COL"):
        categoria = (meta.get("colorCategory") or "").lower()
        precio = 0 if categoria == "solid" else 6500 if codigo["name"].lower().startswith("satin") else 2400
    else:
        precio = PRECIO_ASTON.get(coleccion, 800)
    return round(precio * (2.5 if meta.get("qOption") else 1))


def _bonito(nombre: str) -> str:
    return nombre.replace("_", " ").capitalize()


def extraer_aston(pedidos: list) -> dict:
    import lzstring

    salida = {}
    vacio = lzstring.LZString().compressToEncodedURIComponent("[]")
    for modelo_id, codigo in CODIGOS_ASTON.items():
        modelo = autos.POR_ID.get(modelo_id)
        if modelo is None or (pedidos and codigo not in pedidos):
            continue
        reglas = _json(f"{ASTON}/rules/configuration/{codigo}?options={vacio}&country=GB")
        detalles = _json(f"{ASTON}/models/products/{codigo}/details")
        de_fabrica = {o if isinstance(o, str) else f"{next(iter(o))}:{next(iter(o.values()))[next(iter(o))]}"
                      for o in reglas.get("options", [])}
        opciones, vistos = [], set()

        def recorrer(nodo, ruta, lista=None):
            for hijo in nodo.get("content", []):
                if hijo["type"] in ("Code",) and hijo.get("active", True):
                    op_id = f"{lista}:{hijo['code']}" if lista else hijo["code"]
                    seccion = _seccion_aston(ruta)
                    if op_id in vistos or seccion is None:
                        continue
                    vistos.add(op_id)
                    coleccion = lista or ruta[-1]
                    elegida = op_id in de_fabrica
                    pintura = seccion in ("section-exterior-color", "section-interior-color") or lista
                    opciones.append({
                        "id": op_id, "nombre": hijo["name"], "seccion": seccion,
                        "categoria": f"Cuero ({lista})" if lista else _bonito(ruta[-1]),
                        "grupo": _bonito(coleccion), "grupo_id": "/".join(ruta + ([lista] if lista else [])),
                        "hex": configurador.color_por_nombre(hijo["name"]) if pintura else "",
                        "precio": _precio_aston("PAINT" if seccion == "section-exterior-color" else coleccion, hijo, elegida),
                        "estandar": elegida, "seleccionada": elegida, "miniatura": "", "descripcion": "",
                        "exclusivo": bool(lista) or bool(nodo.get("mandatory")) and seccion != "section-exterior-color",
                    })
                elif hijo["type"] == "List":
                    recorrer(hijo, ruta + [hijo["name"]], hijo["name"])
                elif hijo["type"] == "NestedCode":
                    recorrer(hijo, ruta, lista)
                elif hijo["type"] in ("Group", "Collection"):
                    recorrer(hijo, ruta + [hijo["name"]], lista)

        for grupo in reglas.get("config", []):
            recorrer(grupo, [grupo["name"]])
        camaras = {c["id"] for c in detalles.get("cameras", {}).get("cameras", [])}
        entornos = {e["id"] for e in detalles.get("environments", [])}
        salida[codigo] = {
            "proveedor": "aston", "marca": "Aston Martin", "codigo": codigo, "modelo": modelo.nombre, "anio": None,
            "moneda": "GBP", "base": modelo.precio, "pais": "GB", "modelo_app": modelo.id, "precios_estimados": True,
            "opciones": opciones, "render": sorted(de_fabrica),
            "giro": [c for c in GIRO_ASTON if c[0] in camaras],
            "vistas": {c: n for c, n in VISTAS_ASTON.items() if c in camaras},
            "entornos_ui": {e: n for e, n in ENTORNOS_ASTON.items() if e in entornos},
            "camara_seccion": {"section-exterior-color": "BS_Config_Ext_2", "section-wheels": "BS_Config_Ext_5",
                               "section-interior-color": "BS_Config_Int_1_LH", "section-interior-seats": "BS_Config_Int_1_LH"},
        }
        print(f"{modelo.nombre_completo} ({codigo}): {len(opciones)} opciones")
        time.sleep(PAUSA_S)
    return salida


# ---- Bentley: su API cc2 (publica, se recorre sola por sus enlaces) ----

MODELOS_BENTLEY = {
    "bentley_gt": "continental_gt/continental_gt_v8_hybrid_2027",
    "bentley_gtc": "continental_gtc/continental_gtc_v8_hybrid_2027",
    "bentley_supersports": "supersports/supersports",
    "bentley_flying_spur": "Flying_Spur/new_flying_spur_v8_hybrid_2027",
    "bentley_bentayga": "bentayga/bentayga_v8_2027",
    "bentley_bentayga_ewb": "bentayga_ewb/bentayga_ewb_v8_2027",
    "bentley_torcal": "torcal/torcal",
}
# Bentley no publica precios ("priceEnabled": false): estimados por seccion (libras); "by Mulliner" x2,5
PRECIO_BENTLEY = {"Paints": 3900, "Wheels": 4500, "Hide": 1200, "Veneers": 1800, "Interior Details": 900,
                  "Specifications": 9000, "Vehicle Dynamics": 14000, "Exterior": 2500}
SECCIONES_BENTLEY = {"Paints": "section-exterior-color", "Wheels": "section-wheels", "Hide": "section-interior-color",
                     "Veneers": "section-individualization-interior", "Interior Details": "section-individualization-interior",
                     "Specifications": "section-individualization-packages", "Exterior": "section-individualization-exterior",
                     "Vehicle Dynamics": "section-wheels"}


def _bentley_seccion(seccion: str, sub: str) -> Optional[str]:
    if seccion == "Hide" and sub != "Main Hide":
        return "section-individualization-interior"  # el color principal va en Interior; el resto, a elegir
    if seccion == "Wheels" and sub != "Wheels":
        return "section-individualization-exterior"
    if seccion.strip() == "Optional Equipment":
        return SECCIONES_BENTLEY.get(sub.strip(), "section-individualization-technology")
    return SECCIONES_BENTLEY.get(seccion.strip())


def extraer_bentley(pedidos: list) -> dict:
    marca = _json(f"{configurador.BENTLEY}/bentley/api/cc2/brandmaster?language=en&role=public&debugMode=false")
    params = f"language=en&role=public&dataVersion={marca['dataVersion']}&country={marca['country']}"
    salida = {}
    for modelo_id, camino_modelo in MODELOS_BENTLEY.items():
        modelo = autos.POR_ID.get(modelo_id)
        if modelo is None or (pedidos and modelo_id not in pedidos):
            continue
        rasgos = _json(f"{configurador.BENTLEY}/bentley/api/cc2/brandmaster/features/{camino_modelo}?{params}")
        sugerencias = _json(f"{configurador.BENTLEY}/bentley/api/cc2/brandmaster/{camino_modelo}/suggestions?{params}")
        camino_base = sugerencias["_embedded"]["item"][0]["_links"]["cc2:configuration"][0]["href"]
        de_fabrica = set(configurador.prs_de_camino(camino_base))
        opciones, vistas_seccion = [], {}
        for seccion in rasgos.get("_embedded", {}).get("section", []):
            preferida = (seccion.get("metadata") or {}).get("cc2:preferredView")
            for sub in [seccion] + seccion.get("_embedded", {}).get("section", []):
                destino = _bentley_seccion(seccion["title"], sub["title"])
                if destino is None:
                    continue
                if preferida and destino not in vistas_seccion:
                    vistas_seccion[destino] = preferida
                items = [i for i in sub.get("_embedded", {}).get("item", []) if not (i.get("flags") or {}).get("hidden")]
                for item in items:
                    elegida = item["key"] in de_fabrica
                    # sus fotos estan en www.bentleymotors.com, que a un pedido que no es de su pagina le da 403:
                    # no se piden (las fichas quedan con el nombre, como Aston Martin); los renders si responden
                    foto = ""
                    mulliner = "mulliner" in item["title"].lower()
                    precio = 0 if elegida else round(PRECIO_BENTLEY.get(sub["title"].strip(), PRECIO_BENTLEY.get(
                        seccion["title"].strip(), 1200)) * (2.5 if mulliner else 1))
                    opciones.append({
                        "id": item["key"], "nombre": item["title"].strip(), "seccion": destino,
                        "categoria": sub["title"].strip(), "grupo": sub["title"].strip(), "grupo_id": sub.get("key", sub["title"]),
                        "hex": configurador.color_por_nombre(item["title"]) if destino == "section-exterior-color" else "",
                        "precio": precio, "estandar": elegida, "seleccionada": elegida, "miniatura": foto,
                        "descripcion": "",
                        "exclusivo": destino not in ("section-individualization-packages",
                                                     "section-individualization-technology") and len(items) > 1,
                    })
        salida[f"bentley_{modelo_id}"] = {
            "proveedor": "bentley", "marca": "Bentley", "codigo": modelo_id, "modelo": modelo.nombre, "anio": None,
            "moneda": "GBP", "base": modelo.precio, "pais": "GB", "modelo_app": modelo.id, "precios_estimados": True,
            "sin_noche": True, "camino_base": camino_base, "opciones": opciones, "render": [],
            "giro": configurador.GIRO_BENTLEY, "giro_inicial": 1, "vistas": configurador.VISTAS_BENTLEY,
            "entornos_ui": {"estudio": "Estudio"}, "camara_seccion": vistas_seccion,
        }
        print(f"{modelo.nombre_completo} ({camino_modelo}): {len(opciones)} opciones")
        time.sleep(PAUSA_S)
    return salida


# ---- Ferrari: solo le contesta a su pagina -> desde su pagina, en el navegador de la app (ui/puente_web.py) ----


def _desde_la_pagina(puente_, cuerpo: str):
    from PySide6.QtCore import QEventLoop

    resultado, lazo = {}, QEventLoop()
    puente_.ejecutar(cuerpo, lambda valor: (resultado.update(valor=valor), lazo.quit()))
    lazo.exec()
    return resultado.get("valor")


def extraer_ferrari(pedidos: list) -> dict:
    from roleplay.ui.puente_web import PuenteWeb

    app = QApplication.instance() or QApplication(sys.argv[:1])  # noqa: F841
    puente_ = PuenteWeb(configurador.PAGINA_FERRARI)
    modelos = json.loads(_desde_la_pagina(puente_, "return JSON.stringify(await fetch('/rt-assets/data/models.json')"
                                                   ".then(r => r.json()));") or "[]")
    por_id = {m["id"]: m for m in modelos}
    salida = {}
    for modelo in autos.MODELOS:
        if modelo.marca != "Ferrari":
            continue
        ferrari_id = modelo.url_configurador.split("ferrari_car_configurator/", 1)[-1].split("/")[0]
        if ferrari_id not in por_id or (pedidos and ferrari_id not in pedidos):
            print(f"{modelo.nombre_completo}: no esta en su configurador ({ferrari_id})")
            continue
        arbol = json.loads(_desde_la_pagina(puente_, f"return JSON.stringify(await fetch('/cars/{ferrari_id}/tree-00.json')"
                                                     ".then(r => r.json()));") or "[]")
        if not arbol:
            print(f"{modelo.nombre_completo} ({ferrari_id}): sin datos")
            continue
        datos = configurador.normalizar_ferrari(arbol, por_id[ferrari_id], modelo.id, modelo.precio)
        salida[f"ferrari_{ferrari_id}"] = datos
        print(f"{modelo.nombre_completo} ({ferrari_id}): {len(datos['opciones'])} opciones, "
              f"{'giro de 18 cuadros' if len(datos['giro']) == configurador.CUADROS_FERRARI else '6 vistas'}")
        time.sleep(PAUSA_S)
    return salida


def main():
    pedidos = [a for a in sys.argv[1:] if not a.startswith("--")]
    marca = next((a[8:] for a in sys.argv[1:] if a.startswith("--marca=")), "porsche")
    salida = dict(configurador.catalogo())
    if marca == "aston":
        salida.update(extraer_aston(pedidos))
    elif marca == "ferrari":
        salida.update(extraer_ferrari(pedidos))
    elif marca == "bentley":
        salida.update(extraer_bentley(pedidos))
    else:
        salida.update(extraer_porsche(pedidos))
    configurador.ruta_archivo().write_text(json.dumps({"_que_es": "Opciones reales de los configuradores "
        "oficiales (scripts/extraer_configuradores.py). Solo local: no va al repo ni al paquete.", "modelos": salida},
        ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"\n{len(salida)} modelos en {configurador.ruta_archivo()}")


def extraer_porsche(pedidos: list) -> dict:
    from PySide6.QtWebEngineCore import QWebEnginePage

    app = QApplication(sys.argv[:1])  # noqa: F841
    modelos = [m for m in autos.MODELOS if "configurator.porsche.com" in m.url_configurador and "/model/" in m.url_configurador]
    salida = {}
    pagina = QWebEnginePage()
    for modelo in modelos:
        codigo = modelo.url_configurador.rstrip("/").rsplit("/", 1)[-1]
        if pedidos and codigo not in pedidos:
            continue
        datos = leer(pagina, f"https://configurator.porsche.com/{MERCADO}/mode/model/{codigo}")
        if not datos.get("opciones"):
            print(f"{modelo.nombre_completo} ({codigo}): sin datos")
            continue
        datos["camaras"] = camaras(datos.pop("escenario", []))
        datos.update(marca="Porsche", pais="GB", modelo_app=modelo.id)
        salida[codigo] = datos
        print(f"{modelo.nombre_completo} ({codigo}): {len(datos['opciones'])} opciones, base {datos['base']} {datos['moneda']}")
        time.sleep(PAUSA_S)
    return salida


if __name__ == "__main__":
    main()
