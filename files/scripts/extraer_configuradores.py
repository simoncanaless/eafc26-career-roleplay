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
from pathlib import Path

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
      grupo: g.title || '', hex: (it.color || [])[0] || '', precio: it.priceNumeric || 0,
      estandar: !!it.isStandardEquipment, seleccionada: !!it.isSelected});
  return JSON.stringify({codigo: c.catalog.orderType, modelo: c.catalog.modelName, anio: c.catalog.modelYear,
    moneda: c.market.currency, base: c.configuration.prices.main.base.raw, render: c.prs.optionIds || [],
    opciones: ops});
})()
"""


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


def main():
    from PySide6.QtWebEngineCore import QWebEnginePage

    app = QApplication(sys.argv[:1])  # noqa: F841
    pedidos = sys.argv[1:]
    modelos = [m for m in autos.MODELOS if "configurator.porsche.com" in m.url_configurador and "/model/" in m.url_configurador]
    anterior = configurador.catalogo()
    salida = dict(anterior)
    pagina = QWebEnginePage()
    for modelo in modelos:
        codigo = modelo.url_configurador.rstrip("/").rsplit("/", 1)[-1]
        if pedidos and codigo not in pedidos:
            continue
        datos = leer(pagina, f"https://configurator.porsche.com/{MERCADO}/mode/model/{codigo}")
        if not datos.get("opciones"):
            print(f"{modelo.nombre_completo} ({codigo}): sin datos")
            continue
        datos.update(marca="Porsche", pais="GB", modelo_app=modelo.id)
        salida[codigo] = datos
        print(f"{modelo.nombre_completo} ({codigo}): {len(datos['opciones'])} opciones, base {datos['base']} {datos['moneda']}")
        time.sleep(PAUSA_S)
    configurador.ruta_archivo().write_text(json.dumps({"_que_es": "Opciones reales de los configuradores "
        "oficiales (scripts/extraer_configuradores.py). Solo local: no va al repo ni al paquete.", "modelos": salida},
        ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"\n{len(salida)} modelos en {configurador.ruta_archivo()}")


if __name__ == "__main__":
    main()
