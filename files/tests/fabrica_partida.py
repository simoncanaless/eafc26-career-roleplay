"""
Arma un guardado de carrera de FC 26 FALSO, chico, con el mismo formato
que el real (docs/partida-fc26.md), para probar el lector sin la partida
de nadie.

Mundo de la partida falsa (fecha del juego: 2027-01-16):
- Liga C13 "Premier League" (competicion 808, de Inglaterra) y "Champions"
  (competicion 122, continental, sin nombre en la partida).
- Equipos: Man Utd (11), Manchester City (10), Arsenal (1), Liverpool (9),
  Sunderland (106), Napoli (48) y la seleccion Noruega (1352).
- El usuario: "Simon Canales", jugador 30999, del Man Utd.
"""

import struct
from datetime import date

from roleplay.partida.carrera import ORIGEN_FECHAS

USUARIO = 30999
HAALAND = 239085
BRUNO = 212198
DELANTERO_ARSENAL = 250001
MAN_UTD, CITY, ARSENAL, LIVERPOOL, SUNDERLAND, NAPOLI, NORUEGA = 11, 10, 1, 9, 106, 48, 1352
LIGA, CHAMPIONS = 808, 122
NOMBRES_EQUIPOS = {
    MAN_UTD: "Man Utd", CITY: "Manchester City", ARSENAL: "Arsenal", LIVERPOOL: "Liverpool",
    SUNDERLAND: "Sunderland", NAPOLI: "SSC Napoli", NORUEGA: "Noruega",
}
# equipos que no juegan nada en la partida (no tienen fila en las tablas)
AGENTES_LIBRES, ARSENAL_FEM, CHELSEA_FEM = 111592, 115000, 115001
EQUIPOS_SIN_PARTIDOS = {AGENTES_LIBRES: "Agentes libres", ARSENAL_FEM: "Arsenal", CHELSEA_FEM: "Chelsea"}
# liga de cada equipo, como la guarda EA (id - 1): Premier 12, Serie A 30,
# selecciones 77, agentes libres 381, WSL 2214
LIGA_DE_EQUIPO = {
    MAN_UTD: 12, CITY: 12, ARSENAL: 12, LIVERPOOL: 12, SUNDERLAND: 12, NAPOLI: 30, NORUEGA: 77,
    AGENTES_LIBRES: 381, ARSENAL_FEM: 2214, CHELSEA_FEM: 2214,
}

# (fecha, competicion, local, visita, goles_local, goles_visita, jugado)
PARTIDOS = [
    (20270102, LIGA, MAN_UTD, ARSENAL, 2, 1, True),
    (20270102, LIGA, CITY, LIVERPOOL, 4, 0, True),  # goleada con hat-trick de Haaland
    (20270109, LIGA, ARSENAL, CITY, 1, 1, True),
    (20270109, LIGA, LIVERPOOL, SUNDERLAND, 1, 0, True),
    (20270112, CHAMPIONS, MAN_UTD, NAPOLI, 3, 3, True),
    (20270116, LIGA, MAN_UTD, SUNDERLAND, 5, 3, True),  # el ultimo del usuario
    (20270116, LIGA, CITY, ARSENAL, 2, 0, True),
    (20270120, CHAMPIONS, NAPOLI, MAN_UTD, 0, 0, False),  # el proximo
]

# estadisticas: (jugador, equipo, competicion, partidos, minutos, nota_total,
# goles, amarillas, rojas, asistencias, figura, ultimos[(fecha, min, nota, goles, posicion)])
ESTADISTICAS = [
    (USUARIO, MAN_UTD, LIGA, 2, 180, 190, 6, 0, 0, 2, 2,
     [(20270102, 90, 9.0, 1, 25), (20270116, 90, 10.0, 5, 25)]),
    (USUARIO, MAN_UTD, CHAMPIONS, 1, 90, 85, 2, 1, 0, 1, 0, [(20270112, 90, 8.5, 2, 25)]),
    (BRUNO, MAN_UTD, LIGA, 2, 170, 150, 1, 0, 0, 3, 0,
     [(20270102, 85, 7.5, 1, 18), (20270116, 85, 7.5, 0, 18)]),
    (HAALAND, CITY, LIGA, 3, 270, 255, 5, 0, 0, 0, 1,
     [(20270102, 90, 9.6, 3, 25), (20270109, 90, 7.0, 1, 25), (20270116, 90, 8.9, 1, 25)]),
    (DELANTERO_ARSENAL, ARSENAL, LIGA, 3, 270, 210, 2, 0, 0, 0, 0,
     [(20270102, 90, 7.0, 1, 25), (20270109, 90, 7.4, 1, 25), (20270116, 90, 6.0, 0, 25)]),
]

