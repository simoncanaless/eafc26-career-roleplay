"""
Bytes del guardado -> registros. Nada de aca sabe de futbol: solo del
formato. Todo valida lo que lee (firmas, fechas, indices): un parche del
juego que mueva algo tiene que dar FormatoDesconocido, no datos basura.

Estructura (detalle en docs/partida-fc26.md):
- Bases de datos de EA (firma DB\\0\\x08...): tablas con codigos de 4 letras
  y registros empaquetados en bits (LSB primero).
- Secciones de carrera: [largo][00 00 00][nombre en minusculas] y sus datos.
"""

import re
import struct
from dataclasses import dataclass
from typing import Optional

FIRMA_BASE = b"DB\x00\x08\x00\x00\x00\x00"
PATRON_SECCION = re.compile(rb"([\x04-\x10])\x00\x00\x00([a-z]{4,16})\x01")
MARCA = b"\xff\x01"

TIPO_TEXTO, TIPO_ENTERO, TIPO_REAL = 0, 3, 4

TAM_PARTIDO = 22
TAM_FILA_TABLA = 23
TAM_ESTADISTICA = 73
TAM_COMPETICION = 49
ULTIMOS_PARTIDOS = 5


class FormatoDesconocido(RuntimeError):
    """El guardado no tiene la forma esperada (otra version del juego, otro
    tipo de partida, o un archivo cortado mientras el juego lo escribia)."""


def bits(bloque: bytes, desde: int, ancho: int) -> int:
    return (int.from_bytes(bloque, "little") >> desde) & ((1 << ancho) - 1)


def nombre_partida(datos: bytes) -> str:
    if not datos.startswith(b"FBCHUNKS"):
        raise FormatoDesconocido("No es un guardado de FC (falta la cabecera FBCHUNKS).")
    fin = datos.find(b"\x00", 18, 18 + 256)
    return datos[18:fin].decode("utf-8", "replace") if fin > 18 else ""


# ---- bases de datos de EA ----


@dataclass(frozen=True)
class Campo:
    codigo: str
    tipo: int
    bit: int
    ancho: int


@dataclass
class Tabla:
    codigo: str
    campos: list[Campo]
    registros: list[dict]

    def campo(self, codigo: str) -> Optional[Campo]:
        return next((c for c in self.campos if c.codigo == codigo), None)


def buscar_bases(datos: bytes) -> list[int]:
    posiciones, inicio = [], 0
    while (i := datos.find(FIRMA_BASE, inicio)) >= 0:
        posiciones.append(i)
        largo = struct.unpack_from("<I", datos, i + 8)[0]
        inicio = i + max(largo, len(FIRMA_BASE))
    return posiciones


def codigos_de_tablas(datos: bytes, base: int) -> list[str]:
    cantidad = struct.unpack_from("<I", datos, base + 16)[0]
    return [datos[base + 24 + 8 * t: base + 28 + 8 * t].decode("latin-1") for t in range(cantidad)]


