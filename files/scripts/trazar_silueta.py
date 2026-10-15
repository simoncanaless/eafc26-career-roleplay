"""
Arma la silueta de un auto (para ui/configurador.py:SILUETAS) a partir de
una foto de perfil real de Wikimedia Commons. La guia completa, con las
herramientas del navegador, esta en docs/siluetas.md.

Dos formas de medir:

- Automatica (auto de color fuerte sobre un fondo distinto): medirAuto, en
  el navegador, separa el auto por su color columna por columna. Este script
  ajusta un circulo a cada arco de rueda, escala a la caja del dibujo
  (400 x 170, el auto entre x 17 y 383, apoyado en y 143) y simplifica el
  contorno (Ramer-Douglas-Peucker).
      python scripts/trazar_silueta.py medidas.json [--cola 22] [--nombre huracan]
- A mano (--puntos; un auto negro, plateado, o un fondo con ruido): los
  puntos del contorno, las ruedas, la ventana, los faros... marcados sobre
  la foto con la rejilla del navegador (docs/siluetas/*.json son los de los
  autos que ya estan). Endereza la perspectiva si la foto no es de perfil
  puro, y achica la escala si el auto es mas alto que el dibujo.
      python scripts/trazar_silueta.py docs/siluetas/g63.json --puntos \
          --insertar amg_g63 --fuente "Mercedes-AMG G 63, Commons: ..."
  Con --insertar la pega en SILUETAS y se la asigna a esos modelos; sin el,
  la imprime.
"""

import argparse
import json
import math
import re
import statistics
import sys
from pathlib import Path

X0, X1, SUELO = 17.0, 383.0, 143.0
TECHO_MINIMO = 6.0  # y mas alta que puede tener el techo dentro del dibujo (170 de alto)


def rdp(puntos, epsilon):
    """Ramer-Douglas-Peucker: los puntos que hacen falta para la forma."""
    if len(puntos) < 3:
        return puntos
    (x0, y0), (x1, y1) = puntos[0], puntos[-1]
    largo = math.hypot(x1 - x0, y1 - y0) or 1e-9
    peor, indice = 0.0, 0
    for i, (x, y) in enumerate(puntos[1:-1], start=1):
        distancia = abs((y1 - y0) * x - (x1 - x0) * y + x1 * y0 - y1 * x0) / largo
        if distancia > peor:
            peor, indice = distancia, i
    if peor <= epsilon:
        return [puntos[0], puntos[-1]]
    return rdp(puntos[: indice + 1], epsilon)[:-1] + rdp(puntos[indice:], epsilon)


def curva(puntos, tension: float = 0.5) -> str:
    """Una polilinea convertida en curva suave (Catmull-Rom -> Bezier cubicas)
    que pasa por todos los puntos: sin el aspecto facetado."""
    if len(puntos) < 3:
        return " ".join(f"L {x} {y}" for x, y in puntos[1:])
    partes = []
    p = [puntos[0]] + list(puntos) + [puntos[-1]]
    for i in range(1, len(p) - 2):
        (x0, y0), (x1, y1), (x2, y2), (x3, y3) = p[i - 1], p[i], p[i + 1], p[i + 2]
        c1 = (x1 + (x2 - x0) * tension / 3, y1 + (y2 - y0) * tension / 3)
        c2 = (x2 - (x3 - x1) * tension / 3, y2 - (y3 - y1) * tension / 3)
        partes.append(f"C {c1[0]:.1f} {c1[1]:.1f} {c2[0]:.1f} {c2[1]:.1f} {x2} {y2}")
    return " ".join(partes)


def armar_cuerpo(techo, cola, ruedas, piso, frente=None) -> str:
    """El contorno: `techo` (de la trompa a la cola, en coordenadas del
    dibujo) en curva suave, la cola hacia abajo, los arcos de rueda
    (`ruedas`: (x, y, radio del arco)) sobre el zocalo `piso`, y vuelta."""
    partes = [f"M {techo[0][0]} {techo[0][1]}", curva(techo)]
    partes += [f"L {x} {y}" for x, y in cola]
    for cx, cy, arco in sorted(ruedas, reverse=True):
        dy = piso - cy
        dx = round(math.sqrt(max(arco * arco - dy * dy, 0.0)), 1)
        partes.append(f"L {round(cx + dx, 1)} {piso} A {arco} {arco} 0 {1 if dy > 0 else 0} 0 {round(cx - dx, 1)} {piso}")
    partes += [f"L {x} {y}" for x, y in (frente or [(techo[0][0], piso)])]
    partes.append("Z")  # cierra en la trompa
    return " ".join(partes)