JUGADORA = 300001
SUPLENTE_CITY = 250002
# jugador -> (fecha de nacimiento, [(equipo, posicion)])
JUGADORES = {
    USUARIO: (date(2003, 4, 4), [(MAN_UTD, 25)]),
    BRUNO: (date(1994, 9, 8), [(MAN_UTD, 18)]),
    HAALAND: (date(2000, 7, 21), [(CITY, 25), (NORUEGA, 25)]),
    DELANTERO_ARSENAL: (date(2001, 1, 1), [(ARSENAL, 25)]),
    SUPLENTE_CITY: (date(2004, 5, 5), [(CITY, 28)]),
    JUGADORA: (date(1998, 2, 2), [(ARSENAL_FEM, 25)]),
}
SUELDO = 145_000  # por semana, el del usuario
MEDIAS = {USUARIO: 79, BRUNO: 86, HAALAND: 92, DELANTERO_ARSENAL: 76, SUPLENTE_CITY: 64, JUGADORA: 88}
POSICION_PREFERIDA = {SUPLENTE_CITY: 3}  # suplente (28) en el plantel; lateral derecho de preferencia


# ---- base de datos de EA ----


def _tabla(campos: list[tuple[str, int, int]], filas: list[dict]) -> bytes:
    """campos: (codigo, tipo, ancho). Textos alineados a byte."""
    descriptores, bit = [], 0
    for codigo, tipo, ancho in campos:
        if tipo == 0:
            bit = (bit + 7) // 8 * 8
        descriptores.append((codigo, tipo, bit, ancho))
        bit += ancho
    tam = (bit + 7) // 8 + 1  # un byte de relleno: el ultimo nunca es 0x80 (borrado)
    registros = b""
    for fila in filas:
        entero, crudo = 0, bytearray(tam)
        for codigo, tipo, desde, ancho in descriptores:
            if tipo == 3:
                entero |= (fila.get(codigo, 0) & ((1 << ancho) - 1)) << desde
        crudo[:] = entero.to_bytes(tam, "little")
        for codigo, tipo, desde, ancho in descriptores:
            if tipo == 0:
                texto = fila.get(codigo, "").encode()[: ancho // 8 - 1]
                crudo[desde // 8: desde // 8 + len(texto)] = texto
        registros += bytes(crudo)
    cabecera = struct.pack("<IIIIHHHHB7sI", 0, tam, bit, 0, len(filas), len(filas), 0, 0, len(campos), b"\x00" * 7, 0)
    return cabecera + b"".join(struct.pack("<ii4si", tipo, desde, codigo.encode(), ancho) for codigo, tipo, desde, ancho in descriptores) + registros


def _base(tablas: dict[str, bytes]) -> bytes:
    cuerpo, directorio = b"", b""
    for codigo, datos in tablas.items():
        directorio += struct.pack("<4sI", codigo.encode(), len(cuerpo))
        cuerpo += datos
    largo = 28 + len(directorio) + len(cuerpo)
    return b"DB\x00\x08\x00\x00\x00\x00" + struct.pack("<IIII", largo, 0, len(tablas), 0) + directorio + b"\x00" * 4 + cuerpo


def _seccion(nombre: str, datos: bytes, terminador: bool = True) -> bytes:
    return bytes([len(nombre)]) + b"\x00\x00\x00" + nombre.encode() + (b"\x01" if terminador else b"") + datos


def _bits(valores: list[tuple[int, int, int]], tam: int, base: int = 0) -> bytes:
    entero = base
    for valor, desde, ancho in valores:
        entero |= (valor & ((1 << ancho) - 1)) << desde
    return entero.to_bytes(tam, "little")


# Lo que cambia cuando el usuario juega un partido mas (modo en vivo)
PARTIDO_NUEVO = (20270123, LIGA, MAN_UTD, ARSENAL, 2, 1, True)
ACTUACION_NUEVA = (20270123, 90, 8.8, 2, 25)


def construir_bytes(
    nombre_partida: str = "Carrera - Prog. de Futbolista 1", partido_nuevo: bool = False,
    fichajes: dict | None = None, otros_partidos: list | None = None, etapas: bool = False,
    jugador_del_mes: int = 5,
) -> bytes:
    """`partido_nuevo`: la misma partida despues de que el usuario jugo el
    Man Utd 2-1 Arsenal del 23-01-2027 (2 goles suyos, 1 asistencia).
    `fichajes`: {jugador: club nuevo} (el resto de sus vinculos queda igual).
    `otros_partidos`: partidos de mas, con el formato de PARTIDOS (ej. de
    otros equipos: el juego avanzo de dia sin que juegue el usuario)."""
    fichajes = fichajes or {}
    partidos_lista = list(PARTIDOS) + list(otros_partidos or [])
    estadisticas_lista = list(ESTADISTICAS)
    if partido_nuevo:
        partidos_lista.insert(-1, PARTIDO_NUEVO)
        jugador, equipo, comp, pj, minutos, nota, goles, ta, tr, ast, fig, ultimos = estadisticas_lista[0]
        estadisticas_lista[0] = (jugador, equipo, comp, pj + 1, minutos + 90, nota + 88, goles + 2, ta, tr,
                                 ast + 1, fig, ultimos + [ACTUACION_NUEVA])
    mundo = _base({
        "lyxL": _tabla([("mCXg", 3, 18), ("AUsv", 0, 240)],
                       [{"mCXg": i - 1, "AUsv": n} for i, n in {**NOMBRES_EQUIPOS, **EQUIPOS_SIN_PARTIDOS}.items()]),
        "CZUM": _tabla([("ykFq", 3, 19), ("WVIU", 3, 18), ("UERs", 3, 7), ("mpuH", 3, 7), ("EveZ", 3, 1),
                        ("wZQU", 3, 5)],
                       [{"ykFq": j, "WVIU": (nac - ORIGEN_FECHAS).days, "UERs": MEDIAS[j], "mpuH": MEDIAS[j] + 3,
                         "EveZ": int(j == JUGADORA), "wZQU": POSICION_PREFERIDA.get(j, vs[0][1])}
                        for j, (nac, vs) in JUGADORES.items()]),
        "RrqT": _tabla([("ykFq", 3, 19), ("mCXg", 3, 18), ("vjla", 3, 6)],
                       [{"ykFq": j, "mCXg": (fichajes[j] if j in fichajes and n == 0 else e) - 1, "vjla": pos}
                        for j, (_, vs) in JUGADORES.items() for n, (e, pos) in enumerate(vs)]),
        "qdZF": _tabla([("aQrQ", 3, 12), ("mCXg", 3, 18)],
                       [{"aQrQ": liga, "mCXg": e - 1} for e, liga in LIGA_DE_EQUIPO.items()]),
        "onMQ": _tabla([("aQrQ", 3, 12), ("HEQX", 0, 240)], [{"aQrQ": 12, "HEQX": "Premier League"}]),
        "nQVU": _tabla([("HdeP", 0, 240), ("xnfZ", 0, 240), ("rREd", 0, 240), ("ykFq", 3, 19)],
                       [{"HdeP": "Andres", "xnfZ": "A. Iniesta", "rREd": "Iniesta", "ykFq": 41},
                        {"HdeP": "Simon", "xnfZ": "", "rREd": "Canales", "ykFq": USUARIO}]),
    })
    tablas_carrera = {"mPrV": _tabla([("HdeP", 0, 240), ("rREd", 0, 240), ("XGBd", 3, 12), ("cmGX", 3, 31)],
                                     [{"HdeP": "Simon", "rREd": "Canales", "XGBd": LIGA, "cmGX": SUELDO}])}
    if etapas:  # la carrera entera: primero el Arsenal (salio campeon de la liga), despues el Man Utd
        campos = [("vojK", 3, 4), ("mCXg", 3, 18), ("aQrQ", 3, 12), ("nVWT", 3, 12), ("zjtP", 3, 12), ("EBvI", 3, 12),
                  ("BsgO", 3, 12), ("MERA", 3, 12), ("xEsZ", 3, 12), ("isoi", 3, 8), ("OcFS", 3, 12), ("cmGX", 3, 31), ("SbfX", 3, 31),
                  ("qnUa", 3, 8)]
        tablas_carrera["YMgA"] = _tabla(campos, [  # club y liga corridos en 1, como en el juego
            {"vojK": 1, "mCXg": ARSENAL + 1, "aQrQ": 14, "nVWT": 42, "zjtP": 33, "EBvI": 7, "BsgO": 2, "MERA": 152,
             "xEsZ": 35, "isoi": 0, "OcFS": 34, "cmGX": 4100, "SbfX": 7_500_000, "qnUa": 88},
            {"vojK": 2, "mCXg": MAN_UTD + 1, "aQrQ": 14, "nVWT": 36, "zjtP": 30, "EBvI": 1, "BsgO": 5, "MERA": 112,
             "xEsZ": 26, "isoi": 3, "OcFS": 29, "cmGX": SUELDO, "SbfX": 44_000_000, "qnUa": 87}])
        tablas_carrera["NgwF"] = _tabla([("vojK", 3, 4), ("mCXg", 3, 18), ("OvfW", 3, 12), ("SDel", 3, 1)], [
            {"vojK": 1, "mCXg": ARSENAL, "OvfW": LIGA, "SDel": 1},
            {"vojK": 2, "mCXg": MAN_UTD, "OvfW": LIGA, "SDel": 0}, {"vojK": 2, "mCXg": MAN_UTD, "OvfW": CHAMPIONS}])
        tablas_carrera["cPet"] = _tabla([("vojK", 3, 4), ("Bwgx", 3, 4), ("ytjZ", 3, 8), ("ykFq", 3, 19)], [
            {"vojK": 1, "Bwgx": 0, "ytjZ": 21, "ykFq": USUARIO}, {"vojK": 1, "Bwgx": 1, "ytjZ": 7, "ykFq": USUARIO},
            {"vojK": 1, "Bwgx": 2, "ytjZ": 2, "ykFq": USUARIO},  # sin confirmar: no se muestra
            {"vojK": 2, "Bwgx": 0, "ytjZ": 15, "ykFq": USUARIO},
            {"vojK": 2, "Bwgx": 1, "ytjZ": jugador_del_mes, "ykFq": USUARIO}])
    carrera = _base(tablas_carrera)

    # tablas de posiciones: una fila por equipo y competicion (indices desde 1)
    filas, indice_de = b"", {}
    for competicion, grupo in ((LIGA, 1), (CHAMPIONS, 2)):
        for equipo in sorted(NOMBRES_EQUIPOS):
            if equipo == NORUEGA:
                continue
            indice = len(indice_de) + 1
            indice_de[(competicion, equipo)] = indice
            filas += struct.pack("<2sHHiB5s5sBB", b"\xff\x01", indice, grupo, equipo, 0, bytes(5), bytes(5), 0, 0)

    partidos = b"basura" + bytes(9)
    for n, (fecha, comp, local, visita, gl, gv, jugado) in enumerate(partidos_lista, start=1):
        partidos += struct.pack(
            "<2sHHBIHHBBHBBB", b"\xff\x01", n, comp, 1, fecha, 2000,
            indice_de[(comp, local)], gl, 0, indice_de[(comp, visita)], gv, 0, int(jugado),
        )
        partidos += b"\x07\x07\x07"  # datos entre medio, como en el real

    estadisticas = b""
    for jugador, equipo, comp, pj, minutos, nota, goles, ta, tr, ast, fig, ultimos in estadisticas_lista:
        cabeza = _bits(
            [(equipo + 1, 16, 18), (jugador + 1, 34, 19), (comp, 53, 11), (minutos, 69, 15), (nota, 84, 12),
             (goles, 108, 9), (ta, 117, 7), (tr, 124, 6), (pj, 130, 8), (ast, 138, 8), (fig, 146, 8)],
            22, base=0x0101,
        )
        entradas = b"".join(
            _bits([(f, 3, 25), (m, 35, 7), (round(nt * 10), 42, 7), (g, 50, 3), (pos + 1, 64, 6)], 10)
            for f, m, nt, g, pos in ultimos
        )
        estadisticas += cabeza + entradas.ljust(50, b"\x00") + b"\x00"
    estadisticas += b"\x99" * 80  # fin de la racha

    competiciones = b""
    for ident, nivel, padre, codigo in ((497, 2, 0, "N14"), (84, 1, 0, "UEFA"), (LIGA, 3, 497, "C13"), (CHAMPIONS, 3, 84, "C223")):
        competiciones += struct.pack("<2sHHBH7s33s", b"\xff\x01", ident, ident, nivel, padre, codigo.encode(), f"Nombre_{codigo}".encode())

    cabecera = b"FBCHUNKS" + bytes(10) + nombre_partida.encode() + b"\x00"
    cabecera = cabecera.ljust(512, b"\x00")
    return (
        cabecera + carrera + mundo
        + _seccion("compavg", competiciones)
        + _seccion("teams", partidos)
        + _seccion("stagadv", filas)
        + _seccion("stndgs", estadisticas, terminador=False)
        + _seccion("weather", b"\x00" * 16)
        + b"\x00" * 1024
    )