def leer_tablas(datos: bytes, base: int, codigos: Optional[set] = None) -> dict[str, Tabla]:
    """Las tablas de la base que empieza en `base` (solo `codigos` si se
    dice: leer las 33 tablas completas tarda ~1 s)."""
    largo, _, cantidad = struct.unpack_from("<III", datos, base + 8)
    if cantidad > 4096 or base + largo > len(datos):
        raise FormatoDesconocido("Base de datos con cabecera invalida.")
    directorio = [struct.unpack_from("<4sI", datos, base + 24 + 8 * t) for t in range(cantidad)]
    origen = base + 28 + 8 * cantidad
    tablas = {}
    for codigo_crudo, desplazamiento in directorio:
        codigo = codigo_crudo.decode("latin-1")
        if codigos is not None and codigo not in codigos:
            continue
        inicio = origen + desplazamiento
        tam_registro = struct.unpack_from("<I", datos, inicio + 4)[0]
        escritos = struct.unpack_from("<H", datos, inicio + 18)[0]
        n_campos = datos[inicio + 24]
        campos = []
        for c in range(n_campos):
            tipo, bit, corto, ancho = struct.unpack_from("<ii4si", datos, inicio + 36 + 16 * c)
            campos.append(Campo(corto.decode("latin-1"), tipo, bit, ancho))
        primero = inicio + 36 + 16 * n_campos
        registros = []
        for r in range(escritos):
            crudo = datos[primero + r * tam_registro: primero + (r + 1) * tam_registro]
            if not crudo or crudo[-1] == 0x80:  # registro borrado
                continue
            entero = int.from_bytes(crudo, "little")
            fila = {}
            for campo in campos:
                if campo.tipo == TIPO_ENTERO:
                    fila[campo.codigo] = (entero >> campo.bit) & ((1 << campo.ancho) - 1)
                elif campo.tipo == TIPO_TEXTO:
                    texto = crudo[campo.bit // 8: campo.bit // 8 + campo.ancho // 8]
                    fila[campo.codigo] = texto.split(b"\x00")[0].decode("utf-8", "replace")
                elif campo.tipo == TIPO_REAL:
                    fila[campo.codigo] = struct.unpack_from("<f", crudo, campo.bit // 8)[0]
            registros.append(fila)
        tablas[codigo] = Tabla(codigo, campos, registros)
    return tablas


def base_con_tabla(datos: bytes, codigo: str) -> int:
    for base in buscar_bases(datos):
        if codigo in codigos_de_tablas(datos, base):
            return base
    raise FormatoDesconocido(f"No encontre la tabla {codigo} en el guardado.")


# ---- secciones de carrera ----


def secciones(datos: bytes) -> dict[str, tuple[int, int]]:
    """nombre -> (inicio, fin). Si un nombre se repite, vale la primera."""
    encontradas = [
        (m.group(2).decode(), m.start())
        for m in PATRON_SECCION.finditer(datos)
        if m.group(1)[0] == len(m.group(2))
    ]
    limites = {}
    for k, (nombre, inicio) in enumerate(encontradas):
        fin = encontradas[k + 1][1] if k + 1 < len(encontradas) else len(datos)
        limites.setdefault(nombre, (inicio, fin))
    return limites


def seccion(limites: dict, nombre: str) -> tuple[int, int]:
    if nombre not in limites:
        raise FormatoDesconocido(f"No encontre la seccion '{nombre}' en el guardado.")
    return limites[nombre]


@dataclass(frozen=True)
class FilaTabla:
    indice: int
    grupo: int
    equipo: Optional[int]


def leer_filas_de_tabla(datos: bytes, inicio: int, fin: int) -> dict[int, FilaTabla]:
    """Filas de 23 bytes (FF 01 + indice correlativo desde 1): con ellas los
    partidos dicen que equipo jugo."""
    for desde in range(inicio, fin - 2 * TAM_FILA_TABLA):
        if (
            datos[desde: desde + 2] == MARCA
            and struct.unpack_from("<H", datos, desde + 2)[0] == 1
            and datos[desde + TAM_FILA_TABLA: desde + TAM_FILA_TABLA + 2] == MARCA
            and struct.unpack_from("<H", datos, desde + TAM_FILA_TABLA + 2)[0] == 2
        ):
            break
    else:
        raise FormatoDesconocido("No encontre las tablas de posiciones de la carrera.")
    filas, esperado, i = {}, 1, desde
    while i + TAM_FILA_TABLA <= fin and datos[i: i + 2] == MARCA and struct.unpack_from("<H", datos, i + 2)[0] == esperado:
        grupo, equipo = struct.unpack_from("<Hi", datos, i + 4)
        filas[esperado] = FilaTabla(esperado, grupo, equipo if equipo >= 0 else None)
        esperado += 1
        i += TAM_FILA_TABLA
    return filas


def fecha_valida(valor: int) -> bool:
    return 19000101 <= valor <= 29991231 and 1 <= valor // 100 % 100 <= 12 and 1 <= valor % 100 <= 31


@dataclass(frozen=True)
class RegistroPartido:
    indice: int
    competicion: int
    ronda: int
    fecha: int  # AAAAMMDD
    hora: int  # HHMM
    fila_local: int
    goles_local: int
    fila_visita: int
    goles_visita: int
    jugado: bool


def leer_partidos(datos: bytes, inicio: int, fin: int, filas: dict) -> list[RegistroPartido]:
    """Registros de 22 bytes con FF 01; los que no validan (fecha, hora,
    filas de tabla existentes) se saltan: entre medio hay otros datos."""
    partidos = []
    zona = datos[inicio:fin]
    for m in re.finditer(re.escape(MARCA), zona):
        i = inicio + m.start()
        if i + TAM_PARTIDO > fin:
            break
        indice, competicion, ronda = struct.unpack_from("<HHB", datos, i + 2)
        fecha, hora = struct.unpack_from("<IH", datos, i + 7)
        local, goles_local, _, visita, goles_visita, _ = struct.unpack_from("<HBBHBB", datos, i + 13)
        jugado = datos[i + 21]
        if (
            fecha_valida(fecha) and hora < 2400 and hora % 100 < 60 and jugado in (0, 1)
            and local in filas and visita in filas and local != visita
        ):
            partidos.append(
                RegistroPartido(indice, competicion, ronda, fecha, hora, local, goles_local, visita, goles_visita, bool(jugado))
            )
    return partidos


@dataclass(frozen=True)
class RegistroActuacion:
    fecha: int  # AAAAMMDD
    minutos: int
    nota: Optional[float]
    goles: int
    posicion: Optional[int]


@dataclass(frozen=True)
class RegistroEstadistica:
    jugador: int
    equipo: int
    competicion: int
    partidos: int
    minutos: int
    nota_total: int  # decimas
    goles: int
    amarillas: int
    rojas: int
    asistencias: int
    figura: int
    ultimos: tuple  # RegistroActuacion, del mas viejo al mas nuevo


def _ultimos(registro: bytes) -> tuple:
    entradas = []
    for k in range(ULTIMOS_PARTIDOS):
        entrada = registro[22 + 10 * k: 32 + 10 * k]
        fecha = bits(entrada, 3, 25)
        if not fecha or not fecha_valida(fecha):
            continue
        minutos, nota = bits(entrada, 35, 7), bits(entrada, 42, 7)
        posicion = bits(entrada, 64, 6)
        entradas.append(
            RegistroActuacion(
                fecha, minutos, nota / 10 if minutos and nota else None, bits(entrada, 50, 3),
                posicion - 1 if posicion else None,
            )
        )
    return tuple(sorted(entradas, key=lambda e: e.fecha))


def leer_estadisticas(datos: bytes, inicio: int, fin: int) -> list[RegistroEstadistica]:
    """Registros de 73 bytes (01 01) seguidos: uno por jugador, equipo y
    competicion. Se busca la primera racha de tres y se lee hasta que corta."""
    for desde in range(inicio, min(fin, inicio + 4096)):
        if all(datos[desde + k * TAM_ESTADISTICA: desde + k * TAM_ESTADISTICA + 2] == b"\x01\x01" for k in range(3)):
            break
    else:
        raise FormatoDesconocido("No encontre las estadisticas de jugadores de la carrera.")
    lista, i = [], desde
    while i + TAM_ESTADISTICA <= fin and datos[i: i + 2] == b"\x01\x01":
        r = datos[i: i + TAM_ESTADISTICA]
        jugador = bits(r, 34, 19) - 1
        if jugador >= 0:
            lista.append(
                RegistroEstadistica(
                    jugador=jugador,
                    equipo=bits(r, 16, 18) - 1,
                    competicion=bits(r, 53, 11),
                    partidos=bits(r, 130, 8),
                    minutos=bits(r, 69, 15),
                    nota_total=bits(r, 84, 12),
                    goles=bits(r, 108, 9),
                    amarillas=bits(r, 117, 7),
                    rojas=bits(r, 124, 6),
                    asistencias=bits(r, 138, 8),
                    figura=bits(r, 146, 8),
                    ultimos=_ultimos(r),
                )
            )
        i += TAM_ESTADISTICA
    return lista


@dataclass(frozen=True)
class RegistroCompeticion:
    id: int
    nivel: int  # 1 confederacion, 2 pais, 3 competicion, 4 fase, 5 grupo
    padre: Optional[int]
    codigo: str  # ej. "C13" (13 = id de la liga en la tabla de ligas)


def _imprimible(texto: bytes) -> bool:
    texto = texto.split(b"\x00")[0]
    return bool(texto) and all(0x20 <= b <= 0x7E for b in texto)


def leer_competiciones(datos: bytes, inicio: int = 0, fin: Optional[int] = None) -> dict[int, RegistroCompeticion]:
    fin = len(datos) if fin is None else fin
    competiciones = {}
    zona = datos[inicio:fin]
    for m in re.finditer(re.escape(MARCA), zona):
        i = inicio + m.start()
        if i + TAM_COMPETICION > fin:
            break
        ident, copia, nivel, padre = struct.unpack_from("<HHBH", datos, i + 2)
        if ident == copia and 1 <= nivel <= 9 and _imprimible(datos[i + 9: i + 16]) and _imprimible(datos[i + 16: i + 49]):
            competiciones[ident] = RegistroCompeticion(
                ident, nivel, None if padre in (0, 0xFFFF) else padre,
                datos[i + 9: i + 16].split(b"\x00")[0].decode("ascii"),
            )
    return competiciones