def circulo(puntos):
    """El circulo que mejor pasa por los puntos (minimos cuadrados, metodo de Kasa)."""
    n = len(puntos)
    sx = sum(x for x, _ in puntos); sy = sum(y for _, y in puntos)
    sxx = sum(x * x for x, _ in puntos); syy = sum(y * y for _, y in puntos); sxy = sum(x * y for x, y in puntos)
    sxz = sum(x * (x * x + y * y) for x, y in puntos); syz = sum(y * (x * x + y * y) for x, y in puntos)
    sz = sum(x * x + y * y for x, y in puntos)
    # [sxx sxy sx][a]   [sxz]
    # [sxy syy sy][b] = [syz]   con x^2 + y^2 = a x + b y + c
    # [sx  sy  n ][c]   [sz ]
    m = [[sxx, sxy, sx, sxz], [sxy, syy, sy, syz], [sx, sy, n, sz]]
    for i in range(3):  # Gauss
        p = max(range(i, 3), key=lambda f: abs(m[f][i]))
        m[i], m[p] = m[p], m[i]
        for f in range(3):
            if f != i:
                k = m[f][i] / m[i][i]
                m[f] = [a - k * b for a, b in zip(m[f], m[i])]
    a, b, c = (m[i][3] / m[i][i] for i in range(3))
    cx, cy = a / 2, b / 2
    return cx, cy, math.sqrt(c + cx * cx + cy * cy)


def suavizar(valores, ancho=5):
    """Mediana movil y despues promedio de 3: saca el ruido de 1 px sin
    redondear las esquinas de verdad."""
    medio = ancho // 2
    medianas = [statistics.median(valores[max(0, i - medio): i + medio + 1]) for i in range(len(valores))]
    return [statistics.mean(medianas[max(0, i - 1): i + 2]) for i in range(len(medianas))]


def tramos(columnas, condicion):
    """Grupos de columnas seguidas que cumplen la condicion."""
    grupos, actual = [], []
    for col in columnas:
        if condicion(col):
            actual.append(col)
        elif actual:
            grupos.append(actual)
            actual = []
    if actual:
        grupos.append(actual)
    return grupos


def trazar(medidas: dict, cola: float = 0.0, epsilon: float = 0.9) -> dict:
    cols = [c for c in medidas["cols"] if c[2] - c[1] > 12]
    # la carroceria: el tramo mas largo de columnas seguidas (sin saltos de mas de 6 px)
    corridas, actual = [], [cols[0]]
    for a, b in zip(cols, cols[1:]):
        if b[0] - a[0] <= 6 and abs(b[1] - a[1]) < 25:
            actual.append(b)
        else:
            corridas.append(actual)
            actual = [b]
    corridas.append(actual)
    cols = max(corridas, key=len)

    piso = statistics.median(c[2] for c in cols)  # el zocalo entre las ruedas
    arcos = [g for g in tramos(cols, lambda c: c[2] < piso - 8) if len(g) >= 8]
    if len(arcos) < 2:
        raise SystemExit(f"No encontre dos arcos de rueda ({len(arcos)}): revisa la franja o el color")
    arcos = sorted(arcos, key=len)[-2:]
    arcos.sort(key=lambda g: g[0][0])
    ruedas = []
    for g in arcos:
        cx, cy, radio = circulo([(c[0], c[2]) for c in g])
        ruedas.append((cx, cy, radio))
    radio_rueda = statistics.mean(r for _, _, r in ruedas) * 0.88
    suelo_foto = statistics.mean(cy for _, cy, _ in ruedas) + radio_rueda

    x_ini, x_fin = cols[0][0], cols[-1][0] + cola
    escala = (X1 - X0) / (x_fin - x_ini)
    X = lambda x: round(X0 + (x - x_ini) * escala, 1)  # noqa: E731
    Y = lambda y: round(SUELO - (suelo_foto - y) * escala, 1)  # noqa: E731

    arriba_suave = suavizar([c[1] for c in cols])
    techo = rdp([(X(c[0]), Y(y)) for c, y in zip(cols, arriba_suave)], epsilon)
    frente_abajo = [(X(c[0]), Y(c[2])) for c in cols if c[0] < arcos[0][0][0]]
    atras_abajo = [(X(c[0]), Y(c[2])) for c in cols if c[0] > arcos[1][-1][0]]
    y_piso = Y(piso)

    partes = [f"M {frente_abajo[0][0]} {frente_abajo[0][1]}"]
    partes += [f"L {x} {y}" for x, y in techo]
    if cola:  # la cola que no se pinto (luces, paragolpes): baja recta hasta el piso
        ultimo = atras_abajo[-1] if atras_abajo else (techo[-1][0], y_piso)
        partes += [f"L {X1} {techo[-1][1] + 3}", f"L {X1} {ultimo[1] - 4}", f"L {ultimo[0]} {ultimo[1]}"]
    for x, y in reversed(rdp(atras_abajo, epsilon) if len(atras_abajo) > 1 else atras_abajo):
        partes.append(f"L {x} {y}")
    for cx, cy, radio in reversed(ruedas):
        cx_, cy_, r_ = X(cx), Y(cy), round(radio * escala, 1)
        dy = y_piso - cy_
        dx = round(math.sqrt(max(r_ * r_ - dy * dy, 0.0)), 1)
        grande = 1 if dy > 0 else 0
        partes.append(f"L {round(cx_ + dx, 1)} {y_piso} A {r_} {r_} 0 {grande} 0 {round(cx_ - dx, 1)} {y_piso}")
    for x, y in reversed(rdp(frente_abajo, epsilon)):
        partes.append(f"L {x} {y}")
    partes.append("Z")

    # la ventana: el tramo no pintado de arriba, solo donde la columna llega
    # cerca del techo (si no, los faros o las tomas de aire parecen ventana)
    altura = piso - min(c[1] for c in cols)
    alto_del_techo = min(c[1] for c in cols) + 0.4 * altura
    candidatas = tramos(cols, lambda c: c[3] > 0 and c[4] > 4 and c[1] < alto_del_techo)
    vent = max(candidatas, key=len) if candidatas else []
    ventana = ""
    if len(vent) > 6:
        # arriba: el techo menos el marco (un margen constante: el espejo no lo mueve)
        marco = statistics.median(c[3] - c[1] for c in vent)
        techo_de = dict(zip((c[0] for c in cols), arriba_suave))
        arriba = rdp([(X(c[0]), Y(techo_de[c[0]] + marco)) for c in vent], epsilon)
        # abajo: la linea de cintura, una recta ajustada sin los puntos que tapa el espejo
        pares = [(c[0], c[3] + c[4]) for c in vent]
        for _ in range(3):
            n = len(pares)
            mx = sum(x for x, _ in pares) / n; my = sum(y for _, y in pares) / n
            pend = sum((x - mx) * (y - my) for x, y in pares) / (sum((x - mx) ** 2 for x, _ in pares) or 1)
            desvio = [abs(y - (my + pend * (x - mx))) for x, y in pares]
            limite = 2.5 * (statistics.median(desvio) or 1)
            pares = [p for p, dv in zip(pares, desvio) if dv <= limite] or pares
        x_a, x_b = vent[0][0], vent[-1][0]
        cintura = lambda x: my + pend * (x - mx)  # noqa: E731
        abajo = [(X(x_a), Y(cintura(x_a))), (X(x_b), Y(cintura(x_b)))]
        puntos = arriba + list(reversed(abajo))
        ventana = "M " + " L ".join(f"{x} {y}" for x, y in puntos) + " Z"
        base_ventana = round(statistics.median(y for _, y in abajo), 1)
    else:
        base_ventana = round((min(y for _, y in techo) + y_piso) / 2, 1)

    return {
        "conversion": {"x_ini": x_ini, "escala": round(escala, 5), "suelo_foto": round(suelo_foto, 1)},
        "cuerpo": " ".join(partes),
        "ventana": ventana,
        "ruedas": tuple((X(cx), round(SUELO - radio_rueda * escala, 1), round(radio_rueda * escala, 1)) for cx, _, _ in ruedas),
        "techo": min(y for _, y in techo),
        "base_ventana": base_ventana,
        "piso": y_piso,
    }


def como_codigo(nombre: str, s: dict) -> str:
    cuerpo = s["cuerpo"]
    lineas = [cuerpo[i:i + 100] for i in range(0, len(cuerpo), 100)]
    texto = "\n".join(f'        "{t}"' for t in lineas)
    conv = s["conversion"]
    return (
        f"    # foto -> dibujo: x = 17 + (x_foto - {conv['x_ini']}) * {conv['escala']}; "
        f"y = 143 - ({conv['suelo_foto']} - y_foto) * {conv['escala']}\n"
        f'    "{nombre}": Silueta(\n{texto},\n        "{s["ventana"]}",\n'
        f'        {s["ruedas"]}, {s["techo"]}, {s["base_ventana"]}, piso={s["piso"]},\n    ),'
    )


def resolver(matriz, vector):
    """Sistema lineal por Gauss con pivoteo (8 x 8 para la homografia)."""
    n = len(vector)
    m = [list(fila) + [v] for fila, v in zip(matriz, vector)]
    for i in range(n):
        p = max(range(i, n), key=lambda f: abs(m[f][i]))
        m[i], m[p] = m[p], m[i]
        for f in range(n):
            if f != i and m[i][i]:
                k = m[f][i] / m[i][i]
                m[f] = [a - k * b for a, b in zip(m[f], m[i])]
    return [m[i][n] / m[i][i] for i in range(n)]


def homografia(origen, destino):
    """La transformacion de perspectiva que lleva 4 puntos a otros 4."""
    filas, valores = [], []
    for (x, y), (u, v) in zip(origen, destino):
        filas.append([x, y, 1, 0, 0, 0, -u * x, -u * y]); valores.append(u)
        filas.append([0, 0, 0, x, y, 1, -v * x, -v * y]); valores.append(v)
    h = resolver(filas, valores) + [1.0]

    def aplicar(x, y):
        w = h[6] * x + h[7] * y + h[8]
        return ((h[0] * x + h[1] * y + h[2]) / w, (h[3] * x + h[4] * y + h[5]) / w)
    return aplicar


def rectificar(spec: dict) -> dict:
    """Endereza una foto casi de perfil. Las dos ruedas son, en la realidad,
    circulos iguales a la misma altura, separados por la distancia entre
    ejes (`ejes_sobre_radio`: distancia entre ejes / radio de la rueda, de
    la ficha tecnica). Con el centro y el punto mas alto de cada rueda se
    arma la perspectiva que los lleva a eso, y se aplica a todo."""
    (xa, ya, ra, aa), (xb, yb, rb, ab) = spec["ruedas"]
    r = max(ra, rb)
    distancia = spec["ejes_sobre_radio"] * r * (1 if xa > xb else -1)
    f = homografia(
        [(xa, ya), (xa, ya - ra), (xb, yb), (xb, yb - rb)],
        [(xa, ya), (xa, ya - r), (xa - distancia, ya), (xa - distancia, ya - r)],
    )
    nuevo = dict(spec)
    puntos = lambda lista: [tuple(round(c, 1) for c in f(x, y)) for x, y in lista]  # noqa: E731
    for clave in ("techo", "cola_abajo", "frente_abajo", "ventana"):
        if spec.get(clave):
            nuevo[clave] = puntos(spec[clave])
    nuevo["formas"] = {c: [(puntos(pts), rel) for pts, rel in v] for c, v in spec.get("formas", {}).items()}
    escala_arco = lambda arco, radio: arco / radio * r  # noqa: E731
    nuevo["ruedas"] = [(xa, ya, r, escala_arco(aa, ra)), (xa - distancia, ya, r, escala_arco(ab, rb))]
    nuevo["piso"] = f((xa + xb) / 2, spec["piso"])[1]
    nuevo["frente"] = f(spec["frente"], ya)[0]
    nuevo["cola"] = f(spec["cola"], ya)[0]
    nuevo["suelo"] = ya + r
    for clave in ("parantes", "puertas"):
        if spec.get(clave):
            nuevo[clave] = [f(x, ya - r)[0] for x in spec[clave]]
    if spec.get("asiento"):
        nuevo["asiento"] = f(*spec["asiento"])
    nuevo.pop("ejes_sobre_radio")
    return nuevo


def desde_puntos(spec: dict) -> str:
    """La Silueta a partir de puntos marcados a mano sobre una foto (para
    autos que no se separan del fondo por color). `spec`, en pixeles de la
    foto: frente/cola (x de las puntas), suelo (y), techo (puntos de la trompa
    a la cola), cola_abajo, frente_abajo, ruedas [(cx, cy, radio, radio del
    arco)], piso (y del zocalo), ventana, parantes, puertas, asiento y, en
    `formas`, faro/luz/detalles como [(puntos, relleno)]."""
    if spec.get("ejes_sobre_radio"):  # foto casi de perfil: se rectifica la perspectiva
        spec = rectificar(spec)
    if spec.get("perspectiva"):  # (aproximado) la rueda de atras se ve mas chica y mas alta: se endereza
        (xa, ya, ra, aa), (xb, yb, rb, ab) = spec["ruedas"]
        k = ((ya + ra) - (yb + rb)) / (xa - xb)  # cuanto sube el apoyo por pixel hacia atras
        enderezar = lambda puntos: [(x, y - k * (x - xa)) for x, y in puntos]  # noqa: E731
        spec = dict(spec)
        for clave in ("techo", "cola_abajo", "frente_abajo", "ventana"):
            if spec.get(clave):
                spec[clave] = enderezar(spec[clave])
        spec["formas"] = {c: [(enderezar(pts), rel) for pts, rel in v] for c, v in spec.get("formas", {}).items()}
        r, arco = max(ra, rb), max(aa, ab)
        spec["ruedas"] = [(xa, ya + ra - r, r, arco), (xb, yb - k * (xb - xa) + rb - r, r, arco)]
        spec["piso"] = spec["piso"] - k * ((xa + xb) / 2 - xa)
    # "voltear": el auto de la foto mira a la derecha (frente > cola): se espeja
    largo = abs(spec["cola"] - spec["frente"])
    escala = (X1 - X0) / largo
    # un auto alto (un todoterreno) no cabe a lo ancho: se achica hasta que el techo entre, y se centra
    alto = spec["suelo"] - min(y for _, y in spec["techo"])
    escala = min(escala, (SUELO - TECHO_MINIMO) / alto)
    inicio = (X0 + X1) / 2 - largo * escala / 2
    signo = -1 if spec["frente"] > spec["cola"] else 1
    X = lambda x: round(inicio + (x - spec["frente"]) * signo * escala, 1)  # noqa: E731
    Y = lambda y: round(SUELO - (spec["suelo"] - y) * escala, 1)  # noqa: E731
    P = lambda puntos: [(X(x), Y(y)) for x, y in puntos]  # noqa: E731
    piso = Y(spec["piso"])
    ruedas = [(X(cx), Y(cy), round(arco * escala, 1)) for cx, cy, _, arco in spec["ruedas"]]
    cuerpo = armar_cuerpo(P(spec["techo"]), P(spec.get("cola_abajo", [])), ruedas, piso, P(spec.get("frente_abajo", [])))
    ventana = "M " + " L ".join(f"{x} {y}" for x, y in P(spec["ventana"])) + " Z"
    tire = [(X(cx), round(SUELO - r * escala, 1), round(r * escala, 1)) for cx, _, r, _ in spec["ruedas"]]

    def forma(lista):
        return "".join(
            f'<path d="M {" L ".join(f"{x} {y}" for x, y in P(puntos))} Z" fill="{relleno}"/>' for puntos, relleno in lista
        )

    formas = spec.get("formas", {})
    techo = min(y for _, y in P(spec["techo"]))
    base = round(statistics.mean(sorted(y for _, y in P(spec["ventana"]))[-2:]), 1)  # la cintura: lo mas bajo
    asiento = spec.get("asiento")
    lineas = [cuerpo[i:i + 100] for i in range(0, len(cuerpo), 100)]
    texto = "\n".join(f'        "{t}"' for t in lineas)
    extras = []
    if spec.get("parantes"):
        extras.append(f"parantes={tuple(X(x) for x in spec['parantes'])}")
    if spec.get("puertas"):
        extras.append(f"puertas={tuple(X(x) for x in spec['puertas'])}")
    for clave in ("faro", "luz", "detalles", "aleron"):
        dibujo = forma(formas.get(clave, [])) + "".join(formas.get(clave + "_svg", []))  # *_svg: ya en el dibujo
        if dibujo:
            extras.append(f"{clave}='{dibujo}'")
    extras.append(f"piso={piso}")
    extras.append(f"arcos={tuple(ruedas)}")
    cola = max(x for x, _ in P(spec.get("cola_abajo") or spec["techo"][-1:]))
    if cola < X1 - 2:  # la cola no llega al borde (un auto alto, centrado): ahi va el escape
        extras.append(f"cola={cola}")
    return (
        f'    "{spec["nombre"]}": Silueta(\n{texto},\n        "{ventana}",\n'
        f"        {tuple(tire)}, {techo}, {base}, {(X(asiento[0]), Y(asiento[1])) if asiento else (200, techo + 12)},\n"
        + "".join(f"        {e},\n" for e in extras) + "    ),"
    )


def insertar(codigo: str, fuente: str, modelos: list) -> str:
    """Pega la Silueta en ui/configurador.py:SILUETAS (reemplaza la de ese
    nombre si ya estaba) con la foto de origen como comentario, y se la
    asigna a los modelos de servicios/autos.py."""
    raiz = Path(__file__).resolve().parents[1]
    nombre = re.search(r'"(\w+)": Silueta\(', codigo).group(1)
    bloque = f"    # {fuente}\n{codigo}\n"
    archivo = raiz / "roleplay/ui/configurador.py"
    texto = archivo.read_text(encoding="utf-8")
    patron = re.compile(r"    # [^\n]*\n    \"" + nombre + r"\": Silueta\(.*?\n    \),\n", re.S)
    if patron.search(texto):
        texto = patron.sub(lambda _: bloque, texto, count=1)
    else:
        texto = texto.replace("SILUETAS = {\n", "SILUETAS = {\n" + bloque, 1)
    archivo.write_text(texto, encoding="utf-8")
    archivo = raiz / "roleplay/servicios/autos.py"
    texto = archivo.read_text(encoding="utf-8")
    for modelo in modelos:
        texto, n = re.subn(r'(Modelo\("' + modelo + r'", "[^"]+", "[^"]+", )"[^"]+"', r'\g<1>"' + nombre + '"', texto)
        if n != 1:
            raise SystemExit(f"no encontre el modelo {modelo} en servicios/autos.py")
    archivo.write_text(texto, encoding="utf-8")
    return nombre


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("medidas", help="JSON del navegador (o, con --puntos, los puntos marcados a mano)")
    parser.add_argument("--puntos", action="store_true", help="el archivo trae puntos marcados a mano (ver desde_puntos)")
    parser.add_argument("--cola", type=float, default=0.0)
    parser.add_argument("--nombre", default="auto")
    parser.add_argument("--json", action="store_true", help="salida en JSON en vez de codigo")
    parser.add_argument("--insertar", nargs="+", metavar="MODELO",
                        help="(con --puntos) pegarla en SILUETAS y asignarsela a estos modelos de autos.py")
    parser.add_argument("--fuente", default="", help="la foto de origen, queda como comentario arriba de la silueta")
    args = parser.parse_args()
    with open(args.medidas, encoding="utf-8") as archivo:
        medidas = json.loads(archivo.read())
    if isinstance(medidas, str):  # tal cual lo devuelve el navegador
        medidas = json.loads(medidas)
    if args.puntos:
        codigo = desde_puntos(medidas)
        if args.insertar:
            print("ok", insertar(codigo, args.fuente or args.medidas, args.insertar), args.insertar)
        else:
            print(codigo)
        return
    silueta = trazar(medidas, cola=args.cola)
    print(json.dumps(silueta) if args.json else como_codigo(args.nombre, silueta))


if __name__ == "__main__":
    sys.exit(main())
